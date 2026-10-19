// The selected location lives in the browser URL as `?location=`, so links keep the filter.
import { useCallback } from 'react'
import { useSearchParams } from 'react-router'

export const ALL_LOCATIONS = 'all'
export const LOCATION_SEPARATOR = ':'
const PARAM = 'location'

export function useSelectedLocation(): [string, (location: string) => void] {
  const [searchParams, setSearchParams] = useSearchParams()
  const location = searchParams.get(PARAM) || ALL_LOCATIONS

  const select = useCallback(
    (next: string) =>
      setSearchParams((params) => {
        // `all` is the default, so it's left out of the URL.
        if (next === ALL_LOCATIONS) params.delete(PARAM)
        else params.set(PARAM, next)
        return params
      }),
    [setSearchParams],
  )

  return [location, select]
}
