import type { Period, TopScan } from '../contract'
import { PERIOD_LABELS, useUnknownOnly } from '../selectedPeriod'
import { ScannedProductRow } from './ScannedProductRow'

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
        <ol className="scanned-product-rows">
          {rows.map((row) => (
            <ScannedProductRow key={row.product.code} product={row.product} count={row.count}>
              <span className="share">{percent.format(row.share)}</span>
            </ScannedProductRow>
          ))}
        </ol>
      )}
    </>
  )
}
