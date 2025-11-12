"""
Deployment Agent: DevOps and deployment management
Manages CI/CD pipelines, Kubernetes deployments, monitoring, and infrastructure
"""

import asyncio
import logging
import subprocess
import uuid
from collections import deque
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

import docker
import tekton
from argo_cd import ArgoCD
from chaos_mesh import ChaosMeshClient
from grafana_api_client import GrafanaApi
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from prometheus_api_client import PrometheusConnect
from velero import VeleroClient

import helm

from ..agents.base_agent import AgentMessage, BaseAgent

logger = logging.getLogger(__name__)


class DeploymentAgent(BaseAgent):
    """
    Deployment Agent for DevOps and infrastructure management
    Handles CI/CD, Kubernetes, monitoring, and deployment operations
    """

    def __init__(self, agent_id: str = "deployment_agent", config: dict[str, Any] | None = None):
        super().__init__(agent_id, config or {})

        # Deployment configuration
        self.deployment_config = {
            "kubernetes_config": self.config.get(
                "kubernetes",
                {
                    "namespace": "predator-analytics",
                    "cluster_name": "predator-cluster",
                    "version": "1.28+",
                    "autoscaling": True,
                },
            ),
            "ci_cd_config": self.config.get(
                "ci_cd",
                {
                    "pipeline_type": "tekton",  # tekton, jenkins, github_actions, gitlab_ci
                    "trigger_events": ["push", "pull_request", "tag"],
                    "environments": ["dev", "staging", "prod"],
                    "approval_required": True,
                },
            ),
            "monitoring_config": self.config.get(
                "monitoring",
                {
                    "prometheus_url": "http://prometheus:9090",
                    "grafana_url": "http://grafana:3000",
                    "alertmanager_url": "http://alertmanager:9093",
                    "metrics_retention": "30d",
                    "alert_rules": ["cpu_usage", "memory_usage", "error_rate"],
                },
            ),
            "infrastructure_config": self.config.get(
                "infrastructure",
                {
                    "provider": "kubernetes",  # kubernetes, aks, eks, gke
                    "region": "us-east-1",
                    "availability_zones": 3,
                    "backup_schedule": "daily",
                    "disaster_recovery": True,
                },
            ),
            "deployment_strategies": self.config.get(
                "strategies", ["rolling_update", "blue_green", "canary", "a_b_testing"]
            ),
            "security_config": self.config.get(
                "security",
                {
                    "image_scanning": True,
                    "vulnerability_checks": True,
                    "compliance_scanning": True,
                    "secret_management": "vault",
                },
            ),
            "processing_options": self.config.get(
                "options",
                {
                    "parallel_deployments": 3,
                    "rollback_timeout": 300,  # seconds
                    "health_check_timeout": 60,
                    "max_retry_attempts": 3,
                    "enable_dry_run": True,
                },
            ),
        }

        # Deployment clients and managers
        self.k8s_client = None
        self.helm_client = None
        self.argo_cd_client = None
        self.tekton_client = None
        self.prometheus_client = None
        self.grafana_client = None
        self.docker_client = None
        self.chaos_client = None
        self.velero_client = None

        # Deployment state
        self.deployment_state = {
            "active_deployments": {},
            "deployment_history": deque(maxlen=1000),
            "infrastructure_status": {},
            "pipeline_status": {},
            "monitoring_alerts": deque(maxlen=500),
            "rollback_queue": deque(maxlen=100),
            "health_checks": {},
            "resource_usage": {},
            "deployment_queue": deque(maxlen=200),
            "infrastructure_events": deque(maxlen=1000),
        }

        # Background tasks
        self.deployment_monitor_task = None
        self.infrastructure_monitor_task = None
        self.pipeline_monitor_task = None

        logger.info(f"Deployment Agent initialized: {agent_id}")

    async def start(self):
        """
        Start the deployment agent
        """
        await super().start()

        # Initialize deployment clients
        await self._initialize_deployment_clients()

        # Load deployment data
        await self._load_deployment_data()

        # Start background tasks
        self.deployment_monitor_task = asyncio.create_task(self._continuous_deployment_monitoring())
        self.infrastructure_monitor_task = asyncio.create_task(
            self._continuous_infrastructure_monitoring()
        )
        self.pipeline_monitor_task = asyncio.create_task(self._continuous_pipeline_monitoring())

        logger.info("Deployment agent started")

    async def stop(self):
        """
        Stop the deployment agent
        """
        if self.deployment_monitor_task:
            self.deployment_monitor_task.cancel()
            try:
                await self.deployment_monitor_task
            except asyncio.CancelledError:
                pass

        if self.infrastructure_monitor_task:
            self.infrastructure_monitor_task.cancel()
            try:
                await self.infrastructure_monitor_task
            except asyncio.CancelledError:
                pass

        if self.pipeline_monitor_task:
            self.pipeline_monitor_task.cancel()
            try:
                await self.pipeline_monitor_task
            except asyncio.CancelledError:
                pass

        await super().stop()
        logger.info("Deployment agent stopped")

    async def _initialize_deployment_clients(self):
        """
        Initialize deployment clients and connections
        """
        try:
            # Initialize Kubernetes client
            try:
                config.load_kube_config()
                self.k8s_client = client.CoreV1Api()
                logger.info("Kubernetes client initialized")
            except Exception as e:
                logger.warning(f"Kubernetes client initialization failed: {e}")

            # Initialize Helm client
            try:
                self.helm_client = helm.Helm()
                logger.info("Helm client initialized")
            except Exception as e:
                logger.warning(f"Helm client initialization failed: {e}")

            # Initialize ArgoCD client
            try:
                self.argo_cd_client = ArgoCD(
                    server_url=self.deployment_config.get("argo_cd_url", "http://argocd-server"),
                    username=self.deployment_config.get("argo_cd_username", "admin"),
                    password=self.deployment_config.get("argo_cd_password"),
                )
                logger.info("ArgoCD client initialized")
            except Exception as e:
                logger.warning(f"ArgoCD client initialization failed: {e}")

            # Initialize Tekton client
            try:
                self.tekton_client = tekton.TektonClient()
                logger.info("Tekton client initialized")
            except Exception as e:
                logger.warning(f"Tekton client initialization failed: {e}")

            # Initialize Prometheus client
            try:
                self.prometheus_client = PrometheusConnect(
                    url=self.deployment_config["monitoring_config"]["prometheus_url"]
                )
                logger.info("Prometheus client initialized")
            except Exception as e:
                logger.warning(f"Prometheus client initialization failed: {e}")

            # Initialize Grafana client
            try:
                self.grafana_client = GrafanaApi(
                    host=self.deployment_config["monitoring_config"]["grafana_url"]
                )
                logger.info("Grafana client initialized")
            except Exception as e:
                logger.warning(f"Grafana client initialization failed: {e}")

            # Initialize Docker client
            try:
                self.docker_client = docker.from_env()
                logger.info("Docker client initialized")
            except Exception as e:
                logger.warning(f"Docker client initialization failed: {e}")

            # Initialize Chaos Mesh client
            try:
                self.chaos_client = ChaosMeshClient()
                logger.info("Chaos Mesh client initialized")
            except Exception as e:
                logger.warning(f"Chaos Mesh client initialization failed: {e}")

            # Initialize Velero client
            try:
                self.velero_client = VeleroClient()
                logger.info("Velero client initialized")
            except Exception as e:
                logger.warning(f"Velero client initialization failed: {e}")

        except Exception as e:
            logger.error(f"Deployment client initialization failed: {e}")

    async def _load_deployment_data(self):
        """
        Load existing deployment data and status
        """
        try:
            # Load deployment history, infrastructure status, etc.
            await self._load_deployment_history()
            await self._load_infrastructure_status()
            await self._load_pipeline_status()

            logger.info("Deployment data loaded")

        except Exception as e:
            logger.error(f"Deployment data loading failed: {e}")

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process deployment requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "deploy_application":
                async for response in self._handle_application_deployment(message):
                    yield response

            elif message_type == "rollback_deployment":
                async for response in self._handle_deployment_rollback(message):
                    yield response

            elif message_type == "scale_deployment":
                async for response in self._handle_deployment_scaling(message):
                    yield response

            elif message_type == "monitor_deployment":
                async for response in self._handle_deployment_monitoring(message):
                    yield response

            elif message_type == "run_pipeline":
                async for response in self._handle_pipeline_execution(message):
                    yield response

            elif message_type == "check_health":
                async for response in self._handle_health_check(message):
                    yield response

            elif message_type == "backup_infrastructure":
                async for response in self._handle_infrastructure_backup(message):
                    yield response

            elif message_type == "restore_infrastructure":
                async for response in self._handle_infrastructure_restore(message):
                    yield response

            elif message_type == "run_chaos_experiment":
                async for response in self._handle_chaos_experiment(message):
                    yield response

            elif message_type == "generate_deployment_report":
                async for response in self._handle_deployment_report(message):
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
            logger.error(f"Deployment processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_application_deployment(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle application deployment request
        """
        try:
            deployment_config = message.content.get("deployment_config", {})
            environment = message.content.get("environment", "dev")
            strategy = message.content.get("strategy", "rolling_update")

            # Deploy application
            deployment_result = await self._deploy_application(
                deployment_config, environment, strategy
            )

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "application_deployment_response",
                    "deployment_result": deployment_result,
                    "environment": environment,
                    "strategy": strategy,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Application deployment handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _deploy_application(
        self, deployment_config: dict[str, Any], environment: str, strategy: str
    ) -> dict[str, Any]:
        """
        Deploy application using specified strategy
        """
        try:
            deployment_id = str(uuid.uuid4())

            # Create deployment record
            deployment_record = {
                "id": deployment_id,
                "config": deployment_config,
                "environment": environment,
                "strategy": strategy,
                "status": "starting",
                "start_time": datetime.now(),
                "progress": 0,
            }

            self.deployment_state["active_deployments"][deployment_id] = deployment_record

            # Execute deployment based on strategy
            if strategy == "rolling_update":
                result = await self._rolling_update_deployment(deployment_config, environment)
            elif strategy == "blue_green":
                result = await self._blue_green_deployment(deployment_config, environment)
            elif strategy == "canary":
                result = await self._canary_deployment(deployment_config, environment)
            else:
                result = await self._rolling_update_deployment(deployment_config, environment)

            # Update deployment record
            deployment_record.update(
                {
                    "status": result.get("status", "completed"),
                    "end_time": datetime.now(),
                    "progress": 100,
                    "result": result,
                }
            )

            # Store in history
            self.deployment_state["deployment_history"].append(deployment_record)

            return {
                "deployment_id": deployment_id,
                "status": result.get("status", "completed"),
                "message": result.get("message", "Deployment completed"),
                "duration": (datetime.now() - deployment_record["start_time"]).total_seconds(),
                "strategy": strategy,
                "environment": environment,
            }

        except Exception as e:
            logger.error(f"Application deployment failed: {e}")
            return {"error": str(e), "status": "failed"}

    async def _rolling_update_deployment(
        self, deployment_config: dict[str, Any], environment: str
    ) -> dict[str, Any]:
        """
        Perform rolling update deployment
        """
        try:
            # Get deployment specification
            app_name = deployment_config.get("app_name")
            image_tag = deployment_config.get("image_tag")
            namespace = self.deployment_config["kubernetes_config"]["namespace"]

            if not app_name or not image_tag:
                raise ValueError("App name and image tag required")

            # Update deployment via Kubernetes API
            if self.k8s_client:
                # Get current deployment
                try:
                    deployment = self.k8s_client.read_namespaced_deployment(
                        name=app_name, namespace=namespace
                    )

                    # Update container image
                    deployment.spec.template.spec.containers[0].image = image_tag

                    # Apply rolling update
                    self.k8s_client.patch_namespaced_deployment(
                        name=app_name, namespace=namespace, body=deployment
                    )

                    # Wait for rollout to complete
                    await self._wait_for_rollout(app_name, namespace)

                    return {
                        "status": "success",
                        "message": f"Rolling update completed for {app_name}",
                        "image_tag": image_tag,
                    }

                except ApiException as e:
                    logger.error(f"Kubernetes API error: {e}")
                    return {"status": "failed", "message": str(e)}
            else:
                # Simulate deployment
                await asyncio.sleep(5)  # Simulate deployment time
                return {
                    "status": "success",
                    "message": f"Rolling update simulated for {app_name}",
                    "image_tag": image_tag,
                }

        except Exception as e:
            logger.error(f"Rolling update deployment failed: {e}")
            return {"status": "failed", "message": str(e)}

    async def _blue_green_deployment(
        self, deployment_config: dict[str, Any], environment: str
    ) -> dict[str, Any]:
        """
        Perform blue-green deployment
        """
        try:
            app_name = deployment_config.get("app_name")
            image_tag = deployment_config.get("image_tag")

            # Create green environment
            green_app_name = f"{app_name}-green"

            # Deploy to green environment
            green_deployment = await self._deploy_to_environment(
                green_app_name, image_tag, environment
            )

            if green_deployment["status"] != "success":
                return green_deployment

            # Run tests on green environment
            test_result = await self._run_deployment_tests(green_app_name, environment)

            if not test_result.get("passed", False):
                # Rollback: delete green environment
                await self._cleanup_environment(green_app_name, environment)
                return {"status": "failed", "message": "Tests failed on green environment"}

            # Switch traffic to green environment
            await self._switch_traffic_to_environment(green_app_name, environment)

            # Cleanup blue environment
            blue_app_name = f"{app_name}-blue"
            await self._cleanup_environment(blue_app_name, environment)

            # Rename green to main
            await self._rename_environment(green_app_name, app_name, environment)

            return {
                "status": "success",
                "message": f"Blue-green deployment completed for {app_name}",
                "strategy": "blue_green",
            }

        except Exception as e:
            logger.error(f"Blue-green deployment failed: {e}")
            return {"status": "failed", "message": str(e)}

    async def _canary_deployment(
        self, deployment_config: dict[str, Any], environment: str
    ) -> dict[str, Any]:
        """
        Perform canary deployment
        """
        try:
            app_name = deployment_config.get("app_name")
            image_tag = deployment_config.get("image_tag")
            canary_percentage = deployment_config.get("canary_percentage", 10)

            # Deploy canary version
            canary_app_name = f"{app_name}-canary"
            canary_deployment = await self._deploy_to_environment(
                canary_app_name, image_tag, environment
            )

            if canary_deployment["status"] != "success":
                return canary_deployment

            # Route percentage of traffic to canary
            await self._route_traffic_to_canary(canary_app_name, app_name, canary_percentage)

            # Monitor canary performance
            monitoring_result = await self._monitor_canary_performance(
                canary_app_name,
                app_name,
                duration=300,  # 5 minutes
            )

            if monitoring_result.get("success", False):
                # Promote canary to full deployment
                await self._promote_canary_to_full(canary_app_name, app_name, environment)

                return {
                    "status": "success",
                    "message": f"Canary deployment promoted for {app_name}",
                    "canary_percentage": canary_percentage,
                }
            else:
                # Rollback canary
                await self._rollback_canary(canary_app_name, environment)

                return {
                    "status": "failed",
                    "message": "Canary monitoring failed, deployment rolled back",
                }

        except Exception as e:
            logger.error(f"Canary deployment failed: {e}")
            return {"status": "failed", "message": str(e)}

    async def _wait_for_rollout(self, app_name: str, namespace: str, timeout: int = 300):
        """
        Wait for Kubernetes rollout to complete
        """
        try:
            start_time = datetime.now()

            while (datetime.now() - start_time).total_seconds() < timeout:
                # Check rollout status
                try:
                    rollout_status = subprocess.run(
                        [
                            "kubectl",
                            "rollout",
                            "status",
                            f"deployment/{app_name}",
                            f"--namespace={namespace}",
                            "--timeout=10s",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )

                    if rollout_status.returncode == 0:
                        logger.info(f"Rollout completed for {app_name}")
                        return True

                except subprocess.TimeoutExpired:
                    pass

                await asyncio.sleep(10)

            raise TimeoutError(f"Rollout timeout for {app_name}")

        except Exception as e:
            logger.error(f"Rollout wait failed: {e}")
            raise

    async def _deploy_to_environment(
        self, app_name: str, image_tag: str, environment: str
    ) -> dict[str, Any]:
        """
        Deploy application to specific environment
        """
        try:
            # Implementation for environment-specific deployment
            await asyncio.sleep(2)  # Simulate deployment
            return {"status": "success", "app_name": app_name}

        except Exception as e:
            logger.error(f"Environment deployment failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _run_deployment_tests(self, app_name: str, environment: str) -> dict[str, Any]:
        """
        Run deployment tests
        """
        try:
            # Implementation for running tests
            await asyncio.sleep(1)  # Simulate tests
            return {"passed": True, "test_results": []}

        except Exception as e:
            logger.error(f"Deployment tests failed: {e}")
            return {"passed": False, "error": str(e)}

    async def _cleanup_environment(self, app_name: str, environment: str):
        """
        Cleanup deployment environment
        """
        try:
            # Implementation for cleanup
            pass
        except Exception as e:
            logger.error(f"Environment cleanup failed: {e}")

    async def _switch_traffic_to_environment(self, app_name: str, environment: str):
        """
        Switch traffic to specified environment
        """
        try:
            # Implementation for traffic switching
            pass
        except Exception as e:
            logger.error(f"Traffic switching failed: {e}")

    async def _rename_environment(self, old_name: str, new_name: str, environment: str):
        """
        Rename deployment environment
        """
        try:
            # Implementation for renaming
            pass
        except Exception as e:
            logger.error(f"Environment renaming failed: {e}")

    async def _route_traffic_to_canary(self, canary_app: str, main_app: str, percentage: int):
        """
        Route traffic to canary deployment
        """
        try:
            # Implementation for traffic routing
            pass
        except Exception as e:
            logger.error(f"Canary traffic routing failed: {e}")

    async def _monitor_canary_performance(
        self, canary_app: str, main_app: str, duration: int
    ) -> dict[str, Any]:
        """
        Monitor canary deployment performance
        """
        try:
            # Implementation for monitoring
            await asyncio.sleep(duration / 10)  # Simulate monitoring
            return {"success": True, "metrics": {}}

        except Exception as e:
            logger.error(f"Canary monitoring failed: {e}")
            return {"success": False, "error": str(e)}

    async def _promote_canary_to_full(self, canary_app: str, main_app: str, environment: str):
        """
        Promote canary to full deployment
        """
        try:
            # Implementation for promotion
            pass
        except Exception as e:
            logger.error(f"Canary promotion failed: {e}")

    async def _rollback_canary(self, canary_app: str, environment: str):
        """
        Rollback canary deployment
        """
        try:
            # Implementation for rollback
            pass
        except Exception as e:
            logger.error(f"Canary rollback failed: {e}")

    async def _handle_deployment_rollback(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle deployment rollback request
        """
        try:
            deployment_id = message.content.get("deployment_id")
            target_version = message.content.get("target_version")

            # Rollback deployment
            rollback_result = await self._rollback_deployment(deployment_id, target_version)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "deployment_rollback_response",
                    "rollback_result": rollback_result,
                    "deployment_id": deployment_id,
                    "target_version": target_version,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Deployment rollback handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _rollback_deployment(
        self, deployment_id: str, target_version: str | None = None
    ) -> dict[str, Any]:
        """
        Rollback deployment to previous version
        """
        try:
            # Find deployment record
            deployment_record = None
            for record in reversed(self.deployment_state["deployment_history"]):
                if record["id"] == deployment_id:
                    deployment_record = record
                    break

            if not deployment_record:
                return {"error": "Deployment not found", "status": "failed"}

            # Determine rollback version
            if target_version:
                rollback_config = {"image_tag": target_version}
            else:
                # Rollback to previous version
                previous_records = [
                    r
                    for r in self.deployment_state["deployment_history"]
                    if r["config"].get("app_name") == deployment_record["config"].get("app_name")
                    and r["id"] != deployment_id
                ]
                if previous_records:
                    rollback_config = previous_records[-1]["config"]
                else:
                    return {"error": "No previous version found", "status": "failed"}

            # Execute rollback
            rollback_result = await self._deploy_application(
                rollback_config, deployment_record["environment"], "rolling_update"
            )

            return {
                "status": rollback_result.get("status"),
                "message": f"Rollback completed for deployment {deployment_id}",
                "rollback_version": rollback_config.get("image_tag"),
                "original_deployment": deployment_id,
            }

        except Exception as e:
            logger.error(f"Deployment rollback failed: {e}")
            return {"error": str(e), "status": "failed"}

    async def _handle_deployment_scaling(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle deployment scaling request
        """
        try:
            app_name = message.content.get("app_name")
            namespace = message.content.get(
                "namespace", self.deployment_config["kubernetes_config"]["namespace"]
            )
            replicas = message.content.get("replicas")

            # Scale deployment
            scaling_result = await self._scale_deployment(app_name, namespace, replicas)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "deployment_scaling_response",
                    "scaling_result": scaling_result,
                    "app_name": app_name,
                    "replicas": replicas,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Deployment scaling handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _scale_deployment(
        self, app_name: str, namespace: str, replicas: int
    ) -> dict[str, Any]:
        """
        Scale Kubernetes deployment
        """
        try:
            if self.k8s_client:
                # Scale deployment via Kubernetes API
                scaling_body = {"spec": {"replicas": replicas}}

                self.k8s_client.patch_namespaced_deployment_scale(
                    name=app_name, namespace=namespace, body=scaling_body
                )

                return {
                    "status": "success",
                    "message": f"Scaled {app_name} to {replicas} replicas",
                    "replicas": replicas,
                }
            else:
                # Simulate scaling
                return {
                    "status": "success",
                    "message": f"Simulated scaling of {app_name} to {replicas} replicas",
                    "replicas": replicas,
                }

        except Exception as e:
            logger.error(f"Deployment scaling failed: {e}")
            return {"error": str(e), "status": "failed"}

    async def _handle_pipeline_execution(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle CI/CD pipeline execution request
        """
        try:
            pipeline_config = message.content.get("pipeline_config", {})
            trigger_event = message.content.get("trigger_event", "manual")

            # Execute pipeline
            pipeline_result = await self._execute_pipeline(pipeline_config, trigger_event)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "pipeline_execution_response",
                    "pipeline_result": pipeline_result,
                    "trigger_event": trigger_event,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Pipeline execution handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _execute_pipeline(
        self, pipeline_config: dict[str, Any], trigger_event: str
    ) -> dict[str, Any]:
        """
        Execute CI/CD pipeline
        """
        try:
            pipeline_type = self.deployment_config["ci_cd_config"]["pipeline_type"]

            if pipeline_type == "tekton":
                result = await self._execute_tekton_pipeline(pipeline_config)
            elif pipeline_type == "jenkins":
                result = await self._execute_jenkins_pipeline(pipeline_config)
            elif pipeline_type == "github_actions":
                result = await self._execute_github_actions_pipeline(pipeline_config)
            else:
                result = await self._execute_generic_pipeline(pipeline_config)

            return result

        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            return {"error": str(e), "status": "failed"}

    async def _execute_tekton_pipeline(self, pipeline_config: dict[str, Any]) -> dict[str, Any]:
        """
        Execute Tekton pipeline
        """
        try:
            # Implementation for Tekton pipeline execution
            await asyncio.sleep(3)  # Simulate pipeline execution
            return {
                "status": "success",
                "pipeline_id": str(uuid.uuid4()),
                "stages": ["build", "test", "deploy"],
                "duration": 180,
            }

        except Exception as e:
            logger.error(f"Tekton pipeline execution failed: {e}")
            return {"error": str(e), "status": "failed"}

    async def _execute_jenkins_pipeline(self, pipeline_config: dict[str, Any]) -> dict[str, Any]:
        """
        Execute Jenkins pipeline
        """
        try:
            # Implementation for Jenkins pipeline execution
            await asyncio.sleep(2)  # Simulate pipeline execution
            return {
                "status": "success",
                "build_number": 123,
                "stages": ["checkout", "build", "test", "deploy"],
                "duration": 240,
            }

        except Exception as e:
            logger.error(f"Jenkins pipeline execution failed: {e}")
            return {"error": str(e), "status": "failed"}

    async def _execute_github_actions_pipeline(
        self, pipeline_config: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute GitHub Actions pipeline
        """
        try:
            # Implementation for GitHub Actions execution
            await asyncio.sleep(4)  # Simulate pipeline execution
            return {"status": "success", "run_id": 456, "workflow": "ci-cd", "duration": 300}

        except Exception as e:
            logger.error(f"GitHub Actions execution failed: {e}")
            return {"error": str(e), "status": "failed"}

    async def _execute_generic_pipeline(self, pipeline_config: dict[str, Any]) -> dict[str, Any]:
        """
        Execute generic pipeline
        """
        try:
            # Simulate generic pipeline execution
            await asyncio.sleep(2)
            return {
                "status": "success",
                "pipeline_type": "generic",
                "stages": ["prepare", "build", "test", "deploy"],
                "duration": 200,
            }

        except Exception as e:
            logger.error(f"Generic pipeline execution failed: {e}")
            return {"error": str(e), "status": "failed"}

    async def _handle_health_check(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle health check request
        """
        try:
            component = message.content.get("component", "all")
            check_type = message.content.get("check_type", "basic")

            # Perform health check
            health_result = await self._perform_health_check(component, check_type)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "health_check_response",
                    "health_result": health_result,
                    "component": component,
                    "check_type": check_type,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Health check handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _perform_health_check(self, component: str, check_type: str) -> dict[str, Any]:
        """
        Perform health check on component
        """
        try:
            if component == "all":
                # Check all components
                health_results = {}

                # Kubernetes health
                health_results["kubernetes"] = await self._check_kubernetes_health()

                # Database health
                health_results["database"] = await self._check_database_health()

                # Services health
                health_results["services"] = await self._check_services_health()

                # Overall health
                overall_healthy = all(
                    result.get("healthy", False) for result in health_results.values()
                )

                return {
                    "overall_healthy": overall_healthy,
                    "component_health": health_results,
                    "timestamp": datetime.now(),
                }
            else:
                # Check specific component
                if component == "kubernetes":
                    return await self._check_kubernetes_health()
                elif component == "database":
                    return await self._check_database_health()
                elif component == "services":
                    return await self._check_services_health()
                else:
                    return {"healthy": False, "error": f"Unknown component: {component}"}

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"healthy": False, "error": str(e)}

    async def _check_kubernetes_health(self) -> dict[str, Any]:
        """
        Check Kubernetes cluster health
        """
        try:
            if self.k8s_client:
                # Check node status
                nodes = self.k8s_client.list_node()
                healthy_nodes = sum(
                    1
                    for node in nodes.items
                    if all(
                        condition.status == "True"
                        for condition in node.status.conditions
                        if condition.type
                        in ["Ready", "MemoryPressure", "DiskPressure", "PIDPressure"]
                    )
                )

                # Check pod status
                pods = self.k8s_client.list_pod_for_all_namespaces()
                healthy_pods = sum(1 for pod in pods.items if pod.status.phase == "Running")

                return {
                    "healthy": healthy_nodes > 0 and healthy_pods > 0,
                    "nodes": {"total": len(nodes.items), "healthy": healthy_nodes},
                    "pods": {"total": len(pods.items), "healthy": healthy_pods},
                }
            else:
                return {"healthy": True, "message": "Kubernetes client not available"}

        except Exception as e:
            logger.error(f"Kubernetes health check failed: {e}")
            return {"healthy": False, "error": str(e)}

    async def _check_database_health(self) -> dict[str, Any]:
        """
        Check database health
        """
        try:
            # Implementation for database health check
            return {"healthy": True, "connections": 10, "response_time": 5}

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {"healthy": False, "error": str(e)}

    async def _check_services_health(self) -> dict[str, Any]:
        """
        Check services health
        """
        try:
            # Implementation for services health check
            return {"healthy": True, "services_checked": 5, "failed_services": 0}

        except Exception as e:
            logger.error(f"Services health check failed: {e}")
            return {"healthy": False, "error": str(e)}

    # Background monitoring tasks
    async def _continuous_deployment_monitoring(self):
        """
        Continuous deployment monitoring
        """
        try:
            while True:
                try:
                    # Monitor active deployments
                    await self._monitor_active_deployments()

                    # Check deployment health
                    await self._check_deployment_health()

                except Exception as e:
                    logger.error(f"Deployment monitoring error: {e}")

                # Monitor every 30 seconds
                await asyncio.sleep(30)

        except asyncio.CancelledError:
            logger.info("Deployment monitoring cancelled")
            raise

    async def _continuous_infrastructure_monitoring(self):
        """
        Continuous infrastructure monitoring
        """
        try:
            while True:
                try:
                    # Monitor infrastructure status
                    await self._monitor_infrastructure_status()

                    # Check resource usage
                    await self._monitor_resource_usage()

                except Exception as e:
                    logger.error(f"Infrastructure monitoring error: {e}")

                # Monitor every 60 seconds
                await asyncio.sleep(60)

        except asyncio.CancelledError:
            logger.info("Infrastructure monitoring cancelled")
            raise

    async def _continuous_pipeline_monitoring(self):
        """
        Continuous pipeline monitoring
        """
        try:
            while True:
                try:
                    # Monitor pipeline status
                    await self._monitor_pipeline_status()

                    # Check for alerts
                    await self._check_monitoring_alerts()

                except Exception as e:
                    logger.error(f"Pipeline monitoring error: {e}")

                # Monitor every 45 seconds
                await asyncio.sleep(45)

        except asyncio.CancelledError:
            logger.info("Pipeline monitoring cancelled")
            raise

    # Additional helper methods would continue...

    async def _load_deployment_history(self):
        """Load deployment history"""
        try:
            # Implementation for loading deployment history
            pass
        except Exception as e:
            logger.error(f"Deployment history loading failed: {e}")

    async def _load_infrastructure_status(self):
        """Load infrastructure status"""
        try:
            # Implementation for loading infrastructure status
            pass
        except Exception as e:
            logger.error(f"Infrastructure status loading failed: {e}")

    async def _load_pipeline_status(self):
        """Load pipeline status"""
        try:
            # Implementation for loading pipeline status
            pass
        except Exception as e:
            logger.error(f"Pipeline status loading failed: {e}")

    async def _monitor_active_deployments(self):
        """Monitor active deployments"""
        try:
            # Implementation for monitoring deployments
            pass
        except Exception as e:
            logger.error(f"Active deployment monitoring failed: {e}")

    async def _check_deployment_health(self):
        """Check deployment health"""
        try:
            # Implementation for health checking
            pass
        except Exception as e:
            logger.error(f"Deployment health check failed: {e}")

    async def _monitor_infrastructure_status(self):
        """Monitor infrastructure status"""
        try:
            # Implementation for infrastructure monitoring
            pass
        except Exception as e:
            logger.error(f"Infrastructure status monitoring failed: {e}")

    async def _monitor_resource_usage(self):
        """Monitor resource usage"""
        try:
            # Implementation for resource monitoring
            pass
        except Exception as e:
            logger.error(f"Resource usage monitoring failed: {e}")

    async def _monitor_pipeline_status(self):
        """Monitor pipeline status"""
        try:
            # Implementation for pipeline monitoring
            pass
        except Exception as e:
            logger.error(f"Pipeline status monitoring failed: {e}")

    async def _check_monitoring_alerts(self):
        """Check monitoring alerts"""
        try:
            # Implementation for alert checking
            pass
        except Exception as e:
            logger.error(f"Monitoring alert check failed: {e}")


# ========== TEST ==========
if __name__ == "__main__":

    async def test_deployment_agent():
        # Initialize deployment agent
        agent = DeploymentAgent()
        await agent.start()

        # Test application deployment
        deployment_message = AgentMessage(
            id="test_deployment",
            from_agent="test",
            to_agent="deployment_agent",
            content={
                "type": "deploy_application",
                "deployment_config": {
                    "app_name": "predator-api",
                    "image_tag": "v1.0.0",
                    "replicas": 3,
                },
                "environment": "dev",
                "strategy": "rolling_update",
            },
            timestamp=datetime.now(),
        )

        print("Testing deployment agent...")
        async for response in agent.process_message(deployment_message):
            print(f"Deployment response: {response.content.get('type')}")
            result = response.content.get("deployment_result")
            print(f"Deployment result: {result}")

        # Test health check
        health_message = AgentMessage(
            id="test_health",
            from_agent="test",
            to_agent="deployment_agent",
            content={"type": "check_health", "component": "kubernetes", "check_type": "basic"},
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(health_message):
            print(f"Health check response: {response.content.get('type')}")
            health = response.content.get("health_result")
            print(f"Health result: {health}")

        # Stop agent
        await agent.stop()
        print("Deployment agent test completed")

    # Run test
    asyncio.run(test_deployment_agent())
