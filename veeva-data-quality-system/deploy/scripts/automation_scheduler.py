#!/usr/bin/env python3
"""
Automation Scheduler and Orchestrator for Veeva Data Quality System
Coordinates all automation tasks and ensures system self-maintenance
"""

import os
import sys
import json
import logging
import schedule
import time
import threading
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass, asdict
import signal
import psutil

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

@dataclass
class ScheduledTask:
    """Scheduled task configuration"""
    name: str
    function: Callable
    schedule_type: str  # 'interval', 'daily', 'weekly', 'monthly'
    schedule_value: str  # '5m', '1h', '2d', 'monday', etc.
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    failure_count: int = 0
    max_failures: int = 3
    timeout_seconds: int = 3600
    critical: bool = False
    dependencies: List[str] = None

class AutomationScheduler:
    """Comprehensive automation scheduler and orchestrator"""
    
    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.tasks = {}
        self.running = False
        self.scheduler_thread = None
        self.task_history = []
        
        # Setup logging
        self._setup_logging()
        
        # Initialize components
        self._init_automation_modules()
        
        # Setup scheduled tasks
        self._setup_scheduled_tasks()
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
    def _load_config(self, config_path: str = None) -> Dict:
        """Load scheduler configuration"""
        default_config = {
            'scheduler': {
                'check_interval_seconds': 30,
                'max_concurrent_tasks': 3,
                'task_timeout_seconds': 3600,
                'log_retention_days': 30,
                'enable_health_monitoring': True
            },
            'tasks': {
                'backup': {
                    'enabled': True,
                    'schedule': 'daily',
                    'time': '02:00',
                    'critical': True,
                    'timeout_seconds': 1800
                },
                'disk_cleanup': {
                    'enabled': True,
                    'schedule': 'daily',
                    'time': '01:00',
                    'critical': True,
                    'timeout_seconds': 600
                },
                'system_maintenance': {
                    'enabled': True,
                    'schedule': 'weekly',
                    'day': 'sunday',
                    'time': '03:00',
                    'critical': True,
                    'timeout_seconds': 3600
                },
                'monitoring': {
                    'enabled': True,
                    'schedule': 'interval',
                    'interval': '5m',
                    'critical': True,
                    'timeout_seconds': 300
                },
                'health_check': {
                    'enabled': True,
                    'schedule': 'interval',
                    'interval': '10m',
                    'critical': False,
                    'timeout_seconds': 120
                },
                'database_optimization': {
                    'enabled': True,
                    'schedule': 'weekly',
                    'day': 'saturday',
                    'time': '04:00',
                    'critical': False,
                    'timeout_seconds': 1800
                },
                'security_scan': {
                    'enabled': True,
                    'schedule': 'daily',
                    'time': '05:00',
                    'critical': False,
                    'timeout_seconds': 900
                }
            },
            'notifications': {
                'task_failure_threshold': 2,
                'critical_failure_immediate_notify': True,
                'daily_summary_enabled': True,
                'daily_summary_time': '08:00'
            },
            'recovery': {
                'auto_restart_failed_tasks': True,
                'restart_delay_minutes': 10,
                'max_restart_attempts': 3
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
        
        # Create logs directory
        log_dir = Path('/app/logs/automation')
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'scheduler.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('AutomationScheduler')
        
    def _init_automation_modules(self):
        """Initialize automation modules"""
        try:
            # Import automation modules
            from automated_backup import AutomatedBackupSystem
            from disk_space_manager import DiskSpaceManager
            from system_maintenance import SystemMaintenanceAutomation
            from monitoring_automation import MonitoringAutomation
            
            self.backup_system = AutomatedBackupSystem()
            self.disk_manager = DiskSpaceManager()
            self.maintenance_system = SystemMaintenanceAutomation()
            self.monitoring_system = MonitoringAutomation()
            
            self.logger.info("Automation modules initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize automation modules: {e}")
            raise
    
    def _setup_scheduled_tasks(self):
        """Setup all scheduled tasks"""
        task_configs = self.config['tasks']
        
        # Backup task
        if task_configs['backup']['enabled']:
            self.add_task(ScheduledTask(
                name='automated_backup',
                function=self._run_backup_task,
                schedule_type='daily',
                schedule_value=task_configs['backup']['time'],
                critical=task_configs['backup']['critical'],
                timeout_seconds=task_configs['backup']['timeout_seconds']
            ))
        
        # Disk cleanup task
        if task_configs['disk_cleanup']['enabled']:
            self.add_task(ScheduledTask(
                name='disk_cleanup',
                function=self._run_disk_cleanup_task,
                schedule_type='daily',
                schedule_value=task_configs['disk_cleanup']['time'],
                critical=task_configs['disk_cleanup']['critical'],
                timeout_seconds=task_configs['disk_cleanup']['timeout_seconds']
            ))
        
        # System maintenance task
        if task_configs['system_maintenance']['enabled']:
            self.add_task(ScheduledTask(
                name='system_maintenance',
                function=self._run_maintenance_task,
                schedule_type='weekly',
                schedule_value=f"{task_configs['system_maintenance']['day']}_{task_configs['system_maintenance']['time']}",
                critical=task_configs['system_maintenance']['critical'],
                timeout_seconds=task_configs['system_maintenance']['timeout_seconds']
            ))
        
        # Monitoring task
        if task_configs['monitoring']['enabled']:
            self.add_task(ScheduledTask(
                name='monitoring_cycle',
                function=self._run_monitoring_task,
                schedule_type='interval',
                schedule_value=task_configs['monitoring']['interval'],
                critical=task_configs['monitoring']['critical'],
                timeout_seconds=task_configs['monitoring']['timeout_seconds']
            ))
        
        # Health check task
        if task_configs['health_check']['enabled']:
            self.add_task(ScheduledTask(
                name='health_check',
                function=self._run_health_check_task,
                schedule_type='interval',
                schedule_value=task_configs['health_check']['interval'],
                critical=task_configs['health_check']['critical'],
                timeout_seconds=task_configs['health_check']['timeout_seconds']
            ))
        
        # Database optimization task
        if task_configs['database_optimization']['enabled']:
            self.add_task(ScheduledTask(
                name='database_optimization',
                function=self._run_database_optimization_task,
                schedule_type='weekly',
                schedule_value=f"{task_configs['database_optimization']['day']}_{task_configs['database_optimization']['time']}",
                critical=task_configs['database_optimization']['critical'],
                timeout_seconds=task_configs['database_optimization']['timeout_seconds']
            ))
        
        # Security scan task
        if task_configs['security_scan']['enabled']:
            self.add_task(ScheduledTask(
                name='security_scan',
                function=self._run_security_scan_task,
                schedule_type='daily',
                schedule_value=task_configs['security_scan']['time'],
                critical=task_configs['security_scan']['critical'],
                timeout_seconds=task_configs['security_scan']['timeout_seconds']
            ))
        
        # Daily summary task
        if self.config['notifications']['daily_summary_enabled']:
            self.add_task(ScheduledTask(
                name='daily_summary',
                function=self._run_daily_summary_task,
                schedule_type='daily',
                schedule_value=self.config['notifications']['daily_summary_time'],
                critical=False,
                timeout_seconds=300
            ))
        
        self.logger.info(f"Setup {len(self.tasks)} scheduled tasks")
    
    def add_task(self, task: ScheduledTask) -> None:
        """Add a scheduled task"""
        self.tasks[task.name] = task
        self._schedule_task(task)
        self.logger.info(f"Added scheduled task: {task.name}")
    
    def _schedule_task(self, task: ScheduledTask) -> None:
        """Schedule a task using the schedule library"""
        if task.schedule_type == 'interval':
            # Parse interval (e.g., '5m', '1h', '30s')
            interval_value = task.schedule_value
            if interval_value.endswith('s'):
                seconds = int(interval_value[:-1])
                schedule.every(seconds).seconds.do(self._execute_task_wrapper, task.name)
            elif interval_value.endswith('m'):
                minutes = int(interval_value[:-1])
                schedule.every(minutes).minutes.do(self._execute_task_wrapper, task.name)
            elif interval_value.endswith('h'):
                hours = int(interval_value[:-1])
                schedule.every(hours).hours.do(self._execute_task_wrapper, task.name)
            elif interval_value.endswith('d'):
                days = int(interval_value[:-1])
                schedule.every(days).days.do(self._execute_task_wrapper, task.name)
        
        elif task.schedule_type == 'daily':
            schedule.every().day.at(task.schedule_value).do(self._execute_task_wrapper, task.name)
        
        elif task.schedule_type == 'weekly':
            # Parse weekly schedule (e.g., 'monday_10:00', 'sunday_03:00')
            if '_' in task.schedule_value:
                day, time = task.schedule_value.split('_')
                getattr(schedule.every(), day.lower()).at(time).do(self._execute_task_wrapper, task.name)
        
        elif task.schedule_type == 'monthly':
            # For monthly tasks, we'll check on the first day of each month
            schedule.every().month.do(self._execute_task_wrapper, task.name)
    
    def _execute_task_wrapper(self, task_name: str) -> None:
        """Wrapper for task execution with error handling"""
        if not self.running:
            return
        
        task = self.tasks.get(task_name)
        if not task or not task.enabled:
            return
        
        # Check if task is already running
        if self._is_task_running(task_name):
            self.logger.warning(f"Task {task_name} is already running, skipping")
            return
        
        # Execute task in a separate thread
        task_thread = threading.Thread(
            target=self._execute_task,
            args=(task,),
            name=f"Task-{task_name}"
        )
        task_thread.daemon = True
        task_thread.start()
    
    def _is_task_running(self, task_name: str) -> bool:
        """Check if a task is currently running"""
        for thread in threading.enumerate():
            if thread.name == f"Task-{task_name}" and thread.is_alive():
                return True
        return False
    
    def _execute_task(self, task: ScheduledTask) -> None:
        """Execute a scheduled task"""
        start_time = datetime.now()
        task_result = {
            'task_name': task.name,
            'start_time': start_time,
            'end_time': None,
            'duration_seconds': 0,
            'success': False,
            'error': None,
            'result': None
        }
        
        try:
            self.logger.info(f"Starting task: {task.name}")
            
            # Update task status
            task.last_run = start_time
            task.run_count += 1
            
            # Execute the task function with timeout
            if task.timeout_seconds:
                result = self._execute_with_timeout(task.function, task.timeout_seconds)
            else:
                result = task.function()
            
            # Task completed successfully
            task_result['success'] = True
            task_result['result'] = result
            task.failure_count = 0  # Reset failure count on success
            
            self.logger.info(f"Task {task.name} completed successfully")
            
        except Exception as e:
            # Task failed
            task_result['error'] = str(e)
            task.failure_count += 1
            
            self.logger.error(f"Task {task.name} failed: {e}")
            
            # Handle critical task failures
            if task.critical:
                self._handle_critical_task_failure(task, str(e))
            
            # Auto-restart failed tasks if enabled
            if self.config['recovery']['auto_restart_failed_tasks'] and task.failure_count < task.max_failures:
                self._schedule_task_restart(task)
        
        finally:
            # Update task result
            task_result['end_time'] = datetime.now()
            task_result['duration_seconds'] = (task_result['end_time'] - start_time).total_seconds()
            
            # Store task history
            self.task_history.append(task_result)
            
            # Cleanup old history
            self._cleanup_task_history()
    
    def _execute_with_timeout(self, func: Callable, timeout_seconds: int):
        """Execute function with timeout"""
        import signal
        
        class TimeoutException(Exception):
            pass
        
        def timeout_handler(signum, frame):
            raise TimeoutException(f"Task timed out after {timeout_seconds} seconds")
        
        # Set up timeout
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout_seconds)
        
        try:
            result = func()
            signal.alarm(0)  # Cancel alarm
            return result
        finally:
            signal.signal(signal.SIGALRM, old_handler)
    
    def _handle_critical_task_failure(self, task: ScheduledTask, error: str) -> None:
        """Handle critical task failure"""
        self.logger.critical(f"CRITICAL TASK FAILURE: {task.name} - {error}")
        
        # Send immediate notification if enabled
        if self.config['notifications']['critical_failure_immediate_notify']:
            self._send_critical_failure_notification(task, error)
        
        # Attempt emergency recovery
        self._attempt_emergency_recovery(task, error)
    
    def _schedule_task_restart(self, task: ScheduledTask) -> None:
        """Schedule a failed task for restart"""
        restart_delay = self.config['recovery']['restart_delay_minutes']
        
        def restart_task():
            if task.failure_count < task.max_failures:
                self.logger.info(f"Restarting failed task: {task.name}")
                self._execute_task(task)
        
        # Schedule restart
        threading.Timer(restart_delay * 60, restart_task).start()
        self.logger.info(f"Scheduled restart for {task.name} in {restart_delay} minutes")
    
    def _attempt_emergency_recovery(self, task: ScheduledTask, error: str) -> None:
        """Attempt emergency recovery for critical system failures"""
        try:
            if 'disk' in error.lower() or 'space' in error.lower():
                # Emergency disk cleanup
                self.logger.info("Attempting emergency disk cleanup")
                emergency_cleanup = self.disk_manager.perform_cleanup(aggressive=True)
                if emergency_cleanup['total_freed_mb'] > 0:
                    self.logger.info(f"Emergency cleanup freed {emergency_cleanup['total_freed_mb']} MB")
            
            elif 'memory' in error.lower():
                # Restart containers to free memory
                self.logger.info("Attempting container restart for memory issues")
                try:
                    subprocess.run(['docker', 'restart', 'veeva-data-quality-system'], 
                                 check=True, timeout=60)
                    self.logger.info("Container restarted successfully")
                except Exception as e:
                    self.logger.error(f"Failed to restart container: {e}")
            
            elif 'database' in error.lower():
                # Database recovery
                self.logger.info("Attempting database recovery")
                try:
                    recovery_result = self.maintenance_system.optimize_databases()
                    if recovery_result['issues_fixed'] > 0:
                        self.logger.info("Database recovery completed")
                except Exception as e:
                    self.logger.error(f"Database recovery failed: {e}")
        
        except Exception as e:
            self.logger.error(f"Emergency recovery failed: {e}")
    
    def _send_critical_failure_notification(self, task: ScheduledTask, error: str) -> None:
        """Send critical failure notification"""
        try:
            # Use monitoring system to send alert
            from monitoring_automation import Alert
            
            critical_alert = Alert(
                id=f"critical_task_failure_{task.name}_{int(time.time())}",
                severity='critical',
                title=f'Critical Task Failure: {task.name}',
                description=f'Critical automation task "{task.name}" has failed: {error}',
                timestamp=datetime.now(),
                source='automation_scheduler',
                metric_name='task_failure',
                metric_value=task.failure_count,
                threshold=task.max_failures
            )
            
            self.monitoring_system.send_alert_notification(critical_alert)
            
        except Exception as e:
            self.logger.error(f"Failed to send critical failure notification: {e}")
    
    def _cleanup_task_history(self) -> None:
        """Cleanup old task history"""
        retention_days = self.config['scheduler']['log_retention_days']
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        
        self.task_history = [
            result for result in self.task_history
            if result['start_time'] > cutoff_date
        ]
    
    def start(self) -> None:
        """Start the automation scheduler"""
        if self.running:
            self.logger.warning("Scheduler is already running")
            return
        
        self.running = True
        self.logger.info("Starting automation scheduler")
        
        # Start scheduler thread
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        self.logger.info("Automation scheduler started successfully")
    
    def stop(self) -> None:
        """Stop the automation scheduler"""
        if not self.running:
            return
        
        self.logger.info("Stopping automation scheduler")
        self.running = False
        
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        self.logger.info("Automation scheduler stopped")
    
    def _scheduler_loop(self) -> None:
        """Main scheduler loop"""
        check_interval = self.config['scheduler']['check_interval_seconds']
        
        while self.running:
            try:
                # Run pending scheduled tasks
                schedule.run_pending()
                
                # Health monitoring
                if self.config['scheduler']['enable_health_monitoring']:
                    self._monitor_scheduler_health()
                
                time.sleep(check_interval)
                
            except Exception as e:
                self.logger.error(f"Scheduler loop error: {e}")
                time.sleep(check_interval)
    
    def _monitor_scheduler_health(self) -> None:
        """Monitor scheduler health"""
        try:
            # Check system resources
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_percent = psutil.virtual_memory().percent
            
            # Check if we have too many concurrent tasks
            active_task_threads = [
                thread for thread in threading.enumerate()
                if thread.name.startswith('Task-') and thread.is_alive()
            ]
            
            if len(active_task_threads) > self.config['scheduler']['max_concurrent_tasks']:
                self.logger.warning(f"Too many concurrent tasks: {len(active_task_threads)}")
            
            # Check for stuck tasks
            for thread in active_task_threads:
                # This is a basic check - in production you'd want more sophisticated monitoring
                pass
        
        except Exception as e:
            self.logger.error(f"Scheduler health monitoring failed: {e}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully")
        self.stop()
        sys.exit(0)
    
    # Task implementations
    def _run_backup_task(self) -> Dict:
        """Run automated backup task"""
        success, backup_name, backup_info = self.backup_system.create_backup()
        
        if success:
            # Cleanup old backups
            cleanup_count, removed_backups = self.backup_system.cleanup_old_backups()
            backup_info['cleanup_count'] = cleanup_count
            backup_info['removed_backups'] = removed_backups
            
        return {
            'success': success,
            'backup_name': backup_name,
            'backup_info': backup_info
        }
    
    def _run_disk_cleanup_task(self) -> Dict:
        """Run disk cleanup task"""
        # Check current disk status
        disk_status = self.disk_manager.check_disk_status()
        
        # Perform cleanup based on disk status
        if disk_status['action_needed'] in ['immediate_cleanup', 'scheduled_cleanup']:
            cleanup_results = self.disk_manager.perform_cleanup(
                aggressive=(disk_status['action_needed'] == 'immediate_cleanup')
            )
        else:
            cleanup_results = {'total_freed_mb': 0, 'operations': [], 'errors': []}
        
        return {
            'disk_status': disk_status,
            'cleanup_results': cleanup_results
        }
    
    def _run_maintenance_task(self) -> Dict:
        """Run system maintenance task"""
        maintenance_results = self.maintenance_system.run_full_maintenance()
        return maintenance_results
    
    def _run_monitoring_task(self) -> Dict:
        """Run monitoring cycle task"""
        monitoring_results = self.monitoring_system.run_monitoring_cycle()
        return monitoring_results
    
    def _run_health_check_task(self) -> Dict:
        """Run health check task"""
        health_results = self.maintenance_system.perform_health_check()
        return health_results
    
    def _run_database_optimization_task(self) -> Dict:
        """Run database optimization task"""
        optimization_results = self.maintenance_system.optimize_databases()
        return optimization_results
    
    def _run_security_scan_task(self) -> Dict:
        """Run security scan task"""
        security_results = self.maintenance_system.check_security_updates()
        return security_results
    
    def _run_daily_summary_task(self) -> Dict:
        """Run daily summary task"""
        try:
            # Generate daily summary
            summary = self._generate_daily_summary()
            
            # Send summary notification
            self._send_daily_summary(summary)
            
            return {
                'success': True,
                'summary': summary
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _generate_daily_summary(self) -> Dict:
        """Generate daily operations summary"""
        yesterday = datetime.now() - timedelta(days=1)
        
        # Get task history for the last 24 hours
        recent_tasks = [
            result for result in self.task_history
            if result['start_time'] > yesterday
        ]
        
        # Calculate summary statistics
        summary = {
            'date': yesterday.date().isoformat(),
            'total_tasks': len(recent_tasks),
            'successful_tasks': len([t for t in recent_tasks if t['success']]),
            'failed_tasks': len([t for t in recent_tasks if not t['success']]),
            'total_runtime_minutes': sum(t['duration_seconds'] for t in recent_tasks) / 60,
            'task_breakdown': {},
            'system_health': 'healthy',
            'recommendations': []
        }
        
        # Task breakdown
        for task_result in recent_tasks:
            task_name = task_result['task_name']
            if task_name not in summary['task_breakdown']:
                summary['task_breakdown'][task_name] = {
                    'runs': 0,
                    'successes': 0,
                    'failures': 0,
                    'avg_duration_seconds': 0
                }
            
            breakdown = summary['task_breakdown'][task_name]
            breakdown['runs'] += 1
            if task_result['success']:
                breakdown['successes'] += 1
            else:
                breakdown['failures'] += 1
            breakdown['avg_duration_seconds'] = (
                breakdown['avg_duration_seconds'] * (breakdown['runs'] - 1) + 
                task_result['duration_seconds']
            ) / breakdown['runs']
        
        # Health assessment
        failure_rate = summary['failed_tasks'] / max(summary['total_tasks'], 1)
        if failure_rate > 0.2:  # More than 20% failures
            summary['system_health'] = 'degraded'
            summary['recommendations'].append('High task failure rate detected - investigate system issues')
        
        if failure_rate > 0.5:  # More than 50% failures
            summary['system_health'] = 'critical'
            summary['recommendations'].append('Critical system issues detected - immediate attention required')
        
        return summary
    
    def _send_daily_summary(self, summary: Dict) -> None:
        """Send daily summary notification"""
        try:
            # Create summary alert
            from monitoring_automation import Alert
            
            health_status = summary['system_health']
            severity = 'info'
            if health_status == 'degraded':
                severity = 'warning'
            elif health_status == 'critical':
                severity = 'critical'
            
            summary_alert = Alert(
                id=f"daily_summary_{summary['date']}",
                severity=severity,
                title=f'Daily Operations Summary - {summary["date"]}',
                description=f"""
                Daily Operations Summary for {summary['date']}:
                
                Tasks Executed: {summary['total_tasks']}
                Successful: {summary['successful_tasks']}
                Failed: {summary['failed_tasks']}
                Total Runtime: {summary['total_runtime_minutes']:.1f} minutes
                
                System Health: {health_status.upper()}
                
                {'Recommendations:' if summary['recommendations'] else ''}
                {chr(10).join(f'• {rec}' for rec in summary['recommendations'])}
                """,
                timestamp=datetime.now(),
                source='automation_scheduler',
                metric_name='daily_summary',
                metric_value=summary['successful_tasks'],
                threshold=summary['total_tasks']
            )
            
            self.monitoring_system.send_alert_notification(summary_alert)
            
        except Exception as e:
            self.logger.error(f"Failed to send daily summary: {e}")
    
    def get_status(self) -> Dict:
        """Get scheduler status"""
        try:
            status = {
                'running': self.running,
                'uptime_seconds': 0,
                'tasks': {},
                'recent_activity': [],
                'system_health': 'healthy'
            }
            
            # Task status
            for task_name, task in self.tasks.items():
                status['tasks'][task_name] = {
                    'enabled': task.enabled,
                    'schedule_type': task.schedule_type,
                    'schedule_value': task.schedule_value,
                    'last_run': task.last_run.isoformat() if task.last_run else None,
                    'run_count': task.run_count,
                    'failure_count': task.failure_count,
                    'critical': task.critical,
                    'currently_running': self._is_task_running(task_name)
                }
            
            # Recent activity (last 10 task executions)
            status['recent_activity'] = [
                {
                    'task_name': result['task_name'],
                    'start_time': result['start_time'].isoformat(),
                    'duration_seconds': result['duration_seconds'],
                    'success': result['success'],
                    'error': result.get('error')
                }
                for result in sorted(
                    self.task_history, 
                    key=lambda x: x['start_time'], 
                    reverse=True
                )[:10]
            ]
            
            # Health assessment
            recent_failures = [
                result for result in self.task_history[-20:]  # Last 20 tasks
                if not result['success']
            ]
            
            if len(recent_failures) > 10:  # More than 50% failures in recent tasks
                status['system_health'] = 'critical'
            elif len(recent_failures) > 4:  # More than 20% failures
                status['system_health'] = 'degraded'
            
            return status
            
        except Exception as e:
            return {
                'error': str(e),
                'running': self.running,
                'system_health': 'error'
            }


def main():
    """Main entry point for automation scheduler"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Veeva Data Quality System Automation Scheduler')
    parser.add_argument('action', 
                       choices=['start', 'stop', 'status', 'run-task'],
                       help='Action to perform')
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument('--task', help='Task name to run (for run-task action)')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon')
    
    args = parser.parse_args()
    
    scheduler = AutomationScheduler(config_path=args.config)
    
    if args.action == 'start':
        if args.daemon:
            # Run as daemon
            scheduler.start()
            try:
                while scheduler.running:
                    time.sleep(10)
            except KeyboardInterrupt:
                scheduler.stop()
        else:
            # Run and monitor
            scheduler.start()
            print("🚀 Automation scheduler started")
            print("   Press Ctrl+C to stop")
            
            try:
                while scheduler.running:
                    time.sleep(10)
                    if not args.json:
                        # Show brief status
                        status = scheduler.get_status()
                        active_tasks = [name for name, info in status['tasks'].items() 
                                      if info['currently_running']]
                        if active_tasks:
                            print(f"   🔄 Running tasks: {', '.join(active_tasks)}")
                        
            except KeyboardInterrupt:
                print("\n🛑 Stopping automation scheduler...")
                scheduler.stop()
                print("✅ Scheduler stopped")
    
    elif args.action == 'stop':
        scheduler.stop()
        print("✅ Scheduler stopped")
    
    elif args.action == 'status':
        status = scheduler.get_status()
        
        if args.json:
            print(json.dumps(status, indent=2, default=str))
        else:
            health_icon = {
                'healthy': '✅',
                'degraded': '⚠️',
                'critical': '🔴',
                'error': '❌'
            }.get(status['system_health'], '❓')
            
            print(f"{health_icon} Scheduler Status: {'RUNNING' if status['running'] else 'STOPPED'}")
            print(f"🏥 System Health: {status['system_health'].upper()}")
            print(f"📋 Tasks: {len(status['tasks'])}")
            
            print("\n📊 Task Status:")
            for task_name, task_info in status['tasks'].items():
                status_icon = "🔄" if task_info['currently_running'] else ("✅" if task_info['failure_count'] == 0 else "⚠️")
                print(f"   {status_icon} {task_name}: {task_info['run_count']} runs, {task_info['failure_count']} failures")
            
            if status['recent_activity']:
                print(f"\n📈 Recent Activity:")
                for activity in status['recent_activity'][:5]:
                    status_icon = "✅" if activity['success'] else "❌"
                    print(f"   {status_icon} {activity['task_name']}: {activity['duration_seconds']:.1f}s")
    
    elif args.action == 'run-task':
        if not args.task:
            print("❌ --task parameter required for run-task action")
            sys.exit(1)
        
        if args.task not in scheduler.tasks:
            print(f"❌ Task '{args.task}' not found")
            print(f"Available tasks: {', '.join(scheduler.tasks.keys())}")
            sys.exit(1)
        
        task = scheduler.tasks[args.task]
        print(f"🔄 Running task: {args.task}")
        
        start_time = time.time()
        scheduler._execute_task(task)
        duration = time.time() - start_time
        
        print(f"✅ Task completed in {duration:.1f} seconds")


if __name__ == '__main__':
    main()