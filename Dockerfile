FROM python:3.11-slim

WORKDIR /app

COPY requirements_api.txt .
RUN pip install --no-cache-dir -r requirements_api.txt

COPY src/api ./src/api
COPY output ./output
COPY web ./web

ENV OUTPUT_DIR=/app/output
ENV WEB_DIR=/app/web

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
