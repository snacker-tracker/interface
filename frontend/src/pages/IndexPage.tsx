import { DailyScansChart } from '../components/DailyScansChart'
import { HealthiestAndLeastHealthy } from '../components/HealthiestAndLeastHealthy'
import { PeriodSelector } from '../components/PeriodSelector'
import { RecentScans } from '../components/RecentScans'
import { TopScans } from '../components/TopScans'
import type { IndexFile } from '../contract'
import { indexDataPath, useJson } from '../data'
import { useSelectedLocation } from '../selectedLocation'
import { PERIOD_LABELS, useSelectedPeriod } from '../selectedPeriod'

export function IndexPage() {
  const [location] = useSelectedLocation()
  const index = useJson<IndexFile>(indexDataPath(location))
  const [period] = useSelectedPeriod()

  if (index.status === 'loading') return <p className="status">Loading scans…</p>
  if (index.status === 'missing') {
    return <p className="status status-error">There's no data for {location}. Is it a known location, and has the data been built?</p>
  }
  if (index.status === 'error') {
    return <p className="status status-error">Couldn't load scans for {location} ({index.message}).</p>
  }

  const { top_scans, top_unknown_scans, healthiest_and_least_healthy, daily, recent } = index.data
  const periodName = PERIOD_LABELS[period].tab
  return (
    <>
      <PeriodSelector />
      <section className="panel" aria-labelledby="daily-heading">
        <h2 id="daily-heading">Scans per day</h2>
        <p className="panel-hint">Drag across the lower chart to zoom in; double-click it to reset.</p>
        <DailyScansChart daily={daily} />
      </section>
      <section className="panel" aria-labelledby="top-scans-heading">
        <h2 id="top-scans-heading">Top scans · {periodName}</h2>
        <p className="panel-hint">The codes scanned most, up to when the data was built.</p>
        <TopScans topScans={top_scans} topUnknownScans={top_unknown_scans} />
      </section>
      <section className="panel" aria-labelledby="health-heading">
        <h2 id="health-heading">Healthiest and least healthy products · {periodName}</h2>
        <HealthiestAndLeastHealthy byPeriod={healthiest_and_least_healthy} />
      </section>
      <section className="panel" aria-labelledby="recent-heading">
        <h2 id="recent-heading">Latest {recent.length} scans</h2>
        <RecentScans scans={recent} />
      </section>
    </>
  )
}
