FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir fastapi uvicorn pydantic httpx
COPY . .
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "ai_preconsult_backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
