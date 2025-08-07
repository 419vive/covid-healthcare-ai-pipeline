#!/bin/bash

# Veeva Data Quality System Database Restore Script
# Usage: ./restore.sh [backup_file] [options]

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
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
ENVIRONMENT="production"
FORCE_RESTORE=false
VERIFY_RESTORE=true
CREATE_BACKUP_BEFORE_RESTORE=true

# Function to show usage
show_usage() {
    echo "Usage: $0 [backup_file] [options]"
    echo "Arguments:"
    echo "  backup_file          Path to backup file (or 'latest' for most recent)"
    echo "Options:"
    echo "  --environment ENV    Target environment (default: production)"
    echo "  --force             Skip confirmation prompts"
    echo "  --no-verify         Skip restore verification"
    echo "  --no-backup         Don't backup current database before restore"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 latest                                    # Restore latest backup"
    echo "  $0 /path/to/backup.db.gz --environment staging  # Restore specific file"
    echo "  $0 latest --force --no-backup                # Quick restore without backup"
}

# Parse command line arguments
BACKUP_FILE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --force)
            FORCE_RESTORE=true
            shift
            ;;
        --no-verify)
            VERIFY_RESTORE=false
            shift
            ;;
        --no-backup)
            CREATE_BACKUP_BEFORE_RESTORE=false
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
        *)
            if [[ -z "$BACKUP_FILE" ]]; then
                BACKUP_FILE="$1"
                shift
            else
                log_error "Multiple backup files specified"
                show_usage
                exit 1
            fi
            ;;
    esac
done

# Check if backup file argument is provided
if [[ -z "$BACKUP_FILE" ]]; then
    log_error "No backup file specified"
    show_usage
    exit 1
fi

# Load environment configuration
ENV_FILE="$PROJECT_ROOT/deploy/environments/.env.$ENVIRONMENT"
if [[ -f "$ENV_FILE" ]]; then
    set -o allexport
    source "$ENV_FILE"
    set +o allexport
else
    log_warning "Environment file not found: $ENV_FILE, using defaults"
fi

# Set default database path if not set
VEEVA_DB_PATH=${VEEVA_DB_PATH:-"$PROJECT_ROOT/data/database/veeva_opendata.db"}

log_info "Starting restore process..."
log_info "Environment: $ENVIRONMENT"
log_info "Target database: $VEEVA_DB_PATH"

# Resolve backup file path
if [[ "$BACKUP_FILE" == "latest" ]]; then
    # Find the latest backup file
    LATEST_BACKUP=$(find "$BACKUP_DIR" -name "veeva_db_${ENVIRONMENT}_*.db*" -type f -printf "%T@ %p\n" | sort -n | tail -1 | cut -d' ' -f2-)
    
    if [[ -z "$LATEST_BACKUP" ]]; then
        log_error "No backup files found for environment: $ENVIRONMENT"
        log_info "Available backups:"
        ls -la "$BACKUP_DIR"/veeva_db_*.db* 2>/dev/null || log_info "No backups found in $BACKUP_DIR"
        exit 1
    fi
    
    BACKUP_FILE="$LATEST_BACKUP"
    log_info "Using latest backup: $(basename "$BACKUP_FILE")"
else
    # Check if it's a relative path and make it absolute
    if [[ ! "$BACKUP_FILE" = /* ]]; then
        BACKUP_FILE="$BACKUP_DIR/$BACKUP_FILE"
    fi
fi

# Verify backup file exists
if [[ ! -f "$BACKUP_FILE" ]]; then
    log_error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Get backup file info
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
BACKUP_DATE=$(date -r "$BACKUP_FILE" "+%Y-%m-%d %H:%M:%S")

log_info "Backup file: $BACKUP_FILE"
log_info "Backup size: $BACKUP_SIZE"
log_info "Backup date: $BACKUP_DATE"

# Check if backup metadata exists
METADATA_FILE="${BACKUP_FILE%.*}.meta"
if [[ -f "$METADATA_FILE" ]]; then
    log_info "Backup metadata found, loading..."
    source "$METADATA_FILE"
    log_info "Backup created: $created_at"
    log_info "Original environment: $environment"
fi

# Confirmation prompt (unless forced)
if [[ "$FORCE_RESTORE" != "true" ]]; then
    echo ""
    log_warning "This will replace the current database!"
    log_warning "Target: $VEEVA_DB_PATH"
    log_warning "Source: $BACKUP_FILE ($BACKUP_SIZE, $BACKUP_DATE)"
    echo ""
    read -p "Are you sure you want to continue? [y/N]: " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Restore cancelled by user"
        exit 0
    fi
fi

# Create backup of current database before restore
if [[ "$CREATE_BACKUP_BEFORE_RESTORE" == "true" && -f "$VEEVA_DB_PATH" ]]; then
    log_info "Creating backup of current database..."
    CURRENT_BACKUP="$BACKUP_DIR/pre_restore_$(date +%Y%m%d_%H%M%S).db"
    cp "$VEEVA_DB_PATH" "$CURRENT_BACKUP"
    log_success "Current database backed up to: $CURRENT_BACKUP"
fi

# Ensure target directory exists
TARGET_DIR=$(dirname "$VEEVA_DB_PATH")
mkdir -p "$TARGET_DIR"

# Prepare the backup file for restore
TEMP_BACKUP="$BACKUP_FILE"
CLEANUP_TEMP=false

# If backup is compressed, decompress it
if [[ "$BACKUP_FILE" == *.gz ]]; then
    log_info "Decompressing backup file..."
    TEMP_BACKUP="${BACKUP_FILE%.gz}"
    
    if [[ -f "$TEMP_BACKUP" ]]; then
        log_warning "Temporary file already exists: $TEMP_BACKUP"
        TEMP_BACKUP="/tmp/veeva_restore_$(date +%s).db"
    fi
    
    gunzip -c "$BACKUP_FILE" > "$TEMP_BACKUP"
    CLEANUP_TEMP=true
    log_success "Backup decompressed to: $TEMP_BACKUP"
fi

# Verify backup integrity before restore
if [[ "$VERIFY_RESTORE" == "true" ]]; then
    log_info "Verifying backup integrity..."
    INTEGRITY_CHECK=$(sqlite3 "$TEMP_BACKUP" "PRAGMA integrity_check;")
    if [[ "$INTEGRITY_CHECK" == "ok" ]]; then
        log_success "Backup integrity verified"
    else
        log_error "Backup integrity check failed: $INTEGRITY_CHECK"
        [[ "$CLEANUP_TEMP" == "true" ]] && rm -f "$TEMP_BACKUP"
        exit 1
    fi
fi

# Perform the restore
log_info "Restoring database..."
cp "$TEMP_BACKUP" "$VEEVA_DB_PATH"

if [[ $? -eq 0 ]]; then
    log_success "Database restored successfully"
else
    log_error "Failed to restore database"
    [[ "$CLEANUP_TEMP" == "true" ]] && rm -f "$TEMP_BACKUP"
    exit 1
fi

# Cleanup temporary files
if [[ "$CLEANUP_TEMP" == "true" ]]; then
    rm -f "$TEMP_BACKUP"
fi

# Verify the restored database
if [[ "$VERIFY_RESTORE" == "true" ]]; then
    log_info "Verifying restored database..."
    
    # Check database integrity
    RESTORE_INTEGRITY=$(sqlite3 "$VEEVA_DB_PATH" "PRAGMA integrity_check;")
    if [[ "$RESTORE_INTEGRITY" == "ok" ]]; then
        log_success "Restored database integrity verified"
    else
        log_error "Restored database integrity check failed: $RESTORE_INTEGRITY"
        exit 1
    fi
    
    # Check if we can query the database
    RECORD_COUNT=$(sqlite3 "$VEEVA_DB_PATH" "SELECT COUNT(*) FROM healthcare_providers;" 2>/dev/null || echo "0")
    log_success "Healthcare providers count: $RECORD_COUNT"
    
    FACILITY_COUNT=$(sqlite3 "$VEEVA_DB_PATH" "SELECT COUNT(*) FROM healthcare_facilities;" 2>/dev/null || echo "0")
    log_success "Healthcare facilities count: $FACILITY_COUNT"
fi

# Set proper file permissions
chmod 644 "$VEEVA_DB_PATH"

log_success "Restore process completed successfully!"
log_info "Database restored from: $(basename "$BACKUP_FILE")"
log_info "Restored to: $VEEVA_DB_PATH"
log_info "You may want to restart the application to ensure it picks up the restored database"

exit 0