FROM ghcr.io/astral-sh/uv:debian-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev --group prod --frozen
COPY . .
ENTRYPOINT ["uv", "run", "--no-sync", "gunicorn", "--bind", "0.0.0.0:8080", "returns_dashboard:server"]