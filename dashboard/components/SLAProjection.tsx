"use client";

interface SLABreach {
  breach_eta_minutes: number;
  confidence: "low" | "medium" | "high";
  trend: "stable" | "worsening" | "improving";
}

interface Props {
  breach: SLABreach | null;
  lagSeconds: number;
  thresholdSeconds: number;
}

const confidenceColor: Record<string, string> = {
  high: "text-danger",
  medium: "text-warning",
  low: "text-muted",
};

const trendIcon: Record<string, string> = {
  worsening: "↑",
  improving: "↓",
  stable: "→",
};

export function SLAProjection({ breach, lagSeconds, thresholdSeconds }: Props) {
  const pct = Math.min(100, (lagSeconds / thresholdSeconds) * 100);

  return (
    <div className="bg-bg-card border border-border p-5">
      <h2 className="text-xs font-mono text-muted uppercase tracking-wider mb-4">
        SLA Projection
      </h2>

      <div className="mb-4">
        <div className="flex justify-between text-xs font-mono text-muted mb-1">
          <span>0</span>
          <span>SLA threshold</span>
        </div>
        <div className="h-1.5 bg-bg-elevated relative overflow-hidden">
          <div
            className={`h-full transition-all ${pct > 100 ? "bg-danger" : pct > 75 ? "bg-warning" : "bg-success"}`}
            style={{ width: `${Math.min(pct, 100)}%` }}
          />
        </div>
        <p className="text-xs font-mono text-muted mt-1 text-right">{pct.toFixed(0)}% of SLA used</p>
      </div>

      {breach ? (
        <div>
          <p className={`text-lg font-mono font-medium ${confidenceColor[breach.confidence]}`}>
            ~{breach.breach_eta_minutes}m {trendIcon[breach.trend]}
          </p>
          <p className="text-xs text-muted font-mono mt-1">
            to SLA breach · {breach.confidence} confidence · {breach.trend}
          </p>
        </div>
      ) : (
        <p className="text-sm font-mono text-success">Within SLA</p>
      )}
    </div>
  );
}
