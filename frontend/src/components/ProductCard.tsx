import { useState } from 'react'

import type { ProductFile } from '../contract'
import { Grades } from './Grades'
import { ArchiveTag, OpenFoodFactsLink } from './ScannedProduct'

/**
 * A code's product: image, name, brands, quantity, grades, category tags and a link to OpenFoodFacts.
 * A product only the Snacker archive has shows just its tagged name, and a link to add it to OpenFoodFacts.
 */
export function ProductCard({ file: { code, known, product }, headingId }: { file: ProductFile; headingId: string }) {
  return (
    <div className="product-card">
      <ProductImage url={product?.image_url ?? null} name={product?.name ?? null} />
      <div className="product-details">
        <h2 id={headingId} className={product?.name ? 'product-name' : 'product-name unknown'}>
          {product?.name ?? 'Unknown product'}
          {product && <ArchiveTag nameSource={product.name_source} />}
        </h2>
        {product?.brands && <p className="brands">{product.brands}</p>}
        {product?.quantity && <p className="quantity">{product.quantity}</p>}
        {product && <Grades product={product} />}
        {product && product.categories.length > 0 && (
          <ul className="categories" aria-label="Categories">
            {product.categories.map((category) => (
              <li key={category}>{category}</li>
            ))}
          </ul>
        )}
        <p className="code">{code}</p>
        {product?.off_url && (
          <a href={product.off_url} target="_blank" rel="noreferrer">
            View on OpenFoodFacts
          </a>
        )}
        {product && !known && (
          <p className="not-on-off">
            Not on OpenFoodFacts. <OpenFoodFactsLink code={code} known={false} />
          </p>
        )}
      </div>
    </div>
  )
}

/** Hotlinked from OpenFoodFacts, which can be slow or drop images: a fixed frame, and a fallback on error. */
function ProductImage({ url, name }: { url: string | null; name: string | null }) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  if (!url || failedUrl === url) {
    return (
      <div className="product-image product-image-missing" aria-hidden="true">
        No image
      </div>
    )
  }
  return (
    <img
      className="product-image"
      src={url}
      alt={name ? `Front of ${name}` : 'Product front'}
      loading="lazy"
      onError={() => setFailedUrl(url)}
    />
  )
}
