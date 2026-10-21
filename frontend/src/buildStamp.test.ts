import { expect, test } from 'vitest'

import { buildStampFrom } from './buildStamp'

// As GitHub Actions sets them on the pipeline's frontend job.
const actionsEnv = {
  GITHUB_SERVER_URL: 'https://github.com',
  GITHUB_REPOSITORY: 'snacker-tracker/interface',
  GITHUB_SHA: 'fdaa87a1faae87ca264d19b63bc4d5edd78086d3',
  GITHUB_RUN_NUMBER: '412',
  GITHUB_RUN_ID: '39657128807',
}

test('a build in GitHub Actions is stamped with its commit and run', () => {
  expect(buildStampFrom(actionsEnv)).toEqual({
    repository: 'snacker-tracker/interface',
    sha: 'fdaa87a1faae87ca264d19b63bc4d5edd78086d3',
    commitUrl: 'https://github.com/snacker-tracker/interface/commit/fdaa87a1faae87ca264d19b63bc4d5edd78086d3',
    runNumber: '412',
    runUrl: 'https://github.com/snacker-tracker/interface/actions/runs/39657128807',
  })
})

test('a build outside GitHub Actions has no stamp', () => {
  expect(buildStampFrom({})).toBeNull()
})

test.each(Object.keys(actionsEnv))('a build without %s has no stamp, rather than a broken link', (name) => {
  expect(buildStampFrom({ ...actionsEnv, [name]: undefined })).toBeNull()
  expect(buildStampFrom({ ...actionsEnv, [name]: '' })).toBeNull()
})
