# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging

from celery import shared_task
from django.db.models import Max, Q

from plane.db.models import (
    GithubCommentSync,
    GithubIssueSync,
    GithubRepository,
    GithubRepositorySync,
    Issue,
    IssueComment,
    IssueSequence,
    Label,
    State,
)
from plane.utils.html_processor import strip_tags

logger = logging.getLogger(__name__)


@shared_task
def process_github_webhook_event(event, delivery, payload):
    if event == "ping":
        return

    if event == "issues":
        _handle_issue_event(payload)
    elif event == "issue_comment":
        _handle_comment_event(payload)


def _repo_sync_for_payload(payload):
    repo_payload = payload.get("repository") or {}
    repository_id = repo_payload.get("id")
    if not repository_id:
        return None
    repo = GithubRepository.objects.filter(repository_id=repository_id).select_related("project").first()
    if not repo:
        return None
    return (
        GithubRepositorySync.objects.filter(repository=repo)
        .select_related("actor", "label", "project", "workspace_integration")
        .first()
    )


def _handle_issue_event(payload):
    action = payload.get("action")
    if action not in ("opened", "edited", "reopened", "closed"):
        return

    repo_sync = _repo_sync_for_payload(payload)
    if not repo_sync:
        return

    gh_issue = payload.get("issue") or {}
    github_issue_id = gh_issue.get("id")
    number = gh_issue.get("number")
    title = gh_issue.get("title") or "GitHub issue"
    body = gh_issue.get("body") or ""
    html_url = gh_issue.get("html_url") or ""

    existing = GithubIssueSync.objects.filter(
        repository_sync=repo_sync, github_issue_id=github_issue_id
    ).select_related("issue").first()

    description_html = f"<p>{body}</p>" if body else "<p></p>"

    if existing and existing.issue_id:
        issue = existing.issue
        issue.name = title[:255]
        issue.description_html = description_html
        issue.description_stripped = strip_tags(description_html)
        issue.save(update_fields=["name", "description_html", "description_stripped", "updated_at"])
        return

    project_id = repo_sync.project_id
    default_state = (
        State.objects.filter(~Q(name="Triage"), project_id=project_id, default=True).first()
        or State.objects.filter(~Q(name="Triage"), project_id=project_id).first()
    )
    last_id = IssueSequence.objects.filter(project_id=project_id).aggregate(largest=Max("sequence"))["largest"]
    last_id = 1 if last_id is None else last_id + 1

    issue = Issue.objects.create(
        project_id=project_id,
        workspace_id=repo_sync.workspace_id,
        name=title[:255],
        description_html=description_html,
        description_stripped=strip_tags(description_html),
        state=default_state,
        sequence_id=last_id,
        created_by=repo_sync.actor,
        updated_by=repo_sync.actor,
        external_id=str(github_issue_id),
        external_source="github",
    )
    IssueSequence.objects.create(
        issue=issue,
        sequence=issue.sequence_id,
        project_id=project_id,
        workspace_id=repo_sync.workspace_id,
    )

    if repo_sync.label_id:
        from plane.db.models import IssueLabel

        IssueLabel.objects.get_or_create(
            issue=issue,
            label_id=repo_sync.label_id,
            project_id=project_id,
            workspace_id=repo_sync.workspace_id,
            defaults={"created_by": repo_sync.actor},
        )

    GithubIssueSync.objects.create(
        repo_issue_id=number or 0,
        github_issue_id=github_issue_id,
        issue_url=html_url,
        issue=issue,
        repository_sync=repo_sync,
        project_id=project_id,
        workspace_id=repo_sync.workspace_id,
        created_by=repo_sync.actor,
        updated_by=repo_sync.actor,
    )


def _handle_comment_event(payload):
    action = payload.get("action")
    if action not in ("created", "edited"):
        return

    repo_sync = _repo_sync_for_payload(payload)
    if not repo_sync:
        return

    gh_issue = payload.get("issue") or {}
    github_issue_id = gh_issue.get("id")
    issue_sync = GithubIssueSync.objects.filter(
        repository_sync=repo_sync, github_issue_id=github_issue_id
    ).first()
    if not issue_sync:
        return

    comment_payload = payload.get("comment") or {}
    repo_comment_id = comment_payload.get("id")
    body = comment_payload.get("body") or ""
    comment_html = f"<p>{body}</p>" if body else "<p></p>"

    existing = GithubCommentSync.objects.filter(
        issue_sync=issue_sync, repo_comment_id=repo_comment_id
    ).select_related("comment").first()
    if existing and existing.comment_id:
        c = existing.comment
        c.comment_html = comment_html
        c.save(update_fields=["comment_html", "updated_at"])
        return

    comment = IssueComment.objects.create(
        issue_id=issue_sync.issue_id,
        comment_html=comment_html,
        actor=repo_sync.actor,
        project_id=repo_sync.project_id,
        workspace_id=repo_sync.workspace_id,
        created_by=repo_sync.actor,
        external_id=str(repo_comment_id),
        external_source="github",
    )
    GithubCommentSync.objects.create(
        repo_comment_id=repo_comment_id,
        comment=comment,
        issue_sync=issue_sync,
        project_id=repo_sync.project_id,
        workspace_id=repo_sync.workspace_id,
        created_by=repo_sync.actor,
        updated_by=repo_sync.actor,
    )
