#!/bin/bash
set -euo pipefail

#======================================================================
# Veeva Data Quality System - Production Installation Script
# 
# This script automates the complete installation and setup of the
# Veeva Data Quality System for production environments.
#
# Usage: ./install.sh [OPTIONS]
#
# Options:
#   --environment=ENV    Target environment (production|staging|development)
#   --skip-deps         Skip dependency checks
#   --skip-tests        Skip post-installation tests
#   --with-monitoring   Install with monitoring stack
#   --backup            Create initial backup
#   --help              Show this help message
#
# Prerequisites:
#   - Docker 20.10+ and Docker Compose 2.0+
#   - Minimum 4GB RAM, 2 CPU cores
#   - 20GB+ available storage
#
# Author: Veeva Data Quality Team
# Version: 3.0.0
#======================================================================

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENVIRONMENT="${ENVIRONMENT:-production}"
SKIP_DEPS=false
SKIP_TESTS=false
WITH_MONITORING=false
CREATE_BACKUP=false

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

# Print banner
print_banner() {
    echo -e "${BLUE}"
    cat << "EOF"
    ____   ____                             ____   ___  
    \   \ /   /____   _______  _______     |    \ /   \ 
     \   Y   // __ \_/ __ \  \/ /\__  \    |  |  \   /  
      \     /\  ___/\  ___/\   /  / __ \_  |  |__|\   \  
       \___/  \___  >\___  >\_/  (____  /  |____|\\____\ 
                  \/     \/           \/                  
                                                          
    Data Quality System - Production Installation
    Version 3.0.0 | Phase 3 Production Ready
    
EOF
    echo -e "${NC}"
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --environment=*)
                ENVIRONMENT="${1#*=}"
                shift
                ;;
            --skip-deps)
                SKIP_DEPS=true
                shift
                ;;
            --skip-tests)
                SKIP_TESTS=true
                shift
                ;;
            --with-monitoring)
                WITH_MONITORING=true
                shift
                ;;
            --backup)
                CREATE_BACKUP=true
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Show help
show_help() {
    echo "Veeva Data Quality System Installation Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --environment=ENV    Target environment (production|staging|development)"
    echo "  --skip-deps         Skip dependency checks"
    echo "  --skip-tests        Skip post-installation tests"
    echo "  --with-monitoring   Install with monitoring stack"
    echo "  --backup            Create initial backup"
    echo "  --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --environment=production --with-monitoring"
    echo "  $0 --environment=staging --skip-tests"
    echo ""
}

# Check system dependencies
check_dependencies() {
    if [[ "$SKIP_DEPS" == "true" ]]; then
        log_info "Skipping dependency checks"
        return 0
    fi

    log_info "Checking system dependencies..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker 20.10 or later."
        exit 1
    fi

    # Check Docker version
    DOCKER_VERSION=$(docker --version | grep -oE '[0-9]+\.[0-9]+' | head -n1)
    if [[ $(echo "$DOCKER_VERSION 20.10" | awk '{print ($1 >= $2)}') -eq 0 ]]; then
        log_error "Docker version $DOCKER_VERSION is too old. Please upgrade to 20.10 or later."
        exit 1
    fi
    log_success "Docker $DOCKER_VERSION detected"

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose 2.0 or later."
        exit 1
    fi
    log_success "Docker Compose detected"

    # Check system resources
    TOTAL_MEM=$(free -m | awk 'NR==2{printf "%.0f", $2}')
    if [[ $TOTAL_MEM -lt 3072 ]]; then
        log_warning "System has only ${TOTAL_MEM}MB RAM. Minimum 4GB recommended for production."
    else
        log_success "System has ${TOTAL_MEM}MB RAM available"
    fi

    # Check disk space
    AVAILABLE_SPACE=$(df "$PROJECT_ROOT" | awk 'NR==2 {printf "%.0f", $4/1024/1024}')
    if [[ $AVAILABLE_SPACE -lt 20 ]]; then
        log_warning "Only ${AVAILABLE_SPACE}GB disk space available. Minimum 20GB recommended."
    else
        log_success "${AVAILABLE_SPACE}GB disk space available"
    fi
}

# Validate environment
validate_environment() {
    log_info "Validating environment: $ENVIRONMENT"

    case $ENVIRONMENT in
        production|staging|development)
            ;;
        *)
            log_error "Invalid environment: $ENVIRONMENT"
            log_error "Valid environments: production, staging, development"
            exit 1
            ;;
    esac

    # Check if environment file exists
    ENV_FILE="$DEPLOY_DIR/environments/.env.$ENVIRONMENT"
    if [[ ! -f "$ENV_FILE" ]]; then
        log_error "Environment file not found: $ENV_FILE"
        exit 1
    fi
    log_success "Environment file found: $ENV_FILE"
}

# Prepare environment configuration
prepare_configuration() {
    log_info "Preparing $ENVIRONMENT configuration..."

    cd "$DEPLOY_DIR"

    # Copy environment file
    ENV_SOURCE="environments/.env.$ENVIRONMENT"
    ENV_TARGET=".env.${ENVIRONMENT}.local"

    if [[ ! -f "$ENV_TARGET" ]]; then
        cp "$ENV_SOURCE" "$ENV_TARGET"
        log_success "Created local environment file: $ENV_TARGET"
        log_warning "Please review and customize $ENV_TARGET before proceeding to production"
    else
        log_info "Using existing environment file: $ENV_TARGET"
    fi

    # Set deployment environment
    export VEEVA_ENV="$ENVIRONMENT"
    export DEPLOYMENT_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    export BUILD_ID="${BUILD_ID:-$(date +%Y%m%d-%H%M%S)}"

    # Create necessary directories
    mkdir -p backups logs data/database reports/validation reports/monitoring
    log_success "Created necessary directories"
}

# Build Docker images
build_images() {
    log_info "Building Docker images for $ENVIRONMENT..."

    cd "$DEPLOY_DIR"

    if [[ "$ENVIRONMENT" == "production" ]]; then
        docker build --target production -t veeva-dq:${BUILD_ID} -t veeva-dq:latest -f Dockerfile ..
    else
        docker build -t veeva-dq:${BUILD_ID} -t veeva-dq:latest -f Dockerfile ..
    fi

    log_success "Docker images built successfully"
}

# Deploy services
deploy_services() {
    log_info "Deploying services for $ENVIRONMENT..."

    cd "$DEPLOY_DIR"

    # Set Docker Compose profiles
    COMPOSE_PROFILES=""
    if [[ "$WITH_MONITORING" == "true" ]]; then
        COMPOSE_PROFILES="monitoring"
        log_info "Enabling monitoring stack"
    fi

    # Deploy with appropriate profiles
    if [[ -n "$COMPOSE_PROFILES" ]]; then
        COMPOSE_PROFILES="$COMPOSE_PROFILES" docker-compose up -d
    else
        docker-compose up -d veeva-dq-app
    fi

    log_success "Services deployed successfully"
}

# Wait for services to be ready
wait_for_services() {
    log_info "Waiting for services to be ready..."

    local max_attempts=30
    local attempt=1

    while [[ $attempt -le $max_attempts ]]; do
        if docker-compose exec -T veeva-dq-app python python/main.py status >/dev/null 2>&1; then
            log_success "Application is ready"
            break
        fi

        log_info "Attempt $attempt/$max_attempts - Waiting for application to be ready..."
        sleep 10
        ((attempt++))
    done

    if [[ $attempt -gt $max_attempts ]]; then
        log_error "Application failed to start within expected time"
        log_info "Checking application logs..."
        docker-compose logs veeva-dq-app
        exit 1
    fi
}

# Run post-installation tests
run_tests() {
    if [[ "$SKIP_TESTS" == "true" ]]; then
        log_info "Skipping post-installation tests"
        return 0
    fi

    log_info "Running post-installation tests..."

    cd "$PROJECT_ROOT"

    # Run health checks
    if docker-compose -f deploy/docker-compose.yml exec -T veeva-dq-app python python/main.py status; then
        log_success "Health check passed"
    else
        log_error "Health check failed"
        exit 1
    fi

    # Run basic system tests if available
    if [[ -f "test_system.py" ]]; then
        log_info "Running system tests..."
        if docker-compose -f deploy/docker-compose.yml exec -T veeva-dq-app python test_system.py; then
            log_success "System tests passed"
        else
            log_warning "Some system tests failed - check logs for details"
        fi
    fi
}

# Create initial backup
create_initial_backup() {
    if [[ "$CREATE_BACKUP" != "true" ]]; then
        return 0
    fi

    log_info "Creating initial backup..."

    cd "$DEPLOY_DIR"

    if [[ -f "scripts/backup.sh" ]]; then
        if ./scripts/backup.sh --environment "$ENVIRONMENT" --initial; then
            log_success "Initial backup created"
        else
            log_warning "Backup creation failed - continuing with installation"
        fi
    else
        log_warning "Backup script not found - skipping initial backup"
    fi
}

# Display final status
display_final_status() {
    echo ""
    log_success "🎉 Veeva Data Quality System installation completed!"
    echo ""
    echo -e "${BLUE}Installation Summary:${NC}"
    echo "  • Environment: $ENVIRONMENT"
    echo "  • Build ID: $BUILD_ID"
    echo "  • Deployment Date: $DEPLOYMENT_DATE"
    echo ""
    
    echo -e "${BLUE}Next Steps:${NC}"
    echo "  1. Review configuration: deploy/.env.${ENVIRONMENT}.local"
    echo "  2. Access application: docker-compose -f deploy/docker-compose.yml exec veeva-dq-app python python/main.py --help"
    echo "  3. Check health: ./deploy/scripts/monitor.sh health"
    
    if [[ "$WITH_MONITORING" == "true" ]]; then
        echo ""
        echo -e "${BLUE}Monitoring Endpoints:${NC}"
        echo "  • Grafana: http://localhost:3000 (admin/admin)"
        echo "  • Prometheus: http://localhost:9090"
    fi
    
    echo ""
    echo -e "${BLUE}Useful Commands:${NC}"
    echo "  • Start services: cd deploy && docker-compose up -d"
    echo "  • Stop services: cd deploy && docker-compose down"
    echo "  • View logs: cd deploy && docker-compose logs -f"
    echo "  • Run validation: ./deploy/scripts/monitor.sh health"
    echo ""
    
    if [[ "$ENVIRONMENT" == "production" ]]; then
        echo -e "${YELLOW}Production Reminders:${NC}"
        echo "  • Configure backup schedules"
        echo "  • Set up monitoring alerts"
        echo "  • Review security settings"
        echo "  • Plan maintenance windows"
        echo ""
    fi
}

# Cleanup on exit
cleanup() {
    log_info "Cleaning up temporary files..."
    # Add any cleanup operations here
}

# Error handling
error_handler() {
    local line_no=$1
    local error_code=$2
    log_error "Installation failed on line $line_no with exit code $error_code"
    log_info "Check the logs above for details"
    cleanup
    exit $error_code
}

# Main installation function
main() {
    # Set up error handling
    trap 'error_handler ${LINENO} $?' ERR
    trap cleanup EXIT

    # Parse arguments and show banner
    parse_arguments "$@"
    print_banner

    log_info "Starting Veeva Data Quality System installation..."
    log_info "Target environment: $ENVIRONMENT"
    
    # Installation steps
    check_dependencies
    validate_environment
    prepare_configuration
    build_images
    deploy_services
    wait_for_services
    run_tests
    create_initial_backup
    display_final_status

    log_success "Installation completed successfully! 🚀"
}

# Run main function with all arguments
main "$@"