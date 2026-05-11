export type SystemStatus = {
  armed: boolean;
  sandbox: boolean;
  hammerspoon_reachable: boolean;
  last_error: string | null;
  recent_logs: Record<string, unknown>[];
  autonomy_tier?: string;
  autonomy_note?: string;
};

export type ProfileInfo = {
  id: string;
  label: string;
  step_count: number;
};

export type ProfilesListResponse = {
  profiles: ProfileInfo[];
};

export type WorkflowRunResponse = {
  ok: boolean;
  pending?: boolean;
  challenge?: string | null;
  profile_id?: string | null;
  message?: string | null;
  results?: unknown[];
  errors?: string[];
  preview?: { type: string; target: string; tier: string; bundle_id?: string | null; meta?: Record<string, unknown> }[];
};
