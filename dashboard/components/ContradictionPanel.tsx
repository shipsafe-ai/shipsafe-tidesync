"use client";

interface SLABreach {
  breach_eta_minutes: number;
  confidence: "low" | "medium" | "high";
  trend: "stable" | "worsening" | "improving";
}

interface ContradictionData {
  is_stale: boolean;
  lag_display: string;
  lag_seconds: number;
  sla_breach_eta: SLABreach | null;
  recommendation: string;
  cost_rec: string | null;
}

interface FivetranData {
  succeeded_at: string | null;
  row_count: number;
  status: string;
}

interface Props {
  contradiction: ContradictionData | null;
  fivetran: FivetranData | null;
  bqMaxSynced: string | null;
  approvalToken: string | null;
  onApprove: (token: string) => void;
}

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
}

export function ContradictionPanel({ contradiction, fivetran, bqMaxSynced, approvalToken, onApprove }: Props) {
  if (!contradiction) {
    return (
      <div className="bg-bg-card border border-border p-6">
        <p className="text-muted text-sm font-mono">No analysis yet. Run TideSync to detect contradictions.</p>
      </div>
    );
  }

  const isStale = contradiction.is_stale;

  return (
    <div className={`border p-6 ${isStale ? "border-danger bg-danger/5" : "border-success bg-success/5"}`}>
      <div className="flex items-center gap-2 mb-6">
        <span className={`w-2 h-2 rounded-full ${isStale ? "bg-danger" : "bg-success"}`} />
        <span className="font-semibold text-sm tracking-wide">
          {isStale ? "CONTRADICTION DETECTED" : "PIPELINE HEALTHY"}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-8 mb-6">
        <div>
          <p className="text-xs text-muted font-mono mb-2 uppercase tracking-wider">Fivetran MCP</p>
          <p className="text-sm text-zinc-300">
            sync succeeded{" "}
            <span className="font-mono text-zinc-100">{formatTime(fivetran?.succeeded_at ?? null)}</span>
          </p>
          <p className="text-sm text-zinc-300 mt-1">
            <span className="font-mono text-zinc-100">
              {fivetran?.row_count?.toLocaleString() ?? "—"}
            </span>{" "}
            rows
          </p>
          <p className={`text-xs font-mono mt-2 ${fivetran?.status === "connected" ? "text-success" : "text-danger"}`}>
            {fivetran?.status ?? "unknown"}
          </p>
        </div>

        <div>
          <p className="text-xs text-muted font-mono mb-2 uppercase tracking-wider">BigQuery Truth</p>
          <p className="text-sm text-zinc-300">
            MAX(_fivetran_synced){" "}
            <span className="font-mono text-zinc-100">{formatTime(bqMaxSynced)}</span>
          </p>
          <p className={`text-sm font-mono mt-1 ${isStale ? "text-danger" : "text-success"}`}>
            lag = {contradiction.lag_display}
          </p>
          {isStale && (
            <p className="text-xs text-warning font-mono mt-2">
              ⚠ stale
            </p>
          )}
        </div>
      </div>

      {isStale && (
        <div className="border-t border-border pt-4 mb-4">
          <p className="text-xs text-muted font-mono mb-1">Gemini Analysis</p>
          <p className="text-sm text-zinc-200">{contradiction.recommendation}</p>
          {contradiction.sla_breach_eta && (
            <p className="text-xs font-mono text-warning mt-2">
              SLA breach in ~{contradiction.sla_breach_eta.breach_eta_minutes}m
              · {contradiction.sla_breach_eta.trend}
              · confidence: {contradiction.sla_breach_eta.confidence}
            </p>
          )}
          {contradiction.cost_rec && (
            <p className="text-xs text-muted mt-2">{contradiction.cost_rec}</p>
          )}
        </div>
      )}

      {approvalToken && (
        <div className="flex gap-3 mt-4">
          <button
            onClick={() => onApprove(approvalToken)}
            className="px-4 py-2 bg-accent text-white text-xs font-mono hover:bg-violet-500 transition-colors"
          >
            Approve Resync
          </button>
          <span className="text-xs text-muted font-mono self-center">
            Human approval required before sync
          </span>
        </div>
      )}
    </div>
  );
}
