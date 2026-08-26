# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging

import requests
from django.db.models import Max, Q
from requests.auth import HTTPBasicAuth

from plane.db.models import (
    Issue,
    IssueSequence,
    Label,
    Module,
    ModuleIssue,
    State,
)
from plane.utils.html_processor import strip_tags
from plane.utils.importers.jira import generate_url, generate_valid_project_key, is_allowed_hostname

logger = logging.getLogger(__name__)

STATUS_CATEGORY_MAP = {
    "new": "unstarted",
    "indeterminate": "started",
    "done": "completed",
}


def run_jira_import(importer):
    metadata = importer.metadata or {}
    data = importer.data or {}
    email = metadata.get("email") or data.get("email")
    api_token = metadata.get("api_token") or data.get("api_token")
    cloud_hostname = metadata.get("cloud_hostname")
    project_key = generate_valid_project_key(metadata.get("project_key") or data.get("project_key"))

    if not all([email, api_token, cloud_hostname, project_key]):
        raise ValueError("Jira import requires email, api_token, cloud_hostname and project_key")
    if not is_allowed_hostname(cloud_hostname):
        raise ValueError("Invalid Jira hostname")

    auth = HTTPBasicAuth(email, api_token)
    headers = {"Accept": "application/json"}
    project_id = importer.project_id
    workspace_id = importer.workspace_id
    actor = importer.initiated_by

    # States from Jira statuses
    status_url = generate_url(cloud_hostname, f"/rest/api/3/project/{project_key}/statuses")
    statuses = requests.get(status_url, headers=headers, auth=auth, timeout=60).json()
    state_map = {}
    for issue_type in statuses if isinstance(statuses, list) else []:
        for st in issue_type.get("statuses", []):
            name = st.get("name")
            category = (st.get("statusCategory") or {}).get("key", "new")
            group = STATUS_CATEGORY_MAP.get(category, "unstarted")
            state, _ = State.objects.get_or_create(
                project_id=project_id,
                name=name[:255],
                defaults={
                    "group": group,
                    "color": "#3f76ff",
                    "workspace_id": workspace_id,
                    "created_by": actor,
                },
            )
            state_map[name] = state.id

    default_state = (
        State.objects.filter(~Q(name="Triage"), project_id=project_id, default=True).first()
        or State.objects.filter(~Q(name="Triage"), project_id=project_id).first()
    )

    # Epics -> modules
    epic_jql = f"project={project_key} AND issuetype=Epic"
    epic_url = generate_url(cloud_hostname, f"/rest/api/3/search?jql={epic_jql}&maxResults=100")
    epics = requests.get(epic_url, headers=headers, auth=auth, timeout=60).json().get("issues", [])
    epic_module_map = {}
    imported_modules = []
    for epic in epics:
        fields = epic.get("fields") or {}
        module = Module.objects.create(
            name=(fields.get("summary") or epic.get("key"))[:255],
            description=fields.get("description") or "",
            project_id=project_id,
            workspace_id=workspace_id,
            created_by=actor,
        )
        epic_module_map[epic.get("key")] = module.id
        imported_modules.append(str(module.id))

    # Issues (non-epic)
    issue_jql = f"project={project_key} AND issuetype!=Epic"
    start_at = 0
    imported_issues = []
    last_id = IssueSequence.objects.filter(project_id=project_id).aggregate(largest=Max("sequence"))["largest"]
    last_id = 1 if last_id is None else last_id + 1

    while True:
        issue_url = generate_url(
            cloud_hostname,
            f"/rest/api/3/search?jql={issue_jql}&startAt={start_at}&maxResults=50",
        )
        payload = requests.get(issue_url, headers=headers, auth=auth, timeout=60).json()
        issues = payload.get("issues", [])
        if not issues:
            break

        for jira_issue in issues:
            fields = jira_issue.get("fields") or {}
            key = jira_issue.get("key")
            if Issue.objects.filter(project_id=project_id, external_source="jira", external_id=key).exists():
                continue
            status_name = (fields.get("status") or {}).get("name")
            state_id = state_map.get(status_name) or (default_state.id if default_state else None)
            description = fields.get("description")
            # description may be ADF; store as plain fallback
            if isinstance(description, dict):
                description_html = f"<p>{fields.get('summary') or ''}</p>"
            else:
                description_html = f"<p>{description or ''}</p>"

            issue = Issue.objects.create(
                project_id=project_id,
                workspace_id=workspace_id,
                name=(fields.get("summary") or key)[:255],
                description_html=description_html,
                description_stripped=strip_tags(description_html),
                state_id=state_id,
                sequence_id=last_id,
                created_by=actor,
                updated_by=actor,
                external_id=key,
                external_source="jira",
            )
            IssueSequence.objects.create(
                issue=issue,
                sequence=issue.sequence_id,
                project_id=project_id,
                workspace_id=workspace_id,
            )
            last_id += 1
            imported_issues.append(str(issue.id))

            parent = fields.get("parent") or {}
            parent_key = parent.get("key")
            if parent_key and parent_key in epic_module_map:
                ModuleIssue.objects.get_or_create(
                    module_id=epic_module_map[parent_key],
                    issue=issue,
                    project_id=project_id,
                    workspace_id=workspace_id,
                    defaults={"created_by": actor},
                )

            for label_name in fields.get("labels") or []:
                label, _ = Label.objects.get_or_create(
                    project_id=project_id,
                    name=str(label_name)[:255],
                    defaults={"color": "#003773", "workspace_id": workspace_id, "created_by": actor},
                )
                from plane.db.models import IssueLabel

                IssueLabel.objects.get_or_create(
                    issue=issue,
                    label=label,
                    project_id=project_id,
                    workspace_id=workspace_id,
                    defaults={"created_by": actor},
                )

        start_at += len(issues)
        if start_at >= payload.get("total", 0):
            break

    return {"issues": imported_issues, "modules": imported_modules}
