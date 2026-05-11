import type { JarvisConfig } from "@/types/jarvis-config";

export const defaultRendererConfig: JarvisConfig = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000",
  accent: "cyan",
  ollamaModel: import.meta.env.VITE_OLLAMA_MODEL ?? "llama3",
};
