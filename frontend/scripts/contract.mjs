// Generates src/contract.ts, the types of the static JSON, from the backend's JSON Schema
// (contract/static-json.schema.json at the repo root; see PRD.md §7.2).
//
//   node scripts/contract.mjs           write src/contract.ts
//   node scripts/contract.mjs --check   fail if src/contract.ts is out of date
import { readFileSync, writeFileSync } from 'node:fs'
import { compile } from 'json-schema-to-typescript'

const schemaFile = new URL('../../contract/static-json.schema.json', import.meta.url)
const outFile = new URL('../src/contract.ts', import.meta.url)

const schema = JSON.parse(readFileSync(schemaFile, 'utf8'))

const banner = `// Generated from contract/static-json.schema.json by \`npm run contract\`: don't edit by hand.
// The schema is generated from the backend's contract module (\`snacker schema\`).
`

/**
 * A `$ref` with a description beside it would become a second, numbered copy of the
 * referenced type (`TopScansByPeriod1`), so keep only the reference.
 */
function bareRefs(node) {
  if (Array.isArray(node)) return node.map(bareRefs)
  if (node === null || typeof node !== 'object') return node
  if ('$ref' in node) return { $ref: node.$ref }
  return Object.fromEntries(Object.entries(node).map(([key, value]) => [key, bareRefs(value)]))
}

const types = await compile(
  { ...bareRefs(schema), title: 'Contract', description: undefined },
  'Contract',
  {
    unreachableDefinitions: true,
    additionalProperties: false,
    bannerComment: '',
    format: true,
    style: { semi: false, singleQuote: true, printWidth: 110 },
  },
)

const generated =
  banner +
  types
    // The schema's root only gathers $defs; it describes no file of its own.
    .replace(/export interface Contract \{\n\s*\[k: string\]: unknown\n\}\n/, '')
    // Drop the boilerplate naming each type's $defs entry, then the comment lines it leaves empty.
    .replace(/ \* This interface was referenced by `Contract`'s JSON-Schema\n \* via the `definition` "\w+"\.\n/g, '')
    .replace(/ \*\n \*\//g, ' */')
    .replace(/\/\*\*\n \*\/\n/g, '') +
  `
/** Every period top scans are ranked over, in display order (see GLOSSARY.md, Period). */
export const PERIODS = ${JSON.stringify(schema.$defs.TopScansByPeriod.required, null, 2).replaceAll('"', "'")} as const
export type Period = (typeof PERIODS)[number]

/** The contract version this frontend was built for; meta.json names the one the data was built to. */
export const CONTRACT_VERSION = ${schema.$defs.MetaFile.properties.contract_version.const}
`

if (process.argv.includes('--check')) {
  if (readFileSync(outFile, 'utf8') !== generated) {
    console.error('src/contract.ts is out of date with contract/static-json.schema.json: run `npm run contract`')
    process.exit(1)
  }
} else {
  writeFileSync(outFile, generated)
  console.log('Wrote src/contract.ts')
}
