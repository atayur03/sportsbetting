import { useState } from "react";

import { EMPTY_FILTERS, formatDate, formatStrategy, type FilterOptions, type StatusFilters } from "../lib/statusData";

type StatusFiltersProps = {
  filters: StatusFilters;
  options: FilterOptions;
  visibleCount: number;
  totalCount: number;
  onChange: (filters: StatusFilters) => void;
};

type ListFilterKey =
  | "strategyExclude"
  | "sportExclude"
  | "statusExclude"
  | "sideExclude";

type IncludeFilterKey = "strategyInclude" | "sportInclude" | "statusInclude" | "sideInclude";

const INCLUDE_KEY_BY_EXCLUDE_KEY: Record<ListFilterKey, IncludeFilterKey> = {
  strategyExclude: "strategyInclude",
  sportExclude: "sportInclude",
  statusExclude: "statusInclude",
  sideExclude: "sideInclude",
};

type FilterGroupProps = {
  label: string;
  variant?: "plain" | "status" | "side" | "sport";
  formatValue?: (value: string) => string;
  values: string[];
  excludeValues: string[];
  onToggle: (value: string) => void;
};

function toggleExcludedValue(filters: StatusFilters, key: ListFilterKey, value: string): StatusFilters {
  const currentValues = filters[key];
  const nextValues = currentValues.includes(value)
    ? currentValues.filter((currentValue) => currentValue !== value)
    : [...currentValues, value];
  const includeKey = INCLUDE_KEY_BY_EXCLUDE_KEY[key];
  return {
    ...filters,
    [key]: nextValues,
    [includeKey]: filters[includeKey].filter((currentValue) => currentValue !== value),
  };
}

function updateTextFilter(filters: StatusFilters, key: "startDate" | "endDate" | "query", value: string): StatusFilters {
  return { ...filters, [key]: value };
}

function searchPlaceholder(label: string): string {
  return `Search ${label}`;
}

function FilterLabel({
  value,
  variant = "plain",
  formatValue = (rawValue: string) => rawValue,
}: {
  value: string;
  variant?: FilterGroupProps["variant"];
  formatValue?: (value: string) => string;
}) {
  if (variant === "status") {
    return (
      <span className="status-pill" data-status={value}>
        {value}
      </span>
    );
  }
  if (variant === "side") {
    return (
      <span className="side-pill" data-side={value}>
        {value}
      </span>
    );
  }
  if (variant === "sport") {
    return (
      <span className="sport-pill" data-sport={value.toLowerCase()}>
        {value}
      </span>
    );
  }
  return <span className="filter-chip-name">{formatValue(value)}</span>;
}

function FilterGroup({ label, variant = "plain", formatValue, values, excludeValues, onToggle }: FilterGroupProps) {
  const [valueSearch, setValueSearch] = useState("");
  const normalizedSearch = valueSearch.trim().toLowerCase();
  const visibleValues = normalizedSearch
    ? values.filter((value) =>
        [value, formatValue ? formatValue(value) : value].join(" ").toLowerCase().includes(normalizedSearch),
      )
    : values;

  return (
    <div className="filter-group">
      <div className="filter-group-label">{label}</div>
      <input
        className="filter-value-search"
        type="search"
        value={valueSearch}
        placeholder={searchPlaceholder(label)}
        onChange={(event) => setValueSearch(event.target.value)}
      />
      <div className="filter-chip-list">
        {visibleValues.length ? (
          visibleValues.map((value) => {
            const excluded = excludeValues.includes(value);
            return (
              <div className="filter-chip-row" key={value}>
                <FilterLabel value={value} variant={variant} formatValue={formatValue} />
                <button
                  type="button"
                  className="include-exclude-switch"
                  data-state={excluded ? "excluded" : "included"}
                  aria-pressed={excluded}
                  onClick={() => onToggle(value)}
                >
                  <span className="switch-track" aria-hidden="true">
                    <span className="switch-thumb" />
                  </span>
                  <span className="switch-label">{excluded ? "Excluded" : "Included"}</span>
                </button>
              </div>
            );
          })
        ) : (
          <span className="filter-empty">{values.length ? "No matches" : "None present"}</span>
        )}
      </div>
    </div>
  );
}

export function StatusFilters({
  filters,
  options,
  visibleCount,
  totalCount,
  onChange,
}: StatusFiltersProps) {
  const [open, setOpen] = useState(false);

  return (
    <section className="panel filters-panel" aria-label="Status filters">
      <div className="filters-bar">
        <div>
          <h2>Filters</h2>
          <p>
            Showing {visibleCount} of {totalCount} Positions
          </p>
        </div>
        <div className="filters-actions">
          <button type="button" onClick={() => setOpen((currentOpen) => !currentOpen)}>
            {open ? "Hide Filters" : "Show Filters"}
          </button>
          <button type="button" onClick={() => onChange(EMPTY_FILTERS)}>
            Reset
          </button>
        </div>
      </div>

      {open ? (
        <div className="filters-content">
          <div className="filters-grid">
            <FilterGroup
              label="Strategy"
              formatValue={formatStrategy}
              values={options.strategies}
              excludeValues={filters.strategyExclude}
              onToggle={(value) => onChange(toggleExcludedValue(filters, "strategyExclude", value))}
            />
            <FilterGroup
              label="Sport"
              variant="sport"
              values={options.sports}
              excludeValues={filters.sportExclude}
              onToggle={(value) => onChange(toggleExcludedValue(filters, "sportExclude", value))}
            />
            <FilterGroup
              label="Status"
              variant="status"
              values={options.statuses}
              excludeValues={filters.statusExclude}
              onToggle={(value) => onChange(toggleExcludedValue(filters, "statusExclude", value))}
            />
            <FilterGroup
              label="Side"
              variant="side"
              values={options.sides}
              excludeValues={filters.sideExclude}
              onToggle={(value) => onChange(toggleExcludedValue(filters, "sideExclude", value))}
            />
          </div>

          <div className="filters-secondary-grid">
            <label className="filter-control">
              <span>Start Date</span>
              <input
                type="date"
                min={options.minDate}
                max={options.maxDate}
                value={filters.startDate}
                onChange={(event) => onChange(updateTextFilter(filters, "startDate", event.target.value))}
              />
              <small>{formatDate(filters.startDate)}</small>
            </label>

            <label className="filter-control">
              <span>End Date</span>
              <input
                type="date"
                min={options.minDate}
                max={options.maxDate}
                value={filters.endDate}
                onChange={(event) => onChange(updateTextFilter(filters, "endDate", event.target.value))}
              />
              <small>{formatDate(filters.endDate)}</small>
            </label>

            <label className="filter-control">
              <span>Search</span>
              <input
                type="search"
                value={filters.query}
                placeholder="Market, Side, Result"
                onChange={(event) => onChange(updateTextFilter(filters, "query", event.target.value))}
              />
            </label>
          </div>
        </div>
      ) : null}
    </section>
  );
}
