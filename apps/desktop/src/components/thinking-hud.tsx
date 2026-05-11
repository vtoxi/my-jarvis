import { motion, useReducedMotion } from "framer-motion";

import { cn } from "@/lib/utils";

export function ThinkingHud({ active, label }: { active: boolean; label: string }) {
  const reduceMotion = useReducedMotion();
  if (!active) {
    return null;
  }
  return (
    <div
      className={cn(
        "mb-3 flex items-center gap-3 rounded-hud border border-[hsl(var(--neon)/0.35)] bg-muted/30 px-4 py-3 text-xs font-medium text-foreground/90",
      )}
      role="status"
      aria-live="polite"
    >
      {!reduceMotion ? (
        <motion.span
          className="relative flex h-3 w-3"
          animate={{ opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
        >
          <span className="absolute inline-flex h-full w-full rounded-full bg-[hsl(var(--neon))] opacity-60 blur-[2px]" />
          <span className="relative inline-flex h-3 w-3 rounded-full bg-[hsl(var(--neon))]" />
        </motion.span>
      ) : (
        <span className="h-3 w-3 rounded-full bg-[hsl(var(--neon))]" />
      )}
      <span className="tracking-wide text-muted-foreground">{label}</span>
    </div>
  );
}
