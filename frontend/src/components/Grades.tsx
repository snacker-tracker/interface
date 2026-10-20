import type { Product } from '../contract'

type Scale = 'nutri-score' | 'nova-group' | 'green-score'

const LABELS: Record<Scale, string> = {
  'nutri-score': 'Nutri-Score',
  'nova-group': 'NOVA',
  'green-score': 'Green-Score',
}

/** What each grade means, shown as the badge's tooltip. */
const MEANINGS: Record<Scale, Record<string, string>> = {
  'nutri-score': {
    A: 'Best nutritional quality (Nutri-Score runs from A to E)',
    B: 'Good nutritional quality (Nutri-Score runs from A to E)',
    C: 'Average nutritional quality (Nutri-Score runs from A to E)',
    D: 'Poor nutritional quality (Nutri-Score runs from A to E)',
    E: 'Worst nutritional quality (Nutri-Score runs from A to E)',
  },
  'nova-group': {
    1: 'Unprocessed or minimally processed food',
    2: 'Processed culinary ingredient',
    3: 'Processed food',
    4: 'Ultra-processed food',
  },
  'green-score': {
    A: 'Lowest environmental impact (Green-Score runs from A to F)',
    B: 'Low environmental impact (Green-Score runs from A to F)',
    C: 'Moderate environmental impact (Green-Score runs from A to F)',
    D: 'High environmental impact (Green-Score runs from A to F)',
    E: 'Very high environmental impact (Green-Score runs from A to F)',
    F: 'Highest environmental impact (Green-Score runs from A to F)',
  },
}

/** A product's grades from OpenFoodFacts (GLOSSARY.md, Grade); grades it lacks are left out. */
export function Grades({ product }: { product: Product }) {
  const grades: [Scale, string | number | null][] = [
    ['nutri-score', product.nutri_score],
    ['nova-group', product.nova_group],
    ['green-score', product.green_score],
  ]
  const present = grades.filter((entry): entry is [Scale, string | number] => entry[1] !== null)
  if (present.length === 0) return null
  return (
    <ul className="grades" aria-label="Grades">
      {present.map(([scale, grade]) => (
        <li key={scale}>
          <GradeBadge scale={scale} grade={grade} />
        </li>
      ))}
    </ul>
  )
}

/** A grade as text on its colour, so it reads without the colour too. */
function GradeBadge({ scale, grade }: { scale: Scale; grade: string | number }) {
  return (
    <span className={`grade ${scale}`} data-grade={grade} title={MEANINGS[scale][grade]}>
      {LABELS[scale]} {grade}
    </span>
  )
}
