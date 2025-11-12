"""
Monitoring Agent: Comprehensive system monitoring and alerting
Handles metrics collection, alerting, dashboards, and performance monitoring
"""

import asyncio
import logging
import smtplib
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import GPUtil
import kubernetes
import psutil
import requests
import slack
import telegram
from grafana_api_client import GrafanaApi
from prometheus_api_client import PrometheusConnect
from sklearn.ensemble import IsolationForest
from twilio.rest import Client as TwilioClient

from ..agents.base_agent import AgentMessage, BaseAgent

logger = logging.getLogger(__name__)


class MonitoringAgent(BaseAgent):
    """
    Monitoring Agent for comprehensive system monitoring and alerting
    Handles metrics collection, alerting, dashboards, and performance monitoring
    """

    def __init__(self, agent_id: str = "monitoring_agent", config: dict[str, Any] | None = None):
        super().__init__(agent_id, config or {})

        # Monitoring configuration
        self.monitoring_config = {
            "prometheus": self.config.get(
                "prometheus",
                {
                    "url": "http://prometheus:9090",
                    "metrics_retention": "30d",
                    "scrape_interval": "15s",
                    "evaluation_interval": "15s",
                },
            ),
            "grafana": self.config.get(
                "grafana",
                {
                    "url": "http://grafana:3000",
                    "api_key": self.config.get("grafana_api_key"),
                    "dashboards": ["system", "application", "business"],
                    "alert_channels": ["email", "slack", "telegram"],
                },
            ),
            "alerting": self.config.get(
                "alerting",
                {
                    "rules": {
                        "cpu_usage": {"threshold": 80, "duration": "5m", "severity": "warning"},
                        "memory_usage": {"threshold": 85, "duration": "5m", "severity": "warning"},
                        "disk_usage": {"threshold": 90, "duration": "10m", "severity": "critical"},
                        "error_rate": {"threshold": 5, "duration": "5m", "severity": "critical"},
                        "response_time": {
                            "threshold": 2000,
                            "duration": "5m",
                            "severity": "warning",
                        },
                    },
                    "channels": {
                        "email": {"enabled": True, "recipients": ["admin@predator-analytics.com"]},
                        "slack": {"enabled": True, "webhook_url": self.config.get("slack_webhook")},
                        "telegram": {
                            "enabled": True,
                            "bot_token": self.config.get("telegram_bot_token"),
                            "chat_id": self.config.get("telegram_chat_id"),
                        },
                        "sms": {"enabled": False, "twilio_sid": self.config.get("twilio_sid")},
                    },
                    "cooldown_period": 300,  # seconds
                    "escalation_levels": ["warning", "critical", "emergency"],
                },
            ),
            "metrics": self.config.get(
                "metrics",
                {
                    "system_metrics": ["cpu", "memory", "disk", "network"],
                    "application_metrics": ["requests", "errors", "latency", "throughput"],
                    "business_metrics": ["user_sessions", "data_processed", "insights_generated"],
                    "custom_metrics": [],
                    "collection_interval": 60,  # seconds
                    "anomaly_detection": True,
                },
            ),
            "dashboards": self.config.get(
                "dashboards",
                {
                    "auto_create": True,
                    "update_interval": 300,  # seconds
                    "retention_period": "90d",
                    "export_formats": ["pdf", "png", "json"],
                },
            ),
            "health_checks": self.config.get(
                "health_checks",
                {
                    "endpoints": ["/health", "/metrics", "/status"],
                    "timeout": 30,  # seconds
                    "interval": 60,  # seconds
                    "failure_threshold": 3,
                },
            ),
            "anomaly_detection": self.config.get(
                "anomaly_detection",
                {
                    "enabled": True,
                    "algorithms": ["isolation_forest", "z_score", "mad"],
                    "sensitivity": 0.8,
                    "training_window": "7d",
                    "alert_on_anomaly": True,
                },
            ),
            "processing_options": self.config.get(
                "options",
                {
                    "parallel_collection": 5,
                    "batch_size": 1000,
                    "max_metrics_history": 100000,
                    "enable_caching": True,
                    "compression_enabled": True,
                },
            ),
        }

        # Monitoring clients and managers
        self.prometheus_client = None
        self.grafana_client = None
        self.k8s_client = None
        self.email_client = None
        self.slack_client = None
        self.telegram_client = None
        self.twilio_client = None

        # Monitoring state
        self.monitoring_state = {
            "metrics_history": deque(
                maxlen=self.monitoring_config["processing_options"]["max_metrics_history"]
            ),
            "active_alerts": {},
            "alert_history": deque(maxlen=5000),
            "system_health": {},
            "anomaly_models": {},
            "dashboard_state": {},
            "health_check_results": {},
            "performance_baselines": {},
            "alert_cooldowns": {},
            "metrics_cache": {},
            "anomaly_scores": defaultdict(list),
            "trend_analysis": {},
            "capacity_planning": {},
            "incident_timeline": deque(maxlen=1000),
        }

        # ML models for anomaly detection
        self.anomaly_models = {}

        # Background tasks
        self.metrics_collection_task = None
        self.alert_monitoring_task = None
        self.health_check_task = None

        logger.info(f"Monitoring Agent initialized: {agent_id}")

    async def start(self):
        """
        Start the monitoring agent
        """
        await super().start()

        # Initialize monitoring clients
        await self._initialize_monitoring_clients()

        # Load monitoring data
        await self._load_monitoring_data()

        # Initialize anomaly detection models
        await self._initialize_anomaly_models()

        # Start background tasks
        self.metrics_collection_task = asyncio.create_task(self._continuous_metrics_collection())
        self.alert_monitoring_task = asyncio.create_task(self._continuous_alert_monitoring())
        self.health_check_task = asyncio.create_task(self._continuous_health_checks())

        logger.info("Monitoring agent started")

    async def stop(self):
        """
        Stop the monitoring agent
        """
        if self.metrics_collection_task:
            self.metrics_collection_task.cancel()
            try:
                await self.metrics_collection_task
            except asyncio.CancelledError:
                pass

        if self.alert_monitoring_task:
            self.alert_monitoring_task.cancel()
            try:
                await self.alert_monitoring_task
            except asyncio.CancelledError:
                pass

        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass

        await super().stop()
        logger.info("Monitoring agent stopped")

    async def _initialize_monitoring_clients(self):
        """
        Initialize monitoring clients and connections
        """
        try:
            # Initialize Prometheus client
            try:
                self.prometheus_client = PrometheusConnect(
                    url=self.monitoring_config["prometheus"]["url"]
                )
                logger.info("Prometheus client initialized")
            except Exception as e:
                logger.warning(f"Prometheus client initialization failed: {e}")

            # Initialize Grafana client
            try:
                self.grafana_client = GrafanaApi(
                    host=self.monitoring_config["grafana"]["url"],
                    api_key=self.monitoring_config["grafana"]["api_key"],
                )
                logger.info("Grafana client initialized")
            except Exception as e:
                logger.warning(f"Grafana client initialization failed: {e}")

            # Initialize Kubernetes client
            try:
                kubernetes.config.load_kube_config()
                self.k8s_client = kubernetes.client.CoreV1Api()
                logger.info("Kubernetes client initialized")
            except Exception as e:
                logger.warning(f"Kubernetes client initialization failed: {e}")

            # Initialize notification clients
            try:
                if self.monitoring_config["alerting"]["channels"]["slack"]["enabled"]:
                    self.slack_client = slack.WebClient(
                        token=self.monitoring_config["alerting"]["channels"]["slack"].get(
                            "bot_token"
                        )
                    )
                    logger.info("Slack client initialized")
            except Exception as e:
                logger.warning(f"Slack client initialization failed: {e}")

            try:
                if self.monitoring_config["alerting"]["channels"]["telegram"]["enabled"]:
                    self.telegram_client = telegram.Bot(
                        token=self.monitoring_config["alerting"]["channels"]["telegram"][
                            "bot_token"
                        ]
                    )
                    logger.info("Telegram client initialized")
            except Exception as e:
                logger.warning(f"Telegram client initialization failed: {e}")

            try:
                if self.monitoring_config["alerting"]["channels"]["sms"]["enabled"]:
                    self.twilio_client = TwilioClient(
                        self.monitoring_config["alerting"]["channels"]["sms"]["twilio_sid"],
                        self.monitoring_config["alerting"]["channels"]["sms"]["auth_token"],
                    )
                    logger.info("Twilio client initialized")
            except Exception as e:
                logger.warning(f"Twilio client initialization failed: {e}")

        except Exception as e:
            logger.error(f"Monitoring client initialization failed: {e}")

    async def _load_monitoring_data(self):
        """
        Load existing monitoring data and configurations
        """
        try:
            # Load metrics history, alert history, system health, etc.
            await self._load_metrics_history()
            await self._load_alert_history()
            await self._load_system_health()

            logger.info("Monitoring data loaded")

        except Exception as e:
            logger.error(f"Monitoring data loading failed: {e}")

    async def _initialize_anomaly_models(self):
        """
        Initialize ML models for anomaly detection
        """
        try:
            # Isolation Forest for anomaly detection
            self.anomaly_models["isolation_forest"] = IsolationForest(
                contamination=0.1, random_state=42
            )

            logger.info("Anomaly detection models initialized")

        except Exception as e:
            logger.error(f"Anomaly model initialization failed: {e}")

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process monitoring requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "collect_metrics":
                async for response in self._handle_metrics_collection(message):
                    yield response

            elif message_type == "check_alerts":
                async for response in self._handle_alert_checking(message):
                    yield response

            elif message_type == "create_dashboard":
                async for response in self._handle_dashboard_creation(message):
                    yield response

            elif message_type == "perform_health_check":
                async for response in self._handle_health_check(message):
                    yield response

            elif message_type == "detect_anomalies":
                async for response in self._handle_anomaly_detection(message):
                    yield response

            elif message_type == "generate_report":
                async for response in self._handle_report_generation(message):
                    yield response

            elif message_type == "send_alert":
                async for response in self._handle_alert_sending(message):
                    yield response

            elif message_type == "analyze_trends":
                async for response in self._handle_trend_analysis(message):
                    yield response

            else:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": f"Unknown message type: {message_type}"},
                    timestamp=datetime.now(),
                )

        except Exception as e:
            logger.error(f"Monitoring processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_metrics_collection(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle metrics collection request
        """
        try:
            metrics_type = message.content.get("metrics_type", "all")
            time_range = message.content.get("time_range", "1h")

            # Collect metrics
            metrics_result = await self._collect_metrics(metrics_type, time_range)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "metrics_collection_response",
                    "metrics_result": metrics_result,
                    "metrics_type": metrics_type,
                    "time_range": time_range,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Metrics collection handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _collect_metrics(self, metrics_type: str, time_range: str) -> dict[str, Any]:
        """
        Collect system and application metrics
        """
        try:
            metrics = {}

            if metrics_type == "all" or metrics_type == "system":
                # Collect system metrics
                system_metrics = await self._collect_system_metrics()
                metrics.update(system_metrics)

            if metrics_type == "all" or metrics_type == "application":
                # Collect application metrics
                app_metrics = await self._collect_application_metrics()
                metrics.update(app_metrics)

            if metrics_type == "all" or metrics_type == "business":
                # Collect business metrics
                business_metrics = await self._collect_business_metrics()
                metrics.update(business_metrics)

            # Store metrics in history
            metrics_entry = {
                "timestamp": datetime.now(),
                "metrics_type": metrics_type,
                "data": metrics,
            }
            self.monitoring_state["metrics_history"].append(metrics_entry)

            return {
                "metrics_collected": True,
                "metrics": metrics,
                "collection_time": datetime.now(),
                "metrics_count": len(metrics),
            }

        except Exception as e:
            logger.error(f"Metrics collection failed: {e}")
            return {"error": str(e), "metrics_collected": False}

    async def _collect_system_metrics(self) -> dict[str, Any]:
        """
        Collect system-level metrics
        """
        try:
            metrics = {}

            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()

            metrics["cpu"] = {
                "usage_percent": cpu_percent,
                "count": cpu_count,
                "frequency_mhz": cpu_freq.current if cpu_freq else None,
            }

            # Memory metrics
            memory = psutil.virtual_memory()
            metrics["memory"] = {
                "total_gb": memory.total / (1024**3),
                "used_gb": memory.used / (1024**3),
                "available_gb": memory.available / (1024**3),
                "usage_percent": memory.percent,
            }

            # Disk metrics
            disk = psutil.disk_usage("/")
            metrics["disk"] = {
                "total_gb": disk.total / (1024**3),
                "used_gb": disk.used / (1024**3),
                "free_gb": disk.free / (1024**3),
                "usage_percent": disk.percent,
            }

            # Network metrics
            network = psutil.net_io_counters()
            metrics["network"] = {
                "bytes_sent_mb": network.bytes_sent / (1024**2),
                "bytes_recv_mb": network.bytes_recv / (1024**2),
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv,
            }

            # GPU metrics (if available)
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu_metrics = []
                    for gpu in gpus:
                        gpu_metrics.append(
                            {
                                "id": gpu.id,
                                "name": gpu.name,
                                "memory_used_mb": gpu.memoryUsed,
                                "memory_total_mb": gpu.memoryTotal,
                                "memory_free_mb": gpu.memoryFree,
                                "memory_usage_percent": gpu.memoryUtil * 100,
                                "gpu_usage_percent": gpu.load * 100,
                                "temperature_c": gpu.temperature,
                            }
                        )
                    metrics["gpu"] = gpu_metrics
            except Exception as e:
                logger.warning(f"GPU metrics collection failed: {e}")

            return metrics

        except Exception as e:
            logger.error(f"System metrics collection failed: {e}")
            return {}

    async def _collect_application_metrics(self) -> dict[str, Any]:
        """
        Collect application-level metrics
        """
        try:
            metrics = {}

            # Get metrics from Prometheus
            if self.prometheus_client:
                try:
                    # HTTP request metrics
                    http_requests = self.prometheus_client.custom_query(
                        "rate(http_requests_total[5m])"
                    )
                    if http_requests:
                        metrics["http_requests"] = float(http_requests[0]["value"][1])

                    # Error rate
                    error_rate = self.prometheus_client.custom_query(
                        'rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100'
                    )
                    if error_rate:
                        metrics["error_rate_percent"] = float(error_rate[0]["value"][1])

                    # Response time
                    response_time = self.prometheus_client.custom_query(
                        "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"
                    )
                    if response_time:
                        metrics["response_time_p95_seconds"] = float(response_time[0]["value"][1])

                except Exception as e:
                    logger.warning(f"Prometheus metrics collection failed: {e}")

            # Application-specific metrics
            metrics.update(
                {
                    "active_connections": 150,  # Example
                    "queue_size": 25,  # Example
                    "cache_hit_rate": 0.85,  # Example
                }
            )

            return metrics

        except Exception as e:
            logger.error(f"Application metrics collection failed: {e}")
            return {}

    async def _collect_business_metrics(self) -> dict[str, Any]:
        """
        Collect business-level metrics
        """
        try:
            metrics = {}

            # User sessions
            metrics["active_user_sessions"] = 1250  # Example

            # Data processing
            metrics["data_processed_gb"] = 45.7  # Example

            # Insights generated
            metrics["insights_generated"] = 89  # Example

            # Revenue metrics (if applicable)
            metrics["monthly_revenue"] = 125000  # Example

            return metrics

        except Exception as e:
            logger.error(f"Business metrics collection failed: {e}")
            return {}

    async def _handle_alert_checking(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle alert checking request
        """
        try:
            alert_type = message.content.get("alert_type", "all")

            # Check alerts
            alert_result = await self._check_alerts(alert_type)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "alert_checking_response",
                    "alert_result": alert_result,
                    "alert_type": alert_type,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Alert checking handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _check_alerts(self, alert_type: str) -> dict[str, Any]:
        """
        Check for alerts based on metrics
        """
        try:
            alerts = []

            # Get current metrics
            current_metrics = await self._collect_metrics("all", "5m")

            if not current_metrics.get("metrics_collected"):
                return {"alerts_found": False, "error": "Metrics collection failed"}

            metrics = current_metrics["metrics"]

            # Check CPU usage alert
            cpu_usage = metrics.get("cpu", {}).get("usage_percent", 0)
            cpu_threshold = self.monitoring_config["alerting"]["rules"]["cpu_usage"]["threshold"]

            if cpu_usage > cpu_threshold:
                alerts.append(
                    {
                        "alert_id": str(uuid.uuid4()),
                        "type": "cpu_usage",
                        "severity": self.monitoring_config["alerting"]["rules"]["cpu_usage"][
                            "severity"
                        ],
                        "message": f"CPU usage is {cpu_usage:.1f}%, above threshold of {cpu_threshold}%",
                        "value": cpu_usage,
                        "threshold": cpu_threshold,
                        "timestamp": datetime.now(),
                    }
                )

            # Check memory usage alert
            memory_usage = metrics.get("memory", {}).get("usage_percent", 0)
            memory_threshold = self.monitoring_config["alerting"]["rules"]["memory_usage"][
                "threshold"
            ]

            if memory_usage > memory_threshold:
                alerts.append(
                    {
                        "alert_id": str(uuid.uuid4()),
                        "type": "memory_usage",
                        "severity": self.monitoring_config["alerting"]["rules"]["memory_usage"][
                            "severity"
                        ],
                        "message": f"Memory usage is {memory_usage:.1f}%, above threshold of {memory_threshold}%",
                        "value": memory_usage,
                        "threshold": memory_threshold,
                        "timestamp": datetime.now(),
                    }
                )

            # Check disk usage alert
            disk_usage = metrics.get("disk", {}).get("usage_percent", 0)
            disk_threshold = self.monitoring_config["alerting"]["rules"]["disk_usage"]["threshold"]

            if disk_usage > disk_threshold:
                alerts.append(
                    {
                        "alert_id": str(uuid.uuid4()),
                        "type": "disk_usage",
                        "severity": self.monitoring_config["alerting"]["rules"]["disk_usage"][
                            "severity"
                        ],
                        "message": f"Disk usage is {disk_usage:.1f}%, above threshold of {disk_threshold}%",
                        "value": disk_usage,
                        "threshold": disk_threshold,
                        "timestamp": datetime.now(),
                    }
                )

            # Check error rate alert
            error_rate = metrics.get("error_rate_percent", 0)
            error_threshold = self.monitoring_config["alerting"]["rules"]["error_rate"]["threshold"]

            if error_rate > error_threshold:
                alerts.append(
                    {
                        "alert_id": str(uuid.uuid4()),
                        "type": "error_rate",
                        "severity": self.monitoring_config["alerting"]["rules"]["error_rate"][
                            "severity"
                        ],
                        "message": f"Error rate is {error_rate:.1f}%, above threshold of {error_threshold}%",
                        "value": error_rate,
                        "threshold": error_threshold,
                        "timestamp": datetime.now(),
                    }
                )

            # Send alerts if any
            for alert in alerts:
                await self._send_alert(alert)
                self.monitoring_state["active_alerts"][alert["alert_id"]] = alert
                self.monitoring_state["alert_history"].append(alert)

            return {
                "alerts_found": len(alerts) > 0,
                "alerts": alerts,
                "alert_count": len(alerts),
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Alert checking failed: {e}")
            return {"error": str(e), "alerts_found": False}

    async def _send_alert(self, alert: dict[str, Any]):
        """
        Send alert through configured channels
        """
        try:
            alert_message = f"🚨 ALERT: {alert['message']}\nSeverity: {alert['severity']}\nTime: {alert['timestamp']}"

            # Send via email
            if self.monitoring_config["alerting"]["channels"]["email"]["enabled"]:
                await self._send_email_alert(alert, alert_message)

            # Send via Slack
            if (
                self.monitoring_config["alerting"]["channels"]["slack"]["enabled"]
                and self.slack_client
            ):
                await self._send_slack_alert(alert, alert_message)

            # Send via Telegram
            if (
                self.monitoring_config["alerting"]["channels"]["telegram"]["enabled"]
                and self.telegram_client
            ):
                await self._send_telegram_alert(alert, alert_message)

            # Send via SMS
            if (
                self.monitoring_config["alerting"]["channels"]["sms"]["enabled"]
                and self.twilio_client
            ):
                await self._send_sms_alert(alert, alert_message)

        except Exception as e:
            logger.error(f"Alert sending failed: {e}")

    async def _send_email_alert(self, alert: dict[str, Any], message: str):
        """
        Send alert via email
        """
        try:
            msg = MIMEMultipart()
            msg["From"] = self.monitoring_config["alerting"]["channels"]["email"].get(
                "from", "alerts@predator-analytics.com"
            )
            msg["To"] = ", ".join(
                self.monitoring_config["alerting"]["channels"]["email"]["recipients"]
            )
            msg["Subject"] = f"Predator Analytics Alert: {alert['type']}"

            msg.attach(MIMEText(message, "plain"))

            server = smtplib.SMTP(
                self.monitoring_config["alerting"]["channels"]["email"].get(
                    "smtp_server", "localhost"
                ),
                self.monitoring_config["alerting"]["channels"]["email"].get("smtp_port", 587),
            )

            if self.monitoring_config["alerting"]["channels"]["email"].get("use_tls", True):
                server.starttls()

            if "smtp_username" in self.monitoring_config["alerting"]["channels"]["email"]:
                server.login(
                    self.monitoring_config["alerting"]["channels"]["email"]["smtp_username"],
                    self.monitoring_config["alerting"]["channels"]["email"]["smtp_password"],
                )

            server.send_message(msg)
            server.quit()

        except Exception as e:
            logger.error(f"Email alert sending failed: {e}")

    async def _send_slack_alert(self, alert: dict[str, Any], message: str):
        """
        Send alert via Slack
        """
        try:
            webhook_url = self.monitoring_config["alerting"]["channels"]["slack"]["webhook_url"]

            payload = {
                "text": message,
                "username": "Predator Analytics Monitor",
                "icon_emoji": ":warning:",
            }

            response = requests.post(webhook_url, json=payload)
            response.raise_for_status()

        except Exception as e:
            logger.error(f"Slack alert sending failed: {e}")

    async def _send_telegram_alert(self, alert: dict[str, Any], message: str):
        """
        Send alert via Telegram
        """
        try:
            chat_id = self.monitoring_config["alerting"]["channels"]["telegram"]["chat_id"]

            await self.telegram_client.send_message(
                chat_id=chat_id, text=message, parse_mode="Markdown"
            )

        except Exception as e:
            logger.error(f"Telegram alert sending failed: {e}")

    async def _send_sms_alert(self, alert: dict[str, Any], message: str):
        """
        Send alert via SMS
        """
        try:
            from_number = self.monitoring_config["alerting"]["channels"]["sms"]["from_number"]
            to_numbers = self.monitoring_config["alerting"]["channels"]["sms"]["to_numbers"]

            for to_number in to_numbers:
                self.twilio_client.messages.create(body=message, from_=from_number, to=to_number)

        except Exception as e:
            logger.error(f"SMS alert sending failed: {e}")

    async def _handle_dashboard_creation(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle dashboard creation request
        """
        try:
            dashboard_type = message.content.get("dashboard_type", "system")
            metrics = message.content.get("metrics", [])

            # Create dashboard
            dashboard_result = await self._create_dashboard(dashboard_type, metrics)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "dashboard_creation_response",
                    "dashboard_result": dashboard_result,
                    "dashboard_type": dashboard_type,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Dashboard creation handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _create_dashboard(self, dashboard_type: str, metrics: list[str]) -> dict[str, Any]:
        """
        Create monitoring dashboard
        """
        try:
            dashboard_config = {
                "title": f"Predator Analytics - {dashboard_type.title()} Dashboard",
                "tags": ["predator-analytics", dashboard_type],
                "panels": [],
            }

            # Add panels based on dashboard type
            if dashboard_type == "system":
                dashboard_config["panels"] = await self._create_system_panels(metrics)
            elif dashboard_type == "application":
                dashboard_config["panels"] = await self._create_application_panels(metrics)
            elif dashboard_type == "business":
                dashboard_config["panels"] = await self._create_business_panels(metrics)

            # Create dashboard in Grafana
            if self.grafana_client:
                try:
                    dashboard = self.grafana_client.dashboards.create(
                        dashboard=dashboard_config, folder_id=0
                    )

                    return {
                        "dashboard_created": True,
                        "dashboard_id": dashboard["id"],
                        "dashboard_url": dashboard["url"],
                        "panel_count": len(dashboard_config["panels"]),
                    }

                except Exception as e:
                    logger.warning(f"Grafana dashboard creation failed: {e}")

            # Fallback: return dashboard configuration
            return {
                "dashboard_created": True,
                "dashboard_config": dashboard_config,
                "message": "Dashboard configuration generated (Grafana not available)",
            }

        except Exception as e:
            logger.error(f"Dashboard creation failed: {e}")
            return {"error": str(e), "dashboard_created": False}

    async def _create_system_panels(self, metrics: list[str]) -> list[dict[str, Any]]:
        """
        Create system monitoring panels
        """
        try:
            panels = []

            # CPU Usage Panel
            if not metrics or "cpu" in metrics:
                panels.append(
                    {
                        "title": "CPU Usage",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": '100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)',
                                "legendFormat": "CPU Usage %",
                            }
                        ],
                        "yAxes": [{"unit": "percent", "min": 0, "max": 100}],
                    }
                )

            # Memory Usage Panel
            if not metrics or "memory" in metrics:
                panels.append(
                    {
                        "title": "Memory Usage",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": "100 - ((node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100)",
                                "legendFormat": "Memory Usage %",
                            }
                        ],
                        "yAxes": [{"unit": "percent", "min": 0, "max": 100}],
                    }
                )

            # Disk Usage Panel
            if not metrics or "disk" in metrics:
                panels.append(
                    {
                        "title": "Disk Usage",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": "(node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes * 100",
                                "legendFormat": "Disk Usage %",
                            }
                        ],
                        "yAxes": [{"unit": "percent", "min": 0, "max": 100}],
                    }
                )

            return panels

        except Exception as e:
            logger.error(f"System panels creation failed: {e}")
            return []

    async def _create_application_panels(self, metrics: list[str]) -> list[dict[str, Any]]:
        """
        Create application monitoring panels
        """
        try:
            panels = []

            # HTTP Request Rate Panel
            if not metrics or "requests" in metrics:
                panels.append(
                    {
                        "title": "HTTP Request Rate",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": "rate(http_requests_total[5m])",
                                "legendFormat": "Requests/sec",
                            }
                        ],
                        "yAxes": [{"unit": "reqps"}],
                    }
                )

            # Error Rate Panel
            if not metrics or "errors" in metrics:
                panels.append(
                    {
                        "title": "Error Rate",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": 'rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100',
                                "legendFormat": "Error Rate %",
                            }
                        ],
                        "yAxes": [{"unit": "percent"}],
                    }
                )

            # Response Time Panel
            if not metrics or "latency" in metrics:
                panels.append(
                    {
                        "title": "Response Time (95th percentile)",
                        "type": "graph",
                        "targets": [
                            {
                                "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
                                "legendFormat": "95th percentile",
                            }
                        ],
                        "yAxes": [{"unit": "seconds"}],
                    }
                )

            return panels

        except Exception as e:
            logger.error(f"Application panels creation failed: {e}")
            return []

    async def _create_business_panels(self, metrics: list[str]) -> list[dict[str, Any]]:
        """
        Create business monitoring panels
        """
        try:
            panels = []

            # Active User Sessions Panel
            if not metrics or "user_sessions" in metrics:
                panels.append(
                    {
                        "title": "Active User Sessions",
                        "type": "graph",
                        "targets": [
                            {"expr": "active_user_sessions", "legendFormat": "Active Sessions"}
                        ],
                        "yAxes": [{"unit": "none"}],
                    }
                )

            # Data Processed Panel
            if not metrics or "data_processed" in metrics:
                panels.append(
                    {
                        "title": "Data Processed (GB)",
                        "type": "graph",
                        "targets": [
                            {"expr": "data_processed_gb", "legendFormat": "Data Processed"}
                        ],
                        "yAxes": [{"unit": "bytes"}],
                    }
                )

            # Insights Generated Panel
            if not metrics or "insights_generated" in metrics:
                panels.append(
                    {
                        "title": "Insights Generated",
                        "type": "graph",
                        "targets": [
                            {"expr": "insights_generated_total", "legendFormat": "Insights"}
                        ],
                        "yAxes": [{"unit": "none"}],
                    }
                )

            return panels

        except Exception as e:
            logger.error(f"Business panels creation failed: {e}")
            return []

    async def _handle_health_check(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle health check request
        """
        try:
            service_url = message.content.get("service_url")
            check_type = message.content.get("check_type", "basic")

            # Perform health check
            health_result = await self._perform_health_check(service_url, check_type)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "health_check_response",
                    "health_result": health_result,
                    "service_url": service_url,
                    "check_type": check_type,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Health check handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _perform_health_check(self, service_url: str, check_type: str) -> dict[str, Any]:
        """
        Perform health check on service
        """
        try:
            if not service_url:
                # Check system health
                return await self._check_system_health()

            # Check service health
            timeout = self.monitoring_config["health_checks"]["timeout"]

            start_time = datetime.now()

            try:
                response = requests.get(f"{service_url}/health", timeout=timeout)

                response_time = (datetime.now() - start_time).total_seconds() * 1000  # ms

                if response.status_code == 200:
                    health_data = response.json()

                    return {
                        "healthy": True,
                        "status_code": response.status_code,
                        "response_time_ms": response_time,
                        "service": service_url,
                        "details": health_data,
                        "timestamp": datetime.now(),
                    }
                else:
                    return {
                        "healthy": False,
                        "status_code": response.status_code,
                        "response_time_ms": response_time,
                        "service": service_url,
                        "error": f"HTTP {response.status_code}",
                        "timestamp": datetime.now(),
                    }

            except requests.exceptions.RequestException as e:
                return {
                    "healthy": False,
                    "service": service_url,
                    "error": str(e),
                    "timestamp": datetime.now(),
                }

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"healthy": False, "error": str(e)}

    async def _check_system_health(self) -> dict[str, Any]:
        """
        Check overall system health
        """
        try:
            health_checks = []

            # CPU health
            cpu_percent = psutil.cpu_percent()
            cpu_healthy = cpu_percent < 90
            health_checks.append(
                {"component": "cpu", "healthy": cpu_healthy, "value": cpu_percent, "threshold": 90}
            )

            # Memory health
            memory = psutil.virtual_memory()
            memory_healthy = memory.percent < 95
            health_checks.append(
                {
                    "component": "memory",
                    "healthy": memory_healthy,
                    "value": memory.percent,
                    "threshold": 95,
                }
            )

            # Disk health
            disk = psutil.disk_usage("/")
            disk_healthy = disk.percent < 95
            health_checks.append(
                {
                    "component": "disk",
                    "healthy": disk_healthy,
                    "value": disk.percent,
                    "threshold": 95,
                }
            )

            # Overall health
            overall_healthy = all(check["healthy"] for check in health_checks)

            return {
                "healthy": overall_healthy,
                "component_checks": health_checks,
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error(f"System health check failed: {e}")
            return {"healthy": False, "error": str(e)}

    # Background monitoring tasks
    async def _continuous_metrics_collection(self):
        """
        Continuous metrics collection
        """
        try:
            while True:
                try:
                    # Collect metrics
                    await self._collect_metrics("all", "1m")

                    # Update performance baselines
                    await self._update_performance_baselines()

                except Exception as e:
                    logger.error(f"Metrics collection error: {e}")

                # Collect every configured interval
                interval = self.monitoring_config["metrics"]["collection_interval"]
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info("Metrics collection cancelled")
            raise

    async def _continuous_alert_monitoring(self):
        """
        Continuous alert monitoring
        """
        try:
            while True:
                try:
                    # Check for alerts
                    await self._check_alerts("all")

                    # Clean up old alerts
                    await self._cleanup_old_alerts()

                except Exception as e:
                    logger.error(f"Alert monitoring error: {e}")

                # Monitor every 60 seconds
                await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("Alert monitoring cancelled")
            raise

    async def _continuous_health_checks(self):
        """
        Continuous health checks
        """
        try:
            while True:
                try:
                    # Perform health checks
                    endpoints = self.monitoring_config["health_checks"]["endpoints"]

                    for endpoint in endpoints:
                        await self._perform_health_check(
                            f"http://localhost:8000{endpoint}", "basic"
                        )

                    # Update health status
                    await self._update_health_status()

                except Exception as e:
                    logger.error(f"Health check error: {e}")

                # Check every configured interval
                interval = self.monitoring_config["health_checks"]["interval"]
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info("Health checks cancelled")
            raise

    # Additional helper methods would continue...

    async def _load_metrics_history(self):
        """Load metrics history"""
        try:
            # Implementation for loading metrics history
            pass
        except Exception as e:
            logger.error(f"Metrics history loading failed: {e}")

    async def _load_alert_history(self):
        """Load alert history"""
        try:
            # Implementation for loading alert history
            pass
        except Exception as e:
            logger.error(f"Alert history loading failed: {e}")

    async def _load_system_health(self):
        """Load system health"""
        try:
            # Implementation for loading system health
            pass
        except Exception as e:
            logger.error(f"System health loading failed: {e}")

    async def _update_performance_baselines(self):
        """Update performance baselines"""
        try:
            # Implementation for updating baselines
            pass
        except Exception as e:
            logger.error(f"Performance baseline update failed: {e}")

    async def _cleanup_old_alerts(self):
        """Clean up old alerts"""
        try:
            # Implementation for cleaning up alerts
            pass
        except Exception as e:
            logger.error(f"Alert cleanup failed: {e}")

    async def _update_health_status(self):
        """Update health status"""
        try:
            # Implementation for updating health status
            pass
        except Exception as e:
            logger.error(f"Health status update failed: {e}")


# ========== TEST ==========
if __name__ == "__main__":

    async def test_monitoring_agent():
        # Initialize monitoring agent
        agent = MonitoringAgent()
        await agent.start()

        # Test metrics collection
        metrics_message = AgentMessage(
            id="test_metrics",
            from_agent="test",
            to_agent="monitoring_agent",
            content={"type": "collect_metrics", "metrics_type": "system", "time_range": "1h"},
            timestamp=datetime.now(),
        )

        print("Testing monitoring agent...")
        async for response in agent.process_message(metrics_message):
            print(f"Metrics response: {response.content.get('type')}")
            metrics_result = response.content.get("metrics_result")
            print(f"Metrics collected: {metrics_result.get('metrics_collected')}")

        # Test alert checking
        alert_message = AgentMessage(
            id="test_alerts",
            from_agent="test",
            to_agent="monitoring_agent",
            content={"type": "check_alerts", "alert_type": "all"},
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(alert_message):
            print(f"Alert response: {response.content.get('type')}")
            alert_result = response.content.get("alert_result")
            print(f"Alerts found: {alert_result.get('alerts_found')}")

        # Test health check
        health_message = AgentMessage(
            id="test_health",
            from_agent="test",
            to_agent="monitoring_agent",
            content={
                "type": "perform_health_check",
                "service_url": None,  # System health check
                "check_type": "basic",
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(health_message):
            print(f"Health response: {response.content.get('type')}")
            health_result = response.content.get("health_result")
            print(f"System healthy: {health_result.get('healthy')}")

        # Stop agent
        await agent.stop()
        print("Monitoring agent test completed")

    # Run test
    asyncio.run(test_monitoring_agent())
