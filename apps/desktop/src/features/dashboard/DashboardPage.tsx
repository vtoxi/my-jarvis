import { motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight, Radar } from "lucide-react";
import { Link } from "react-router-dom";

import { GlassPanel } from "@/components/glass-panel";
import { HudSectionTitle } from "@/components/hud-section-title";
import { Button } from "@/components/ui/button";
import { mockAgents } from "@/data/mock-agents";

export function DashboardPage() {
  const reduceMotion = useReducedMotion();
  const activeAgents = mockAgents.filter((a) => a.status === "active").length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <HudSectionTitle eyebrow="Mission control" title="JARVIS command overview" />
        <Button variant="hud" asChild>
          <Link to="/console">
            Open console <ArrowUpRight className="h-4 w-4" aria-hidden />
          </Link>
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <GlassPanel className="relative overflow-hidden p-6 lg:col-span-2">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_80%_0%,hsl(var(--neon)/0.12),transparent_45%)]" />
          <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Operational posture</p>
              <p className="mt-2 text-3xl font-semibold tracking-tight">
                <span className="neon-text">Nominal</span>
              </p>
              <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
                Phase 2 routes natural language through the local crew (Planner → Commander) with Ollama and session
                memory. Use the console to issue missions.
              </p>
            </div>
            <div className="flex items-center gap-3 rounded-hud border border-border/70 bg-muted/30 px-4 py-3">
              <Radar className="h-8 w-8 text-[hsl(var(--neon))]" aria-hidden />
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-muted-foreground">Scan</p>
                <p className="text-sm font-medium">Local mesh</p>
              </div>
            </div>
          </div>
        </GlassPanel>

        <GlassPanel className="p-6">
          <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-muted-foreground">Agents</p>
          <p className="mt-3 text-4xl font-semibold tabular-nums">{activeAgents}</p>
          <p className="text-sm text-muted-foreground">active of {mockAgents.length}</p>
          <Button variant="outline" className="mt-6 w-full" asChild>
            <Link to="/agents">View roster</Link>
          </Button>
        </GlassPanel>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {[
          { title: "Metrics deck", body: "CPU / RAM placeholders with cinematic charts.", to: "/metrics" },
          { title: "Command console", body: "Transcript + input shell. Execution arrives later.", to: "/console" },
        ].map((tile, i) => (
          <motion.div
            key={tile.title}
            initial={reduceMotion ? false : { opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: reduceMotion ? 0 : 0.08 + i * 0.06, duration: 0.35 }}
          >
            <GlassPanel className="flex h-full flex-col p-6">
              <p className="text-sm font-semibold">{tile.title}</p>
              <p className="mt-2 flex-1 text-sm text-muted-foreground">{tile.body}</p>
              <Button variant="ghost" className="mt-4 justify-start px-0 text-[hsl(var(--neon))]" asChild>
                <Link to={tile.to}>
                  Open <ArrowUpRight className="h-4 w-4" aria-hidden />
                </Link>
              </Button>
            </GlassPanel>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
