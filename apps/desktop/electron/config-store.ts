import fs from "node:fs";
import path from "node:path";
import { z } from "zod";

export const jarvisConfigSchema = z.object({
  apiBaseUrl: z.string().url(),
  accent: z.enum(["cyan", "amber", "violet"]),
  ollamaModel: z.string().min(1),
});

export type JarvisConfig = z.infer<typeof jarvisConfigSchema>;

export const defaultJarvisConfig: JarvisConfig = {
  apiBaseUrl: "http://127.0.0.1:8000",
  accent: "cyan",
  ollamaModel: "llama3",
};

export function configFilePath(userData: string): string {
  return path.join(userData, "config.json");
}

export function readConfig(userData: string): JarvisConfig {
  const file = configFilePath(userData);
  try {
    const raw = fs.readFileSync(file, "utf-8");
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const merged = { ...defaultJarvisConfig, ...parsed };
    return jarvisConfigSchema.parse(merged);
  } catch {
    return { ...defaultJarvisConfig };
  }
}

export function writeConfig(userData: string, config: JarvisConfig): void {
  const file = configFilePath(userData);
  const validated = jarvisConfigSchema.parse(config);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(validated, null, 2), "utf-8");
}
