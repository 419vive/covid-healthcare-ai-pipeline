#!/bin/bash
"""
Emergency Disk Cleanup Script for Veeva Data Quality System
CRITICAL DISK SPACE MANAGEMENT - Use when system is at >95% disk usage
"""

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/app/logs/emergency_cleanup_$(date +%Y%m%d_%H%M%S).log"
CRITICAL_THRESHOLD=95
WARNING_THRESHOLD=85

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level=$1
    shift
    local message="$*"
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$level] $message" | tee -a "$LOG_FILE"
}

# Error handling
error_exit() {
    log "ERROR" "$1"
    exit 1
}

# Get disk usage percentage
get_disk_usage() {
    df / | awk 'NR==2 {print int($5)}'
}

# Emergency cleanup functions
emergency_log_cleanup() {
    log "INFO" "Starting emergency log cleanup..."
    
    local freed_mb=0
    
    # Clean Docker logs
    if command -v docker &> /dev/null; then
        log "INFO" "Cleaning Docker container logs..."
        docker container ls -q | xargs -r docker container logs --details 2>/dev/null | wc -c || true
        
        # Truncate Docker logs
        find /var/lib/docker/containers -name "*.log" -type f -exec truncate -s 0 {} \; 2>/dev/null || true
        log "INFO" "Docker logs truncated"
    fi
    
    # Clean application logs older than 1 day
    if [[ -d "/app/logs" ]]; then
        local before_size=$(du -sm /app/logs 2>/dev/null | cut -f1)
        find /app/logs -type f -name "*.log" -mtime +1 -delete 2>/dev/null || true
        find /app/logs -type f -name "*.log.*" -mtime +0 -delete 2>/dev/null || true
        local after_size=$(du -sm /app/logs 2>/dev/null | cut -f1)
        freed_mb=$((freed_mb + before_size - after_size))
        log "INFO" "Cleaned application logs: ${before_size}MB -> ${after_size}MB"
    fi
    
    echo $freed_mb
}

emergency_temp_cleanup() {
    log "INFO" "Starting emergency temporary files cleanup..."
    
    local freed_mb=0
    
    # Clean /tmp
    local before_size=$(du -sm /tmp 2>/dev/null | cut -f1)
    find /tmp -type f -atime +0 -delete 2>/dev/null || true
    find /tmp -type d -empty -delete 2>/dev/null || true
    local after_size=$(du -sm /tmp 2>/dev/null | cut -f1)
    freed_mb=$((freed_mb + before_size - after_size))
    
    # Clean Python cache
    find /app -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
    find /app -name "*.pyc" -delete 2>/dev/null || true
    
    # Clean pip cache
    if command -v pip &> /dev/null; then
        pip cache purge 2>/dev/null || true
    fi
    
    echo $freed_mb
}

emergency_reports_cleanup() {
    log "INFO" "Starting emergency reports cleanup..."
    
    local freed_mb=0
    
    if [[ -d "/app/reports" ]]; then
        local before_size=$(du -sm /app/reports 2>/dev/null | cut -f1)
        
        # Remove validation reports older than 7 days
        find /app/reports/validation -type f -mtime +7 -delete 2>/dev/null || true
        
        # Remove large report files older than 3 days
        find /app/reports -type f -size +10M -mtime +3 -delete 2>/dev/null || true
        
        # Clean empty directories
        find /app/reports -type d -empty -delete 2>/dev/null || true
        
        local after_size=$(du -sm /app/reports 2>/dev/null | cut -f1)
        freed_mb=$((freed_mb + before_size - after_size))
        log "INFO" "Cleaned reports: ${before_size}MB -> ${after_size}MB"
    fi
    
    echo $freed_mb
}

emergency_cache_cleanup() {
    log "INFO" "Starting emergency cache cleanup..."
    
    local freed_mb=0
    
    # Clean application cache
    if [[ -d "/app/cache" ]]; then
        local before_size=$(du -sm /app/cache 2>/dev/null | cut -f1)
        rm -rf /app/cache/* 2>/dev/null || true
        local after_size=$(du -sm /app/cache 2>/dev/null | cut -f1)
        freed_mb=$((freed_mb + before_size - after_size))
        log "INFO" "Cleaned application cache: ${before_size}MB -> ${after_size}MB"
    fi
    
    # Clean system cache
    sync
    echo 1 > /proc/sys/vm/drop_caches 2>/dev/null || true
    
    echo $freed_mb
}

emergency_docker_cleanup() {
    log "INFO" "Starting emergency Docker cleanup..."
    
    local freed_mb=0
    
    if command -v docker &> /dev/null; then
        # Get space before cleanup
        local docker_space_before=$(docker system df -v 2>/dev/null | grep -E "REPOSITORY|Local Volumes|Build Cache" || echo "")
        
        # Clean up Docker system
        docker system prune -af --volumes 2>/dev/null || true
        docker container prune -f 2>/dev/null || true
        docker image prune -af 2>/dev/null || true
        docker volume prune -f 2>/dev/null || true
        
        log "INFO" "Docker system cleaned"
        
        # Estimate freed space (Docker doesn't give exact numbers)
        freed_mb=50  # Conservative estimate
    fi
    
    echo $freed_mb
}

vacuum_databases() {
    log "INFO" "Starting emergency database optimization..."
    
    local freed_mb=0
    
    # Vacuum main database
    if [[ -f "/app/data/database/veeva_opendata.db" ]]; then
        local before_size=$(stat -f%z "/app/data/database/veeva_opendata.db" 2>/dev/null || echo "0")
        sqlite3 /app/data/database/veeva_opendata.db "VACUUM;" 2>/dev/null || true
        local after_size=$(stat -f%z "/app/data/database/veeva_opendata.db" 2>/dev/null || echo "0")
        freed_mb=$((freed_mb + (before_size - after_size) / 1024 / 1024))
        log "INFO" "Vacuumed main database"
    fi
    
    # Vacuum metrics database
    if [[ -f "/app/data/metrics.db" ]]; then
        local before_size=$(stat -f%z "/app/data/metrics.db" 2>/dev/null || echo "0")
        sqlite3 /app/data/metrics.db "VACUUM;" 2>/dev/null || true
        local after_size=$(stat -f%z "/app/data/metrics.db" 2>/dev/null || echo "0")
        freed_mb=$((freed_mb + (before_size - after_size) / 1024 / 1024))
        log "INFO" "Vacuumed metrics database"
    fi
    
    echo $freed_mb
}

# Main emergency cleanup function
run_emergency_cleanup() {
    local initial_usage=$(get_disk_usage)
    local total_freed=0
    
    echo -e "${RED}🚨 EMERGENCY DISK CLEANUP INITIATED${NC}"
    echo -e "${RED}Initial disk usage: ${initial_usage}%${NC}"
    log "CRITICAL" "Emergency disk cleanup started - disk usage at ${initial_usage}%"
    
    # Phase 1: Quick wins
    echo -e "${YELLOW}Phase 1: Quick cleanup operations...${NC}"
    
    freed=$(emergency_temp_cleanup)
    total_freed=$((total_freed + freed))
    log "INFO" "Phase 1 - Temp cleanup: ${freed}MB freed"
    
    freed=$(emergency_cache_cleanup)
    total_freed=$((total_freed + freed))
    log "INFO" "Phase 1 - Cache cleanup: ${freed}MB freed"
    
    current_usage=$(get_disk_usage)
    echo -e "${BLUE}After Phase 1: ${current_usage}% disk usage${NC}"
    
    # Phase 2: Log cleanup
    if [[ $current_usage -gt $WARNING_THRESHOLD ]]; then
        echo -e "${YELLOW}Phase 2: Log cleanup operations...${NC}"
        
        freed=$(emergency_log_cleanup)
        total_freed=$((total_freed + freed))
        log "INFO" "Phase 2 - Log cleanup: ${freed}MB freed"
        
        current_usage=$(get_disk_usage)
        echo -e "${BLUE}After Phase 2: ${current_usage}% disk usage${NC}"
    fi
    
    # Phase 3: Reports cleanup
    if [[ $current_usage -gt $WARNING_THRESHOLD ]]; then
        echo -e "${YELLOW}Phase 3: Reports cleanup operations...${NC}"
        
        freed=$(emergency_reports_cleanup)
        total_freed=$((total_freed + freed))
        log "INFO" "Phase 3 - Reports cleanup: ${freed}MB freed"
        
        current_usage=$(get_disk_usage)
        echo -e "${BLUE}After Phase 3: ${current_usage}% disk usage${NC}"
    fi
    
    # Phase 4: Database optimization
    if [[ $current_usage -gt $WARNING_THRESHOLD ]]; then
        echo -e "${YELLOW}Phase 4: Database optimization...${NC}"
        
        freed=$(vacuum_databases)
        total_freed=$((total_freed + freed))
        log "INFO" "Phase 4 - Database vacuum: ${freed}MB freed"
        
        current_usage=$(get_disk_usage)
        echo -e "${BLUE}After Phase 4: ${current_usage}% disk usage${NC}"
    fi
    
    # Phase 5: Docker cleanup (most disruptive)
    if [[ $current_usage -gt $WARNING_THRESHOLD ]]; then
        echo -e "${YELLOW}Phase 5: Docker system cleanup (may impact running services)...${NC}"
        read -p "Continue with Docker cleanup? This may temporarily disrupt services. (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            freed=$(emergency_docker_cleanup)
            total_freed=$((total_freed + freed))
            log "INFO" "Phase 5 - Docker cleanup: ${freed}MB freed"
            
            current_usage=$(get_disk_usage)
            echo -e "${BLUE}After Phase 5: ${current_usage}% disk usage${NC}"
        fi
    fi
    
    # Final status
    local final_usage=$(get_disk_usage)
    local usage_reduction=$((initial_usage - final_usage))
    
    echo
    echo -e "${GREEN}🎉 EMERGENCY CLEANUP COMPLETED${NC}"
    echo -e "${GREEN}Initial usage: ${initial_usage}%${NC}"
    echo -e "${GREEN}Final usage: ${final_usage}%${NC}"
    echo -e "${GREEN}Usage reduction: ${usage_reduction} percentage points${NC}"
    echo -e "${GREEN}Total space freed: ~${total_freed}MB${NC}"
    
    log "INFO" "Emergency cleanup completed: ${initial_usage}% -> ${final_usage}% (${total_freed}MB freed)"
    
    # Recommendations
    echo
    echo -e "${BLUE}📋 POST-CLEANUP RECOMMENDATIONS:${NC}"
    
    if [[ $final_usage -gt $CRITICAL_THRESHOLD ]]; then
        echo -e "${RED}• CRITICAL: Disk usage still above 95% - consider manual intervention${NC}"
        echo -e "${RED}• Check for large files: find / -size +100M -type f 2>/dev/null | head -10${NC}"
        echo -e "${RED}• Consider expanding disk space or moving data to external storage${NC}"
    elif [[ $final_usage -gt $WARNING_THRESHOLD ]]; then
        echo -e "${YELLOW}• WARNING: Disk usage still above 85% - monitor closely${NC}"
        echo -e "${YELLOW}• Schedule more frequent automated cleanups${NC}"
        echo -e "${YELLOW}• Review data retention policies${NC}"
    else
        echo -e "${GREEN}• SUCCESS: Disk usage is now at safe levels${NC}"
        echo -e "${GREEN}• Continue regular maintenance to prevent future issues${NC}"
    fi
    
    echo -e "${BLUE}• Review log file for details: ${LOG_FILE}${NC}"
}

# Check if running as root for some operations
check_permissions() {
    if [[ $EUID -ne 0 ]]; then
        log "WARNING" "Not running as root - some cleanup operations may fail"
        echo -e "${YELLOW}⚠️  Warning: Not running as root - some cleanup operations may be limited${NC}"
    fi
}

# Show help
show_help() {
    cat << EOF
Emergency Disk Cleanup Script for Veeva Data Quality System

USAGE:
    $0 [OPTION]

OPTIONS:
    --auto          Run automated cleanup without prompts
    --check-only    Only check disk usage, don't perform cleanup
    --help          Show this help message

DESCRIPTION:
    This script performs emergency disk cleanup when the system is running
    critically low on disk space (>95% usage). It performs cleanup in phases:
    
    Phase 1: Temporary files and cache
    Phase 2: Log files
    Phase 3: Old reports and validation files
    Phase 4: Database optimization (VACUUM)
    Phase 5: Docker system cleanup (with confirmation)

WARNING:
    This is an emergency script that may remove important files.
    Only use when disk space is critically low.

EOF
}

# Main script logic
main() {
    local auto_mode=false
    local check_only=false
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --auto)
                auto_mode=true
                shift
                ;;
            --check-only)
                check_only=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Create log directory
    mkdir -p "$(dirname "$LOG_FILE")"
    
    # Check permissions
    check_permissions
    
    # Get current disk usage
    local current_usage=$(get_disk_usage)
    
    echo -e "${BLUE}🔍 VEEVA SYSTEM DISK SPACE CHECK${NC}"
    echo -e "${BLUE}Current disk usage: ${current_usage}%${NC}"
    
    if [[ $check_only == true ]]; then
        if [[ $current_usage -gt $CRITICAL_THRESHOLD ]]; then
            echo -e "${RED}🚨 CRITICAL: Disk usage above ${CRITICAL_THRESHOLD}% - emergency cleanup recommended${NC}"
            exit 2
        elif [[ $current_usage -gt $WARNING_THRESHOLD ]]; then
            echo -e "${YELLOW}⚠️  WARNING: Disk usage above ${WARNING_THRESHOLD}% - cleanup recommended${NC}"
            exit 1
        else
            echo -e "${GREEN}✅ OK: Disk usage is at safe levels${NC}"
            exit 0
        fi
    fi
    
    # Determine if cleanup is needed
    if [[ $current_usage -le $WARNING_THRESHOLD ]]; then
        echo -e "${GREEN}✅ Disk usage is at safe levels (${current_usage}%) - no cleanup needed${NC}"
        exit 0
    fi
    
    # Warn about cleanup operation
    if [[ $current_usage -gt $CRITICAL_THRESHOLD ]]; then
        echo -e "${RED}🚨 CRITICAL DISK USAGE DETECTED (${current_usage}%)${NC}"
    else
        echo -e "${YELLOW}⚠️  HIGH DISK USAGE DETECTED (${current_usage}%)${NC}"
    fi
    
    # Confirm cleanup unless in auto mode
    if [[ $auto_mode == false ]]; then
        echo
        echo -e "${YELLOW}This script will perform aggressive cleanup operations that may:${NC}"
        echo -e "${YELLOW}• Remove old log files and reports${NC}"
        echo -e "${YELLOW}• Clear temporary files and caches${NC}"
        echo -e "${YELLOW}• Optimize databases${NC}"
        echo -e "${YELLOW}• Potentially affect running services${NC}"
        echo
        read -p "Do you want to proceed with emergency cleanup? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Cleanup cancelled by user"
            exit 0
        fi
    fi
    
    # Run cleanup
    run_emergency_cleanup
    
    # Exit with appropriate code
    local final_usage=$(get_disk_usage)
    if [[ $final_usage -gt $CRITICAL_THRESHOLD ]]; then
        exit 2
    elif [[ $final_usage -gt $WARNING_THRESHOLD ]]; then
        exit 1
    else
        exit 0
    fi
}

# Run main function
main "$@"