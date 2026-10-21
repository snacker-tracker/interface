import type { NutriScoreCounts } from './contract'

/** What each Nutri-Score grade means (GLOSSARY.md, Nutri-Score), A best to E worst. */
export const NUTRI_SCORE_MEANINGS: Record<keyof NutriScoreCounts, string> = {
  A: 'Best nutritional quality',
  B: 'Good nutritional quality',
  C: 'Average nutritional quality',
  D: 'Poor nutritional quality',
  E: 'Worst nutritional quality',
}
