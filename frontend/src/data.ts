// Paths and fetching for the static JSON written by the backend build (see PRD.md §7).
// Its types are generated into ./contract.ts.
import { useEffect, useState } from 'react'

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
