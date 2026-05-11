import { motion, useReducedMotion } from "framer-motion";
import { Cpu, Shield } from "lucide-react";

import { GlassPanel } from "@/components/glass-panel";
import { cn } from "@/lib/utils";
import type { AgentViewModel } from "@/types/agents";

const statusLabel: Record<AgentViewModel["status"], string> = {
  idle: "Idle",
  active: "Active",
  degraded: "Degraded",
  offline: "Offline",
};

const statusStyles: Record<AgentViewModel["status"], string> = {
  idle: "bg-slate-500/20 text-slate-200 border-slate-500/30",
  active: "bg-emerald-500/15 text-emerald-200 border-emerald-500/30",
  degraded: "bg-amber-500/15 text-amber-200 border-amber-500/30",
  offline: "bg-rose-500/10 text-rose-200 border-rose-500/25",
};

export function AgentCard({ agent, index }: { agent: AgentViewModel; index: number }) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      initial={reduceMotion ? false : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: reduceMotion ? 0 : index * 0.06, duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
    >
      <GlassPanel className="relative overflow-hidden p-5">
        <div className="pointer-events-none absolute inset-0 hud-grid-bg opacity-40" />
        <div className="relative flex items-start justify-between gap-3">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Shield className="h-4 w-4 text-[hsl(var(--neon))]" aria-hidden />
              <p className="text-sm font-semibold tracking-tight">{agent.name}</p>
            </div>
            <p className="text-xs text-muted-foreground">{agent.role}</p>
            <p className="text-xs leading-relaxed text-foreground/80">{agent.detail}</p>
          </div>
          <span
            className={cn(
              "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
              statusStyles[agent.status],
            )}
          >
            {statusLabel[agent.status]}
          </span>
        </div>
        <div className="relative mt-4 flex items-center gap-2 text-xs text-muted-foreground">
          <Cpu className="h-3.5 w-3.5" aria-hidden />
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
            <motion.div
              className="h-full rounded-full bg-[hsl(var(--neon))]"
              initial={{ width: 0 }}
              animate={{ width: `${Math.round(agent.load * 100)}%` }}
              transition={{ duration: reduceMotion ? 0 : 0.8, ease: "easeOut" }}
            />
          </div>
          <span className="w-10 text-right tabular-nums">{Math.round(agent.load * 100)}%</span>
        </div>
        {agent.status === "active" && !reduceMotion ? (
          <motion.span
            className="pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full bg-[hsl(var(--neon))] opacity-10 blur-2xl"
            animate={{ opacity: [0.06, 0.14, 0.06] }}
            transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
          />
        ) : null}
      </GlassPanel>
    </motion.div>
  );
}
