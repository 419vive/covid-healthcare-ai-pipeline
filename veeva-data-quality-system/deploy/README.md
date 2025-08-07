# Veeva Data Quality System - Production Deployment Guide

This directory contains all the necessary files and scripts for deploying the Veeva Data Quality System to production environments.

## Quick Start

### Docker Deployment (Recommended)

```bash
# 1. Clone and navigate to project
cd veeva-data-quality-system/deploy

# 2. Configure environment
cp environments/.env.production .env.production.local
# Edit .env.production.local with your specific settings

# 3. Deploy with monitoring
./scripts/deploy.sh production --build --backup

# 4. Verify deployment
./scripts/monitor.sh health
```

### Kubernetes Deployment

```bash
# 1. Create namespace and resources
kubectl apply -f kubernetes/

# 2. Check deployment status
kubectl get pods -n veeva-dq-system

# 3. View logs
kubectl logs -f deployment/veeva-dq-app -n veeva-dq-system
```

## Directory Structure

```
deploy/
├── README.md                 # This file
├── Dockerfile               # Production Docker image
├── .dockerignore            # Docker build exclusions
├── docker-compose.yml       # Docker Compose configuration
├── environments/            # Environment-specific configurations
│   ├── .env.production     # Production environment settings
│   ├── .env.staging        # Staging environment settings
│   └── .env.dev            # Development environment settings
├── scripts/                 # Deployment and maintenance scripts
│   ├── deploy.sh           # Main deployment script
│   ├── backup.sh           # Database backup script
│   ├── restore.sh          # Database restore script
│   ├── monitor.sh          # Monitoring and health checks
│   └── maintenance.sh      # System maintenance tasks
├── monitoring/              # Monitoring configuration
│   ├── prometheus.yml      # Prometheus configuration
│   ├── alert_rules.yml     # Alerting rules
│   └── grafana/            # Grafana dashboards
└── kubernetes/              # Kubernetes deployment manifests
    ├── namespace.yaml      # Namespace definition
    ├── configmap.yaml      # Configuration maps
    ├── deployment.yaml     # Application deployment
    ├── service.yaml        # Service definitions
    └── pvc.yaml           # Persistent volume claims
```

## Environment Configuration

### Production Environment Variables

Copy `environments/.env.production` to `.env.production.local` and customize:

```bash
# Application Settings
VEEVA_ENV=production
VEEVA_LOG_LEVEL=INFO
VEEVA_DB_PATH=/app/data/database/veeva_opendata.db

# Performance Settings
VEEVA_DB_POOL_SIZE=10
VEEVA_MAX_WORKERS=4
VEEVA_QUERY_TIMEOUT=300

# Monitoring Settings
VEEVA_METRICS_ENABLED=true
VEEVA_HEALTH_CHECK_INTERVAL=30

# Security Settings
VEEVA_SECURE_LOGS=true
VEEVA_MASK_SENSITIVE_DATA=true

# Resource Limits
MEMORY_LIMIT=2g
CPU_LIMIT=1.0
```

### Critical Configuration Items

1. **Database Path**: Ensure `VEEVA_DB_PATH` points to persistent storage
2. **Resource Limits**: Adjust based on your infrastructure capacity
3. **Alert Thresholds**: Configure monitoring thresholds for your environment
4. **Backup Settings**: Configure backup retention and frequency

## Deployment Scripts

### deploy.sh

Main deployment script with comprehensive options:

```bash
# Full production deployment with all checks
./scripts/deploy.sh production --build --test --backup

# Quick staging deployment
./scripts/deploy.sh staging --build

# Force recreate containers
./scripts/deploy.sh production --force-recreate

# Skip health checks (for automated deployments)
./scripts/deploy.sh production --skip-health-check
```

**Options:**
- `--build`: Build new Docker image
- `--backup`: Create database backup before deployment
- `--test`: Run tests before deployment
- `--skip-health-check`: Skip post-deployment health checks
- `--force-recreate`: Force recreate containers

### backup.sh

Database backup with integrity verification:

```bash
# Create production backup
./scripts/backup.sh --environment production

# Backup with custom retention
./scripts/backup.sh --retention-days 60

# Uncompressed backup without verification
./scripts/backup.sh --no-compress --no-verify
```

### restore.sh

Database restore with safety checks:

```bash
# Restore latest backup
./scripts/restore.sh latest

# Restore specific backup file
./scripts/restore.sh /path/to/backup.db.gz

# Force restore without confirmation
./scripts/restore.sh latest --force --no-backup
```

### monitor.sh

Comprehensive monitoring and alerting:

```bash
# Start monitoring stack
./scripts/monitor.sh start

# Check system status
./scripts/monitor.sh status

# Run health checks
./scripts/monitor.sh health

# View real-time metrics
./scripts/monitor.sh metrics

# Generate monitoring report
./scripts/monitor.sh status --report --output /path/to/report.md
```

### maintenance.sh

Automated maintenance tasks:

```bash
# Run all maintenance tasks
./scripts/maintenance.sh all

# Clean up old files
./scripts/maintenance.sh cleanup --retention 30

# Optimize database
./scripts/maintenance.sh optimize

# Dry run mode
./scripts/maintenance.sh all --dry-run
```

## Monitoring and Alerting

### Prometheus Metrics

The system exports metrics for monitoring:

- **System Metrics**: CPU, memory, disk usage
- **Database Metrics**: Query performance, database size, connection pool
- **Application Metrics**: Validation results, processing times, error rates
- **Health Check Metrics**: Service availability, response times

### Grafana Dashboards

Access Grafana at `http://localhost:3000` (admin/admin) for:

- System overview dashboard
- Database performance metrics
- Application health monitoring
- Alert status and history

### Alert Configuration

Alerts are configured for:

- **Critical**: Database unavailable, high error rates, system failures
- **Warning**: High resource usage, slow queries, validation issues
- **Info**: Deployment notifications, maintenance schedules

## Health Checks

### Application Health Endpoints

```bash
# Basic status check
curl http://localhost:8001/health

# Detailed health report
curl http://localhost:8001/health/detailed

# System metrics
curl http://localhost:8000/metrics
```

### Health Check Components

1. **Database Health**: Connectivity, integrity, performance
2. **System Resources**: CPU, memory, disk space
3. **Application Health**: Service availability, recent errors
4. **Performance Metrics**: Query times, processing rates

## Backup and Recovery

### Backup Strategy

- **Frequency**: Every 6 hours (configurable)
- **Retention**: 30 days for production, 7 days for staging
- **Verification**: Integrity checks on all backups
- **Compression**: Gzip compression to reduce storage
- **Metadata**: Backup information and restore instructions

### Recovery Procedures

1. **Identify backup**: Use `ls -la deploy/backups/` to find backups
2. **Stop application**: `docker-compose down`
3. **Restore database**: `./scripts/restore.sh latest`
4. **Restart application**: `./scripts/deploy.sh production`
5. **Verify functionality**: `./scripts/monitor.sh health`

## Security Considerations

### Container Security

- Non-root user (UID 1000)
- Read-only root filesystem
- No privileged escalation
- Minimal base image
- Regular security updates

### Data Security

- Encrypted data at rest (configure volume encryption)
- Secure logging (sensitive data masking)
- Access controls (file permissions)
- Backup encryption (configure backup encryption)

### Network Security

- Container network isolation
- Firewall rules (configure as needed)
- TLS encryption (configure reverse proxy)
- Access logging and monitoring

## Performance Tuning

### Database Optimization

```bash
# Run database optimization
./scripts/maintenance.sh optimize

# Monitor database performance
docker-compose exec veeva-dq-app python python/main.py monitor --database
```

### Resource Allocation

Adjust resource limits based on usage:

```yaml
# docker-compose.yml
services:
  veeva-dq-app:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

### Scaling Considerations

- **Horizontal Scaling**: Multiple container instances with load balancer
- **Vertical Scaling**: Increase CPU/memory allocation
- **Database Scaling**: Consider read replicas for heavy query workloads
- **Storage Scaling**: Monitor disk usage and add capacity proactively

## Troubleshooting

### Common Issues

#### Container Won't Start

```bash
# Check container logs
docker-compose logs veeva-dq-app

# Check resource usage
docker stats

# Verify configuration
docker-compose config
```

#### Database Connection Issues

```bash
# Check database file permissions
ls -la data/database/

# Test database connectivity
docker-compose exec veeva-dq-app python python/main.py status

# Check database integrity
sqlite3 data/database/veeva_opendata.db "PRAGMA integrity_check;"
```

#### High Resource Usage

```bash
# Monitor system resources
./scripts/monitor.sh metrics

# Run maintenance tasks
./scripts/maintenance.sh all

# Optimize database
./scripts/maintenance.sh optimize
```

#### Monitoring Stack Issues

```bash
# Restart monitoring services
docker-compose restart prometheus grafana

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Validate Prometheus config
docker-compose exec prometheus promtool check config /etc/prometheus/prometheus.yml
```

### Log Analysis

```bash
# Application logs
docker-compose logs -f veeva-dq-app

# System logs
journalctl -u docker -f

# Search for errors
grep -r "ERROR" logs/

# Monitor log file sizes
du -sh logs/*
```

## Maintenance Schedules

### Daily Tasks

- Health check monitoring
- Log rotation (automatic)
- Backup verification
- Alert review

### Weekly Tasks

```bash
# Run comprehensive maintenance
./scripts/maintenance.sh all

# Generate system reports
./scripts/monitor.sh status --report

# Review and rotate logs
./scripts/maintenance.sh rotate-logs
```

### Monthly Tasks

- Database optimization
- Security updates
- Capacity planning review
- Backup restoration testing
- Performance analysis

## Support and Documentation

### Getting Help

1. Check logs: `./scripts/monitor.sh logs`
2. Run health checks: `./scripts/monitor.sh health`
3. Review documentation in `docs/` directory
4. Check GitHub issues for known problems

### Additional Resources

- Application documentation: `../docs/`
- API documentation: `../docs/api/`
- Configuration reference: `../docs/configuration/`
- Troubleshooting guide: `../docs/troubleshooting/`

---

**Note**: This deployment guide assumes familiarity with Docker, containerization concepts, and basic system administration. For production deployments, ensure proper security reviews, capacity planning, and disaster recovery procedures are in place.