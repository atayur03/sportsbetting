export type TradeStatus = "open" | "won" | "lost" | "unknown" | string;

export type StatusBet = {
  id: string;
  gameDate: string;
  checkedDate: string;
  engine: string;
  status: TradeStatus;
  strategy: string;
  sport: string;
  side: string;
  contracts: number;
  priceDollars: number;
  stakeDollars: number;
  payoutDollars: number;
  pnlDollars: number;
  marketTitle: string;
  marketSubtitle: string;
  marketResult: string;
  marketStatus: string;
};

export type StatusPayload = {
  generatedAt?: string;
  bets?: StatusBet[];
};

export type StatusSummary = {
  total: number;
  open: number;
  won: number;
  lost: number;
  unknown: number;
  closed: number;
  netPnl: number;
  staked: number;
  winRate: number;
  [status: string]: number;
};

export type ChartRow = {
  date: string;
  total: number;
  strategies: Record<string, number>;
};

export type StatusFilters = {
  strategy: string;
  sport: string;
  status: string;
  startDate: string;
  endDate: string;
  query: string;
};

export const EMPTY_FILTERS: StatusFilters = {
  strategy: "",
  sport: "",
  status: "",
  startDate: "",
  endDate: "",
  query: "",
};

export type FilterOptions = {
  strategies: string[];
  sports: string[];
  statuses: string[];
  minDate: string;
  maxDate: string;
};

export function money(value: number | string | null | undefined): string {
  const amount = Number(value || 0);
  return amount.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatRate(value: number): string {
  if (!Number.isFinite(value)) {
    return "0.0%";
  }
  return `${(value * 100).toFixed(1)}%`;
}

export function summarizeBets(bets: StatusBet[]): StatusSummary {
  const summary: StatusSummary = {
    total: bets.length,
    open: 0,
    won: 0,
    lost: 0,
    unknown: 0,
    closed: 0,
    netPnl: 0,
    staked: 0,
    winRate: 0,
  };

  for (const bet of bets) {
    const status = bet.status || "unknown";
    summary[status] = (summary[status] || 0) + 1;
    summary.staked += Number(bet.stakeDollars || 0);
    if (status === "won" || status === "lost") {
      summary.closed += 1;
      summary.netPnl += Number(bet.pnlDollars || 0);
    }
  }

  summary.winRate = summary.closed ? summary.won / summary.closed : 0;
  return summary;
}

export function filterOptions(bets: StatusBet[]): FilterOptions {
  const dates = bets.map((bet) => bet.gameDate).filter(Boolean).sort();
  return {
    strategies: [...new Set(bets.map((bet) => bet.strategy).filter(Boolean))].sort(),
    sports: [...new Set(bets.map((bet) => bet.sport).filter(Boolean))].sort(),
    statuses: [...new Set(bets.map((bet) => bet.status).filter(Boolean))].sort(),
    minDate: dates[0] || "",
    maxDate: dates[dates.length - 1] || "",
  };
}

export function filterBets(bets: StatusBet[], filters: StatusFilters): StatusBet[] {
  const query = filters.query.trim().toLowerCase();
  return bets.filter((bet) => {
    if (filters.strategy && bet.strategy !== filters.strategy) {
      return false;
    }
    if (filters.sport && bet.sport !== filters.sport) {
      return false;
    }
    if (filters.status && bet.status !== filters.status) {
      return false;
    }
    if (filters.startDate && bet.gameDate < filters.startDate) {
      return false;
    }
    if (filters.endDate && bet.gameDate > filters.endDate) {
      return false;
    }
    if (query) {
      const text = [
        bet.gameDate,
        bet.status,
        bet.strategy,
        bet.sport,
        bet.side,
        bet.marketTitle,
        bet.marketSubtitle,
        bet.marketResult,
        bet.marketStatus,
      ]
        .join(" ")
        .toLowerCase();
      return text.includes(query);
    }
    return true;
  });
}

export function groupClosedBetsByDate(closedBets: StatusBet[]): ChartRow[] {
  const dates = [...new Set(closedBets.map((bet) => bet.gameDate).filter(Boolean))].sort();
  const strategies = [...new Set(closedBets.map((bet) => bet.strategy || "unknown"))].sort();
  const cumulativeByStrategy: Record<string, number> = Object.fromEntries(
    strategies.map((strategy) => [strategy, 0]),
  );
  let cumulativeTotal = 0;

  return dates.map((date) => {
    const betsForDate = closedBets.filter((bet) => bet.gameDate === date);
    for (const bet of betsForDate) {
      const strategy = bet.strategy || "unknown";
      const pnl = Number(bet.pnlDollars || 0);
      cumulativeByStrategy[strategy] = (cumulativeByStrategy[strategy] || 0) + pnl;
      cumulativeTotal += pnl;
    }

    return {
      date,
      total: cumulativeTotal,
      strategies: { ...cumulativeByStrategy },
    };
  });
}
