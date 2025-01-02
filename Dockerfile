FROM python:3.11-slim

RUN pip install poetry

WORKDIR /app
COPY . /app/

WORKDIR /app/backend
RUN poetry install --no-root

ENTRYPOINT ["sh", "-c", "poetry run python main.py -m $APP_MODE -w $APP_WORKERS"]