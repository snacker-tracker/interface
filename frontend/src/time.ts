// Relative times and a ticking clock, shared by everything that says "X ago".
import { useEffect, useState } from 'react'

/** The current time, refreshed every minute so "X ago" and offline flags stay current. */
export function useNow(): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60 * 1000)
    return () => window.clearInterval(timer)
  }, [])
  return now
}

const relative = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

/** "3 minutes ago", "2 hours ago", "yesterday". A time ahead of the browser's clock reads as now. */
export function ago(then: number, now: number): string {
  const minutes = Math.round((Math.min(then, now) - now) / 60_000)
  if (Math.abs(minutes) < 60) return relative.format(minutes, 'minute')
  const hours = Math.round(minutes / 60)
  if (Math.abs(hours) < 24) return relative.format(hours, 'hour')
  return relative.format(Math.round(hours / 24), 'day')
}

/** "19 Oct 2026, 14:05" in the viewer's time zone. */
export const exactTime = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})
