// Types and fetching for the static JSON written by the backend build (see PRD.md §7).
import { useEffect, useState } from 'react'

export type DailyCount = { date: string; count: number }

/** `hour` is 0-23 in the office time zone; a file always lists all 24. */
export type HourlyCount = { hour: number; count: number }

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

/** The periods top scans are ranked over, in display order (see GLOSSARY.md, Period). */
export const PERIODS = [
  'today',
  'this-work-week',
  'last-7-days',
  'this-month',
  'last-30-days',
  'this-year',
  'last-365-days',
  'all-time',
] as const
export type Period = (typeof PERIODS)[number]

export type TopScan = {
  code: string
  name: string | null
  brands: string | null
  /** Whether OpenFoodFacts has the product. */
  known: boolean
  count: number
  /** Fraction of the period's scans, e.g. 0.25. */
  share: number
}

export type IndexData = {
  location: string
  top_scans: Record<Period, TopScan[]>
  daily: DailyCount[]
  recent: ScanRow[]
}

export type CodeScansData = {
  code: string
  location: string
  daily: DailyCount[]
  hourly: HourlyCount[]
  recent: ScanRow[]
}

export type Product = {
  name: string | null
  brands: string | null
  quantity: string | null
  categories: string[]
  /** OpenFoodFacts's front image (docs/adr/0001); may be slow or gone, so treat it as optional. */
  image_url: string | null
  off_url: string
}

export type ProductData = {
  code: string
  /** Null for an unknown product. */
  product: Product | null
}

export type ScannerStatus = {
  /** The scanner's name, e.g. "rpi-pico-w-01" */
  name: string
  location: string
  app_version: string
  /** UTC time of its latest heartbeat */
  last_seen: string
  /** The latest scan sent with its API key (docs/adr/0002); null if none. */
  last_scan: LastScan | null
}

export type LastScan = {
  /** UTC */
  scanned_at: string
  code: string
  /** Null for an unknown product. */
  product_name: string | null
}

export type ScannersData = { location: string; scanners: ScannerStatus[] }

export type MetaData = {
  /** UTC time the data was built */
  generated_at: string
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
export const metaDataPath = () => dataPath('meta')
export const scannersDataPath = (location: string) => dataPath('scanners', 'by-location', location)
export const indexDataPath = (location: string) => dataPath('index', 'by-location', location)
export const productDataPath = (code: string) => dataPath('codes', code, 'product')
export const codeScansDataPath = (code: string, location: string) =>
  dataPath('codes', code, 'by-location', location)

export type Fetched<T> =
  | { status: 'loading' }
  /** No such file. Pages decide what that means, e.g. a code never scanned at a location. */
  | { status: 'missing' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: T }

class Missing extends Error {}

export function useJson<T>(path: string): Fetched<T> {
  const [result, setResult] = useState<{ path: string; fetched: Fetched<T> }>({
    path,
    fetched: { status: 'loading' },
  })

  useEffect(() => {
    const controller = new AbortController()
    fetch(path, { signal: controller.signal })
      .then((response) => {
        if (response.status === 404) throw new Missing()
        if (!response.ok) throw new Error(`${response.status} ${response.statusText}`)
        // Dev servers and SPA hosts answer a missing file with index.html and a 200.
        if (!response.headers.get('content-type')?.includes('json')) throw new Missing()
        return response.json() as Promise<T>
      })
      .then((data) => setResult({ path, fetched: { status: 'ready', data } }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        const fetched: Fetched<T> =
          error instanceof Missing ? { status: 'missing' } : { status: 'error', message: String(error) }
        setResult({ path, fetched })
      })
    return () => controller.abort()
  }, [path])

  // A result for a previous path is stale: report loading until this path's arrives.
  return result.path === path ? result.fetched : { status: 'loading' }
}
