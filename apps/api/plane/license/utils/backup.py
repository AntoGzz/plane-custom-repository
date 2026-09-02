# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import os
import shutil
import subprocess
from urllib.parse import urlparse

# Django imports
from django.conf import settings


def backups_dir() -> str:
    path = getattr(settings, "BACKUPS_DIR", None) or os.path.join(os.path.dirname(settings.BASE_DIR), "backups")
    os.makedirs(path, exist_ok=True)
    return path


def postgres_connection():
    """
    Return (env, host, port, user, dbname) for pg_dump / pg_restore.
    """
    db = settings.DATABASES["default"]
    env = os.environ.copy()
    env["PGPASSWORD"] = str(db.get("PASSWORD") or "")
    host = db.get("HOST") or "localhost"
    port = str(db.get("PORT") or "5432")
    user = db.get("USER") or "postgres"
    name = db.get("NAME")
    if not name and os.environ.get("DATABASE_URL"):
        parsed = urlparse(os.environ["DATABASE_URL"])
        name = parsed.path.lstrip("/")
        host = parsed.hostname or host
        port = str(parsed.port or port)
        user = parsed.username or user
        if parsed.password:
            env["PGPASSWORD"] = parsed.password
    return env, host, port, user, name


def require_pg_tool(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise FileNotFoundError(
            f"{binary} is not installed in this container. Rebuild the API image so postgresql-client is available."
        )
    return path


def run_pg_dump(output_path: str) -> None:
    env, host, port, user, name = postgres_connection()
    binary = require_pg_tool("pg_dump")
    subprocess.run(
        [
            binary,
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-d",
            name,
            "-Fc",
            "--no-owner",
            "--no-acl",
            "--exclude-table=instance_backups",
            "-f",
            output_path,
        ],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )


def run_pg_restore(dump_path: str) -> None:
    env, host, port, user, name = postgres_connection()
    binary = require_pg_tool("pg_restore")
    subprocess.run(
        [
            binary,
            "-h",
            host,
            "-p",
            port,
            "-U",
            user,
            "-d",
            name,
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-acl",
            dump_path,
        ],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )
