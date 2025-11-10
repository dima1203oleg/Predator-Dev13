"""
Auto Heal Agent: Self-healing system
Automatically detects and resolves system issues, failures, and performance degradation
"""
import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
import asyncio
import json
from datetime import datetime, timedelta
from collections import defaultdict
import uuid
import subprocess
import psutil
import socket
import requests
from concurrent.futures import ThreadPoolExecutor

from ..agents.base_agent import BaseAgent, AgentState, AgentMessage
from ..api.database import get_db_session
from ..api.models import SystemHealth, Incident, RecoveryAction

logger = logging.getLogger(__name__)


class AutoHealAgent(BaseAgent):
    """
    Auto Heal Agent for automatic system recovery and maintenance
    Detects issues and applies healing strategies autonomously
    """
    
    def __init__(
        self,
        agent_id: str = "auto_heal_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # Health monitoring configuration
        self.monitoring_config = {
            "check_interval": self.config.get("check_interval", 60),  # seconds
            "cpu_threshold": self.config.get("cpu_threshold", 80.0),  # percentage
            "memory_threshold": self.config.get("memory_threshold", 85.0),  # percentage
            "disk_threshold": self.config.get("disk_threshold", 90.0),  # percentage
            "network_timeout": self.config.get("network_timeout", 10),  # seconds
            "max_retry_attempts": self.config.get("max_retry_attempts", 3)
        }
        
        # Service endpoints to monitor
        self.service_endpoints = self.config.get("service_endpoints", {
            "fastapi": "http://localhost:8000/health",
            "opensearch": "http://localhost:9200/_cluster/health",
            "qdrant": "http://localhost:6333/health",
            "redis": "redis://localhost:6379",
            "kafka": "localhost:9092"
        })
        
        # Healing strategies
        self.healing_strategies = {
            "service_restart": self._restart_service,
            "memory_cleanup": self._cleanup_memory,
            "disk_cleanup": self._cleanup_disk,
            "network_reset": self._reset_network,
            "database_reconnect": self._reconnect_database,
            "cache_flush": self._flush_cache,
            "log_rotation": self._rotate_logs,
            "process_restart": self._restart_process
        }
        
        # Incident tracking
        self.active_incidents = {}
        self.incident_history = []
        self.recovery_actions = []
        
        # Health status
        self.system_health = {
            "overall_status": "healthy",
            "last_check": None,
            "components": {}
        }
        
        # Background monitoring task
        self.monitoring_task = None
        
        logger.info(f"Auto Heal Agent initialized: {agent_id}")
    
    async def start(self):
        """
        Start the auto heal agent
        """
        await super().start()
        
        # Start monitoring loop
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info("Auto heal monitoring started")
    
    async def stop(self):
        """
        Stop the auto heal agent
        """
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        await super().stop()
        logger.info("Auto heal agent stopped")
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process auto heal requests
        """
        try:
            message_type = message.content.get("type", "")
            
            if message_type == "check_system_health":
                async for response in self._handle_health_check(message):
                    yield response
                    
            elif message_type == "heal_system_issue":
                async for response in self._handle_system_healing(message):
                    yield response
                    
            elif message_type == "get_incident_history":
                async for response in self._handle_incident_history(message):
                    yield response
                    
            elif message_type == "force_recovery_action":
                async for response in self._handle_force_recovery(message):
                    yield response
                    
            elif message_type == "analyze_system_performance":
                async for response in self._handle_performance_analysis(message):
                    yield response
                    
            elif message_type == "predict_system_failures":
                async for response in self._handle_failure_prediction(message):
                    yield response
                    
            else:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": f"Unknown message type: {message_type}"
                    },
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            logger.error(f"Auto heal processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _monitoring_loop(self):
        """
        Continuous system monitoring loop
        """
        try:
            while True:
                try:
                    # Perform health check
                    await self._perform_health_check()
                    
                    # Check for issues and heal
                    await self._detect_and_heal_issues()
                    
                    # Update system health status
                    await self._update_system_health()
                    
                except Exception as e:
                    logger.error(f"Monitoring loop error: {e}")
                
                # Wait for next check
                await asyncio.sleep(self.monitoring_config["check_interval"])
                
        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled")
            raise
    
    async def _perform_health_check(self):
        """
        Perform comprehensive system health check
        """
        try:
            health_status = {
                "timestamp": datetime.now(),
                "components": {}
            }
            
            # Check system resources
            health_status["components"]["system_resources"] = await self._check_system_resources()
            
            # Check service endpoints
            health_status["components"]["services"] = await self._check_service_endpoints()
            
            # Check database connectivity
            health_status["components"]["database"] = await self._check_database_connectivity()
            
            # Check external dependencies
            health_status["components"]["external_deps"] = await self._check_external_dependencies()
            
            # Update health status
            self.system_health = health_status
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
    
    async def _check_system_resources(self) -> Dict[str, Any]:
        """
        Check system resource usage
        """
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Network connections
            network_connections = len(psutil.net_connections())
            
            return {
                "cpu_usage": cpu_percent,
                "memory_usage": memory_percent,
                "disk_usage": disk_percent,
                "network_connections": network_connections,
                "status": "healthy" if (
                    cpu_percent < self.monitoring_config["cpu_threshold"] and
                    memory_percent < self.monitoring_config["memory_threshold"] and
                    disk_percent < self.monitoring_config["disk_threshold"]
                ) else "degraded"
            }
            
        except Exception as e:
            logger.error(f"System resource check failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _check_service_endpoints(self) -> Dict[str, Any]:
        """
        Check service endpoint health
        """
        try:
            service_status = {}
            
            for service_name, endpoint in self.service_endpoints.items():
                try:
                    if endpoint.startswith("http"):
                        # HTTP endpoint check
                        response = await asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: requests.get(endpoint, timeout=self.monitoring_config["network_timeout"])
                        )
                        status = "healthy" if response.status_code == 200 else "unhealthy"
                        service_status[service_name] = {
                            "status": status,
                            "response_code": response.status_code
                        }
                        
                    elif endpoint.startswith("redis"):
                        # Redis connectivity check
                        # This would require redis client
                        service_status[service_name] = {"status": "unknown"}
                        
                    else:
                        # Generic connectivity check
                        service_status[service_name] = {"status": "unknown"}
                        
                except Exception as e:
                    service_status[service_name] = {
                        "status": "unhealthy",
                        "error": str(e)
                    }
            
            # Overall service status
            unhealthy_count = sum(1 for s in service_status.values() if s["status"] == "unhealthy")
            overall_status = "healthy" if unhealthy_count == 0 else "degraded" if unhealthy_count < 3 else "critical"
            
            return {
                "services": service_status,
                "overall_status": overall_status,
                "unhealthy_count": unhealthy_count
            }
            
        except Exception as e:
            logger.error(f"Service endpoint check failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _check_database_connectivity(self) -> Dict[str, Any]:
        """
        Check database connectivity
        """
        try:
            async with get_db_session() as session:
                # Simple query to test connectivity
                result = await session.execute("SELECT 1")
                return {"status": "healthy", "response_time": 0.1}  # Mock response time
                
        except Exception as e:
            logger.error(f"Database connectivity check failed: {e}")
            return {"status": "unhealthy", "error": str(e)}
    
    async def _check_external_dependencies(self) -> Dict[str, Any]:
        """
        Check external dependencies
        """
        try:
            dependencies = {}
            
            # Check internet connectivity
            try:
                socket.create_connection(("8.8.8.8", 53), timeout=5)
                dependencies["internet"] = {"status": "healthy"}
            except:
                dependencies["internet"] = {"status": "unhealthy"}
            
            # Check model registry connectivity (if applicable)
            # This would check connections to external model providers
            
            return {
                "dependencies": dependencies,
                "overall_status": "healthy" if all(d["status"] == "healthy" for d in dependencies.values()) else "degraded"
            }
            
        except Exception as e:
            logger.error(f"External dependencies check failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _detect_and_heal_issues(self):
        """
        Detect system issues and apply healing strategies
        """
        try:
            issues = await self._identify_issues()
            
            for issue in issues:
                # Check if already handling this issue
                issue_key = f"{issue['component']}_{issue['type']}"
                if issue_key in self.active_incidents:
                    continue
                
                # Create incident
                incident_id = await self._create_incident(issue)
                
                # Attempt automatic healing
                healing_success = await self._attempt_automatic_healing(incident_id, issue)
                
                if not healing_success:
                    # Escalate if auto-healing fails
                    await self._escalate_incident(incident_id, issue)
                
        except Exception as e:
            logger.error(f"Issue detection and healing failed: {e}")
    
    async def _identify_issues(self) -> List[Dict[str, Any]]:
        """
        Identify current system issues
        """
        try:
            issues = []
            
            # Check system resources
            resources = self.system_health["components"].get("system_resources", {})
            if resources.get("status") == "degraded":
                if resources.get("cpu_usage", 0) > self.monitoring_config["cpu_threshold"]:
                    issues.append({
                        "component": "system",
                        "type": "high_cpu_usage",
                        "severity": "medium",
                        "description": f"CPU usage at {resources['cpu_usage']:.1f}%",
                        "suggested_action": "memory_cleanup"
                    })
                
                if resources.get("memory_usage", 0) > self.monitoring_config["memory_threshold"]:
                    issues.append({
                        "component": "system",
                        "type": "high_memory_usage",
                        "severity": "high",
                        "description": f"Memory usage at {resources['memory_usage']:.1f}%",
                        "suggested_action": "memory_cleanup"
                    })
                
                if resources.get("disk_usage", 0) > self.monitoring_config["disk_threshold"]:
                    issues.append({
                        "component": "system",
                        "type": "high_disk_usage",
                        "severity": "high",
                        "description": f"Disk usage at {resources['disk_usage']:.1f}%",
                        "suggested_action": "disk_cleanup"
                    })
            
            # Check services
            services = self.system_health["components"].get("services", {})
            for service_name, service_info in services.get("services", {}).items():
                if service_info.get("status") == "unhealthy":
                    issues.append({
                        "component": service_name,
                        "type": "service_unhealthy",
                        "severity": "high",
                        "description": f"Service {service_name} is unhealthy",
                        "suggested_action": "service_restart"
                    })
            
            # Check database
            database = self.system_health["components"].get("database", {})
            if database.get("status") == "unhealthy":
                issues.append({
                    "component": "database",
                    "type": "database_unhealthy",
                    "severity": "critical",
                    "description": "Database connectivity issues",
                    "suggested_action": "database_reconnect"
                })
            
            return issues
            
        except Exception as e:
            logger.error(f"Issue identification failed: {e}")
            return []
    
    async def _create_incident(self, issue: Dict[str, Any]) -> str:
        """
        Create incident record
        """
        try:
            incident_id = str(uuid.uuid4())
            
            incident = {
                "id": incident_id,
                "component": issue["component"],
                "type": issue["type"],
                "severity": issue["severity"],
                "description": issue["description"],
                "status": "active",
                "created_at": datetime.now(),
                "suggested_action": issue.get("suggested_action"),
                "attempted_actions": []
            }
            
            self.active_incidents[f"{issue['component']}_{issue['type']}"] = incident
            self.incident_history.append(incident)
            
            # Save to database
            async with get_db_session() as session:
                incident_record = Incident(
                    incident_id=incident_id,
                    component=issue["component"],
                    incident_type=issue["type"],
                    severity=issue["severity"],
                    description=issue["description"],
                    status="active",
                    created_at=datetime.now()
                )
                session.add(incident_record)
                await session.commit()
            
            logger.warning(f"Incident created: {incident_id} - {issue['description']}")
            return incident_id
            
        except Exception as e:
            logger.error(f"Incident creation failed: {e}")
            return str(uuid.uuid4())
    
    async def _attempt_automatic_healing(
        self,
        incident_id: str,
        issue: Dict[str, Any]
    ) -> bool:
        """
        Attempt automatic healing for an issue
        """
        try:
            suggested_action = issue.get("suggested_action")
            if not suggested_action or suggested_action not in self.healing_strategies:
                return False
            
            # Execute healing strategy
            healing_strategy = self.healing_strategies[suggested_action]
            success = await healing_strategy(issue)
            
            # Record recovery action
            action_record = {
                "incident_id": incident_id,
                "action": suggested_action,
                "success": success,
                "timestamp": datetime.now(),
                "details": issue
            }
            
            self.recovery_actions.append(action_record)
            
            # Update incident
            issue_key = f"{issue['component']}_{issue['type']}"
            if issue_key in self.active_incidents:
                self.active_incidents[issue_key]["attempted_actions"].append(action_record)
                
                if success:
                    self.active_incidents[issue_key]["status"] = "resolved"
                    self.active_incidents[issue_key]["resolved_at"] = datetime.now()
            
            # Save to database
            async with get_db_session() as session:
                recovery_record = RecoveryAction(
                    incident_id=incident_id,
                    action_type=suggested_action,
                    success=success,
                    executed_at=datetime.now(),
                    details=json.dumps(issue)
                )
                session.add(recovery_record)
                await session.commit()
            
            logger.info(f"Healing attempt for {incident_id}: {suggested_action} - {'SUCCESS' if success else 'FAILED'}")
            return success
            
        except Exception as e:
            logger.error(f"Automatic healing failed: {e}")
            return False
    
    async def _restart_service(self, issue: Dict[str, Any]) -> bool:
        """
        Restart a service
        """
        try:
            service_name = issue["component"]
            
            # Service-specific restart commands
            restart_commands = {
                "fastapi": ["systemctl", "restart", "predator-api"],
                "opensearch": ["systemctl", "restart", "opensearch"],
                "qdrant": ["docker", "restart", "qdrant"],
                "redis": ["systemctl", "restart", "redis"],
                "kafka": ["systemctl", "restart", "kafka"]
            }
            
            if service_name in restart_commands:
                cmd = restart_commands[service_name]
                result = await asyncio.get_event_loop().run_in_executor(
                    None, subprocess.run, cmd, {"capture_output": True, "text": True}
                )
                return result.returncode == 0
            
            return False
            
        except Exception as e:
            logger.error(f"Service restart failed: {e}")
            return False
    
    async def _cleanup_memory(self, issue: Dict[str, Any]) -> bool:
        """
        Clean up system memory
        """
        try:
            # Force garbage collection
            import gc
            gc.collect()
            
            # Clear system cache (Linux specific)
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, subprocess.run, 
                    ["sync", "&&", "echo", "3", ">", "/proc/sys/vm/drop_caches"],
                    {"shell": True, "capture_output": True}
                )
                return result.returncode == 0
            except:
                # Fallback for non-Linux systems
                return True
                
        except Exception as e:
            logger.error(f"Memory cleanup failed: {e}")
            return False
    
    async def _cleanup_disk(self, issue: Dict[str, Any]) -> bool:
        """
        Clean up disk space
        """
        try:
            # Remove old log files
            log_dirs = ["/var/log", "./logs"]
            for log_dir in log_dirs:
                if os.path.exists(log_dir):
                    # Remove files older than 30 days
                    cmd = f"find {log_dir} -type f -mtime +30 -delete"
                    result = await asyncio.get_event_loop().run_in_executor(
                        None, subprocess.run, cmd, {"shell": True, "capture_output": True}
                    )
            
            # Clean package manager cache
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, subprocess.run, ["apt-get", "autoclean"], {"capture_output": True}
                )
            except:
                pass  # Not on apt-based system
            
            return True
            
        except Exception as e:
            logger.error(f"Disk cleanup failed: {e}")
            return False
    
    async def _reset_network(self, issue: Dict[str, Any]) -> bool:
        """
        Reset network connections
        """
        try:
            # Restart network service
            result = await asyncio.get_event_loop().run_in_executor(
                None, subprocess.run, 
                ["systemctl", "restart", "networking"], 
                {"capture_output": True}
            )
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Network reset failed: {e}")
            return False
    
    async def _reconnect_database(self, issue: Dict[str, Any]) -> bool:
        """
        Reconnect to database
        """
        try:
            # Force reconnection by closing existing connections
            # This would typically involve connection pool management
            async with get_db_session() as session:
                await session.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction'")
            
            return True
            
        except Exception as e:
            logger.error(f"Database reconnect failed: {e}")
            return False
    
    async def _flush_cache(self, issue: Dict[str, Any]) -> bool:
        """
        Flush system caches
        """
        try:
            # Clear Redis cache if available
            # This would require redis client
            return True
            
        except Exception as e:
            logger.error(f"Cache flush failed: {e}")
            return False
    
    async def _rotate_logs(self, issue: Dict[str, Any]) -> bool:
        """
        Rotate log files
        """
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None, subprocess.run, 
                ["logrotate", "-f", "/etc/logrotate.conf"], 
                {"capture_output": True}
            )
            return result.returncode == 0
            
        except Exception as e:
            logger.error(f"Log rotation failed: {e}")
            return False
    
    async def _restart_process(self, issue: Dict[str, Any]) -> bool:
        """
        Restart a specific process
        """
        try:
            # Find and restart process by name
            process_name = issue.get("process_name", issue["component"])
            
            # Kill existing processes
            for proc in psutil.process_iter(['pid', 'name']):
                if process_name.lower() in proc.info['name'].lower():
                    proc.kill()
            
            # Restart would depend on how the process is managed
            # This is a simplified version
            return True
            
        except Exception as e:
            logger.error(f"Process restart failed: {e}")
            return False
    
    async def _escalate_incident(self, incident_id: str, issue: Dict[str, Any]):
        """
        Escalate incident when auto-healing fails
        """
        try:
            logger.warning(f"Escalating incident {incident_id}: {issue['description']}")
            
            # In a real system, this would:
            # 1. Send alerts to on-call engineers
            # 2. Create tickets in incident management system
            # 3. Notify stakeholders
            
            # For now, just log the escalation
            escalation_record = {
                "incident_id": incident_id,
                "escalated_at": datetime.now(),
                "reason": "auto_healing_failed",
                "severity": issue["severity"]
            }
            
            # Update incident status
            issue_key = f"{issue['component']}_{issue['type']}"
            if issue_key in self.active_incidents:
                self.active_incidents[issue_key]["status"] = "escalated"
            
        except Exception as e:
            logger.error(f"Incident escalation failed: {e}")
    
    async def _update_system_health(self):
        """
        Update overall system health status
        """
        try:
            components = self.system_health.get("components", {})
            
            # Calculate overall status
            statuses = []
            for component_status in components.values():
                if isinstance(component_status, dict):
                    status = component_status.get("status") or component_status.get("overall_status")
                    if status:
                        statuses.append(status)
            
            # Determine overall status
            if "critical" in statuses:
                overall_status = "critical"
            elif "unhealthy" in statuses or "error" in statuses:
                overall_status = "unhealthy"
            elif "degraded" in statuses:
                overall_status = "degraded"
            else:
                overall_status = "healthy"
            
            self.system_health["overall_status"] = overall_status
            self.system_health["last_check"] = datetime.now()
            
        except Exception as e:
            logger.error(f"System health update failed: {e}")
    
    async def _handle_health_check(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle system health check request
        """
        try:
            # Perform fresh health check
            await self._perform_health_check()
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "health_check_response",
                    "health_status": self.system_health,
                    "active_incidents": len(self.active_incidents),
                    "recent_recoveries": len([r for r in self.recovery_actions if (datetime.now() - r["timestamp"]).seconds < 3600])
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Health check handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _handle_system_healing(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle manual system healing request
        """
        try:
            component = message.content.get("component")
            issue_type = message.content.get("issue_type")
            healing_action = message.content.get("healing_action")
            
            # Create mock issue for manual healing
            issue = {
                "component": component,
                "type": issue_type,
                "severity": "high",
                "description": f"Manual healing requested for {component}",
                "suggested_action": healing_action
            }
            
            # Attempt healing
            incident_id = await self._create_incident(issue)
            success = await self._attempt_automatic_healing(incident_id, issue)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "healing_response",
                    "incident_id": incident_id,
                    "component": component,
                    "action": healing_action,
                    "success": success
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"System healing handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _handle_incident_history(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle incident history request
        """
        try:
            limit = message.content.get("limit", 50)
            
            # Get recent incidents
            recent_incidents = self.incident_history[-limit:] if limit > 0 else self.incident_history
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "incident_history_response",
                    "incidents": [
                        {
                            "id": incident["id"],
                            "component": incident["component"],
                            "type": incident["type"],
                            "severity": incident["severity"],
                            "description": incident["description"],
                            "status": incident["status"],
                            "created_at": incident["created_at"].isoformat(),
                            "resolved_at": incident.get("resolved_at").isoformat() if incident.get("resolved_at") else None
                        }
                        for incident in recent_incidents
                    ],
                    "total_count": len(self.incident_history),
                    "active_count": len(self.active_incidents)
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Incident history handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _handle_force_recovery(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle force recovery action request
        """
        try:
            action_type = message.content.get("action_type")
            target_component = message.content.get("target_component")
            
            if action_type not in self.healing_strategies:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": f"Unknown action type: {action_type}"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Execute recovery action
            mock_issue = {
                "component": target_component,
                "type": "manual_recovery",
                "severity": "high",
                "description": f"Manual recovery action: {action_type}"
            }
            
            success = await self.healing_strategies[action_type](mock_issue)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "force_recovery_response",
                    "action_type": action_type,
                    "target_component": target_component,
                    "success": success
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Force recovery handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _handle_performance_analysis(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle system performance analysis request
        """
        try:
            analysis_period_hours = message.content.get("analysis_period_hours", 24)
            
            # Analyze performance trends
            analysis = await self._analyze_performance_trends(analysis_period_hours)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "performance_analysis_response",
                    "analysis_period_hours": analysis_period_hours,
                    "analysis": analysis
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Performance analysis handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _analyze_performance_trends(self, period_hours: int) -> Dict[str, Any]:
        """
        Analyze system performance trends
        """
        try:
            # Mock performance analysis
            analysis = {
                "cpu_trend": "stable",
                "memory_trend": "increasing",
                "disk_trend": "stable",
                "incident_frequency": "decreasing",
                "recovery_success_rate": 0.85,
                "bottlenecks_identified": [
                    "Database connection pooling",
                    "Cache hit rate optimization"
                ],
                "recommendations": [
                    "Increase database connection pool size",
                    "Implement cache warming strategy"
                ]
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Performance trend analysis failed: {e}")
            return {"error": str(e)}
    
    async def _handle_failure_prediction(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle failure prediction request
        """
        try:
            prediction_window_hours = message.content.get("prediction_window_hours", 24)
            
            # Predict potential failures
            predictions = await self._predict_system_failures(prediction_window_hours)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "failure_prediction_response",
                    "prediction_window_hours": prediction_window_hours,
                    "predictions": predictions
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Failure prediction handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "error",
                    "error": str(e)
                },
                timestamp=datetime.now()
            )
    
    async def _predict_system_failures(self, window_hours: int) -> List[Dict[str, Any]]:
        """
        Predict potential system failures
        """
        try:
            # Mock failure predictions based on current health
            predictions = []
            
            resources = self.system_health["components"].get("system_resources", {})
            
            if resources.get("disk_usage", 0) > 75:
                predictions.append({
                    "component": "system",
                    "failure_type": "disk_full",
                    "probability": 0.3,
                    "predicted_time": (datetime.now() + timedelta(hours=12)).isoformat(),
                    "impact": "high",
                    "preventive_action": "disk_cleanup"
                })
            
            if resources.get("memory_usage", 0) > 80:
                predictions.append({
                    "component": "system",
                    "failure_type": "memory_exhaustion",
                    "probability": 0.4,
                    "predicted_time": (datetime.now() + timedelta(hours=6)).isoformat(),
                    "impact": "medium",
                    "preventive_action": "memory_cleanup"
                })
            
            # Service-specific predictions
            services = self.system_health["components"].get("services", {}).get("services", {})
            for service_name, service_info in services.items():
                if service_info.get("status") == "degraded":
                    predictions.append({
                        "component": service_name,
                        "failure_type": "service_failure",
                        "probability": 0.6,
                        "predicted_time": (datetime.now() + timedelta(hours=2)).isoformat(),
                        "impact": "high",
                        "preventive_action": "service_restart"
                    })
            
            return predictions
            
        except Exception as e:
            logger.error(f"Failure prediction failed: {e}")
            return []


# ========== TEST ==========
if __name__ == "__main__":
    async def test_auto_heal_agent():
        # Initialize auto heal agent
        agent = AutoHealAgent()
        await agent.start()
        
        # Test health check
        test_message = AgentMessage(
            id="test_health",
            from_agent="test",
            to_agent="auto_heal_agent",
            content={
                "type": "check_system_health"
            },
            timestamp=datetime.now()
        )
        
        print("Testing auto heal agent...")
        async for response in agent.process_message(test_message):
            print(f"Response type: {response.content.get('type')}")
            if response.content.get("type") == "health_check_response":
                health = response.content.get("health_status", {})
                print(f"Overall status: {health.get('overall_status')}")
                print(f"Active incidents: {response.content.get('active_incidents', 0)}")
        
        # Test incident history
        history_message = AgentMessage(
            id="test_history",
            from_agent="test",
            to_agent="auto_heal_agent",
            content={
                "type": "get_incident_history",
                "limit": 10
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(history_message):
            print(f"History response: {response.content.get('type')}")
            if response.content.get("type") == "incident_history_response":
                print(f"Total incidents: {response.content.get('total_count', 0)}")
        
        # Stop agent
        await agent.stop()
        print("Auto heal agent test completed")
    
    # Run test
    asyncio.run(test_auto_heal_agent())
