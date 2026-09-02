# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from plane.license.models import Instance, InstanceAdmin, InstanceBackup


@pytest.fixture
def create_instance(db):
    return Instance.objects.create(
        instance_name="Test instance",
        instance_id="test-instance-id",
        current_version="1.0.0",
        last_checked_at=timezone.now(),
        is_setup_done=True,
    )


@pytest.fixture
def instance_admin(db, create_user, create_instance):
    return InstanceAdmin.objects.create(instance=create_instance, user=create_user, role=20)


@pytest.mark.contract
class TestInstanceBackupEndpoint:
    @pytest.mark.django_db
    def test_list_requires_instance_admin(self, session_client, create_user, create_instance):
        session_client.force_authenticate(user=create_user)
        url = reverse("instance-backups")
        response = session_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.django_db
    def test_list_empty_for_instance_admin(self, session_client, create_user, instance_admin):
        session_client.force_authenticate(user=create_user)
        url = reverse("instance-backups")
        response = session_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    @pytest.mark.django_db
    def test_create_requires_component(self, session_client, create_user, instance_admin, mocker):
        session_client.force_authenticate(user=create_user)
        mocker.patch("plane.license.api.views.backup.create_instance_backup.delay")
        url = reverse("instance-backups")
        response = session_client.post(
            url,
            {"include_database": False, "include_files": False},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert InstanceBackup.objects.count() == 0

    @pytest.mark.django_db
    def test_create_queues_backup(self, session_client, create_user, instance_admin, mocker):
        session_client.force_authenticate(user=create_user)
        delay = mocker.patch("plane.license.api.views.backup.create_instance_backup.delay")
        url = reverse("instance-backups")
        response = session_client.post(
            url,
            {"include_database": True, "include_files": True, "note": "nightly"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "queued"
        assert response.data["note"] == "nightly"
        assert InstanceBackup.objects.get(pk=response.data["id"])
        delay.assert_called_once_with(str(backup.id))

    @pytest.mark.django_db
    def test_list_accepts_web_app_session_cookie(self, client, create_user, instance_admin):
        client.force_login(create_user)
        url = reverse("instance-backups")
        response = client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []
