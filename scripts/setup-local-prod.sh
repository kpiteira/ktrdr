#!/bin/bash
# scripts/setup-local-prod.sh
# Interactive setup for KTRDR local-prod environment
#
# This script solves the chicken-and-egg problem: you need the CLI to
# setup local-prod, but you need a clone to have the CLI.
#
# Usage:
#   ./setup-local-prod.sh               # Interactive setup
#   ./setup-local-prod.sh --check-only  # Just check prerequisites
#   ./setup-local-prod.sh --help        # Show usage
#   ./setup-local-prod.sh --non-interactive --path=/path/to/dest  # CI/scripted mode

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/kpiteira/ktrdr.git"
DEFAULT_PATH="$HOME/Documents/dev/ktrdr-prod"
ONEPASSWORD_ITEM="ktrdr-local-prod"
REQUIRED_FIELDS="db_password, jwt_secret, anthropic_api_key, grafana_password"

# Script options
CHECK_ONLY=false
NON_INTERACTIVE=false
DEST_PATH=""

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

usage() {
    echo "Usage: $(basename "$0") [OPTIONS]"
    echo ""
    echo "Interactive setup for KTRDR local-prod environment."
    echo ""
    echo "Options:"
    echo "  --help            Show this help message"
    echo "  --check-only      Only check prerequisites, don't install"
    echo "  --non-interactive Run without prompts (for CI/scripting)"
    echo "  --path=PATH       Installation path (default: $DEFAULT_PATH)"
    echo ""
    echo "Examples:"
    echo "  $(basename "$0")                    # Interactive setup"
    echo "  $(basename "$0") --check-only       # Check prerequisites only"
    echo "  $(basename "$0") --non-interactive --path=/tmp/ktrdr-prod"
    echo ""
}

print_banner() {
    echo ""
    echo -e "${CYAN}${BOLD}=== KTRDR Local-Prod Setup ===${NC}"
    echo ""
}

check_prereq() {
    local name="$1"
    local cmd="$2"
    local install_hint="$3"

    if command -v "$cmd" &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} $name"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name (not found)"
        if [ -n "$install_hint" ]; then
            echo -e "      ${YELLOW}Install: $install_hint${NC}"
        fi
        return 1
    fi
}

check_docker_running() {
    if docker info &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} Docker Desktop is running"
        return 0
    else
        echo -e "  ${RED}✗${NC} Docker Desktop is not running"
        echo -e "      ${YELLOW}Start Docker Desktop and try again${NC}"
        return 1
    fi
}

check_1password_auth() {
    if op account get &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} 1Password authenticated"
        return 0
    else
        echo -e "  ${YELLOW}!${NC} 1Password not authenticated (optional)"
        return 1
    fi
}

explain_1password() {
    echo ""
    echo -e "${BOLD}1Password Configuration (optional but recommended):${NC}"
    echo ""
    echo "  For secure secrets management, create a 1Password item:"
    echo ""
    echo -e "    ${CYAN}Item name:${NC} $ONEPASSWORD_ITEM"
    echo -e "    ${CYAN}Required fields:${NC} $REQUIRED_FIELDS"
    echo ""
    echo "  Without 1Password, the system will use insecure defaults."
    echo "  You can configure 1Password later by running:"
    echo "    op signin"
    echo ""
}

# -----------------------------------------------------------------------------
# Main Logic
# -----------------------------------------------------------------------------

parse_args() {
    for arg in "$@"; do
        case $arg in
            --help)
                usage
                exit 0
                ;;
            --check-only)
                CHECK_ONLY=true
                ;;
            --non-interactive)
                NON_INTERACTIVE=true
                ;;
            --path=*)
                DEST_PATH="${arg#*=}"
                ;;
            *)
                echo -e "${RED}Unknown option: $arg${NC}"
                usage
                exit 1
                ;;
        esac
    done
}

check_prerequisites() {
    echo "Checking prerequisites..."
    echo ""

    local missing=0

    check_prereq "Git" "git" "brew install git" || missing=1
    check_prereq "Docker" "docker" "Install Docker Desktop from docker.com" || missing=1
    check_prereq "uv (Python package manager)" "uv" "curl -LsSf https://astral.sh/uv/install.sh | sh" || missing=1
    check_prereq "1Password CLI (op)" "op" "brew install 1password-cli" || missing=1

    echo ""

    # Docker running check
    if command -v docker &> /dev/null; then
        check_docker_running || missing=1
    fi

    # 1Password auth check (optional, don't fail)
    local op_auth=0
    if command -v op &> /dev/null; then
        check_1password_auth || op_auth=1
    fi

    explain_1password

    if [ $missing -eq 1 ]; then
        echo -e "${RED}${BOLD}Some prerequisites are missing.${NC}"
        echo "Install the missing tools before continuing."
        return 1
    fi

    echo -e "${GREEN}${BOLD}All prerequisites met!${NC}"
    return 0
}

get_installation_path() {
    if [ -n "$DEST_PATH" ]; then
        # Path provided via command line
        return 0
    fi

    if [ "$NON_INTERACTIVE" = true ]; then
        DEST_PATH="$DEFAULT_PATH"
        return 0
    fi

    echo ""
    read -p "Installation path [$DEFAULT_PATH]: " input_path
    DEST_PATH="${input_path:-$DEFAULT_PATH}"
}

validate_destination() {
    if [ -d "$DEST_PATH" ]; then
        echo -e "${RED}Error:${NC} Directory already exists: $DEST_PATH"
        echo "  Choose a different path or remove the existing directory."
        return 1
    fi

    # Check parent directory exists
    local parent_dir
    parent_dir=$(dirname "$DEST_PATH")
    if [ ! -d "$parent_dir" ]; then
        echo -e "${YELLOW}Note:${NC} Parent directory will be created: $parent_dir"
        if [ "$NON_INTERACTIVE" = false ]; then
            read -p "Continue? [Y/n] " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Nn]$ ]]; then
                return 1
            fi
        fi
    fi

    return 0
}

clone_repository() {
    echo ""
    echo "Cloning repository to $DEST_PATH..."
    echo ""

    git clone "$REPO_URL" "$DEST_PATH"

    echo -e "${GREEN}✓${NC} Repository cloned"
}

install_dependencies() {
    echo ""
    echo "Installing dependencies..."
    echo ""

    cd "$DEST_PATH"
    uv sync

    echo -e "${GREEN}✓${NC} Dependencies installed"
}

initialize_local_prod() {
    echo ""
    echo "Initializing local-prod..."
    echo ""

    cd "$DEST_PATH"
    uv run ktrdr local-prod init

    echo -e "${GREEN}✓${NC} Local-prod initialized"
}

setup_shared_data() {
    if [ "$NON_INTERACTIVE" = true ]; then
        # In non-interactive mode, skip shared data setup
        echo ""
        echo -e "${YELLOW}Skipping shared data setup in non-interactive mode.${NC}"
        echo "Run 'ktrdr sandbox init-shared --minimal' later if needed."
        return 0
    fi

    echo ""
    read -p "Initialize shared data? [Y/n] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        return 0
    fi

    echo ""
    echo "Shared data options:"
    echo "  1. Copy from existing KTRDR environment (e.g., ~/Documents/dev/ktrdr2)"
    echo "  2. Create minimal shared data (empty directories)"
    echo ""
    read -p "Enter path to copy from, or 'minimal' for empty setup: " shared_source

    cd "$DEST_PATH"

    if [ "$shared_source" = "minimal" ]; then
        uv run ktrdr sandbox init-shared --minimal
    elif [ -n "$shared_source" ]; then
        uv run ktrdr sandbox init-shared --from "$shared_source"
    fi

    echo -e "${GREEN}✓${NC} Shared data initialized"
}

offer_to_start() {
    if [ "$NON_INTERACTIVE" = true ]; then
        return 0
    fi

    echo ""
    read -p "Start local-prod now? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo ""
        echo "Starting local-prod..."
        cd "$DEST_PATH"
        uv run ktrdr local-prod up
    fi
}

print_summary() {
    echo ""
    echo -e "${GREEN}${BOLD}=== Setup Complete ===${NC}"
    echo ""
    echo "Local-prod is installed at: $DEST_PATH"
    echo ""
    echo "To start local-prod:"
    echo "  cd $DEST_PATH"
    echo "  ktrdr local-prod up"
    echo ""
    echo "To stop local-prod:"
    echo "  ktrdr local-prod down"
    echo ""
    echo "To view status:"
    echo "  ktrdr local-prod status"
    echo ""
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

main() {
    parse_args "$@"

    print_banner

    # Check prerequisites
    if ! check_prerequisites; then
        exit 1
    fi

    # If check-only mode, exit here
    if [ "$CHECK_ONLY" = true ]; then
        echo ""
        echo "Prerequisite check complete."
        exit 0
    fi

    # Get installation path
    get_installation_path

    # Validate destination
    if ! validate_destination; then
        exit 1
    fi

    # Clone repository
    clone_repository

    # Install dependencies
    install_dependencies

    # Initialize local-prod
    initialize_local_prod

    # Setup shared data (optional)
    setup_shared_data

    # Offer to start
    offer_to_start

    # Print summary
    print_summary
}

main "$@"
