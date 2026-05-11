import * as React from "react";

import { cn } from "@/lib/utils";

export type GlassPanelProps = React.HTMLAttributes<HTMLDivElement>;

export function GlassPanel({ className, ...props }: GlassPanelProps) {
  return <div className={cn("glass-panel rounded-hud", className)} {...props} />;
}
