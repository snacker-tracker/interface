import type { ScanRow } from '../contract'
import { ScannedProduct } from './ScannedProduct'

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

/** The latest scans. On a code page (`forOneCode`) every row is the same code, so the product is left out. */
export function RecentScans({ scans, forOneCode = false }: { scans: ScanRow[]; forOneCode?: boolean }) {
  if (scans.length === 0) return <p className="status">No scans yet.</p>

  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>When (office time)</th>
            {!forOneCode && <th>Product</th>}
            <th>Location</th>
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
              {!forOneCode && (
                <td className="product">
                  {/* Scan rows don't say whether a product is known, so a nameless one reads as unknown (§10). */}
                  <ScannedProduct code={scan.code} name={scan.name} brands={scan.brands} known={scan.name !== null} />
                </td>
              )}
              <td>{scan.location}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
