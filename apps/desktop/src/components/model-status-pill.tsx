import { Cpu } from "lucide-react";

import { cn } from "@/lib/utils";

export function ModelStatusPill({
  reachable,
  model,
}: {
  reachable: boolean;
  model: string;
}) {
  const color = reachable ? "text-emerald-300" : "text-rose-300";
  const dot = reachable ? "bg-emerald-400" : "bg-rose-400";

  return (
    <div
      className={cn(
        "glass-panel inline-flex max-w-[220px] items-center gap-2 truncate rounded-full border border-border/80 px-3 py-1 text-xs font-medium",
        color,
      )}
    >
      <span className={cn("h-2 w-2 shrink-0 rounded-full", dot)} />
      <Cpu className="h-3.5 w-3.5 shrink-0 opacity-80" aria-hidden />
      <span className="truncate text-foreground/90">{reachable ? model : "Ollama offline"}</span>
    </div>
  );
}
