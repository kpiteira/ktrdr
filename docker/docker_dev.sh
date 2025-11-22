#!/bin/bash
# ⚠️  DEPRECATED: This script is deprecated in favor of direct docker compose commands.
#
# Use instead:
#   docker compose -f docker-compose.dev.yml up        # Start all services
#   docker compose -f docker-compose.dev.yml up -d     # Start in background
#   docker compose -f docker-compose.dev.yml logs -f   # View logs
#   docker compose -f docker-compose.dev.yml down      # Stop all services
#   docker compose -f docker-compose.dev.yml build     # Rebuild after Dockerfile changes
#   docker compose -f docker-compose.dev.yml restart backend  # Restart specific service
#
# See CLAUDE.md for complete command reference.
#
# Docker development helper script for KTRDR (DEPRECATED)

# Change to docker directory for docker-compose commands
# Get the actual script location (resolving symlinks) - macOS compatible
SOURCE="$0"
while [ -h "$SOURCE" ]; do
  DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
cd "$SCRIPT_DIR"

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
    echo -e "\n${YELLOW}Core Development Commands:${NC}"
    echo -e "  ${GREEN}start${NC}        Start development environment"
    echo -e "  ${GREEN}stop${NC}         Stop development environment"
    echo -e "  ${GREEN}restart${NC}      Restart development environment"
    echo -e "  ${GREEN}logs${NC}         View logs from running containers"
    echo -e "  ${GREEN}logs-backend${NC} View logs from backend container"
    echo -e "  ${GREEN}logs-frontend${NC} View logs from frontend container"
    echo -e "  ${GREEN}logs-mcp${NC}     View logs from MCP server (application logs)"
    echo -e "  ${GREEN}logs-clear-frontend${NC} Clear logs and restart frontend container"
    echo -e "  ${GREEN}shell-backend${NC} Open a shell in the backend container"
    echo -e "  ${GREEN}shell-frontend${NC} Open a shell in the frontend container"
    echo -e "  ${GREEN}rebuild${NC}      Rebuild containers with caching (faster)"
    echo -e "  ${GREEN}rebuild-nocache${NC} Rebuild containers without cache (clean build)"
    echo -e "  ${GREEN}rebuild-backend${NC} Rebuild only the backend container"
    echo -e "  ${GREEN}rebuild-frontend${NC} Rebuild only the frontend container"
    echo -e "  ${GREEN}clean${NC}        Stop containers and remove volumes"
    echo -e "  ${GREEN}test${NC}         Run tests in the backend container"
    echo -e "  ${GREEN}lint${NC}         Run linting checks (flake8, mypy, black)"
    echo -e "  ${GREEN}ci${NC}           Run CI checks locally (linting, tests)"
    echo -e "  ${GREEN}prod${NC}         Start the production environment"
    echo -e "  ${GREEN}health${NC}       Check container health status"
    
    echo -e "\n${YELLOW}Research Agent Commands:${NC}"
    echo -e "  ${GREEN}start-research${NC}    Start research agent containers"
    echo -e "  ${GREEN}stop-research${NC}     Stop research agent containers"
    echo -e "  ${GREEN}restart-research${NC}  Restart research agent containers"
    echo -e "  ${GREEN}logs-research${NC}     View logs from research containers"
    echo -e "  ${GREEN}logs-coordinator${NC}  View logs from coordinator container"
    echo -e "  ${GREEN}logs-agent${NC}        View logs from agent containers"
    echo -e "  ${GREEN}shell-coordinator${NC} Open shell in coordinator container"
    echo -e "  ${GREEN}shell-agent${NC}       Open shell in agent container"
    echo -e "  ${GREEN}shell-postgres-research${NC} Open shell in research postgres"
    echo -e "  ${GREEN}rebuild-research${NC}  Rebuild research containers"
    echo -e "  ${GREEN}clean-research${NC}    Stop and remove research containers/volumes"
    echo -e "  ${GREEN}test-research${NC}     Run research agent tests"
    echo -e "  ${GREEN}health-research${NC}   Check research container health"
    
    echo -e "\n${YELLOW}Combined Commands:${NC}"
    echo -e "  ${GREEN}start-all${NC}         Start both KTRDR and research containers"
    echo -e "  ${GREEN}stop-all${NC}          Stop both KTRDR and research containers"
    echo -e "  ${GREEN}logs-all${NC}          View logs from all containers"
    echo -e "  ${GREEN}help${NC}              Show this help message"
}

function start_dev() {
    echo -e "${BLUE}Starting KTRDR development environment...${NC}"
    docker-compose up -d
    echo -e "${GREEN}Development environment started!${NC}"
    echo -e "API available at: ${YELLOW}http://localhost:8000${NC}"
    echo -e "API docs available at: ${YELLOW}http://localhost:8000/api/docs${NC}"
    echo -e "Frontend available at: ${YELLOW}http://localhost:3000${NC}"
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

function view_backend_logs() {
    echo -e "${BLUE}Showing logs from backend container...${NC}"
    echo -e "Press ${YELLOW}Ctrl+C${NC} to exit logs view."
    docker-compose logs -f backend
}

function view_frontend_logs() {
    echo -e "${BLUE}Showing logs from frontend container...${NC}"
    echo -e "Press ${YELLOW}Ctrl+C${NC} to exit logs view."
    docker-compose logs -f frontend
}

function view_mcp_logs() {
    echo -e "${BLUE}Showing logs from MCP server...${NC}"
    echo -e "${YELLOW}Note: MCP runs on-demand when Claude Desktop connects${NC}"
    echo -e "Press ${YELLOW}Ctrl+C${NC} to exit logs view."
    # Use file logs for persistent history (MCP runs on-demand, not continuously)
    docker-compose exec mcp tail -f /app/logs/mcp.log
}

function clear_frontend_logs() {
    echo -e "${BLUE}Clearing frontend container logs and restarting...${NC}"
    # Stop the frontend container
    docker-compose stop frontend
    # Remove the container (which clears its logs)
    docker-compose rm -f frontend
    # Start it again
    docker-compose up -d frontend
    echo -e "${GREEN}Frontend container restarted with fresh logs!${NC}"
    echo -e "To view logs, run: ${YELLOW}./docker_dev.sh logs-frontend${NC}"
}

function open_backend_shell() {
    echo -e "${BLUE}Opening shell in backend container...${NC}"
    docker-compose exec backend bash
}

function open_frontend_shell() {
    echo -e "${BLUE}Opening shell in frontend container...${NC}"
    docker-compose exec frontend sh
}

function rebuild_containers() {
    echo -e "${BLUE}Rebuilding KTRDR containers with optimized caching...${NC}"
    docker-compose down
    # Use our optimized build script
    ./build_docker_dev.sh
    docker-compose up -d
    echo -e "${GREEN}Containers rebuilt and started!${NC}"
}

function rebuild_nocache() {
    echo -e "${BLUE}Rebuilding KTRDR containers without cache (clean build)...${NC}"
    docker-compose down
    docker-compose build --no-cache
    docker-compose up -d
    echo -e "${GREEN}Containers rebuilt from scratch and started!${NC}"
}

function rebuild_backend() {
    echo -e "${BLUE}Rebuilding backend container...${NC}"
    docker-compose down backend
    # Build with optimized caching
    export DOCKER_BUILDKIT=1
    docker build \
      --build-arg BUILDKIT_INLINE_CACHE=1 \
      --cache-from ktrdr-backend:dev \
      -f backend/Dockerfile.dev \
      -t ktrdr-backend:dev ..
    docker-compose up -d backend
    echo -e "${GREEN}Backend container rebuilt and started!${NC}"
}

function rebuild_frontend() {
    echo -e "${BLUE}Rebuilding frontend container...${NC}"
    docker-compose down frontend
    # Build with optimized caching
    export DOCKER_BUILDKIT=1
    docker build \
      --build-arg BUILDKIT_INLINE_CACHE=1 \
      --cache-from ktrdr-frontend:dev \
      -f ../frontend/Dockerfile.dev \
      -t ktrdr-frontend:dev ../frontend
    docker-compose up -d frontend
    echo -e "${GREEN}Frontend container rebuilt and started!${NC}"
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

    echo -e "${BLUE}Running frontend linting checks...${NC}"
    docker-compose exec frontend npm run lint
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

# ============================================================================
# RESEARCH AGENT FUNCTIONS
# ============================================================================

function start_research() {
    echo -e "${BLUE}Starting KTRDR Research Agents...${NC}"
    
    # Environment check
    if [ -z "$OPENAI_API_KEY" ]; then
        echo -e "${YELLOW}⚠️  Notice: OPENAI_API_KEY not set - AI features will be limited${NC}"
    fi
    
    docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" up -d
    echo -e "${GREEN}Research agents started!${NC}"
    echo -e "Research API available at: ${YELLOW}http://localhost:8101${NC}"
    echo -e "Research Coordinator available at: ${YELLOW}http://localhost:8100${NC}"
    echo -e "Research Board MCP available at: ${YELLOW}http://localhost:8102${NC}"
    echo -e "Research PostgreSQL available at: ${YELLOW}localhost:5433${NC}"
}

function stop_research() {
    echo -e "${BLUE}Stopping KTRDR Research Agents...${NC}"
    docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" down
    echo -e "${GREEN}Research agents stopped!${NC}"
}

function restart_research() {
    echo -e "${BLUE}Restarting KTRDR Research Agents...${NC}"
    docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" restart
    echo -e "${GREEN}Research agents restarted!${NC}"
}

function view_research_logs() {
    echo -e "${BLUE}Showing logs from research containers...${NC}"
    echo -e "Press ${YELLOW}Ctrl+C${NC} to exit logs view."
    docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" logs -f
}

function view_coordinator_logs() {
    echo -e "${BLUE}Showing logs from coordinator container...${NC}"
    echo -e "Press ${YELLOW}Ctrl+C${NC} to exit logs view."
    docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" logs -f research-coordinator
}

function view_agent_logs() {
    echo -e "${BLUE}Showing logs from agent containers...${NC}"
    echo -e "Press ${YELLOW}Ctrl+C${NC} to exit logs view."
    docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" logs -f research-agent-mvp
}

function open_coordinator_shell() {
    echo -e "${BLUE}Opening shell in coordinator container...${NC}"
    docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" exec research-coordinator bash
}

function open_agent_shell() {
    echo -e "${BLUE}Opening shell in agent container...${NC}"
    # Connect to the first agent instance
    docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" exec research-agent-mvp bash
}

function open_postgres_research_shell() {
    echo -e "${BLUE}Opening shell in research postgres container...${NC}"
    docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" exec research-postgres psql -U research_admin -d research_agents
}

function rebuild_research() {
    echo -e "${BLUE}Rebuilding research containers with optimized caching...${NC}"
    docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" down
    # Use optimized build with BuildKit
    export DOCKER_BUILDKIT=1
    docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" build --parallel
    docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" up -d
    echo -e "${GREEN}Research containers rebuilt and started!${NC}"
}

function clean_research() {
    echo -e "${RED}WARNING: This will remove all research containers and volumes.${NC}"
    read -p "Are you sure you want to continue? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Cleaning up research environment...${NC}"
        docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" down -v
        echo -e "${GREEN}Research environment cleaned up!${NC}"
    fi
}

function run_research_tests() {
    echo -e "${BLUE}Running research agent tests...${NC}"
    docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" exec research-coordinator python -m pytest tests/research/ -v
}

function check_research_health() {
    echo -e "${BLUE}Checking research container health...${NC}"
    
    # Check for important environment variables
    if [ -z "$OPENAI_API_KEY" ]; then
        echo -e "${YELLOW}⚠️  Notice: OPENAI_API_KEY not set - AI features will be limited${NC}"
    fi
    
    docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" ps
    
    echo -e "\n${BLUE}Service connectivity tests:${NC}"
    
    # PostgreSQL health check
    echo -e "${YELLOW}Testing PostgreSQL connection...${NC}"
    if docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" exec research-postgres pg_isready -U research_admin -d research_agents > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PostgreSQL: Ready and accepting connections${NC}"
    else
        echo -e "${RED}✗ PostgreSQL: Connection failed${NC}"
    fi
    
    # Redis health check
    echo -e "${YELLOW}Testing Redis connection...${NC}"
    REDIS_RESPONSE=$(docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" exec research-redis redis-cli ping 2>/dev/null | tr -d '\r\n')
    if [ "$REDIS_RESPONSE" = "PONG" ]; then
        echo -e "${GREEN}✓ Redis: Responding correctly (PONG received)${NC}"
    else
        echo -e "${RED}✗ Redis: Connection failed or unexpected response${NC}"
    fi
    
    echo -e "\n${GREEN}Health check completed${NC}"
}

function start_all() {
    echo -e "${BLUE}Starting both KTRDR and Research systems...${NC}"
    start_dev
    start_research
}

function stop_all() {
    echo -e "${BLUE}Stopping both KTRDR and Research systems...${NC}"
    stop_dev
    stop_research
}

function view_all_logs() {
    echo -e "${BLUE}Showing logs from all containers...${NC}"
    echo -e "Press ${YELLOW}Ctrl+C${NC} to exit logs view."
    # Run both log commands in parallel
    (cd "$SCRIPT_DIR" && docker-compose logs -f) &
    KTRDR_PID=$!
    (docker-compose -f "$SCRIPT_DIR/docker-compose.research.yml" logs -f) &
    RESEARCH_PID=$!
    
    # Wait for either process to exit (user hits Ctrl+C)
    wait $KTRDR_PID $RESEARCH_PID
}

# ============================================================================
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
    logs-backend)
        view_backend_logs
        ;;
    logs-frontend)
        view_frontend_logs
        ;;
    logs-mcp)
        view_mcp_logs
        ;;
    logs-clear-frontend)
        clear_frontend_logs
        ;;
    shell-backend)
        open_backend_shell
        ;;
    shell-frontend)
        open_frontend_shell
        ;;
    rebuild)
        rebuild_containers
        ;;
    rebuild-nocache)
        rebuild_nocache
        ;;
    rebuild-backend)
        rebuild_backend
        ;;
    rebuild-frontend)
        rebuild_frontend
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
    start-research)
        start_research
        ;;
    stop-research)
        stop_research
        ;;
    restart-research)
        restart_research
        ;;
    logs-research)
        view_research_logs
        ;;
    logs-coordinator)
        view_coordinator_logs
        ;;
    logs-agent)
        view_agent_logs
        ;;
    shell-coordinator)
        open_coordinator_shell
        ;;
    shell-agent)
        open_agent_shell
        ;;
    shell-postgres-research)
        open_postgres_research_shell
        ;;
    rebuild-research)
        rebuild_research
        ;;
    clean-research)
        clean_research
        ;;
    test-research)
        run_research_tests
        ;;
    health-research)
        check_research_health
        ;;
    start-all)
        start_all
        ;;
    stop-all)
        stop_all
        ;;
    logs-all)
        view_all_logs
        ;;
    help|*)
        print_help
        ;;
esac