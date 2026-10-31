// The run file `stepdag report` writes: one finished run of the stepdag graph that builds the data.
// Its shape is stepdag's, not the data contract's (PRD.md §7), so it lives outside data/.

export type AssetStatus = 'computed' | 'skipped' | 'not_selected' | 'failed' | 'running' | 'not_run'

export type RunAsset = {
  name: string
  /** Which level of the graph it runs in, from 0; a level's assets run in parallel. */
  level: number
  deps: string[]
  io_manager: string
  status: AssetStatus
  started_at: string | null
  stopped_at: string | null
  /** The IO manager's version of the value, such as a Delta table's version; null when it has none. */
  version: number | string | null
  /** The run that wrote the value: this one when it was computed, an earlier one when it skipped. */
  written_by: string | null
}

export type RunFile = {
  graph: string
  run: {
    id: string
    status: 'SUCCEEDED' | 'FAILED' | 'TIMED_OUT' | 'ABORTED' | 'RUNNING'
    started_at: string
    stopped_at: string | null
    config: Record<string, unknown>
    error: { step: string | null; error: string | null; cause: string | null } | null
  }
  levels: string[][]
  assets: RunAsset[]
}

export const latestRunPath = () => '/pipeline/latest.json'

/** How long a step or run took, in seconds, or null if it hasn't both started and stopped. */
export function seconds(started: string | null, stopped: string | null): number | null {
  if (!started || !stopped) return null
  return (Date.parse(stopped) - Date.parse(started)) / 1000
}

/** "3.2 s", or "2 min 5 s" from a minute up. */
export function formatSeconds(total: number): string {
  if (total < 60) return `${total.toFixed(1)} s`
  const minutes = Math.floor(total / 60)
  return `${minutes} min ${Math.round(total - minutes * 60)} s`
}
