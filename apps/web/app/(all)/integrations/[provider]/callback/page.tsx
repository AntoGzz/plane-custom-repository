/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router";
import { AppInstallationService } from "@/services/app_installation.service";

const appInstallationService = new AppInstallationService();

/**
 * OAuth / GitHub App callback landing page.
 * - Slack: ?code=...&state=<workspaceSlug>
 * - GitHub App: ?installation_id=...&state=<workspaceSlug>
 * Configure Slack redirect URL and GitHub App Setup URL to:
 *   {WEB_URL}/integrations/{provider}/callback
 */
export default function IntegrationCallbackPage() {
  const { provider } = useParams();
  const [searchParams] = useSearchParams();
  const [message, setMessage] = useState("Connecting integration…");

  useEffect(() => {
    const run = async () => {
      try {
        const state = searchParams.get("state") || "";
        const workspaceSlug = state.split(",")[0];
        if (!workspaceSlug || !provider) {
          setMessage("Missing workspace or provider in callback.");
          return;
        }

        if (provider === "github") {
          const installationId = searchParams.get("installation_id");
          if (!installationId) {
            setMessage("Missing installation_id from GitHub.");
            return;
          }
          await appInstallationService.addInstallationApp(workspaceSlug, "github", {
            installation_id: installationId,
          });
        } else if (provider === "slack") {
          const code = searchParams.get("code");
          if (!code) {
            setMessage("Missing OAuth code from Slack.");
            return;
          }
          await appInstallationService.addInstallationApp(workspaceSlug, "slack", {
            code,
            redirect_uri: `${window.location.origin}/integrations/slack/callback`,
          });
        } else {
          setMessage(`Unsupported provider: ${provider}`);
          return;
        }

        setMessage("Installed successfully. You can close this window.");
        window.setTimeout(() => {
          try {
            window.close();
          } catch {
            /* ignore */
          }
          window.location.href = `/${workspaceSlug}/settings/integrations/`;
        }, 800);
      } catch (e: any) {
        console.error(e);
        setMessage(e?.data?.error || e?.message || "Installation failed. Check logs and credentials.");
      }
    };
    run();
  }, [provider, searchParams]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-1 p-8">
      <div className="max-w-md rounded-lg border border-subtle bg-layer-1 p-6 text-center">
        <h1 className="text-lg font-semibold text-primary">Plane Integrations</h1>
        <p className="text-sm mt-3 text-secondary">{message}</p>
      </div>
    </div>
  );
}
