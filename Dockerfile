FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ADD . ./app
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1
RUN uv sync --no-dev --group prod --frozen
ENTRYPOINT ["uv", "run", "--no-sync", "gunicorn", "--bind", "0.0.0.0:8080", "returns_dashboard:server"]