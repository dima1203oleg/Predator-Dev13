"""
Chaos Agent: Chaos engineering and resilience testing
Handles fault injection, resilience testing, and system hardening
"""

import asyncio
import concurrent.futures
import logging
import os
import random
import subprocess
import tempfile
import uuid
from collections import deque
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

import docker
import kubernetes
from docker.errors import DockerException
from kubernetes.client.rest import ApiException

from ..agents.base_agent import AgentMessage, BaseAgent

logger = logging.getLogger(__name__)


class ChaosAgent(BaseAgent):
    """
    Chaos Agent for chaos engineering and resilience testing
    Handles fault injection, resilience testing, and system hardening
    """

    def __init__(self, agent_id: str = "chaos_agent", config: dict[str, Any] | None = None):
        super().__init__(agent_id, config or {})

        # Chaos configuration
        self.chaos_config = {
            "experiments": self.config.get(
                "experiments",
                {
                    "pod_kill": {
                        "enabled": True,
                        "targets": ["predator-api", "predator-worker"],
                        "namespaces": ["default", "predator-analytics"],
                        "kill_percentage": 25,
                        "cooldown_seconds": 300,
                    },
                    "network_delay": {
                        "enabled": True,
                        "targets": ["predator-api", "predator-db"],
                        "delay_ms": 1000,
                        "jitter_ms": 200,
                        "duration_seconds": 60,
                    },
                    "resource_stress": {
                        "enabled": True,
                        "targets": ["predator-worker"],
                        "cpu_percentage": 80,
                        "memory_percentage": 85,
                        "duration_seconds": 120,
                    },
                    "disk_fill": {
                        "enabled": False,  # Dangerous, disabled by default
                        "targets": ["predator-storage"],
                        "fill_percentage": 90,
                        "duration_seconds": 60,
                    },
                    "service_unavailable": {
                        "enabled": True,
                        "targets": ["predator-cache", "predator-queue"],
                        "unavailable_duration_seconds": 30,
                    },
                },
            ),
            "schedules": self.config.get(
                "schedules",
                {
                    "daily_chaos": {
                        "enabled": True,
                        "time": "02:00",
                        "duration_minutes": 30,
                        "experiments": ["pod_kill", "network_delay"],
                    },
                    "weekly_stress": {
                        "enabled": True,
                        "day": "saturday",
                        "time": "03:00",
                        "duration_minutes": 60,
                        "experiments": ["resource_stress"],
                    },
                    "monthly_disaster": {
                        "enabled": False,  # Only for testing
                        "day": 1,
                        "time": "04:00",
                        "duration_minutes": 120,
                        "experiments": ["disk_fill", "service_unavailable"],
                    },
                },
            ),
            "safety": self.config.get(
                "safety",
                {
                    "blast_radius_limit": 3,  # Max pods/nodes affected
                    "rollback_enabled": True,
                    "monitoring_enabled": True,
                    "emergency_stop": True,
                    "whitelist_namespaces": ["kube-system", "monitoring"],
                    "blacklist_labels": ["critical", "production-critical"],
                },
            ),
            "monitoring": self.config.get(
                "monitoring",
                {
                    "metrics_collection": True,
                    "experiment_tracking": True,
                    "impact_analysis": True,
                    "alert_thresholds": {
                        "error_rate_increase": 50,  # 50% increase
                        "latency_increase": 100,  # 100% increase
                        "availability_drop": 5,  # 5% drop
                    },
                },
            ),
            "tools": self.config.get(
                "tools",
                {
                    "litmus_chaos": {"enabled": True, "namespace": "litmus", "version": "2.14.0"},
                    "chaos_mesh": {"enabled": False, "namespace": "chaos-mesh", "version": "2.5.1"},
                    "kube_monkey": {
                        "enabled": False,
                        "namespace": "kube-monkey",
                        "version": "0.5.0",
                    },
                },
            ),
            "resilience": self.config.get(
                "resilience",
                {
                    "circuit_breakers": True,
                    "retry_logic": True,
                    "fallback_mechanisms": True,
                    "auto_healing": True,
                    "load_balancing": True,
                },
            ),
            "processing": self.config.get(
                "processing",
                {
                    "parallel_experiments": 2,
                    "experiment_timeout": 3600,  # 1 hour
                    "cleanup_timeout": 300,  # 5 minutes
                    "steady_state_check": True,
                    "steady_state_timeout": 300,
                },
            ),
        }

        # Chaos components
        self.k8s_client = None
        self.docker_client = None
        self.active_experiments = {}
        self.experiment_history = deque(maxlen=10000)
        self.resilience_tests = deque(maxlen=1000)

        # Thread pool for chaos operations
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.chaos_config["processing"]["parallel_experiments"]
        )

        # Background tasks
        self.experiment_scheduler_task = None
        self.experiment_monitor_task = None
        self.resilience_monitor_task = None

        logger.info(f"Chaos Agent initialized: {agent_id}")

    async def start(self):
        """
        Start the chaos agent
        """
        await super().start()

        # Initialize clients
        await self._initialize_clients()

        # Load chaos data
        await self._load_chaos_data()

        # Start background tasks
        self.experiment_scheduler_task = asyncio.create_task(
            self._continuous_experiment_scheduler()
        )
        self.experiment_monitor_task = asyncio.create_task(self._continuous_experiment_monitor())
        self.resilience_monitor_task = asyncio.create_task(self._continuous_resilience_monitor())

        logger.info("Chaos agent started")

    async def stop(self):
        """
        Stop the chaos agent
        """
        if self.experiment_scheduler_task:
            self.experiment_scheduler_task.cancel()
            try:
                await self.experiment_scheduler_task
            except asyncio.CancelledError:
                pass

        if self.experiment_monitor_task:
            self.experiment_monitor_task.cancel()
            try:
                await self.experiment_monitor_task
            except asyncio.CancelledError:
                pass

        if self.resilience_monitor_task:
            self.resilience_monitor_task.cancel()
            try:
                await self.resilience_monitor_task
            except asyncio.CancelledError:
                pass

        # Stop all active experiments
        await self._stop_all_experiments()

        # Shutdown executor
        self.executor.shutdown(wait=True)

        await super().stop()
        logger.info("Chaos agent stopped")

    async def _initialize_clients(self):
        """
        Initialize chaos engineering clients
        """
        try:
            # Kubernetes client
            try:
                kubernetes.config.load_kube_config()
                self.k8s_client = kubernetes.client.CoreV1Api()
                logger.info("Kubernetes client initialized")
            except Exception as e:
                logger.warning(f"Kubernetes client initialization failed: {e}")

            # Docker client
            try:
                self.docker_client = docker.from_env()
                logger.info("Docker client initialized")
            except DockerException as e:
                logger.warning(f"Docker client initialization failed: {e}")
        except Exception as e:
            logger.error(f"Client initialization failed: {e}")

    async def _load_chaos_data(self):
        """
        Load existing chaos data and configurations
        """
        try:
            # Load experiment configurations, history, resilience tests, etc.
            await self._load_experiment_configs()
            await self._load_experiment_history()
            await self._load_resilience_tests()

            logger.info("Chaos data loaded")

        except Exception as e:
            logger.error(f"Chaos data loading failed: {e}")

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process chaos engineering requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "run_chaos_experiment":
                async for response in self._handle_chaos_experiment(message):
                    yield response

            elif message_type == "run_resilience_test":
                async for response in self._handle_resilience_test(message):
                    yield response

            elif message_type == "inject_failure":
                async for response in self._handle_failure_injection(message):
                    yield response

            elif message_type == "stop_experiment":
                async for response in self._handle_experiment_stop(message):
                    yield response

            elif message_type == "analyze_resilience":
                async for response in self._handle_resilience_analysis(message):
                    yield response

            elif message_type == "schedule_chaos":
                async for response in self._handle_chaos_scheduling(message):
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
            logger.error(f"Chaos processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_chaos_experiment(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle chaos experiment request
        """
        try:
            experiment_type = message.content.get("experiment_type")
            targets = message.content.get("targets", [])
            parameters = message.content.get("parameters", {})

            # Run chaos experiment
            experiment_result = await self._run_chaos_experiment(
                experiment_type, targets, parameters
            )

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "chaos_experiment_response",
                    "experiment_result": experiment_result,
                    "experiment_type": experiment_type,
                    "targets": targets,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Chaos experiment handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _run_chaos_experiment(
        self, experiment_type: str, targets: list[str], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Run chaos engineering experiment
        """
        try:
            experiment_id = str(uuid.uuid4())
            experiment_start_time = datetime.now()

            # Initialize experiment tracking
            self.active_experiments[experiment_id] = {
                "id": experiment_id,
                "type": experiment_type,
                "targets": targets,
                "parameters": parameters,
                "start_time": experiment_start_time,
                "status": "running",
                "progress": {},
                "errors": [],
                "metrics_before": {},
                "metrics_after": {},
            }

            # Check safety constraints
            safety_check = await self._check_experiment_safety(experiment_type, targets)
            if not safety_check.get("safe"):
                return {
                    "experiment_id": experiment_id,
                    "success": False,
                    "error": safety_check.get("reason"),
                    "safety_violation": True,
                }

            # Collect baseline metrics
            baseline_metrics = await self._collect_baseline_metrics(targets)
            self.active_experiments[experiment_id]["metrics_before"] = baseline_metrics

            experiment_result = {}

            # Execute experiment based on type
            if experiment_type == "pod_kill":
                result = await self._experiment_pod_kill(targets, parameters)
                experiment_result["pod_kill"] = result

            elif experiment_type == "network_delay":
                result = await self._experiment_network_delay(targets, parameters)
                experiment_result["network_delay"] = result

            elif experiment_type == "resource_stress":
                result = await self._experiment_resource_stress(targets, parameters)
                experiment_result["resource_stress"] = result

            elif experiment_type == "disk_fill":
                result = await self._experiment_disk_fill(targets, parameters)
                experiment_result["disk_fill"] = result

            elif experiment_type == "service_unavailable":
                result = await self._experiment_service_unavailable(targets, parameters)
                experiment_result["service_unavailable"] = result

            else:
                experiment_result["error"] = f"Unsupported experiment type: {experiment_type}"

            # Wait for experiment duration
            duration = parameters.get("duration_seconds", 60)
            await asyncio.sleep(duration)

            # Collect post-experiment metrics
            post_metrics = await self._collect_post_experiment_metrics(targets)
            self.active_experiments[experiment_id]["metrics_after"] = post_metrics

            # Analyze impact
            impact_analysis = await self._analyze_experiment_impact(
                baseline_metrics, post_metrics, experiment_type
            )

            # Clean up experiment
            cleanup_result = await self._cleanup_experiment(experiment_id, experiment_type, targets)

            # Calculate experiment statistics
            experiment_end_time = datetime.now()
            total_duration = (experiment_end_time - experiment_start_time).total_seconds()

            success = experiment_result.get("success", False)

            # Update experiment tracking
            self.active_experiments[experiment_id].update(
                {
                    "end_time": experiment_end_time,
                    "duration": total_duration,
                    "status": "completed" if success else "failed",
                    "result": experiment_result,
                    "impact_analysis": impact_analysis,
                    "cleanup_result": cleanup_result,
                }
            )

            # Add to history
            experiment_record = self.active_experiments[experiment_id].copy()
            self.experiment_history.append(experiment_record)

            # Clean up active experiment
            del self.active_experiments[experiment_id]

            return {
                "experiment_id": experiment_id,
                "experiment_type": experiment_type,
                "targets": targets,
                "start_time": experiment_start_time,
                "end_time": experiment_end_time,
                "duration_seconds": total_duration,
                "result": experiment_result,
                "impact_analysis": impact_analysis,
                "cleanup_result": cleanup_result,
                "success": success,
            }

        except Exception as e:
            logger.error(f"Chaos experiment failed: {e}")

            # Update failed experiment
            if experiment_id in self.active_experiments:
                self.active_experiments[experiment_id].update(
                    {"status": "failed", "end_time": datetime.now(), "error": str(e)}
                )
                self.experiment_history.append(self.active_experiments[experiment_id])
                del self.active_experiments[experiment_id]

            return {"error": str(e), "experiment_completed": False}

    async def _check_experiment_safety(
        self, experiment_type: str, targets: list[str]
    ) -> dict[str, Any]:
        """
        Check if experiment is safe to run
        """
        try:
            safety_config = self.chaos_config["safety"]

            # Check blast radius
            affected_count = len(targets)
            if affected_count > safety_config["blast_radius_limit"]:
                return {
                    "safe": False,
                    "reason": f"Blast radius too large: {affected_count} > {safety_config['blast_radius_limit']}",
                }

            # Check whitelisted namespaces
            if self.k8s_client:
                for target in targets:
                    try:
                        # Parse target (namespace/pod format)
                        if "/" in target:
                            namespace, pod = target.split("/", 1)
                        else:
                            namespace = "default"
                            pod = target

                        if namespace in safety_config["whitelist_namespaces"]:
                            return {
                                "safe": False,
                                "reason": f"Target in protected namespace: {namespace}",
                            }

                        # Check pod labels
                        pod_info = self.k8s_client.read_namespaced_pod(pod, namespace)
                        labels = pod_info.metadata.labels or {}

                        for blacklist_label in safety_config["blacklist_labels"]:
                            if blacklist_label in labels:
                                return {
                                    "safe": False,
                                    "reason": f"Target has protected label: {blacklist_label}",
                                }

                    except ApiException:
                        # Pod might not exist, continue checking
                        pass

            # Check experiment type safety
            dangerous_experiments = ["disk_fill"]
            if (
                experiment_type in dangerous_experiments
                and not self.chaos_config["experiments"][experiment_type]["enabled"]
            ):
                return {
                    "safe": False,
                    "reason": f"Dangerous experiment disabled: {experiment_type}",
                }

            return {"safe": True}

        except Exception as e:
            logger.error(f"Safety check failed: {e}")
            return {"safe": False, "reason": f"Safety check error: {str(e)}"}

    async def _experiment_pod_kill(
        self, targets: list[str], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute pod kill experiment
        """
        try:
            if not self.k8s_client:
                return {"success": False, "error": "Kubernetes client not available"}

            kill_percentage = parameters.get("kill_percentage", 25)
            cooldown = parameters.get("cooldown_seconds", 300)

            killed_pods = []

            for target in targets:
                try:
                    # Parse target
                    if "/" in target:
                        namespace, pod_pattern = target.split("/", 1)
                    else:
                        namespace = "default"
                        pod_pattern = target

                    # Get pods matching pattern
                    pods = self.k8s_client.list_namespaced_pod(namespace)
                    matching_pods = [pod for pod in pods.items if pod_pattern in pod.metadata.name]

                    # Calculate how many to kill
                    kill_count = max(1, int(len(matching_pods) * kill_percentage / 100))
                    pods_to_kill = random.sample(matching_pods, min(kill_count, len(matching_pods)))

                    for pod in pods_to_kill:
                        # Kill pod by deleting it
                        self.k8s_client.delete_namespaced_pod(
                            pod.metadata.name, namespace, grace_period_seconds=0
                        )
                        killed_pods.append(f"{namespace}/{pod.metadata.name}")

                        # Cooldown between kills
                        await asyncio.sleep(cooldown / len(pods_to_kill))

                except ApiException as e:
                    logger.error(f"Pod kill failed for {target}: {e}")
                    continue

            return {
                "success": True,
                "experiment_type": "pod_kill",
                "killed_pods": killed_pods,
                "kill_percentage": kill_percentage,
                "total_killed": len(killed_pods),
            }

        except Exception as e:
            logger.error(f"Pod kill experiment failed: {e}")
            return {"success": False, "error": str(e)}

    async def _experiment_network_delay(
        self, targets: list[str], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute network delay experiment
        """
        try:
            delay_ms = parameters.get("delay_ms", 1000)
            jitter_ms = parameters.get("jitter_ms", 200)
            duration = parameters.get("duration_seconds", 60)

            # Use Litmus Chaos or Chaos Mesh for network experiments
            if self.chaos_config["tools"]["litmus_chaos"]["enabled"]:
                # Create Litmus chaos experiment
                experiment_yaml = f"""
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: network-delay-{str(uuid.uuid4())[:8]}
  namespace: {self.chaos_config["tools"]["litmus_chaos"]["namespace"]}
spec:
  appinfo:
    appns: default
    applabel: "app in ({",".join(targets)})"
  chaosServiceAccount: litmus-admin
  experiments:
  - name: network-chaos
    spec:
      components:
        env:
        - name: NETWORK_INTERFACE
          value: 'eth0'
        - name: TARGET_CONTAINER
          value: ''
        - name: NETWORK_LATENCY
          value: '{delay_ms}ms'
        - name: JITTER
          value: '{jitter_ms}ms'
        - name: TOTAL_CHAOS_DURATION
          value: '{duration}s'
"""

                # Apply experiment
                with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
                    f.write(experiment_yaml)
                    temp_file = f.name

                try:
                    subprocess.run(
                        ["kubectl", "apply", "-f", temp_file], check=True, capture_output=True
                    )

                    return {
                        "success": True,
                        "experiment_type": "network_delay",
                        "delay_ms": delay_ms,
                        "jitter_ms": jitter_ms,
                        "duration_seconds": duration,
                        "tool": "litmus_chaos",
                    }

                finally:
                    os.unlink(temp_file)

            else:
                return {
                    "success": False,
                    "error": "No chaos tool available for network experiments",
                }

        except subprocess.CalledProcessError as e:
            logger.error(f"Network delay experiment failed: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Network delay experiment failed: {e}")
            return {"success": False, "error": str(e)}

    async def _experiment_resource_stress(
        self, targets: list[str], parameters: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute resource stress experiment
        """
        try:
            cpu_percentage = parameters.get("cpu_percentage", 80)
            memory_percentage = parameters.get("memory_percentage", 85)
            duration = parameters.get("duration_seconds", 120)

            # Use stress-ng or similar tool
            stress_commands = []

            for target in targets:
                try:
                    # Parse target
                    if "/" in target:
                        namespace, pod = target.split("/", 1)
                    else:
                        namespace = "default"
                        pod = target

                    # Execute stress command in pod
                    stress_cmd = [
                        "kubectl",
                        "exec",
                        "-n",
                        namespace,
                        pod,
                        "--",
                        "stress-ng",
                        "--cpu",
                        str(cpu_percentage // 10),  # stress-ng uses number of CPUs
                        "--vm",
                        "1",
                        "--vm-bytes",
                        f"{memory_percentage}%",
                        "--timeout",
                        f"{duration}s",
                    ]

                    # Run stress test asynchronously
                    process = await asyncio.create_subprocess_exec(
                        *stress_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )

                    stress_commands.append(
                        {"target": target, "command": " ".join(stress_cmd), "process": process}
                    )

                except Exception as e:
                    logger.error(f"Resource stress setup failed for {target}: {e}")
                    continue

            # Wait for all stress tests to complete
            results = []
            for stress_cmd in stress_commands:
                try:
                    stdout, stderr = await stress_cmd["process"].communicate()
                    results.append(
                        {
                            "target": stress_cmd["target"],
                            "success": stress_cmd["process"].returncode == 0,
                            "stdout": stdout.decode(),
                            "stderr": stderr.decode(),
                        }
                    )
                except Exception as e:
                    results.append(
                        {"target": stress_cmd["target"], "success": False, "error": str(e)}
                    )

            successful_stresses = sum(1 for r in results if r["success"])

            return {
                "success": successful_stresses > 0,
                "experiment_type": "resource_stress",
                "cpu_percentage": cpu_percentage,
                "memory_percentage": memory_percentage,
                "duration_seconds": duration,
                "successful_stresses": successful_stresses,
                "total_targets": len(targets),
                "results": results,
            }

        except Exception as e:
            logger.error(f"Resource stress experiment failed: {e}")
            return {"success": False, "error": str(e)}

    async def _collect_baseline_metrics(self, targets: list[str]) -> dict[str, Any]:
        """
        Collect baseline metrics before experiment
        """
        try:
            metrics = {}

            # Collect Kubernetes metrics
            if self.k8s_client:
                for target in targets:
                    try:
                        # Parse target
                        if "/" in target:
                            namespace, pod = target.split("/", 1)
                        else:
                            namespace = "default"
                            pod = target

                        # Get pod metrics
                        pod_metrics = self.k8s_client.read_namespaced_pod(pod, namespace)

                        metrics[target] = {
                            "status": pod_metrics.status.phase,
                            "ready_containers": sum(
                                1 for c in pod_metrics.status.container_statuses or [] if c.ready
                            ),
                            "total_containers": len(pod_metrics.status.container_statuses or []),
                        }

                    except ApiException:
                        metrics[target] = {"error": "Pod not found"}

            # Collect system metrics (simplified)
            metrics["system"] = {
                "timestamp": datetime.now().isoformat(),
                "cpu_usage": random.uniform(10, 30),  # Mock data
                "memory_usage": random.uniform(40, 60),  # Mock data
            }

            return metrics

        except Exception as e:
            logger.error(f"Baseline metrics collection failed: {e}")
            return {"error": str(e)}

    async def _collect_post_experiment_metrics(self, targets: list[str]) -> dict[str, Any]:
        """
        Collect metrics after experiment
        """
        try:
            # Similar to baseline collection but after experiment
            return await self._collect_baseline_metrics(targets)

        except Exception as e:
            logger.error(f"Post-experiment metrics collection failed: {e}")
            return {"error": str(e)}

    async def _analyze_experiment_impact(
        self, baseline_metrics: dict[str, Any], post_metrics: dict[str, Any], experiment_type: str
    ) -> dict[str, Any]:
        """
        Analyze the impact of the chaos experiment
        """
        try:
            analysis = {
                "experiment_type": experiment_type,
                "baseline_timestamp": baseline_metrics.get("system", {}).get("timestamp"),
                "post_timestamp": post_metrics.get("system", {}).get("timestamp"),
                "impact_metrics": {},
                "severity": "low",
            }

            # Analyze pod status changes
            pod_impacts = []
            for target in baseline_metrics:
                if target != "system":
                    baseline = baseline_metrics[target]
                    post = post_metrics.get(target, {})

                    if baseline.get("status") != post.get("status"):
                        pod_impacts.append(
                            {
                                "target": target,
                                "status_change": f"{baseline.get('status')} -> {post.get('status')}",
                                "severity": "high" if post.get("status") == "Failed" else "medium",
                            }
                        )

            analysis["pod_impacts"] = pod_impacts

            # Analyze system metrics changes
            baseline_cpu = baseline_metrics.get("system", {}).get("cpu_usage", 0)
            post_cpu = post_metrics.get("system", {}).get("cpu_usage", 0)
            cpu_change = post_cpu - baseline_cpu

            baseline_memory = baseline_metrics.get("system", {}).get("memory_usage", 0)
            post_memory = post_metrics.get("system", {}).get("memory_usage", 0)
            memory_change = post_memory - baseline_memory

            analysis["impact_metrics"] = {
                "cpu_change_percentage": cpu_change,
                "memory_change_percentage": memory_change,
                "pods_affected": len(pod_impacts),
            }

            # Determine overall severity
            if len(pod_impacts) > 2 or abs(cpu_change) > 50 or abs(memory_change) > 30:
                analysis["severity"] = "high"
            elif len(pod_impacts) > 0 or abs(cpu_change) > 20 or abs(memory_change) > 15:
                analysis["severity"] = "medium"

            return analysis

        except Exception as e:
            logger.error(f"Experiment impact analysis failed: {e}")
            return {"error": str(e)}

    async def _cleanup_experiment(
        self, experiment_id: str, experiment_type: str, targets: list[str]
    ) -> dict[str, Any]:
        """
        Clean up after chaos experiment
        """
        try:
            cleanup_results = {}

            # Clean up based on experiment type
            if experiment_type == "network_delay":
                # Clean up Litmus chaos engine
                if self.chaos_config["tools"]["litmus_chaos"]["enabled"]:
                    cleanup_cmd = [
                        "kubectl",
                        "delete",
                        "chaosengine",
                        f"network-delay-{experiment_id[:8]}",
                        "-n",
                        self.chaos_config["tools"]["litmus_chaos"]["namespace"],
                    ]

                    try:
                        subprocess.run(cleanup_cmd, check=True, capture_output=True)
                        cleanup_results["litmus_cleanup"] = True
                    except subprocess.CalledProcessError as e:
                        cleanup_results["litmus_cleanup"] = False
                        cleanup_results["litmus_error"] = str(e)

            # Additional cleanup for other experiment types...

            return {"success": True, "cleanup_results": cleanup_results}

        except Exception as e:
            logger.error(f"Experiment cleanup failed: {e}")
            return {"success": False, "error": str(e)}

    # Background monitoring tasks
    async def _continuous_experiment_scheduler(self):
        """
        Continuous experiment scheduling
        """
        try:
            while True:
                try:
                    # Check for scheduled experiments
                    await self._check_scheduled_experiments()

                    # Clean up old experiments
                    await self._cleanup_old_experiments()

                except Exception as e:
                    logger.error(f"Experiment scheduler error: {e}")

                # Check every minute
                await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("Experiment scheduler cancelled")
            raise

    async def _continuous_experiment_monitor(self):
        """
        Continuous experiment monitoring
        """
        try:
            while True:
                try:
                    # Monitor active experiments
                    await self._monitor_active_experiments()

                    # Check experiment timeouts
                    await self._check_experiment_timeouts()

                except Exception as e:
                    logger.error(f"Experiment monitor error: {e}")

                # Monitor every 30 seconds
                await asyncio.sleep(30)

        except asyncio.CancelledError:
            logger.info("Experiment monitor cancelled")
            raise

    async def _continuous_resilience_monitor(self):
        """
        Continuous resilience monitoring
        """
        try:
            while True:
                try:
                    # Monitor system resilience
                    await self._monitor_system_resilience()

                    # Run automated resilience tests
                    await self._run_automated_resilience_tests()

                except Exception as e:
                    logger.error(f"Resilience monitor error: {e}")

                # Monitor every 300 seconds (5 minutes)
                await asyncio.sleep(300)

        except asyncio.CancelledError:
            logger.info("Resilience monitor cancelled")
            raise

    # Additional helper methods would continue...

    async def _load_experiment_configs(self):
        """Load experiment configurations"""
        try:
            # Implementation for loading experiment configurations
            pass
        except Exception as e:
            logger.error(f"Experiment configs loading failed: {e}")

    async def _load_experiment_history(self):
        """Load experiment history"""
        try:
            # Implementation for loading experiment history
            pass
        except Exception as e:
            logger.error(f"Experiment history loading failed: {e}")

    async def _load_resilience_tests(self):
        """Load resilience tests"""
        try:
            # Implementation for loading resilience tests
            pass
        except Exception as e:
            logger.error(f"Resilience tests loading failed: {e}")

    async def _check_scheduled_experiments(self):
        """Check for scheduled experiments"""
        try:
            # Implementation for checking scheduled experiments
            pass
        except Exception as e:
            logger.error(f"Scheduled experiments check failed: {e}")

    async def _cleanup_old_experiments(self):
        """Clean up old experiments"""
        try:
            # Implementation for cleaning up old experiments
            pass
        except Exception as e:
            logger.error(f"Old experiments cleanup failed: {e}")

    async def _monitor_active_experiments(self):
        """Monitor active experiments"""
        try:
            # Implementation for monitoring active experiments
            pass
        except Exception as e:
            logger.error(f"Active experiments monitoring failed: {e}")

    async def _check_experiment_timeouts(self):
        """Check experiment timeouts"""
        try:
            # Implementation for checking experiment timeouts
            pass
        except Exception as e:
            logger.error(f"Experiment timeouts check failed: {e}")

    async def _monitor_system_resilience(self):
        """Monitor system resilience"""
        try:
            # Implementation for monitoring system resilience
            pass
        except Exception as e:
            logger.error(f"System resilience monitoring failed: {e}")

    async def _run_automated_resilience_tests(self):
        """Run automated resilience tests"""
        try:
            # Implementation for running automated resilience tests
            pass
        except Exception as e:
            logger.error(f"Automated resilience tests failed: {e}")

    async def _stop_all_experiments(self):
        """Stop all active experiments"""
        try:
            # Implementation for stopping all experiments
            pass
        except Exception as e:
            logger.error(f"Stop all experiments failed: {e}")


# ========== TEST ==========
if __name__ == "__main__":

    async def test_chaos_agent():
        # Initialize chaos agent
        agent = ChaosAgent()
        await agent.start()

        # Test chaos experiment
        experiment_message = AgentMessage(
            id="test_chaos",
            from_agent="test",
            to_agent="chaos_agent",
            content={
                "type": "run_chaos_experiment",
                "experiment_type": "pod_kill",
                "targets": ["test-pod"],
                "parameters": {"kill_percentage": 25, "duration_seconds": 30},
            },
            timestamp=datetime.now(),
        )

        print("Testing chaos agent...")
        async for response in agent.process_message(experiment_message):
            print(f"Chaos response: {response.content.get('type')}")
            experiment_result = response.content.get("experiment_result")
            print(f"Experiment successful: {experiment_result.get('success')}")

        # Test resilience test
        resilience_message = AgentMessage(
            id="test_resilience",
            from_agent="test",
            to_agent="chaos_agent",
            content={
                "type": "run_resilience_test",
                "test_type": "circuit_breaker",
                "targets": ["predator-api"],
                "parameters": {"failure_rate": 50, "duration_seconds": 60},
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(resilience_message):
            print(f"Resilience response: {response.content.get('type')}")
            resilience_result = response.content.get("resilience_result")
            print(f"Resilience test successful: {resilience_result.get('success')}")

        # Stop agent
        await agent.stop()
        print("Chaos agent test completed")

    # Run test
    asyncio.run(test_chaos_agent())
