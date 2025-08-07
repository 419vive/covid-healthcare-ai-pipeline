#!/bin/bash

# Veeva Data Quality System - Quick Production Deployment Monitor
# This script provides rapid infrastructure monitoring during deployment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="/Users/jerrylaivivemachi/DS PROJECT/project5/veeva-data-quality-system"
MONITOR_SCRIPT="$PROJECT_DIR/deploy/production_monitor.py"
LOG_FILE="/tmp/veeva_quick_monitor.log"
PID_FILE="/tmp/veeva_monitor.pid"

# Function to print colored output
print_status() {
    local color=$1
    local message=$2
    echo -e "${color}[$(date '+%H:%M:%S')] $message${NC}"
}

# Function to check if monitoring is running
is_monitoring_running() {
    if [[ -f "$PID_FILE" ]]; then
        local pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        else
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1
}

# Function to start monitoring
start_monitoring() {
    local duration=${1:-60}
    local interval=${2:-30}
    
    if is_monitoring_running; then
        print_status $YELLOW "Monitoring is already running (PID: $(cat $PID_FILE))"
        return 0
    fi
    
    print_status $BLUE "Starting Veeva Data Quality System monitoring..."
    print_status $BLUE "Duration: ${duration} minutes, Interval: ${interval} seconds"
    
    # Check if Python monitoring script exists
    if [[ ! -f "$MONITOR_SCRIPT" ]]; then
        print_status $RED "Monitoring script not found: $MONITOR_SCRIPT"
        exit 1
    fi
    
    # Start monitoring in background
    python3 "$MONITOR_SCRIPT" --duration "$duration" --interval "$interval" --project-path "$PROJECT_DIR" > "$LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    
    print_status $GREEN "Monitoring started with PID: $pid"
    print_status $BLUE "Log file: $LOG_FILE"
    print_status $BLUE "Use 'tail -f $LOG_FILE' to follow logs"
}

# Function to stop monitoring
stop_monitoring() {
    if is_monitoring_running; then
        local pid=$(cat "$PID_FILE")
        kill "$pid" 2>/dev/null || true
        rm -f "$PID_FILE"
        print_status $YELLOW "Monitoring stopped (PID: $pid)"
    else
        print_status $YELLOW "No monitoring process is running"
    fi
}

# Function to show monitoring status
show_status() {
    if is_monitoring_running; then
        local pid=$(cat "$PID_FILE")
        print_status $GREEN "Monitoring is running (PID: $pid)"
        
        # Show recent log entries
        if [[ -f "$LOG_FILE" ]]; then
            print_status $BLUE "Recent log entries:"
            tail -n 10 "$LOG_FILE" | while read line; do
                echo "  $line"
            done
        fi
    else
        print_status $RED "Monitoring is not running"
    fi
}

# Function to run quick health check
quick_check() {
    print_status $BLUE "Running quick health check..."
    
    # Check if Python script exists and run one-shot monitoring
    if [[ -f "$MONITOR_SCRIPT" ]]; then
        python3 "$MONITOR_SCRIPT" --one-shot --project-path "$PROJECT_DIR"
    else
        print_status $RED "Python monitoring script not found, running basic checks..."
        
        # Basic system checks
        print_status $BLUE "System Resources:"
        echo "  CPU Usage: $(top -l 1 -s 0 | grep "CPU usage" | awk '{print $3}' | sed 's/%//')"
        echo "  Memory: $(vm_stat | grep "Pages free" | awk '{print $3}' | sed 's/\.//')"
        echo "  Disk: $(df -h / | awk 'NR==2{print $5 " used, " $4 " free"}')"
        
        # Check Docker
        if command -v docker &> /dev/null; then
            if docker info &> /dev/null; then
                print_status $GREEN "Docker daemon is running"
                echo "  Containers: $(docker ps --format '{{.Names}} ({{.Status}})' | wc -l) running"
            else
                print_status $RED "Docker daemon is not accessible"
            fi
        else
            print_status $YELLOW "Docker not installed"
        fi
        
        # Check database
        local db_file="$PROJECT_DIR/data/veeva_healthcare_data.db"
        if [[ -f "$db_file" ]]; then
            local db_size=$(du -h "$db_file" | awk '{print $1}')
            print_status $GREEN "Database found: $db_size"
        else
            print_status $YELLOW "Database not found: $db_file"
        fi
    fi
}

# Function to show system metrics
show_metrics() {
    print_status $BLUE "Current System Metrics:"
    
    # CPU Usage
    local cpu_usage=$(ps -A -o %cpu | awk '{sum += $1} END {printf "%.1f", sum}')
    echo "  CPU Usage: ${cpu_usage}%"
    
    # Memory Usage
    local memory_info=$(vm_stat | grep -E "(Pages free|Pages active|Pages inactive|Pages speculative|Pages wired down)")
    local free_pages=$(echo "$memory_info" | grep "Pages free" | awk '{print $3}' | sed 's/\.//')
    local active_pages=$(echo "$memory_info" | grep "Pages active" | awk '{print $3}' | sed 's/\.//')
    local inactive_pages=$(echo "$memory_info" | grep "Pages inactive" | awk '{print $3}' | sed 's/\.//')
    local wired_pages=$(echo "$memory_info" | grep "Pages wired down" | awk '{print $4}' | sed 's/\.//')
    
    local page_size=4096
    local total_memory=$((($free_pages + $active_pages + $inactive_pages + $wired_pages) * $page_size))
    local used_memory=$((($active_pages + $inactive_pages + $wired_pages) * $page_size))
    local memory_percent=$((used_memory * 100 / total_memory))
    
    echo "  Memory Usage: ${memory_percent}% ($(echo $used_memory | awk '{printf "%.1f", $1/1024/1024/1024}')GB used)"
    
    # Disk Usage
    local disk_info=$(df -h / | awk 'NR==2{print $5 " used, " $4 " available"}')
    echo "  Disk Usage: $disk_info"
    
    # Load Average
    local load_avg=$(uptime | awk -F'load averages:' '{print $2}' | awk '{print $1 $2 $3}')
    echo "  Load Average: $load_avg"
    
    # Process Count
    local process_count=$(ps aux | wc -l)
    echo "  Running Processes: $process_count"
}

# Function to tail monitoring logs
tail_logs() {
    if [[ -f "$LOG_FILE" ]]; then
        print_status $BLUE "Tailing monitoring logs (Ctrl+C to stop):"
        tail -f "$LOG_FILE"
    else
        print_status $RED "Log file not found: $LOG_FILE"
    fi
}

# Function to show help
show_help() {
    echo "Veeva Data Quality System - Quick Deployment Monitor"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  start [DURATION] [INTERVAL]  Start continuous monitoring"
    echo "                               DURATION: monitoring duration in minutes (default: 60)"
    echo "                               INTERVAL: check interval in seconds (default: 30)"
    echo "  stop                         Stop monitoring"
    echo "  status                       Show monitoring status"
    echo "  check                        Run quick health check"
    echo "  metrics                      Show current system metrics"
    echo "  logs                         Tail monitoring logs"
    echo "  help                         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 start                     # Start monitoring for 60 minutes, check every 30 seconds"
    echo "  $0 start 120 15              # Start monitoring for 120 minutes, check every 15 seconds"
    echo "  $0 check                     # Run immediate health check"
    echo "  $0 metrics                   # Show current system metrics"
    echo ""
}

# Main script logic
main() {
    local command=${1:-help}
    
    case "$command" in
        start)
            local duration=${2:-60}
            local interval=${3:-30}
            start_monitoring "$duration" "$interval"
            ;;
        stop)
            stop_monitoring
            ;;
        status)
            show_status
            ;;
        check)
            quick_check
            ;;
        metrics)
            show_metrics
            ;;
        logs)
            tail_logs
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_status $RED "Unknown command: $command"
            show_help
            exit 1
            ;;
    esac
}

# Trap signals to cleanup on exit
trap 'if is_monitoring_running; then stop_monitoring; fi' EXIT INT TERM

# Run main function
main "$@"