import { Link, useLocation } from 'react-router'

import { codePagePath } from '../routes'

/**
 * A scanned product in a list, linking to its code page: its name and brands, or, without a name,
 * its code and a link to OpenFoodFacts (R3). An unknown product's link adds it to OpenFoodFacts.
 */
export function ScannedProduct({
  code,
  name,
  brands,
  known,
}: {
  code: string
  name: string | null
  brands: string | null
  known: boolean
}) {
  // Keeps ?location= (and ?period=) when following the link to the code page.
  const { search } = useLocation()
  const codePage = { pathname: codePagePath(code), search }
  if (name) {
    return (
      <>
        <Link to={codePage}>{name}</Link>
        {brands && <span className="brands">{brands}</span>}
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

function OpenFoodFactsLink({ code, known }: { code: string; known: boolean }) {
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
