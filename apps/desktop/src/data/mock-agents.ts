import type { AgentViewModel } from "@/types/agents";

export const mockAgents: AgentViewModel[] = [
  {
    id: "commander",
    name: "Commander",
    role: "Intent routing",
    status: "active",
    load: 0.62,
    detail: "Awaiting Phase 2 orchestration",
  },
  {
    id: "planner",
    name: "Planner",
    role: "Task decomposition",
    status: "idle",
    load: 0.12,
    detail: "Standby — no mission queue",
  },
  {
    id: "memory",
    name: "Memory",
    role: "Context retention",
    status: "degraded",
    load: 0.88,
    detail: "Placeholder graph — Phase 2",
  },
  {
    id: "ops",
    name: "Ops Bridge",
    role: "System interface",
    status: "offline",
    load: 0,
    detail: "Hammerspoon bridge disabled (Phase 3)",
  },
];
