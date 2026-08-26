/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { NotAuthorizedView } from "@/components/auth-screens/not-authorized-view";
import { PageHead } from "@/components/core/page-title";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { useProject } from "@/hooks/store/use-project";
import { useWorkspace } from "@/hooks/store/use-workspace";
import { useUserPermissions } from "@/hooks/store/user";
import { GithubIntegrationService } from "@/services/integrations/github.service";
import { JiraImporterService } from "@/services/integrations/jira.service";
import { IntegrationService } from "@/services/integrations";
import type { Route } from "./+types/page";

const integrationService = new IntegrationService();
const githubService = new GithubIntegrationService();
const jiraService = new JiraImporterService();

function WorkspaceImportsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  const { allowPermissions } = useUserPermissions();
  const { currentWorkspace } = useWorkspace();
  const { workspaceProjectIds, getProjectById } = useProject();
  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.WORKSPACE);

  const [projectId, setProjectId] = useState("");
  const [githubOwner, setGithubOwner] = useState("");
  const [githubRepo, setGithubRepo] = useState("");
  const [jiraEmail, setJiraEmail] = useState("");
  const [jiraToken, setJiraToken] = useState("");
  const [jiraHost, setJiraHost] = useState("");
  const [jiraKey, setJiraKey] = useState("");
  const [busy, setBusy] = useState(false);

  const { data: imports, mutate } = useSWR(isAdmin ? `IMPORTS_${workspaceSlug}` : null, () =>
    isAdmin ? integrationService.getImporterServicesList(workspaceSlug) : null
  );

  if (!isAdmin) return <NotAuthorizedView section="settings" className="h-auto" />;

  const projects = (workspaceProjectIds || []).map((id) => getProjectById(id)).filter(Boolean);

  const runGithubImport = async () => {
    if (!projectId || !githubOwner || !githubRepo) return;
    setBusy(true);
    try {
      const info = await githubService.getGithubRepoInfo(workspaceSlug, { owner: githubOwner, repo: githubRepo });
      await githubService.createGithubServiceImport(workspaceSlug, {
        metadata: {
          owner: githubOwner,
          name: githubRepo,
          repository_id: (info as any)?.id,
          url: `https://github.com/${githubOwner}/${githubRepo}`,
        },
        data: { users: [] },
        config: { sync: true },
        project_id: projectId,
      } as any);
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Queued", message: "GitHub import started." });
      mutate();
    } catch (e: any) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: e?.error || "GitHub import failed" });
    } finally {
      setBusy(false);
    }
  };

  const runJiraImport = async () => {
    if (!projectId || !jiraEmail || !jiraToken || !jiraHost || !jiraKey) return;
    setBusy(true);
    try {
      await jiraService.createJiraImporter(workspaceSlug, {
        metadata: {
          email: jiraEmail,
          api_token: jiraToken,
          cloud_hostname: jiraHost,
          project_key: jiraKey,
        },
        data: { users: [] },
        config: {},
        project_id: projectId,
      } as any);
      setToast({ type: TOAST_TYPE.SUCCESS, title: "Queued", message: "Jira import started." });
      mutate();
    } catch (e: any) {
      setToast({ type: TOAST_TYPE.ERROR, title: "Error", message: e?.error || "Jira import failed" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <SettingsContentWrapper>
      <PageHead title={currentWorkspace?.name ? `${currentWorkspace.name} - Imports` : undefined} />
      <div className="space-y-8 p-4">
        <div>
          <h2 className="text-lg font-semibold">Imports</h2>
          <p className="text-sm text-secondary">One-shot import from GitHub or Jira into a Plane project.</p>
        </div>

        <label className="text-sm block">
          Target project
          <select
            className="mt-1 w-full rounded border border-subtle bg-surface-1 px-3 py-2"
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
          >
            <option value="">Select project</option>
            {projects.map((p: any) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>

        <section className="rounded border border-subtle p-4">
          <h3 className="font-medium">GitHub</h3>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <input
              className="rounded border border-subtle bg-surface-1 px-3 py-2"
              placeholder="owner"
              value={githubOwner}
              onChange={(e) => setGithubOwner(e.target.value)}
            />
            <input
              className="rounded border border-subtle bg-surface-1 px-3 py-2"
              placeholder="repository"
              value={githubRepo}
              onChange={(e) => setGithubRepo(e.target.value)}
            />
          </div>
          <Button className="mt-3" variant="primary" onClick={runGithubImport} loading={busy} disabled={!projectId}>
            Import from GitHub
          </Button>
        </section>

        <section className="rounded border border-subtle p-4">
          <h3 className="font-medium">Jira Cloud</h3>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            <input
              className="rounded border border-subtle bg-surface-1 px-3 py-2"
              placeholder="email"
              value={jiraEmail}
              onChange={(e) => setJiraEmail(e.target.value)}
            />
            <input
              className="rounded border border-subtle bg-surface-1 px-3 py-2"
              placeholder="API token"
              type="password"
              value={jiraToken}
              onChange={(e) => setJiraToken(e.target.value)}
            />
            <input
              className="rounded border border-subtle bg-surface-1 px-3 py-2"
              placeholder="your-domain.atlassian.net"
              value={jiraHost}
              onChange={(e) => setJiraHost(e.target.value)}
            />
            <input
              className="rounded border border-subtle bg-surface-1 px-3 py-2"
              placeholder="PROJECT KEY"
              value={jiraKey}
              onChange={(e) => setJiraKey(e.target.value)}
            />
          </div>
          <Button className="mt-3" variant="primary" onClick={runJiraImport} loading={busy} disabled={!projectId}>
            Import from Jira
          </Button>
        </section>

        <section>
          <h3 className="font-medium">Recent imports</h3>
          <ul className="text-sm mt-2 space-y-2">
            {(imports || []).map((item: any) => (
              <li key={item.id} className="rounded border border-subtle px-3 py-2">
                {item.service} · {item.status} · {item.project_detail?.name || item.project}
              </li>
            ))}
            {imports && imports.length === 0 && <li className="text-secondary">No imports yet.</li>}
          </ul>
        </section>
      </div>
    </SettingsContentWrapper>
  );
}

export default observer(WorkspaceImportsPage);
