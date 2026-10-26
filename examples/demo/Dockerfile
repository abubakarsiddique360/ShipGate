FROM python:3.12-slim

WORKDIR /app
COPY . .

RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 8080
CMD ["python", "-m", "http.server", "8080"]
