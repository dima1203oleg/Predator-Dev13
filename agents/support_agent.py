"""
Support Agent: User support and help system management
Handles user queries, troubleshooting, knowledge base, and support automation
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
from ..api.models import SupportTicket, KnowledgeBase, UserQuery

logger = logging.getLogger(__name__)


class SupportAgent(BaseAgent):
    """
    Support Agent for user support and help system management
    Handles user queries, troubleshooting, knowledge base, and support automation
    """
    
    def __init__(
        self,
        agent_id: str = "support_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # Support configuration
        self.support_config = {
            "support_channels": self.config.get("support_channels", {
                "chat": True,
                "email": True,
                "phone": True,
                "ticketing": True,
                "knowledge_base": True,
                "community_forum": True,
                "video_call": True
            }),
            "query_handling": self.config.get("query_handling", {
                "natural_language_processing": True,
                "intent_recognition": True,
                "sentiment_analysis": True,
                "auto_routing": True,
                "escalation_rules": True,
                "priority_assignment": True
            }),
            "knowledge_base": self.config.get("knowledge_base", {
                "faq_database": True,
                "troubleshooting_guides": True,
                "video_tutorials": True,
                "api_documentation": True,
                "user_manuals": True,
                "search_indexing": True
            }),
            "automation": self.config.get("automation", {
                "auto_responses": True,
                "smart_suggestions": True,
                "predictive_support": True,
                "self_service_portal": True,
                "chatbot_integration": True,
                "voice_assistant": True
            }),
            "analytics": self.config.get("analytics", {
                "query_analytics": True,
                "satisfaction_scores": True,
                "resolution_metrics": True,
                "support_trends": True,
                "performance_monitoring": True
            }),
            "escalation": self.config.get("escalation", {
                "automatic_escalation": True,
                "expert_routing": True,
                "crisis_management": True,
                "stakeholder_alerts": True,
                "backup_support": True
            }),
            "multilingual_support": self.config.get("multilingual_support", {
                "language_detection": True,
                "translation_services": True,
                "localized_content": True,
                "cultural_adaptation": True,
                "rtl_support": True
            }),
            "processing": self.config.get("processing", {
                "parallel_query_processing": 4,
                "response_timeout_seconds": 30,
                "max_concurrent_queries": 100,
                "cache_ttl_seconds": 3600
            })
        }
        
        # Support management
        self.support_tickets = {}
        self.knowledge_base = {}
        self.user_queries = deque(maxlen=100000)
        self.support_analytics = {}
        
        # Background tasks
        self.query_processor_task = None
        self.ticket_monitor_task = None
        self.knowledge_updater_task = None
        
        logger.info(f"Support Agent initialized: {agent_id}")
    
    async def start(self):
        """
        Start the support agent
        """
        await super().start()
        
        # Load support data
        await self._load_support_data()
        
        # Start background tasks
        self.query_processor_task = asyncio.create_task(self._continuous_query_processor())
        self.ticket_monitor_task = asyncio.create_task(self._continuous_ticket_monitor())
        self.knowledge_updater_task = asyncio.create_task(self._continuous_knowledge_updater())
        
        logger.info("Support agent started")
    
    async def stop(self):
        """
        Stop the support agent
        """
        if self.query_processor_task:
            self.query_processor_task.cancel()
            try:
                await self.query_processor_task
            except asyncio.CancelledError:
                pass
        
        if self.ticket_monitor_task:
            self.ticket_monitor_task.cancel()
            try:
                await self.ticket_monitor_task
            except asyncio.CancelledError:
                pass
        
        if self.knowledge_updater_task:
            self.knowledge_updater_task.cancel()
            try:
                await self.knowledge_updater_task
            except asyncio.CancelledError:
                pass
        
        await super().stop()
        logger.info("Support agent stopped")
    
    async def _load_support_data(self):
        """
        Load existing support data and configurations
        """
        try:
            # Load support tickets, knowledge base, analytics, etc.
            await self._load_support_tickets()
            await self._load_knowledge_base()
            await self._load_support_analytics()
            
            logger.info("Support data loaded")
            
        except Exception as e:
            logger.error(f"Support data loading failed: {e}")
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process support requests
        """
        try:
            message_type = message.content.get("type", "")
            
            if message_type == "handle_query":
                async for response in self._handle_user_query(message):
                    yield response
                    
            elif message_type == "create_ticket":
                async for response in self._handle_ticket_creation(message):
                    yield response
                    
            elif message_type == "search_knowledge":
                async for response in self._handle_knowledge_search(message):
                    yield response
                    
            elif message_type == "generate_response":
                async for response in self._handle_response_generation(message):
                    yield response
                    
            elif message_type == "analyze_feedback":
                async for response in self._handle_feedback_analysis(message):
                    yield response
                    
            elif message_type == "escalate_issue":
                async for response in self._handle_issue_escalation(message):
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
            logger.error(f"Support processing failed: {e}")
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
    
    async def _handle_user_query(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle user query processing
        """
        try:
            user_id = message.content.get("user_id")
            query_text = message.content.get("query_text")
            channel = message.content.get("channel", "chat")
            language = message.content.get("language", "en")
            
            # Process user query
            query_result = await self._process_user_query(user_id, query_text, channel, language)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "query_response",
                    "query_result": query_result,
                    "user_id": user_id,
                    "channel": channel
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"User query handling failed: {e}")
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
    
    async def _process_user_query(
        self,
        user_id: str,
        query_text: str,
        channel: str,
        language: str
    ) -> Dict[str, Any]:
        """
        Process user query and generate response
        """
        try:
            processing_start = datetime.now()
            
            # Detect language if not provided
            if language == "auto":
                language = await self._detect_language(query_text)
            
            # Translate query if needed
            if language != "en":
                query_text_en = await self._translate_query(query_text, language, "en")
            else:
                query_text_en = query_text
            
            # Analyze query intent and sentiment
            intent_analysis = await self._analyze_query_intent(query_text_en)
            sentiment_analysis = await self._analyze_query_sentiment(query_text_en)
            
            # Search knowledge base
            kb_results = await self._search_knowledge_base(query_text_en, intent_analysis)
            
            # Generate response
            response = await self._generate_support_response(
                query_text_en, intent_analysis, sentiment_analysis, kb_results, language
            )
            
            # Determine if escalation needed
            escalation_needed = await self._check_escalation_needed(
                intent_analysis, sentiment_analysis, kb_results
            )
            
            # Create support ticket if needed
            ticket_id = None
            if escalation_needed or intent_analysis.get("complexity") == "high":
                ticket_id = await self._create_support_ticket(
                    user_id, query_text, intent_analysis, sentiment_analysis, channel
                )
            
            # Log query
            query_log = {
                "user_id": user_id,
                "query_text": query_text,
                "language": language,
                "channel": channel,
                "intent": intent_analysis,
                "sentiment": sentiment_analysis,
                "kb_results_count": len(kb_results),
                "response_generated": bool(response),
                "escalation_needed": escalation_needed,
                "ticket_id": ticket_id,
                "processing_time": (datetime.now() - processing_start).total_seconds(),
                "timestamp": datetime.now()
            }
            
            self.user_queries.append(query_log)
            
            return {
                "response": response,
                "language": language,
                "intent": intent_analysis,
                "sentiment": sentiment_analysis,
                "knowledge_base_results": kb_results[:5],  # Top 5 results
                "escalation_needed": escalation_needed,
                "ticket_id": ticket_id,
                "processing_time": query_log["processing_time"],
                "channel": channel
            }
            
        except Exception as e:
            logger.error(f"User query processing failed: {e}")
            return {"error": str(e), "query_text": query_text}
    
    async def _detect_language(self, text: str) -> str:
        """
        Detect language of the query
        """
        try:
            # Simple language detection based on character patterns
            # In production, would use a proper language detection library
            
            if re.search(r'[а-яё]', text.lower()):
                return "ru"
            elif re.search(r'[ğüşöçı]', text.lower()):
                return "tr"
            elif re.search(r'[ñáéíóúü]', text.lower()):
                return "es"
            else:
                return "en"
                
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            return "en"
    
    async def _translate_query(self, text: str, from_lang: str, to_lang: str) -> str:
        """
        Translate query text
        """
        try:
            # Simple translation mapping for common phrases
            # In production, would use translation services
            
            translations = {
                "ru": {
                    "помощь": "help",
                    "ошибка": "error",
                    "проблема": "problem",
                    "не работает": "not working"
                }
            }
            
            if from_lang in translations:
                for ru_word, en_word in translations[from_lang].items():
                    text = re.sub(r'\b' + ru_word + r'\b', en_word, text, flags=re.IGNORECASE)
            
            return text
            
        except Exception as e:
            logger.error(f"Query translation failed: {e}")
            return text
    
    async def _analyze_query_intent(self, query_text: str) -> Dict[str, Any]:
        """
        Analyze query intent
        """
        try:
            # Simple intent classification
            # In production, would use ML models
            
            query_lower = query_text.lower()
            
            intent = {
                "primary": "general_inquiry",
                "category": "support",
                "complexity": "low",
                "urgency": "normal",
                "entities": [],
                "keywords": []
            }
            
            # Classify intent
            if any(word in query_lower for word in ["error", "bug", "crash", "fail", "broken"]):
                intent["primary"] = "technical_issue"
                intent["category"] = "technical_support"
                intent["complexity"] = "medium"
                intent["urgency"] = "high"
                
            elif any(word in query_lower for word in ["how to", "how do", "guide", "tutorial"]):
                intent["primary"] = "how_to_question"
                intent["category"] = "documentation"
                intent["complexity"] = "low"
                
            elif any(word in query_lower for word in ["billing", "payment", "cost", "price"]):
                intent["primary"] = "billing_inquiry"
                intent["category"] = "billing"
                intent["complexity"] = "medium"
                
            elif any(word in query_lower for word in ["feature", "enhancement", "request"]):
                intent["primary"] = "feature_request"
                intent["category"] = "product"
                intent["complexity"] = "medium"
            
            # Extract keywords
            intent["keywords"] = re.findall(r'\b\w{4,}\b', query_lower)
            
            return intent
            
        except Exception as e:
            logger.error(f"Query intent analysis failed: {e}")
            return {"primary": "unknown", "error": str(e)}
    
    async def _analyze_query_sentiment(self, query_text: str) -> Dict[str, Any]:
        """
        Analyze query sentiment
        """
        try:
            # Simple sentiment analysis
            # In production, would use sentiment analysis models
            
            query_lower = query_text.lower()
            
            sentiment = {
                "score": 0.0,  # -1 to 1
                "label": "neutral",
                "confidence": 0.5,
                "emotions": []
            }
            
            # Positive indicators
            positive_words = ["good", "great", "excellent", "thanks", "helpful", "appreciate"]
            positive_count = sum(1 for word in positive_words if word in query_lower)
            
            # Negative indicators
            negative_words = ["bad", "terrible", "awful", "frustrated", "angry", "hate", "worst"]
            negative_count = sum(1 for word in negative_words if word in query_lower)
            
            # Calculate sentiment score
            total_sentiment_words = positive_count + negative_count
            if total_sentiment_words > 0:
                sentiment["score"] = (positive_count - negative_count) / total_sentiment_words
            else:
                sentiment["score"] = 0.0
            
            # Determine label
            if sentiment["score"] > 0.2:
                sentiment["label"] = "positive"
            elif sentiment["score"] < -0.2:
                sentiment["label"] = "negative"
            else:
                sentiment["label"] = "neutral"
            
            # Detect emotions
            if "frustrated" in query_lower or "angry" in query_lower:
                sentiment["emotions"].append("anger")
            if "worried" in query_lower or "concerned" in query_lower:
                sentiment["emotions"].append("fear")
            
            return sentiment
            
        except Exception as e:
            logger.error(f"Query sentiment analysis failed: {e}")
            return {"score": 0.0, "label": "neutral", "error": str(e)}
    
    async def _search_knowledge_base(
        self,
        query_text: str,
        intent_analysis: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Search knowledge base for relevant information
        """
        try:
            results = []
            
            # Simple keyword-based search
            # In production, would use full-text search with embeddings
            
            query_keywords = set(intent_analysis.get("keywords", []))
            query_keywords.update(re.findall(r'\b\w{4,}\b', query_text.lower()))
            
            for kb_id, kb_entry in self.knowledge_base.items():
                kb_keywords = set(kb_entry.get("keywords", []))
                kb_title = kb_entry.get("title", "").lower()
                kb_content = kb_entry.get("content", "").lower()
                
                # Calculate relevance score
                keyword_overlap = len(query_keywords.intersection(kb_keywords))
                title_match = any(kw in kb_title for kw in query_keywords)
                content_match = any(kw in kb_content for kw in query_keywords)
                
                relevance_score = keyword_overlap + (2 if title_match else 0) + (1 if content_match else 0)
                
                if relevance_score > 0:
                    results.append({
                        "kb_id": kb_id,
                        "title": kb_entry.get("title"),
                        "content": kb_entry.get("content")[:500] + "..." if len(kb_entry.get("content", "")) > 500 else kb_entry.get("content"),
                        "url": kb_entry.get("url"),
                        "category": kb_entry.get("category"),
                        "relevance_score": relevance_score,
                        "type": kb_entry.get("type", "article")
                    })
            
            # Sort by relevance
            results.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            return results[:10]  # Return top 10 results
            
        except Exception as e:
            logger.error(f"Knowledge base search failed: {e}")
            return []
    
    async def _generate_support_response(
        self,
        query_text: str,
        intent_analysis: Dict[str, Any],
        sentiment_analysis: Dict[str, Any],
        kb_results: List[Dict[str, Any]],
        language: str
    ) -> Dict[str, Any]:
        """
        Generate support response
        """
        try:
            response = {
                "text": "",
                "type": "text",
                "confidence": 0.8,
                "suggested_actions": [],
                "related_articles": []
            }
            
            # Generate response based on intent
            intent = intent_analysis.get("primary")
            
            if intent == "technical_issue":
                response["text"] = "I'm sorry you're experiencing a technical issue. Let me help you troubleshoot this."
                response["suggested_actions"] = ["run_diagnostics", "check_logs", "restart_service"]
                
            elif intent == "how_to_question":
                response["text"] = "I'd be happy to guide you through this process."
                response["suggested_actions"] = ["view_tutorial", "step_by_step_guide"]
                
            elif intent == "billing_inquiry":
                response["text"] = "I'll help you with your billing question."
                response["suggested_actions"] = ["view_invoice", "update_payment_method"]
                
            else:
                response["text"] = "Thank you for your question. Let me assist you with that."
            
            # Add empathy for negative sentiment
            if sentiment_analysis.get("label") == "negative":
                response["text"] = "I understand this is frustrating. " + response["text"]
            
            # Include knowledge base results
            if kb_results:
                response["text"] += " Here are some relevant articles that might help:"
                response["related_articles"] = [
                    {"title": kb["title"], "url": kb["url"]}
                    for kb in kb_results[:3]
                ]
            
            # Translate response if needed
            if language != "en":
                response["text"] = await self._translate_response(response["text"], "en", language)
            
            return response
            
        except Exception as e:
            logger.error(f"Support response generation failed: {e}")
            return {"text": "I'm sorry, I'm having trouble generating a response right now. Please try again.", "error": str(e)}
    
    async def _check_escalation_needed(
        self,
        intent_analysis: Dict[str, Any],
        sentiment_analysis: Dict[str, Any],
        kb_results: List[Dict[str, Any]]
    ) -> bool:
        """
        Check if issue needs escalation
        """
        try:
            # Escalation criteria
            escalation_reasons = []
            
            # High complexity
            if intent_analysis.get("complexity") == "high":
                escalation_reasons.append("high_complexity")
            
            # Negative sentiment
            if sentiment_analysis.get("label") == "negative" and sentiment_analysis.get("score", 0) < -0.5:
                escalation_reasons.append("negative_sentiment")
            
            # No relevant KB results
            if len(kb_results) == 0 or max(r.get("relevance_score", 0) for r in kb_results) < 2:
                escalation_reasons.append("no_kb_results")
            
            # High urgency
            if intent_analysis.get("urgency") == "high":
                escalation_reasons.append("high_urgency")
            
            return len(escalation_reasons) > 0
            
        except Exception as e:
            logger.error(f"Escalation check failed: {e}")
            return False
    
    async def _create_support_ticket(
        self,
        user_id: str,
        query_text: str,
        intent_analysis: Dict[str, Any],
        sentiment_analysis: Dict[str, Any],
        channel: str
    ) -> str:
        """
        Create support ticket
        """
        try:
            ticket_id = str(uuid.uuid4())
            
            ticket = {
                "ticket_id": ticket_id,
                "user_id": user_id,
                "query_text": query_text,
                "intent": intent_analysis,
                "sentiment": sentiment_analysis,
                "channel": channel,
                "status": "open",
                "priority": intent_analysis.get("urgency", "normal"),
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "assigned_to": None,
                "escalation_reason": "automated_creation"
            }
            
            self.support_tickets[ticket_id] = ticket
            
            return ticket_id
            
        except Exception as e:
            logger.error(f"Support ticket creation failed: {e}")
            return None
    
    async def _translate_response(self, text: str, from_lang: str, to_lang: str) -> str:
        """
        Translate response text
        """
        try:
            # Simple translation for common responses
            # In production, would use translation services
            
            if to_lang == "ru":
                translations = {
                    "I'm sorry you're experiencing": "Извините, что у вас возникла",
                    "Let me help you": "Позвольте мне помочь вам",
                    "Thank you for your question": "Спасибо за ваш вопрос"
                }
                
                for en, ru in translations.items():
                    text = text.replace(en, ru)
            
            return text
            
        except Exception as e:
            logger.error(f"Response translation failed: {e}")
            return text
    
    # Background monitoring tasks
    async def _continuous_query_processor(self):
        """
        Continuous query processing
        """
        try:
            while True:
                try:
                    # Process queued queries
                    await self._process_queued_queries()
                    
                    # Update query analytics
                    await self._update_query_analytics()
                    
                except Exception as e:
                    logger.error(f"Query processor error: {e}")
                
                # Process every 10 seconds
                await asyncio.sleep(10)
                
        except asyncio.CancelledError:
            logger.info("Query processor cancelled")
            raise
    
    async def _continuous_ticket_monitor(self):
        """
        Continuous ticket monitoring
        """
        try:
            while True:
                try:
                    # Monitor ticket status
                    await self._monitor_ticket_status()
                    
                    # Auto-escalate tickets
                    await self._auto_escalate_tickets()
                    
                except Exception as e:
                    logger.error(f"Ticket monitor error: {e}")
                
                # Monitor every 5 minutes
                await asyncio.sleep(300)
                
        except asyncio.CancelledError:
            logger.info("Ticket monitor cancelled")
            raise
    
    async def _continuous_knowledge_updater(self):
        """
        Continuous knowledge base updates
        """
        try:
            while True:
                try:
                    # Update knowledge base
                    await self._update_knowledge_base()
                    
                    # Generate new KB articles
                    await self._generate_kb_articles()
                    
                except Exception as e:
                    logger.error(f"Knowledge updater error: {e}")
                
                # Update every hour
                await asyncio.sleep(3600)
                
        except asyncio.CancelledError:
            logger.info("Knowledge updater cancelled")
            raise
    
    # Additional helper methods would continue...
    
    async def _load_support_tickets(self):
        """Load support tickets"""
        try:
            # Implementation for loading support tickets
            pass
        except Exception as e:
            logger.error(f"Support tickets loading failed: {e}")
    
    async def _load_knowledge_base(self):
        """Load knowledge base"""
        try:
            # Implementation for loading knowledge base
            pass
        except Exception as e:
            logger.error(f"Knowledge base loading failed: {e}"}
    
    async def _load_support_analytics(self):
        """Load support analytics"""
        try:
            # Implementation for loading support analytics
            pass
        except Exception as e:
            logger.error(f"Support analytics loading failed: {e}"}


# ========== TEST ==========
if __name__ == "__main__":
    async def test_support_agent():
        # Initialize support agent
        agent = SupportAgent()
        await agent.start()
        
        # Test query handling
        query_message = AgentMessage(
            id="test_query",
            from_agent="test",
            to_agent="support_agent",
            content={
                "type": "handle_query",
                "user_id": "user123",
                "query_text": "I'm having trouble with the dashboard not loading",
                "channel": "chat",
                "language": "en"
            },
            timestamp=datetime.now()
        )
        
        print("Testing support agent...")
        async for response in agent.process_message(query_message):
            print(f"Query response: {response.content.get('type')}")
            query_result = response.content.get('query_result')
            print(f"Query processed: {query_result.get('response', {}).get('text', '')[:100]}...")
        
        # Test ticket creation
        ticket_message = AgentMessage(
            id="test_ticket",
            from_agent="test",
            to_agent="support_agent",
            content={
                "type": "create_ticket",
                "user_id": "user123",
                "title": "Dashboard loading issue",
                "description": "Dashboard not loading after login",
                "priority": "high"
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(ticket_message):
            print(f"Ticket response: {response.content.get('type')}")
            ticket_result = response.content.get('ticket_result')
            print(f"Ticket created: {ticket_result.get('ticket_id') if ticket_result else 'None'}")
        
        # Stop agent
        await agent.stop()
        print("Support agent test completed")
    
    # Run test
    asyncio.run(test_support_agent())
