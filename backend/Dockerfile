# The one Lambda image (aws-deployment ticket 04), running the stepdag graph (#118): every function
# runs stepdag.aws.asset_handler or stepdag.aws.plan_handler, set from the manifest by Terraform.
# Build context: the REPO ROOT, so the image can hold stepdag/ as well as backend/:
#   docker build --platform linux/amd64 --provenance=false -f backend/Dockerfile .
# The root .dockerignore keeps the context to the files copied here.
FROM public.ecr.aws/lambda/python:3.15

# From PyPI rather than ghcr.io/astral-sh/uv, whose pulls can fail authentication.
RUN pip install --no-cache-dir uv==0.13.4

# The repo's layout is kept under /build, so backend's path source (../stepdag) still resolves.
WORKDIR /build

# Dependencies first, so a code change doesn't reinstall Polars and deltalake. backend's lock
# covers stepdag's dependencies too; stepdag and snacker are installed from source below.
COPY backend/pyproject.toml backend/uv.lock backend/README.md backend/
RUN cd backend \
 && uv export --frozen --no-dev --no-emit-project --no-emit-package stepdag --no-hashes -o /tmp/requirements.txt \
 && uv pip install --system --no-cache --target "${LAMBDA_TASK_ROOT}" -r /tmp/requirements.txt

COPY stepdag/pyproject.toml stepdag/README.md stepdag/
COPY stepdag/src/ stepdag/src/
RUN uv pip install --system --no-cache --no-deps --target "${LAMBDA_TASK_ROOT}" ./stepdag

COPY backend/src/ backend/src/
RUN uv pip install --system --no-cache --no-deps --target "${LAMBDA_TASK_ROOT}" ./backend \
 && cd / && rm -rf /build /tmp/requirements.txt

WORKDIR ${LAMBDA_TASK_ROOT}

CMD ["stepdag.aws.asset_handler"]
