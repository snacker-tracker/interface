import { useMemo } from 'react'
import { VegaEmbed } from 'react-vega'

import type { DailyCount, PeriodDays } from '../contract'
import { useChartTokens } from '../theme'
import { dailyScansSpec } from './dailyScansSpec'

/**
 * Scans per day, with brush-to-zoom (see `dailyScansSpec`) and a table view of the same data.
 * With `zoom`, it opens zoomed to those days; brushing by hand still moves it. `until` is the
 * build's office day, which the overview runs to.
 */
export function DailyScansChart({
  daily,
  zoom = null,
  until = null,
}: {
  daily: DailyCount[]
  zoom?: PeriodDays | null
  until?: string | null
}) {
  const tokens = useChartTokens()
  const spec = useMemo(() => dailyScansSpec(daily, tokens, { zoom, until }), [daily, tokens, zoom, until])

  if (daily.length === 0) return <p className="status">No scans yet.</p>

  return (
    <>
      <VegaEmbed
        className="chart"
        spec={spec}
        options={{ actions: false, renderer: 'svg', tooltip: { theme: tokens.scheme } }}
        role="img"
        aria-label="Bar chart of scans per day. Drag across the lower overview chart to zoom in."
      />
      <DailyCountsTable daily={daily} />
    </>
  )
}

function DailyCountsTable({ daily }: { daily: DailyCount[] }) {
  const newestFirst = useMemo(() => [...daily].reverse(), [daily])
  return (
    <details>
      <summary>Show scans per day as a table</summary>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th className="numeric">Scans</th>
            </tr>
          </thead>
          <tbody>
            {newestFirst.map(({ date, count }) => (
              <tr key={date}>
                <td>{date}</td>
                <td className="numeric">{count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}
