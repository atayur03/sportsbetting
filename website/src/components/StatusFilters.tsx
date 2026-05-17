import { EMPTY_FILTERS, type FilterOptions, type StatusFilters } from "../lib/statusData";

type StatusFiltersProps = {
  filters: StatusFilters;
  options: FilterOptions;
  visibleCount: number;
  totalCount: number;
  onChange: (filters: StatusFilters) => void;
};

function updateFilter(
  filters: StatusFilters,
  key: keyof StatusFilters,
  value: string,
): StatusFilters {
  return { ...filters, [key]: value };
}

export function StatusFilters({
  filters,
  options,
  visibleCount,
  totalCount,
  onChange,
}: StatusFiltersProps) {
  return (
    <section className="panel filters-panel" aria-label="Status filters">
      <div className="filters-grid">
        <label className="filter-control">
          <span>Strategy</span>
          <select
            value={filters.strategy}
            onChange={(event) => onChange(updateFilter(filters, "strategy", event.target.value))}
          >
            <option value="">All strategies</option>
            {options.strategies.map((strategy) => (
              <option value={strategy} key={strategy}>
                {strategy}
              </option>
            ))}
          </select>
        </label>

        <label className="filter-control">
          <span>Sport</span>
          <select
            value={filters.sport}
            onChange={(event) => onChange(updateFilter(filters, "sport", event.target.value))}
          >
            <option value="">All sports</option>
            {options.sports.map((sport) => (
              <option value={sport} key={sport}>
                {sport}
              </option>
            ))}
          </select>
        </label>

        <label className="filter-control">
          <span>Status</span>
          <select
            value={filters.status}
            onChange={(event) => onChange(updateFilter(filters, "status", event.target.value))}
          >
            <option value="">All statuses</option>
            {options.statuses.map((status) => (
              <option value={status} key={status}>
                {status}
              </option>
            ))}
          </select>
        </label>

        <label className="filter-control">
          <span>Start date</span>
          <input
            type="date"
            min={options.minDate}
            max={options.maxDate}
            value={filters.startDate}
            onChange={(event) => onChange(updateFilter(filters, "startDate", event.target.value))}
          />
        </label>

        <label className="filter-control">
          <span>End date</span>
          <input
            type="date"
            min={options.minDate}
            max={options.maxDate}
            value={filters.endDate}
            onChange={(event) => onChange(updateFilter(filters, "endDate", event.target.value))}
          />
        </label>

        <label className="filter-control search-control">
          <span>Search</span>
          <input
            type="search"
            value={filters.query}
            placeholder="Market, side, result"
            onChange={(event) => onChange(updateFilter(filters, "query", event.target.value))}
          />
        </label>
      </div>

      <div className="filters-footer">
        <span>
          Showing {visibleCount} of {totalCount}
        </span>
        <button type="button" onClick={() => onChange(EMPTY_FILTERS)}>
          Reset
        </button>
      </div>
    </section>
  );
}
