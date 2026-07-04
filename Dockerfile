FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev

FROM python:3.12-slim
RUN useradd -m -u 10001 nightman
COPY --from=builder --chown=nightman:nightman /app /app
ENV PATH="/app/.venv/bin:$PATH"
USER nightman
WORKDIR /app
EXPOSE 8000
ENTRYPOINT ["nightman"]
CMD ["serve", "--http"]
