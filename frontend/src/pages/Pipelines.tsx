import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, type PipelineRun } from "../api";
import { ACTIVE, useRuns } from "../hooks";

function Param(props: { label: string; value: number; onChange: (n: number) => void; step?: number }) {
  return (
    <label className="field">
      <span>{props.label}</span>
      <div className="inputwrap">
        <input
          type="number"
          step={props.step ?? 1}
          value={props.value}
          onChange={(e) => props.onChange(Number(e.target.value))}
        />
      </div>
    </label>
  );
}

function RunStatus({ run }: { run: PipelineRun | undefined }) {
  if (!run) return <p className="muted">Never run.</p>;
  return (
    <div>
      <p>
        <span className={`badge ${run.status}`}>{run.status}</span> run #{run.id} &middot;{" "}
        {new Date(run.started_at).toLocaleString()}
      </p>
      {ACTIVE.includes(run.status) && (
        <progress value={run.progress} max={1} aria-label="Pipeline progress" />
      )}
      {run.message && <p className="muted">{run.message}</p>}
      {run.error && <p className="error">{run.error}</p>}
    </div>
  );
}

export default function Pipelines() {
  const qc = useQueryClient();
  const runs = useRuns();
  const universe = useQuery({ queryKey: ["universe"], queryFn: api.universe });

  const anyActive = runs.data?.some((r) => ACTIVE.includes(r.status)) ?? false;
  const latest = (name: string) => runs.data?.find((r) => r.pipeline === name);

  const [uni, setUni] = useState({ top_n: 250, min_avg_option_volume: 10000, volume_lookback_days: 20, market_cap_max_age_days: 7 });
  const [opt, setOpt] = useState({ min_dte: 14, max_dte: 120, strike_window_pct: 5 });

  const start = useMutation({
    mutationFn: ({ name, params }: { name: "universe" | "options"; params: Record<string, number> }) =>
      api.runPipeline(name, params),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["runs"] });
    },
  });

  return (
    <>
      <h1>Data Pipelines</h1>
      <p className="muted">
        Run these in order: the universe pipeline picks tickers, the options pipeline pulls their option
        data. Only one pipeline can run at a time.
      </p>
      {start.error && <p className="error">{(start.error as Error).message}</p>}

      <div className="grid2">
        <section className="card">
          <h2>1. Stock universe</h2>
          <p className="muted">
            S&amp;P 500 + Nasdaq-100 &rarr; market cap (Finnhub, about 1 call/sec, so the first run takes
            several minutes) &rarr; top N &rarr; average option volume (Alpaca).
          </p>
          <div className="controls">
            <Param label="Top N by market cap" value={uni.top_n} onChange={(v) => setUni({ ...uni, top_n: v })} />
            <Param label="Min avg option volume / day" value={uni.min_avg_option_volume} step={500} onChange={(v) => setUni({ ...uni, min_avg_option_volume: v })} />
            <Param label="Volume lookback (days)" value={uni.volume_lookback_days} onChange={(v) => setUni({ ...uni, volume_lookback_days: v })} />
            <Param label="Reuse market caps newer than (days)" value={uni.market_cap_max_age_days} onChange={(v) => setUni({ ...uni, market_cap_max_age_days: v })} />
          </div>
          <button disabled={anyActive || start.isPending} onClick={() => start.mutate({ name: "universe", params: uni })}>
            Run universe pipeline
          </button>
          <RunStatus run={latest("universe")} />
        </section>

        <section className="card">
          <h2>2. Option data</h2>
          <p className="muted">
            For each selected ticker: call quotes and vendor IV within the strike and DTE window, plus the
            next earnings date.
          </p>
          <div className="controls">
            <Param label="Min DTE" value={opt.min_dte} onChange={(v) => setOpt({ ...opt, min_dte: v })} />
            <Param label="Max DTE" value={opt.max_dte} onChange={(v) => setOpt({ ...opt, max_dte: v })} />
            <Param label="Strike window (± % of spot)" value={opt.strike_window_pct} step={0.5} onChange={(v) => setOpt({ ...opt, strike_window_pct: v })} />
          </div>
          <button disabled={anyActive || start.isPending} onClick={() => start.mutate({ name: "options", params: opt })}>
            Run options pipeline
          </button>
          <RunStatus run={latest("options")} />
        </section>
      </div>

      <section className="card">
        <h2>Run history</h2>
        <div className="tablewrap">
          <table>
            <thead>
              <tr><th>#</th><th>Pipeline</th><th>Status</th><th>Started</th><th>Finished</th><th>Result</th></tr>
            </thead>
            <tbody>
              {runs.data?.map((r) => (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td>{r.pipeline}</td>
                  <td><span className={`badge ${r.status}`}>{r.status}</span></td>
                  <td>{new Date(r.started_at).toLocaleString()}</td>
                  <td>{r.finished_at ? new Date(r.finished_at).toLocaleString() : ""}</td>
                  <td>{r.error ?? r.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card">
        <h2>Current universe ({universe.data?.length ?? 0} tickers)</h2>
        <div className="tablewrap short">
          <table>
            <thead>
              <tr><th>Ticker</th><th>Name</th><th>Market cap ($B)</th><th>Avg option vol/day</th><th>Index</th></tr>
            </thead>
            <tbody>
              {universe.data?.map((t) => (
                <tr key={t.symbol}>
                  <td><strong>{t.symbol}</strong></td>
                  <td>{t.name}</td>
                  <td>{t.market_cap ? (t.market_cap / 1e9).toFixed(1) : ""}</td>
                  <td>{t.avg_option_volume ? Math.round(t.avg_option_volume).toLocaleString() : ""}</td>
                  <td>{[t.in_sp500 && "S&P 500", t.in_nasdaq100 && "NDX"].filter(Boolean).join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
