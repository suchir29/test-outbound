# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.11.6
FROM python:${PYTHON_VERSION}-slim

ENV PYTHONUNBUFFERED=1

ARG UID=10001
RUN adduser \
  --disabled-password \
  --gecos "" \
  --home "/home/appuser" \
  --shell "/sbin/nologin" \
  --uid "${UID}" \
  appuser

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

USER appuser
WORKDIR /home/appuser

RUN mkdir -p /home/appuser/.cache && \
    chown -R appuser /home/appuser/.cache

COPY requirements.txt .
RUN python -m pip install --user --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "python agent.py download-files && python agent.py dev"]
