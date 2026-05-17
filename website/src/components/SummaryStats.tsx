import { formatRate, money, type StatusSummary } from "../lib/statusData";

type SummaryStatsProps = {
  summary: StatusSummary;
};

export function SummaryStats({ summary }: SummaryStatsProps) {
  const items: Array<[string, string | number]> = [
    ["Total", summary.total],
    ["Open", summary.open],
    ["Closed", summary.closed],
    ["Won", summary.won],
    ["Lost", summary.lost],
    ["Win rate", formatRate(summary.winRate)],
    ["Staked", money(summary.staked)],
    ["Closed P&L", money(summary.netPnl)],
  ];

  return (
    <section className="summary-grid" aria-label="Execution summary">
      {items.map(([label, value]) => (
        <div className="summary-tile" key={label}>
          <span>{label}</span>
          <strong>{value}</strong>
        </div>
      ))}
    </section>
  );
}
