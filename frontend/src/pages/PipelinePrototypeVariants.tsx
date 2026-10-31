// PROTOTYPE, throwaway (branch prototype/pipeline-react-flow). Question: does React Flow with an
// auto-layout (ELK) make the run graph readable enough to be stepdag's viewer?
// Three variants of the /pipeline graph, switchable via ?variant=: A is the Vega-Lite baseline,
// B is React Flow + ELK layered left to right, C is React Flow placing nodes on a time axis.
import '@xyflow/react/dist/style.css'

import { Background, Controls, type Edge, Handle, MiniMap, type Node, type NodeProps, Position, ReactFlow } from '@xyflow/react'
import ELK from 'elkjs/lib/elk.bundled.js'
import { useEffect, useState } from 'react'

import { STATUS_LABELS } from '../components/pipelineSpecs'
import { type AssetStatus, formatSeconds, type RunAsset, type RunFile, seconds } from '../pipeline'

const elk = new ELK()

const STATUS_COLOUR: Record<AssetStatus, string> = {
  computed: 'var(--nutri-score-a)',
  skipped: 'var(--grid)',
  not_selected: 'var(--grid)',
  failed: 'var(--nutri-score-e)',
  running: 'var(--nutri-score-c)',
  not_run: 'var(--text-secondary)',
}

type AssetData = { asset: RunAsset; width: number }

function details(asset: RunAsset): string {
  const took = seconds(asset.started_at, asset.stopped_at)
  const version = asset.version === null ? '' : typeof asset.version === 'number' ? `v${asset.version}` : asset.version
  return [version, took === null ? '' : formatSeconds(took)].filter((part) => part !== '').join(' · ')
}

/** B's node: a card with a status stripe, the asset's name, its status, version and duration. */
function AssetCard({ data }: NodeProps<Node<AssetData>>) {
  const { asset } = data
  return (
    <div
      style={{
        width: data.width,
        boxSizing: 'border-box',
        background: 'var(--surface-1)',
        color: 'var(--text-primary)',
        border: '1px solid var(--border)',
        borderLeft: `6px solid ${STATUS_COLOUR[asset.status]}`,
        borderRadius: 6,
        padding: '6px 10px',
        fontSize: 12,
        lineHeight: 1.35,
      }}
      title={`${asset.name}: ${STATUS_LABELS[asset.status]}${asset.written_by ? `, written by ${asset.written_by}` : ''}`}
    >
      <Handle type="target" position={Position.Left} style={{ visibility: 'hidden' }} />
      <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{asset.name}</div>
      <div style={{ color: 'var(--text-secondary)' }}>
        {STATUS_LABELS[asset.status]}
        {details(asset) && <> · {details(asset)}</>}
      </div>
      <Handle type="source" position={Position.Right} style={{ visibility: 'hidden' }} />
    </div>
  )
}

/** C's node: a bar as long as the step took, its name inside, coloured by status. */
function AssetBar({ data }: NodeProps<Node<AssetData>>) {
  const { asset } = data
  return (
    <div
      style={{
        width: data.width,
        height: 26,
        boxSizing: 'border-box',
        background: STATUS_COLOUR[asset.status],
        color: 'black',
        borderRadius: 4,
        padding: '4px 6px',
        fontSize: 11,
        whiteSpace: 'nowrap',
        overflow: 'visible',
      }}
      title={`${asset.name}: ${STATUS_LABELS[asset.status]} ${details(asset)}`}
    >
      <Handle type="target" position={Position.Left} style={{ visibility: 'hidden' }} />
      <span style={{ fontWeight: 600 }}>{asset.name}</span> <span style={{ opacity: 0.75 }}>{details(asset)}</span>
      <Handle type="source" position={Position.Right} style={{ visibility: 'hidden' }} />
    </div>
  )
}

const nodeTypes = { card: AssetCard, bar: AssetBar }

function edgesOf(run: RunFile, animated: boolean): Edge[] {
  return run.assets.flatMap((asset) =>
    asset.deps.map((dep) => ({
      id: `${dep}->${asset.name}`,
      source: dep,
      target: asset.name,
      type: 'smoothstep',
      animated: animated && asset.status === 'running',
      style: { stroke: 'var(--text-secondary)', strokeWidth: 1.2, opacity: 0.6 },
    })),
  )
}

const CARD = { width: 210, height: 46 }

/** ELK's layered layout, left to right: positions for every asset, crossings minimised. */
async function layered(run: RunFile, width: number, height: number) {
  const graph = await elk.layout({
    id: 'run',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'RIGHT',
      'elk.layered.spacing.nodeNodeBetweenLayers': '70',
      'elk.spacing.nodeNode': '14',
      'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
    },
    children: run.assets.map((asset) => ({ id: asset.name, width, height })),
    edges: run.assets.flatMap((asset) => asset.deps.map((dep) => ({ id: `${dep}->${asset.name}`, sources: [dep], targets: [asset.name] }))),
  })
  return new Map((graph.children ?? []).map((child) => [child.id, { x: child.x ?? 0, y: child.y ?? 0 }]))
}

function Canvas({ nodes, edges, height }: { nodes: Node<AssetData>[]; edges: Edge[]; height: number }) {
  return (
    <div style={{ height, border: '1px solid var(--border)', borderRadius: 8 }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
        colorMode="system"
      >
        <Background gap={24} />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </div>
  )
}

export function VariantB({ run }: { run: RunFile }) {
  const [nodes, setNodes] = useState<Node<AssetData>[]>([])
  useEffect(() => {
    void layered(run, CARD.width, CARD.height).then((at) =>
      setNodes(
        run.assets.map((asset) => ({
          id: asset.name,
          type: 'card',
          position: at.get(asset.name) ?? { x: 0, y: 0 },
          data: { asset, width: CARD.width },
        })),
      ),
    )
  }, [run])
  return <Canvas nodes={nodes} edges={edgesOf(run, true)} height={560} />
}

/** Pixels per second of the run, so the whole run is about 1,600 px wide. */
function scaleOf(run: RunFile): number {
  const total = seconds(run.run.started_at, run.run.stopped_at) ?? 60
  return 1600 / Math.max(total, 1)
}

export function VariantC({ run }: { run: RunFile }) {
  const [nodes, setNodes] = useState<Node<AssetData>[]>([])
  useEffect(() => {
    const perSecond = scaleOf(run)
    const start = Date.parse(run.run.started_at)
    // ELK only orders the rows (its y), so related assets sit near each other; x is time.
    void layered(run, 120, 26).then((at) => {
      const rows = [...run.assets].sort((a, b) => (at.get(a.name)?.y ?? 0) - (at.get(b.name)?.y ?? 0) || a.level - b.level)
      setNodes(
        rows.map((asset, row) => {
          const begin = asset.started_at ? (Date.parse(asset.started_at) - start) / 1000 : 0
          const took = seconds(asset.started_at, asset.stopped_at) ?? 0
          return {
            id: asset.name,
            type: 'bar',
            position: { x: begin * perSecond, y: row * 34 },
            data: { asset, width: Math.max(took * perSecond, 6) },
          }
        }),
      )
    })
  }, [run])
  return (
    <>
      <p className="panel-hint">
        Each bar starts when its step started and is as long as it took; lines join each asset to the ones made from it.
      </p>
      <Canvas nodes={nodes} edges={edgesOf(run, false)} height={Math.max(300, run.assets.length * 34 + 80)} />
    </>
  )
}
