import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TickItem,
  type TooltipProps,
} from "recharts";
import { useMemo, useState } from "react";

import { formatDate, formatDateTime, formatStrategy, money, type ChartRow } from "../lib/statusData";

const COLORS = ["#2f6fed", "#c2410c", "#047857", "#7c3aed", "#be123c", "#0f766e"];
const MINUTE_MS = 60 * 1000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;

type BucketUnit = "minutes" | "hours" | "days";

type ResultsChartProps = {
  rows: ChartRow[];
};

type ChartDatum = {
  timestamp: number;
  label: string;
  settledAt: string;
  total: number;
  [strategy: string]: number | string;
};

type AxisTickProps = {
  x?: number;
  y?: number;
  payload?: TickItem;
  maxTimestamp: number;
};

function timestampForRow(row: ChartRow): number {
  const parsed = Date.parse(row.settledAt || row.date);
  return Number.isFinite(parsed) ? parsed : 0;
}

function bucketSizeMs(amount: number, unit: BucketUnit): number {
  const safeAmount = Math.max(1, Math.floor(amount));
  if (unit === "hours") {
    return safeAmount * HOUR_MS;
  }
  if (unit === "days") {
    return safeAmount * DAY_MS;
  }
  return safeAmount * MINUTE_MS;
}

function bucketTimestamp(timestamp: number, bucketMs: number): number {
  return timestamp > 0 ? Math.floor(timestamp / bucketMs) * bucketMs : 0;
}

function formatTimestamp(value: number | string): string {
  const timestamp = Number(value);
  if (!Number.isFinite(timestamp)) {
    return "";
  }
  return formatDateTime(new Date(timestamp).toISOString());
}

function formatAxisTimestamp(value: number | string): string {
  const timestamp = Number(value);
  if (!Number.isFinite(timestamp)) {
    return "";
  }
  const parsed = new Date(timestamp);
  const month = String(parsed.getMonth() + 1).padStart(2, "0");
  const day = String(parsed.getDate()).padStart(2, "0");
  const year = String(parsed.getFullYear()).slice(-2);
  const hours = String(parsed.getHours()).padStart(2, "0");
  const minutes = String(parsed.getMinutes()).padStart(2, "0");
  return `${month}/${day}/${year} ${hours}:${minutes}`;
}

function chartData(rows: ChartRow[], strategies: string[], bucketMs: number): ChartDatum[] {
  const dataByBucket = new Map<number, ChartDatum>();

  for (const row of rows) {
    const rawTimestamp = timestampForRow(row);
    const timestamp = bucketTimestamp(rawTimestamp, bucketMs);
    const datum: ChartDatum = {
      timestamp,
      label: formatTimestamp(timestamp) || formatDate(row.date),
      settledAt: row.settledAt,
      total: row.total,
    };
    for (const strategy of strategies) {
      datum[strategy] = row.strategies[strategy] || 0;
    }
    dataByBucket.set(timestamp, datum);
  }

  return [...dataByBucket.values()].sort((a, b) => a.timestamp - b.timestamp);
}

function formatLegendValue(value: string): string {
  return value === "total" ? "Total" : formatStrategy(value);
}

function TimeAxisTick({ x = 0, y = 0, payload, maxTimestamp }: AxisTickProps) {
  const value = Number(payload?.value);
  const isRightEdge = value === maxTimestamp;

  return (
    <text className="chart-axis-tick" x={x + (isRightEdge ? 24 : 4)} y={y + 16} textAnchor={isRightEdge ? "end" : "start"}>
      {formatAxisTimestamp(value)}
    </text>
  );
}

function ChartTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) {
    return null;
  }
  const datum = payload[0].payload as ChartDatum;

  return (
    <div className="chart-tooltip">
      <div className="chart-tooltip-title">{datum.label}</div>
      {payload.map((entry) => (
        <div className="chart-tooltip-row" key={entry.dataKey}>
          <span>
            <i style={{ background: entry.color }} /> {formatLegendValue(String(entry.dataKey))}
          </span>
          <strong>{money(entry.value)}</strong>
        </div>
      ))}
    </div>
  );
}

export function ResultsChart({ rows }: ResultsChartProps) {
  const [bucketAmount, setBucketAmount] = useState(10);
  const [bucketUnit, setBucketUnit] = useState<BucketUnit>("minutes");
  const strategies = useMemo(
    () => [...new Set(rows.flatMap((row) => Object.keys(row.strategies)))].sort(),
    [rows],
  );
  const bucketMs = useMemo(() => bucketSizeMs(bucketAmount, bucketUnit), [bucketAmount, bucketUnit]);
  const data = useMemo(() => chartData(rows, strategies, bucketMs), [bucketMs, rows, strategies]);
  const timestamps = data.map((datum) => datum.timestamp).filter((timestamp) => timestamp > 0);
  const minTimestamp = timestamps.length ? Math.min(...timestamps) : 0;
  const maxTimestamp = timestamps.length ? Math.max(...timestamps) : 0;
  const xDomain =
    minTimestamp === maxTimestamp
      ? [minTimestamp - 60_000, maxTimestamp + 60_000]
      : [minTimestamp, maxTimestamp];

  if (!rows.length) {
    return (
      <div className="empty-state">
        Closed bets will appear here once markets resolve to won or lost.
      </div>
    );
  }

  return (
    <>
      <div className="panel-heading">
        <div>
          <h2>Performance</h2>
          <p>Total and strategy-level cumulative result by game date.</p>
        </div>
        <details className="chart-menu">
          <summary aria-label="Chart options">⋮</summary>
          <div className="chart-menu-panel">
            <div className="chart-menu-title">Grouping</div>
            <label className="chart-menu-control">
              <span>Amount</span>
              <input
                min="1"
                step="1"
                type="number"
                value={bucketAmount}
                onChange={(event) => setBucketAmount(Math.max(1, Number(event.target.value) || 1))}
              />
            </label>
            <label className="chart-menu-control">
              <span>Unit</span>
              <select value={bucketUnit} onChange={(event) => setBucketUnit(event.target.value as BucketUnit)}>
                <option value="minutes">minutes</option>
                <option value="hours">hours</option>
                <option value="days">days</option>
              </select>
            </label>
          </div>
        </details>
      </div>
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height={360}>
          <LineChart data={data} margin={{ top: 18, right: 28, bottom: 8, left: 12 }}>
            <CartesianGrid stroke="#e7ebf2" strokeDasharray="4 4" />
            <XAxis
              dataKey="timestamp"
              type="number"
              scale="time"
              domain={xDomain}
              tick={(props) => <TimeAxisTick {...props} maxTimestamp={maxTimestamp} />}
              tickFormatter={(value) => formatAxisTimestamp(value)}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "#6b7280", fontSize: 12 }}
              tickFormatter={(value) => money(value)}
              tickLine={false}
              width={74}
            />
            <Tooltip content={<ChartTooltip />} />
            <Line
              type="monotone"
              dataKey="total"
              stroke="#111827"
              strokeWidth={3}
              dot={{ r: 2 }}
              activeDot={{ r: 5 }}
              name="Total"
            />
            {strategies.map((strategy, index) => (
              <Line
                type="monotone"
                dataKey={strategy}
                stroke={COLORS[index % COLORS.length]}
                strokeWidth={2}
                dot={{ r: 2 }}
                activeDot={{ r: 4 }}
                key={strategy}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
        <div className="compact-chart-legend">
          <span>
            <i className="legend-swatch total" /> Total
          </span>
          {strategies.map((strategy, index) => (
            <span key={strategy}>
              <i className="legend-swatch" style={{ background: COLORS[index % COLORS.length] }} />
              {formatStrategy(strategy)}
            </span>
          ))}
        </div>
      </div>
    </>
  );
}
