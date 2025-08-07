#!/bin/bash

# Veeva Data Quality System Monitoring Script
# Usage: ./monitor.sh [options]

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MONITORING_DIR="$PROJECT_ROOT/deploy/monitoring"
REPORTS_DIR="$PROJECT_ROOT/reports/monitoring"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Default values
MODE="status"  # status, start, stop, logs, health, metrics
FOLLOW_LOGS=false
GENERATE_REPORT=false
OUTPUT_FILE=""
ALERT_CHECK=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        status|start|stop|logs|health|metrics|alerts)
            MODE="$1"
            shift
            ;;
        --follow|-f)
            FOLLOW_LOGS=true
            shift
            ;;
        --report|-r)
            GENERATE_REPORT=true
            shift
            ;;
        --output|-o)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --check-alerts)
            ALERT_CHECK=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [mode] [options]"
            echo "Modes:"
            echo "  status     Show monitoring stack status (default)"
            echo "  start      Start monitoring services"
            echo "  stop       Stop monitoring services"
            echo "  logs       Show monitoring logs"
            echo "  health     Run comprehensive health check"
            echo "  metrics    Show current system metrics"
            echo "  alerts     Check active alerts"
            echo "Options:"
            echo "  --follow, -f       Follow logs (for logs mode)"
            echo "  --report, -r       Generate monitoring report"
            echo "  --output, -o FILE  Output file for reports"
            echo "  --check-alerts     Check for active alerts"
            echo "  -h, --help         Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create necessary directories
mkdir -p "$REPORTS_DIR"

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running or accessible"
        exit 1
    fi
}

# Function to check if monitoring stack is running
check_monitoring_stack() {
    cd "$PROJECT_ROOT/deploy"
    
    if docker-compose ps | grep -q "prometheus.*Up"; then
        return 0
    else
        return 1
    fi
}

# Function to start monitoring services
start_monitoring() {
    log_info "Starting monitoring services..."
    
    cd "$PROJECT_ROOT/deploy"
    
    # Start with monitoring profile
    docker-compose --profile monitoring up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to start..."
    sleep 15
    
    if check_monitoring_stack; then
        log_success "Monitoring services started successfully"
        log_info "Prometheus: http://localhost:9090"
        log_info "Grafana: http://localhost:3000 (admin/admin)"
    else
        log_error "Failed to start monitoring services"
        docker-compose logs
        exit 1
    fi
}

# Function to stop monitoring services
stop_monitoring() {
    log_info "Stopping monitoring services..."
    
    cd "$PROJECT_ROOT/deploy"
    docker-compose --profile monitoring down
    
    log_success "Monitoring services stopped"
}

# Function to show monitoring status
show_status() {
    log_info "Monitoring Stack Status:"
    
    cd "$PROJECT_ROOT/deploy"
    
    if check_monitoring_stack; then
        log_success "Monitoring stack is running"
        
        echo "\nServices:"
        docker-compose ps
        
        echo "\nResource Usage:"
        docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
        
    else
        log_warning "Monitoring stack is not running"
        log_info "Use '$0 start' to start monitoring services"
    fi
}

# Function to show logs
show_logs() {
    cd "$PROJECT_ROOT/deploy"
    
    if [[ "$FOLLOW_LOGS" == "true" ]]; then
        log_info "Following monitoring logs (Ctrl+C to exit)..."
        docker-compose logs -f prometheus grafana
    else
        log_info "Recent monitoring logs:"
        docker-compose logs --tail=50 prometheus grafana
    fi
}

# Function to run health check
run_health_check() {
    log_info "Running comprehensive health check..."
    
    # Run application health check
    cd "$PROJECT_ROOT"
    python python/utils/health_check.py > "$REPORTS_DIR/health_check_$(date +%Y%m%d_%H%M%S).json"
    
    if [[ $? -eq 0 ]]; then
        log_success "Health check completed successfully"
    else
        log_error "Health check failed"
        exit 1
    fi
    
    # Check monitoring stack health
    if check_monitoring_stack; then
        log_info "Checking Prometheus health..."
        PROMETHEUS_STATUS=$(curl -s http://localhost:9090/-/healthy || echo "failed")
        
        if [[ "$PROMETHEUS_STATUS" == "Prometheus is Healthy." ]]; then
            log_success "Prometheus is healthy"
        else
            log_warning "Prometheus health check failed"
        fi
        
        log_info "Checking Grafana health..."
        GRAFANA_STATUS=$(curl -s http://localhost:3000/api/health || echo "failed")
        
        if echo "$GRAFANA_STATUS" | grep -q '"database":"ok"'; then
            log_success "Grafana is healthy"
        else
            log_warning "Grafana health check failed"
        fi
    else
        log_warning "Monitoring stack is not running"
    fi
}

# Function to show current metrics
show_metrics() {
    log_info "Current System Metrics:"
    
    # System metrics
    echo "\n=== System Resources ==="
    echo "CPU Usage: $(top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print 100 - $1 "%"}' 2>/dev/null || echo "N/A")"
    echo "Memory Usage: $(free | grep Mem | awk '{printf "%.1f%%", $3/$2 * 100.0}' 2>/dev/null || echo "N/A")"
    echo "Disk Usage: $(df -h / | awk 'NR==2 {print $5}' 2>/dev/null || echo "N/A")"
    echo "Load Average: $(uptime | awk '{print $(NF-2), $(NF-1), $NF}' 2>/dev/null || echo "N/A")"
    
    # Application metrics
    echo "\n=== Application Metrics ==="
    cd "$PROJECT_ROOT"
    
    if [[ -f "python/main.py" ]]; then
        # Run status check
        python python/main.py status 2>/dev/null || echo "Application status check failed"
    fi
    
    # Database metrics
    if [[ -f "data/database/veeva_opendata.db" ]]; then
        DB_SIZE=$(du -h "data/database/veeva_opendata.db" | cut -f1 2>/dev/null || echo "N/A")
        echo "Database Size: $DB_SIZE"
    fi
    
    # Recent activity
    echo "\n=== Recent Activity ==="
    if [[ -d "logs" ]]; then
        RECENT_ERRORS=$(find logs -name "*.log" -mtime -1 -exec grep -l "ERROR" {} \; 2>/dev/null | wc -l)
        echo "Recent Error Logs: $RECENT_ERRORS files"
    fi
    
    if [[ -d "reports" ]]; then
        RECENT_REPORTS=$(find reports -name "*" -mtime -1 -type f 2>/dev/null | wc -l)
        echo "Recent Reports: $RECENT_REPORTS files"
    fi
}

# Function to check alerts
check_alerts() {
    log_info "Checking for active alerts..."
    
    if ! check_monitoring_stack; then
        log_warning "Monitoring stack is not running, cannot check alerts"
        return
    fi
    
    # Query Prometheus for active alerts
    ALERTS=$(curl -s "http://localhost:9090/api/v1/alerts" | jq '.data[] | select(.state == "firing")' 2>/dev/null || echo "{}")
    
    if [[ "$ALERTS" == "{}" || -z "$ALERTS" ]]; then
        log_success "No active alerts"
    else
        log_warning "Active alerts detected:"
        echo "$ALERTS" | jq -r '.labels.alertname + ": " + .annotations.summary' 2>/dev/null || echo "$ALERTS"
    fi
}

# Function to generate monitoring report
generate_report() {
    local output_file="$1"
    [[ -z "$output_file" ]] && output_file="$REPORTS_DIR/monitoring_report_$(date +%Y%m%d_%H%M%S).md"
    
    log_info "Generating monitoring report: $output_file"
    
    cat > "$output_file" << EOF
# Veeva Data Quality System - Monitoring Report
Generated: $(date)

## System Status
$(show_status 2>&1)

## Health Check Results
$(run_health_check 2>&1)

## Current Metrics
$(show_metrics 2>&1)

## Alert Status
$(check_alerts 2>&1)

## Recent Logs
$(show_logs 2>&1 | tail -20)
EOF
    
    log_success "Report generated: $output_file"
}

# Main execution
check_docker

case $MODE in
    "status")
        show_status
        ;;
    "start")
        start_monitoring
        ;;
    "stop")
        stop_monitoring
        ;;
    "logs")
        show_logs
        ;;
    "health")
        run_health_check
        ;;
    "metrics")
        show_metrics
        ;;
    "alerts")
        check_alerts
        ;;
    *)
        log_error "Unknown mode: $MODE"
        exit 1
        ;;
esac

# Generate report if requested
if [[ "$GENERATE_REPORT" == "true" ]]; then
    generate_report "$OUTPUT_FILE"
fi

# Check alerts if requested
if [[ "$ALERT_CHECK" == "true" ]]; then
    check_alerts
fi

exit 0