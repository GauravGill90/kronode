import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { OnboardingState } from "./types";

interface OnboardingStore extends OnboardingState {
  setStep: (step: number) => void;
  setAgentProfile: (data: OnboardingState["agentProfile"]) => void;
  setAccount: (data: OnboardingState["account"]) => void;
  setRepo: (data: OnboardingState["repo"]) => void;
  setJira: (data: OnboardingState["jira"]) => void;
  setSlack: (data: OnboardingState["slack"]) => void;
  setDocs: (data: OnboardingState["docs"]) => void;
  setCapabilities: (data: OnboardingState["capabilities"]) => void;
  setGuardrails: (data: OnboardingState["guardrails"]) => void;
  setAgent: (data: OnboardingState["agent"]) => void;
  setProjectContext: (context: string) => void;
  setCodingStandards: (standards: string) => void;
  reset: () => void;
}

const initialState: OnboardingState = {
  currentStep: 1,
  agentProfile: null,
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
};

export const useOnboardingStore = create<OnboardingStore>()(
  persist(
    (set) => ({
      ...initialState,
      setStep: (step) => set({ currentStep: step }),
      setAgentProfile: (data) => set({ agentProfile: data }),
      setAccount: (data) => set({ account: data }),
      setRepo: (data) => set({ repo: data }),
      setJira: (data) => set({ jira: data }),
      setSlack: (data) => set({ slack: data }),
      setDocs: (data) => set({ docs: data }),
      setCapabilities: (data) => set({ capabilities: data }),
      setGuardrails: (data) => set({ guardrails: data }),
      setAgent: (data) => set({ agent: data }),
      setProjectContext: (context) => set({ projectContext: context }),
      setCodingStandards: (standards) => set({ codingStandards: standards }),
      reset: () => set(initialState),
    }),
    { name: "kronode-onboarding" }
  )
);
