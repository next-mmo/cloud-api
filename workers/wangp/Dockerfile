FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg curl ca-certificates && rm -rf /var/lib/apt/lists/*
COPY packages/python_common /opt/python_common
COPY workers/common/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY workers/common/worker_base.py /app/worker_base.py
COPY workers/common/start.sh /app/start.sh
COPY workers/wangp/app /app/app
RUN chmod +x /app/start.sh && mkdir -p /app/data/files /outputs
EXPOSE 8012
ENV PORT=8012 ENGINE_MODE=mock
CMD ["/app/start.sh"]
