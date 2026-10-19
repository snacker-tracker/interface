# Product images link to OpenFoodFacts's image server

Code pages show a product's image straight from `images.openfoodfacts.org`; the image isn't copied into the published data. The build works out the URL from the food parquet:

- **Which image:** the "front" image selected in the product's own language (`lang`), then English, then any selected front image. Products with no selected front image show no image.
- **Size:** the 400px version, `{key}.{rev}.400.jpg`, where `rev` is the selected image's revision.
- **Folder:** the code is padded with leading zeros to 13 digits and split 3/3/3/rest, e.g. `885/099/922/0000`. 8-digit codes also resolve under their unsplit folder, but the padded form is the current OpenFoodFacts layout. Only codes OpenFoodFacts has get an image URL, and those are numeric.

We hotlink rather than copy because the parquet has no image bytes. Fetching a few hundred images at build time would add a network dependency to an offline step and make the published data much larger. The cost is that images rely on OpenFoodFacts staying up, and on a selected image's revision not being replaced. If that happens, the page shows the product without its image, which the UI already handles.

Checked 2026-10-19 against the live image server: `885/099/922/0000/front_th.20.400.jpg` and the padded and unpadded folders for an 8-digit code load, and a wrong revision returns 404.
