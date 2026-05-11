import { cn } from "@/lib/utils";

export function HudSectionTitle({
  eyebrow,
  title,
  className,
}: {
  eyebrow?: string;
  title: string;
  className?: string;
}) {
  return (
    <div className={cn("space-y-1", className)}>
      {eyebrow ? (
        <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-muted-foreground">{eyebrow}</p>
      ) : null}
      <h2 className="text-lg font-semibold tracking-tight text-foreground">{title}</h2>
    </div>
  );
}
