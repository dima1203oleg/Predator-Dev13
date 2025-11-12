"""
Data Quality Agent: Data validation and quality assessment
Ensures data integrity, consistency, and reliability across the platform
"""

import asyncio
import logging
import re
import uuid
from collections import deque
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sqlalchemy.ext.declarative import declarative_base

from ..agents.base_agent import AgentMessage, BaseAgent

logger = logging.getLogger(__name__)

Base = declarative_base()


class DataQualityAgent(BaseAgent):
    """
    Data Quality Agent for comprehensive data validation and quality assessment
    Uses statistical methods, ML models, and rule-based validation
    """

    def __init__(
        self, agent_id: str = "data_quality_agent", config: dict[str, Any] | None = None
    ):
        super().__init__(agent_id, config or {})

        # Data quality configuration
        self.dq_config = {
            "quality_dimensions": self.config.get(
                "quality_dimensions",
                ["accuracy", "completeness", "consistency", "timeliness", "validity", "uniqueness"],
            ),
            "validation_rules": self.config.get(
                "validation_rules",
                [
                    "range_check",
                    "format_check",
                    "consistency_check",
                    "completeness_check",
                    "uniqueness_check",
                    "referential_integrity",
                    "business_rules",
                ],
            ),
            "data_types": self.config.get(
                "data_types", ["numeric", "categorical", "text", "date", "boolean", "json"]
            ),
            "quality_thresholds": self.config.get(
                "quality_thresholds",
                {
                    "accuracy": 0.95,
                    "completeness": 0.90,
                    "consistency": 0.85,
                    "timeliness": 0.95,
                    "validity": 0.90,
                    "uniqueness": 0.95,
                },
            ),
            "anomaly_detection": self.config.get(
                "anomaly_detection", ["statistical", "ml_based", "rule_based", "time_series"]
            ),
            "profiling_methods": self.config.get(
                "profiling_methods",
                [
                    "basic_stats",
                    "distribution_analysis",
                    "correlation_analysis",
                    "outlier_detection",
                ],
            ),
            "quality_limits": self.config.get(
                "quality_limits",
                {
                    "max_sample_size": 100000,
                    "min_sample_size": 100,
                    "max_columns": 1000,
                    "batch_size": 10000,
                },
            ),
        }

        # ML models for quality assessment
        self.quality_models = {}
        self.anomaly_detectors = {}
        self.validation_models = {}

        # Quality rules and patterns
        self.quality_rules = {}
        self.validation_patterns = {}

        # Quality state
        self.quality_state = {
            "data_sources": {},
            "quality_metrics": {},
            "validation_results": {},
            "anomaly_history": deque(maxlen=10000),
            "quality_trends": {},
            "alerts": deque(maxlen=1000),
            "processing_queue": deque(),
            "quality_log": deque(maxlen=10000),
        }

        # Background tasks
        self.validation_task = None
        self.monitoring_task = None
        self.profiling_task = None

        logger.info(f"Data Quality Agent initialized: {agent_id}")

    async def start(self):
        """
        Start the data quality agent
        """
        await super().start()

        # Initialize quality models
        await self._initialize_quality_models()

        # Initialize quality rules
        await self._initialize_quality_rules()

        # Start background tasks
        self.validation_task = asyncio.create_task(self._continuous_validation())
        self.monitoring_task = asyncio.create_task(self._continuous_monitoring())
        self.profiling_task = asyncio.create_task(self._data_profiling())

        logger.info("Data quality processing started")

    async def stop(self):
        """
        Stop the data quality agent
        """
        if self.validation_task:
            self.validation_task.cancel()
            try:
                await self.validation_task
            except asyncio.CancelledError:
                pass

        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

        if self.profiling_task:
            self.profiling_task.cancel()
            try:
                await self.profiling_task
            except asyncio.CancelledError:
                pass

        await super().stop()
        logger.info("Data quality agent stopped")

    async def _initialize_quality_models(self):
        """
        Initialize ML models for data quality assessment
        """
        try:
            # Quality classification models
            self.quality_models = {
                "quality_classifier": RandomForestClassifier(n_estimators=100, random_state=42),
                "anomaly_detector": IsolationForest(contamination=0.1, random_state=42),
                "validation_model": GradientBoostingClassifier(n_estimators=100, random_state=42),
            }

            # Anomaly detection models
            self.anomaly_detectors = {
                "isolation_forest": IsolationForest(contamination=0.05, random_state=42),
                "one_class_svm": None,  # Initialize when needed
                "local_outlier_factor": None,  # Initialize when needed
            }

            # Validation models for different data types
            self.validation_models = {
                "numeric_validator": {},
                "categorical_validator": {},
                "text_validator": {},
                "date_validator": {},
            }

            logger.info("Quality models initialized")

        except Exception as e:
            logger.error(f"Quality model initialization failed: {e}")

    async def _initialize_quality_rules(self):
        """
        Initialize quality rules and validation patterns
        """
        try:
            # Basic validation rules
            self.quality_rules = {
                "numeric_range": {
                    "type": "range_check",
                    "min_value": None,
                    "max_value": None,
                    "allow_null": False,
                },
                "string_format": {"type": "format_check", "pattern": None, "allow_null": False},
                "date_format": {"type": "format_check", "format": "%Y-%m-%d", "allow_null": False},
                "categorical_values": {
                    "type": "categorical_check",
                    "allowed_values": [],
                    "allow_null": False,
                },
                "uniqueness": {
                    "type": "uniqueness_check",
                    "columns": [],
                    "allow_duplicates": False,
                },
                "completeness": {
                    "type": "completeness_check",
                    "threshold": 0.95,
                    "allow_null": False,
                },
            }

            # Validation patterns
            self.validation_patterns = {
                "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
                "phone": r"^\+?[\d\s\-\(\)]+$",
                "url": r"^https?://[^\s]+$",
                "ip_address": r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",
                "credit_card": r"^\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}$",
                "postal_code": r"^\d{5}(?:[-\s]\d{4})?$",
            }

            logger.info("Quality rules initialized")

        except Exception as e:
            logger.error(f"Quality rules initialization failed: {e}")

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process data quality requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "validate_data":
                async for response in self._handle_data_validation(message):
                    yield response

            elif message_type == "assess_quality":
                async for response in self._handle_quality_assessment(message):
                    yield response

            elif message_type == "detect_anomalies":
                async for response in self._handle_anomaly_detection(message):
                    yield response

            elif message_type == "profile_data":
                async for response in self._handle_data_profiling(message):
                    yield response

            elif message_type == "check_rules":
                async for response in self._handle_rule_checking(message):
                    yield response

            elif message_type == "generate_report":
                async for response in self._handle_quality_report(message):
                    yield response

            elif message_type == "monitor_quality":
                async for response in self._handle_quality_monitoring(message):
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
            logger.error(f"Data quality processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _continuous_validation(self):
        """
        Continuous data validation across data sources
        """
        try:
            while True:
                try:
                    # Process queued validation requests
                    while self.quality_state["processing_queue"]:
                        item = self.quality_state["processing_queue"].popleft()
                        await self._process_validation_item(item)

                    # Validate recent data
                    await self._validate_recent_data()

                    # Update quality metrics
                    await self._update_quality_metrics()

                except Exception as e:
                    logger.error(f"Continuous validation error: {e}")

                # Wait for next validation cycle
                await asyncio.sleep(300)  # Validate every 5 minutes

        except asyncio.CancelledError:
            logger.info("Continuous validation cancelled")
            raise

    async def _continuous_monitoring(self):
        """
        Continuous quality monitoring and alerting
        """
        try:
            while True:
                try:
                    # Check quality thresholds
                    await self._check_quality_thresholds()

                    # Detect quality degradation
                    await self._detect_quality_degradation()

                    # Generate alerts
                    await self._generate_quality_alerts()

                except Exception as e:
                    logger.error(f"Continuous monitoring error: {e}")

                # Wait for next monitoring cycle
                await asyncio.sleep(600)  # Monitor every 10 minutes

        except asyncio.CancelledError:
            logger.info("Continuous monitoring cancelled")
            raise

    async def _data_profiling(self):
        """
        Continuous data profiling and analysis
        """
        try:
            while True:
                try:
                    # Profile new data sources
                    await self._profile_new_sources()

                    # Update data profiles
                    await self._update_data_profiles()

                    # Analyze data patterns
                    await self._analyze_data_patterns()

                except Exception as e:
                    logger.error(f"Data profiling error: {e}")

                # Wait for next profiling cycle
                await asyncio.sleep(1800)  # Profile every 30 minutes

        except asyncio.CancelledError:
            logger.info("Data profiling cancelled")
            raise

    async def _handle_data_validation(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle data validation request
        """
        try:
            data_source = message.content.get("data_source", {})
            validation_rules = message.content.get("validation_rules", [])
            validation_type = message.content.get("validation_type", "comprehensive")

            # Validate data
            validation_result = await self._validate_data(
                data_source, validation_rules, validation_type
            )

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "data_validation_response",
                    "validation_type": validation_type,
                    "result": validation_result,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Data validation handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _validate_data(
        self,
        data_source: dict[str, Any],
        validation_rules: list[dict[str, Any]],
        validation_type: str,
    ) -> dict[str, Any]:
        """
        Validate data against rules
        """
        try:
            validation_result = {
                "validation_type": validation_type,
                "timestamp": datetime.now(),
                "total_records": 0,
                "valid_records": 0,
                "invalid_records": 0,
                "validation_errors": [],
                "quality_score": 0.0,
                "rule_results": {},
            }

            # Extract data
            if "dataframe" in data_source:
                df = data_source["dataframe"]
            elif "records" in data_source:
                df = pd.DataFrame(data_source["records"])
            else:
                return {"error": "No valid data source provided"}

            validation_result["total_records"] = len(df)

            # Apply validation rules
            rule_results = {}
            all_errors = []

            for rule in validation_rules:
                rule_name = rule.get("name", "unnamed_rule")
                rule_result = await self._apply_validation_rule(df, rule)
                rule_results[rule_name] = rule_result

                if "errors" in rule_result:
                    all_errors.extend(rule_result["errors"])

            validation_result["rule_results"] = rule_results
            validation_result["validation_errors"] = all_errors
            validation_result["invalid_records"] = len(
                set(error["record_index"] for error in all_errors)
            )
            validation_result["valid_records"] = (
                validation_result["total_records"] - validation_result["invalid_records"]
            )

            # Calculate quality score
            validation_result["quality_score"] = await self._calculate_quality_score(
                validation_result
            )

            # Log validation
            await self._log_quality_check("validation", validation_result)

            return validation_result

        except Exception as e:
            logger.error(f"Data validation failed: {e}")
            return {"error": str(e), "status": "validation_failed"}

    async def _apply_validation_rule(
        self, df: pd.DataFrame, rule: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Apply a specific validation rule
        """
        try:
            rule_type = rule.get("type", "")
            column = rule.get("column", "")

            if rule_type == "range_check":
                return await self._validate_range(df, column, rule)
            elif rule_type == "format_check":
                return await self._validate_format(df, column, rule)
            elif rule_type == "categorical_check":
                return await self._validate_categorical(df, column, rule)
            elif rule_type == "uniqueness_check":
                return await self._validate_uniqueness(df, column, rule)
            elif rule_type == "completeness_check":
                return await self._validate_completeness(df, column, rule)
            elif rule_type == "consistency_check":
                return await self._validate_consistency(df, rule)
            else:
                return {"error": f"Unknown rule type: {rule_type}"}

        except Exception as e:
            logger.error(f"Validation rule application failed: {e}")
            return {"error": str(e)}

    async def _validate_range(
        self, df: pd.DataFrame, column: str, rule: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Validate numeric range
        """
        try:
            if column not in df.columns:
                return {"error": f"Column {column} not found"}

            min_val = rule.get("min_value")
            max_val = rule.get("max_value")
            allow_null = rule.get("allow_null", False)

            errors = []

            for idx, value in df[column].items():
                if pd.isna(value):
                    if not allow_null:
                        errors.append(
                            {
                                "record_index": idx,
                                "column": column,
                                "error_type": "null_value",
                                "value": None,
                            }
                        )
                elif not isinstance(value, (int, float)):
                    errors.append(
                        {
                            "record_index": idx,
                            "column": column,
                            "error_type": "invalid_type",
                            "value": value,
                        }
                    )
                else:
                    if min_val is not None and value < min_val:
                        errors.append(
                            {
                                "record_index": idx,
                                "column": column,
                                "error_type": "below_minimum",
                                "value": value,
                                "expected": f">= {min_val}",
                            }
                        )
                    if max_val is not None and value > max_val:
                        errors.append(
                            {
                                "record_index": idx,
                                "column": column,
                                "error_type": "above_maximum",
                                "value": value,
                                "expected": f"<= {max_val}",
                            }
                        )

            return {
                "rule_type": "range_check",
                "column": column,
                "errors": errors,
                "error_count": len(errors),
                "valid_count": len(df) - len(errors),
            }

        except Exception as e:
            logger.error(f"Range validation failed: {e}")
            return {"error": str(e)}

    async def _validate_format(
        self, df: pd.DataFrame, column: str, rule: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Validate data format using regex patterns
        """
        try:
            if column not in df.columns:
                return {"error": f"Column {column} not found"}

            pattern_name = rule.get("pattern_name")
            custom_pattern = rule.get("pattern")
            allow_null = rule.get("allow_null", False)

            # Get pattern
            if pattern_name and pattern_name in self.validation_patterns:
                pattern = self.validation_patterns[pattern_name]
            elif custom_pattern:
                pattern = custom_pattern
            else:
                return {"error": "No pattern specified"}

            errors = []
            compiled_pattern = re.compile(pattern)

            for idx, value in df[column].items():
                if pd.isna(value):
                    if not allow_null:
                        errors.append(
                            {
                                "record_index": idx,
                                "column": column,
                                "error_type": "null_value",
                                "value": None,
                            }
                        )
                else:
                    value_str = str(value)
                    if not compiled_pattern.match(value_str):
                        errors.append(
                            {
                                "record_index": idx,
                                "column": column,
                                "error_type": "format_mismatch",
                                "value": value_str,
                                "expected_pattern": pattern,
                            }
                        )

            return {
                "rule_type": "format_check",
                "column": column,
                "pattern": pattern,
                "errors": errors,
                "error_count": len(errors),
                "valid_count": len(df) - len(errors),
            }

        except Exception as e:
            logger.error(f"Format validation failed: {e}")
            return {"error": str(e)}

    async def _validate_categorical(
        self, df: pd.DataFrame, column: str, rule: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Validate categorical values
        """
        try:
            if column not in df.columns:
                return {"error": f"Column {column} not found"}

            allowed_values = rule.get("allowed_values", [])
            allow_null = rule.get("allow_null", False)

            errors = []

            for idx, value in df[column].items():
                if pd.isna(value):
                    if not allow_null:
                        errors.append(
                            {
                                "record_index": idx,
                                "column": column,
                                "error_type": "null_value",
                                "value": None,
                            }
                        )
                elif value not in allowed_values:
                    errors.append(
                        {
                            "record_index": idx,
                            "column": column,
                            "error_type": "invalid_category",
                            "value": value,
                            "allowed_values": allowed_values,
                        }
                    )

            return {
                "rule_type": "categorical_check",
                "column": column,
                "allowed_values": allowed_values,
                "errors": errors,
                "error_count": len(errors),
                "valid_count": len(df) - len(errors),
            }

        except Exception as e:
            logger.error(f"Categorical validation failed: {e}")
            return {"error": str(e)}

    async def _validate_uniqueness(
        self, df: pd.DataFrame, columns: list[str], rule: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Validate uniqueness constraints
        """
        try:
            allow_duplicates = rule.get("allow_duplicates", False)

            errors = []

            if len(columns) == 1:
                # Single column uniqueness
                column = columns[0]
                if column not in df.columns:
                    return {"error": f"Column {column} not found"}

                duplicates = df[df[column].duplicated(keep=False)]
                if not duplicates.empty and not allow_duplicates:
                    for idx in duplicates.index:
                        errors.append(
                            {
                                "record_index": idx,
                                "column": column,
                                "error_type": "duplicate_value",
                                "value": df.loc[idx, column],
                            }
                        )
            else:
                # Multi-column uniqueness
                missing_columns = [col for col in columns if col not in df.columns]
                if missing_columns:
                    return {"error": f"Columns not found: {missing_columns}"}

                subset_df = df[columns]
                duplicates = subset_df[subset_df.duplicated(keep=False)]

                if not duplicates.empty and not allow_duplicates:
                    for idx in duplicates.index:
                        errors.append(
                            {
                                "record_index": idx,
                                "columns": columns,
                                "error_type": "duplicate_combination",
                                "values": {col: df.loc[idx, col] for col in columns},
                            }
                        )

            return {
                "rule_type": "uniqueness_check",
                "columns": columns,
                "errors": errors,
                "error_count": len(errors),
                "valid_count": len(df) - len(errors),
            }

        except Exception as e:
            logger.error(f"Uniqueness validation failed: {e}")
            return {"error": str(e)}

    async def _validate_completeness(
        self, df: pd.DataFrame, column: str, rule: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Validate data completeness
        """
        try:
            if column not in df.columns:
                return {"error": f"Column {column} not found"}

            threshold = rule.get("threshold", 0.95)

            null_count = df[column].isnull().sum()
            completeness_ratio = 1 - (null_count / len(df))

            errors = []
            if completeness_ratio < threshold:
                errors.append(
                    {
                        "column": column,
                        "error_type": "low_completeness",
                        "completeness_ratio": completeness_ratio,
                        "threshold": threshold,
                        "null_count": null_count,
                    }
                )

            return {
                "rule_type": "completeness_check",
                "column": column,
                "completeness_ratio": completeness_ratio,
                "threshold": threshold,
                "errors": errors,
                "error_count": len(errors),
            }

        except Exception as e:
            logger.error(f"Completeness validation failed: {e}")
            return {"error": str(e)}

    async def _validate_consistency(self, df: pd.DataFrame, rule: dict[str, Any]) -> dict[str, Any]:
        """
        Validate data consistency across columns
        """
        try:
            consistency_checks = rule.get("checks", [])

            errors = []

            for check in consistency_checks:
                check_type = check.get("type")

                if check_type == "conditional":
                    # Example: if column A has value X, column B should have value Y
                    condition_column = check.get("condition_column")
                    condition_value = check.get("condition_value")
                    target_column = check.get("target_column")
                    expected_value = check.get("expected_value")

                    if all(col in df.columns for col in [condition_column, target_column]):
                        inconsistent_rows = df[
                            (df[condition_column] == condition_value)
                            & (df[target_column] != expected_value)
                        ]

                        for idx in inconsistent_rows.index:
                            errors.append(
                                {
                                    "record_index": idx,
                                    "error_type": "consistency_violation",
                                    "condition": f"{condition_column} == {condition_value}",
                                    "expected": f"{target_column} == {expected_value}",
                                    "actual": df.loc[idx, target_column],
                                }
                            )

                elif check_type == "referential_integrity":
                    # Check foreign key relationships
                    parent_table = check.get("parent_table")
                    check.get("parent_key")
                    child_column = check.get("child_column")

                    if child_column in df.columns:
                        # This would require database access to check referential integrity
                        # Simplified version - check for nulls in required foreign keys
                        if check.get("required", False):
                            null_refs = df[df[child_column].isnull()]
                            for idx in null_refs.index:
                                errors.append(
                                    {
                                        "record_index": idx,
                                        "column": child_column,
                                        "error_type": "missing_reference",
                                        "reference_table": parent_table,
                                    }
                                )

            return {
                "rule_type": "consistency_check",
                "checks": consistency_checks,
                "errors": errors,
                "error_count": len(errors),
            }

        except Exception as e:
            logger.error(f"Consistency validation failed: {e}")
            return {"error": str(e)}

    async def _calculate_quality_score(self, validation_result: dict[str, Any]) -> float:
        """
        Calculate overall quality score
        """
        try:
            total_records = validation_result.get("total_records", 0)
            invalid_records = validation_result.get("invalid_records", 0)

            if total_records == 0:
                return 0.0

            # Base score from validation
            base_score = 1 - (invalid_records / total_records)

            # Adjust based on rule results
            rule_penalty = 0
            rule_results = validation_result.get("rule_results", {})

            for rule_name, rule_result in rule_results.items():
                if "error_count" in rule_result:
                    error_count = rule_result["error_count"]
                    rule_penalty += error_count / total_records

            # Final score
            quality_score = max(0, base_score - rule_penalty)

            return round(quality_score, 4)

        except Exception as e:
            logger.error(f"Quality score calculation failed: {e}")
            return 0.0

    async def _handle_quality_assessment(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle quality assessment request
        """
        try:
            data_source = message.content.get("data_source", {})
            assessment_type = message.content.get("assessment_type", "comprehensive")
            dimensions = message.content.get("dimensions", self.dq_config["quality_dimensions"])

            # Assess data quality
            assessment_result = await self._assess_data_quality(
                data_source, assessment_type, dimensions
            )

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "quality_assessment_response",
                    "assessment_type": assessment_type,
                    "dimensions": dimensions,
                    "result": assessment_result,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Quality assessment handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _assess_data_quality(
        self, data_source: dict[str, Any], assessment_type: str, dimensions: list[str]
    ) -> dict[str, Any]:
        """
        Assess data quality across multiple dimensions
        """
        try:
            assessment_result = {
                "assessment_type": assessment_type,
                "dimensions": dimensions,
                "timestamp": datetime.now(),
                "overall_score": 0.0,
                "dimension_scores": {},
                "recommendations": [],
            }

            # Extract data
            if "dataframe" in data_source:
                df = data_source["dataframe"]
            elif "records" in data_source:
                df = pd.DataFrame(data_source["records"])
            else:
                return {"error": "No valid data source provided"}

            # Assess each dimension
            dimension_scores = {}

            for dimension in dimensions:
                if dimension == "accuracy":
                    score = await self._assess_accuracy(df)
                elif dimension == "completeness":
                    score = await self._assess_completeness(df)
                elif dimension == "consistency":
                    score = await self._assess_consistency(df)
                elif dimension == "timeliness":
                    score = await self._assess_timeliness(df)
                elif dimension == "validity":
                    score = await self._assess_validity(df)
                elif dimension == "uniqueness":
                    score = await self._assess_uniqueness(df)
                else:
                    score = {"score": 0.5, "details": f"Unknown dimension: {dimension}"}

                dimension_scores[dimension] = score

            assessment_result["dimension_scores"] = dimension_scores

            # Calculate overall score
            scores = [dim_score.get("score", 0) for dim_score in dimension_scores.values()]
            assessment_result["overall_score"] = (
                round(sum(scores) / len(scores), 4) if scores else 0.0
            )

            # Generate recommendations
            assessment_result["recommendations"] = await self._generate_quality_recommendations(
                dimension_scores
            )

            # Log assessment
            await self._log_quality_check("assessment", assessment_result)

            return assessment_result

        except Exception as e:
            logger.error(f"Quality assessment failed: {e}")
            return {"error": str(e), "status": "assessment_failed"}

    async def _assess_accuracy(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Assess data accuracy
        """
        try:
            accuracy_checks = []

            for column in df.columns:
                column_accuracy = {"column": column, "issues": 0, "total": len(df)}

                # Check for obvious inaccuracies
                if df[column].dtype in ["int64", "float64"]:
                    # Check for negative values where they shouldn't exist
                    if column.lower() in ["age", "count", "quantity", "price"]:
                        negatives = (df[column] < 0).sum()
                        if negatives > 0:
                            column_accuracy["issues"] += negatives
                            accuracy_checks.append(f"Negative values in {column}: {negatives}")

                    # Check for outliers using IQR
                    Q1 = df[column].quantile(0.25)
                    Q3 = df[column].quantile(0.75)
                    IQR = Q3 - Q1
                    outliers = (
                        (df[column] < (Q1 - 1.5 * IQR)) | (df[column] > (Q3 + 1.5 * IQR))
                    ).sum()
                    if outliers > 0:
                        column_accuracy["issues"] += outliers
                        accuracy_checks.append(f"Outliers in {column}: {outliers}")

                elif df[column].dtype == "object":
                    # Check for suspicious patterns
                    suspicious_patterns = ["test", "dummy", "null", "n/a", "unknown"]
                    suspicious_count = df[column].str.lower().isin(suspicious_patterns).sum()
                    if suspicious_count > 0:
                        column_accuracy["issues"] += suspicious_count
                        accuracy_checks.append(f"Suspicious values in {column}: {suspicious_count}")

            total_issues = sum(check["issues"] for check in accuracy_checks)
            total_values = sum(check["total"] for check in accuracy_checks)

            accuracy_score = 1 - (total_issues / total_values) if total_values > 0 else 1.0

            return {
                "score": round(accuracy_score, 4),
                "details": {
                    "total_issues": total_issues,
                    "total_values": total_values,
                    "checks": accuracy_checks,
                },
            }

        except Exception as e:
            logger.error(f"Accuracy assessment failed: {e}")
            return {"score": 0.5, "error": str(e)}

    async def _assess_completeness(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Assess data completeness
        """
        try:
            completeness_stats = {}

            for column in df.columns:
                null_count = df[column].isnull().sum()
                completeness_ratio = 1 - (null_count / len(df))
                completeness_stats[column] = {
                    "null_count": null_count,
                    "completeness_ratio": round(completeness_ratio, 4),
                }

            # Overall completeness
            avg_completeness = sum(
                stats["completeness_ratio"] for stats in completeness_stats.values()
            ) / len(completeness_stats)

            return {
                "score": round(avg_completeness, 4),
                "details": {
                    "column_stats": completeness_stats,
                    "average_completeness": round(avg_completeness, 4),
                },
            }

        except Exception as e:
            logger.error(f"Completeness assessment failed: {e}")
            return {"score": 0.5, "error": str(e)}

    async def _assess_consistency(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Assess data consistency
        """
        try:
            consistency_issues = 0
            total_checks = 0

            # Check for format consistency in similar columns
            date_columns = [col for col in df.columns if "date" in col.lower()]
            if len(date_columns) > 1:
                total_checks += 1
                # Check if date formats are consistent
                date_formats = []
                for col in date_columns:
                    try:
                        pd.to_datetime(df[col].dropna().head(10))
                        date_formats.append("consistent")
                    except Exception:
                        date_formats.append("inconsistent")

                if len(set(date_formats)) > 1:
                    consistency_issues += 1

            # Check for value range consistency
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            for col in numeric_columns:
                total_checks += 1
                if (
                    df[col].std() > df[col].mean() * 10
                ):  # High variance might indicate inconsistency
                    consistency_issues += 1

            consistency_score = 1 - (consistency_issues / total_checks) if total_checks > 0 else 1.0

            return {
                "score": round(consistency_score, 4),
                "details": {"consistency_issues": consistency_issues, "total_checks": total_checks},
            }

        except Exception as e:
            logger.error(f"Consistency assessment failed: {e}")
            return {"score": 0.5, "error": str(e)}

    async def _assess_timeliness(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Assess data timeliness
        """
        try:
            timeliness_score = 1.0
            timeliness_details = {}

            # Check for date/timestamp columns
            date_columns = []
            for col in df.columns:
                if (
                    df[col].dtype == "datetime64[ns]"
                    or "date" in col.lower()
                    or "time" in col.lower()
                ):
                    date_columns.append(col)

            if date_columns:
                for col in date_columns:
                    if df[col].dtype == "datetime64[ns]":
                        # Check how current the data is
                        max_date = df[col].max()
                        days_old = (datetime.now() - max_date).days

                        # Penalize data older than 30 days
                        if days_old > 30:
                            timeliness_score *= 0.8

                        timeliness_details[col] = {"max_date": str(max_date), "days_old": days_old}

            return {"score": round(timeliness_score, 4), "details": timeliness_details}

        except Exception as e:
            logger.error(f"Timeliness assessment failed: {e}")
            return {"score": 0.5, "error": str(e)}

    async def _assess_validity(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Assess data validity
        """
        try:
            validity_issues = 0
            total_values = 0

            for column in df.columns:
                total_values += len(df)

                if df[column].dtype in ["int64", "float64"]:
                    # Check for NaN or infinite values
                    invalid_count = df[column].isin([np.nan, np.inf, -np.inf]).sum()
                    validity_issues += invalid_count

                elif df[column].dtype == "object":
                    # Check for empty strings
                    empty_count = (df[column].str.strip() == "").sum()
                    validity_issues += empty_count

            validity_score = 1 - (validity_issues / total_values) if total_values > 0 else 1.0

            return {
                "score": round(validity_score, 4),
                "details": {"validity_issues": validity_issues, "total_values": total_values},
            }

        except Exception as e:
            logger.error(f"Validity assessment failed: {e}")
            return {"score": 0.5, "error": str(e)}

    async def _assess_uniqueness(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Assess data uniqueness
        """
        try:
            uniqueness_scores = {}

            for column in df.columns:
                unique_ratio = df[column].nunique() / len(df)
                uniqueness_scores[column] = round(unique_ratio, 4)

            # Overall uniqueness score (average)
            avg_uniqueness = sum(uniqueness_scores.values()) / len(uniqueness_scores)

            return {
                "score": round(avg_uniqueness, 4),
                "details": {
                    "column_uniqueness": uniqueness_scores,
                    "average_uniqueness": round(avg_uniqueness, 4),
                },
            }

        except Exception as e:
            logger.error(f"Uniqueness assessment failed: {e}")
            return {"score": 0.5, "error": str(e)}

    async def _generate_quality_recommendations(
        self, dimension_scores: dict[str, Any]
    ) -> list[str]:
        """
        Generate quality improvement recommendations
        """
        try:
            recommendations = []

            for dimension, score_info in dimension_scores.items():
                score = score_info.get("score", 1.0)
                threshold = self.dq_config["quality_thresholds"].get(dimension, 0.9)

                if score < threshold:
                    if dimension == "completeness":
                        recommendations.append(
                            "Consider data imputation techniques for missing values"
                        )
                        recommendations.append(
                            "Review data collection processes to reduce null values"
                        )
                    elif dimension == "accuracy":
                        recommendations.append("Implement outlier detection and removal procedures")
                        recommendations.append("Add business rule validations for data entry")
                    elif dimension == "consistency":
                        recommendations.append("Standardize data formats across similar columns")
                        recommendations.append("Implement cross-field validation rules")
                    elif dimension == "timeliness":
                        recommendations.append("Review data refresh schedules and frequencies")
                        recommendations.append("Implement real-time data validation")
                    elif dimension == "validity":
                        recommendations.append("Add format validation at data entry points")
                        recommendations.append("Implement data type constraints")
                    elif dimension == "uniqueness":
                        recommendations.append("Review duplicate detection and removal processes")
                        recommendations.append("Implement unique key constraints")

            return recommendations

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")
            return []

    async def _handle_anomaly_detection(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle anomaly detection request
        """
        try:
            data_source = message.content.get("data_source", {})
            detection_method = message.content.get("detection_method", "statistical")
            sensitivity = message.content.get("sensitivity", 0.05)

            # Detect anomalies
            anomaly_result = await self._detect_anomalies(
                data_source, detection_method, sensitivity
            )

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "anomaly_detection_response",
                    "detection_method": detection_method,
                    "sensitivity": sensitivity,
                    "result": anomaly_result,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Anomaly detection handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _detect_anomalies(
        self, data_source: dict[str, Any], detection_method: str, sensitivity: float
    ) -> dict[str, Any]:
        """
        Detect anomalies in data
        """
        try:
            anomaly_result = {
                "detection_method": detection_method,
                "sensitivity": sensitivity,
                "timestamp": datetime.now(),
                "anomalies_detected": 0,
                "total_records": 0,
                "anomaly_score": 0.0,
                "anomalous_records": [],
            }

            # Extract data
            if "dataframe" in data_source:
                df = data_source["dataframe"]
            elif "records" in data_source:
                df = pd.DataFrame(data_source["records"])
            else:
                return {"error": "No valid data source provided"}

            anomaly_result["total_records"] = len(df)

            # Apply anomaly detection
            if detection_method == "statistical":
                anomalies = await self._statistical_anomaly_detection(df, sensitivity)
            elif detection_method == "ml_based":
                anomalies = await self._ml_anomaly_detection(df, sensitivity)
            elif detection_method == "isolation_forest":
                anomalies = await self._isolation_forest_detection(df, sensitivity)
            else:
                return {"error": f"Unsupported detection method: {detection_method}"}

            anomaly_result["anomalies_detected"] = len(anomalies)
            anomaly_result["anomalous_records"] = anomalies
            anomaly_result["anomaly_score"] = len(anomalies) / len(df) if len(df) > 0 else 0.0

            # Log anomalies
            await self._log_anomaly_detection(anomaly_result)

            return anomaly_result

        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return {"error": str(e), "status": "detection_failed"}

    async def _statistical_anomaly_detection(
        self, df: pd.DataFrame, sensitivity: float
    ) -> list[dict[str, Any]]:
        """
        Statistical anomaly detection using z-score and IQR
        """
        try:
            anomalies = []

            # Process numeric columns
            numeric_columns = df.select_dtypes(include=[np.number]).columns

            for col in numeric_columns:
                # Z-score method
                z_scores = np.abs((df[col] - df[col].mean()) / df[col].std())
                z_anomalies = df[z_scores > 3]  # 3 standard deviations

                # IQR method
                Q1 = df[col].quantile(0.25)
                Q3 = df[col].quantile(0.75)
                IQR = Q3 - Q1
                iqr_anomalies = df[(df[col] < (Q1 - 1.5 * IQR)) | (df[col] > (Q3 + 1.5 * IQR))]

                # Combine anomalies
                all_anomalies = pd.concat([z_anomalies, iqr_anomalies]).drop_duplicates()

                for idx in all_anomalies.index:
                    anomalies.append(
                        {
                            "record_index": idx,
                            "column": col,
                            "value": df.loc[idx, col],
                            "method": "statistical",
                            "reason": f"Outlier in {col}",
                        }
                    )

            return anomalies

        except Exception as e:
            logger.error(f"Statistical anomaly detection failed: {e}")
            return []

    async def _ml_anomaly_detection(
        self, df: pd.DataFrame, sensitivity: float
    ) -> list[dict[str, Any]]:
        """
        ML-based anomaly detection
        """
        try:
            anomalies = []

            # Prepare numeric data
            numeric_data = df.select_dtypes(include=[np.number])

            if not numeric_data.empty:
                # Scale data
                scaler = StandardScaler()
                scaled_data = scaler.fit_transform(numeric_data)

                # Use isolation forest
                if self.anomaly_detectors["isolation_forest"]:
                    predictions = self.anomaly_detectors["isolation_forest"].fit_predict(
                        scaled_data
                    )

                    # Anomalies are marked as -1
                    anomaly_indices = np.where(predictions == -1)[0]

                    for idx in anomaly_indices:
                        anomalies.append(
                            {
                                "record_index": df.index[idx],
                                "method": "ml_isolation_forest",
                                "reason": "Anomaly detected by isolation forest",
                                "confidence": 0.8,
                            }
                        )

            return anomalies

        except Exception as e:
            logger.error(f"ML anomaly detection failed: {e}")
            return []

    async def _isolation_forest_detection(
        self, df: pd.DataFrame, sensitivity: float
    ) -> list[dict[str, Any]]:
        """
        Isolation Forest anomaly detection
        """
        try:
            anomalies = []

            # Prepare numeric data
            numeric_data = df.select_dtypes(include=[np.number])

            if not numeric_data.empty:
                # Configure contamination based on sensitivity
                contamination = min(sensitivity, 0.1)  # Cap at 10%

                # Fit isolation forest
                iso_forest = IsolationForest(contamination=contamination, random_state=42)
                predictions = iso_forest.fit_predict(numeric_data)

                # Anomalies are marked as -1
                anomaly_indices = np.where(predictions == -1)[0]

                for idx in anomaly_indices:
                    anomaly_scores = iso_forest.decision_function(numeric_data.iloc[idx : idx + 1])
                    confidence = 1 - anomaly_scores[0]  # Convert to confidence score

                    anomalies.append(
                        {
                            "record_index": df.index[idx],
                            "method": "isolation_forest",
                            "reason": "Anomaly detected by isolation forest",
                            "confidence": round(float(confidence), 4),
                        }
                    )

            return anomalies

        except Exception as e:
            logger.error(f"Isolation forest detection failed: {e}")
            return []

    async def _handle_data_profiling(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle data profiling request
        """
        try:
            data_source = message.content.get("data_source", {})
            profiling_type = message.content.get("profiling_type", "comprehensive")

            # Profile data
            profile_result = await self._profile_data(data_source, profiling_type)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "data_profiling_response",
                    "profiling_type": profiling_type,
                    "result": profile_result,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Data profiling handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _profile_data(
        self, data_source: dict[str, Any], profiling_type: str
    ) -> dict[str, Any]:
        """
        Profile data to understand its characteristics
        """
        try:
            profile_result = {
                "profiling_type": profiling_type,
                "timestamp": datetime.now(),
                "dataset_info": {},
                "column_profiles": {},
                "data_patterns": {},
                "quality_insights": {},
            }

            # Extract data
            if "dataframe" in data_source:
                df = data_source["dataframe"]
            elif "records" in data_source:
                df = pd.DataFrame(data_source["records"])
            else:
                return {"error": "No valid data source provided"}

            # Dataset info
            profile_result["dataset_info"] = {
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "memory_usage": df.memory_usage(deep=True).sum(),
                "data_types": df.dtypes.to_dict(),
            }

            # Column profiles
            column_profiles = {}
            for column in df.columns:
                column_profile = await self._profile_column(df, column)
                column_profiles[column] = column_profile

            profile_result["column_profiles"] = column_profiles

            # Data patterns
            if profiling_type == "comprehensive":
                profile_result["data_patterns"] = await self._analyze_data_patterns(df)

            # Quality insights
            profile_result["quality_insights"] = await self._generate_quality_insights(
                df, column_profiles
            )

            return profile_result

        except Exception as e:
            logger.error(f"Data profiling failed: {e}")
            return {"error": str(e), "status": "profiling_failed"}

    async def _profile_column(self, df: pd.DataFrame, column: str) -> dict[str, Any]:
        """
        Profile a single column
        """
        try:
            column_data = df[column]
            profile = {
                "data_type": str(column_data.dtype),
                "null_count": column_data.isnull().sum(),
                "null_percentage": round(column_data.isnull().sum() / len(df) * 100, 2),
                "unique_count": column_data.nunique(),
                "unique_percentage": round(column_data.nunique() / len(df) * 100, 2),
            }

            # Type-specific profiling
            if column_data.dtype in ["int64", "float64"]:
                profile.update(
                    {
                        "min": float(column_data.min()) if not column_data.empty else None,
                        "max": float(column_data.max()) if not column_data.empty else None,
                        "mean": (
                            round(float(column_data.mean()), 4) if not column_data.empty else None
                        ),
                        "median": (
                            round(float(column_data.median()), 4) if not column_data.empty else None
                        ),
                        "std": (
                            round(float(column_data.std()), 4) if not column_data.empty else None
                        ),
                        "quartiles": {
                            "25%": round(float(column_data.quantile(0.25)), 4),
                            "50%": round(float(column_data.quantile(0.5)), 4),
                            "75%": round(float(column_data.quantile(0.75)), 4),
                        },
                    }
                )

            elif column_data.dtype == "object":
                # Text statistics
                non_null_data = column_data.dropna()
                if not non_null_data.empty:
                    text_lengths = non_null_data.str.len()
                    profile.update(
                        {
                            "avg_length": round(float(text_lengths.mean()), 2),
                            "min_length": int(text_lengths.min()),
                            "max_length": int(text_lengths.max()),
                            "most_common": column_data.value_counts().head(5).to_dict(),
                        }
                    )

            return profile

        except Exception as e:
            logger.error(f"Column profiling failed for {column}: {e}")
            return {"error": str(e)}

    async def _analyze_data_patterns(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Analyze data patterns and relationships
        """
        try:
            patterns = {"correlations": {}, "dependencies": [], "distributions": {}}

            # Correlation analysis for numeric columns
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            if len(numeric_columns) > 1:
                correlation_matrix = df[numeric_columns].corr()
                patterns["correlations"] = correlation_matrix.to_dict()

            # Distribution analysis
            for column in df.columns:
                if df[column].dtype in ["int64", "float64"]:
                    # Simple distribution info
                    patterns["distributions"][column] = {
                        "skewness": round(float(df[column].skew()), 4),
                        "kurtosis": round(float(df[column].kurtosis()), 4),
                    }

            return patterns

        except Exception as e:
            logger.error(f"Data pattern analysis failed: {e}")
            return {}

    async def _generate_quality_insights(
        self, df: pd.DataFrame, column_profiles: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Generate quality insights from profiling data
        """
        try:
            insights = {
                "high_null_columns": [],
                "low_uniqueness_columns": [],
                "potential_issues": [],
            }

            for column, profile in column_profiles.items():
                # High null percentage
                if profile.get("null_percentage", 0) > 20:
                    insights["high_null_columns"].append(
                        {"column": column, "null_percentage": profile["null_percentage"]}
                    )

                # Low uniqueness (potential categorical)
                if (
                    profile.get("unique_percentage", 100) < 5
                    and profile.get("unique_count", 0) < 20
                ):
                    insights["low_uniqueness_columns"].append(
                        {"column": column, "unique_count": profile["unique_count"]}
                    )

            return insights

        except Exception as e:
            logger.error(f"Quality insights generation failed: {e}")
            return {}

    async def _handle_rule_checking(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle rule checking request
        """
        try:
            data_source = message.content.get("data_source", {})
            rules = message.content.get("rules", [])

            # Check rules
            rule_check_result = await self._check_rules(data_source, rules)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "rule_checking_response", "result": rule_check_result},
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Rule checking handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _check_rules(
        self, data_source: dict[str, Any], rules: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Check custom rules against data
        """
        try:
            rule_check_result = {
                "timestamp": datetime.now(),
                "total_rules": len(rules),
                "passed_rules": 0,
                "failed_rules": 0,
                "rule_results": {},
            }

            # Extract data
            if "dataframe" in data_source:
                df = data_source["dataframe"]
            elif "records" in data_source:
                df = pd.DataFrame(data_source["records"])
            else:
                return {"error": "No valid data source provided"}

            # Check each rule
            rule_results = {}
            for rule in rules:
                rule_name = rule.get("name", f"rule_{len(rule_results)}")
                rule_result = await self._evaluate_custom_rule(df, rule)
                rule_results[rule_name] = rule_result

                if rule_result.get("passed", False):
                    rule_check_result["passed_rules"] += 1
                else:
                    rule_check_result["failed_rules"] += 1

            rule_check_result["rule_results"] = rule_results

            return rule_check_result

        except Exception as e:
            logger.error(f"Rule checking failed: {e}")
            return {"error": str(e), "status": "rule_check_failed"}

    async def _evaluate_custom_rule(self, df: pd.DataFrame, rule: dict[str, Any]) -> dict[str, Any]:
        """
        Evaluate a custom rule
        """
        try:
            rule_type = rule.get("type")
            condition = rule.get("condition")

            if rule_type == "sql_like":
                # SQL-like condition evaluation
                result = await self._evaluate_sql_condition(df, condition)
            elif rule_type == "python_expression":
                # Python expression evaluation
                result = await self._evaluate_python_expression(df, condition)
            else:
                return {"error": f"Unsupported rule type: {rule_type}"}

            return {
                "rule": rule,
                "passed": result.get("passed", False),
                "violations": result.get("violations", 0),
                "details": result,
            }

        except Exception as e:
            logger.error(f"Custom rule evaluation failed: {e}")
            return {"error": str(e), "passed": False}

    async def _evaluate_sql_condition(self, df: pd.DataFrame, condition: str) -> dict[str, Any]:
        """
        Evaluate SQL-like condition
        """
        try:
            # Simple SQL-like condition parser (basic implementation)
            # This would need a more sophisticated parser for complex conditions

            # For now, support basic conditions like "column > value"
            if ">" in condition:
                parts = condition.split(">")
                if len(parts) == 2:
                    column = parts[0].strip()
                    value = float(parts[1].strip())

                    if column in df.columns:
                        violations = (df[column] <= value).sum()
                        return {
                            "passed": violations == 0,
                            "violations": int(violations),
                            "condition": condition,
                        }

            return {"passed": False, "violations": 0, "error": "Unsupported condition format"}

        except Exception as e:
            logger.error(f"SQL condition evaluation failed: {e}")
            return {"passed": False, "violations": 0, "error": str(e)}

    async def _evaluate_python_expression(
        self, df: pd.DataFrame, expression: str
    ) -> dict[str, Any]:
        """
        Evaluate Python expression
        """
        try:
            # Safe evaluation of Python expressions
            # This is a simplified implementation - in production, use restricted execution

            # For basic expressions like "df['column'] > 100"
            local_vars = {"df": df, "np": np, "pd": pd}

            result = eval(expression, {"__builtins__": {}}, local_vars)

            if isinstance(result, pd.Series):
                violations = (~result).sum()
                return {
                    "passed": violations == 0,
                    "violations": int(violations),
                    "expression": expression,
                }
            else:
                return {"passed": bool(result), "expression": expression}

        except Exception as e:
            logger.error(f"Python expression evaluation failed: {e}")
            return {"passed": False, "error": str(e)}

    async def _handle_quality_report(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle quality report generation request
        """
        try:
            data_source_id = message.content.get("data_source_id")
            report_type = message.content.get("report_type", "comprehensive")
            time_range = message.content.get("time_range", "last_30_days")

            # Generate quality report
            report_result = await self._generate_quality_report(
                data_source_id, report_type, time_range
            )

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "quality_report_response",
                    "report_type": report_type,
                    "time_range": time_range,
                    "result": report_result,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Quality report handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _generate_quality_report(
        self, data_source_id: str | None, report_type: str, time_range: str
    ) -> dict[str, Any]:
        """
        Generate comprehensive quality report
        """
        try:
            report = {
                "report_type": report_type,
                "time_range": time_range,
                "generated_at": datetime.now(),
                "data_sources": {},
                "quality_trends": {},
                "alerts_summary": {},
                "recommendations": [],
            }

            # Get time range
            start_date = await self._parse_time_range(time_range)

            # Generate report based on type
            if report_type == "comprehensive":
                report["data_sources"] = await self._get_data_source_quality_summary(start_date)
                report["quality_trends"] = await self._get_quality_trends(start_date)
                report["alerts_summary"] = await self._get_alerts_summary(start_date)

            elif report_type == "data_source":
                if data_source_id:
                    report["data_sources"][data_source_id] = await self._get_data_source_report(
                        data_source_id, start_date
                    )

            elif report_type == "trends":
                report["quality_trends"] = await self._get_quality_trends(start_date)

            # Generate recommendations
            report["recommendations"] = await self._generate_report_recommendations(report)

            return report

        except Exception as e:
            logger.error(f"Quality report generation failed: {e}")
            return {"error": str(e), "status": "report_generation_failed"}

    async def _parse_time_range(self, time_range: str) -> datetime:
        """
        Parse time range string to datetime
        """
        try:
            now = datetime.now()

            if time_range == "last_24_hours":
                return now - timedelta(hours=24)
            elif time_range == "last_7_days":
                return now - timedelta(days=7)
            elif time_range == "last_30_days":
                return now - timedelta(days=30)
            elif time_range == "last_90_days":
                return now - timedelta(days=90)
            else:
                return now - timedelta(days=30)  # Default to 30 days

        except Exception as e:
            logger.error(f"Time range parsing failed: {e}")
            return datetime.now() - timedelta(days=30)

    async def _get_data_source_quality_summary(self, start_date: datetime) -> dict[str, Any]:
        """
        Get quality summary for all data sources
        """
        try:
            summary = {}

            # This would query the database for quality metrics
            # Simplified implementation
            for source_id, source_data in self.quality_state["data_sources"].items():
                summary[source_id] = {
                    "latest_quality_score": source_data.get("latest_score", 0.0),
                    "trend": source_data.get("trend", "stable"),
                    "last_updated": source_data.get("last_updated"),
                }

            return summary

        except Exception as e:
            logger.error(f"Data source quality summary failed: {e}")
            return {}

    async def _get_quality_trends(self, start_date: datetime) -> dict[str, Any]:
        """
        Get quality trends over time
        """
        try:
            trends = {}

            # Analyze quality log for trends
            quality_logs = [
                log for log in self.quality_state["quality_log"] if log["timestamp"] > start_date
            ]

            # Group by data source and calculate trends
            source_trends = {}
            for log in quality_logs:
                source_id = log.get("data_source_id", "unknown")
                if source_id not in source_trends:
                    source_trends[source_id] = []
                source_trends[source_id].append(log)

            for source_id, logs in source_trends.items():
                if logs:
                    scores = [log.get("quality_score", 0) for log in logs]
                    trends[source_id] = {
                        "average_score": round(sum(scores) / len(scores), 4),
                        "min_score": min(scores),
                        "max_score": max(scores),
                        "trend": await self._calculate_trend(scores),
                        "data_points": len(scores),
                    }

            return trends

        except Exception as e:
            logger.error(f"Quality trends calculation failed: {e}")
            return {}

    async def _calculate_trend(self, scores: list[float]) -> str:
        """
        Calculate trend from score series
        """
        try:
            if len(scores) < 2:
                return "insufficient_data"

            # Simple linear trend
            x = list(range(len(scores)))
            slope = np.polyfit(x, scores, 1)[0]

            if slope > 0.01:
                return "improving"
            elif slope < -0.01:
                return "degrading"
            else:
                return "stable"

        except Exception as e:
            logger.error(f"Trend calculation failed: {e}")
            return "unknown"

    async def _get_alerts_summary(self, start_date: datetime) -> dict[str, Any]:
        """
        Get alerts summary
        """
        try:
            alerts = [
                alert for alert in self.quality_state["alerts"] if alert["timestamp"] > start_date
            ]

            summary = {
                "total_alerts": len(alerts),
                "by_severity": {},
                "by_type": {},
                "recent_alerts": alerts[-10:],  # Last 10 alerts
            }

            # Group by severity and type
            for alert in alerts:
                severity = alert.get("severity", "unknown")
                alert_type = alert.get("type", "unknown")

                summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
                summary["by_type"][alert_type] = summary["by_type"].get(alert_type, 0) + 1

            return summary

        except Exception as e:
            logger.error(f"Alerts summary failed: {e}")
            return {}

    async def _generate_report_recommendations(self, report: dict[str, Any]) -> list[str]:
        """
        Generate recommendations based on report data
        """
        try:
            recommendations = []

            # Analyze data sources
            for source_id, source_data in report.get("data_sources", {}).items():
                score = source_data.get("latest_quality_score", 1.0)
                if score < 0.8:
                    recommendations.append(
                        f"Improve data quality for {source_id} (current score: {score})"
                    )

            # Analyze trends
            for source_id, trend_data in report.get("quality_trends", {}).items():
                if trend_data.get("trend") == "degrading":
                    recommendations.append(f"Address quality degradation in {source_id}")

            # Analyze alerts
            alerts_summary = report.get("alerts_summary", {})
            if alerts_summary.get("total_alerts", 0) > 10:
                recommendations.append("Review and address high number of quality alerts")

            return recommendations

        except Exception as e:
            logger.error(f"Report recommendations generation failed: {e}")
            return []

    async def _handle_quality_monitoring(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle quality monitoring request
        """
        try:
            monitoring_config = message.content.get("monitoring_config", {})

            # Start/stop monitoring
            monitoring_result = await self._configure_quality_monitoring(monitoring_config)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "quality_monitoring_response", "result": monitoring_result},
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Quality monitoring handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _configure_quality_monitoring(self, config: dict[str, Any]) -> dict[str, Any]:
        """
        Configure quality monitoring
        """
        try:
            action = config.get("action", "status")

            if action == "start":
                # Start monitoring for data sources
                data_sources = config.get("data_sources", [])
                monitoring_result = await self._start_monitoring(data_sources)

            elif action == "stop":
                # Stop monitoring
                monitoring_result = await self._stop_monitoring()

            elif action == "status":
                # Get monitoring status
                monitoring_result = await self._get_monitoring_status()

            else:
                return {"error": f"Unsupported action: {action}"}

            return monitoring_result

        except Exception as e:
            logger.error(f"Quality monitoring configuration failed: {e}")
            return {"error": str(e)}

    async def _start_monitoring(self, data_sources: list[str]) -> dict[str, Any]:
        """
        Start quality monitoring for data sources
        """
        try:
            # This would set up monitoring for specified data sources
            # Simplified implementation
            self.quality_state["monitoring_active"] = True
            self.quality_state["monitored_sources"] = data_sources

            return {
                "status": "monitoring_started",
                "monitored_sources": data_sources,
                "monitoring_interval": 300,  # 5 minutes
            }

        except Exception as e:
            logger.error(f"Monitoring start failed: {e}")
            return {"error": str(e)}

    async def _stop_monitoring(self) -> dict[str, Any]:
        """
        Stop quality monitoring
        """
        try:
            self.quality_state["monitoring_active"] = False
            self.quality_state["monitored_sources"] = []

            return {"status": "monitoring_stopped"}

        except Exception as e:
            logger.error(f"Monitoring stop failed: {e}")
            return {"error": str(e)}

    async def _get_monitoring_status(self) -> dict[str, Any]:
        """
        Get monitoring status
        """
        try:
            return {
                "monitoring_active": self.quality_state.get("monitoring_active", False),
                "monitored_sources": self.quality_state.get("monitored_sources", []),
                "last_check": self.quality_state.get("last_monitoring_check"),
                "alerts_count": len(self.quality_state["alerts"]),
            }

        except Exception as e:
            logger.error(f"Monitoring status retrieval failed: {e}")
            return {"error": str(e)}

    # Additional helper methods would continue here...

    async def _process_validation_item(self, item: dict[str, Any]):
        """Process validation item from queue"""
        try:
            # Implementation for processing queued validation items
            pass
        except Exception as e:
            logger.error(f"Validation item processing failed: {e}")

    async def _validate_recent_data(self):
        """Validate recently added data"""
        try:
            # Implementation for validating recent data
            pass
        except Exception as e:
            logger.error(f"Recent data validation failed: {e}")

    async def _update_quality_metrics(self):
        """Update quality metrics"""
        try:
            # Implementation for updating quality metrics
            pass
        except Exception as e:
            logger.error(f"Quality metrics update failed: {e}")

    async def _check_quality_thresholds(self):
        """Check quality thresholds and generate alerts"""
        try:
            # Implementation for threshold checking
            pass
        except Exception as e:
            logger.error(f"Quality threshold check failed: {e}")

    async def _detect_quality_degradation(self):
        """Detect quality degradation trends"""
        try:
            # Implementation for quality degradation detection
            pass
        except Exception as e:
            logger.error(f"Quality degradation detection failed: {e}")

    async def _generate_quality_alerts(self):
        """Generate quality alerts"""
        try:
            # Implementation for alert generation
            pass
        except Exception as e:
            logger.error(f"Quality alert generation failed: {e}")

    async def _profile_new_sources(self):
        """Profile new data sources"""
        try:
            # Implementation for profiling new sources
            pass
        except Exception as e:
            logger.error(f"New source profiling failed: {e}")

    async def _update_data_profiles(self):
        """Update data profiles"""
        try:
            # Implementation for profile updates
            pass
        except Exception as e:
            logger.error(f"Data profile update failed: {e}")

    async def _analyze_data_patterns(self):
        """Analyze data patterns"""
        try:
            # Implementation for pattern analysis
            pass
        except Exception as e:
            logger.error(f"Data pattern analysis failed: {e}")

    async def _log_quality_check(self, check_type: str, check_data: dict[str, Any]):
        """Log quality check"""
        try:
            log_entry = {
                "check_type": check_type,
                "check_data": check_data,
                "timestamp": datetime.now(),
            }
            self.quality_state["quality_log"].append(log_entry)
        except Exception as e:
            logger.error(f"Quality check logging failed: {e}")

    async def _log_anomaly_detection(self, anomaly_data: dict[str, Any]):
        """Log anomaly detection"""
        try:
            self.quality_state["anomaly_history"].append(anomaly_data)
        except Exception as e:
            logger.error(f"Anomaly detection logging failed: {e}")

    async def _get_data_source_report(self, source_id: str, start_date: datetime) -> dict[str, Any]:
        """Get report for specific data source"""
        try:
            # Implementation for data source specific report
            return {}
        except Exception as e:
            logger.error(f"Data source report generation failed: {e}")
            return {}


# ========== TEST ==========
if __name__ == "__main__":

    async def test_data_quality_agent():
        # Initialize data quality agent
        agent = DataQualityAgent()
        await agent.start()

        # Test data validation
        test_data = {
            "records": [
                {"name": "John", "age": 25, "email": "john@example.com", "salary": 50000},
                {"name": "Jane", "age": 30, "email": "jane@example.com", "salary": 60000},
                {"name": "Bob", "age": -5, "email": "invalid-email", "salary": 70000},
                {"name": "", "age": 35, "email": "alice@example.com", "salary": None},
            ]
        }

        validation_message = AgentMessage(
            id="test_validation",
            from_agent="test",
            to_agent="data_quality_agent",
            content={
                "type": "validate_data",
                "data_source": test_data,
                "validation_rules": [
                    {
                        "name": "age_range",
                        "type": "range_check",
                        "column": "age",
                        "min_value": 0,
                        "max_value": 120,
                    },
                    {
                        "name": "email_format",
                        "type": "format_check",
                        "column": "email",
                        "pattern_name": "email",
                    },
                    {
                        "name": "completeness",
                        "type": "completeness_check",
                        "column": "name",
                        "threshold": 0.8,
                    },
                ],
                "validation_type": "comprehensive",
            },
            timestamp=datetime.now(),
        )

        print("Testing data quality agent...")
        async for response in agent.process_message(validation_message):
            print(f"Validation response: {response.content.get('type')}")
            result = response.content.get("result", {})
            print(f"Quality score: {result.get('quality_score')}")
            print(f"Validation errors: {len(result.get('validation_errors', []))}")

        # Test quality assessment
        assessment_message = AgentMessage(
            id="test_assessment",
            from_agent="test",
            to_agent="data_quality_agent",
            content={
                "type": "assess_quality",
                "data_source": test_data,
                "assessment_type": "comprehensive",
                "dimensions": ["completeness", "validity", "uniqueness"],
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(assessment_message):
            print(f"Assessment response: {response.content.get('type')}")
            result = response.content.get("result", {})
            print(f"Overall score: {result.get('overall_score')}")

        # Test anomaly detection
        anomaly_message = AgentMessage(
            id="test_anomaly",
            from_agent="test",
            to_agent="data_quality_agent",
            content={
                "type": "detect_anomalies",
                "data_source": test_data,
                "detection_method": "statistical",
                "sensitivity": 0.1,
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(anomaly_message):
            print(f"Anomaly detection response: {response.content.get('type')}")
            result = response.content.get("result", {})
            print(f"Anomalies detected: {result.get('anomalies_detected')}")

        # Stop agent
        await agent.stop()
        print("Data quality agent test completed")

    # Run test
    asyncio.run(test_data_quality_agent())
