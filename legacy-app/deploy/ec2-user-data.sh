#!/bin/bash
# EC2 user data: paste this into "Advanced details -> User data" when
# launching smb-migration-demo-legacy (Amazon Linux 2023). Runs once on
# first boot and installs Docker + the Compose plugin -- nothing app-
# specific. Deploying the app itself (copying the code over, running
# `docker compose up`) is still a manual step, on purpose: this instance
# is meant to look like unmanaged SMB infrastructure, not a templated
# one. See docs/roadmap.md, milestone 2.
set -e

dnf install -y docker
systemctl enable --now docker
usermod -aG docker ec2-user

mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
