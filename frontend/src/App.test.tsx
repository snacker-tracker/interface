// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import App from './App'
import { CONTRACT_VERSION } from './contract'

// Serves meta.json at the given contract version; every other data file is missing.
function serveData(contractVersion: number) {
  vi.stubGlobal('fetch', async (path: string) =>
    path === '/data/meta.json'
      ? Response.json({ contract_version: contractVersion })
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

test.each(['/', '/codes/5000159484695', '/scanners'])('%s names the interface build in its footer', async (url) => {
  visit(url)
  await expectLocalBuildFooter()
})

test('data out of step with the interface still shows the footer', async () => {
  serveData(CONTRACT_VERSION + 1)
  visit('/')
  await screen.findByRole('heading', { name: 'Data and interface are out of step' })
  await expectLocalBuildFooter()
})
