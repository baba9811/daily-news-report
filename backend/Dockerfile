# Daily Scheduler backend — production-ish container for co-deployment.
FROM python:3.11-slim

WORKDIR /app

# Install uv first so dependency resolution is cached.
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --extra dev --frozen

# Copy the rest of the source tree.
COPY . .

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "daily_scheduler.entrypoints.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
