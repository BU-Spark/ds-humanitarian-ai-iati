FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOST=0.0.0.0 PORT=8080
WORKDIR /app/fa26
COPY web/requirements-deploy.txt web/requirements-deploy.txt
RUN pip install --no-cache-dir -r web/requirements-deploy.txt
COPY src src
COPY retrieval retrieval
COPY benchmark/snapshot benchmark/snapshot
COPY benchmark/manifest.json benchmark/manifest.json
COPY web web
RUN useradd --create-home atlas && chown -R atlas /app
USER atlas
EXPOSE 8080
CMD ["python", "web/server.py"]
