FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY tasks ./tasks

# Bake open TestMyBrain HTML/JS (LGPL upstream). Override with --build-arg INCLUDE_TMB=0 to skip.
ARG INCLUDE_TMB=1
RUN if [ "$INCLUDE_TMB" = "1" ]; then \
      git clone --depth 1 https://github.com/manybrainsproject/TestMyBrainCodeRepo.git /tmb; \
    else \
      mkdir -p /tmb; \
    fi

ENV TMB_REPO_PATH=/tmb

EXPOSE 8000
# PORT is set by Fly (often 8080); local compose leaves default 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
