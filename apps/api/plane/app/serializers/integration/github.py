# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Module imports
from plane.app.serializers.base import BaseSerializer
from plane.db.models import (
    GithubIssueSync,
    GithubRepository,
    GithubRepositorySync,
    GithubCommentSync,
)


class GithubRepositorySerializer(BaseSerializer):
    class Meta:
        model = GithubRepository
        fields = "__all__"


class GithubRepositorySyncSerializer(BaseSerializer):
    repo_detail = GithubRepositorySerializer(source="repository")

    class Meta:
        model = GithubRepositorySync
        fields = "__all__"


class GithubIssueSyncSerializer(BaseSerializer):
    class Meta:
        model = GithubIssueSync
        fields = "__all__"
        read_only_fields = [
            "project",
            "workspace",
            "repository_sync",
        ]


class GithubCommentSyncSerializer(BaseSerializer):
    class Meta:
        model = GithubCommentSync
        fields = "__all__"
        read_only_fields = [
            "project",
            "workspace",
            "repository_sync",
            "issue_sync",
        ]
