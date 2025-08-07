#!/bin/bash

# Veeva Data Quality System Maintenance Script
# Usage: ./maintenance.sh [task] [options]

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOGS_DIR="$PROJECT_ROOT/logs"
REPORTS_DIR="$PROJECT_ROOT/reports"
BACKUP_DIR="$PROJECT_ROOT/deploy/backups"

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
TASK="all"
DRY_RUN=false
VERBOSE=false
FORCE=false
RETENTION_DAYS=30

# Function to show usage
show_usage() {
    echo "Usage: $0 [task] [options]"
    echo "Tasks:"
    echo "  all              Run all maintenance tasks (default)"
    echo "  cleanup          Clean up old logs and reports"
    echo "  optimize         Optimize database and system"
    echo "  backup           Create system backup"
    echo "  health-check     Run comprehensive health check"
    echo "  update-config    Update configuration files"
    echo "  rotate-logs      Rotate and compress log files"
    echo "  vacuum-db        Vacuum and analyze database"
    echo "  check-disk       Check disk usage and cleanup"
    echo "Options:"
    echo "  --dry-run        Show what would be done without executing"
    echo "  --verbose, -v    Enable verbose output"
    echo "  --force          Force execution without confirmations"
    echo "  --retention N    Set retention period in days (default: 30)"
    echo "  -h, --help       Show this help message"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        all|cleanup|optimize|backup|health-check|update-config|rotate-logs|vacuum-db|check-disk)
            TASK="$1"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --retention)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Enable verbose output if requested
if [[ "$VERBOSE" == "true" ]]; then
    set -x
fi

# Function to execute command with dry-run support
execute_cmd() {
    local cmd="$1"
    local description="$2"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] $description: $cmd"
    else
        if [[ "$VERBOSE" == "true" ]]; then
            log_info "Executing: $cmd"
        fi
        eval "$cmd"
    fi
}

# Function to cleanup old files
cleanup_old_files() {
    log_info "Cleaning up old files (retention: $RETENTION_DAYS days)..."
    
    # Cleanup old log files
    if [[ -d "$LOGS_DIR" ]]; then
        log_info "Cleaning up log files older than $RETENTION_DAYS days..."
        execute_cmd "find '$LOGS_DIR' -name '*.log' -mtime +$RETENTION_DAYS -type f -delete" "Delete old log files"
        
        # Count remaining log files
        LOG_COUNT=$(find "$LOGS_DIR" -name '*.log' -type f | wc -l)
        log_success "Log files remaining: $LOG_COUNT"
    fi
    
    # Cleanup old report files
    if [[ -d "$REPORTS_DIR" ]]; then
        log_info "Cleaning up report files older than $RETENTION_DAYS days..."
        execute_cmd "find '$REPORTS_DIR' -name '*.xlsx' -o -name '*.csv' -o -name '*.json' | xargs -I {} find {} -mtime +$RETENTION_DAYS -type f -delete" "Delete old report files"
        
        # Count remaining report files
        REPORT_COUNT=$(find "$REPORTS_DIR" -type f | wc -l)
        log_success "Report files remaining: $REPORT_COUNT"
    fi
    
    # Cleanup old backup files
    if [[ -d "$BACKUP_DIR" ]]; then
        log_info "Cleaning up backup files older than $RETENTION_DAYS days..."
        execute_cmd "find '$BACKUP_DIR' -name '*.db' -o -name '*.db.gz' | xargs -I {} find {} -mtime +$RETENTION_DAYS -type f -delete" "Delete old backup files"
        execute_cmd "find '$BACKUP_DIR' -name '*.meta' -mtime +$RETENTION_DAYS -type f -delete" "Delete old backup metadata"
        
        # Count remaining backup files
        BACKUP_COUNT=$(find "$BACKUP_DIR" -type f | wc -l)
        log_success "Backup files remaining: $BACKUP_COUNT"
    fi
    
    # Cleanup temporary files
    log_info "Cleaning up temporary files..."
    execute_cmd "find /tmp -name 'veeva_*' -mtime +1 -type f -delete 2>/dev/null || true" "Delete temporary files"
    
    # Cleanup Python cache files
    execute_cmd "find '$PROJECT_ROOT' -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true" "Delete Python cache files"
    execute_cmd "find '$PROJECT_ROOT' -name '*.pyc' -type f -delete 2>/dev/null || true" "Delete Python compiled files"
}

# Function to rotate log files
rotate_logs() {
    log_info "Rotating log files..."
    
    if [[ ! -d "$LOGS_DIR" ]]; then
        log_warning "Logs directory does not exist: $LOGS_DIR"
        return
    fi
    
    cd "$LOGS_DIR"
    
    for log_file in *.log; do
        if [[ -f "$log_file" ]]; then
            # Get file size in MB
            file_size=$(du -m "$log_file" | cut -f1)
            
            # Rotate if file is larger than 10MB
            if [[ $file_size -gt 10 ]]; then
                timestamp=$(date +%Y%m%d_%H%M%S)
                rotated_file="${log_file%.log}_${timestamp}.log"
                
                execute_cmd "mv '$log_file' '$rotated_file'" "Rotate $log_file"
                execute_cmd "gzip '$rotated_file'" "Compress $rotated_file"
                execute_cmd "touch '$log_file'" "Create new $log_file"
                
                log_success "Rotated and compressed: $log_file"
            fi
        fi
    done
}

# Function to optimize database
optimize_database() {
    log_info "Optimizing database..."
    
    cd "$PROJECT_ROOT"
    
    # Load environment configuration
    if [[ -f "deploy/environments/.env.production" ]]; then
        set -o allexport
        source "deploy/environments/.env.production"
        set +o allexport
    fi
    
    # Set default database path if not set
    VEEVA_DB_PATH=${VEEVA_DB_PATH:-"data/database/veeva_opendata.db"}
    
    if [[ ! -f "$VEEVA_DB_PATH" ]]; then
        log_warning "Database file not found: $VEEVA_DB_PATH"
        return
    fi
    
    # Create backup before optimization
    backup_file="$BACKUP_DIR/pre_optimize_$(date +%Y%m%d_%H%M%S).db"
    execute_cmd "cp '$VEEVA_DB_PATH' '$backup_file'" "Backup database before optimization"
    
    # Vacuum database
    log_info "Running VACUUM on database..."
    execute_cmd "sqlite3 '$VEEVA_DB_PATH' 'VACUUM;'" "Vacuum database"
    
    # Analyze database
    log_info "Running ANALYZE on database..."
    execute_cmd "sqlite3 '$VEEVA_DB_PATH' 'ANALYZE;'" "Analyze database"
    
    # Check integrity
    log_info "Checking database integrity..."
    if [[ "$DRY_RUN" != "true" ]]; then
        integrity_result=$(sqlite3 "$VEEVA_DB_PATH" "PRAGMA integrity_check;")
        if [[ "$integrity_result" == "ok" ]]; then
            log_success "Database integrity check passed"
        else
            log_error "Database integrity check failed: $integrity_result"
            # Restore from backup
            execute_cmd "cp '$backup_file' '$VEEVA_DB_PATH'" "Restore database from backup"
            exit 1
        fi
    fi
    
    # Get database statistics
    if [[ "$DRY_RUN" != "true" ]]; then
        db_size_before=$(du -h "$backup_file" | cut -f1)
        db_size_after=$(du -h "$VEEVA_DB_PATH" | cut -f1)
        
        log_success "Database optimization completed"
        log_info "Size before: $db_size_before"
        log_info "Size after: $db_size_after"
    fi
}

# Function to check disk usage
check_disk_usage() {
    log_info "Checking disk usage..."
    
    # Check overall disk usage
    df -h /
    
    # Check specific directories
    echo "\nDisk usage by directory:"
    du -sh "$PROJECT_ROOT"/* 2>/dev/null | sort -hr | head -10
    
    # Check if disk usage is above threshold
    disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [[ $disk_usage -gt 90 ]]; then
        log_error "Disk usage critical: ${disk_usage}%"
        
        # Suggest cleanup actions
        log_info "Suggested cleanup actions:"
        echo "  1. Run: $0 cleanup --retention 7"
        echo "  2. Remove old Docker images: docker system prune -f"
        echo "  3. Check large files: find $PROJECT_ROOT -size +100M -type f -ls"
        
        if [[ "$FORCE" == "true" ]]; then
            log_warning "Force flag set, running aggressive cleanup..."
            cleanup_old_files
        fi
        
        exit 1
    elif [[ $disk_usage -gt 80 ]]; then
        log_warning "Disk usage high: ${disk_usage}%"
    else
        log_success "Disk usage normal: ${disk_usage}%"
    fi
}

# Function to run health check
run_health_check() {
    log_info "Running comprehensive health check..."
    
    cd "$PROJECT_ROOT"
    
    if [[ "$DRY_RUN" != "true" ]]; then
        # Run health check script
        python python/utils/health_check.py
        
        # Run application status check
        python python/main.py status
        
        log_success "Health check completed"
    else
        log_info "[DRY RUN] Would run health check scripts"
    fi
}

# Function to create system backup
create_backup() {
    log_info "Creating system backup..."
    
    if [[ -f "$SCRIPT_DIR/backup.sh" ]]; then
        execute_cmd "$SCRIPT_DIR/backup.sh --environment production" "Create database backup"
    else
        log_warning "Backup script not found"
    fi
}

# Function to update configuration
update_configuration() {
    log_info "Updating configuration files..."
    
    # This function would typically:
    # 1. Pull latest configuration from version control
    # 2. Validate configuration files
    # 3. Restart services if needed
    
    log_info "[PLACEHOLDER] Configuration update logic would go here"
}

# Function to run all maintenance tasks
run_all_maintenance() {
    log_info "Running all maintenance tasks..."
    
    if [[ "$FORCE" != "true" && "$DRY_RUN" != "true" ]]; then
        echo "This will run all maintenance tasks including:"
        echo "  - File cleanup"
        echo "  - Log rotation"
        echo "  - Database optimization"
        echo "  - Health check"
        echo "  - Disk usage check"
        echo ""
        read -p "Are you sure you want to continue? [y/N]: " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Maintenance cancelled by user"
            exit 0
        fi
    fi
    
    cleanup_old_files
    rotate_logs
    optimize_database
    run_health_check
    check_disk_usage
    
    log_success "All maintenance tasks completed"
}

# Main execution
log_info "Starting maintenance task: $TASK"

if [[ "$DRY_RUN" == "true" ]]; then
    log_warning "DRY RUN MODE - No changes will be made"
fi

case $TASK in
    "all")
        run_all_maintenance
        ;;
    "cleanup")
        cleanup_old_files
        ;;
    "optimize")
        optimize_database
        ;;
    "backup")
        create_backup
        ;;
    "health-check")
        run_health_check
        ;;
    "update-config")
        update_configuration
        ;;
    "rotate-logs")
        rotate_logs
        ;;
    "vacuum-db")
        optimize_database
        ;;
    "check-disk")
        check_disk_usage
        ;;
    *)
        log_error "Unknown task: $TASK"
        show_usage
        exit 1
        ;;
esac

log_success "Maintenance task '$TASK' completed successfully"

exit 0