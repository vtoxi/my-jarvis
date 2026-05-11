import { Loader2, Orbit, RefreshCw, ShieldAlert, Stethoscope, Wrench } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { GlassPanel } from "@/components/glass-panel";
import { HudSectionTitle } from "@/components/hud-section-title";
import { Button } from "@/components/ui/button";
import { useConfig } from "@/context/config-context";
import {
  fetchAutoworkStatus,
  fetchSystemErrors,
  fetchSystemHealth,
  fetchSystemPatchQueue,
  postAutoworkTick,
  postSystemAudit,
  postSystemRepair,
  type SystemAuditResponse,
  type SystemAutoworkStatus,
  type SystemErrorsPayload,
  type SystemHealth,
  type SystemPatchRow,
  type SystemRepairResponse,
} from "@/lib/api";
import { OPERATOR_TAKEOVER_LINES } from "@/lib/operator-takeover";
import { cn } from "@/lib/utils";

function errorWithTakeover(e: unknown): { message: string; lines: string[] } {
  if (e instanceof Error && "operatorTakeover" in e) {
    const lines = (e as Error & { operatorTakeover?: string[] }).operatorTakeover;
    if (lines?.length) return { message: e.message, lines };
  }
  if (e instanceof Error) return { message: e.message, lines: [...OPERATOR_TAKEOVER_LINES] };
  return { message: "Request failed", lines: [...OPERATOR_TAKEOVER_LINES] };
}

export function SystemEvolutionPage() {
  const { config } = useConfig();
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [errors, setErrors] = useState<SystemErrorsPayload | null>(null);
  const [patches, setPatches] = useState<SystemPatchRow[]>([]);
  const [audit, setAudit] = useState<SystemAuditResponse | null>(null);
  const [repair, setRepair] = useState<SystemRepairResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [operatorTakeover, setOperatorTakeover] = useState<string[] | null>(null);
  const [autowork, setAutowork] = useState<SystemAutoworkStatus | null>(null);
  const [autoworkBusy, setAutoworkBusy] = useState(false);

  const refresh = useCallback(async () => {
    setMsg(null);
    setOperatorTakeover(null);
    try {
      const [h, e, q, aw] = await Promise.all([
        fetchSystemHealth(config.apiBaseUrl),
        fetchSystemErrors(config.apiBaseUrl),
        fetchSystemPatchQueue(config.apiBaseUrl),
        fetchAutoworkStatus(config.apiBaseUrl).catch(() => null),
      ]);
      setHealth(h);
      setErrors(e);
      setPatches(q.patches ?? []);
      setAutowork(aw);
    } catch (e) {
      setHealth(null);
      setErrors(null);
      setPatches([]);
      setMsg(e instanceof Error ? e.message : "Failed to load system state");
    }
  }, [config.apiBaseUrl]);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 15000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const onAudit = async () => {
    setBusy("audit");
    setAudit(null);
    setOperatorTakeover(null);
    try {
      const r = await postSystemAudit(config.apiBaseUrl, { mode: "audit", run_tools: false });
      setAudit(r);
    } catch (e) {
      const { message, lines } = errorWithTakeover(e);
      setMsg(message);
      setOperatorTakeover(lines);
    } finally {
      setBusy(null);
    }
  };

  const onRepair = async () => {
    setBusy("repair");
    setRepair(null);
    setOperatorTakeover(null);
    try {
      const r = await postSystemRepair(config.apiBaseUrl, { context: "Operator requested diagnostic from Evolution UI." });
      setRepair(r);
    } catch (e) {
      const { message, lines } = errorWithTakeover(e);
      setMsg(message);
      setOperatorTakeover(lines);
    } finally {
      setBusy(null);
    }
  };

  const onAutoworkTick = async () => {
    setAutoworkBusy(true);
    setMsg(null);
    try {
      await postAutoworkTick(config.apiBaseUrl);
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Autowork tick failed");
    } finally {
      setAutoworkBusy(false);
    }
  };

  const score = health?.health_score ?? null;
  const status = health?.status ?? "—";

  const takeoverLines =
    operatorTakeover ??
    (repair?.operator_takeover_checklist?.length ? repair.operator_takeover_checklist : null) ??
    (audit?.operator_takeover_checklist?.length ? audit.operator_takeover_checklist : null);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-muted-foreground">Phase 6</p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight">System evolution</h2>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            Local-first health, diagnostics, and approval-gated change. Self-healing here means <strong>analysis + logged
            suggestions</strong> — it does not move your mouse, type keys, or apply patches without your explicit
            actions (safety by design).
          </p>
          {autowork ? (
            <p className="mt-3 max-w-xl text-[11px] text-muted-foreground">
              Autowork: {autowork.enabled ? "enabled" : "disabled"} on API
              {autowork.schedule_enabled ? " · scheduled" : ""}
              {autowork.restart_pending ? " · restart request file pending" : ""}. Does not auto-apply git patches or
              restart uvicorn in-process — see <span className="font-mono">data_dir/autowork/</span>.
            </p>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => void refresh()} className="border-[hsl(var(--neon))]/40">
            <RefreshCw className="mr-2 h-4 w-4" aria-hidden />
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={() => void onAudit()} disabled={busy === "audit"}>
            {busy === "audit" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ShieldAlert className="mr-2 h-4 w-4" />}
            Run code audit
          </Button>
          <Button size="sm" onClick={() => void onRepair()} disabled={busy === "repair"}>
            {busy === "repair" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Stethoscope className="mr-2 h-4 w-4" />}
            Run self-healing scan
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void onAutoworkTick()}
            disabled={autoworkBusy || autowork?.enabled !== true}
            className="border-border/60"
          >
            {autoworkBusy ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Wrench className="mr-2 h-4 w-4" />}
            Autowork tick
          </Button>
        </div>
      </div>

      {msg ? (
        <p className="whitespace-pre-wrap text-sm text-amber-500" role="status">
          {msg}
        </p>
      ) : null}

      {takeoverLines?.length ? (
        <GlassPanel className="border-amber-500/30 bg-amber-500/5 p-5">
          <HudSectionTitle eyebrow="Human in the loop" title="You take control — keyboard, screen, Terminal" />
          <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
            When the API hits an exception or incomplete signals, JARVIS asks you to operate the Mac directly: read the
            screen (Copilot / screen endpoints), copy errors into repair context, run suggested commands yourself only
            after you understand them.
          </p>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-xs text-foreground">
            {takeoverLines.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </GlassPanel>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <GlassPanel className="p-5 lg:col-span-1">
          <div className="flex items-start gap-2">
            <Orbit className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--neon))]" aria-hidden />
            <HudSectionTitle eyebrow="Aggregate signal" title="Health score" />
          </div>
          <div className="mt-6 flex items-end gap-2">
            <span className="text-5xl font-semibold tabular-nums text-foreground">{score ?? "—"}</span>
            <span className="pb-1 text-sm text-muted-foreground">/ 100</span>
          </div>
          <p className="mt-2 text-xs uppercase tracking-wider text-muted-foreground">Status: {status}</p>
          <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
            Score reflects core services only. Hammerspoon and sibling repos are optional Mac/local processes — not{" "}
            <span className="font-mono">systemctl</span> units.
          </p>
          <ul className="mt-4 max-h-64 space-y-2 overflow-y-auto text-xs">
            {(health?.subsystems ?? []).map((s) => (
              <li
                key={s.id}
                title={s.detail ?? undefined}
                className={cn(
                  "flex flex-wrap items-center justify-between gap-2 rounded border border-border/60 px-2 py-1.5",
                  s.ok ? "bg-muted/20" : "border-amber-500/40 bg-amber-500/5",
                )}
              >
                <span className="font-mono text-[11px]">{s.id}</span>
                <div className="flex shrink-0 items-center gap-2">
                  {s.optional_for_score ? (
                    <span className="rounded bg-muted/80 px-1.5 py-0.5 text-[9px] font-medium uppercase tracking-wide text-muted-foreground">
                      info
                    </span>
                  ) : null}
                  <span className={cn(s.ok ? "text-[hsl(var(--neon))]" : "text-amber-500")}>
                    {s.ok ? "ok" : "issue"}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </GlassPanel>

        <GlassPanel className="p-5 lg:col-span-2">
          <div className="flex items-start gap-2">
            <Wrench className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--neon))]" aria-hidden />
            <HudSectionTitle eyebrow="Signed change rail" title="Patch queue" />
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Use <span className="font-mono">POST /system/improve/prepare</span> then{" "}
            <span className="font-mono">/system/improve/apply</span> with{" "}
            <span className="font-mono">JARVIS_SYSTEM_PATCHES_ENABLED=true</span> and a clean git tree.
          </p>
          <div className="mt-4 max-h-56 overflow-y-auto text-xs">
            {patches.length === 0 ? (
              <p className="text-muted-foreground">No patch proposals yet.</p>
            ) : (
              <ul className="space-y-2">
                {patches.map((p) => (
                  <li key={p.id} className="rounded border border-border/50 px-2 py-2 font-mono text-[11px]">
                    <div className="flex flex-wrap justify-between gap-1">
                      <span className="truncate">{p.id.slice(0, 8)}…</span>
                      <span className="text-muted-foreground">{p.status}</span>
                    </div>
                    <div className="mt-1 text-muted-foreground">{p.branch_name}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </GlassPanel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <GlassPanel className="p-5">
          <HudSectionTitle eyebrow="Incidents + repairs" title="Recent diagnostics" />
          <div className="mt-3 max-h-64 overflow-y-auto text-xs text-muted-foreground">
            {(errors?.incidents ?? []).length === 0 ? (
              <p>No incidents logged.</p>
            ) : (
              <ul className="space-y-3">
                {(errors?.incidents ?? []).slice(0, 12).map((i) => (
                  <li key={i.id} className="border-b border-border/40 pb-2">
                    <p className="font-medium text-foreground">{i.summary}</p>
                    <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                      {i.created_at} · {i.severity}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </GlassPanel>

        <GlassPanel className="p-5">
          <HudSectionTitle eyebrow="Agent output" title="Latest analysis" />
          <div className="mt-3 max-h-80 overflow-y-auto text-xs leading-relaxed">
            {repair ? (
              <div className="space-y-2">
                <p className="font-semibold text-foreground">{repair.user_visible_summary}</p>
                <p className="text-muted-foreground">{repair.root_cause_hypothesis}</p>
                {repair.recommended_commands.length > 0 ? (
                  <ul className="list-disc pl-4">
                    {repair.recommended_commands.map((c) => (
                      <li key={c} className="font-mono text-[11px]">
                        {c}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : audit ? (
              <pre className="whitespace-pre-wrap font-sans text-[11px] text-muted-foreground">
                {audit.synthesis_markdown.slice(0, 12000)}
              </pre>
            ) : (
              <p className="text-muted-foreground">Run audit or self-healing scan to populate this panel.</p>
            )}
          </div>
        </GlassPanel>
      </div>
    </div>
  );
}
