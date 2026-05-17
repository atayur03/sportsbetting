import { useEffect, useMemo, useState } from "react";

import { ResultsChart } from "./components/ResultsChart";
import { StatusFilters } from "./components/StatusFilters";
import { StatusTable } from "./components/StatusTable";
import { SummaryStats } from "./components/SummaryStats";
import {
  EMPTY_FILTERS,
  filterBets,
  filterOptions,
  groupClosedBetsByDate,
  summarizeBets,
  type StatusBet,
  type StatusFilters as StatusFiltersState,
  type StatusPayload,
} from "./lib/statusData";

const DATA_URL = "/data/trade-status.json";
type LoadState = "loading" | "ready" | "missing";

export function App() {
  const [bets, setBets] = useState<StatusBet[]>([]);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [filters, setFilters] = useState<StatusFiltersState>(EMPTY_FILTERS);

  useEffect(() => {
    fetch(DATA_URL, { cache: "no-store" })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Missing ${DATA_URL}`);
        }
        return response.json() as Promise<StatusPayload>;
      })
      .then((payload) => {
        setBets(Array.isArray(payload.bets) ? payload.bets : []);
        setLoadState("ready");
      })
      .catch(() => {
        setBets([]);
        setLoadState("missing");
      });
  }, []);

  const options = useMemo(() => filterOptions(bets), [bets]);
  const filteredBets = useMemo(() => filterBets(bets, filters), [bets, filters]);
  const closedBets = useMemo(
    () => filteredBets.filter((bet) => bet.status === "won" || bet.status === "lost"),
    [filteredBets],
  );
  const chartRows = useMemo(() => groupClosedBetsByDate(closedBets), [closedBets]);
  const summary = useMemo(() => summarizeBets(filteredBets), [filteredBets]);

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">Execution status</p>
          <h1>Trade Results</h1>
        </div>
      </header>

      <StatusFilters
        filters={filters}
        options={options}
        visibleCount={filteredBets.length}
        totalCount={bets.length}
        onChange={setFilters}
      />

      <SummaryStats summary={summary} />

      <section className="panel chart-panel" aria-label="Closed bet result graph">
        <div className="panel-heading">
          <div>
            <h2>Performance</h2>
            <p>Total and strategy-level cumulative result by game date.</p>
          </div>
        </div>
        <ResultsChart rows={chartRows} />
      </section>

      <section className="panel table-panel" aria-label="Trade status table">
        <div className="panel-heading">
          <div>
            <h2>Status Table</h2>
            <p>Sanitized fields only. Tickers, order IDs, client IDs, and rule text are excluded.</p>
          </div>
        </div>
        <StatusTable bets={filteredBets} />
      </section>
    </main>
  );
}
