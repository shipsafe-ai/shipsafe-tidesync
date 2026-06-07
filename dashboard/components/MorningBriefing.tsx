"use client";

interface Anomaly {
  connection: string;
  lag_display: string;
  severity?: string;
}

interface Briefing {
  summary: string;
  connections_ok: number;
  anomalies: Anomaly[];
  actions_taken: string[];
  generated_at?: string;
}

interface Props {
  briefing: Briefing | null;
  loading: boolean;
}

export function MorningBriefing({ briefing, loading }: Props) {
  return (
    <div className="bg-bg-card border border-border p-5">
      <h2 className="text-xs font-mono text-muted uppercase tracking-wider mb-4">
        Morning Briefing
      </h2>
      {loading ? (
        <p className="text-muted text-xs font-mono">Generating briefing...</p>
      ) : !briefing || !briefing.summary ? (
        <p className="text-muted text-xs font-mono">No briefing yet.</p>
      ) : (
        <>
          <p className="text-sm text-zinc-200 mb-4">{briefing.summary}</p>

          <div className="flex gap-6 mb-4">
            <div>
              <p className="text-xs text-muted font-mono">Connections OK</p>
              <p className="text-xl font-mono font-medium text-success">{briefing.connections_ok}</p>
            </div>
            <div>
              <p className="text-xs text-muted font-mono">Anomalies</p>
              <p className={`text-xl font-mono font-medium ${briefing.anomalies.length > 0 ? "text-danger" : "text-success"}`}>
                {briefing.anomalies.length}
              </p>
            </div>
          </div>

          {briefing.anomalies.length > 0 && (
            <div className="mb-3">
              <p className="text-xs text-muted font-mono mb-2">Anomalies</p>
              {briefing.anomalies.map((a, i) => (
                <div key={i} className="flex justify-between py-1 border-b border-border last:border-0">
                  <span className="text-xs font-mono text-zinc-300">{a.connection}</span>
                  <span className="text-xs font-mono text-danger">{a.lag_display}</span>
                </div>
              ))}
            </div>
          )}

          {briefing.actions_taken.length > 0 && (
            <div>
              <p className="text-xs text-muted font-mono mb-2">Actions Taken</p>
              {briefing.actions_taken.map((a, i) => (
                <p key={i} className="text-xs font-mono text-zinc-400">· {a}</p>
              ))}
            </div>
          )}

          {briefing.generated_at && (
            <p className="text-xs text-muted font-mono mt-3">
              Generated {new Date(briefing.generated_at).toLocaleTimeString()}
            </p>
          )}
        </>
      )}
    </div>
  );
}
