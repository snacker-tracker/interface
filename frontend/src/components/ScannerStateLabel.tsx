import { SCANNER_STATES, type ScannerState } from '../scanners'

/** "✓ Online" / "✕ Offline": the icon carries the colour, the label stays readable. */
export function ScannerStateLabel({ state, label = SCANNER_STATES[state].label }: { state: ScannerState; label?: string }) {
  return (
    <>
      <span className="scanner-icon" aria-hidden="true">{SCANNER_STATES[state].icon}</span> {label}
    </>
  )
}
