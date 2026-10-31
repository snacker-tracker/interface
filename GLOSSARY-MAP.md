# Glossary Map

## Contexts

- [Snacker Tracker](./GLOSSARY.md): which snacks are taken from office pantries, as recorded by barcode scanners
- [stepdag](./stepdag/GLOSSARY.md): a framework that runs a graph of assets as a Step Functions workflow, one Lambda per asset

## Relationships

- **Snacker Tracker ↔ stepdag**: none. stepdag is developed in this repository but is a separate project, proven on its own hello-world graph. Snacker's backend doesn't use it, and stepdag never imports Snacker, so it can move to its own repository.
