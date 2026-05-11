import { AnimatePresence, motion } from "framer-motion";
import { FolderGit2, Loader2, OctagonAlert, Power, ShieldCheck, Square, Terminal, Zap } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { GlassPanel } from "@/components/glass-panel";
import { HudSectionTitle } from "@/components/hud-section-title";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useConfig } from "@/context/config-context";
import {
  fetchAutomationProfiles,
  fetchSiblingPaths,
  fetchSiblingStatus,
  fetchSystemStatus,
  postKill,
  postSiblingStart,
  postSiblingStop,
  postSystemArm,
  postWorkflowRun,
} from "@/lib/api";
import { getOrCreateSessionId } from "@/lib/session";
import { cn } from "@/lib/utils";
import type { ProfileInfo, SystemStatus } from "@/types/automation";
import type { SiblingPathsResponse, SiblingStatusResponse } from "@/lib/api";

type PendingModal = {
  profileId: string;
  challenge: string;
  preview: { type: string; target: string; tier: string }[];
};

const PRESETS = [
  { id: "morning", label: "Morning office" },
  { id: "coding", label: "Coding mode" },
  { id: "meetings", label: "Meeting mode" },
  { id: "quick", label: "Quick stack" },
];

export function ControlDeckPage() {
  const { config } = useConfig();
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [profiles, setProfiles] = useState<ProfileInfo[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [lastMsg, setLastMsg] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingModal | null>(null);
  const [siblingPaths, setSiblingPaths] = useState<SiblingPathsResponse | null>(null);
  const [siblingStatus, setSiblingStatus] = useState<SiblingStatusResponse | null>(null);
  const [siblingBusy, setSiblingBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const s = await fetchSystemStatus(config.apiBaseUrl);
      setStatus(s);
      const p = await fetchAutomationProfiles(config.apiBaseUrl);
      setProfiles(p.profiles);
      try {
        const [paths, sib] = await Promise.all([
          fetchSiblingPaths(config.apiBaseUrl),
          fetchSiblingStatus(config.apiBaseUrl),
        ]);
        setSiblingPaths(paths);
        setSiblingStatus(sib);
      } catch {
        setSiblingPaths(null);
        setSiblingStatus(null);
      }
    } catch {
      setStatus(null);
    }
  }, [config.apiBaseUrl]);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const runWorkflow = async (profileId: string, challenge?: string) => {
    setBusy(profileId);
    setLastMsg(null);
    try {
      const sid = getOrCreateSessionId();
      const res = await postWorkflowRun(config.apiBaseUrl, {
        profile_id: profileId,
        session_id: sid,
        challenge: challenge ?? undefined,
      });
      if (res.pending && res.challenge) {
        setPending({
          profileId,
          challenge: res.challenge,
          preview: (res.preview ?? []).map((x) => ({ type: x.type, target: x.target, tier: x.tier })),
        });
        setLastMsg("Awaiting operator confirmation…");
        return;
      }
      if (res.ok) {
        setLastMsg("Mission complete — automation rail finished.");
        setPending(null);
      } else {
        setLastMsg((res.errors ?? []).join(" · ") || res.message || "Execution halted.");
        setPending(null);
      }
      void refresh();
    } catch (e) {
      setLastMsg(e instanceof Error ? e.message : "Execution fault");
    } finally {
      setBusy(null);
    }
  };

  const onKill = async () => {
    try {
      await postKill(config.apiBaseUrl);
      setLastMsg("Kill switch engaged — automation disarmed.");
      void refresh();
    } catch (e) {
      setLastMsg(e instanceof Error ? e.message : "Kill failed");
    }
  };

  const onArm = async () => {
    try {
      await postSystemArm(config.apiBaseUrl, true);
      setLastMsg("Automation re-armed.");
      void refresh();
    } catch (e) {
      setLastMsg(e instanceof Error ? e.message : "Arm failed");
    }
  };

  const siblingCtl = async (id: "open-interpreter" | "crewai", action: "start" | "stop") => {
    setSiblingBusy(`${id}-${action}`);
    try {
      if (action === "start") {
        const r = await postSiblingStart(config.apiBaseUrl, id, {});
        if (r.ok) {
          const url = typeof r.interpreter_url === "string" ? r.interpreter_url : null;
          const log = typeof r.log_file === "string" ? r.log_file : null;
          setLastMsg(
            `Started ${id} (pid ${String(r.pid)})${url ? ` — ${url}` : ""}${log ? ` · log: ${log}` : ""}`,
          );
        } else {
          const tail = typeof r.log_tail === "string" && r.log_tail ? `\n${String(r.log_tail).slice(-600)}` : "";
          setLastMsg(
            `${id}: ${String(r.reason ?? r.message ?? "failed")}${r.hint ? ` — ${String(r.hint)}` : ""}${tail}`,
          );
        }
      } else {
        await postSiblingStop(config.apiBaseUrl, id);
        setLastMsg(`Stopped ${id}.`);
      }
      void refresh();
    } catch (e) {
      setLastMsg(e instanceof Error ? e.message : "Sibling control failed");
    } finally {
      setSiblingBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <HudSectionTitle eyebrow="Phase 3" title="Control deck" />
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" className="gap-2 border-rose-500/40 text-rose-200" onClick={() => void onKill()}>
            <OctagonAlert className="h-4 w-4" aria-hidden />
            Kill switch
          </Button>
          <Button variant="hud" className="gap-2" onClick={() => void onArm()} disabled={status?.armed !== false}>
            <Power className="h-4 w-4" aria-hidden />
            Re-arm
          </Button>
        </div>
      </div>

      {status?.autonomy_tier === "elevated" ? (
        <GlassPanel className="border-amber-500/35 bg-amber-500/10 p-4 text-xs leading-relaxed text-amber-100">
          <p className="font-semibold text-amber-50">Elevated autonomy (API)</p>
          <p className="mt-1 text-amber-100/90">{status.autonomy_note}</p>
        </GlassPanel>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-3">
        <GlassPanel className="relative overflow-hidden p-6 lg:col-span-2">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_0%,hsl(var(--neon)/0.12),transparent_50%)]" />
          <div className="relative flex items-center gap-3">
            <Zap className="h-8 w-8 text-[hsl(var(--neon))]" aria-hidden />
            <div>
              <p className="text-sm font-semibold">Workflow presets</p>
              <p className="text-xs text-muted-foreground">
                Hammerspoon bridge —{" "}
                {status?.autonomy_tier === "elevated"
                  ? "elevated autonomy: medium-risk steps run without a second confirm (kill switch still works)."
                  : "confirm when the API prompts for a challenge token."}
              </p>
            </div>
          </div>
          <div className="relative mt-6 flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <Button
                key={p.id}
                variant="hud"
                disabled={busy !== null || status?.armed === false}
                className="min-w-[140px]"
                onClick={() => void runWorkflow(p.id)}
              >
                {busy === p.id ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
                {p.label}
              </Button>
            ))}
          </div>
          {profiles.length ? (
            <p className="relative mt-4 text-[11px] text-muted-foreground">
              Server profiles: {profiles.map((x) => x.id).join(", ")}
            </p>
          ) : null}
        </GlassPanel>

        <GlassPanel className="space-y-3 p-6">
          <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-muted-foreground">Rail status</p>
          {status ? (
            <ul className="space-y-2 text-sm">
              <li className="flex items-center justify-between gap-2">
                <span className="text-muted-foreground">Armed</span>
                <span className={cn("font-mono", status.armed ? "text-emerald-300" : "text-rose-300")}>
                  {status.armed ? "YES" : "NO"}
                </span>
              </li>
              <li className="flex items-center justify-between gap-2">
                <span className="text-muted-foreground">Sandbox</span>
                <span className="font-mono">{status.sandbox ? "ON" : "OFF"}</span>
              </li>
              <li className="flex items-center justify-between gap-2">
                <span className="text-muted-foreground">Hammerspoon</span>
                <span className={cn("font-mono", status.hammerspoon_reachable ? "text-emerald-300" : "text-amber-300")}>
                  {status.hammerspoon_reachable ? "LIVE" : "DOWN"}
                </span>
              </li>
              <li className="flex items-center justify-between gap-2">
                <span className="text-muted-foreground">Autonomy</span>
                <span className="font-mono text-[11px]">{status.autonomy_tier ?? "standard"}</span>
              </li>
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">Status unavailable.</p>
          )}
          {status?.last_error ? (
            <p className="text-xs text-rose-300">{status.last_error}</p>
          ) : null}
          {lastMsg ? <p className="text-xs text-[hsl(var(--neon))]">{lastMsg}</p> : null}
        </GlassPanel>
      </div>

      <GlassPanel className="space-y-4 p-6">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <FolderGit2 className="h-4 w-4 text-[hsl(var(--neon))]" aria-hidden />
          Sibling repos — Open Interpreter &amp; CrewAI
        </div>
        <p className="text-xs text-muted-foreground">
          Paths default to <span className="font-mono">../open-interpreter</span> and{" "}
          <span className="font-mono">../crewAI</span> beside <span className="font-mono">my-jarvis</span>. Override with{" "}
          <span className="font-mono">JARVIS_*_REPO_PATH</span>. When <span className="font-mono">JARVIS_AUTOMATION_SANDBOX</span>{" "}
          is true, start is blocked. Open Interpreter is started in <span className="font-mono">--server</span> mode (no
          TTY); logs under <span className="font-mono">.jarvis_data/sibling_logs/</span>.
        </p>
        {siblingPaths ? (
          <p className="font-mono text-[10px] leading-relaxed text-muted-foreground">
            OI: {siblingPaths.open_interpreter_dir}
            <br />
            CrewAI: {siblingPaths.crewai_dir}
          </p>
        ) : null}
        <div className="grid gap-3 sm:grid-cols-2">
          {(["open-interpreter", "crewai"] as const).map((id) => {
            const row = siblingStatus?.[id === "open-interpreter" ? "open_interpreter" : "crewai"];
            const label = id === "open-interpreter" ? "Open Interpreter" : "CrewAI";
            return (
              <div key={id} className="rounded-lg border border-border/60 bg-muted/15 p-4">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium">{label}</span>
                  <span className={cn("font-mono text-xs", row?.running ? "text-emerald-300" : "text-muted-foreground")}>
                    {row?.running ? `PID ${row.pid}` : "stopped"}
                  </span>
                </div>
                <p className="mt-2 line-clamp-2 font-mono text-[10px] text-muted-foreground">{row?.cmd}</p>
                <div className="mt-3 flex gap-2">
                  <Button
                    size="sm"
                    variant="hud"
                    className="gap-1"
                    disabled={siblingBusy !== null || siblingStatus?.sandbox || row?.running}
                    onClick={() => void siblingCtl(id, "start")}
                  >
                    {siblingBusy === `${id}-start` ? <Loader2 className="h-3 w-3 animate-spin" /> : <Terminal className="h-3 w-3" />}
                    Start
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="gap-1"
                    disabled={siblingBusy !== null || !row?.running}
                    onClick={() => void siblingCtl(id, "stop")}
                  >
                    {siblingBusy === `${id}-stop` ? <Loader2 className="h-3 w-3 animate-spin" /> : <Square className="h-3 w-3" />}
                    Stop
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      </GlassPanel>

      <GlassPanel className="p-0">
        <div className="flex items-center justify-between border-b border-border/60 px-5 py-3">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck className="h-4 w-4 text-[hsl(var(--neon))]" aria-hidden />
            Execution log
          </div>
        </div>
        <ScrollArea className="h-[220px] px-5 py-3">
          <pre className="whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-muted-foreground">
            {status?.recent_logs?.length
              ? JSON.stringify(status.recent_logs.slice(-12), null, 2)
              : "No recent events."}
          </pre>
        </ScrollArea>
      </GlassPanel>

      <AnimatePresence>
        {pending ? (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              initial={{ scale: 0.96, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.96, opacity: 0 }}
              className="glass-panel max-h-[80vh] w-full max-w-lg overflow-hidden rounded-hud p-6"
            >
              <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-muted-foreground">
                Confirmation required
              </p>
              <h3 className="mt-2 text-lg font-semibold">Authorize workflow</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Profile <span className="font-mono text-foreground">{pending.profileId}</span> includes steps that
                require explicit approval.
              </p>
              <ScrollArea className="mt-4 h-40 rounded-md border border-border/60 bg-muted/20 p-3">
                <ul className="space-y-2 text-xs">
                  {pending.preview.map((s, i) => (
                    <li key={`${s.type}-${i}`} className="font-mono text-foreground/90">
                      <span className="text-[hsl(var(--neon))]">{s.type}</span> → {s.target}{" "}
                      <span className="text-muted-foreground">({s.tier})</span>
                    </li>
                  ))}
                </ul>
              </ScrollArea>
              <div className="mt-6 flex justify-end gap-2">
                <Button variant="outline" onClick={() => setPending(null)}>
                  Abort
                </Button>
                <Button variant="hud" onClick={() => void runWorkflow(pending.profileId, pending.challenge)}>
                  Authorize &amp; execute
                </Button>
              </div>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
