import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Signal, type SignalFilters } from "../api";
import { ACTIVE, useRuns } from "../hooks";

type SortKey = keyof Signal;

const OPTIONS_DEFAULTS = { min_dte: 14, max_dte: 120, strike_window_pct: 5 };

/** Run button + live status for the options pipeline. Reuses the last options run's settings. */
function OptionsRunBar() {
  const qc = useQueryClient();
  const runs = useRuns();
  const active = runs.data?.find((r) => ACTIVE.includes(r.status));
  const lastOptions = runs.data?.find((r) => r.pipeline === "options");
  const params = { ...OPTIONS_DEFAULTS, ...(lastOptions?.params ?? {}) };

  const start = useMutation({
    mutationFn: () => api.runPipeline("options", params),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });

  return (
    <section className="card runbar">
      <button disabled={!!active || start.isPending} onClick={() => start.mutate()}>
        {active?.pipeline === "options" ? "Running…" : "Run options pipeline"}
      </button>
      <div className="runstatus">
        {active ? (
          <>
            <span>
              {active.pipeline === "options" ? "Options" : "Universe"} pipeline {active.status}
              {active.message ? ` · ${active.message}` : ""}
            </span>
            <progress value={active.progress} max={1} aria-label="Pipeline progress" />
          </>
        ) : lastOptions ? (
          <span className={lastOptions.status === "failed" ? "error" : "muted"}>
            Last run #{lastOptions.id} {lastOptions.status}
            {lastOptions.finished_at ? ` at ${new Date(lastOptions.finished_at).toLocaleString()}` : ""}
            {lastOptions.error ?? (lastOptions.message ? ` · ${lastOptions.message}` : "")}
          </span>
        ) : (
          <span className="muted">No options run yet.</span>
        )}
        {start.error && <span className="error">{(start.error as Error).message}</span>}
      </div>
      <span className="muted small">
        DTE {params.min_dte}&ndash;{params.max_dte}, strikes &plusmn;{params.strike_window_pct}% of spot.{" "}
        <Link to="/pipelines">Change settings</Link>
      </span>
    </section>
  );
}

const DEFAULTS: SignalFilters = {
  min_ff_pct: 20,
  min_front_dte: 14,
  min_gap: 14,
  max_back_dte: 120,
  max_spread_pct: 10,
  exclude_earnings: false,
};

function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function NumberField(props: {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
  step?: number;
  suffix?: string;
  allowEmpty?: boolean;
}) {
  return (
    <label className="field">
      <span>{props.label}</span>
      <div className="inputwrap">
        <input
          type="number"
          step={props.step ?? 1}
          value={props.value ?? ""}
          onChange={(e) => {
            const raw = e.target.value;
            if (raw === "") return props.onChange(props.allowEmpty ? null : 0);
            props.onChange(Number(raw));
          }}
        />
        {props.suffix && <em>{props.suffix}</em>}
      </div>
    </label>
  );
}

const fmt = (n: number, d = 2) => n.toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });

export default function Screener() {
  const [filters, setFilters] = useState<SignalFilters>(DEFAULTS);
  const applied = useDebounced(filters);
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "ff_pct", dir: -1 });

  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ["signals", applied],
    queryFn: () => api.signals(applied),
  });

  const rows = useMemo(() => {
    const list = [...(data?.signals ?? [])];
    list.sort((a, b) => {
      const x = a[sort.key] ?? -Infinity;
      const y = b[sort.key] ?? -Infinity;
      return (x < y ? -1 : x > y ? 1 : 0) * sort.dir;
    });
    return list;
  }, [data, sort]);

  const set = <K extends keyof SignalFilters>(k: K, v: SignalFilters[K]) =>
    setFilters((f) => ({ ...f, [k]: v }));

  const head = (key: SortKey, label: string) => (
    <th onClick={() => setSort((s) => ({ key, dir: s.key === key ? (-s.dir as 1 | -1) : -1 }))}>
      {label}
      {sort.key === key ? (sort.dir === -1 ? " ▾" : " ▴") : ""}
    </th>
  );

  return (
    <>
      <h1>Forward Factor Screener</h1>
      <p className="muted">
        Call calendar spreads. FF = (front IV &minus; forward vol) / forward vol, using Alpaca&apos;s
        implied vol. Higher FF means the front month is rich relative to the back.
      </p>

      <OptionsRunBar />

      <section className="card controls">
        <NumberField label="Min FF" suffix="%" value={filters.min_ff_pct} onChange={(v) => set("min_ff_pct", v ?? 0)} />
        <NumberField label="Min front DTE" suffix="days" value={filters.min_front_dte} onChange={(v) => set("min_front_dte", v ?? 1)} />
        <NumberField label="Min DTE gap" suffix="days" value={filters.min_gap} onChange={(v) => set("min_gap", v ?? 1)} />
        <NumberField label="Max back DTE" suffix="days" value={filters.max_back_dte} onChange={(v) => set("max_back_dte", v ?? 1)} />
        <NumberField label="Max spread" suffix="% of debit" allowEmpty value={filters.max_spread_pct} onChange={(v) => set("max_spread_pct", v)} />
        <label className="field check">
          <input
            type="checkbox"
            checked={filters.exclude_earnings}
            onChange={(e) => set("exclude_earnings", e.target.checked)}
          />
          <span>Hide earnings before back expiry</span>
        </label>
      </section>

      {error && <p className="error">Could not load signals: {(error as Error).message}</p>}
      {isLoading && <p className="muted">Loading&hellip;</p>}

      {data && data.run_id === null && (
        <p className="card">
          No option data yet. Go to <Link to="/pipelines">Data Pipelines</Link> and run the universe
          pipeline, then the options pipeline.
        </p>
      )}

      {data && data.run_id !== null && (
        <>
          <p className="muted">
            {rows.length} of {data.total_pairs.toLocaleString()} calendar pairs shown &middot; data from run #
            {data.run_id}, {data.as_of ? new Date(data.as_of).toLocaleString() : ""}
            {isFetching ? " · updating…" : ""}
          </p>
          <div className="tablewrap">
            <table>
              <thead>
                <tr>
                  {head("underlying", "Ticker")}
                  {head("spot", "Spot")}
                  {head("strike", "Strike")}
                  {head("front_expiration", "Front exp")}
                  {head("front_dte", "Front DTE")}
                  {head("back_expiration", "Back exp")}
                  {head("back_dte", "Back DTE")}
                  {head("dte_gap", "DTE gap")}
                  {head("front_iv", "Front IV")}
                  {head("back_iv", "Back IV")}
                  {head("forward_vol_pct", "Fwd vol")}
                  {head("ff_pct", "FF")}
                  {head("debit", "Debit")}
                  {head("spread_pct", "Spread")}
                  {head("days_to_earnings", "Earnings")}
                </tr>
              </thead>
              <tbody>
                {rows.map((s) => (
                  <tr key={`${s.underlying}-${s.front_expiration}-${s.back_expiration}`}>
                    <td><strong>{s.underlying}</strong></td>
                    <td>{fmt(s.spot)}</td>
                    <td>{fmt(s.strike)}</td>
                    <td>{s.front_expiration}</td>
                    <td>{s.front_dte}</td>
                    <td>{s.back_expiration}</td>
                    <td>{s.back_dte}</td>
                    <td><strong>{s.dte_gap}d</strong></td>
                    <td>{fmt(s.front_iv * 100, 1)}%</td>
                    <td>{fmt(s.back_iv * 100, 1)}%</td>
                    <td>{fmt(s.forward_vol_pct, 1)}%</td>
                    <td className="ff">{fmt(s.ff_pct, 1)}%</td>
                    <td>${fmt(s.debit)}</td>
                    <td>{fmt(s.spread_pct, 1)}%</td>
                    <td>
                      {s.earnings_date ? (
                        <span className={s.earnings_before_front ? "badge bad" : s.earnings_before_back ? "badge warn" : "muted"}>
                          {s.earnings_date} ({s.days_to_earnings}d)
                          {s.earnings_before_front ? " · before front" : s.earnings_before_back ? " · before back" : ""}
                        </span>
                      ) : (
                        <span className="muted">&mdash;</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <p className="muted pad">No pairs match these filters.</p>}
          </div>
        </>
      )}
    </>
  );
}
