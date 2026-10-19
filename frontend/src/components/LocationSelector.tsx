import { type LocationsData, locationsDataPath, useJson } from '../data'
import { ALL_LOCATIONS, LOCATION_SEPARATOR, useSelectedLocation } from '../selectedLocation'

/** Lists `all` and every location prefix, indented by depth so the hierarchy reads at a glance. */
export function LocationSelector() {
  const [selected, select] = useSelectedLocation()
  const locations = useJson<LocationsData>(locationsDataPath())

  const ids = locations.status === 'ready' ? locations.data.locations.map(({ id }) => id) : [selected]
  // Keep an unknown `?location=` visible rather than silently showing another value.
  const options = ids.includes(selected) ? ids : [...ids, selected]

  return (
    <label className="location-selector">
      <span>Location</span>
      <select value={selected} onChange={(event) => select(event.target.value)} disabled={locations.status !== 'ready'}>
        {options.map((id) => (
          <option key={id} value={id} title={id}>
            {optionLabel(id)}
          </option>
        ))}
      </select>
    </label>
  )
}

function optionLabel(id: string): string {
  if (id === ALL_LOCATIONS) return 'All locations'
  const segments = id.split(LOCATION_SEPARATOR)
  // Non-breaking spaces: browsers collapse ordinary leading spaces in <option> text.
  return '\u00a0\u00a0'.repeat(segments.length - 1) + segments[segments.length - 1]
}
