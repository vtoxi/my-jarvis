import { useEffect, useMemo, useState } from "react";

import { AgentCard } from "@/components/agent-card";
import { HudSectionTitle } from "@/components/hud-section-title";
import { useConfig } from "@/context/config-context";
import { fetchAgentsStatus } from "@/lib/api";
import { getOrCreateSessionId } from "@/lib/session";
import type { AgentStatusItem } from "@/types/brain";
import type { AgentViewModel } from "@/types/agents";

function toViewModel(agent: AgentStatusItem): AgentViewModel {
  const status = !agent.enabled ? "offline" : agent.last_event ? "active" : "idle";
  const load = !agent.enabled ? 0.05 : agent.last_event ? 0.72 : 0.18;
  const detail = agent.last_event
    ? `${agent.description}\nLast signal: ${agent.last_event.summary}`
    : agent.description;
  return {
    id: agent.id,
    name: agent.name,
    role: `Phase ${agent.phase}`,
    status,
    load,
    detail,
  };
}

export function AgentsPage() {
  const { config } = useConfig();
  const [items, setItems] = useState<AgentStatusItem[]>([]);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const sid = getOrCreateSessionId();
        const res = await fetchAgentsStatus(config.apiBaseUrl, sid);
        if (!cancelled) {
          setItems(res.agents);
          setNote(null);
        }
      } catch (e) {
        if (!cancelled) {
          setNote(e instanceof Error ? e.message : "Unable to reach agents endpoint");
        }
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 10000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [config.apiBaseUrl]);

  const models = useMemo(() => items.map(toViewModel), [items]);

  return (
    <div className="space-y-6">
      <HudSectionTitle eyebrow="Synthetic crew" title="Agent status grid" className="max-w-2xl" />
      <p className="max-w-2xl text-sm text-muted-foreground">
        Live roster from <span className="font-mono text-foreground">GET /agents/status</span> with session-scoped
        activity hints.
      </p>
      {note ? <p className="text-sm text-amber-300">{note}</p> : null}
      <div className="grid gap-4 md:grid-cols-2">
        {models.map((agent, index) => (
          <AgentCard key={agent.id} agent={agent} index={index} />
        ))}
      </div>
    </div>
  );
}
