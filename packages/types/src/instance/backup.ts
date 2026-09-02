/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TInstanceBackupStatus = "queued" | "processing" | "completed" | "failed" | "restoring";

export interface IInstanceBackupUser {
  id: string;
  first_name?: string;
  last_name?: string;
  email?: string;
  display_name?: string;
  avatar_url?: string | null;
}

export interface IInstanceBackup {
  id: string;
  name: string;
  status: TInstanceBackupStatus;
  include_database: boolean;
  include_files: boolean;
  file_name: string;
  file_size: number;
  note: string;
  error_message: string;
  initiated_by: string | null;
  initiated_by_detail: IInstanceBackupUser | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export interface IInstanceBackupCreatePayload {
  name?: string;
  note?: string;
  include_database?: boolean;
  include_files?: boolean;
}
