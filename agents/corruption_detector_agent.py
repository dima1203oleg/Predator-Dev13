"""
Corruption Detector Agent: Pattern analysis for corruption detection
Uses ML models to identify suspicious customs activities
"""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from ..agents.base_agent import AgentMessage, BaseAgent
from ..api.database import get_db_session
from ..api.models import Company, CorruptionAlert, CustomsData
from ..model_registry import ModelRegistry

logger = logging.getLogger(__name__)


class CorruptionDetectorAgent(BaseAgent):
    """
    Corruption Detector Agent for identifying suspicious patterns
    Uses machine learning to detect potential corruption in customs data
    """

    def __init__(
        self, agent_id: str = "corruption_detector_agent", config: dict[str, Any] | None = None
    ):
        super().__init__(agent_id, config or {})

        # Detection settings
        self.confidence_threshold = self.config.get("confidence_threshold", 0.8)
        self.alert_severity_levels = self.config.get(
            "alert_severity_levels", {"low": 0.6, "medium": 0.75, "high": 0.9, "critical": 0.95}
        )

        # Model settings
        self.use_isolation_forest = self.config.get("use_isolation_forest", True)
        self.use_supervised_model = self.config.get("use_supervised_model", True)
        self.model_update_frequency = self.config.get("model_update_frequency", 7)  # days

        # Risk patterns
        self.risk_patterns = self._load_risk_patterns()

        # Model registry
        self.model_registry = ModelRegistry()

        # Cached models
        self.models_cache = {}
        self.scalers_cache = {}
        self.last_model_update = None

        logger.info(f"Corruption Detector Agent initialized: {agent_id}")

    def _load_risk_patterns(self) -> dict[str, Any]:
        """
        Load predefined risk patterns for corruption detection
        """
        return {
            "value_anomalies": {
                "description": "Unusual value declarations",
                "patterns": [
                    "value_too_high",  # Values significantly above market rates
                    "value_too_low",  # Values significantly below market rates
                    "round_numbers",  # Suspiciously round numbers
                    "value_spikes",  # Sudden spikes in declared values
                ],
            },
            "frequency_anomalies": {
                "description": "Unusual transaction frequencies",
                "patterns": [
                    "high_frequency",  # Too many declarations in short period
                    "bulk_operations",  # Large bulk operations
                    "timing_patterns",  # Suspicious timing patterns
                ],
            },
            "relationship_anomalies": {
                "description": "Suspicious company relationships",
                "patterns": [
                    "connected_companies",  # Companies with complex ownership structures
                    "shell_companies",  # Potential shell company indicators
                    "beneficial_owners",  # Hidden beneficial ownership
                ],
            },
            "documentation_anomalies": {
                "description": "Documentation irregularities",
                "patterns": [
                    "missing_docs",  # Missing required documentation
                    "inconsistent_data",  # Inconsistencies in declaration data
                    "altered_docs",  # Signs of document alteration
                ],
            },
            "geographic_anomalies": {
                "description": "Geographic irregularities",
                "patterns": [
                    "unusual_routes",  # Unusual trade routes
                    "high_risk_countries",  # Trade with high-risk countries
                    "destination_mismatch",  # Mismatch between origin and destination
                ],
            },
        }

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process corruption detection requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "corruption_scan":
                async for response in self._handle_corruption_scan(message):
                    yield response

            elif message_type == "corruption_analysis":
                async for response in self._handle_corruption_analysis(message):
                    yield response

            elif message_type == "risk_assessment":
                async for response in self._handle_risk_assessment(message):
                    yield response

            elif message_type == "model_update":
                async for response in self._handle_model_update(message):
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
            logger.error(f"Corruption detector processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_corruption_scan(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle corruption scan request
        """
        try:
            # Extract parameters
            scan_filters = message.content.get("filters", {})
            scan_period_days = message.content.get("scan_period_days", 30)
            min_confidence = message.content.get("min_confidence", self.confidence_threshold)

            # Get data for scanning
            scan_data = await self._get_scan_data(scan_filters, scan_period_days)

            if not scan_data:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "corruption_scan_response",
                        "status": "no_data",
                        "message": "No data found for the specified scan period",
                    },
                    timestamp=datetime.now(),
                )
                return

            # Perform corruption detection
            detection_results = await self._detect_corruption(scan_data, min_confidence)

            # Generate alerts
            alerts = await self._generate_corruption_alerts(detection_results)

            # Save alerts to database
            await self._save_corruption_alerts(alerts, message.content.get("user_id"))

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "corruption_scan_response",
                    "status": "completed",
                    "scan_summary": {
                        "total_records_scanned": len(scan_data),
                        "alerts_generated": len(alerts),
                        "high_severity_alerts": len([a for a in alerts if a["severity"] == "high"]),
                        "scan_period_days": scan_period_days,
                    },
                    "alerts": alerts[:50],  # Limit for response size
                    "filters": scan_filters,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Corruption scan failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _get_scan_data(
        self, filters: dict[str, Any], scan_period_days: int
    ) -> list[dict[str, Any]]:
        """
        Get data for corruption scanning
        """
        try:
            async with get_db_session() as session:
                # Calculate date range
                end_date = datetime.now()
                start_date = end_date - timedelta(days=scan_period_days)

                # Build query
                query = (
                    session.query(
                        CustomsData.id,
                        CustomsData.declaration_number,
                        CustomsData.company_id,
                        CustomsData.hs_code,
                        CustomsData.value_usd,
                        CustomsData.quantity,
                        CustomsData.country_origin,
                        CustomsData.declaration_date,
                        Company.company_name,
                        Company.registration_date,
                        Company.activity_type,
                    )
                    .join(Company, CustomsData.company_id == Company.id)
                    .filter(CustomsData.declaration_date.between(start_date, end_date))
                )

                # Apply filters
                if filters.get("company_id"):
                    query = query.filter(CustomsData.company_id == filters["company_id"])

                if filters.get("hs_code"):
                    query = query.filter(CustomsData.hs_code.like(f"{filters['hs_code']}%"))

                if filters.get("country_origin"):
                    query = query.filter(CustomsData.country_origin == filters["country_origin"])

                if filters.get("min_value"):
                    query = query.filter(CustomsData.value_usd >= filters["min_value"])

                # Execute query
                results = await session.execute(query)
                rows = results.fetchall()

                # Convert to dict format
                scan_data = []
                for row in rows:
                    scan_data.append(
                        {
                            "id": row[0],
                            "declaration_number": row[1],
                            "company_id": row[2],
                            "hs_code": row[3],
                            "value_usd": float(row[4]) if row[4] else 0,
                            "quantity": float(row[5]) if row[5] else 0,
                            "country_origin": row[6],
                            "declaration_date": row[7].isoformat() if row[7] else None,
                            "company_name": row[8],
                            "company_registration_date": row[9].isoformat() if row[9] else None,
                            "activity_type": row[10],
                        }
                    )

                return scan_data

        except Exception as e:
            logger.error(f"Scan data retrieval failed: {e}")
            return []

    async def _detect_corruption(
        self, scan_data: list[dict[str, Any]], min_confidence: float
    ) -> list[dict[str, Any]]:
        """
        Detect corruption patterns in the data
        """
        try:
            detection_results = []

            # Convert to DataFrame for analysis
            df = pd.DataFrame(scan_data)

            # Rule-based detection
            rule_based_alerts = self._rule_based_detection(df)
            detection_results.extend(rule_based_alerts)

            # ML-based detection
            if self.use_isolation_forest:
                ml_alerts = await self._ml_based_detection(df, min_confidence)
                detection_results.extend(ml_alerts)

            # Pattern-based detection
            pattern_alerts = self._pattern_based_detection(df)
            detection_results.extend(pattern_alerts)

            # Remove duplicates and filter by confidence
            unique_results = self._deduplicate_alerts(detection_results)
            filtered_results = [r for r in unique_results if r["confidence"] >= min_confidence]

            return filtered_results

        except Exception as e:
            logger.error(f"Corruption detection failed: {e}")
            return []

    def _rule_based_detection(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """
        Rule-based corruption detection
        """
        alerts = []

        try:
            # Rule 1: Round number values (suspicious)
            round_values = df[df["value_usd"] % 1000 == 0]
            for _, row in round_values.iterrows():
                if row["value_usd"] >= 10000:  # Only flag large round numbers
                    alerts.append(
                        {
                            "alert_id": f"round_value_{row['id']}",
                            "declaration_id": row["id"],
                            "company_id": row["company_id"],
                            "alert_type": "value_anomalies",
                            "pattern": "round_numbers",
                            "severity": "low",
                            "confidence": 0.7,
                            "description": f"Round number value: ${row['value_usd']:,.0f}",
                            "evidence": {
                                "value_usd": row["value_usd"],
                                "declaration_number": row["declaration_number"],
                            },
                        }
                    )

            # Rule 2: High frequency declarations
            company_counts = df.groupby("company_id").size()
            high_freq_companies = company_counts[company_counts > company_counts.quantile(0.95)]

            for company_id, count in high_freq_companies.items():
                company_data = df[df["company_id"] == company_id]
                alerts.append(
                    {
                        "alert_id": f"high_freq_{company_id}",
                        "declaration_id": None,
                        "company_id": company_id,
                        "alert_type": "frequency_anomalies",
                        "pattern": "high_frequency",
                        "severity": "medium",
                        "confidence": 0.8,
                        "description": f"High declaration frequency: {count} declarations",
                        "evidence": {
                            "declaration_count": int(count),
                            "company_name": company_data["company_name"].iloc[0],
                            "avg_value": company_data["value_usd"].mean(),
                        },
                    }
                )

            # Rule 3: Value spikes
            df_sorted = df.sort_values("declaration_date")
            df_sorted["value_change"] = df_sorted.groupby("company_id")["value_usd"].pct_change()

            spikes = df_sorted[df_sorted["value_change"] > 5]  # 500% increase
            for _, row in spikes.iterrows():
                alerts.append(
                    {
                        "alert_id": f"value_spike_{row['id']}",
                        "declaration_id": row["id"],
                        "company_id": row["company_id"],
                        "alert_type": "value_anomalies",
                        "pattern": "value_spikes",
                        "severity": "medium",
                        "confidence": 0.75,
                        "description": f"Value spike: {row['value_change']:.1%} increase",
                        "evidence": {
                            "previous_value": row["value_usd"] / (1 + row["value_change"]),
                            "current_value": row["value_usd"],
                            "change_percent": row["value_change"],
                        },
                    }
                )

            # Rule 4: New companies with high values
            df["company_age_days"] = (
                pd.Timestamp.now() - pd.to_datetime(df["company_registration_date"])
            ).dt.days
            new_companies_high_value = df[
                (df["company_age_days"] < 365)  # Less than 1 year old
                & (df["value_usd"] > df["value_usd"].quantile(0.9))  # Top 10% of values
            ]

            for _, row in new_companies_high_value.iterrows():
                alerts.append(
                    {
                        "alert_id": f"new_company_high_value_{row['id']}",
                        "declaration_id": row["id"],
                        "company_id": row["company_id"],
                        "alert_type": "relationship_anomalies",
                        "pattern": "shell_companies",
                        "severity": "high",
                        "confidence": 0.85,
                        "description": f"New company ({row['company_age_days']} days) with high value: ${row['value_usd']:,.0f}",
                        "evidence": {
                            "company_age_days": row["company_age_days"],
                            "value_usd": row["value_usd"],
                            "activity_type": row["activity_type"],
                        },
                    }
                )

        except Exception as e:
            logger.error(f"Rule-based detection failed: {e}")

        return alerts

    async def _ml_based_detection(
        self, df: pd.DataFrame, min_confidence: float
    ) -> list[dict[str, Any]]:
        """
        ML-based corruption detection using isolation forest
        """
        alerts = []

        try:
            # Prepare features for ML
            features_df = self._prepare_ml_features(df)

            if len(features_df) < 100:  # Need minimum data for ML
                return alerts

            # Load or train model
            model_key = "corruption_detector_v1"
            model = await self._get_or_train_model(model_key, features_df)

            if model is None:
                return alerts

            # Get feature matrix
            feature_cols = [
                col
                for col in features_df.columns
                if col.startswith(("value_", "freq_", "ratio_", "age_"))
            ]
            X = features_df[feature_cols].fillna(0)

            # Scale features
            scaler_key = f"{model_key}_scaler"
            scaler = self.scalers_cache.get(scaler_key)
            if scaler:
                X_scaled = scaler.transform(X)
            else:
                X_scaled = X.values

            # Predict anomalies
            anomaly_scores = model.decision_function(X_scaled)
            predictions = model.predict(X_scaled)

            # Convert to confidence scores (isolation forest returns -1 for anomalies)
            confidence_scores = 1 / (1 + np.exp(-anomaly_scores))  # Sigmoid transformation

            # Generate alerts for anomalies
            anomaly_indices = np.where(predictions == -1)[0]

            for idx in anomaly_indices:
                row = features_df.iloc[idx]
                confidence = float(confidence_scores[idx])

                if confidence >= min_confidence:
                    severity = self._calculate_severity(confidence)

                    alerts.append(
                        {
                            "alert_id": f"ml_anomaly_{row['id']}",
                            "declaration_id": row["id"],
                            "company_id": row["company_id"],
                            "alert_type": "value_anomalies",
                            "pattern": "ml_detected_anomaly",
                            "severity": severity,
                            "confidence": confidence,
                            "description": f"ML-detected anomaly (confidence: {confidence:.2%})",
                            "evidence": {
                                "anomaly_score": float(anomaly_scores[idx]),
                                "value_usd": row["value_usd"],
                                "company_name": row["company_name"],
                                "features": {
                                    col: row[col] for col in feature_cols[:5]
                                },  # Top 5 features
                            },
                        }
                    )

        except Exception as e:
            logger.error(f"ML-based detection failed: {e}")

        return alerts

    def _prepare_ml_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare features for ML model
        """
        try:
            features_df = df.copy()

            # Value-based features
            features_df["value_log"] = np.log1p(features_df["value_usd"])
            features_df["value_rounded"] = (features_df["value_usd"] % 1000 == 0).astype(int)

            # Frequency features
            company_freq = features_df.groupby("company_id").size()
            features_df["freq_company_total"] = features_df["company_id"].map(company_freq)

            # Time-based features
            features_df["declaration_hour"] = pd.to_datetime(
                features_df["declaration_date"]
            ).dt.hour
            features_df["is_business_hours"] = (
                features_df["declaration_hour"].between(9, 17).astype(int)
            )

            # Company age features
            features_df["company_age_days"] = (
                pd.Timestamp.now() - pd.to_datetime(features_df["company_registration_date"])
            ).dt.days
            features_df["company_age_months"] = features_df["company_age_days"] / 30
            features_df["is_new_company"] = (features_df["company_age_days"] < 365).astype(int)

            # Ratio features
            hs_code_stats = features_df.groupby("hs_code")["value_usd"].agg(["mean", "std"])
            features_df["hs_code_mean"] = features_df["hs_code"].map(hs_code_stats["mean"])
            features_df["hs_code_std"] = features_df["hs_code"].map(hs_code_stats["std"])
            features_df["value_to_hs_mean_ratio"] = (
                features_df["value_usd"] / features_df["hs_code_mean"]
            )

            # Country risk features (simplified)
            high_risk_countries = ["RU", "CN", "IR", "KP", "SY"]  # Example high-risk countries
            features_df["high_risk_country"] = (
                features_df["country_origin"].isin(high_risk_countries).astype(int)
            )

            return features_df

        except Exception as e:
            logger.error(f"Feature preparation failed: {e}")
            return df

    async def _get_or_train_model(self, model_key: str, features_df: pd.DataFrame):
        """
        Get cached model or train new one
        """
        try:
            # Check if model needs update
            if (
                self.last_model_update
                and (datetime.now() - self.last_model_update).days < self.model_update_frequency
                and model_key in self.models_cache
            ):
                return self.models_cache[model_key]

            # Prepare training data
            feature_cols = [
                col
                for col in features_df.columns
                if col.startswith(("value_", "freq_", "ratio_", "age_", "is_", "high_"))
            ]
            X = features_df[feature_cols].fillna(0)

            # Scale features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # Train isolation forest
            model = IsolationForest(
                n_estimators=100,
                contamination=0.1,
                random_state=42,  # Expected 10% anomalies
            )

            model.fit(X_scaled)

            # Cache model and scaler
            self.models_cache[model_key] = model
            self.scalers_cache[f"{model_key}_scaler"] = scaler
            self.last_model_update = datetime.now()

            logger.info(f"Trained new corruption detection model: {model_key}")
            return model

        except Exception as e:
            logger.error(f"Model training failed: {e}")
            return None

    def _pattern_based_detection(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        """
        Pattern-based corruption detection
        """
        alerts = []

        try:
            # Pattern 1: Companies declaring same values repeatedly
            value_counts = df.groupby(["company_id", "value_usd"]).size()
            repetitive_values = value_counts[value_counts > 5]  # Same value more than 5 times

            for (company_id, value), count in repetitive_values.items():
                company_data = df[df["company_id"] == company_id]
                alerts.append(
                    {
                        "alert_id": f"repetitive_value_{company_id}_{value}",
                        "declaration_id": None,
                        "company_id": company_id,
                        "alert_type": "value_anomalies",
                        "pattern": "repetitive_values",
                        "severity": "medium",
                        "confidence": 0.75,
                        "description": f"Repetitive value declarations: ${value:,.0f} declared {count} times",
                        "evidence": {
                            "value": value,
                            "count": int(count),
                            "company_name": company_data["company_name"].iloc[0],
                        },
                    }
                )

            # Pattern 2: Unusual timing patterns (e.g., always at same time)
            df["declaration_datetime"] = pd.to_datetime(df["declaration_date"])
            df["declaration_minute"] = df["declaration_datetime"].dt.minute

            # Check for declarations at exact same minute
            minute_counts = df.groupby(["company_id", "declaration_minute"]).size()
            suspicious_timing = minute_counts[minute_counts > minute_counts.quantile(0.95)]

            for (company_id, minute), count in suspicious_timing.items():
                if count > 3:  # More than 3 declarations at same minute
                    company_data = df[df["company_id"] == company_id]
                    alerts.append(
                        {
                            "alert_id": f"suspicious_timing_{company_id}_{minute}",
                            "declaration_id": None,
                            "company_id": company_id,
                            "alert_type": "frequency_anomalies",
                            "pattern": "timing_patterns",
                            "severity": "low",
                            "confidence": 0.6,
                            "description": f"Suspicious timing pattern: {count} declarations at minute {minute}",
                            "evidence": {
                                "minute": minute,
                                "count": int(count),
                                "company_name": company_data["company_name"].iloc[0],
                            },
                        }
                    )

        except Exception as e:
            logger.error(f"Pattern-based detection failed: {e}")

        return alerts

    def _deduplicate_alerts(self, alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Remove duplicate alerts
        """
        seen = set()
        unique_alerts = []

        for alert in alerts:
            alert_key = (alert["alert_id"], alert.get("declaration_id"), alert.get("company_id"))

            if alert_key not in seen:
                seen.add(alert_key)
                unique_alerts.append(alert)

        return unique_alerts

    def _calculate_severity(self, confidence: float) -> str:
        """
        Calculate alert severity based on confidence
        """
        if confidence >= self.alert_severity_levels["critical"]:
            return "critical"
        elif confidence >= self.alert_severity_levels["high"]:
            return "high"
        elif confidence >= self.alert_severity_levels["medium"]:
            return "medium"
        else:
            return "low"

    async def _generate_corruption_alerts(
        self, detection_results: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Generate detailed corruption alerts
        """
        try:
            alerts = []

            for result in detection_results:
                alert = {
                    "alert_id": result["alert_id"],
                    "declaration_id": result.get("declaration_id"),
                    "company_id": result.get("company_id"),
                    "alert_type": result["alert_type"],
                    "pattern": result["pattern"],
                    "severity": result["severity"],
                    "confidence": result["confidence"],
                    "description": result["description"],
                    "evidence": result["evidence"],
                    "recommendations": self._generate_recommendations(result),
                    "detected_at": datetime.now().isoformat(),
                    "status": "active",
                }

                alerts.append(alert)

            return alerts

        except Exception as e:
            logger.error(f"Alert generation failed: {e}")
            return []

    def _generate_recommendations(self, alert: dict[str, Any]) -> list[str]:
        """
        Generate recommendations based on alert type
        """
        recommendations = []

        try:
            pattern = alert.get("pattern", "")

            if pattern == "round_numbers":
                recommendations.extend(
                    [
                        "Verify actual transaction value with supporting documentation",
                        "Cross-check with similar HS code declarations",
                        "Interview company representatives about pricing",
                    ]
                )

            elif pattern == "high_frequency":
                recommendations.extend(
                    [
                        "Review company business model and transaction volumes",
                        "Check for related companies or subsidiaries",
                        "Verify compliance with customs regulations",
                    ]
                )

            elif pattern == "value_spikes":
                recommendations.extend(
                    [
                        "Investigate reason for sudden value increase",
                        "Review market conditions and pricing",
                        "Check for related transactions or contracts",
                    ]
                )

            elif pattern == "shell_companies":
                recommendations.extend(
                    [
                        "Verify beneficial ownership and control structure",
                        "Check company registration and business activity",
                        "Review financial statements and tax records",
                    ]
                )

            elif pattern == "ml_detected_anomaly":
                recommendations.extend(
                    [
                        "Conduct detailed audit of the transaction",
                        "Review all supporting documentation",
                        "Interview involved parties",
                    ]
                )

            else:
                recommendations.append("Conduct thorough investigation of the flagged activity")

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")
            recommendations = ["Conduct thorough investigation"]

        return recommendations

    async def _save_corruption_alerts(
        self, alerts: list[dict[str, Any]], user_id: str | None = None
    ) -> list[str]:
        """
        Save corruption alerts to database
        """
        try:
            saved_ids = []

            async with get_db_session() as session:
                for alert in alerts:
                    db_alert = CorruptionAlert(
                        alert_id=alert["alert_id"],
                        declaration_id=alert.get("declaration_id"),
                        company_id=alert.get("company_id"),
                        alert_type=alert["alert_type"],
                        pattern=alert["pattern"],
                        severity=alert["severity"],
                        confidence=alert["confidence"],
                        description=alert["description"],
                        evidence=json.dumps(alert["evidence"]),
                        recommendations=json.dumps(alert["recommendations"]),
                        status=alert["status"],
                        detected_by=self.agent_id,
                        user_id=user_id,
                        created_at=datetime.now(),
                    )

                    session.add(db_alert)
                    saved_ids.append(alert["alert_id"])

                await session.commit()

            logger.info(f"Saved {len(saved_ids)} corruption alerts")
            return saved_ids

        except Exception as e:
            logger.error(f"Alert saving failed: {e}")
            return []

    async def _handle_corruption_analysis(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle detailed corruption analysis request
        """
        try:
            alert_id = message.content.get("alert_id")

            if not alert_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "alert_id required"},
                    timestamp=datetime.now(),
                )
                return

            # Get alert details
            analysis = await self._analyze_corruption_alert(alert_id)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "corruption_analysis_response",
                    "alert_id": alert_id,
                    "analysis": analysis,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Corruption analysis failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _analyze_corruption_alert(self, alert_id: str) -> dict[str, Any]:
        """
        Perform detailed analysis of a corruption alert
        """
        try:
            async with get_db_session() as session:
                # Get alert
                alert = await session.get(CorruptionAlert, alert_id)

                if not alert:
                    return {"error": "Alert not found"}

                analysis = {
                    "alert_details": {
                        "alert_id": alert.alert_id,
                        "alert_type": alert.alert_type,
                        "pattern": alert.pattern,
                        "severity": alert.severity,
                        "confidence": alert.confidence,
                        "description": alert.description,
                        "status": alert.status,
                    },
                    "evidence": json.loads(alert.evidence),
                    "recommendations": json.loads(alert.recommendations),
                    "related_alerts": [],
                    "company_analysis": {},
                    "historical_pattern": {},
                }

                # Get related alerts for same company
                if alert.company_id:
                    related_query = (
                        session.query(CorruptionAlert)
                        .filter(
                            CorruptionAlert.company_id == alert.company_id,
                            CorruptionAlert.id != alert.id,
                        )
                        .order_by(CorruptionAlert.created_at.desc())
                        .limit(10)
                    )

                    related_results = await session.execute(related_query)
                    related_alerts = related_results.fetchall()

                    analysis["related_alerts"] = [
                        {
                            "alert_id": r.alert_id,
                            "pattern": r.pattern,
                            "severity": r.severity,
                            "created_at": r.created_at.isoformat(),
                        }
                        for r in related_alerts
                    ]

                # Company analysis
                if alert.company_id:
                    company_analysis = await self._analyze_company(alert.company_id)
                    analysis["company_analysis"] = company_analysis

                # Historical pattern analysis
                if alert.declaration_id:
                    pattern_analysis = await self._analyze_historical_pattern(alert.declaration_id)
                    analysis["historical_pattern"] = pattern_analysis

                return analysis

        except Exception as e:
            logger.error(f"Alert analysis failed: {e}")
            return {"error": str(e)}

    async def _analyze_company(self, company_id: str) -> dict[str, Any]:
        """
        Analyze company corruption risk
        """
        try:
            async with get_db_session() as session:
                # Get company details
                company = await session.get(Company, company_id)

                if not company:
                    return {"error": "Company not found"}

                # Get company's customs activity
                customs_query = session.query(CustomsData).filter(
                    CustomsData.company_id == company_id
                )

                customs_results = await session.execute(customs_query)
                customs_records = customs_results.fetchall()

                # Calculate risk metrics
                total_value = sum(float(r.value_usd) for r in customs_records if r.value_usd)
                total_declarations = len(customs_records)

                # Get corruption alerts for company
                alerts_query = session.query(CorruptionAlert).filter(
                    CorruptionAlert.company_id == company_id
                )

                alerts_results = await session.execute(alerts_query)
                alerts = alerts_results.fetchall()

                risk_score = min(
                    100, len(alerts) * 10 + (total_declarations / 10)
                )  # Simple risk scoring

                return {
                    "company_name": company.company_name,
                    "registration_date": (
                        company.registration_date.isoformat() if company.registration_date else None
                    ),
                    "activity_type": company.activity_type,
                    "total_declarations": total_declarations,
                    "total_value_usd": total_value,
                    "corruption_alerts_count": len(alerts),
                    "risk_score": risk_score,
                    "risk_level": (
                        "high" if risk_score > 70 else "medium" if risk_score > 40 else "low"
                    ),
                }

        except Exception as e:
            logger.error(f"Company analysis failed: {e}")
            return {"error": str(e)}

    async def _analyze_historical_pattern(self, declaration_id: str) -> dict[str, Any]:
        """
        Analyze historical patterns for declaration
        """
        try:
            async with get_db_session() as session:
                # Get declaration
                declaration = await session.get(CustomsData, declaration_id)

                if not declaration:
                    return {"error": "Declaration not found"}

                # Get similar declarations by HS code and company
                similar_query = (
                    session.query(CustomsData)
                    .filter(
                        CustomsData.hs_code == declaration.hs_code,
                        CustomsData.company_id == declaration.company_id,
                        CustomsData.id != declaration.id,
                    )
                    .order_by(CustomsData.declaration_date.desc())
                    .limit(20)
                )

                similar_results = await session.execute(similar_query)
                similar_declarations = similar_results.fetchall()

                # Analyze patterns
                values = [float(d.value_usd) for d in similar_declarations if d.value_usd]

                if values:
                    avg_value = np.mean(values)
                    std_value = np.std(values)
                    current_value = float(declaration.value_usd) if declaration.value_usd else 0

                    deviation = abs(current_value - avg_value) / std_value if std_value > 0 else 0

                    return {
                        "similar_declarations_count": len(similar_declarations),
                        "average_value_usd": avg_value,
                        "value_std": std_value,
                        "current_value_usd": current_value,
                        "deviation_from_mean": deviation,
                        "is_outlier": deviation > 2,  # More than 2 standard deviations
                        "value_trend": "increasing" if current_value > avg_value else "decreasing",
                    }
                else:
                    return {
                        "similar_declarations_count": 0,
                        "note": "No similar declarations found for comparison",
                    }

        except Exception as e:
            logger.error(f"Historical pattern analysis failed: {e}")
            return {"error": str(e)}

    async def _handle_risk_assessment(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle risk assessment request
        """
        try:
            company_id = message.content.get("company_id")
            assessment_period_days = message.content.get("assessment_period_days", 365)

            if not company_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "company_id required"},
                    timestamp=datetime.now(),
                )
                return

            # Perform risk assessment
            assessment = await self._assess_company_risk(company_id, assessment_period_days)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "risk_assessment_response",
                    "company_id": company_id,
                    "assessment": assessment,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _assess_company_risk(
        self, company_id: str, assessment_period_days: int
    ) -> dict[str, Any]:
        """
        Assess corruption risk for a company
        """
        try:
            # Get company analysis
            company_analysis = await self._analyze_company(company_id)

            # Get recent alerts
            async with get_db_session() as session:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=assessment_period_days)

                alerts_query = session.query(CorruptionAlert).filter(
                    CorruptionAlert.company_id == company_id,
                    CorruptionAlert.created_at.between(start_date, end_date),
                )

                alerts_results = await session.execute(alerts_query)
                recent_alerts = alerts_results.fetchall()

            # Calculate risk factors
            risk_factors = {
                "alert_frequency": len(recent_alerts)
                / (assessment_period_days / 30),  # Alerts per month
                "high_severity_alerts": len(
                    [a for a in recent_alerts if a.severity in ["high", "critical"]]
                ),
                "company_age_risk": (
                    1.0 if company_analysis.get("company_age_days", 365) < 365 else 0.0
                ),
                "activity_volume_risk": min(
                    1.0, company_analysis.get("total_declarations", 0) / 1000
                ),  # Scale with volume
            }

            # Calculate overall risk score (0-100)
            risk_score = (
                risk_factors["alert_frequency"] * 30
                + risk_factors["high_severity_alerts"] * 20
                + risk_factors["company_age_risk"] * 25
                + risk_factors["activity_volume_risk"] * 25
            )

            risk_score = min(100, max(0, risk_score))

            # Determine risk level
            if risk_score >= 70:
                risk_level = "critical"
            elif risk_score >= 50:
                risk_level = "high"
            elif risk_score >= 30:
                risk_level = "medium"
            else:
                risk_level = "low"

            return {
                "company_id": company_id,
                "assessment_period_days": assessment_period_days,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "risk_factors": risk_factors,
                "recent_alerts_count": len(recent_alerts),
                "company_analysis": company_analysis,
                "recommendations": self._generate_risk_recommendations(risk_level, risk_factors),
            }

        except Exception as e:
            logger.error(f"Risk assessment calculation failed: {e}")
            return {"error": str(e)}

    def _generate_risk_recommendations(
        self, risk_level: str, risk_factors: dict[str, float]
    ) -> list[str]:
        """
        Generate risk-based recommendations
        """
        recommendations = []

        if risk_level == "critical":
            recommendations.extend(
                [
                    "Immediate audit required",
                    "Freeze all customs activities pending investigation",
                    "Notify law enforcement authorities",
                    "Conduct forensic accounting review",
                ]
            )

        elif risk_level == "high":
            recommendations.extend(
                [
                    "Enhanced monitoring required",
                    "Review all recent declarations manually",
                    "Verify beneficial ownership",
                    "Implement additional compliance controls",
                ]
            )

        elif risk_level == "medium":
            recommendations.extend(
                [
                    "Regular monitoring of activities",
                    "Review high-value transactions",
                    "Verify documentation completeness",
                    "Conduct periodic compliance checks",
                ]
            )

        else:  # low
            recommendations.extend(
                [
                    "Continue standard monitoring",
                    "Annual compliance review",
                    "Maintain documentation standards",
                ]
            )

        # Add specific recommendations based on risk factors
        if risk_factors.get("alert_frequency", 0) > 2:
            recommendations.append("Address frequent alert patterns")

        if risk_factors.get("company_age_risk", 0) > 0.5:
            recommendations.append("Verify new company legitimacy and operations")

        return recommendations

    async def _handle_model_update(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle model update/retraining request
        """
        try:
            # Clear model cache to force retraining
            self.models_cache.clear()
            self.scalers_cache.clear()
            self.last_model_update = None

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "model_update_response",
                    "status": "completed",
                    "message": "Corruption detection models cleared and will be retrained on next use",
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


# ========== TEST ==========
if __name__ == "__main__":

    async def test_corruption_detector():
        # Initialize corruption detector
        detector = CorruptionDetectorAgent()

        # Test message
        test_message = AgentMessage(
            id="test_corruption",
            from_agent="test",
            to_agent="corruption_detector_agent",
            content={
                "type": "corruption_scan",
                "filters": {},
                "scan_period_days": 30,
                "min_confidence": 0.5,
            },
            timestamp=datetime.now(),
        )

        print("Testing corruption detector...")
        async for response in detector.process_message(test_message):
            print(f"Response type: {response.content.get('type')}")
            if response.content.get("type") == "corruption_scan_response":
                summary = response.content.get("scan_summary", {})
                print(f"Scan completed: {summary.get('alerts_generated', 0)} alerts generated")

        print("Corruption detector test completed")

    # Run test
    asyncio.run(test_corruption_detector())
