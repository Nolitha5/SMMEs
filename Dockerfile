FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p /data
ENV DATABASE_PATH=/data/price_agent.db
ENV SECRET_KEY=change-me-in-production
ENV CHECK_INTERVAL_HOURS=6
ENV ENABLE_BACKGROUND_CHECKER=true
ENV PORT=5000
ENV GEMINI_API_KEY=
ENV GEMINI_MODEL=gemini-3.8-flash
EXPOSE 5000
CMD ["sh", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT} --workers 1 --timeout 120 --access-logfile - --error-logfile -"]
