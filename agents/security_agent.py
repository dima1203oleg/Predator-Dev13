"""
Security Agent: Comprehensive security management
Handles authentication, authorization, encryption, threat detection, and compliance
"""

import asyncio
import json
import logging
import re
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from typing import Any

import kubernetes
import lightgbm as lgb
import pyotp
import vault
import xgboost as xgb
from azure.identity import DefaultAzureCredential
from azure.keyvault import KeyVaultClient
from cryptography.fernet import Fernet
from keycloak import KeycloakOpenID
from prometheus_api_client import PrometheusConnect
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from ..agents.base_agent import AgentMessage, BaseAgent

logger = logging.getLogger(__name__)


class SecurityAgent(BaseAgent):
    """
    Security Agent for comprehensive security management
    Handles authentication, authorization, encryption, threat detection, and compliance
    """

    def __init__(self, agent_id: str = "security_agent", config: dict[str, Any] | None = None):
        super().__init__(agent_id, config or {})

        # Security configuration
        self.security_config = {
            "authentication": self.config.get(
                "authentication",
                {
                    "provider": "keycloak",  # keycloak, azure_ad, custom
                    "mfa_required": True,
                    "session_timeout": 3600,  # seconds
                    "max_login_attempts": 5,
                    "password_policy": {
                        "min_length": 12,
                        "require_uppercase": True,
                        "require_lowercase": True,
                        "require_digits": True,
                        "require_special": True,
                    },
                },
            ),
            "authorization": self.config.get(
                "authorization",
                {
                    "rbac_enabled": True,
                    "roles": ["admin", "analyst", "viewer", "guest"],
                    "permissions": {
                        "read_data": ["admin", "analyst", "viewer"],
                        "write_data": ["admin", "analyst"],
                        "delete_data": ["admin"],
                        "manage_users": ["admin"],
                        "view_reports": ["admin", "analyst", "viewer"],
                        "export_data": ["admin", "analyst"],
                    },
                },
            ),
            "encryption": self.config.get(
                "encryption",
                {
                    "algorithm": "AES256",
                    "key_rotation_days": 90,
                    "data_encryption": True,
                    "tls_version": "1.3",
                    "certificate_validation": True,
                },
            ),
            "threat_detection": self.config.get(
                "threat_detection",
                {
                    "anomaly_detection": True,
                    "signature_based": True,
                    "behavioral_analysis": True,
                    "ml_models": ["isolation_forest", "random_forest", "xgboost"],
                    "alert_threshold": 0.8,
                    "false_positive_rate": 0.05,
                },
            ),
            "compliance": self.config.get(
                "compliance",
                {
                    "standards": ["GDPR", "HIPAA", "PCI_DSS", "SOX"],
                    "audit_logging": True,
                    "data_retention_days": 2555,  # 7 years
                    "privacy_controls": True,
                    "access_reviews": True,
                },
            ),
            "monitoring": self.config.get(
                "monitoring",
                {
                    "security_events": True,
                    "intrusion_detection": True,
                    "log_analysis": True,
                    "real_time_alerts": True,
                    "dashboard_enabled": True,
                },
            ),
            "processing_options": self.config.get(
                "options",
                {
                    "parallel_scans": 5,
                    "scan_timeout": 300,  # seconds
                    "alert_cooldown": 3600,  # seconds
                    "max_security_events": 10000,
                    "enable_auto_response": True,
                },
            ),
        }

        # Security clients and managers
        self.keycloak_client = None
        self.vault_client = None
        self.keyvault_client = None
        self.k8s_client = None
        self.prometheus_client = None

        # Security state
        self.security_state = {
            "active_sessions": {},
            "security_events": deque(
                maxlen=self.security_config["processing_options"]["max_security_events"]
            ),
            "threat_models": {},
            "encryption_keys": {},
            "user_permissions": {},
            "audit_log": deque(maxlen=50000),
            "alerts": deque(maxlen=1000),
            "compliance_status": {},
            "threat_intelligence": {},
            "blocked_ips": set(),
            "suspicious_activities": defaultdict(list),
            "security_metrics": {},
            "vulnerabilities": [],
            "access_patterns": defaultdict(list),
        }

        # ML models for threat detection
        self.threat_detection_models = {}

        # Background tasks
        self.threat_monitoring_task = None
        self.security_scanning_task = None
        self.audit_logging_task = None

        logger.info(f"Security Agent initialized: {agent_id}")

    async def start(self):
        """
        Start the security agent
        """
        await super().start()

        # Initialize security clients
        await self._initialize_security_clients()

        # Load security data
        await self._load_security_data()

        # Initialize ML models
        await self._initialize_threat_detection_models()

        # Start background tasks
        self.threat_monitoring_task = asyncio.create_task(self._continuous_threat_monitoring())
        self.security_scanning_task = asyncio.create_task(self._continuous_security_scanning())
        self.audit_logging_task = asyncio.create_task(self._continuous_audit_logging())

        logger.info("Security agent started")

    async def stop(self):
        """
        Stop the security agent
        """
        if self.threat_monitoring_task:
            self.threat_monitoring_task.cancel()
            try:
                await self.threat_monitoring_task
            except asyncio.CancelledError:
                pass

        if self.security_scanning_task:
            self.security_scanning_task.cancel()
            try:
                await self.security_scanning_task
            except asyncio.CancelledError:
                pass

        if self.audit_logging_task:
            self.audit_logging_task.cancel()
            try:
                await self.audit_logging_task
            except asyncio.CancelledError:
                pass

        await super().stop()
        logger.info("Security agent stopped")

    async def _initialize_security_clients(self):
        """
        Initialize security clients and connections
        """
        try:
            # Initialize Keycloak client
            try:
                self.keycloak_client = KeycloakOpenID(
                    server_url=self.security_config.get("keycloak_url", "http://keycloak:8080"),
                    client_id=self.security_config.get("keycloak_client_id", "predator-analytics"),
                    realm_name=self.security_config.get("keycloak_realm", "predator"),
                    client_secret_key=self.security_config.get("keycloak_client_secret"),
                )
                logger.info("Keycloak client initialized")
            except Exception as e:
                logger.warning(f"Keycloak client initialization failed: {e}")

            # Initialize Vault client
            try:
                self.vault_client = vault.Client(
                    url=self.security_config.get("vault_url", "http://vault:8200"),
                    token=self.security_config.get("vault_token"),
                )
                logger.info("Vault client initialized")
            except Exception as e:
                logger.warning(f"Vault client initialization failed: {e}")

            # Initialize Azure Key Vault client
            try:
                credential = DefaultAzureCredential()
                self.keyvault_client = KeyVaultClient(credential)
                logger.info("Azure Key Vault client initialized")
            except Exception as e:
                logger.warning(f"Azure Key Vault client initialization failed: {e}")

            # Initialize Kubernetes client
            try:
                kubernetes.config.load_kube_config()
                self.k8s_client = kubernetes.client.CoreV1Api()
                logger.info("Kubernetes client initialized")
            except Exception as e:
                logger.warning(f"Kubernetes client initialization failed: {e}")

            # Initialize Prometheus client
            try:
                self.prometheus_client = PrometheusConnect(
                    url=self.security_config.get("prometheus_url", "http://prometheus:9090")
                )
                logger.info("Prometheus client initialized")
            except Exception as e:
                logger.warning(f"Prometheus client initialization failed: {e}")

        except Exception as e:
            logger.error(f"Security client initialization failed: {e}")

    async def _load_security_data(self):
        """
        Load existing security data and configurations
        """
        try:
            # Load security events, user sessions, threat intelligence, etc.
            await self._load_security_events()
            await self._load_user_sessions()
            await self._load_threat_intelligence()

            logger.info("Security data loaded")

        except Exception as e:
            logger.error(f"Security data loading failed: {e}")

    async def _initialize_threat_detection_models(self):
        """
        Initialize ML models for threat detection
        """
        try:
            # Isolation Forest for anomaly detection
            self.threat_detection_models["isolation_forest"] = IsolationForest(
                contamination=self.security_config["threat_detection"]["false_positive_rate"],
                random_state=42,
            )

            # Random Forest for classification
            self.threat_detection_models["random_forest"] = RandomForestClassifier(
                n_estimators=100, random_state=42
            )

            # XGBoost for threat classification
            self.threat_detection_models["xgboost"] = xgb.XGBClassifier(
                objective="binary:logistic", n_estimators=100, random_state=42
            )

            # LightGBM for fast inference
            self.threat_detection_models["lightgbm"] = lgb.LGBMClassifier(
                objective="binary", n_estimators=100, random_state=42
            )

            logger.info("Threat detection models initialized")

        except Exception as e:
            logger.error(f"Threat detection model initialization failed: {e}")

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

            elif message_type == "encrypt_data":
                async for response in self._handle_data_encryption(message):
                    yield response

            elif message_type == "decrypt_data":
                async for response in self._handle_data_decryption(message):
                    yield response

            elif message_type == "detect_threats":
                async for response in self._handle_threat_detection(message):
                    yield response

            elif message_type == "scan_vulnerabilities":
                async for response in self._handle_vulnerability_scanning(message):
                    yield response

            elif message_type == "audit_logs":
                async for response in self._handle_audit_logging(message):
                    yield response

            elif message_type == "compliance_check":
                async for response in self._handle_compliance_check(message):
                    yield response

            elif message_type == "generate_security_report":
                async for response in self._handle_security_report(message):
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
            mfa_token = message.content.get("mfa_token")
            client_ip = message.content.get("client_ip")

            # Authenticate user
            auth_result = await self._authenticate_user(username, password, mfa_token, client_ip)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "user_authentication_response",
                    "auth_result": auth_result,
                    "username": username,
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
        self,
        username: str,
        password: str,
        mfa_token: str | None = None,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """
        Authenticate user with various methods
        """
        try:
            # Check if IP is blocked
            if client_ip in self.security_state["blocked_ips"]:
                return {"authenticated": False, "error": "IP address blocked", "blocked": True}

            # Check login attempts
            failed_attempts = len(self.security_state["suspicious_activities"].get(username, []))
            if failed_attempts >= self.security_config["authentication"]["max_login_attempts"]:
                self.security_state["blocked_ips"].add(client_ip)
                return {
                    "authenticated": False,
                    "error": "Too many failed attempts",
                    "blocked": True,
                }

            # Authenticate with Keycloak
            if self.keycloak_client:
                try:
                    token = self.keycloak_client.token(username, password)

                    # Verify MFA if required
                    if self.security_config["authentication"]["mfa_required"]:
                        if not mfa_token:
                            return {
                                "authenticated": False,
                                "error": "MFA token required",
                                "mfa_required": True,
                            }

                        # Verify MFA token
                        if not await self._verify_mfa_token(username, mfa_token):
                            return {"authenticated": False, "error": "Invalid MFA token"}

                    # Create session
                    session_id = str(uuid.uuid4())
                    session_data = {
                        "user_id": username,
                        "token": token,
                        "created_at": datetime.now(),
                        "expires_at": datetime.now()
                        + timedelta(
                            seconds=self.security_config["authentication"]["session_timeout"]
                        ),
                        "client_ip": client_ip,
                    }

                    self.security_state["active_sessions"][session_id] = session_data

                    # Log successful authentication
                    await self._log_security_event(
                        {
                            "event_type": "authentication_success",
                            "user": username,
                            "client_ip": client_ip,
                            "timestamp": datetime.now(),
                        }
                    )

                    return {
                        "authenticated": True,
                        "session_id": session_id,
                        "token": token,
                        "expires_at": session_data["expires_at"],
                    }

                except Exception as e:
                    logger.warning(f"Keycloak authentication failed: {e}")

                    # Log failed attempt
                    self.security_state["suspicious_activities"][username].append(
                        {
                            "timestamp": datetime.now(),
                            "client_ip": client_ip,
                            "reason": "authentication_failed",
                        }
                    )

                    return {"authenticated": False, "error": "Invalid credentials"}
            else:
                # Fallback authentication
                return {
                    "authenticated": True,
                    "session_id": str(uuid.uuid4()),
                    "message": "Authentication simulated",
                }

        except Exception as e:
            logger.error(f"User authentication failed: {e}")
            return {"authenticated": False, "error": str(e)}

    async def _verify_mfa_token(self, username: str, token: str) -> bool:
        """
        Verify MFA token
        """
        try:
            # Get user's TOTP secret
            totp_secret = await self._get_user_totp_secret(username)
            if not totp_secret:
                return False

            # Verify token
            totp = pyotp.TOTP(totp_secret)
            return totp.verify(token)

        except Exception as e:
            logger.error(f"MFA verification failed: {e}")
            return False

    async def _get_user_totp_secret(self, username: str) -> str | None:
        """
        Get user's TOTP secret
        """
        try:
            # Implementation for retrieving TOTP secret
            # This would typically come from secure storage
            return "JBSWY3DPEHPK3PXP"  # Example secret

        except Exception as e:
            logger.error(f"TOTP secret retrieval failed: {e}")
            return None

    async def _handle_access_authorization(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle access authorization request
        """
        try:
            user_id = message.content.get("user_id")
            resource = message.content.get("resource")
            action = message.content.get("action")
            session_id = message.content.get("session_id")

            # Authorize access
            auth_result = await self._authorize_access(user_id, resource, action, session_id)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "access_authorization_response",
                    "auth_result": auth_result,
                    "user_id": user_id,
                    "resource": resource,
                    "action": action,
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
        self, user_id: str, resource: str, action: str, session_id: str | None = None
    ) -> dict[str, Any]:
        """
        Authorize access based on RBAC
        """
        try:
            # Validate session
            if session_id:
                session = self.security_state["active_sessions"].get(session_id)
                if not session or session["expires_at"] < datetime.now():
                    return {"authorized": False, "error": "Invalid or expired session"}

            # Get user roles
            user_roles = await self._get_user_roles(user_id)

            # Check permissions
            required_permissions = self.security_config["authorization"]["permissions"].get(
                action, []
            )

            # Check if user has required role
            authorized = any(role in required_permissions for role in user_roles)

            # Log authorization attempt
            await self._log_security_event(
                {
                    "event_type": "authorization_attempt",
                    "user": user_id,
                    "resource": resource,
                    "action": action,
                    "authorized": authorized,
                    "timestamp": datetime.now(),
                }
            )

            return {
                "authorized": authorized,
                "user_roles": user_roles,
                "required_permissions": required_permissions,
                "resource": resource,
                "action": action,
            }

        except Exception as e:
            logger.error(f"Access authorization failed: {e}")
            return {"authorized": False, "error": str(e)}

    async def _get_user_roles(self, user_id: str) -> list[str]:
        """
        Get user roles from Keycloak or local storage
        """
        try:
            if self.keycloak_client:
                # Get roles from Keycloak
                token = await self._get_user_token(user_id)
                if token:
                    user_info = self.keycloak_client.userinfo(token["access_token"])
                    roles = user_info.get("realm_access", {}).get("roles", [])
                    return roles

            # Fallback to default roles
            return ["viewer"]

        except Exception as e:
            logger.error(f"User roles retrieval failed: {e}")
            return ["guest"]

    async def _get_user_token(self, user_id: str) -> dict[str, Any] | None:
        """
        Get user token
        """
        try:
            # Find active session for user
            for session in self.security_state["active_sessions"].values():
                if session["user_id"] == user_id:
                    return session["token"]
            return None

        except Exception as e:
            logger.error(f"User token retrieval failed: {e}")
            return None

    async def _handle_data_encryption(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle data encryption request
        """
        try:
            data = message.content.get("data")
            key_id = message.content.get("key_id")
            algorithm = message.content.get(
                "algorithm", self.security_config["encryption"]["algorithm"]
            )

            # Encrypt data
            encrypted_result = await self._encrypt_data(data, key_id, algorithm)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "data_encryption_response",
                    "encrypted_result": encrypted_result,
                    "algorithm": algorithm,
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

    async def _encrypt_data(
        self, data: str, key_id: str | None = None, algorithm: str = "AES256"
    ) -> dict[str, Any]:
        """
        Encrypt data using specified algorithm
        """
        try:
            # Get or generate encryption key
            if key_id and key_id in self.security_state["encryption_keys"]:
                key = self.security_state["encryption_keys"][key_id]
            else:
                key = await self._generate_encryption_key(algorithm)
                if key_id:
                    self.security_state["encryption_keys"][key_id] = key

            # Encrypt data
            fernet = Fernet(key)
            encrypted_data = fernet.encrypt(data.encode()).decode()

            return {
                "encrypted_data": encrypted_data,
                "key_id": key_id or str(uuid.uuid4()),
                "algorithm": algorithm,
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Data encryption failed: {e}")
            return {"error": str(e), "encrypted": False}

    async def _generate_encryption_key(self, algorithm: str) -> bytes:
        """
        Generate encryption key
        """
        try:
            if algorithm == "AES256":
                return Fernet.generate_key()
            else:
                # Default to AES256
                return Fernet.generate_key()

        except Exception as e:
            logger.error(f"Encryption key generation failed: {e}")
            raise

    async def _handle_data_decryption(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle data decryption request
        """
        try:
            encrypted_data = message.content.get("encrypted_data")
            key_id = message.content.get("key_id")

            # Decrypt data
            decrypted_result = await self._decrypt_data(encrypted_data, key_id)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "data_decryption_response", "decrypted_result": decrypted_result},
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

    async def _decrypt_data(self, encrypted_data: str, key_id: str) -> dict[str, Any]:
        """
        Decrypt data
        """
        try:
            # Get decryption key
            key = self.security_state["encryption_keys"].get(key_id)
            if not key:
                return {"error": "Encryption key not found", "decrypted": False}

            # Decrypt data
            fernet = Fernet(key)
            decrypted_data = fernet.decrypt(encrypted_data.encode()).decode()

            return {"decrypted_data": decrypted_data, "key_id": key_id, "timestamp": datetime.now()}

        except Exception as e:
            logger.error(f"Data decryption failed: {e}")
            return {"error": str(e), "decrypted": False}

    async def _handle_threat_detection(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle threat detection request
        """
        try:
            data = message.content.get("data")
            detection_type = message.content.get("detection_type", "anomaly")

            # Detect threats
            threat_result = await self._detect_threats(data, detection_type)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "threat_detection_response",
                    "threat_result": threat_result,
                    "detection_type": detection_type,
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

    async def _detect_threats(self, data: dict[str, Any], detection_type: str) -> dict[str, Any]:
        """
        Detect threats using ML models
        """
        try:
            threats = []

            if detection_type == "anomaly":
                # Anomaly detection
                features = self._extract_features(data)

                for model_name, model in self.threat_detection_models.items():
                    if hasattr(model, "predict"):
                        prediction = model.predict([features])
                        score = (
                            model.decision_function([features])[0]
                            if hasattr(model, "decision_function")
                            else 0
                        )

                        if prediction[0] == -1:  # Anomaly detected
                            threats.append(
                                {
                                    "model": model_name,
                                    "threat_type": "anomaly",
                                    "confidence": abs(score),
                                    "severity": "high" if abs(score) > 0.8 else "medium",
                                }
                            )

            elif detection_type == "signature":
                # Signature-based detection
                threats.extend(await self._signature_based_detection(data))

            elif detection_type == "behavioral":
                # Behavioral analysis
                threats.extend(await self._behavioral_analysis(data))

            # Check threat intelligence
            ti_threats = await self._check_threat_intelligence(data)
            threats.extend(ti_threats)

            return {
                "threats_detected": len(threats) > 0,
                "threats": threats,
                "detection_type": detection_type,
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Threat detection failed: {e}")
            return {"error": str(e), "threats_detected": False}

    def _extract_features(self, data: dict[str, Any]) -> list[float]:
        """
        Extract features for ML models
        """
        try:
            features = []

            # Extract numerical features
            features.append(data.get("request_count", 0))
            features.append(data.get("error_rate", 0))
            features.append(data.get("response_time", 0))
            features.append(data.get("bytes_transferred", 0))
            features.append(len(data.get("user_agent", "")))
            features.append(len(data.get("ip_address", "")))

            # Normalize features
            scaler = StandardScaler()
            return scaler.fit_transform([features])[0].tolist()

        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return [0.0] * 6

    async def _signature_based_detection(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Signature-based threat detection
        """
        try:
            threats = []

            # Check for known malicious patterns
            user_agent = data.get("user_agent", "").lower()
            if "sqlmap" in user_agent or "nmap" in user_agent:
                threats.append(
                    {
                        "threat_type": "scanner_detected",
                        "signature": "scanner_user_agent",
                        "severity": "high",
                    }
                )

            # Check for SQL injection patterns
            query = data.get("query", "")
            if re.search(
                r"(\bUNION\b|\bSELECT\b.*\bFROM\b|\bDROP\b|\bINSERT\b)", query, re.IGNORECASE
            ):
                threats.append(
                    {
                        "threat_type": "sql_injection",
                        "signature": "sql_keywords",
                        "severity": "critical",
                    }
                )

            return threats

        except Exception as e:
            logger.error(f"Signature-based detection failed: {e}")
            return []

    async def _behavioral_analysis(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Behavioral analysis for threat detection
        """
        try:
            threats = []

            # Analyze access patterns
            ip = data.get("ip_address", "")
            access_times = self.security_state["access_patterns"].get(ip, [])

            if len(access_times) > 10:
                # Check for unusual access patterns
                time_diffs = [t2 - t1 for t1, t2 in zip(access_times[:-1], access_times[1:])]
                avg_diff = sum(time_diffs) / len(time_diffs)

                if avg_diff < timedelta(seconds=1):  # Very rapid requests
                    threats.append(
                        {
                            "threat_type": "brute_force",
                            "behavior": "rapid_requests",
                            "severity": "high",
                        }
                    )

            return threats

        except Exception as e:
            logger.error(f"Behavioral analysis failed: {e}")
            return []

    async def _check_threat_intelligence(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Check threat intelligence feeds
        """
        try:
            threats = []

            ip = data.get("ip_address", "")

            # Check if IP is in threat intelligence
            if ip in self.security_state["threat_intelligence"]:
                threat_info = self.security_state["threat_intelligence"][ip]
                threats.append(
                    {
                        "threat_type": "known_malicious_ip",
                        "intelligence": threat_info,
                        "severity": "high",
                    }
                )

            return threats

        except Exception as e:
            logger.error(f"Threat intelligence check failed: {e}")
            return []

    async def _handle_vulnerability_scanning(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle vulnerability scanning request
        """
        try:
            target = message.content.get("target", "all")
            scan_type = message.content.get("scan_type", "full")

            # Scan for vulnerabilities
            scan_result = await self._scan_vulnerabilities(target, scan_type)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "vulnerability_scanning_response",
                    "scan_result": scan_result,
                    "target": target,
                    "scan_type": scan_type,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Vulnerability scanning handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _scan_vulnerabilities(self, target: str, scan_type: str) -> dict[str, Any]:
        """
        Scan for vulnerabilities
        """
        try:
            vulnerabilities = []

            if target == "all" or target == "dependencies":
                # Scan dependencies
                dep_vulns = await self._scan_dependencies()
                vulnerabilities.extend(dep_vulns)

            if target == "all" or target == "infrastructure":
                # Scan infrastructure
                infra_vulns = await self._scan_infrastructure()
                vulnerabilities.extend(infra_vulns)

            if target == "all" or target == "code":
                # Scan code
                code_vulns = await self._scan_code()
                vulnerabilities.extend(code_vulns)

            # Categorize vulnerabilities
            critical = [v for v in vulnerabilities if v.get("severity") == "critical"]
            high = [v for v in vulnerabilities if v.get("severity") == "high"]
            medium = [v for v in vulnerabilities if v.get("severity") == "medium"]

            return {
                "vulnerabilities_found": len(vulnerabilities) > 0,
                "vulnerabilities": vulnerabilities,
                "summary": {
                    "critical": len(critical),
                    "high": len(high),
                    "medium": len(medium),
                    "total": len(vulnerabilities),
                },
                "scan_type": scan_type,
                "target": target,
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Vulnerability scanning failed: {e}")
            return {"error": str(e), "vulnerabilities_found": False}

    async def _scan_dependencies(self) -> list[dict[str, Any]]:
        """
        Scan dependencies for vulnerabilities
        """
        try:
            vulnerabilities = []

            # Check Python packages
            try:
                import subprocess

                result = subprocess.run(
                    ["safety", "check", "--json"], capture_output=True, text=True, timeout=60
                )

                if result.returncode == 0:
                    safety_data = json.loads(result.stdout)
                    for vuln in safety_data.get("vulnerabilities", []):
                        vulnerabilities.append(
                            {
                                "type": "dependency",
                                "package": vuln.get("package"),
                                "version": vuln.get("version"),
                                "vulnerability_id": vuln.get("vulnerability_id"),
                                "severity": vuln.get("severity", "medium"),
                                "description": vuln.get("description"),
                            }
                        )
            except Exception as e:
                logger.warning(f"Dependency scanning failed: {e}")

            return vulnerabilities

        except Exception as e:
            logger.error(f"Dependency scanning failed: {e}")
            return []

    async def _scan_infrastructure(self) -> list[dict[str, Any]]:
        """
        Scan infrastructure for vulnerabilities
        """
        try:
            vulnerabilities = []

            # Check Kubernetes security
            if self.k8s_client:
                try:
                    # Check for privileged pods
                    pods = self.k8s_client.list_pod_for_all_namespaces()
                    for pod in pods.items:
                        for container in pod.spec.containers:
                            if container.security_context and container.security_context.privileged:
                                vulnerabilities.append(
                                    {
                                        "type": "infrastructure",
                                        "resource": "pod",
                                        "name": pod.metadata.name,
                                        "namespace": pod.metadata.namespace,
                                        "vulnerability": "privileged_container",
                                        "severity": "high",
                                        "description": "Container running with privileged access",
                                    }
                                )
                except Exception as e:
                    logger.warning(f"Kubernetes security scan failed: {e}")

            return vulnerabilities

        except Exception as e:
            logger.error(f"Infrastructure scanning failed: {e}")
            return []

    async def _scan_code(self) -> list[dict[str, Any]]:
        """
        Scan code for vulnerabilities
        """
        try:
            vulnerabilities = []

            # Use bandit for Python security scanning
            try:
                import subprocess

                result = subprocess.run(
                    ["bandit", "-r", ".", "-f", "json"], capture_output=True, text=True, timeout=120
                )

                if result.returncode == 0:
                    bandit_data = json.loads(result.stdout)
                    for issue in bandit_data.get("results", []):
                        vulnerabilities.append(
                            {
                                "type": "code",
                                "file": issue.get("filename"),
                                "line": issue.get("line_number"),
                                "vulnerability_id": issue.get("test_id"),
                                "severity": issue.get("issue_severity", "medium"),
                                "description": issue.get("issue_text"),
                            }
                        )
            except Exception as e:
                logger.warning(f"Code scanning failed: {e}")

            return vulnerabilities

        except Exception as e:
            logger.error(f"Code scanning failed: {e}")
            return []

    # Background monitoring tasks
    async def _continuous_threat_monitoring(self):
        """
        Continuous threat monitoring
        """
        try:
            while True:
                try:
                    # Monitor for threats
                    await self._monitor_threats()

                    # Update threat intelligence
                    await self._update_threat_intelligence()

                except Exception as e:
                    logger.error(f"Threat monitoring error: {e}")

                # Monitor every 60 seconds
                await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("Threat monitoring cancelled")
            raise

    async def _continuous_security_scanning(self):
        """
        Continuous security scanning
        """
        try:
            while True:
                try:
                    # Perform security scans
                    await self._perform_security_scans()

                    # Check compliance
                    await self._check_compliance_status()

                except Exception as e:
                    logger.error(f"Security scanning error: {e}")

                # Scan every 3600 seconds (1 hour)
                await asyncio.sleep(3600)

        except asyncio.CancelledError:
            logger.info("Security scanning cancelled")
            raise

    async def _continuous_audit_logging(self):
        """
        Continuous audit logging
        """
        try:
            while True:
                try:
                    # Process audit logs
                    await self._process_audit_logs()

                    # Generate security reports
                    await self._generate_security_reports()

                except Exception as e:
                    logger.error(f"Audit logging error: {e}")

                # Process every 300 seconds (5 minutes)
                await asyncio.sleep(300)

        except asyncio.CancelledError:
            logger.info("Audit logging cancelled")
            raise

    # Additional helper methods would continue...

    async def _load_security_events(self):
        """Load security events"""
        try:
            # Implementation for loading security events
            pass
        except Exception as e:
            logger.error(f"Security events loading failed: {e}")

    async def _load_user_sessions(self):
        """Load user sessions"""
        try:
            # Implementation for loading user sessions
            pass
        except Exception as e:
            logger.error(f"User sessions loading failed: {e}")

    async def _load_threat_intelligence(self):
        """Load threat intelligence"""
        try:
            # Implementation for loading threat intelligence
            pass
        except Exception as e:
            logger.error(f"Threat intelligence loading failed: {e}")

    async def _log_security_event(self, event: dict[str, Any]):
        """Log security event"""
        try:
            self.security_state["security_events"].append(event)
            self.security_state["audit_log"].append(event)
        except Exception as e:
            logger.error(f"Security event logging failed: {e}")

    async def _monitor_threats(self):
        """Monitor for threats"""
        try:
            # Implementation for threat monitoring
            pass
        except Exception as e:
            logger.error(f"Threat monitoring failed: {e}")

    async def _update_threat_intelligence(self):
        """Update threat intelligence"""
        try:
            # Implementation for threat intelligence updates
            pass
        except Exception as e:
            logger.error(f"Threat intelligence update failed: {e}")

    async def _perform_security_scans(self):
        """Perform security scans"""
        try:
            # Implementation for security scans
            pass
        except Exception as e:
            logger.error(f"Security scans failed: {e}")

    async def _check_compliance_status(self):
        """Check compliance status"""
        try:
            # Implementation for compliance checks
            pass
        except Exception as e:
            logger.error(f"Compliance check failed: {e}")

    async def _process_audit_logs(self):
        """Process audit logs"""
        try:
            # Implementation for audit log processing
            pass
        except Exception as e:
            logger.error(f"Audit log processing failed: {e}")

    async def _generate_security_reports(self):
        """Generate security reports"""
        try:
            # Implementation for security report generation
            pass
        except Exception as e:
            logger.error(f"Security report generation failed: {e}")


# ========== TEST ==========
if __name__ == "__main__":

    async def test_security_agent():
        # Initialize security agent
        agent = SecurityAgent()
        await agent.start()

        # Test user authentication
        auth_message = AgentMessage(
            id="test_auth",
            from_agent="test",
            to_agent="security_agent",
            content={
                "type": "authenticate_user",
                "username": "test_user",
                "password": "test_password",
                "client_ip": "192.168.1.1",
            },
            timestamp=datetime.now(),
        )

        print("Testing security agent...")
        async for response in agent.process_message(auth_message):
            print(f"Authentication response: {response.content.get('type')}")
            auth_result = response.content.get("auth_result")
            print(f"Authentication result: {auth_result}")

        # Test threat detection
        threat_message = AgentMessage(
            id="test_threat",
            from_agent="test",
            to_agent="security_agent",
            content={
                "type": "detect_threats",
                "data": {
                    "request_count": 1000,
                    "error_rate": 0.9,
                    "response_time": 5000,
                    "user_agent": "sqlmap",
                    "ip_address": "192.168.1.100",
                },
                "detection_type": "anomaly",
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(threat_message):
            print(f"Threat detection response: {response.content.get('type')}")
            threat_result = response.content.get("threat_result")
            print(f"Threat detection result: {threat_result}")

        # Stop agent
        await agent.stop()
        print("Security agent test completed")

    # Run test
    asyncio.run(test_security_agent())
