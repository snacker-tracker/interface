# Glossary Map

## Contexts

- [Snacker Tracker](./GLOSSARY.md): which snacks are taken from office pantries, as recorded by barcode scanners
- [stepdag](./stepdag/GLOSSARY.md): a framework that runs a graph of assets as a Step Functions workflow, one Lambda per asset

## Relationships

- **Snacker Tracker → stepdag**: Snacker's backend is stepdag's only consumer. `backend/src/snacker/graph/` defines Snacker's build as a stepdag graph; the backend depends on `stepdag` by path (`../stepdag`), the one Lambda image bakes it in, and Terraform deploys the manifest it renders.
- **stepdag ↛ Snacker**: stepdag never imports Snacker, and its only dependency is `boto3`. It is a separate project developed in this repository, so it can move to its own repository; the work is repointing the backend's dependency, the Dockerfile, and the pipeline's stepdag test job.
