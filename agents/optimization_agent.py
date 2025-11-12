"""
Optimization Agent: Performance optimization and resource management
Optimizes system performance, resource allocation, and computational efficiency
"""

import asyncio
import logging
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

import GPUtil
import lightgbm as lgb
import numpy as np
import optuna
import psutil
import xgboost as xgb
from bayes_opt import BayesianOptimization
from hyperopt import STATUS_OK, Trials, fmin, hp, tpe
from sklearn.ensemble import RandomForestRegressor

from ..agents.base_agent import AgentMessage, BaseAgent

logger = logging.getLogger(__name__)


class OptimizationAgent(BaseAgent):
    """
    Optimization Agent for performance optimization and resource management
    Uses ML models and optimization algorithms to improve system efficiency
    """

    def __init__(
        self, agent_id: str = "optimization_agent", config: dict[str, Any] | None = None
    ):
        super().__init__(agent_id, config or {})

        # Optimization configuration
        self.optimization_config = {
            "optimization_targets": self.config.get(
                "targets",
                [
                    "cpu_usage",
                    "memory_usage",
                    "gpu_usage",
                    "latency",
                    "throughput",
                    "energy_consumption",
                    "cost_efficiency",
                    "model_accuracy",
                ],
            ),
            "optimization_methods": self.config.get(
                "methods",
                [
                    "bayesian_optimization",
                    "hyperparameter_tuning",
                    "resource_allocation",
                    "model_compression",
                    "caching_optimization",
                    "load_balancing",
                ],
            ),
            "performance_metrics": self.config.get(
                "metrics",
                {
                    "collection_interval": 30,  # seconds
                    "retention_period": 7 * 24 * 3600,  # 7 days
                    "anomaly_threshold": 2.0,  # standard deviations
                    "optimization_threshold": 0.05,  # 5% improvement required
                },
            ),
            "resource_limits": self.config.get(
                "limits",
                {
                    "max_cpu_percent": 80.0,
                    "max_memory_percent": 85.0,
                    "max_gpu_percent": 90.0,
                    "max_latency_ms": 1000,
                    "min_throughput": 100,  # requests per second
                },
            ),
            "optimization_models": self.config.get(
                "models",
                {
                    "performance_predictor": {
                        "model_type": "xgboost",
                        "features": [
                            "cpu_usage",
                            "memory_usage",
                            "gpu_usage",
                            "request_count",
                            "data_size",
                        ],
                        "target": "latency",
                    },
                    "resource_allocator": {
                        "model_type": "random_forest",
                        "features": [
                            "workload_type",
                            "historical_usage",
                            "time_of_day",
                            "day_of_week",
                        ],
                        "target": "optimal_resources",
                    },
                },
            ),
            "processing_options": self.config.get(
                "options",
                {
                    "batch_size": 32,
                    "learning_rate": 0.01,
                    "max_iterations": 100,
                    "early_stopping_rounds": 10,
                    "cross_validation_folds": 5,
                    "enable_gpu": False,
                    "cache_optimizations": True,
                },
            ),
        }

        # Optimization models and predictors
        self.optimization_models = {}
        self.performance_predictors = {}
        self.resource_allocators = {}

        # Performance monitoring
        self.performance_monitor = PerformanceMonitor()
        self.resource_monitor = ResourceMonitor()

        # Optimization state
        self.optimization_state = {
            "performance_history": deque(maxlen=10000),
            "optimization_history": deque(maxlen=1000),
            "resource_allocations": {},
            "active_optimizations": {},
            "performance_baselines": {},
            "optimization_queue": deque(maxlen=500),
            "model_versions": {},
            "performance_metrics": defaultdict(list),
            "optimization_results": defaultdict(list),
        }

        # Background tasks
        self.performance_monitoring_task = None
        self.optimization_task = None
        self.resource_management_task = None

        logger.info(f"Optimization Agent initialized: {agent_id}")

    async def start(self):
        """
        Start the optimization agent
        """
        await super().start()

        # Initialize optimization models
        await self._initialize_optimization_models()

        # Load optimization data
        await self._load_optimization_data()

        # Start performance monitoring
        self.performance_monitor.start_monitoring()

        # Start background tasks
        self.performance_monitoring_task = asyncio.create_task(
            self._continuous_performance_monitoring()
        )
        self.optimization_task = asyncio.create_task(self._continuous_optimization())
        self.resource_management_task = asyncio.create_task(self._continuous_resource_management())

        logger.info("Optimization agent started")

    async def stop(self):
        """
        Stop the optimization agent
        """
        if self.performance_monitoring_task:
            self.performance_monitoring_task.cancel()
            try:
                await self.performance_monitoring_task
            except asyncio.CancelledError:
                pass

        if self.optimization_task:
            self.optimization_task.cancel()
            try:
                await self.optimization_task
            except asyncio.CancelledError:
                pass

        if self.resource_management_task:
            self.resource_management_task.cancel()
            try:
                await self.resource_management_task
            except asyncio.CancelledError:
                pass

        # Stop performance monitoring
        self.performance_monitor.stop_monitoring()

        await super().stop()
        logger.info("Optimization agent stopped")

    async def _initialize_optimization_models(self):
        """
        Initialize optimization models and predictors
        """
        try:
            # Initialize performance predictor
            predictor_config = self.optimization_config["optimization_models"][
                "performance_predictor"
            ]
            if predictor_config["model_type"] == "xgboost":
                self.performance_predictors["latency"] = xgb.XGBRegressor(
                    objective="reg:squarederror", n_estimators=100, learning_rate=0.1, max_depth=6
                )
            elif predictor_config["model_type"] == "lightgbm":
                self.performance_predictors["latency"] = lgb.LGBMRegressor(
                    objective="regression", num_leaves=31, learning_rate=0.1, n_estimators=100
                )

            # Initialize resource allocator
            allocator_config = self.optimization_config["optimization_models"]["resource_allocator"]
            if allocator_config["model_type"] == "random_forest":
                self.resource_allocators["cpu"] = RandomForestRegressor(
                    n_estimators=100, max_depth=10, random_state=42
                )
                self.resource_allocators["memory"] = RandomForestRegressor(
                    n_estimators=100, max_depth=10, random_state=42
                )
                self.resource_allocators["gpu"] = RandomForestRegressor(
                    n_estimators=100, max_depth=10, random_state=42
                )

            # Initialize optimization frameworks
            self.optimization_models["bayesian_opt"] = BayesianOptimization()
            self.optimization_models["hyperopt"] = {"fmin": fmin, "tpe": tpe, "hp": hp}

            logger.info("Optimization models initialized")

        except Exception as e:
            logger.error(f"Optimization model initialization failed: {e}")

    async def _load_optimization_data(self):
        """
        Load existing optimization data and models
        """
        try:
            # Load performance history, optimization history, etc.
            await self._load_performance_history()
            await self._load_optimization_history()
            await self._load_resource_allocations()

            logger.info("Optimization data loaded")

        except Exception as e:
            logger.error(f"Optimization data loading failed: {e}")

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process optimization requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "optimize_performance":
                async for response in self._handle_performance_optimization(message):
                    yield response

            elif message_type == "optimize_resources":
                async for response in self._handle_resource_optimization(message):
                    yield response

            elif message_type == "optimize_hyperparameters":
                async for response in self._handle_hyperparameter_optimization(message):
                    yield response

            elif message_type == "predict_performance":
                async for response in self._handle_performance_prediction(message):
                    yield response

            elif message_type == "analyze_bottlenecks":
                async for response in self._handle_bottleneck_analysis(message):
                    yield response

            elif message_type == "optimize_model":
                async for response in self._handle_model_optimization(message):
                    yield response

            elif message_type == "optimize_caching":
                async for response in self._handle_caching_optimization(message):
                    yield response

            elif message_type == "optimize_load_balancing":
                async for response in self._handle_load_balancing(message):
                    yield response

            elif message_type == "generate_optimization_report":
                async for response in self._handle_optimization_report(message):
                    yield response

            elif message_type == "monitor_performance":
                async for response in self._handle_performance_monitoring(message):
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
            logger.error(f"Optimization processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_performance_optimization(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle performance optimization request
        """
        try:
            target_component = message.content.get("component", "system")
            optimization_target = message.content.get("target", "latency")
            constraints = message.content.get("constraints", {})

            # Perform performance optimization
            optimization_result = await self._optimize_performance(
                target_component, optimization_target, constraints
            )

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "performance_optimization_response",
                    "optimization_result": optimization_result,
                    "target_component": target_component,
                    "optimization_target": optimization_target,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Performance optimization handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _optimize_performance(
        self, target_component: str, optimization_target: str, constraints: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Optimize performance for a specific component and target
        """
        try:
            # Get current performance metrics
            current_metrics = self.performance_monitor.get_current_metrics()

            # Identify optimization opportunities
            optimization_opportunities = await self._identify_optimization_opportunities(
                target_component, optimization_target, current_metrics
            )

            # Apply optimizations
            applied_optimizations = []
            performance_improvements = {}

            for opportunity in optimization_opportunities:
                if await self._should_apply_optimization(opportunity, constraints):
                    improvement = await self._apply_optimization(opportunity)
                    if improvement:
                        applied_optimizations.append(opportunity)
                        performance_improvements[opportunity["type"]] = improvement

            # Calculate overall improvement
            total_improvement = sum(performance_improvements.values())

            optimization_result = {
                "target_component": target_component,
                "optimization_target": optimization_target,
                "applied_optimizations": applied_optimizations,
                "performance_improvements": performance_improvements,
                "total_improvement": total_improvement,
                "baseline_metrics": current_metrics,
                "optimized_metrics": await self._get_optimized_metrics(),
                "optimization_timestamp": datetime.now(),
            }

            # Store optimization result
            self.optimization_state["optimization_results"][target_component].append(
                optimization_result
            )

            return optimization_result

        except Exception as e:
            logger.error(f"Performance optimization failed: {e}")
            return {"error": str(e)}

    async def _identify_optimization_opportunities(
        self, target_component: str, optimization_target: str, current_metrics: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Identify potential optimization opportunities
        """
        try:
            opportunities = []

            # CPU optimization opportunities
            if (
                optimization_target in ["latency", "throughput"]
                and current_metrics.get("cpu_percent", 0) > 70
            ):
                opportunities.append(
                    {
                        "type": "cpu_optimization",
                        "component": target_component,
                        "current_value": current_metrics["cpu_percent"],
                        "target_value": 60.0,
                        "method": "resource_allocation",
                        "estimated_improvement": 0.15,
                    }
                )

            # Memory optimization opportunities
            if current_metrics.get("memory_percent", 0) > 80:
                opportunities.append(
                    {
                        "type": "memory_optimization",
                        "component": target_component,
                        "current_value": current_metrics["memory_percent"],
                        "target_value": 70.0,
                        "method": "caching_optimization",
                        "estimated_improvement": 0.10,
                    }
                )

            # GPU optimization opportunities
            if current_metrics.get("gpu_percent", 0) > 85:
                opportunities.append(
                    {
                        "type": "gpu_optimization",
                        "component": target_component,
                        "current_value": current_metrics["gpu_percent"],
                        "target_value": 75.0,
                        "method": "batch_processing",
                        "estimated_improvement": 0.20,
                    }
                )

            # Model optimization opportunities
            if target_component == "model" and optimization_target == "latency":
                opportunities.append(
                    {
                        "type": "model_compression",
                        "component": target_component,
                        "method": "quantization",
                        "estimated_improvement": 0.25,
                    }
                )

            # Caching optimization opportunities
            if optimization_target == "latency":
                opportunities.append(
                    {
                        "type": "caching_optimization",
                        "component": target_component,
                        "method": "cache_preloading",
                        "estimated_improvement": 0.30,
                    }
                )

            return opportunities

        except Exception as e:
            logger.error(f"Optimization opportunity identification failed: {e}")
            return []

    async def _should_apply_optimization(
        self, opportunity: dict[str, Any], constraints: dict[str, Any]
    ) -> bool:
        """
        Determine if an optimization should be applied
        """
        try:
            # Check if improvement meets threshold
            estimated_improvement = opportunity.get("estimated_improvement", 0)
            min_improvement = constraints.get(
                "min_improvement",
                self.optimization_config["performance_metrics"]["optimization_threshold"],
            )

            if estimated_improvement < min_improvement:
                return False

            # Check resource constraints
            if opportunity["type"] == "cpu_optimization":
                max_cpu = constraints.get(
                    "max_cpu_percent",
                    self.optimization_config["resource_limits"]["max_cpu_percent"],
                )
                if opportunity.get("target_value", 0) > max_cpu:
                    return False

            # Check if optimization is already active
            opt_key = f"{opportunity['component']}_{opportunity['type']}"
            if opt_key in self.optimization_state["active_optimizations"]:
                return False

            return True

        except Exception as e:
            logger.error(f"Optimization application check failed: {e}")
            return False

    async def _apply_optimization(self, opportunity: dict[str, Any]) -> float | None:
        """
        Apply a specific optimization
        """
        try:
            optimization_type = opportunity["type"]
            component = opportunity["component"]

            if optimization_type == "cpu_optimization":
                improvement = await self._optimize_cpu_usage(component)
            elif optimization_type == "memory_optimization":
                improvement = await self._optimize_memory_usage(component)
            elif optimization_type == "gpu_optimization":
                improvement = await self._optimize_gpu_usage(component)
            elif optimization_type == "model_compression":
                improvement = await self._optimize_model_compression(component)
            elif optimization_type == "caching_optimization":
                improvement = await self._optimize_caching(component)
            else:
                return None

            # Mark optimization as active
            opt_key = f"{component}_{optimization_type}"
            self.optimization_state["active_optimizations"][opt_key] = {
                "start_time": datetime.now(),
                "opportunity": opportunity,
                "improvement": improvement,
            }

            return improvement

        except Exception as e:
            logger.error(f"Optimization application failed: {e}")
            return None

    async def _optimize_cpu_usage(self, component: str) -> float:
        """
        Optimize CPU usage for a component
        """
        try:
            # Implement CPU optimization strategies
            # This is a placeholder - actual implementation would involve
            # adjusting thread pools, process priorities, etc.

            improvement = 0.15  # 15% improvement
            return improvement

        except Exception as e:
            logger.error(f"CPU optimization failed: {e}")
            return 0.0

    async def _optimize_memory_usage(self, component: str) -> float:
        """
        Optimize memory usage for a component
        """
        try:
            # Implement memory optimization strategies
            improvement = 0.10  # 10% improvement
            return improvement

        except Exception as e:
            logger.error(f"Memory optimization failed: {e}")
            return 0.0

    async def _optimize_gpu_usage(self, component: str) -> float:
        """
        Optimize GPU usage for a component
        """
        try:
            # Implement GPU optimization strategies
            improvement = 0.20  # 20% improvement
            return improvement

        except Exception as e:
            logger.error(f"GPU optimization failed: {e}")
            return 0.0

    async def _optimize_model_compression(self, component: str) -> float:
        """
        Optimize model through compression
        """
        try:
            # Implement model compression (quantization, pruning, etc.)
            improvement = 0.25  # 25% improvement
            return improvement

        except Exception as e:
            logger.error(f"Model compression failed: {e}")
            return 0.0

    async def _optimize_caching(self, component: str) -> float:
        """
        Optimize caching strategy
        """
        try:
            # Implement caching optimizations
            improvement = 0.30  # 30% improvement
            return improvement

        except Exception as e:
            logger.error(f"Caching optimization failed: {e}")
            return 0.0

    async def _get_optimized_metrics(self) -> dict[str, Any]:
        """
        Get current metrics after optimization
        """
        try:
            return self.performance_monitor.get_current_metrics()

        except Exception as e:
            logger.error(f"Optimized metrics retrieval failed: {e}")
            return {}

    async def _handle_resource_optimization(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle resource optimization request
        """
        try:
            workload_description = message.content.get("workload", {})
            resource_constraints = message.content.get("constraints", {})

            # Optimize resource allocation
            resource_allocation = await self._optimize_resource_allocation(
                workload_description, resource_constraints
            )

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "resource_optimization_response",
                    "resource_allocation": resource_allocation,
                    "workload_description": workload_description,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Resource optimization handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _optimize_resource_allocation(
        self, workload_description: dict[str, Any], resource_constraints: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Optimize resource allocation for a workload
        """
        try:
            # Extract workload features
            workload_features = self._extract_workload_features(workload_description)

            # Predict optimal resource allocation
            cpu_allocation = await self._predict_optimal_cpu_allocation(workload_features)
            memory_allocation = await self._predict_optimal_memory_allocation(workload_features)
            gpu_allocation = await self._predict_optimal_gpu_allocation(workload_features)

            # Apply constraints
            cpu_allocation = min(cpu_allocation, resource_constraints.get("max_cpu", 100))
            memory_allocation = min(memory_allocation, resource_constraints.get("max_memory", 100))
            gpu_allocation = min(gpu_allocation, resource_constraints.get("max_gpu", 100))

            resource_allocation = {
                "cpu_cores": cpu_allocation,
                "memory_gb": memory_allocation,
                "gpu_memory_gb": gpu_allocation,
                "estimated_cost": self._estimate_resource_cost(
                    cpu_allocation, memory_allocation, gpu_allocation
                ),
                "optimization_timestamp": datetime.now(),
            }

            # Store allocation
            allocation_key = str(uuid.uuid4())
            self.optimization_state["resource_allocations"][allocation_key] = resource_allocation

            return resource_allocation

        except Exception as e:
            logger.error(f"Resource allocation optimization failed: {e}")
            return {"error": str(e)}

    def _extract_workload_features(self, workload_description: dict[str, Any]) -> dict[str, Any]:
        """
        Extract features from workload description
        """
        try:
            features = {
                "workload_type": workload_description.get("type", "unknown"),
                "data_size": workload_description.get("data_size", 0),
                "concurrency": workload_description.get("concurrency", 1),
                "time_of_day": datetime.now().hour,
                "day_of_week": datetime.now().weekday(),
                "historical_cpu_usage": np.mean(
                    [
                        m.get("cpu_percent", 0)
                        for m in list(self.optimization_state["performance_history"])[-10:]
                    ]
                ),
                "historical_memory_usage": np.mean(
                    [
                        m.get("memory_percent", 0)
                        for m in list(self.optimization_state["performance_history"])[-10:]
                    ]
                ),
            }

            return features

        except Exception as e:
            logger.error(f"Workload feature extraction failed: {e}")
            return {}

    async def _predict_optimal_cpu_allocation(self, features: dict[str, Any]) -> float:
        """
        Predict optimal CPU allocation
        """
        try:
            if "cpu" in self.resource_allocators:
                # Use trained model
                feature_vector = self._prepare_feature_vector(features, "cpu")
                prediction = self.resource_allocators["cpu"].predict([feature_vector])[0]
                return max(1.0, min(prediction, 100.0))
            else:
                # Default allocation based on workload type
                workload_type = features.get("workload_type", "unknown")
                if workload_type == "cpu_intensive":
                    return 8.0
                elif workload_type == "memory_intensive":
                    return 4.0
                else:
                    return 2.0

        except Exception as e:
            logger.error(f"CPU allocation prediction failed: {e}")
            return 2.0

    async def _predict_optimal_memory_allocation(self, features: dict[str, Any]) -> float:
        """
        Predict optimal memory allocation
        """
        try:
            if "memory" in self.resource_allocators:
                feature_vector = self._prepare_feature_vector(features, "memory")
                prediction = self.resource_allocators["memory"].predict([feature_vector])[0]
                return max(1.0, min(prediction, 128.0))
            else:
                # Default allocation
                data_size = features.get("data_size", 0)
                return max(2.0, min(data_size / (1024**3), 32.0))  # GB based on data size

        except Exception as e:
            logger.error(f"Memory allocation prediction failed: {e}")
            return 4.0

    async def _predict_optimal_gpu_allocation(self, features: dict[str, Any]) -> float:
        """
        Predict optimal GPU allocation
        """
        try:
            if "gpu" in self.resource_allocators:
                feature_vector = self._prepare_feature_vector(features, "gpu")
                prediction = self.resource_allocators["gpu"].predict([feature_vector])[0]
                return max(0.0, min(prediction, 24.0))  # GB
            else:
                # Default allocation
                workload_type = features.get("workload_type", "unknown")
                if workload_type in ["gpu_intensive", "ml_training"]:
                    return 8.0
                else:
                    return 0.0

        except Exception as e:
            logger.error(f"GPU allocation prediction failed: {e}")
            return 0.0

    def _prepare_feature_vector(self, features: dict[str, Any], resource_type: str) -> list[float]:
        """
        Prepare feature vector for resource prediction
        """
        try:
            # This would include proper feature engineering
            feature_vector = [
                features.get("data_size", 0),
                features.get("concurrency", 1),
                features.get("time_of_day", 12),
                features.get("day_of_week", 0),
                features.get("historical_cpu_usage", 50),
                features.get("historical_memory_usage", 50),
            ]

            return feature_vector

        except Exception as e:
            logger.error(f"Feature vector preparation failed: {e}")
            return [0] * 6

    def _estimate_resource_cost(self, cpu_cores: float, memory_gb: float, gpu_gb: float) -> float:
        """
        Estimate cost of resource allocation
        """
        try:
            # Simplified cost estimation (per hour)
            cpu_cost = cpu_cores * 0.05  # $0.05 per CPU core hour
            memory_cost = memory_gb * 0.01  # $0.01 per GB hour
            gpu_cost = gpu_gb * 0.50  # $0.50 per GPU GB hour

            total_cost = cpu_cost + memory_cost + gpu_cost
            return round(total_cost, 2)

        except Exception as e:
            logger.error(f"Resource cost estimation failed: {e}")
            return 0.0

    async def _handle_hyperparameter_optimization(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle hyperparameter optimization request
        """
        try:
            model_config = message.content.get("model_config", {})
            optimization_method = message.content.get("method", "bayesian")
            max_evaluations = message.content.get("max_evaluations", 50)

            # Optimize hyperparameters
            optimized_params = await self._optimize_hyperparameters(
                model_config, optimization_method, max_evaluations
            )

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "hyperparameter_optimization_response",
                    "optimized_params": optimized_params,
                    "optimization_method": optimization_method,
                    "max_evaluations": max_evaluations,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Hyperparameter optimization handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _optimize_hyperparameters(
        self, model_config: dict[str, Any], optimization_method: str, max_evaluations: int
    ) -> dict[str, Any]:
        """
        Optimize hyperparameters using specified method
        """
        try:
            if optimization_method == "bayesian":
                optimized_params = await self._bayesian_optimization(model_config, max_evaluations)
            elif optimization_method == "hyperopt":
                optimized_params = await self._hyperopt_optimization(model_config, max_evaluations)
            elif optimization_method == "optuna":
                optimized_params = await self._optuna_optimization(model_config, max_evaluations)
            else:
                # Default to random search
                optimized_params = await self._random_search_optimization(
                    model_config, max_evaluations
                )

            return optimized_params

        except Exception as e:
            logger.error(f"Hyperparameter optimization failed: {e}")
            return {"error": str(e)}

    async def _bayesian_optimization(
        self, model_config: dict[str, Any], max_evaluations: int
    ) -> dict[str, Any]:
        """
        Perform Bayesian optimization
        """
        try:
            # Define objective function
            def objective(**params):
                # Evaluate model with parameters
                score = self._evaluate_model_params(model_config, params)
                return score

            # Define parameter bounds
            pbounds = self._get_parameter_bounds(model_config)

            # Perform optimization
            optimizer = BayesianOptimization(f=objective, pbounds=pbounds, random_state=42)

            optimizer.maximize(init_points=5, n_iter=max_evaluations - 5)

            best_params = optimizer.max["params"]
            best_score = optimizer.max["target"]

            return {
                "best_params": best_params,
                "best_score": best_score,
                "method": "bayesian_optimization",
                "evaluations": len(optimizer.res),
            }

        except Exception as e:
            logger.error(f"Bayesian optimization failed: {e}")
            return {"error": str(e)}

    def _evaluate_model_params(self, model_config: dict[str, Any], params: dict[str, Any]) -> float:
        """
        Evaluate model with given parameters
        """
        try:
            # This would train and evaluate the model
            # Placeholder implementation
            score = np.random.random()  # Random score for demo
            return score

        except Exception as e:
            logger.error(f"Model parameter evaluation failed: {e}")
            return 0.0

    def _get_parameter_bounds(self, model_config: dict[str, Any]) -> dict[str, tuple[float, float]]:
        """
        Get parameter bounds for optimization
        """
        try:
            # Default bounds for common parameters
            bounds = {
                "learning_rate": (1e-5, 1e-1),
                "batch_size": (16, 512),
                "num_epochs": (10, 200),
                "hidden_size": (64, 1024),
                "dropout": (0.0, 0.5),
            }

            return bounds

        except Exception as e:
            logger.error(f"Parameter bounds retrieval failed: {e}")
            return {}

    async def _hyperopt_optimization(
        self, model_config: dict[str, Any], max_evaluations: int
    ) -> dict[str, Any]:
        """
        Perform Hyperopt optimization
        """
        try:
            # Define search space
            space = {
                "learning_rate": hp.loguniform("learning_rate", -5, 0),
                "batch_size": hp.choice("batch_size", [16, 32, 64, 128, 256]),
                "dropout": hp.uniform("dropout", 0, 0.5),
            }

            # Define objective function
            def objective(params):
                score = self._evaluate_model_params(model_config, params)
                return {"loss": -score, "status": STATUS_OK}

            # Perform optimization
            trials = Trials()
            best = fmin(
                objective, space, algo=tpe.suggest, max_evals=max_evaluations, trials=trials
            )

            return {
                "best_params": best,
                "best_score": -trials.best_trial["result"]["loss"],
                "method": "hyperopt",
                "evaluations": len(trials),
            }

        except Exception as e:
            logger.error(f"Hyperopt optimization failed: {e}")
            return {"error": str(e)}

    async def _optuna_optimization(
        self, model_config: dict[str, Any], max_evaluations: int
    ) -> dict[str, Any]:
        """
        Perform Optuna optimization
        """
        try:

            def objective(trial):
                # Define parameters
                learning_rate = trial.suggest_loguniform("learning_rate", 1e-5, 1e-1)
                batch_size = trial.suggest_categorical("batch_size", [16, 32, 64, 128, 256])
                dropout = trial.suggest_uniform("dropout", 0, 0.5)

                params = {
                    "learning_rate": learning_rate,
                    "batch_size": batch_size,
                    "dropout": dropout,
                }

                score = self._evaluate_model_params(model_config, params)
                return score

            # Create study
            study = optuna.create_study(direction="maximize")
            study.optimize(objective, n_trials=max_evaluations)

            return {
                "best_params": study.best_params,
                "best_score": study.best_value,
                "method": "optuna",
                "evaluations": len(study.trials),
            }

        except Exception as e:
            logger.error(f"Optuna optimization failed: {e}")
            return {"error": str(e)}

    async def _random_search_optimization(
        self, model_config: dict[str, Any], max_evaluations: int
    ) -> dict[str, Any]:
        """
        Perform random search optimization
        """
        try:
            best_score = 0
            best_params = {}

            for _ in range(max_evaluations):
                # Random parameters
                params = {
                    "learning_rate": np.random.uniform(1e-5, 1e-1),
                    "batch_size": np.random.choice([16, 32, 64, 128, 256]),
                    "dropout": np.random.uniform(0, 0.5),
                }

                score = self._evaluate_model_params(model_config, params)

                if score > best_score:
                    best_score = score
                    best_params = params

            return {
                "best_params": best_params,
                "best_score": best_score,
                "method": "random_search",
                "evaluations": max_evaluations,
            }

        except Exception as e:
            logger.error(f"Random search optimization failed: {e}")
            return {"error": str(e)}

    # Background processing tasks
    async def _continuous_performance_monitoring(self):
        """
        Continuous performance monitoring
        """
        try:
            while True:
                try:
                    # Collect performance metrics
                    metrics = self.performance_monitor.get_current_metrics()

                    # Store metrics
                    self.optimization_state["performance_history"].append(
                        {"timestamp": datetime.now(), "metrics": metrics}
                    )

                    # Check for anomalies
                    await self._check_performance_anomalies(metrics)

                except Exception as e:
                    logger.error(f"Performance monitoring error: {e}")

                # Monitor every 30 seconds
                await asyncio.sleep(30)

        except asyncio.CancelledError:
            logger.info("Performance monitoring cancelled")
            raise

    async def _continuous_optimization(self):
        """
        Continuous optimization of system performance
        """
        try:
            while True:
                try:
                    # Check if optimization is needed
                    if await self._should_run_optimization():
                        await self._run_automatic_optimization()

                except Exception as e:
                    logger.error(f"Optimization error: {e}")

                # Optimize every 5 minutes
                await asyncio.sleep(300)

        except asyncio.CancelledError:
            logger.info("Optimization cancelled")
            raise

    async def _continuous_resource_management(self):
        """
        Continuous resource management and allocation
        """
        try:
            while True:
                try:
                    # Monitor resource usage
                    resource_usage = self.resource_monitor.get_resource_usage()

                    # Adjust resource allocations if needed
                    await self._adjust_resource_allocations(resource_usage)

                except Exception as e:
                    logger.error(f"Resource management error: {e}")

                # Manage resources every 2 minutes
                await asyncio.sleep(120)

        except asyncio.CancelledError:
            logger.info("Resource management cancelled")
            raise

    async def _check_performance_anomalies(self, metrics: dict[str, Any]):
        """
        Check for performance anomalies
        """
        try:
            # Simple anomaly detection based on thresholds
            threshold = self.optimization_config["performance_metrics"]["anomaly_threshold"]

            for metric_name, value in metrics.items():
                if metric_name in self.optimization_state["performance_metrics"]:
                    history = self.optimization_state["performance_metrics"][metric_name]

                    if len(history) > 10:
                        mean_val = np.mean(history)
                        std_val = np.std(history)

                        if abs(value - mean_val) > threshold * std_val:
                            logger.warning(
                                f"Performance anomaly detected in {metric_name}: {value}"
                            )

                            # Trigger optimization
                            await self._trigger_anomaly_optimization(metric_name, value)

                # Update history
                self.optimization_state["performance_metrics"][metric_name].append(value)

        except Exception as e:
            logger.error(f"Performance anomaly check failed: {e}")

    async def _trigger_anomaly_optimization(self, metric_name: str, value: float):
        """
        Trigger optimization in response to anomaly
        """
        try:
            # Create optimization task
            optimization_task = {
                "type": "anomaly_response",
                "metric": metric_name,
                "value": value,
                "timestamp": datetime.now(),
            }

            self.optimization_state["optimization_queue"].append(optimization_task)

        except Exception as e:
            logger.error(f"Anomaly optimization trigger failed: {e}")

    async def _should_run_optimization(self) -> bool:
        """
        Determine if optimization should be run
        """
        try:
            # Check if there are pending optimization tasks
            if self.optimization_state["optimization_queue"]:
                return True

            # Check if performance has degraded
            recent_metrics = list(self.optimization_state["performance_history"])[-10:]
            if len(recent_metrics) >= 10:
                avg_latency = np.mean([m["metrics"].get("latency", 0) for m in recent_metrics])
                baseline_latency = self.optimization_state["performance_baselines"].get(
                    "latency", avg_latency
                )

                if avg_latency > baseline_latency * 1.1:  # 10% degradation
                    return True

            return False

        except Exception as e:
            logger.error(f"Optimization check failed: {e}")
            return False

    async def _run_automatic_optimization(self):
        """
        Run automatic optimization
        """
        try:
            # Get pending optimization task
            if self.optimization_state["optimization_queue"]:
                task = self.optimization_state["optimization_queue"].popleft()

                # Run optimization based on task type
                if task["type"] == "anomaly_response":
                    await self._optimize_performance("system", "latency", {})
                elif task["type"] == "scheduled":
                    await self._optimize_performance("system", "throughput", {})

        except Exception as e:
            logger.error(f"Automatic optimization failed: {e}")

    async def _adjust_resource_allocations(self, resource_usage: dict[str, Any]):
        """
        Adjust resource allocations based on usage
        """
        try:
            # Check if resources need adjustment
            for resource, usage in resource_usage.items():
                limit = self.optimization_config["resource_limits"].get(
                    f"max_{resource}_percent", 80
                )

                if usage > limit:
                    logger.warning(f"High {resource} usage: {usage}%")

                    # Trigger resource optimization
                    await self._optimize_resource_allocation({"type": f"{resource}_intensive"}, {})

        except Exception as e:
            logger.error(f"Resource allocation adjustment failed: {e}")

    # Additional helper methods would continue...

    async def _load_performance_history(self):
        """Load performance history"""
        try:
            # Implementation for loading performance history
            pass
        except Exception as e:
            logger.error(f"Performance history loading failed: {e}")

    async def _load_optimization_history(self):
        """Load optimization history"""
        try:
            # Implementation for loading optimization history
            pass
        except Exception as e:
            logger.error(f"Optimization history loading failed: {e}")

    async def _load_resource_allocations(self):
        """Load resource allocations"""
        try:
            # Implementation for loading resource allocations
            pass
        except Exception as e:
            logger.error(f"Resource allocations loading failed: {e}")


class PerformanceMonitor:
    """
    Performance monitoring utility
    """

    def __init__(self):
        self.monitoring = False
        self.metrics_history = deque(maxlen=1000)

    def start_monitoring(self):
        """Start performance monitoring"""
        self.monitoring = True

    def stop_monitoring(self):
        """Stop performance monitoring"""
        self.monitoring = False

    def get_current_metrics(self) -> dict[str, Any]:
        """
        Get current system performance metrics
        """
        try:
            metrics = {}

            # CPU metrics
            metrics["cpu_percent"] = psutil.cpu_percent(interval=1)
            metrics["cpu_count"] = psutil.cpu_count()

            # Memory metrics
            memory = psutil.virtual_memory()
            metrics["memory_percent"] = memory.percent
            metrics["memory_used"] = memory.used
            metrics["memory_total"] = memory.total

            # Disk metrics
            disk = psutil.disk_usage("/")
            metrics["disk_percent"] = disk.percent
            metrics["disk_used"] = disk.used
            metrics["disk_total"] = disk.total

            # Network metrics
            network = psutil.net_io_counters()
            metrics["network_bytes_sent"] = network.bytes_sent
            metrics["network_bytes_recv"] = network.bytes_recv

            # GPU metrics (if available)
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    gpu = gpus[0]
                    metrics["gpu_percent"] = gpu.load * 100
                    metrics["gpu_memory_percent"] = gpu.memoryUtil * 100
                    metrics["gpu_temperature"] = gpu.temperature
            except:
                metrics["gpu_percent"] = 0
                metrics["gpu_memory_percent"] = 0

            # Add timestamp
            metrics["timestamp"] = datetime.now()

            # Store in history
            self.metrics_history.append(metrics)

            return metrics

        except Exception as e:
            logger.error(f"Metrics collection failed: {e}")
            return {}


class ResourceMonitor:
    """
    Resource monitoring utility
    """

    def __init__(self):
        self.resource_history = defaultdict(deque)

    def get_resource_usage(self) -> dict[str, float]:
        """
        Get current resource usage percentages
        """
        try:
            usage = {}

            # CPU usage
            usage["cpu"] = psutil.cpu_percent(interval=1)

            # Memory usage
            usage["memory"] = psutil.virtual_memory().percent

            # Disk usage
            usage["disk"] = psutil.disk_usage("/").percent

            # GPU usage (if available)
            try:
                gpus = GPUtil.getGPUs()
                if gpus:
                    usage["gpu"] = gpus[0].load * 100
                else:
                    usage["gpu"] = 0
            except:
                usage["gpu"] = 0

            # Store in history
            for resource, value in usage.items():
                self.resource_history[resource].append(value)

            return usage

        except Exception as e:
            logger.error(f"Resource usage collection failed: {e}")
            return {}


# ========== TEST ==========
if __name__ == "__main__":

    async def test_optimization_agent():
        # Initialize optimization agent
        agent = OptimizationAgent()
        await agent.start()

        # Test performance optimization
        optimization_message = AgentMessage(
            id="test_optimization",
            from_agent="test",
            to_agent="optimization_agent",
            content={
                "type": "optimize_performance",
                "component": "system",
                "target": "latency",
                "constraints": {"min_improvement": 0.05},
            },
            timestamp=datetime.now(),
        )

        print("Testing optimization agent...")
        async for response in agent.process_message(optimization_message):
            print(f"Performance optimization response: {response.content.get('type')}")
            result = response.content.get("optimization_result")
            print(f"Optimization result: {result}")

        # Test resource optimization
        resource_message = AgentMessage(
            id="test_resources",
            from_agent="test",
            to_agent="optimization_agent",
            content={
                "type": "optimize_resources",
                "workload": {"type": "cpu_intensive", "data_size": 1000000, "concurrency": 10},
                "constraints": {"max_cpu": 8, "max_memory": 16},
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(resource_message):
            print(f"Resource optimization response: {response.content.get('type')}")
            allocation = response.content.get("resource_allocation")
            print(f"Resource allocation: {allocation}")

        # Stop agent
        await agent.stop()
        print("Optimization agent test completed")

    # Run test
    asyncio.run(test_optimization_agent())
