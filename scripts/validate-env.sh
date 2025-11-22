#!/bin/bash
# scripts/validate-env.sh
# Validates that required environment variables are set for local development

set -e

REQUIRED_DEV=(DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD JWT_SECRET)

check_vars() {
  local missing=()

  for var in "${REQUIRED_DEV[@]}"; do
    if [[ -z "${!var}" ]]; then
      missing+=("$var")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "❌ Missing required variables: ${missing[*]}"
    return 1
  fi

  echo "✅ All required variables set"
  return 0
}

# Source .env.dev if it exists
if [[ -f .env.dev ]]; then
  echo "Loading .env.dev..."
  set -a
  source .env.dev
  set +a
fi

check_vars
