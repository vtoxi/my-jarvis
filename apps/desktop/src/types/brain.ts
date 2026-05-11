export type OllamaModelInfo = {
  name: string;
  size?: number | null;
  modified_at?: string | null;
};

export type ModelsResponse = {
  ollama_reachable: boolean;
  ollama_error: string | null;
  active_model: string;
  installed: OllamaModelInfo[];
  recommended_defaults: string[];
};

export type AgentStatusItem = {
  id: string;
  name: string;
  phase: number;
  enabled: boolean;
  description: string;
  last_event: { agent_id: string; summary: string; created_at: string } | null;
};

export type AgentsStatusResponse = {
  agents: AgentStatusItem[];
};

export type CommandResponse = {
  reply: string;
  session_id: string;
  model: string;
  agents_used: { id: string; name: string; summary: string }[];
  errors: string[];
};
