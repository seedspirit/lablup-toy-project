FROM python:3.11

RUN pip install poetry

WORKDIR /app
COPY . /app/

WORKDIR /app/backend
RUN poetry install --no-root

ENTRYPOINT ["poetry", "run", "python", "app.py"]