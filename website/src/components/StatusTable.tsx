import { useMemo, useState } from "react";

import { money, type StatusBet } from "../lib/statusData";

type StatusTableProps = {
  bets: StatusBet[];
};

type SortDirection = "asc" | "desc";
type SortKey =
  | "gameDate"
  | "status"
  | "strategy"
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
};

const COLUMNS: Column[] = [
  { key: "gameDate", label: "Game date" },
  { key: "status", label: "Status" },
  { key: "strategy", label: "Strategy" },
  { key: "sport", label: "Sport" },
  { key: "side", label: "Side" },
  { key: "contracts", label: "Contracts", numeric: true },
  { key: "stakeDollars", label: "Stake", numeric: true },
  { key: "priceDollars", label: "Price", numeric: true },
  { key: "pnlDollars", label: "P&L", numeric: true },
  { key: "marketTitle", label: "Market" },
  { key: "marketResult", label: "Result" },
];

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

export function StatusTable({ bets }: StatusTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("gameDate");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const sortedBets = useMemo(
    () => [...bets].sort((a, b) => compareBets(a, b, sortKey, sortDirection)),
    [bets, sortDirection, sortKey],
  );

  if (!bets.length) {
    return (
      <div className="empty-state">
        Export status data with <code>npm run export-status</code> from the website folder.
      </div>
    );
  }

  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {COLUMNS.map((column) => (
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
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedBets.map((bet) => (
            <tr key={bet.id}>
              <td>{bet.gameDate || ""}</td>
              <td>
                <span className="status-pill" data-status={bet.status}>
                  {bet.status}
                </span>
              </td>
              <td>{bet.strategy}</td>
              <td>{bet.sport}</td>
              <td>{bet.side}</td>
              <td className="numeric-cell">{bet.contracts}</td>
              <td className="numeric-cell">{money(bet.stakeDollars)}</td>
              <td className="numeric-cell">{money(bet.priceDollars)}</td>
              <td className="numeric-cell">
                {bet.status === "won" || bet.status === "lost" ? money(bet.pnlDollars) : ""}
              </td>
              <td>{bet.marketTitle}</td>
              <td>{bet.marketResult}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
