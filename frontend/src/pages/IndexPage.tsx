import { DailyScansChart } from '../components/DailyScansChart'
import { RecentScans } from '../components/RecentScans'
import { type IndexData, indexDataPath, useJson } from '../data'

// Every location until the location selector arrives (ticket 03).
const ALL_LOCATIONS = 'all'

export function IndexPage() {
  const index = useJson<IndexData>(indexDataPath(ALL_LOCATIONS))

  if (index.status === 'loading') return <p className="status">Loading scans…</p>
  if (index.status === 'error') {
    return <p className="status status-error">Couldn't load scans ({index.message}). Has the data been built?</p>
  }

  const { daily, recent } = index.data
  return (
    <>
      <section className="panel" aria-labelledby="daily-heading">
        <h2 id="daily-heading">Scans per day</h2>
        <p className="panel-hint">Drag across the lower chart to zoom in; double-click it to reset.</p>
        <DailyScansChart daily={daily} />
      </section>
      <section className="panel" aria-labelledby="recent-heading">
        <h2 id="recent-heading">Latest {recent.length} scans</h2>
        <RecentScans scans={recent} />
      </section>
    </>
  )
}
