"""
Self Improvement Agent: Drift detection and model improvement
Continuously monitors model performance and triggers retraining when performance degrades
"""

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from typing import Any

import numpy as np
from scipy.stats import ks_2samp
from sklearn.ensemble import IsolationForest
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.preprocessing import StandardScaler

from ..agents.base_agent import AgentMessage, BaseAgent
from ..agents.lora_trainer_agent import LoRATrainerAgent
from ..api.database import get_db_session
from ..api.models import DriftDetection, ModelMetrics

logger = logging.getLogger(__name__)


class SelfImprovementAgent(BaseAgent):
    """
    Self Improvement Agent for continuous model monitoring and improvement
    Detects performance drift and triggers automatic model retraining
    """

    def __init__(
        self, agent_id: str = "self_improvement_agent", config: dict[str, Any] | None = None
    ):
        super().__init__(agent_id, config or {})

        # Drift detection configuration
        self.drift_config = {
            "monitoring_interval": self.config.get("monitoring_interval", 3600),  # seconds
            "drift_threshold": self.config.get("drift_threshold", 0.1),  # 10% change
            "min_samples_for_drift": self.config.get("min_samples_for_drift", 100),
            "performance_window": self.config.get("performance_window", 7),  # days
            "retraining_trigger_threshold": self.config.get(
                "retraining_trigger_threshold", 0.15
            ),  # 15% degradation
            "confidence_interval": self.config.get("confidence_interval", 0.95),
        }

        # Model monitoring
        self.monitored_models = {}
        self.performance_history = defaultdict(list)
        self.drift_history = []

        # Anomaly detection
        self.anomaly_detector = None
        self.scaler = StandardScaler()

        # Retraining coordination
        self.lora_trainer = LoRATrainerAgent()

        # Performance baselines
        self.baseline_metrics = {}
        self.metric_thresholds = {
            "f1_score": {"warning": 0.05, "critical": 0.1},
            "precision": {"warning": 0.05, "critical": 0.1},
            "recall": {"warning": 0.05, "critical": 0.1},
            "accuracy": {"warning": 0.03, "critical": 0.08},
        }

        # Background monitoring task
        self.monitoring_task = None

        logger.info(f"Self Improvement Agent initialized: {agent_id}")

    async def start(self):
        """
        Start the self improvement agent
        """
        await super().start()

        # Start monitoring loop
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())

        # Initialize anomaly detector
        await self._initialize_anomaly_detector()

        logger.info("Self improvement monitoring started")

    async def stop(self):
        """
        Stop the self improvement agent
        """
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        await super().stop()
        logger.info("Self improvement agent stopped")

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process self improvement requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "register_model_for_monitoring":
                async for response in self._handle_model_registration(message):
                    yield response

            elif message_type == "check_model_performance":
                async for response in self._handle_performance_check(message):
                    yield response

            elif message_type == "detect_drift":
                async for response in self._handle_drift_detection(message):
                    yield response

            elif message_type == "trigger_retraining":
                async for response in self._handle_retraining_trigger(message):
                    yield response

            elif message_type == "analyze_performance_trends":
                async for response in self._handle_performance_analysis(message):
                    yield response

            elif message_type == "update_baseline_metrics":
                async for response in self._handle_baseline_update(message):
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
            logger.error(f"Self improvement processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _monitoring_loop(self):
        """
        Continuous model performance monitoring loop
        """
        try:
            while True:
                try:
                    # Monitor all registered models
                    for model_id in self.monitored_models:
                        await self._monitor_model_performance(model_id)

                    # Check for performance degradation
                    await self._check_performance_degradation()

                    # Trigger retraining if needed
                    await self._trigger_automatic_retraining()

                except Exception as e:
                    logger.error(f"Monitoring loop error: {e}")

                # Wait for next monitoring cycle
                await asyncio.sleep(self.drift_config["monitoring_interval"])

        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled")
            raise

    async def _initialize_anomaly_detector(self):
        """
        Initialize anomaly detection model
        """
        try:
            # Initialize Isolation Forest for anomaly detection
            self.anomaly_detector = IsolationForest(
                n_estimators=100, contamination=0.1, random_state=42
            )

            logger.info("Anomaly detector initialized")

        except Exception as e:
            logger.error(f"Anomaly detector initialization failed: {e}")

    async def _monitor_model_performance(self, model_id: str):
        """
        Monitor performance of a specific model
        """
        try:
            self.monitored_models[model_id]

            # Get recent predictions and ground truth
            recent_data = await self._get_recent_model_data(model_id)

            if not recent_data or len(recent_data) < self.drift_config["min_samples_for_drift"]:
                return

            # Calculate current performance metrics
            current_metrics = self._calculate_performance_metrics(recent_data)

            # Store performance history
            self.performance_history[model_id].append(
                {
                    "timestamp": datetime.now(),
                    "metrics": current_metrics,
                    "sample_count": len(recent_data),
                }
            )

            # Keep only recent history (last 30 days)
            cutoff_date = datetime.now() - timedelta(days=30)
            self.performance_history[model_id] = [
                entry
                for entry in self.performance_history[model_id]
                if entry["timestamp"] > cutoff_date
            ]

            # Check for drift
            drift_detected = await self._detect_performance_drift(model_id, current_metrics)

            if drift_detected:
                await self._handle_drift_detection(model_id, current_metrics)

        except Exception as e:
            logger.error(f"Model performance monitoring failed for {model_id}: {e}")

    async def _get_recent_model_data(self, model_id: str) -> list[dict[str, Any]]:
        """
        Get recent prediction data for model evaluation
        """
        try:
            # Query recent predictions from database
            async with get_db_session():
                # This would query actual prediction logs
                # For now, generate mock data
                mock_data = self._generate_mock_prediction_data()
                return mock_data

        except Exception as e:
            logger.error(f"Recent model data retrieval failed: {e}")
            return []

    def _generate_mock_prediction_data(self) -> list[dict[str, Any]]:
        """
        Generate mock prediction data for testing
        """
        np.random.seed(42)
        n_samples = 200

        # Generate realistic-looking predictions
        true_labels = np.random.choice([0, 1], n_samples, p=[0.6, 0.4])
        predicted_labels = true_labels.copy()

        # Add some noise (misclassifications)
        noise_indices = np.random.choice(n_samples, int(n_samples * 0.1), replace=False)
        predicted_labels[noise_indices] = 1 - predicted_labels[noise_indices]

        # Add prediction probabilities
        probabilities = np.random.beta(2, 2, n_samples)  # Beta distribution for probabilities

        return [
            {
                "true_label": int(true_labels[i]),
                "predicted_label": int(predicted_labels[i]),
                "probability": float(probabilities[i]),
                "timestamp": datetime.now() - timedelta(minutes=i),
            }
            for i in range(n_samples)
        ]

    def _calculate_performance_metrics(
        self, prediction_data: list[dict[str, Any]]
    ) -> dict[str, float]:
        """
        Calculate performance metrics from prediction data
        """
        try:
            true_labels = [item["true_label"] for item in prediction_data]
            predicted_labels = [item["predicted_label"] for item in prediction_data]

            metrics = {
                "accuracy": accuracy_score(true_labels, predicted_labels),
                "precision": precision_score(
                    true_labels, predicted_labels, average="weighted", zero_division=0
                ),
                "recall": recall_score(
                    true_labels, predicted_labels, average="weighted", zero_division=0
                ),
                "f1_score": f1_score(
                    true_labels, predicted_labels, average="weighted", zero_division=0
                ),
            }

            return metrics

        except Exception as e:
            logger.error(f"Performance metrics calculation failed: {e}")
            return {"accuracy": 0, "precision": 0, "recall": 0, "f1_score": 0}

    async def _detect_performance_drift(
        self, model_id: str, current_metrics: dict[str, float]
    ) -> bool:
        """
        Detect performance drift using statistical tests
        """
        try:
            history = self.performance_history[model_id]

            if len(history) < 2:
                return False

            # Get baseline metrics (average of recent history)
            baseline_metrics = self._calculate_baseline_metrics(history)

            # Perform statistical tests for each metric
            drift_indicators = []

            for metric_name in ["f1_score", "precision", "recall", "accuracy"]:
                current_value = current_metrics.get(metric_name, 0)
                baseline_value = baseline_metrics.get(metric_name, 0)

                # Calculate relative change
                if baseline_value > 0:
                    relative_change = abs(current_value - baseline_value) / baseline_value
                    drift_indicators.append(relative_change > self.drift_config["drift_threshold"])
                else:
                    drift_indicators.append(False)

            # Check for distribution drift using KS test
            recent_predictions = []
            for entry in history[-10:]:  # Last 10 measurements
                # This would use actual prediction distributions
                recent_predictions.extend([entry["metrics"].get("f1_score", 0)])

            if len(recent_predictions) >= 10:
                # Perform KS test between recent and baseline distributions
                baseline_dist = [h["metrics"].get("f1_score", 0) for h in history[:-10]]
                if baseline_dist:
                    ks_statistic, p_value = ks_2samp(recent_predictions, baseline_dist)
                    distribution_drift = p_value < 0.05  # Significant difference
                    drift_indicators.append(distribution_drift)

            # Overall drift detection
            drift_detected = any(drift_indicators)

            if drift_detected:
                # Record drift event
                drift_record = {
                    "model_id": model_id,
                    "timestamp": datetime.now(),
                    "current_metrics": current_metrics,
                    "baseline_metrics": baseline_metrics,
                    "drift_indicators": drift_indicators,
                    "severity": "high" if sum(drift_indicators) > 2 else "medium",
                }

                self.drift_history.append(drift_record)

                # Save to database
                await self._save_drift_detection(drift_record)

            return drift_detected

        except Exception as e:
            logger.error(f"Performance drift detection failed: {e}")
            return False

    def _calculate_baseline_metrics(self, history: list[dict[str, Any]]) -> dict[str, float]:
        """
        Calculate baseline metrics from performance history
        """
        try:
            if not history:
                return {"f1_score": 0, "precision": 0, "recall": 0, "accuracy": 0}

            # Use weighted average (more recent entries have higher weight)
            metrics_sum = defaultdict(float)
            weights_sum = 0

            for i, entry in enumerate(history):
                weight = i + 1  # Linear weighting
                weights_sum += weight

                for metric_name, value in entry["metrics"].items():
                    metrics_sum[metric_name] += value * weight

            baseline = {}
            for metric_name in metrics_sum:
                baseline[metric_name] = metrics_sum[metric_name] / weights_sum

            return dict(baseline)

        except Exception as e:
            logger.error(f"Baseline metrics calculation failed: {e}")
            return {"f1_score": 0, "precision": 0, "recall": 0, "accuracy": 0}

    async def _handle_drift_detection(self, model_id: str, current_metrics: dict[str, float]):
        """
        Handle detected performance drift
        """
        try:
            logger.warning(f"Performance drift detected for model {model_id}")

            # Check if retraining should be triggered
            degradation_level = await self._assess_degradation_level(model_id, current_metrics)

            if degradation_level >= self.drift_config["retraining_trigger_threshold"]:
                await self._trigger_model_retraining(
                    model_id, f"Performance degradation: {degradation_level:.2%}"
                )

        except Exception as e:
            logger.error(f"Drift detection handling failed: {e}")

    async def _assess_degradation_level(
        self, model_id: str, current_metrics: dict[str, float]
    ) -> float:
        """
        Assess the level of performance degradation
        """
        try:
            baseline = self.baseline_metrics.get(model_id, {})
            if not baseline:
                return 0.0

            # Calculate weighted degradation across all metrics
            total_degradation = 0
            total_weight = 0

            metric_weights = {"f1_score": 0.4, "precision": 0.2, "recall": 0.2, "accuracy": 0.2}

            for metric_name, weight in metric_weights.items():
                current_value = current_metrics.get(metric_name, 0)
                baseline_value = baseline.get(metric_name, 0)

                if baseline_value > 0:
                    degradation = max(0, baseline_value - current_value) / baseline_value
                    total_degradation += degradation * weight
                    total_weight += weight

            return total_degradation / total_weight if total_weight > 0 else 0

        except Exception as e:
            logger.error(f"Degradation assessment failed: {e}")
            return 0

    async def _trigger_model_retraining(self, model_id: str, reason: str):
        """
        Trigger automatic model retraining
        """
        try:
            logger.info(f"Triggering retraining for model {model_id}: {reason}")

            model_config = self.monitored_models[model_id]

            # Prepare retraining configuration
            retraining_config = {
                "base_model": model_config["base_model"],
                "task_type": model_config["task_type"],
                "dataset_path": model_config["dataset_path"],
                "trigger_reason": reason,
                "drift_detected": True,
            }

            # Start retraining via LoRA trainer
            training_message = AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent="lora_trainer_agent",
                content={"type": "start_lora_training", "training_config": retraining_config},
                timestamp=datetime.now(),
            )

            # Process retraining request
            async for response in self.lora_trainer.process_message(training_message):
                if response.content.get("type") == "training_started":
                    training_id = response.content.get("training_id")
                    logger.info(
                        f"Retraining started for model {model_id}, training ID: {training_id}"
                    )

                    # Update model status
                    model_config["last_retraining"] = datetime.now()
                    model_config["retraining_reason"] = reason

                elif response.content.get("type") == "error":
                    logger.error(
                        f"Retraining failed to start for model {model_id}: {response.content.get('error')}"
                    )

        except Exception as e:
            logger.error(f"Model retraining trigger failed: {e}")

    async def _check_performance_degradation(self):
        """
        Check for gradual performance degradation across all models
        """
        try:
            for model_id in self.monitored_models:
                history = self.performance_history[model_id]

                if len(history) < 10:  # Need sufficient history
                    continue

                # Calculate performance trend
                recent_metrics = [entry["metrics"]["f1_score"] for entry in history[-10:]]
                older_metrics = [entry["metrics"]["f1_score"] for entry in history[-20:-10]]

                if older_metrics:
                    recent_avg = np.mean(recent_metrics)
                    older_avg = np.mean(older_metrics)

                    degradation = (older_avg - recent_avg) / older_avg

                    if degradation > self.drift_config["retraining_trigger_threshold"]:
                        await self._trigger_model_retraining(
                            model_id, f"Gradual performance degradation: {degradation:.2%}"
                        )

        except Exception as e:
            logger.error(f"Performance degradation check failed: {e}")

    async def _trigger_automatic_retraining(self):
        """
        Trigger retraining for models that haven't been updated recently
        """
        try:
            max_age_days = self.config.get("max_model_age_days", 30)
            cutoff_date = datetime.now() - timedelta(days=max_age_days)

            for model_id, model_config in self.monitored_models.items():
                last_updated = model_config.get("last_updated")

                if not last_updated or last_updated < cutoff_date:
                    await self._trigger_model_retraining(
                        model_id, f"Model age exceeds {max_age_days} days"
                    )

        except Exception as e:
            logger.error(f"Automatic retraining trigger failed: {e}")

    async def _save_drift_detection(self, drift_record: dict[str, Any]):
        """
        Save drift detection to database
        """
        try:
            async with get_db_session() as session:
                drift_entry = DriftDetection(
                    model_id=drift_record["model_id"],
                    drift_timestamp=drift_record["timestamp"],
                    current_metrics=json.dumps(drift_record["current_metrics"]),
                    baseline_metrics=json.dumps(drift_record["baseline_metrics"]),
                    severity=drift_record["severity"],
                    detected_at=datetime.now(),
                )

                session.add(drift_entry)
                await session.commit()

        except Exception as e:
            logger.error(f"Drift detection save failed: {e}")

    async def _handle_model_registration(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle model registration for monitoring
        """
        try:
            model_config = message.content.get("model_config", {})

            required_fields = ["model_id", "base_model", "task_type", "dataset_path"]
            for field in required_fields:
                if field not in model_config:
                    yield AgentMessage(
                        id=str(uuid.uuid4()),
                        from_agent=self.agent_id,
                        to_agent=message.from_agent,
                        content={"type": "error", "error": f"Missing required field: {field}"},
                        timestamp=datetime.now(),
                    )
                    return

            model_id = model_config["model_id"]

            # Register model
            self.monitored_models[model_id] = {
                **model_config,
                "registered_at": datetime.now(),
                "last_updated": datetime.now(),
                "status": "active",
            }

            # Initialize baseline metrics
            await self._initialize_baseline_metrics(model_id, model_config)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "model_registered",
                    "model_id": model_id,
                    "status": "monitoring_active",
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Model registration failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _initialize_baseline_metrics(self, model_id: str, model_config: dict[str, Any]):
        """
        Initialize baseline metrics for a new model
        """
        try:
            # Get initial performance data
            initial_data = await self._get_recent_model_data(model_id)

            if initial_data:
                baseline_metrics = self._calculate_performance_metrics(initial_data)
                self.baseline_metrics[model_id] = baseline_metrics

                # Save to database
                async with get_db_session() as session:
                    metrics_entry = ModelMetrics(
                        model_id=model_id,
                        metric_type="baseline",
                        f1_score=baseline_metrics.get("f1_score"),
                        precision=baseline_metrics.get("precision"),
                        recall=baseline_metrics.get("recall"),
                        accuracy=baseline_metrics.get("accuracy"),
                        recorded_at=datetime.now(),
                    )

                    session.add(metrics_entry)
                    await session.commit()

        except Exception as e:
            logger.error(f"Baseline metrics initialization failed: {e}")

    async def _handle_performance_check(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle model performance check request
        """
        try:
            model_id = message.content.get("model_id")

            if not model_id or model_id not in self.monitored_models:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Model not found"},
                    timestamp=datetime.now(),
                )
                return

            # Get current performance
            performance_data = await self._get_model_performance_summary(model_id)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "performance_check_response",
                    "model_id": model_id,
                    "performance": performance_data,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Performance check failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _get_model_performance_summary(self, model_id: str) -> dict[str, Any]:
        """
        Get comprehensive performance summary for a model
        """
        try:
            history = self.performance_history[model_id]

            if not history:
                return {"status": "no_data"}

            # Calculate current metrics
            latest_entry = history[-1]
            current_metrics = latest_entry["metrics"]

            # Calculate trends
            trends = self._calculate_performance_trends(history)

            # Get drift history
            recent_drifts = [
                drift for drift in self.drift_history if drift["model_id"] == model_id
            ][-5:]  # Last 5 drift events

            return {
                "current_metrics": current_metrics,
                "baseline_metrics": self.baseline_metrics.get(model_id, {}),
                "performance_trend": trends,
                "drift_events": len(recent_drifts),
                "last_updated": latest_entry["timestamp"].isoformat(),
                "monitoring_status": "active",
            }

        except Exception as e:
            logger.error(f"Performance summary generation failed: {e}")
            return {"error": str(e)}

    def _calculate_performance_trends(self, history: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Calculate performance trends from history
        """
        try:
            if len(history) < 2:
                return {"trend": "insufficient_data"}

            # Calculate trend for each metric
            trends = {}
            metrics_to_track = ["f1_score", "precision", "recall", "accuracy"]

            for metric in metrics_to_track:
                values = [entry["metrics"].get(metric, 0) for entry in history]

                if len(values) >= 2:
                    # Simple linear trend
                    slope = np.polyfit(range(len(values)), values, 1)[0]

                    if slope > 0.001:
                        trends[metric] = "improving"
                    elif slope < -0.001:
                        trends[metric] = "degrading"
                    else:
                        trends[metric] = "stable"
                else:
                    trends[metric] = "unknown"

            return trends

        except Exception as e:
            logger.error(f"Performance trend calculation failed: {e}")
            return {"trend": "error"}

    async def _handle_drift_detection(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle manual drift detection request
        """
        try:
            model_id = message.content.get("model_id")

            if not model_id or model_id not in self.monitored_models:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Model not found"},
                    timestamp=datetime.now(),
                )
                return

            # Perform drift detection
            recent_data = await self._get_recent_model_data(model_id)
            current_metrics = self._calculate_performance_metrics(recent_data)

            drift_detected = await self._detect_performance_drift(model_id, current_metrics)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "drift_detection_response",
                    "model_id": model_id,
                    "drift_detected": drift_detected,
                    "current_metrics": current_metrics,
                    "baseline_metrics": self.baseline_metrics.get(model_id, {}),
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Drift detection handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_retraining_trigger(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle manual retraining trigger request
        """
        try:
            model_id = message.content.get("model_id")
            reason = message.content.get("reason", "Manual trigger")

            if not model_id or model_id not in self.monitored_models:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Model not found"},
                    timestamp=datetime.now(),
                )
                return

            # Trigger retraining
            await self._trigger_model_retraining(model_id, reason)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "retraining_triggered",
                    "model_id": model_id,
                    "reason": reason,
                    "status": "initiated",
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Retraining trigger failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_performance_analysis(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle performance trend analysis request
        """
        try:
            model_id = message.content.get("model_id")
            analysis_period_days = message.content.get("analysis_period_days", 30)

            if not model_id or model_id not in self.monitored_models:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Model not found"},
                    timestamp=datetime.now(),
                )
                return

            # Analyze performance trends
            analysis = await self._analyze_performance_trends_detailed(
                model_id, analysis_period_days
            )

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "performance_analysis_response",
                    "model_id": model_id,
                    "analysis_period_days": analysis_period_days,
                    "analysis": analysis,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Performance analysis failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _analyze_performance_trends_detailed(
        self, model_id: str, period_days: int
    ) -> dict[str, Any]:
        """
        Perform detailed performance trend analysis
        """
        try:
            history = self.performance_history[model_id]
            cutoff_date = datetime.now() - timedelta(days=period_days)

            # Filter history for the analysis period
            period_history = [entry for entry in history if entry["timestamp"] > cutoff_date]

            if not period_history:
                return {"status": "insufficient_data"}

            # Calculate detailed metrics
            analysis = {
                "period_days": period_days,
                "data_points": len(period_history),
                "metrics_summary": {},
                "anomalies_detected": 0,
                "trend_direction": {},
                "volatility": {},
            }

            # Analyze each metric
            for metric_name in ["f1_score", "precision", "recall", "accuracy"]:
                values = [entry["metrics"].get(metric_name, 0) for entry in period_history]

                if values:
                    analysis["metrics_summary"][metric_name] = {
                        "mean": float(np.mean(values)),
                        "std": float(np.std(values)),
                        "min": float(np.min(values)),
                        "max": float(np.max(values)),
                        "trend": (
                            "improving"
                            if values[-1] > values[0]
                            else "degrading"
                            if values[-1] < values[0]
                            else "stable"
                        ),
                    }

                    # Calculate volatility (coefficient of variation)
                    if np.mean(values) > 0:
                        analysis["volatility"][metric_name] = float(
                            np.std(values) / np.mean(values)
                        )

            # Detect anomalies using Isolation Forest
            if len(period_history) >= 10:
                # Prepare feature matrix
                feature_matrix = []
                for entry in period_history:
                    features = [
                        entry["metrics"].get("f1_score", 0),
                        entry["metrics"].get("precision", 0),
                        entry["metrics"].get("recall", 0),
                        entry["metrics"].get("accuracy", 0),
                    ]
                    feature_matrix.append(features)

                # Fit and predict anomalies
                if self.anomaly_detector:
                    scaled_features = self.scaler.fit_transform(feature_matrix)
                    anomaly_scores = self.anomaly_detector.fit_predict(scaled_features)
                    analysis["anomalies_detected"] = int(np.sum(anomaly_scores == -1))

            return analysis

        except Exception as e:
            logger.error(f"Detailed performance analysis failed: {e}")
            return {"error": str(e)}

    async def _handle_baseline_update(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle baseline metrics update request
        """
        try:
            model_id = message.content.get("model_id")
            new_baseline = message.content.get("baseline_metrics", {})

            if not model_id or model_id not in self.monitored_models:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Model not found"},
                    timestamp=datetime.now(),
                )
                return

            # Update baseline metrics
            self.baseline_metrics[model_id] = new_baseline

            # Save to database
            async with get_db_session() as session:
                metrics_entry = ModelMetrics(
                    model_id=model_id,
                    metric_type="baseline_update",
                    f1_score=new_baseline.get("f1_score"),
                    precision=new_baseline.get("precision"),
                    recall=new_baseline.get("recall"),
                    accuracy=new_baseline.get("accuracy"),
                    recorded_at=datetime.now(),
                )

                session.add(metrics_entry)
                await session.commit()

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "baseline_updated",
                    "model_id": model_id,
                    "new_baseline": new_baseline,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Baseline update failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )


# ========== TEST ==========
if __name__ == "__main__":

    async def test_self_improvement_agent():
        # Initialize self improvement agent
        agent = SelfImprovementAgent()
        await agent.start()

        # Test model registration
        register_message = AgentMessage(
            id="test_register",
            from_agent="test",
            to_agent="self_improvement_agent",
            content={
                "type": "register_model_for_monitoring",
                "model_config": {
                    "model_id": "test_model_123",
                    "base_model": "bert-base-uncased",
                    "task_type": "classification",
                    "dataset_path": "./data/test_dataset.csv",
                },
            },
            timestamp=datetime.now(),
        )

        print("Testing self improvement agent...")
        async for response in agent.process_message(register_message):
            print(f"Registration response: {response.content.get('type')}")
            if response.content.get("type") == "model_registered":
                print(f"Model registered: {response.content.get('model_id')}")

        # Test performance check
        check_message = AgentMessage(
            id="test_check",
            from_agent="test",
            to_agent="self_improvement_agent",
            content={"type": "check_model_performance", "model_id": "test_model_123"},
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(check_message):
            print(f"Performance check response: {response.content.get('type')}")

        # Stop agent
        await agent.stop()
        print("Self improvement agent test completed")

    # Run test
    asyncio.run(test_self_improvement_agent())
