import { motion } from "framer-motion";
import { Activity } from "lucide-react";

import { cn } from "@/lib/utils";

export function ApiStatusPill({
  status,
  label,
}: {
  status: "ok" | "down" | "checking";
  label: string;
}) {
  const color =
    status === "ok" ? "text-emerald-400" : status === "checking" ? "text-amber-300" : "text-rose-400";
  const dot =
    status === "ok" ? "bg-emerald-400" : status === "checking" ? "bg-amber-300 animate-pulse" : "bg-rose-400";

  return (
    <div
      className={cn(
        "glass-panel inline-flex items-center gap-2 rounded-full border border-border/80 px-3 py-1 text-xs font-medium",
        color,
      )}
    >
      {status === "ok" ? (
        <motion.span
          className={cn("h-2 w-2 rounded-full", dot)}
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
      ) : (
        <span className={cn("h-2 w-2 rounded-full", dot)} />
      )}
      <Activity className="h-3.5 w-3.5 opacity-80" aria-hidden />
      <span className="text-foreground/90">{label}</span>
    </div>
  );
}
