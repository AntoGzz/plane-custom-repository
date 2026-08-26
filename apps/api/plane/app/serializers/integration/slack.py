# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Module imports
from plane.app.serializers.base import BaseSerializer
from plane.db.models import SlackProjectSync


class SlackProjectSyncSerializer(BaseSerializer):
    class Meta:
        model = SlackProjectSync
        fields = "__all__"
        read_only_fields = [
            "project",
            "workspace",
            "workspace_integration",
        ]
