import type { Period, TopScan } from '../contract'
import { PERIOD_LABELS, useUnknownOnly } from '../selectedPeriod'
import { ScannedProduct } from './ScannedProduct'

const percent = new Intl.NumberFormat('en', { style: 'percent', maximumFractionDigits: 1 })

/**
 * The codes scanned most in the selected period (see GLOSSARY.md, Top scans).
 * "Unknown only" switches to the most-scanned unknown products, the ones worth adding to OpenFoodFacts.
 */
export function TopScans({
  period,
  topScans,
  topUnknownScans,
}: {
  period: Period
  topScans: Record<Period, TopScan[]>
  topUnknownScans: Record<Period, TopScan[]>
}) {
  const [unknownOnly, setUnknownOnly] = useUnknownOnly()
  const rows = (unknownOnly ? topUnknownScans : topScans)[period] ?? []
  const empty = unknownOnly
    ? PERIOD_LABELS[period].empty.replace('No scans', 'No unknown products scanned')
    : PERIOD_LABELS[period].empty

  return (
    <>
      <div className="top-scans-controls">
        <button
          type="button"
          className="unknown-toggle"
          aria-pressed={unknownOnly}
          onClick={() => setUnknownOnly(!unknownOnly)}
        >
          Unknown only
        </button>
      </div>
      {rows.length === 0 ? (
        <p className="status">{empty}.</p>
      ) : (
        <ol className="top-scans">
          {rows.map((row) => (
            <TopScanRow key={row.code} row={row} />
          ))}
        </ol>
      )}
    </>
  )
}

/** A ranked code: its product, its count and, unless left out, its share of the period's scans. */
export function TopScanRow({ row, withShare = true }: { row: TopScan; withShare?: boolean }) {
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
          {withShare && <span className="share">{percent.format(row.share)}</span>}
        </div>
      </div>
    </li>
  )
}
