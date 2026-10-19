// Reads the colour tokens defined in index.css so charts follow the light/dark theme.
import { useEffect, useState } from 'react'
import type { Config } from 'vega-lite'

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

/** The Vega-Lite config every chart shares: fonts, recessive axes and grid, tooltips. */
export function chartConfig(tokens: ChartTokens): Config {
  return {
    font: 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
    view: { stroke: null },
    axis: {
      domainColor: tokens.grid,
      gridColor: tokens.grid,
      gridWidth: 1,
      tickColor: tokens.grid,
      labelColor: tokens.textSecondary,
      titleColor: tokens.textSecondary,
      labelFontSize: 11,
      titleFontWeight: 'normal',
    },
    axisX: { grid: false },
    mark: { tooltip: true },
    selection: {
      interval: { mark: { fill: tokens.textSecondary, fillOpacity: 0.15, stroke: tokens.textSecondary } },
    },
  }
}
