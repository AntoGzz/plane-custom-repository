# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.conf import settings
from django.db import models

# Module imports
from plane.db.models import BaseModel


class InstanceBackup(BaseModel):
    STATUS_QUEUED = "queued"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_RESTORING = "restoring"

    STATUS_CHOICES = (
        (STATUS_QUEUED, "Queued"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_RESTORING, "Restoring"),
    )

    name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    include_database = models.BooleanField(default=True)
    include_files = models.BooleanField(default=True)
    file_name = models.CharField(max_length=255, blank=True)
    file_path = models.TextField(blank=True)
    file_size = models.BigIntegerField(default=0)
    note = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="instance_backups",
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Instance Backup"
        verbose_name_plural = "Instance Backups"
        db_table = "instance_backups"
        ordering = ("-created_at",)

    def __str__(self):
        return self.name or str(self.id)
