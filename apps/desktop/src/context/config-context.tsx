import * as React from "react";

import { defaultRendererConfig } from "@/lib/default-config";
import type { JarvisConfig } from "@/types/jarvis-config";

type ConfigContextValue = {
  config: JarvisConfig;
  ready: boolean;
  update: (next: JarvisConfig) => Promise<void>;
  reset: () => Promise<void>;
};

const ConfigContext = React.createContext<ConfigContextValue | null>(null);

async function loadFromBridge(): Promise<JarvisConfig> {
  if (typeof window !== "undefined" && window.jarvis) {
    return window.jarvis.config.get();
  }
  return defaultRendererConfig;
}

async function saveToBridge(next: JarvisConfig): Promise<JarvisConfig> {
  if (typeof window !== "undefined" && window.jarvis) {
    return window.jarvis.config.set(next);
  }
  return next;
}

async function resetBridge(): Promise<JarvisConfig> {
  if (typeof window !== "undefined" && window.jarvis) {
    return window.jarvis.config.reset();
  }
  return defaultRendererConfig;
}

export function ConfigProvider({ children }: { children: React.ReactNode }) {
  const [config, setConfig] = React.useState<JarvisConfig>(defaultRendererConfig);
  const [ready, setReady] = React.useState(false);

  React.useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const loaded = await loadFromBridge();
        if (!cancelled) {
          setConfig(loaded);
        }
      } finally {
        if (!cancelled) {
          setReady(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  React.useEffect(() => {
    document.documentElement.dataset.accent = config.accent;
  }, [config.accent]);

  const update = React.useCallback(async (next: JarvisConfig) => {
    const saved = await saveToBridge(next);
    setConfig(saved);
  }, []);

  const reset = React.useCallback(async () => {
    const saved = await resetBridge();
    setConfig(saved);
  }, []);

  const value = React.useMemo(
    () => ({
      config,
      ready,
      update,
      reset,
    }),
    [config, ready, update, reset],
  );

  return <ConfigContext.Provider value={value}>{children}</ConfigContext.Provider>;
}

export function useConfig(): ConfigContextValue {
  const ctx = React.useContext(ConfigContext);
  if (!ctx) {
    throw new Error("useConfig must be used within ConfigProvider");
  }
  return ctx;
}
