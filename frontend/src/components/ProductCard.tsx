import { useState } from 'react'

import type { Product } from '../contract'

/** A code's product: image, name, brands, quantity, category tags and a link to OpenFoodFacts. */
export function ProductCard({ code, product, headingId }: { code: string; product: Product | null; headingId: string }) {
  return (
    <div className="product-card">
      <ProductImage url={product?.image_url ?? null} name={product?.name ?? null} />
      <div className="product-details">
        <h2 id={headingId} className={product?.name ? 'product-name' : 'product-name unknown'}>
          {product?.name ?? 'Unknown product'}
        </h2>
        {product?.brands && <p className="brands">{product.brands}</p>}
        {product?.quantity && <p className="quantity">{product.quantity}</p>}
        {product && product.categories.length > 0 && (
          <ul className="categories" aria-label="Categories">
            {product.categories.map((category) => (
              <li key={category}>{category}</li>
            ))}
          </ul>
        )}
        <p className="code">{code}</p>
        {product && (
          <a href={product.off_url} target="_blank" rel="noreferrer">
            View on OpenFoodFacts
          </a>
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
