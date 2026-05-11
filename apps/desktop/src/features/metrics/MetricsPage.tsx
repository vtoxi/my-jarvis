import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { GlassPanel } from "@/components/glass-panel";
import { HudSectionTitle } from "@/components/hud-section-title";

type Point = {
  t: string;
  cpu: number;
  ram: number;
};

function nextPoint(prev: Point[], tick: number): Point[] {
  const lastCpu = prev.at(-1)?.cpu ?? 22;
  const lastRam = prev.at(-1)?.ram ?? 48;
  const cpu = Math.min(98, Math.max(6, lastCpu + (Math.sin(tick / 2) + Math.random() - 0.5) * 8));
  const ram = Math.min(92, Math.max(18, lastRam + (Math.cos(tick / 3) + Math.random() - 0.45) * 6));
  const label = `${String(tick % 24).padStart(2, "0")}:${String((tick * 5) % 60).padStart(2, "0")}`;
  const next = [...prev, { t: label, cpu, ram }];
  return next.slice(-24);
}

export function MetricsPage() {
  const [data, setData] = useState<Point[]>(() =>
    Array.from({ length: 16 }, (_, i) => ({
      t: `${String(i).padStart(2, "0")}:00`,
      cpu: 18 + ((i * 7) % 40),
      ram: 40 + ((i * 5) % 25),
    })),
  );
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => {
      setTick((t) => t + 1);
    }, 1500);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    setData((prev) => nextPoint(prev, tick));
  }, [tick]);

  const gradientIdCpu = useMemo(() => "cpuFill", []);
  const gradientIdRam = useMemo(() => "ramFill", []);

  return (
    <div className="space-y-6">
      <HudSectionTitle
        eyebrow="Telemetry"
        title="System metrics (simulated)"
        className="max-w-2xl"
      />
      <p className="max-w-2xl text-sm text-muted-foreground">
        Phase 1 uses mock series with timer drift. Native sensors and permissions land in Phase 3.
      </p>

      <GlassPanel className="p-4 sm:p-6">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-muted-foreground">Live feed</p>
            <p className="text-sm text-foreground/90">CPU vs RAM — placeholder signals</p>
          </div>
          <div className="flex gap-4 text-xs text-muted-foreground">
            <span className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-[hsl(var(--neon))]" /> CPU
            </span>
            <span className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-violet-400" /> RAM
            </span>
          </div>
        </div>
        <div className="h-[320px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id={gradientIdCpu} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--neon))" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="hsl(var(--neon))" stopOpacity={0} />
                </linearGradient>
                <linearGradient id={gradientIdRam} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#a78bfa" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#a78bfa" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.6} />
              <XAxis dataKey="t" tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${v}%`}
              />
              <Tooltip
                contentStyle={{
                  background: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: 12,
                }}
                labelStyle={{ color: "hsl(var(--foreground))" }}
              />
              <Area type="monotone" dataKey="cpu" stroke="hsl(var(--neon))" fillOpacity={1} fill={`url(#${gradientIdCpu})`} strokeWidth={2} />
              <Area type="monotone" dataKey="ram" stroke="#a78bfa" fillOpacity={1} fill={`url(#${gradientIdRam})`} strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </GlassPanel>
    </div>
  );
}
