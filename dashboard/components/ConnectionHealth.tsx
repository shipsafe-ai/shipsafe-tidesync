"use client";

interface Connection {
  connection_id: string;
  status: string;
  succeeded_at: string | null;
  failed_at: string | null;
  sync_frequency: number | null;
  service: string;
  paused: boolean;
}

interface Props {
  connections: Connection[];
  loading: boolean;
}

function statusColor(status: string, paused: boolean): string {
  if (paused) return "text-warning";
  if (status === "connected") return "text-success";
  if (status === "broken") return "text-danger";
  return "text-muted";
}

function statusDot(status: string, paused: boolean): string {
  if (paused) return "bg-warning";
  if (status === "connected") return "bg-success";
  if (status === "broken") return "bg-danger";
  return "bg-muted";
}

export function ConnectionHealth({ connections, loading }: Props) {
  return (
    <div className="bg-bg-card border border-border p-5">
      <h2 className="text-xs font-mono text-muted uppercase tracking-wider mb-4">
        Connector Health
      </h2>
      {loading ? (
        <p className="text-muted text-xs font-mono">Loading...</p>
      ) : connections.length === 0 ? (
        <p className="text-muted text-xs font-mono">No connections found.</p>
      ) : (
        <div className="space-y-3">
          {connections.map((conn) => (
            <div key={conn.connection_id} className="flex items-center justify-between py-2 border-b border-border last:border-0">
              <div className="flex items-center gap-2">
                <span className={`w-1.5 h-1.5 rounded-full ${statusDot(conn.status, conn.paused)}`} />
                <div>
                  <p className="text-xs font-mono text-zinc-200">{conn.connection_id}</p>
                  <p className="text-xs text-muted">{conn.service}</p>
                </div>
              </div>
              <div className="text-right">
                <p className={`text-xs font-mono ${statusColor(conn.status, conn.paused)}`}>
                  {conn.paused ? "paused" : conn.status}
                </p>
                {conn.sync_frequency && (
                  <p className="text-xs text-muted font-mono">every {conn.sync_frequency}m</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
