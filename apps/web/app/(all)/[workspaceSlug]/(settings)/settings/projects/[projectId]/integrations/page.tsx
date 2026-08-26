/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import useSWR from "swr";
import { EUserPermissions, EUserPermissionsLevel, WORKSPACE_INTEGRATIONS } from "@plane/constants";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { IntegrationCard } from "@/components/project/integration-card";
import { IntegrationAndImportExportBanner } from "@/components/ui/integration-and-import-export-banner";
import { IntegrationsSettingsLoader } from "@/components/ui/loader/settings/integration";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { useProject } from "@/hooks/store/use-project";
import { useUserPermissions } from "@/hooks/store/user";
import { IntegrationService } from "@/services/integrations";
import type { Route } from "./+types/page";

const integrationService = new IntegrationService();

function ProjectIntegrationsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const { allowPermissions } = useUserPermissions();
  const { getProjectById } = useProject();
  const project = getProjectById(projectId);
  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.PROJECT);

  const { data: workspaceIntegrations } = useSWR(isAdmin ? WORKSPACE_INTEGRATIONS(workspaceSlug) : null, () =>
    isAdmin ? integrationService.getWorkspaceIntegrationsList(workspaceSlug) : null
  );

  if (!isAdmin) return <NotAuthorizedView section="settings" className="h-auto" />;

  const pageTitle = project?.name ? `${project.name} - Integrations` : undefined;

  return (
    <SettingsContentWrapper>
      <PageHead title={pageTitle} />
      <IntegrationAndImportExportBanner bannerName="Integrations" />
      <div>
        {workspaceIntegrations ? (
          workspaceIntegrations.length > 0 ? (
            workspaceIntegrations
              .filter((i) => ["github", "slack"].includes(i.integration_detail?.provider))
              .map((integration) => <IntegrationCard key={integration.id} integration={integration} />)
          ) : (
            <p className="text-sm px-4 py-6 text-secondary">
              No workspace integrations installed. Connect GitHub or Slack under Workspace Settings → Integrations
              first.
            </p>
          )
        ) : (
          <IntegrationsSettingsLoader />
        )}
      </div>
    </SettingsContentWrapper>
  );
}

export default observer(ProjectIntegrationsPage);
