FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG APP_USER=luminos
ARG APP_UID=10001
ARG APP_GID=10001

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libsndfile1 \
    && groupadd --gid ${APP_GID} ${APP_USER} \
    && useradd --uid ${APP_UID} --gid ${APP_GID} --create-home --shell /usr/sbin/nologin ${APP_USER} \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R ${APP_UID}:${APP_GID} /app

USER ${APP_UID}:${APP_GID}

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
