/** Shown when the API cannot safely auto-fix — mirrors server `operator_takeover` intent. */
export const OPERATOR_TAKEOVER_LINES: readonly string[] = [
  "JARVIS does not move your mouse, type passwords, or run shell commands on its own — that is intentional for safety and macOS privacy.",
  "Use Copilot / screen: capture or refresh context, then paste text into the repair `context` field so the model sees what you see.",
  "Read API logs (GET /system/logs or the path in the error) while you reproduce the problem in Terminal or the failing app.",
  "UI control only exists where you enable Control deck + Hammerspoon and approve actions — not from background self-healing.",
];
