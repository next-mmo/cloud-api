FROM python:3.11-slim
WORKDIR /app
COPY packages/python_common /opt/python_common
COPY services/controller/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services/controller/app /app/app
RUN mkdir -p /app/data/files
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
