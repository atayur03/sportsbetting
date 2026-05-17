import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../..");
const statusDir = path.join(repoRoot, "execution/data");
const outputPath = path.join(repoRoot, "website/public/data/trade-status.json");

const SAFE_FIELDS = [
  "id",
  "gameDate",
  "checkedDate",
  "engine",
  "status",
  "strategy",
  "sport",
  "side",
  "contracts",
  "priceDollars",
  "stakeDollars",
  "payoutDollars",
  "pnlDollars",
  "marketTitle",
  "marketSubtitle",
  "marketResult",
  "marketStatus",
] as const;

type CsvRow = Record<string, string>;
type SafeField = (typeof SAFE_FIELDS)[number];
type SanitizedBet = Record<SafeField, string | number>;

function parseCsv(text: string): CsvRow[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let value = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (quoted) {
      if (char === '"' && next === '"') {
        value += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        value += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(value);
      value = "";
    } else if (char === "\n") {
      row.push(value);
      rows.push(row);
      row = [];
      value = "";
    } else if (char !== "\r") {
      value += char;
    }
  }

  if (value || row.length) {
    row.push(value);
    rows.push(row);
  }

  const [headers, ...dataRows] = rows;
  if (!headers) {
    return [];
  }
  return dataRows
    .filter((dataRow: string[]) => dataRow.some((cell: string) => cell !== ""))
    .map((dataRow) =>
      Object.fromEntries(headers.map((header, index) => [header, dataRow[index] || ""])),
    );
}

function dateOnly(value: string | undefined): string {
  return value ? String(value).slice(0, 10) : "";
}

function numberValue(value: string | undefined): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function sanitizedBet(row: CsvRow, index: number): SanitizedBet {
  const status = (row.trade_status || "unknown").toLowerCase();
  const contracts = numberValue(row.count);
  const priceDollars = numberValue(row.price_at_placement_dollars || row.limit_price_dollars);
  const stakeDollars = numberValue(row.amount_dollars) || contracts * priceDollars;
  const payoutDollars = status === "won" ? contracts : 0;
  const pnlDollars = status === "won" || status === "lost" ? payoutDollars - stakeDollars : 0;
  const record = {
    id: `${dateOnly(row.occurrence_datetime)}-${index}`,
    gameDate: dateOnly(row.occurrence_datetime || row.expected_expiration_time),
    checkedDate: dateOnly(row.checked_time_utc),
    engine: row.engine || "kalshi",
    status,
    strategy: row.strategy || "unknown",
    sport: row.sports_league || "",
    side: row.side || "",
    contracts,
    priceDollars,
    stakeDollars,
    payoutDollars,
    pnlDollars,
    marketTitle: row.title || "",
    marketSubtitle: row.subtitle || row.yes_sub_title || row.no_sub_title || "",
    marketResult: row.market_result || row.expiration_value || "",
    marketStatus: row.market_status || "",
  };
  return Object.fromEntries(SAFE_FIELDS.map((field) => [field, record[field]])) as SanitizedBet;
}

async function main(): Promise<void> {
  const files = (await readdir(statusDir))
    .filter((file) => /^trade_status_\d{4}-\d{2}-\d{2}\.csv$/.test(file))
    .sort();

  const bets: SanitizedBet[] = [];
  for (const file of files) {
    const csv = await readFile(path.join(statusDir, file), "utf8");
    const rows = parseCsv(csv);
    rows.forEach((row, index) => bets.push(sanitizedBet(row, bets.length + index)));
  }

  await mkdir(path.dirname(outputPath), { recursive: true });
  await writeFile(
    outputPath,
    `${JSON.stringify({ generatedAt: new Date().toISOString(), bets }, null, 2)}\n`,
    "utf8",
  );

  console.log(`Wrote ${bets.length} sanitized status rows to ${path.relative(repoRoot, outputPath)}`);
}

main().catch((error: unknown) => {
  console.error(error);
  process.exitCode = 1;
});
