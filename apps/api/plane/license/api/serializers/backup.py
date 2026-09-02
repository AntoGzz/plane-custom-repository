# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Module imports
from plane.app.serializers import BaseSerializer, UserLiteSerializer
from plane.license.models import InstanceBackup


class InstanceBackupSerializer(BaseSerializer):
    initiated_by_detail = UserLiteSerializer(source="initiated_by", read_only=True)

    class Meta:
        model = InstanceBackup
        fields = (
            "id",
            "name",
            "status",
            "include_database",
            "include_files",
            "file_name",
            "file_size",
            "note",
            "error_message",
            "initiated_by",
            "initiated_by_detail",
            "created_at",
            "updated_at",
            "completed_at",
        )
        read_only_fields = fields
