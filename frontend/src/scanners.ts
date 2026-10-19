// What makes a scanner offline (see GLOSSARY.md, Offline).
import type { ScannerStatus } from './data'

/** A scanner sends a heartbeat every few minutes; an hour without one means something is wrong. */
const OFFLINE_AFTER_MS = 60 * 60 * 1000

export function isOffline(scanner: ScannerStatus, now: number): boolean {
  return now - Date.parse(scanner.last_seen) > OFFLINE_AFTER_MS
}

export type ScannerState = keyof typeof SCANNER_STATES

export function scannerState(scanner: ScannerStatus, now: number): ScannerState {
  return isOffline(scanner, now) ? 'offline' : 'online'
}

/** Status is never colour alone: each state has an icon and a label too. */
export const SCANNER_STATES = {
  online: { icon: '✓', label: 'Online' },
  offline: { icon: '✕', label: 'Offline' },
} as const
