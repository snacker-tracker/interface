// Which build of the interface this is. vite.config.ts reads it from GitHub Actions'
// environment at build time and defines it as __BUILD_STAMP__; local builds have none.

declare global {
  /** This build's stamp, defined by vite.config.ts. */
  const __BUILD_STAMP__: BuildStamp | null
}

/** The commit and Actions run a CI build of the interface came from. */
export type BuildStamp = {
  /** `owner/name` on GitHub. */
  repository: string
  sha: string
  commitUrl: string
  runNumber: string
  runUrl: string
}

/**
 * The stamp for a build in GitHub Actions, from the variables Actions sets on every job.
 * Without all of them it's not such a build, and a partial stamp would only make broken links.
 */
export function buildStampFrom(env: Record<string, string | undefined>): BuildStamp | null {
  const { GITHUB_SERVER_URL, GITHUB_REPOSITORY, GITHUB_SHA, GITHUB_RUN_NUMBER, GITHUB_RUN_ID } = env
  if (!GITHUB_SERVER_URL || !GITHUB_REPOSITORY || !GITHUB_SHA || !GITHUB_RUN_NUMBER || !GITHUB_RUN_ID) return null
  const repositoryUrl = `${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}`
  return {
    repository: GITHUB_REPOSITORY,
    sha: GITHUB_SHA,
    commitUrl: `${repositoryUrl}/commit/${GITHUB_SHA}`,
    runNumber: GITHUB_RUN_NUMBER,
    runUrl: `${repositoryUrl}/actions/runs/${GITHUB_RUN_ID}`,
  }
}
