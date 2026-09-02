# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import json
import os
import shutil
import subprocess
import tempfile
import zipfile

# Third party imports
import boto3
from botocore.client import Config
from celery import shared_task

# Django imports
from django.conf import settings
from django.utils import timezone

# Module imports
from plane.license.models import InstanceBackup
from plane.license.utils.backup import backups_dir, run_pg_dump, run_pg_restore
from plane.utils.exception_logger import log_exception

BACKUP_DB_NAME = "database.dump"
BACKUP_MANIFEST_NAME = "manifest.json"


def _s3_client():
    kwargs = {
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
        "config": Config(signature_version="s3v4"),
    }
    if getattr(settings, "AWS_S3_ENDPOINT_URL", None):
        kwargs["endpoint_url"] = settings.AWS_S3_ENDPOINT_URL
    if getattr(settings, "AWS_REGION", None):
        kwargs["region_name"] = settings.AWS_REGION
    return boto3.client("s3", **kwargs)


def _iter_bucket_keys(client, bucket: str):
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for item in page.get("Contents") or []:
            key = item.get("Key")
            if key and not key.endswith("/"):
                yield key


def _archive_files(client, bucket: str, files_dir: str) -> int:
    count = 0
    for key in _iter_bucket_keys(client, bucket):
        dest = os.path.join(files_dir, key)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        client.download_file(bucket, key, dest)
        count += 1
    return count


def _restore_files(client, bucket: str, files_dir: str) -> int:
    count = 0
    for root, _, filenames in os.walk(files_dir):
        for filename in filenames:
            full_path = os.path.join(root, filename)
            key = os.path.relpath(full_path, files_dir).replace(os.sep, "/")
            extra = {}
            if getattr(settings, "AWS_DEFAULT_ACL", None):
                extra["ACL"] = settings.AWS_DEFAULT_ACL
            if extra:
                client.upload_file(full_path, bucket, key, ExtraArgs=extra)
            else:
                client.upload_file(full_path, bucket, key)
            count += 1
    return count


def _zip_directory(source_dir: str, zip_path: str) -> None:
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for root, _, filenames in os.walk(source_dir):
            for filename in filenames:
                full_path = os.path.join(root, filename)
                archive.write(full_path, os.path.relpath(full_path, source_dir))


@shared_task
def create_instance_backup(backup_id: str) -> None:
    backup = InstanceBackup.objects.filter(pk=backup_id).first()
    if backup is None:
        return

    backup.status = InstanceBackup.STATUS_PROCESSING
    backup.save(update_fields=["status", "updated_at"])

    staging = tempfile.mkdtemp(prefix="plane-backup-")
    try:
        file_count = 0
        if backup.include_database:
            run_pg_dump(os.path.join(staging, BACKUP_DB_NAME))

        if backup.include_files:
            files_dir = os.path.join(staging, "files")
            os.makedirs(files_dir, exist_ok=True)
            client = _s3_client()
            file_count = _archive_files(client, settings.AWS_STORAGE_BUCKET_NAME, files_dir)

        manifest = {
            "id": str(backup.id),
            "include_database": backup.include_database,
            "include_files": backup.include_files,
            "file_count": file_count,
            "created_at": timezone.now().isoformat(),
            "note": backup.note,
        }
        with open(os.path.join(staging, BACKUP_MANIFEST_NAME), "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)

        stamp = timezone.now().strftime("%Y%m%d-%H%M%S")
        file_name = f"plane-backup-{stamp}-{str(backup.id)[:8]}.zip"
        zip_path = os.path.join(backups_dir(), file_name)
        _zip_directory(staging, zip_path)

        backup.file_name = file_name
        backup.file_path = zip_path
        backup.file_size = os.path.getsize(zip_path)
        backup.status = InstanceBackup.STATUS_COMPLETED
        backup.completed_at = timezone.now()
        backup.error_message = ""
        backup.save(
            update_fields=[
                "file_name",
                "file_path",
                "file_size",
                "status",
                "completed_at",
                "error_message",
                "updated_at",
            ]
        )
    except Exception as exc:
        log_exception(exc)
        message = str(exc)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            message = str(exc.stderr).strip() or message
        backup.status = InstanceBackup.STATUS_FAILED
        backup.error_message = message[:4000]
        backup.save(update_fields=["status", "error_message", "updated_at"])
    finally:
        shutil.rmtree(staging, ignore_errors=True)


@shared_task
def restore_instance_backup(backup_id: str) -> None:
    backup = InstanceBackup.objects.filter(pk=backup_id).first()
    if backup is None:
        return

    if backup.status != InstanceBackup.STATUS_COMPLETED or not backup.file_path or not os.path.isfile(backup.file_path):
        backup.status = InstanceBackup.STATUS_FAILED
        backup.error_message = "Backup file is not available to restore."
        backup.save(update_fields=["status", "error_message", "updated_at"])
        return

    previous_status = backup.status
    backup.status = InstanceBackup.STATUS_RESTORING
    backup.save(update_fields=["status", "updated_at"])

    staging = tempfile.mkdtemp(prefix="plane-restore-")
    try:
        with zipfile.ZipFile(backup.file_path, "r") as archive:
            archive.extractall(staging)

        files_dir = os.path.join(staging, "files")
        if backup.include_files and os.path.isdir(files_dir):
            client = _s3_client()
            _restore_files(client, settings.AWS_STORAGE_BUCKET_NAME, files_dir)

        dump_path = os.path.join(staging, BACKUP_DB_NAME)
        if backup.include_database and os.path.isfile(dump_path):
            run_pg_restore(dump_path)
            return

        backup.status = previous_status
        backup.error_message = ""
        backup.save(update_fields=["status", "error_message", "updated_at"])
    except Exception as exc:
        log_exception(exc)
        message = str(exc)
        if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
            message = str(exc.stderr).strip() or message
        backup.status = InstanceBackup.STATUS_FAILED
        backup.error_message = message[:4000]
        backup.save(update_fields=["status", "error_message", "updated_at"])
    finally:
        shutil.rmtree(staging, ignore_errors=True)
