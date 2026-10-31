// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import App from './App'
import { CONTRACT_VERSION } from './contract'

// Serves meta.json at the given contract version, and any `extra` files; every other file is missing.
function serveData(contractVersion: number, extra: Record<string, unknown> = {}) {
  vi.stubGlobal('fetch', async (path: string) =>
    path === '/data/meta.json'
      ? Response.json({ contract_version: contractVersion })
      : path in extra
        ? Response.json(extra[path])
        : new Response(null, { status: 404 }),
  )
}

beforeEach(() => serveData(CONTRACT_VERSION))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function visit(url: string) {
  window.history.pushState({}, '', url)
  render(<App />)
}

async function expectLocalBuildFooter() {
  const footer = await screen.findByRole('contentinfo')
  expect(footer.textContent).toBe('snacker-tracker/interface local build')
  expect(within(footer).queryAllByRole('link')).toEqual([])
}

test.each(['/', '/codes/5000159484695', '/scanners', '/pipeline'])('%s names the interface build in its footer', async (url) => {
  visit(url)
  await expectLocalBuildFooter()
})

test('data out of step with the interface still shows the footer', async () => {
  serveData(CONTRACT_VERSION + 1)
  visit('/')
  await screen.findByRole('heading', { name: 'Data and interface are out of step' })
  await expectLocalBuildFooter()
})

test('the pipeline page says when no run has been recorded', async () => {
  visit('/pipeline')
  await screen.findByText('No run has been recorded.')
})

test("the pipeline page names the latest run's outcome and its failed step", async () => {
  // jsdom has no matchMedia, which the charts' theme listens to.
  vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener() {}, removeEventListener() {} }))
  serveData(CONTRACT_VERSION, {
    '/pipeline/latest.json': {
      graph: 'snacker.graph.definitions:defs',
      run: {
        id: 'run-7',
        status: 'FAILED',
        started_at: '2026-10-31T11:09:04.803000+00:00',
        stopped_at: '2026-10-31T11:10:04.803000+00:00',
        config: { download: true },
        error: { step: 'products', error: 'StepFailed', cause: 'products: no copy' },
      },
      levels: [['products']],
      assets: [
        {
          name: 'products',
          level: 0,
          deps: [],
          io_manager: 'delta',
          status: 'failed',
          started_at: '2026-10-31T11:09:05.000000+00:00',
          stopped_at: null,
          version: null,
          written_by: null,
        },
      ],
    },
  })
  visit('/pipeline')
  const outcome = await screen.findByText('Failed', { selector: 'strong' })
  expect(outcome.parentElement?.textContent).toContain('run run-7')
  expect(outcome.parentElement?.textContent).toContain('took 1 min 0 s')
  expect(outcome.parentElement?.textContent).toContain('{"download":true}')
  await screen.findByText('products failed: StepFailed', { exact: false })
})
