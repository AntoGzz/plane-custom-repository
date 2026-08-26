# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging

import requests
from django.db.models import Max, Q

from plane.db.models import (
    GithubIssueSync,
    GithubRepositorySync,
    Issue,
    IssueComment,
    IssueLabel,
    IssueSequence,
    Label,
    State,
)
from plane.utils.html_processor import strip_tags
from plane.utils.integrations.github import get_installation_access_token

logger = logging.getLogger(__name__)


def _paginate(url, headers):
    results = []
    while url:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            results.extend(data)
        else:
            results.append(data)
        url = response.links.get("next", {}).get("url")
    return results


def run_github_import(importer):
    """
    Import open issues/labels/comments from the linked GitHub repo into Plane.
    Uses GitHub App installation token from workspace integration.
    """
    from plane.db.models import WorkspaceIntegration

    metadata = importer.metadata or {}
    owner = metadata.get("owner")
    repo = metadata.get("name") or metadata.get("repo")
    if not owner or not repo:
        raise ValueError("GitHub import requires metadata.owner and metadata.name")

    wi = WorkspaceIntegration.objects.get(
        workspace_id=importer.workspace_id, integration__provider="github"
    )
    installation_id = wi.config.get("installation_id")
    token = get_installation_access_token(installation_id)
    if not token:
        raise ValueError("Unable to obtain GitHub installation token")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    project_id = importer.project_id
    workspace_id = importer.workspace_id
    actor = wi.actor

    # Labels
    gh_labels = _paginate(f"https://api.github.com/repos/{owner}/{repo}/labels?per_page=100", headers)
    label_map = {}
    imported_label_ids = []
    for gh_label in gh_labels:
        label, _ = Label.objects.get_or_create(
            project_id=project_id,
            name=gh_label.get("name")[:255],
            defaults={
                "color": f"#{gh_label.get('color')}" if gh_label.get("color") else "#003773",
                "description": gh_label.get("description") or "",
                "workspace_id": workspace_id,
                "created_by": actor,
            },
        )
        label_map[gh_label.get("name")] = label.id
        imported_label_ids.append(str(label.id))

    default_state = (
        State.objects.filter(~Q(name="Triage"), project_id=project_id, default=True).first()
        or State.objects.filter(~Q(name="Triage"), project_id=project_id).first()
    )
    last_id = IssueSequence.objects.filter(project_id=project_id).aggregate(largest=Max("sequence"))["largest"]
    last_id = 1 if last_id is None else last_id + 1

    issues = _paginate(
        f"https://api.github.com/repos/{owner}/{repo}/issues?state=all&per_page=100",
        headers,
    )
    imported_issue_ids = []
    repo_sync = GithubRepositorySync.objects.filter(project_id=project_id).first()

    for gh_issue in issues:
        # Skip pull requests
        if gh_issue.get("pull_request"):
            continue
        github_issue_id = gh_issue.get("id")
        if Issue.objects.filter(project_id=project_id, external_source="github", external_id=str(github_issue_id)).exists():
            continue

        body = gh_issue.get("body") or ""
        description_html = f"<p>{body}</p>" if body else "<p></p>"
        issue = Issue.objects.create(
            project_id=project_id,
            workspace_id=workspace_id,
            name=(gh_issue.get("title") or "GitHub issue")[:255],
            description_html=description_html,
            description_stripped=strip_tags(description_html),
            state=default_state,
            sequence_id=last_id,
            created_by=actor,
            updated_by=actor,
            external_id=str(github_issue_id),
            external_source="github",
        )
        IssueSequence.objects.create(
            issue=issue,
            sequence=issue.sequence_id,
            project_id=project_id,
            workspace_id=workspace_id,
        )
        last_id += 1
        imported_issue_ids.append(str(issue.id))

        for label_name in [l.get("name") for l in gh_issue.get("labels", []) if isinstance(l, dict)]:
            label_id = label_map.get(label_name)
            if label_id:
                IssueLabel.objects.get_or_create(
                    issue=issue,
                    label_id=label_id,
                    project_id=project_id,
                    workspace_id=workspace_id,
                    defaults={"created_by": actor},
                )

        if repo_sync:
            GithubIssueSync.objects.get_or_create(
                repository_sync=repo_sync,
                github_issue_id=github_issue_id,
                defaults={
                    "repo_issue_id": gh_issue.get("number") or 0,
                    "issue_url": gh_issue.get("html_url") or "",
                    "issue": issue,
                    "project_id": project_id,
                    "workspace_id": workspace_id,
                    "created_by": actor,
                    "updated_by": actor,
                },
            )

        # Comments (first page only for speed; webhook covers the rest)
        comments = requests.get(
            gh_issue.get("comments_url"),
            headers=headers,
            params={"per_page": 100},
            timeout=60,
        ).json()
        if isinstance(comments, list):
            for c in comments:
                c_html = f"<p>{c.get('body') or ''}</p>"
                IssueComment.objects.create(
                    issue=issue,
                    comment_html=c_html,
                    actor=actor,
                    project_id=project_id,
                    workspace_id=workspace_id,
                    created_by=actor,
                    external_id=str(c.get("id")),
                    external_source="github",
                )

    return {"issues": imported_issue_ids, "labels": imported_label_ids}
