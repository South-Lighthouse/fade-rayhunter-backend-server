# fade-server

> **Work in progress.** This project is under active development and is expected to be heavily contributed to over the coming months.

## What is this?

This is the server-side stack for the [FADE project](https://fadeproject.org), built to ingest and process data from [Rayhunter](https://github.com/EFForg/rayhunter) sensors deployed in the field.

The server lets you register any number of sensors, each getting its own WebDAV endpoint with a dedicated username and password. Sensors upload their QMDL recordings and GPS sidecar files to these endpoints. Once uploaded, files are queued for server-side processing — the goal being to run analysis on the Rayhunter readings, detect anomalies, and surface them alongside the alerts generated on-device.

Processing components (PCAP conversion, variable extraction, anomaly detection) will be added as separate Django apps as the project advances.

## Stack

- **Django** — core framework, one app per major aspect of execution
- **MySQL** — database backend
- **Celery + Redis** — async task queue and file scan scheduler
- **wsgidav** — WebDAV server, mounted at `/webdav/{sensor-slug}/`
- **nginx** — reverse proxy, handles TLS termination
- **Docker Compose** — runs everything, no host dependencies beyond Docker

## Running on a new server

### Requirements

- Docker with the Compose plugin
- Ports 80 and 443 open on the server firewall
- A domain name pointing to the server (for HTTPS)

### Steps

**1. Clone and configure**

```bash
git clone <repo-url> fade_server
cd fade_server
cp .env.example .env
```

Edit `.env` and set at minimum:
- `SECRET_KEY` — a long random string
- `DB_PASSWORD` — database password
- `ALLOWED_HOSTS` — your domain (e.g. `dashboard.example.com`)
- `CSRF_TRUSTED_ORIGINS` — full HTTPS URL (e.g. `https://dashboard.example.com`)
- `DOMAIN` — your domain, for the TLS certificate
- `CERTBOT_EMAIL` — your email, for Let's Encrypt notifications

**2. Obtain a TLS certificate (first deploy only)**

```bash
chmod +x init-letsencrypt.sh
./init-letsencrypt.sh
```

This generates the nginx config, starts nginx, requests a Let's Encrypt certificate, and reloads nginx. The `certbot` container will handle renewals automatically after this.

**3. Start the stack**

```bash
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

**4. Add sensors**

Go to `https://your-domain/admin/` and create a **Sensor** record. Each sensor gets:
- A slug-based WebDAV endpoint: `https://your-domain/webdav/{slug}/`
- A dedicated username and password for uploads

Sensors can upload files using any WebDAV client:

```bash
curl -u user:password -T recording.qmdl \
  https://your-domain/webdav/sensor-slug/recording.qmdl
```

Uploaded files appear under **Ingestion → Ingested files** in the admin within 30 seconds.

### Local testing (no domain, no HTTPS)

```bash
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Access the admin at `http://<server-ip>/admin/`. WebDAV endpoints work the same over HTTP.
