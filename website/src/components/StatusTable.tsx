import { useEffect, useMemo, useState } from "react";

import {
  formatDate,
  formatDateTime,
  formatEngine,
  formatStatus,
  formatStrategy,
  money,
  simulationLabel,
  type StatusBet,
} from "../lib/statusData";

type StatusTableProps = {
  bets: StatusBet[];
  totalRows: number;
  generatedAt: string;
};

type SortDirection = "asc" | "desc";
type SortKey =
  | "gameDate"
  | "status"
  | "orderLifecycleStatus"
  | "fillStatus"
  | "positionStatus"
  | "strategy"
  | "engine"
  | "simulated"
  | "sport"
  | "side"
  | "contracts"
  | "stakeDollars"
  | "priceDollars"
  | "pnlDollars"
  | "marketTitle"
  | "marketResult";

type Column = {
  key: SortKey;
  label: string;
  numeric?: boolean;
  defaultWidth: number;
  render: (bet: StatusBet) => string | number;
};

const PAGE_SIZES = [10, 25, 50, 100];

const COLUMNS: Column[] = [
  { key: "simulated", label: "Mode", defaultWidth: 124, render: (bet) => formatEngine(simulationLabel(bet.simulated)) },
  { key: "gameDate", label: "Game date", defaultWidth: 132, render: (bet) => formatDate(bet.gameDate) },
  { key: "status", label: "Status", defaultWidth: 142, render: (bet) => formatStatus(bet.status) },
  { key: "orderLifecycleStatus", label: "Order", defaultWidth: 142, render: (bet) => formatStatus(bet.orderLifecycleStatus) },
  { key: "fillStatus", label: "Fill", defaultWidth: 118, render: (bet) => formatStatus(bet.fillStatus) },
  { key: "positionStatus", label: "Position", defaultWidth: 126, render: (bet) => formatStatus(bet.positionStatus) },
  { key: "strategy", label: "Strategy", defaultWidth: 180, render: (bet) => formatStrategy(bet.strategy) },
  { key: "engine", label: "Engine", defaultWidth: 112, render: (bet) => formatEngine(bet.engine) },
  { key: "sport", label: "Sport", defaultWidth: 92, render: (bet) => bet.sport },
  { key: "contracts", label: "Contracts", numeric: true, defaultWidth: 112, render: (bet) => bet.contracts },
  { key: "stakeDollars", label: "Stake", numeric: true, defaultWidth: 112, render: (bet) => money(bet.stakeDollars) },
  { key: "priceDollars", label: "Price", numeric: true, defaultWidth: 108, render: (bet) => money(bet.priceDollars) },
  {
    key: "pnlDollars",
    label: "P&L",
    numeric: true,
    defaultWidth: 108,
    render: (bet) => money(bet.pnlDollars),
  },
  { key: "side", label: "Side", defaultWidth: 104, render: (bet) => bet.side },
  { key: "marketTitle", label: "Market", defaultWidth: 320, render: (bet) => bet.marketTitle },
  { key: "marketResult", label: "Result", defaultWidth: 132, render: (bet) => bet.marketResult },
];

const DEFAULT_VISIBLE_COLUMNS = COLUMNS.map((column) => column.key).filter(
  (key) => key !== "simulated" && key !== "orderLifecycleStatus" && key !== "positionStatus",
);

function sortValue(bet: StatusBet, key: SortKey): string | number {
  const value = bet[key];
  if (typeof value === "number") {
    return value;
  }
  return String(value || "").toLowerCase();
}

function compareBets(a: StatusBet, b: StatusBet, key: SortKey, direction: SortDirection): number {
  const aValue = sortValue(a, key);
  const bValue = sortValue(b, key);
  const directionMultiplier = direction === "asc" ? 1 : -1;

  if (typeof aValue === "number" && typeof bValue === "number") {
    return (aValue - bValue) * directionMultiplier;
  }
  return String(aValue).localeCompare(String(bValue)) * directionMultiplier;
}

function nextDirection(currentKey: SortKey, nextKey: SortKey, currentDirection: SortDirection): SortDirection {
  if (currentKey !== nextKey) {
    return "asc";
  }
  return currentDirection === "asc" ? "desc" : "asc";
}

function defaultColumnWidths(): Record<SortKey, number> {
  return Object.fromEntries(COLUMNS.map((column) => [column.key, column.defaultWidth])) as Record<SortKey, number>;
}

export function StatusTable({ bets, totalRows, generatedAt }: StatusTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("gameDate");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [pageSize, setPageSize] = useState(25);
  const [page, setPage] = useState(1);
  const [visibleColumns, setVisibleColumns] = useState<SortKey[]>(DEFAULT_VISIBLE_COLUMNS);
  const [columnWidths, setColumnWidths] = useState<Record<SortKey, number>>(defaultColumnWidths);

  const sortedBets = useMemo(
    () => [...bets].sort((a, b) => compareBets(a, b, sortKey, sortDirection)),
    [bets, sortDirection, sortKey],
  );
  const pageCount = Math.max(1, Math.ceil(sortedBets.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const pageStart = (safePage - 1) * pageSize;
  const pageRows = sortedBets.slice(pageStart, pageStart + pageSize);
  const selectedColumns = COLUMNS.filter((column) => visibleColumns.includes(column.key));
  const tableWidth = selectedColumns.reduce((total, column) => total + columnWidths[column.key], 0);
  const lastUpdatedLabel = generatedAt ? formatDateTime(generatedAt) : "No export found";

  useEffect(() => {
    setPage(1);
  }, [bets.length, pageSize]);

  function toggleColumn(key: SortKey): void {
    setVisibleColumns((currentColumns) => {
      if (currentColumns.includes(key)) {
        if (currentColumns.length === 1) {
          return currentColumns;
        }
        return currentColumns.filter((columnKey) => columnKey !== key);
      }
      return [...currentColumns, key];
    });
  }

  function startColumnResize(key: SortKey, clientX: number): void {
    const startWidth = columnWidths[key];
    const onMove = (event: MouseEvent) => {
      const nextWidth = Math.max(72, startWidth + event.clientX - clientX);
      setColumnWidths((currentWidths) => ({ ...currentWidths, [key]: nextWidth }));
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }

  if (!bets.length) {
    return (
      <>
        <div className="panel-heading">
          <div>
            <h2>Positions</h2>
            <p>Last updated: {lastUpdatedLabel}</p>
          </div>
        </div>
        <div className="empty-state">
          {totalRows
            ? "No rows match the current filters."
            : "Export status data with npm run export-status from the website folder."}
        </div>
      </>
    );
  }

  return (
    <div className="status-table-wrap">
      <div className="panel-heading">
        <div>
          <h2>Positions</h2>
          <p>Last updated: {lastUpdatedLabel}</p>
        </div>
        <details className="table-menu">
          <summary aria-label="Table options">⋮</summary>
          <div className="table-menu-panel">
            <label className="rows-menu-control">
              <span>Rows per page</span>
              <select value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))}>
                {PAGE_SIZES.map((size) => (
                  <option value={size} key={size}>
                    {size}
                  </option>
                ))}
              </select>
            </label>
            <div className="table-menu-section-title">Visible columns</div>
            {COLUMNS.map((column) => (
              <label className="column-toggle-row" key={column.key}>
                <span>{column.label}</span>
                <input
                  type="checkbox"
                  checked={visibleColumns.includes(column.key)}
                  onChange={() => toggleColumn(column.key)}
                />
                <span className="column-toggle-track" aria-hidden="true">
                  <span className="column-toggle-thumb" />
                </span>
              </label>
            ))}
          </div>
        </details>
      </div>

      <div className="table-scroll">
        <table style={{ minWidth: tableWidth }}>
          <colgroup>
            {selectedColumns.map((column) => (
              <col key={column.key} style={{ width: columnWidths[column.key] }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              {selectedColumns.map((column) => (
                <th
                  key={column.key}
                  className={column.numeric ? "numeric-cell" : undefined}
                  aria-sort={
                    sortKey === column.key
                      ? sortDirection === "asc"
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                >
                  <button
                    type="button"
                    className="sort-button"
                    onClick={() => {
                      setSortDirection(nextDirection(sortKey, column.key, sortDirection));
                      setSortKey(column.key);
                    }}
                  >
                    <span>{column.label}</span>
                    <span className="sort-indicator" aria-hidden="true">
                      {sortKey === column.key ? (sortDirection === "asc" ? "↑" : "↓") : "↕"}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="resize-handle"
                    aria-label={`Resize ${column.label} column`}
                    onMouseDown={(event) => {
                      event.preventDefault();
                      startColumnResize(column.key, event.clientX);
                    }}
                  />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((bet) => (
              <tr key={bet.id}>
                {selectedColumns.map((column) => {
                  const value = column.render(bet);
                  if (column.key === "status") {
                    return (
                      <td className="status-cell" data-status={bet.status} key={column.key}>
                        {value}
                      </td>
                    );
                  }
                  if (column.key === "orderLifecycleStatus") {
                    return (
                      <td className="status-cell" data-status={bet.orderLifecycleStatus} key={column.key}>
                        {value}
                      </td>
                    );
                  }
                  if (column.key === "fillStatus") {
                    return (
                      <td className="status-cell" data-status={bet.fillStatus} key={column.key}>
                        {value}
                      </td>
                    );
                  }
                  if (column.key === "positionStatus") {
                    return (
                      <td className="status-cell" data-status={bet.positionStatus} key={column.key}>
                        {value}
                      </td>
                    );
                  }
                  if (column.key === "side") {
                    return (
                      <td className="side-cell" data-side={bet.side} key={column.key}>
                        {value}
                      </td>
                    );
                  }
                  if (column.key === "sport") {
                    return (
                      <td className="sport-cell" data-sport={bet.sport.toLowerCase()} key={column.key}>
                        {value}
                      </td>
                    );
                  }
                  if (column.key === "engine") {
                    return (
                      <td className="engine-cell" data-engine={bet.engine.toLowerCase()} key={column.key}>
                        {value}
                      </td>
                    );
                  }
                  if (column.key === "simulated") {
                    return (
                      <td className="simulation-cell" data-simulated={String(bet.simulated)} key={column.key}>
                        {value}
                      </td>
                    );
                  }
                  if (column.key === "marketResult") {
                    return (
                      <td className="result-cell" data-result={String(value).toLowerCase()} key={column.key}>
                        {value}
                      </td>
                    );
                  }
                  if (column.key === "pnlDollars") {
                    const pnlState =
                      ["open", "pending_order", "unfilled", "partial_order"].includes(bet.status)
                        ? "open"
                        : bet.pnlDollars > 0
                          ? "positive"
                          : bet.pnlDollars < 0
                            ? "negative"
                            : "flat";
                    return (
                      <td className="numeric-cell pnl-cell" data-pnl={pnlState} key={column.key}>
                        {value}
                      </td>
                    );
                  }
                  return (
                    <td className={column.numeric ? "numeric-cell" : undefined} key={column.key}>
                      {value}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="table-footer">
        <span>
          {pageStart + 1}-{Math.min(pageStart + pageSize, sortedBets.length)} of {sortedBets.length}
        </span>
        <div className="table-page-buttons">
          <span>
            Page {safePage} of {pageCount}
          </span>
          <button type="button" disabled={safePage === 1} onClick={() => setPage((currentPage) => currentPage - 1)}>
            Prev
          </button>
          <button
            type="button"
            disabled={safePage === pageCount}
            onClick={() => setPage((currentPage) => currentPage + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
