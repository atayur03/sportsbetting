import { formatRate, money, type StatusSummary } from "../lib/statusData";

type SummaryStatsProps = {
  summary: StatusSummary;
};

export function SummaryStats({ summary }: SummaryStatsProps) {
  const items: Array<[string, string | number, string]> = [
    ["Total", summary.total, summary.total ? "blue" : "neutral"],
    ["Open", summary.open, summary.open ? "blue" : "neutral"],
    ["Closed", summary.closed, summary.closed ? "blue" : "neutral"],
    ["Won", summary.won, summary.won ? "green" : "neutral"],
    ["Lost", summary.lost, summary.lost ? "red" : "neutral"],
    ["Win rate", formatRate(summary.winRate), summary.winRate ? "blue" : "neutral"],
    ["Staked", money(summary.staked), summary.staked ? "blue" : "neutral"],
    ["Realized P&L", money(summary.netPnl), summary.netPnl === 0 ? "neutral" : summary.netPnl > 0 ? "green" : "red"],
  ];

  return (
    <section className="summary-grid" aria-label="Execution summary">
      {items.map(([label, value, tone]) => (
        <div className="summary-tile" data-tone={tone} key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </section>
  );
}
