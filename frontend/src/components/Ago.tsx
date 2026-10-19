import { ago, exactTime } from '../time'

/** "3 minutes ago", with the exact time on hover, or underneath when `showExact`. */
export function Ago({ iso, now, showExact = false }: { iso: string; now: number; showExact?: boolean }) {
  const then = new Date(iso)
  return (
    <>
      <time dateTime={iso} title={exactTime.format(then)}>
        {ago(then.getTime(), now)}
      </time>
      {showExact && <span className="exact-time">{exactTime.format(then)}</span>}
    </>
  )
}
