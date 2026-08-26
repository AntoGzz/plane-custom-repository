# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from plane.app.serializers.base import BaseSerializer
from plane.db.models import Integration, WorkspaceIntegration


class IntegrationSerializer(BaseSerializer):
    class Meta:
        model = Integration
        fields = "__all__"
        read_only_fields = [
            "verified",
        ]


class WorkspaceIntegrationSerializer(BaseSerializer):
    integration_detail = IntegrationSerializer(read_only=True, source="integration")

    class Meta:
        model = WorkspaceIntegration
        fields = "__all__"
        extra_kwargs = {
            "api_token": {"write_only": True},
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        config = dict(data.get("config") or {})
        # Never leak secrets to the browser
        for key in ("access_token", "api_token", "private_key"):
            if key in config:
                config[key] = "***"
        data["config"] = config
        metadata = dict(data.get("metadata") or {})
        if "access_token" in metadata:
            metadata["access_token"] = "***"
        data["metadata"] = metadata
        return data
