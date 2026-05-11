import { motion, useReducedMotion } from "framer-motion";
import { Send } from "lucide-react";
import { type FormEvent, useCallback, useMemo, useRef, useState } from "react";

import { ThinkingHud } from "@/components/thinking-hud";
import { GlassPanel } from "@/components/glass-panel";
import { HudSectionTitle } from "@/components/hud-section-title";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useConfig } from "@/context/config-context";
import { postCommand } from "@/lib/api";
import { getOrCreateSessionId } from "@/lib/session";
import { cn } from "@/lib/utils";

type LineRole = "user" | "assistant" | "system" | "error";

type Line = {
  id: string;
  role: LineRole;
  text: string;
  ts: string;
};

function nowTs(): string {
  const d = new Date();
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function ConsolePage() {
  const reduceMotion = useReducedMotion();
  const { config } = useConfig();
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const [lines, setLines] = useState<Line[]>(() => [
    {
      id: "boot",
      role: "system",
      text: "Neural link established. Phase 2 local brain online — commands route to FastAPI + Ollama + CrewAI.",
      ts: nowTs(),
    },
  ]);

  const append = useCallback((role: LineRole, text: string) => {
    setLines((prev) => [...prev, { id: crypto.randomUUID(), role, text, ts: nowTs() }]);
  }, []);

  const onSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      const trimmed = input.trim();
      if (!trimmed || thinking) return;
      append("user", trimmed);
      setInput("");
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setThinking(true);
      try {
        const sessionId = getOrCreateSessionId();
        const res = await postCommand(
          config.apiBaseUrl,
          { message: trimmed, session_id: sessionId, model: config.ollamaModel },
          controller.signal,
        );
        append("assistant", res.reply);
        if (res.agents_used.length) {
          const brief = res.agents_used.map((a) => `${a.name}: ${a.summary}`).join("\n");
          append("system", `Agent trace\n${brief}`);
        }
        if (res.errors.length) {
          append("error", res.errors.join("\n"));
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Unknown failure";
        append("error", `Command channel fault — ${msg}`);
      } finally {
        setThinking(false);
        abortRef.current = null;
      }
    },
    [append, config.apiBaseUrl, config.ollamaModel, input, thinking],
  );

  const transcript = useMemo(
    () =>
      lines.map((line) => (
        <div key={line.id} className="space-y-1 py-2">
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.25em] text-muted-foreground">
            <span
              className={cn(
                line.role === "user" && "text-[hsl(var(--neon))]",
                line.role === "assistant" && "text-sky-200",
                line.role === "system" && "text-violet-300",
                line.role === "error" && "text-rose-300",
              )}
            >
              {line.role === "user"
                ? "Operator"
                : line.role === "assistant"
                  ? "JARVIS"
                  : line.role === "error"
                    ? "Fault"
                    : "System"}
            </span>
            <span className="tabular-nums text-muted-foreground/80">{line.ts}</span>
          </div>
          <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground/90">{line.text}</pre>
        </div>
      )),
    [lines],
  );

  return (
    <div className="space-y-6">
      <HudSectionTitle eyebrow="I/O" title="Command console" className="max-w-2xl" />
      <p className="max-w-2xl text-sm text-muted-foreground">
        Natural-language directives execute locally through the JARVIS crew (Planner → Commander) with session memory.
      </p>

      <GlassPanel className="flex min-h-[420px] flex-col p-0">
        <div className="px-5 pt-4">
          <ThinkingHud active={thinking} label="JARVIS is thinking — routing through local crew…" />
        </div>
        <ScrollArea className="h-[340px] px-5 py-2">
          <motion.div
            initial={reduceMotion ? false : { opacity: 0.001 }}
            animate={{ opacity: 1 }}
            className="pr-3"
          >
            {transcript}
          </motion.div>
        </ScrollArea>
        <div className="border-t border-border/70 p-4">
          <form className="flex gap-2" onSubmit={(ev) => void onSubmit(ev)}>
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Issue a command…"
              autoComplete="off"
              className="font-mono text-sm"
              disabled={thinking}
            />
            <Button type="submit" variant="hud" className="shrink-0 gap-2" disabled={thinking}>
              <Send className="h-4 w-4" aria-hidden />
              Send
            </Button>
          </form>
        </div>
      </GlassPanel>
    </div>
  );
}
