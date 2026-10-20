import type { ReactNode } from 'react'

import type { ScannedProduct as Scanned } from '../contract'
import { ScannedProduct } from './ScannedProduct'

/** A ranked list's row: the scanned product and its scan count, then anything the list adds (e.g. a share). */
export function ScannedProductRow({ product, count, children }: { product: Scanned; count: number; children?: ReactNode }) {
  return (
    <li>
      <div className="scanned-product-row">
        <div className="scanned-product-row-product">
          <ScannedProduct product={product} />
        </div>
        <div className="scanned-product-row-count">
          <strong>{count}</strong> {count === 1 ? 'scan' : 'scans'}
          {children}
        </div>
      </div>
    </li>
  )
}
