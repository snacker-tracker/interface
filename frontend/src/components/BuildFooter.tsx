import type { BuildStamp } from '../buildStamp'

/** Names the build of the interface on every page: its commit and Actions run, or a local build. */
export function BuildFooter({ stamp }: { stamp: BuildStamp | null }) {
  if (!stamp) return <footer className="app-footer">snacker-tracker/interface local build</footer>
  return (
    <footer className="app-footer">
      {stamp.repository} <a href={stamp.commitUrl}>{stamp.sha.slice(0, 7)}</a> (
      <a href={stamp.runUrl}>run #{stamp.runNumber}</a>)
    </footer>
  )
}
