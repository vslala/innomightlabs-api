#############################################
# Stage 1: pull in Astral’s real uv helper
#############################################
FROM ghcr.io/astral-sh/uv:0.6.6 AS uv

#############################################
# Stage 2: builder—install into /var/task
#############################################
FROM public.ecr.aws/lambda/python:3.13 AS builder

# 1) OS deps for C-extensions (psycopg2, etc.)
RUN microdnf update -y \
 && microdnf install -y gcc postgresql-devel \
 && microdnf clean all

# 2) Copy in the uv binary
COPY --from=uv /uv /usr/local/bin/uv
RUN chmod +x /usr/local/bin/uv

# 3) uv config: bytecode on, strip metadata
ENV UV_COMPILE_BYTECODE=1 \
    UV_NO_INSTALLER_METADATA=1 \
    UV_LINK_MODE=copy

WORKDIR ${LAMBDA_TASK_ROOT}

# 4) Copy project metadata & code
COPY uv.lock pyproject.toml ./

# 5) Generate a locked requirements.txt
RUN mkdir -p /root/.cache/uv \
 && uv sync \
 && uv export \
     --frozen \
     --no-emit-workspace \
     --no-dev \
     --no-editable \
     -o requirements.txt && \
    uv pip install -r requirements.txt --target ./

COPY ./app ./app
COPY ./migrations ./migrations
COPY ./alembic.ini ./alembic.ini

# Lambda entrypoint
CMD ["app.main.handler"]
