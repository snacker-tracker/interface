// The top-scans period lives in the browser URL as `?period=`, so a shared link opens on it.
import { useCallback } from 'react'
import { useSearchParams } from 'react-router'

import { type Period, PERIODS } from './contract'

export const DEFAULT_PERIOD: Period = 'last-30-days'

/** Each period's tab, and what its lists say when they're empty. */
export const PERIOD_LABELS: Record<Period, { tab: string; empty: string }> = {
  today: { tab: 'Today', empty: 'No scans today' },
  'this-work-week': { tab: 'This work week', empty: 'No scans this work week' },
  'last-7-days': { tab: 'Last 7 days', empty: 'No scans in the last 7 days' },
  'this-month': { tab: 'This month', empty: 'No scans this month' },
  'last-30-days': { tab: 'Last 30 days', empty: 'No scans in the last 30 days' },
  'this-year': { tab: 'This year', empty: 'No scans this year' },
  'last-365-days': { tab: 'Last 365 days', empty: 'No scans in the last 365 days' },
  'all-time': { tab: 'All time', empty: 'No scans yet' },
}

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
