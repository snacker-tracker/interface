import type { VisualizationSpec } from 'vega-embed'

import { type AssetStatus, formatSeconds, type RunFile, seconds } from '../pipeline'
import { type ChartTokens, chartConfig } from '../theme'

export const STATUS_LABELS: Record<AssetStatus, string> = {
  computed: 'Computed',
  skipped: 'Skipped (unchanged)',
  not_selected: 'Not selected',
  failed: 'Failed',
  running: 'Running',
  not_run: 'Not run',
}

const STATUSES = Object.keys(STATUS_LABELS) as AssetStatus[]

/** Each status's colour: the Nutri-Score badges' green, amber and red, and the grid's grey for "nothing done". */
function statusColours(tokens: ChartTokens): string[] {
  const colour: Record<AssetStatus, string> = {
    computed: tokens.nutriScore.A,
    skipped: tokens.grid,
    not_selected: tokens.grid,
    failed: tokens.nutriScore.E,
    running: tokens.nutriScore.C,
    not_run: tokens.textSecondary,
  }
  return STATUSES.map((status) => colour[status])
}

const statusScale = (tokens: ChartTokens) => ({ domain: STATUSES, range: statusColours(tokens) })

/** "v12", or "" for an asset whose IO manager keeps no version. */
function versionLabel(version: number | string | null): string {
  return version === null ? '' : typeof version === 'number' ? `v${version}` : version
}

export type GraphNode = {
  name: string
  level: number
  /** Its position within its level, from the top. */
  row: number
  status: AssetStatus
  statusLabel: string
  version: string
  duration: string
  /** Its name, and below it its version and duration. */
  label: string
}

/** Each asset placed by level (a column) and its order in the level (a row). */
export function graphNodes(run: RunFile): GraphNode[] {
  const row = new Map(run.levels.flatMap((level) => level.map((name, i) => [name, i] as const)))
  return run.assets.map((asset) => {
    const took = seconds(asset.started_at, asset.stopped_at)
    const version = versionLabel(asset.version)
    const duration = took === null ? '' : formatSeconds(took)
    const details = [version, duration].filter((part) => part !== '').join(' · ')
    return {
      name: asset.name,
      level: asset.level,
      row: row.get(asset.name) ?? 0,
      status: asset.status,
      statusLabel: STATUS_LABELS[asset.status],
      version,
      duration,
      label: details ? `${asset.name}\n${details}` : asset.name,
    }
  })
}

export type GraphEdge = { from: string; to: string; x: number; y: number; x2: number; y2: number }

/** A line from each parent's node to its child's. */
export function graphEdges(run: RunFile): GraphEdge[] {
  const at = new Map(graphNodes(run).map((node) => [node.name, node]))
  return run.assets.flatMap((asset) =>
    asset.deps.flatMap((dep) => {
      const parent = at.get(dep)
      const child = at.get(asset.name)
      return parent && child ? [{ from: dep, to: asset.name, x: parent.level, y: parent.row, x2: child.level, y2: child.row }] : []
    }),
  )
}

const ROW_HEIGHT = 46

/**
 * Vega-Lite spec for the run's graph: one column per level, a box per asset coloured by its
 * status and labelled with its version and duration, and a line from each parent to its child.
 */
export function pipelineGraphSpec(run: RunFile, tokens: ChartTokens): VisualizationSpec {
  const nodes = graphNodes(run)
  const rows = Math.max(1, ...run.levels.map((level) => level.length))
  const x = { type: 'quantitative' as const, axis: null, scale: { domain: [-0.5, run.levels.length - 0.5] } }
  // Reversed, so the first row is at the top.
  const y = { type: 'quantitative' as const, axis: null, scale: { domain: [rows - 0.5, -0.5] } }

  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
    autosize: { type: 'fit-x', contains: 'padding' },
    background: 'transparent',
    width: 'container',
    height: rows * ROW_HEIGHT,
    layer: [
      {
        data: { values: graphEdges(run) },
        mark: { type: 'rule', color: tokens.grid, strokeWidth: 1.5 },
        encoding: { x: { field: 'x', ...x }, y: { field: 'y', ...y }, x2: { field: 'x2' }, y2: { field: 'y2' } },
      },
      {
        data: { values: nodes },
        transform: [
          { calculate: 'datum.level - 0.42', as: 'left' },
          { calculate: 'datum.level + 0.42', as: 'right' },
          { calculate: 'datum.row - 0.36', as: 'top' },
          { calculate: 'datum.row + 0.36', as: 'bottom' },
        ],
        layer: [
          {
            mark: { type: 'rect', cornerRadius: 4, opacity: 0.85 },
            encoding: {
              x: { field: 'left', ...x },
              x2: { field: 'right' },
              y: { field: 'top', ...y },
              y2: { field: 'bottom' },
              color: { field: 'status', type: 'nominal', scale: statusScale(tokens), legend: null },
              tooltip: [
                { field: 'name', title: 'Asset' },
                { field: 'statusLabel', title: 'Status' },
                { field: 'version', title: 'Version' },
                { field: 'duration', title: 'Took' },
              ],
            },
          },
          {
            mark: { type: 'text', fontSize: 11, lineBreak: '\n', fill: 'black' },
            encoding: {
              x: { field: 'level', ...x },
              y: { field: 'row', ...y },
              text: { field: 'label' },
            },
          },
        ],
      },
    ],
    config: chartConfig(tokens),
  }
}

export type TimelineBar = { name: string; level: number; status: AssetStatus; statusLabel: string; start: string; end: string; duration: string }

/** Each asset that ran, as a bar from its start to its stop, in the order the graph runs them. */
export function timelineBars(run: RunFile): TimelineBar[] {
  return run.assets
    .flatMap((asset) => {
      const took = seconds(asset.started_at, asset.stopped_at)
      return asset.started_at && asset.stopped_at && took !== null
        ? [{
            name: asset.name,
            level: asset.level,
            status: asset.status,
            statusLabel: STATUS_LABELS[asset.status],
            start: asset.started_at,
            end: asset.stopped_at,
            duration: formatSeconds(took),
          }]
        : []
    })
    .sort((a, b) => a.level - b.level || a.start.localeCompare(b.start) || a.name.localeCompare(b.name))
}

/** Vega-Lite spec for the run's timeline: a bar per step that ran, from its start to its stop. */
export function pipelineTimelineSpec(run: RunFile, tokens: ChartTokens): VisualizationSpec {
  const bars = timelineBars(run)
  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
    autosize: { type: 'fit-x', contains: 'padding' },
    background: 'transparent',
    width: 'container',
    height: Math.max(1, bars.length) * 18,
    data: { values: bars },
    mark: { type: 'bar', cornerRadius: 2, height: { band: 0.7 } },
    encoding: {
      y: { field: 'name', type: 'nominal', title: null, sort: bars.map((bar) => bar.name) },
      x: { field: 'start', type: 'temporal', title: null, axis: { format: '%H:%M:%S' } },
      x2: { field: 'end' },
      color: { field: 'status', type: 'nominal', scale: statusScale(tokens), legend: null },
      tooltip: [
        { field: 'name', title: 'Asset' },
        { field: 'statusLabel', title: 'Status' },
        { field: 'start', type: 'temporal', title: 'Started', format: '%H:%M:%S' },
        { field: 'duration', title: 'Took' },
      ],
    },
    config: chartConfig(tokens),
  }
}
