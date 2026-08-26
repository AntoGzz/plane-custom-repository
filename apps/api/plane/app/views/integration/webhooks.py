# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import hmac
import json
import os
from urllib.parse import parse_qs

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView
from plane.bgtasks.github_webhook_task import process_github_webhook_event
from plane.bgtasks.slack_create_issue_task import slack_create_issue
from plane.db.models import Project, WorkspaceIntegration
from plane.utils.integrations.slack import (
    build_create_issue_modal,
    slack_views_open,
    verify_slack_signature,
)


@method_decorator(csrf_exempt, name="dispatch")
class SlackEventsEndpoint(BaseAPIView):
    """
    Slack Events / Interactivity / Slash commands entrypoint.
    Configure Slack Request URL to POST here.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw_body = request.body or b""
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")
        if not verify_slack_signature(raw_body, timestamp, signature):
            return Response({"error": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)

        content_type = request.headers.get("Content-Type", "")
        payload = {}
        if "application/json" in content_type:
            payload = request.data if isinstance(request.data, dict) else {}
        else:
            # slash commands / interactivity often use form encoding
            form = parse_qs(raw_body.decode("utf-8"))
            if "payload" in form:
                payload = json.loads(form["payload"][0])
            else:
                payload = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in form.items()}

        # URL verification challenge
        if payload.get("type") == "url_verification":
            return Response({"challenge": payload.get("challenge")})

        # Slash command create-issue
        if payload.get("command") or payload.get("trigger_id") and payload.get("team_id") and "view" not in payload:
            if payload.get("command") or payload.get("text") is not None:
                return self._handle_slash(payload)

        # Interactive / view_submission
        if payload.get("type") == "view_submission":
            return self._handle_view_submission(payload)

        if payload.get("type") == "event_callback":
            # Acknowledge events; deeper handling can expand later
            return Response({"ok": True})

        return Response({"ok": True})

    def _workspace_integration_for_team(self, team_id):
        return (
            WorkspaceIntegration.objects.filter(
                integration__provider="slack",
                config__team_id=team_id,
            )
            .select_related("workspace", "actor", "integration")
            .first()
        )

    def _handle_slash(self, payload):
        team_id = payload.get("team_id")
        trigger_id = payload.get("trigger_id")
        text = (payload.get("text") or "").strip()
        wi = self._workspace_integration_for_team(team_id)
        if not wi:
            return Response(
                {
                    "response_type": "ephemeral",
                    "text": "Slack is not connected to a Plane workspace. Install it from Workspace Settings → Integrations.",
                }
            )

        access_token = wi.config.get("access_token")
        if not access_token:
            return Response(
                {"response_type": "ephemeral", "text": "Missing Slack access token. Reinstall the integration."}
            )

        # Quick create: `/plane Fix login bug`
        if text:
            project = Project.objects.filter(workspace_id=wi.workspace_id).order_by("created_at").first()
            if not project:
                return Response({"response_type": "ephemeral", "text": "No projects found in the workspace."})
            slack_create_issue.delay(
                str(wi.workspace_id),
                str(project.id),
                text,
                f"<p>{text}</p>",
                str(wi.actor_id) if wi.actor_id else None,
            )
            return Response(
                {
                    "response_type": "ephemeral",
                    "text": f"Creating issue in *{project.name}*: {text}",
                }
            )

        projects = list(
            Project.objects.filter(workspace_id=wi.workspace_id).values("id", "name")[:100]
        )
        view = build_create_issue_modal(projects)
        slack_views_open(access_token, trigger_id, view)
        return Response(status=status.HTTP_200_OK)

    def _handle_view_submission(self, payload):
        team_id = payload.get("team", {}).get("id")
        wi = self._workspace_integration_for_team(team_id)
        if not wi:
            return Response({"response_action": "errors", "errors": {"title_block": "Workspace not linked"}})

        values = payload.get("view", {}).get("state", {}).get("values", {})
        project_id = (
            values.get("project_block", {})
            .get("project_select", {})
            .get("selected_option", {})
            .get("value")
        )
        title = values.get("title_block", {}).get("title_input", {}).get("value") or "Issue from Slack"
        description = values.get("description_block", {}).get("description_input", {}).get("value") or ""

        if not project_id or project_id == "none":
            return Response(
                {
                    "response_action": "errors",
                    "errors": {"project_block": "Select a project"},
                }
            )

        slack_create_issue.delay(
            str(wi.workspace_id),
            str(project_id),
            title,
            f"<p>{description}</p>" if description else "<p></p>",
            str(wi.actor_id) if wi.actor_id else None,
        )
        return Response({"response_action": "clear"})


@method_decorator(csrf_exempt, name="dispatch")
class GithubAppWebhookEndpoint(BaseAPIView):
    """
    GitHub App webhook receiver. Verifies X-Hub-Signature-256 when secret is set.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
        if secret:
            signature = request.headers.get("X-Hub-Signature-256", "")
            digest = hmac.new(secret.encode("utf-8"), request.body, hashlib.sha256).hexdigest()
            expected = f"sha256={digest}"
            if not hmac.compare_digest(expected, signature):
                return Response({"error": "Invalid signature"}, status=status.HTTP_401_UNAUTHORIZED)

        event = request.headers.get("X-GitHub-Event", "")
        delivery = request.headers.get("X-GitHub-Delivery", "")
        payload = request.data if isinstance(request.data, dict) else {}
        process_github_webhook_event.delay(event, delivery, payload)
        return Response({"ok": True})
