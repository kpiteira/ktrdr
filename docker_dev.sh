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
    docker-compose exec backend pytest
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