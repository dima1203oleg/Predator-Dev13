"""
Collaboration Agent: Team collaboration and communication management
Handles team workflows, communication channels, project coordination, and collaboration tools
"""
import os
import logging
import asyncio
import json
import yaml
from typing import Dict, Any, List, Optional, Tuple, Union, Set
from pathlib import Path
import re
import hashlib
from datetime import datetime, timedelta
from collections import defaultdict, deque
import uuid
import base64
import subprocess
import sys

from ..agents.base_agent import BaseAgent, AgentState, AgentMessage
from ..api.database import get_db_session
from ..api.models import Team, Project, Task, Communication

logger = logging.getLogger(__name__)


class CollaborationAgent(BaseAgent):
    """
    Collaboration Agent for team collaboration and communication management
    Handles team workflows, communication channels, project coordination, and collaboration tools
    """
    
    def __init__(
        self,
        agent_id: str = "collaboration_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # Collaboration configuration
        self.collaboration_config = {
            "communication_channels": self.config.get("communication_channels", {
                "chat": True,
                "video_call": True,
                "email": True,
                "project_boards": True,
                "document_sharing": True,
                "screen_sharing": True,
                "whiteboard": True
            }),
            "team_management": self.config.get("team_management", {
                "team_creation": True,
                "role_assignment": True,
                "permission_management": True,
                "team_analytics": True,
                "performance_tracking": True,
                "conflict_resolution": True
            }),
            "project_coordination": self.config.get("project_coordination", {
                "project_planning": True,
                "task_assignment": True,
                "progress_tracking": True,
                "deadline_management": True,
                "resource_allocation": True,
                "milestone_tracking": True
            }),
            "workflow_automation": self.config.get("workflow_automation", {
                "automated_assignments": True,
                "notification_system": True,
                "approval_workflows": True,
                "escalation_rules": True,
                "reminder_system": True,
                "status_updates": True
            }),
            "collaboration_tools": self.config.get("collaboration_tools", {
                "real_time_editing": True,
                "version_control": True,
                "comment_system": True,
                "review_process": True,
                "integration_apis": True,
                "mobile_access": True
            }),
            "analytics_reporting": self.config.get("analytics_reporting", {
                "team_productivity": True,
                "project_metrics": True,
                "communication_analytics": True,
                "collaboration_insights": True,
                "performance_reports": True
            }),
            "integration": self.config.get("integration", {
                "slack_integration": True,
                "microsoft_teams": True,
                "zoom_integration": True,
                "google_workspace": True,
                "jira_integration": True,
                "github_integration": True
            }),
            "processing": self.config.get("processing", {
                "parallel_communication_processing": 4,
                "real_time_update_interval": 5,
                "max_concurrent_sessions": 1000,
                "cache_ttl_seconds": 300
            })
        }
        
        # Collaboration management
        self.teams = {}
        self.projects = {}
        self.tasks = {}
        self.communications = deque(maxlen=100000)
        self.collaboration_analytics = {}
        
        # Background tasks
        self.communication_processor_task = None
        self.workflow_monitor_task = None
        self.analytics_updater_task = None
        
        logger.info(f"Collaboration Agent initialized: {agent_id}")
    
    async def start(self):
        """
        Start the collaboration agent
        """
        await super().start()
        
        # Load collaboration data
        await self._load_collaboration_data()
        
        # Start background tasks
        self.communication_processor_task = asyncio.create_task(self._continuous_communication_processor())
        self.workflow_monitor_task = asyncio.create_task(self._continuous_workflow_monitor())
        self.analytics_updater_task = asyncio.create_task(self._continuous_analytics_updater())
        
        logger.info("Collaboration agent started")
    
    async def stop(self):
        """
        Stop the collaboration agent
        """
        if self.communication_processor_task:
            self.communication_processor_task.cancel()
            try:
                await self.communication_processor_task
            except asyncio.CancelledError:
                pass
        
        if self.workflow_monitor_task:
            self.workflow_monitor_task.cancel()
            try:
                await self.workflow_monitor_task
            except asyncio.CancelledError:
                pass
        
        if self.analytics_updater_task:
            self.analytics_updater_task.cancel()
            try:
                await self.analytics_updater_task
            except asyncio.CancelledError:
                pass
        
        await super().stop()
        logger.info("Collaboration agent stopped")
    
    async def _load_collaboration_data(self):
        """
        Load existing collaboration data and configurations
        """
        try:
            # Load teams, projects, tasks, communications, analytics, etc.
            await self._load_teams()
            await self._load_projects()
            await self._load_tasks()
            await self._load_collaboration_analytics()
            
            logger.info("Collaboration data loaded")
            
        except Exception as e:
            logger.error(f"Collaboration data loading failed: {e}")
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process collaboration requests
        """
        try:
            message_type = message.content.get("type", "")
            
            if message_type == "create_team":
                async for response in self._handle_team_creation(message):
                    yield response
                    
            elif message_type == "manage_project":
                async for response in self._handle_project_management(message):
                    yield response
                    
            elif message_type == "assign_task":
                async for response in self._handle_task_assignment(message):
                    yield response
                    
            elif message_type == "send_message":
                async for response in self._handle_message_sending(message):
                    yield response
                    
            elif message_type == "schedule_meeting":
                async for response in self._handle_meeting_scheduling(message):
                    yield response
                    
            elif message_type == "track_progress":
                async for response in self._handle_progress_tracking(message):
                    yield response
                    
            elif message_type == "generate_report":
                async for response in self._handle_report_generation(message):
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
            logger.error(f"Collaboration processing failed: {e}")
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
    
    async def _handle_team_creation(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle team creation
        """
        try:
            team_name = message.content.get("team_name")
            team_members = message.content.get("team_members", [])
            team_lead = message.content.get("team_lead")
            team_description = message.content.get("team_description", "")
            
            # Create team
            team_result = await self._create_team(team_name, team_members, team_lead, team_description)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "team_created",
                    "team_result": team_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Team creation handling failed: {e}")
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
    
    async def _create_team(
        self,
        team_name: str,
        team_members: List[str],
        team_lead: str,
        team_description: str
    ) -> Dict[str, Any]:
        """
        Create a new team
        """
        try:
            team_id = str(uuid.uuid4())
            
            team = {
                "team_id": team_id,
                "name": team_name,
                "members": team_members,
                "lead": team_lead,
                "description": team_description,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "status": "active",
                "projects": [],
                "communication_channels": {
                    "chat": f"team_{team_id}_chat",
                    "email": f"team_{team_id}@company.com",
                    "project_board": f"team_{team_id}_board"
                },
                "performance_metrics": {
                    "productivity_score": 0.0,
                    "communication_score": 0.0,
                    "collaboration_score": 0.0
                }
            }
            
            self.teams[team_id] = team
            
            # Notify team members
            await self._notify_team_members(team_id, "team_created", {
                "team_name": team_name,
                "team_lead": team_lead
            })
            
            return {
                "team_id": team_id,
                "name": team_name,
                "members_count": len(team_members),
                "lead": team_lead,
                "communication_channels": team["communication_channels"],
                "created_at": team["created_at"]
            }
            
        except Exception as e:
            logger.error(f"Team creation failed: {e}")
            return {"error": str(e)}
    
    async def _handle_project_management(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle project management
        """
        try:
            action = message.content.get("action")
            project_data = message.content.get("project_data", {})
            
            if action == "create":
                project_result = await self._create_project(project_data)
            elif action == "update":
                project_result = await self._update_project(project_data)
            elif action == "delete":
                project_result = await self._delete_project(project_data.get("project_id"))
            else:
                project_result = {"error": f"Unknown action: {action}"}
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "project_managed",
                    "action": action,
                    "project_result": project_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Project management handling failed: {e}")
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
    
    async def _create_project(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new project
        """
        try:
            project_id = str(uuid.uuid4())
            
            project = {
                "project_id": project_id,
                "name": project_data.get("name"),
                "description": project_data.get("description", ""),
                "team_id": project_data.get("team_id"),
                "owner": project_data.get("owner"),
                "start_date": project_data.get("start_date"),
                "end_date": project_data.get("end_date"),
                "status": "planning",
                "priority": project_data.get("priority", "medium"),
                "budget": project_data.get("budget"),
                "milestones": project_data.get("milestones", []),
                "tasks": [],
                "progress": 0.0,
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "communication_channel": f"project_{project_id}_chat"
            }
            
            self.projects[project_id] = project
            
            # Add to team
            if project["team_id"] and project["team_id"] in self.teams:
                self.teams[project["team_id"]]["projects"].append(project_id)
            
            # Notify team
            await self._notify_team_members(project["team_id"], "project_created", {
                "project_name": project["name"],
                "project_owner": project["owner"]
            })
            
            return {
                "project_id": project_id,
                "name": project["name"],
                "status": project["status"],
                "progress": project["progress"],
                "created_at": project["created_at"]
            }
            
        except Exception as e:
            logger.error(f"Project creation failed: {e}")
            return {"error": str(e)}
    
    async def _handle_task_assignment(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle task assignment
        """
        try:
            task_data = message.content.get("task_data", {})
            
            # Assign task
            task_result = await self._assign_task(task_data)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "task_assigned",
                    "task_result": task_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Task assignment handling failed: {e}")
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
    
    async def _assign_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assign a task to team member
        """
        try:
            task_id = str(uuid.uuid4())
            
            task = {
                "task_id": task_id,
                "title": task_data.get("title"),
                "description": task_data.get("description", ""),
                "project_id": task_data.get("project_id"),
                "assigned_to": task_data.get("assigned_to"),
                "assigned_by": task_data.get("assigned_by"),
                "priority": task_data.get("priority", "medium"),
                "status": "assigned",
                "due_date": task_data.get("due_date"),
                "estimated_hours": task_data.get("estimated_hours"),
                "actual_hours": 0,
                "dependencies": task_data.get("dependencies", []),
                "tags": task_data.get("tags", []),
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "completed_at": None
            }
            
            self.tasks[task_id] = task
            
            # Add to project
            if task["project_id"] and task["project_id"] in self.projects:
                self.projects[task["project_id"]]["tasks"].append(task_id)
            
            # Notify assignee
            await self._notify_user(task["assigned_to"], "task_assigned", {
                "task_title": task["title"],
                "project_name": self.projects.get(task["project_id"], {}).get("name", "Unknown"),
                "due_date": task["due_date"]
            })
            
            return {
                "task_id": task_id,
                "title": task["title"],
                "assigned_to": task["assigned_to"],
                "status": task["status"],
                "due_date": task["due_date"],
                "created_at": task["created_at"]
            }
            
        except Exception as e:
            logger.error(f"Task assignment failed: {e}")
            return {"error": str(e)}
    
    async def _handle_message_sending(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle message sending
        """
        try:
            message_data = message.content.get("message_data", {})
            
            # Send message
            message_result = await self._send_message(message_data)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "message_sent",
                    "message_result": message_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Message sending handling failed: {e}")
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
    
    async def _send_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a message to team/channel
        """
        try:
            message_id = str(uuid.uuid4())
            
            message = {
                "message_id": message_id,
                "sender": message_data.get("sender"),
                "recipient": message_data.get("recipient"),  # user_id, team_id, or channel
                "channel": message_data.get("channel", "chat"),
                "content": message_data.get("content"),
                "message_type": message_data.get("message_type", "text"),
                "attachments": message_data.get("attachments", []),
                "timestamp": datetime.now(),
                "read_by": [],
                "reactions": []
            }
            
            # Store message
            self.communications.append(message)
            
            # Process based on channel
            if message["channel"] == "team":
                await self._broadcast_to_team(message["recipient"], message)
            elif message["channel"] == "project":
                await self._broadcast_to_project(message["recipient"], message)
            else:
                await self._send_direct_message(message["recipient"], message)
            
            return {
                "message_id": message_id,
                "recipient": message["recipient"],
                "channel": message["channel"],
                "timestamp": message["timestamp"],
                "delivered": True
            }
            
        except Exception as e:
            logger.error(f"Message sending failed: {e}")
            return {"error": str(e)}
    
    async def _handle_meeting_scheduling(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle meeting scheduling
        """
        try:
            meeting_data = message.content.get("meeting_data", {})
            
            # Schedule meeting
            meeting_result = await self._schedule_meeting(meeting_data)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "meeting_scheduled",
                    "meeting_result": meeting_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Meeting scheduling handling failed: {e}")
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
    
    async def _schedule_meeting(self, meeting_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Schedule a meeting
        """
        try:
            meeting_id = str(uuid.uuid4())
            
            meeting = {
                "meeting_id": meeting_id,
                "title": meeting_data.get("title"),
                "description": meeting_data.get("description", ""),
                "organizer": meeting_data.get("organizer"),
                "participants": meeting_data.get("participants", []),
                "start_time": meeting_data.get("start_time"),
                "end_time": meeting_data.get("end_time"),
                "location": meeting_data.get("location", "virtual"),
                "meeting_link": meeting_data.get("meeting_link"),
                "agenda": meeting_data.get("agenda", []),
                "status": "scheduled",
                "created_at": datetime.now()
            }
            
            # Find optimal time if not specified
            if not meeting["start_time"]:
                meeting["start_time"] = await self._find_optimal_meeting_time(
                    meeting["participants"]
                )
                meeting["end_time"] = meeting["start_time"] + timedelta(hours=1)
            
            # Generate meeting link if virtual
            if meeting["location"] == "virtual" and not meeting["meeting_link"]:
                meeting["meeting_link"] = await self._generate_meeting_link(meeting)
            
            # Send invitations
            await self._send_meeting_invitations(meeting)
            
            return {
                "meeting_id": meeting_id,
                "title": meeting["title"],
                "start_time": meeting["start_time"],
                "end_time": meeting["end_time"],
                "location": meeting["location"],
                "meeting_link": meeting["meeting_link"],
                "participants_count": len(meeting["participants"])
            }
            
        except Exception as e:
            logger.error(f"Meeting scheduling failed: {e}")
            return {"error": str(e)}
    
    async def _handle_progress_tracking(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle progress tracking
        """
        try:
            tracking_data = message.content.get("tracking_data", {})
            
            # Track progress
            progress_result = await self._track_progress(tracking_data)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "progress_tracked",
                    "progress_result": progress_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Progress tracking handling failed: {e}")
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
    
    async def _track_progress(self, tracking_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Track progress for tasks/projects
        """
        try:
            entity_type = tracking_data.get("entity_type")  # "task" or "project"
            entity_id = tracking_data.get("entity_id")
            progress_update = tracking_data.get("progress_update", {})
            
            if entity_type == "task":
                result = await self._update_task_progress(entity_id, progress_update)
            elif entity_type == "project":
                result = await self._update_project_progress(entity_id, progress_update)
            else:
                result = {"error": f"Unknown entity type: {entity_type}"}
            
            return result
            
        except Exception as e:
            logger.error(f"Progress tracking failed: {e}")
            return {"error": str(e)}
    
    async def _update_task_progress(
        self,
        task_id: str,
        progress_update: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update task progress
        """
        try:
            if task_id not in self.tasks:
                return {"error": "Task not found"}
            
            task = self.tasks[task_id]
            
            # Update progress fields
            if "status" in progress_update:
                task["status"] = progress_update["status"]
                if progress_update["status"] == "completed":
                    task["completed_at"] = datetime.now()
            
            if "actual_hours" in progress_update:
                task["actual_hours"] = progress_update["actual_hours"]
            
            if "notes" in progress_update:
                task["notes"] = progress_update.get("notes", [])
            
            task["updated_at"] = datetime.now()
            
            # Notify relevant parties
            if task["status"] == "completed":
                await self._notify_task_completion(task)
            
            return {
                "task_id": task_id,
                "status": task["status"],
                "updated_at": task["updated_at"],
                "completed": task["status"] == "completed"
            }
            
        except Exception as e:
            logger.error(f"Task progress update failed: {e}")
            return {"error": str(e)}
    
    async def _update_project_progress(
        self,
        project_id: str,
        progress_update: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update project progress
        """
        try:
            if project_id not in self.projects:
                return {"error": "Project not found"}
            
            project = self.projects[project_id]
            
            # Calculate overall progress from tasks
            if project["tasks"]:
                completed_tasks = sum(
                    1 for task_id in project["tasks"]
                    if self.tasks.get(task_id, {}).get("status") == "completed"
                )
                project["progress"] = (completed_tasks / len(project["tasks"])) * 100
            
            # Update project status
            if project["progress"] >= 100:
                project["status"] = "completed"
            elif project["progress"] > 0:
                project["status"] = "in_progress"
            
            project["updated_at"] = datetime.now()
            
            return {
                "project_id": project_id,
                "progress": project["progress"],
                "status": project["status"],
                "updated_at": project["updated_at"]
            }
            
        except Exception as e:
            logger.error(f"Project progress update failed: {e}")
            return {"error": str(e)}
    
    async def _handle_report_generation(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle report generation
        """
        try:
            report_data = message.content.get("report_data", {})
            
            # Generate report
            report_result = await self._generate_report(report_data)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "report_generated",
                    "report_result": report_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Report generation handling failed: {e}")
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
    
    async def _generate_report(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate collaboration report
        """
        try:
            report_type = report_data.get("report_type", "team_productivity")
            entity_id = report_data.get("entity_id")
            date_range = report_data.get("date_range", {})
            
            if report_type == "team_productivity":
                report = await self._generate_team_productivity_report(entity_id, date_range)
            elif report_type == "project_status":
                report = await self._generate_project_status_report(entity_id, date_range)
            elif report_type == "communication_analytics":
                report = await self._generate_communication_analytics_report(entity_id, date_range)
            else:
                report = {"error": f"Unknown report type: {report_type}"}
            
            return report
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            return {"error": str(e)}
    
    # Background monitoring tasks
    async def _continuous_communication_processor(self):
        """
        Continuous communication processing
        """
        try:
            while True:
                try:
                    # Process queued communications
                    await self._process_queued_communications()
                    
                    # Update communication analytics
                    await self._update_communication_analytics()
                    
                except Exception as e:
                    logger.error(f"Communication processor error: {e}")
                
                # Process every 5 seconds
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            logger.info("Communication processor cancelled")
            raise
    
    async def _continuous_workflow_monitor(self):
        """
        Continuous workflow monitoring
        """
        try:
            while True:
                try:
                    # Monitor task deadlines
                    await self._monitor_task_deadlines()
                    
                    # Auto-assign tasks
                    await self._auto_assign_tasks()
                    
                    # Send reminders
                    await self._send_reminders()
                    
                except Exception as e:
                    logger.error(f"Workflow monitor error: {e}")
                
                # Monitor every minute
                await asyncio.sleep(60)
                
        except asyncio.CancelledError:
            logger.info("Workflow monitor cancelled")
            raise
    
    async def _continuous_analytics_updater(self):
        """
        Continuous analytics updates
        """
        try:
            while True:
                try:
                    # Update team analytics
                    await self._update_team_analytics()
                    
                    # Update project analytics
                    await self._update_project_analytics()
                    
                except Exception as e:
                    logger.error(f"Analytics updater error: {e}")
                
                # Update every 15 minutes
                await asyncio.sleep(900)
                
        except asyncio.CancelledError:
            logger.info("Analytics updater cancelled")
            raise
    
    # Additional helper methods would continue...
    
    async def _notify_team_members(self, team_id: str, event_type: str, event_data: Dict[str, Any]):
        """Notify team members"""
        try:
            # Implementation for notifying team members
            pass
        except Exception as e:
            logger.error(f"Team notification failed: {e}")
    
    async def _notify_user(self, user_id: str, event_type: str, event_data: Dict[str, Any]):
        """Notify user"""
        try:
            # Implementation for notifying user
            pass
        except Exception as e:
            logger.error(f"User notification failed: {e}")
    
    async def _broadcast_to_team(self, team_id: str, message: Dict[str, Any]):
        """Broadcast message to team"""
        try:
            # Implementation for broadcasting to team
            pass
        except Exception as e:
            logger.error(f"Team broadcast failed: {e}")
    
    async def _broadcast_to_project(self, project_id: str, message: Dict[str, Any]):
        """Broadcast message to project"""
        try:
            # Implementation for broadcasting to project
            pass
        except Exception as e:
            logger.error(f"Project broadcast failed: {e}")
    
    async def _send_direct_message(self, user_id: str, message: Dict[str, Any]):
        """Send direct message"""
        try:
            # Implementation for sending direct message
            pass
        except Exception as e:
            logger.error(f"Direct message failed: {e}")
    
    async def _find_optimal_meeting_time(self, participants: List[str]) -> datetime:
        """Find optimal meeting time"""
        try:
            # Implementation for finding optimal meeting time
            return datetime.now() + timedelta(hours=1)
        except Exception as e:
            logger.error(f"Meeting time finding failed: {e}")
            return datetime.now() + timedelta(hours=1)
    
    async def _generate_meeting_link(self, meeting: Dict[str, Any]) -> str:
        """Generate meeting link"""
        try:
            # Implementation for generating meeting link
            return f"https://meet.company.com/{meeting['meeting_id']}"
        except Exception as e:
            logger.error(f"Meeting link generation failed: {e}")
            return ""
    
    async def _send_meeting_invitations(self, meeting: Dict[str, Any]):
        """Send meeting invitations"""
        try:
            # Implementation for sending meeting invitations
            pass
        except Exception as e:
            logger.error(f"Meeting invitation sending failed: {e}")
    
    async def _notify_task_completion(self, task: Dict[str, Any]):
        """Notify task completion"""
        try:
            # Implementation for notifying task completion
            pass
        except Exception as e:
            logger.error(f"Task completion notification failed: {e}")
    
    async def _generate_team_productivity_report(self, team_id: str, date_range: Dict[str, Any]) -> Dict[str, Any]:
        """Generate team productivity report"""
        try:
            # Implementation for generating team productivity report
            return {"report_type": "team_productivity", "team_id": team_id}
        except Exception as e:
            logger.error(f"Team productivity report generation failed: {e}")
            return {"error": str(e)}
    
    async def _generate_project_status_report(self, project_id: str, date_range: Dict[str, Any]) -> Dict[str, Any]:
        """Generate project status report"""
        try:
            # Implementation for generating project status report
            return {"report_type": "project_status", "project_id": project_id}
        except Exception as e:
            logger.error(f"Project status report generation failed: {e}")
            return {"error": str(e)}
    
    async def _generate_communication_analytics_report(self, entity_id: str, date_range: Dict[str, Any]) -> Dict[str, Any]:
        """Generate communication analytics report"""
        try:
            # Implementation for generating communication analytics report
            return {"report_type": "communication_analytics", "entity_id": entity_id}
        except Exception as e:
            logger.error(f"Communication analytics report generation failed: {e}")
            return {"error": str(e)}
    
    async def _process_queued_communications(self):
        """Process queued communications"""
        try:
            # Implementation for processing queued communications
            pass
        except Exception as e:
            logger.error(f"Queued communications processing failed: {e}")
    
    async def _update_communication_analytics(self):
        """Update communication analytics"""
        try:
            # Implementation for updating communication analytics
            pass
        except Exception as e:
            logger.error(f"Communication analytics update failed: {e}")
    
    async def _monitor_task_deadlines(self):
        """Monitor task deadlines"""
        try:
            # Implementation for monitoring task deadlines
            pass
        except Exception as e:
            logger.error(f"Task deadline monitoring failed: {e}")
    
    async def _auto_assign_tasks(self):
        """Auto-assign tasks"""
        try:
            # Implementation for auto-assigning tasks
            pass
        except Exception as e:
            logger.error(f"Task auto-assignment failed: {e}")
    
    async def _send_reminders(self):
        """Send reminders"""
        try:
            # Implementation for sending reminders
            pass
        except Exception as e:
            logger.error(f"Reminder sending failed: {e}")
    
    async def _update_team_analytics(self):
        """Update team analytics"""
        try:
            # Implementation for updating team analytics
            pass
        except Exception as e:
            logger.error(f"Team analytics update failed: {e}")
    
    async def _update_project_analytics(self):
        """Update project analytics"""
        try:
            # Implementation for updating project analytics
            pass
        except Exception as e:
            logger.error(f"Project analytics update failed: {e}")
    
    async def _load_teams(self):
        """Load teams"""
        try:
            # Implementation for loading teams
            pass
        except Exception as e:
            logger.error(f"Teams loading failed: {e}")
    
    async def _load_projects(self):
        """Load projects"""
        try:
            # Implementation for loading projects
            pass
        except Exception as e:
            logger.error(f"Projects loading failed: {e}")
    
    async def _load_tasks(self):
        """Load tasks"""
        try:
            # Implementation for loading tasks
            pass
        except Exception as e:
            logger.error(f"Tasks loading failed: {e}")
    
    async def _load_collaboration_analytics(self):
        """Load collaboration analytics"""
        try:
            # Implementation for loading collaboration analytics
            pass
        except Exception as e:
            logger.error(f"Collaboration analytics loading failed: {e}")
    
    async def _update_project(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update project"""
        try:
            # Implementation for updating project
            return {"project_id": project_data.get("project_id"), "updated": True}
        except Exception as e:
            logger.error(f"Project update failed: {e}")
            return {"error": str(e)}
    
    async def _delete_project(self, project_id: str) -> Dict[str, Any]:
        """Delete project"""
        try:
            # Implementation for deleting project
            return {"project_id": project_id, "deleted": True}
        except Exception as e:
            logger.error(f"Project deletion failed: {e}")
            return {"error": str(e)}


# ========== TEST ==========
if __name__ == "__main__":
    async def test_collaboration_agent():
        # Initialize collaboration agent
        agent = CollaborationAgent()
        await agent.start()
        
        # Test team creation
        team_message = AgentMessage(
            id="test_team",
            from_agent="test",
            to_agent="collaboration_agent",
            content={
                "type": "create_team",
                "team_name": "Data Analytics Team",
                "team_members": ["user1", "user2", "user3"],
                "team_lead": "user1",
                "team_description": "Team for data analytics projects"
            },
            timestamp=datetime.now()
        )
        
        print("Testing collaboration agent...")
        async for response in agent.process_message(team_message):
            print(f"Team response: {response.content.get('type')}")
            team_result = response.content.get('team_result')
            print(f"Team created: {team_result.get('team_id') if team_result else 'None'}")
        
        # Test project management
        project_message = AgentMessage(
            id="test_project",
            from_agent="test",
            to_agent="collaboration_agent",
            content={
                "type": "manage_project",
                "action": "create",
                "project_data": {
                    "name": "Predator Analytics v13",
                    "description": "Complete autonomous analytics platform",
                    "team_id": team_result.get('team_id') if team_result else None,
                    "owner": "user1",
                    "start_date": datetime.now(),
                    "end_date": datetime.now() + timedelta(days=90),
                    "priority": "high"
                }
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(project_message):
            print(f"Project response: {response.content.get('type')}")
            project_result = response.content.get('project_result')
            print(f"Project created: {project_result.get('project_id') if project_result else 'None'}")
        
        # Test task assignment
        task_message = AgentMessage(
            id="test_task",
            from_agent="test",
            to_agent="collaboration_agent",
            content={
                "type": "assign_task",
                "task_data": {
                    "title": "Implement MAS agents",
                    "description": "Create all required multi-agent system agents",
                    "project_id": project_result.get('project_id') if project_result else None,
                    "assigned_to": "user2",
                    "assigned_by": "user1",
                    "priority": "high",
                    "due_date": datetime.now() + timedelta(days=30)
                }
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(task_message):
            print(f"Task response: {response.content.get('type')}")
            task_result = response.content.get('task_result')
            print(f"Task assigned: {task_result.get('task_id') if task_result else 'None'}")
        
        # Stop agent
        await agent.stop()
        print("Collaboration agent test completed")
    
    # Run test
    asyncio.run(test_collaboration_agent())
