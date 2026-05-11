import { AnimatePresence, motion } from "framer-motion";
import { Flame, Loader2, MessageSquare, Radar, Send, ShieldCheck, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { GlassPanel } from "@/components/glass-panel";
import { HudSectionTitle } from "@/components/hud-section-title";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useConfig } from "@/context/config-context";
import {
  fetchSlackPriority,
  fetchSlackStatus,
  fetchSlackUnread,
  postSlackBriefing,
  postSlackDraft,
  postSlackSend,
  postSlackSendPrepare,
  slackConnectUrl,
  type SlackPriorityResponse,
  type SlackStatus,
  type SlackUnreadResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

export function SlackHubPage() {
  const { config } = useConfig();
  const [status, setStatus] = useState<SlackStatus | null>(null);
  const [priority, setPriority] = useState<SlackPriorityResponse | null>(null);
  const [unread, setUnread] = useState<SlackUnreadResponse | null>(null);
  const [briefing, setBriefing] = useState<string | null>(null);
  const [draft, setDraft] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [tone, setTone] = useState<"executive" | "friendly" | "technical">("executive");
  const [draftCtx, setDraftCtx] = useState("Paste thread summary or paste Slack text you want to answer…");
  const [sendChannelId, setSendChannelId] = useState("");
  const [sendThreadTs, setSendThreadTs] = useState("");
  const [sendText, setSendText] = useState("");
  const [sendToken, setSendToken] = useState<string | null>(null);
  const [sendTokenExp, setSendTokenExp] = useState<number | null>(null);
  const [sendMsg, setSendMsg] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const s = await fetchSlackStatus(config.apiBaseUrl);
      setStatus(s);
      if (!s.connected) {
        setPriority(null);
        setUnread(null);
        return;
      }
      try {
        const [p, u] = await Promise.all([
          fetchSlackPriority(config.apiBaseUrl),
          fetchSlackUnread(config.apiBaseUrl),
        ]);
        setPriority(p);
        setUnread(u);
      } catch {
        setPriority(null);
        setUnread(null);
      }
    } catch {
      setStatus(null);
    }
  }, [config.apiBaseUrl]);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 12000);
    return () => window.clearInterval(id);
  }, [refresh]);

  const heatData = useMemo(() => {
    const rows = priority?.heatmap ?? [];
    return rows.slice(0, 10).map((r) => ({
      id: (r.channel_id ?? "").slice(-6),
      intensity: Math.round((r.intensity ?? 0) * 100),
    }));
  }, [priority]);

  const onWorkday = async () => {
    setBusy("briefing");
    setBriefing(null);
    try {
      const res = await postSlackBriefing(config.apiBaseUrl, {
        max_channels: 10,
        messages_per_channel: 45,
        model: config.ollamaModel,
      });
      setBriefing(res.briefing_markdown);
    } catch (e) {
      setBriefing(e instanceof Error ? e.message : "Briefing failed");
    } finally {
      setBusy(null);
    }
  };

  const onDraft = async () => {
    setBusy("draft");
    setDraft(null);
    try {
      const res = await postSlackDraft(config.apiBaseUrl, {
        channel_id: "draft-local",
        context: draftCtx,
        tone,
        model: config.ollamaModel,
      });
      setDraft(res.draft_markdown);
    } catch (e) {
      setDraft(e instanceof Error ? e.message : "Draft failed");
    } finally {
      setBusy(null);
    }
  };

  const onMintSendToken = async () => {
    setSendMsg(null);
    setSendToken(null);
    setSendTokenExp(null);
    setBusy("send-prepare");
    try {
      const res = await postSlackSendPrepare(config.apiBaseUrl, {
        channel_id: sendChannelId.trim(),
        thread_ts: sendThreadTs.trim() || null,
        text: sendText,
      });
      setSendToken(res.approval_token);
      setSendTokenExp(res.expires_at_unix);
      setSendMsg("Token minted — review the message, then confirm send.");
    } catch (e) {
      setSendMsg(e instanceof Error ? e.message : "Prepare failed");
    } finally {
      setBusy(null);
    }
  };

  const onConfirmSend = async () => {
    if (!sendToken) {
      setSendMsg("Mint a token first.");
      return;
    }
    setBusy("send");
    setSendMsg(null);
    try {
      const res = await postSlackSend(config.apiBaseUrl, { approval_token: sendToken, text: sendText });
      setSendMsg(res.ok ? `Posted — ts ${res.ts ?? "?"}` : "Send failed");
      if (res.ok) {
        setSendToken(null);
        setSendTokenExp(null);
      }
    } catch (e) {
      setSendMsg(e instanceof Error ? e.message : "Send failed");
    } finally {
      setBusy(null);
    }
  };

  const topCards = priority?.ranked_messages?.slice(0, 5) ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-muted-foreground">Phase 4</p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight">Slack command center</h2>
          <p className="mt-2 max-w-xl text-sm text-muted-foreground">
            Read-first intelligence, priority heatmap, and draft-only replies. No auto-send — approval always required.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            className="border-[hsl(var(--neon))]/40"
            onClick={() => window.open(slackConnectUrl(config.apiBaseUrl), "_blank", "noopener,noreferrer")}
            disabled={status !== null && (!status.oauth_configured || status.redirect_uri_ok === false)}
            title={
              status !== null && !status.oauth_configured
                ? "Set JARVIS_SLACK_CLIENT_ID and JARVIS_SLACK_CLIENT_SECRET in apps/api/.env, then restart the API."
                : status?.redirect_uri_ok === false && status.redirect_uri_issue
                  ? status.redirect_uri_issue
                  : "Opens Slack OAuth in your default browser (Electron blocks popups; the app uses the system browser)."
            }
          >
            <MessageSquare className="mr-2 h-4 w-4" aria-hidden />
            Connect Slack
          </Button>
          <Button className="shadow-hud" onClick={() => void onWorkday()} disabled={!status?.connected || busy === "briefing"}>
            {busy === "briefing" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
            Start workday brief
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <GlassPanel className="p-5 lg:col-span-1">
          <div className="flex items-start gap-2">
            <Radar className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--neon))]" aria-hidden />
            <HudSectionTitle eyebrow="Workspace + permission rail" title="Link status" />
          </div>
          <div className="mt-4 space-y-2 text-sm">
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Connected</span>
              <span className={cn("font-semibold", status?.connected ? "text-[hsl(var(--neon))]" : "text-amber-500")}>
                {status?.connected ? "Yes" : "No"}
              </span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Workspace</span>
              <span className="truncate font-medium">{status?.team_name ?? "—"}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Phase</span>
              <span className="font-mono text-xs">{status?.phase ?? "—"}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">OAuth ready</span>
              <span>{status?.oauth_configured ? "Yes" : "No"}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Approved send</span>
              <span className={status?.write_enabled ? "font-semibold text-amber-500" : ""}>
                {status?.write_enabled ? "Armed (4C)" : "Off"}
              </span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Slack health</span>
              <span className="font-semibold tabular-nums">{priority?.slack_health_score ?? "—"}</span>
            </div>
            {status?.oauth_configured && status.redirect_uri_ok === false && status.redirect_uri_issue ? (
              <div className="mt-4 rounded-md border border-red-500/40 bg-red-500/10 p-3 text-xs leading-relaxed text-red-200/95">
                <p className="font-semibold text-red-100">Slack OAuth redirect is not valid for bot install</p>
                <p className="mt-2">{status.redirect_uri_issue}</p>
              </div>
            ) : null}
            {status?.oauth_configured && status.redirect_uri_note ? (
              <div className="mt-4 rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-xs leading-relaxed text-muted-foreground">
                <p className="font-semibold text-amber-200/90">Redirect URI note</p>
                <p className="mt-2">{status.redirect_uri_note}</p>
              </div>
            ) : null}
            {status?.oauth_configured && status.redirect_uri ? (
              <div className="mt-4 rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-xs leading-relaxed text-muted-foreground">
                <p className="font-semibold text-amber-200/90">Slack redirect URL (must match app settings)</p>
                <p className="mt-1">
                  In{" "}
                  <a
                    className="text-[hsl(var(--neon))] underline underline-offset-2"
                    href="https://api.slack.com/apps"
                    target="_blank"
                    rel="noreferrer"
                  >
                    api.slack.com/apps
                  </a>{" "}
                  → your app → <strong className="text-foreground/90">OAuth &amp; Permissions</strong> →{" "}
                  <strong className="text-foreground/90">Redirect URLs</strong>, add this <em>exact</em> URL (scheme,
                  host, path, no trailing slash unless you configured one):
                </p>
                <code className="mt-2 block break-all rounded bg-muted/50 px-2 py-1.5 font-mono text-[11px] text-foreground/90">
                  {status.redirect_uri}
                </code>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="mt-2"
                  onClick={() => void navigator.clipboard.writeText(status.redirect_uri ?? "")}
                >
                  Copy redirect URI
                </Button>
                <p className="mt-2 text-[11px]">
                  If Slack says “redirect_uri did not match”, you pasted a different host (e.g.{" "}
                  <span className="font-mono">localhost</span> vs <span className="font-mono">127.0.0.1</span>) or{" "}
                  <span className="font-mono">https</span> vs <span className="font-mono">http</span>. Either add this
                  URI in Slack or set <span className="font-mono">JARVIS_SLACK_REDIRECT_URI</span> to match what you
                  already added, then restart the API.
                </p>
              </div>
            ) : null}
          </div>
        </GlassPanel>

        <GlassPanel className="p-5 lg:col-span-2">
          <div className="flex items-start gap-2">
            <Flame className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--neon))]" aria-hidden />
            <HudSectionTitle eyebrow="Relative activity by channel (recent pull)" title="Communication heatmap" />
          </div>
          <div className="mt-4 h-48 w-full">
            {heatData.length === 0 ? (
              <p className="text-sm text-muted-foreground">Connect Slack to populate the heatmap.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={heatData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <XAxis dataKey="id" tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis hide domain={[0, 100]} />
                  <Tooltip
                    cursor={{ fill: "hsl(var(--muted) / 0.15)" }}
                    contentStyle={{
                      background: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="intensity" fill="hsl(var(--neon))" radius={[4, 4, 0, 0]} opacity={0.85} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </GlassPanel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <GlassPanel className="p-5">
          <div className="flex items-start gap-2">
            <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--neon))]" aria-hidden />
            <HudSectionTitle eyebrow="Scored signals — not native Slack unread" title="Priority inbox" />
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <AnimatePresence>
              {topCards.length === 0 ? (
                <p className="text-sm text-muted-foreground sm:col-span-2">No priority rows yet.</p>
              ) : (
                topCards.map((m, i) => (
                  <motion.div
                    key={`${m.channel_id}-${m.ts}-${i}`}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04 }}
                    className="rounded-lg border border-border/60 bg-background/40 p-3 text-xs shadow-inner"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate font-semibold">{m.channel_name ?? m.channel_id}</span>
                      <span className="shrink-0 rounded bg-[hsl(var(--neon))]/15 px-2 py-0.5 font-mono text-[10px] text-[hsl(var(--neon))]">
                        {m.score.toFixed(1)}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-3 text-muted-foreground">{m.text}</p>
                  </motion.div>
                ))
              )}
            </AnimatePresence>
          </div>
        </GlassPanel>

        <GlassPanel className="p-5">
          <div className="flex items-start gap-2">
            <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--neon))]" aria-hidden />
            <HudSectionTitle eyebrow="Channels with high-priority hits" title="Heuristic unread" />
          </div>
          <ScrollArea className="mt-4 h-56 pr-3">
            <ul className="space-y-2 text-sm">
              {(unread?.channels ?? []).map((c) => (
                <li key={c.channel_id} className="rounded-md border border-border/50 bg-muted/20 px-3 py-2">
                  <div className="flex justify-between gap-2 font-medium">
                    <span className="truncate">{c.name ?? c.channel_id}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">{c.high_priority_hits} hits</span>
                  </div>
                  {c.top_snippet ? <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{c.top_snippet}</p> : null}
                </li>
              ))}
              {(!unread?.channels || unread.channels.length === 0) && (
                <li className="text-muted-foreground">Connect to load channel summaries.</li>
              )}
            </ul>
          </ScrollArea>
        </GlassPanel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <GlassPanel className="p-5">
          <div className="flex items-start gap-2">
            <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--neon))]" aria-hidden />
            <HudSectionTitle eyebrow="CrewAI + Slack intel + draft themes" title="Today’s command brief" />
          </div>
          <div className="mt-4 flex gap-2">
            <Button size="sm" variant="outline" onClick={() => void onWorkday()} disabled={!status?.connected || busy === "briefing"}>
              Refresh brief
            </Button>
          </div>
          <ScrollArea className="mt-4 h-[min(420px,55vh)] rounded-md border border-border/40 bg-background/30">
            <pre className="whitespace-pre-wrap p-4 font-sans text-xs leading-relaxed text-foreground/90">
              {briefing ?? "Run “Start workday brief” after connecting Slack."}
            </pre>
          </ScrollArea>
        </GlassPanel>

        <GlassPanel className="p-5">
          <div className="flex items-start gap-2">
            <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-[hsl(var(--neon))]" aria-hidden />
            <HudSectionTitle eyebrow="Phase 4B — drafts only" title="Reply draft rail" />
          </div>
          <div className="mt-4 space-y-3">
            <label className="text-xs font-medium text-muted-foreground">Tone</label>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={tone}
              onChange={(e) => setTone(e.target.value as typeof tone)}
            >
              <option value="executive">Executive</option>
              <option value="friendly">Friendly</option>
              <option value="technical">Technical</option>
            </select>
            <textarea
              value={draftCtx}
              onChange={(e) => setDraftCtx(e.target.value)}
              rows={6}
              className={cn(
                "flex min-h-[140px] w-full rounded-md border border-border bg-muted/40 px-3 py-2 font-mono text-xs shadow-sm",
                "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              )}
            />
            <Button onClick={() => void onDraft()} disabled={busy === "draft"}>
              {busy === "draft" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Generate drafts
            </Button>
            <ScrollArea className="h-48 rounded-md border border-border/40 bg-background/30">
              <pre className="whitespace-pre-wrap p-3 font-sans text-xs leading-relaxed">{draft ?? "Drafts appear here."}</pre>
            </ScrollArea>
          </div>
        </GlassPanel>
      </div>

      <GlassPanel className="p-5">
        <div className="flex items-start gap-2">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" aria-hidden />
          <HudSectionTitle
            eyebrow="Two-step HMAC token — never auto-send"
            title="Phase 4C — approved Slack send"
          />
        </div>
        {!status?.write_enabled ? (
          <p className="mt-4 text-sm text-muted-foreground">
            Set <span className="font-mono text-foreground/80">JARVIS_SLACK_WRITE_ENABLED=true</span> in{" "}
            <span className="font-mono text-foreground/80">apps/api/.env</span>, add the{" "}
            <span className="font-mono text-foreground/80">chat:write</span> bot scope in your Slack app, then use{" "}
            <span className="font-semibold">Connect Slack</span> again to reinstall the token.
          </p>
        ) : !status.connected ? (
          <p className="mt-4 text-sm text-muted-foreground">Connect Slack first, then use the send rail below.</p>
        ) : (
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div className="space-y-3 text-sm">
              <label className="text-xs font-medium text-muted-foreground">Channel ID</label>
              <input
                value={sendChannelId}
                onChange={(e) => setSendChannelId(e.target.value)}
                placeholder="C0123456789"
                className="flex h-9 w-full rounded-md border border-border bg-muted/40 px-3 font-mono text-xs shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <label className="text-xs font-medium text-muted-foreground">Thread ts (optional)</label>
              <input
                value={sendThreadTs}
                onChange={(e) => setSendThreadTs(e.target.value)}
                placeholder="1234567890.123456"
                className="flex h-9 w-full rounded-md border border-border bg-muted/40 px-3 font-mono text-xs shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <label className="text-xs font-medium text-muted-foreground">Message (exact bytes for token + send)</label>
              <textarea
                value={sendText}
                onChange={(e) => {
                  setSendText(e.target.value);
                  setSendToken(null);
                  setSendTokenExp(null);
                }}
                rows={5}
                className={cn(
                  "flex min-h-[100px] w-full rounded-md border border-border bg-muted/40 px-3 py-2 text-sm shadow-sm",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                )}
              />
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => void onMintSendToken()}
                  disabled={busy === "send-prepare" || !sendChannelId.trim() || !sendText.trim()}
                >
                  {busy === "send-prepare" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Step 1 — Mint token
                </Button>
                <Button
                  type="button"
                  className="shadow-hud"
                  onClick={() => void onConfirmSend()}
                  disabled={busy === "send" || !sendToken}
                >
                  {busy === "send" ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
                  Step 2 — Send
                </Button>
              </div>
            </div>
            <div className="space-y-2 rounded-md border border-border/50 bg-background/30 p-4 text-xs">
              <p className="font-semibold text-foreground">Operator checklist</p>
              <ul className="list-inside list-disc space-y-1 text-muted-foreground">
                <li>Token binds channel, optional thread, and SHA-256 of the message.</li>
                <li>Changing the message after mint invalidates the token.</li>
                <li>Tokens expire in a few minutes.</li>
              </ul>
              {sendTokenExp ? (
                <p className="pt-2 font-mono text-[11px] text-muted-foreground">
                  Expires: {new Date(sendTokenExp * 1000).toLocaleString()}
                </p>
              ) : null}
              {sendToken ? (
                <ScrollArea className="mt-2 max-h-28 rounded border border-border/40 bg-muted/20 p-2">
                  <code className="break-all text-[10px] leading-relaxed text-foreground/90">{sendToken}</code>
                </ScrollArea>
              ) : (
                <p className="pt-2 text-muted-foreground">No active token.</p>
              )}
              {sendMsg ? <p className="pt-2 text-[hsl(var(--neon))]">{sendMsg}</p> : null}
            </div>
          </div>
        )}
      </GlassPanel>
    </div>
  );
}
