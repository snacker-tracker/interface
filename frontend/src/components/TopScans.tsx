import { type Period, PERIODS, type TopScan } from '../contract'
import { useSelectedPeriod, useUnknownOnly } from '../selectedPeriod'
import { ScannedProduct } from './ScannedProduct'

const LABELS: Record<Period, { tab: string; empty: string }> = {
  today: { tab: 'Today', empty: 'No scans today' },
  'this-work-week': { tab: 'This work week', empty: 'No scans this work week' },
  'last-7-days': { tab: 'Last 7 days', empty: 'No scans in the last 7 days' },
  'this-month': { tab: 'This month', empty: 'No scans this month' },
  'last-30-days': { tab: 'Last 30 days', empty: 'No scans in the last 30 days' },
  'this-year': { tab: 'This year', empty: 'No scans this year' },
  'last-365-days': { tab: 'Last 365 days', empty: 'No scans in the last 365 days' },
  'all-time': { tab: 'All time', empty: 'No scans yet' },
}

const percent = new Intl.NumberFormat('en', { style: 'percent', maximumFractionDigits: 1 })

/**
 * The codes scanned most in the chosen period, with a tab per period (see GLOSSARY.md, Top scans).
 * "Unknown only" switches to the most-scanned unknown products, the ones worth adding to OpenFoodFacts.
 */
export function TopScans({
  topScans,
  topUnknownScans,
}: {
  topScans: Record<Period, TopScan[]>
  topUnknownScans: Record<Period, TopScan[]>
}) {
  const [period, select] = useSelectedPeriod()
  const [unknownOnly, setUnknownOnly] = useUnknownOnly()
  const rows = (unknownOnly ? topUnknownScans : topScans)[period] ?? []
  const empty = unknownOnly
    ? LABELS[period].empty.replace('No scans', 'No unknown products scanned')
    : LABELS[period].empty

  return (
    <>
      <div className="top-scans-controls">
        <div className="period-tabs" role="tablist" aria-label="Period">
          {PERIODS.map((id) => (
            <button
              key={id}
              type="button"
              role="tab"
              id={`period-${id}`}
              aria-selected={id === period}
              aria-controls="top-scans-list"
              onClick={() => select(id)}
            >
              {LABELS[id].tab}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="unknown-toggle"
          aria-pressed={unknownOnly}
          onClick={() => setUnknownOnly(!unknownOnly)}
        >
          Unknown only
        </button>
      </div>
      <div id="top-scans-list" role="tabpanel" aria-labelledby={`period-${period}`}>
        {rows.length === 0 ? (
          <p className="status">{empty}.</p>
        ) : (
          <ol className="top-scans">
            {rows.map((row) => (
              <TopScanRow key={row.code} row={row} />
            ))}
          </ol>
        )}
      </div>
    </>
  )
}

function TopScanRow({ row }: { row: TopScan }) {
  return (
    <li>
      <div className="top-scan-row">
        <div className="top-scan-product">
          <ScannedProduct
            code={row.code}
            name={row.name}
            nameSource={row.name_source}
            brands={row.brands}
            known={row.known}
            nutriScore={row.nutri_score}
          />
        </div>
        <div className="top-scan-count">
          <strong>{row.count}</strong> {row.count === 1 ? 'scan' : 'scans'}
          <span className="share">{percent.format(row.share)}</span>
        </div>
      </div>
    </li>
  )
}
