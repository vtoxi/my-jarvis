import { z } from "zod";

export const jarvisConfigSchema = z.object({
  apiBaseUrl: z.string().url(),
  accent: z.enum(["cyan", "amber", "violet"]),
  ollamaModel: z.string().min(1).default("llama3"),
});

export type JarvisConfigInput = z.infer<typeof jarvisConfigSchema>;
