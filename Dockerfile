# PanelAtlas – distribution board documentation
FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends libcairo2 fonts-dejavu-core ca-certificates rclone \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --create-home --home-dir /data --uid 10001 verteiler

WORKDIR /opt/verteiler
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

ENV VERTEILER_DATA=/data \
    PYTHONUNBUFFERED=1
USER verteiler
VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/state', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
