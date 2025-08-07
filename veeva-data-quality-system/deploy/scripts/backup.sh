#!/bin/bash

# Veeva Data Quality System Database Backup Script
# Usage: ./backup.sh [options]

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_DIR="$PROJECT_ROOT/deploy/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

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
RETENTION_DAYS=30
COMPRESS=true
VERIFY_BACKUP=true
ENVIRONMENT="production"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --retention-days)
            RETENTION_DAYS="$2"
            shift 2
            ;;
        --no-compress)
            COMPRESS=false
            shift
            ;;
        --no-verify)
            VERIFY_BACKUP=false
            shift
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --retention-days N   Keep backups for N days (default: 30)"
            echo "  --no-compress        Don't compress backup files"
            echo "  --no-verify          Skip backup verification"
            echo "  --environment ENV    Environment to backup (default: production)"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create backup directory
mkdir -p "$BACKUP_DIR"

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

log_info "Starting backup process..."
log_info "Environment: $ENVIRONMENT"
log_info "Database: $VEEVA_DB_PATH"
log_info "Backup directory: $BACKUP_DIR"

# Check if database exists
if [[ ! -f "$VEEVA_DB_PATH" ]]; then
    log_error "Database file not found: $VEEVA_DB_PATH"
    exit 1
fi

# Generate backup filename
BACKUP_NAME="veeva_db_${ENVIRONMENT}_${TIMESTAMP}"
BACKUP_FILE="$BACKUP_DIR/${BACKUP_NAME}.db"

# Create the backup
log_info "Creating database backup..."
sqlite3 "$VEEVA_DB_PATH" ".backup '$BACKUP_FILE'"

if [[ $? -eq 0 ]]; then
    log_success "Database backup created: $BACKUP_FILE"
else
    log_error "Failed to create database backup"
    exit 1
fi

# Verify backup integrity
if [[ "$VERIFY_BACKUP" == "true" ]]; then
    log_info "Verifying backup integrity..."
    
    # Check database integrity
    INTEGRITY_CHECK=$(sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;")
    if [[ "$INTEGRITY_CHECK" == "ok" ]]; then
        log_success "Backup integrity verified"
    else
        log_error "Backup integrity check failed: $INTEGRITY_CHECK"
        rm -f "$BACKUP_FILE"
        exit 1
    fi
    
    # Compare record counts
    ORIGINAL_COUNT=$(sqlite3 "$VEEVA_DB_PATH" "SELECT SUM(count) FROM (SELECT COUNT(*) as count FROM healthcare_providers UNION ALL SELECT COUNT(*) FROM healthcare_facilities);")
    BACKUP_COUNT=$(sqlite3 "$BACKUP_FILE" "SELECT SUM(count) FROM (SELECT COUNT(*) as count FROM healthcare_providers UNION ALL SELECT COUNT(*) FROM healthcare_facilities);")
    
    if [[ "$ORIGINAL_COUNT" == "$BACKUP_COUNT" ]]; then
        log_success "Record count verification passed ($ORIGINAL_COUNT records)"
    else
        log_error "Record count mismatch - Original: $ORIGINAL_COUNT, Backup: $BACKUP_COUNT"
        rm -f "$BACKUP_FILE"
        exit 1
    fi
fi

# Compress backup if requested
if [[ "$COMPRESS" == "true" ]]; then
    log_info "Compressing backup..."
    gzip "$BACKUP_FILE"
    BACKUP_FILE="${BACKUP_FILE}.gz"
    
    if [[ -f "$BACKUP_FILE" ]]; then
        log_success "Backup compressed: $BACKUP_FILE"
    else
        log_error "Failed to compress backup"
        exit 1
    fi
fi

# Get backup file size
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log_info "Backup size: $BACKUP_SIZE"

# Create backup metadata
METADATA_FILE="$BACKUP_DIR/${BACKUP_NAME}.meta"
cat > "$METADATA_FILE" << EOF
# Veeva Data Quality System Backup Metadata
backup_timestamp=$TIMESTAMP
environment=$ENVIRONMENT
original_database=$VEEVA_DB_PATH
backup_file=$(basename "$BACKUP_FILE")
backup_size=$BACKUP_SIZE
compressed=$COMPRESS
verified=$VERIFY_BACKUP
created_by=$(whoami)
created_at=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
EOF

log_success "Backup metadata created: $METADATA_FILE"

# Cleanup old backups
log_info "Cleaning up backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "veeva_db_${ENVIRONMENT}_*.db*" -mtime +$RETENTION_DAYS -type f -delete
find "$BACKUP_DIR" -name "veeva_db_${ENVIRONMENT}_*.meta" -mtime +$RETENTION_DAYS -type f -delete

# Count remaining backups
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "veeva_db_${ENVIRONMENT}_*.db*" -type f | wc -l)
log_info "Total backups for $ENVIRONMENT environment: $BACKUP_COUNT"

# List recent backups
log_info "Recent backups:"
ls -lht "$BACKUP_DIR"/veeva_db_${ENVIRONMENT}_*.db* 2>/dev/null | head -5 || log_info "No previous backups found"

log_success "Backup process completed successfully!"
log_info "Backup location: $BACKUP_FILE"
log_info "Metadata: $METADATA_FILE"

exit 0