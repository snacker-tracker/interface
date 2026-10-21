# Product images are proxied through CloudFront, not hotlinked from OpenFoodFacts

Supersedes ADR 0001 on where images are loaded from. ADR 0001 still describes which image the build picks and how its URL is formed.

`images.openfoodfacts.org` is slow: on 2026-10-21, three fetches of a 14 KB image each took 3–6 s before the first byte. The site's CloudFront distribution now has OpenFoodFacts's image server as a second origin, under the same path it uses there, `/images/products/*`. The published data still holds the absolute OpenFoodFacts URL. The frontend replaces the `https://images.openfoodfacts.org` prefix with `VITE_OFF_IMAGE_BASE` when it is set. CI sets it to an empty string, so the site loads images from its own origin. Locally it is unset, so images load straight from OpenFoodFacts and no dev proxy is needed. The frontend is built once per commit for both environments, so the base has to be relative, never a hostname.

## Considered options

- **Copying images into the site bucket at build time.** This would avoid the slow first fetch and keep images up through an OpenFoodFacts outage. ADR 0001's objection, that the build was an offline step, no longer holds, since the build Lambda already reads Hugging Face. It was rejected as more build work than the problem needs.
- **Same-origin paths in the published data.** Rejected so that the data stays meaningful outside the site. The swap lives in one place in the frontend.
- **30-day caching with our own cache and response headers policies.** Rejected because cache and response headers policies can't be tagged, so the CI role (ADR 0005) would need account-wide permission to manage them, or an admin would have to own them. The behaviour uses `Managed-CachingOptimized` instead.

## Consequences

- OpenFoodFacts sends no `Cache-Control` header, so each edge keeps an image for CachingOptimized's 1-day default. Browsers cache it by heuristic. The first viewer of an image at an edge each day still waits on OpenFoodFacts.
- The distribution-wide 403/404 → `index.html` mapping applies to images too. A missing image arrives as `index.html` with a 200, fails to decode, and the card hides it as before.
- Images still depend on OpenFoodFacts for any image the edge doesn't already hold.
