import { PERIODS } from '../contract'
import { PERIOD_LABELS, useSelectedPeriod } from '../selectedPeriod'

/** The index page's period (GLOSSARY.md), which every period-driven section on it follows. */
export function PeriodSelector() {
  const [period, select] = useSelectedPeriod()
  return (
    <div className="period-tabs" role="group" aria-label="Period">
      {PERIODS.map((id) => (
        <button key={id} type="button" aria-pressed={id === period} onClick={() => select(id)}>
          {PERIOD_LABELS[id].tab}
        </button>
      ))}
    </div>
  )
}
