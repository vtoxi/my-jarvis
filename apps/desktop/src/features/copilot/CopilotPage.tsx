import { motion } from "framer-motion";
import { Brain, Eye, Loader2, PauseCircle, PlayCircle, ScanEye, Shield, Sparkles, Timer } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { GlassPanel } from "@/components/glass-panel";
import { HudSectionTitle } from "@/components/hud-section-title";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useConfig } from "@/context/config-context";
import {
  fetchCopilotStatus,
  fetchFocusState,
  fetchScreenContext,
  postCopilotConfig,
  postCopilotSuggestions,
  postFocusControl,
  postScreenCapture,
  type CopilotStatus,
  type ScreenContextResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export function CopilotPage() {
  const { config } = useConfig();
  const [status, setStatus] = useState<CopilotStatus | null>(null);
  const [ctx, setCtx] = useState<ScreenContextResponse | null>(null);
  const [suggestions, setSuggestions] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [exclusions, setExclusions] = useState("");
  const [focus, setFocus] = useState<{ running: boolean; elapsed_seconds: number } | null>(null);
  const exclusionsSeeded = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const [s, c, f] = await Promise.all([
        fetchCopilotStatus(config.apiBaseUrl),
        fetchScreenContext(config.apiBaseUrl, false),
        fetchFocusState(config.apiBaseUrl),
      ]);
      setStatus(s);
      setCtx(c);
      setFocus(f);
    } catch {
      setStatus(null);
    }
  }, [config.apiBaseUrl]);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 8000);
    return () => window.clearInterval(id);
  }, [refresh]);

  useEffect(() => {
    if (exclusionsSeeded.current || !status?.excluded_app_substrings?.length) return;
    setExclusions(status.excluded_app_substrings.join(", "));
    exclusionsSeeded.current = true;
  }, [status]);

  useEffect(() => {
    if (!focus?.running) return;
    const id = window.setInterval(() => {
      void (async () => {
        try {
          const f = await fetchFocusState(config.apiBaseUrl);
          setFocus(f);
        } catch {
          /* ignore */
        }
      })();
    }, 1000);
    return () => window.clearInterval(id);
  }, [focus?.running, config.apiBaseUrl]);

  const onPauseToggle = async () => {
    if (!status) return;
    setBusy("cfg");
    try {
      await postCopilotConfig(config.apiBaseUrl, { monitoring_paused: !status.monitoring_paused });
      await refresh();
    } finally {
      setBusy(null);
    }
  };

  const onPrivateToggle = async () => {
    if (!status) return;
    setBusy("cfg");
    try {
      await postCopilotConfig(config.apiBaseUrl, { private_mode: !status.private_mode });
      await refresh();
    } finally {
      setBusy(null);
    }
  };

  const onAssist = async (mode: CopilotStatus["assist_mode"]) => {
    setBusy("cfg");
    try {
      await postCopilotConfig(config.apiBaseUrl, { assist_mode: mode });
      await refresh();
    } finally {
      setBusy(null);
    }
  };

  const saveExclusions = async () => {
    const parts = exclusions
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    setBusy("cfg");
    try {
      await postCopilotConfig(config.apiBaseUrl, { excluded_app_substrings: parts });
      await refresh();
    } finally {
      setBusy(null);
    }
  };

  const onCapture = async () => {
    setBusy("cap");
    try {
      await postScreenCapture(config.apiBaseUrl, { include_image: false });
      const c = await fetchScreenContext(config.apiBaseUrl, false);
      setCtx(c);
      await refresh();
    } catch (e) {
      setCtx({
        front_app: null,
        window_title: null,
        tags: [],
        ocr_excerpt: e instanceof Error ? e.message : "Capture failed",
        monitoring_paused: true,
        private_mode: false,
        assist_mode: "advisory",
        visible_indicator: true,
        productivity_score: null,
      });
    } finally {
      setBusy(null);
    }
  };

  const onRefreshContext = async () => {
    setBusy("ctx");
    try {
      const c = await fetchScreenContext(config.apiBaseUrl, true);
      setCtx(c);
    } catch (e) {
      setCtx(null);
    } finally {
      setBusy(null);
    }
  };

  const onSuggestions = async () => {
    setBusy("sug");
    setSuggestions(null);
    try {
      const res = await postCopilotSuggestions(config.apiBaseUrl, {
        model: config.ollamaModel,
        refresh_screen: true,
      });
      setSuggestions(res.markdown);
    } catch (e) {
      setSuggestions(e instanceof Error ? e.message : "Suggestions failed");
    } finally {
      setBusy(null);
    }
  };

  const onFocus = async (action: "start" | "stop") => {
    setBusy("focus");
    try {
      await postFocusControl(config.apiBaseUrl, { action });
      setFocus(await fetchFocusState(config.apiBaseUrl));
    } finally {
      setBusy(null);
    }
  };

  const score = typeof ctx?.productivity_score === "number" ? ctx.productivity_score : null;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-muted-foreground">Phase 5</p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight">Neural copilot</h2>
          <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
            Local-first screen read + OCR + situational crew.{" "}
            <span className="text-foreground/90">You stay in control</span> — pause, private mode, and exclusions are
            first-class.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void onPauseToggle()} disabled={busy === "cfg" || !status}>
            {status?.monitoring_paused ? (
              <>
                <PlayCircle className="mr-2 h-4 w-4" /> Resume
              </>
            ) : (
              <>
                <PauseCircle className="mr-2 h-4 w-4" /> Pause monitoring
              </>
            )}
          </Button>
          <Button variant="outline" onClick={() => void onPrivateToggle()} disabled={busy === "cfg" || !status}>
            <Shield className="mr-2 h-4 w-4" />
            {status?.private_mode ? "Leave private" : "Private mode"}
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <GlassPanel className="p-5 lg:col-span-1">
          <div className="flex items-start gap-2">
            <Eye className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--neon))]" aria-hidden />
            <HudSectionTitle eyebrow="Trust-first visibility" title="Jarvis sees" />
          </div>
          <dl className="mt-4 space-y-2 text-sm">
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Active app</dt>
              <dd className="truncate font-medium">{ctx?.front_app ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Window</dt>
              <dd className="max-w-[12rem] truncate text-right text-xs text-muted-foreground">
                {ctx?.window_title ?? "—"}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Tags</dt>
              <dd className="text-right font-mono text-[10px] text-[hsl(var(--neon))]">
                {(ctx?.tags ?? []).join(", ") || "—"}
              </dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Assist mode</dt>
              <dd className="font-mono text-xs">{status?.assist_mode ?? "—"}</dd>
            </div>
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Productivity</dt>
              <dd className="tabular-nums font-semibold">{score ?? "—"}</dd>
            </div>
          </dl>
          <p className="mt-4 text-xs leading-relaxed text-muted-foreground">{ctx?.trust_note}</p>
        </GlassPanel>

        <GlassPanel className="p-5 lg:col-span-2">
          <div className="flex items-start gap-2">
            <ScanEye className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--neon))]" aria-hidden />
            <HudSectionTitle eyebrow="OCR excerpt (refresh to update)" title="Live context" />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" onClick={() => void onCapture()} disabled={busy === "cap" || status?.monitoring_paused}>
              {busy === "cap" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanEye className="h-4 w-4" />}
              <span className="ml-2">Capture now</span>
            </Button>
            <Button size="sm" variant="outline" onClick={() => void onRefreshContext()} disabled={busy === "ctx"}>
              Refresh context
            </Button>
            <Button size="sm" className="shadow-hud" onClick={() => void onSuggestions()} disabled={busy === "sug"}>
              {busy === "sug" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
              Copilot suggestions
            </Button>
          </div>
          <ScrollArea className="mt-4 h-52 rounded-md border border-border/40 bg-background/30">
            <pre className="whitespace-pre-wrap p-4 font-sans text-xs leading-relaxed text-foreground/90">
              {(ctx?.ocr_excerpt || "").trim() || "No OCR yet — capture when Screen Recording is granted."}
            </pre>
          </ScrollArea>
        </GlassPanel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <GlassPanel className="p-5">
          <div className="flex items-start gap-2">
            <Brain className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--neon))]" aria-hidden />
            <HudSectionTitle eyebrow="passive · advisory · interactive · controlled" title="Assist rail" />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {(["passive", "advisory", "interactive", "controlled"] as const).map((m) => (
              <Button
                key={m}
                size="sm"
                variant={status?.assist_mode === m ? "default" : "outline"}
                className={cn(status?.assist_mode === m && "shadow-hud")}
                onClick={() => void onAssist(m)}
                disabled={busy === "cfg"}
              >
                {m}
              </Button>
            ))}
          </div>
          <div className="mt-6 space-y-2">
            <label className="text-xs font-medium text-muted-foreground">App exclusion substrings (comma)</label>
            <textarea
              value={exclusions}
              onChange={(e) => setExclusions(e.target.value)}
              rows={2}
              className="flex w-full rounded-md border border-border bg-muted/40 px-3 py-2 font-mono text-xs shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <Button size="sm" variant="outline" onClick={() => void saveExclusions()} disabled={busy === "cfg"}>
              Save exclusions
            </Button>
          </div>
        </GlassPanel>

        <GlassPanel className="p-5">
          <div className="flex items-start gap-2">
            <Timer className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--neon))]" aria-hidden />
            <HudSectionTitle eyebrow="Server-tracked focus session" title="Focus timer" />
          </div>
          <p className="mt-3 text-3xl font-semibold tabular-nums tracking-tight text-[hsl(var(--neon))]">
            {Math.floor((focus?.elapsed_seconds ?? 0) / 60)
              .toString()
              .padStart(2, "0")}
            :{((focus?.elapsed_seconds ?? 0) % 60).toString().padStart(2, "0")}
          </p>
          <div className="mt-4 flex gap-2">
            <Button size="sm" onClick={() => void onFocus("start")} disabled={busy === "focus" || focus?.running}>
              Start
            </Button>
            <Button size="sm" variant="outline" onClick={() => void onFocus("stop")} disabled={busy === "focus" || !focus?.running}>
              Stop
            </Button>
          </div>
        </GlassPanel>
      </div>

      <GlassPanel className="p-5">
        <div className="flex items-start gap-2">
          <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--neon))]" aria-hidden />
          <HudSectionTitle eyebrow="Context Analyst + Productivity Copilot" title="Suggestion queue" />
        </div>
        <ScrollArea className="mt-4 h-[min(380px,50vh)] rounded-md border border-border/40 bg-background/30">
          <motion.pre
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="whitespace-pre-wrap p-4 font-sans text-xs leading-relaxed text-foreground/90"
          >
            {suggestions ?? "Run “Copilot suggestions” to generate a situational brief (requires Ollama unless stub mode)."}
          </motion.pre>
        </ScrollArea>
      </GlassPanel>
    </div>
  );
}
