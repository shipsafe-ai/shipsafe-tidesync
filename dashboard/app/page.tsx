"use client";

import { useCallback, useEffect, useState } from "react";
import { ConnectionHealth } from "@/components/ConnectionHealth";
import { ContradictionPanel } from "@/components/ContradictionPanel";
import { MorningBriefing } from "@/components/MorningBriefing";
import { SLAProjection } from "@/components/SLAProjection";
import { StalenessIndicator } from "@/components/StalenessIndicator";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const STALE_THRESHOLD = parseInt(process.env.NEXT_PUBLIC_STALE_THRESHOLD ?? "3600");

export default function Home() {
  const [connections, setConnections] = useState<any[]>([]);
  const [freshnessReports, setFreshnessReports] = useState<any[]>([]);
  const [briefing, setBriefing] = useState<any>(null);
  const [contradiction, setContradiction] = useState<any>(null);
  const [critic, setCritic] = useState<any>(null);
  const [approvalToken, setApprovalToken] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [runStep, setRunStep] = useState<string | null>(null);
  const [loadingConnections, setLoadingConnections] = useState(true);
  const [loadingFreshness, setLoadingFreshness] = useState(true);

  const RUN_STEPS = [
    { ms: 0, text: "Querying Fivetran MCP connectors..." },
    { ms: 6_000, text: "Checking BigQuery data freshness..." },
    { ms: 14_000, text: "Running Gemini contradiction analysis..." },
    { ms: 30_000, text: "Finalizing analysis..." },
  ];

  const fetchConnections = useCallback(async () => {
    setLoadingConnections(true);
    try {
      const res = await fetch(`${API}/connections`);
      if (res.ok) setConnections(await res.json());
    } catch {}
    setLoadingConnections(false);
  }, []);

  const fetchFreshness = useCallback(async () => {
    setLoadingFreshness(true);
    try {
      const res = await fetch(`${API}/freshness`);
      if (res.ok) setFreshnessReports(await res.json());
    } catch {}
    setLoadingFreshness(false);
  }, []);

  const fetchBriefing = useCallback(async () => {
    try {
      const res = await fetch(`${API}/briefing`);
      const data = await res.json();
      if (data.summary && Array.isArray(data.anomalies)) setBriefing(data);
    } catch {}
  }, []);

  useEffect(() => {
    fetchConnections();
    fetchFreshness();
    fetchBriefing();
  }, [fetchConnections, fetchFreshness, fetchBriefing]);

  async function runAnalysis() {
    setRunning(true);
    setRunStep(RUN_STEPS[0].text);
    const timers = RUN_STEPS.slice(1).map((s) =>
      setTimeout(() => setRunStep(s.text), s.ms)
    );
    try {
      const res = await fetch(`${API}/run`, { method: "POST" });
      const data = await res.json();
      if (data.contradiction) setContradiction(data.contradiction);
      if (data.critic_challenge) setCritic(data.critic_challenge);
      if (data.approval_token) setApprovalToken(data.approval_token);
      await fetchFreshness();
      await fetchConnections();
      // Poll for background briefing after a delay
      setTimeout(fetchBriefing, 10_000);
      setTimeout(fetchBriefing, 25_000);
    } catch {}
    timers.forEach(clearTimeout);
    setRunStep(null);
    setRunning(false);
  }

  async function approveResync(token: string) {
    try {
      const res = await fetch(`${API}/approve/${token}`, { method: "POST" });
      if (res.ok) {
        setApprovalToken(null);
        await fetchFreshness();
      }
    } catch {}
  }

  const latestBQ = freshnessReports[0] ?? null;
  const latestFT = connections[0] ?? null;

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">Pipeline Monitor</h1>
          <p className="text-xs text-muted font-mono mt-0.5">
            Detects sync-OK but data-stale contradictions
          </p>
        </div>
        <button
          onClick={runAnalysis}
          disabled={running}
          className="px-5 py-2 bg-accent text-white text-xs font-mono disabled:opacity-50 hover:bg-violet-500 transition-colors"
        >
          {running ? "Running..." : "Run TideSync"}
        </button>
      </div>

      {/* Thinking panel */}
      {running && runStep && (
        <div className="bg-bg-card border border-accent/30 p-4" style={{ borderRadius: "4px" }}>
          <div className="flex items-center gap-3">
            <div className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <span
                  key={i}
                  className="inline-block w-1.5 h-1.5 rounded-full bg-accent animate-bounce"
                  style={{ animationDelay: `${i * 120}ms` }}
                />
              ))}
            </div>
            <p className="text-xs font-mono text-accent">{runStep}</p>
          </div>
        </div>
      )}

      {/* Main contradiction panel */}
      <ContradictionPanel
        contradiction={contradiction}
        fivetran={latestFT ? {
          succeeded_at: latestFT.succeeded_at,
          row_count: latestFT.row_count ?? 0,
          status: latestFT.status,
        } : null}
        bqMaxSynced={latestBQ?.max_synced_at ?? null}
        approvalToken={approvalToken}
        onApprove={approveResync}
      />

      {/* Gemini adversarial Critic — challenges the staleness verdict, shows reasoning */}
      {critic && (
        <div className="bg-bg-card border border-accent/30 p-4" style={{ borderRadius: "4px" }}>
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-mono uppercase tracking-wider text-muted">
              Adversarial Critic · Gemini
            </span>
            <span
              className={`text-xs font-mono px-2 py-0.5 ${
                critic.verdict === "UPHOLD"
                  ? "bg-signal-approve/15 text-signal-approve"
                  : "bg-signal-warn/15 text-signal-warn"
              }`}
              style={{ borderRadius: "4px" }}
            >
              {critic.verdict}
              {typeof critic.confidence === "number"
                ? ` · ${Math.round(critic.confidence * 100)}%`
                : ""}
            </span>
          </div>
          <p className="text-sm text-text-primary/90 leading-relaxed font-mono">
            {critic.reasoning}
          </p>
          {critic.injection_suspected && (
            <p className="mt-2 text-xs font-mono text-signal-block">
              ⚠ Possible prompt-injection in source data — flagged for human review.
            </p>
          )}
          {Array.isArray(critic.concerns) && critic.concerns.length > 0 && (
            <ul className="mt-2 space-y-1">
              {critic.concerns.map((c: string, i: number) => (
                <li key={i} className="text-xs font-mono text-muted flex gap-2">
                  <span className="text-accent">→</span>
                  {c}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="grid grid-cols-3 gap-4">
        <SLAProjection
          breach={contradiction?.sla_breach_eta ?? null}
          lagSeconds={latestBQ?.lag_seconds ?? 0}
          thresholdSeconds={STALE_THRESHOLD}
        />
        <div className="col-span-2">
          <StalenessIndicator
            reports={freshnessReports}
            threshold={STALE_THRESHOLD}
            loading={loadingFreshness}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <ConnectionHealth connections={connections} loading={loadingConnections} />
        <MorningBriefing briefing={briefing} loading={false} />
      </div>
    </div>
  );
}
