"""
Anomaly Detection Agent: Real-time anomaly detection in data streams
Uses statistical methods, ML models, and time-series analysis for anomaly detection
"""

import asyncio
import json
import logging
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import torch
import torch.nn as nn
from scipy import stats
from scipy.signal import find_peaks
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from ..agents.base_agent import AgentMessage, BaseAgent
from ..api.database import get_db_session
from ..api.models import Alert, AnomalyDetection, DataStream

logger = logging.getLogger(__name__)


class AnomalyDetectionAgent(BaseAgent):
    """
    Anomaly Detection Agent for real-time anomaly detection in data streams
    Uses multiple detection methods: statistical, ML-based, and deep learning
    approaches
    """

    def __init__(
        self, agent_id: str = "anomaly_detection_agent", config: dict[str, Any] | None = None
    ):
        super().__init__(agent_id, config or {})

        # Anomaly detection configuration
        self.anomaly_config = {
            "detection_methods": self.config.get(
                "detection_methods",
                [
                    "isolation_forest",
                    "one_class_svm",
                    "local_outlier_factor",
                    "statistical",
                    "time_series",
                    "autoencoder",
                ],
            ),
            "contamination": self.config.get("contamination", 0.1),
            "window_size": self.config.get("window_size", 100),
            "threshold_sensitivity": self.config.get("threshold_sensitivity", 0.95),
            "alert_cooldown": self.config.get("alert_cooldown", 300),
            "retraining_interval": self.config.get("retraining_interval", 3600),
            "feature_importance_threshold": self.config.get("feature_importance_threshold", 0.7),
        }

        # Detection models
        self.models = {}
        self.scalers = {}

        # Data buffers for sliding windows
        self.data_buffers = defaultdict(lambda: deque(maxlen=self.anomaly_config["window_size"]))
        self.feature_buffers = defaultdict(lambda: deque(maxlen=self.anomaly_config["window_size"]))

        # Anomaly tracking
        self.anomaly_history = defaultdict(list)
        self.alert_cooldowns = {}

        # Statistical baselines
        self.statistical_baselines = {}

        # Autoencoder for deep learning anomaly detection
        self.autoencoder_model = None
        self.autoencoder_scaler = StandardScaler()

        # Background tasks
        self.monitoring_task = None
        self.retraining_task = None

        logger.info(f"Anomaly Detection Agent initialized: {agent_id}")

    async def start(self):
        """
        Start the anomaly detection agent
        """
        await super().start()

        # Initialize detection models
        await self._initialize_detection_models()

        # Start monitoring loop
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

        # Start retraining loop
        self.retraining_task = asyncio.create_task(self._retraining_loop())

        logger.info("Anomaly detection monitoring started")

    async def stop(self):
        """
        Stop the anomaly detection agent
        """
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        if self.retraining_task:
            self.retraining_task.cancel()
            try:
                await self.retraining_task
            except asyncio.CancelledError:
                pass

        await super().stop()
        logger.info("Anomaly detection agent stopped")

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process anomaly detection requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "register_data_stream":
                async for response in self._handle_stream_registration(message):
                    yield response

            elif message_type == "detect_anomalies":
                async for response in self._handle_anomaly_detection(message):
                    yield response

            elif message_type == "analyze_anomaly":
                async for response in self._handle_anomaly_analysis(message):
                    yield response

            elif message_type == "get_anomaly_history":
                async for response in self._handle_anomaly_history(message):
                    yield response

            elif message_type == "update_detection_model":
                async for response in self._handle_model_update(message):
                    yield response

            elif message_type == "process_data_point":
                async for response in self._handle_data_point(message):
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
            logger.error(f"Anomaly detection processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _initialize_detection_models(self):
        """
        Initialize all anomaly detection models
        """
        try:
            # Isolation Forest
            self.models["isolation_forest"] = IsolationForest(
                n_estimators=100,
                contamination=self.anomaly_config["contamination"],
                random_state=42,
            )

            # One-Class SVM
            self.models["one_class_svm"] = OneClassSVM(
                kernel="rbf", nu=self.anomaly_config["contamination"], gamma="scale"
            )

            # Local Outlier Factor
            self.models["local_outlier_factor"] = LocalOutlierFactor(
                n_neighbors=20, contamination=self.anomaly_config["contamination"], novelty=True
            )

            # Initialize scalers
            for method in self.anomaly_config["detection_methods"]:
                if method != "statistical":
                    self.scalers[method] = StandardScaler()

            # Initialize autoencoder
            await self._initialize_autoencoder()

            logger.info("Detection models initialized")

        except Exception as e:
            logger.error(f"Detection models initialization failed: {e}")

    async def _initialize_autoencoder(self):
        """
        Initialize autoencoder neural network for deep anomaly detection
        """
        try:

            class Autoencoder(nn.Module):
                def __init__(self, input_dim: int, hidden_dim: int = 64):
                    super().__init__()
                    self.encoder = nn.Sequential(
                        nn.Linear(input_dim, hidden_dim),
                        nn.ReLU(),
                        nn.Linear(hidden_dim, hidden_dim // 2),
                        nn.ReLU(),
                        nn.Linear(hidden_dim // 2, hidden_dim // 4),
                    )
                    self.decoder = nn.Sequential(
                        nn.Linear(hidden_dim // 4, hidden_dim // 2),
                        nn.ReLU(),
                        nn.Linear(hidden_dim // 2, hidden_dim),
                        nn.ReLU(),
                        nn.Linear(hidden_dim, input_dim),
                    )

                def forward(self, x):
                    encoded = self.encoder(x)
                    decoded = self.decoder(encoded)
                    return decoded

            # Placeholder input dimension (will be set when data arrives)
            self.autoencoder_model = Autoencoder(input_dim=10)  # Default, will be updated

        except Exception as e:
            logger.error(f"Autoencoder initialization failed: {e}")

    async def _monitoring_loop(self):
        """
        Continuous monitoring loop for real-time anomaly detection
        """
        try:
            while True:
                try:
                    # Monitor all registered streams
                    for stream_id in self.data_buffers:
                        await self._monitor_stream_anomalies(stream_id)

                    # Clean up old anomaly history
                    await self._cleanup_old_anomalies()

                except Exception as e:
                    logger.error(f"Monitoring loop error: {e}")

                # Wait before next monitoring cycle
                await asyncio.sleep(10)  # Check every 10 seconds

        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled")
            raise

    async def _retraining_loop(self):
        """
        Periodic retraining loop for adaptive models
        """
        try:
            while True:
                try:
                    # Retrain models periodically
                    for stream_id in self.models:
                        if (
                            stream_id in self.data_buffers
                            and len(self.data_buffers[stream_id]) >= 50
                        ):
                            await self._retrain_models(stream_id)

                except Exception as e:
                    logger.error(f"Retraining loop error: {e}")

                # Wait for retraining interval
                await asyncio.sleep(self.anomaly_config["retraining_interval"])

        except asyncio.CancelledError:
            logger.info("Retraining loop cancelled")
            raise

    async def _monitor_stream_anomalies(self, stream_id: str):
        """
        Monitor a specific data stream for anomalies
        """
        try:
            buffer = self.data_buffers[stream_id]

            if len(buffer) < 10:  # Need minimum data for detection
                return

            # Convert buffer to feature matrix
            feature_matrix = np.array(list(buffer))

            # Detect anomalies using all methods
            anomaly_results = {}

            for method in self.anomaly_config["detection_methods"]:
                try:
                    if method in self.models:
                        scores = await self._detect_anomalies_method(
                            feature_matrix, method, stream_id
                        )
                        anomaly_results[method] = scores
                except Exception as e:
                    logger.error(f"Anomaly detection failed for method {method}: {e}")

            # Combine results using ensemble approach
            ensemble_score = self._combine_anomaly_scores(anomaly_results)

            # Check if anomaly threshold is exceeded
            if ensemble_score > self.anomaly_config["threshold_sensitivity"]:
                # Use internal handler for automatic anomaly processing
                await self._process_detected_anomaly(stream_id, ensemble_score, anomaly_results)

        except Exception as e:
            logger.error(f"Stream monitoring failed for {stream_id}: {e}")

    async def _detect_anomalies_method(
        self, feature_matrix: np.ndarray, method: str, stream_id: str
    ) -> dict[str, Any]:
        """
        Detect anomalies using a specific method
        """
        try:
            if method == "isolation_forest":
                # Scale features
                scaler = self.scalers.get(method, StandardScaler())
                scaled_features = scaler.fit_transform(feature_matrix)

                # Fit and predict
                model = self.models[method]
                anomaly_scores = model.fit_predict(scaled_features)

                # Convert to anomaly scores (-1 for outliers, 1 for inliers)
                scores = (anomaly_scores == -1).astype(int)

            elif method == "one_class_svm":
                scaler = self.scalers.get(method, StandardScaler())
                scaled_features = scaler.fit_transform(feature_matrix)

                model = self.models[method]
                anomaly_scores = model.fit_predict(scaled_features)

                scores = (anomaly_scores == -1).astype(int)

            elif method == "local_outlier_factor":
                scaler = self.scalers.get(method, StandardScaler())
                scaled_features = scaler.fit_transform(feature_matrix)

                model = self.models[method]
                anomaly_scores = model.fit_predict(scaled_features)

                scores = (anomaly_scores == -1).astype(int)

            elif method == "statistical":
                scores = self._statistical_anomaly_detection(feature_matrix)

            elif method == "time_series":
                scores = self._time_series_anomaly_detection(feature_matrix)

            elif method == "autoencoder":
                scores = await self._autoencoder_anomaly_detection(feature_matrix)

            else:
                scores = np.zeros(len(feature_matrix))

            return {
                "scores": scores.tolist(),
                "anomaly_count": int(np.sum(scores)),
                "anomaly_ratio": float(np.mean(scores)),
            }

        except Exception as e:
            logger.error(f"Method {method} anomaly detection failed: {e}")
            return {"scores": [], "anomaly_count": 0, "anomaly_ratio": 0.0}

    def _statistical_anomaly_detection(self, feature_matrix: np.ndarray) -> np.ndarray:
        """
        Statistical anomaly detection using z-score and IQR methods
        """
        try:
            scores = np.zeros(len(feature_matrix))

            for i in range(feature_matrix.shape[1]):
                feature_values = feature_matrix[:, i]

                # Z-score method
                z_scores = np.abs(stats.zscore(feature_values))
                z_anomalies = z_scores > 3  # 3 standard deviations

                # IQR method
                Q1 = np.percentile(feature_values, 25)
                Q3 = np.percentile(feature_values, 75)
                IQR = Q3 - Q1
                iqr_anomalies = (feature_values < Q1 - 1.5 * IQR) | (
                    feature_values > Q3 + 1.5 * IQR
                )

                # Combine methods
                feature_anomalies = z_anomalies | iqr_anomalies
                scores = np.maximum(scores, feature_anomalies.astype(int))

            return scores

        except Exception as e:
            logger.error(f"Statistical anomaly detection failed: {e}")
            return np.zeros(len(feature_matrix))

    def _time_series_anomaly_detection(self, feature_matrix: np.ndarray) -> np.ndarray:
        """
        Time series anomaly detection using trend analysis and peak detection
        """
        try:
            scores = np.zeros(len(feature_matrix))

            for i in range(feature_matrix.shape[1]):
                feature_values = feature_matrix[:, i]

                if len(feature_values) < 10:
                    continue

                # Detect peaks (potential anomalies)
                peaks, _ = find_peaks(feature_values, distance=5, prominence=np.std(feature_values))

                # Detect valleys
                valleys, _ = find_peaks(
                    -feature_values, distance=5, prominence=np.std(feature_values)
                )

                # Mark peaks and valleys as potential anomalies
                for peak_idx in peaks:
                    if peak_idx < len(scores):
                        scores[peak_idx] = 1

                for valley_idx in valleys:
                    if valley_idx < len(scores):
                        scores[valley_idx] = 1

                # Check for sudden changes
                diff = np.abs(np.diff(feature_values))
                threshold = np.mean(diff) + 2 * np.std(diff)
                change_anomalies = diff > threshold

                for j, is_anomaly in enumerate(change_anomalies):
                    if is_anomaly and j + 1 < len(scores):
                        scores[j + 1] = 1

            return scores

        except Exception as e:
            logger.error(f"Time series anomaly detection failed: {e}")
            return np.zeros(len(feature_matrix))

    async def _autoencoder_anomaly_detection(self, feature_matrix: np.ndarray) -> np.ndarray:
        """
        Autoencoder-based anomaly detection
        """
        try:
            if self.autoencoder_model is None:
                return np.zeros(len(feature_matrix))

            # Update input dimension if needed
            current_dim = feature_matrix.shape[1]
            if self.autoencoder_model.encoder[0].in_features != current_dim:
                await self._initialize_autoencoder()
                self.autoencoder_model.encoder[0] = nn.Linear(current_dim, 64)
                self.autoencoder_model.decoder[-1] = nn.Linear(64, current_dim)

            # Scale features
            scaled_features = self.autoencoder_scaler.fit_transform(feature_matrix)

            # Convert to tensor
            features_tensor = torch.FloatTensor(scaled_features)

            # Forward pass
            with torch.no_grad():
                reconstructed = self.autoencoder_model(features_tensor)
                reconstruction_error = torch.mean((features_tensor - reconstructed) ** 2, dim=1)

            # Convert to numpy and calculate anomaly scores
            errors = reconstruction_error.numpy()

            # Use statistical threshold for anomaly detection
            threshold = np.mean(errors) + 2 * np.std(errors)
            scores = (errors > threshold).astype(int)

            return scores

        except Exception as e:
            logger.error(f"Autoencoder anomaly detection failed: {e}")
            return np.zeros(len(feature_matrix))

    def _combine_anomaly_scores(self, anomaly_results: dict[str, dict[str, Any]]) -> float:
        """
        Combine anomaly scores from multiple methods using ensemble approach
        """
        try:
            if not anomaly_results:
                return 0.0

            # Calculate weighted ensemble score
            total_weight = 0
            ensemble_score = 0

            method_weights = {
                "isolation_forest": 0.25,
                "one_class_svm": 0.20,
                "local_outlier_factor": 0.20,
                "statistical": 0.15,
                "time_series": 0.10,
                "autoencoder": 0.10,
            }

            for method, results in anomaly_results.items():
                weight = method_weights.get(method, 0.1)
                anomaly_ratio = results.get("anomaly_ratio", 0)

                ensemble_score += anomaly_ratio * weight
                total_weight += weight

            return ensemble_score / total_weight if total_weight > 0 else 0

        except Exception as e:
            logger.error(f"Anomaly score combination failed: {e}")
            return 0.0

    async def _process_detected_anomaly(
        self, stream_id: str, ensemble_score: float, anomaly_results: dict[str, dict[str, Any]]
    ):
        """
        Handle detected anomaly (internal, automatic pipeline)
        """
        try:
            # Check alert cooldown
            last_alert = self.alert_cooldowns.get(stream_id)
            if (
                last_alert
                and (datetime.now() - last_alert).seconds < self.anomaly_config["alert_cooldown"]
            ):
                return

            # Record anomaly
            anomaly_record = {
                "stream_id": stream_id,
                "timestamp": datetime.now(),
                "ensemble_score": ensemble_score,
                "method_results": anomaly_results,
                "severity": (
                    "high" if ensemble_score > 0.8 else "medium" if ensemble_score > 0.6 else "low"
                ),
            }

            self.anomaly_history[stream_id].append(anomaly_record)

            # Update cooldown
            self.alert_cooldowns[stream_id] = datetime.now()

            # Save to database
            await self._save_anomaly_detection(anomaly_record)

            # Generate alert
            await self._generate_anomaly_alert(anomaly_record)

            logger.warning(f"Anomaly detected in stream {stream_id}: score={ensemble_score:.3f}")

        except Exception as e:
            logger.error(f"Anomaly handling failed: {e}")

    async def _save_anomaly_detection(self, anomaly_record: dict[str, Any]):
        """
        Save anomaly detection to database
        """
        try:
            async with get_db_session() as session:
                anomaly_entry = AnomalyDetection(
                    stream_id=anomaly_record["stream_id"],
                    detection_timestamp=anomaly_record["timestamp"],
                    anomaly_score=anomaly_record["ensemble_score"],
                    method_results=json.dumps(anomaly_record["method_results"]),
                    severity=anomaly_record["severity"],
                    detected_at=datetime.now(),
                )

                session.add(anomaly_entry)
                await session.commit()

        except Exception as e:
            logger.error(f"Anomaly detection save failed: {e}")

    async def _generate_anomaly_alert(self, anomaly_record: dict[str, Any]):
        """
        Generate alert for detected anomaly
        """
        try:
            alert_message = (
                f"Anomaly detected in stream {anomaly_record['stream_id']} "
                f"with score {anomaly_record['ensemble_score']:.3f} "
                f"(severity: {anomaly_record['severity']})"
            )

            # Create alert record
            async with get_db_session() as session:
                alert = Alert(
                    alert_type="anomaly_detection",
                    severity=anomaly_record["severity"],
                    message=alert_message,
                    details=json.dumps(anomaly_record),
                    created_at=datetime.now(),
                    status="active",
                )

                session.add(alert)
                await session.commit()

        except Exception as e:
            logger.error(f"Anomaly alert generation failed: {e}")

    async def _retrain_models(self, stream_id: str):
        """
        Retrain anomaly detection models with new data
        """
        try:
            buffer = self.data_buffers[stream_id]

            if len(buffer) < 50:  # Need sufficient data for retraining
                return

            feature_matrix = np.array(list(buffer))

            # Retrain each model
            for method in ["isolation_forest", "one_class_svm", "local_outlier_factor"]:
                if method in self.models:
                    scaler = self.scalers.get(method, StandardScaler())
                    scaled_features = scaler.fit_transform(feature_matrix)

                    self.models[method].fit(scaled_features)

            # Retrain autoencoder
            await self._retrain_autoencoder(feature_matrix)

            logger.info(f"Models retrained for stream {stream_id}")

        except Exception as e:
            logger.error(f"Model retraining failed for {stream_id}: {e}")

    async def _retrain_autoencoder(self, feature_matrix: np.ndarray):
        """
        Retrain autoencoder model
        """
        try:
            if self.autoencoder_model is None:
                return

            # Update input dimension
            current_dim = feature_matrix.shape[1]
            if self.autoencoder_model.encoder[0].in_features != current_dim:
                self.autoencoder_model.encoder[0] = nn.Linear(current_dim, 64)
                self.autoencoder_model.decoder[-1] = nn.Linear(64, current_dim)

            # Scale features
            scaled_features = self.autoencoder_scaler.fit_transform(feature_matrix)

            # Convert to tensor
            features_tensor = torch.FloatTensor(scaled_features)

            # Training parameters
            criterion = nn.MSELoss()
            optimizer = torch.optim.Adam(self.autoencoder_model.parameters(), lr=0.001)

            # Train for a few epochs
            self.autoencoder_model.train()
            for epoch in range(10):
                optimizer.zero_grad()
                output = self.autoencoder_model(features_tensor)
                loss = criterion(output, features_tensor)
                loss.backward()
                optimizer.step()

            logger.info("Autoencoder retrained")

        except Exception as e:
            logger.error(f"Autoencoder retraining failed: {e}")

    async def _cleanup_old_anomalies(self):
        """
        Clean up old anomaly records to prevent memory bloat
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=7)  # Keep 7 days of history

            for stream_id in self.anomaly_history:
                self.anomaly_history[stream_id] = [
                    anomaly
                    for anomaly in self.anomaly_history[stream_id]
                    if anomaly["timestamp"] > cutoff_date
                ]

        except Exception as e:
            logger.error(f"Anomaly cleanup failed: {e}")

    async def _handle_stream_registration(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle data stream registration for monitoring
        """
        try:
            stream_config = message.content.get("stream_config", {})

            required_fields = ["stream_id", "feature_columns", "data_source"]
            for field in required_fields:
                if field not in stream_config:
                    yield AgentMessage(
                        id=str(uuid.uuid4()),
                        from_agent=self.agent_id,
                        to_agent=message.from_agent,
                        content={"type": "error", "error": f"Missing required field: {field}"},
                        timestamp=datetime.now(),
                    )
                    return

            stream_id = stream_config["stream_id"]

            # Initialize stream monitoring
            self.data_buffers[stream_id] = deque(maxlen=self.anomaly_config["window_size"])
            self.feature_buffers[stream_id] = deque(maxlen=self.anomaly_config["window_size"])

            # Save stream configuration
            await self._save_stream_config(stream_config)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "stream_registered",
                    "stream_id": stream_id,
                    "status": "monitoring_active",
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Stream registration failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _save_stream_config(self, stream_config: dict[str, Any]):
        """
        Save stream configuration to database
        """
        try:
            async with get_db_session() as session:
                stream_entry = DataStream(
                    stream_id=stream_config["stream_id"],
                    feature_columns=json.dumps(stream_config["feature_columns"]),
                    data_source=stream_config["data_source"],
                    config=json.dumps(stream_config),
                    created_at=datetime.now(),
                    status="active",
                )

                session.add(stream_entry)
                await session.commit()

        except Exception as e:
            logger.error(f"Stream config save failed: {e}")

    async def _handle_anomaly_detection(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle manual anomaly detection request
        """
        try:
            stream_id = message.content.get("stream_id")
            data_points = message.content.get("data_points", [])

            if not stream_id or stream_id not in self.data_buffers:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Stream not found"},
                    timestamp=datetime.now(),
                )
                return

            # Add data points to buffer
            for data_point in data_points:
                self.data_buffers[stream_id].append(data_point)

            # Perform detection
            feature_matrix = np.array(list(self.data_buffers[stream_id]))
            anomaly_results = {}

            for method in self.anomaly_config["detection_methods"]:
                try:
                    scores = await self._detect_anomalies_method(feature_matrix, method, stream_id)
                    anomaly_results[method] = scores
                except Exception as e:
                    logger.error(f"Manual detection failed for method {method}: {e}")

            ensemble_score = self._combine_anomaly_scores(anomaly_results)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "anomaly_detection_response",
                    "stream_id": stream_id,
                    "ensemble_score": ensemble_score,
                    "method_results": anomaly_results,
                    "anomaly_detected": ensemble_score
                    > self.anomaly_config["threshold_sensitivity"],
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Manual anomaly detection failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_anomaly_analysis(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle anomaly analysis request
        """
        try:
            anomaly_id = message.content.get("anomaly_id")

            if not anomaly_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Anomaly ID required"},
                    timestamp=datetime.now(),
                )
                return

            # Analyze anomaly (placeholder - would query database)
            analysis = await self._analyze_anomaly_details(anomaly_id)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "anomaly_analysis_response",
                    "anomaly_id": anomaly_id,
                    "analysis": analysis,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Anomaly analysis failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _analyze_anomaly_details(self, anomaly_id: str) -> dict[str, Any]:
        """
        Analyze detailed anomaly information
        """
        try:
            # Placeholder analysis - would query actual anomaly data
            return {
                "anomaly_id": anomaly_id,
                "root_cause_analysis": "Data distribution shift detected",
                "impact_assessment": "Medium impact on system performance",
                "recommended_actions": [
                    "Review data quality",
                    "Update model thresholds",
                    "Monitor closely for 24 hours",
                ],
                "confidence_score": 0.85,
            }

        except Exception as e:
            logger.error(f"Anomaly details analysis failed: {e}")
            return {"error": str(e)}

    async def _handle_anomaly_history(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle anomaly history request
        """
        try:
            stream_id = message.content.get("stream_id")
            limit = message.content.get("limit", 50)

            if not stream_id or stream_id not in self.anomaly_history:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Stream not found"},
                    timestamp=datetime.now(),
                )
                return

            # Get recent anomaly history
            history = self.anomaly_history[stream_id][-limit:]

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "anomaly_history_response",
                    "stream_id": stream_id,
                    "history": history,
                    "total_count": len(self.anomaly_history[stream_id]),
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Anomaly history retrieval failed: {e}")
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
        Handle detection model update request
        """
        try:
            stream_id = message.content.get("stream_id")
            model_updates = message.content.get("model_updates", {})

            if not stream_id or stream_id not in self.models:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Stream not found"},
                    timestamp=datetime.now(),
                )
                return

            # Update model parameters
            for method, params in model_updates.items():
                if method in self.models:
                    # Update model parameters (simplified)
                    if hasattr(self.models[method], "set_params"):
                        self.models[method].set_params(**params)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "model_updated",
                    "stream_id": stream_id,
                    "updated_methods": list(model_updates.keys()),
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Model update failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_data_point(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle incoming data point for real-time monitoring
        """
        try:
            stream_id = message.content.get("stream_id")
            data_point = message.content.get("data_point")

            if not stream_id or stream_id not in self.data_buffers:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Stream not found"},
                    timestamp=datetime.now(),
                )
                return

            # Add data point to buffer
            self.data_buffers[stream_id].append(data_point)

            # Immediate anomaly check
            if len(self.data_buffers[stream_id]) >= 10:
                feature_matrix = np.array(list(self.data_buffers[stream_id]))
                anomaly_results = {}

                for method in ["statistical", "time_series"]:  # Quick methods for real-time
                    try:
                        if method == "statistical":
                            scores = self._statistical_anomaly_detection(
                                feature_matrix[-10:]
                            )  # Last 10 points
                        elif method == "time_series":
                            scores = self._time_series_anomaly_detection(
                                feature_matrix[-20:]
                            )  # Last 20 points

                        anomaly_results[method] = {
                            "scores": scores.tolist(),
                            "anomaly_count": int(np.sum(scores)),
                            "anomaly_ratio": float(np.mean(scores)),
                        }
                    except Exception as e:
                        logger.error(f"Real-time detection failed for method {method}: {e}")

                ensemble_score = self._combine_anomaly_scores(anomaly_results)

                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "data_point_processed",
                        "stream_id": stream_id,
                        "anomaly_score": ensemble_score,
                        "is_anomaly": ensemble_score > self.anomaly_config["threshold_sensitivity"],
                    },
                    timestamp=datetime.now(),
                )
            else:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "data_point_processed",
                        "stream_id": stream_id,
                        "status": "buffer_filling",
                        "buffer_size": len(self.data_buffers[stream_id]),
                    },
                    timestamp=datetime.now(),
                )

        except Exception as e:
            logger.error(f"Data point processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )


# ========== TEST ==========
if __name__ == "__main__":

    async def test_anomaly_detection_agent():
        # Initialize anomaly detection agent
        agent = AnomalyDetectionAgent()
        await agent.start()

        # Test stream registration
        register_message = AgentMessage(
            id="test_register",
            from_agent="test",
            to_agent="anomaly_detection_agent",
            content={
                "type": "register_data_stream",
                "stream_config": {
                    "stream_id": "test_stream_123",
                    "feature_columns": ["feature1", "feature2", "feature3"],
                    "data_source": "test_database",
                },
            },
            timestamp=datetime.now(),
        )

        print("Testing anomaly detection agent...")
        async for response in agent.process_message(register_message):
            print(f"Registration response: {response.content.get('type')}")
            if response.content.get("type") == "stream_registered":
                print(f"Stream registered: {response.content.get('stream_id')}")

        # Test data point processing
        for i in range(15):
            # Generate normal data with occasional anomalies
            if i == 10:  # Inject anomaly
                data_point = [10.0, 20.0, 30.0]  # Anomalous values
            else:
                data_point = [1.0, 2.0, 3.0]  # Normal values

            data_message = AgentMessage(
                id=f"test_data_{i}",
                from_agent="test",
                to_agent="anomaly_detection_agent",
                content={
                    "type": "process_data_point",
                    "stream_id": "test_stream_123",
                    "data_point": data_point,
                },
                timestamp=datetime.now(),
            )

            async for response in agent.process_message(data_message):
                if response.content.get("type") == "data_point_processed":
                    anomaly_score = response.content.get("anomaly_score", 0)
                    is_anomaly = response.content.get("is_anomaly", False)
                    print(f"Data point {i}: score={anomaly_score:.3f}, anomaly={is_anomaly}")

        # Test anomaly history
        history_message = AgentMessage(
            id="test_history",
            from_agent="test",
            to_agent="anomaly_detection_agent",
            content={"type": "get_anomaly_history", "stream_id": "test_stream_123", "limit": 10},
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(history_message):
            print(f"History response: {response.content.get('type')}")
            if response.content.get("type") == "anomaly_history_response":
                history = response.content.get("history", [])
                print(f"Found {len(history)} anomaly records")

        # Stop agent
        await agent.stop()
        print("Anomaly detection agent test completed")

    # Run test
    asyncio.run(test_anomaly_detection_agent())
