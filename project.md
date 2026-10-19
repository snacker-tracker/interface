# Project: Snacker Tracker Interface

Snacker-Tracker is a hobby project that helps office management keep track of snacks that are taken from the pantry. It is deployed in only one office (Bangkok), but lets assume it will be deployed in other offices soon.

The objective is to gain insights into people's preferences, to inform the grocery list at the next opportunity.

Additionally: It's gives office-goers visibility into snacks that are taken.

## What exists

While the data should like and be processed "in the cloud" and stored on "s3", I've copied it locally for your convenience, and better performance.

### Snacker-Tracker Data

I already have an internet-connected barcode scanner, which publishes scan events that eventually get saved to S3. 

All data is wrapped in an AWS EventBus envelope, which includes things like the time at which an event was received. The envelop and payloads are all JSON. Each file can have 1 or more events.

There is data that we are accumulating "live", and there is data I have populated from a previous version of our software, before we used AWS so heavily.

There are 2 kinds of data:

- scans: these are scan events, each contain a code, a location, an API-Key ID, maybe a scanned-at event
  If there is no scanned-at, the EventBus time can be used as a "reported-at" field.
- heartbeats: these are automated "pings" from the barcode scanners to our backend, to signify the hardware is functional. In addition to providing a sign of life, they also include versioning information.

### OpenFoodFacts

You also have access to product and food data in a parquet file located at `data/openfoodfacts__product-database/food.parquet`

Columns of interest include:
- brand
- brands
- code

There will be others, but we can figure what later.

## Objective

I want us to build a simple server and UI to let people view the snacks that have been taken from the pantry.

The backend code should by python, and use Polars. The backend code you write will likely be thrown away after being rewritten or integrated as part of a dagster data pipeline. The code should be clear in what it does to make it easier to re-intergrate.

The frontend code read what _could be_ static JSON files (therefore, do not include parameters in query parameters) -- all generated in advance.

## Pages

### Global

Because scanners can be deployed to multiple offices, the UI should include a location filtering mechanism promonently. The "all" option should be possible.

### Welcome / Index

url: /

The default page for the interface.

I think this screen should include a bar graph of the number of barcode scans per day, and a list of the last N (lets start with 25) scans.

If we have a product name or description for that UPC code, we should display it.

### Code Page

url: codes/$CODE

If we have product information, we should display it.

Additionally, we should also display bar chart for the number of scans over time (per day), and the number of scans per hour (eg, 24 hours)

There should be a list of the last N scans (lets start with the last 25), and include the datetime of the scan, and location

## Technical Choices

- The backend should be python with polars
- Use UV for dependency management

- The frontend should be React based
- Graphs should use vega/vega-lite

## Testing

Testing is good. Aim for decent coverage in the critical sections. We will add more tests as we tighten up our specification and cross-functional requirements.
