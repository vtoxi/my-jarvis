import * as React from "react";

import { fetchHealth } from "@/lib/api";

export type ApiHealth = {
  status: "ok" | "down" | "checking";
  lastChecked: Date | null;
  error: string | null;
};

export function useApiHealth(apiBaseUrl: string, enabled: boolean): ApiHealth {
  const [state, setState] = React.useState<ApiHealth>({
    status: "checking",
    lastChecked: null,
    error: null,
  });

  React.useEffect(() => {
    if (!enabled) {
      return;
    }

    const controller = new AbortController();
    let cancelled = false;

    const tick = async () => {
      setState((s) => ({ ...s, status: "checking" }));
      try {
        await fetchHealth(apiBaseUrl, controller.signal);
        if (cancelled) return;
        setState({ status: "ok", lastChecked: new Date(), error: null });
      } catch (e) {
        if (cancelled) return;
        const message = e instanceof Error ? e.message : "unreachable";
        setState({ status: "down", lastChecked: new Date(), error: message });
      }
    };

    void tick();
    const id = window.setInterval(() => void tick(), 5000);

    return () => {
      cancelled = true;
      controller.abort();
      window.clearInterval(id);
    };
  }, [apiBaseUrl, enabled]);

  return state;
}
