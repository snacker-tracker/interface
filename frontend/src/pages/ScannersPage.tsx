import { Link, useLocation } from 'react-router'

import { Ago } from '../components/Ago'
import { ScannerStateLabel } from '../components/ScannerStateLabel'
import type { MetaFile, ScannersFile, ScannerStatus } from '../contract'
import { metaDataPath, scannersDataPath, useJson } from '../data'
import { codePagePath } from '../routes'
import { isOffline, scannerState } from '../scanners'
import { ALL_LOCATIONS, useSelectedLocation } from '../selectedLocation'
import { exactTime, useNow } from '../time'

/** Every known scanner within the selected location: offline first, then by name. */
export function ScannersPage() {
  const [location] = useSelectedLocation()
  const scanners = useJson<ScannersFile>(scannersDataPath(location))
  const meta = useJson<MetaFile>(metaDataPath())
  const now = useNow()
  const where = location === ALL_LOCATIONS ? 'anywhere' : `at ${location}`

  return (
    <section className="panel" aria-labelledby="scanners-heading">
      <h2 id="scanners-heading">Scanners</h2>
      <p className="panel-hint">
        A scanner is offline after an hour without a heartbeat.
        {meta.status === 'ready' && (
          <>
            {' '}Data built <Ago iso={meta.data.generated_at} now={now} /> ({exactTimeOf(meta.data.generated_at)}).
          </>
        )}
      </p>
      {scanners.status === 'loading' && <p className="status">Loading scanners…</p>}
      {(scanners.status === 'missing' || scanners.status === 'error') && (
        <p className="status status-error">Scanner status unavailable.</p>
      )}
      {scanners.status === 'ready' &&
        (scanners.data.scanners.length === 0 ? (
          <p className="status">No scanners {where}.</p>
        ) : (
          <ScannersTable scanners={scanners.data.scanners} now={now} />
        ))}
    </section>
  )
}

function ScannersTable({ scanners, now }: { scanners: ScannerStatus[]; now: number }) {
  const { search } = useLocation()
  const sorted = [...scanners].sort(
    (a, b) => Number(isOffline(b, now)) - Number(isOffline(a, now)) || a.name.localeCompare(b.name),
  )
  return (
    <div className="table-scroll">
      <table className="scanners-table">
        <thead>
          <tr>
            <th>Status</th>
            <th>Scanner</th>
            <th>Location</th>
            <th>Last heartbeat</th>
            <th>Last scan</th>
            <th>Version</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((scanner) => {
            const state = scannerState(scanner, now)
            return (
              <tr key={scanner.name} className={state}>
                <td className="scanner-state">
                  <ScannerStateLabel state={state} />
                </td>
                <td className="scanner-name">{scanner.name}</td>
                <td>{scanner.location}</td>
                <td>
                  <Ago iso={scanner.last_seen} now={now} showExact />
                </td>
                <td>
                  {scanner.last_scan ? (
                    <>
                      <Ago iso={scanner.last_scan.scanned_at} now={now} />
                      <Link className="last-scan-product" to={{ pathname: codePagePath(scanner.last_scan.code), search }}>
                        {scanner.last_scan.product_name ?? scanner.last_scan.code}
                      </Link>
                    </>
                  ) : (
                    'Never'
                  )}
                </td>
                <td>{scanner.app_version}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

const exactTimeOf = (iso: string) => exactTime.format(new Date(iso))
