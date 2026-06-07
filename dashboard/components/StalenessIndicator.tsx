"use client";

interface TableReport {
  table: string;
  max_synced_at: string | null;
  row_count: number;
  lag_seconds: number;
  null_rates: Record<string, number>;
}

interface Props {
  reports: TableReport[];
  threshold: number;
  loading: boolean;
}

function lagColor(lag: number, threshold: number): string {
  if (lag > threshold * 2) return "text-danger";
  if (lag > threshold) return "text-warning";
  return "text-success";
}

function formatLag(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export function StalenessIndicator({ reports, threshold, loading }: Props) {
  return (
    <div className="bg-bg-card border border-border p-5">
      <h2 className="text-xs font-mono text-muted uppercase tracking-wider mb-4">
        BigQuery Freshness
      </h2>
      {loading ? (
        <p className="text-muted text-xs font-mono">Querying BigQuery...</p>
      ) : reports.length === 0 ? (
        <p className="text-muted text-xs font-mono">No tables found.</p>
      ) : (
        <div className="space-y-4">
          {reports.map((r) => (
            <div key={r.table} className="border border-border p-3">
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-mono text-zinc-200">{r.table}</p>
                <span className={`text-sm font-mono font-medium ${lagColor(r.lag_seconds, threshold)}`}>
                  {formatLag(r.lag_seconds)}
                </span>
              </div>
              <div className="flex gap-4 text-xs font-mono text-muted">
                <span>{r.row_count.toLocaleString()} rows</span>
                {r.max_synced_at && (
                  <span>
                    last: {new Date(r.max_synced_at).toLocaleTimeString()}
                  </span>
                )}
              </div>
              {Object.entries(r.null_rates).some(([, rate]) => rate > 0.1) && (
                <div className="mt-2">
                  <p className="text-xs text-warning font-mono">null drift:</p>
                  {Object.entries(r.null_rates)
                    .filter(([, rate]) => rate > 0.1)
                    .map(([col, rate]) => (
                      <p key={col} className="text-xs font-mono text-muted">
                        {col}: {(rate * 100).toFixed(1)}%
                      </p>
                    ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
