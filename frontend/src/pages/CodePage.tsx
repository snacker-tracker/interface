import { useParams } from 'react-router'

import { DailyScansChart } from '../components/DailyScansChart'
import { HourlyScansChart } from '../components/HourlyScansChart'
import { ProductCard } from '../components/ProductCard'
import { RecentScans } from '../components/RecentScans'
import { type CodeScansData, codeScansDataPath, type ProductData, productDataPath, useJson } from '../data'
import { ALL_LOCATIONS, useSelectedLocation } from '../selectedLocation'

/** One code: its product (the same everywhere) and its scans within the selected location. */
export function CodePage() {
  // The route param arrives decoded, so it's the code exactly as scanned.
  const { code = '' } = useParams()
  const [location] = useSelectedLocation()
  const product = useJson<ProductData>(productDataPath(code))
  const scans = useJson<CodeScansData>(codeScansDataPath(code, location))

  if (product.status === 'loading' || scans.status === 'loading') return <p className="status">Loading…</p>
  if (product.status === 'missing') {
    return <p className="status status-error">The code {code} has never been scanned.</p>
  }
  for (const fetched of [product, scans]) {
    if (fetched.status === 'error') {
      return <p className="status status-error">Couldn't load this code ({fetched.message}).</p>
    }
  }
  if (product.status !== 'ready') return null // unreachable: loading and missing are handled above

  // No file for this location means the code was never scanned there: zero scans.
  const { daily, hourly, recent } = scans.status === 'ready' ? scans.data : noScans(code, location)
  const total = daily.reduce((sum, { count }) => sum + count, 0)
  const where = location === ALL_LOCATIONS ? 'everywhere' : `at ${location}`

  return (
    <>
      <section className="panel product-panel" aria-labelledby="product-heading">
        <ProductCard code={code} product={product.data.product} headingId="product-heading" />
        <p className="panel-hint">
          {total} {total === 1 ? 'scan' : 'scans'} {where}
        </p>
      </section>
      <section className="panel" aria-labelledby="daily-heading">
        <h2 id="daily-heading">Scans per day</h2>
        {daily.length > 0 && <p className="panel-hint">Drag across the lower chart to zoom in; double-click it to reset.</p>}
        <DailyScansChart daily={daily} />
      </section>
      <section className="panel" aria-labelledby="hourly-heading">
        <h2 id="hourly-heading">Scans by hour of the day</h2>
        <p className="panel-hint">In each office's time zone.</p>
        <HourlyScansChart hourly={hourly} />
      </section>
      <section className="panel" aria-labelledby="recent-heading">
        <h2 id="recent-heading">Latest {recent.length} scans</h2>
        <RecentScans scans={recent} forOneCode />
      </section>
    </>
  )
}

function noScans(code: string, location: string): CodeScansData {
  return {
    code,
    location,
    daily: [],
    hourly: Array.from({ length: 24 }, (_, hour) => ({ hour, count: 0 })),
    recent: [],
  }
}
