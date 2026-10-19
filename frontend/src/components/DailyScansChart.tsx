import { useMemo } from 'react'
import { VegaEmbed } from 'react-vega'

import type { DailyCount } from '../data'
import { useChartTokens } from '../theme'
import { dailyScansSpec } from './dailyScansSpec'

/** Scans per day, with brush-to-zoom (see `dailyScansSpec`) and a table view of the same data. */
export function DailyScansChart({ daily }: { daily: DailyCount[] }) {
  const tokens = useChartTokens()
  const spec = useMemo(() => dailyScansSpec(daily, tokens), [daily, tokens])

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
