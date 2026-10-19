import type { VisualizationSpec } from 'vega-embed'

import type { DailyCount } from '../data'
import type { ChartTokens } from '../theme'

/**
 * Vega-Lite spec for scans per day: a detail chart on top, and below it an overview of
 * the whole range where dragging a brush zooms the detail chart in. Dates are calendar
 * days already bucketed by the backend, so they're handled as UTC to avoid browser
 * timezone shifts.
 */
export function dailyScansSpec(daily: DailyCount[], tokens: ChartTokens): VisualizationSpec {
  const x = {
    field: 'date',
    timeUnit: 'utcyearmonthdate',
    title: null,
    // Short tick labels: "2023" on year boundaries, "Sep" on months, "08 Jan" on days.
    axis: {
      labelOverlap: true,
      labelExpr:
        "utcmonth(datum.value) == 0 && utcdate(datum.value) == 1 ? utcFormat(datum.value, '%Y')" +
        " : utcdate(datum.value) == 1 ? utcFormat(datum.value, '%b')" +
        " : utcFormat(datum.value, '%d %b')",
    },
  } as const
  const bar = {
    type: 'bar',
    color: tokens.series1,
    // No rounded data-ends: most days are sub-pixel wide, and Vega-Lite's per-bar
    // corner clipping stopped the brush from zooming the detail view.
    // A gap relative to the day's slot: a fixed 2px gap would swallow the bars when
    // years of days share a few hundred pixels, but still separates them when zoomed in.
    width: { band: 0.85 },
  } as const

  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
    // Each sub-view fills the container: a top-level width doesn't reach concatenated views.
    autosize: { type: 'fit-x', contains: 'padding' },
    background: 'transparent',
    data: { values: daily },
    vconcat: [
      {
        width: 'container',
        height: 220,
        mark: bar,
        // Only the brushed days, so the y-axis rescales to them (all days when no brush).
        transform: [{ filter: { param: 'brush' } }],
        encoding: {
          x: { ...x, scale: { domain: { param: 'brush' } } },
          y: { field: 'count', type: 'quantitative', title: 'Scans', axis: { tickMinStep: 1 } },
          tooltip: [
            { field: 'date', timeUnit: 'utcyearmonthdate', title: 'Date', format: '%a %d %b %Y' },
            { field: 'count', type: 'quantitative', title: 'Scans' },
          ],
        },
      },
      {
        width: 'container',
        height: 60,
        mark: { ...bar, width: { band: 1 } },
        params: [{ name: 'brush', select: { type: 'interval', encodings: ['x'] } }],
        encoding: {
          x,
          y: { field: 'count', type: 'quantitative', title: null, axis: { tickCount: 2, grid: false } },
        },
      },
    ],
    config: {
      font: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
      view: { stroke: null },
      axis: {
        domainColor: tokens.grid,
        gridColor: tokens.grid,
        gridWidth: 1,
        tickColor: tokens.grid,
        labelColor: tokens.textSecondary,
        titleColor: tokens.textSecondary,
        labelFontSize: 11,
        titleFontWeight: 'normal',
      },
      axisX: { grid: false },
      mark: { tooltip: true },
      selection: { interval: { mark: { fill: tokens.textSecondary, fillOpacity: 0.15, stroke: tokens.textSecondary } } },
    },
  }
}
