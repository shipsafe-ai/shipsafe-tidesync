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
  const [approvalToken, setApprovalToken] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [loadingConnections, setLoadingConnections] = useState(true);
  const [loadingFreshness, setLoadingFreshness] = useState(true);

  const fetchConnections = useCallback(async () => {
    setLoadingConnections(true);
    try {
      const res = await fetch(`${API}/connections`);
      setConnections(await res.json());
    } catch {}
    setLoadingConnections(false);
  }, []);

  const fetchFreshness = useCallback(async () => {
    setLoadingFreshness(true);
    try {
      const res = await fetch(`${API}/freshness`);
      setFreshnessReports(await res.json());
    } catch {}
    setLoadingFreshness(false);
  }, []);

  const fetchBriefing = useCallback(async () => {
    try {
      const res = await fetch(`${API}/briefing`);
      const data = await res.json();
      if (data.summary) setBriefing(data);
    } catch {}
  }, []);

  useEffect(() => {
    fetchConnections();
    fetchFreshness();
    fetchBriefing();
  }, [fetchConnections, fetchFreshness, fetchBriefing]);

  async function runAnalysis() {
    setRunning(true);
    try {
      const res = await fetch(`${API}/run`, { method: "POST" });
      const data = await res.json();
      if (data.contradiction) setContradiction(data.contradiction);
      if (data.briefing) setBriefing(data.briefing);
      if (data.approval_token) setApprovalToken(data.approval_token);
      await fetchFreshness();
      await fetchConnections();
    } catch {}
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
