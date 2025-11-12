"""
Fraud Detection Agent: ML-based fraud detection and prevention
Uses advanced ML models to detect fraudulent activities and patterns
"""

import asyncio
import json
import logging
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

import lightgbm as lgb
import networkx as nx
import numpy as np
import pandas as pd
import xgboost as xgb
from imblearn.ensemble import BalancedRandomForestClassifier
from imblearn.over_sampling import SMOTE
from networkx.algorithms import community
from scipy.stats import zscore
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import LabelEncoder, StandardScaler

from ..agents.base_agent import AgentMessage, BaseAgent
from ..api.database import get_db_session
from ..api.models import FraudAlerts, TransactionPatterns

logger = logging.getLogger(__name__)


class FraudDetectionAgent(BaseAgent):
    """
    Fraud Detection Agent for ML-based fraud detection and prevention
    Uses ensemble of ML models and behavioral analysis for comprehensive fraud detection
    """

    def __init__(
        self, agent_id: str = "fraud_detection_agent", config: dict[str, Any] | None = None
    ):
        super().__init__(agent_id, config or {})

        # Fraud detection configuration
        self.fraud_config = {
            "detection_methods": self.config.get(
                "detection_methods",
                [
                    "isolation_forest",
                    "random_forest",
                    "xgboost",
                    "lightgbm",
                    "behavioral_analysis",
                    "network_analysis",
                    "rule_based",
                ],
            ),
            "contamination": self.config.get("contamination", 0.01),  # Expected fraud ratio
            "alert_threshold": self.config.get(
                "alert_threshold", 0.8
            ),  # Fraud probability threshold
            "retraining_frequency": self.config.get("retraining_frequency", 3600),  # seconds
            "behavioral_window": self.config.get(
                "behavioral_window", 30
            ),  # days for behavioral analysis
            "network_depth": self.config.get("network_depth", 2),  # Network analysis depth
            "real_time_detection": self.config.get("real_time_detection", True),
        }

        # Fraud detection models
        self.fraud_models = {}
        self.scalers = {}
        self.label_encoders = {}

        # Behavioral analysis
        self.user_profiles = defaultdict(dict)
        self.transaction_history = defaultdict(lambda: deque(maxlen=1000))
        self.behavioral_baselines = {}

        # Network analysis
        self.transaction_graph = nx.DiGraph()
        self.entity_graph = nx.Graph()

        # Fraud patterns and rules
        self.fraud_rules = self._initialize_fraud_rules()
        self.fraud_patterns = defaultdict(list)

        # Detection history
        self.detection_history = defaultdict(list)
        self.false_positive_history = []

        # Background tasks
        self.detection_task = None
        self.retraining_task = None
        self.pattern_update_task = None

        logger.info(f"Fraud Detection Agent initialized: {agent_id}")

    def _initialize_fraud_rules(self) -> list[dict[str, Any]]:
        """
        Initialize rule-based fraud detection rules
        """
        return [
            {
                "name": "high_amount_transaction",
                "condition": lambda tx: tx.get("amount", 0) > 10000,
                "severity": "medium",
                "description": "Transaction amount exceeds threshold",
            },
            {
                "name": "unusual_location",
                "condition": lambda tx: self._check_location_anomaly(tx),
                "severity": "high",
                "description": "Transaction from unusual location",
            },
            {
                "name": "rapid_successive_transactions",
                "condition": lambda tx: self._check_transaction_frequency(tx),
                "severity": "medium",
                "description": "Unusual transaction frequency",
            },
            {
                "name": "round_amount_suspicion",
                "condition": lambda tx: tx.get("amount", 0) % 1000 == 0
                and tx.get("amount", 0) > 5000,
                "severity": "low",
                "description": "Round amount transaction",
            },
            {
                "name": "time_anomaly",
                "condition": lambda tx: self._check_time_anomaly(tx),
                "severity": "medium",
                "description": "Transaction at unusual time",
            },
            {
                "name": "velocity_check",
                "condition": lambda tx: self._check_velocity_anomaly(tx),
                "severity": "high",
                "description": "High velocity transaction pattern",
            },
        ]

    async def start(self):
        """
        Start the fraud detection agent
        """
        await super().start()

        # Initialize fraud detection models
        await self._initialize_fraud_models()

        # Start detection loops
        self.detection_task = asyncio.create_task(self._detection_loop())
        self.retraining_task = asyncio.create_task(self._retraining_loop())
        self.pattern_update_task = asyncio.create_task(self._pattern_update_loop())

        logger.info("Fraud detection monitoring started")

    async def stop(self):
        """
        Stop the fraud detection agent
        """
        if self.detection_task:
            self.detection_task.cancel()
            try:
                await self.detection_task
            except asyncio.CancelledError:
                pass

        if self.retraining_task:
            self.retraining_task.cancel()
            try:
                await self.retraining_task
            except asyncio.CancelledError:
                pass

        if self.pattern_update_task:
            self.pattern_update_task.cancel()
            try:
                await self.pattern_update_task
            except asyncio.CancelledError:
                pass

        await super().stop()
        logger.info("Fraud detection agent stopped")

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process fraud detection requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "analyze_transaction":
                async for response in self._handle_transaction_analysis(message):
                    yield response

            elif message_type == "detect_fraud_patterns":
                async for response in self._handle_fraud_pattern_detection(message):
                    yield response

            elif message_type == "get_fraud_history":
                async for response in self._handle_fraud_history(message):
                    yield response

            elif message_type == "update_fraud_model":
                async for response in self._handle_model_update(message):
                    yield response

            elif message_type == "analyze_user_behavior":
                async for response in self._handle_behavior_analysis(message):
                    yield response

            elif message_type == "investigate_alert":
                async for response in self._handle_alert_investigation(message):
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
            logger.error(f"Fraud detection processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _initialize_fraud_models(self):
        """
        Initialize fraud detection models
        """
        try:
            # Initialize multiple models for ensemble approach
            self.fraud_models = {
                "isolation_forest": IsolationForest(
                    n_estimators=100,
                    contamination=self.fraud_config["contamination"],
                    random_state=42,
                ),
                "random_forest": BalancedRandomForestClassifier(n_estimators=100, random_state=42),
                "xgboost": xgb.XGBClassifier(
                    n_estimators=100,
                    scale_pos_weight=100,  # Handle class imbalance
                    random_state=42,
                ),
                "lightgbm": lgb.LGBMClassifier(
                    n_estimators=100, scale_pos_weight=100, random_state=42
                ),
            }

            # Initialize scalers and encoders
            for model_name in self.fraud_models:
                self.scalers[model_name] = StandardScaler()
                self.label_encoders[model_name] = LabelEncoder()

            logger.info("Fraud detection models initialized")

        except Exception as e:
            logger.error(f"Fraud models initialization failed: {e}")

    async def _detection_loop(self):
        """
        Continuous fraud detection loop
        """
        try:
            while True:
                try:
                    # Analyze pending transactions
                    await self._analyze_pending_transactions()

                    # Update behavioral profiles
                    await self._update_behavioral_profiles()

                    # Check for fraud patterns
                    await self._check_fraud_patterns()

                except Exception as e:
                    logger.error(f"Detection loop error: {e}")

                # Wait before next detection cycle
                await asyncio.sleep(5)  # Check every 5 seconds

        except asyncio.CancelledError:
            logger.info("Detection loop cancelled")
            raise

    async def _retraining_loop(self):
        """
        Periodic model retraining loop
        """
        try:
            while True:
                try:
                    # Retrain models with new data
                    await self._retrain_fraud_models()

                except Exception as e:
                    logger.error(f"Retraining loop error: {e}")

                # Wait for retraining interval
                await asyncio.sleep(self.fraud_config["retraining_frequency"])

        except asyncio.CancelledError:
            logger.info("Retraining loop cancelled")
            raise

    async def _pattern_update_loop(self):
        """
        Pattern update and analysis loop
        """
        try:
            while True:
                try:
                    # Update fraud patterns
                    await self._update_fraud_patterns()

                    # Analyze network patterns
                    await self._analyze_network_patterns()

                except Exception as e:
                    logger.error(f"Pattern update loop error: {e}")

                # Wait for pattern update interval
                await asyncio.sleep(1800)  # Update every 30 minutes

        except asyncio.CancelledError:
            logger.info("Pattern update loop cancelled")
            raise

    async def _analyze_pending_transactions(self):
        """
        Analyze transactions that are pending fraud review
        """
        try:
            # Get pending transactions (placeholder - would query database)
            pending_transactions = await self._get_pending_transactions()

            for transaction in pending_transactions:
                fraud_score = await self._analyze_transaction_fraud(transaction)

                if fraud_score > self.fraud_config["alert_threshold"]:
                    await self._handle_fraud_alert(transaction, fraud_score)

                # Update transaction status
                await self._update_transaction_status(transaction, fraud_score)

        except Exception as e:
            logger.error(f"Pending transaction analysis failed: {e}")

    async def _get_pending_transactions(self) -> list[dict[str, Any]]:
        """
        Get transactions pending fraud analysis
        """
        try:
            # Placeholder - would query actual pending transactions
            return [
                {
                    "transaction_id": "tx_001",
                    "user_id": "user_123",
                    "amount": 1500.00,
                    "timestamp": datetime.now(),
                    "location": "New York",
                    "merchant": "Online Store",
                    "device_fingerprint": "device_abc",
                    "ip_address": "192.168.1.1",
                }
            ]

        except Exception as e:
            logger.error(f"Pending transaction retrieval failed: {e}")
            return []

    async def _analyze_transaction_fraud(self, transaction: dict[str, Any]) -> float:
        """
        Analyze transaction for fraud using multiple methods
        """
        try:
            fraud_scores = {}

            # ML-based detection
            for method in ["isolation_forest", "random_forest", "xgboost", "lightgbm"]:
                try:
                    score = await self._ml_fraud_detection(transaction, method)
                    fraud_scores[method] = score
                except Exception as e:
                    logger.error(f"ML detection failed for {method}: {e}")
                    fraud_scores[method] = 0.0

            # Rule-based detection
            rule_score = self._rule_based_fraud_detection(transaction)
            fraud_scores["rule_based"] = rule_score

            # Behavioral analysis
            behavioral_score = await self._behavioral_fraud_detection(transaction)
            fraud_scores["behavioral"] = behavioral_score

            # Network analysis
            network_score = await self._network_fraud_detection(transaction)
            fraud_scores["network"] = network_score

            # Ensemble score (weighted average)
            weights = {
                "isolation_forest": 0.15,
                "random_forest": 0.20,
                "xgboost": 0.20,
                "lightgbm": 0.15,
                "rule_based": 0.10,
                "behavioral": 0.10,
                "network": 0.10,
            }

            ensemble_score = sum(
                fraud_scores.get(method, 0) * weight for method, weight in weights.items()
            )

            # Store analysis results
            transaction["fraud_analysis"] = {
                "ensemble_score": ensemble_score,
                "method_scores": fraud_scores,
                "timestamp": datetime.now(),
            }

            return ensemble_score

        except Exception as e:
            logger.error(f"Transaction fraud analysis failed: {e}")
            return 0.0

    async def _ml_fraud_detection(self, transaction: dict[str, Any], method: str) -> float:
        """
        ML-based fraud detection using specified method
        """
        try:
            # Prepare features
            features = self._extract_transaction_features(transaction)

            if not features:
                return 0.0

            features_array = np.array([features])

            # Scale features
            scaler = self.scalers.get(method, StandardScaler())
            scaled_features = scaler.transform(features_array)

            # Get model prediction
            model = self.fraud_models.get(method)
            if not model:
                return 0.0

            if method == "isolation_forest":
                # Isolation Forest returns -1 for outliers, 1 for inliers
                prediction = model.predict(scaled_features)[0]
                score = 1.0 if prediction == -1 else 0.0
            else:
                # Other models return probability
                probabilities = model.predict_proba(scaled_features)[0]
                score = probabilities[1] if len(probabilities) > 1 else 0.0

            return float(score)

        except Exception as e:
            logger.error(f"ML fraud detection failed for {method}: {e}")
            return 0.0

    def _extract_transaction_features(self, transaction: dict[str, Any]) -> list[float] | None:
        """
        Extract numerical features from transaction
        """
        try:
            features = []

            # Basic transaction features
            features.extend(
                [
                    float(transaction.get("amount", 0)),
                    transaction.get("timestamp", datetime.now()).hour,  # Hour of day
                    transaction.get("timestamp", datetime.now()).weekday(),  # Day of week
                ]
            )

            # Location encoding (simplified)
            location = transaction.get("location", "")
            features.append(hash(location) % 1000 / 1000.0)  # Simple hash-based encoding

            # Merchant encoding
            merchant = transaction.get("merchant", "")
            features.append(hash(merchant) % 1000 / 1000.0)

            # Device fingerprint
            device = transaction.get("device_fingerprint", "")
            features.append(hash(device) % 1000 / 1000.0)

            # IP address (simplified)
            ip = transaction.get("ip_address", "")
            features.append(hash(ip) % 1000 / 1000.0)

            # Behavioral features (would be calculated from user history)
            features.extend(
                [
                    0.5,  # Average transaction amount ratio
                    0.3,  # Location consistency
                    0.7,  # Time pattern consistency
                    0.2,  # Amount pattern consistency
                ]
            )

            return features

        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return None

    def _rule_based_fraud_detection(self, transaction: dict[str, Any]) -> float:
        """
        Rule-based fraud detection
        """
        try:
            triggered_rules = []

            for rule in self.fraud_rules:
                if rule["condition"](transaction):
                    triggered_rules.append(rule)

            # Calculate score based on triggered rules and their severity
            if not triggered_rules:
                return 0.0

            severity_weights = {"low": 0.3, "medium": 0.6, "high": 0.9}

            total_weight = sum(
                severity_weights.get(rule["severity"], 0.5) for rule in triggered_rules
            )
            average_score = total_weight / len(triggered_rules)

            return min(average_score, 1.0)

        except Exception as e:
            logger.error(f"Rule-based fraud detection failed: {e}")
            return 0.0

    def _check_location_anomaly(self, transaction: dict[str, Any]) -> bool:
        """Check if transaction location is anomalous"""
        user_id = transaction.get("user_id")
        location = transaction.get("location")

        if not user_id or not location:
            return False

        # Check against user's typical locations
        user_profile = self.user_profiles.get(user_id, {})
        typical_locations = user_profile.get("typical_locations", [])

        return location not in typical_locations

    def _check_transaction_frequency(self, transaction: dict[str, Any]) -> bool:
        """Check for unusual transaction frequency"""
        user_id = transaction.get("user_id")

        if not user_id:
            return False

        # Get recent transactions
        recent_txs = list(self.transaction_history.get(user_id, []))
        recent_txs = [
            tx
            for tx in recent_txs
            if (datetime.now() - tx.get("timestamp", datetime.now())).seconds < 3600
        ]  # Last hour

        # Check frequency
        return len(recent_txs) > 5  # More than 5 transactions per hour

    def _check_time_anomaly(self, transaction: dict[str, Any]) -> bool:
        """Check if transaction time is anomalous"""
        timestamp = transaction.get("timestamp", datetime.now())
        hour = timestamp.hour

        # Unusual hours (2 AM - 5 AM)
        return 2 <= hour <= 5

    def _check_velocity_anomaly(self, transaction: dict[str, Any]) -> bool:
        """Check for velocity-based anomalies"""
        user_id = transaction.get("user_id")
        amount = transaction.get("amount", 0)

        if not user_id:
            return False

        # Check against user's average transaction amount
        user_profile = self.user_profiles.get(user_id, {})
        avg_amount = user_profile.get("avg_transaction_amount", 0)

        if avg_amount == 0:
            return False

        # Check if amount is significantly higher than average
        return amount > avg_amount * 3

    async def _behavioral_fraud_detection(self, transaction: dict[str, Any]) -> float:
        """
        Behavioral analysis for fraud detection
        """
        try:
            user_id = transaction.get("user_id")

            if not user_id:
                return 0.0

            # Get user profile
            profile = self.user_profiles.get(user_id, {})

            if not profile:
                return 0.5  # Neutral score for new users

            # Calculate behavioral anomalies
            anomalies = []

            # Amount anomaly
            amount = transaction.get("amount", 0)
            avg_amount = profile.get("avg_transaction_amount", amount)
            amount_zscore = abs(
                (amount - avg_amount) / max(profile.get("std_transaction_amount", 1), 1)
            )
            anomalies.append(amount_zscore > 3)

            # Location anomaly
            location = transaction.get("location")
            typical_locations = profile.get("typical_locations", [])
            location_anomaly = location not in typical_locations if typical_locations else False
            anomalies.append(location_anomaly)

            # Time anomaly
            timestamp = transaction.get("timestamp", datetime.now())
            typical_hours = profile.get("typical_hours", set(range(24)))
            time_anomaly = timestamp.hour not in typical_hours
            anomalies.append(time_anomaly)

            # Frequency anomaly
            recent_txs = [
                tx
                for tx in self.transaction_history.get(user_id, [])
                if (datetime.now() - tx.get("timestamp", datetime.now())).seconds < 3600
            ]
            frequency_anomaly = len(recent_txs) > profile.get("avg_hourly_transactions", 2) * 3
            anomalies.append(frequency_anomaly)

            # Calculate behavioral score
            anomaly_ratio = sum(anomalies) / len(anomalies) if anomalies else 0

            return min(anomaly_ratio, 1.0)

        except Exception as e:
            logger.error(f"Behavioral fraud detection failed: {e}")
            return 0.0

    async def _network_fraud_detection(self, transaction: dict[str, Any]) -> float:
        """
        Network-based fraud detection
        """
        try:
            user_id = transaction.get("user_id")
            merchant = transaction.get("merchant")

            if not user_id or not merchant:
                return 0.0

            # Check for connections in transaction graph
            if self.transaction_graph.has_node(user_id) and self.transaction_graph.has_node(
                merchant
            ):
                # Calculate network centrality measures
                user_centrality = nx.degree_centrality(self.transaction_graph).get(user_id, 0)
                merchant_centrality = nx.degree_centrality(self.transaction_graph).get(merchant, 0)

                # Check for suspicious patterns
                suspicious_patterns = [
                    user_centrality > 0.8,  # Highly connected user
                    merchant_centrality < 0.1,  # Rarely used merchant
                    self._check_graph_anomalies(user_id, merchant),
                ]

                network_score = sum(suspicious_patterns) / len(suspicious_patterns)

                return min(network_score, 1.0)

            return 0.0

        except Exception as e:
            logger.error(f"Network fraud detection failed: {e}")
            return 0.0

    def _check_graph_anomalies(self, user_id: str, merchant: str) -> bool:
        """
        Check for graph-based anomalies
        """
        try:
            # Check if this creates a suspicious pattern
            # (simplified - would use more sophisticated graph analysis)
            user_neighbors = set(self.transaction_graph.neighbors(user_id))
            merchant_neighbors = set(self.transaction_graph.neighbors(merchant))

            # Check for isolated connections
            common_neighbors = user_neighbors.intersection(merchant_neighbors)

            return len(common_neighbors) == 0  # No common connections

        except Exception:
            return False

    async def _handle_fraud_alert(self, transaction: dict[str, Any], fraud_score: float):
        """
        Handle detected fraud alert
        """
        try:
            alert = {
                "transaction_id": transaction.get("transaction_id"),
                "user_id": transaction.get("user_id"),
                "fraud_score": fraud_score,
                "severity": (
                    "high" if fraud_score > 0.9 else "medium" if fraud_score > 0.8 else "low"
                ),
                "detection_methods": transaction.get("fraud_analysis", {}).get("method_scores", {}),
                "timestamp": datetime.now(),
                "status": "active",
            }

            # Save alert
            await self._save_fraud_alert(alert)

            # Update detection history
            user_id = transaction.get("user_id")
            self.detection_history[user_id].append(
                {
                    "transaction_id": transaction.get("transaction_id"),
                    "fraud_score": fraud_score,
                    "timestamp": datetime.now(),
                    "false_positive": False,  # To be determined later
                }
            )

            logger.warning(
                f"Fraud alert generated for transaction {transaction.get('transaction_id')}: score={fraud_score:.3f}"
            )

        except Exception as e:
            logger.error(f"Fraud alert handling failed: {e}")

    async def _save_fraud_alert(self, alert: dict[str, Any]):
        """
        Save fraud alert to database
        """
        try:
            async with get_db_session() as session:
                alert_entry = FraudAlerts(
                    transaction_id=alert["transaction_id"],
                    user_id=alert["user_id"],
                    fraud_score=alert["fraud_score"],
                    severity=alert["severity"],
                    detection_methods=json.dumps(alert["detection_methods"]),
                    status=alert["status"],
                    created_at=datetime.now(),
                )

                session.add(alert_entry)
                await session.commit()

        except Exception as e:
            logger.error(f"Fraud alert save failed: {e}")

    async def _update_transaction_status(self, transaction: dict[str, Any], fraud_score: float):
        """
        Update transaction status based on fraud analysis
        """
        try:
            # Placeholder - would update transaction status in database
            status = "approved" if fraud_score < self.fraud_config["alert_threshold"] else "flagged"

            logger.info(
                f"Transaction {transaction.get('transaction_id')} status updated to: {status}"
            )

        except Exception as e:
            logger.error(f"Transaction status update failed: {e}")

    async def _update_behavioral_profiles(self):
        """
        Update user behavioral profiles
        """
        try:
            for user_id, transactions in self.transaction_history.items():
                if len(transactions) < 10:  # Need sufficient data
                    continue

                # Calculate behavioral metrics
                amounts = [tx.get("amount", 0) for tx in transactions]
                locations = [tx.get("location", "") for tx in transactions]
                hours = [tx.get("timestamp", datetime.now()).hour for tx in transactions]

                profile = {
                    "avg_transaction_amount": np.mean(amounts),
                    "std_transaction_amount": np.std(amounts),
                    "typical_locations": list(set(locations)),
                    "typical_hours": set(hours),
                    "avg_hourly_transactions": len(transactions) / 24,  # Rough estimate
                    "last_updated": datetime.now(),
                }

                self.user_profiles[user_id] = profile

        except Exception as e:
            logger.error(f"Behavioral profile update failed: {e}")

    async def _check_fraud_patterns(self):
        """
        Check for emerging fraud patterns
        """
        try:
            # Analyze recent transactions for patterns
            recent_transactions = []

            for user_transactions in self.transaction_history.values():
                recent = [
                    tx
                    for tx in user_transactions
                    if (datetime.now() - tx.get("timestamp", datetime.now())).days <= 1
                ]
                recent_transactions.extend(recent)

            if len(recent_transactions) < 50:
                return

            # Look for patterns (simplified)
            df = pd.DataFrame(recent_transactions)

            # Check for amount patterns
            amount_pattern = self._detect_amount_pattern(df)

            # Check for location patterns
            location_pattern = self._detect_location_pattern(df)

            # Check for time patterns
            time_pattern = self._detect_time_pattern(df)

            # Update fraud patterns
            patterns = {
                "amount_pattern": amount_pattern,
                "location_pattern": location_pattern,
                "time_pattern": time_pattern,
                "detected_at": datetime.now(),
            }

            self.fraud_patterns["recent"].append(patterns)

        except Exception as e:
            logger.error(f"Fraud pattern checking failed: {e}")

    def _detect_amount_pattern(self, df: pd.DataFrame) -> dict[str, Any]:
        """Detect suspicious amount patterns"""
        try:
            amounts = df["amount"].values
            z_scores = zscore(amounts)

            outliers = np.abs(z_scores) > 3
            pattern = {
                "outlier_ratio": np.mean(outliers),
                "max_z_score": np.max(np.abs(z_scores)),
                "suspicious": np.mean(outliers) > 0.1,
            }

            return pattern

        except Exception as e:
            return {"error": str(e)}

    def _detect_location_pattern(self, df: pd.DataFrame) -> dict[str, Any]:
        """Detect suspicious location patterns"""
        try:
            location_counts = df["location"].value_counts()
            unique_locations = len(location_counts)
            max_location_freq = location_counts.max() / len(df)

            pattern = {
                "unique_locations": unique_locations,
                "max_location_frequency": max_location_freq,
                "suspicious": unique_locations > 10 and max_location_freq < 0.3,
            }

            return pattern

        except Exception as e:
            return {"error": str(e)}

    def _detect_time_pattern(self, df: pd.DataFrame) -> dict[str, Any]:
        """Detect suspicious time patterns"""
        try:
            hours = pd.to_datetime(df["timestamp"]).dt.hour.values
            hour_counts = np.bincount(hours, minlength=24)
            unusual_hours = [2, 3, 4, 5]  # 2 AM - 5 AM

            unusual_hour_ratio = sum(hour_counts[h] for h in unusual_hours) / len(df)

            pattern = {
                "unusual_hour_ratio": unusual_hour_ratio,
                "suspicious": unusual_hour_ratio > 0.3,
            }

            return pattern

        except Exception as e:
            return {"error": str(e)}

    async def _analyze_network_patterns(self):
        """
        Analyze transaction network for fraud patterns
        """
        try:
            if len(self.transaction_graph.nodes()) < 10:
                return

            # Calculate network metrics
            centrality = nx.degree_centrality(self.transaction_graph)
            nx.betweenness_centrality(self.transaction_graph)

            # Detect suspicious nodes
            suspicious_nodes = []

            for node, cent in centrality.items():
                if cent > 0.8:  # Highly connected nodes
                    suspicious_nodes.append(
                        {"node": node, "centrality": cent, "reason": "high_centrality"}
                    )

            # Detect communities (potential fraud rings)
            communities = list(
                community.greedy_modularity_communities(self.transaction_graph.to_undirected())
            )

            for i, comm in enumerate(communities):
                if len(comm) > 5:  # Large communities
                    suspicious_nodes.append(
                        {"community_id": i, "size": len(comm), "reason": "large_community"}
                    )

            # Store network analysis results
            self.fraud_patterns["network"] = {
                "suspicious_nodes": suspicious_nodes,
                "communities": len(communities),
                "analyzed_at": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Network pattern analysis failed: {e}")

    async def _retrain_fraud_models(self):
        """
        Retrain fraud detection models with new data
        """
        try:
            # Get training data (placeholder - would get actual labeled data)
            training_data = await self._get_training_data()

            if not training_data:
                return

            # Prepare features and labels
            X = []
            y = []

            for sample in training_data:
                features = self._extract_transaction_features(sample)
                if features:
                    X.append(features)
                    y.append(1 if sample.get("is_fraud", False) else 0)

            if not X or not y:
                return

            X = np.array(X)
            y = np.array(y)

            # Handle class imbalance
            if len(np.unique(y)) > 1:
                smote = SMOTE(random_state=42)
                X_resampled, y_resampled = smote.fit_resample(X, y)
            else:
                X_resampled, y_resampled = X, y

            # Retrain each model
            for model_name, model in self.fraud_models.items():
                try:
                    if model_name != "isolation_forest":
                        model.fit(X_resampled, y_resampled)

                    # Update scaler
                    self.scalers[model_name].fit(X_resampled)

                    logger.info(f"Retrained {model_name} model")

                except Exception as e:
                    logger.error(f"Model retraining failed for {model_name}: {e}")

        except Exception as e:
            logger.error(f"Model retraining failed: {e}")

    async def _get_training_data(self) -> list[dict[str, Any]]:
        """
        Get training data for model retraining
        """
        try:
            # Placeholder - would get actual training data
            return [
                {
                    "amount": 100.0,
                    "timestamp": datetime.now(),
                    "location": "New York",
                    "merchant": "Store A",
                    "is_fraud": False,
                },
                {
                    "amount": 5000.0,
                    "timestamp": datetime.now(),
                    "location": "Unknown",
                    "merchant": "Suspicious Store",
                    "is_fraud": True,
                },
            ]

        except Exception as e:
            logger.error(f"Training data retrieval failed: {e}")
            return []

    async def _update_fraud_patterns(self):
        """
        Update fraud patterns database
        """
        try:
            async with get_db_session() as session:
                # Save pattern analysis results
                for pattern_type, patterns in self.fraud_patterns.items():
                    if isinstance(patterns, list) and patterns:
                        latest_pattern = patterns[-1]

                        pattern_entry = TransactionPatterns(
                            pattern_type=pattern_type,
                            pattern_data=json.dumps(latest_pattern),
                            detected_at=datetime.now(),
                        )

                        session.add(pattern_entry)

                await session.commit()

        except Exception as e:
            logger.error(f"Fraud pattern update failed: {e}")

    async def _handle_transaction_analysis(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle transaction analysis request
        """
        try:
            transaction = message.content.get("transaction", {})

            if not transaction:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Transaction data required"},
                    timestamp=datetime.now(),
                )
                return

            # Analyze transaction
            fraud_score = await self._analyze_transaction_fraud(transaction)

            # Add transaction to history
            user_id = transaction.get("user_id")
            if user_id:
                self.transaction_history[user_id].append(transaction)

            # Update graphs
            await self._update_transaction_graph(transaction)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "transaction_analysis_response",
                    "transaction_id": transaction.get("transaction_id"),
                    "fraud_score": fraud_score,
                    "is_fraudulent": fraud_score > self.fraud_config["alert_threshold"],
                    "analysis_details": transaction.get("fraud_analysis", {}),
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Transaction analysis handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _update_transaction_graph(self, transaction: dict[str, Any]):
        """
        Update transaction graph with new transaction
        """
        try:
            user_id = transaction.get("user_id")
            merchant = transaction.get("merchant")

            if user_id and merchant:
                # Add nodes
                self.transaction_graph.add_node(user_id, type="user")
                self.transaction_graph.add_node(merchant, type="merchant")

                # Add edge
                self.transaction_graph.add_edge(
                    user_id,
                    merchant,
                    weight=transaction.get("amount", 0),
                    timestamp=transaction.get("timestamp", datetime.now()),
                )

        except Exception as e:
            logger.error(f"Transaction graph update failed: {e}")

    async def _handle_fraud_pattern_detection(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle fraud pattern detection request
        """
        try:
            pattern_type = message.content.get("pattern_type", "all")

            patterns = {}

            if pattern_type == "all":
                patterns = dict(self.fraud_patterns)
            else:
                patterns = {pattern_type: self.fraud_patterns.get(pattern_type, [])}

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "fraud_pattern_response",
                    "pattern_type": pattern_type,
                    "patterns": patterns,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Fraud pattern detection handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_fraud_history(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle fraud history request
        """
        try:
            user_id = message.content.get("user_id")
            limit = message.content.get("limit", 50)

            if not user_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "User ID required"},
                    timestamp=datetime.now(),
                )
                return

            # Get fraud history
            history = self.detection_history.get(user_id, [])[-limit:]

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "fraud_history_response",
                    "user_id": user_id,
                    "history": history,
                    "total_alerts": len(self.detection_history.get(user_id, [])),
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Fraud history handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_model_update(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle fraud model update request
        """
        try:
            training_data = message.content.get("training_data", [])

            if not training_data:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Training data required"},
                    timestamp=datetime.now(),
                )
                return

            # Update models
            success = await self._update_models_with_data(training_data)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "model_update_response",
                    "success": success,
                    "models_updated": list(self.fraud_models.keys()) if success else [],
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Model update handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _update_models_with_data(self, training_data: list[dict[str, Any]]) -> bool:
        """
        Update models with provided training data
        """
        try:
            # Prepare data
            X = []
            y = []

            for sample in training_data:
                features = self._extract_transaction_features(sample)
                if features:
                    X.append(features)
                    y.append(1 if sample.get("is_fraud", False) else 0)

            if not X:
                return False

            X = np.array(X)
            y = np.array(y)

            # Update scalers
            for scaler in self.scalers.values():
                scaler.fit(X)

            # Retrain supervised models
            for model_name, model in self.fraud_models.items():
                if model_name != "isolation_forest":
                    try:
                        model.fit(X, y)
                    except Exception as e:
                        logger.error(f"Model update failed for {model_name}: {e}")

            return True

        except Exception as e:
            logger.error(f"Model update with data failed: {e}")
            return False

    async def _handle_behavior_analysis(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle user behavior analysis request
        """
        try:
            user_id = message.content.get("user_id")

            if not user_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "User ID required"},
                    timestamp=datetime.now(),
                )
                return

            # Get behavioral profile
            profile = self.user_profiles.get(user_id, {})

            # Analyze behavior patterns
            analysis = await self._analyze_user_behavior(user_id)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "behavior_analysis_response",
                    "user_id": user_id,
                    "profile": profile,
                    "analysis": analysis,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Behavior analysis handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _analyze_user_behavior(self, user_id: str) -> dict[str, Any]:
        """
        Analyze user behavior patterns
        """
        try:
            transactions = list(self.transaction_history.get(user_id, []))

            if not transactions:
                return {"status": "no_data"}

            # Calculate behavioral metrics
            df = pd.DataFrame(transactions)

            analysis = {
                "total_transactions": len(transactions),
                "avg_transaction_amount": df["amount"].mean(),
                "transaction_frequency": len(transactions) / 30,  # Per day
                "unique_locations": df["location"].nunique(),
                "unique_merchants": df["merchant"].nunique(),
                "preferred_hours": (
                    df["timestamp"].dt.hour.mode().tolist() if "timestamp" in df.columns else []
                ),
                "amount_volatility": (
                    df["amount"].std() / df["amount"].mean() if df["amount"].mean() > 0 else 0
                ),
                "analyzed_at": datetime.now(),
            }

            return analysis

        except Exception as e:
            logger.error(f"User behavior analysis failed: {e}")
            return {"error": str(e)}

    async def _handle_alert_investigation(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle fraud alert investigation request
        """
        try:
            alert_id = message.content.get("alert_id")

            if not alert_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Alert ID required"},
                    timestamp=datetime.now(),
                )
                return

            # Investigate alert (placeholder - would query actual alert)
            investigation = await self._investigate_fraud_alert(alert_id)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "alert_investigation_response",
                    "alert_id": alert_id,
                    "investigation": investigation,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Alert investigation handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _investigate_fraud_alert(self, alert_id: str) -> dict[str, Any]:
        """
        Investigate fraud alert details
        """
        try:
            # Placeholder investigation
            return {
                "alert_id": alert_id,
                "risk_factors": [
                    "Unusual transaction amount",
                    "Location anomaly",
                    "Time pattern deviation",
                ],
                "evidence": [
                    "Transaction amount 3x higher than user average",
                    "Location not in user's typical locations",
                    "Transaction occurred at unusual hour",
                ],
                "recommended_action": "Flag for manual review",
                "confidence_score": 0.85,
                "investigated_at": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Fraud alert investigation failed: {e}")
            return {"error": str(e)}


# ========== TEST ==========
if __name__ == "__main__":

    async def test_fraud_detection_agent():
        # Initialize fraud detection agent
        agent = FraudDetectionAgent()
        await agent.start()

        # Test transaction analysis
        transaction = {
            "transaction_id": "test_tx_001",
            "user_id": "test_user_123",
            "amount": 2500.00,
            "timestamp": datetime.now(),
            "location": "Unknown City",
            "merchant": "Suspicious Store",
            "device_fingerprint": "unknown_device",
            "ip_address": "10.0.0.1",
        }

        analysis_message = AgentMessage(
            id="test_analyze",
            from_agent="test",
            to_agent="fraud_detection_agent",
            content={"type": "analyze_transaction", "transaction": transaction},
            timestamp=datetime.now(),
        )

        print("Testing fraud detection agent...")
        async for response in agent.process_message(analysis_message):
            print(f"Analysis response: {response.content.get('type')}")
            if response.content.get("type") == "transaction_analysis_response":
                fraud_score = response.content.get("fraud_score", 0)
                is_fraud = response.content.get("is_fraudulent", False)
                print(f"Fraud score: {fraud_score:.3f}, Is fraudulent: {is_fraud}")

        # Test behavior analysis
        behavior_message = AgentMessage(
            id="test_behavior",
            from_agent="test",
            to_agent="fraud_detection_agent",
            content={"type": "analyze_user_behavior", "user_id": "test_user_123"},
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(behavior_message):
            print(f"Behavior analysis response: {response.content.get('type')}")

        # Stop agent
        await agent.stop()
        print("Fraud detection agent test completed")

    # Run test
    asyncio.run(test_fraud_detection_agent())
