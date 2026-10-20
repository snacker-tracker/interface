import { Link, useLocation } from 'react-router'

import type { ScanRow } from '../contract'
import { codePagePath } from '../routes'

type NameSource = ScanRow['name_source']

/**
 * A scanned product in a list, linking to its code page: its name and brands, or, without a name,
 * its code (R3). A name from the Snacker archive is tagged. An unknown product links to adding it
 * to OpenFoodFacts, and a known one without a name to its OpenFoodFacts page.
 */
export function ScannedProduct({
  code,
  name,
  nameSource,
  brands,
  known,
}: {
  code: string
  name: string | null
  nameSource: NameSource
  brands: string | null
  known: boolean
}) {
  // Keeps ?location= (and ?period=) when following the link to the code page.
  const { search } = useLocation()
  const codePage = { pathname: codePagePath(code), search }
  if (name) {
    return (
      <>
        <Link to={codePage} title={code}>
          {name}
        </Link>
        <ArchiveTag nameSource={nameSource} />
        {brands && <span className="brands">{brands}</span>}
        {!known && <OpenFoodFactsLink code={code} known={known} />}
      </>
    )
  }
  return (
    <>
      <Link to={codePage} className="code unknown">
        {code}
      </Link>
      <OpenFoodFactsLink code={code} known={known} />
    </>
  )
}

/** Marks a name taken from the Snacker archive; OpenFoodFacts names go unmarked. */
export function ArchiveTag({ nameSource }: { nameSource: NameSource }) {
  if (nameSource !== 'snacker-archive') return null
  return (
    <span className="archive-tag" title="Named by the previous Snacker Tracker, not by OpenFoodFacts">
      Snacker archive
    </span>
  )
}

export function OpenFoodFactsLink({ code, known }: { code: string; known: boolean }) {
  if (!/^\d+$/.test(code)) return null // QR-code URLs and the like aren't on OpenFoodFacts
  const barcode = encodeURIComponent(code)
  return (
    <a
      className="off-link"
      href={
        known
          ? `https://world.openfoodfacts.org/product/${barcode}`
          : `https://world.openfoodfacts.org/cgi/product.pl?type=search_or_add&action=process&code=${barcode}`
      }
      target="_blank"
      rel="noreferrer"
    >
      {known ? 'On OpenFoodFacts' : 'Add it to OpenFoodFacts'}
    </a>
  )
}
