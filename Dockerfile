FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY rulebook rulebook
COPY eval eval
# Fetches and parses the four sources (cached in the mounted data/ after the first start), then serves
# the API and the demo page. Answers come from the Anthropic API (ANTHROPIC_API_KEY), not `claude -p`.
CMD ["sh", "-c", "uv run --no-sync python -m rulebook.corpus && exec uv run --no-sync uvicorn rulebook.api:app --host 0.0.0.0 --port 8000"]
