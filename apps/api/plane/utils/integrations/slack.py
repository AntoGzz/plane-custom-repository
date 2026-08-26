# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import hmac
import json
import os
import time

import requests


def slack_oauth(code, redirect_uri=None):
    """Exchange a Slack OAuth v2 authorization code for an access token."""
    slack_oauth_url = os.environ.get("SLACK_OAUTH_URL", "https://slack.com/api/oauth.v2.access")
    slack_client_id = os.environ.get("SLACK_CLIENT_ID", False)
    slack_client_secret = os.environ.get("SLACK_CLIENT_SECRET", False)

    if not (slack_oauth_url and slack_client_id and slack_client_secret):
        return {}

    payload = {
        "code": code,
        "client_id": slack_client_id,
        "client_secret": slack_client_secret,
    }
    if redirect_uri:
        payload["redirect_uri"] = redirect_uri

    response = requests.post(slack_oauth_url, data=payload, timeout=30)
    return response.json()


def verify_slack_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """Validate Slack request signature (v0)."""
    signing_secret = os.environ.get("SLACK_SIGNING_SECRET", "")
    if not signing_secret:
        return True
    if not timestamp or not signature:
        return False

    try:
        if abs(time.time() - int(timestamp)) > 60 * 5:
            return False
    except (TypeError, ValueError):
        return False

    basestring = f"v0:{timestamp}:{request_body.decode('utf-8')}"
    digest = hmac.new(
        signing_secret.encode("utf-8"),
        basestring.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    computed = f"v0={digest}"
    return hmac.compare_digest(computed, signature)


def post_slack_webhook(webhook_url: str, payload: dict) -> bool:
    if not webhook_url:
        return False
    response = requests.post(webhook_url, json=payload, timeout=15)
    return response.status_code < 300


def slack_chat_post_message(access_token: str, channel: str, text: str, blocks=None) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    body = {"channel": channel, "text": text}
    if blocks is not None:
        body["blocks"] = blocks
    response = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers=headers,
        data=json.dumps(body),
        timeout=15,
    )
    return response.json()


def build_activity_blocks(project_name, issue_identifier, summary, actor_name, url=None):
    text = f"*{project_name}* · `{issue_identifier}`\n{summary}\n_by {actor_name}_"
    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": text},
        }
    ]
    if url:
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Open in Plane"},
                        "url": url,
                    }
                ],
            }
        )
    return blocks


def build_create_issue_modal(projects, callback_id="plane_create_issue"):
    options = [
        {
            "text": {"type": "plain_text", "text": p["name"][:75]},
            "value": str(p["id"]),
        }
        for p in projects[:100]
    ]
    return {
        "type": "modal",
        "callback_id": callback_id,
        "title": {"type": "plain_text", "text": "Create Plane issue"},
        "submit": {"type": "plain_text", "text": "Create"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "project_block",
                "label": {"type": "plain_text", "text": "Project"},
                "element": {
                    "type": "static_select",
                    "action_id": "project_select",
                    "options": options
                    or [
                        {
                            "text": {"type": "plain_text", "text": "No projects"},
                            "value": "none",
                        }
                    ],
                },
            },
            {
                "type": "input",
                "block_id": "title_block",
                "label": {"type": "plain_text", "text": "Title"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "title_input",
                },
            },
            {
                "type": "input",
                "block_id": "description_block",
                "optional": True,
                "label": {"type": "plain_text", "text": "Description"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "description_input",
                    "multiline": True,
                },
            },
        ],
    }


def slack_views_open(access_token: str, trigger_id: str, view: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    response = requests.post(
        "https://slack.com/api/views.open",
        headers=headers,
        data=json.dumps({"trigger_id": trigger_id, "view": view}),
        timeout=15,
    )
    return response.json()
