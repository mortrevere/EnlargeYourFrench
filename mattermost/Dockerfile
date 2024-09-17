FROM python:3.11-alpine

WORKDIR /app/

RUN apk add --no-cache curl 
RUN pip install poetry

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.create false && \
    poetry install --no-dev

RUN addgroup -S eyf && \
    adduser  -s /bin/bash -S eyf -G eyf

COPY python /app/

RUN chown -R eyf:eyf /app
