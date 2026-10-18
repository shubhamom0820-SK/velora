#!/usr/bin/env bash
# The VM's startup script (P-49, D-1020): Google runs it as root on every boot,
# from the instance's `startup-script` metadata. It prepares the machine and
# nothing else: Docker, automatic security updates, the image registry's login,
# and the folders the deploy writes to. The API, the worker and Caddy arrive with
# a deploy (`infra/gce/deploy`), never from here, and come back after a reboot by
# Docker's restart policy.
#
# Safe to run any number of times: each step checks before it changes anything.
# Its log is the serial console's and journald's (`journalctl -u google-startup-scripts`).
# Changing this file changes nothing on a running VM until its metadata is set
# again (`infra/STAGING.md`, `infra/PRODUCTION.md`).
set -euo pipefail

say() { printf 'velora-startup: %s\n' "$*"; }

# Docker's apt signing key, by its full fingerprint, as Docker's install page
# publishes it; checked by Claude on 18 October 2026 against the key Docker serves.
DOCKER_KEY_FPR=9DC858229FC7DD38854AE2D88D81803C0EBFCD88
REGISTRY_HOST=asia-south1-docker.pkg.dev

export DEBIAN_FRONTEND=noninteractive

# --- Packages: Docker from Docker's repository, and unattended upgrades -------
if ! command -v docker >/dev/null || ! docker compose version >/dev/null 2>&1; then
  say "installing Docker"
  apt-get update -q
  apt-get install -y -q ca-certificates curl gnupg unattended-upgrades apt-listchanges
  install -d -m 0755 /etc/apt/keyrings
  key="$(mktemp)"
  curl -fsSL https://download.docker.com/linux/debian/gpg -o "$key"
  fpr="$(gpg --show-keys --with-colons "$key" | awk -F: '/^fpr:/ { print $10; exit }')"
  if [[ "$fpr" != "$DOCKER_KEY_FPR" ]]; then
    say "STOP: Docker's key has fingerprint '${fpr:-none}', not $DOCKER_KEY_FPR; nothing installed"
    exit 1
  fi
  gpg --dearmor --yes -o /etc/apt/keyrings/docker.gpg "$key"
  chmod 0644 /etc/apt/keyrings/docker.gpg
  rm -f "$key"
  codename="$(. /etc/os-release && echo "$VERSION_CODENAME")"
  echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $codename stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

# --- Docker's daemon -----------------------------------------------------------
# Logs rotate (10 MB x 5 per container), so they can't fill the disk. Containers
# keep running while dockerd itself restarts for an update (live-restore).
# userland-proxy off: published ports go through iptables, which keeps the
# client's own address as the connection's source, so Caddy's {remote_host} is
# the client, never Docker's gateway (D-1021).
daemon_json='{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "5" },
  "live-restore": true,
  "userland-proxy": false
}'
if [[ "$(cat /etc/docker/daemon.json 2>/dev/null)" != "$daemon_json" ]]; then
  say "writing Docker's daemon settings"
  printf '%s\n' "$daemon_json" > /etc/docker/daemon.json
  systemctl restart docker
fi
systemctl enable --now docker >/dev/null

# --- Security updates, and the reboot they may need ----------------------------
# Debian's security updates and Docker's own packages install unattended. A
# reboot, when one is needed, happens at 22:30 UTC, 04:00 IST; Docker brings the
# containers back and WebSocket clients reconnect (T-7.12).
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'APT'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT
cat > /etc/apt/apt.conf.d/52velora-unattended <<'APT'
Unattended-Upgrade::Origins-Pattern {
        "origin=Debian,codename=${distro_codename}-security,label=Debian-Security";
        "origin=Docker,label=Docker CE";
};
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "22:30";
APT

# --- The image registry: root's Docker pulls with the VM's own account ---------
# Google's Debian images ship the gcloud CLI; the VM's service account may only
# read this project's registry (block 3).
if ! command -v gcloud >/dev/null; then
  say "STOP: no gcloud on this image; the deploy can't read the registry or the secrets"
  exit 1
fi
gcloud auth configure-docker "$REGISTRY_HOST" --quiet >/dev/null 2>&1

# --- Where deploys write --------------------------------------------------------
# /etc/velora: the secrets each container reads, rendered at deploy time, root only.
# /opt/velora: the releases the deploy copies in, and what is running now.
install -d -m 0700 /etc/velora
install -d -m 0755 /opt/velora /opt/velora/releases /opt/velora/state /opt/velora/edge

say "ready"
