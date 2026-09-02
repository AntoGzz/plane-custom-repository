/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { Download, RotateCcw, Trash2 } from "lucide-react";
import useSWR, { mutate } from "swr";
// plane imports
import { INSTANCE_BACKUPS_LIST } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { InstanceService } from "@plane/services";
import type { IInstanceBackup, TInstanceBackupStatus } from "@plane/types";
import { AlertModalCore, Input } from "@plane/ui";
import { cn, renderFormattedDate, renderFormattedTime } from "@plane/utils";
// components
import { ProfileSettingsHeading } from "@/components/settings/profile/heading";

const instanceService = new InstanceService();

const STATUS_CLASS: Record<TInstanceBackupStatus, string> = {
  queued: "bg-layer-1 text-placeholder",
  processing: "bg-accent-primary/10 text-accent-primary",
  restoring: "bg-accent-primary/10 text-accent-primary",
  completed: "bg-success-subtle text-success-primary",
  failed: "bg-danger-subtle text-danger-primary",
};

function formatBytes(bytes: number): string {
  if (!bytes) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value < 10 && unit > 0 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
}

function triggerBlobDownload(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export const BackupProfileSettings = observer(function BackupProfileSettings() {
  const { t } = useTranslation();
  const [includeDatabase, setIncludeDatabase] = useState(true);
  const [includeFiles, setIncludeFiles] = useState(true);
  const [note, setNote] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<IInstanceBackup | null>(null);
  const [restoreTarget, setRestoreTarget] = useState<IInstanceBackup | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isRestoring, setIsRestoring] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const { data: backups, error } = useSWR<IInstanceBackup[], { status?: number; error?: string }>(
    INSTANCE_BACKUPS_LIST,
    () => instanceService.listBackups(),
    {
      refreshInterval: (latest) =>
        latest?.some((item) => ["queued", "processing", "restoring"].includes(item.status)) ? 4000 : 0,
    }
  );

  const isForbidden = error?.status === 403 || error?.status === 401;
  const items = backups ?? [];
  const isBusy = items.some(
    (item) => item.status === "queued" || item.status === "processing" || item.status === "restoring"
  );

  const handleCreate = async () => {
    if (!includeDatabase && !includeFiles) {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("account_settings.backup.toast.error_title"),
        message: t("account_settings.backup.errors.select_component"),
      });
      return;
    }
    setIsCreating(true);
    try {
      const created = await instanceService.createBackup({
        include_database: includeDatabase,
        include_files: includeFiles,
        note: note.trim(),
      });
      mutate<IInstanceBackup[]>(INSTANCE_BACKUPS_LIST, (current) => [created, ...(current ?? [])], false);
      setNote("");
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("account_settings.backup.toast.created_title"),
        message: t("account_settings.backup.toast.created_message"),
      });
    } catch (err: unknown) {
      const payload = err as { error?: string; status?: number };
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("account_settings.backup.toast.error_title"),
        message: payload?.error ?? t("account_settings.backup.toast.error_message"),
      });
    } finally {
      setIsCreating(false);
    }
  };

  const handleDownload = async (backup: IInstanceBackup) => {
    setDownloadingId(backup.id);
    try {
      const blob = await instanceService.downloadBackup(backup.id);
      triggerBlobDownload(blob, backup.file_name || `plane-backup-${backup.id}.zip`);
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("account_settings.backup.toast.error_title"),
        message: t("account_settings.backup.toast.download_error"),
      });
    } finally {
      setDownloadingId(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await instanceService.deleteBackup(deleteTarget.id);
      mutate<IInstanceBackup[]>(
        INSTANCE_BACKUPS_LIST,
        (current) => (current ?? []).filter((item) => item.id !== deleteTarget.id),
        false
      );
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("account_settings.backup.toast.deleted_title"),
        message: t("account_settings.backup.toast.deleted_message"),
      });
      setDeleteTarget(null);
    } catch (err: unknown) {
      const payload = err as { error?: string };
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("account_settings.backup.toast.error_title"),
        message: payload?.error ?? t("account_settings.backup.toast.error_message"),
      });
    } finally {
      setIsDeleting(false);
    }
  };

  const handleRestore = async () => {
    if (!restoreTarget) return;
    setIsRestoring(true);
    try {
      const updated = await instanceService.restoreBackup(restoreTarget.id);
      mutate<IInstanceBackup[]>(
        INSTANCE_BACKUPS_LIST,
        (current) => (current ?? []).map((item) => (item.id === updated.id ? updated : item)),
        false
      );
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("account_settings.backup.toast.restored_title"),
        message: t("account_settings.backup.toast.restored_message"),
      });
      setRestoreTarget(null);
    } catch (err: unknown) {
      const payload = err as { error?: string };
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("account_settings.backup.toast.error_title"),
        message: payload?.error ?? t("account_settings.backup.toast.error_message"),
      });
    } finally {
      setIsRestoring(false);
    }
  };

  if (isForbidden) {
    return (
      <div className="size-full">
        <ProfileSettingsHeading
          title={t("account_settings.backup.heading")}
          description={t("account_settings.backup.description")}
        />
        <p className="mt-8 text-13 text-tertiary">{t("account_settings.backup.forbidden")}</p>
      </div>
    );
  }

  return (
    <div className="size-full">
      <AlertModalCore
        isOpen={Boolean(deleteTarget)}
        handleClose={() => setDeleteTarget(null)}
        handleSubmit={handleDelete}
        isSubmitting={isDeleting}
        title={t("account_settings.backup.delete_title")}
        content={t("account_settings.backup.delete_description")}
      />
      <AlertModalCore
        isOpen={Boolean(restoreTarget)}
        handleClose={() => setRestoreTarget(null)}
        handleSubmit={handleRestore}
        isSubmitting={isRestoring}
        variant="danger"
        title={t("account_settings.backup.restore_title")}
        content={t("account_settings.backup.restore_description")}
        primaryButtonText={{
          default: t("account_settings.backup.restore"),
          loading: t("account_settings.backup.restoring"),
        }}
      />
      <ProfileSettingsHeading
        title={t("account_settings.backup.heading")}
        description={t("account_settings.backup.description")}
        control={
          <Button
            variant="primary"
            size="lg"
            onClick={handleCreate}
            loading={isCreating}
            disabled={isCreating || isBusy || (!includeDatabase && !includeFiles)}
          >
            {isCreating ? t("account_settings.backup.creating") : t("account_settings.backup.create")}
          </Button>
        }
      />

      <div className="mt-8 flex flex-col gap-4 rounded-lg border border-subtle p-4">
        <p className="text-13 font-medium text-primary">{t("account_settings.backup.components")}</p>
        <label className="flex items-center gap-2 text-13 text-secondary">
          <input
            type="checkbox"
            className="size-4 rounded-sm border-subtle"
            checked={includeDatabase}
            onChange={(event) => setIncludeDatabase(event.target.checked)}
          />
          {t("account_settings.backup.include_database")}
        </label>
        <label className="flex items-center gap-2 text-13 text-secondary">
          <input
            type="checkbox"
            className="size-4 rounded-sm border-subtle"
            checked={includeFiles}
            onChange={(event) => setIncludeFiles(event.target.checked)}
          />
          {t("account_settings.backup.include_files")}
        </label>
        <div className="flex flex-col gap-2">
          <h4 className="text-13">{t("account_settings.backup.note_label")}</h4>
          <Input
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder={t("account_settings.backup.note_placeholder")}
            className="w-full"
          />
        </div>
      </div>

      <div className="mt-8">
        {items.length === 0 ? (
          <p className="py-12 text-13 text-tertiary">{t("account_settings.backup.empty_description")}</p>
        ) : (
          items.map((backup) => (
            <div key={backup.id} className="group relative flex flex-col justify-center border-b border-subtle py-4">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h5 className="truncate text-13 font-medium">{backup.name}</h5>
                    <span
                      className={cn(
                        "flex h-4 items-center rounded-xs px-2 text-11 font-medium",
                        STATUS_CLASS[backup.status]
                      )}
                    >
                      {t(`account_settings.backup.status.${backup.status}`)}
                    </span>
                  </div>
                  <p className="mt-1 text-11 leading-6 text-placeholder">
                    {renderFormattedDate(backup.created_at)} · {renderFormattedTime(backup.created_at)}
                    {" · "}
                    {formatBytes(backup.file_size)}
                    {" · "}
                    {[
                      backup.include_database ? t("account_settings.backup.database") : null,
                      backup.include_files ? t("account_settings.backup.files") : null,
                    ]
                      .filter(Boolean)
                      .join(", ")}
                  </p>
                  {backup.note && <p className="mt-1 max-w-[80%] text-13 break-words text-secondary">{backup.note}</p>}
                  {backup.error_message && <p className="mt-1 text-11 text-danger-primary">{backup.error_message}</p>}
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    type="button"
                    className="grid size-8 place-items-center rounded-md text-secondary hover:bg-layer-transparent-hover disabled:opacity-40"
                    disabled={backup.status !== "completed" || downloadingId === backup.id}
                    onClick={() => handleDownload(backup)}
                    title={t("account_settings.backup.download")}
                  >
                    <Download className="size-4" />
                  </button>
                  <button
                    type="button"
                    className="grid size-8 place-items-center rounded-md text-secondary hover:bg-layer-transparent-hover disabled:opacity-40"
                    disabled={backup.status !== "completed"}
                    onClick={() => setRestoreTarget(backup)}
                    title={t("account_settings.backup.restore")}
                  >
                    <RotateCcw className="size-4" />
                  </button>
                  <button
                    type="button"
                    className="grid size-8 place-items-center rounded-md text-danger-primary hover:bg-danger-subtle disabled:opacity-40"
                    disabled={backup.status === "processing" || backup.status === "restoring"}
                    onClick={() => setDeleteTarget(backup)}
                    title={t("account_settings.backup.delete")}
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
});
