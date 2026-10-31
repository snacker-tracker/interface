// PROTOTYPE, throwaway: a floating bar cycling ?variant= through `variants`. Hidden in production builds.
import { useEffect } from 'react'
import { useSearchParams } from 'react-router'

export function PrototypeSwitcher({ variants }: { variants: Record<string, string> }) {
  const [params, setParams] = useSearchParams()
  const keys = Object.keys(variants)
  const current = params.get('variant') ?? keys[0]
  const index = Math.max(0, keys.indexOf(current))

  const go = (step: number) => {
    const next = keys[(index + step + keys.length) % keys.length]
    setParams((p) => ({ ...Object.fromEntries(p), variant: next }), { replace: true })
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null
      if (target && (target.closest('input, textarea, [contenteditable]') !== null)) return
      if (event.key === 'ArrowLeft') go(-1)
      if (event.key === 'ArrowRight') go(1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (import.meta.env.PROD) return null
  return (
    <div
      style={{
        position: 'fixed',
        bottom: 16,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '8px 14px',
        borderRadius: 999,
        background: '#111',
        color: '#fff',
        boxShadow: '0 4px 16px rgba(0,0,0,0.35)',
        fontSize: 14,
      }}
    >
      <button type="button" onClick={() => go(-1)} aria-label="Previous variant">←</button>
      <span>
        {keys[index]} ({variants[keys[index]]})
      </span>
      <button type="button" onClick={() => go(1)} aria-label="Next variant">→</button>
    </div>
  )
}
