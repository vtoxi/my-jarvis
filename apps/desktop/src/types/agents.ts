export type AgentStatus = "idle" | "active" | "degraded" | "offline";

export type AgentViewModel = {
  id: string;
  name: string;
  role: string;
  status: AgentStatus;
  load: number;
  detail: string;
};
