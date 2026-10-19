# Minimal image for the hypothetical APRA agent service.
FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir uv

COPY pyproject.toml ./
COPY src ./src
COPY run_agent_service.py ./
RUN uv sync --no-dev

ENV AGENT_SECTOR=banking \
    AGENT_MODE=vulnerable

EXPOSE 9000

# Config via env (AGENT_SECTOR / AGENT_MODE / AGENT_NAME / AGENT_AUTH_TOKEN).
CMD ["uv", "run", "uvicorn", "src.agent_service.app:app", "--host", "0.0.0.0", "--port", "9000", "--log-level", "warning"]
