FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev

COPY . .

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
