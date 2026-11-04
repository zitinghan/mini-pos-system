FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --uid 10001 --create-home pos && mkdir -p /data/tickets && chown -R pos:pos /data /app
USER pos
ENV DATABASE_URL=sqlite:////data/pos.db PRINT_OUTPUT_DIR=/data/tickets
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Test dependencies stay out of the production image.
FROM base AS test
USER root
RUN pip install --no-cache-dir -r requirements-dev.txt
USER pos
CMD ["python", "-m", "pytest"]

FROM base AS runtime
