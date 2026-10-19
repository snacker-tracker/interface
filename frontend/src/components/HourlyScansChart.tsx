import { useMemo } from 'react'
import { VegaEmbed } from 'react-vega'

import type { HourlyCount } from '../contract'
import { useChartTokens } from '../theme'
import { hourlyScansSpec } from './hourlyScansSpec'

/** Scans per hour of the day in office time, with a table view of the same counts. */
export function HourlyScansChart({ hourly }: { hourly: HourlyCount[] }) {
  const tokens = useChartTokens()
  const spec = useMemo(() => hourlyScansSpec(hourly, tokens), [hourly, tokens])

  return (
    <>
      <VegaEmbed
        className="chart"
        spec={spec}
        options={{ actions: false, renderer: 'svg', tooltip: { theme: tokens.scheme } }}
        role="img"
        aria-label="Bar chart of scans per hour of the day, in office time."
      />
      <details>
        <summary>Show scans per hour as a table</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Hour</th>
                <th className="numeric">Scans</th>
              </tr>
            </thead>
            <tbody>
              {hourly.map(({ hour, count }) => (
                <tr key={hour}>
                  <td>{String(hour).padStart(2, '0')}:00</td>
                  <td className="numeric">{count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  )
}
