#!/usr/bin/env bash
# =============================================================================
# start_sole.sh — Local startup script for the SOLe Odoo instance
#
# Usage:
#   ./start_sole.sh            # start normally (foreground)
#   ./start_sole.sh --dev      # start in developer mode
#   ./start_sole.sh -u MODULE  # update a specific module
#   ./start_sole.sh -i MODULE  # install a specific module
#   ./start_sole.sh --stop     # kill any running instance on port 8069
# =============================================================================

set -euo pipefail

# ── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ODOO_BIN="${HOME}/odoo19_community/odoo-bin"
CONF="${SCRIPT_DIR}/sole.conf"
VENV="${HOME}/odoo_venv"
LOG="/tmp/sole_odoo.log"
PID_FILE="/tmp/sole_odoo.pid"

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[SOLe]${NC} $*"; }
warn()  { echo -e "${YELLOW}[SOLe]${NC} $*"; }
error() { echo -e "${RED}[SOLe]${NC} $*" >&2; }

# ── --stop flag ──────────────────────────────────────────────────────────────
if [[ "${1:-}" == "--stop" ]]; then
    if [[ -f "$PID_FILE" ]]; then
        PID="$(cat "$PID_FILE")"
        if kill -0 "$PID" 2>/dev/null; then
            info "Stopping SOLe (PID $PID)..."
            kill "$PID"
            rm -f "$PID_FILE"
            info "Stopped."
        else
            warn "PID $PID not running. Removing stale PID file."
            rm -f "$PID_FILE"
        fi
    else
        # fallback: kill by port
        PORT_PID="$(lsof -ti :8069 2>/dev/null || true)"
        if [[ -n "$PORT_PID" ]]; then
            info "Killing process on port 8069 (PID $PORT_PID)..."
            kill "$PORT_PID"
        else
            warn "No SOLe instance found."
        fi
    fi
    exit 0
fi

# ── Pre-flight checks ────────────────────────────────────────────────────────
if [[ ! -f "$ODOO_BIN" ]]; then
    error "Odoo binary not found at $ODOO_BIN"
    error "Edit ODOO_BIN in this script to point to your odoo-bin."
    exit 1
fi

if [[ ! -f "$CONF" ]]; then
    error "Configuration not found at $CONF"
    exit 1
fi

if [[ ! -d "$VENV" ]]; then
    error "Virtual environment not found at $VENV"
    exit 1
fi

# ── Check PostgreSQL ──────────────────────────────────────────────────────────
if ! pg_isready -h 127.0.0.1 -p 5432 -q 2>/dev/null; then
    warn "PostgreSQL does not appear to be ready on 127.0.0.1:5432"
    warn "Attempting to start PostgreSQL..."
    sudo service postgresql start 2>/dev/null || sudo systemctl start postgresql 2>/dev/null || true
    sleep 2
fi

# ── Activate virtual environment ──────────────────────────────────────────────
info "Activating virtual environment at $VENV..."
# shellcheck source=/dev/null
source "${VENV}/bin/activate"

# ── Ensure database exists ────────────────────────────────────────────────────
DB_NAME="$(grep '^db_name' "$CONF" | awk -F'=' '{print $2}' | xargs)"
DB_USER="$(grep '^db_user' "$CONF" | awk -F'=' '{print $2}' | xargs)"
DB_PASSWORD="$(grep '^db_password' "$CONF" | awk -F'=' '{print $2}' | xargs)"
DB_HOST="$(grep '^db_host' "$CONF" | awk -F'=' '{print $2}' | xargs)"
DB_PORT="$(grep '^db_port' "$CONF" | awk -F'=' '{print $2}' | xargs)"

export PGPASSWORD="$DB_PASSWORD"
if ! psql -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" -lqt 2>/dev/null | cut -d\| -f1 | grep -qw "$DB_NAME"; then
    info "Database '$DB_NAME' does not exist — creating..."
    createdb -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" "$DB_NAME" 2>/dev/null || true
    info "Database created. Odoo will initialize it on first start."
fi
unset PGPASSWORD

# ── Parse extra args ──────────────────────────────────────────────────────────
EXTRA_ARGS=()
DEV_MODE=false

for arg in "$@"; do
    case "$arg" in
        --dev) DEV_MODE=true ;;
        *)     EXTRA_ARGS+=("$arg") ;;
    esac
done

if $DEV_MODE; then
    EXTRA_ARGS+=("--dev=all")
    warn "Developer mode ON — do not use in production!"
fi

# ── Start Odoo ────────────────────────────────────────────────────────────────
info "Starting SOLe Odoo 19..."
info "  Config  : $CONF"
info "  Database: $DB_NAME"
info "  Port    : 8069"
info "  Log     : $LOG"
info "  URL     : http://localhost:8069"
echo ""

python "$ODOO_BIN" -c "$CONF" "${EXTRA_ARGS[@]}"
