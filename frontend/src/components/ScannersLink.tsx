import { Link, useLocation } from 'react-router'

import type { ScannersFile } from '../contract'
import { scannersDataPath, useJson } from '../data'
import { isOffline } from '../scanners'
import { useSelectedLocation } from '../selectedLocation'
import { useNow } from '../time'
import { ScannerStateLabel } from './ScannerStateLabel'

/** The header's way to the scanners page; it warns when a scanner in the selected location is offline. */
export function ScannersLink() {
  const { search } = useLocation()
  const [location] = useSelectedLocation()
  const scanners = useJson<ScannersFile>(scannersDataPath(location))
  const now = useNow()

  const offline = scanners.status === 'ready' ? scanners.data.scanners.filter((s) => isOffline(s, now)).length : 0
  return (
    <Link to={{ pathname: '/scanners', search }} className={offline > 0 ? 'scanners-link offline' : 'scanners-link'}>
      {offline > 0 ? <ScannerStateLabel state="offline" label={`${offline} offline`} /> : 'Scanners'}
    </Link>
  )
}
