export interface Signal {
  underlying: string;
  spot: number;
  strike: number;
  front_expiration: string;
  back_expiration: string;
  front_dte: number;
  back_dte: number;
  dte_gap: number;
  front_iv: number;
  back_iv: number;
  forward_vol_pct: number;
  ff_pct: number;
  debit: number;
  spread_pct: number;
  earnings_date: string | null;
  days_to_earnings: number | null;
  earnings_before_front: boolean;
  earnings_before_back: boolean;
}

export interface SignalsResponse {
  run_id: number | null;
  as_of: string | null;
  total_pairs: number;
  signals: Signal[];
}

export interface SignalFilters {
  min_ff_pct: number;
  min_front_dte: number;
  min_gap: number;
  max_back_dte: number;
  max_spread_pct: number | null;
  exclude_earnings: boolean;
}

export interface PipelineRun {
  id: number;
  pipeline: "universe" | "options";
  status: "queued" | "running" | "succeeded" | "failed";
  params: Record<string, number>;
  progress: number;
  message: string | null;
  error: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface Ticker {
  symbol: string;
  name: string | null;
  market_cap: number | null;
  avg_option_volume: number | null;
  in_sp500: boolean;
  in_nasdaq100: boolean;
  selected: boolean;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

export const api = {
  signals(f: SignalFilters) {
    const q = new URLSearchParams({
      min_ff_pct: String(f.min_ff_pct),
      min_front_dte: String(f.min_front_dte),
      min_gap: String(f.min_gap),
      max_back_dte: String(f.max_back_dte),
      exclude_earnings: String(f.exclude_earnings),
    });
    if (f.max_spread_pct !== null) q.set("max_spread_pct", String(f.max_spread_pct));
    return request<SignalsResponse>(`/api/signals?${q}`);
  },
  runs: () => request<PipelineRun[]>("/api/pipelines/runs"),
  universe: () => request<Ticker[]>("/api/universe?selected_only=true"),
  runPipeline: (name: "universe" | "options", params: Record<string, number>) =>
    request<PipelineRun>(`/api/pipelines/${name}/run`, {
      method: "POST",
      body: JSON.stringify(params),
    }),
};
