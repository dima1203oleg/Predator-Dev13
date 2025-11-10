"""
Personal Feed Agent: Daily Newspaper personalization
Creates personalized daily news feeds based on user preferences and behavior
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
import heapq

from ..agents.base_agent import BaseAgent, AgentState, AgentMessage
from ..api.database import get_db_session
from ..api.models import CustomsData, Company, HSCode, PersonalFeed

logger = logging.getLogger(__name__)


class PersonalFeedAgent(BaseAgent):
    """
    Personal Feed Agent for creating personalized daily newspaper feeds
    Learns user preferences and generates customized content digests
    """
    
    def __init__(
        self,
        agent_id: str = "personal_feed_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # Personalization settings
        self.feed_update_frequency = self.config.get("feed_update_frequency", 24)  # hours
        self.max_feed_items = self.config.get("max_feed_items", 50)
        self.content_freshness_days = self.config.get("content_freshness_days", 7)
        
        # User preference learning
        self.preference_decay = self.config.get("preference_decay", 0.95)  # Daily decay factor
        self.min_interactions = self.config.get("min_interactions", 5)  # Min interactions for learning
        
        # Content categories
        self.content_categories = {
            "corruption_alerts": {"weight": 1.0, "description": "Corruption and fraud alerts"},
            "company_news": {"weight": 0.8, "description": "Company-related news and updates"},
            "market_trends": {"weight": 0.7, "description": "Market and industry trends"},
            "regulatory_changes": {"weight": 0.9, "description": "Regulatory and policy changes"},
            "risk_assessments": {"weight": 0.8, "description": "Risk assessment reports"},
            "forecasts": {"weight": 0.6, "description": "Economic forecasts and predictions"},
            "investigations": {"weight": 1.0, "description": "Ongoing investigations"},
            "breaking_news": {"weight": 1.2, "description": "Breaking news and urgent alerts"}
        }
        
        # User profiles cache
        self.user_profiles = {}
        self.last_profile_update = {}
        
        logger.info(f"Personal Feed Agent initialized: {agent_id}")
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process personal feed requests
        """
        try:
            message_type = message.content.get("type", "")
            
            if message_type == "generate_daily_feed":
                async for response in self._handle_daily_feed_generation(message):
                    yield response
                    
            elif message_type == "update_user_preferences":
                async for response in self._handle_preference_update(message):
                    yield response
                    
            elif message_type == "get_user_profile":
                async for response in self._handle_profile_request(message):
                    yield response
                    
            elif message_type == "customize_feed":
                async for response in self._handle_feed_customization(message):
                    yield response
                    
            elif message_type == "analyze_feed_performance":
                async for response in self._handle_performance_analysis(message):
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
            logger.error(f"Personal feed processing failed: {e}")
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
    
    async def _handle_daily_feed_generation(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle daily feed generation request
        """
        try:
            user_id = message.content.get("user_id")
            feed_date = message.content.get("feed_date")
            
            if not user_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "user_id required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            if not feed_date:
                feed_date = datetime.now().date()
            elif isinstance(feed_date, str):
                feed_date = datetime.fromisoformat(feed_date).date()
            
            # Generate personalized feed
            feed = await self._generate_personalized_feed(user_id, feed_date)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "daily_feed_response",
                    "user_id": user_id,
                    "feed_date": feed_date.isoformat(),
                    "feed": feed
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Daily feed generation failed: {e}")
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
    
    async def _generate_personalized_feed(
        self,
        user_id: str,
        feed_date: datetime.date
    ) -> Dict[str, Any]:
        """
        Generate personalized daily feed for user
        """
        try:
            # Get user profile
            user_profile = await self._get_user_profile(user_id)
            
            # Get available content
            available_content = await self._get_available_content(feed_date)
            
            # Score and rank content
            scored_content = await self._score_content_for_user(available_content, user_profile)
            
            # Select top content
            selected_content = self._select_feed_content(scored_content, user_profile)
            
            # Organize into newspaper format
            newspaper_feed = self._format_as_newspaper(selected_content, user_profile, feed_date)
            
            # Update user engagement tracking
            await self._update_user_engagement(user_id, selected_content)
            
            return newspaper_feed
            
        except Exception as e:
            logger.error(f"Personalized feed generation failed: {e}")
            return {"error": str(e)}
    
    async def _get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Get or create user profile
        """
        try:
            # Check cache first
            if user_id in self.user_profiles:
                last_update = self.last_profile_update.get(user_id)
                if last_update and (datetime.now() - last_update).total_seconds() < 3600:  # 1 hour cache
                    return self.user_profiles[user_id]
            
            # Load from database
            async with get_db_session() as session:
                # Get user preferences and interaction history
                profile_data = await self._load_user_profile_from_db(session, user_id)
                
                if not profile_data:
                    # Create default profile
                    profile_data = self._create_default_profile(user_id)
                
                # Apply preference decay
                profile_data = self._apply_preference_decay(profile_data)
                
                # Cache profile
                self.user_profiles[user_id] = profile_data
                self.last_profile_update[user_id] = datetime.now()
                
                return profile_data
                
        except Exception as e:
            logger.error(f"User profile retrieval failed: {e}")
            return self._create_default_profile(user_id)
    
    async def _load_user_profile_from_db(
        self,
        session,
        user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Load user profile from database
        """
        try:
            # This would query actual user preference tables
            # For now, return None to trigger default profile creation
            return None
            
        except Exception as e:
            logger.error(f"Database profile loading failed: {e}")
            return None
    
    def _create_default_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Create default user profile
        """
        return {
            "user_id": user_id,
            "preferences": {
                "content_categories": self.content_categories.copy(),
                "priority_topics": [],
                "excluded_topics": [],
                "preferred_companies": [],
                "risk_tolerance": "medium",
                "content_volume": "normal"
            },
            "behavior_patterns": {
                "interaction_history": [],
                "content_engagement": defaultdict(float),
                "time_preferences": {
                    "morning": 0.3,
                    "afternoon": 0.4,
                    "evening": 0.3
                },
                "device_types": [],
                "session_duration_avg": 300  # seconds
            },
            "demographics": {
                "role": "analyst",
                "experience_level": "intermediate",
                "industry_focus": []
            },
            "last_updated": datetime.now(),
            "interaction_count": 0
        }
    
    def _apply_preference_decay(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply time-based decay to user preferences
        """
        try:
            last_updated = profile.get("last_updated")
            if not last_updated:
                return profile
            
            days_since_update = (datetime.now() - last_updated).days
            
            if days_since_update > 0:
                decay_factor = self.preference_decay ** days_since_update
                
                # Decay content engagement scores
                engagement = profile["behavior_patterns"]["content_engagement"]
                for category in engagement:
                    engagement[category] *= decay_factor
                
                profile["last_updated"] = datetime.now()
            
            return profile
            
        except Exception as e:
            logger.error(f"Preference decay application failed: {e}")
            return profile
    
    async def _get_available_content(self, feed_date: datetime.date) -> List[Dict[str, Any]]:
        """
        Get available content for the feed date
        """
        try:
            content_items = []
            
            # Calculate date range
            start_date = feed_date - timedelta(days=self.content_freshness_days)
            end_date = feed_date + timedelta(days=1)
            
            async with get_db_session() as session:
                # Get corruption alerts
                corruption_query = session.query(
                    # This would be actual content queries
                    # For now, generate mock content
                )
                
                # Mock content generation for demonstration
                content_items = self._generate_mock_content(feed_date)
            
            return content_items
            
        except Exception as e:
            logger.error(f"Available content retrieval failed: {e}")
            return []
    
    def _generate_mock_content(self, feed_date: datetime.date) -> List[Dict[str, Any]]:
        """
        Generate mock content for demonstration
        """
        content_templates = [
            {
                "id": f"alert_{feed_date}_1",
                "category": "corruption_alerts",
                "title": "Suspicious Customs Declaration Pattern Detected",
                "summary": "Multiple declarations with identical values suggest potential fraud",
                "content": "Analysis of recent customs data revealed unusual patterns...",
                "priority": "high",
                "companies": ["Company A", "Company B"],
                "timestamp": datetime.combine(feed_date, datetime.min.time()),
                "source": "corruption_detector_agent"
            },
            {
                "id": f"news_{feed_date}_1",
                "category": "company_news",
                "title": "Major Trade Company Announces Restructuring",
                "summary": "Company X begins major operational changes",
                "content": "Following recent regulatory scrutiny...",
                "priority": "medium",
                "companies": ["Company X"],
                "timestamp": datetime.combine(feed_date, datetime.min.time()),
                "source": "miner_agent"
            },
            {
                "id": f"trend_{feed_date}_1",
                "category": "market_trends",
                "title": "Import Volume Increases 15% in Electronics Sector",
                "summary": "Market analysis shows significant growth",
                "content": "Customs data indicates strong demand...",
                "priority": "low",
                "companies": [],
                "timestamp": datetime.combine(feed_date, datetime.min.time()),
                "source": "forecast_agent"
            },
            {
                "id": f"regulatory_{feed_date}_1",
                "category": "regulatory_changes",
                "title": "New Customs Regulations Take Effect",
                "summary": "Updated compliance requirements announced",
                "content": "The customs authority has issued new guidelines...",
                "priority": "high",
                "companies": [],
                "timestamp": datetime.combine(feed_date, datetime.min.time()),
                "source": "retriever_agent"
            }
        ]
        
        return content_templates
    
    async def _score_content_for_user(
        self,
        content_items: List[Dict[str, Any]],
        user_profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Score content items for user relevance
        """
        try:
            scored_items = []
            
            preferences = user_profile["preferences"]
            behavior = user_profile["behavior_patterns"]
            
            for item in content_items:
                # Base score from category preference
                category = item["category"]
                base_score = preferences["content_categories"].get(category, {}).get("weight", 0.5)
                
                # Adjust for user engagement history
                engagement_multiplier = behavior["content_engagement"].get(category, 1.0)
                
                # Priority multiplier
                priority_multipliers = {
                    "low": 0.7,
                    "medium": 1.0,
                    "high": 1.3,
                    "urgent": 1.5
                }
                priority_multiplier = priority_multipliers.get(item.get("priority", "medium"), 1.0)
                
                # Company relevance
                company_relevance = self._calculate_company_relevance(
                    item.get("companies", []),
                    preferences.get("preferred_companies", [])
                )
                
                # Topic relevance
                topic_relevance = self._calculate_topic_relevance(
                    item,
                    preferences.get("priority_topics", []),
                    preferences.get("excluded_topics", [])
                )
                
                # Time preference
                time_relevance = self._calculate_time_relevance(item, behavior)
                
                # Calculate final score
                final_score = (
                    base_score * 0.3 +
                    engagement_multiplier * 0.25 +
                    priority_multiplier * 0.2 +
                    company_relevance * 0.15 +
                    topic_relevance * 0.05 +
                    time_relevance * 0.05
                )
                
                scored_item = {
                    **item,
                    "relevance_score": final_score,
                    "scoring_factors": {
                        "base_category": base_score,
                        "engagement": engagement_multiplier,
                        "priority": priority_multiplier,
                        "company_relevance": company_relevance,
                        "topic_relevance": topic_relevance,
                        "time_relevance": time_relevance
                    }
                }
                
                scored_items.append(scored_item)
            
            return scored_items
            
        except Exception as e:
            logger.error(f"Content scoring failed: {e}")
            return content_items
    
    def _calculate_company_relevance(
        self,
        item_companies: List[str],
        preferred_companies: List[str]
    ) -> float:
        """
        Calculate relevance based on company preferences
        """
        try:
            if not preferred_companies:
                return 0.5  # Neutral if no preferences
            
            if not item_companies:
                return 0.3  # Lower if no companies mentioned
            
            # Check for matches
            matches = set(item_companies) & set(preferred_companies)
            
            if matches:
                return 1.0  # Full relevance if preferred company mentioned
            else:
                return 0.4  # Lower relevance for non-preferred companies
                
        except Exception as e:
            return 0.5
    
    def _calculate_topic_relevance(
        self,
        item: Dict[str, Any],
        priority_topics: List[str],
        excluded_topics: List[str]
    ) -> float:
        """
        Calculate relevance based on topic preferences
        """
        try:
            title = item.get("title", "").lower()
            content = item.get("content", "").lower()
            full_text = title + " " + content
            
            # Check excluded topics first
            for excluded in excluded_topics:
                if excluded.lower() in full_text:
                    return 0.1  # Very low relevance for excluded topics
            
            # Check priority topics
            priority_matches = 0
            for priority in priority_topics:
                if priority.lower() in full_text:
                    priority_matches += 1
            
            if priority_matches > 0:
                return min(1.0, 0.7 + (priority_matches * 0.1))  # Bonus for priority topics
            
            return 0.5  # Neutral relevance
            
        except Exception as e:
            return 0.5
    
    def _calculate_time_relevance(
        self,
        item: Dict[str, Any],
        behavior: Dict[str, Any]
    ) -> float:
        """
        Calculate relevance based on time preferences
        """
        try:
            timestamp = item.get("timestamp")
            if not timestamp:
                return 0.5
            
            hour = timestamp.hour
            time_preferences = behavior.get("time_preferences", {})
            
            # Determine time of day
            if 6 <= hour < 12:
                time_slot = "morning"
            elif 12 <= hour < 18:
                time_slot = "afternoon"
            else:
                time_slot = "evening"
            
            return time_preferences.get(time_slot, 0.3)
            
        except Exception as e:
            return 0.5
    
    def _select_feed_content(
        self,
        scored_content: List[Dict[str, Any]],
        user_profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Select content for the feed based on scores and diversity
        """
        try:
            preferences = user_profile["preferences"]
            content_volume = preferences.get("content_volume", "normal")
            
            # Determine feed size
            volume_multipliers = {
                "minimal": 0.5,
                "normal": 1.0,
                "extensive": 1.5
            }
            
            max_items = int(self.max_feed_items * volume_multipliers.get(content_volume, 1.0))
            
            # Sort by relevance score
            sorted_content = sorted(scored_content, key=lambda x: x["relevance_score"], reverse=True)
            
            # Ensure diversity - select from different categories
            selected_items = []
            category_counts = defaultdict(int)
            
            for item in sorted_content:
                category = item["category"]
                
                # Allow maximum 40% from any single category
                max_per_category = max(2, max_items // 5)
                
                if category_counts[category] < max_per_category:
                    selected_items.append(item)
                    category_counts[category] += 1
                    
                    if len(selected_items) >= max_items:
                        break
            
            return selected_items
            
        except Exception as e:
            logger.error(f"Content selection failed: {e}")
            return scored_content[:self.max_feed_items]
    
    def _format_as_newspaper(
        self,
        selected_content: List[Dict[str, Any]],
        user_profile: Dict[str, Any],
        feed_date: datetime.date
    ) -> Dict[str, Any]:
        """
        Format selected content as a personalized newspaper
        """
        try:
            # Group content by category
            sections = defaultdict(list)
            
            for item in selected_content:
                sections[item["category"]].append(item)
            
            # Create newspaper structure
            newspaper = {
                "title": f"Predator Analytics Daily - {feed_date.strftime('%B %d, %Y')}",
                "user_id": user_profile["user_id"],
                "generated_at": datetime.now().isoformat(),
                "total_items": len(selected_content),
                "sections": {},
                "summary": {
                    "top_story": None,
                    "breaking_news": [],
                    "key_insights": []
                }
            }
            
            # Format each section
            for category, items in sections.items():
                # Sort items within category by score
                sorted_items = sorted(items, key=lambda x: x["relevance_score"], reverse=True)
                
                section_info = self.content_categories.get(category, {})
                newspaper["sections"][category] = {
                    "title": section_info.get("description", category.replace("_", " ").title()),
                    "description": section_info.get("description", ""),
                    "item_count": len(sorted_items),
                    "items": [
                        {
                            "id": item["id"],
                            "title": item["title"],
                            "summary": item["summary"],
                            "content": item["content"],
                            "priority": item["priority"],
                            "companies": item.get("companies", []),
                            "timestamp": item["timestamp"].isoformat(),
                            "source": item["source"],
                            "relevance_score": item["relevance_score"]
                        }
                        for item in sorted_items
                    ]
                }
            
            # Identify top story (highest scoring item)
            if selected_content:
                top_story = max(selected_content, key=lambda x: x["relevance_score"])
                newspaper["summary"]["top_story"] = {
                    "id": top_story["id"],
                    "title": top_story["title"],
                    "summary": top_story["summary"],
                    "category": top_story["category"]
                }
            
            # Identify breaking news (high priority items)
            breaking_news = [
                item for item in selected_content
                if item.get("priority") in ["high", "urgent"]
            ][:3]  # Top 3
            
            newspaper["summary"]["breaking_news"] = [
                {
                    "id": item["id"],
                    "title": item["title"],
                    "category": item["category"]
                }
                for item in breaking_news
            ]
            
            # Generate key insights
            newspaper["summary"]["key_insights"] = self._generate_key_insights(selected_content)
            
            return newspaper
            
        except Exception as e:
            logger.error(f"Newspaper formatting failed: {e}")
            return {"error": str(e)}
    
    def _generate_key_insights(self, content_items: List[Dict[str, Any]]) -> List[str]:
        """
        Generate key insights from the content
        """
        try:
            insights = []
            
            # Count by category
            category_counts = defaultdict(int)
            for item in content_items:
                category_counts[item["category"]] += 1
            
            # Generate insights based on content patterns
            if category_counts.get("corruption_alerts", 0) > 2:
                insights.append("Multiple corruption alerts detected - increased monitoring recommended")
            
            if category_counts.get("regulatory_changes", 0) > 0:
                insights.append("New regulatory changes may impact compliance requirements")
            
            if category_counts.get("market_trends", 0) > 1:
                insights.append("Several market trends identified - potential opportunities or risks")
            
            # Add general insights
            total_items = len(content_items)
            if total_items > 10:
                insights.append(f"High activity day with {total_items} relevant updates")
            elif total_items < 5:
                insights.append("Quiet day with minimal relevant updates")
            
            return insights[:3]  # Limit to 3 insights
            
        except Exception as e:
            return ["Content analysis completed"]
    
    async def _update_user_engagement(
        self,
        user_id: str,
        selected_content: List[Dict[str, Any]]
    ):
        """
        Update user engagement tracking
        """
        try:
            if user_id not in self.user_profiles:
                return
            
            profile = self.user_profiles[user_id]
            behavior = profile["behavior_patterns"]
            
            # Update engagement scores
            for item in selected_content:
                category = item["category"]
                # Assume some engagement (in real system, this would come from actual user interactions)
                engagement_score = item["relevance_score"] * 0.1  # Small boost for being selected
                behavior["content_engagement"][category] += engagement_score
            
            # Update interaction count
            profile["interaction_count"] += 1
            
        except Exception as e:
            logger.error(f"User engagement update failed: {e}")
    
    async def _handle_preference_update(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle user preference update
        """
        try:
            user_id = message.content.get("user_id")
            preferences = message.content.get("preferences", {})
            
            if not user_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "user_id required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Update user preferences
            updated_profile = await self._update_user_preferences(user_id, preferences)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "preference_update_response",
                    "user_id": user_id,
                    "updated_preferences": updated_profile["preferences"]
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Preference update failed: {e}")
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
    
    async def _update_user_preferences(
        self,
        user_id: str,
        new_preferences: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update user preferences in profile
        """
        try:
            profile = await self._get_user_profile(user_id)
            
            # Update preferences
            for key, value in new_preferences.items():
                if key in profile["preferences"]:
                    if isinstance(profile["preferences"][key], dict):
                        profile["preferences"][key].update(value)
                    else:
                        profile["preferences"][key] = value
            
            # Mark as updated
            profile["last_updated"] = datetime.now()
            
            # Update cache
            self.user_profiles[user_id] = profile
            self.last_profile_update[user_id] = datetime.now()
            
            return profile
            
        except Exception as e:
            logger.error(f"User preference update failed: {e}")
            return self._create_default_profile(user_id)
    
    async def _handle_profile_request(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle user profile request
        """
        try:
            user_id = message.content.get("user_id")
            
            if not user_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "user_id required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Get user profile
            profile = await self._get_user_profile(user_id)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "user_profile_response",
                    "user_id": user_id,
                    "profile": profile
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Profile request failed: {e}")
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
    
    async def _handle_feed_customization(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle feed customization request
        """
        try:
            user_id = message.content.get("user_id")
            customization = message.content.get("customization", {})
            
            if not user_id:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "user_id required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Apply customization
            customized_feed = await self._apply_feed_customization(user_id, customization)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "feed_customization_response",
                    "user_id": user_id,
                    "customization": customization,
                    "customized_feed": customized_feed
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Feed customization failed: {e}")
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
    
    async def _apply_feed_customization(
        self,
        user_id: str,
        customization: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply customization to feed generation
        """
        try:
            # This would modify the feed generation parameters
            # For now, return a mock response
            return {
                "customization_applied": True,
                "parameters": customization,
                "estimated_impact": "Feed will be adjusted based on your preferences"
            }
            
        except Exception as e:
            logger.error(f"Feed customization application failed: {e}")
            return {"error": str(e)}
    
    async def _handle_performance_analysis(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle feed performance analysis request
        """
        try:
            user_id = message.content.get("user_id")
            analysis_period_days = message.content.get("analysis_period_days", 30)
            
            # Analyze feed performance
            performance = await self._analyze_feed_performance(user_id, analysis_period_days)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "performance_analysis_response",
                    "user_id": user_id,
                    "analysis_period_days": analysis_period_days,
                    "performance": performance
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Performance analysis failed: {e}")
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
    
    async def _analyze_feed_performance(
        self,
        user_id: str,
        analysis_period_days: int
    ) -> Dict[str, Any]:
        """
        Analyze feed performance for user
        """
        try:
            profile = await self._get_user_profile(user_id)
            
            # Mock performance analysis
            performance = {
                "engagement_rate": 0.75,
                "content_relevance": 0.82,
                "feed_completion_rate": 0.65,
                "category_performance": {},
                "recommendations": []
            }
            
            # Category performance
            engagement = profile["behavior_patterns"]["content_engagement"]
            for category in self.content_categories:
                performance["category_performance"][category] = {
                    "engagement_score": engagement.get(category, 0),
                    "items_served": 10,  # Mock
                    "avg_relevance": 0.8  # Mock
                }
            
            # Generate recommendations
            low_engagement = [
                cat for cat, score in engagement.items()
                if score < 0.5
            ]
            
            if low_engagement:
                performance["recommendations"].append(
                    f"Consider reducing {', '.join(low_engagement)} content"
                )
            
            high_engagement = [
                cat for cat, score in engagement.items()
                if score > 1.0
            ]
            
            if high_engagement:
                performance["recommendations"].append(
                    f"Increase {', '.join(high_engagement)} content"
                )
            
            return performance
            
        except Exception as e:
            logger.error(f"Feed performance analysis failed: {e}")
            return {"error": str(e)}


# ========== TEST ==========
if __name__ == "__main__":
    async def test_personal_feed_agent():
        # Initialize personal feed agent
        agent = PersonalFeedAgent()
        
        # Test daily feed generation
        test_message = AgentMessage(
            id="test_feed",
            from_agent="test",
            to_agent="personal_feed_agent",
            content={
                "type": "generate_daily_feed",
                "user_id": "test_user_123"
            },
            timestamp=datetime.now()
        )
        
        print("Testing personal feed agent...")
        async for response in agent.process_message(test_message):
            print(f"Response type: {response.content.get('type')}")
            if response.content.get("type") == "daily_feed_response":
                feed = response.content.get("feed", {})
                print(f"Feed title: {feed.get('title')}")
                print(f"Total items: {feed.get('total_items', 0)}")
                print(f"Sections: {list(feed.get('sections', {}).keys())}")
        
        print("Personal feed agent test completed")
    
    # Run test
    asyncio.run(test_personal_feed_agent())
