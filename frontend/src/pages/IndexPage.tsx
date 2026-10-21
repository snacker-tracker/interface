import { useState } from 'react'

import { DailyScansChart } from '../components/DailyScansChart'
import { HealthiestAndLeastHealthy } from '../components/HealthiestAndLeastHealthy'
import { NutriScoreChart } from '../components/NutriScoreChart'
import { PeriodSelector } from '../components/PeriodSelector'
import { RecentScans } from '../components/RecentScans'
import { TopScans } from '../components/TopScans'
import type { IndexFile, NutriScoreDistribution, Period } from '../contract'
import { indexDataPath, useJson } from '../data'
import { useSelectedLocation } from '../selectedLocation'
import { PERIOD_LABELS, useSelectedPeriod } from '../selectedPeriod'

export function IndexPage() {
  const [location] = useSelectedLocation()
  const index = useJson<IndexFile>(indexDataPath(location))
  const [period, selectPeriod] = useSelectedPeriod()
  // Choosing a period, even the selected one, zooms the chart back to it after a hand-brushed zoom.
  const [zooms, setZooms] = useState(0)
  const choosePeriod = (next: Period) => {
    selectPeriod(next)
    setZooms((count) => count + 1)
  }

  if (index.status === 'loading') return <p className="status">Loading scans…</p>
  if (index.status === 'missing') {
    return <p className="status status-error">There's no data for {location}. Is it a known location, and has the data been built?</p>
  }
  if (index.status === 'error') {
    return <p className="status status-error">Couldn't load scans for {location} ({index.message}).</p>
  }

  const { top_scans, top_unknown_scans, healthiest_and_least_healthy, nutri_score_distribution, period_days, daily, recent } =
    index.data
  const periodName = PERIOD_LABELS[period].label
  // All time is the whole history, so it needs no zoom.
  const zoom = period === 'all-time' ? null : period_days[period]
  return (
    <>
      <PeriodSelector period={period} select={choosePeriod} />
      <section className="panel" aria-labelledby="daily-heading">
        <h2 id="daily-heading">Scans per day</h2>
        <p className="panel-hint">
          {zoom
            ? 'Zoomed to the period; drag across the lower chart to look elsewhere.'
            : 'Drag across the lower chart to zoom in; double-click it to reset.'}
        </p>
        <DailyScansChart key={zooms} daily={daily} zoom={zoom} until={period_days['all-time'].last_day} />
      </section>
      <section className="panel" aria-labelledby="top-scans-heading">
        <h2 id="top-scans-heading">Top scans · {periodName}</h2>
        <p className="panel-hint">The codes scanned most, up to when the data was built.</p>
        <TopScans period={period} topScans={top_scans} topUnknownScans={top_unknown_scans} />
      </section>
      <section className="panel" aria-labelledby="nutri-score-heading">
        <h2 id="nutri-score-heading">Nutri-Score of scans · {periodName}</h2>
        <NutriScoreHint distribution={nutri_score_distribution[period]} period={period} />
        <NutriScoreChart distribution={nutri_score_distribution[period]} />
      </section>
      <section className="panel" aria-labelledby="health-heading">
        <h2 id="health-heading">Healthiest and least healthy products · {periodName}</h2>
        <HealthiestAndLeastHealthy period={period} byPeriod={healthiest_and_least_healthy} />
      </section>
      <section className="panel" aria-labelledby="recent-heading">
        <h2 id="recent-heading">Latest {recent.length} scans</h2>
        <RecentScans scans={recent} />
      </section>
    </>
  )
}

const count = new Intl.NumberFormat('en')

/** What the Nutri-Score chart covers: only scans of products with a Nutri-Score. */
function NutriScoreHint({ distribution, period }: { distribution: NutriScoreDistribution; period: Period }) {
  if (distribution.graded_scans === 0) {
    return <p className="panel-hint">{PERIOD_LABELS[period].empty.replace('No scans', 'No scans with a Nutri-Score')}.</p>
  }
  return (
    <p className="panel-hint">
      Based on the {count.format(distribution.graded_scans)} of {count.format(distribution.scans)} scans with a
      Nutri-Score.
    </p>
  )
}
