// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'

import { BuildFooter } from './BuildFooter'

afterEach(cleanup)

test('a CI build names its commit and run, each linking to GitHub', () => {
  render(
    <BuildFooter
      stamp={{
        repository: 'snacker-tracker/interface',
        sha: 'fdaa87a1faae87ca264d19b63bc4d5edd78086d3',
        commitUrl: 'https://github.com/snacker-tracker/interface/commit/fdaa87a1faae87ca264d19b63bc4d5edd78086d3',
        runNumber: '412',
        runUrl: 'https://github.com/snacker-tracker/interface/actions/runs/39657128807',
      }}
    />,
  )
  const footer = screen.getByRole('contentinfo')
  expect(footer.textContent).toBe('snacker-tracker/interface fdaa87a (run #412)')
  expect(within(footer).getByRole('link', { name: 'fdaa87a' }).getAttribute('href')).toBe(
    'https://github.com/snacker-tracker/interface/commit/fdaa87a1faae87ca264d19b63bc4d5edd78086d3',
  )
  expect(within(footer).getByRole('link', { name: 'run #412' }).getAttribute('href')).toBe(
    'https://github.com/snacker-tracker/interface/actions/runs/39657128807',
  )
})
