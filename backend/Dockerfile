# The Lambda image for both functions (aws-deployment ticket 04). The handler picks the job:
# snacker.handlers.build_handler (the default) or snacker.handlers.extract_handler.
FROM public.ecr.aws/lambda/python:3.13

# From PyPI rather than ghcr.io/astral-sh/uv, whose pulls can fail authentication.
RUN pip install --no-cache-dir uv==0.13.4

# Dependencies first, so a code change doesn't reinstall Polars.
COPY pyproject.toml uv.lock README.md ./
RUN uv export --frozen --no-dev --no-emit-project --no-hashes -o /tmp/requirements.txt \
 && uv pip install --system --no-cache --target "${LAMBDA_TASK_ROOT}" -r /tmp/requirements.txt

COPY src/ src/
RUN uv pip install --system --no-cache --no-deps --target "${LAMBDA_TASK_ROOT}" . \
 && rm -rf src

CMD ["snacker.handlers.build_handler"]
