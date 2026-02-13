#!/usr/bin/env bash
# ============================================================================
# start-linux.sh — Start MT5 Docker + API + Dashboard on Linux
# ============================================================================
# Usage: ./start-linux.sh
#
# Starts all three services:
#   1. MT5 Docker container (gmag11/metatrader5_vnc) on ports 3000 + 8001
#   2. Trading API (FastAPI) on port 8000
#   3. Dashboard (Next.js) on port 3001 (3000 is taken by MT5 VNC)
#
# Press Ctrl+C to stop all services gracefully.
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$SCRIPT_DIR/api"
DASHBOARD_DIR="$SCRIPT_DIR/dashboard"
DASHBOARD_PORT=3001

# Docker compose file for MT5 (external repo)
MT5_COMPOSE="${MT5_DOCKER_COMPOSE:-$SCRIPT_DIR/../metatrader5-docker/docker-compose.yaml}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# PIDs for cleanup
API_PID=""
DASHBOARD_PID=""

cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"

    if [[ -n "$DASHBOARD_PID" ]] && kill -0 "$DASHBOARD_PID" 2>/dev/null; then
        echo -e "  ${CYAN}Stopping dashboard...${NC}"
        kill "$DASHBOARD_PID" 2>/dev/null
        wait "$DASHBOARD_PID" 2>/dev/null || true
    fi

    if [[ -n "$API_PID" ]] && kill -0 "$API_PID" 2>/dev/null; then
        echo -e "  ${CYAN}Stopping API...${NC}"
        kill "$API_PID" 2>/dev/null
        wait "$API_PID" 2>/dev/null || true
    fi

    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

check_command() {
    if ! command -v "$1" &>/dev/null; then
        echo -e "${RED}Error: '$1' is not installed.${NC}"
        echo "  $2"
        exit 1
    fi
}

wait_for_port() {
    local port=$1
    local name=$2
    local max_wait=$3
    local elapsed=0

    while ! ss -tln 2>/dev/null | grep -q ":${port} " && [[ $elapsed -lt $max_wait ]]; do
        sleep 1
        elapsed=$((elapsed + 1))
    done

    if [[ $elapsed -ge $max_wait ]]; then
        echo -e "${RED}Timed out waiting for $name on port $port${NC}"
        return 1
    fi
    return 0
}

# ============================================================================
echo -e "${BOLD}${BLUE}"
echo "  ╔══════════════════════════════════════════╗"
echo "  ║     Tania Signal Copier — Linux Start    ║"
echo "  ╚══════════════════════════════════════════╝"
echo -e "${NC}"

# --- Check prerequisites ---
echo -e "${BOLD}Checking prerequisites...${NC}"
check_command docker "Install Docker: https://docs.docker.com/engine/install/"
check_command uv "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"

if command -v bun &>/dev/null; then
    PKG_MGR="bun"
elif command -v npm &>/dev/null; then
    PKG_MGR="npm"
else
    echo -e "${RED}Error: Neither 'bun' nor 'npm' found. Install Node.js 20+ or Bun.${NC}"
    exit 1
fi
echo -e "  ${GREEN}docker, uv, $PKG_MGR${NC} — all found"

# --- 1) MT5 Docker ---
echo ""
echo -e "${BOLD}[1/3] MT5 Docker container${NC}"

if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^mt5$'; then
    echo -e "  ${GREEN}Already running${NC}"
else
    if docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q '^mt5$'; then
        echo -e "  ${CYAN}Starting existing container...${NC}"
        docker start mt5 >/dev/null 2>&1
    elif [[ -f "$MT5_COMPOSE" ]]; then
        echo -e "  ${CYAN}Starting via docker compose...${NC}"
        docker compose -f "$MT5_COMPOSE" up -d 2>&1 | sed 's/^/  /'
    else
        echo -e "  ${CYAN}Pulling and starting gmag11/metatrader5_vnc...${NC}"
        docker run -d --name mt5 \
            -p 3000:3000 -p 8001:8001 \
            gmag11/metatrader5_vnc 2>&1 | sed 's/^/  /'
    fi

    echo -e "  ${CYAN}Waiting for MT5 RPyC server (port 8001)...${NC}"
    if wait_for_port 8001 "MT5 RPyC" 30; then
        echo -e "  ${GREEN}MT5 Docker is up${NC}"
    else
        echo -e "  ${YELLOW}MT5 RPyC not ready yet — it may need more time on first run.${NC}"
        echo -e "  ${YELLOW}Open http://localhost:3000 to check the VNC interface.${NC}"
    fi
fi

echo -e "  VNC:  ${CYAN}http://localhost:3000${NC}"
echo -e "  RPyC: ${CYAN}localhost:8001${NC}"

# --- 2) API ---
echo ""
echo -e "${BOLD}[2/3] Trading API${NC}"

if ! [[ -f "$API_DIR/.env" ]]; then
    if [[ -f "$API_DIR/.env.example" ]]; then
        cp "$API_DIR/.env.example" "$API_DIR/.env"
        echo -e "  ${YELLOW}Created api/.env from .env.example — edit with your credentials${NC}"
    else
        echo -e "  ${RED}No api/.env or .env.example found${NC}"
        exit 1
    fi
fi

echo -e "  ${CYAN}Installing dependencies...${NC}"
(cd "$API_DIR" && uv sync 2>&1 | tail -1 | sed 's/^/  /')

echo -e "  ${CYAN}Starting API server on port 8000...${NC}"
(cd "$API_DIR" && uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 2>&1 | sed 's/^/  [API] /') &
API_PID=$!

if wait_for_port 8000 "API" 15; then
    echo -e "  ${GREEN}API is up${NC}"
else
    echo -e "  ${YELLOW}API still starting...${NC}"
fi
echo -e "  Docs: ${CYAN}http://localhost:8000/docs${NC}"

# --- 3) Dashboard ---
echo ""
echo -e "${BOLD}[3/3] Dashboard${NC}"

echo -e "  ${CYAN}Installing dependencies...${NC}"
(cd "$DASHBOARD_DIR" && $PKG_MGR install 2>&1 | tail -1 | sed 's/^/  /')

echo -e "  ${CYAN}Starting dashboard on port $DASHBOARD_PORT...${NC}"
(cd "$DASHBOARD_DIR" && PORT=$DASHBOARD_PORT $PKG_MGR run dev 2>&1 | sed 's/^/  [Dashboard] /') &
DASHBOARD_PID=$!

if wait_for_port "$DASHBOARD_PORT" "Dashboard" 20; then
    echo -e "  ${GREEN}Dashboard is up${NC}"
else
    echo -e "  ${YELLOW}Dashboard still starting...${NC}"
fi

# --- Summary ---
echo ""
echo -e "${BOLD}${GREEN}All services started!${NC}"
echo ""
echo -e "  ${BOLD}Dashboard:${NC}  ${CYAN}http://localhost:${DASHBOARD_PORT}${NC}"
echo -e "  ${BOLD}API docs:${NC}   ${CYAN}http://localhost:8000/docs${NC}"
echo -e "  ${BOLD}MT5 VNC:${NC}    ${CYAN}http://localhost:3000${NC}"
echo ""
echo -e "  Press ${BOLD}Ctrl+C${NC} to stop all services."
echo ""

# Wait for background processes
wait
