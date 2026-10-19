import { useEffect, useState } from 'react'

import { type MetaData, metaDataPath, type ScannersData, scannersDataPath, useJson } from '../data'
import { useSelectedLocation } from '../selectedLocation'

/** A scanner sends a heartbeat every few minutes; an hour without one means something is wrong. */
const OFFLINE_AFTER_MS = 60 * 60 * 1000

/** Status is never colour alone: each state has an icon and a label too. */
const STATES = {
  online: { icon: '✓', label: 'Online' },
  offline: { icon: '✕', label: 'Offline' },
} as const

/** The scanners within the selected location, and when the data was built. */
export function ScannerStatusWidget() {
  const [location] = useSelectedLocation()
  const scanners = useJson<ScannersData>(scannersDataPath(location))
  const meta = useJson<MetaData>(metaDataPath())
  const now = useNow()

  return (
    <section className="scanner-status" aria-label="Scanner status">
      {scanners.status === 'ready' &&
        (scanners.data.scanners.length > 0 ? (
          <ul>
            {scanners.data.scanners.map((scanner) => {
              const state = now - Date.parse(scanner.last_seen) > OFFLINE_AFTER_MS ? 'offline' : 'online'
              return (
                <li key={scanner.name} className={state}>
                  <span className="scanner-state">
                    <span className="scanner-icon" aria-hidden="true">{STATES[state].icon}</span>{' '}
                    {STATES[state].label}
                  </span>{' '}
                  <span className="scanner-name">{scanner.name}</span>{' '}
                  <span className="scanner-detail">
                    seen <Ago iso={scanner.last_seen} now={now} /> · {scanner.app_version}
                  </span>
                </li>
              )
            })}
          </ul>
        ) : (
          <p className="scanner-detail">No scanners here</p>
        ))}
      {(scanners.status === 'missing' || scanners.status === 'error') && (
        <p className="scanner-detail">Scanner status unavailable</p>
      )}
      {meta.status === 'ready' && (
        <p className="scanner-detail">
          Data built <Ago iso={meta.data.generated_at} now={now} /> ({builtAt.format(new Date(meta.data.generated_at))})
        </p>
      )}
    </section>
  )
}

/** "3 minutes ago", with the exact time on hover. */
function Ago({ iso, now }: { iso: string; now: number }) {
  const then = new Date(iso)
  return (
    <time dateTime={iso} title={then.toLocaleString()}>
      {ago(then.getTime(), now)}
    </time>
  )
}

/** The current time, refreshed every minute so "X ago" and offline flags stay current. */
function useNow(): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60 * 1000)
    return () => window.clearInterval(timer)
  }, [])
  return now
}

/** "19 Oct, 13:05" in the viewer's time zone. */
const builtAt = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })

const relative = new Intl.RelativeTimeFormat('en', { numeric: 'auto' })

/** "3 minutes ago", "2 hours ago", "yesterday". A time ahead of the browser's clock reads as now. */
function ago(then: number, now: number): string {
  const minutes = Math.round((Math.min(then, now) - now) / 60_000)
  if (Math.abs(minutes) < 60) return relative.format(minutes, 'minute')
  const hours = Math.round(minutes / 60)
  if (Math.abs(hours) < 24) return relative.format(hours, 'hour')
  return relative.format(Math.round(hours / 24), 'day')
}
