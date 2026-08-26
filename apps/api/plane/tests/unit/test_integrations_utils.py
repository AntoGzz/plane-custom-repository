# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import hashlib
import hmac
import os
import time

from plane.utils.importers.jira import is_allowed_hostname, is_valid_project_key
from plane.utils.integrations.slack import verify_slack_signature


def test_jira_hostname_allowlist():
    assert is_allowed_hostname("acme.atlassian.net") is True
    assert is_allowed_hostname("evil.example.com") is False


def test_jira_project_key():
    assert is_valid_project_key("ABC") is not None
    assert is_valid_project_key("too-long-and-invalid!!!") is False


def test_slack_signature_roundtrip(monkeypatch):
    secret = "test_signing_secret"
    monkeypatch.setenv("SLACK_SIGNING_SECRET", secret)
    body = b'{"type":"url_verification","challenge":"abc"}'
    ts = str(int(time.time()))
    basestring = f"v0:{ts}:{body.decode('utf-8')}"
    digest = hmac.new(secret.encode(), basestring.encode(), hashlib.sha256).hexdigest()
    sig = f"v0={digest}"
    assert verify_slack_signature(body, ts, sig) is True
    assert verify_slack_signature(body, ts, "v0=deadbeef") is False
