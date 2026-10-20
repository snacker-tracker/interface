import { type Period, PERIODS } from '../contract'
import { PERIOD_LABELS } from '../selectedPeriod'

/** The index page's period (GLOSSARY.md), which every period-driven section on it follows. */
export function PeriodSelector({ period, select }: { period: Period; select: (period: Period) => void }) {
  return (
    <div className="period-selector" role="group" aria-label="Period">
      {PERIODS.map((id) => (
        <button key={id} type="button" aria-pressed={id === period} onClick={() => select(id)}>
          {PERIOD_LABELS[id].label}
        </button>
      ))}
    </div>
  )
}
