# The one Lambda image (aws-deployment ticket 04), running the stepdag graph (#118): every function
# runs stepdag.aws.asset_handler or stepdag.aws.plan_handler, set from the manifest by Terraform.
# stepdag comes from the git source pinned in backend/pyproject.toml, not from this checkout.
# Build context: the REPO ROOT (the root .dockerignore keeps it to the files copied here):
#   docker build --platform linux/amd64 --provenance=false -f backend/Dockerfile .
FROM public.ecr.aws/lambda/python:3.15

# From PyPI rather than ghcr.io/astral-sh/uv, whose pulls can fail authentication.
RUN pip install --no-cache-dir uv==0.13.4

# uv and pip fetch git sources with the git binary, which the base image lacks.
RUN microdnf install -y git && microdnf clean all

WORKDIR /build

# Dependencies first, so a code change doesn't reinstall Polars and deltalake. backend's lock
# covers stepdag, fetched from its pinned git commit; snacker is installed from source below.
COPY backend/pyproject.toml backend/uv.lock backend/README.md backend/
RUN cd backend \
 && uv export --frozen --no-dev --no-emit-project --no-hashes -o /tmp/requirements.txt \
 && uv pip install --system --no-cache --target "${LAMBDA_TASK_ROOT}" -r /tmp/requirements.txt

COPY backend/src/ backend/src/
RUN uv pip install --system --no-cache --no-deps --target "${LAMBDA_TASK_ROOT}" ./backend \
 && cd / && rm -rf /build /tmp/requirements.txt

WORKDIR ${LAMBDA_TASK_ROOT}

CMD ["stepdag.aws.asset_handler"]
