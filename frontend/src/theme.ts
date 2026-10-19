// Reads the colour tokens defined in index.css so charts follow the light/dark theme.
import { useEffect, useState } from 'react'

export type ChartTokens = {
  textSecondary: string
  grid: string
  series1: string
  scheme: 'light' | 'dark'
}

const DARK_QUERY = '(prefers-color-scheme: dark)'

function readTokens(): ChartTokens {
  const styles = getComputedStyle(document.documentElement)
  const token = (name: string) => styles.getPropertyValue(name).trim()
  return {
    textSecondary: token('--text-secondary'),
    grid: token('--grid'),
    series1: token('--series-1'),
    scheme: token('color-scheme') === 'dark' ? 'dark' : 'light',
  }
}

export function useChartTokens(): ChartTokens {
  const [tokens, setTokens] = useState(readTokens)
  useEffect(() => {
    const media = window.matchMedia(DARK_QUERY)
    const update = () => setTokens(readTokens())
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
  return tokens
}
