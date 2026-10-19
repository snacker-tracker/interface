// The top-scans period lives in the browser URL as `?period=`, so a shared link opens on it.
import { useCallback } from 'react'
import { useSearchParams } from 'react-router'

import { type Period, PERIODS } from './data'

export const DEFAULT_PERIOD: Period = 'last-30-days'
const PARAM = 'period'

const isPeriod = (value: string | null): value is Period => PERIODS.some((period) => period === value)

export function useSelectedPeriod(): [Period, (period: Period) => void] {
  const [searchParams, setSearchParams] = useSearchParams()
  const value = searchParams.get(PARAM)
  // An unknown value (an old or mistyped link) falls back to the default.
  const period = isPeriod(value) ? value : DEFAULT_PERIOD

  const select = useCallback(
    (next: Period) =>
      setSearchParams((params) => {
        // The default is left out of the URL; other parameters such as ?location= are kept.
        if (next === DEFAULT_PERIOD) params.delete(PARAM)
        else params.set(PARAM, next)
        return params
      }),
    [setSearchParams],
  )

  return [period, select]
}

const UNKNOWN_PARAM = 'unknown'

/** Whether Top scans shows unknown products only: `?unknown=1`, absent means off. */
export function useUnknownOnly(): [boolean, (on: boolean) => void] {
  const [searchParams, setSearchParams] = useSearchParams()
  const on = searchParams.get(UNKNOWN_PARAM) === '1'

  const set = useCallback(
    (next: boolean) =>
      setSearchParams((params) => {
        if (next) params.set(UNKNOWN_PARAM, '1')
        else params.delete(UNKNOWN_PARAM)
        return params
      }),
    [setSearchParams],
  )

  return [on, set]
}
