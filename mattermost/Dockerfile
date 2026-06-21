FROM python:3.11-alpine

WORKDIR /app/

RUN apk add --no-cache curl
RUN pip install poetry

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.create false && \
    poetry install --only main --no-root --no-interaction --no-ansi

RUN addgroup -S eyf && \
    adduser -S eyf -G eyf

COPY . /app/

RUN chown -R eyf:eyf /app
