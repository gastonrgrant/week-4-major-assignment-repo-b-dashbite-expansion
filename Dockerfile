FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DASHBITE_DATA_ROOT=/data

WORKDIR /app

RUN useradd --create-home --uid 1000 dashbite

COPY pyproject.toml docker-compose.yml ./
COPY pipeline ./pipeline
COPY tests ./tests

RUN pip install --no-cache-dir ".[dev]" \
    && chown -R dashbite:dashbite /app

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 755 /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "-m", "pipeline.simulator"]
