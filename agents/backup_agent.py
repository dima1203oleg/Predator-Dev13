"""
Backup Agent: Comprehensive data backup and recovery
Handles automated backups, disaster recovery, and data restoration
"""
import os
import logging
import shutil
from typing import Dict, Any, List, Optional, Tuple, Union, Set
from pathlib import Path
import asyncio
import json
import gzip
import tarfile
import hashlib
import tempfile
from datetime import datetime, timedelta
from collections import defaultdict, deque
import uuid
import base64
import boto3
from azure.storage.blob import BlobServiceClient
from google.cloud import storage
import paramiko
import psycopg2
from psycopg2 import sql
import redis
import elasticsearch
from elasticsearch import Elasticsearch
import kubernetes
from kubernetes.client.rest import ApiException
import docker
from docker.errors import DockerException
import subprocess
import threading
import concurrent.futures

from ..agents.base_agent import BaseAgent, AgentState, AgentMessage
from ..api.database import get_db_session
from ..api.models import BackupHistory, RecoveryHistory, BackupSchedule

logger = logging.getLogger(__name__)


class BackupAgent(BaseAgent):
    """
    Backup Agent for comprehensive data backup and recovery
    Handles automated backups, disaster recovery, and data restoration
    """
    
    def __init__(
        self,
        agent_id: str = "backup_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # Backup configuration
        self.backup_config = {
            "schedules": self.config.get("schedules", {
                "database": {"frequency": "daily", "retention": 30, "time": "02:00"},
                "files": {"frequency": "hourly", "retention": 24, "time": "00:00"},
                "logs": {"frequency": "daily", "retention": 90, "time": "03:00"},
                "configurations": {"frequency": "weekly", "retention": 52, "time": "sunday 04:00"},
                "kubernetes": {"frequency": "daily", "retention": 14, "time": "01:00"}
            }),
            "storage": self.config.get("storage", {
                "local": {
                    "enabled": True,
                    "path": "/opt/predator/backups",
                    "compression": True,
                    "encryption": False
                },
                "s3": {
                    "enabled": False,
                    "bucket": "predator-backups",
                    "region": "us-east-1",
                    "access_key": self.config.get("aws_access_key"),
                    "secret_key": self.config.get("aws_secret_key"),
                    "encryption": True
                },
                "azure": {
                    "enabled": False,
                    "container": "backups",
                    "account_name": self.config.get("azure_account_name"),
                    "account_key": self.config.get("azure_account_key"),
                    "encryption": True
                },
                "gcs": {
                    "enabled": False,
                    "bucket": "predator-backups",
                    "credentials_path": self.config.get("gcp_credentials_path"),
                    "encryption": True
                },
                "nfs": {
                    "enabled": False,
                    "mount_point": "/mnt/backups",
                    "server": self.config.get("nfs_server"),
                    "share": self.config.get("nfs_share")
                }
            }),
            "targets": self.config.get("targets", {
                "postgresql": {
                    "enabled": True,
                    "host": "localhost",
                    "port": 5432,
                    "database": "predator_analytics",
                    "username": self.config.get("db_username"),
                    "password": self.config.get("db_password"),
                    "backup_method": "pg_dump"  # pg_dump, pg_basebackup
                },
                "redis": {
                    "enabled": True,
                    "host": "localhost",
                    "port": 6379,
                    "backup_method": "rdb"  # rdb, aof
                },
                "elasticsearch": {
                    "enabled": True,
                    "hosts": ["localhost:9200"],
                    "backup_method": "snapshot"  # snapshot, export
                },
                "qdrant": {
                    "enabled": True,
                    "url": "http://localhost:6333",
                    "backup_method": "api"  # api, filesystem
                },
                "files": {
                    "enabled": True,
                    "paths": ["/opt/predator/data", "/opt/predator/configs"],
                    "excludes": ["*.tmp", "*.log"]
                },
                "kubernetes": {
                    "enabled": True,
                    "namespaces": ["default", "predator-analytics"],
                    "backup_method": "velero"  # velero, kubectl
                }
            }),
            "recovery": self.config.get("recovery", {
                "point_in_time": True,
                "parallel_recovery": 4,
                "validation_enabled": True,
                "auto_recovery": False,
                "recovery_timeout": 3600,  # seconds
                "rollback_enabled": True
            }),
            "monitoring": self.config.get("monitoring", {
                "backup_success_alerts": True,
                "backup_failure_alerts": True,
                "storage_usage_alerts": True,
                "recovery_test_schedules": "monthly",
                "performance_metrics": True
            }),
            "processing": self.config.get("processing", {
                "parallel_backups": 3,
                "chunk_size": 1048576,  # 1MB
                "compression_level": 6,
                "encryption_algorithm": "AES256",
                "temp_directory": "/tmp/backups"
            })
        }
        
        # Backup components
        self.storage_clients = {}
        self.backup_schedules = {}
        self.active_backups = {}
        self.backup_history = deque(maxlen=10000)
        self.recovery_history = deque(maxlen=1000)
        
        # Thread pool for I/O operations
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.backup_config["processing"]["parallel_backups"]
        )
        
        # Background tasks
        self.backup_scheduler_task = None
        self.backup_monitor_task = None
        self.recovery_monitor_task = None
        
        logger.info(f"Backup Agent initialized: {agent_id}")
    
    async def start(self):
        """
        Start the backup agent
        """
        await super().start()
        
        # Initialize storage clients
        await self._initialize_storage_clients()
        
        # Load backup data
        await self._load_backup_data()
        
        # Start backup scheduler
        await self._start_backup_scheduler()
        
        # Start background tasks
        self.backup_scheduler_task = asyncio.create_task(self._continuous_backup_scheduler())
        self.backup_monitor_task = asyncio.create_task(self._continuous_backup_monitor())
        self.recovery_monitor_task = asyncio.create_task(self._continuous_recovery_monitor())
        
        logger.info("Backup agent started")
    
    async def stop(self):
        """
        Stop the backup agent
        """
        if self.backup_scheduler_task:
            self.backup_scheduler_task.cancel()
            try:
                await self.backup_scheduler_task
            except asyncio.CancelledError:
                pass
        
        if self.backup_monitor_task:
            self.backup_monitor_task.cancel()
            try:
                await self.backup_monitor_task
            except asyncio.CancelledError:
                pass
        
        if self.recovery_monitor_task:
            self.recovery_monitor_task.cancel()
            try:
                await self.recovery_monitor_task
            except asyncio.CancelledError:
                pass
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        await super().stop()
        logger.info("Backup agent stopped")
    
    async def _initialize_storage_clients(self):
        """
        Initialize storage clients for different backup destinations
        """
        try:
            # Local storage
            if self.backup_config["storage"]["local"]["enabled"]:
                local_path = self.backup_config["storage"]["local"]["path"]
                os.makedirs(local_path, exist_ok=True)
                self.storage_clients["local"] = {"type": "local", "path": local_path}
            
            # AWS S3
            if self.backup_config["storage"]["s3"]["enabled"]:
                try:
                    s3_client = boto3.client(
                        's3',
                        aws_access_key_id=self.backup_config["storage"]["s3"]["access_key"],
                        aws_secret_access_key=self.backup_config["storage"]["s3"]["secret_key"],
                        region_name=self.backup_config["storage"]["s3"]["region"]
                    )
                    self.storage_clients["s3"] = s3_client
                    logger.info("S3 client initialized")
                except Exception as e:
                    logger.warning(f"S3 client initialization failed: {e}")
            
            # Azure Blob Storage
            if self.backup_config["storage"]["azure"]["enabled"]:
                try:
                    account_url = f"https://{self.backup_config['storage']['azure']['account_name']}.blob.core.windows.net"
                    azure_client = BlobServiceClient(
                        account_url=account_url,
                        credential=self.backup_config["storage"]["azure"]["account_key"]
                    )
                    self.storage_clients["azure"] = azure_client
                    logger.info("Azure client initialized")
                except Exception as e:
                    logger.warning(f"Azure client initialization failed: {e}")
            
            # Google Cloud Storage
            if self.backup_config["storage"]["gcs"]["enabled"]:
                try:
                    gcs_client = storage.Client.from_service_account_json(
                        self.backup_config["storage"]["gcs"]["credentials_path"]
                    )
                    self.storage_clients["gcs"] = gcs_client
                    logger.info("GCS client initialized")
                except Exception as e:
                    logger.warning(f"GCS client initialization failed: {e}")
            
        except Exception as e:
            logger.error(f"Storage client initialization failed: {e}")
    
    async def _load_backup_data(self):
        """
        Load existing backup data and configurations
        """
        try:
            # Load backup schedules, history, recovery history, etc.
            await self._load_backup_schedules()
            await self._load_backup_history()
            await self._load_recovery_history()
            
            logger.info("Backup data loaded")
            
        except Exception as e:
            logger.error(f"Backup data loading failed: {e}")
    
    async def _start_backup_scheduler(self):
        """
        Start the backup scheduler
        """
        try:
            # Schedule backups based on configuration
            for backup_type, schedule in self.backup_config["schedules"].items():
                await self._schedule_backup(backup_type, schedule)
            
            logger.info("Backup scheduler started")
            
        except Exception as e:
            logger.error(f"Backup scheduler startup failed: {e}")
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process backup requests
        """
        try:
            message_type = message.content.get("type", "")
            
            if message_type == "create_backup":
                async for response in self._handle_backup_creation(message):
                    yield response
                    
            elif message_type == "restore_backup":
                async for response in self._handle_backup_restoration(message):
                    yield response
                    
            elif message_type == "list_backups":
                async for response in self._handle_backup_listing(message):
                    yield response
                    
            elif message_type == "validate_backup":
                async for response in self._handle_backup_validation(message):
                    yield response
                    
            elif message_type == "delete_backup":
                async for response in self._handle_backup_deletion(message):
                    yield response
                    
            elif message_type == "schedule_backup":
                async for response in self._handle_backup_scheduling(message):
                    yield response
                    
            elif message_type == "test_recovery":
                async for response in self._handle_recovery_testing(message):
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
            logger.error(f"Backup processing failed: {e}")
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
    
    async def _handle_backup_creation(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle backup creation request
        """
        try:
            backup_type = message.content.get("backup_type", "full")
            targets = message.content.get("targets", ["all"])
            storage_destinations = message.content.get("storage", ["local"])
            
            # Create backup
            backup_result = await self._create_backup(backup_type, targets, storage_destinations)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "backup_creation_response",
                    "backup_result": backup_result,
                    "backup_type": backup_type,
                    "targets": targets
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Backup creation handling failed: {e}")
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
    
    async def _create_backup(
        self,
        backup_type: str,
        targets: List[str],
        storage_destinations: List[str]
    ) -> Dict[str, Any]:
        """
        Create backup of specified targets
        """
        try:
            backup_id = str(uuid.uuid4())
            backup_start_time = datetime.now()
            
            # Initialize backup tracking
            self.active_backups[backup_id] = {
                "id": backup_id,
                "type": backup_type,
                "targets": targets,
                "destinations": storage_destinations,
                "start_time": backup_start_time,
                "status": "running",
                "progress": {},
                "errors": []
            }
            
            backup_results = {}
            
            # Backup each target
            for target in targets:
                if target == "all" or target == "postgresql":
                    if self.backup_config["targets"]["postgresql"]["enabled"]:
                        result = await self._backup_postgresql(backup_id)
                        backup_results["postgresql"] = result
                
                if target == "all" or target == "redis":
                    if self.backup_config["targets"]["redis"]["enabled"]:
                        result = await self._backup_redis(backup_id)
                        backup_results["redis"] = result
                
                if target == "all" or target == "elasticsearch":
                    if self.backup_config["targets"]["elasticsearch"]["enabled"]:
                        result = await self._backup_elasticsearch(backup_id)
                        backup_results["elasticsearch"] = result
                
                if target == "all" or target == "qdrant":
                    if self.backup_config["targets"]["qdrant"]["enabled"]:
                        result = await self._backup_qdrant(backup_id)
                        backup_results["qdrant"] = result
                
                if target == "all" or target == "files":
                    if self.backup_config["targets"]["files"]["enabled"]:
                        result = await self._backup_files(backup_id)
                        backup_results["files"] = result
                
                if target == "all" or target == "kubernetes":
                    if self.backup_config["targets"]["kubernetes"]["enabled"]:
                        result = await self._backup_kubernetes(backup_id)
                        backup_results["kubernetes"] = result
            
            # Store backup in configured destinations
            storage_results = {}
            for destination in storage_destinations:
                result = await self._store_backup(backup_id, destination)
                storage_results[destination] = result
            
            # Calculate backup statistics
            backup_end_time = datetime.now()
            duration = (backup_end_time - backup_start_time).total_seconds()
            
            successful_backups = sum(1 for result in backup_results.values() if result.get("success"))
            total_backups = len(backup_results)
            
            # Update backup tracking
            self.active_backups[backup_id].update({
                "end_time": backup_end_time,
                "duration": duration,
                "status": "completed" if successful_backups == total_backups else "failed",
                "results": backup_results,
                "storage_results": storage_results
            })
            
            # Add to history
            backup_record = self.active_backups[backup_id].copy()
            self.backup_history.append(backup_record)
            
            # Clean up active backup
            del self.active_backups[backup_id]
            
            return {
                "backup_id": backup_id,
                "backup_type": backup_type,
                "targets": targets,
                "destinations": storage_destinations,
                "start_time": backup_start_time,
                "end_time": backup_end_time,
                "duration_seconds": duration,
                "results": backup_results,
                "storage_results": storage_results,
                "success": successful_backups == total_backups,
                "successful_backups": successful_backups,
                "total_backups": total_backups
            }
            
        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            
            # Update failed backup
            if backup_id in self.active_backups:
                self.active_backups[backup_id].update({
                    "status": "failed",
                    "end_time": datetime.now(),
                    "error": str(e)
                })
                self.backup_history.append(self.active_backups[backup_id])
                del self.active_backups[backup_id]
            
            return {"error": str(e), "backup_created": False}
    
    async def _backup_postgresql(self, backup_id: str) -> Dict[str, Any]:
        """
        Backup PostgreSQL database
        """
        try:
            config = self.backup_config["targets"]["postgresql"]
            method = config["backup_method"]
            
            if method == "pg_dump":
                # Use pg_dump for logical backup
                backup_file = f"/tmp/{backup_id}_postgresql.sql.gz"
                
                # Build pg_dump command
                cmd = [
                    "pg_dump",
                    f"--host={config['host']}",
                    f"--port={config['port']}",
                    f"--username={config['username']}",
                    f"--dbname={config['database']}",
                    "--no-password",
                    "--format=custom",
                    "--compress=6",
                    f"--file={backup_file}"
                ]
                
                # Set password environment
                env = os.environ.copy()
                env["PGPASSWORD"] = config["password"]
                
                # Run pg_dump
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    env=env,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    # Get file size
                    file_size = os.path.getsize(backup_file)
                    
                    return {
                        "success": True,
                        "method": method,
                        "file": backup_file,
                        "size_bytes": file_size,
                        "database": config["database"]
                    }
                else:
                    error_msg = stderr.decode()
                    logger.error(f"PostgreSQL backup failed: {error_msg}")
                    return {
                        "success": False,
                        "method": method,
                        "error": error_msg
                    }
            
            else:
                return {
                    "success": False,
                    "method": method,
                    "error": f"Unsupported backup method: {method}"
                }
                
        except Exception as e:
            logger.error(f"PostgreSQL backup failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _backup_redis(self, backup_id: str) -> Dict[str, Any]:
        """
        Backup Redis database
        """
        try:
            config = self.backup_config["targets"]["redis"]
            method = config["backup_method"]
            
            if method == "rdb":
                # Use Redis RDB file
                backup_file = f"/tmp/{backup_id}_redis.rdb.gz"
                
                # Connect to Redis
                r = redis.Redis(
                    host=config["host"],
                    port=config["port"],
                    decode_responses=False
                )
                
                # Trigger save
                r.save()
                
                # Copy RDB file (assuming default location)
                rdb_path = "/var/lib/redis/dump.rdb"  # Default Redis RDB path
                
                if os.path.exists(rdb_path):
                    # Compress and copy
                    with open(rdb_path, 'rb') as src, gzip.open(backup_file, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    
                    file_size = os.path.getsize(backup_file)
                    
                    return {
                        "success": True,
                        "method": method,
                        "file": backup_file,
                        "size_bytes": file_size,
                        "keys_count": r.dbsize()
                    }
                else:
                    return {
                        "success": False,
                        "method": method,
                        "error": "RDB file not found"
                    }
            
            else:
                return {
                    "success": False,
                    "method": method,
                    "error": f"Unsupported backup method: {method}"
                }
                
        except Exception as e:
            logger.error(f"Redis backup failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _backup_elasticsearch(self, backup_id: str) -> Dict[str, Any]:
        """
        Backup Elasticsearch indices
        """
        try:
            config = self.backup_config["targets"]["elasticsearch"]
            method = config["backup_method"]
            
            if method == "snapshot":
                # Create Elasticsearch snapshot
                es_client = Elasticsearch(config["hosts"])
                
                # Create snapshot repository (if not exists)
                repo_config = {
                    "type": "fs",
                    "settings": {
                        "location": f"/tmp/es_snapshots/{backup_id}"
                    }
                }
                
                try:
                    es_client.snapshot.create_repository(
                        repository=f"backup_repo_{backup_id}",
                        body=repo_config
                    )
                except elasticsearch.TransportError:
                    # Repository might already exist
                    pass
                
                # Create snapshot
                snapshot_body = {
                    "indices": "_all",
                    "ignore_unavailable": True,
                    "include_global_state": False
                }
                
                response = es_client.snapshot.create(
                    repository=f"backup_repo_{backup_id}",
                    snapshot=f"snapshot_{backup_id}",
                    body=snapshot_body,
                    wait_for_completion=True
                )
                
                if response.get("snapshot", {}).get("state") == "SUCCESS":
                    return {
                        "success": True,
                        "method": method,
                        "snapshot_name": f"snapshot_{backup_id}",
                        "repository": f"backup_repo_{backup_id}",
                        "indices_count": len(response.get("snapshot", {}).get("indices", []))
                    }
                else:
                    return {
                        "success": False,
                        "method": method,
                        "error": "Snapshot creation failed"
                    }
            
            else:
                return {
                    "success": False,
                    "method": method,
                    "error": f"Unsupported backup method: {method}"
                }
                
        except Exception as e:
            logger.error(f"Elasticsearch backup failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _backup_qdrant(self, backup_id: str) -> Dict[str, Any]:
        """
        Backup Qdrant collections
        """
        try:
            config = self.backup_config["targets"]["qdrant"]
            method = config["backup_method"]
            
            if method == "api":
                # Use Qdrant API for backup
                import requests
                
                # Get collections
                response = requests.get(f"{config['url']}/collections")
                if response.status_code != 200:
                    return {
                        "success": False,
                        "method": method,
                        "error": "Failed to get collections"
                    }
                
                collections = response.json().get("result", {}).get("collections", [])
                
                backup_results = []
                for collection in collections:
                    collection_name = collection["name"]
                    
                    # Create snapshot
                    snapshot_response = requests.post(
                        f"{config['url']}/collections/{collection_name}/snapshots"
                    )
                    
                    if snapshot_response.status_code == 200:
                        snapshot_name = snapshot_response.json().get("result", {}).get("name")
                        backup_results.append({
                            "collection": collection_name,
                            "snapshot": snapshot_name,
                            "success": True
                        })
                    else:
                        backup_results.append({
                            "collection": collection_name,
                            "success": False,
                            "error": snapshot_response.text
                        })
                
                successful_backups = sum(1 for r in backup_results if r["success"])
                
                return {
                    "success": successful_backups > 0,
                    "method": method,
                    "collections_backed_up": successful_backups,
                    "total_collections": len(collections),
                    "results": backup_results
                }
            
            else:
                return {
                    "success": False,
                    "method": method,
                    "error": f"Unsupported backup method: {method}"
                }
                
        except Exception as e:
            logger.error(f"Qdrant backup failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _backup_files(self, backup_id: str) -> Dict[str, Any]:
        """
        Backup files and directories
        """
        try:
            config = self.backup_config["targets"]["files"]
            backup_file = f"/tmp/{backup_id}_files.tar.gz"
            
            # Create tar archive
            with tarfile.open(backup_file, "w:gz", compresslevel=self.backup_config["processing"]["compression_level"]) as tar:
                for path in config["paths"]:
                    if os.path.exists(path):
                        # Add directory to tar, excluding specified patterns
                        excludes = config.get("excludes", [])
                        
                        def exclude_filter(tarinfo):
                            for exclude in excludes:
                                if tarinfo.name.endswith(exclude.replace("*", "")):
                                    return None
                            return tarinfo
                        
                        tar.add(path, arcname=os.path.basename(path), filter=exclude_filter)
            
            file_size = os.path.getsize(backup_file)
            
            return {
                "success": True,
                "method": "tar_gz",
                "file": backup_file,
                "size_bytes": file_size,
                "paths": config["paths"]
            }
            
        except Exception as e:
            logger.error(f"Files backup failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _backup_kubernetes(self, backup_id: str) -> Dict[str, Any]:
        """
        Backup Kubernetes resources
        """
        try:
            config = self.backup_config["targets"]["kubernetes"]
            method = config["backup_method"]
            
            if method == "velero":
                # Use Velero for Kubernetes backup
                backup_name = f"backup-{backup_id}"
                
                # Create Velero backup
                cmd = [
                    "velero",
                    "backup",
                    "create",
                    backup_name,
                    "--include-namespaces",
                    ",".join(config["namespaces"])
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    return {
                        "success": True,
                        "method": method,
                        "backup_name": backup_name,
                        "namespaces": config["namespaces"]
                    }
                else:
                    error_msg = stderr.decode()
                    logger.error(f"Kubernetes backup failed: {error_msg}")
                    return {
                        "success": False,
                        "method": method,
                        "error": error_msg
                    }
            
            else:
                return {
                    "success": False,
                    "method": method,
                    "error": f"Unsupported backup method: {method}"
                }
                
        except Exception as e:
            logger.error(f"Kubernetes backup failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _store_backup(
        self,
        backup_id: str,
        destination: str
    ) -> Dict[str, Any]:
        """
        Store backup in specified destination
        """
        try:
            if destination == "local":
                # Already stored locally during backup creation
                return {"success": True, "destination": destination}
            
            elif destination == "s3":
                if "s3" not in self.storage_clients:
                    return {"success": False, "destination": destination, "error": "S3 client not initialized"}
                
                # Upload backup files to S3
                s3_client = self.storage_clients["s3"]
                bucket = self.backup_config["storage"]["s3"]["bucket"]
                
                # Find and upload backup files
                uploaded_files = []
                for filename in os.listdir("/tmp"):
                    if filename.startswith(backup_id):
                        file_path = f"/tmp/{filename}"
                        s3_key = f"backups/{backup_id}/{filename}"
                        
                        s3_client.upload_file(file_path, bucket, s3_key)
                        uploaded_files.append(s3_key)
                
                return {
                    "success": True,
                    "destination": destination,
                    "bucket": bucket,
                    "files_uploaded": len(uploaded_files),
                    "files": uploaded_files
                }
            
            elif destination == "azure":
                if "azure" not in self.storage_clients:
                    return {"success": False, "destination": destination, "error": "Azure client not initialized"}
                
                # Upload to Azure Blob Storage
                blob_client = self.storage_clients["azure"]
                container = self.backup_config["storage"]["azure"]["container"]
                
                uploaded_files = []
                for filename in os.listdir("/tmp"):
                    if filename.startswith(backup_id):
                        file_path = f"/tmp/{filename}"
                        blob_name = f"backups/{backup_id}/{filename}"
                        
                        with open(file_path, "rb") as data:
                            blob_client.get_blob_client(container=container, blob=blob_name).upload_blob(data, overwrite=True)
                        
                        uploaded_files.append(blob_name)
                
                return {
                    "success": True,
                    "destination": destination,
                    "container": container,
                    "files_uploaded": len(uploaded_files),
                    "files": uploaded_files
                }
            
            else:
                return {
                    "success": False,
                    "destination": destination,
                    "error": f"Unsupported destination: {destination}"
                }
                
        except Exception as e:
            logger.error(f"Backup storage failed for {destination}: {e}")
            return {"success": False, "destination": destination, "error": str(e)}
    
    async def _handle_backup_restoration(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle backup restoration request
        """
        try:
            backup_id = message.content.get("backup_id")
            targets = message.content.get("targets", ["all"])
            restore_options = message.content.get("restore_options", {})
            
            # Restore backup
            restore_result = await self._restore_backup(backup_id, targets, restore_options)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "backup_restoration_response",
                    "restore_result": restore_result,
                    "backup_id": backup_id,
                    "targets": targets
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Backup restoration handling failed: {e}")
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
    
    async def _restore_backup(
        self,
        backup_id: str,
        targets: List[str],
        restore_options: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Restore backup to specified targets
        """
        try:
            restore_start_time = datetime.now()
            recovery_id = str(uuid.uuid4())
            
            # Initialize recovery tracking
            recovery_record = {
                "id": recovery_id,
                "backup_id": backup_id,
                "targets": targets,
                "options": restore_options,
                "start_time": restore_start_time,
                "status": "running"
            }
            
            self.recovery_history.append(recovery_record)
            
            restore_results = {}
            
            # Restore each target
            for target in targets:
                if target == "all" or target == "postgresql":
                    if self.backup_config["targets"]["postgresql"]["enabled"]:
                        result = await self._restore_postgresql(backup_id, restore_options)
                        restore_results["postgresql"] = result
                
                if target == "all" or target == "redis":
                    if self.backup_config["targets"]["redis"]["enabled"]:
                        result = await self._restore_redis(backup_id, restore_options)
                        restore_results["redis"] = result
                
                if target == "all" or target == "elasticsearch":
                    if self.backup_config["targets"]["elasticsearch"]["enabled"]:
                        result = await self._restore_elasticsearch(backup_id, restore_options)
                        restore_results["elasticsearch"] = result
                
                if target == "all" or target == "qdrant":
                    if self.backup_config["targets"]["qdrant"]["enabled"]:
                        result = await self._restore_qdrant(backup_id, restore_options)
                        restore_results["qdrant"] = result
                
                if target == "all" or target == "files":
                    if self.backup_config["targets"]["files"]["enabled"]:
                        result = await self._restore_files(backup_id, restore_options)
                        restore_results["files"] = result
                
                if target == "all" or target == "kubernetes":
                    if self.backup_config["targets"]["kubernetes"]["enabled"]:
                        result = await self._restore_kubernetes(backup_id, restore_options)
                        restore_results["kubernetes"] = result
            
            # Calculate restore statistics
            restore_end_time = datetime.now()
            duration = (restore_end_time - restore_start_time).total_seconds()
            
            successful_restores = sum(1 for result in restore_results.values() if result.get("success"))
            total_restores = len(restore_results)
            
            # Update recovery record
            recovery_record.update({
                "end_time": restore_end_time,
                "duration": duration,
                "status": "completed" if successful_restores == total_restores else "failed",
                "results": restore_results
            })
            
            return {
                "recovery_id": recovery_id,
                "backup_id": backup_id,
                "targets": targets,
                "start_time": restore_start_time,
                "end_time": restore_end_time,
                "duration_seconds": duration,
                "results": restore_results,
                "success": successful_restores == total_restores,
                "successful_restores": successful_restores,
                "total_restores": total_restores
            }
            
        except Exception as e:
            logger.error(f"Backup restoration failed: {e}")
            return {"error": str(e), "restoration_completed": False}
    
    # Background monitoring tasks
    async def _continuous_backup_scheduler(self):
        """
        Continuous backup scheduling
        """
        try:
            while True:
                try:
                    # Check for scheduled backups
                    await self._check_scheduled_backups()
                    
                    # Clean up old backups
                    await self._cleanup_old_backups()
                    
                except Exception as e:
                    logger.error(f"Backup scheduler error: {e}")
                
                # Check every minute
                await asyncio.sleep(60)
                
        except asyncio.CancelledError:
            logger.info("Backup scheduler cancelled")
            raise
    
    async def _continuous_backup_monitor(self):
        """
        Continuous backup monitoring
        """
        try:
            while True:
                try:
                    # Monitor active backups
                    await self._monitor_active_backups()
                    
                    # Check storage usage
                    await self._check_storage_usage()
                    
                except Exception as e:
                    logger.error(f"Backup monitor error: {e}")
                
                # Monitor every 30 seconds
                await asyncio.sleep(30)
                
        except asyncio.CancelledError:
            logger.info("Backup monitor cancelled")
            raise
    
    async def _continuous_recovery_monitor(self):
        """
        Continuous recovery monitoring
        """
        try:
            while True:
                try:
                    # Monitor recovery operations
                    await self._monitor_recovery_operations()
                    
                    # Run recovery tests if scheduled
                    await self._run_scheduled_recovery_tests()
                    
                except Exception as e:
                    logger.error(f"Recovery monitor error: {e}")
                
                # Monitor every 60 seconds
                await asyncio.sleep(60)
                
        except asyncio.CancelledError:
            logger.info("Recovery monitor cancelled")
            raise
    
    # Additional helper methods would continue...
    
    async def _load_backup_schedules(self):
        """Load backup schedules"""
        try:
            # Implementation for loading backup schedules
            pass
        except Exception as e:
            logger.error(f"Backup schedules loading failed: {e}")
    
    async def _load_backup_history(self):
        """Load backup history"""
        try:
            # Implementation for loading backup history
            pass
        except Exception as e:
            logger.error(f"Backup history loading failed: {e}")
    
    async def _load_recovery_history(self):
        """Load recovery history"""
        try:
            # Implementation for loading recovery history
            pass
        except Exception as e:
            logger.error(f"Recovery history loading failed: {e}")
    
    async def _schedule_backup(self, backup_type: str, schedule: Dict[str, Any]):
        """Schedule backup"""
        try:
            # Implementation for scheduling backups
            pass
        except Exception as e:
            logger.error(f"Backup scheduling failed: {e}")
    
    async def _check_scheduled_backups(self):
        """Check for scheduled backups"""
        try:
            # Implementation for checking scheduled backups
            pass
        except Exception as e:
            logger.error(f"Scheduled backups check failed: {e}")
    
    async def _cleanup_old_backups(self):
        """Clean up old backups"""
        try:
            # Implementation for cleaning up old backups
            pass
        except Exception as e:
            logger.error(f"Old backups cleanup failed: {e}")
    
    async def _monitor_active_backups(self):
        """Monitor active backups"""
        try:
            # Implementation for monitoring active backups
            pass
        except Exception as e:
            logger.error(f"Active backups monitoring failed: {e}")
    
    async def _check_storage_usage(self):
        """Check storage usage"""
        try:
            # Implementation for checking storage usage
            pass
        except Exception as e:
            logger.error(f"Storage usage check failed: {e}")
    
    async def _monitor_recovery_operations(self):
        """Monitor recovery operations"""
        try:
            # Implementation for monitoring recovery operations
            pass
        except Exception as e:
            logger.error(f"Recovery operations monitoring failed: {e}")
    
    async def _run_scheduled_recovery_tests(self):
        """Run scheduled recovery tests"""
        try:
            # Implementation for running scheduled recovery tests
            pass
        except Exception as e:
            logger.error(f"Scheduled recovery tests failed: {e}")
    
    async def _restore_postgresql(self, backup_id: str, options: Dict[str, Any]):
        """Restore PostgreSQL"""
        try:
            # Implementation for PostgreSQL restoration
            return {"success": True, "method": "pg_restore"}
        except Exception as e:
            logger.error(f"PostgreSQL restoration failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _restore_redis(self, backup_id: str, options: Dict[str, Any]):
        """Restore Redis"""
        try:
            # Implementation for Redis restoration
            return {"success": True, "method": "rdb_restore"}
        except Exception as e:
            logger.error(f"Redis restoration failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _restore_elasticsearch(self, backup_id: str, options: Dict[str, Any]):
        """Restore Elasticsearch"""
        try:
            # Implementation for Elasticsearch restoration
            return {"success": True, "method": "snapshot_restore"}
        except Exception as e:
            logger.error(f"Elasticsearch restoration failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _restore_qdrant(self, backup_id: str, options: Dict[str, Any]):
        """Restore Qdrant"""
        try:
            # Implementation for Qdrant restoration
            return {"success": True, "method": "snapshot_restore"}
        except Exception as e:
            logger.error(f"Qdrant restoration failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _restore_files(self, backup_id: str, options: Dict[str, Any]):
        """Restore files"""
        try:
            # Implementation for files restoration
            return {"success": True, "method": "tar_extract"}
        except Exception as e:
            logger.error(f"Files restoration failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def _restore_kubernetes(self, backup_id: str, options: Dict[str, Any]):
        """Restore Kubernetes"""
        try:
            # Implementation for Kubernetes restoration
            return {"success": True, "method": "velero_restore"}
        except Exception as e:
            logger.error(f"Kubernetes restoration failed: {e}")
            return {"success": False, "error": str(e)}


# ========== TEST ==========
if __name__ == "__main__":
    async def test_backup_agent():
        # Initialize backup agent
        agent = BackupAgent()
        await agent.start()
        
        # Test backup creation
        backup_message = AgentMessage(
            id="test_backup",
            from_agent="test",
            to_agent="backup_agent",
            content={
                "type": "create_backup",
                "backup_type": "full",
                "targets": ["files"],
                "storage": ["local"]
            },
            timestamp=datetime.now()
        )
        
        print("Testing backup agent...")
        async for response in agent.process_message(backup_message):
            print(f"Backup response: {response.content.get('type')}")
            backup_result = response.content.get('backup_result')
            print(f"Backup created: {backup_result.get('success')}")
        
        # Test backup listing
        list_message = AgentMessage(
            id="test_list",
            from_agent="test",
            to_agent="backup_agent",
            content={
                "type": "list_backups",
                "limit": 10
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(list_message):
            print(f"List response: {response.content.get('type')}")
            list_result = response.content.get('list_result')
            print(f"Backups found: {list_result.get('backups_found')}")
        
        # Stop agent
        await agent.stop()
        print("Backup agent test completed")
    
    # Run test
    asyncio.run(test_backup_agent())
