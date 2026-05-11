const SESSION_KEY = "jarvis:session_id";

export function getOrCreateSessionId(): string {
  if (typeof window === "undefined" || !window.localStorage) {
    return "dev-session";
  }
  let existing = window.localStorage.getItem(SESSION_KEY);
  if (!existing) {
    existing = crypto.randomUUID();
    window.localStorage.setItem(SESSION_KEY, existing);
  }
  return existing;
}
