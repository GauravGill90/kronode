import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { OnboardingState } from "./types";

interface OnboardingStore extends OnboardingState {
  setStep: (step: number) => void;
  setAccount: (data: OnboardingState["account"]) => void;
  setRepo: (data: OnboardingState["repo"]) => void;
  setJira: (data: OnboardingState["jira"]) => void;
  setSlack: (data: OnboardingState["slack"]) => void;
  setDocs: (data: OnboardingState["docs"]) => void;
  setProjectContext: (context: string) => void;
  setCodingStandards: (standards: string) => void;
  setIngestionDone: (done: boolean) => void;
  setApiKeyGenerated: (generated: boolean) => void;
  reset: () => void;
  // Legacy setters (kept for backward compat with settings hydration)
  setAgentProfile: (data: any) => void;
  setSkills: (data: any) => void;
  setCapabilities: (data: any) => void;
  setGuardrails: (data: any) => void;
  setAgent: (data: any) => void;
}

const initialState: OnboardingState = {
  currentStep: 1,
  agentProfile: null,
  skills: null,
  account: null,
  repo: null,
  jira: null,
  slack: null,
  docs: null,
  capabilities: null,
  guardrails: null,
  agent: null,
  projectContext: "",
  codingStandards: "",
  ingestionDone: false,
  apiKeyGenerated: false,
};

export const useOnboardingStore = create<OnboardingStore>()(
  persist(
    (set) => ({
      ...initialState,
      setStep: (step) => set({ currentStep: step }),
      setAccount: (data) => set({ account: data }),
      setRepo: (data) => set({ repo: data }),
      setJira: (data) => set({ jira: data }),
      setSlack: (data) => set({ slack: data }),
      setDocs: (data) => set({ docs: data }),
      setProjectContext: (context) => set({ projectContext: context }),
      setCodingStandards: (standards) => set({ codingStandards: standards }),
      setIngestionDone: (done) => set({ ingestionDone: done }),
      setApiKeyGenerated: (generated) => set({ apiKeyGenerated: generated }),
      reset: () => set(initialState),
      // Legacy
      setAgentProfile: (data) => set({ agentProfile: data }),
      setSkills: (data) => set({ skills: data }),
      setCapabilities: (data) => set({ capabilities: data }),
      setGuardrails: (data) => set({ guardrails: data }),
      setAgent: (data) => set({ agent: data }),
    }),
    { name: "kronode-onboarding" }
  )
);
