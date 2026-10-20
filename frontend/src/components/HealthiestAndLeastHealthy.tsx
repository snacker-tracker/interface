import type { HealthiestAndLeastHealthy as Lists, Period, ScannedProductCount } from '../contract'
import { PERIOD_LABELS } from '../selectedPeriod'
import { ScannedProductRow } from './ScannedProductRow'

const count = new Intl.NumberFormat('en')

/**
 * The healthiest and least healthy products scanned in the selected period (GLOSSARY.md), side by
 * side: only products with a Nutri-Score are ranked, and the coverage line says how many scans that is.
 */
export function HealthiestAndLeastHealthy({ period, byPeriod }: { period: Period; byPeriod: Record<Period, Lists> }) {
  const lists = byPeriod[period]
  if (!lists || lists.graded_scans === 0) {
    return <p className="status">{PERIOD_LABELS[period].empty.replace('No scans', 'No products with a Nutri-Score scanned')}.</p>
  }
  return (
    <>
      <p className="panel-hint">
        Based on the {count.format(lists.graded_scans)} of {count.format(lists.scans)}{' '}
        scans with a Nutri-Score.
      </p>
      <div className="health-lists">
        <HealthList heading="Healthiest" rows={lists.healthiest} />
        <HealthList heading="Least healthy" rows={lists.least_healthy} />
      </div>
    </>
  )
}

function HealthList({ heading, rows }: { heading: string; rows: ScannedProductCount[] }) {
  return (
    <div>
      <h3>{heading}</h3>
      {rows.length === 0 ? (
        <p className="status">Nothing else to compare.</p>
      ) : (
        <ol className="top-scans">
          {rows.map((row) => (
            <ScannedProductRow key={row.product.code} product={row.product} count={row.count} />
          ))}
        </ol>
      )}
    </div>
  )
}
