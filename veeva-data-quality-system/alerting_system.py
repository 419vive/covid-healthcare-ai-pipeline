#!/usr/bin/env python3
"""
Veeva Data Quality System - Advanced Alerting System
Proactive monitoring and intelligent alerting for production infrastructure

This system provides intelligent alerting, escalation management, and
automated incident response for the Veeva Data Quality System.
"""

import os
import sys
import json
import time
import smtplib
import sqlite3
import logging
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Callable
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import psutil


@dataclass
class Alert:
    """Alert data structure"""
    id: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    component: str
    message: str
    details: Dict
    timestamp: str
    status: str  # ACTIVE, ACKNOWLEDGED, RESOLVED
    escalation_level: int
    last_notified: Optional[str]


@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    component: str
    metric: str
    operator: str  # >, <, ==, !=
    threshold: float
    severity: str
    enabled: bool
    cooldown_minutes: int


class AlertingSystem:
    """Advanced alerting and notification system"""
    
    def __init__(self, config_file: str = "config/alerting.json"):
        self.config_file = config_file
        self.alerts_db = os.path.join("data", "alerts.db")
        self.log_file = os.path.join("logs", "alerting_system.log")
        
        # Default thresholds
        self.default_rules = [
            AlertRule("CPU_HIGH", "system", "cpu_percent", ">", 80.0, "HIGH", True, 15),
            AlertRule("MEMORY_HIGH", "system", "memory_percent", ">", 85.0, "HIGH", True, 15),
            AlertRule("DISK_LOW", "system", "disk_free_gb", "<", 5.0, "CRITICAL", True, 30),
            AlertRule("QUERY_SLOW", "database", "avg_query_time_ms", ">", 100.0, "MEDIUM", True, 10),
            AlertRule("CONTAINER_DOWN", "container", "container_count", "<", 3, "CRITICAL", True, 5),
            AlertRule("ERROR_RATE_HIGH", "application", "error_rate_percent", ">", 5.0, "HIGH", True, 10)
        ]
        
        # Alert escalation configuration
        self.escalation_levels = {
            1: {"delay_minutes": 5, "method": "log"},
            2: {"delay_minutes": 15, "method": "email"},
            3: {"delay_minutes": 30, "method": "webhook"},
            4: {"delay_minutes": 60, "method": "emergency"}
        }
        
        self.config = self._load_config()
        self.active_alerts = {}
        self.notification_handlers = {
            "log": self._log_notification,
            "email": self._email_notification,
            "webhook": self._webhook_notification,
            "emergency": self._emergency_notification
        }
        
        self._setup_logging()
        self._setup_database()
        
    def _setup_logging(self):
        """Setup logging configuration"""
        os.makedirs("logs", exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def _setup_database(self):
        """Setup alerts database"""
        os.makedirs("data", exist_ok=True)
        
        with sqlite3.connect(self.alerts_db) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY,
                    severity TEXT NOT NULL,
                    component TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details TEXT,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    escalation_level INTEGER DEFAULT 0,
                    last_notified TEXT,
                    resolved_at TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS alert_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    component TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    threshold REAL NOT NULL,
                    severity TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    cooldown_minutes INTEGER DEFAULT 15,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS alert_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT,
                    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert default rules if they don't exist
            cursor = conn.cursor()
            for rule in self.default_rules:
                cursor.execute('''
                    INSERT OR IGNORE INTO alert_rules 
                    (name, component, metric, operator, threshold, severity, enabled, cooldown_minutes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    rule.name, rule.component, rule.metric, rule.operator,
                    rule.threshold, rule.severity, rule.enabled, rule.cooldown_minutes
                ))
                
    def _load_config(self) -> Dict:
        """Load alerting configuration"""
        default_config = {
            "email": {
                "enabled": False,
                "smtp_host": "",
                "smtp_port": 587,
                "username": "",
                "password": "",
                "from_email": "",
                "to_emails": []
            },
            "webhook": {
                "enabled": False,
                "urls": [],
                "timeout": 10
            },
            "emergency": {
                "enabled": False,
                "phone_numbers": [],
                "service": ""
            }
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    user_config = json.load(f)
                    # Merge with defaults
                    for section in default_config:
                        if section in user_config:
                            default_config[section].update(user_config[section])
            except Exception as e:
                self.logger.warning(f"Error loading config: {e}, using defaults")
                
        return default_config
        
    def evaluate_metrics(self, metrics: Dict) -> List[Alert]:
        """Evaluate metrics against alert rules"""
        new_alerts = []
        
        # Get active alert rules
        with sqlite3.connect(self.alerts_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT name, component, metric, operator, threshold, severity, cooldown_minutes
                FROM alert_rules WHERE enabled = 1
            ''')
            rules = cursor.fetchall()
            
        for rule_data in rules:
            rule = AlertRule(*rule_data, enabled=True)
            
            # Check if metric exists and evaluate
            if rule.metric in metrics:
                value = metrics[rule.metric]
                triggered = self._evaluate_condition(value, rule.operator, rule.threshold)
                
                if triggered:
                    # Check cooldown period
                    if self._is_in_cooldown(rule.name, rule.cooldown_minutes):
                        continue
                        
                    alert = Alert(
                        id=f"{rule.name}_{int(time.time())}",
                        severity=rule.severity,
                        component=rule.component,
                        message=f"{rule.name}: {rule.metric} {rule.operator} {rule.threshold} (current: {value})",
                        details={
                            "rule": rule.name,
                            "metric": rule.metric,
                            "threshold": rule.threshold,
                            "current_value": value,
                            "operator": rule.operator
                        },
                        timestamp=datetime.now().isoformat(),
                        status="ACTIVE",
                        escalation_level=0,
                        last_notified=None
                    )
                    
                    new_alerts.append(alert)
                    
        return new_alerts
        
    def _evaluate_condition(self, value: float, operator: str, threshold: float) -> bool:
        """Evaluate alert condition"""
        if operator == ">":
            return value > threshold
        elif operator == "<":
            return value < threshold
        elif operator == "==":
            return abs(value - threshold) < 0.001  # Float comparison
        elif operator == "!=":
            return abs(value - threshold) >= 0.001
        elif operator == ">=":
            return value >= threshold
        elif operator == "<=":
            return value <= threshold
        else:
            return False
            
    def _is_in_cooldown(self, rule_name: str, cooldown_minutes: int) -> bool:
        """Check if alert rule is in cooldown period"""
        cutoff = datetime.now() - timedelta(minutes=cooldown_minutes)
        
        with sqlite3.connect(self.alerts_db) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM alerts 
                WHERE message LIKE ? AND timestamp > ?
            ''', (f"{rule_name}:%", cutoff.isoformat()))
            
            count = cursor.fetchone()[0]
            return count > 0
            
    def process_alert(self, alert: Alert):
        """Process and handle a new alert"""
        # Store alert in database
        self._store_alert(alert)
        
        # Add to active alerts
        self.active_alerts[alert.id] = alert
        
        # Log the alert
        self.logger.warning(f"ALERT [{alert.severity}] {alert.component}: {alert.message}")
        
        # Start escalation process
        self._start_escalation(alert)
        
        # Record alert history
        self._record_alert_history(alert.id, "CREATED", {"severity": alert.severity})
        
    def _store_alert(self, alert: Alert):
        """Store alert in database"""
        with sqlite3.connect(self.alerts_db) as conn:
            conn.execute('''
                INSERT INTO alerts 
                (id, severity, component, message, details, timestamp, status, escalation_level, last_notified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                alert.id, alert.severity, alert.component, alert.message,
                json.dumps(alert.details), alert.timestamp, alert.status,
                alert.escalation_level, alert.last_notified
            ))
            
    def _start_escalation(self, alert: Alert):
        """Start alert escalation process"""
        def escalate():
            current_level = 1
            max_level = len(self.escalation_levels)
            
            while alert.status == "ACTIVE" and current_level <= max_level:
                # Wait for escalation delay
                if current_level > 1:
                    delay = self.escalation_levels[current_level]["delay_minutes"]
                    time.sleep(delay * 60)  # Convert to seconds
                    
                # Check if alert is still active
                if alert.id not in self.active_alerts or alert.status != "ACTIVE":
                    break
                    
                # Send notification
                method = self.escalation_levels[current_level]["method"]
                success = self._send_notification(alert, method, current_level)
                
                if success:
                    alert.escalation_level = current_level
                    alert.last_notified = datetime.now().isoformat()
                    self._update_alert(alert)
                    
                    self._record_alert_history(
                        alert.id, 
                        "ESCALATED", 
                        {"level": current_level, "method": method}
                    )
                    
                current_level += 1
                
        # Start escalation in background thread
        escalation_thread = threading.Thread(target=escalate)
        escalation_thread.daemon = True
        escalation_thread.start()
        
    def _send_notification(self, alert: Alert, method: str, level: int) -> bool:
        """Send notification using specified method"""
        try:
            if method in self.notification_handlers:
                return self.notification_handlers[method](alert, level)
            else:
                self.logger.error(f"Unknown notification method: {method}")
                return False
                
        except Exception as e:
            self.logger.error(f"Notification failed ({method}): {e}")
            return False
            
    def _log_notification(self, alert: Alert, level: int) -> bool:
        """Log notification method"""
        severity_emoji = {
            "CRITICAL": "🚨",
            "HIGH": "⚠️",
            "MEDIUM": "📄",
            "LOW": "ℹ️"
        }
        
        emoji = severity_emoji.get(alert.severity, "📄")
        message = f"{emoji} ALERT LEVEL {level}: [{alert.severity}] {alert.message}"
        
        self.logger.critical(message)
        return True
        
    def _email_notification(self, alert: Alert, level: int) -> bool:
        """Email notification method"""
        if not self.config["email"]["enabled"]:
            return False
            
        try:
            smtp_config = self.config["email"]
            
            # Create message
            msg = MIMEMultipart()
            msg["From"] = smtp_config["from_email"]
            msg["To"] = ", ".join(smtp_config["to_emails"])
            msg["Subject"] = f"[{alert.severity}] Veeva System Alert - {alert.component}"
            
            # Create email body
            body = f"""
VEEVA DATA QUALITY SYSTEM ALERT

Severity: {alert.severity}
Component: {alert.component}
Time: {alert.timestamp}
Escalation Level: {level}

Message: {alert.message}

Details:
{json.dumps(alert.details, indent=2)}

Please investigate immediately.

---
Veeva Infrastructure Monitoring System
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(smtp_config["smtp_host"], smtp_config["smtp_port"])
            server.starttls()
            server.login(smtp_config["username"], smtp_config["password"])
            
            text = msg.as_string()
            server.sendmail(smtp_config["from_email"], smtp_config["to_emails"], text)
            server.quit()
            
            self.logger.info(f"Email notification sent for alert {alert.id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Email notification failed: {e}")
            return False
            
    def _webhook_notification(self, alert: Alert, level: int) -> bool:
        """Webhook notification method"""
        if not self.config["webhook"]["enabled"]:
            return False
            
        payload = {
            "alert_id": alert.id,
            "severity": alert.severity,
            "component": alert.component,
            "message": alert.message,
            "details": alert.details,
            "timestamp": alert.timestamp,
            "escalation_level": level
        }
        
        success = True
        for url in self.config["webhook"]["urls"]:
            try:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=self.config["webhook"]["timeout"]
                )
                
                if response.status_code != 200:
                    self.logger.warning(f"Webhook {url} returned {response.status_code}")
                    success = False
                    
            except Exception as e:
                self.logger.error(f"Webhook {url} failed: {e}")
                success = False
                
        return success
        
    def _emergency_notification(self, alert: Alert, level: int) -> bool:
        """Emergency notification method (placeholder)"""
        # This would integrate with services like PagerDuty, Twilio, etc.
        self.logger.critical(f"EMERGENCY NOTIFICATION: {alert.message}")
        
        # For now, just log as emergency
        return True
        
    def acknowledge_alert(self, alert_id: str, user: str = "system") -> bool:
        """Acknowledge an active alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = "ACKNOWLEDGED"
            
            self._update_alert(alert)
            self._record_alert_history(alert_id, "ACKNOWLEDGED", {"user": user})
            
            self.logger.info(f"Alert {alert_id} acknowledged by {user}")
            return True
            
        return False
        
    def resolve_alert(self, alert_id: str, user: str = "system") -> bool:
        """Resolve an active alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.status = "RESOLVED"
            
            # Remove from active alerts
            del self.active_alerts[alert_id]
            
            # Update in database
            with sqlite3.connect(self.alerts_db) as conn:
                conn.execute('''
                    UPDATE alerts 
                    SET status = ?, resolved_at = ? 
                    WHERE id = ?
                ''', (alert.status, datetime.now().isoformat(), alert_id))
                
            self._record_alert_history(alert_id, "RESOLVED", {"user": user})
            
            self.logger.info(f"Alert {alert_id} resolved by {user}")
            return True
            
        return False
        
    def _update_alert(self, alert: Alert):
        """Update alert in database"""
        with sqlite3.connect(self.alerts_db) as conn:
            conn.execute('''
                UPDATE alerts 
                SET status = ?, escalation_level = ?, last_notified = ?
                WHERE id = ?
            ''', (alert.status, alert.escalation_level, alert.last_notified, alert.id))
            
    def _record_alert_history(self, alert_id: str, action: str, details: Dict):
        """Record alert history entry"""
        with sqlite3.connect(self.alerts_db) as conn:
            conn.execute('''
                INSERT INTO alert_history (alert_id, action, details)
                VALUES (?, ?, ?)
            ''', (alert_id, action, json.dumps(details)))
            
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        return list(self.active_alerts.values())
        
    def get_alert_summary(self) -> Dict:
        """Get summary of alert status"""
        active_alerts = self.get_active_alerts()
        
        summary = {
            "total_active": len(active_alerts),
            "by_severity": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
            "by_component": {},
            "oldest_alert": None,
            "newest_alert": None
        }
        
        if active_alerts:
            # Count by severity
            for alert in active_alerts:
                summary["by_severity"][alert.severity] += 1
                
                # Count by component
                if alert.component not in summary["by_component"]:
                    summary["by_component"][alert.component] = 0
                summary["by_component"][alert.component] += 1
                
            # Find oldest and newest
            sorted_alerts = sorted(active_alerts, key=lambda x: x.timestamp)
            summary["oldest_alert"] = sorted_alerts[0].timestamp if sorted_alerts else None
            summary["newest_alert"] = sorted_alerts[-1].timestamp if sorted_alerts else None
            
        return summary
        
    def cleanup_old_alerts(self, days: int = 30):
        """Clean up old resolved alerts"""
        cutoff = datetime.now() - timedelta(days=days)
        
        with sqlite3.connect(self.alerts_db) as conn:
            cursor = conn.cursor()
            
            # Delete old resolved alerts
            cursor.execute('''
                DELETE FROM alerts 
                WHERE status = 'RESOLVED' AND resolved_at < ?
            ''', (cutoff.isoformat(),))
            
            deleted_alerts = cursor.rowcount
            
            # Delete old alert history
            cursor.execute('''
                DELETE FROM alert_history 
                WHERE timestamp < ?
            ''', (cutoff.isoformat(),))
            
            deleted_history = cursor.rowcount
            
        self.logger.info(f"Cleaned up {deleted_alerts} old alerts and {deleted_history} history entries")
        
        return {"alerts_deleted": deleted_alerts, "history_deleted": deleted_history}


def main():
    """Main function for alerting system testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Veeva Alerting System')
    parser.add_argument('--test', action='store_true', help='Run test alert')
    parser.add_argument('--cleanup', type=int, help='Cleanup old alerts (days)')
    parser.add_argument('--summary', action='store_true', help='Show alert summary')
    
    args = parser.parse_args()
    
    alerting = AlertingSystem()
    
    if args.test:
        # Create test alert
        test_alert = Alert(
            id=f"TEST_{int(time.time())}",
            severity="MEDIUM",
            component="test",
            message="Test alert for system validation",
            details={"test": True},
            timestamp=datetime.now().isoformat(),
            status="ACTIVE",
            escalation_level=0,
            last_notified=None
        )
        
        alerting.process_alert(test_alert)
        print(f"Test alert created: {test_alert.id}")
        
        # Wait a bit then resolve
        time.sleep(5)
        alerting.resolve_alert(test_alert.id, "test_user")
        
    elif args.cleanup:
        result = alerting.cleanup_old_alerts(args.cleanup)
        print(f"Cleanup completed: {result}")
        
    elif args.summary:
        summary = alerting.get_alert_summary()
        print("Alert Summary:")
        print(json.dumps(summary, indent=2))
        
    else:
        print("Alerting system initialized. Use --help for options.")


if __name__ == "__main__":
    main()