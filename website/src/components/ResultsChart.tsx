import { money, type ChartRow } from "../lib/statusData";

const COLORS = ["#2f6fed", "#c2410c", "#047857", "#7c3aed", "#be123c", "#0f766e"];

type ResultsChartProps = {
  rows: ChartRow[];
};

function pointsForSeries(
  rows: ChartRow[],
  selector: (row: ChartRow) => number,
  width: number,
  height: number,
  minY: number,
  maxY: number,
): string {
  if (!rows.length) {
    return "";
  }
  const span = Math.max(maxY - minY, 1);
  return rows
    .map((row, index) => {
      const x = rows.length === 1 ? width / 2 : (index / (rows.length - 1)) * width;
      const y = height - ((selector(row) - minY) / span) * height;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

export function ResultsChart({ rows }: ResultsChartProps) {
  const strategies = [...new Set(rows.flatMap((row) => Object.keys(row.strategies)))].sort();
  const values = rows.flatMap((row) => [row.total, ...Object.values(row.strategies)]);
  const minY = Math.min(0, ...values);
  const maxY = Math.max(0, ...values);
  const width = 920;
  const height = 280;

  if (!rows.length) {
    return (
      <div className="empty-state">
        Closed bets will appear here once markets resolve to won or lost.
      </div>
    );
  }

  return (
    <div className="chart-wrap">
      <svg viewBox={`0 0 ${width + 80} ${height + 72}`} role="img" aria-label="Cumulative closed bet P&L">
        <line className="axis-line" x1="44" y1="20" x2="44" y2={height + 20} />
        <line className="axis-line" x1="44" y1={height + 20} x2={width + 44} y2={height + 20} />
        <text className="axis-label" x="44" y="14">
          {money(maxY)}
        </text>
        <text className="axis-label" x="44" y={height + 40}>
          {money(minY)}
        </text>

        <g transform="translate(44 20)">
          <polyline
            className="series-line total-line"
            points={pointsForSeries(rows, (row) => row.total, width, height, minY, maxY)}
          />
          {strategies.map((strategy, index) => (
            <polyline
              className="series-line"
              key={strategy}
              points={pointsForSeries(
                rows,
                (row) => Number(row.strategies[strategy] || 0),
                width,
                height,
                minY,
                maxY,
              )}
              style={{ stroke: COLORS[index % COLORS.length] }}
            />
          ))}
        </g>

        <text className="axis-label" x="44" y={height + 62}>
          {rows[0].date}
        </text>
        <text className="axis-label end-label" x={width + 44} y={height + 62}>
          {rows[rows.length - 1].date}
        </text>
      </svg>

      <div className="legend">
        <span>
          <i className="legend-swatch total" /> Total
        </span>
        {strategies.map((strategy, index) => (
          <span key={strategy}>
            <i className="legend-swatch" style={{ background: COLORS[index % COLORS.length] }} /> {strategy}
          </span>
        ))}
      </div>
    </div>
  );
}
