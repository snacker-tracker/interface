# The scans example's Lambda image (scans ticket 05; Snacker's package added in parity ticket 09).
# Build context: the REPO ROOT, so the image can hold backend/ (Snacker) as well as stepdag/.
#   docker build --platform linux/amd64 --provenance=false -f stepdag/examples/scans/Dockerfile -t stepdag-scans .
# The root .dockerignore keeps the context to the files copied here.
# Terraform sets each function's handler (image_config command) from the manifest:
# stepdag.aws.asset_handler (the default) or stepdag.aws.plan_handler.
FROM public.ecr.aws/lambda/python:3.14

# From PyPI rather than ghcr.io/astral-sh/uv, whose pulls can fail authentication.
RUN pip install --no-cache-dir uv==0.13.4

# The repo's layout is kept under /build, so the example's path sources (../.. for stepdag,
# ../../../backend for Snacker) still resolve.
WORKDIR /build

# Dependencies first, so a code change doesn't reinstall Polars and deltalake. The example's
# lock covers stepdag's and Snacker's dependencies too; both are installed from source below.
COPY stepdag/examples/scans/pyproject.toml stepdag/examples/scans/uv.lock stepdag/examples/scans/README.md stepdag/examples/scans/
RUN cd stepdag/examples/scans \
 && uv export --frozen --no-dev --no-emit-project --no-emit-package stepdag --no-emit-package snacker --no-hashes -o /tmp/requirements.txt \
 && uv pip install --system --no-cache --target "${LAMBDA_TASK_ROOT}" -r /tmp/requirements.txt

COPY backend/pyproject.toml backend/README.md backend/
COPY backend/src/ backend/src/
RUN uv pip install --system --no-cache --no-deps --target "${LAMBDA_TASK_ROOT}" ./backend

COPY stepdag/pyproject.toml stepdag/README.md stepdag/
COPY stepdag/src/ stepdag/src/
RUN uv pip install --system --no-cache --no-deps --target "${LAMBDA_TASK_ROOT}" ./stepdag

COPY stepdag/examples/scans/src/ stepdag/examples/scans/src/
RUN uv pip install --system --no-cache --no-deps --target "${LAMBDA_TASK_ROOT}" ./stepdag/examples/scans \
 && cd / && rm -rf /build /tmp/requirements.txt

WORKDIR ${LAMBDA_TASK_ROOT}

CMD ["stepdag.aws.asset_handler"]
