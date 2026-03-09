import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface OnboardingState {
  // GitHub
  repoUrl: string | null;
  repoProvider: string | null;

  // Jira
  jiraProjectKey: string | null;
  jiraWorkspaceUrl: string | null;
  jiraStatusMappings: Record<string, string> | null;

  // Slack
  slackChannelId: string | null;
  slackChannelName: string | null;

  // Confluence
  confluenceBaseUrl: string | null;
  confluenceSpaceKeys: string[];
  confluenceIncludeLabels: string[];

  // Agent
  agentName: string | null;
  agentAvatar: string | null;
  projectContext: string | null;

  // Meta
  completedAt: string | null;

  // Actions
  setConfluenceConfig: (
    baseUrl: string,
    spaceKeys: string[],
    includeLabels: string[]
  ) => void;
  hydrateFromApi: (config: {
    repo_url?: string | null;
    repo_provider?: string | null;
    jira_project_key?: string | null;
    jira_workspace_url?: string | null;
    jira_status_mappings?: Record<string, string> | null;
    slack_channel_id?: string | null;
    slack_channel_name?: string | null;
    confluence_base_url?: string | null;
    confluence_space_keys?: string[] | null;
    confluence_include_labels?: string[] | null;
    agent_name?: string | null;
    agent_avatar?: string | null;
    project_context?: string | null;
    completed_at?: string | null;
  }) => void;
}

export const useOnboardingStore = create<OnboardingState>()(
  persist(
    (set) => ({
      // GitHub
      repoUrl: null,
      repoProvider: null,

      // Jira
      jiraProjectKey: null,
      jiraWorkspaceUrl: null,
      jiraStatusMappings: null,

      // Slack
      slackChannelId: null,
      slackChannelName: null,

      // Confluence
      confluenceBaseUrl: null,
      confluenceSpaceKeys: [],
      confluenceIncludeLabels: [],

      // Agent
      agentName: null,
      agentAvatar: null,
      projectContext: null,

      // Meta
      completedAt: null,

      // Actions
      setConfluenceConfig: (baseUrl, spaceKeys, includeLabels) =>
        set({
          confluenceBaseUrl: baseUrl,
          confluenceSpaceKeys: spaceKeys,
          confluenceIncludeLabels: includeLabels,
        }),

      hydrateFromApi: (config) =>
        set({
          repoUrl: config.repo_url ?? null,
          repoProvider: config.repo_provider ?? null,
          jiraProjectKey: config.jira_project_key ?? null,
          jiraWorkspaceUrl: config.jira_workspace_url ?? null,
          jiraStatusMappings: config.jira_status_mappings ?? null,
          slackChannelId: config.slack_channel_id ?? null,
          slackChannelName: config.slack_channel_name ?? null,
          confluenceBaseUrl: config.confluence_base_url ?? null,
          confluenceSpaceKeys: config.confluence_space_keys ?? [],
          confluenceIncludeLabels: config.confluence_include_labels ?? [],
          agentName: config.agent_name ?? null,
          agentAvatar: config.agent_avatar ?? null,
          projectContext: config.project_context ?? null,
          completedAt: config.completed_at ?? null,
        }),
    }),
    {
      name: "kronode-onboarding",
    }
  )
);
