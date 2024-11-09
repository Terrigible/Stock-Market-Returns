FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ADD . ./app
WORKDIR /app
RUN uv sync --no-dev --group prod
ENTRYPOINT ["uv", "run", "gunicorn", "--bind", "0.0.0.0:8080", "returns_dashboard:server"]