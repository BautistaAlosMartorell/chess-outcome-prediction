# Custom Airflow image — Proyecto Integrador Ajedrez (UTN FRM 2026)
# Extiende la imagen oficial de Airflow e instala las dependencias del proyecto.
ARG AIRFLOW_VERSION=2.10.5
FROM apache/airflow:${AIRFLOW_VERSION}

# Install project dependencies as the airflow user (no root needed for pip)
COPY requirements.txt /project/requirements.txt
RUN pip install --no-cache-dir -r /project/requirements.txt

# Copy the src package so the DAG can import it
COPY src/ /project/src/
COPY config/ /project/config/

# Add /project to PYTHONPATH so `from src.xxx import ...` works in the DAG
ENV PYTHONPATH="/project:${PYTHONPATH}"
