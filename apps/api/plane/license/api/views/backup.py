# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import os

# Django imports
from django.http import FileResponse
from django.utils import timezone

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.license.api.serializers.backup import InstanceBackupSerializer
from plane.license.api.views.base import BaseAPIView
from plane.license.bgtasks.backup_task import create_instance_backup, restore_instance_backup
from plane.license.models import InstanceBackup


def _as_bool(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


class InstanceBackupEndpoint(BaseAPIView):
    def get(self, request):
        backups = InstanceBackup.objects.select_related("initiated_by").all()
        serializer = InstanceBackupSerializer(backups, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        include_database = _as_bool(request.data.get("include_database"), True)
        include_files = _as_bool(request.data.get("include_files"), True)
        if not include_database and not include_files:
            return Response(
                {"error": "Select at least the database or the files to include in the backup."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        note = (request.data.get("note") or "").strip()[:2000]
        stamp = timezone.now().strftime("%Y-%m-%d %H:%M")
        backup = InstanceBackup.objects.create(
            name=request.data.get("name") or f"Backup {stamp}",
            include_database=include_database,
            include_files=include_files,
            note=note,
            initiated_by=request.user,
            status=InstanceBackup.STATUS_QUEUED,
        )
        create_instance_backup.delay(str(backup.id))
        serializer = InstanceBackupSerializer(backup)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class InstanceBackupDetailEndpoint(BaseAPIView):
    def get(self, request, pk):
        backup = InstanceBackup.objects.select_related("initiated_by").get(pk=pk)
        serializer = InstanceBackupSerializer(backup)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        backup = InstanceBackup.objects.get(pk=pk)
        if backup.status == InstanceBackup.STATUS_PROCESSING or backup.status == InstanceBackup.STATUS_RESTORING:
            return Response(
                {"error": "Wait until the backup finishes before deleting it."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if backup.file_path and os.path.isfile(backup.file_path):
            try:
                os.remove(backup.file_path)
            except OSError:
                pass
        backup.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class InstanceBackupDownloadEndpoint(BaseAPIView):
    def get(self, request, pk):
        backup = InstanceBackup.objects.get(pk=pk)
        if backup.status != InstanceBackup.STATUS_COMPLETED or not backup.file_path or not os.path.isfile(backup.file_path):
            return Response(
                {"error": "Backup file is not available."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        handle = open(backup.file_path, "rb")
        response = FileResponse(handle, as_attachment=True, filename=backup.file_name or "plane-backup.zip")
        return response


class InstanceBackupRestoreEndpoint(BaseAPIView):
    def post(self, request, pk):
        backup = InstanceBackup.objects.get(pk=pk)
        if backup.status != InstanceBackup.STATUS_COMPLETED:
            return Response(
                {"error": "Only a completed backup can be restored."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not backup.file_path or not os.path.isfile(backup.file_path):
            return Response(
                {"error": "Backup file is not available."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        restore_instance_backup.delay(str(backup.id))
        backup.status = InstanceBackup.STATUS_RESTORING
        backup.save(update_fields=["status", "updated_at"])
        serializer = InstanceBackupSerializer(backup)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)
