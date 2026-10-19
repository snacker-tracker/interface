import type { ScanRow } from '../data'

// One formatter per office time zone; a list rarely spans more than a few.
const formatters = new Map<string, Intl.DateTimeFormat>()

/** "16 Oct 2026, 17:33 GMT+7": the scan's time in its office time zone, with the zone shown. */
function officeTime(scan: ScanRow): string {
  let format = formatters.get(scan.office_time_zone)
  if (!format) {
    format = new Intl.DateTimeFormat('en-GB', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      timeZone: scan.office_time_zone,
      timeZoneName: 'short',
    })
    formatters.set(scan.office_time_zone, format)
  }
  return format.format(new Date(scan.scanned_at))
}

export function RecentScans({ scans }: { scans: ScanRow[] }) {
  if (scans.length === 0) return <p className="status">No scans yet.</p>

  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>When (office time)</th>
            <th>Product</th>
            <th>Location</th>
            <th>Code</th>
          </tr>
        </thead>
        <tbody>
          {scans.map((scan, i) => (
            <tr key={`${scan.scanned_at}-${scan.code}-${i}`}>
              <td>
                <time dateTime={scan.office_time} title={`${scan.scanned_at} (UTC) · ${scan.office_time_zone}`}>
                  {officeTime(scan)}
                </time>
              </td>
              <td className="product">
                <span className={scan.name ? undefined : 'unknown'}>{scan.name ?? 'Unknown product'}</span>
                {scan.brands && <span className="brands">{scan.brands}</span>}
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
