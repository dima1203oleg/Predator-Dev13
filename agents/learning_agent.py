"""
Learning Agent: Continuous learning and knowledge acquisition
Handles knowledge acquisition, skill development, and learning management
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
from ..api.models import LearningPath, Skill, KnowledgeBase

logger = logging.getLogger(__name__)


class LearningAgent(BaseAgent):
    """
    Learning Agent for continuous learning and knowledge acquisition
    Handles knowledge acquisition, skill development, and learning management
    """
    
    def __init__(
        self,
        agent_id: str = "learning_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # Learning configuration
        self.learning_config = {
            "knowledge_acquisition": self.config.get("knowledge_acquisition", {
                "continuous_learning": True,
                "knowledge_discovery": True,
                "skill_assessment": True,
                "learning_path_generation": True,
                "content_curation": True,
                "expert_networking": True
            }),
            "skill_development": self.config.get("skill_development", {
                "skill_gap_analysis": True,
                "personalized_learning": True,
                "adaptive_learning": True,
                "micro_learning": True,
                "peer_learning": True,
                "mentorship_programs": True
            }),
            "learning_management": self.config.get("learning_management", {
                "learning_analytics": True,
                "progress_tracking": True,
                "certification_tracking": True,
                "competency_mapping": True,
                "learning_recommendations": True,
                "performance_analytics": True
            }),
            "content_management": self.config.get("content_management", {
                "content_creation": True,
                "content_curation": True,
                "content_personalization": True,
                "multi_modal_content": True,
                "content_analytics": True,
                "knowledge_sharing": True
            }),
            "adaptive_learning": self.config.get("adaptive_learning", {
                "learning_style_adaptation": True,
                "pace_adaptation": True,
                "difficulty_adaptation": True,
                "context_aware_learning": True,
                "reinforcement_learning": True,
                "cognitive_load_management": True
            }),
            "collaboration_learning": self.config.get("collaboration_learning", {
                "peer_learning": True,
                "group_learning": True,
                "expert_mentoring": True,
                "knowledge_sharing": True,
                "community_learning": True,
                "cross_team_learning": True
            }),
            "analytics_reporting": self.config.get("analytics_reporting", {
                "learning_metrics": True,
                "skill_development_tracking": True,
                "knowledge_retention": True,
                "learning_effectiveness": True,
                "roi_analysis": True
            }),
            "integration": self.config.get("integration", {
                "lms_integration": True,
                "hr_systems": True,
                "content_platforms": True,
                "social_learning": True,
                "mobile_learning": True,
                "api_integrations": True
            }),
            "processing": self.config.get("processing", {
                "parallel_learning_processing": 4,
                "real_time_adaptation": True,
                "batch_learning_updates": 100,
                "cache_ttl_seconds": 3600
            })
        }
        
        # Learning management
        self.learning_paths = {}
        self.skills = {}
        self.knowledge_base = {}
        self.learning_analytics = {}
        self.user_learning_profiles = {}
        
        # Background tasks
        self.knowledge_acquisition_task = None
        self.skill_assessment_task = None
        self.learning_adaptation_task = None
        
        logger.info(f"Learning Agent initialized: {agent_id}")
    
    async def start(self):
        """
        Start the learning agent
        """
        await super().start()
        
        # Load learning data
        await self._load_learning_data()
        
        # Start background tasks
        self.knowledge_acquisition_task = asyncio.create_task(self._continuous_knowledge_acquisition())
        self.skill_assessment_task = asyncio.create_task(self._continuous_skill_assessment())
        self.learning_adaptation_task = asyncio.create_task(self._continuous_learning_adaptation())
        
        logger.info("Learning agent started")
    
    async def stop(self):
        """
        Stop the learning agent
        """
        if self.knowledge_acquisition_task:
            self.knowledge_acquisition_task.cancel()
            try:
                await self.knowledge_acquisition_task
            except asyncio.CancelledError:
                pass
        
        if self.skill_assessment_task:
            self.skill_assessment_task.cancel()
            try:
                await self.skill_assessment_task
            except asyncio.CancelledError:
                pass
        
        if self.learning_adaptation_task:
            self.learning_adaptation_task.cancel()
            try:
                await self.learning_adaptation_task
            except asyncio.CancelledError:
                pass
        
        await super().stop()
        logger.info("Learning agent stopped")
    
    async def _load_learning_data(self):
        """
        Load existing learning data and configurations
        """
        try:
            # Load learning paths, skills, knowledge base, analytics, user profiles, etc.
            await self._load_learning_paths()
            await self._load_skills()
            await self._load_knowledge_base()
            await self._load_learning_analytics()
            await self._load_user_learning_profiles()
            
            logger.info("Learning data loaded")
            
        except Exception as e:
            logger.error(f"Learning data loading failed: {e}")
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process learning requests
        """
        try:
            message_type = message.content.get("type", "")
            
            if message_type == "assess_skills":
                async for response in self._handle_skill_assessment(message):
                    yield response
                    
            elif message_type == "generate_learning_path":
                async for response in self._handle_learning_path_generation(message):
                    yield response
                    
            elif message_type == "acquire_knowledge":
                async for response in self._handle_knowledge_acquisition(message):
                    yield response
                    
            elif message_type == "adapt_learning":
                async for response in self._handle_learning_adaptation(message):
                    yield response
                    
            elif message_type == "track_progress":
                async for response in self._handle_progress_tracking(message):
                    yield response
                    
            elif message_type == "generate_content":
                async for response in self._handle_content_generation(message):
                    yield response
                    
            elif message_type == "analyze_learning":
                async for response in self._handle_learning_analytics(message):
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
            logger.error(f"Learning processing failed: {e}")
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
    
    async def _handle_skill_assessment(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle skill assessment
        """
        try:
            user_id = message.content.get("user_id")
            assessment_data = message.content.get("assessment_data", {})
            
            # Assess skills
            assessment_result = await self._assess_skills(user_id, assessment_data)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "skills_assessed",
                    "assessment_result": assessment_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Skill assessment handling failed: {e}")
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
    
    async def _assess_skills(
        self,
        user_id: str,
        assessment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Assess user skills
        """
        try:
            assessment_type = assessment_data.get("assessment_type", "comprehensive")
            
            # Get or create user learning profile
            if user_id not in self.user_learning_profiles:
                self.user_learning_profiles[user_id] = {
                    "user_id": user_id,
                    "current_skills": {},
                    "skill_gaps": {},
                    "learning_history": [],
                    "learning_preferences": {},
                    "performance_metrics": {},
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                }
            
            profile = self.user_learning_profiles[user_id]
            
            # Perform assessment based on type
            if assessment_type == "comprehensive":
                assessment_result = await self._perform_comprehensive_assessment(user_id, assessment_data)
            elif assessment_type == "skill_specific":
                assessment_result = await self._perform_skill_specific_assessment(user_id, assessment_data)
            elif assessment_type == "performance_based":
                assessment_result = await self._perform_performance_based_assessment(user_id, assessment_data)
            else:
                assessment_result = {"error": f"Unknown assessment type: {assessment_type}"}
            
            # Update profile
            if "current_skills" in assessment_result:
                profile["current_skills"].update(assessment_result["current_skills"])
            
            if "skill_gaps" in assessment_result:
                profile["skill_gaps"].update(assessment_result["skill_gaps"])
            
            profile["updated_at"] = datetime.now()
            
            return assessment_result
            
        except Exception as e:
            logger.error(f"Skill assessment failed: {e}")
            return {"error": str(e)}
    
    async def _perform_comprehensive_assessment(
        self,
        user_id: str,
        assessment_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Perform comprehensive skill assessment
        """
        try:
            current_skills = {}
            skill_gaps = {}
            
            # Assess technical skills
            technical_assessment = await self._assess_technical_skills(user_id, assessment_data)
            current_skills.update(technical_assessment.get("current_skills", {}))
            skill_gaps.update(technical_assessment.get("skill_gaps", {}))
            
            # Assess soft skills
            soft_assessment = await self._assess_soft_skills(user_id, assessment_data)
            current_skills.update(soft_assessment.get("current_skills", {}))
            skill_gaps.update(soft_assessment.get("skill_gaps", {}))
            
            # Assess domain knowledge
            domain_assessment = await self._assess_domain_knowledge(user_id, assessment_data)
            current_skills.update(domain_assessment.get("current_skills", {}))
            skill_gaps.update(domain_assessment.get("skill_gaps", {}))
            
            # Calculate overall competency score
            overall_score = await self._calculate_overall_competency(current_skills)
            
            return {
                "assessment_type": "comprehensive",
                "current_skills": current_skills,
                "skill_gaps": skill_gaps,
                "overall_competency_score": overall_score,
                "assessment_date": datetime.now(),
                "recommendations": await self._generate_assessment_recommendations(skill_gaps)
            }
            
        except Exception as e:
            logger.error(f"Comprehensive assessment failed: {e}")
            return {"error": str(e)}
    
    async def _handle_learning_path_generation(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle learning path generation
        """
        try:
            user_id = message.content.get("user_id")
            path_data = message.content.get("path_data", {})
            
            # Generate learning path
            path_result = await self._generate_learning_path(user_id, path_data)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "learning_path_generated",
                    "path_result": path_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Learning path generation handling failed: {e}")
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
    
    async def _generate_learning_path(
        self,
        user_id: str,
        path_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate personalized learning path
        """
        try:
            target_skills = path_data.get("target_skills", [])
            current_level = path_data.get("current_level", "beginner")
            time_available = path_data.get("time_available", "part_time")
            learning_goals = path_data.get("learning_goals", [])
            
            # Get user profile
            profile = self.user_learning_profiles.get(user_id, {})
            current_skills = profile.get("current_skills", {})
            learning_preferences = profile.get("learning_preferences", {})
            
            # Generate learning path
            learning_path = {
                "path_id": str(uuid.uuid4()),
                "user_id": user_id,
                "title": f"Personalized Learning Path for {user_id}",
                "description": f"Custom learning path based on skill assessment and goals",
                "target_skills": target_skills,
                "current_level": current_level,
                "estimated_duration": await self._estimate_path_duration(target_skills, current_level, time_available),
                "modules": await self._generate_learning_modules(target_skills, current_skills, current_level),
                "milestones": await self._generate_milestones(target_skills),
                "resources": await self._recommend_resources(target_skills, learning_preferences),
                "schedule": await self._create_learning_schedule(target_skills, time_available),
                "assessment_points": await self._define_assessment_points(target_skills),
                "created_at": datetime.now(),
                "status": "active"
            }
            
            # Store learning path
            self.learning_paths[learning_path["path_id"]] = learning_path
            
            return learning_path
            
        except Exception as e:
            logger.error(f"Learning path generation failed: {e}")
            return {"error": str(e)}
    
    async def _handle_knowledge_acquisition(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle knowledge acquisition
        """
        try:
            acquisition_data = message.content.get("acquisition_data", {})
            
            # Acquire knowledge
            acquisition_result = await self._acquire_knowledge(acquisition_data)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "knowledge_acquired",
                    "acquisition_result": acquisition_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Knowledge acquisition handling failed: {e}")
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
    
    async def _acquire_knowledge(
        self,
        acquisition_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Acquire new knowledge from various sources
        """
        try:
            knowledge_sources = acquisition_data.get("sources", ["web", "academic", "industry", "internal"])
            topics = acquisition_data.get("topics", [])
            acquisition_method = acquisition_data.get("method", "automated")
            
            acquired_knowledge = []
            
            # Acquire from different sources
            for source in knowledge_sources:
                if source == "web":
                    web_knowledge = await self._acquire_from_web(topics)
                    acquired_knowledge.extend(web_knowledge)
                    
                elif source == "academic":
                    academic_knowledge = await self._acquire_from_academic_sources(topics)
                    acquired_knowledge.extend(academic_knowledge)
                    
                elif source == "industry":
                    industry_knowledge = await self._acquire_from_industry_sources(topics)
                    acquired_knowledge.extend(industry_knowledge)
                    
                elif source == "internal":
                    internal_knowledge = await self._acquire_from_internal_sources(topics)
                    acquired_knowledge.extend(internal_knowledge)
            
            # Process and store acquired knowledge
            processed_knowledge = await self._process_acquired_knowledge(acquired_knowledge)
            
            # Update knowledge base
            for knowledge_item in processed_knowledge:
                kb_id = str(uuid.uuid4())
                self.knowledge_base[kb_id] = {
                    "kb_id": kb_id,
                    "content": knowledge_item,
                    "source": knowledge_item.get("source"),
                    "topic": knowledge_item.get("topic"),
                    "acquisition_date": datetime.now(),
                    "quality_score": knowledge_item.get("quality_score", 0.8),
                    "tags": knowledge_item.get("tags", [])
                }
            
            return {
                "acquisition_method": acquisition_method,
                "sources_used": knowledge_sources,
                "topics_covered": topics,
                "knowledge_items_acquired": len(processed_knowledge),
                "quality_metrics": await self._calculate_knowledge_quality_metrics(processed_knowledge),
                "acquisition_timestamp": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Knowledge acquisition failed: {e}")
            return {"error": str(e)}
    
    async def _handle_learning_adaptation(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle learning adaptation
        """
        try:
            user_id = message.content.get("user_id")
            adaptation_data = message.content.get("adaptation_data", {})
            
            # Adapt learning
            adaptation_result = await self._adapt_learning(user_id, adaptation_data)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "learning_adapted",
                    "adaptation_result": adaptation_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Learning adaptation handling failed: {e}")
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
    
    async def _adapt_learning(
        self,
        user_id: str,
        adaptation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Adapt learning based on user performance and preferences
        """
        try:
            performance_data = adaptation_data.get("performance_data", {})
            learning_style = adaptation_data.get("learning_style")
            current_difficulty = adaptation_data.get("current_difficulty", "medium")
            
            # Analyze learning patterns
            learning_patterns = await self._analyze_learning_patterns(user_id, performance_data)
            
            # Determine optimal adaptations
            adaptations = {
                "pace_adjustment": await self._determine_pace_adjustment(learning_patterns),
                "difficulty_adjustment": await self._determine_difficulty_adjustment(learning_patterns, current_difficulty),
                "content_adaptation": await self._adapt_content_style(learning_style, learning_patterns),
                "method_adaptation": await self._adapt_learning_method(learning_patterns),
                "resource_recommendations": await self._recommend_adapted_resources(learning_patterns),
                "intervention_needed": await self._check_intervention_needed(learning_patterns)
            }
            
            # Apply adaptations to user profile
            if user_id in self.user_learning_profiles:
                profile = self.user_learning_profiles[user_id]
                profile["learning_preferences"].update({
                    "adapted_pace": adaptations["pace_adjustment"],
                    "adapted_difficulty": adaptations["difficulty_adjustment"],
                    "adapted_style": adaptations["content_adaptation"],
                    "adapted_method": adaptations["method_adaptation"],
                    "last_adaptation": datetime.now()
                })
            
            return {
                "user_id": user_id,
                "adaptations": adaptations,
                "learning_patterns": learning_patterns,
                "adaptation_timestamp": datetime.now(),
                "expected_improvement": await self._predict_adaptation_impact(adaptations)
            }
            
        except Exception as e:
            logger.error(f"Learning adaptation failed: {e}")
            return {"error": str(e)}
    
    async def _handle_progress_tracking(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle progress tracking
        """
        try:
            user_id = message.content.get("user_id")
            progress_data = message.content.get("progress_data", {})
            
            # Track progress
            progress_result = await self._track_progress(user_id, progress_data)
            
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
    
    async def _track_progress(
        self,
        user_id: str,
        progress_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Track learning progress
        """
        try:
            learning_path_id = progress_data.get("learning_path_id")
            completed_modules = progress_data.get("completed_modules", [])
            assessment_scores = progress_data.get("assessment_scores", {})
            time_spent = progress_data.get("time_spent", 0)
            
            # Get learning path
            learning_path = self.learning_paths.get(learning_path_id)
            if not learning_path:
                return {"error": "Learning path not found"}
            
            # Calculate progress metrics
            total_modules = len(learning_path.get("modules", []))
            completed_count = len(completed_modules)
            progress_percentage = (completed_count / total_modules) * 100 if total_modules > 0 else 0
            
            # Calculate skill improvement
            skill_improvement = await self._calculate_skill_improvement(user_id, assessment_scores)
            
            # Update learning history
            if user_id in self.user_learning_profiles:
                profile = self.user_learning_profiles[user_id]
                profile["learning_history"].append({
                    "learning_path_id": learning_path_id,
                    "progress_update": progress_percentage,
                    "completed_modules": completed_modules,
                    "assessment_scores": assessment_scores,
                    "time_spent": time_spent,
                    "timestamp": datetime.now()
                })
            
            # Check for milestones
            milestones_achieved = await self._check_milestones_achieved(learning_path, progress_percentage)
            
            return {
                "user_id": user_id,
                "learning_path_id": learning_path_id,
                "progress_percentage": progress_percentage,
                "completed_modules": completed_count,
                "total_modules": total_modules,
                "skill_improvement": skill_improvement,
                "time_spent": time_spent,
                "milestones_achieved": milestones_achieved,
                "estimated_completion": await self._estimate_completion_time(learning_path, progress_percentage),
                "recommendations": await self._generate_progress_recommendations(progress_percentage, skill_improvement)
            }
            
        except Exception as e:
            logger.error(f"Progress tracking failed: {e}")
            return {"error": str(e)}
    
    # Background monitoring tasks
    async def _continuous_knowledge_acquisition(self):
        """
        Continuous knowledge acquisition
        """
        try:
            while True:
                try:
                    # Acquire new knowledge
                    await self._acquire_new_knowledge()
                    
                    # Update knowledge base
                    await self._update_knowledge_base()
                    
                except Exception as e:
                    logger.error(f"Knowledge acquisition error: {e}")
                
                # Acquire every 2 hours
                await asyncio.sleep(7200)
                
        except asyncio.CancelledError:
            logger.info("Knowledge acquisition cancelled")
            raise
    
    async def _continuous_skill_assessment(self):
        """
        Continuous skill assessment
        """
        try:
            while True:
                try:
                    # Assess skills for all users
                    await self._assess_all_user_skills()
                    
                    # Update skill gaps
                    await self._update_skill_gaps()
                    
                except Exception as e:
                    logger.error(f"Skill assessment error: {e}")
                
                # Assess every 24 hours
                await asyncio.sleep(86400)
                
        except asyncio.CancelledError:
            logger.info("Skill assessment cancelled")
            raise
    
    async def _continuous_learning_adaptation(self):
        """
        Continuous learning adaptation
        """
        try:
            while True:
                try:
                    # Adapt learning for all users
                    await self._adapt_all_user_learning()
                    
                    # Update learning recommendations
                    await self._update_learning_recommendations()
                    
                except Exception as e:
                    logger.error(f"Learning adaptation error: {e}")
                
                # Adapt every 6 hours
                await asyncio.sleep(21600)
                
        except asyncio.CancelledError:
            logger.info("Learning adaptation cancelled")
            raise
    
    # Additional helper methods would continue...
    
    async def _assess_technical_skills(self, user_id: str, assessment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess technical skills"""
        try:
            # Implementation for assessing technical skills
            return {"current_skills": {"python": 0.8, "sql": 0.7}, "skill_gaps": {"machine_learning": 0.6}}
        except Exception as e:
            logger.error(f"Technical skills assessment failed: {e}")
            return {"error": str(e)}
    
    async def _assess_soft_skills(self, user_id: str, assessment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess soft skills"""
        try:
            # Implementation for assessing soft skills
            return {"current_skills": {"communication": 0.9, "leadership": 0.6}, "skill_gaps": {"teamwork": 0.4}}
        except Exception as e:
            logger.error(f"Soft skills assessment failed: {e}")
            return {"error": str(e)}
    
    async def _assess_domain_knowledge(self, user_id: str, assessment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess domain knowledge"""
        try:
            # Implementation for assessing domain knowledge
            return {"current_skills": {"data_analytics": 0.8, "business_intelligence": 0.7}, "skill_gaps": {"ai_ml": 0.5}}
        except Exception as e:
            logger.error(f"Domain knowledge assessment failed: {e}")
            return {"error": str(e)}
    
    async def _calculate_overall_competency(self, current_skills: Dict[str, float]) -> float:
        """Calculate overall competency score"""
        try:
            # Implementation for calculating overall competency
            return sum(current_skills.values()) / len(current_skills) if current_skills else 0.0
        except Exception as e:
            logger.error(f"Overall competency calculation failed: {e}")
            return 0.0
    
    async def _generate_assessment_recommendations(self, skill_gaps: Dict[str, float]) -> List[str]:
        """Generate assessment recommendations"""
        try:
            # Implementation for generating assessment recommendations
            return ["Focus on machine learning skills", "Improve leadership abilities"]
        except Exception as e:
            logger.error(f"Assessment recommendations generation failed: {e}")
            return []
    
    async def _estimate_path_duration(self, target_skills: List[str], current_level: str, time_available: str) -> int:
        """Estimate learning path duration"""
        try:
            # Implementation for estimating path duration
            return 90  # days
        except Exception as e:
            logger.error(f"Path duration estimation failed: {e}")
            return 0
    
    async def _generate_learning_modules(self, target_skills: List[str], current_skills: Dict[str, float], current_level: str) -> List[Dict[str, Any]]:
        """Generate learning modules"""
        try:
            # Implementation for generating learning modules
            return [{"title": "Python Basics", "duration": 30, "difficulty": "beginner"}]
        except Exception as e:
            logger.error(f"Learning modules generation failed: {e}")
            return []
    
    async def _generate_milestones(self, target_skills: List[str]) -> List[Dict[str, Any]]:
        """Generate milestones"""
        try:
            # Implementation for generating milestones
            return [{"title": "Complete Python course", "target_date": datetime.now() + timedelta(days=30)}]
        except Exception as e:
            logger.error(f"Milestones generation failed: {e}")
            return []
    
    async def _recommend_resources(self, target_skills: List[str], learning_preferences: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Recommend resources"""
        try:
            # Implementation for recommending resources
            return [{"title": "Python Crash Course", "type": "book", "url": "example.com"}]
        except Exception as e:
            logger.error(f"Resource recommendation failed: {e}")
            return []
    
    async def _create_learning_schedule(self, target_skills: List[str], time_available: str) -> Dict[str, Any]:
        """Create learning schedule"""
        try:
            # Implementation for creating learning schedule
            return {"weekly_hours": 10, "schedule": "Monday-Friday evenings"}
        except Exception as e:
            logger.error(f"Learning schedule creation failed: {e}")
            return {}
    
    async def _define_assessment_points(self, target_skills: List[str]) -> List[Dict[str, Any]]:
        """Define assessment points"""
        try:
            # Implementation for defining assessment points
            return [{"title": "Python Assessment", "type": "quiz", "due_date": datetime.now() + timedelta(days=30)}]
        except Exception as e:
            logger.error(f"Assessment points definition failed: {e}")
            return []
    
    async def _acquire_from_web(self, topics: List[str]) -> List[Dict[str, Any]]:
        """Acquire knowledge from web"""
        try:
            # Implementation for acquiring from web
            return [{"content": "Web knowledge", "source": "web", "topic": topics[0] if topics else "general"}]
        except Exception as e:
            logger.error(f"Web knowledge acquisition failed: {e}")
            return []
    
    async def _acquire_from_academic_sources(self, topics: List[str]) -> List[Dict[str, Any]]:
        """Acquire knowledge from academic sources"""
        try:
            # Implementation for acquiring from academic sources
            return [{"content": "Academic knowledge", "source": "academic", "topic": topics[0] if topics else "general"}]
        except Exception as e:
            logger.error(f"Academic knowledge acquisition failed: {e}")
            return []
    
    async def _acquire_from_industry_sources(self, topics: List[str]) -> List[Dict[str, Any]]:
        """Acquire knowledge from industry sources"""
        try:
            # Implementation for acquiring from industry sources
            return [{"content": "Industry knowledge", "source": "industry", "topic": topics[0] if topics else "general"}]
        except Exception as e:
            logger.error(f"Industry knowledge acquisition failed: {e}")
            return []
    
    async def _acquire_from_internal_sources(self, topics: List[str]) -> List[Dict[str, Any]]:
        """Acquire knowledge from internal sources"""
        try:
            # Implementation for acquiring from internal sources
            return [{"content": "Internal knowledge", "source": "internal", "topic": topics[0] if topics else "general"}]
        except Exception as e:
            logger.error(f"Internal knowledge acquisition failed: {e}")
            return []
    
    async def _process_acquired_knowledge(self, acquired_knowledge: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process acquired knowledge"""
        try:
            # Implementation for processing acquired knowledge
            return acquired_knowledge
        except Exception as e:
            logger.error(f"Knowledge processing failed: {e}")
            return []
    
    async def _calculate_knowledge_quality_metrics(self, processed_knowledge: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate knowledge quality metrics"""
        try:
            # Implementation for calculating knowledge quality metrics
            return {"average_quality": 0.8, "total_items": len(processed_knowledge)}
        except Exception as e:
            logger.error(f"Knowledge quality metrics calculation failed: {e}")
            return {}
    
    async def _analyze_learning_patterns(self, user_id: str, performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze learning patterns"""
        try:
            # Implementation for analyzing learning patterns
            return {"pattern": "consistent_learner", "strengths": ["quick_comprehension"], "weaknesses": ["needs_more_practice"]}
        except Exception as e:
            logger.error(f"Learning patterns analysis failed: {e}")
            return {}
    
    async def _determine_pace_adjustment(self, learning_patterns: Dict[str, Any]) -> str:
        """Determine pace adjustment"""
        try:
            # Implementation for determining pace adjustment
            return "maintain_current_pace"
        except Exception as e:
            logger.error(f"Pace adjustment determination failed: {e}")
            return "maintain_current_pace"
    
    async def _determine_difficulty_adjustment(self, learning_patterns: Dict[str, Any], current_difficulty: str) -> str:
        """Determine difficulty adjustment"""
        try:
            # Implementation for determining difficulty adjustment
            return "increase_slightly"
        except Exception as e:
            logger.error(f"Difficulty adjustment determination failed: {e}")
            return "maintain_current"
    
    async def _adapt_content_style(self, learning_style: str, learning_patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt content style"""
        try:
            # Implementation for adapting content style
            return {"style": "visual", "format": "videos_and_diagrams"}
        except Exception as e:
            logger.error(f"Content style adaptation failed: {e}")
            return {}
    
    async def _adapt_learning_method(self, learning_patterns: Dict[str, Any]) -> str:
        """Adapt learning method"""
        try:
            # Implementation for adapting learning method
            return "interactive_learning"
        except Exception as e:
            logger.error(f"Learning method adaptation failed: {e}")
            return "standard_method"
    
    async def _recommend_adapted_resources(self, learning_patterns: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Recommend adapted resources"""
        try:
            # Implementation for recommending adapted resources
            return [{"title": "Interactive Python Tutorial", "type": "interactive_course"}]
        except Exception as e:
            logger.error(f"Adapted resources recommendation failed: {e}")
            return []
    
    async def _check_intervention_needed(self, learning_patterns: Dict[str, Any]) -> bool:
        """Check if intervention is needed"""
        try:
            # Implementation for checking intervention needed
            return False
        except Exception as e:
            logger.error(f"Intervention check failed: {e}")
            return False
    
    async def _predict_adaptation_impact(self, adaptations: Dict[str, Any]) -> Dict[str, Any]:
        """Predict adaptation impact"""
        try:
            # Implementation for predicting adaptation impact
            return {"expected_improvement": 0.15, "confidence": 0.8}
        except Exception as e:
            logger.error(f"Adaptation impact prediction failed: {e}")
            return {}
    
    async def _calculate_skill_improvement(self, user_id: str, assessment_scores: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate skill improvement"""
        try:
            # Implementation for calculating skill improvement
            return {"python": 0.2, "sql": 0.1, "overall": 0.15}
        except Exception as e:
            logger.error(f"Skill improvement calculation failed: {e}")
            return {}
    
    async def _check_milestones_achieved(self, learning_path: Dict[str, Any], progress_percentage: float) -> List[str]:
        """Check milestones achieved"""
        try:
            # Implementation for checking milestones achieved
            return ["Completed Python basics module"]
        except Exception as e:
            logger.error(f"Milestones check failed: {e}")
            return []
    
    async def _estimate_completion_time(self, learning_path: Dict[str, Any], progress_percentage: float) -> datetime:
        """Estimate completion time"""
        try:
            # Implementation for estimating completion time
            return datetime.now() + timedelta(days=60)
        except Exception as e:
            logger.error(f"Completion time estimation failed: {e}")
            return datetime.now()
    
    async def _generate_progress_recommendations(self, progress_percentage: float, skill_improvement: Dict[str, Any]) -> List[str]:
        """Generate progress recommendations"""
        try:
            # Implementation for generating progress recommendations
            return ["Continue with current pace", "Focus on weak areas"]
        except Exception as e:
            logger.error(f"Progress recommendations generation failed: {e}")
            return []
    
    async def _acquire_new_knowledge(self):
        """Acquire new knowledge"""
        try:
            # Implementation for acquiring new knowledge
            pass
        except Exception as e:
            logger.error(f"New knowledge acquisition failed: {e}")
    
    async def _update_knowledge_base(self):
        """Update knowledge base"""
        try:
            # Implementation for updating knowledge base
            pass
        except Exception as e:
            logger.error(f"Knowledge base update failed: {e}")
    
    async def _assess_all_user_skills(self):
        """Assess skills for all users"""
        try:
            # Implementation for assessing all user skills
            pass
        except Exception as e:
            logger.error(f"All user skills assessment failed: {e}")
    
    async def _update_skill_gaps(self):
        """Update skill gaps"""
        try:
            # Implementation for updating skill gaps
            pass
        except Exception as e:
            logger.error(f"Skill gaps update failed: {e}")
    
    async def _adapt_all_user_learning(self):
        """Adapt learning for all users"""
        try:
            # Implementation for adapting all user learning
            pass
        except Exception as e:
            logger.error(f"All user learning adaptation failed: {e}")
    
    async def _update_learning_recommendations(self):
        """Update learning recommendations"""
        try:
            # Implementation for updating learning recommendations
            pass
        except Exception as e:
            logger.error(f"Learning recommendations update failed: {e}")
    
    async def _load_learning_paths(self):
        """Load learning paths"""
        try:
            # Implementation for loading learning paths
            pass
        except Exception as e:
            logger.error(f"Learning paths loading failed: {e}")
    
    async def _load_skills(self):
        """Load skills"""
        try:
            # Implementation for loading skills
            pass
        except Exception as e:
            logger.error(f"Skills loading failed: {e}")
    
    async def _load_knowledge_base(self):
        """Load knowledge base"""
        try:
            # Implementation for loading knowledge base
            pass
        except Exception as e:
            logger.error(f"Knowledge base loading failed: {e}")
    
    async def _load_learning_analytics(self):
        """Load learning analytics"""
        try:
            # Implementation for loading learning analytics
            pass
        except Exception as e:
            logger.error(f"Learning analytics loading failed: {e}")
    
    async def _load_user_learning_profiles(self):
        """Load user learning profiles"""
        try:
            # Implementation for loading user learning profiles
            pass
        except Exception as e:
            logger.error(f"User learning profiles loading failed: {e)}
    
    async def _perform_skill_specific_assessment(self, user_id: str, assessment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform skill-specific assessment"""
        try:
            # Implementation for skill-specific assessment
            return {"current_skills": {}, "skill_gaps": {}}
        except Exception as e:
            logger.error(f"Skill-specific assessment failed: {e}")
            return {"error": str(e)}
    
    async def _perform_performance_based_assessment(self, user_id: str, assessment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Perform performance-based assessment"""
        try:
            # Implementation for performance-based assessment
            return {"current_skills": {}, "skill_gaps": {}}
        except Exception as e:
            logger.error(f"Performance-based assessment failed: {e}")
            return {"error": str(e)}
    
    async def _handle_content_generation(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """Handle content generation"""
        try:
            content_data = message.content.get("content_data", {})
            
            # Generate content
            content_result = await self._generate_content(content_data)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "content_generated",
                    "content_result": content_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Content generation handling failed: {e}")
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
    
    async def _generate_content(self, content_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate learning content"""
        try:
            # Implementation for generating content
            return {"content": "Generated learning content", "type": "tutorial"}
        except Exception as e:
            logger.error(f"Content generation failed: {e}")
            return {"error": str(e)}
    
    async def _handle_learning_analytics(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """Handle learning analytics"""
        try:
            analytics_data = message.content.get("analytics_data", {})
            
            # Analyze learning
            analytics_result = await self._analyze_learning(analytics_data)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "learning_analyzed",
                    "analytics_result": analytics_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Learning analytics handling failed: {e}")
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
    
    async def _analyze_learning(self, analytics_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze learning data"""
        try:
            # Implementation for analyzing learning
            return {"analytics": "Learning analytics results", "insights": []}
        except Exception as e:
            logger.error(f"Learning analysis failed: {e}")
            return {"error": str(e)}


# ========== TEST ==========
if __name__ == "__main__":
    async def test_learning_agent():
        # Initialize learning agent
        agent = LearningAgent()
        await agent.start()
        
        # Test skill assessment
        assessment_message = AgentMessage(
            id="test_assessment",
            from_agent="test",
            to_agent="learning_agent",
            content={
                "type": "assess_skills",
                "user_id": "user123",
                "assessment_data": {
                    "assessment_type": "comprehensive",
                    "include_technical": True,
                    "include_soft": True,
                    "include_domain": True
                }
            },
            timestamp=datetime.now()
        )
        
        print("Testing learning agent...")
        async for response in agent.process_message(assessment_message):
            print(f"Assessment response: {response.content.get('type')}")
            assessment_result = response.content.get('assessment_result')
            print(f"Skills assessed: {assessment_result.get('assessment_type') if assessment_result else 'None'}")
        
        # Test learning path generation
        path_message = AgentMessage(
            id="test_path",
            from_agent="test",
            to_agent="learning_agent",
            content={
                "type": "generate_learning_path",
                "user_id": "user123",
                "path_data": {
                    "target_skills": ["python", "machine_learning", "data_analysis"],
                    "current_level": "intermediate",
                    "time_available": "part_time",
                    "learning_goals": ["Become data scientist", "Improve ML skills"]
                }
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(path_message):
            print(f"Path response: {response.content.get('type')}")
            path_result = response.content.get('path_result')
            print(f"Learning path generated: {path_result.get('path_id') if path_result else 'None'}")
        
        # Stop agent
        await agent.stop()
        print("Learning agent test completed")
    
    # Run test
    asyncio.run(test_learning_agent())
