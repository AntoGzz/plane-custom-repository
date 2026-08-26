/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import { useParams } from "next/navigation";
import useSWR, { mutate } from "swr";
import { CheckCircle } from "lucide-react";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { Tooltip } from "@plane/propel/tooltip";
import type { IAppIntegration, IWorkspaceIntegration } from "@plane/types";
// ui
import { Loader } from "@plane/ui";
// assets
import GithubLogo from "@/app/assets/services/github.png?url";
import SlackLogo from "@/app/assets/services/slack.png?url";
import JiraLogo from "@/app/assets/services/jira.svg?url";
// constants
import { WORKSPACE_INTEGRATIONS } from "@plane/constants";
// hooks
import { useInstance } from "@/hooks/store/use-instance";
import { useUserPermissions } from "@/hooks/store/user";
import useIntegrationPopup from "@/hooks/use-integration-popup";
import { usePlatformOS } from "@/hooks/use-platform-os";
// services
import { IntegrationService } from "@/services/integrations";

type Props = {
  integration: IAppIntegration;
};

const integrationDetails: { [key: string]: any } = {
  github: {
    logo: GithubLogo,
    installed: "Activate GitHub on individual projects to sync with specific repositories.",
    notInstalled: "Connect with GitHub with your Plane workspace to sync project work items.",
  },
  slack: {
    logo: SlackLogo,
    installed: "Activate Slack on individual projects to sync with specific channels.",
    notInstalled: "Connect with Slack with your Plane workspace to sync project work items.",
  },
  jira: {
    logo: JiraLogo,
    installed: "Jira Cloud connected. Use Workspace Settings → Imports to pull projects.",
    notInstalled: "Connect Jira Cloud with an email and API token to import work items.",
  },
};

// services
const integrationService = new IntegrationService();

const isEmptyCred = (value: string) => !value || value === "...";
const isTestPlaceholder = (value: string) =>
  value.startsWith("test-") || value.includes("PLACEHOLDER") || value.includes("local-test");

export const SingleIntegrationCard = observer(function SingleIntegrationCard({ integration }: Props) {
  // states
  const [deletingIntegration, setDeletingIntegration] = useState(false);
  const [showJiraForm, setShowJiraForm] = useState(false);
  const [jiraEmail, setJiraEmail] = useState("");
  const [jiraToken, setJiraToken] = useState("");
  const [jiraHost, setJiraHost] = useState("");
  const [installingJira, setInstallingJira] = useState(false);
  // router
  const { workspaceSlug } = useParams();
  // store hooks
  const { config } = useInstance();
  const { allowPermissions } = useUserPermissions();

  const isUserAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE);
  const { isMobile } = usePlatformOS();

  const githubAppName = (config?.github_app_name || "").trim();
  const slackClientId = (config?.slack_client_id || "").trim();

  const missingOauthCreds =
    (integration.provider === "github" && isEmptyCred(githubAppName)) ||
    (integration.provider === "slack" && isEmptyCred(slackClientId));

  const usingTestCreds =
    !missingOauthCreds &&
    ((integration.provider === "github" && isTestPlaceholder(githubAppName)) ||
      (integration.provider === "slack" && isTestPlaceholder(slackClientId)));

  const { startAuth, isConnecting: isInstalling } = useIntegrationPopup({
    provider: integration.provider,
    github_app_name: githubAppName,
    slack_client_id: slackClientId,
  });

  const { data: workspaceIntegrations } = useSWR(workspaceSlug ? WORKSPACE_INTEGRATIONS(workspaceSlug) : null, () =>
    workspaceSlug ? integrationService.getWorkspaceIntegrationsList(workspaceSlug) : null
  );

  const handleRemoveIntegration = async () => {
    if (!workspaceSlug || !integration || !workspaceIntegrations) return;

    const workspaceIntegrationId = Array.isArray(workspaceIntegrations)
      ? workspaceIntegrations.find((i) => i.integration === integration.id)?.id
      : undefined;

    setDeletingIntegration(true);

    try {
      await integrationService.deleteWorkspaceIntegration(workspaceSlug, workspaceIntegrationId ?? "");
      await mutate<IWorkspaceIntegration[]>(
        WORKSPACE_INTEGRATIONS(workspaceSlug),
        (prevData) => prevData?.filter((i) => i.id !== workspaceIntegrationId),
        false
      );
      setDeletingIntegration(false);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Deleted successfully!",
        message: `${integration.title} integration deleted successfully.`,
      });
    } catch {
      setDeletingIntegration(false);
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Error!",
        message: `${integration.title} integration could not be deleted. Please try again.`,
      });
    }
  };

  const isInstalled = Array.isArray(workspaceIntegrations)
    ? workspaceIntegrations.find((i: IWorkspaceIntegration) => i.integration_detail.id === integration.id)
    : undefined;

  return (
    <div className="flex items-center justify-between gap-2 border-b border-subtle bg-surface-1 px-4 py-6">
      <div className="flex items-start gap-4">
        <div className="h-10 w-10 flex-shrink-0">
          <img
            src={integrationDetails[integration.provider]?.logo || GithubLogo}
            className="h-full w-full object-cover"
            alt={`${integration.title} Logo`}
          />
        </div>
        <div>
          <h3 className="flex items-center gap-2 text-body-xs-medium">
            {integration.title}
            {workspaceIntegrations
              ? isInstalled && <CheckCircle className="h-3.5 w-3.5 fill-transparent text-success-primary" />
              : null}
          </h3>
          <p className="text-body-xs-regular text-secondary">
            {workspaceIntegrations
              ? isInstalled
                ? integrationDetails[integration.provider]?.installed || "Installed."
                : integrationDetails[integration.provider]?.notInstalled || "Not installed."
              : "Loading..."}
          </p>
          {missingOauthCreds && !isInstalled && (
            <p className="mt-1 text-11 text-danger-primary">
              Missing OAuth config. Set {integration.provider === "github" ? "GITHUB_APP_NAME" : "SLACK_CLIENT_ID"} in{" "}
              <code className="text-11">apps/api/.env</code> and restart the API.
            </p>
          )}
          {usingTestCreds && !isInstalled && (
            <p className="mt-1 text-11 text-tertiary">
              Using test placeholders — replace with real Slack/GitHub App credentials before Install will succeed.
            </p>
          )}
        </div>
      </div>

      {workspaceIntegrations ? (
        isInstalled ? (
          <Tooltip
            isMobile={isMobile}
            disabled={isUserAdmin}
            tooltipContent={!isUserAdmin ? "You don't have permission to perform this" : null}
          >
            <Button
              className={`${!isUserAdmin ? "hover:cursor-not-allowed" : ""}`}
              variant="error-fill"
              onClick={() => {
                if (!isUserAdmin) return;
                handleRemoveIntegration();
              }}
              disabled={!isUserAdmin}
              loading={deletingIntegration}
            >
              {deletingIntegration ? "Uninstalling..." : "Uninstall"}
            </Button>
          </Tooltip>
        ) : (
          <Tooltip
            isMobile={isMobile}
            disabled={isUserAdmin && !missingOauthCreds}
            tooltipContent={
              !isUserAdmin
                ? "You don't have permission to perform this"
                : missingOauthCreds
                  ? `Configure ${integration.provider === "github" ? "GITHUB_APP_NAME" : "SLACK_CLIENT_ID"} in apps/api/.env`
                  : null
            }
          >
            <Button
              className={`${!isUserAdmin || missingOauthCreds ? "hover:cursor-not-allowed" : ""}`}
              variant="primary"
              onClick={() => {
                if (!isUserAdmin || missingOauthCreds) return;
                if (integration.provider === "jira") {
                  setShowJiraForm(true);
                  return;
                }
                startAuth();
              }}
              disabled={!isUserAdmin || missingOauthCreds}
              loading={isInstalling || installingJira}
            >
              {isInstalling || installingJira ? "Installing..." : "Install"}
            </Button>
          </Tooltip>
        )
      ) : (
        <Loader>
          <Loader.Item height="32px" width="64px" />
        </Loader>
      )}
      {showJiraForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-backdrop/60 p-4">
          <div className="shadow-lg w-full max-w-md rounded-lg border border-subtle bg-surface-1 p-4">
            <h4 className="text-sm font-semibold">Connect Jira Cloud</h4>
            <div className="mt-3 space-y-2">
              <input
                className="text-sm w-full rounded border border-subtle bg-layer-1 px-3 py-2"
                placeholder="email"
                value={jiraEmail}
                onChange={(e) => setJiraEmail(e.target.value)}
              />
              <input
                className="text-sm w-full rounded border border-subtle bg-layer-1 px-3 py-2"
                placeholder="API token"
                type="password"
                value={jiraToken}
                onChange={(e) => setJiraToken(e.target.value)}
              />
              <input
                className="text-sm w-full rounded border border-subtle bg-layer-1 px-3 py-2"
                placeholder="your-domain.atlassian.net"
                value={jiraHost}
                onChange={(e) => setJiraHost(e.target.value)}
              />
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="secondary" onClick={() => setShowJiraForm(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                loading={installingJira}
                onClick={async () => {
                  if (!workspaceSlug) return;
                  setInstallingJira(true);
                  try {
                    const { AppInstallationService } = await import("@/services/app_installation.service");
                    const svc = new AppInstallationService();
                    await svc.addInstallationApp(workspaceSlug.toString(), "jira", {
                      email: jiraEmail,
                      api_token: jiraToken,
                      cloud_hostname: jiraHost,
                    });
                    mutate(WORKSPACE_INTEGRATIONS(workspaceSlug.toString()));
                    setShowJiraForm(false);
                    setToast({
                      type: TOAST_TYPE.SUCCESS,
                      title: "Connected",
                      message: "Jira integration installed.",
                    });
                  } catch (e: any) {
                    setToast({
                      type: TOAST_TYPE.ERROR,
                      title: "Error",
                      message: e?.data?.error || "Could not connect Jira",
                    });
                  } finally {
                    setInstallingJira(false);
                  }
                }}
              >
                Connect
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});
