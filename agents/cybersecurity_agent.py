"""
Cybersecurity Agent: Security monitoring and threat detection
Provides comprehensive security monitoring, threat detection, and incident response
capabilities for the autonomous analytics platform
"""

import asyncio
import base64
import logging
import re
import secrets
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
import xgboost as xgb
from cryptography.fernet import Fernet
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from ..agents.base_agent import AgentMessage, BaseAgent

logger = logging.getLogger(__name__)


class CybersecurityAgent(BaseAgent):
    """
    Cybersecurity Agent for threat detection and security monitoring
    Uses ML models and rule-based systems for comprehensive security
    """

    def __init__(self, agent_id: str = "cybersecurity_agent", config: dict[str, Any] | None = None):
        super().__init__(agent_id, config or {})

        # Security configuration
        self.security_config = {
            "threat_detection_methods": self.config.get(
                "threat_methods",
                [
                    "anomaly_detection",
                    "signature_based",
                    "behavioral_analysis",
                    "network_analysis",
                    "user_behavior_analytics",
                    "log_analysis",
                ],
            ),
            "security_levels": self.config.get(
                "security_levels", ["low", "medium", "high", "critical"]
            ),
            "monitoring_components": self.config.get(
                "monitoring",
                [
                    "authentication",
                    "authorization",
                    "data_access",
                    "api_calls",
                    "file_operations",
                    "network_traffic",
                    "system_resources",
                ],
            ),
            "threat_types": self.config.get(
                "threat_types",
                [
                    "brute_force",
                    "sql_injection",
                    "xss",
                    "csrf",
                    "ddos",
                    "malware",
                    "phishing",
                    "insider_threat",
                    "data_exfiltration",
                    "privilege_escalation",
                    "unauthorized_access",
                ],
            ),
            "response_actions": self.config.get(
                "response_actions",
                [
                    "alert",
                    "block",
                    "quarantine",
                    "isolate",
                    "terminate",
                    "log",
                    "notify_admin",
                    "auto_remediate",
                ],
            ),
            "encryption_algorithms": self.config.get(
                "encryption", ["AES256", "ChaCha20", "RSA4096", "Ed25519"]
            ),
            "security_policies": self.config.get(
                "policies",
                {
                    "password_policy": {
                        "min_length": 12,
                        "require_uppercase": True,
                        "require_lowercase": True,
                        "require_numbers": True,
                        "require_special": True,
                        "max_age_days": 90,
                    },
                    "session_policy": {
                        "max_session_time": 480,  # minutes
                        "max_concurrent_sessions": 3,
                        "idle_timeout": 30,
                    },
                    "access_policy": {
                        "failed_login_attempts": 5,
                        "lockout_duration": 900,  # seconds
                        "require_mfa": True,
                    },
                },
            ),
        }

        # ML models for threat detection
        self.threat_detection_models = {}
        self.anomaly_detection_models = {}
        self.behavior_analysis_models = {}

        # Security state
        self.security_state = {
            "active_threats": {},
            "security_events": deque(maxlen=10000),
            "user_sessions": {},
            "failed_login_attempts": defaultdict(int),
            "blocked_ips": set(),
            "suspicious_activities": deque(maxlen=5000),
            "security_alerts": deque(maxlen=2000),
            "encryption_keys": {},
            "access_patterns": {},
            "threat_intelligence": {},
            "security_metrics": {},
            "incident_response_log": deque(maxlen=1000),
            "compliance_status": {},
            "vulnerability_scan_results": {},
            "security_policies_status": {},
        }

        # Background tasks
        self.threat_monitoring_task = None
        self.anomaly_detection_task = None
        self.security_audit_task = None
        self.incident_response_task = None

        logger.info(f"Cybersecurity Agent initialized: {agent_id}")

    async def start(self):
        """
        Start the cybersecurity agent
        """
        await super().start()

        # Initialize security models
        await self._initialize_security_models()

        # Load security data
        await self._load_security_data()

        # Start background tasks
        self.threat_monitoring_task = asyncio.create_task(self._continuous_threat_monitoring())
        self.anomaly_detection_task = asyncio.create_task(self._continuous_anomaly_detection())
        self.security_audit_task = asyncio.create_task(self._continuous_security_audit())
        self.incident_response_task = asyncio.create_task(self._continuous_incident_response())

        logger.info("Security monitoring started")

    async def stop(self):
        """
        Stop the cybersecurity agent
        """
        if self.threat_monitoring_task:
            self.threat_monitoring_task.cancel()
            try:
                await self.threat_monitoring_task
            except asyncio.CancelledError:
                pass

        if self.anomaly_detection_task:
            self.anomaly_detection_task.cancel()
            try:
                await self.anomaly_detection_task
            except asyncio.CancelledError:
                pass

        if self.security_audit_task:
            self.security_audit_task.cancel()
            try:
                await self.security_audit_task
            except asyncio.CancelledError:
                pass

        if self.incident_response_task:
            self.incident_response_task.cancel()
            try:
                await self.incident_response_task
            except asyncio.CancelledError:
                pass

        await super().stop()
        logger.info("Cybersecurity agent stopped")

    async def _initialize_security_models(self):
        """
        Initialize ML models for security analysis
        """
        try:
            # Anomaly detection models
            self.anomaly_detection_models = {
                "isolation_forest": IsolationForest(
                    n_estimators=100, contamination=0.1, random_state=42
                ),
                "autoencoder": None,  # Initialize when needed
                "one_class_svm": None,  # Initialize when needed
            }

            # Threat detection models
            self.threat_detection_models = {
                "intrusion_detector": RandomForestClassifier(n_estimators=100, random_state=42),
                "malware_classifier": xgb.XGBClassifier(
                    n_estimators=100, max_depth=6, learning_rate=0.1
                ),
                "behavior_analyzer": lgb.LGBMClassifier(n_estimators=100, learning_rate=0.1),
            }

            # Behavior analysis models
            self.behavior_analysis_models = {
                "user_behavior_model": None,
                "session_anomaly_detector": None,
                "access_pattern_analyzer": None,
            }

            # Initialize encryption keys
            await self._initialize_encryption_keys()

            logger.info("Security models initialized")

        except Exception as e:
            logger.error(f"Security model initialization failed: {e}")

    async def _initialize_encryption_keys(self):
        """
        Initialize encryption keys for secure operations
        """
        try:
            # Generate master key
            master_key = Fernet.generate_key()
            self.security_state["encryption_keys"]["master"] = master_key

            # Generate session keys
            for i in range(5):
                session_key = Fernet.generate_key()
                self.security_state["encryption_keys"][f"session_{i}"] = session_key

            logger.info("Encryption keys initialized")

        except Exception as e:
            logger.error(f"Encryption key initialization failed: {e}")

    async def _load_security_data(self):
        """
        Load existing security data
        """
        try:
            # Load threat intelligence, user behavior patterns, etc.
            await self._load_threat_intelligence()
            await self._load_user_behavior_patterns()
            await self._load_security_policies()

            logger.info("Security data loaded")

        except Exception as e:
            logger.error(f"Security data loading failed: {e}")

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process security requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "authenticate_user":
                async for response in self._handle_user_authentication(message):
                    yield response

            elif message_type == "authorize_access":
                async for response in self._handle_access_authorization(message):
                    yield response

            elif message_type == "analyze_security_event":
                async for response in self._handle_security_event_analysis(message):
                    yield response

            elif message_type == "detect_threats":
                async for response in self._handle_threat_detection(message):
                    yield response

            elif message_type == "encrypt_data":
                async for response in self._handle_data_encryption(message):
                    yield response

            elif message_type == "decrypt_data":
                async for response in self._handle_data_decryption(message):
                    yield response

            elif message_type == "scan_vulnerabilities":
                async for response in self._handle_vulnerability_scan(message):
                    yield response

            elif message_type == "generate_security_report":
                async for response in self._handle_security_report(message):
                    yield response

            elif message_type == "respond_to_incident":
                async for response in self._handle_incident_response(message):
                    yield response

            elif message_type == "monitor_user_activity":
                async for response in self._handle_user_activity_monitoring(message):
                    yield response

            elif message_type == "validate_password":
                async for response in self._handle_password_validation(message):
                    yield response

            elif message_type == "check_compliance":
                async for response in self._handle_compliance_check(message):
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
            logger.error(f"Security processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_user_authentication(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle user authentication request
        """
        try:
            username = message.content.get("username")
            password = message.content.get("password")
            ip_address = message.content.get("ip_address")
            user_agent = message.content.get("user_agent")

            # Authenticate user
            auth_result = await self._authenticate_user(username, password, ip_address, user_agent)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "authentication_response",
                    "username": username,
                    "authenticated": auth_result["authenticated"],
                    "session_token": auth_result.get("session_token"),
                    "security_level": auth_result.get("security_level"),
                    "warnings": auth_result.get("warnings", []),
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"User authentication handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _authenticate_user(
        self, username: str, password: str, ip_address: str, user_agent: str
    ) -> dict[str, Any]:
        """
        Authenticate user with security checks
        """
        try:
            auth_result = {"authenticated": False, "warnings": []}

            # Check if IP is blocked
            if ip_address in self.security_state["blocked_ips"]:
                auth_result["warnings"].append("IP address is blocked")
                return auth_result

            # Check failed login attempts
            failed_attempts = self.security_state["failed_login_attempts"].get(username, 0)
            if (
                failed_attempts
                >= self.security_config["security_policies"]["access_policy"][
                    "failed_login_attempts"
                ]
            ):
                auth_result["warnings"].append(
                    "Account temporarily locked due to failed login attempts"
                )
                return auth_result

            # Basic authentication (would integrate with actual user store)
            if username and password:
                # Simulate password verification
                if len(password) >= 8:  # Basic check
                    auth_result["authenticated"] = True

                    # Generate session token
                    session_token = secrets.token_urlsafe(32)
                    auth_result["session_token"] = session_token

                    # Determine security level
                    auth_result["security_level"] = await self._determine_security_level(
                        username, ip_address
                    )

                    # Create session
                    session_id = str(uuid.uuid4())
                    self.security_state["user_sessions"][session_id] = {
                        "username": username,
                        "ip_address": ip_address,
                        "user_agent": user_agent,
                        "start_time": datetime.now(),
                        "last_activity": datetime.now(),
                        "security_level": auth_result["security_level"],
                    }

                    # Reset failed attempts
                    self.security_state["failed_login_attempts"][username] = 0

                    # Log successful authentication
                    await self._log_security_event(
                        "authentication_success",
                        {"username": username, "ip_address": ip_address},
                        "low",
                    )

                else:
                    auth_result["authenticated"] = False
                    auth_result["warnings"].append("Invalid credentials")

                    # Increment failed attempts
                    self.security_state["failed_login_attempts"][username] += 1

                    # Log failed authentication
                    await self._log_security_event(
                        "authentication_failure",
                        {"username": username, "ip_address": ip_address},
                        "medium",
                    )
            else:
                auth_result["warnings"].append("Missing credentials")

            return auth_result

        except Exception as e:
            logger.error(f"User authentication failed: {e}")
            return {"authenticated": False, "warnings": [str(e)]}

    async def _determine_security_level(self, username: str, ip_address: str) -> str:
        """
        Determine security level for user session
        """
        try:
            # Basic security level determination
            # In production, would check user roles, location, device trust, etc.

            security_level = "medium"

            # Check if IP is from trusted network
            trusted_networks = ["192.168.", "10.", "172."]
            if any(ip_address.startswith(network) for network in trusted_networks):
                security_level = "high"

            # Check user risk profile
            # This would be based on user behavior history

            return security_level

        except Exception as e:
            logger.error(f"Security level determination failed: {e}")
            return "medium"

    async def _handle_access_authorization(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle access authorization request
        """
        try:
            session_token = message.content.get("session_token")
            resource = message.content.get("resource")
            action = message.content.get("action")
            context = message.content.get("context", {})

            # Authorize access
            auth_result = await self._authorize_access(session_token, resource, action, context)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "authorization_response",
                    "authorized": auth_result["authorized"],
                    "resource": resource,
                    "action": action,
                    "security_level": auth_result.get("security_level"),
                    "restrictions": auth_result.get("restrictions", []),
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Access authorization handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _authorize_access(
        self, session_token: str, resource: str, action: str, context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Authorize access to resource
        """
        try:
            auth_result = {"authorized": False, "restrictions": []}

            # Validate session
            session = self.security_state["user_sessions"].get(session_token)
            if not session:
                auth_result["restrictions"].append("Invalid session")
                return auth_result

            # Check session expiry
            session_start = session["start_time"]
            max_session_time = self.security_config["security_policies"]["session_policy"][
                "max_session_time"
            ]
            if (datetime.now() - session_start).seconds > max_session_time * 60:
                auth_result["restrictions"].append("Session expired")
                return auth_result

            # Update last activity
            session["last_activity"] = datetime.now()

            # Check concurrent sessions
            user_sessions = [
                s
                for s in self.security_state["user_sessions"].values()
                if s["username"] == session["username"]
            ]
            max_concurrent = self.security_config["security_policies"]["session_policy"][
                "max_concurrent_sessions"
            ]
            if len(user_sessions) > max_concurrent:
                auth_result["restrictions"].append("Too many concurrent sessions")
                return auth_result

            # Check resource permissions based on security level
            security_level = session["security_level"]

            # Define access rules
            access_rules = {
                "data_read": ["low", "medium", "high"],
                "data_write": ["medium", "high"],
                "admin_access": ["high"],
                "system_config": ["high"],
            }

            allowed_levels = access_rules.get(action, ["high"])

            if security_level in allowed_levels:
                auth_result["authorized"] = True
                auth_result["security_level"] = security_level

                # Log authorized access
                await self._log_security_event(
                    "access_authorized",
                    {
                        "username": session["username"],
                        "resource": resource,
                        "action": action,
                        "security_level": security_level,
                    },
                    "low",
                )
            else:
                auth_result["authorized"] = False
                auth_result["restrictions"].append(f"Insufficient security level: {security_level}")

                # Log unauthorized access attempt
                await self._log_security_event(
                    "access_denied",
                    {
                        "username": session["username"],
                        "resource": resource,
                        "action": action,
                        "security_level": security_level,
                    },
                    "high",
                )

            return auth_result

        except Exception as e:
            logger.error(f"Access authorization failed: {e}")
            return {"authorized": False, "restrictions": [str(e)]}

    async def _handle_security_event_analysis(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle security event analysis request
        """
        try:
            event_data = message.content.get("event_data", {})
            event_type = message.content.get("event_type")

            # Analyze security event
            analysis = await self._analyze_security_event(event_data, event_type)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "security_event_analysis_response",
                    "event_type": event_type,
                    "analysis": analysis,
                    "threat_level": analysis.get("threat_level"),
                    "recommended_actions": analysis.get("recommended_actions", []),
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Security event analysis handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _analyze_security_event(
        self, event_data: dict[str, Any], event_type: str
    ) -> dict[str, Any]:
        """
        Analyze security event for threats
        """
        try:
            analysis = {
                "threat_level": "low",
                "confidence": 0.0,
                "indicators": [],
                "recommended_actions": [],
            }

            # Analyze based on event type
            if event_type == "login_attempt":
                analysis = await self._analyze_login_event(event_data)
            elif event_type == "api_call":
                analysis = await self._analyze_api_event(event_data)
            elif event_type == "file_access":
                analysis = await self._analyze_file_event(event_data)
            elif event_type == "network_traffic":
                analysis = await self._analyze_network_event(event_data)
            else:
                analysis = await self._analyze_generic_event(event_data)

            # Log analysis result
            if analysis["threat_level"] in ["high", "critical"]:
                await self._log_security_event(
                    "threat_detected",
                    {
                        "event_type": event_type,
                        "threat_level": analysis["threat_level"],
                        "confidence": analysis["confidence"],
                    },
                    analysis["threat_level"],
                )

            return analysis

        except Exception as e:
            logger.error(f"Security event analysis failed: {e}")
            return {
                "threat_level": "unknown",
                "error": str(e),
                "recommended_actions": ["investigate_manually"],
            }

    async def _analyze_login_event(self, event_data: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze login event
        """
        try:
            analysis = {
                "threat_level": "low",
                "confidence": 0.5,
                "indicators": [],
                "recommended_actions": [],
            }

            username = event_data.get("username")
            ip_address = event_data.get("ip_address")
            success = event_data.get("success", False)

            # Check for brute force indicators
            if not success:
                failed_attempts = self.security_state["failed_login_attempts"].get(username, 0) + 1
                if failed_attempts >= 3:
                    analysis["threat_level"] = "medium"
                    analysis["indicators"].append("multiple_failed_attempts")
                    analysis["recommended_actions"].append("temporary_lockout")

                if failed_attempts >= 5:
                    analysis["threat_level"] = "high"
                    analysis["indicators"].append("brute_force_attempt")
                    analysis["recommended_actions"].extend(["block_ip", "alert_admin"])

            # Check for suspicious IP
            if ip_address in self.security_state["blocked_ips"]:
                analysis["threat_level"] = "high"
                analysis["indicators"].append("blocked_ip")
                analysis["recommended_actions"].append("block_access")

            # Check for unusual location/time
            # This would compare with user's normal behavior

            analysis["confidence"] = 0.8 if analysis["threat_level"] != "low" else 0.3

            return analysis

        except Exception as e:
            logger.error(f"Login event analysis failed: {e}")
            return {"threat_level": "unknown", "error": str(e)}

    async def _analyze_api_event(self, event_data: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze API call event
        """
        try:
            analysis = {
                "threat_level": "low",
                "confidence": 0.5,
                "indicators": [],
                "recommended_actions": [],
            }

            endpoint = event_data.get("endpoint", "")
            method = event_data.get("method", "")
            response_code = event_data.get("response_code", 200)
            request_size = event_data.get("request_size", 0)

            # Check for SQL injection patterns
            if self._detect_sql_injection(endpoint):
                analysis["threat_level"] = "high"
                analysis["indicators"].append("sql_injection_attempt")
                analysis["recommended_actions"].extend(["block_request", "alert_security_team"])

            # Check for XSS patterns
            if self._detect_xss(endpoint):
                analysis["threat_level"] = "high"
                analysis["indicators"].append("xss_attempt")
                analysis["recommended_actions"].extend(["sanitize_input", "alert_security_team"])

            # Check for unusual request patterns
            if request_size > 1000000:  # 1MB
                analysis["threat_level"] = "medium"
                analysis["indicators"].append("large_request")
                analysis["recommended_actions"].append("rate_limit")

            # Check for error patterns
            if response_code in [400, 401, 403, 404] and method in ["POST", "PUT", "DELETE"]:
                analysis["threat_level"] = "medium"
                analysis["indicators"].append("suspicious_api_call")
                analysis["recommended_actions"].append("monitor_user")

            analysis["confidence"] = 0.8 if analysis["threat_level"] != "low" else 0.4

            return analysis

        except Exception as e:
            logger.error(f"API event analysis failed: {e}")
            return {"threat_level": "unknown", "error": str(e)}

    def _detect_sql_injection(self, input_string: str) -> bool:
        """
        Detect SQL injection patterns
        """
        sql_patterns = [
            r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b)",
            r"(\b(union|select|insert|update|delete|drop|create|alter)\b.*\b(select|from|where|and|or)\b)",
            r"(\b(union|select|insert|update|delete|drop|create|alter)\b.*\b(--|#|/\*|\*/)\b)",
            r"(\b(union|select|insert|update|delete|drop|create|alter)\b.*\b(1=1|1=0|'or'|'and')\b)",
        ]

        for pattern in sql_patterns:
            if re.search(pattern, input_string, re.IGNORECASE):
                return True

        return False

    def _detect_xss(self, input_string: str) -> bool:
        """
        Detect XSS patterns
        """
        xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>.*?</iframe>",
            r"<object[^>]*>.*?</object>",
            r"<embed[^>]*>.*?</embed>",
        ]

        for pattern in xss_patterns:
            if re.search(pattern, input_string, re.IGNORECASE):
                return True

        return False

    async def _handle_threat_detection(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle threat detection request
        """
        try:
            data_source = message.content.get("data_source")
            detection_method = message.content.get("detection_method", "anomaly_detection")
            time_window = message.content.get("time_window", "1h")

            # Detect threats
            threats = await self._detect_threats(data_source, detection_method, time_window)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "threat_detection_response",
                    "data_source": data_source,
                    "detection_method": detection_method,
                    "time_window": time_window,
                    "threats_detected": len(threats),
                    "threats": threats,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Threat detection handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _detect_threats(
        self, data_source: str, detection_method: str, time_window: str
    ) -> list[dict[str, Any]]:
        """
        Detect threats using specified method
        """
        try:
            threats = []

            # Get data for time window
            data = await self._get_data_for_time_window(data_source, time_window)

            if not data:
                return threats

            # Apply detection method
            if detection_method == "anomaly_detection":
                threats = await self._detect_anomalies(data)
            elif detection_method == "signature_based":
                threats = await self._detect_signatures(data)
            elif detection_method == "behavioral_analysis":
                threats = await self._detect_behavioral_anomalies(data)
            elif detection_method == "network_analysis":
                threats = await self._detect_network_threats(data)

            return threats

        except Exception as e:
            logger.error(f"Threat detection failed: {e}")
            return []

    async def _detect_anomalies(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Detect anomalies using ML models
        """
        try:
            threats = []

            if not data:
                return threats

            # Prepare data for ML
            df = pd.DataFrame(data)
            numeric_columns = df.select_dtypes(include=[np.number]).columns

            if len(numeric_columns) < 2:
                return threats

            # Use Isolation Forest for anomaly detection
            features = df[numeric_columns].fillna(0)
            scaler = StandardScaler()
            scaled_features = scaler.fit_transform(features)

            if self.anomaly_detection_models.get("isolation_forest"):
                predictions = self.anomaly_detection_models["isolation_forest"].fit_predict(
                    scaled_features
                )

                # Find anomalies (prediction = -1)
                anomaly_indices = np.where(predictions == -1)[0]

                for idx in anomaly_indices:
                    threat = {
                        "type": "anomaly",
                        "severity": "medium",
                        "confidence": 0.8,
                        "description": f"Anomalous behavior detected in {data[idx]}",
                        "data_point": data[idx],
                        "timestamp": datetime.now(),
                    }
                    threats.append(threat)

            return threats

        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return []

    async def _detect_signatures(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Detect threats using signature-based detection
        """
        try:
            threats = []

            # Define threat signatures
            signatures = {
                "brute_force": {
                    "pattern": lambda x: x.get("failed_attempts", 0) > 5,
                    "severity": "high",
                    "description": "Brute force attack detected",
                },
                "unusual_traffic": {
                    "pattern": lambda x: x.get("requests_per_minute", 0) > 1000,
                    "severity": "medium",
                    "description": "Unusual traffic pattern detected",
                },
                "suspicious_login": {
                    "pattern": lambda x: x.get("login_from_new_location", False),
                    "severity": "medium",
                    "description": "Login from unusual location",
                },
            }

            for item in data:
                for threat_type, signature in signatures.items():
                    if signature["pattern"](item):
                        threat = {
                            "type": threat_type,
                            "severity": signature["severity"],
                            "confidence": 0.9,
                            "description": signature["description"],
                            "data_point": item,
                            "timestamp": datetime.now(),
                        }
                        threats.append(threat)

            return threats

        except Exception as e:
            logger.error(f"Signature detection failed: {e}")
            return []

    async def _handle_data_encryption(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle data encryption request
        """
        try:
            data = message.content.get("data")
            encryption_type = message.content.get("encryption_type", "AES256")
            key_id = message.content.get("key_id", "master")

            # Encrypt data
            encrypted_data = await self._encrypt_data(data, encryption_type, key_id)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "encryption_response",
                    "encrypted_data": encrypted_data,
                    "encryption_type": encryption_type,
                    "key_id": key_id,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Data encryption handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _encrypt_data(self, data: str, encryption_type: str, key_id: str) -> str:
        """
        Encrypt data using specified method
        """
        try:
            # Get encryption key
            key = self.security_state["encryption_keys"].get(key_id)
            if not key:
                raise ValueError(f"Encryption key not found: {key_id}")

            # Encrypt using Fernet (AES 128)
            f = Fernet(key)
            encrypted_data = f.encrypt(data.encode())

            # Return base64 encoded
            return base64.b64encode(encrypted_data).decode()

        except Exception as e:
            logger.error(f"Data encryption failed: {e}")
            raise

    async def _handle_data_decryption(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle data decryption request
        """
        try:
            encrypted_data = message.content.get("encrypted_data")
            key_id = message.content.get("key_id", "master")

            # Decrypt data
            decrypted_data = await self._decrypt_data(encrypted_data, key_id)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "decryption_response",
                    "decrypted_data": decrypted_data,
                    "key_id": key_id,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Data decryption handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _decrypt_data(self, encrypted_data: str, key_id: str) -> str:
        """
        Decrypt data using specified key
        """
        try:
            # Get encryption key
            key = self.security_state["encryption_keys"].get(key_id)
            if not key:
                raise ValueError(f"Encryption key not found: {key_id}")

            # Decrypt using Fernet
            f = Fernet(key)
            decrypted_data = f.decrypt(base64.b64decode(encrypted_data))

            return decrypted_data.decode()

        except Exception as e:
            logger.error(f"Data decryption failed: {e}")
            raise

    async def _handle_vulnerability_scan(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle vulnerability scan request
        """
        try:
            scan_target = message.content.get("scan_target")
            scan_type = message.content.get("scan_type", "full")

            # Perform vulnerability scan
            scan_results = await self._perform_vulnerability_scan(scan_target, scan_type)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "vulnerability_scan_response",
                    "scan_target": scan_target,
                    "scan_type": scan_type,
                    "vulnerabilities_found": len(scan_results.get("vulnerabilities", [])),
                    "scan_results": scan_results,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Vulnerability scan handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _perform_vulnerability_scan(self, scan_target: str, scan_type: str) -> dict[str, Any]:
        """
        Perform vulnerability scanning
        """
        try:
            scan_results = {
                "scan_time": datetime.now(),
                "vulnerabilities": [],
                "risk_score": 0.0,
                "recommendations": [],
            }

            # Simulate vulnerability scanning
            # In production, would integrate with tools like OpenVAS, Nessus, etc.

            vulnerabilities = [
                {
                    "id": "CVE-2023-12345",
                    "severity": "high",
                    "description": "SQL injection vulnerability",
                    "cvss_score": 8.5,
                    "affected_component": "database_layer",
                    "recommendation": "Implement prepared statements",
                },
                {
                    "id": "CVE-2023-12346",
                    "severity": "medium",
                    "description": "Weak password policy",
                    "cvss_score": 5.5,
                    "affected_component": "authentication",
                    "recommendation": "Enforce strong password requirements",
                },
            ]

            scan_results["vulnerabilities"] = vulnerabilities

            # Calculate risk score
            high_severity = sum(1 for v in vulnerabilities if v["severity"] == "high")
            medium_severity = sum(1 for v in vulnerabilities if v["severity"] == "medium")

            scan_results["risk_score"] = min((high_severity * 10 + medium_severity * 5) / 10, 10.0)

            # Generate recommendations
            scan_results["recommendations"] = [
                "Apply security patches immediately",
                "Review and update security policies",
                "Implement regular security audits",
                "Monitor for suspicious activities",
            ]

            # Store scan results
            self.security_state["vulnerability_scan_results"][scan_target] = scan_results

            return scan_results

        except Exception as e:
            logger.error(f"Vulnerability scan failed: {e}")
            return {"error": str(e)}

    async def _handle_security_report(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle security report generation request
        """
        try:
            report_type = message.content.get("report_type", "summary")
            time_period = message.content.get("time_period", "24h")

            # Generate security report
            report = await self._generate_security_report(report_type, time_period)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "security_report_response",
                    "report_type": report_type,
                    "time_period": time_period,
                    "report": report,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Security report generation handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _generate_security_report(self, report_type: str, time_period: str) -> dict[str, Any]:
        """
        Generate comprehensive security report
        """
        try:
            report = {
                "generated_at": datetime.now(),
                "time_period": time_period,
                "summary": {},
                "details": {},
            }

            # Calculate time window
            if time_period == "1h":
                hours = 1
            elif time_period == "24h":
                hours = 24
            elif time_period == "7d":
                hours = 168
            else:
                hours = 24

            cutoff_time = datetime.now() - timedelta(hours=hours)

            # Get security events for period
            recent_events = [
                event
                for event in self.security_state["security_events"]
                if event.get("timestamp", datetime.min) > cutoff_time
            ]

            # Generate summary
            report["summary"] = {
                "total_events": len(recent_events),
                "threats_detected": len(
                    [e for e in recent_events if e.get("threat_level") in ["high", "critical"]]
                ),
                "authentication_attempts": len(
                    [e for e in recent_events if e.get("event_type") == "authentication"]
                ),
                "blocked_ips": len(self.security_state["blocked_ips"]),
                "active_sessions": len(self.security_state["user_sessions"]),
            }

            # Generate detailed sections based on report type
            if report_type == "summary":
                report["details"] = {
                    "top_threats": await self._get_top_threats(recent_events, 5),
                    "security_metrics": self.security_state["security_metrics"],
                    "recommendations": await self._generate_security_recommendations(recent_events),
                }
            elif report_type == "detailed":
                report["details"] = {
                    "events_by_type": await self._group_events_by_type(recent_events),
                    "events_by_severity": await self._group_events_by_severity(recent_events),
                    "user_activity_summary": await self._summarize_user_activity(recent_events),
                    "system_health": await self._assess_system_health(),
                    "compliance_status": self.security_state["compliance_status"],
                }
            elif report_type == "threat_analysis":
                report["details"] = {
                    "threat_trends": await self._analyze_threat_trends(recent_events),
                    "attack_patterns": await self._identify_attack_patterns(recent_events),
                    "vulnerability_assessment": self.security_state["vulnerability_scan_results"],
                    "risk_assessment": await self._perform_risk_assessment(),
                }

            return report

        except Exception as e:
            logger.error(f"Security report generation failed: {e}")
            return {"error": str(e)}

    async def _get_top_threats(
        self, events: list[dict[str, Any]], limit: int
    ) -> list[dict[str, Any]]:
        """Get top threats from events"""
        try:
            threat_counts = defaultdict(int)
            for event in events:
                if event.get("threat_level") in ["high", "critical"]:
                    threat_type = event.get("event_type", "unknown")
                    threat_counts[threat_type] += 1

            sorted_threats = sorted(threat_counts.items(), key=lambda x: x[1], reverse=True)
            return [{"threat_type": t, "count": c} for t, c in sorted_threats[:limit]]
        except Exception:
            return []

    async def _generate_security_recommendations(self, events: list[dict[str, Any]]) -> list[str]:
        """Generate security recommendations based on events"""
        try:
            recommendations = []

            threat_count = len([e for e in events if e.get("threat_level") in ["high", "critical"]])
            if threat_count > 10:
                recommendations.append("Increase monitoring frequency")
                recommendations.append("Review access control policies")

            failed_auths = len(
                [e for e in events if e.get("event_type") == "authentication_failure"]
            )
            if failed_auths > 5:
                recommendations.append("Implement stronger authentication measures")
                recommendations.append("Consider multi-factor authentication")

            if len(self.security_state["blocked_ips"]) > 0:
                recommendations.append("Regularly review and update IP blocklists")

            recommendations.extend(
                [
                    "Conduct regular security training",
                    "Keep systems and software updated",
                    "Implement regular backup procedures",
                    "Monitor system logs continuously",
                ]
            )

            return recommendations
        except Exception:
            return ["Conduct comprehensive security audit"]

    async def _log_security_event(
        self, event_type: str, details: dict[str, Any], threat_level: str
    ):
        """
        Log security event
        """
        try:
            event = {
                "id": str(uuid.uuid4()),
                "event_type": event_type,
                "threat_level": threat_level,
                "details": details,
                "timestamp": datetime.now(),
            }

            self.security_state["security_events"].append(event)

            # Add to alerts if high threat level
            if threat_level in ["high", "critical"]:
                alert = {"event": event, "priority": threat_level, "timestamp": datetime.now()}
                self.security_state["security_alerts"].append(alert)

            logger.info(f"Security event logged: {event_type} ({threat_level})")

        except Exception as e:
            logger.error(f"Security event logging failed: {e}")

    # Background monitoring tasks
    async def _continuous_threat_monitoring(self):
        """
        Continuous threat monitoring
        """
        try:
            while True:
                try:
                    # Monitor various data sources for threats
                    await self._monitor_authentication_events()
                    await self._monitor_api_calls()
                    await self._monitor_file_access()
                    await self._monitor_network_traffic()

                except Exception as e:
                    logger.error(f"Threat monitoring error: {e}")

                # Monitor every 30 seconds
                await asyncio.sleep(30)

        except asyncio.CancelledError:
            logger.info("Threat monitoring cancelled")
            raise

    async def _continuous_anomaly_detection(self):
        """
        Continuous anomaly detection
        """
        try:
            while True:
                try:
                    # Run anomaly detection on recent data
                    await self._detect_system_anomalies()
                    await self._detect_user_behavior_anomalies()
                    await self._detect_network_anomalies()

                except Exception as e:
                    logger.error(f"Anomaly detection error: {e}")

                # Detect anomalies every 5 minutes
                await asyncio.sleep(300)

        except asyncio.CancelledError:
            logger.info("Anomaly detection cancelled")
            raise

    async def _continuous_security_audit(self):
        """
        Continuous security auditing
        """
        try:
            while True:
                try:
                    # Perform security audits
                    await self._audit_user_access()
                    await self._audit_system_configuration()
                    await self._audit_compliance_status()

                except Exception as e:
                    logger.error(f"Security audit error: {e}")

                # Audit every hour
                await asyncio.sleep(3600)

        except asyncio.CancelledError:
            logger.info("Security audit cancelled")
            raise

    async def _continuous_incident_response(self):
        """
        Continuous incident response
        """
        try:
            while True:
                try:
                    # Check for active incidents and respond
                    await self._check_active_incidents()
                    await self._execute_automated_responses()
                    await self._update_incident_status()

                except Exception as e:
                    logger.error(f"Incident response error: {e}")

                # Respond every minute
                await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("Incident response cancelled")
            raise

    # Additional helper methods would continue here...

    async def _load_threat_intelligence(self):
        """Load threat intelligence data"""
        try:
            # Implementation for loading threat intelligence
            pass
        except Exception as e:
            logger.error(f"Threat intelligence loading failed: {e}")

    async def _load_user_behavior_patterns(self):
        """Load user behavior patterns"""
        try:
            # Implementation for loading user behavior patterns
            pass
        except Exception as e:
            logger.error(f"User behavior patterns loading failed: {e}")

    async def _load_security_policies(self):
        """Load security policies"""
        try:
            # Implementation for loading security policies
            pass
        except Exception as e:
            logger.error(f"Security policies loading failed: {e}")

    async def _get_data_for_time_window(self, data_source: str, time_window: str):
        """Get data for specified time window"""
        try:
            # Implementation for getting data
            return []
        except Exception as e:
            logger.error(f"Data retrieval failed: {e}")
            return []

    async def _detect_behavioral_anomalies(self, data: list[dict[str, Any]]):
        """Detect behavioral anomalies"""
        try:
            # Implementation for behavioral anomaly detection
            return []
        except Exception as e:
            logger.error(f"Behavioral anomaly detection failed: {e}")
            return []

    async def _detect_network_threats(self, data: list[dict[str, Any]]):
        """Detect network threats"""
        try:
            # Implementation for network threat detection
            return []
        except Exception as e:
            logger.error(f"Network threat detection failed: {e}")
            return []

    async def _monitor_authentication_events(self):
        """Monitor authentication events"""
        try:
            # Implementation for authentication monitoring
            pass
        except Exception as e:
            logger.error(f"Authentication monitoring failed: {e}")

    async def _monitor_api_calls(self):
        """Monitor API calls"""
        try:
            # Implementation for API monitoring
            pass
        except Exception as e:
            logger.error(f"API monitoring failed: {e}")

    async def _monitor_file_access(self):
        """Monitor file access"""
        try:
            # Implementation for file access monitoring
            pass
        except Exception as e:
            logger.error(f"File access monitoring failed: {e}")

    async def _monitor_network_traffic(self):
        """Monitor network traffic"""
        try:
            # Implementation for network traffic monitoring
            pass
        except Exception as e:
            logger.error(f"Network traffic monitoring failed: {e}")

    async def _detect_system_anomalies(self):
        """Detect system anomalies"""
        try:
            # Implementation for system anomaly detection
            pass
        except Exception as e:
            logger.error(f"System anomaly detection failed: {e}")

    async def _detect_user_behavior_anomalies(self):
        """Detect user behavior anomalies"""
        try:
            # Implementation for user behavior anomaly detection
            pass
        except Exception as e:
            logger.error(f"User behavior anomaly detection failed: {e}")

    async def _detect_network_anomalies(self):
        """Detect network anomalies"""
        try:
            # Implementation for network anomaly detection
            pass
        except Exception as e:
            logger.error(f"Network anomaly detection failed: {e}")

    async def _audit_user_access(self):
        """Audit user access"""
        try:
            # Implementation for user access auditing
            pass
        except Exception as e:
            logger.error(f"User access auditing failed: {e}")

    async def _audit_system_configuration(self):
        """Audit system configuration"""
        try:
            # Implementation for system configuration auditing
            pass
        except Exception as e:
            logger.error(f"System configuration auditing failed: {e}")

    async def _audit_compliance_status(self):
        """Audit compliance status"""
        try:
            # Implementation for compliance auditing
            pass
        except Exception as e:
            logger.error(f"Compliance auditing failed: {e}")

    async def _check_active_incidents(self):
        """Check for active incidents"""
        try:
            # Implementation for incident checking
            pass
        except Exception as e:
            logger.error(f"Active incident checking failed: {e}")

    async def _execute_automated_responses(self):
        """Execute automated responses"""
        try:
            # Implementation for automated response execution
            pass
        except Exception as e:
            logger.error(f"Automated response execution failed: {e}")

    async def _update_incident_status(self):
        """Update incident status"""
        try:
            # Implementation for incident status updates
            pass
        except Exception as e:
            logger.error(f"Incident status update failed: {e}")

    async def _group_events_by_type(self, events: list[dict[str, Any]]):
        """Group events by type"""
        try:
            # Implementation for event grouping
            return {}
        except Exception as e:
            logger.error(f"Event grouping failed: {e}")
            return {}

    async def _group_events_by_severity(self, events: list[dict[str, Any]]):
        """Group events by severity"""
        try:
            # Implementation for severity grouping
            return {}
        except Exception as e:
            logger.error(f"Severity grouping failed: {e}")
            return {}

    async def _summarize_user_activity(self, events: list[dict[str, Any]]):
        """Summarize user activity"""
        try:
            # Implementation for user activity summarization
            return {}
        except Exception as e:
            logger.error(f"User activity summarization failed: {e}")
            return {}

    async def _assess_system_health(self):
        """Assess system health"""
        try:
            # Implementation for system health assessment
            return {}
        except Exception as e:
            logger.error(f"System health assessment failed: {e}")
            return {}

    async def _analyze_threat_trends(self, events: list[dict[str, Any]]):
        """Analyze threat trends"""
        try:
            # Implementation for threat trend analysis
            return {}
        except Exception as e:
            logger.error(f"Threat trend analysis failed: {e}")
            return {}

    async def _identify_attack_patterns(self, events: list[dict[str, Any]]):
        """Identify attack patterns"""
        try:
            # Implementation for attack pattern identification
            return {}
        except Exception as e:
            logger.error(f"Attack pattern identification failed: {e}")
            return {}

    async def _perform_risk_assessment(self):
        """Perform risk assessment"""
        try:
            # Implementation for risk assessment
            return {}
        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            return {}


# ========== TEST ==========
if __name__ == "__main__":

    async def test_cybersecurity_agent():
        # Initialize cybersecurity agent
        agent = CybersecurityAgent()
        await agent.start()

        # Test user authentication
        auth_message = AgentMessage(
            id="test_auth",
            from_agent="test",
            to_agent="cybersecurity_agent",
            content={
                "type": "authenticate_user",
                "username": "testuser",
                "password": "testpass123",
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0",
            },
            timestamp=datetime.now(),
        )

        print("Testing cybersecurity agent...")
        async for response in agent.process_message(auth_message):
            print(f"Authentication response: {response.content.get('type')}")
            authenticated = response.content.get("result", {}).get("authenticated", False)
            print(f"Authentication successful: {authenticated}")

        # Test access authorization
        authz_message = AgentMessage(
            id="test_authz",
            from_agent="test",
            to_agent="cybersecurity_agent",
            content={
                "type": "authorize_access",
                "session_token": "test_session_123",
                "resource": "/api/data",
                "action": "read",
                "context": {"source": "web_app"},
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(authz_message):
            print(f"Authorization response: {response.content.get('type')}")
            authorized = response.content.get("result", {}).get("authorized", False)
            print(f"Access authorized: {authorized}")

        # Test threat detection
        threat_message = AgentMessage(
            id="test_threat",
            from_agent="test",
            to_agent="cybersecurity_agent",
            content={
                "type": "detect_threats",
                "data_source": "authentication_logs",
                "detection_method": "anomaly_detection",
                "time_window": "1h",
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(threat_message):
            print(f"Threat detection response: {response.content.get('type')}")
            threats = response.content.get("result", {}).get("threats_detected", 0)
            print(f"Threats detected: {threats}")

        # Test data encryption
        encrypt_message = AgentMessage(
            id="test_encrypt",
            from_agent="test",
            to_agent="cybersecurity_agent",
            content={
                "type": "encrypt_data",
                "data": "sensitive information",
                "encryption_type": "AES256",
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(encrypt_message):
            print(f"Encryption response: {response.content.get('type')}")
            encrypted = response.content.get("result", {}).get("encrypted_data")
            print(f"Data encrypted: {encrypted is not None}")

        # Stop agent
        await agent.stop()
        print("Cybersecurity agent test completed")

    # Run test
    asyncio.run(test_cybersecurity_agent())
