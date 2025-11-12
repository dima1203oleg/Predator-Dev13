"""
Base Agent Class for Predator Analytics v13 MAS
LangGraph-based orchestration with heartbeats, retries, metrics
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import yaml
from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)


@dataclass
class AgentMessage:
    """Standard message format for inter-agent communication"""

    id: str
    from_agent: str
    to_agent: str
    content: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    session_id: str | None = None
    trace_id: str | None = None


class AgentStatus(Enum):
    """Agent execution status"""

    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class AgentContext:
    """Shared context for agent execution"""

    user_id: str
    query: str
    session_id: str
    trace_id: str
    access_level: str = "Client"  # Guest/Client/Pro

    # Results accumulator
    results: dict[str, Any] = field(default_factory=dict)

    # Metadata
    started_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """
    Base class for all MAS agents

    Features:
    - LangGraph integration (StateGraph nodes)
    - Heartbeat monitoring
    - Retry logic with exponential backoff
    - Prometheus metrics
    - Model routing (primary/fallback)
    - PII/billing gate
    """

    def __init__(
        self,
        name: str,
        model_registry_path: str = "agents/model_registry.yaml",
        max_retries: int = 3,
        timeout: int = 60,
        enable_metrics: bool = True,
    ):
        self.name = name
        self.max_retries = max_retries
        self.timeout = timeout
        self.enable_metrics = enable_metrics

        # Load model registry
        self.model_config = self._load_model_config(model_registry_path)

        # Prometheus metrics
        if self.enable_metrics:
            self.execution_counter = Counter(
                f"agent_{name}_executions_total", f"Total executions of {name} agent", ["status"]
            )
            self.execution_duration = Histogram(
                f"agent_{name}_duration_seconds", f"Execution duration of {name} agent"
            )
            self.active_executions = Gauge(
                f"agent_{name}_active", f"Active executions of {name} agent"
            )

        logger.info(f"Initialized agent: {name}")

    def _load_model_config(self, path: str) -> dict[str, Any]:
        """Load model routing configuration"""
        try:
            with open(path) as f:
                config = yaml.safe_load(f)
                agent_config = config.get("routing", {}).get("agents", {}).get(self.name, {})
                return agent_config
        except Exception as e:
            logger.error(f"Failed to load model config: {e}")
            return {}

    def get_model(self, model_type: str = "primary") -> str | None:
        """Get model name from registry (primary/fallback/embed/vision)"""
        if model_type == "primary":
            return self.model_config.get("primary")
        elif model_type == "fallback":
            fallbacks = self.model_config.get("fallback", [])
            return fallbacks[0] if fallbacks else None
        elif model_type == "embed":
            return self.model_config.get("embed")
        elif model_type == "vision":
            return self.model_config.get("vision")
        return None

    def execute(self, context: AgentContext) -> dict[str, Any]:
        """
        Execute agent with retry logic and metrics

        Returns:
            Dict with keys: status, result, error, duration_ms
        """
        start_time = time.time()

        if self.enable_metrics:
            self.active_executions.inc()

        result = {
            "agent": self.name,
            "status": AgentStatus.FAILED.value,
            "result": None,
            "error": None,
            "duration_ms": 0,
            "retries": 0,
        }

        try:
            # Check PII/billing gate
            if not self._check_access(context):
                raise PermissionError(f"Access denied for {context.access_level}")

            # Execute with retries
            for attempt in range(self.max_retries):
                try:
                    logger.debug(f"{self.name}: Attempt {attempt + 1}/{self.max_retries}")

                    # Main execution
                    agent_result = self._execute_impl(context)

                    # Success
                    result["status"] = AgentStatus.SUCCESS.value
                    result["result"] = agent_result
                    result["retries"] = attempt
                    break

                except Exception as e:
                    logger.warning(f"{self.name}: Attempt {attempt + 1} failed: {e}")

                    if attempt == self.max_retries - 1:
                        # Final attempt failed
                        raise

                    # Exponential backoff
                    backoff = 2**attempt
                    time.sleep(backoff)

        except Exception as e:
            logger.error(f"{self.name}: Execution failed: {e}", exc_info=True)
            result["status"] = AgentStatus.FAILED.value
            result["error"] = str(e)

        finally:
            # Calculate duration
            duration = time.time() - start_time
            result["duration_ms"] = int(duration * 1000)

            # Metrics
            if self.enable_metrics:
                self.execution_counter.labels(status=result["status"]).inc()
                self.execution_duration.observe(duration)
                self.active_executions.dec()

            logger.info(
                f"{self.name}: {result['status']} in {result['duration_ms']}ms "
                f"(retries: {result['retries']})"
            )

        return result

    def _check_access(self, context: AgentContext) -> bool:
        """Check PII/billing access (override for agent-specific rules)"""
        # Default: all agents accessible for Client+
        if context.access_level in ["Client", "Pro"]:
            return True
        return False

    @abstractmethod
    def _execute_impl(self, context: AgentContext) -> Any:
        """
        Agent implementation (must override)

        Args:
            context: AgentContext with query, user_id, results from previous agents

        Returns:
            Agent-specific result (dict, list, str, etc.)
        """

    def heartbeat(self) -> dict[str, Any]:
        """Health check endpoint"""
        return {
            "agent": self.name,
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "model_primary": self.get_model("primary"),
            "model_fallback": self.get_model("fallback"),
        }


# ========== EXAMPLE USAGE ==========
class ExampleAgent(BaseAgent):
    """Example agent implementation"""

    def _execute_impl(self, context: AgentContext) -> dict[str, Any]:
        """Simple echo agent"""
        return {
            "query": context.query,
            "user_id": context.user_id,
            "model": self.get_model("primary"),
            "message": f"Processed by {self.name}",
        }


if __name__ == "__main__":
    # Test agent
    agent = ExampleAgent(name="ExampleAgent")

    ctx = AgentContext(
        user_id="user_123",
        query="Test query",
        session_id="session_456",
        trace_id="trace_789",
        access_level="Client",
    )

    result = agent.execute(ctx)
    print(f"Result: {result}")

    # Heartbeat
    health = agent.heartbeat()
    print(f"Health: {health}")
