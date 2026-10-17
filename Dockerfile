FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CLIPX_DATA=/app/data
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core fonts-liberation libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY backend ./backend
RUN pip install --no-cache-dir .
RUN useradd -m clipx && mkdir -p /app/data && chown -R clipx:clipx /app
USER clipx
EXPOSE 8000
CMD ["uvicorn", "clipx.api:app", "--host", "0.0.0.0", "--port", "8000"]
