import { expect, test } from 'vitest'

import type { RunAsset, RunFile } from '../pipeline'
import { graphEdges, graphNodes, timelineBars } from './pipelineSpecs'

function asset(name: string, level: number, overrides: Partial<RunAsset> = {}): RunAsset {
  return {
    name,
    level,
    deps: [],
    io_manager: 'delta',
    status: 'computed',
    started_at: '2026-10-31T11:09:21.000000+00:00',
    stopped_at: '2026-10-31T11:09:28.500000+00:00',
    version: null,
    written_by: 'run-2',
    ...overrides,
  }
}

// A small graph: two sources, then one asset made from both.
const RUN: RunFile = {
  graph: 'example:defs',
  run: {
    id: 'run-2',
    status: 'SUCCEEDED',
    started_at: '2026-10-31T11:09:04.803000+00:00',
    stopped_at: '2026-10-31T11:16:07.392000+00:00',
    config: {},
    error: null,
  },
  levels: [['heartbeats', 'scans'], ['scanned']],
  assets: [
    asset('heartbeats', 0, { status: 'skipped', written_by: 'run-1', version: 4 }),
    asset('scans', 0, { version: 12 }),
    asset('scanned', 1, {
      deps: ['scans', 'heartbeats'],
      started_at: '2026-10-31T11:12:48.000000+00:00',
      stopped_at: '2026-10-31T11:14:53.000000+00:00',
    }),
  ],
}

test('each asset is a node in its level and row, labelled with its version and duration', () => {
  expect(graphNodes(RUN)).toEqual([
    {
      name: 'heartbeats',
      level: 0,
      row: 0,
      status: 'skipped',
      statusLabel: 'Skipped (unchanged)',
      version: 'v4',
      duration: '7.5 s',
      label: 'heartbeats\nv4 · 7.5 s',
    },
    {
      name: 'scans',
      level: 0,
      row: 1,
      status: 'computed',
      statusLabel: 'Computed',
      version: 'v12',
      duration: '7.5 s',
      label: 'scans\nv12 · 7.5 s',
    },
    {
      name: 'scanned',
      level: 1,
      row: 0,
      status: 'computed',
      statusLabel: 'Computed',
      version: '',
      duration: '2 min 5 s',
      label: 'scanned\n2 min 5 s',
    },
  ])
})

test('each parent is joined to its child', () => {
  expect(graphEdges(RUN)).toEqual([
    { from: 'scans', to: 'scanned', x: 0, y: 1, x2: 1, y2: 0 },
    { from: 'heartbeats', to: 'scanned', x: 0, y: 0, x2: 1, y2: 0 },
  ])
})

test('steps that never ran have no bar in the timeline, and bars run in the order the graph does', () => {
  const run: RunFile = {
    ...RUN,
    assets: [...RUN.assets, asset('site_tree', 2, { status: 'not_run', started_at: null, stopped_at: null })],
    levels: [...RUN.levels, ['site_tree']],
  }

  expect(timelineBars(run).map((bar) => [bar.name, bar.duration])).toEqual([
    ['heartbeats', '7.5 s'],
    ['scans', '7.5 s'],
    ['scanned', '2 min 5 s'],
  ])
})
