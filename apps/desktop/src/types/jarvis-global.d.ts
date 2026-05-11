import type { JarvisConfig } from "./jarvis-config";

export type JarvisBridge = {
  config: {
    get: () => Promise<JarvisConfig>;
    set: (value: JarvisConfig) => Promise<JarvisConfig>;
    reset: () => Promise<JarvisConfig>;
  };
  app: {
    getVersion: () => Promise<string>;
  };
};

declare global {
  interface Window {
    jarvis?: JarvisBridge;
  }
}

export {};
