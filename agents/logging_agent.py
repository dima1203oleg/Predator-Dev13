"""
Logging Agent: Comprehensive logging and log analysis
Handles log collection, analysis, correlation, and alerting
"""

import asyncio
import logging
import logging.handlers
import os
import re
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any

import nltk
import numpy as np
import spacy
from elasticsearch import Elasticsearch, helpers
from nltk.sentiment import SentimentIntensityAnalyzer
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from textblob import TextBlob
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..agents.base_agent import AgentMessage, BaseAgent

logger = logging.getLogger(__name__)


class LoggingAgent(BaseAgent):
    """
    Logging Agent for comprehensive log collection, analysis, and alerting
    Handles log aggregation, pattern recognition, anomaly detection, and correlation
    """

    def __init__(self, agent_id: str = "logging_agent", config: dict[str, Any] | None = None):
        super().__init__(agent_id, config or {})

        # Logging configuration
        self.logging_config = {
            "sources": self.config.get(
                "sources",
                {
                    "files": [
                        "/var/log/application.log",
                        "/var/log/system.log",
                        "/var/log/error.log",
                    ],
                    "databases": ["postgresql", "redis"],
                    "applications": ["fastapi", "celery", "mas_agents"],
                    "kubernetes": {
                        "enabled": True,
                        "namespaces": ["default", "predator-analytics"],
                    },
                    "cloud_services": ["aws", "azure", "gcp"],
                },
            ),
            "elasticsearch": self.config.get(
                "elasticsearch",
                {
                    "hosts": ["localhost:9200"],
                    "index_pattern": "logs-{date}",
                    "retention_days": 90,
                    "shards": 3,
                    "replicas": 1,
                },
            ),
            "analysis": self.config.get(
                "analysis",
                {
                    "pattern_recognition": True,
                    "anomaly_detection": True,
                    "sentiment_analysis": True,
                    "correlation_analysis": True,
                    "root_cause_analysis": True,
                    "batch_size": 1000,
                    "analysis_interval": 300,  # seconds
                },
            ),
            "alerting": self.config.get(
                "alerting",
                {
                    "error_patterns": [r"ERROR", r"CRITICAL", r"Exception", r"Traceback"],
                    "warning_patterns": [r"WARNING", r"WARN"],
                    "info_patterns": [r"INFO"],
                    "custom_patterns": [],
                    "alert_thresholds": {
                        "error_rate": 10,  # errors per minute
                        "warning_rate": 50,
                        "unusual_pattern_rate": 5,
                    },
                    "cooldown_period": 300,  # seconds
                },
            ),
            "processing": self.config.get(
                "processing",
                {
                    "parallel_workers": 4,
                    "queue_size": 10000,
                    "compression": True,
                    "encryption": False,
                    "batch_processing": True,
                    "real_time_processing": True,
                },
            ),
            "retention": self.config.get(
                "retention",
                {
                    "hot_storage_days": 7,
                    "warm_storage_days": 30,
                    "cold_storage_days": 90,
                    "delete_after_days": 365,
                },
            ),
            "visualization": self.config.get(
                "visualization",
                {
                    "dashboard_enabled": True,
                    "charts": ["error_trends", "log_volume", "top_errors", "anomaly_patterns"],
                    "export_formats": ["pdf", "png", "csv"],
                    "real_time_updates": True,
                },
            ),
        }

        # Logging components
        self.es_client = None
        self.log_queue = asyncio.Queue(maxsize=self.logging_config["processing"]["queue_size"])
        self.analysis_queue = asyncio.Queue(maxsize=1000)
        self.executor = ThreadPoolExecutor(
            max_workers=self.logging_config["processing"]["parallel_workers"]
        )

        # Logging state
        self.logging_state = {
            "log_collectors": {},
            "active_patterns": set(),
            "error_patterns": defaultdict(int),
            "log_statistics": {},
            "anomaly_scores": defaultdict(list),
            "correlation_matrix": {},
            "alert_history": deque(maxlen=5000),
            "analysis_results": {},
            "file_watchers": {},
            "processing_stats": {
                "logs_processed": 0,
                "errors_detected": 0,
                "patterns_found": 0,
                "alerts_sent": 0,
            },
        }

        # ML models for log analysis
        self.vectorizer = TfidfVectorizer(max_features=1000, stop_words="english")
        self.cluster_model = DBSCAN(eps=0.5, min_samples=5)
        self.scaler = StandardScaler()

        # NLP components
        self.nlp = None
        self.sentiment_analyzer = None

        # Background tasks
        self.log_collection_task = None
        self.log_analysis_task = None
        self.log_monitoring_task = None

        logger.info(f"Logging Agent initialized: {agent_id}")

    async def start(self):
        """
        Start the logging agent
        """
        await super().start()

        # Initialize Elasticsearch client
        await self._initialize_elasticsearch()

        # Initialize NLP components
        await self._initialize_nlp()

        # Load logging data
        await self._load_logging_data()

        # Start log collectors
        await self._start_log_collectors()

        # Start background tasks
        self.log_collection_task = asyncio.create_task(self._continuous_log_collection())
        self.log_analysis_task = asyncio.create_task(self._continuous_log_analysis())
        self.log_monitoring_task = asyncio.create_task(self._continuous_log_monitoring())

        logger.info("Logging agent started")

    async def stop(self):
        """
        Stop the logging agent
        """
        if self.log_collection_task:
            self.log_collection_task.cancel()
            try:
                await self.log_collection_task
            except asyncio.CancelledError:
                pass

        if self.log_analysis_task:
            self.log_analysis_task.cancel()
            try:
                await self.log_analysis_task
            except asyncio.CancelledError:
                pass

        if self.log_monitoring_task:
            self.log_monitoring_task.cancel()
            try:
                await self.log_monitoring_task
            except asyncio.CancelledError:
                pass

        # Stop file watchers
        for watcher in self.logging_state["file_watchers"].values():
            watcher.stop()

        # Shutdown executor
        self.executor.shutdown(wait=True)

        await super().stop()
        logger.info("Logging agent stopped")

    async def _initialize_elasticsearch(self):
        """
        Initialize Elasticsearch client
        """
        try:
            self.es_client = Elasticsearch(hosts=self.logging_config["elasticsearch"]["hosts"])

            # Create index template if it doesn't exist
            await self._create_index_template()

            logger.info("Elasticsearch client initialized")

        except Exception as e:
            logger.warning(f"Elasticsearch initialization failed: {e}")

    async def _initialize_nlp(self):
        """
        Initialize NLP components
        """
        try:
            # Download required NLTK data
            nltk.download("vader_lexicon", quiet=True)
            nltk.download("punkt", quiet=True)
            nltk.download("stopwords", quiet=True)

            # Initialize spaCy
            self.nlp = spacy.load("en_core_web_sm")

            # Initialize sentiment analyzer
            self.sentiment_analyzer = SentimentIntensityAnalyzer()

            logger.info("NLP components initialized")

        except Exception as e:
            logger.warning(f"NLP initialization failed: {e}")

    async def _create_index_template(self):
        """
        Create Elasticsearch index template for logs
        """
        try:
            template = {
                "index_patterns": ["logs-*"],
                "settings": {
                    "number_of_shards": self.logging_config["elasticsearch"]["shards"],
                    "number_of_replicas": self.logging_config["elasticsearch"]["replicas"],
                    "index.lifecycle.name": "logs_lifecycle",
                },
                "mappings": {
                    "properties": {
                        "timestamp": {"type": "date"},
                        "level": {"type": "keyword"},
                        "message": {"type": "text", "analyzer": "standard"},
                        "source": {"type": "keyword"},
                        "component": {"type": "keyword"},
                        "error_type": {"type": "keyword"},
                        "stack_trace": {"type": "text"},
                        "user_id": {"type": "keyword"},
                        "session_id": {"type": "keyword"},
                        "request_id": {"type": "keyword"},
                        "ip_address": {"type": "ip"},
                        "user_agent": {"type": "text"},
                        "response_time": {"type": "float"},
                        "status_code": {"type": "integer"},
                        "anomaly_score": {"type": "float"},
                        "sentiment_score": {"type": "float"},
                        "pattern_id": {"type": "keyword"},
                        "correlation_id": {"type": "keyword"},
                    }
                },
            }

            if self.es_client:
                self.es_client.indices.put_template(name="logs_template", body=template)

        except Exception as e:
            logger.error(f"Index template creation failed: {e}")

    async def _load_logging_data(self):
        """
        Load existing logging data and configurations
        """
        try:
            # Load log patterns, alert history, analysis results, etc.
            await self._load_log_patterns()
            await self._load_alert_history()
            await self._load_analysis_results()

            logger.info("Logging data loaded")

        except Exception as e:
            logger.error(f"Logging data loading failed: {e}")

    async def _start_log_collectors(self):
        """
        Start log collectors for different sources
        """
        try:
            # Start file log collectors
            for file_path in self.logging_config["sources"]["files"]:
                await self._start_file_collector(file_path)

            # Start database log collectors
            for db in self.logging_config["sources"]["databases"]:
                await self._start_database_collector(db)

            # Start application log collectors
            for app in self.logging_config["sources"]["applications"]:
                await self._start_application_collector(app)

            # Start Kubernetes log collectors
            if self.logging_config["sources"]["kubernetes"]["enabled"]:
                await self._start_kubernetes_collector()

            logger.info("Log collectors started")

        except Exception as e:
            logger.error(f"Log collectors startup failed: {e}")

    async def _start_file_collector(self, file_path: str):
        """
        Start file-based log collector
        """
        try:
            if not os.path.exists(file_path):
                logger.warning(f"Log file does not exist: {file_path}")
                return

            # Create file watcher
            event_handler = LogFileHandler(self.log_queue, file_path)
            observer = Observer()
            observer.schedule(event_handler, path=os.path.dirname(file_path), recursive=False)
            observer.start()

            self.logging_state["file_watchers"][file_path] = observer

            # Read existing logs
            await self._read_existing_logs(file_path)

            logger.info(f"File collector started for: {file_path}")

        except Exception as e:
            logger.error(f"File collector startup failed for {file_path}: {e}")

    async def _read_existing_logs(self, file_path: str):
        """
        Read existing logs from file
        """
        try:
            loop = asyncio.get_event_loop()

            def read_file():
                with open(file_path, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        log_entry = self._parse_log_line(line.strip(), file_path)
                        if log_entry:
                            self.log_queue.put_nowait(log_entry)

            await loop.run_in_executor(self.executor, read_file)

        except Exception as e:
            logger.error(f"Reading existing logs failed for {file_path}: {e}")

    async def _start_database_collector(self, db_name: str):
        """
        Start database log collector
        """
        try:
            # Implementation for database log collection
            # This would connect to database and stream logs
            logger.info(f"Database collector started for: {db_name}")

        except Exception as e:
            logger.error(f"Database collector startup failed for {db_name}: {e}")

    async def _start_application_collector(self, app_name: str):
        """
        Start application log collector
        """
        try:
            # Implementation for application log collection
            # This would integrate with application logging frameworks
            logger.info(f"Application collector started for: {app_name}")

        except Exception as e:
            logger.error(f"Application collector startup failed for {app_name}: {e}")

    async def _start_kubernetes_collector(self):
        """
        Start Kubernetes log collector
        """
        try:
            # Implementation for Kubernetes log collection
            # This would use Kubernetes API to collect pod logs
            logger.info("Kubernetes collector started")

        except Exception as e:
            logger.error(f"Kubernetes collector startup failed: {e}")

    def _parse_log_line(self, line: str, source: str) -> dict[str, Any] | None:
        """
        Parse a single log line
        """
        try:
            if not line.strip():
                return None

            # Common log patterns
            patterns = [
                # Python logging format
                r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (\w+) - (.+)",
                # ISO timestamp format
                r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})) (\w+) (.+)",
                # Simple format
                r"(\w+) (.+)",
            ]

            parsed = None
            for pattern in patterns:
                match = re.match(pattern, line)
                if match:
                    if len(match.groups()) == 3:
                        timestamp_str, level, message = match.groups()
                        timestamp = self._parse_timestamp(timestamp_str)
                        parsed = {
                            "timestamp": timestamp,
                            "level": level.upper(),
                            "message": message,
                            "source": source,
                            "raw_line": line,
                        }
                    elif len(match.groups()) == 2:
                        level, message = match.groups()
                        parsed = {
                            "timestamp": datetime.now(),
                            "level": level.upper(),
                            "message": message,
                            "source": source,
                            "raw_line": line,
                        }
                    break

            if not parsed:
                # Fallback parsing
                parsed = {
                    "timestamp": datetime.now(),
                    "level": "UNKNOWN",
                    "message": line,
                    "source": source,
                    "raw_line": line,
                }

            # Extract additional fields
            parsed.update(self._extract_log_fields(parsed["message"]))

            return parsed

        except Exception as e:
            logger.error(f"Log line parsing failed: {e}")
            return None

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """
        Parse timestamp string
        """
        try:
            # Try different timestamp formats
            formats = [
                "%Y-%m-%d %H:%M:%S,%f",
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%d %H:%M:%S",
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(timestamp_str, fmt)
                except ValueError:
                    continue

            # Fallback to current time
            return datetime.now()

        except Exception:
            return datetime.now()

    def _extract_log_fields(self, message: str) -> dict[str, Any]:
        """
        Extract additional fields from log message
        """
        try:
            fields = {}

            # Extract error type
            if "Exception" in message or "Traceback" in message:
                fields["error_type"] = "exception"
            elif "ERROR" in message:
                fields["error_type"] = "error"
            elif "WARNING" in message or "WARN" in message:
                fields["error_type"] = "warning"

            # Extract stack trace
            if "Traceback" in message:
                # Extract stack trace lines
                lines = message.split("\n")
                stack_trace = []
                in_trace = False
                for line in lines:
                    if "Traceback" in line:
                        in_trace = True
                    if in_trace and (
                        line.strip().startswith("File") or line.strip().startswith("  ")
                    ):
                        stack_trace.append(line)
                    elif in_trace and line.strip() and not line.strip().startswith(" "):
                        break
                if stack_trace:
                    fields["stack_trace"] = "\n".join(stack_trace)

            # Extract user/session/request IDs
            id_patterns = {
                "user_id": r"user[_-]id[:=]\s*([^\s,]+)",
                "session_id": r"session[_-]id[:=]\s*([^\s,]+)",
                "request_id": r"request[_-]id[:=]\s*([^\s,]+)",
            }

            for field_name, pattern in id_patterns.items():
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    fields[field_name] = match.group(1)

            # Extract IP address
            ip_pattern = r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"
            match = re.search(ip_pattern, message)
            if match:
                fields["ip_address"] = match.group(0)

            # Extract response time
            time_pattern = r"(\d+(?:\.\d+)?)\s*(?:ms|milliseconds?|seconds?|s)"
            match = re.search(time_pattern, message, re.IGNORECASE)
            if match:
                time_value = float(match.group(1))
                if "s" in match.group(0).lower() and "ms" not in match.group(0).lower():
                    time_value *= 1000  # Convert to milliseconds
                fields["response_time"] = time_value

            # Extract status code
            status_pattern = r"status[_-]?code[:=]\s*(\d{3})"
            match = re.search(status_pattern, message, re.IGNORECASE)
            if match:
                fields["status_code"] = int(match.group(1))

            return fields

        except Exception as e:
            logger.error(f"Log field extraction failed: {e}")
            return {}

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process logging requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "search_logs":
                async for response in self._handle_log_search(message):
                    yield response

            elif message_type == "analyze_logs":
                async for response in self._handle_log_analysis(message):
                    yield response

            elif message_type == "detect_anomalies":
                async for response in self._handle_anomaly_detection(message):
                    yield response

            elif message_type == "correlate_events":
                async for response in self._handle_event_correlation(message):
                    yield response

            elif message_type == "generate_report":
                async for response in self._handle_report_generation(message):
                    yield response

            elif message_type == "create_alert":
                async for response in self._handle_alert_creation(message):
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
            logger.error(f"Logging processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_log_search(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle log search request
        """
        try:
            search_query = message.content.get("query", {})
            time_range = message.content.get("time_range", "1h")
            limit = message.content.get("limit", 100)

            # Search logs
            search_result = await self._search_logs(search_query, time_range, limit)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "log_search_response",
                    "search_result": search_result,
                    "query": search_query,
                    "time_range": time_range,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Log search handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _search_logs(
        self, query: dict[str, Any], time_range: str, limit: int
    ) -> dict[str, Any]:
        """
        Search logs in Elasticsearch
        """
        try:
            if not self.es_client:
                return {"error": "Elasticsearch not available", "logs_found": False}

            # Build Elasticsearch query
            es_query = self._build_es_query(query, time_range)

            # Execute search
            response = self.es_client.search(
                index=f"logs-{datetime.now().strftime('%Y-%m-%d')}", body=es_query, size=limit
            )

            logs = []
            for hit in response["hits"]["hits"]:
                log_entry = hit["_source"]
                log_entry["id"] = hit["_id"]
                log_entry["score"] = hit["_score"]
                logs.append(log_entry)

            return {
                "logs_found": True,
                "logs": logs,
                "total_hits": response["hits"]["total"]["value"],
                "took_ms": response["took"],
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Log search failed: {e}")
            return {"error": str(e), "logs_found": False}

    def _build_es_query(self, query: dict[str, Any], time_range: str) -> dict[str, Any]:
        """
        Build Elasticsearch query
        """
        try:
            # Parse time range
            end_time = datetime.now()
            if time_range.endswith("m"):
                start_time = end_time - timedelta(minutes=int(time_range[:-1]))
            elif time_range.endswith("h"):
                start_time = end_time - timedelta(hours=int(time_range[:-1]))
            elif time_range.endswith("d"):
                start_time = end_time - timedelta(days=int(time_range[:-1]))
            else:
                start_time = end_time - timedelta(hours=1)

            es_query = {
                "query": {
                    "bool": {
                        "must": [],
                        "filter": [
                            {
                                "range": {
                                    "timestamp": {
                                        "gte": start_time.isoformat(),
                                        "lte": end_time.isoformat(),
                                    }
                                }
                            }
                        ],
                    }
                },
                "sort": [{"timestamp": {"order": "desc"}}],
            }

            # Add search terms
            if "message" in query:
                es_query["query"]["bool"]["must"].append({"match": {"message": query["message"]}})

            if "level" in query:
                es_query["query"]["bool"]["must"].append({"term": {"level": query["level"]}})

            if "source" in query:
                es_query["query"]["bool"]["must"].append({"term": {"source": query["source"]}})

            if "component" in query:
                es_query["query"]["bool"]["must"].append(
                    {"term": {"component": query["component"]}}
                )

            return es_query

        except Exception as e:
            logger.error(f"ES query building failed: {e}")
            return {"query": {"match_all": {}}}

    async def _handle_log_analysis(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle log analysis request
        """
        try:
            analysis_type = message.content.get("analysis_type", "pattern")
            time_range = message.content.get("time_range", "1h")

            # Analyze logs
            analysis_result = await self._analyze_logs(analysis_type, time_range)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "log_analysis_response",
                    "analysis_result": analysis_result,
                    "analysis_type": analysis_type,
                    "time_range": time_range,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Log analysis handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _analyze_logs(self, analysis_type: str, time_range: str) -> dict[str, Any]:
        """
        Analyze logs for patterns, anomalies, etc.
        """
        try:
            # Get logs for analysis
            logs = await self._get_logs_for_analysis(time_range)

            if not logs:
                return {"analysis_completed": False, "error": "No logs found for analysis"}

            analysis_result = {}

            if analysis_type == "pattern" or analysis_type == "all":
                # Pattern recognition
                patterns = await self._analyze_patterns(logs)
                analysis_result["patterns"] = patterns

            if analysis_type == "anomaly" or analysis_type == "all":
                # Anomaly detection
                anomalies = await self._detect_log_anomalies(logs)
                analysis_result["anomalies"] = anomalies

            if analysis_type == "sentiment" or analysis_type == "all":
                # Sentiment analysis
                sentiments = await self._analyze_sentiment(logs)
                analysis_result["sentiments"] = sentiments

            if analysis_type == "correlation" or analysis_type == "all":
                # Event correlation
                correlations = await self._analyze_correlations(logs)
                analysis_result["correlations"] = correlations

            # Store analysis results
            self.logging_state["analysis_results"][f"{analysis_type}_{time_range}"] = {
                "result": analysis_result,
                "timestamp": datetime.now(),
                "logs_analyzed": len(logs),
            }

            return {
                "analysis_completed": True,
                "analysis_result": analysis_result,
                "logs_analyzed": len(logs),
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Log analysis failed: {e}")
            return {"analysis_completed": False, "error": str(e)}

    async def _get_logs_for_analysis(self, time_range: str) -> list[dict[str, Any]]:
        """
        Get logs for analysis
        """
        try:
            # For now, return recent logs from queue/memory
            # In production, this would query Elasticsearch
            logs = []

            # Get logs from recent processing
            # This is a simplified implementation
            return logs

        except Exception as e:
            logger.error(f"Getting logs for analysis failed: {e}")
            return []

    async def _analyze_patterns(self, logs: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Analyze log patterns
        """
        try:
            patterns = {}

            # Group logs by level
            level_counts = defaultdict(int)
            for log in logs:
                level_counts[log.get("level", "UNKNOWN")] += 1

            patterns["level_distribution"] = dict(level_counts)

            # Find common error messages
            error_messages = [log["message"] for log in logs if log.get("level") == "ERROR"]
            if error_messages:
                # Simple frequency analysis
                message_counts = defaultdict(int)
                for msg in error_messages:
                    # Normalize message (remove timestamps, IDs, etc.)
                    normalized = re.sub(r"\d+", "<NUM>", msg)
                    normalized = re.sub(
                        r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}",
                        "<UUID>",
                        normalized,
                    )
                    message_counts[normalized] += 1

                patterns["common_errors"] = sorted(
                    message_counts.items(), key=lambda x: x[1], reverse=True
                )[:10]

            # Find time-based patterns
            hourly_counts = defaultdict(int)
            for log in logs:
                hour = log["timestamp"].hour
                hourly_counts[hour] += 1

            patterns["hourly_distribution"] = dict(hourly_counts)

            return patterns

        except Exception as e:
            logger.error(f"Pattern analysis failed: {e}")
            return {}

    async def _detect_log_anomalies(self, logs: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Detect anomalies in logs
        """
        try:
            anomalies = []

            if len(logs) < 10:
                return {
                    "anomalies_detected": [],
                    "message": "Insufficient data for anomaly detection",
                }

            # Prepare data for ML
            messages = [log["message"] for log in logs]

            # Vectorize messages
            try:
                tfidf_matrix = self.vectorizer.fit_transform(messages)
                features = tfidf_matrix.toarray()

                # Scale features
                features_scaled = self.scaler.fit_transform(features)

                # Detect anomalies
                anomaly_labels = self.cluster_model.fit_predict(features_scaled)

                # Find anomalies (outliers)
                for i, (log, label) in enumerate(zip(logs, anomaly_labels)):
                    if label == -1:  # DBSCAN outlier
                        anomalies.append(
                            {
                                "log_index": i,
                                "message": log["message"],
                                "level": log.get("level"),
                                "timestamp": log["timestamp"],
                                "anomaly_score": 1.0,  # Simplified
                                "reason": "Clustering outlier",
                            }
                        )

            except Exception as e:
                logger.warning(f"ML-based anomaly detection failed: {e}")
                # Fallback to rule-based detection
                for i, log in enumerate(logs):
                    if "Exception" in log["message"] or "Traceback" in log["message"]:
                        anomalies.append(
                            {
                                "log_index": i,
                                "message": log["message"],
                                "level": log.get("level"),
                                "timestamp": log["timestamp"],
                                "anomaly_score": 0.8,
                                "reason": "Exception detected",
                            }
                        )

            return {
                "anomalies_detected": anomalies,
                "anomaly_count": len(anomalies),
                "total_logs": len(logs),
            }

        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return {"anomalies_detected": [], "error": str(e)}

    async def _analyze_sentiment(self, logs: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Analyze sentiment in logs
        """
        try:
            sentiments = []

            for log in logs:
                message = log["message"]

                # Use VADER sentiment analyzer
                if self.sentiment_analyzer:
                    scores = self.sentiment_analyzer.polarity_scores(message)
                    sentiment = {
                        "compound": scores["compound"],
                        "positive": scores["pos"],
                        "negative": scores["neg"],
                        "neutral": scores["neu"],
                    }
                else:
                    # Fallback to TextBlob
                    blob = TextBlob(message)
                    sentiment = {
                        "polarity": blob.sentiment.polarity,
                        "subjectivity": blob.sentiment.subjectivity,
                    }

                sentiments.append(
                    {
                        "log_index": logs.index(log),
                        "message": message[:100],  # Truncate for storage
                        "sentiment": sentiment,
                        "timestamp": log["timestamp"],
                    }
                )

            # Aggregate sentiment statistics
            if sentiments:
                compound_scores = [
                    s["sentiment"].get("compound", s["sentiment"].get("polarity", 0))
                    for s in sentiments
                ]
                sentiment_stats = {
                    "average_sentiment": np.mean(compound_scores),
                    "sentiment_std": np.std(compound_scores),
                    "positive_logs": sum(1 for s in compound_scores if s > 0.1),
                    "negative_logs": sum(1 for s in compound_scores if s < -0.1),
                    "neutral_logs": sum(1 for s in compound_scores if -0.1 <= s <= 0.1),
                }
            else:
                sentiment_stats = {}

            return {
                "sentiments": sentiments[:100],  # Limit for response
                "sentiment_stats": sentiment_stats,
                "logs_analyzed": len(sentiments),
            }

        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return {"sentiments": [], "error": str(e)}

    async def _analyze_correlations(self, logs: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Analyze correlations between log events
        """
        try:
            correlations = []

            # Group logs by time windows
            time_windows = defaultdict(list)
            window_size = timedelta(minutes=5)

            for log in logs:
                window_start = log["timestamp"].replace(
                    minute=log["timestamp"].minute // 5 * 5, second=0, microsecond=0
                )
                time_windows[window_start].append(log)

            # Find correlations within windows
            for window_start, window_logs in time_windows.items():
                if len(window_logs) > 1:
                    # Simple correlation: multiple errors in same window
                    error_count = sum(
                        1 for log in window_logs if log.get("level") in ["ERROR", "CRITICAL"]
                    )
                    if error_count > 1:
                        correlations.append(
                            {
                                "correlation_type": "error_burst",
                                "window_start": window_start,
                                "window_end": window_start + window_size,
                                "events": len(window_logs),
                                "errors": error_count,
                                "description": f"Multiple errors detected in {window_size} window",
                            }
                        )

            return {
                "correlations_found": correlations,
                "correlation_count": len(correlations),
                "time_windows_analyzed": len(time_windows),
            }

        except Exception as e:
            logger.error(f"Correlation analysis failed: {e}")
            return {"correlations_found": [], "error": str(e)}

    # Background processing tasks
    async def _continuous_log_collection(self):
        """
        Continuous log collection and processing
        """
        try:
            while True:
                try:
                    # Process log queue
                    batch_size = self.logging_config["processing"]["batch_size"]
                    log_batch = []

                    # Collect batch of logs
                    for _ in range(batch_size):
                        try:
                            log_entry = self.log_queue.get_nowait()
                            log_batch.append(log_entry)
                        except asyncio.QueueEmpty:
                            break

                    if log_batch:
                        # Process batch
                        await self._process_log_batch(log_batch)

                        # Update statistics
                        self.logging_state["processing_stats"]["logs_processed"] += len(log_batch)

                except Exception as e:
                    logger.error(f"Log collection error: {e}")

                # Process every 10 seconds
                await asyncio.sleep(10)

        except asyncio.CancelledError:
            logger.info("Log collection cancelled")
            raise

    async def _continuous_log_analysis(self):
        """
        Continuous log analysis
        """
        try:
            while True:
                try:
                    # Perform periodic analysis
                    await self._analyze_logs("all", "1h")

                    # Check for alerts
                    await self._check_log_alerts()

                except Exception as e:
                    logger.error(f"Log analysis error: {e}")

                # Analyze every configured interval
                interval = self.logging_config["analysis"]["analysis_interval"]
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info("Log analysis cancelled")
            raise

    async def _continuous_log_monitoring(self):
        """
        Continuous log monitoring for alerts
        """
        try:
            while True:
                try:
                    # Monitor log patterns and rates
                    await self._monitor_log_patterns()

                    # Clean up old data
                    await self._cleanup_old_logs()

                except Exception as e:
                    logger.error(f"Log monitoring error: {e}")

                # Monitor every 60 seconds
                await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("Log monitoring cancelled")
            raise

    async def _process_log_batch(self, log_batch: list[dict[str, Any]]):
        """
        Process a batch of log entries
        """
        try:
            # Index logs in Elasticsearch
            if self.es_client:
                actions = []
                for log_entry in log_batch:
                    action = {
                        "_index": f"logs-{log_entry['timestamp'].strftime('%Y-%m-%d')}",
                        "_id": str(uuid.uuid4()),
                        "_source": log_entry,
                    }
                    actions.append(action)

                # Bulk index
                success, failed = helpers.bulk(self.es_client, actions, stats_only=True)
                if failed:
                    logger.warning(f"Failed to index {failed} log entries")

            # Check for alerts
            await self._check_log_alerts_batch(log_batch)

            # Queue for analysis
            for log_entry in log_batch:
                await self.analysis_queue.put(log_entry)

        except Exception as e:
            logger.error(f"Log batch processing failed: {e}")

    async def _check_log_alerts_batch(self, log_batch: list[dict[str, Any]]):
        """
        Check for alerts in log batch
        """
        try:
            alerts = []

            for log_entry in log_batch:
                message = log_entry["message"]
                level = log_entry.get("level", "")

                # Check error patterns
                for pattern in self.logging_config["alerting"]["error_patterns"]:
                    if re.search(pattern, message, re.IGNORECASE):
                        alerts.append(
                            {
                                "alert_type": "error_pattern",
                                "pattern": pattern,
                                "message": message,
                                "level": level,
                                "timestamp": log_entry["timestamp"],
                                "source": log_entry.get("source"),
                            }
                        )
                        break

                # Check warning patterns
                for pattern in self.logging_config["alerting"]["warning_patterns"]:
                    if re.search(pattern, message, re.IGNORECASE):
                        alerts.append(
                            {
                                "alert_type": "warning_pattern",
                                "pattern": pattern,
                                "message": message,
                                "level": level,
                                "timestamp": log_entry["timestamp"],
                                "source": log_entry.get("source"),
                            }
                        )
                        break

            # Send alerts
            for alert in alerts:
                await self._send_log_alert(alert)
                self.logging_state["alert_history"].append(alert)
                self.logging_state["processing_stats"]["alerts_sent"] += 1

        except Exception as e:
            logger.error(f"Log alert checking failed: {e}")

    async def _send_log_alert(self, alert: dict[str, Any]):
        """
        Send log alert
        """
        try:
            # Implementation for sending alerts (email, Slack, etc.)
            # This would integrate with the monitoring agent's alert system
            logger.warning(f"Log alert: {alert['alert_type']} - {alert['message'][:100]}")

        except Exception as e:
            logger.error(f"Log alert sending failed: {e}")

    async def _check_log_alerts(self):
        """
        Check for rate-based alerts
        """
        try:
            # Check error rate
            current_time = datetime.now()
            time_window = timedelta(minutes=1)

            recent_errors = 0
            for alert in self.logging_state["alert_history"]:
                if (current_time - alert["timestamp"]) < time_window:
                    if alert.get("alert_type") == "error_pattern":
                        recent_errors += 1

            if recent_errors > self.logging_config["alerting"]["alert_thresholds"]["error_rate"]:
                alert = {
                    "alert_type": "high_error_rate",
                    "message": f"High error rate detected: {recent_errors} errors in last minute",
                    "value": recent_errors,
                    "threshold": self.logging_config["alerting"]["alert_thresholds"]["error_rate"],
                    "timestamp": current_time,
                }
                await self._send_log_alert(alert)

        except Exception as e:
            logger.error(f"Log alerts checking failed: {e}")

    async def _monitor_log_patterns(self):
        """
        Monitor log patterns for unusual activity
        """
        try:
            # Implementation for pattern monitoring
            pass
        except Exception as e:
            logger.error(f"Log pattern monitoring failed: {e}")

    async def _cleanup_old_logs(self):
        """
        Clean up old log data
        """
        try:
            # Clean up old alert history
            cutoff_time = datetime.now() - timedelta(days=7)
            self.logging_state["alert_history"] = deque(
                [
                    alert
                    for alert in self.logging_state["alert_history"]
                    if alert["timestamp"] > cutoff_time
                ],
                maxlen=5000,
            )

        except Exception as e:
            logger.error(f"Log cleanup failed: {e}")

    # Additional helper methods would continue...

    async def _load_log_patterns(self):
        """Load log patterns"""
        try:
            # Implementation for loading patterns
            pass
        except Exception as e:
            logger.error(f"Log patterns loading failed: {e}")

    async def _load_alert_history(self):
        """Load alert history"""
        try:
            # Implementation for loading alert history
            pass
        except Exception as e:
            logger.error(f"Alert history loading failed: {e}")

    async def _load_analysis_results(self):
        """Load analysis results"""
        try:
            # Implementation for loading analysis results
            pass
        except Exception as e:
            logger.error(f"Analysis results loading failed: {e}")


class LogFileHandler(FileSystemEventHandler):
    """
    File system event handler for log files
    """

    def __init__(self, log_queue: asyncio.Queue, file_path: str):
        self.log_queue = log_queue
        self.file_path = file_path
        self.last_position = 0

        # Get initial file size
        try:
            if os.path.exists(file_path):
                self.last_position = os.path.getsize(file_path)
        except Exception as e:
            logger.error(f"Failed to get initial file position for {file_path}: {e}")

    def on_modified(self, event):
        """
        Handle file modification events
        """
        if event.src_path == self.file_path:
            try:
                with open(self.file_path, encoding="utf-8", errors="ignore") as f:
                    f.seek(self.last_position)
                    new_lines = f.readlines()
                    self.last_position = f.tell()

                # Process new lines
                for line in new_lines:
                    if line.strip():
                        # Parse and queue log entry
                        log_entry = self._parse_log_line(line.strip())
                        if log_entry:
                            # Use asyncio to put in queue
                            asyncio.create_task(self._queue_log_entry(log_entry))

            except Exception as e:
                logger.error(f"Failed to process log file modification: {e}")

    def _parse_log_line(self, line: str) -> dict[str, Any] | None:
        """
        Parse log line (simplified version)
        """
        try:
            return {
                "timestamp": datetime.now(),
                "level": "INFO",  # Default
                "message": line,
                "source": self.file_path,
                "raw_line": line,
            }
        except Exception:
            return None

    async def _queue_log_entry(self, log_entry: dict[str, Any]):
        """
        Queue log entry asynchronously
        """
        try:
            await self.log_queue.put(log_entry)
        except Exception as e:
            logger.error(f"Failed to queue log entry: {e}")


# ========== TEST ==========
if __name__ == "__main__":

    async def test_logging_agent():
        # Initialize logging agent
        agent = LoggingAgent()
        await agent.start()

        # Test log search
        search_message = AgentMessage(
            id="test_search",
            from_agent="test",
            to_agent="logging_agent",
            content={
                "type": "search_logs",
                "query": {"level": "ERROR"},
                "time_range": "1h",
                "limit": 10,
            },
            timestamp=datetime.now(),
        )

        print("Testing logging agent...")
        async for response in agent.process_message(search_message):
            print(f"Search response: {response.content.get('type')}")
            search_result = response.content.get("search_result")
            print(f"Logs found: {search_result.get('logs_found')}")

        # Test log analysis
        analysis_message = AgentMessage(
            id="test_analysis",
            from_agent="test",
            to_agent="logging_agent",
            content={"type": "analyze_logs", "analysis_type": "pattern", "time_range": "1h"},
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(analysis_message):
            print(f"Analysis response: {response.content.get('type')}")
            analysis_result = response.content.get("analysis_result")
            print(f"Analysis completed: {analysis_result.get('analysis_completed')}")

        # Stop agent
        await agent.stop()
        print("Logging agent test completed")

    # Run test
    asyncio.run(test_logging_agent())
