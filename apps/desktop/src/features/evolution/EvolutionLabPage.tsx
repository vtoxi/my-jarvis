import { Atom, Loader2, RefreshCw, Shield } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { GlassPanel } from "@/components/glass-panel";
import { HudSectionTitle } from "@/components/hud-section-title";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useConfig } from "@/context/config-context";
import {
  type EvolutionIdleResponse,
  type EvolutionLogEntry,
  type EvolutionStatus,
  fetchEvolutionLogs,
  fetchEvolutionPredictions,
  fetchEvolutionStatus,
  postEvolutionIdle,
  postEvolutionSandboxBenchmark,
} from "@/lib/api";

export function EvolutionLabPage() {
  const { config } = useConfig();
  const [status, setStatus] = useState<EvolutionStatus | null>(null);
  const [logs, setLogs] = useState<EvolutionLogEntry[]>([]);
  const [predictions, setPredictions] = useState<{ id: string; severity: string; title: string; detail: string }[]>(
    [],
  );
  const [idleReport, setIdleReport] = useState<EvolutionIdleResponse | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [bench, setBench] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setMsg(null);
    try {
      const [s, lg, pr] = await Promise.all([
        fetchEvolutionStatus(config.apiBaseUrl),
        fetchEvolutionLogs(config.apiBaseUrl, 50),
        fetchEvolutionPredictions(config.apiBaseUrl),
      ]);
      setStatus(s);
      setLogs(lg.entries ?? []);
      setPredictions(pr.predictions ?? []);
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed to load evolution lab");
    }
  }, [config.apiBaseUrl]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onIdle = async () => {
    setBusy("idle");
    setIdleReport(null);
    try {
      const r = await postEvolutionIdle(config.apiBaseUrl);
      setIdleReport(r);
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Idle cycle failed");
    } finally {
      setBusy(null);
    }
  };

  const onSandboxBenchmark = async () => {
    setBusy("bench");
    setBench(null);
    try {
      const r = await postEvolutionSandboxBenchmark(config.apiBaseUrl);
      setBench(
        r.skipped
          ? `Skipped: ${r.reason ?? "unknown"}`
          : `Repo benchmark ${r.ok ? "passed" : "failed"}${r.repo_root ? ` (${r.repo_root})` : ""}`,
      );
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Sandbox benchmark failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-muted-foreground">Phase 8</p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight">JARVIS evolution lab</h2>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Digital twin profile, idle learning, and predictive hints — all local-first. No silent autonomy; style
            alignment only, not identity delegation.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => void refresh()} className="border-[hsl(var(--neon))]/40">
            <RefreshCw className="mr-2 h-4 w-4" aria-hidden />
            Refresh
          </Button>
          <Button size="sm" onClick={() => void onIdle()} disabled={busy === "idle"}>
            {busy === "idle" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Atom className="mr-2 h-4 w-4" />}
            Run idle learning cycle
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void onSandboxBenchmark()}
            disabled={busy === "bench"}
            className="border-border/60"
          >
            {busy === "bench" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Sandbox repo benchmark
          </Button>
        </div>
      </div>

      {msg ? (
        <p className="text-sm text-amber-500" role="status">
          {msg}
        </p>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <GlassPanel className="p-5 lg:col-span-1">
          <div className="flex items-start gap-2">
            <Shield className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--neon))]" aria-hidden />
            <HudSectionTitle eyebrow="Twin + governance" title="Status" />
          </div>
          <dl className="mt-4 space-y-2 text-xs">
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Twin version</dt>
              <dd className="font-mono">{status?.twin_version ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Strategic maturity</dt>
              <dd className="font-semibold tabular-nums">{status?.strategic_maturity_index ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Pending approvals</dt>
              <dd>{status?.pending_approvals ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Events (24h)</dt>
              <dd>{status?.evolution_events_24h ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Last idle run</dt>
              <dd className="truncate text-right font-mono text-[10px]">{status?.last_idle_run_at ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Scheduled idle</dt>
              <dd className="text-right">
                {status?.idle_schedule_enabled
                  ? `on · ${status.idle_schedule_interval_s ?? "—"}s`
                  : "off"}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Local knowledge chunks</dt>
              <dd className="tabular-nums">
                {status?.knowledge_enabled === false
                  ? "disabled"
                  : (status?.knowledge_chunk_count ?? "—")}
              </dd>
            </div>
          </dl>
          <p className="mt-4 text-[11px] leading-relaxed text-muted-foreground">{status?.ethics_note}</p>
        </GlassPanel>

        <GlassPanel className="p-5 lg:col-span-2">
          <HudSectionTitle eyebrow="Heuristics" title="Predictive hints" />
          <ul className="mt-3 max-h-48 space-y-2 overflow-y-auto text-xs">
            {predictions.length === 0 ? (
              <li className="text-muted-foreground">No hints — all quiet.</li>
            ) : (
              predictions.map((p) => (
                <li key={p.id} className="rounded border border-border/50 px-2 py-2">
                  <span className="font-medium text-foreground">{p.title}</span>
                  <p className="mt-1 text-muted-foreground">{p.detail}</p>
                  <p className="mt-1 font-mono text-[10px] text-muted-foreground">{p.severity}</p>
                </li>
              ))
            )}
          </ul>
        </GlassPanel>
      </div>

      {bench ? (
        <p className="text-xs text-muted-foreground" role="status">
          {bench}
        </p>
      ) : null}

      {idleReport ? (
        <GlassPanel className="p-5">
          <HudSectionTitle eyebrow="Latest run" title="Idle learning report" />
          <ScrollArea className="mt-3 h-72 w-full rounded-md border border-border/40 p-3">
            <pre className="whitespace-pre-wrap font-sans text-[11px] leading-relaxed text-muted-foreground">
              {idleReport.report_markdown}
            </pre>
          </ScrollArea>
        </GlassPanel>
      ) : null}

      <GlassPanel className="p-5">
        <HudSectionTitle eyebrow="Audit trail" title="Evolution logs" />
        <ScrollArea className="mt-3 h-64 w-full">
          <ul className="space-y-2 pr-3 text-xs">
            {logs.length === 0 ? (
              <li className="text-muted-foreground">No events yet.</li>
            ) : (
              logs.map((e) => (
                <li key={e.id} className="rounded border border-border/40 px-2 py-2 font-mono text-[10px]">
                  <span className="text-foreground">{e.kind}</span> · {e.created_at}
                </li>
              ))
            )}
          </ul>
        </ScrollArea>
      </GlassPanel>
    </div>
  );
}
