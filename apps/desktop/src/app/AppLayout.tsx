import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  Activity,
  Bot,
  Command,
  Cpu,
  Eye,
  LayoutDashboard,
  MessageSquare,
  Orbit,
  Atom,
  Settings2,
  Zap,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { ApiStatusPill } from "@/components/api-status-pill";
import { GlassPanel } from "@/components/glass-panel";
import { ModelStatusPill } from "@/components/model-status-pill";
import { Separator } from "@/components/ui/separator";
import { useConfig } from "@/context/config-context";
import { useApiHealth } from "@/hooks/use-api-health";
import { fetchModels } from "@/lib/api";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { to: "/agents", label: "Agents", icon: Bot },
  { to: "/metrics", label: "Metrics", icon: Cpu },
  { to: "/console", label: "Console", icon: Command },
  { to: "/control", label: "Control", icon: Zap },
  { to: "/slack", label: "Slack", icon: MessageSquare },
  { to: "/copilot", label: "Copilot", icon: Eye },
  { to: "/evolution", label: "Evolution", icon: Orbit },
  { to: "/evolution-lab", label: "Evolution lab", icon: Atom },
  { to: "/settings", label: "Settings", icon: Settings2 },
];

export function AppLayout() {
  const location = useLocation();
  const reduceMotion = useReducedMotion();
  const { config, ready } = useConfig();
  const health = useApiHealth(config.apiBaseUrl, ready);
  const [ollamaReachable, setOllamaReachable] = useState(false);

  useEffect(() => {
    if (!ready) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const m = await fetchModels(config.apiBaseUrl, config.ollamaModel);
        if (!cancelled) {
          setOllamaReachable(m.ollama_reachable);
        }
      } catch {
        if (!cancelled) {
          setOllamaReachable(false);
        }
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 15000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [config.apiBaseUrl, config.ollamaModel, ready]);

  const pillLabel =
    health.status === "ok"
      ? "API online"
      : health.status === "checking"
        ? "API checking…"
        : "API offline";

  return (
    <div className="flex min-h-screen bg-[hsl(var(--hud-bg))] text-foreground">
      <div className="pointer-events-none fixed inset-0 hud-grid-bg opacity-50" />

      <aside className="relative z-10 flex w-[260px] flex-col border-r border-border/60 bg-background/40 pt-10 backdrop-blur-xl">
        <div className="px-5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.4em] text-muted-foreground">JARVIS</p>
          <p className="mt-1 text-lg font-semibold tracking-tight">Operations</p>
        </div>
        <Separator className="my-6 bg-border/60" />
        <nav className="flex flex-1 flex-col gap-1 px-3 pb-6">
          {nav.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    "group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-muted/70 text-foreground shadow-hud"
                      : "text-muted-foreground hover:bg-muted/40 hover:text-foreground",
                  )
                }
              >
                <Icon className="h-4 w-4 opacity-80 group-hover:opacity-100" aria-hidden />
                {item.label}
              </NavLink>
            );
          })}
        </nav>
        <div className="px-4 pb-6">
          <GlassPanel className="p-4 text-xs text-muted-foreground">
            <div className="flex items-center gap-2 text-foreground">
              <Activity className="h-4 w-4 text-[hsl(var(--neon))]" aria-hidden />
              <span className="font-semibold tracking-tight">Core</span>
            </div>
            <p className="mt-2 leading-relaxed">
              Phase 5 — Screen intelligence. Pause anytime; private mode strips pixels; all local.
            </p>
          </GlassPanel>
        </div>
      </aside>

      <div className="relative z-10 flex min-h-screen flex-1 flex-col">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border/60 bg-background/30 px-8 py-4 backdrop-blur-xl">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-muted-foreground">Active deck</p>
            <h1 className="text-xl font-semibold tracking-tight">
              {nav.find((n) => location.pathname.startsWith(n.to))?.label ?? "JARVIS"}
            </h1>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            <ModelStatusPill reachable={ollamaReachable} model={config.ollamaModel} />
            <ApiStatusPill status={health.status} label={pillLabel} />
          </div>
        </header>

        <main className="flex-1 overflow-auto px-8 py-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={reduceMotion ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduceMotion ? undefined : { opacity: 0, y: -6 }}
              transition={{ duration: reduceMotion ? 0 : 0.28, ease: [0.22, 1, 0.36, 1] }}
              className="mx-auto max-w-6xl"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
