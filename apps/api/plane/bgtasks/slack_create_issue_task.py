# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging

from celery import shared_task
from django.db.models import Max, Q

from plane.db.models import Issue, IssueSequence, Project, State, WorkspaceIntegration

logger = logging.getLogger(__name__)


@shared_task
def slack_create_issue(workspace_id, project_id, title, description_html="<p></p>", actor_id=None):
    try:
        project = Project.objects.get(pk=project_id, workspace_id=workspace_id)
    except Project.DoesNotExist:
        logger.error("Project %s not found for slack create issue", project_id)
        return None

    default_state = (
        State.objects.filter(~Q(name="Triage"), project_id=project_id, default=True).first()
        or State.objects.filter(~Q(name="Triage"), project_id=project_id).first()
    )

    last_id = IssueSequence.objects.filter(project_id=project_id).aggregate(largest=Max("sequence"))["largest"]
    last_id = 1 if last_id is None else last_id + 1

    issue = Issue.objects.create(
        project_id=project_id,
        workspace_id=workspace_id,
        name=title[:255] if title else "Issue from Slack",
        description_html=description_html or "<p></p>",
        state=default_state,
        sequence_id=last_id,
        created_by_id=actor_id,
        updated_by_id=actor_id,
    )
    IssueSequence.objects.create(
        issue=issue,
        sequence=issue.sequence_id,
        project_id=project_id,
        workspace_id=workspace_id,
    )
    return str(issue.id)
