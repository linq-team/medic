FROM python:3.12-slim

WORKDIR /usr/src/app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY Medic/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash medic
USER medic

EXPOSE 5000

CMD ["python", "./medic.py"]
