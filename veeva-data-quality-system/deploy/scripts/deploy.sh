#!/bin/bash

# Veeva Data Quality System Deployment Script
# Usage: ./deploy.sh [environment] [options]
# Example: ./deploy.sh production --build --backup

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOY_DIR="$PROJECT_ROOT/deploy"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
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
BUILD_IMAGE=false
RUN_BACKUP=false
RUN_TESTS=false
SKIP_HEALTH_CHECK=false
FORCE_RECREATE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        production|staging|dev)
            ENVIRONMENT="$1"
            shift
            ;;
        --build)
            BUILD_IMAGE=true
            shift
            ;;
        --backup)
            RUN_BACKUP=true
            shift
            ;;
        --test)
            RUN_TESTS=true
            shift
            ;;
        --skip-health-check)
            SKIP_HEALTH_CHECK=true
            shift
            ;;
        --force-recreate)
            FORCE_RECREATE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [environment] [options]"
            echo "Environments: production, staging, dev (default: production)"
            echo "Options:"
            echo "  --build              Build new Docker image"
            echo "  --backup             Run database backup before deployment"
            echo "  --test               Run tests before deployment"
            echo "  --skip-health-check  Skip post-deployment health checks"
            echo "  --force-recreate     Force recreate containers"
            echo "  -h, --help           Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate environment - check both .local and regular versions
ENV_FILE=".env.$ENVIRONMENT.local"
if [[ ! -f "$DEPLOY_DIR/$ENV_FILE" ]]; then
    ENV_FILE="environments/.env.$ENVIRONMENT"
    if [[ ! -f "$DEPLOY_DIR/$ENV_FILE" ]]; then
        log_error "Environment configuration not found: .env.$ENVIRONMENT or .env.$ENVIRONMENT.local"
        log_error "Available environments: $(ls $DEPLOY_DIR/environments/.env.* | sed 's/.*\.env\.//' | tr '\n' ' ')"
        exit 1
    fi
fi

log_info "Starting deployment for environment: $ENVIRONMENT"

# Change to deploy directory
cd "$DEPLOY_DIR"

# Load environment configuration
log_info "Loading environment configuration from: $ENV_FILE"
set -o allexport
source "$ENV_FILE"
set +o allexport

# Create necessary directories
log_info "Creating deployment directories..."
mkdir -p backups logs

# Run backup if requested
if [[ "$RUN_BACKUP" == "true" ]]; then
    log_info "Running database backup..."
    if [[ -f "scripts/backup.sh" ]]; then
        ./scripts/backup.sh
        log_success "Backup completed"
    else
        log_warning "Backup script not found, skipping backup"
    fi
fi

# Run tests if requested
if [[ "$RUN_TESTS" == "true" ]]; then
    log_info "Running tests..."
    cd "$PROJECT_ROOT"
    python -m pytest tests/ -v
    if [[ $? -eq 0 ]]; then
        log_success "All tests passed"
    else
        log_error "Tests failed, aborting deployment"
        exit 1
    fi
    cd "$DEPLOY_DIR"
fi

# Build image if requested
if [[ "$BUILD_IMAGE" == "true" ]]; then
    log_info "Building Docker image..."
    docker compose build --no-cache
    log_success "Docker image built successfully"
fi

# Stop existing containers
log_info "Stopping existing containers..."
docker compose down

# Deploy the application
log_info "Starting Veeva Data Quality System..."
if [[ "$FORCE_RECREATE" == "true" ]]; then
    docker compose up -d --force-recreate
else
    docker compose up -d
fi

# Wait for services to be ready
log_info "Waiting for services to start..."
sleep 10

# Run health checks
if [[ "$SKIP_HEALTH_CHECK" != "true" ]]; then
    log_info "Running health checks..."
    
    # Check if container is running
    if docker compose ps | grep -q "veeva-data-quality-system.*Up"; then
        log_success "Container is running"
    else
        log_error "Container failed to start"
        docker compose logs
        exit 1
    fi
    
    # Check application health
    max_attempts=12
    attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        log_info "Health check attempt $attempt/$max_attempts..."
        
        if docker compose exec -T veeva-dq-app python python/main.py status > /dev/null 2>&1; then
            log_success "Application health check passed"
            break
        else
            if [[ $attempt -eq $max_attempts ]]; then
                log_error "Health check failed after $max_attempts attempts"
                log_error "Application logs:"
                docker compose logs veeva-dq-app --tail=50
                exit 1
            fi
            
            log_warning "Health check failed, retrying in 10 seconds..."
            sleep 10
            ((attempt++))
        fi
    done
fi

# Show deployment status
log_info "Deployment Status:"
docker compose ps

# Show logs
log_info "Recent application logs:"
docker compose logs veeva-dq-app --tail=20

log_success "Deployment completed successfully!"
log_info "Environment: $ENVIRONMENT"
log_info "To view logs: docker compose logs -f"
log_info "To stop: docker compose down"
log_info "To run validation: docker compose exec veeva-dq-app python python/main.py validate"

exit 0