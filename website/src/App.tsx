import { useEffect, useMemo, useState } from "react";

import { ResultsChart } from "./components/ResultsChart";
import { StatusFilters } from "./components/StatusFilters";
import { StatusTable } from "./components/StatusTable";
import { SummaryStats } from "./components/SummaryStats";
import {
  EMPTY_FILTERS,
  filterBets,
  filterOptions,
  filtersWithDateRange,
  groupClosedBetsBySettlement,
  summarizeBets,
  type StatusBet,
  type StatusFilters as StatusFiltersState,
  type StatusPayload,
} from "./lib/statusData";

const DATA_URL = "/api/status";
type LoadState = "loading" | "ready" | "missing";

export function App() {
  const [bets, setBets] = useState<StatusBet[]>([]);
  const [generatedAt, setGeneratedAt] = useState("");
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [loadError, setLoadError] = useState("");
  const [filters, setFilters] = useState<StatusFiltersState>(EMPTY_FILTERS);

  useEffect(() => {
    fetch(DATA_URL, { cache: "no-store" })
      .then((response) => {
        const contentType = response.headers.get("content-type") || "";
        if (!contentType.includes("application/json")) {
          throw new Error(
            "Status API returned HTML instead of JSON. Run with `npx vercel dev` from the repo root, or deploy Vercel from the repo root so `/api/status` is served.",
          );
        }
        if (!response.ok) {
          return response
            .json()
            .catch(() => ({}))
            .then((payload) => {
              throw new Error(String(payload.error || `Unable to load ${DATA_URL}`));
            });
        }
        return response.json() as Promise<StatusPayload>;
      })
      .then((payload) => {
        setBets(Array.isArray(payload.bets) ? payload.bets : []);
        setGeneratedAt(payload.generatedAt || "");
        setLoadError("");
        setLoadState("ready");
      })
      .catch((error: unknown) => {
        setBets([]);
        setGeneratedAt("");
        setLoadError(error instanceof Error ? error.message : "Unable to load status data");
        setLoadState("missing");
      });
  }, []);

  const options = useMemo(() => filterOptions(bets), [bets]);
  useEffect(() => {
    if (!options.minDate || !options.maxDate) {
      return;
    }
    setFilters((currentFilters) => filtersWithDateRange(currentFilters, options));
  }, [options]);

  const filteredBets = useMemo(() => filterBets(bets, filters), [bets, filters]);
  const closedBets = useMemo(
    () => filteredBets.filter((bet) => bet.status === "won" || bet.status === "lost"),
    [filteredBets],
  );
  const chartRows = useMemo(() => groupClosedBetsBySettlement(closedBets), [closedBets]);
  const summary = useMemo(() => summarizeBets(filteredBets), [filteredBets]);

  return (
    <main className="dashboard-shell">
      <header className="dashboard-header">
        {loadState !== "ready" ? (
          <span className="data-state" data-state={loadState}>
            {loadState === "loading"
              ? "Loading status data..."
              : loadError || "Unable to load status data"}
          </span>
        ) : null}
      </header>

      <SummaryStats summary={summary} />

      <section className="panel chart-panel" aria-label="Closed bet result graph">
        <ResultsChart rows={chartRows} />
      </section>

      <StatusFilters
        filters={filters}
        options={options}
        visibleCount={filteredBets.length}
        totalCount={bets.length}
        onChange={setFilters}
      />

      <section className="panel table-panel" aria-label="Trade status table">
        <StatusTable bets={filteredBets} totalRows={bets.length} generatedAt={generatedAt} />
      </section>
    </main>
  );
}
