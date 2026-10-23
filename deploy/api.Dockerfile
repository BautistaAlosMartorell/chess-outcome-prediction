FROM python:3.12-slim

WORKDIR /app
COPY api/requirements*.txt ./api/
RUN pip install --no-cache-dir -r api/requirements-serving.txt

COPY src/ ./src/
COPY api/ ./api/
COPY config/config.yaml ./config/config.yaml
# The model stays outside Git; notebook 04 must generate it before this build.
COPY models/modelo_en_vivo.joblib ./models/modelo_en_vivo.joblib

RUN useradd --create-home --uid 1000 app
USER app
ENV PYTHONUNBUFFERED=1
EXPOSE 7860
HEALTHCHECK --interval=30s --start-period=60s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/salud', timeout=5)"
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
