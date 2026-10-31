import { useMemo } from 'react'
import { useSearchParams } from 'react-router'
import { VegaEmbed } from 'react-vega'

import { Ago } from '../components/Ago'
import { pipelineGraphSpec, pipelineTimelineSpec, STATUS_LABELS } from '../components/pipelineSpecs'
import { PrototypeSwitcher } from '../components/PrototypeSwitcher'
import { useJson } from '../data'
import { formatSeconds, latestRunPath, type RunFile, seconds } from '../pipeline'
import { useChartTokens } from '../theme'
import { exactTime, useNow } from '../time'
import { VariantB, VariantC } from './PipelinePrototypeVariants'

// PROTOTYPE (branch prototype/pipeline-react-flow): the graph section in three variants, via ?variant=.
const VARIANTS = { A: 'Vega-Lite by level', B: 'React Flow + ELK', C: 'React Flow on a time axis' }

const OUTCOMES: Record<RunFile['run']['status'], string> = {
  SUCCEEDED: 'Succeeded',
  FAILED: 'Failed',
  TIMED_OUT: 'Timed out',
  ABORTED: 'Aborted',
  RUNNING: 'Running',
}

/** The latest run of the stepdag graph that builds this site's data: its graph and its timeline. */
export function PipelinePage() {
  const latest = useJson<RunFile>(latestRunPath())

  return (
    <section className="panel" aria-labelledby="pipeline-heading">
      <h2 id="pipeline-heading">Pipeline</h2>
      <p className="panel-hint">The latest run of the graph that builds this site's data, one step per asset.</p>
      {latest.status === 'loading' && <p className="status">Loading the latest run…</p>}
      {latest.status === 'missing' && <p className="status">No run has been recorded.</p>}
      {latest.status === 'error' && <p className="status status-error">The latest run is unavailable.</p>}
      {latest.status === 'ready' && <Run run={latest.data} />}
      <PrototypeSwitcher variants={VARIANTS} />
    </section>
  )
}

function Run({ run }: { run: RunFile }) {
  const now = useNow()
  const tokens = useChartTokens()
  const graph = useMemo(() => pipelineGraphSpec(run, tokens), [run, tokens])
  const timeline = useMemo(() => pipelineTimelineSpec(run, tokens), [run, tokens])
  const took = seconds(run.run.started_at, run.run.stopped_at)
  const config = Object.keys(run.run.config).length > 0 ? JSON.stringify(run.run.config) : null
  const embed = { actions: false, renderer: 'svg', tooltip: { theme: tokens.scheme } } as const
  const [params] = useSearchParams()
  const variant = params.get('variant') ?? 'A'

  return (
    <>
      <p>
        <strong>{OUTCOMES[run.run.status]}</strong>: run <code>{run.run.id}</code>, started{' '}
        <Ago iso={run.run.started_at} now={now} /> ({exactTime.format(new Date(run.run.started_at))})
        {took !== null && <>, took {formatSeconds(took)}</>}.
        {config && <> Config: <code>{config}</code>.</>}
      </p>
      {run.run.error && (
        <p className="status status-error">
          {run.run.error.step ?? 'A step'} failed: {run.run.error.error}
          {run.run.error.cause && <> ({run.run.error.cause})</>}
        </p>
      )}
      <h3>Graph</h3>
      {variant === 'A' && (
        <VegaEmbed
          className="chart"
          spec={graph}
          options={embed}
          role="img"
          aria-label="The graph of assets, one column per level, coloured by what each did in this run."
        />
      )}
      {variant === 'B' && <VariantB run={run} />}
      {variant === 'C' && <VariantC run={run} />}
      {variant !== 'C' && (
        <>
          <h3>Timeline</h3>
          <VegaEmbed
            className="chart"
            spec={timeline}
            options={embed}
            role="img"
            aria-label="When each step started and stopped in this run."
          />
        </>
      )}
      <StepsTable run={run} />
    </>
  )
}

function StepsTable({ run }: { run: RunFile }) {
  return (
    <details>
      <summary>Show the steps as a table</summary>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Asset</th>
              <th>Status</th>
              <th>Version</th>
              <th className="numeric">Took</th>
            </tr>
          </thead>
          <tbody>
            {run.assets.map((asset) => {
              const took = seconds(asset.started_at, asset.stopped_at)
              return (
                <tr key={asset.name}>
                  <td>{asset.name}</td>
                  <td>{STATUS_LABELS[asset.status]}</td>
                  <td>{asset.version ?? ''}</td>
                  <td className="numeric">{took === null ? '' : formatSeconds(took)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </details>
  )
}
