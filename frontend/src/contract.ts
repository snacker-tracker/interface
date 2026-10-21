// Generated from contract/static-json.schema.json by `npm run contract`: don't edit by hand.
// The schema is generated from the backend's contract module (`snacker schema`).
/**
 * One code's scans within one selectable location; written only where it was scanned.
 */
export interface CodeScansFile {
  code: string
  location: string
  /**
   * Scans per office date, oldest first; days without scans are left out.
   */
  daily: DailyCount[]
  /**
   * Scans per office hour of the day: always 24 entries, 0 to 23.
   */
  hourly: HourlyCount[]
  /**
   * The most recent scans, newest first.
   */
  recent: ScanRow[]
}
export interface DailyCount {
  /**
   * A date in the office time zone, e.g. "2026-10-16".
   */
  date: string
  count: number
}
export interface HourlyCount {
  /**
   * 0-23, in the office time zone.
   */
  hour: number
  count: number
}
export interface ScanRow {
  product: ScannedProduct
  location: string
  /**
   * UTC, e.g. "2026-09-23T06:26:00Z".
   */
  scanned_at: string
  /**
   * The same moment in the office time zone, e.g. "2026-09-23T13:26:00+07:00".
   */
  office_time: string
  /**
   * IANA name, e.g. "Asia/Bangkok".
   */
  office_time_zone: string
}
/**
 * A scanned code and what the scan lists show of its product (GLOSSARY.md).
 */
export interface ScannedProduct {
  code: string
  /**
   * The product's name; null when neither OpenFoodFacts nor the Snacker archive names it.
   */
  name: string | null
  /**
   * Where the name came from; null exactly when the name is.
   */
  name_source: ('openfoodfacts' | 'snacker-archive') | null
  brands: string | null
  /**
   * Whether OpenFoodFacts has the product; it may have it without a name.
   */
  known: boolean
  /**
   * The product's Nutri-Score; null when OpenFoodFacts has none.
   */
  nutri_score: ('A' | 'B' | 'C' | 'D' | 'E') | null
}
/**
 * The products with a Nutri-Score scanned within a period (GLOSSARY.md), split in two
 * lists that never share a product: the better half, best grade first, and the worse half,
 * worst grade first; the most scanned first within a grade.
 */
export interface HealthiestAndLeastHealthy {
  healthiest: ScannedProductCount[]
  least_healthy: ScannedProductCount[]
  /**
   * Scans in the period of products with a Nutri-Score.
   */
  graded_scans: number
  /**
   * All scans in the period.
   */
  scans: number
}
/**
 * A scanned product and how often it was scanned in a period.
 */
export interface ScannedProductCount {
  product: ScannedProduct
  count: number
}
export interface HealthiestAndLeastHealthyByPeriod {
  today: HealthiestAndLeastHealthy
  'this-work-week': HealthiestAndLeastHealthy
  'last-7-days': HealthiestAndLeastHealthy
  'this-month': HealthiestAndLeastHealthy
  'last-30-days': HealthiestAndLeastHealthy
  'this-year': HealthiestAndLeastHealthy
  'last-365-days': HealthiestAndLeastHealthy
  'all-time': HealthiestAndLeastHealthy
}
/**
 * The index page for one selectable location.
 */
export interface IndexFile {
  location: string
  top_scans: TopScansByPeriod
  top_unknown_scans: TopScansByPeriod
  healthiest_and_least_healthy: HealthiestAndLeastHealthyByPeriod
  nutri_score_distribution: NutriScoreDistributionByPeriod
  period_days: PeriodDaysByPeriod
  /**
   * Scans per office date, oldest first; days without scans are left out.
   */
  daily: DailyCount[]
  /**
   * The most recent scans, newest first.
   */
  recent: ScanRow[]
}
export interface TopScansByPeriod {
  today: TopScan[]
  'this-work-week': TopScan[]
  'last-7-days': TopScan[]
  'this-month': TopScan[]
  'last-30-days': TopScan[]
  'this-year': TopScan[]
  'last-365-days': TopScan[]
  'all-time': TopScan[]
}
export interface TopScan {
  product: ScannedProduct
  count: number
  /**
   * This code's fraction of all scans in the period, e.g. 0.25.
   */
  share: number
}
export interface NutriScoreDistributionByPeriod {
  today: NutriScoreDistribution
  'this-work-week': NutriScoreDistribution
  'last-7-days': NutriScoreDistribution
  'this-month': NutriScoreDistribution
  'last-30-days': NutriScoreDistribution
  'this-year': NutriScoreDistribution
  'last-365-days': NutriScoreDistribution
  'all-time': NutriScoreDistribution
}
/**
 * How many scans within a period were of products of each Nutri-Score grade (GLOSSARY.md).
 */
export interface NutriScoreDistribution {
  grades: NutriScoreCounts
  /**
   * Scans in the period of products with a Nutri-Score: the grades' sum.
   */
  graded_scans: number
  /**
   * All scans in the period.
   */
  scans: number
}
export interface NutriScoreCounts {
  A: number
  B: number
  C: number
  D: number
  E: number
}
export interface PeriodDaysByPeriod {
  today: PeriodDays
  'this-work-week': PeriodDays
  'last-7-days': PeriodDays
  'this-month': PeriodDays
  'last-30-days': PeriodDays
  'this-year': PeriodDays
  'last-365-days': PeriodDays
  'all-time': PeriodDays
}
/**
 * The office days a period touches, for zooming a chart of scans per day to it. Both are
 * null only when nothing has been scanned, so there's no office time zone to count days in.
 */
export interface PeriodDays {
  /**
   * The office date the period starts on, e.g. "2026-10-12"; a rolling period's partial
   * first day counts. All time starts on the first scanned day. Across office time zones,
   * the earliest.
   */
  first_day: string | null
  /**
   * The office date the data was built on; across office time zones, the latest.
   */
  last_day: string | null
}
export interface LastScan {
  product: ScannedProduct
  /**
   * UTC, e.g. "2026-10-16T10:33:45Z".
   */
  scanned_at: string
}
export interface LocationsFile {
  /**
   * `all`, then every prefix of every scanned location, in path order.
   */
  locations: SelectableLocation[]
}
export interface SelectableLocation {
  /**
   * `all`, or a location path such as "thailand:bangkok".
   */
  id: string
}
export interface MetaFile {
  /**
   * UTC time the data was built; every top-scans period ends then.
   */
  generated_at: string
  /**
   * The version of this contract the data was built to (CONTRACT_VERSION).
   */
  contract_version: 4
}
/**
 * What a code page shows about a product (PRD R5): OpenFoodFacts's details, or for a
 * product only the Snacker archive has, just its name.
 */
export interface Product {
  name: string | null
  /**
   * Where the name came from; null exactly when the name is.
   */
  name_source: ('openfoodfacts' | 'snacker-archive') | null
  brands: string | null
  quantity: string | null
  categories: string[]
  /**
   * OpenFoodFacts's front image (docs/adr/0001).
   */
  image_url: string | null
  /**
   * The product's page on OpenFoodFacts; null when OpenFoodFacts doesn't have it.
   */
  off_url: string | null
  /**
   * The product's Nutri-Score; null when OpenFoodFacts has none, and always for a product it doesn't have.
   */
  nutri_score: ('A' | 'B' | 'C' | 'D' | 'E') | null
  /**
   * The product's NOVA group; null when OpenFoodFacts has none, and always for a product it doesn't have.
   */
  nova_group: (1 | 2 | 3 | 4) | null
  /**
   * The product's Green-Score; null when OpenFoodFacts has none, and always for a product it doesn't have.
   */
  green_score: ('A+' | 'A' | 'B' | 'C' | 'D' | 'E' | 'F') | null
}
/**
 * A code's product; written for every scanned code, whatever the location.
 */
export interface ProductFile {
  code: string
  /**
   * Whether OpenFoodFacts has the product.
   */
  known: boolean
  /**
   * Null when neither OpenFoodFacts nor the Snacker archive has the code.
   */
  product: Product | null
}
export interface ScannerStatus {
  /**
   * The scanner's name, e.g. "rpi-pico-w-01".
   */
  name: string
  /**
   * Where its latest heartbeat said it was.
   */
  location: string
  /**
   * From its latest heartbeat.
   */
  app_version: string
  /**
   * UTC time of its latest heartbeat, e.g. "2026-10-19T09:45:47Z".
   */
  last_seen: string
  /**
   * The latest scan sent with its API key (docs/adr/0002); null if it has sent none.
   */
  last_scan: LastScan | null
}
/**
 * Every scanner within one selectable location, ordered by name.
 */
export interface ScannersFile {
  location: string
  scanners: ScannerStatus[]
}

/** Every period top scans are ranked over, in display order (see GLOSSARY.md, Period). */
export const PERIODS = [
  'today',
  'this-work-week',
  'last-7-days',
  'this-month',
  'last-30-days',
  'this-year',
  'last-365-days',
  'all-time'
] as const
export type Period = (typeof PERIODS)[number]

/** The contract version this frontend was built for; meta.json names the one the data was built to. */
export const CONTRACT_VERSION = 4
