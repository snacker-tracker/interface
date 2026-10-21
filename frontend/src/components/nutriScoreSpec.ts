import type { VisualizationSpec } from 'vega-embed'

import type { NutriScoreDistribution } from '../contract'
import { type ChartTokens, chartConfig } from '../theme'
import { NUTRI_SCORE_MEANINGS } from '../nutriScore'

export type GradeCount = { grade: keyof NutriScoreDistribution['grades']; meaning: string; count: number; share: number }

/** One row per grade, A to E, with its share of the period's graded scans. */
export function gradeCounts({ grades, graded_scans }: NutriScoreDistribution): GradeCount[] {
  return (Object.keys(NUTRI_SCORE_MEANINGS) as GradeCount['grade'][]).map((grade) => ({
    grade,
    meaning: NUTRI_SCORE_MEANINGS[grade],
    count: grades[grade],
    share: graded_scans ? grades[grade] / graded_scans : 0,
  }))
}

/** Vega-Lite spec for the Nutri-Score distribution: always five bars, A to E, in the badges' colours. */
export function nutriScoreSpec(counts: GradeCount[], tokens: ChartTokens): VisualizationSpec {
  const grades = counts.map(({ grade }) => grade)
  const nothingGraded = counts.every(({ count }) => count === 0)
  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
    width: 'container',
    height: 180,
    autosize: { type: 'fit-x', contains: 'padding' },
    background: 'transparent',
    data: { values: counts },
    mark: { type: 'bar', cornerRadiusEnd: 4, width: { band: 0.8 } },
    encoding: {
      x: { field: 'grade', type: 'ordinal', sort: grades, title: null, axis: { labelAngle: 0 } },
      y: {
        field: 'count',
        type: 'quantitative',
        title: 'Scans',
        // With nothing graded the bars are all zero; keep an axis to stand them on.
        scale: nothingGraded ? { domain: [0, 1] } : {},
        axis: { tickMinStep: 1 },
      },
      color: {
        field: 'grade',
        type: 'nominal',
        scale: { domain: grades, range: grades.map((grade) => tokens.nutriScore[grade]) },
        legend: null,
      },
      tooltip: [
        { field: 'grade', title: 'Nutri-Score' },
        { field: 'meaning', title: 'Meaning' },
        { field: 'count', type: 'quantitative', title: 'Scans' },
        { field: 'share', type: 'quantitative', title: 'Of graded scans', format: '.0%' },
      ],
    },
    config: chartConfig(tokens),
  }
}
