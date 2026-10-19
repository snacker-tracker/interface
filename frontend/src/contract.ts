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
  code: string
  /**
   * The product's name; null for an unknown product.
   */
  name: string | null
  brands: string | null
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
 * The index page for one selectable location.
 */
export interface IndexFile {
  location: string
  top_scans: TopScansByPeriod
  top_unknown_scans: TopScansByPeriod
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
  code: string
  name: string | null
  brands: string | null
  /**
   * Whether OpenFoodFacts has the product; unknown products are flagged in the UI.
   */
  known: boolean
  count: number
  /**
   * This code's fraction of all scans in the period, e.g. 0.25.
   */
  share: number
}
export interface LastScan {
  /**
   * UTC, e.g. "2026-10-16T10:33:45Z".
   */
  scanned_at: string
  code: string
  /**
   * Null for an unknown product.
   */
  product_name: string | null
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
}
/**
 * What a code page shows about a product (PRD R5).
 */
export interface Product {
  name: string | null
  brands: string | null
  quantity: string | null
  categories: string[]
  /**
   * OpenFoodFacts's front image (docs/adr/0001).
   */
  image_url: string | null
  /**
   * The product's page on OpenFoodFacts.
   */
  off_url: string
}
/**
 * A code's product; written for every scanned code, whatever the location.
 */
export interface ProductFile {
  code: string
  /**
   * Null for an unknown product.
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
