// Types and fetching for the static JSON written by the backend build (see PRD.md §7).
import { useEffect, useState } from 'react'

export type DailyCount = { date: string; count: number }

export type ScanRow = {
  code: string
  /** The product's name; null for an unknown product. */
  name: string | null
  brands: string | null
  location: string
  /** UTC, e.g. "2026-10-16T10:33:45Z" */
  scanned_at: string
  /** The same moment in the office time zone, e.g. "2026-10-16T17:33:45+07:00" */
  office_time: string
  /** IANA name, e.g. "Asia/Bangkok" */
  office_time_zone: string
}

export type IndexData = {
  location: string
  daily: DailyCount[]
  recent: ScanRow[]
}

export type LocationsData = {
  /** The selectable locations: `all`, then every prefix of every scanned location, in path order. */
  locations: { id: string }[]
}

/**
 * A location or code as the backend names its file: percent-encoded like
 * encodeURIComponent, except that `:` stays readable (`thailand:bangkok`).
 */
function fileName(value: string): string {
  return encodeURIComponent(value).replaceAll('%3A', ':')
}

/**
 * Path to a data file. Static servers decode the request path before looking the
 * file up, so each file name is encoded once more to land on its literal `%` escapes.
 * `:` stays literal in the request too: Vite's dev server doesn't match `%3A` to it.
 */
export function dataPath(...segments: string[]): string {
  return '/data/' + segments.map((s) => fileName(fileName(s))).join('/') + '.json'
}

export const locationsDataPath = () => dataPath('locations')
export const indexDataPath = (location: string) => dataPath('index', 'by-location', location)

export type Fetched<T> =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: T }

export function useJson<T>(path: string): Fetched<T> {
  const [result, setResult] = useState<{ path: string; fetched: Fetched<T> }>({
    path,
    fetched: { status: 'loading' },
  })

  useEffect(() => {
    const controller = new AbortController()
    fetch(path, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
        // Dev servers and SPA hosts answer a missing file with index.html and a 200.
        if (!response.headers.get('content-type')?.includes('json')) throw new Error('not found')
        return response.json() as Promise<T>
      })
      .then((data) => setResult({ path, fetched: { status: 'ready', data } }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        setResult({ path, fetched: { status: 'error', message: String(error) } })
      })
    return () => controller.abort()
  }, [path])

  // A result for a previous path is stale: report loading until this path's arrives.
  return result.path === path ? result.fetched : { status: 'loading' }
}
