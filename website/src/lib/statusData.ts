export type TradeStatus = "open" | "won" | "lost" | "unknown" | string;

export type StatusBet = {
  id: string;
  gameDate: string;
  settledAt: string;
  checkedDate: string;
  engine: string;
  simulated: boolean;
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
  settledAt: string;
  total: number;
  strategies: Record<string, number>;
};

export type StatusFilters = {
  strategyInclude: string[];
  strategyExclude: string[];
  sportInclude: string[];
  sportExclude: string[];
  statusInclude: string[];
  statusExclude: string[];
  sideInclude: string[];
  sideExclude: string[];
  engineInclude: string[];
  engineExclude: string[];
  simulatedInclude: string[];
  simulatedExclude: string[];
  startDate: string;
  endDate: string;
  query: string;
};

export const EMPTY_FILTERS: StatusFilters = {
  strategyInclude: [],
  strategyExclude: [],
  sportInclude: [],
  sportExclude: [],
  statusInclude: [],
  statusExclude: [],
  sideInclude: [],
  sideExclude: [],
  engineInclude: [],
  engineExclude: [],
  simulatedInclude: ["real"],
  simulatedExclude: [],
  startDate: "",
  endDate: "",
  query: "",
};

export function filtersWithDateRange(filters: StatusFilters, options: FilterOptions): StatusFilters {
  return {
    ...filters,
    startDate: filters.startDate || options.minDate,
    endDate: filters.endDate || options.maxDate,
  };
}

export type FilterOptions = {
  strategies: string[];
  sports: string[];
  statuses: string[];
  sides: string[];
  engines: string[];
  simulated: string[];
  minDate: string;
  maxDate: string;
};

const SUPPORTED_SPORTS = ["MLB", "NBA", "NFL", "NHL"];

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

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) {
    return value;
  }
  return `${month}/${day}/${year}`;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return formatDate(value.slice(0, 10));
  }
  const month = String(parsed.getMonth() + 1).padStart(2, "0");
  const day = String(parsed.getDate()).padStart(2, "0");
  const year = parsed.getFullYear();
  const hours = String(parsed.getHours()).padStart(2, "0");
  const minutes = String(parsed.getMinutes()).padStart(2, "0");
  return `${month}/${day}/${year} ${hours}:${minutes}`;
}

export function dateOnly(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : "";
}

export function formatStrategy(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  const explicitLabels: Record<string, string> = {
    initial_test: "Initial Test",
    underdog: "Underdog",
    game_total_under: "Game Total Under",
  };
  if (explicitLabels[value]) {
    return explicitLabels[value];
  }
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

export function formatEngine(value: string | null | undefined): string {
  if (!value) {
    return "";
  }
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

export function simulationLabel(value: boolean): string {
  return value ? "simulated" : "real";
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
    sports: [...new Set([...SUPPORTED_SPORTS, ...bets.map((bet) => bet.sport).filter(Boolean)])].sort(),
    statuses: [...new Set(bets.map((bet) => bet.status).filter(Boolean))].sort(),
    sides: [...new Set(bets.map((bet) => bet.side).filter(Boolean))].sort(),
    engines: [...new Set(bets.map((bet) => bet.engine).filter(Boolean))].sort(),
    simulated: ["real", "simulated"],
    minDate: dates[0] || "",
    maxDate: dates[dates.length - 1] || "",
  };
}

function passesSetFilter(value: string, include: string[], exclude: string[]): boolean {
  if (exclude.includes(value)) {
    return false;
  }
  if (include.length > 0 && !include.includes(value)) {
    return false;
  }
  return true;
}

export function filterBets(bets: StatusBet[], filters: StatusFilters): StatusBet[] {
  const query = filters.query.trim().toLowerCase();
  return bets.filter((bet) => {
    if (!passesSetFilter(bet.strategy, filters.strategyInclude, filters.strategyExclude)) {
      return false;
    }
    if (!passesSetFilter(bet.sport, filters.sportInclude, filters.sportExclude)) {
      return false;
    }
    if (!passesSetFilter(String(bet.status), filters.statusInclude, filters.statusExclude)) {
      return false;
    }
    if (!passesSetFilter(bet.side, filters.sideInclude, filters.sideExclude)) {
      return false;
    }
    if (!passesSetFilter(bet.engine, filters.engineInclude, filters.engineExclude)) {
      return false;
    }
    if (!passesSetFilter(simulationLabel(bet.simulated), filters.simulatedInclude, filters.simulatedExclude)) {
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
        formatStrategy(bet.strategy),
        bet.sport,
        bet.side,
        bet.engine,
        formatEngine(bet.engine),
        simulationLabel(bet.simulated),
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

export function groupClosedBetsBySettlement(closedBets: StatusBet[]): ChartRow[] {
  const strategies = [...new Set(closedBets.map((bet) => bet.strategy || "unknown"))].sort();
  const cumulativeByStrategy: Record<string, number> = Object.fromEntries(
    strategies.map((strategy) => [strategy, 0]),
  );
  let cumulativeTotal = 0;

  return [...closedBets]
    .sort((a, b) => {
      const aTime = a.settledAt || a.gameDate;
      const bTime = b.settledAt || b.gameDate;
      return aTime.localeCompare(bTime);
    })
    .map((bet) => {
      const strategy = bet.strategy || "unknown";
      const pnl = Number(bet.pnlDollars || 0);
      cumulativeByStrategy[strategy] = (cumulativeByStrategy[strategy] || 0) + pnl;
      cumulativeTotal += pnl;

      return {
        date: dateOnly(bet.settledAt) || bet.gameDate,
        settledAt: bet.settledAt,
        total: cumulativeTotal,
        strategies: { ...cumulativeByStrategy },
      };
    });
}
