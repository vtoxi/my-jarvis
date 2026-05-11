import type { AgentsStatusResponse, CommandResponse, ModelsResponse } from "@/types/brain";
import type { ProfilesListResponse, SystemStatus, WorkflowRunResponse } from "@/types/automation";

export type HealthResponse = {
  status: string;
  service: string;
  ollama?: {
    reachable: boolean;
    error?: string | null;
  };
};

export type VersionResponse = {
  version: string;
  service: string;
};

function joinUrl(baseUrl: string, path: string): URL {
  return new URL(path, baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`);
}

function parseFastApiDetailPayload(detail: unknown): { message: string; operatorTakeover: string[] } {
  if (typeof detail === "string") return { message: detail, operatorTakeover: [] };
  if (detail && typeof detail === "object") {
    const o = detail as { message?: unknown; operator_takeover?: unknown };
    const message = typeof o.message === "string" ? o.message : "Request failed";
    const raw = o.operator_takeover;
    const operatorTakeover = Array.isArray(raw)
      ? raw.filter((x): x is string => typeof x === "string")
      : [];
    return { message, operatorTakeover };
  }
  return { message: "Request failed", operatorTakeover: [] };
}

function throwHttpErrorWithTakeover(label: string, status: number, bodyText: string): never {
  let message = bodyText?.trim() || `${label} ${status}`;
  let takeover: string[] = [];
  try {
    const j = JSON.parse(bodyText) as { detail?: unknown };
    const p = parseFastApiDetailPayload(j.detail);
    message = p.message || message;
    takeover = p.operatorTakeover;
  } catch {
    /* keep message as body */
  }
  const err = new Error(
    takeover.length ? [message, ...takeover.map((l) => `• ${l}`)].join("\n") : message,
  ) as Error & { operatorTakeover?: string[] };
  if (takeover.length) err.operatorTakeover = takeover;
  throw err;
}

export async function fetchHealth(baseUrl: string, signal?: AbortSignal): Promise<HealthResponse> {
  const res = await fetch(joinUrl(baseUrl, "/health"), { signal, method: "GET" });
  if (!res.ok) {
    throw new Error(`health ${res.status}`);
  }
  return (await res.json()) as HealthResponse;
}

export async function fetchVersion(baseUrl: string, signal?: AbortSignal): Promise<VersionResponse> {
  const res = await fetch(joinUrl(baseUrl, "/version"), { signal, method: "GET" });
  if (!res.ok) {
    throw new Error(`version ${res.status}`);
  }
  return (await res.json()) as VersionResponse;
}

export async function fetchModels(
  baseUrl: string,
  activeModel: string,
  signal?: AbortSignal,
): Promise<ModelsResponse> {
  const url = joinUrl(baseUrl, "/models");
  url.searchParams.set("active_model", activeModel);
  const res = await fetch(url, { signal, method: "GET" });
  if (!res.ok) {
    throw new Error(`models ${res.status}`);
  }
  return (await res.json()) as ModelsResponse;
}

export async function fetchAgentsStatus(
  baseUrl: string,
  sessionId?: string,
  signal?: AbortSignal,
): Promise<AgentsStatusResponse> {
  const url = joinUrl(baseUrl, "/agents/status");
  if (sessionId) {
    url.searchParams.set("session_id", sessionId);
  }
  const res = await fetch(url, { signal, method: "GET" });
  if (!res.ok) {
    throw new Error(`agents ${res.status}`);
  }
  return (await res.json()) as AgentsStatusResponse;
}

export async function postCommand(
  baseUrl: string,
  payload: { message: string; session_id: string; model?: string },
  signal?: AbortSignal,
): Promise<CommandResponse> {
  const res = await fetch(joinUrl(baseUrl, "/command"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `command ${res.status}`);
  }
  return (await res.json()) as CommandResponse;
}

export async function fetchSystemStatus(baseUrl: string, signal?: AbortSignal): Promise<SystemStatus> {
  const res = await fetch(joinUrl(baseUrl, "/system/status"), { signal, method: "GET" });
  if (!res.ok) {
    throw new Error(`system ${res.status}`);
  }
  return (await res.json()) as SystemStatus;
}

export async function postKill(baseUrl: string, signal?: AbortSignal): Promise<{ armed: boolean; message: string }> {
  const res = await fetch(joinUrl(baseUrl, "/kill"), { method: "POST", signal });
  if (!res.ok) {
    throw new Error(`kill ${res.status}`);
  }
  return (await res.json()) as { armed: boolean; message: string };
}

export async function postSystemArm(
  baseUrl: string,
  armed: boolean,
  signal?: AbortSignal,
): Promise<{ armed: boolean }> {
  const res = await fetch(joinUrl(baseUrl, "/system/arm"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ armed }),
    signal,
  });
  if (!res.ok) {
    throw new Error(`arm ${res.status}`);
  }
  return (await res.json()) as { armed: boolean };
}

export async function fetchAutomationProfiles(
  baseUrl: string,
  signal?: AbortSignal,
): Promise<ProfilesListResponse> {
  const res = await fetch(joinUrl(baseUrl, "/automation/profiles"), { signal, method: "GET" });
  if (!res.ok) {
    throw new Error(`profiles ${res.status}`);
  }
  return (await res.json()) as ProfilesListResponse;
}

export async function postWorkflowRun(
  baseUrl: string,
  payload: { profile_id: string; session_id: string; challenge?: string | null },
  signal?: AbortSignal,
): Promise<WorkflowRunResponse> {
  const res = await fetch(joinUrl(baseUrl, "/workflows/run"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `workflow ${res.status}`);
  }
  return (await res.json()) as WorkflowRunResponse;
}

export type SlackStatus = {
  connected: boolean;
  team_id: string | null;
  team_name: string | null;
  phase: string;
  write_enabled: boolean;
  oauth_configured: boolean;
  oauth_scopes?: string;
  /** Must be added verbatim under Slack app → OAuth & Permissions → Redirect URLs */
  redirect_uri?: string;
  post_oauth_redirect?: string;
  /** False when redirect_uri is a non-web scheme (Slack rejects bot installs). */
  redirect_uri_ok?: boolean;
  redirect_uri_issue?: string;
  redirect_uri_note?: string;
};

export type SlackRankedMessage = {
  channel_id: string;
  channel_name: string | null;
  ts: string;
  user_id: string | null;
  text: string;
  score: number;
  reasons: string[];
};

export type SlackPriorityResponse = {
  ranked_messages: SlackRankedMessage[];
  heatmap: { channel_id: string; activity: number; intensity: number }[];
  slack_health_score: number;
  priority_keywords: string[];
  gather_errors?: string[];
};

export type SlackUnreadChannel = {
  channel_id: string;
  name: string | null;
  high_priority_hits: number;
  top_snippet: string;
  top_score: number;
};

export type SlackUnreadResponse = {
  channels: SlackUnreadChannel[];
  note?: string;
  gather_errors?: string[];
};

export type SlackBriefingResponse = {
  briefing_markdown: string;
  briefing_core: string;
  draft_hints: string;
  priority: SlackPriorityResponse;
  model: string;
  gather_errors?: string[];
  channels_scanned?: { id: string; name: string; message_count: number; importance: number }[];
};

export type SystemSubsystemHealth = {
  id: string;
  ok: boolean;
  detail?: string | null;
  latency_ms?: number | null;
  /** When true, this row is informational only and not counted in health_score */
  optional_for_score?: boolean;
};

export type SystemHealth = {
  status: string;
  health_score: number;
  subsystems: SystemSubsystemHealth[];
  notes?: string[];
};

export type SystemIncident = {
  id: string;
  created_at: string;
  severity: string;
  subsystem: string | null;
  summary: string;
  detail: Record<string, unknown>;
  repair_output?: Record<string, unknown> | null;
};

export type SystemErrorsPayload = {
  incidents: SystemIncident[];
  log_tail_hint?: string | null;
};

export type SystemAuditResponse = {
  audit_id: string;
  mode: string;
  tools: Record<string, unknown>;
  debt_score: number;
  synthesis_markdown: string;
  categories: Record<string, string[]>;
  operator_takeover_checklist?: string[];
};

export type SystemRepairResponse = {
  incident_id: string;
  requires_human_approval: boolean;
  root_cause_hypothesis: string;
  severity: string;
  user_visible_summary: string;
  recommended_commands: string[];
  patch_plan: { path?: string; rationale?: string }[];
  raw_markdown?: string | null;
  operator_takeover_checklist?: string[];
};

export type SystemPatchRow = {
  id: string;
  created_at: string;
  status: string;
  branch_name: string;
  base_sha: string;
  diff_sha256: string;
  outcome_text?: string | null;
  applied_at?: string | null;
  rolled_back_at?: string | null;
};

export async function fetchSystemHealth(baseUrl: string, signal?: AbortSignal): Promise<SystemHealth> {
  const res = await fetch(joinUrl(baseUrl, "/system/health"), { signal, method: "GET" });
  if (!res.ok) throw new Error(`system health ${res.status}`);
  return (await res.json()) as SystemHealth;
}

export async function fetchSystemErrors(baseUrl: string, signal?: AbortSignal): Promise<SystemErrorsPayload> {
  const res = await fetch(joinUrl(baseUrl, "/system/errors"), { signal, method: "GET" });
  if (!res.ok) throw new Error(`system errors ${res.status}`);
  return (await res.json()) as SystemErrorsPayload;
}

export async function fetchSystemPatchQueue(
  baseUrl: string,
  signal?: AbortSignal,
): Promise<{ patches: SystemPatchRow[] }> {
  const res = await fetch(joinUrl(baseUrl, "/system/patch/queue"), { signal, method: "GET" });
  if (!res.ok) throw new Error(`patch queue ${res.status}`);
  return (await res.json()) as { patches: SystemPatchRow[] };
}

export async function postSystemAudit(
  baseUrl: string,
  body: { mode?: "audit" | "improve"; run_tools?: boolean },
  signal?: AbortSignal,
): Promise<SystemAuditResponse> {
  const res = await fetch(joinUrl(baseUrl, "/system/audit"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode: body.mode ?? "audit", run_tools: body.run_tools ?? false }),
    signal,
  });
  if (!res.ok) {
    const t = await res.text();
    throwHttpErrorWithTakeover("audit", res.status, t);
  }
  return (await res.json()) as SystemAuditResponse;
}

export type SystemAutoworkStatus = {
  enabled: boolean;
  schedule_enabled: boolean;
  interval_s: number;
  last_run?: Record<string, unknown> | null;
  restart_request_path?: string | null;
  restart_pending?: boolean;
};

export type SystemAutoworkTickResponse = {
  ok: boolean;
  summary: Record<string, unknown>;
  event_logged?: boolean;
  note?: string;
};

export async function fetchAutoworkStatus(baseUrl: string, signal?: AbortSignal): Promise<SystemAutoworkStatus> {
  const res = await fetch(joinUrl(baseUrl, "/system/autowork/status"), { signal, method: "GET" });
  if (!res.ok) throw new Error(`autowork status ${res.status}`);
  return (await res.json()) as SystemAutoworkStatus;
}

export async function postAutoworkTick(baseUrl: string, signal?: AbortSignal): Promise<SystemAutoworkTickResponse> {
  const res = await fetch(joinUrl(baseUrl, "/system/autowork/tick"), { method: "POST", signal });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `autowork tick ${res.status}`);
  }
  return (await res.json()) as SystemAutoworkTickResponse;
}

export async function postSystemRepair(
  baseUrl: string,
  body: { context?: string | null },
  signal?: AbortSignal,
): Promise<SystemRepairResponse> {
  const res = await fetch(joinUrl(baseUrl, "/system/repair"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ context: body.context ?? null }),
    signal,
  });
  if (!res.ok) {
    const t = await res.text();
    throwHttpErrorWithTakeover("repair", res.status, t);
  }
  return (await res.json()) as SystemRepairResponse;
}

export type EvolutionStatus = {
  twin_version: number;
  twin_confidence: Record<string, number>;
  last_idle_run_at: string | null;
  last_idle_run_id: string | null;
  pending_approvals: number;
  evolution_events_24h: number;
  strategic_maturity_index: number;
  self_healing_hint?: string | null;
  ethics_note?: string;
  idle_schedule_enabled?: boolean;
  idle_schedule_interval_s?: number | null;
  knowledge_enabled?: boolean;
  knowledge_chunk_count?: number;
  autonomy_tier?: string;
  autonomy_note?: string;
};

export type EvolutionSandboxBenchmarkResponse = {
  ok: boolean;
  skipped?: boolean;
  reason?: string | null;
  repo_root?: string | null;
  summary?: Record<string, unknown> | null;
  note?: string;
};

export type EvolutionIdleResponse = {
  run_id: string;
  report_markdown: string;
  actions_proposed: string[];
  requires_approval: boolean;
};

export type EvolutionLogEntry = {
  id: number;
  created_at: string;
  kind: string;
  payload: Record<string, unknown>;
};

export async function fetchEvolutionStatus(baseUrl: string, signal?: AbortSignal): Promise<EvolutionStatus> {
  const res = await fetch(joinUrl(baseUrl, "/evolution/status"), { signal, method: "GET" });
  if (!res.ok) throw new Error(`evolution status ${res.status}`);
  return (await res.json()) as EvolutionStatus;
}

export async function postEvolutionIdle(baseUrl: string, signal?: AbortSignal): Promise<EvolutionIdleResponse> {
  const res = await fetch(joinUrl(baseUrl, "/evolution/idle"), { method: "POST", signal });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `evolution idle ${res.status}`);
  }
  return (await res.json()) as EvolutionIdleResponse;
}

export async function postEvolutionSandboxBenchmark(
  baseUrl: string,
  signal?: AbortSignal,
): Promise<EvolutionSandboxBenchmarkResponse> {
  const res = await fetch(joinUrl(baseUrl, "/evolution/sandbox/benchmark"), { method: "POST", signal });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(t || `evolution sandbox benchmark ${res.status}`);
  }
  return (await res.json()) as EvolutionSandboxBenchmarkResponse;
}

export async function fetchEvolutionLogs(
  baseUrl: string,
  limit = 40,
  signal?: AbortSignal,
): Promise<{ entries: EvolutionLogEntry[] }> {
  const u = joinUrl(baseUrl, "/evolution/logs");
  u.searchParams.set("limit", String(limit));
  const res = await fetch(u, { signal, method: "GET" });
  if (!res.ok) throw new Error(`evolution logs ${res.status}`);
  return (await res.json()) as { entries: EvolutionLogEntry[] };
}

export async function fetchEvolutionPredictions(
  baseUrl: string,
  signal?: AbortSignal,
): Promise<{ predictions: { id: string; severity: string; title: string; detail: string }[] }> {
  const res = await fetch(joinUrl(baseUrl, "/evolution/predictions"), { signal, method: "GET" });
  if (!res.ok) throw new Error(`evolution predictions ${res.status}`);
  return (await res.json()) as { predictions: { id: string; severity: string; title: string; detail: string }[] };
}

export function slackConnectUrl(baseUrl: string): string {
  return joinUrl(baseUrl, "/slack/connect").href;
}

export async function fetchSlackStatus(baseUrl: string, signal?: AbortSignal): Promise<SlackStatus> {
  const res = await fetch(joinUrl(baseUrl, "/slack/status"), { signal, method: "GET" });
  if (!res.ok) {
    throw new Error(`slack status ${res.status}`);
  }
  return (await res.json()) as SlackStatus;
}

export async function fetchSlackPriority(baseUrl: string, signal?: AbortSignal): Promise<SlackPriorityResponse> {
  const res = await fetch(joinUrl(baseUrl, "/slack/priority"), { signal, method: "GET" });
  if (!res.ok) {
    throw new Error(`slack priority ${res.status}`);
  }
  return (await res.json()) as SlackPriorityResponse;
}

export async function fetchSlackUnread(baseUrl: string, signal?: AbortSignal): Promise<SlackUnreadResponse> {
  const res = await fetch(joinUrl(baseUrl, "/slack/unread"), { signal, method: "GET" });
  if (!res.ok) {
    throw new Error(`slack unread ${res.status}`);
  }
  return (await res.json()) as SlackUnreadResponse;
}

export async function postSlackBriefing(
  baseUrl: string,
  payload: { max_channels?: number; messages_per_channel?: number; model?: string | null },
  signal?: AbortSignal,
): Promise<SlackBriefingResponse> {
  const res = await fetch(joinUrl(baseUrl, "/slack/briefing"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `slack briefing ${res.status}`);
  }
  return (await res.json()) as SlackBriefingResponse;
}

export async function postSlackDraft(
  baseUrl: string,
  payload: {
    channel_id: string;
    thread_ts?: string | null;
    context: string;
    tone: "executive" | "friendly" | "technical";
    model?: string | null;
  },
  signal?: AbortSignal,
): Promise<{ draft_markdown: string; tone: string; model: string; approval_required: boolean; auto_send: boolean }> {
  const res = await fetch(joinUrl(baseUrl, "/slack/draft"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `slack draft ${res.status}`);
  }
  return (await res.json()) as {
    draft_markdown: string;
    tone: string;
    model: string;
    approval_required: boolean;
    auto_send: boolean;
  };
}

export async function postSlackSendPrepare(
  baseUrl: string,
  payload: { channel_id: string; thread_ts?: string | null; text: string },
  signal?: AbortSignal,
): Promise<{ approval_token: string; expires_at_unix: number; message: string }> {
  const res = await fetch(joinUrl(baseUrl, "/slack/send/prepare"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `slack send prepare ${res.status}`);
  }
  return (await res.json()) as { approval_token: string; expires_at_unix: number; message: string };
}

export async function postSlackSend(
  baseUrl: string,
  payload: { approval_token: string; text: string },
  signal?: AbortSignal,
): Promise<{ ok: boolean; ts?: string; channel?: string; auto_send: boolean; note?: string }> {
  const res = await fetch(joinUrl(baseUrl, "/slack/send"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `slack send ${res.status}`);
  }
  return (await res.json()) as { ok: boolean; ts?: string; channel?: string; auto_send: boolean; note?: string };
}

export type CopilotStatus = {
  monitoring_paused: boolean;
  private_mode: boolean;
  assist_mode: "passive" | "advisory" | "interactive" | "controlled";
  excluded_app_substrings: string[];
  capture_interval_s: number;
  screen_intel_enabled: boolean;
  last_front_app: string | null;
  last_tags: string[];
  last_capture_mono: number;
  recent_snapshots: { front_app?: string | null; window_title?: string | null; ocr_excerpt?: string; tags?: string[] }[];
};

export type ScreenContextResponse = {
  front_app: string | null;
  window_title: string | null;
  tags: string[];
  ocr_excerpt: string;
  monitoring_paused: boolean;
  private_mode: boolean;
  assist_mode: string;
  visible_indicator: boolean;
  trust_note?: string;
  productivity_score?: number | null;
};

export async function fetchCopilotStatus(baseUrl: string, signal?: AbortSignal): Promise<CopilotStatus> {
  const res = await fetch(joinUrl(baseUrl, "/copilot/status"), { signal, method: "GET" });
  if (!res.ok) {
    throw new Error(`copilot status ${res.status}`);
  }
  return (await res.json()) as CopilotStatus;
}

export async function postCopilotConfig(
  baseUrl: string,
  payload: {
    monitoring_paused?: boolean;
    private_mode?: boolean;
    assist_mode?: CopilotStatus["assist_mode"];
    excluded_app_substrings?: string[];
    capture_interval_s?: number;
  },
  signal?: AbortSignal,
): Promise<{ ok: boolean }> {
  const res = await fetch(joinUrl(baseUrl, "/copilot/config"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) {
    throw new Error(`copilot config ${res.status}`);
  }
  return (await res.json()) as { ok: boolean };
}

export async function postScreenCapture(
  baseUrl: string,
  payload: { include_image?: boolean; force?: boolean },
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  const res = await fetch(joinUrl(baseUrl, "/screen/capture"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `screen capture ${res.status}`);
  }
  return (await res.json()) as Record<string, unknown>;
}

export async function fetchScreenContext(
  baseUrl: string,
  refresh: boolean,
  signal?: AbortSignal,
): Promise<ScreenContextResponse> {
  const url = joinUrl(baseUrl, "/screen/context");
  if (refresh) {
    url.searchParams.set("refresh", "1");
  }
  const res = await fetch(url, { signal, method: "GET" });
  if (!res.ok) {
    throw new Error(`screen context ${res.status}`);
  }
  return (await res.json()) as ScreenContextResponse;
}

export async function postCopilotSuggestions(
  baseUrl: string,
  payload: { model?: string | null; refresh_screen?: boolean },
  signal?: AbortSignal,
): Promise<{ markdown: string; context: string; copilot: string; assist_mode: string; model: string }> {
  const res = await fetch(joinUrl(baseUrl, "/copilot/suggestions"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `copilot suggestions ${res.status}`);
  }
  return (await res.json()) as { markdown: string; context: string; copilot: string; assist_mode: string; model: string };
}

export async function fetchFocusState(
  baseUrl: string,
  signal?: AbortSignal,
): Promise<{ running: boolean; elapsed_seconds: number; assist_mode: string }> {
  const res = await fetch(joinUrl(baseUrl, "/focus/state"), { signal, method: "GET" });
  if (!res.ok) {
    throw new Error(`focus state ${res.status}`);
  }
  return (await res.json()) as { running: boolean; elapsed_seconds: number; assist_mode: string };
}

export async function postFocusControl(
  baseUrl: string,
  payload: { action: "start" | "stop" | "reset" },
  signal?: AbortSignal,
): Promise<{ ok: boolean; action: string; elapsed_seconds: number }> {
  const res = await fetch(joinUrl(baseUrl, "/focus/control"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!res.ok) {
    throw new Error(`focus control ${res.status}`);
  }
  return (await res.json()) as { ok: boolean; action: string; elapsed_seconds: number };
}

export type SiblingPathsResponse = {
  sibling_workspace_parent: string;
  open_interpreter_dir: string;
  crewai_dir: string;
};

export type SiblingProcessRow = {
  running: boolean;
  pid: number | null;
  cwd: string;
  cmd: string;
  exit_code?: number;
};

export type SiblingStatusResponse = {
  open_interpreter: SiblingProcessRow;
  crewai: SiblingProcessRow;
  sandbox: boolean;
};

export async function fetchSiblingPaths(baseUrl: string, signal?: AbortSignal): Promise<SiblingPathsResponse> {
  const res = await fetch(joinUrl(baseUrl, "/sibling-projects/paths"), { signal, method: "GET" });
  if (!res.ok) {
    throw new Error(`sibling paths ${res.status}`);
  }
  return (await res.json()) as SiblingPathsResponse;
}

export async function fetchSiblingStatus(baseUrl: string, signal?: AbortSignal): Promise<SiblingStatusResponse> {
  const res = await fetch(joinUrl(baseUrl, "/sibling-projects/status"), { signal, method: "GET" });
  if (!res.ok) {
    throw new Error(`sibling status ${res.status}`);
  }
  return (await res.json()) as SiblingStatusResponse;
}

export async function postSiblingStart(
  baseUrl: string,
  projectId: "open-interpreter" | "crewai",
  payload?: { cmd?: string | null },
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  const res = await fetch(joinUrl(baseUrl, `/sibling-projects/${projectId}/start`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
    signal,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `sibling start ${res.status}`);
  }
  return (await res.json()) as Record<string, unknown>;
}

export async function postSiblingStop(
  baseUrl: string,
  projectId: "open-interpreter" | "crewai",
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  const res = await fetch(joinUrl(baseUrl, `/sibling-projects/${projectId}/stop`), {
    method: "POST",
    signal,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `sibling stop ${res.status}`);
  }
  return (await res.json()) as Record<string, unknown>;
}
