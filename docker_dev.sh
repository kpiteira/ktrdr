#!/bin/bash
# Docker development helper script for KTRDR

# Set colorful output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

function print_help() {
    echo -e "${BLUE}KTRDR Docker Development Helper${NC}"
    echo -e "${YELLOW}Usage:${NC}"
    echo -e "  ${GREEN}./docker_dev.sh${NC} ${YELLOW}<command>${NC}"
    echo -e "\n${YELLOW}Available commands:${NC}"
    echo -e "  ${GREEN}start${NC}        Start development environment"
    echo -e "  ${GREEN}stop${NC}         Stop development environment"
    echo -e "  ${GREEN}restart${NC}      Restart development environment"
    echo -e "  ${GREEN}logs${NC}         View logs from running containers"
    echo -e "  ${GREEN}shell${NC}        Open a shell in the backend container"
    echo -e "  ${GREEN}rebuild${NC}      Rebuild containers (preserving data)"
    echo -e "  ${GREEN}clean${NC}        Stop containers and remove volumes"
    echo -e "  ${GREEN}test${NC}         Run tests in the backend container"
    echo -e "  ${GREEN}lint${NC}         Run linting checks (flake8, mypy, black)"
    echo -e "  ${GREEN}ci${NC}           Run CI checks locally (linting, tests)"
    echo -e "  ${GREEN}prod${NC}         Start the production environment"
    echo -e "  ${GREEN}health${NC}       Check container health status"
    echo -e "  ${GREEN}help${NC}         Show this help message"
}

function start_dev() {
    echo -e "${BLUE}Starting KTRDR development environment...${NC}"
    docker-compose up -d
    echo -e "${GREEN}Development environment started!${NC}"
    echo -e "API available at: ${YELLOW}http://localhost:8000${NC}"
    echo -e "API docs available at: ${YELLOW}http://localhost:8000/api/docs${NC}"
}

function stop_dev() {
    echo -e "${BLUE}Stopping KTRDR development environment...${NC}"
    docker-compose down
    echo -e "${GREEN}Development environment stopped!${NC}"
}

function restart_dev() {
    echo -e "${BLUE}Restarting KTRDR development environment...${NC}"
    docker-compose restart
    echo -e "${GREEN}Development environment restarted!${NC}"
}

function view_logs() {
    echo -e "${BLUE}Showing logs from KTRDR containers...${NC}"
    echo -e "Press ${YELLOW}Ctrl+C${NC} to exit logs view."
    docker-compose logs -f
}

function open_shell() {
    echo -e "${BLUE}Opening shell in backend container...${NC}"
    docker-compose exec backend bash
}

function rebuild_containers() {
    echo -e "${BLUE}Rebuilding KTRDR containers...${NC}"
    docker-compose down
    docker-compose build --no-cache
    docker-compose up -d
    echo -e "${GREEN}Containers rebuilt and started!${NC}"
}

function clean_environment() {
    echo -e "${RED}WARNING: This will remove all containers and volumes.${NC}"
    read -p "Are you sure you want to continue? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Cleaning up KTRDR environment...${NC}"
        docker-compose down -v
        echo -e "${GREEN}Environment cleaned up!${NC}"
    fi
}

function run_tests() {
    echo -e "${BLUE}Running tests in backend container...${NC}"
    docker-compose exec backend python -m pytest
}

function run_linting() {
    echo -e "${BLUE}Running linting checks...${NC}"
    
    echo -e "${BLUE}Running flake8...${NC}"
    docker-compose exec backend python -m flake8 ktrdr/ --count --select=E9,F63,F7,F82 --show-source --statistics
    docker-compose exec backend python -m flake8 ktrdr/ --count --exit-zero --max-complexity=10 --max-line-length=100 --statistics
    
    echo -e "${BLUE}Running mypy...${NC}"
    docker-compose exec backend python -m mypy ktrdr/
    
    echo -e "${BLUE}Checking code style with black...${NC}"
    docker-compose exec backend python -m black --check ktrdr/
}

function run_ci_checks() {
    echo -e "${BLUE}Running CI checks locally...${NC}"
    
    if ! command -v act &> /dev/null; then
        echo -e "${YELLOW}The 'act' command is not installed. This is needed to run GitHub Actions locally.${NC}"
        echo -e "${BLUE}You can install it with: brew install act (macOS) or follow instructions at https://github.com/nektos/act${NC}"
        read -p "Would you like to continue with basic checks instead? [y/N] " response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            echo -e "${BLUE}Running basic checks...${NC}"
        else
            exit 1
        fi

        # Run linting
        run_linting
        
        # Run tests
        run_tests
    else
        echo -e "${BLUE}Running GitHub Actions workflows locally with act...${NC}"
        
        # Create cache directories if they don't exist
        mkdir -p ~/.cache/pip ~/.cache/uv
        
        # Detect architecture
        ARCH=$(uname -m)
        ARCH_FLAG=""
        if [[ "$ARCH" == "arm64" ]]; then
            echo -e "${YELLOW}Detected Apple Silicon (M-series) chip, using appropriate container architecture...${NC}"
            ARCH_FLAG="--container-architecture linux/amd64"
        fi
        
        echo -e "${BLUE}Using cached dependencies to speed up build...${NC}"
        
        # Run act with the workflow file and architecture flag if needed
        # Important: Specify push event explicitly to prevent -v flag from being interpreted as event
        if [[ "$ARCH" == "arm64" ]]; then
            act push -W .github/workflows/ci.yml $ARCH_FLAG
        else
            act push -W .github/workflows/ci.yml
        fi
            
        CI_EXIT_CODE=$?
        if [ $CI_EXIT_CODE -eq 0 ]; then
            echo -e "${GREEN}CI checks completed successfully!${NC}"
        else
            echo -e "${RED}CI checks failed with exit code: $CI_EXIT_CODE${NC}"
        fi
    fi
}

function start_prod() {
    echo -e "${BLUE}Starting KTRDR production environment...${NC}"
    docker-compose -f docker-compose.prod.yml up -d
    echo -e "${GREEN}Production environment started!${NC}"
}

function check_health() {
    echo -e "${BLUE}Checking container health status...${NC}"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# Main command handling
case "$1" in
    start)
        start_dev
        ;;
    stop)
        stop_dev
        ;;
    restart)
        restart_dev
        ;;
    logs)
        view_logs
        ;;
    shell)
        open_shell
        ;;
    rebuild)
        rebuild_containers
        ;;
    clean)
        clean_environment
        ;;
    test)
        run_tests
        ;;
    lint)
        run_linting
        ;;
    ci)
        run_ci_checks
        ;;
    prod)
        start_prod
        ;;
    health)
        check_health
        ;;
    help|*)
        print_help
        ;;
esac