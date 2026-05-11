import { motion, useReducedMotion } from "framer-motion";
import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const BOOT_MS = 2800;

export function BootScreen() {
  const navigate = useNavigate();
  const reduceMotion = useReducedMotion();
  const [progress, setProgress] = useState(0);

  const finish = useCallback(() => {
    navigate("/dashboard", { replace: true });
  }, [navigate]);

  useEffect(() => {
    if (reduceMotion) {
      setProgress(100);
      const t = window.setTimeout(finish, 400);
      return () => window.clearTimeout(t);
    }
    const started = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const p = Math.min(100, ((now - started) / BOOT_MS) * 100);
      setProgress(p);
      if (p >= 100) {
        finish();
        return;
      }
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [finish, reduceMotion]);

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-[hsl(var(--hud-bg))] px-6">
      <div className="pointer-events-none absolute inset-0 hud-grid-bg" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_20%,hsl(var(--neon)/0.18),transparent_55%)]" />

      <motion.div
        initial={reduceMotion ? false : { opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: reduceMotion ? 0 : 0.8, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 flex max-w-xl flex-col items-center text-center"
      >
        <p className="text-[11px] font-semibold uppercase tracking-[0.45em] text-muted-foreground">JARVIS / OS</p>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-5xl">
          <span className="neon-text">Systems Online</span>
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
          Local-first command center. Phase 1 shell — intelligence layers arrive in Phase 2.
        </p>

        <div className="mt-10 w-full max-w-md">
          <div className="flex items-center justify-between text-[10px] font-semibold uppercase tracking-[0.3em] text-muted-foreground">
            <span>Initialize</span>
            <span className="tabular-nums">{Math.round(progress)}%</span>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <motion.div
              className="h-full rounded-full bg-[hsl(var(--neon))]"
              style={{ width: `${progress}%` }}
              layout
            />
          </div>
        </div>

        <Button variant="hud" className="mt-10" onClick={finish}>
          Enter command center
        </Button>
        <p className={cn("mt-3 text-[11px] text-muted-foreground", reduceMotion && "sr-only")}>
          Or wait for auto-handoff…
        </p>
      </motion.div>
    </div>
  );
}
