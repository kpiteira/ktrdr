#!/bin/bash

# KTRDR Environment Sync Script
# This script copies the root .env file to docker/.env for Docker Compose
# This ensures secrets are properly propagated to Docker containers

set -e  # Exit on any error

# Colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# File paths
ENV_SOURCE="$PROJECT_ROOT/.env"
ENV_TARGET="$PROJECT_ROOT/docker/.env"

# Function to sync .env file
sync_env() {
    echo -e "${BLUE}Syncing environment configuration...${NC}"

    # Check if source .env exists
    if [ ! -f "$ENV_SOURCE" ]; then
        echo -e "${RED}ERROR: .env file not found at: $ENV_SOURCE${NC}"
        echo -e "${YELLOW}Please create .env from .env.example:${NC}"
        echo -e "  cp .env.example .env"
        exit 1
    fi

    # Validate .env has required variables
    echo -e "${BLUE}Validating .env configuration...${NC}"

    REQUIRED_VARS=(
        "POSTGRES_HOST"
        "POSTGRES_PORT"
        "POSTGRES_DB"
        "POSTGRES_USER"
        "POSTGRES_PASSWORD"
    )

    MISSING_VARS=()
    for var in "${REQUIRED_VARS[@]}"; do
        if ! grep -q "^${var}=" "$ENV_SOURCE"; then
            MISSING_VARS+=("$var")
        fi
    done

    if [ ${#MISSING_VARS[@]} -gt 0 ]; then
        echo -e "${RED}ERROR: Missing required variables in .env:${NC}"
        for var in "${MISSING_VARS[@]}"; do
            echo -e "  - $var"
        done
        echo -e "${YELLOW}Please add these variables to: $ENV_SOURCE${NC}"
        exit 1
    fi

    # Check if POSTGRES_PASSWORD is still the example password
    if grep -q "^POSTGRES_PASSWORD=ktrdr_dev_password" "$ENV_SOURCE"; then
        echo -e "${YELLOW}WARNING: Using default development password${NC}"
        echo -e "${YELLOW}For production, use a strong password in .env${NC}"
    fi

    # Copy .env to docker/.env
    echo -e "${BLUE}Copying .env to docker/.env...${NC}"
    cp "$ENV_SOURCE" "$ENV_TARGET"

    # Verify copy
    if [ -f "$ENV_TARGET" ]; then
        echo -e "${GREEN}✓ Environment configuration synced successfully${NC}"

        # Show which password will be used
        PASSWORD=$(grep "^POSTGRES_PASSWORD=" "$ENV_TARGET" | cut -d'=' -f2)
        PASSWORD_MASKED="${PASSWORD:0:4}****${PASSWORD: -4}"
        echo -e "${GREEN}  PostgreSQL password: $PASSWORD_MASKED${NC}"
    else
        echo -e "${RED}ERROR: Failed to copy .env to docker/.env${NC}"
        exit 1
    fi
}

# Function to clean up docker/.env
clean_env() {
    echo -e "${BLUE}Cleaning up docker/.env...${NC}"

    if [ -f "$ENV_TARGET" ]; then
        rm "$ENV_TARGET"
        echo -e "${GREEN}✓ docker/.env removed${NC}"
    else
        echo -e "${YELLOW}docker/.env does not exist (nothing to clean)${NC}"
    fi
}

# Function to show current env status
status_env() {
    echo -e "${BLUE}Environment Configuration Status${NC}"
    echo -e "=================================="
    echo ""

    # Check root .env
    if [ -f "$ENV_SOURCE" ]; then
        echo -e "${GREEN}✓ Root .env exists${NC}: $ENV_SOURCE"

        # Show PostgreSQL config (masked)
        if grep -q "^POSTGRES_PASSWORD=" "$ENV_SOURCE"; then
            PASSWORD=$(grep "^POSTGRES_PASSWORD=" "$ENV_SOURCE" | cut -d'=' -f2)
            PASSWORD_MASKED="${PASSWORD:0:4}****${PASSWORD: -4}"
            echo -e "  PostgreSQL User: $(grep '^POSTGRES_USER=' "$ENV_SOURCE" | cut -d'=' -f2)"
            echo -e "  PostgreSQL Password: $PASSWORD_MASKED"
            echo -e "  PostgreSQL Database: $(grep '^POSTGRES_DB=' "$ENV_SOURCE" | cut -d'=' -f2)"
        fi
    else
        echo -e "${RED}✗ Root .env missing${NC}: $ENV_SOURCE"
    fi

    echo ""

    # Check docker/.env
    if [ -f "$ENV_TARGET" ]; then
        echo -e "${GREEN}✓ Docker .env exists${NC}: $ENV_TARGET"

        # Check if it's in sync
        if diff "$ENV_SOURCE" "$ENV_TARGET" > /dev/null 2>&1; then
            echo -e "${GREEN}  In sync with root .env${NC}"
        else
            echo -e "${YELLOW}  ⚠ OUT OF SYNC with root .env${NC}"
            echo -e "${YELLOW}  Run: ./scripts/sync-env.sh sync${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Docker .env missing${NC}: $ENV_TARGET"
        echo -e "${YELLOW}  Run: ./scripts/sync-env.sh sync${NC}"
    fi

    echo ""
}

# Main command handling
case "${1:-sync}" in
    sync)
        sync_env
        ;;
    clean)
        clean_env
        ;;
    status)
        status_env
        ;;
    help)
        echo -e "${BLUE}KTRDR Environment Sync Script${NC}"
        echo -e "Usage: $0 [command]"
        echo -e ""
        echo -e "Commands:"
        echo -e "  ${GREEN}sync${NC}    Copy .env to docker/.env (default)"
        echo -e "  ${GREEN}clean${NC}   Remove docker/.env"
        echo -e "  ${GREEN}status${NC}  Show environment configuration status"
        echo -e "  ${GREEN}help${NC}    Show this help message"
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        echo -e "Run '$0 help' for usage information"
        exit 1
        ;;
esac
