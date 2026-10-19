import type { ScanRow } from '../data'

// Shown in UTC until scan rows carry the office's local time (ticket 04).
const timeFormat = new Intl.DateTimeFormat('en-GB', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'UTC',
})

export function RecentScans({ scans }: { scans: ScanRow[] }) {
  if (scans.length === 0) return <p className="status">No scans yet.</p>

  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>When (UTC)</th>
            <th>Location</th>
            <th>Code</th>
          </tr>
        </thead>
        <tbody>
          {scans.map((scan, i) => (
            <tr key={`${scan.scanned_at}-${scan.code}-${i}`}>
              <td>
                <time dateTime={scan.scanned_at}>{timeFormat.format(new Date(scan.scanned_at))}</time>
              </td>
              <td>{scan.location}</td>
              <td className="code">{scan.code}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
