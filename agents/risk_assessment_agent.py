"""
Risk Assessment Agent: Comprehensive risk analysis and scoring
Evaluates financial, operational, and compliance risks using ML models and rule-based systems
"""

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

import lightgbm as lgb
import numpy as np
import xgboost as xgb
from imblearn.over_sampling import SMOTE
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler

from ..agents.base_agent import AgentMessage, BaseAgent
from ..api.database import get_db_session
from ..api.models import RiskAlerts, RiskAssessment

logger = logging.getLogger(__name__)


class RiskAssessmentAgent(BaseAgent):
    """
    Risk Assessment Agent for comprehensive risk analysis and scoring
    Evaluates multiple risk dimensions using ML models and expert rules
    """

    def __init__(
        self, agent_id: str = "risk_assessment_agent", config: dict[str, Any] | None = None
    ):
        super().__init__(agent_id, config or {})

        # Risk assessment configuration
        self.risk_config = {
            "risk_dimensions": self.config.get(
                "risk_dimensions",
                ["financial", "operational", "compliance", "reputational", "strategic"],
            ),
            "risk_levels": ["low", "medium", "high", "critical"],
            "assessment_frequency": self.config.get("assessment_frequency", 3600),  # seconds
            "alert_thresholds": self.config.get("alert_thresholds", {"high": 0.7, "critical": 0.9}),
            "model_update_frequency": self.config.get("model_update_frequency", 86400),  # daily
            "historical_window": self.config.get("historical_window", 365),  # days
            "confidence_threshold": self.config.get("confidence_threshold", 0.8),
        }

        # Risk models
        self.risk_models = {}
        self.scalers = {}
        self.label_encoders = {}

        # Risk factors and weights
        self.risk_factors = {
            "financial": {
                "liquidity_ratio": 0.15,
                "debt_to_equity": 0.20,
                "profit_margin": 0.15,
                "cash_flow_volatility": 0.10,
                "credit_rating": 0.20,
                "market_volatility": 0.20,
            },
            "operational": {
                "system_uptime": 0.25,
                "process_efficiency": 0.20,
                "employee_turnover": 0.15,
                "supply_chain_disruption": 0.15,
                "cybersecurity_threats": 0.15,
                "regulatory_changes": 0.10,
            },
            "compliance": {
                "audit_findings": 0.30,
                "regulatory_fines": 0.25,
                "policy_violations": 0.20,
                "data_breach_incidents": 0.15,
                "compliance_training": 0.10,
            },
            "reputational": {
                "customer_satisfaction": 0.25,
                "media_mentions": 0.20,
                "social_media_sentiment": 0.20,
                "brand_value": 0.15,
                "crisis_events": 0.20,
            },
            "strategic": {
                "market_share": 0.20,
                "competitive_position": 0.20,
                "innovation_index": 0.15,
                "talent_attraction": 0.15,
                "sustainability_score": 0.15,
                "geopolitical_risks": 0.15,
            },
        }

        # Risk scoring ranges
        self.risk_ranges = {
            "low": (0, 0.3),
            "medium": (0.3, 0.6),
            "high": (0.6, 0.8),
            "critical": (0.8, 1.0),
        }

        # Assessment history
        self.assessment_history = defaultdict(list)
        self.risk_alerts = []

        # Background tasks
        self.assessment_task = None
        self.model_update_task = None

        logger.info(f"Risk Assessment Agent initialized: {agent_id}")

    async def start(self):
        """
        Start the risk assessment agent
        """
        await super().start()

        # Initialize risk models
        await self._initialize_risk_models()

        # Start assessment loop
        self.assessment_task = asyncio.create_task(self._assessment_loop())

        # Start model update loop
        self.model_update_task = asyncio.create_task(self._model_update_loop())

        logger.info("Risk assessment monitoring started")

    async def stop(self):
        """
        Stop the risk assessment agent
        """
        if self.assessment_task:
            self.assessment_task.cancel()
            try:
                await self.assessment_task
            except asyncio.CancelledError:
                pass

        if self.model_update_task:
            self.model_update_task.cancel()
            try:
                await self.model_update_task
            except asyncio.CancelledError:
                pass

        await super().stop()
        logger.info("Risk assessment agent stopped")

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process risk assessment requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "assess_entity_risk":
                async for response in self._handle_risk_assessment(message):
                    yield response

            elif message_type == "analyze_risk_factors":
                async for response in self._handle_risk_analysis(message):
                    yield response

            elif message_type == "get_risk_history":
                async for response in self._handle_risk_history(message):
                    yield response

            elif message_type == "update_risk_model":
                async for response in self._handle_model_update(message):
                    yield response

            elif message_type == "generate_risk_report":
                async for response in self._handle_risk_report(message):
                    yield response

            elif message_type == "mitigate_risk":
                async for response in self._handle_risk_mitigation(message):
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
            logger.error(f"Risk assessment processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _initialize_risk_models(self):
        """
        Initialize risk assessment models for each dimension
        """
        try:
            for dimension in self.risk_config["risk_dimensions"]:
                # Initialize multiple models for ensemble approach
                self.risk_models[dimension] = {
                    "random_forest": RandomForestClassifier(
                        n_estimators=100, max_depth=10, random_state=42
                    ),
                    "gradient_boosting": GradientBoostingClassifier(
                        n_estimators=100, learning_rate=0.1, random_state=42
                    ),
                    "xgboost": xgb.XGBClassifier(
                        n_estimators=100, learning_rate=0.1, random_state=42
                    ),
                    "lightgbm": lgb.LGBMClassifier(
                        n_estimators=100, learning_rate=0.1, random_state=42
                    ),
                }

                self.scalers[dimension] = StandardScaler()
                self.label_encoders[dimension] = LabelEncoder()

            logger.info("Risk models initialized")

        except Exception as e:
            logger.error(f"Risk models initialization failed: {e}")

    async def _assessment_loop(self):
        """
        Continuous risk assessment loop
        """
        try:
            while True:
                try:
                    # Assess risks for monitored entities
                    await self._perform_risk_assessments()

                    # Check for risk alerts
                    await self._check_risk_alerts()

                    # Update risk trends
                    await self._update_risk_trends()

                except Exception as e:
                    logger.error(f"Assessment loop error: {e}")

                # Wait for next assessment cycle
                await asyncio.sleep(self.risk_config["assessment_frequency"])

        except asyncio.CancelledError:
            logger.info("Assessment loop cancelled")
            raise

    async def _model_update_loop(self):
        """
        Periodic model update loop
        """
        try:
            while True:
                try:
                    # Update risk models with new data
                    await self._update_risk_models()

                except Exception as e:
                    logger.error(f"Model update loop error: {e}")

                # Wait for next update cycle
                await asyncio.sleep(self.risk_config["model_update_frequency"])

        except asyncio.CancelledError:
            logger.info("Model update loop cancelled")
            raise

    async def _perform_risk_assessments(self):
        """
        Perform comprehensive risk assessments
        """
        try:
            # Get entities requiring assessment (placeholder - would query database)
            entities = await self._get_entities_for_assessment()

            for entity in entities:
                assessment = await self._assess_entity_risk(entity)

                if assessment:
                    # Store assessment
                    self.assessment_history[entity["id"]].append(assessment)

                    # Save to database
                    await self._save_risk_assessment(assessment)

                    # Check for alerts
                    await self._evaluate_risk_alerts(assessment)

        except Exception as e:
            logger.error(f"Risk assessments failed: {e}")

    async def _get_entities_for_assessment(self) -> list[dict[str, Any]]:
        """
        Get entities that require risk assessment
        """
        try:
            # Placeholder - would query actual entities from database
            return [
                {
                    "id": "company_001",
                    "type": "company",
                    "name": "Test Company A",
                    "industry": "finance",
                },
                {
                    "id": "company_002",
                    "type": "company",
                    "name": "Test Company B",
                    "industry": "technology",
                },
            ]

        except Exception as e:
            logger.error(f"Entity retrieval failed: {e}")
            return []

    async def _assess_entity_risk(self, entity: dict[str, Any]) -> dict[str, Any] | None:
        """
        Assess risk for a specific entity
        """
        try:
            entity_id = entity["id"]

            # Gather risk factors
            risk_factors = await self._gather_risk_factors(entity)

            if not risk_factors:
                return None

            # Assess each risk dimension
            dimension_scores = {}
            dimension_confidence = {}

            for dimension in self.risk_config["risk_dimensions"]:
                score, confidence = await self._assess_dimension_risk(
                    dimension, risk_factors, entity
                )
                dimension_scores[dimension] = score
                dimension_confidence[dimension] = confidence

            # Calculate overall risk score
            overall_score = self._calculate_overall_risk_score(dimension_scores)
            risk_level = self._determine_risk_level(overall_score)

            # Generate assessment
            assessment = {
                "entity_id": entity_id,
                "entity_info": entity,
                "timestamp": datetime.now(),
                "dimension_scores": dimension_scores,
                "dimension_confidence": dimension_confidence,
                "overall_score": overall_score,
                "risk_level": risk_level,
                "risk_factors": risk_factors,
                "recommendations": await self._generate_risk_recommendations(
                    dimension_scores, risk_level
                ),
            }

            return assessment

        except Exception as e:
            logger.error(f"Entity risk assessment failed for {entity.get('id')}: {e}")
            return None

    async def _gather_risk_factors(self, entity: dict[str, Any]) -> dict[str, Any]:
        """
        Gather risk factors for entity assessment
        """
        try:
            # Placeholder - would gather actual risk factors from various sources
            return {
                "financial": {
                    "liquidity_ratio": 1.5,
                    "debt_to_equity": 0.8,
                    "profit_margin": 0.12,
                    "cash_flow_volatility": 0.15,
                    "credit_rating": "AA",
                    "market_volatility": 0.25,
                },
                "operational": {
                    "system_uptime": 0.98,
                    "process_efficiency": 0.85,
                    "employee_turnover": 0.08,
                    "supply_chain_disruption": 0.05,
                    "cybersecurity_threats": 0.3,
                    "regulatory_changes": 0.1,
                },
                "compliance": {
                    "audit_findings": 2,
                    "regulatory_fines": 0,
                    "policy_violations": 1,
                    "data_breach_incidents": 0,
                    "compliance_training": 0.9,
                },
                "reputational": {
                    "customer_satisfaction": 4.2,
                    "media_mentions": 15,
                    "social_media_sentiment": 0.6,
                    "brand_value": 8.5,
                    "crisis_events": 0,
                },
                "strategic": {
                    "market_share": 0.15,
                    "competitive_position": 0.7,
                    "innovation_index": 0.8,
                    "talent_attraction": 0.75,
                    "sustainability_score": 0.85,
                    "geopolitical_risks": 0.2,
                },
            }

        except Exception as e:
            logger.error(f"Risk factor gathering failed: {e}")
            return {}

    async def _assess_dimension_risk(
        self, dimension: str, risk_factors: dict[str, Any], entity: dict[str, Any]
    ) -> tuple[float, float]:
        """
        Assess risk for a specific dimension
        """
        try:
            dimension_factors = risk_factors.get(dimension, {})

            if not dimension_factors:
                return 0.0, 0.0

            # Prepare features for ML models
            features = self._prepare_dimension_features(dimension, dimension_factors, entity)

            if not features:
                # Fallback to rule-based assessment
                return self._rule_based_risk_assessment(dimension, dimension_factors)

            # Get predictions from ensemble of models
            predictions = []
            probabilities = []

            for model_name, model in self.risk_models[dimension].items():
                try:
                    # Scale features
                    scaler = self.scalers[dimension]
                    scaled_features = scaler.transform([features])

                    # Predict
                    pred = model.predict(scaled_features)[0]
                    prob = model.predict_proba(scaled_features)[0]

                    predictions.append(pred)
                    probabilities.append(prob)

                except Exception as e:
                    logger.error(f"Model prediction failed for {model_name}: {e}")

            if not predictions:
                return self._rule_based_risk_assessment(dimension, dimension_factors)

            # Ensemble prediction (majority vote for classification, average for probabilities)
            final_prediction = np.mean(predictions)  # Assuming regression-style output
            confidence = np.mean([max(prob) for prob in probabilities])

            return float(final_prediction), float(confidence)

        except Exception as e:
            logger.error(f"Dimension risk assessment failed for {dimension}: {e}")
            return 0.0, 0.0

    def _prepare_dimension_features(
        self, dimension: str, factors: dict[str, Any], entity: dict[str, Any]
    ) -> list[float] | None:
        """
        Prepare features for ML model input
        """
        try:
            features = []

            # Extract features based on dimension
            factor_weights = self.risk_factors[dimension]

            for factor_name in factor_weights.keys():
                value = factors.get(factor_name, 0)

                # Normalize/encode factor values
                if isinstance(value, str):
                    # Encode categorical values
                    encoder = self.label_encoders[dimension]
                    try:
                        encoded = encoder.transform([value])[0]
                        features.append(float(encoded))
                    except Exception:
                        features.append(0.0)  # Unknown category
                else:
                    # Normalize numerical values
                    features.append(float(value))

            # Add entity-level features
            features.extend(
                [
                    1.0 if entity.get("industry") == "finance" else 0.0,
                    1.0 if entity.get("industry") == "technology" else 0.0,
                    float(len(entity.get("name", ""))) / 100.0,  # Name length as proxy
                ]
            )

            return features

        except Exception as e:
            logger.error(f"Feature preparation failed for {dimension}: {e}")
            return None

    def _rule_based_risk_assessment(
        self, dimension: str, factors: dict[str, Any]
    ) -> tuple[float, float]:
        """
        Rule-based risk assessment as fallback
        """
        try:
            factor_weights = self.risk_factors[dimension]
            weighted_score = 0.0
            total_weight = 0.0

            for factor_name, weight in factor_weights.items():
                value = factors.get(factor_name, 0)

                # Normalize factor value to 0-1 scale (simplified)
                if dimension == "financial":
                    normalized_value = self._normalize_financial_factor(factor_name, value)
                elif dimension == "operational":
                    normalized_value = self._normalize_operational_factor(factor_name, value)
                elif dimension == "compliance":
                    normalized_value = self._normalize_compliance_factor(factor_name, value)
                elif dimension == "reputational":
                    normalized_value = self._normalize_reputational_factor(factor_name, value)
                elif dimension == "strategic":
                    normalized_value = self._normalize_strategic_factor(factor_name, value)
                else:
                    normalized_value = min(max(float(value), 0), 1)

                weighted_score += normalized_value * weight
                total_weight += weight

            final_score = weighted_score / total_weight if total_weight > 0 else 0.0

            return final_score, 0.7  # Lower confidence for rule-based

        except Exception as e:
            logger.error(f"Rule-based assessment failed for {dimension}: {e}")
            return 0.0, 0.0

    def _normalize_financial_factor(self, factor_name: str, value: Any) -> float:
        """Normalize financial risk factors"""
        try:
            if factor_name == "liquidity_ratio":
                return max(0, min(1, 2 - value))  # Higher is better, optimal ~1.5-2
            elif factor_name == "debt_to_equity":
                return min(1, value / 2)  # Higher debt = higher risk
            elif factor_name == "profit_margin":
                return 1 - min(1, value)  # Lower profit = higher risk
            elif factor_name == "cash_flow_volatility":
                return min(1, value * 2)  # Higher volatility = higher risk
            elif factor_name == "credit_rating":
                rating_map = {
                    "AAA": 0,
                    "AA": 0.1,
                    "A": 0.2,
                    "BBB": 0.4,
                    "BB": 0.6,
                    "B": 0.8,
                    "CCC": 1.0,
                }
                return rating_map.get(str(value).upper(), 0.5)
            elif factor_name == "market_volatility":
                return min(1, value)
            else:
                return min(max(float(value), 0), 1)
        except Exception:
            return 0.5

    def _normalize_operational_factor(self, factor_name: str, value: Any) -> float:
        """Normalize operational risk factors"""
        try:
            if factor_name == "system_uptime":
                return 1 - value  # Lower uptime = higher risk
            elif factor_name == "process_efficiency":
                return 1 - value  # Lower efficiency = higher risk
            elif factor_name == "employee_turnover":
                return min(1, value * 2)  # Higher turnover = higher risk
            elif factor_name == "supply_chain_disruption":
                return min(1, value)
            elif factor_name == "cybersecurity_threats":
                return min(1, value)
            elif factor_name == "regulatory_changes":
                return min(1, value)
            else:
                return min(max(float(value), 0), 1)
        except Exception:
            return 0.5

    def _normalize_compliance_factor(self, factor_name: str, value: Any) -> float:
        """Normalize compliance risk factors"""
        try:
            if factor_name == "audit_findings":
                return min(1, value / 10)  # More findings = higher risk
            elif factor_name == "regulatory_fines":
                return min(1, value / 1000000)  # Higher fines = higher risk
            elif factor_name == "policy_violations":
                return min(1, value / 5)
            elif factor_name == "data_breach_incidents":
                return min(1, value / 3)
            elif factor_name == "compliance_training":
                return 1 - value  # Lower training = higher risk
            else:
                return min(max(float(value), 0), 1)
        except Exception:
            return 0.5

    def _normalize_reputational_factor(self, factor_name: str, value: Any) -> float:
        """Normalize reputational risk factors"""
        try:
            if factor_name == "customer_satisfaction":
                return 1 - (value / 5)  # Lower satisfaction = higher risk
            elif factor_name == "media_mentions":
                return min(1, value / 50)  # More mentions = higher risk
            elif factor_name == "social_media_sentiment":
                return 1 - value  # Lower sentiment = higher risk
            elif factor_name == "brand_value":
                return 1 - (value / 10)  # Lower brand value = higher risk
            elif factor_name == "crisis_events":
                return min(1, value / 5)
            else:
                return min(max(float(value), 0), 1)
        except Exception:
            return 0.5

    def _normalize_strategic_factor(self, factor_name: str, value: Any) -> float:
        """Normalize strategic risk factors"""
        try:
            if factor_name == "market_share":
                return 1 - value  # Lower market share = higher risk
            elif factor_name == "competitive_position":
                return 1 - value  # Lower position = higher risk
            elif factor_name == "innovation_index":
                return 1 - value  # Lower innovation = higher risk
            elif factor_name == "talent_attraction":
                return 1 - value  # Lower attraction = higher risk
            elif factor_name == "sustainability_score":
                return 1 - value  # Lower sustainability = higher risk
            elif factor_name == "geopolitical_risks":
                return min(1, value)
            else:
                return min(max(float(value), 0), 1)
        except Exception:
            return 0.5

    def _calculate_overall_risk_score(self, dimension_scores: dict[str, float]) -> float:
        """
        Calculate overall risk score from dimension scores
        """
        try:
            # Weighted average across dimensions
            dimension_weights = {
                "financial": 0.25,
                "operational": 0.20,
                "compliance": 0.20,
                "reputational": 0.15,
                "strategic": 0.20,
            }

            overall_score = 0.0
            total_weight = 0.0

            for dimension, score in dimension_scores.items():
                weight = dimension_weights.get(dimension, 0.2)
                overall_score += score * weight
                total_weight += weight

            return overall_score / total_weight if total_weight > 0 else 0.0

        except Exception as e:
            logger.error(f"Overall risk score calculation failed: {e}")
            return 0.0

    def _determine_risk_level(self, overall_score: float) -> str:
        """
        Determine risk level from overall score
        """
        for level, (min_val, max_val) in self.risk_ranges.items():
            if min_val <= overall_score < max_val:
                return level

        return "critical"  # Default to highest risk

    async def _generate_risk_recommendations(
        self, dimension_scores: dict[str, float], risk_level: str
    ) -> list[str]:
        """
        Generate risk mitigation recommendations
        """
        try:
            recommendations = []

            # General recommendations based on risk level
            if risk_level == "critical":
                recommendations.extend(
                    [
                        "Immediate executive attention required",
                        "Implement emergency risk mitigation plan",
                        "Conduct comprehensive risk audit",
                        "Consider external risk management consultation",
                    ]
                )
            elif risk_level == "high":
                recommendations.extend(
                    [
                        "Develop detailed risk mitigation strategy",
                        "Increase monitoring frequency",
                        "Allocate additional resources for risk management",
                        "Prepare contingency plans",
                    ]
                )
            elif risk_level == "medium":
                recommendations.extend(
                    [
                        "Monitor risk indicators closely",
                        "Implement preventive measures",
                        "Review and update risk policies",
                        "Conduct regular risk assessments",
                    ]
                )

            # Dimension-specific recommendations
            for dimension, score in dimension_scores.items():
                if score > 0.7:  # High risk in dimension
                    dim_recs = self._get_dimension_recommendations(dimension)
                    recommendations.extend(dim_recs)

            return recommendations[:10]  # Limit to top 10

        except Exception as e:
            logger.error(f"Risk recommendations generation failed: {e}")
            return ["Conduct comprehensive risk assessment"]

    def _get_dimension_recommendations(self, dimension: str) -> list[str]:
        """
        Get dimension-specific risk recommendations
        """
        recommendations = {
            "financial": [
                "Review and optimize capital structure",
                "Improve liquidity management",
                "Diversify revenue streams",
                "Strengthen credit risk controls",
            ],
            "operational": [
                "Enhance system reliability and uptime",
                "Streamline operational processes",
                "Invest in cybersecurity measures",
                "Develop business continuity plans",
            ],
            "compliance": [
                "Strengthen compliance monitoring",
                "Enhance employee training programs",
                "Conduct regular compliance audits",
                "Update policies and procedures",
            ],
            "reputational": [
                "Monitor social media and media coverage",
                "Improve customer service quality",
                "Develop crisis communication plan",
                "Strengthen brand protection measures",
            ],
            "strategic": [
                "Conduct competitive analysis",
                "Invest in innovation and R&D",
                "Strengthen talent management",
                "Monitor geopolitical developments",
            ],
        }

        return recommendations.get(dimension, [])

    async def _evaluate_risk_alerts(self, assessment: dict[str, Any]):
        """
        Evaluate if assessment triggers risk alerts
        """
        try:
            overall_score = assessment["overall_score"]
            risk_level = assessment["risk_level"]

            # Check alert thresholds
            alert_triggered = False

            if risk_level == "critical":
                alert_triggered = True
            elif (
                risk_level == "high"
                and overall_score >= self.risk_config["alert_thresholds"]["high"]
            ):
                alert_triggered = True

            if alert_triggered:
                alert = {
                    "entity_id": assessment["entity_id"],
                    "timestamp": datetime.now(),
                    "risk_level": risk_level,
                    "overall_score": overall_score,
                    "assessment": assessment,
                    "status": "active",
                }

                self.risk_alerts.append(alert)

                # Save alert to database
                await self._save_risk_alert(alert)

                logger.warning(f"Risk alert triggered for {assessment['entity_id']}: {risk_level}")

        except Exception as e:
            logger.error(f"Risk alert evaluation failed: {e}")

    async def _save_risk_assessment(self, assessment: dict[str, Any]):
        """
        Save risk assessment to database
        """
        try:
            async with get_db_session() as session:
                assessment_entry = RiskAssessment(
                    entity_id=assessment["entity_id"],
                    assessment_timestamp=assessment["timestamp"],
                    overall_score=assessment["overall_score"],
                    risk_level=assessment["risk_level"],
                    dimension_scores=json.dumps(assessment["dimension_scores"]),
                    risk_factors=json.dumps(assessment["risk_factors"]),
                    recommendations=json.dumps(assessment["recommendations"]),
                    assessed_at=datetime.now(),
                )

                session.add(assessment_entry)
                await session.commit()

        except Exception as e:
            logger.error(f"Risk assessment save failed: {e}")

    async def _save_risk_alert(self, alert: dict[str, Any]):
        """
        Save risk alert to database
        """
        try:
            async with get_db_session() as session:
                alert_entry = RiskAlerts(
                    entity_id=alert["entity_id"],
                    alert_timestamp=alert["timestamp"],
                    risk_level=alert["risk_level"],
                    overall_score=alert["overall_score"],
                    alert_details=json.dumps(alert["assessment"]),
                    status=alert["status"],
                    created_at=datetime.now(),
                )

                session.add(alert_entry)
                await session.commit()

        except Exception as e:
            logger.error(f"Risk alert save failed: {e}")

    async def _update_risk_trends(self):
        """
        Update risk trends analysis
        """
        try:
            # Analyze trends in risk assessments
            for entity_id, history in self.assessment_history.items():
                if len(history) >= 5:  # Need sufficient history
                    recent_scores = [entry["overall_score"] for entry in history[-10:]]

                    # Calculate trend
                    if len(recent_scores) >= 2:
                        trend = np.polyfit(range(len(recent_scores)), recent_scores, 1)[0]

                        if trend > 0.01:
                            trend_direction = "increasing"
                        elif trend < -0.01:
                            trend_direction = "decreasing"
                        else:
                            trend_direction = "stable"

                        # Log significant trend changes
                        if abs(trend) > 0.05:
                            logger.info(
                                f"Risk trend for {entity_id}: {trend_direction} ({trend:.3f})"
                            )

        except Exception as e:
            logger.error(f"Risk trend update failed: {e}")

    async def _update_risk_models(self):
        """
        Update risk models with new training data
        """
        try:
            # Placeholder - would retrain models with new data
            logger.info("Risk models update cycle completed")

        except Exception as e:
            logger.error(f"Risk model update failed: {e}")

    async def _check_risk_alerts(self):
        """
        Check and update status of active risk alerts
        """
        try:
            # Update alert statuses based on current assessments
            for alert in self.risk_alerts:
                if alert["status"] == "active":
                    # Check if alert should be resolved
                    entity_id = alert["entity_id"]
                    latest_assessment = (
                        self.assessment_history[entity_id][-1]
                        if self.assessment_history[entity_id]
                        else None
                    )

                    if latest_assessment:
                        current_level = latest_assessment["risk_level"]
                        alert_level = alert["risk_level"]

                        # Resolve if risk level improved significantly
                        if (alert_level == "critical" and current_level in ["low", "medium"]) or (
                            alert_level == "high" and current_level == "low"
                        ):
                            alert["status"] = "resolved"
                            alert["resolved_at"] = datetime.now()

                            # Update in database
                            await self._update_alert_status(alert)

        except Exception as e:
            logger.error(f"Risk alert check failed: {e}")

    async def _update_alert_status(self, alert: dict[str, Any]):
        """
        Update alert status in database
        """
        try:
            async with get_db_session():
                # Would update alert status in database
                pass

        except Exception as e:
            logger.error(f"Alert status update failed: {e}")

    async def _handle_risk_assessment(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle risk assessment request
        """
        try:
            entity_id = message.content.get("entity_id")

            if not entity_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Entity ID required"},
                    timestamp=datetime.now(),
                )
                return

            # Get entity info (placeholder)
            entity = {
                "id": entity_id,
                "type": "company",
                "name": f"Entity {entity_id}",
                "industry": "unknown",
            }

            # Perform assessment
            assessment = await self._assess_entity_risk(entity)

            if assessment:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "risk_assessment_response",
                        "entity_id": entity_id,
                        "assessment": assessment,
                    },
                    timestamp=datetime.now(),
                )
            else:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Assessment failed"},
                    timestamp=datetime.now(),
                )

        except Exception as e:
            logger.error(f"Risk assessment handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_risk_analysis(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle risk factor analysis request
        """
        try:
            entity_id = message.content.get("entity_id")
            dimension = message.content.get("dimension")

            if not entity_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Entity ID required"},
                    timestamp=datetime.now(),
                )
                return

            # Analyze risk factors
            analysis = await self._analyze_risk_factors(entity_id, dimension)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "risk_analysis_response",
                    "entity_id": entity_id,
                    "dimension": dimension,
                    "analysis": analysis,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Risk analysis handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _analyze_risk_factors(
        self, entity_id: str, dimension: str | None = None
    ) -> dict[str, Any]:
        """
        Analyze risk factors for entity
        """
        try:
            # Get recent assessments
            history = self.assessment_history.get(entity_id, [])

            if not history:
                return {"status": "no_data"}

            latest = history[-1]

            analysis = {
                "entity_id": entity_id,
                "analysis_timestamp": datetime.now(),
                "overall_risk": latest["risk_level"],
                "overall_score": latest["overall_score"],
            }

            if dimension:
                # Analyze specific dimension
                if dimension in latest["dimension_scores"]:
                    analysis["dimension_analysis"] = {
                        "dimension": dimension,
                        "score": latest["dimension_scores"][dimension],
                        "confidence": latest["dimension_confidence"][dimension],
                        "factors": latest["risk_factors"].get(dimension, {}),
                    }

                    # Add factor importance analysis
                    analysis["dimension_analysis"]["factor_importance"] = (
                        self._analyze_factor_importance(
                            dimension, latest["risk_factors"].get(dimension, {})
                        )
                    )
            else:
                # Analyze all dimensions
                analysis["dimension_breakdown"] = {}
                for dim in self.risk_config["risk_dimensions"]:
                    if dim in latest["dimension_scores"]:
                        analysis["dimension_breakdown"][dim] = {
                            "score": latest["dimension_scores"][dim],
                            "confidence": latest["dimension_confidence"][dim],
                            "level": self._determine_risk_level(latest["dimension_scores"][dim]),
                        }

            # Add trend analysis
            if len(history) >= 3:
                analysis["trend_analysis"] = self._calculate_risk_trends(history)

            return analysis

        except Exception as e:
            logger.error(f"Risk factor analysis failed: {e}")
            return {"error": str(e)}

    def _analyze_factor_importance(
        self, dimension: str, factors: dict[str, Any]
    ) -> dict[str, float]:
        """
        Analyze importance of individual risk factors
        """
        try:
            importance = {}
            factor_weights = self.risk_factors[dimension]

            for factor_name, weight in factor_weights.items():
                value = factors.get(factor_name, 0)

                # Calculate normalized impact
                if dimension == "financial":
                    impact = self._normalize_financial_factor(factor_name, value) * weight
                elif dimension == "operational":
                    impact = self._normalize_operational_factor(factor_name, value) * weight
                elif dimension == "compliance":
                    impact = self._normalize_compliance_factor(factor_name, value) * weight
                elif dimension == "reputational":
                    impact = self._normalize_reputational_factor(factor_name, value) * weight
                elif dimension == "strategic":
                    impact = self._normalize_strategic_factor(factor_name, value) * weight
                else:
                    impact = float(value) * weight

                importance[factor_name] = impact

            return importance

        except Exception as e:
            logger.error(f"Factor importance analysis failed: {e}")
            return {}

    def _calculate_risk_trends(self, history: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Calculate risk trends from assessment history
        """
        try:
            scores = [entry["overall_score"] for entry in history[-10:]]  # Last 10 assessments

            if len(scores) < 2:
                return {"trend": "insufficient_data"}

            # Calculate trend
            slope = np.polyfit(range(len(scores)), scores, 1)[0]

            trend_info = {
                "direction": (
                    "increasing" if slope > 0.01 else "decreasing" if slope < -0.01 else "stable"
                ),
                "slope": float(slope),
                "volatility": float(np.std(scores)),
                "data_points": len(scores),
            }

            return trend_info

        except Exception as e:
            logger.error(f"Risk trend calculation failed: {e}")
            return {"trend": "error"}

    async def _handle_risk_history(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle risk history request
        """
        try:
            entity_id = message.content.get("entity_id")
            limit = message.content.get("limit", 50)

            if not entity_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Entity ID required"},
                    timestamp=datetime.now(),
                )
                return

            # Get risk history
            history = self.assessment_history.get(entity_id, [])[-limit:]

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "risk_history_response",
                    "entity_id": entity_id,
                    "history": history,
                    "total_assessments": len(self.assessment_history.get(entity_id, [])),
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Risk history handling failed: {e}")
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
        Handle risk model update request
        """
        try:
            dimension = message.content.get("dimension")
            training_data = message.content.get("training_data", [])

            if not dimension or dimension not in self.risk_config["risk_dimensions"]:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Valid dimension required"},
                    timestamp=datetime.now(),
                )
                return

            # Update models for dimension
            success = await self._update_dimension_models(dimension, training_data)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "model_update_response",
                    "dimension": dimension,
                    "success": success,
                    "models_updated": list(self.risk_models[dimension].keys()) if success else [],
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

    async def _update_dimension_models(
        self, dimension: str, training_data: list[dict[str, Any]]
    ) -> bool:
        """
        Update models for a specific risk dimension
        """
        try:
            if not training_data:
                return False

            # Prepare training data
            X = []
            y = []

            for sample in training_data:
                features = self._prepare_dimension_features(
                    dimension, sample.get("factors", {}), sample.get("entity", {})
                )

                if features:
                    X.append(features)
                    y.append(sample.get("risk_score", 0))

            if not X or not y:
                return False

            X = np.array(X)
            y = np.array(y)

            # Handle class imbalance
            if len(np.unique(y)) > 2:  # Regression
                smote = SMOTE(random_state=42)
                X_resampled, y_resampled = smote.fit_resample(X, y)
            else:  # Classification
                X_resampled, y_resampled = X, y

            # Train each model
            for model_name, model in self.risk_models[dimension].items():
                try:
                    model.fit(X_resampled, y_resampled)
                    logger.info(f"Updated {model_name} for {dimension}")
                except Exception as e:
                    logger.error(f"Failed to update {model_name}: {e}")

            # Update scaler
            self.scalers[dimension].fit(X_resampled)

            return True

        except Exception as e:
            logger.error(f"Dimension model update failed: {e}")
            return False

    async def _handle_risk_report(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle risk report generation request
        """
        try:
            entity_id = message.content.get("entity_id")
            report_type = message.content.get("report_type", "comprehensive")

            if not entity_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Entity ID required"},
                    timestamp=datetime.now(),
                )
                return

            # Generate risk report
            report = await self._generate_risk_report(entity_id, report_type)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "risk_report_response",
                    "entity_id": entity_id,
                    "report_type": report_type,
                    "report": report,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Risk report generation failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _generate_risk_report(self, entity_id: str, report_type: str) -> dict[str, Any]:
        """
        Generate comprehensive risk report
        """
        try:
            history = self.assessment_history.get(entity_id, [])

            if not history:
                return {"status": "no_assessments"}

            latest = history[-1]

            report = {
                "entity_id": entity_id,
                "report_type": report_type,
                "generated_at": datetime.now(),
                "assessment_period": f"{history[0]['timestamp']} to {latest['timestamp']}",
                "total_assessments": len(history),
            }

            if report_type == "comprehensive":
                report.update(
                    {
                        "current_risk_profile": {
                            "overall_score": latest["overall_score"],
                            "risk_level": latest["risk_level"],
                            "dimension_scores": latest["dimension_scores"],
                        },
                        "risk_trends": (
                            self._calculate_risk_trends(history) if len(history) >= 3 else None
                        ),
                        "key_risk_factors": await self._identify_key_risk_factors(latest),
                        "recommendations": latest["recommendations"],
                        "alerts": [
                            alert for alert in self.risk_alerts if alert["entity_id"] == entity_id
                        ][-5:],
                    }
                )
            elif report_type == "summary":
                report.update(
                    {
                        "current_risk_level": latest["risk_level"],
                        "overall_score": latest["overall_score"],
                        "top_risks": await self._identify_top_risks(latest),
                        "trend": (
                            self._calculate_risk_trends(history)["direction"]
                            if len(history) >= 3
                            else "unknown"
                        ),
                    }
                )

            return report

        except Exception as e:
            logger.error(f"Risk report generation failed: {e}")
            return {"error": str(e)}

    async def _identify_key_risk_factors(self, assessment: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Identify key risk factors from assessment
        """
        try:
            key_factors = []

            for dimension, score in assessment["dimension_scores"].items():
                if score > 0.6:  # High risk dimensions
                    factors = assessment["risk_factors"].get(dimension, {})
                    factor_importance = self._analyze_factor_importance(dimension, factors)

                    # Get top 3 factors
                    sorted_factors = sorted(
                        factor_importance.items(), key=lambda x: x[1], reverse=True
                    )[:3]

                    for factor_name, importance in sorted_factors:
                        key_factors.append(
                            {
                                "dimension": dimension,
                                "factor": factor_name,
                                "importance": importance,
                                "value": factors.get(factor_name),
                            }
                        )

            return key_factors

        except Exception as e:
            logger.error(f"Key risk factor identification failed: {e}")
            return []

    async def _identify_top_risks(self, assessment: dict[str, Any]) -> list[str]:
        """
        Identify top risks from assessment
        """
        try:
            top_risks = []

            # Sort dimensions by risk score
            sorted_dimensions = sorted(
                assessment["dimension_scores"].items(), key=lambda x: x[1], reverse=True
            )

            for dimension, score in sorted_dimensions[:3]:  # Top 3
                risk_level = self._determine_risk_level(score)
                top_risks.append(f"{dimension.capitalize()} risk: {risk_level}")

            return top_risks

        except Exception as e:
            logger.error(f"Top risk identification failed: {e}")
            return []

    async def _handle_risk_mitigation(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle risk mitigation request
        """
        try:
            entity_id = message.content.get("entity_id")
            mitigation_actions = message.content.get("mitigation_actions", [])

            if not entity_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={"type": "error", "error": "Entity ID required"},
                    timestamp=datetime.now(),
                )
                return

            # Implement mitigation actions
            results = await self._implement_mitigation_actions(entity_id, mitigation_actions)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "risk_mitigation_response",
                    "entity_id": entity_id,
                    "actions_implemented": results,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Risk mitigation handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _implement_mitigation_actions(
        self, entity_id: str, actions: list[str]
    ) -> list[dict[str, Any]]:
        """
        Implement risk mitigation actions
        """
        try:
            results = []

            for action in actions:
                # Placeholder - would implement actual mitigation actions
                result = {
                    "action": action,
                    "status": "implemented",
                    "timestamp": datetime.now(),
                    "expected_impact": "medium",
                }
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Mitigation action implementation failed: {e}")
            return []


# ========== TEST ==========
if __name__ == "__main__":

    async def test_risk_assessment_agent():
        # Initialize risk assessment agent
        agent = RiskAssessmentAgent()
        await agent.start()

        # Test risk assessment
        assessment_message = AgentMessage(
            id="test_assess",
            from_agent="test",
            to_agent="risk_assessment_agent",
            content={"type": "assess_entity_risk", "entity_id": "test_entity_123"},
            timestamp=datetime.now(),
        )

        print("Testing risk assessment agent...")
        async for response in agent.process_message(assessment_message):
            print(f"Assessment response: {response.content.get('type')}")
            if response.content.get("type") == "risk_assessment_response":
                assessment = response.content.get("assessment", {})
                print(f"Risk level: {assessment.get('risk_level')}")
                print(f"Overall score: {assessment.get('overall_score'):.3f}")

        # Test risk analysis
        analysis_message = AgentMessage(
            id="test_analyze",
            from_agent="test",
            to_agent="risk_assessment_agent",
            content={
                "type": "analyze_risk_factors",
                "entity_id": "test_entity_123",
                "dimension": "financial",
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(analysis_message):
            print(f"Analysis response: {response.content.get('type')}")

        # Stop agent
        await agent.stop()
        print("Risk assessment agent test completed")

    # Run test
    asyncio.run(test_risk_assessment_agent())
