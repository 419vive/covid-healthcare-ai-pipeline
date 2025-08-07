#!/bin/bash
# Start Infrastructure Monitoring for Veeva Data Quality System
# This script starts the comprehensive monitoring system

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
LOG_DIR="$PROJECT_ROOT/logs"
DATA_DIR="$PROJECT_ROOT/data"
PID_FILE="$PROJECT_ROOT/monitoring.pid"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS] $1${NC}"
}

warning() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

# Check if monitoring is already running
if [[ -f "$PID_FILE" ]]; then
    if ps -p "$(cat "$PID_FILE")" > /dev/null 2>&1; then
        error "Monitoring is already running (PID: $(cat "$PID_FILE"))"
        exit 1
    else
        warning "Removing stale PID file"
        rm -f "$PID_FILE"
    fi
fi

# Create necessary directories
log "Setting up directories..."
mkdir -p "$LOG_DIR" "$DATA_DIR" "$PROJECT_ROOT/reports" "$PROJECT_ROOT/cache"

# Check system requirements
log "Checking system requirements..."

# Check Python
if ! command -v python3 &> /dev/null; then
    error "Python 3 is required but not installed"
    exit 1
fi

# Check required Python modules
REQUIRED_MODULES=("schedule" "psutil" "docker" "requests" "sqlite3")
for module in "${REQUIRED_MODULES[@]}"; do
    if ! python3 -c "import $module" &> /dev/null; then
        error "Required Python module '$module' is not installed"
        exit 1
    fi
done

# Check Docker (optional but recommended)
if ! command -v docker &> /dev/null; then
    warning "Docker not found - container monitoring will be limited"
fi

# Check disk space
DISK_FREE=$(df "$PROJECT_ROOT" | awk 'NR==2 {print $4}')
DISK_FREE_GB=$((DISK_FREE / 1024 / 1024))

if [[ $DISK_FREE_GB -lt 2 ]]; then
    error "Insufficient disk space: ${DISK_FREE_GB}GB free (minimum 2GB required)"
    exit 1
elif [[ $DISK_FREE_GB -lt 5 ]]; then
    warning "Low disk space: ${DISK_FREE_GB}GB free (recommended 5GB+)"
fi

# Check system load
LOAD_AVG=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
if (( $(echo "$LOAD_AVG > 2.0" | bc -l) )); then
    warning "High system load: $LOAD_AVG"
fi

# Start infrastructure monitoring
log "Starting Veeva Infrastructure Monitoring System..."

cd "$PROJECT_ROOT"

# Start monitoring in background
nohup python3 infrastructure_orchestrator.py --mode monitor --data-dir "$DATA_DIR" \
    > "$LOG_DIR/monitoring_startup.log" 2>&1 &

MONITORING_PID=$!
echo $MONITORING_PID > "$PID_FILE"

# Wait a moment to check if it started successfully
sleep 3

if ps -p $MONITORING_PID > /dev/null; then
    success "Infrastructure monitoring started successfully (PID: $MONITORING_PID)"
    
    # Display initial status
    log "Getting initial system status..."
    python3 infrastructure_orchestrator.py --mode dashboard --data-dir "$DATA_DIR" 2>/dev/null | \
        grep -E "(system_status|cpu_percent|memory_percent|disk_free_gb)" || true
        
else
    error "Failed to start monitoring system"
    rm -f "$PID_FILE"
    exit 1
fi

# Create monitoring status script
cat > "$PROJECT_ROOT/check_monitoring_status.sh" << 'EOF'
#!/bin/bash
PID_FILE="monitoring.pid"
if [[ -f "$PID_FILE" ]] && ps -p "$(cat "$PID_FILE")" > /dev/null 2>&1; then
    echo "Monitoring is running (PID: $(cat "$PID_FILE"))"
    python3 infrastructure_orchestrator.py --mode dashboard 2>/dev/null | head -10
else
    echo "Monitoring is not running"
fi
EOF

chmod +x "$PROJECT_ROOT/check_monitoring_status.sh"

# Create stop script
cat > "$PROJECT_ROOT/stop_monitoring.sh" << 'EOF'
#!/bin/bash
PID_FILE="monitoring.pid"
if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Stopping monitoring (PID: $PID)..."
        kill "$PID"
        sleep 2
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "Force stopping..."
            kill -9 "$PID"
        fi
        echo "Monitoring stopped"
    else
        echo "Monitoring was not running"
    fi
    rm -f "$PID_FILE"
else
    echo "No PID file found"
fi
EOF

chmod +x "$PROJECT_ROOT/stop_monitoring.sh"

# Display next steps
echo ""
success "Veeva Infrastructure Monitoring is now active!"
echo ""
log "Available commands:"
echo "  - Check status: ./check_monitoring_status.sh"
echo "  - Stop monitoring: ./stop_monitoring.sh"
echo "  - View logs: tail -f logs/infrastructure_orchestrator.log"
echo "  - View reports: ls -la reports/"
echo ""
log "Monitoring features:"
echo "  ✓ Health checks every 15 minutes"
echo "  ✓ Performance optimization hourly"
echo "  ✓ Database maintenance daily at 2 AM"
echo "  ✓ Daily reports at 8 AM"
echo "  ✓ Automated alerting and escalation"
echo "  ✓ Emergency response protocols"
echo ""
log "Dashboard URLs (when containers are running):"
echo "  - Grafana: http://localhost:3000"
echo "  - Prometheus: http://localhost:9090"
echo ""
warning "Remember to:"
echo "  1. Configure email/webhook alerts in config/alerting.json"
echo "  2. Set up log rotation in production"
echo "  3. Monitor disk space regularly"
echo "  4. Review daily reports"
echo ""

# Run initial health assessment
log "Running initial health assessment..."
python3 infrastructure_orchestrator.py --mode assessment --data-dir "$DATA_DIR" 2>/dev/null || \
    warning "Initial assessment failed - check logs"

success "Infrastructure monitoring setup completed!"