# The tracking plan is analytics-sdk-generator YAML, not part of the backend contract pipeline

The plan of interactions lives in `contract/interactions.yml`. [analytics-sdk-generator](https://github.com/leprechaun/analytics-sdk-generator) compiles it into one typed function per interaction, and the frontend calls those functions. It does not follow `contract/static-json.schema.json`, where the backend's Python models generate the JSON Schema and `npm run contract` generates `frontend/src/contract.ts` from it. That pipeline describes files the backend writes and the frontend reads. Interactions go the other way: the frontend writes them, and nothing in this repo reads them yet. So the backend would only be a detour. The generator's plan has pages, the tracks on each page and the traits, so it says where each interaction may be sent from, not only what it looks like.

## Considered options

- **Interactions as models in the backend, exported through `snacker schema`.** Rejected: the backend would own a shape that only the frontend produces. JSON Schema also can't say which page or component an interaction is sent from.
- **A hand-written TypeScript module of event types.** Rejected: there would be no plan document to review apart from the code, and no path to a schema for whatever later collects interactions.

## Consequences

- The repo has two schema toolchains in `contract/`.
- The generator needs one change upstream before it's usable here: its `source` fields (`screen/feature/widget/element/action`) become `{ page, component }`. Both are enums declared in the plan, and they're type-checked when a track is called from a component.
- When the reporter or the backend needs to read interactions, the generator will need a JSON Schema output. That output is deferred.
