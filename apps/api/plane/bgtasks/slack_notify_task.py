# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging

from celery import shared_task
from django.conf import settings

from plane.db.models import Issue, IssueActivity, SlackProjectSync
from plane.utils.integrations.slack import build_activity_blocks, post_slack_webhook

logger = logging.getLogger(__name__)


@shared_task
def slack_notify_on_activity(activity_id):
    try:
        activity = IssueActivity.objects.select_related(
            "issue", "issue__project", "actor", "project", "workspace"
        ).get(pk=activity_id)
    except IssueActivity.DoesNotExist:
        return

    sync = (
        SlackProjectSync.objects.filter(project_id=activity.project_id)
        .order_by("-created_at")
        .first()
    )
    if not sync or not sync.webhook_url:
        return

    issue = activity.issue
    if issue is None:
        return

    identifier = f"{issue.project.identifier}-{issue.sequence_id}"
    summary = activity.comment or f"{activity.verb} {activity.field or 'issue'}"
    if activity.old_value or activity.new_value:
        summary = f"{activity.field}: {activity.old_value} → {activity.new_value}"

    actor_name = getattr(activity.actor, "display_name", None) or getattr(activity.actor, "email", "Plane")
    web_url = getattr(settings, "WEB_URL", "") or ""
    issue_url = None
    if web_url:
        issue_url = f"{web_url.rstrip('/')}/{activity.workspace.slug}/browse/{identifier}/"

    blocks = build_activity_blocks(
        project_name=issue.project.name,
        issue_identifier=identifier,
        summary=summary,
        actor_name=actor_name,
        url=issue_url,
    )
    ok = post_slack_webhook(
        sync.webhook_url,
        {"text": f"{identifier}: {summary}", "blocks": blocks},
    )
    if not ok:
        logger.warning("Failed to post Slack notification for activity %s", activity_id)
