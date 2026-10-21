import { useMemo } from 'react'
import { VegaEmbed } from 'react-vega'

import type { NutriScoreDistribution } from '../contract'
import { useChartTokens } from '../theme'
import { gradeCounts, nutriScoreSpec } from './nutriScoreSpec'

const percent = new Intl.NumberFormat('en', { style: 'percent' })

/** Scans per Nutri-Score grade (GLOSSARY.md, Nutri-Score distribution), with a table view of the same counts. */
export function NutriScoreChart({ distribution }: { distribution: NutriScoreDistribution }) {
  const tokens = useChartTokens()
  const counts = useMemo(() => gradeCounts(distribution), [distribution])
  const spec = useMemo(() => nutriScoreSpec(counts, tokens), [counts, tokens])

  return (
    <>
      <VegaEmbed
        className="chart"
        spec={spec}
        options={{ actions: false, renderer: 'svg', tooltip: { theme: tokens.scheme } }}
        role="img"
        aria-label="Bar chart of scans per Nutri-Score grade, A to E."
      />
      <details>
        <summary>Show scans per Nutri-Score as a table</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Nutri-Score</th>
                <th className="numeric">Scans</th>
                <th className="numeric">Of graded scans</th>
              </tr>
            </thead>
            <tbody>
              {counts.map(({ grade, meaning, count, share }) => (
                <tr key={grade}>
                  <td title={meaning}>{grade}</td>
                  <td className="numeric">{count}</td>
                  <td className="numeric">{percent.format(share)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  )
}
