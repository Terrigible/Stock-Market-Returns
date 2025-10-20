FROM python:3.13.9-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ADD . ./app
WORKDIR /app
RUN uv sync --no-dev --group prod --frozen
ENTRYPOINT ["uv", "run", "--no-sync", "gunicorn", "--bind", "0.0.0.0:8080", "returns_dashboard:server"]