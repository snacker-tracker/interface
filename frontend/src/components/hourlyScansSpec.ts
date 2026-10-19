import type { VisualizationSpec } from 'vega-embed'

import type { HourlyCount } from '../contract'
import { type ChartTokens, chartConfig } from '../theme'

/** Vega-Lite spec for scans per hour of the day: always 24 bars, 00 to 23, in office time. */
export function hourlyScansSpec(hourly: HourlyCount[], tokens: ChartTokens): VisualizationSpec {
  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
    width: 'container',
    height: 180,
    autosize: { type: 'fit-x', contains: 'padding' },
    background: 'transparent',
    data: { values: hourly },
    transform: [{ calculate: "pad(datum.hour, 2, '0', 'left') + ':00'", as: 'label' }],
    mark: { type: 'bar', color: tokens.series1, cornerRadiusEnd: 4, width: { band: 0.8 } },
    encoding: {
      x: {
        field: 'hour',
        type: 'ordinal',
        title: null,
        // Label every third hour so the axis stays readable on a phone.
        axis: { labelAngle: 0, labelExpr: "datum.value % 3 == 0 ? pad(datum.value, 2, '0', 'left') : ''" },
      },
      y: { field: 'count', type: 'quantitative', title: 'Scans', axis: { tickMinStep: 1 } },
      tooltip: [
        { field: 'label', title: 'Hour' },
        { field: 'count', type: 'quantitative', title: 'Scans' },
      ],
    },
    config: chartConfig(tokens),
  }
}
