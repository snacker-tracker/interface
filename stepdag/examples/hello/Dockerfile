# The hello graph's Lambda image (stepdag ticket 08). Build context: the stepdag/ directory.
#   docker build -f examples/hello/Dockerfile -t stepdag-hello .
# Terraform sets each function's handler (image_config command) from the manifest:
# stepdag.aws.asset_handler (the default) or stepdag.aws.plan_handler.
FROM public.ecr.aws/lambda/python:3.14

# From PyPI rather than ghcr.io/astral-sh/uv, whose pulls can fail authentication.
RUN pip install --no-cache-dir uv==0.13.4

# Dependencies first, so a code change doesn't reinstall them.
COPY pyproject.toml uv.lock README.md ./
RUN uv export --frozen --no-dev --no-emit-project --no-hashes -o /tmp/requirements.txt \
 && uv pip install --system --no-cache --target "${LAMBDA_TASK_ROOT}" -r /tmp/requirements.txt

COPY src/ src/
RUN uv pip install --system --no-cache --no-deps --target "${LAMBDA_TASK_ROOT}" . \
 && rm -rf src pyproject.toml uv.lock README.md

# At the task root, so STEPDAG_DEFINITIONS=hello:defs imports.
COPY examples/hello/hello.py ${LAMBDA_TASK_ROOT}/hello.py

CMD ["stepdag.aws.asset_handler"]
