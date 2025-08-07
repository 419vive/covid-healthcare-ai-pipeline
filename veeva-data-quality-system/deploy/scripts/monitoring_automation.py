#!/usr/bin/env python3
"""
Monitoring and Alerting Automation for Veeva Data Quality System
Comprehensive monitoring with automated incident response
"""

import os
import sys
import json
import logging
import smtplib
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sqlite3
import psutil
import docker
import time
from dataclasses import dataclass, asdict

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

@dataclass
class Alert:
    """Alert data structure"""
    id: str
    severity: str  # critical, warning, info
    title: str
    description: str
    timestamp: datetime
    source: str
    metric_name: str
    metric_value: float
    threshold: float
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class MetricThreshold:
    """Metric threshold configuration"""
    metric_name: str
    warning_threshold: float
    critical_threshold: float
    comparison: str  # 'greater', 'less', 'equal'
    unit: str
    enabled: bool = True

class MonitoringAutomation:
    """Comprehensive monitoring and alerting system"""
    
    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.alerts_db_path = Path('/app/data/alerts.db')
        self.metrics_db_path = Path('/app/data/metrics.db')
        self.docker_client = None
        
        self._setup_logging()
        self._init_docker_client()
        self._init_databases()
        self._load_thresholds()
        
    def _load_config(self, config_path: str = None) -> Dict:
        """Load monitoring configuration"""
        default_config = {
            'monitoring': {
                'interval_seconds': 60,
                'retention_days': 90,
                'enable_email_alerts': True,
                'enable_webhook_alerts': True,
                'enable_auto_remediation': True
            },
            'thresholds': {
                'cpu_usage': {'warning': 80, 'critical': 95},
                'memory_usage': {'warning': 85, 'critical': 95},
                'disk_usage': {'warning': 85, 'critical': 95},
                'response_time': {'warning': 2000, 'critical': 5000},
                'database_connections': {'warning': 80, 'critical': 95},
                'error_rate': {'warning': 5, 'critical': 10}
            },
            'notifications': {
                'email': {
                    'smtp_server': os.getenv('SMTP_SERVER', 'localhost'),
                    'smtp_port': int(os.getenv('SMTP_PORT', '587')),
                    'username': os.getenv('SMTP_USERNAME', ''),
                    'password': os.getenv('SMTP_PASSWORD', ''),
                    'from_address': os.getenv('ALERT_FROM_EMAIL', 'alerts@veeva-system.local'),
                    'to_addresses': os.getenv('ALERT_TO_EMAILS', 'admin@veeva-system.local').split(',')
                },
                'webhook': {
                    'url': os.getenv('WEBHOOK_URL', ''),
                    'timeout': 10
                }
            },
            'auto_remediation': {
                'restart_unhealthy_containers': True,
                'cleanup_disk_space': True,
                'restart_high_memory_processes': False,  # Disabled by default for safety
                'escalation_threshold': 3  # Number of failed remediations before escalation
            }
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    self._deep_update(default_config, user_config)
            except Exception as e:
                print(f"Warning: Failed to load config from {config_path}: {e}")
        
        return default_config
    
    def _deep_update(self, base_dict: Dict, update_dict: Dict) -> None:
        """Deep update dictionary"""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def _setup_logging(self):
        """Setup logging configuration"""
        log_level = os.getenv('VEEVA_LOG_LEVEL', 'INFO')
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('MonitoringAutomation')
    
    def _init_docker_client(self):
        """Initialize Docker client"""
        try:
            self.docker_client = docker.from_env()
            self.docker_client.ping()
        except Exception as e:
            self.logger.warning(f"Failed to initialize Docker client: {e}")
            self.docker_client = None
    
    def _init_databases(self):
        """Initialize monitoring databases"""
        try:
            # Alerts database
            self.alerts_db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(self.alerts_db_path)) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS alerts (
                        id TEXT PRIMARY KEY,
                        severity TEXT NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT,
                        timestamp DATETIME NOT NULL,
                        source TEXT NOT NULL,
                        metric_name TEXT,
                        metric_value REAL,
                        threshold REAL,
                        resolved BOOLEAN DEFAULT FALSE,
                        resolved_at DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)
                ''')
                
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity)
                ''')
            
            # Metrics database
            with sqlite3.connect(str(self.metrics_db_path)) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS system_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        metric_name TEXT NOT NULL,
                        metric_value REAL NOT NULL,
                        unit TEXT,
                        source TEXT,
                        metadata TEXT
                    )
                ''')
                
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON system_metrics(timestamp)
                ''')
                
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_metrics_name ON system_metrics(metric_name)
                ''')
        
        except Exception as e:
            self.logger.error(f"Failed to initialize databases: {e}")
    
    def _load_thresholds(self):
        """Load metric thresholds from configuration"""
        self.thresholds = []
        
        for metric_name, config in self.config['thresholds'].items():
            warning_threshold = MetricThreshold(
                metric_name=metric_name,
                warning_threshold=config['warning'],
                critical_threshold=config['critical'],
                comparison='greater',
                unit=self._get_metric_unit(metric_name),
                enabled=True
            )
            self.thresholds.append(warning_threshold)
    
    def _get_metric_unit(self, metric_name: str) -> str:
        """Get appropriate unit for metric"""
        unit_map = {
            'cpu_usage': '%',
            'memory_usage': '%', 
            'disk_usage': '%',
            'response_time': 'ms',
            'database_connections': 'count',
            'error_rate': '%',
            'temperature': '°C',
            'network_latency': 'ms'
        }
        return unit_map.get(metric_name, '')
    
    def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive system metrics"""
        metrics = {
            'timestamp': datetime.now(),
            'system': {},
            'application': {},
            'containers': {},
            'database': {},
            'network': {}
        }
        
        try:
            # System metrics
            metrics['system'] = self._collect_system_metrics()
            
            # Application metrics
            metrics['application'] = self._collect_application_metrics()
            
            # Container metrics
            if self.docker_client:
                metrics['containers'] = self._collect_container_metrics()
            
            # Database metrics
            metrics['database'] = self._collect_database_metrics()
            
            # Network metrics
            metrics['network'] = self._collect_network_metrics()
            
        except Exception as e:
            self.logger.error(f"Failed to collect metrics: {e}")
        
        return metrics
    
    def _collect_system_metrics(self) -> Dict:
        """Collect system-level metrics"""
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # Network metrics
            network_io = psutil.net_io_counters()
            
            # Process metrics
            process_count = len(psutil.pids())
            
            return {
                'cpu': {
                    'usage_percent': cpu_percent,
                    'count': cpu_count,
                    'load_average': os.getloadavg() if hasattr(os, 'getloadavg') else None
                },
                'memory': {
                    'total_gb': round(memory.total / (1024**3), 2),
                    'available_gb': round(memory.available / (1024**3), 2),
                    'used_percent': memory.percent,
                    'cached_gb': round(memory.cached / (1024**3), 2) if hasattr(memory, 'cached') else 0,
                    'swap_used_percent': swap.percent,
                    'swap_total_gb': round(swap.total / (1024**3), 2)
                },
                'disk': {
                    'total_gb': round(disk.total / (1024**3), 2),
                    'used_gb': round(disk.used / (1024**3), 2),
                    'free_gb': round(disk.free / (1024**3), 2),
                    'used_percent': round((disk.used / disk.total) * 100, 1),
                    'read_bytes_per_sec': disk_io.read_bytes if disk_io else 0,
                    'write_bytes_per_sec': disk_io.write_bytes if disk_io else 0
                },
                'network': {
                    'bytes_sent': network_io.bytes_sent if network_io else 0,
                    'bytes_recv': network_io.bytes_recv if network_io else 0,
                    'packets_sent': network_io.packets_sent if network_io else 0,
                    'packets_recv': network_io.packets_recv if network_io else 0
                },
                'processes': {
                    'count': process_count
                }
            }
            
        except Exception as e:
            self.logger.error(f"Failed to collect system metrics: {e}")
            return {}
    
    def _collect_application_metrics(self) -> Dict:
        """Collect application-specific metrics"""
        try:
            metrics = {
                'response_times': [],
                'error_rates': {},
                'database_query_times': [],
                'active_connections': 0
            }
            
            # Simulate application health check
            start_time = time.time()
            health_check_result = self._perform_application_health_check()
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            metrics['response_times'].append(response_time)
            metrics['health_status'] = health_check_result
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to collect application metrics: {e}")
            return {}
    
    def _collect_container_metrics(self) -> Dict:
        """Collect container-specific metrics"""
        try:
            container_metrics = {}
            
            veeva_containers = ['veeva-data-quality-system', 'veeva-prometheus', 'veeva-grafana']
            
            for container_name in veeva_containers:
                try:
                    container = self.docker_client.containers.get(container_name)
                    
                    # Get container stats
                    stats = container.stats(stream=False)
                    
                    # Calculate CPU usage
                    cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                               stats['precpu_stats']['cpu_usage']['total_usage']
                    system_cpu_delta = stats['cpu_stats']['system_cpu_usage'] - \
                                     stats['precpu_stats']['system_cpu_usage']
                    
                    cpu_usage = (cpu_delta / system_cpu_delta) * \
                               len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100.0
                    
                    # Calculate memory usage
                    memory_usage = stats['memory_stats']['usage']
                    memory_limit = stats['memory_stats']['limit']
                    memory_percent = (memory_usage / memory_limit) * 100.0
                    
                    container_metrics[container_name] = {
                        'status': container.status,
                        'cpu_usage_percent': round(cpu_usage, 2),
                        'memory_usage_mb': round(memory_usage / (1024**2), 2),
                        'memory_limit_mb': round(memory_limit / (1024**2), 2),
                        'memory_usage_percent': round(memory_percent, 2),
                        'network_rx_bytes': stats['networks'].get('eth0', {}).get('rx_bytes', 0),
                        'network_tx_bytes': stats['networks'].get('eth0', {}).get('tx_bytes', 0)
                    }
                    
                except docker.errors.NotFound:
                    container_metrics[container_name] = {'status': 'not_found'}
                except Exception as e:
                    self.logger.warning(f"Failed to get stats for {container_name}: {e}")
                    container_metrics[container_name] = {'status': 'error', 'error': str(e)}
            
            return container_metrics
            
        except Exception as e:
            self.logger.error(f"Failed to collect container metrics: {e}")
            return {}
    
    def _collect_database_metrics(self) -> Dict:
        """Collect database-specific metrics"""
        try:
            metrics = {
                'connection_count': 0,
                'query_times': [],
                'database_size_mb': 0,
                'table_counts': {}
            }
            
            db_path = '/app/data/database/veeva_opendata.db'
            if os.path.exists(db_path):
                # Database size
                metrics['database_size_mb'] = round(os.path.getsize(db_path) / (1024**2), 2)
                
                # Connection test and table counts
                start_time = time.time()
                with sqlite3.connect(db_path, timeout=5) as conn:
                    query_time = (time.time() - start_time) * 1000
                    metrics['query_times'].append(query_time)
                    
                    cursor = conn.cursor()
                    
                    # Get table counts
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    tables = cursor.fetchall()
                    
                    for table in tables:
                        table_name = table[0]
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                        count = cursor.fetchone()[0]
                        metrics['table_counts'][table_name] = count
                    
                    # Database integrity check (quick)
                    cursor.execute("PRAGMA quick_check(1)")
                    integrity_result = cursor.fetchone()[0]
                    metrics['integrity_status'] = integrity_result
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to collect database metrics: {e}")
            return {}
    
    def _collect_network_metrics(self) -> Dict:
        """Collect network-specific metrics"""
        try:
            metrics = {
                'connections': [],
                'latency_tests': {}
            }
            
            # Network connections
            connections = psutil.net_connections()
            established_connections = [conn for conn in connections if conn.status == 'ESTABLISHED']
            
            metrics['connections'] = {
                'total': len(connections),
                'established': len(established_connections),
                'listening': len([conn for conn in connections if conn.status == 'LISTEN'])
            }
            
            # Basic latency tests to important endpoints
            test_endpoints = [
                ('localhost', 9090),  # Prometheus
                ('localhost', 3000)   # Grafana
            ]
            
            for host, port in test_endpoints:
                try:
                    start_time = time.time()
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex((host, port))
                    latency = (time.time() - start_time) * 1000
                    sock.close()
                    
                    metrics['latency_tests'][f"{host}:{port}"] = {
                        'latency_ms': round(latency, 2),
                        'reachable': result == 0
                    }
                except Exception as e:
                    metrics['latency_tests'][f"{host}:{port}"] = {
                        'latency_ms': -1,
                        'reachable': False,
                        'error': str(e)
                    }
            
            return metrics
            
        except Exception as e:
            self.logger.error(f"Failed to collect network metrics: {e}")
            return {}
    
    def _perform_application_health_check(self) -> Dict:
        """Perform application health check"""
        try:
            health_status = {
                'overall': 'healthy',
                'checks': {}
            }
            
            # Database connectivity
            try:
                db_path = '/app/data/database/veeva_opendata.db'
                if os.path.exists(db_path):
                    with sqlite3.connect(db_path, timeout=5) as conn:
                        conn.execute("SELECT 1")
                        health_status['checks']['database'] = 'healthy'
                else:
                    health_status['checks']['database'] = 'unhealthy'
                    health_status['overall'] = 'unhealthy'
            except Exception as e:
                health_status['checks']['database'] = 'unhealthy'
                health_status['overall'] = 'unhealthy'
            
            # File system checks
            try:
                required_paths = ['/app/data', '/app/logs', '/app/reports']
                for path in required_paths:
                    if not os.path.exists(path):
                        health_status['checks']['filesystem'] = 'unhealthy'
                        health_status['overall'] = 'unhealthy'
                        break
                else:
                    health_status['checks']['filesystem'] = 'healthy'
            except Exception:
                health_status['checks']['filesystem'] = 'unhealthy'
                health_status['overall'] = 'unhealthy'
            
            return health_status
            
        except Exception as e:
            return {
                'overall': 'error',
                'error': str(e)
            }
    
    def store_metrics(self, metrics: Dict) -> bool:
        """Store collected metrics in database"""
        try:
            with sqlite3.connect(str(self.metrics_db_path)) as conn:
                timestamp = metrics['timestamp'].isoformat()
                
                # Store system metrics
                system_metrics = metrics.get('system', {})
                for category, data in system_metrics.items():
                    if isinstance(data, dict):
                        for metric_name, value in data.items():
                            if isinstance(value, (int, float)):
                                conn.execute('''
                                    INSERT INTO system_metrics 
                                    (timestamp, metric_name, metric_value, unit, source, metadata)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                ''', (
                                    timestamp,
                                    f"system.{category}.{metric_name}",
                                    value,
                                    self._get_metric_unit(metric_name),
                                    'system',
                                    json.dumps({'category': category})
                                ))
                
                # Store container metrics
                container_metrics = metrics.get('containers', {})
                for container_name, data in container_metrics.items():
                    if isinstance(data, dict):
                        for metric_name, value in data.items():
                            if isinstance(value, (int, float)):
                                conn.execute('''
                                    INSERT INTO system_metrics 
                                    (timestamp, metric_name, metric_value, unit, source, metadata)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                ''', (
                                    timestamp,
                                    f"container.{metric_name}",
                                    value,
                                    self._get_metric_unit(metric_name),
                                    container_name,
                                    json.dumps({'container': container_name})
                                ))
                
                # Store database metrics
                db_metrics = metrics.get('database', {})
                for metric_name, value in db_metrics.items():
                    if isinstance(value, (int, float)):
                        conn.execute('''
                            INSERT INTO system_metrics 
                            (timestamp, metric_name, metric_value, unit, source, metadata)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            timestamp,
                            f"database.{metric_name}",
                            value,
                            self._get_metric_unit(metric_name),
                            'database',
                            json.dumps({'type': 'database'})
                        ))
                
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to store metrics: {e}")
            return False
    
    def check_thresholds(self, metrics: Dict) -> List[Alert]:
        """Check metrics against thresholds and generate alerts"""
        alerts = []
        
        try:
            # Extract flat metrics for threshold checking
            flat_metrics = self._flatten_metrics(metrics)
            
            for threshold in self.thresholds:
                if not threshold.enabled:
                    continue
                
                metric_name = threshold.metric_name
                metric_value = None
                
                # Map threshold names to actual metric paths
                metric_mapping = {
                    'cpu_usage': 'system.cpu.usage_percent',
                    'memory_usage': 'system.memory.used_percent',
                    'disk_usage': 'system.disk.used_percent',
                    'response_time': 'application.response_times.avg',
                    'database_connections': 'database.connection_count',
                    'error_rate': 'application.error_rate'
                }
                
                actual_metric_path = metric_mapping.get(metric_name)
                if actual_metric_path and actual_metric_path in flat_metrics:
                    metric_value = flat_metrics[actual_metric_path]
                elif metric_name in flat_metrics:
                    metric_value = flat_metrics[metric_name]
                
                if metric_value is None:
                    continue
                
                # Check thresholds
                if self._exceeds_threshold(metric_value, threshold.critical_threshold, threshold.comparison):
                    alert = Alert(
                        id=f"alert_{metric_name}_{int(time.time())}",
                        severity='critical',
                        title=f"Critical: {metric_name.replace('_', ' ').title()}",
                        description=f"{metric_name} is {metric_value}{threshold.unit}, exceeding critical threshold of {threshold.critical_threshold}{threshold.unit}",
                        timestamp=datetime.now(),
                        source='monitoring',
                        metric_name=metric_name,
                        metric_value=metric_value,
                        threshold=threshold.critical_threshold
                    )
                    alerts.append(alert)
                    
                elif self._exceeds_threshold(metric_value, threshold.warning_threshold, threshold.comparison):
                    alert = Alert(
                        id=f"alert_{metric_name}_{int(time.time())}",
                        severity='warning',
                        title=f"Warning: {metric_name.replace('_', ' ').title()}",
                        description=f"{metric_name} is {metric_value}{threshold.unit}, exceeding warning threshold of {threshold.warning_threshold}{threshold.unit}",
                        timestamp=datetime.now(),
                        source='monitoring',
                        metric_name=metric_name,
                        metric_value=metric_value,
                        threshold=threshold.warning_threshold
                    )
                    alerts.append(alert)
            
        except Exception as e:
            self.logger.error(f"Failed to check thresholds: {e}")
        
        return alerts
    
    def _flatten_metrics(self, metrics: Dict, prefix: str = '') -> Dict[str, float]:
        """Flatten nested metrics dictionary"""
        flat = {}
        
        for key, value in metrics.items():
            if key == 'timestamp':
                continue
                
            new_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                flat.update(self._flatten_metrics(value, new_key))
            elif isinstance(value, (int, float)):
                flat[new_key] = value
            elif isinstance(value, list) and value and all(isinstance(x, (int, float)) for x in value):
                # Handle lists of numbers (e.g., response times)
                flat[f"{new_key}.avg"] = sum(value) / len(value)
                flat[f"{new_key}.max"] = max(value)
                flat[f"{new_key}.min"] = min(value)
        
        return flat
    
    def _exceeds_threshold(self, value: float, threshold: float, comparison: str) -> bool:
        """Check if value exceeds threshold based on comparison type"""
        if comparison == 'greater':
            return value > threshold
        elif comparison == 'less':
            return value < threshold
        elif comparison == 'equal':
            return value == threshold
        return False
    
    def store_alert(self, alert: Alert) -> bool:
        """Store alert in database"""
        try:
            with sqlite3.connect(str(self.alerts_db_path)) as conn:
                conn.execute('''
                    INSERT INTO alerts 
                    (id, severity, title, description, timestamp, source, 
                     metric_name, metric_value, threshold, resolved, resolved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    alert.id,
                    alert.severity,
                    alert.title,
                    alert.description,
                    alert.timestamp.isoformat(),
                    alert.source,
                    alert.metric_name,
                    alert.metric_value,
                    alert.threshold,
                    alert.resolved,
                    alert.resolved_at.isoformat() if alert.resolved_at else None
                ))
                conn.commit()
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to store alert: {e}")
            return False
    
    def send_alert_notification(self, alert: Alert) -> bool:
        """Send alert notification via configured channels"""
        success = True
        
        try:
            if self.config['notifications']['email']['from_address']:
                success &= self._send_email_alert(alert)
            
            if self.config['notifications']['webhook']['url']:
                success &= self._send_webhook_alert(alert)
                
        except Exception as e:
            self.logger.error(f"Failed to send alert notification: {e}")
            success = False
        
        return success
    
    def _send_email_alert(self, alert: Alert) -> bool:
        """Send email alert notification"""
        try:
            email_config = self.config['notifications']['email']
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = email_config['from_address']
            msg['To'] = ', '.join(email_config['to_addresses'])
            msg['Subject'] = f"[{alert.severity.upper()}] Veeva System Alert: {alert.title}"
            
            # Create email body
            body = f"""
            Alert Details:
            =============
            Severity: {alert.severity.upper()}
            Title: {alert.title}
            Description: {alert.description}
            Timestamp: {alert.timestamp}
            Source: {alert.source}
            
            Metric Information:
            - Metric: {alert.metric_name}
            - Current Value: {alert.metric_value}
            - Threshold: {alert.threshold}
            
            Alert ID: {alert.id}
            
            This is an automated alert from the Veeva Data Quality System monitoring.
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            with smtplib.SMTP(email_config['smtp_server'], email_config['smtp_port']) as server:
                if email_config['username'] and email_config['password']:
                    server.starttls()
                    server.login(email_config['username'], email_config['password'])
                
                server.send_message(msg)
            
            self.logger.info(f"Email alert sent for {alert.id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email alert: {e}")
            return False
    
    def _send_webhook_alert(self, alert: Alert) -> bool:
        """Send webhook alert notification"""
        try:
            webhook_config = self.config['notifications']['webhook']
            
            payload = {
                'alert': alert.to_dict(),
                'system': 'veeva-data-quality-system',
                'timestamp': datetime.now().isoformat()
            }
            
            response = requests.post(
                webhook_config['url'],
                json=payload,
                timeout=webhook_config['timeout'],
                headers={'Content-Type': 'application/json'}
            )
            
            response.raise_for_status()
            self.logger.info(f"Webhook alert sent for {alert.id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send webhook alert: {e}")
            return False
    
    def attempt_auto_remediation(self, alert: Alert) -> Dict:
        """Attempt automated remediation for alert"""
        remediation_result = {
            'attempted': False,
            'successful': False,
            'actions': [],
            'error': None
        }
        
        if not self.config['auto_remediation']:
            return remediation_result
        
        try:
            remediation_result['attempted'] = True
            
            if alert.metric_name == 'disk_usage' and alert.severity == 'critical':
                # Disk cleanup remediation
                if self.config['auto_remediation']['cleanup_disk_space']:
                    from disk_space_manager import DiskSpaceManager
                    disk_manager = DiskSpaceManager()
                    cleanup_results = disk_manager.perform_cleanup(aggressive=True)
                    
                    if cleanup_results['total_freed_mb'] > 0:
                        remediation_result['successful'] = True
                        remediation_result['actions'].append(f"Freed {cleanup_results['total_freed_mb']} MB disk space")
            
            elif alert.metric_name in ['cpu_usage', 'memory_usage'] and alert.severity == 'critical':
                # Container restart remediation
                if self.config['auto_remediation']['restart_unhealthy_containers'] and self.docker_client:
                    containers = self.docker_client.containers.list()
                    for container in containers:
                        if 'veeva' in container.name.lower():
                            container.restart()
                            remediation_result['actions'].append(f"Restarted container {container.name}")
                    
                    if remediation_result['actions']:
                        remediation_result['successful'] = True
            
        except Exception as e:
            remediation_result['error'] = str(e)
            self.logger.error(f"Auto-remediation failed for {alert.id}: {e}")
        
        return remediation_result
    
    def run_monitoring_cycle(self) -> Dict:
        """Run complete monitoring cycle"""
        cycle_result = {
            'timestamp': datetime.now(),
            'metrics_collected': False,
            'alerts_generated': 0,
            'notifications_sent': 0,
            'remediations_attempted': 0,
            'errors': []
        }
        
        try:
            # Collect metrics
            metrics = self.collect_system_metrics()
            if metrics:
                # Store metrics
                if self.store_metrics(metrics):
                    cycle_result['metrics_collected'] = True
                
                # Check thresholds and generate alerts
                alerts = self.check_thresholds(metrics)
                cycle_result['alerts_generated'] = len(alerts)
                
                # Process each alert
                for alert in alerts:
                    # Store alert
                    self.store_alert(alert)
                    
                    # Send notifications
                    if self.send_alert_notification(alert):
                        cycle_result['notifications_sent'] += 1
                    
                    # Attempt auto-remediation
                    if alert.severity == 'critical':
                        remediation_result = self.attempt_auto_remediation(alert)
                        if remediation_result['attempted']:
                            cycle_result['remediations_attempted'] += 1
        
        except Exception as e:
            self.logger.error(f"Monitoring cycle failed: {e}")
            cycle_result['errors'].append(str(e))
        
        return cycle_result
    
    def cleanup_old_data(self) -> Dict:
        """Clean up old monitoring data"""
        cleanup_result = {
            'alerts_cleaned': 0,
            'metrics_cleaned': 0,
            'errors': []
        }
        
        try:
            retention_days = self.config['monitoring']['retention_days']
            cutoff_date = datetime.now() - timedelta(days=retention_days)
            
            # Clean old alerts
            with sqlite3.connect(str(self.alerts_db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM alerts WHERE timestamp < ?', (cutoff_date.isoformat(),))
                alerts_count = cursor.fetchone()[0]
                
                cursor.execute('DELETE FROM alerts WHERE timestamp < ?', (cutoff_date.isoformat(),))
                conn.commit()
                cleanup_result['alerts_cleaned'] = alerts_count
            
            # Clean old metrics
            with sqlite3.connect(str(self.metrics_db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM system_metrics WHERE timestamp < ?', (cutoff_date.isoformat(),))
                metrics_count = cursor.fetchone()[0]
                
                cursor.execute('DELETE FROM system_metrics WHERE timestamp < ?', (cutoff_date.isoformat(),))
                conn.commit()
                cleanup_result['metrics_cleaned'] = metrics_count
        
        except Exception as e:
            cleanup_result['errors'].append(str(e))
            self.logger.error(f"Data cleanup failed: {e}")
        
        return cleanup_result
    
    def get_system_status(self) -> Dict:
        """Get comprehensive system status"""
        try:
            # Get recent metrics
            metrics = self.collect_system_metrics()
            
            # Get recent alerts
            recent_alerts = []
            try:
                with sqlite3.connect(str(self.alerts_db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT severity, title, description, timestamp, resolved
                        FROM alerts 
                        WHERE timestamp > datetime('now', '-1 hour')
                        ORDER BY timestamp DESC
                        LIMIT 10
                    ''')
                    
                    for row in cursor.fetchall():
                        recent_alerts.append({
                            'severity': row[0],
                            'title': row[1],
                            'description': row[2],
                            'timestamp': row[3],
                            'resolved': bool(row[4])
                        })
            except Exception:
                pass  # Database might not exist yet
            
            # Determine overall health
            health_issues = []
            if metrics.get('system', {}).get('cpu', {}).get('usage_percent', 0) > 90:
                health_issues.append('High CPU usage')
            if metrics.get('system', {}).get('memory', {}).get('used_percent', 0) > 90:
                health_issues.append('High memory usage')
            if metrics.get('system', {}).get('disk', {}).get('used_percent', 0) > 95:
                health_issues.append('Critical disk usage')
            
            overall_health = 'healthy'
            if any(alert['severity'] == 'critical' and not alert['resolved'] for alert in recent_alerts):
                overall_health = 'critical'
            elif health_issues or any(alert['severity'] == 'warning' and not alert['resolved'] for alert in recent_alerts):
                overall_health = 'warning'
            
            return {
                'overall_health': overall_health,
                'health_issues': health_issues,
                'current_metrics': metrics,
                'recent_alerts': recent_alerts,
                'monitoring_status': 'active',
                'last_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'overall_health': 'error',
                'error': str(e),
                'monitoring_status': 'error',
                'last_check': datetime.now().isoformat()
            }


def main():
    """Main entry point for monitoring automation"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Veeva Data Quality System Monitoring')
    parser.add_argument('action', 
                       choices=['run', 'status', 'cleanup', 'test-alert'],
                       help='Action to perform')
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    parser.add_argument('--interval', type=int, default=60, help='Monitoring interval in seconds')
    
    args = parser.parse_args()
    
    monitoring = MonitoringAutomation(config_path=args.config)
    
    if args.action == 'run':
        if args.continuous:
            print(f"🔍 Starting continuous monitoring (interval: {args.interval}s)")
            try:
                while True:
                    result = monitoring.run_monitoring_cycle()
                    
                    if not args.json:
                        print(f"[{result['timestamp']}] Cycle complete - "
                              f"Alerts: {result['alerts_generated']}, "
                              f"Notifications: {result['notifications_sent']}")
                    
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\n🛑 Monitoring stopped by user")
        else:
            result = monitoring.run_monitoring_cycle()
            
            if args.json:
                print(json.dumps(result, indent=2, default=str))
            else:
                print("🔍 Monitoring cycle completed")
                print(f"   📊 Metrics collected: {'Yes' if result['metrics_collected'] else 'No'}")
                print(f"   🚨 Alerts generated: {result['alerts_generated']}")
                print(f"   📧 Notifications sent: {result['notifications_sent']}")
                print(f"   🔧 Remediations attempted: {result['remediations_attempted']}")
                
                if result['errors']:
                    print("   ⚠️ Errors:")
                    for error in result['errors']:
                        print(f"     - {error}")
    
    elif args.action == 'status':
        status = monitoring.get_system_status()
        
        if args.json:
            print(json.dumps(status, indent=2, default=str))
        else:
            health_icon = {
                'healthy': '✅',
                'warning': '⚠️',
                'critical': '🔴',
                'error': '❌'
            }.get(status['overall_health'], '❓')
            
            print(f"{health_icon} System Health: {status['overall_health'].upper()}")
            
            if status.get('health_issues'):
                print("⚠️ Health Issues:")
                for issue in status['health_issues']:
                    print(f"   • {issue}")
            
            if status.get('recent_alerts'):
                print(f"\n🚨 Recent Alerts ({len(status['recent_alerts'])}):")
                for alert in status['recent_alerts'][:5]:
                    status_icon = "✅" if alert['resolved'] else "🔴"
                    print(f"   {status_icon} [{alert['severity'].upper()}] {alert['title']}")
    
    elif args.action == 'cleanup':
        result = monitoring.cleanup_old_data()
        
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("🧹 Data cleanup completed")
            print(f"   🚨 Alerts cleaned: {result['alerts_cleaned']}")
            print(f"   📊 Metrics cleaned: {result['metrics_cleaned']}")
            
            if result['errors']:
                print("   ⚠️ Errors:")
                for error in result['errors']:
                    print(f"     - {error}")
    
    elif args.action == 'test-alert':
        # Generate a test alert
        test_alert = Alert(
            id=f"test_alert_{int(time.time())}",
            severity='warning',
            title='Test Alert',
            description='This is a test alert to verify notification systems are working',
            timestamp=datetime.now(),
            source='test',
            metric_name='test_metric',
            metric_value=100,
            threshold=50
        )
        
        monitoring.store_alert(test_alert)
        success = monitoring.send_alert_notification(test_alert)
        
        if success:
            print("✅ Test alert sent successfully")
        else:
            print("❌ Failed to send test alert")


if __name__ == '__main__':
    main()