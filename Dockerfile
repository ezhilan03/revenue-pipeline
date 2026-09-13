FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN uv sync --frozen --no-dev && useradd --uid 10001 --create-home revenue
USER revenue
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "revenue_pipeline.api:app", "--host", "0.0.0.0", "--port", "8000"]
