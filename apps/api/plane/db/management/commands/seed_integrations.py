# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.management.base import BaseCommand

from plane.db.models import Integration


INTEGRATIONS = [
    {
        "title": "GitHub",
        "provider": "github",
        "network": 2,
        "description": {
            "title": "GitHub",
            "description": "Connect GitHub App to sync repositories, import issues, and receive webhooks.",
        },
        "author": "Plane",
        "verified": True,
        "avatar_url": "/assets/services/github.png",
        "metadata": {"scopes": ["issues", "metadata", "pull_requests"]},
    },
    {
        "title": "Slack",
        "provider": "slack",
        "network": 2,
        "description": {
            "title": "Slack",
            "description": "Connect Slack to post activity to channels and create issues from slash commands.",
        },
        "author": "Plane",
        "verified": True,
        "avatar_url": "/assets/services/slack.png",
        "metadata": {"scopes": ["chat:write", "incoming-webhook", "commands"]},
    },
    {
        "title": "Jira",
        "provider": "jira",
        "network": 2,
        "description": {
            "title": "Jira",
            "description": "Connect Jira Cloud with an API token to import projects into Plane.",
        },
        "author": "Plane",
        "verified": True,
        "avatar_url": "/assets/services/jira.svg",
        "metadata": {"auth": "api_token"},
    },
]


class Command(BaseCommand):
    help = "Seed catalog rows for GitHub, Slack and Jira integrations"

    def handle(self, *args, **options):
        for payload in INTEGRATIONS:
            obj, created = Integration.objects.update_or_create(
                provider=payload["provider"],
                defaults=payload,
            )
            self.stdout.write(
                self.style.SUCCESS(f"{'Created' if created else 'Updated'} integration: {obj.provider}")
            )
