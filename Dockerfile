# Builds the qmdl2pcap binary (tools/qmdl2pcap, Rust) in its own stage so the
# runtime image never carries a Rust toolchain or a git-fetched source tree.
# Pinned to the same Debian codename as the runtime stage below (bookworm) --
# a floating tag on either side risks a glibc mismatch across COPY --from=.
FROM rust:1-slim-bookworm AS qmdl2pcap-builder

# git is needed to fetch the `rayhunter` git dependency; not included in the
# slim Rust image by default.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY tools/qmdl2pcap/Cargo.toml tools/qmdl2pcap/Cargo.lock ./
COPY tools/qmdl2pcap/src ./src
# --locked: Cargo.lock already pins an exact commit of the rayhunter git
# dependency; this turns any future drift into a hard build failure instead
# of a silent surprise.
RUN cargo build --release --locked

FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    default-libmysqlclient-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# tshark, for the radio pipeline's `tshark -T ek` parsing step. Nothing here
# does live capture (only `tshark -r <file>` on already-written pcaps), so
# the setuid-install prompt is answered "no" rather than left to debconf's
# noninteractive default (which would otherwise still block on it).
RUN echo 'wireshark-common wireshark-common/install-setuid boolean false' | debconf-set-selections \
    && DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    tshark \
    && rm -rf /var/lib/apt/lists/*

COPY --from=qmdl2pcap-builder /build/target/release/qmdl2pcap /usr/local/bin/qmdl2pcap

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/uploads /data/radio_pcaps /app/static

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=config.settings

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120"]
