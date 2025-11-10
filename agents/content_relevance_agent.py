"""
Content Relevance Agent: RAG scorer for content relevance assessment
Evaluates and scores content relevance for retrieval-augmented generation
"""
import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
import asyncio
import json
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import uuid

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

from ..agents.base_agent import BaseAgent, AgentState, AgentMessage
from ..api.database import get_db_session
from ..api.models import CustomsData, Company, HSCode

logger = logging.getLogger(__name__)

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')


class ContentRelevanceAgent(BaseAgent):
    """
    Content Relevance Agent for evaluating content relevance in RAG systems
    Scores documents, chunks, and search results for relevance to queries
    """
    
    def __init__(
        self,
        agent_id: str = "content_relevance_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # Embedding model for semantic similarity
        self.embedding_model_name = self.config.get("embedding_model", "all-MiniLM-L6-v2")
        self.embedding_model = None
        
        # TF-IDF vectorizer for lexical similarity
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        
        # Relevance scoring weights
        self.scoring_weights = {
            "semantic_similarity": 0.4,
            "lexical_overlap": 0.3,
            "context_relevance": 0.2,
            "temporal_relevance": 0.1
        }
        
        # Caching for performance
        self.embedding_cache = {}
        self.tfidf_cache = {}
        
        # Relevance thresholds
        self.relevance_thresholds = {
            "high": 0.8,
            "medium": 0.6,
            "low": 0.4
        }
        
        logger.info(f"Content Relevance Agent initialized: {agent_id}")
    
    async def initialize(self):
        """
        Initialize the agent with required models
        """
        try:
            # Load embedding model
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
            logger.info(f"Loaded embedding model: {self.embedding_model_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {e}")
            self.embedding_model = None
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process content relevance requests
        """
        try:
            message_type = message.content.get("type", "")
            
            if message_type == "score_relevance":
                async for response in self._handle_relevance_scoring(message):
                    yield response
                    
            elif message_type == "rank_documents":
                async for response in self._handle_document_ranking(message):
                    yield response
                    
            elif message_type == "filter_relevant":
                async for response in self._handle_relevance_filtering(message):
                    yield response
                    
            elif message_type == "evaluate_search":
                async for response in self._handle_search_evaluation(message):
                    yield response
                    
            elif message_type == "optimize_retrieval":
                async for response in self._handle_retrieval_optimization(message):
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
            logger.error(f"Content relevance processing failed: {e}")
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
    
    async def _handle_relevance_scoring(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle relevance scoring request
        """
        try:
            query = message.content.get("query", "")
            content = message.content.get("content", "")
            context = message.content.get("context", {})
            
            if not query or not content:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Query and content required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Score relevance
            relevance_score = await self._score_content_relevance(query, content, context)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "relevance_score_response",
                    "query": query,
                    "content_preview": content[:200] + "..." if len(content) > 200 else content,
                    "relevance_score": relevance_score
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Relevance scoring failed: {e}")
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
    
    async def _score_content_relevance(
        self,
        query: str,
        content: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Score content relevance to query
        """
        try:
            relevance_scores = {
                "overall_score": 0.0,
                "semantic_similarity": 0.0,
                "lexical_overlap": 0.0,
                "context_relevance": 0.0,
                "temporal_relevance": 0.0,
                "relevance_level": "low",
                "explanation": "",
                "confidence": 0.0
            }
            
            # Calculate semantic similarity
            semantic_score = await self._calculate_semantic_similarity(query, content)
            relevance_scores["semantic_similarity"] = semantic_score
            
            # Calculate lexical overlap
            lexical_score = self._calculate_lexical_overlap(query, content)
            relevance_scores["lexical_overlap"] = lexical_score
            
            # Calculate context relevance
            context_score = self._calculate_context_relevance(query, content, context)
            relevance_scores["context_relevance"] = context_score
            
            # Calculate temporal relevance
            temporal_score = self._calculate_temporal_relevance(content, context)
            relevance_scores["temporal_relevance"] = temporal_score
            
            # Calculate overall score
            overall_score = (
                semantic_score * self.scoring_weights["semantic_similarity"] +
                lexical_score * self.scoring_weights["lexical_overlap"] +
                context_score * self.scoring_weights["context_relevance"] +
                temporal_score * self.scoring_weights["temporal_relevance"]
            )
            
            relevance_scores["overall_score"] = overall_score
            
            # Determine relevance level
            if overall_score >= self.relevance_thresholds["high"]:
                relevance_scores["relevance_level"] = "high"
            elif overall_score >= self.relevance_thresholds["medium"]:
                relevance_scores["relevance_level"] = "medium"
            else:
                relevance_scores["relevance_level"] = "low"
            
            # Generate explanation
            relevance_scores["explanation"] = self._generate_relevance_explanation(relevance_scores)
            
            # Calculate confidence
            relevance_scores["confidence"] = self._calculate_scoring_confidence(relevance_scores)
            
            return relevance_scores
            
        except Exception as e:
            logger.error(f"Content relevance scoring failed: {e}")
            return {"error": str(e)}
    
    async def _calculate_semantic_similarity(
        self,
        query: str,
        content: str
    ) -> float:
        """
        Calculate semantic similarity using embeddings
        """
        try:
            if not self.embedding_model:
                return 0.0
            
            # Create cache key
            cache_key = f"{hash(query)}:{hash(content)}"
            
            if cache_key in self.embedding_cache:
                return self.embedding_cache[cache_key]
            
            # Generate embeddings
            query_embedding = self.embedding_model.encode([query])[0]
            content_embedding = self.embedding_model.encode([content])[0]
            
            # Calculate cosine similarity
            similarity = cosine_similarity(
                [query_embedding],
                [content_embedding]
            )[0][0]
            
            # Cache result
            self.embedding_cache[cache_key] = similarity
            
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Semantic similarity calculation failed: {e}")
            return 0.0
    
    def _calculate_lexical_overlap(
        self,
        query: str,
        content: str
    ) -> float:
        """
        Calculate lexical overlap using TF-IDF
        """
        try:
            # Preprocess text
            query_tokens = self._preprocess_text(query)
            content_tokens = self._preprocess_text(content)
            
            if not query_tokens or not content_tokens:
                return 0.0
            
            # Create cache key
            cache_key = f"lexical:{hash(query)}:{hash(content)}"
            
            if cache_key in self.tfidf_cache:
                return self.tfidf_cache[cache_key]
            
            # Calculate Jaccard similarity
            query_set = set(query_tokens)
            content_set = set(content_tokens)
            
            intersection = query_set.intersection(content_set)
            union = query_set.union(content_set)
            
            if not union:
                return 0.0
            
            jaccard_similarity = len(intersection) / len(union)
            
            # Cache result
            self.tfidf_cache[cache_key] = jaccard_similarity
            
            return jaccard_similarity
            
        except Exception as e:
            logger.error(f"Lexical overlap calculation failed: {e}")
            return 0.0
    
    def _preprocess_text(self, text: str) -> List[str]:
        """
        Preprocess text for analysis
        """
        try:
            # Tokenize
            tokens = word_tokenize(text.lower())
            
            # Remove stopwords and non-alphabetic tokens
            stop_words = set(stopwords.words('english'))
            tokens = [
                token for token in tokens
                if token.isalpha() and token not in stop_words and len(token) > 2
            ]
            
            return tokens
            
        except Exception as e:
            logger.error(f"Text preprocessing failed: {e}")
            return []
    
    def _calculate_context_relevance(
        self,
        query: str,
        content: str,
        context: Dict[str, Any]
    ) -> float:
        """
        Calculate context-based relevance
        """
        try:
            context_score = 0.0
            factors = 0
            
            # Check for domain-specific keywords
            domain_keywords = context.get("domain_keywords", [])
            if domain_keywords:
                content_lower = content.lower()
                keyword_matches = sum(
                    1 for keyword in domain_keywords
                    if keyword.lower() in content_lower
                )
                context_score += keyword_matches / len(domain_keywords)
                factors += 1
            
            # Check for entity matches
            query_entities = context.get("query_entities", [])
            content_entities = self._extract_entities(content)
            
            if query_entities and content_entities:
                entity_overlap = len(
                    set(query_entities).intersection(set(content_entities))
                ) / len(query_entities)
                context_score += entity_overlap
                factors += 1
            
            # Check for temporal context
            query_date = context.get("query_date")
            content_date = self._extract_date(content)
            
            if query_date and content_date:
                date_diff = abs((query_date - content_date).days)
                # Closer dates get higher scores
                temporal_context = max(0, 1 - (date_diff / 365))  # Within 1 year
                context_score += temporal_context
                factors += 1
            
            return context_score / max(1, factors)
            
        except Exception as e:
            logger.error(f"Context relevance calculation failed: {e}")
            return 0.0
    
    def _extract_entities(self, text: str) -> List[str]:
        """
        Extract entities from text (simplified implementation)
        """
        try:
            # Simple entity extraction - look for capitalized words
            tokens = word_tokenize(text)
            entities = []
            
            for token in tokens:
                if token[0].isupper() and len(token) > 3:
                    entities.append(token)
            
            return list(set(entities))
            
        except Exception as e:
            return []
    
    def _extract_date(self, text: str) -> Optional[datetime]:
        """
        Extract date from text (simplified implementation)
        """
        try:
            # Look for date patterns
            import re
            
            date_patterns = [
                r'\d{4}-\d{2}-\d{2}',
                r'\d{2}/\d{2}/\d{4}',
                r'\d{2}\.\d{2}\.\d{4}'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    date_str = match.group()
                    try:
                        if '-' in date_str:
                            return datetime.strptime(date_str, '%Y-%m-%d')
                        elif '/' in date_str:
                            return datetime.strptime(date_str, '%m/%d/%Y')
                        elif '.' in date_str:
                            return datetime.strptime(date_str, '%d.%m.%Y')
                    except ValueError:
                        continue
            
            return None
            
        except Exception as e:
            return None
    
    def _calculate_temporal_relevance(
        self,
        content: str,
        context: Dict[str, Any]
    ) -> float:
        """
        Calculate temporal relevance
        """
        try:
            current_date = datetime.now()
            content_date = self._extract_date(content)
            
            if not content_date:
                return 0.5  # Neutral score if no date found
            
            # Calculate recency score
            days_diff = (current_date - content_date).days
            
            if days_diff < 0:
                # Future dates get low relevance
                return 0.2
            elif days_diff < 7:
                # Very recent content
                return 1.0
            elif days_diff < 30:
                # Recent content
                return 0.8
            elif days_diff < 90:
                # Somewhat recent
                return 0.6
            elif days_diff < 365:
                # Within a year
                return 0.4
            else:
                # Older content
                return 0.2
                
        except Exception as e:
            logger.error(f"Temporal relevance calculation failed: {e}")
            return 0.5
    
    def _generate_relevance_explanation(self, scores: Dict[str, Any]) -> str:
        """
        Generate human-readable explanation of relevance score
        """
        try:
            level = scores["relevance_level"]
            overall = scores["overall_score"]
            
            explanation = f"Content has {level} relevance (score: {overall:.2f}). "
            
            # Explain key factors
            factors = []
            
            semantic = scores["semantic_similarity"]
            if semantic > 0.7:
                factors.append(f"strong semantic similarity ({semantic:.2f})")
            elif semantic > 0.4:
                factors.append(f"moderate semantic similarity ({semantic:.2f})")
            
            lexical = scores["lexical_overlap"]
            if lexical > 0.3:
                factors.append(f"good lexical overlap ({lexical:.2f})")
            
            context = scores["context_relevance"]
            if context > 0.5:
                factors.append(f"strong context relevance ({context:.2f})")
            
            temporal = scores["temporal_relevance"]
            if temporal > 0.7:
                factors.append("very recent content")
            elif temporal < 0.3:
                factors.append("older content")
            
            if factors:
                explanation += "Key factors: " + ", ".join(factors)
            else:
                explanation += "No strong relevance factors identified."
            
            return explanation
            
        except Exception as e:
            return "Unable to generate explanation."
    
    def _calculate_scoring_confidence(self, scores: Dict[str, Any]) -> float:
        """
        Calculate confidence in the relevance scoring
        """
        try:
            # Higher confidence when multiple factors agree
            factor_agreement = 0
            factors = ["semantic_similarity", "lexical_overlap", "context_relevance", "temporal_relevance"]
            
            for i, factor1 in enumerate(factors):
                for factor2 in factors[i+1:]:
                    if abs(scores[factor1] - scores[factor2]) < 0.3:  # Close agreement
                        factor_agreement += 1
            
            # Base confidence on factor agreement and score magnitude
            agreement_score = factor_agreement / 6  # Max 6 agreements
            magnitude_score = scores["overall_score"]
            
            confidence = (agreement_score + magnitude_score) / 2
            
            return min(1.0, confidence)
            
        except Exception as e:
            return 0.5
    
    async def _handle_document_ranking(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle document ranking request
        """
        try:
            query = message.content.get("query", "")
            documents = message.content.get("documents", [])
            context = message.content.get("context", {})
            top_k = message.content.get("top_k", 10)
            
            if not query or not documents:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Query and documents required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Rank documents
            ranked_documents = await self._rank_documents(query, documents, context, top_k)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "document_ranking_response",
                    "query": query,
                    "total_documents": len(documents),
                    "ranked_documents": ranked_documents
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Document ranking failed: {e}")
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
    
    async def _rank_documents(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        context: Dict[str, Any],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Rank documents by relevance to query
        """
        try:
            ranked_docs = []
            
            # Score each document
            for doc in documents:
                content = doc.get("content", "")
                doc_context = doc.get("context", {})
                
                # Combine global context with document-specific context
                combined_context = {**context, **doc_context}
                
                # Score relevance
                score = await self._score_content_relevance(query, content, combined_context)
                
                ranked_doc = {
                    **doc,
                    "relevance_score": score["overall_score"],
                    "relevance_level": score["relevance_level"],
                    "scoring_details": score
                }
                
                ranked_docs.append(ranked_doc)
            
            # Sort by relevance score (descending)
            ranked_docs.sort(key=lambda x: x["relevance_score"], reverse=True)
            
            # Return top K
            return ranked_docs[:top_k]
            
        except Exception as e:
            logger.error(f"Document ranking failed: {e}")
            return []
    
    async def _handle_relevance_filtering(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle relevance filtering request
        """
        try:
            query = message.content.get("query", "")
            documents = message.content.get("documents", [])
            threshold = message.content.get("threshold", self.relevance_thresholds["medium"])
            context = message.content.get("context", {})
            
            if not query or not documents:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Query and documents required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Filter relevant documents
            relevant_documents = await self._filter_relevant_documents(
                query, documents, threshold, context
            )
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "relevance_filter_response",
                        "query": query,
                        "threshold": threshold,
                        "total_documents": len(documents),
                        "relevant_documents": relevant_documents,
                        "filtered_count": len(relevant_documents)
                    },
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            logger.error(f"Relevance filtering failed: {e}")
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
    
    async def _filter_relevant_documents(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        threshold: float,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Filter documents above relevance threshold
        """
        try:
            relevant_docs = []
            
            for doc in documents:
                content = doc.get("content", "")
                doc_context = doc.get("context", {})
                
                # Combine contexts
                combined_context = {**context, **doc_context}
                
                # Score relevance
                score = await self._score_content_relevance(query, content, combined_context)
                
                if score["overall_score"] >= threshold:
                    filtered_doc = {
                        **doc,
                        "relevance_score": score["overall_score"],
                        "relevance_level": score["relevance_level"]
                    }
                    relevant_docs.append(filtered_doc)
            
            return relevant_docs
            
        except Exception as e:
            logger.error(f"Document filtering failed: {e}")
            return []
    
    async def _handle_search_evaluation(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle search evaluation request
        """
        try:
            query = message.content.get("query", "")
            search_results = message.content.get("search_results", [])
            ground_truth = message.content.get("ground_truth", [])
            context = message.content.get("context", {})
            
            if not query or not search_results:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Query and search results required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Evaluate search results
            evaluation = await self._evaluate_search_results(query, search_results, ground_truth, context)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "search_evaluation_response",
                    "query": query,
                    "evaluation": evaluation
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Search evaluation failed: {e}")
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
    
    async def _evaluate_search_results(
        self,
        query: str,
        search_results: List[Dict[str, Any]],
        ground_truth: List[Dict[str, Any]],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate search results quality
        """
        try:
            evaluation = {
                "precision_at_k": {},
                "recall_at_k": {},
                "mean_reciprocal_rank": 0.0,
                "mean_average_precision": 0.0,
                "ndcg_score": 0.0,
                "relevance_distribution": {},
                "search_quality_score": 0.0
            }
            
            if not ground_truth:
                # Evaluate based on relevance scores only
                relevance_scores = []
                
                for result in search_results:
                    content = result.get("content", "")
                    score = await self._score_content_relevance(query, content, context)
                    relevance_scores.append(score["overall_score"])
                
                # Calculate basic metrics
                evaluation["avg_relevance_score"] = np.mean(relevance_scores) if relevance_scores else 0
                evaluation["relevance_distribution"] = {
                    "high": sum(1 for s in relevance_scores if s >= self.relevance_thresholds["high"]),
                    "medium": sum(1 for s in relevance_scores if s >= self.relevance_thresholds["medium"]),
                    "low": sum(1 for s in relevance_scores if s < self.relevance_thresholds["medium"])
                }
                
                evaluation["search_quality_score"] = evaluation["avg_relevance_score"]
                
                return evaluation
            
            # Full evaluation with ground truth
            relevant_docs = set(doc.get("id", doc.get("content", "")) for doc in ground_truth)
            
            # Calculate Precision@K and Recall@K
            for k in [1, 3, 5, 10]:
                if k > len(search_results):
                    continue
                
                top_k_results = search_results[:k]
                relevant_in_top_k = sum(
                    1 for result in top_k_results
                    if result.get("id", result.get("content", "")) in relevant_docs
                )
                
                precision = relevant_in_top_k / k
                recall = relevant_in_top_k / len(relevant_docs) if relevant_docs else 0
                
                evaluation["precision_at_k"][f"p@{k}"] = precision
                evaluation["recall_at_k"][f"r@{k}"] = recall
            
            # Calculate Mean Reciprocal Rank (MRR)
            reciprocal_ranks = []
            for i, result in enumerate(search_results):
                doc_id = result.get("id", result.get("content", ""))
                if doc_id in relevant_docs:
                    reciprocal_ranks.append(1.0 / (i + 1))
            
            evaluation["mean_reciprocal_rank"] = np.mean(reciprocal_ranks) if reciprocal_ranks else 0
            
            # Calculate Mean Average Precision (MAP)
            average_precisions = []
            relevant_found = 0
            
            for i, result in enumerate(search_results):
                doc_id = result.get("id", result.get("content", ""))
                if doc_id in relevant_docs:
                    relevant_found += 1
                    precision_at_i = relevant_found / (i + 1)
                    average_precisions.append(precision_at_i)
            
            evaluation["mean_average_precision"] = np.mean(average_precisions) if average_precisions else 0
            
            # Calculate NDCG
            evaluation["ndcg_score"] = self._calculate_ndcg(search_results, ground_truth)
            
            # Overall search quality score
            evaluation["search_quality_score"] = (
                evaluation["mean_average_precision"] * 0.4 +
                evaluation["mean_reciprocal_rank"] * 0.3 +
                evaluation["ndcg_score"] * 0.3
            )
            
            return evaluation
            
        except Exception as e:
            logger.error(f"Search evaluation failed: {e}")
            return {"error": str(e)}
    
    def _calculate_ndcg(self, search_results: List[Dict[str, Any]], ground_truth: List[Dict[str, Any]]) -> float:
        """
        Calculate Normalized Discounted Cumulative Gain
        """
        try:
            # Create relevance mapping
            relevance_map = {}
            for doc in ground_truth:
                doc_id = doc.get("id", doc.get("content", ""))
                relevance_map[doc_id] = doc.get("relevance", 1)  # Default relevance 1
            
            # Calculate DCG
            dcg = 0.0
            for i, result in enumerate(search_results):
                doc_id = result.get("id", result.get("content", ""))
                relevance = relevance_map.get(doc_id, 0)
                dcg += relevance / np.log2(i + 2)  # i + 2 because positions start from 1
            
            # Calculate IDCG (ideal DCG)
            ideal_relevances = sorted(relevance_map.values(), reverse=True)
            idcg = 0.0
            for i, relevance in enumerate(ideal_relevances):
                idcg += relevance / np.log2(i + 2)
            
            return dcg / idcg if idcg > 0 else 0.0
            
        except Exception as e:
            logger.error(f"NDCG calculation failed: {e}")
            return 0.0
    
    async def _handle_retrieval_optimization(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle retrieval optimization request
        """
        try:
            evaluation_history = message.content.get("evaluation_history", [])
            current_config = message.content.get("current_config", {})
            
            # Optimize retrieval parameters
            optimized_config = await self._optimize_retrieval_config(evaluation_history, current_config)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "retrieval_optimization_response",
                    "current_config": current_config,
                    "optimized_config": optimized_config
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Retrieval optimization failed: {e}")
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
    
    async def _optimize_retrieval_config(
        self,
        evaluation_history: List[Dict[str, Any]],
        current_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Optimize retrieval configuration based on evaluation history
        """
        try:
            optimized_config = current_config.copy()
            
            if not evaluation_history:
                return optimized_config
            
            # Analyze performance patterns
            avg_precision = np.mean([e.get("mean_average_precision", 0) for e in evaluation_history])
            avg_recall = np.mean([e.get("recall_at_k", {}).get("r@5", 0) for e in evaluation_history])
            
            # Adjust relevance thresholds based on performance
            if avg_precision < 0.5:
                # Lower threshold to include more relevant documents
                optimized_config["relevance_threshold"] = max(
                    0.3, current_config.get("relevance_threshold", 0.6) - 0.1
                )
            elif avg_precision > 0.8:
                # Raise threshold for higher precision
                optimized_config["relevance_threshold"] = min(
                    0.9, current_config.get("relevance_threshold", 0.6) + 0.05
                )
            
            # Adjust scoring weights based on what works best
            if avg_recall > avg_precision:
                # Favor recall - increase lexical overlap weight
                weights = optimized_config.get("scoring_weights", self.scoring_weights.copy())
                weights["lexical_overlap"] = min(0.5, weights.get("lexical_overlap", 0.3) + 0.1)
                weights["semantic_similarity"] = max(0.2, weights.get("semantic_similarity", 0.4) - 0.1)
                optimized_config["scoring_weights"] = weights
            else:
                # Favor precision - increase semantic similarity weight
                weights = optimized_config.get("scoring_weights", self.scoring_weights.copy())
                weights["semantic_similarity"] = min(0.6, weights.get("semantic_similarity", 0.4) + 0.1)
                weights["lexical_overlap"] = max(0.2, weights.get("lexical_overlap", 0.3) - 0.1)
                optimized_config["scoring_weights"] = weights
            
            # Update embedding model if needed
            if avg_precision < 0.4:
                # Try a different embedding model
                optimized_config["embedding_model"] = "all-mpnet-base-v2"  # More accurate but slower
            
            return optimized_config
            
        except Exception as e:
            logger.error(f"Retrieval optimization failed: {e}")
            return current_config


# ========== TEST ==========
if __name__ == "__main__":
    async def test_content_relevance_agent():
        # Initialize content relevance agent
        agent = ContentRelevanceAgent()
        await agent.initialize()
        
        # Test relevance scoring
        test_message = AgentMessage(
            id="test_relevance",
            from_agent="test",
            to_agent="content_relevance_agent",
            content={
                "type": "score_relevance",
                "query": "corruption in customs declarations",
                "content": "The company submitted customs declarations with inflated values to avoid taxes. This appears to be a case of customs fraud and corruption involving multiple officials."
            },
            timestamp=datetime.now()
        )
        
        print("Testing content relevance agent...")
        async for response in agent.process_message(test_message):
            print(f"Response type: {response.content.get('type')}")
            if response.content.get("type") == "relevance_score_response":
                score = response.content.get("relevance_score", {})
                print(f"Overall score: {score.get('overall_score', 0):.2f}")
                print(f"Relevance level: {score.get('relevance_level')}")
                print(f"Explanation: {score.get('explanation')}")
        
        print("Content relevance agent test completed")
    
    # Run test
    asyncio.run(test_content_relevance_agent())
