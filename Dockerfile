FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PHDAI_PRIVATE_DIR=/var/lib/phd-atlas

WORKDIR /opt/phd-atlas

COPY requirements-intelligence.txt ./
RUN python -m pip install --no-cache-dir -r requirements-intelligence.txt \
    && useradd --uid 10001 --home-dir /var/lib/phd-atlas --no-create-home --shell /usr/sbin/nologin atlas

COPY . .
RUN mkdir -p /var/lib/phd-atlas /opt/phd-atlas/site/data \
    && chown -R 10001:10001 /var/lib/phd-atlas /opt/phd-atlas/site/data

USER 10001:10001
EXPOSE 8765

CMD ["python", "-m", "phd_agents", "serve", "--port", "8765"]
