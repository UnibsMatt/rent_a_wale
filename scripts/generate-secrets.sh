#!/usr/bin/env bash
# Print strong values for the CHANGE_ME entries in .env.
set -euo pipefail

echo "SECRET_KEY=$(openssl rand -hex 32)"
echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)"
echo "FIRST_ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=')"
