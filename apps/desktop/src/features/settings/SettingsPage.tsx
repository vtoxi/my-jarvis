import { useEffect, useState } from "react";

import { GlassPanel } from "@/components/glass-panel";
import { HudSectionTitle } from "@/components/hud-section-title";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { useConfig } from "@/context/config-context";
import { fetchModels } from "@/lib/api";
import { jarvisConfigSchema } from "@/lib/config-schema";
import type { Accent } from "@/types/jarvis-config";

export function SettingsPage() {
  const { config, update, reset } = useConfig();
  const [apiBaseUrl, setApiBaseUrl] = useState(config.apiBaseUrl);
  const [accent, setAccent] = useState<Accent>(config.accent);
  const [ollamaModel, setOllamaModel] = useState(config.ollamaModel);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState<string>("—");
  const [modelChoices, setModelChoices] = useState<string[]>([]);
  const [modelsNote, setModelsNote] = useState<string | null>(null);

  useEffect(() => {
    setApiBaseUrl(config.apiBaseUrl);
    setAccent(config.accent);
    setOllamaModel(config.ollamaModel);
  }, [config.apiBaseUrl, config.accent, config.ollamaModel]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      if (typeof window !== "undefined" && window.jarvis) {
        const v = await window.jarvis.app.getVersion();
        if (!cancelled) setVersion(v);
      } else if (!cancelled) {
        setVersion("dev");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const m = await fetchModels(apiBaseUrl, ollamaModel);
        if (cancelled) return;
        const names = m.installed.map((x) => x.name);
        const rec = m.recommended_defaults ?? [];
        const merged = Array.from(new Set([...rec, ...names]));
        setModelChoices(merged);
        setModelsNote(m.ollama_reachable ? null : m.ollama_error ?? "Ollama unreachable");
      } catch (e) {
        if (!cancelled) {
          setModelsNote(e instanceof Error ? e.message : "Failed to load models");
          setModelChoices(["llama3", "qwen2.5-coder"]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, ollamaModel]);

  const onSave = async () => {
    const parsed = jarvisConfigSchema.safeParse({ apiBaseUrl, accent, ollamaModel });
    if (!parsed.success) {
      setError(parsed.error.issues.map((x) => x.message).join(" · "));
      return;
    }
    setError(null);
    await update(parsed.data);
  };

  return (
    <div className="space-y-6">
      <HudSectionTitle eyebrow="Control plane" title="Local configuration" className="max-w-2xl" />
      <p className="max-w-2xl text-sm text-muted-foreground">
        API base URL, Ollama model tag, and HUD accent persist under the app userData directory via IPC.
      </p>

      <GlassPanel className="max-w-xl space-y-5 p-6">
        <div className="space-y-2">
          <Label htmlFor="api">API base URL</Label>
          <Input
            id="api"
            value={apiBaseUrl}
            onChange={(e) => setApiBaseUrl(e.target.value)}
            placeholder="http://127.0.0.1:8000"
            className="font-mono text-sm"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="model">Ollama model tag</Label>
          <Input
            id="model"
            list="ollama-model-options"
            value={ollamaModel}
            onChange={(e) => setOllamaModel(e.target.value)}
            placeholder="llama3"
            className="font-mono text-sm"
          />
          <datalist id="ollama-model-options">
            {modelChoices.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
          {modelsNote ? <p className="text-xs text-amber-300">{modelsNote}</p> : null}
        </div>

        <div className="space-y-2">
          <Label>Accent</Label>
          <div className="flex flex-wrap gap-2">
            {(["cyan", "amber", "violet"] as const).map((a) => (
              <Button
                key={a}
                type="button"
                variant={accent === a ? "default" : "outline"}
                size="sm"
                onClick={() => setAccent(a)}
                className="capitalize"
              >
                {a}
              </Button>
            ))}
          </div>
        </div>

        {error ? <p className="text-sm text-rose-300">{error}</p> : null}

        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={() => void onSave()}>
            Save changes
          </Button>
          <Button type="button" variant="outline" onClick={() => void reset()}>
            Reset defaults
          </Button>
        </div>

        <Separator className="bg-border/70" />

        <div className="text-sm text-muted-foreground">
          <p>
            <span className="font-semibold text-foreground">Desktop version:</span> {version}
          </p>
          <p className="mt-2 leading-relaxed">
            DevTools: set <span className="font-mono text-foreground">JARVIS_OPEN_DEVTOOLS=1</span> when launching
            Electron in development.
          </p>
        </div>
      </GlassPanel>
    </div>
  );
}
