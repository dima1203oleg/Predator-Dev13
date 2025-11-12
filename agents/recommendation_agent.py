"""
Recommendation Agent: Personalized recommendations and suggestions
Provides intelligent recommendations based on user behavior, preferences, and context
"""

import asyncio
import logging
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from typing import Any

import networkx as nx
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from surprise import SVD, Dataset, KNNBasic, Reader

from ..agents.base_agent import AgentMessage, BaseAgent

logger = logging.getLogger(__name__)


class RecommendationAgent(BaseAgent):
    """
    Recommendation Agent for personalized recommendations and suggestions
    Uses collaborative filtering, content-based filtering, and hybrid approaches
    """

    def __init__(
        self, agent_id: str = "recommendation_agent", config: dict[str, Any] | None = None
    ):
        super().__init__(agent_id, config or {})

        # Recommendation configuration
        self.rec_config = {
            "recommendation_algorithms": self.config.get(
                "algorithms",
                [
                    "collaborative_filtering",
                    "content_based",
                    "hybrid",
                    "context_aware",
                    "knowledge_based",
                    "demographic",
                    "trend_based",
                ],
            ),
            "similarity_measures": self.config.get(
                "similarity_measures", ["cosine", "pearson", "jaccard", "euclidean"]
            ),
            "model_types": self.config.get(
                "model_types", ["matrix_factorization", "neural_network", "ensemble", "graph_based"]
            ),
            "recommendation_types": self.config.get(
                "recommendation_types", ["user_based", "item_based", "content_based", "hybrid"]
            ),
            "diversity_settings": self.config.get(
                "diversity_settings",
                {"min_diversity": 0.3, "max_similar_items": 2, "category_balance": True},
            ),
            "personalization_levels": self.config.get(
                "personalization_levels",
                ["basic", "intermediate", "advanced", "ultra_personalized"],
            ),
            "recommendation_limits": self.config.get(
                "recommendation_limits",
                {"max_recommendations": 20, "min_confidence": 0.1, "max_processing_time": 30},
            ),
        }

        # ML models for recommendations
        self.recommendation_models = {}
        self.similarity_models = {}
        self.personalization_models = {}

        # Recommendation state
        self.recommendation_state = {
            "user_profiles": {},
            "item_profiles": {},
            "interaction_matrix": None,
            "similarity_matrices": {},
            "recommendation_cache": {},
            "model_performance": {},
            "user_segments": {},
            "content_graph": nx.Graph(),
            "trending_items": deque(maxlen=1000),
            "recommendation_log": deque(maxlen=10000),
            "feedback_loop": deque(maxlen=5000),
        }

        # Background tasks
        self.model_training_task = None
        self.recommendation_update_task = None
        self.feedback_processing_task = None

        logger.info(f"Recommendation Agent initialized: {agent_id}")

    async def start(self):
        """
        Start the recommendation agent
        """
        await super().start()

        # Initialize recommendation models
        await self._initialize_recommendation_models()

        # Load existing data
        await self._load_recommendation_data()

        # Start background tasks
        self.model_training_task = asyncio.create_task(self._continuous_model_training())
        self.recommendation_update_task = asyncio.create_task(
            self._continuous_recommendation_updates()
        )
        self.feedback_processing_task = asyncio.create_task(self._process_feedback_loop())

        logger.info("Recommendation processing started")

    async def stop(self):
        """
        Stop the recommendation agent
        """
        if self.model_training_task:
            self.model_training_task.cancel()
            try:
                await self.model_training_task
            except asyncio.CancelledError:
                pass

        if self.recommendation_update_task:
            self.recommendation_update_task.cancel()
            try:
                await self.recommendation_update_task
            except asyncio.CancelledError:
                pass

        if self.feedback_processing_task:
            self.feedback_processing_task.cancel()
            try:
                await self.feedback_processing_task
            except asyncio.CancelledError:
                pass

        await super().stop()
        logger.info("Recommendation agent stopped")

    async def _initialize_recommendation_models(self):
        """
        Initialize ML models for recommendations
        """
        try:
            # Collaborative filtering models
            self.recommendation_models = {
                "svd": SVD(n_factors=100, random_state=42),
                "knn_user": KNNBasic(k=40, sim_options={"name": "cosine", "user_based": True}),
                "knn_item": KNNBasic(k=40, sim_options={"name": "cosine", "user_based": False}),
                "neural_cf": None,  # Initialize when needed
                "lightfm": None,  # Initialize when needed
            }

            # Content-based models
            self.similarity_models = {
                "tfidf_vectorizer": TfidfVectorizer(max_features=5000, stop_words="english"),
                "content_similarity": None,
            }

            # Personalization models
            self.personalization_models = {
                "user_classifier": RandomForestClassifier(n_estimators=100, random_state=42),
                "preference_predictor": GradientBoostingRegressor(
                    n_estimators=100, random_state=42
                ),
                "context_analyzer": None,
            }

            logger.info("Recommendation models initialized")

        except Exception as e:
            logger.error(f"Recommendation model initialization failed: {e}")

    async def _load_recommendation_data(self):
        """
        Load existing recommendation data
        """
        try:
            # Load user profiles, interactions, and content
            await self._load_user_profiles()
            await self._load_item_profiles()
            await self._load_interaction_data()
            await self._build_similarity_matrices()

            logger.info("Recommendation data loaded")

        except Exception as e:
            logger.error(f"Recommendation data loading failed: {e}")

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process recommendation requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "get_recommendations":
                async for response in self._handle_get_recommendations(message):
                    yield response

            elif message_type == "update_preferences":
                async for response in self._handle_update_preferences(message):
                    yield response

            elif message_type == "analyze_user":
                async for response in self._handle_user_analysis(message):
                    yield response

            elif message_type == "find_similar_items":
                async for response in self._handle_similar_items(message):
                    yield response

            elif message_type == "get_trending":
                async for response in self._handle_trending_items(message):
                    yield response

            elif message_type == "personalize_content":
                async for response in self._handle_content_personalization(message):
                    yield response

            elif message_type == "feedback":
                async for response in self._handle_user_feedback(message):
                    yield response

            elif message_type == "train_models":
                async for response in self._handle_model_training(message):
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
            logger.error(f"Recommendation processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_get_recommendations(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle recommendation request
        """
        try:
            user_id = message.content.get("user_id")
            context = message.content.get("context", {})
            recommendation_type = message.content.get("recommendation_type", "hybrid")
            num_recommendations = message.content.get("num_recommendations", 10)
            filters = message.content.get("filters", {})

            # Get recommendations
            recommendations = await self._get_recommendations(
                user_id, context, recommendation_type, num_recommendations, filters
            )

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "recommendations_response",
                    "user_id": user_id,
                    "recommendation_type": recommendation_type,
                    "recommendations": recommendations,
                    "context": context,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Recommendation handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _get_recommendations(
        self,
        user_id: str,
        context: dict[str, Any],
        recommendation_type: str,
        num_recommendations: int,
        filters: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Get personalized recommendations
        """
        try:
            recommendations = []

            # Check cache first
            cache_key = (
                f"{user_id}_{recommendation_type}_{num_recommendations}_{hash(str(filters))}"
            )
            if cache_key in self.recommendation_state["recommendation_cache"]:
                cached_result = self.recommendation_state["recommendation_cache"][cache_key]
                if (datetime.now() - cached_result["timestamp"]).seconds < 3600:  # 1 hour cache
                    return cached_result["recommendations"]

            # Generate recommendations based on type
            if recommendation_type == "collaborative":
                recommendations = await self._collaborative_filtering_recommendations(
                    user_id, num_recommendations
                )
            elif recommendation_type == "content_based":
                recommendations = await self._content_based_recommendations(
                    user_id, num_recommendations
                )
            elif recommendation_type == "hybrid":
                recommendations = await self._hybrid_recommendations(user_id, num_recommendations)
            elif recommendation_type == "context_aware":
                recommendations = await self._context_aware_recommendations(
                    user_id, context, num_recommendations
                )
            elif recommendation_type == "trend_based":
                recommendations = await self._trend_based_recommendations(num_recommendations)
            else:
                recommendations = await self._fallback_recommendations(num_recommendations)

            # Apply filters
            recommendations = await self._apply_recommendation_filters(recommendations, filters)

            # Ensure diversity
            recommendations = await self._ensure_recommendation_diversity(
                recommendations, num_recommendations
            )

            # Add explanations
            recommendations = await self._add_recommendation_explanations(recommendations, user_id)

            # Cache results
            self.recommendation_state["recommendation_cache"][cache_key] = {
                "recommendations": recommendations,
                "timestamp": datetime.now(),
            }

            # Log recommendations
            await self._log_recommendations(user_id, recommendations, recommendation_type)

            return recommendations

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")
            return []

    async def _collaborative_filtering_recommendations(
        self, user_id: str, num_recommendations: int
    ) -> list[dict[str, Any]]:
        """
        Generate collaborative filtering recommendations
        """
        try:
            recommendations = []

            if user_id not in self.recommendation_state["user_profiles"]:
                return await self._cold_start_recommendations(num_recommendations)

            # Use SVD model for predictions
            if self.recommendation_models.get("svd"):
                user_interactions = self.recommendation_state["user_profiles"][user_id].get(
                    "interactions", {}
                )

                # Get unrated items
                all_items = set(self.recommendation_state["item_profiles"].keys())
                rated_items = set(user_interactions.keys())
                unrated_items = all_items - rated_items

                # Predict ratings for unrated items
                predictions = []
                for item_id in unrated_items:
                    try:
                        prediction = self.recommendation_models["svd"].predict(user_id, item_id)
                        predictions.append(
                            {
                                "item_id": item_id,
                                "predicted_rating": prediction.est,
                                "confidence": 1.0,  # Could be based on prediction variance
                            }
                        )
                    except Exception:
                        continue

                # Sort by predicted rating
                predictions.sort(key=lambda x: x["predicted_rating"], reverse=True)
                recommendations = predictions[:num_recommendations]

            return recommendations

        except Exception as e:
            logger.error(f"Collaborative filtering failed: {e}")
            return []

    async def _content_based_recommendations(
        self, user_id: str, num_recommendations: int
    ) -> list[dict[str, Any]]:
        """
        Generate content-based recommendations
        """
        try:
            recommendations = []

            if user_id not in self.recommendation_state["user_profiles"]:
                return await self._cold_start_recommendations(num_recommendations)

            user_profile = self.recommendation_state["user_profiles"][user_id]
            user_interactions = user_profile.get("interactions", {})

            # Get user's preferred items (highly rated)
            preferred_items = [
                item_id
                for item_id, rating in user_interactions.items()
                if rating >= 4.0  # Assuming 5-star scale
            ]

            if not preferred_items:
                return await self._cold_start_recommendations(num_recommendations)

            # Calculate similarity to preferred items
            item_similarities = {}
            for item_id in self.recommendation_state["item_profiles"]:
                if item_id not in user_interactions:
                    max_similarity = 0
                    for pref_item in preferred_items:
                        if pref_item in self.recommendation_state["similarity_matrices"].get(
                            "content", {}
                        ):
                            similarity = self.recommendation_state["similarity_matrices"][
                                "content"
                            ].get((pref_item, item_id), 0)
                            max_similarity = max(max_similarity, similarity)

                    if max_similarity > 0:
                        item_similarities[item_id] = max_similarity

            # Sort by similarity
            sorted_items = sorted(item_similarities.items(), key=lambda x: x[1], reverse=True)
            recommendations = [
                {"item_id": item_id, "similarity_score": score, "confidence": score}
                for item_id, score in sorted_items[:num_recommendations]
            ]

            return recommendations

        except Exception as e:
            logger.error(f"Content-based recommendations failed: {e}")
            return []

    async def _hybrid_recommendations(
        self, user_id: str, num_recommendations: int
    ) -> list[dict[str, Any]]:
        """
        Generate hybrid recommendations combining multiple approaches
        """
        try:
            # Get recommendations from different methods
            cf_recs = await self._collaborative_filtering_recommendations(
                user_id, num_recommendations * 2
            )
            cb_recs = await self._content_based_recommendations(user_id, num_recommendations * 2)

            # Combine and rank
            combined_scores = {}

            # Weight collaborative filtering higher for established users
            cf_weight = 0.6
            cb_weight = 0.4

            # Add CF scores
            for rec in cf_recs:
                item_id = rec["item_id"]
                combined_scores[item_id] = {
                    "cf_score": rec.get("predicted_rating", 0),
                    "cb_score": 0,
                    "final_score": rec.get("predicted_rating", 0) * cf_weight,
                }

            # Add CB scores
            for rec in cb_recs:
                item_id = rec["item_id"]
                if item_id in combined_scores:
                    combined_scores[item_id]["cb_score"] = rec.get("similarity_score", 0)
                    combined_scores[item_id]["final_score"] += (
                        rec.get("similarity_score", 0) * cb_weight
                    )
                else:
                    combined_scores[item_id] = {
                        "cf_score": 0,
                        "cb_score": rec.get("similarity_score", 0),
                        "final_score": rec.get("similarity_score", 0) * cb_weight,
                    }

            # Sort by final score
            sorted_items = sorted(
                combined_scores.items(), key=lambda x: x[1]["final_score"], reverse=True
            )

            recommendations = [
                {
                    "item_id": item_id,
                    "final_score": scores["final_score"],
                    "cf_score": scores["cf_score"],
                    "cb_score": scores["cb_score"],
                    "confidence": min(scores["final_score"] / 5.0, 1.0),  # Normalize confidence
                }
                for item_id, scores in sorted_items[:num_recommendations]
            ]

            return recommendations

        except Exception as e:
            logger.error(f"Hybrid recommendations failed: {e}")
            return []

    async def _context_aware_recommendations(
        self, user_id: str, context: dict[str, Any], num_recommendations: int
    ) -> list[dict[str, Any]]:
        """
        Generate context-aware recommendations
        """
        try:
            recommendations = []

            # Extract context features
            time_of_day = context.get("time_of_day")
            location = context.get("location")
            device_type = context.get("device_type")
            mood = context.get("mood")

            # Get base recommendations
            base_recs = await self._hybrid_recommendations(user_id, num_recommendations * 2)

            # Apply context filters and re-ranking
            contextual_scores = {}

            for rec in base_recs:
                item_id = rec["item_id"]
                base_score = rec.get("final_score", 0)

                # Context adjustment factors
                time_factor = await self._calculate_time_factor(item_id, time_of_day)
                location_factor = await self._calculate_location_factor(item_id, location)
                device_factor = await self._calculate_device_factor(item_id, device_type)
                mood_factor = await self._calculate_mood_factor(item_id, mood)

                # Combine factors
                context_multiplier = (
                    time_factor + location_factor + device_factor + mood_factor
                ) / 4.0
                contextual_score = base_score * context_multiplier

                contextual_scores[item_id] = {
                    "base_score": base_score,
                    "contextual_score": contextual_score,
                    "context_factors": {
                        "time": time_factor,
                        "location": location_factor,
                        "device": device_factor,
                        "mood": mood_factor,
                    },
                }

            # Sort by contextual score
            sorted_items = sorted(
                contextual_scores.items(), key=lambda x: x[1]["contextual_score"], reverse=True
            )

            recommendations = [
                {
                    "item_id": item_id,
                    "contextual_score": scores["contextual_score"],
                    "base_score": scores["base_score"],
                    "context_factors": scores["context_factors"],
                    "confidence": min(scores["contextual_score"] / 5.0, 1.0),
                }
                for item_id, scores in sorted_items[:num_recommendations]
            ]

            return recommendations

        except Exception as e:
            logger.error(f"Context-aware recommendations failed: {e}")
            return []

    async def _trend_based_recommendations(self, num_recommendations: int) -> list[dict[str, Any]]:
        """
        Generate trend-based recommendations
        """
        try:
            # Get trending items from recent activity
            trending_items = list(self.recommendation_state["trending_items"])

            if not trending_items:
                return await self._fallback_recommendations(num_recommendations)

            # Count item frequencies (recent trends)
            item_counts = {}
            for item in trending_items[-1000:]:  # Last 1000 interactions
                item_id = item.get("item_id")
                if item_id:
                    item_counts[item_id] = item_counts.get(item_id, 0) + 1

            # Sort by trend score
            sorted_trends = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)

            recommendations = [
                {
                    "item_id": item_id,
                    "trend_score": count,
                    "confidence": min(count / 100, 1.0),  # Normalize based on max expected count
                    "reason": "trending",
                }
                for item_id, count in sorted_trends[:num_recommendations]
            ]

            return recommendations

        except Exception as e:
            logger.error(f"Trend-based recommendations failed: {e}")
            return []

    async def _cold_start_recommendations(self, num_recommendations: int) -> list[dict[str, Any]]:
        """
        Recommendations for new users (cold start problem)
        """
        try:
            # For new users, recommend popular items
            all_interactions = []
            for user_profile in self.recommendation_state["user_profiles"].values():
                all_interactions.extend(user_profile.get("interactions", {}).items())

            if not all_interactions:
                return await self._fallback_recommendations(num_recommendations)

            # Count item popularity
            item_popularity = {}
            for item_id, rating in all_interactions:
                if rating >= 3.0:  # Consider only positive interactions
                    item_popularity[item_id] = item_popularity.get(item_id, 0) + 1

            # Sort by popularity
            sorted_popular = sorted(item_popularity.items(), key=lambda x: x[1], reverse=True)

            recommendations = [
                {
                    "item_id": item_id,
                    "popularity_score": count,
                    "confidence": 0.5,  # Lower confidence for cold start
                    "reason": "popular",
                }
                for item_id, count in sorted_popular[:num_recommendations]
            ]

            return recommendations

        except Exception as e:
            logger.error(f"Cold start recommendations failed: {e}")
            return []

    async def _fallback_recommendations(self, num_recommendations: int) -> list[dict[str, Any]]:
        """
        Fallback recommendations when other methods fail
        """
        try:
            # Return random sample of available items
            all_items = list(self.recommendation_state["item_profiles"].keys())

            if not all_items:
                return []

            # Random sample
            import random

            sampled_items = random.sample(all_items, min(num_recommendations, len(all_items)))

            recommendations = [
                {"item_id": item_id, "confidence": 0.1, "reason": "fallback"}  # Very low confidence
                for item_id in sampled_items
            ]

            return recommendations

        except Exception as e:
            logger.error(f"Fallback recommendations failed: {e}")
            return []

    async def _calculate_time_factor(self, item_id: str, time_of_day: str | None) -> float:
        """Calculate time-based context factor"""
        try:
            if not time_of_day or item_id not in self.recommendation_state["item_profiles"]:
                return 1.0

            item_profile = self.recommendation_state["item_profiles"][item_id]
            time_preferences = item_profile.get("time_preferences", {})

            # Default time factor
            factor = time_preferences.get(time_of_day, 1.0)
            return factor

        except Exception:
            return 1.0

    async def _calculate_location_factor(self, item_id: str, location: str | None) -> float:
        """Calculate location-based context factor"""
        try:
            if not location or item_id not in self.recommendation_state["item_profiles"]:
                return 1.0

            item_profile = self.recommendation_state["item_profiles"][item_id]
            location_preferences = item_profile.get("location_preferences", {})

            factor = location_preferences.get(location, 1.0)
            return factor

        except Exception:
            return 1.0

    async def _calculate_device_factor(self, item_id: str, device_type: str | None) -> float:
        """Calculate device-based context factor"""
        try:
            if not device_type or item_id not in self.recommendation_state["item_profiles"]:
                return 1.0

            item_profile = self.recommendation_state["item_profiles"][item_id]
            device_preferences = item_profile.get("device_preferences", {})

            factor = device_preferences.get(device_type, 1.0)
            return factor

        except Exception:
            return 1.0

    async def _calculate_mood_factor(self, item_id: str, mood: str | None) -> float:
        """Calculate mood-based context factor"""
        try:
            if not mood or item_id not in self.recommendation_state["item_profiles"]:
                return 1.0

            item_profile = self.recommendation_state["item_profiles"][item_id]
            mood_preferences = item_profile.get("mood_preferences", {})

            factor = mood_preferences.get(mood, 1.0)
            return factor

        except Exception:
            return 1.0

    async def _apply_recommendation_filters(
        self, recommendations: list[dict[str, Any]], filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """
        Apply filters to recommendations
        """
        try:
            filtered_recs = recommendations.copy()

            # Category filter
            if "categories" in filters:
                allowed_categories = set(filters["categories"])
                filtered_recs = [
                    rec
                    for rec in filtered_recs
                    if self.recommendation_state["item_profiles"]
                    .get(rec["item_id"], {})
                    .get("category")
                    in allowed_categories
                ]

            # Price range filter
            if "price_range" in filters:
                min_price = filters["price_range"].get("min", 0)
                max_price = filters["price_range"].get("max", float("inf"))
                filtered_recs = [
                    rec
                    for rec in filtered_recs
                    if min_price
                    <= self.recommendation_state["item_profiles"]
                    .get(rec["item_id"], {})
                    .get("price", 0)
                    <= max_price
                ]

            # Rating filter
            if "min_rating" in filters:
                min_rating = filters["min_rating"]
                filtered_recs = [
                    rec
                    for rec in filtered_recs
                    if self.recommendation_state["item_profiles"]
                    .get(rec["item_id"], {})
                    .get("average_rating", 0)
                    >= min_rating
                ]

            # Exclude items
            if "exclude_items" in filters:
                exclude_set = set(filters["exclude_items"])
                filtered_recs = [rec for rec in filtered_recs if rec["item_id"] not in exclude_set]

            return filtered_recs

        except Exception as e:
            logger.error(f"Recommendation filtering failed: {e}")
            return recommendations

    async def _ensure_recommendation_diversity(
        self, recommendations: list[dict[str, Any]], max_recommendations: int
    ) -> list[dict[str, Any]]:
        """
        Ensure diversity in recommendations
        """
        try:
            if len(recommendations) <= max_recommendations:
                return recommendations

            diverse_recs = []
            category_counts = defaultdict(int)

            for rec in recommendations:
                item_id = rec["item_id"]
                item_profile = self.recommendation_state["item_profiles"].get(item_id, {})
                category = item_profile.get("category", "unknown")

                # Check diversity constraints
                if (
                    category_counts[category]
                    < self.rec_config["diversity_settings"]["max_similar_items"]
                ):
                    diverse_recs.append(rec)
                    category_counts[category] += 1

                    if len(diverse_recs) >= max_recommendations:
                        break

            return diverse_recs

        except Exception as e:
            logger.error(f"Diversity enforcement failed: {e}")
            return recommendations[:max_recommendations]

    async def _add_recommendation_explanations(
        self, recommendations: list[dict[str, Any]], user_id: str
    ) -> list[dict[str, Any]]:
        """
        Add explanations for recommendations
        """
        try:
            for rec in recommendations:
                rec["item_id"]

                # Generate explanation based on recommendation type
                if "reason" in rec:
                    if rec["reason"] == "trending":
                        rec["explanation"] = "This item is currently trending"
                    elif rec["reason"] == "popular":
                        rec["explanation"] = "This is a popular item among users"
                    elif rec["reason"] == "fallback":
                        rec["explanation"] = "Recommended item"
                elif "cf_score" in rec and rec["cf_score"] > 0:
                    rec["explanation"] = "Recommended based on similar users' preferences"
                elif "cb_score" in rec and rec["cb_score"] > 0:
                    rec["explanation"] = "Recommended based on similar items you've liked"
                elif "contextual_score" in rec:
                    rec["explanation"] = "Recommended for your current context"
                else:
                    rec["explanation"] = "Personalized recommendation"

            return recommendations

        except Exception as e:
            logger.error(f"Explanation generation failed: {e}")
            return recommendations

    async def _handle_update_preferences(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle preference update request
        """
        try:
            user_id = message.content.get("user_id")
            preferences = message.content.get("preferences", {})

            # Update user preferences
            await self._update_user_preferences(user_id, preferences)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "preferences_updated",
                    "user_id": user_id,
                    "preferences": preferences,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Preference update handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _update_user_preferences(self, user_id: str, preferences: dict[str, Any]):
        """
        Update user preferences
        """
        try:
            if user_id not in self.recommendation_state["user_profiles"]:
                self.recommendation_state["user_profiles"][user_id] = {
                    "interactions": {},
                    "preferences": {},
                    "profile": {},
                }

            # Update preferences
            self.recommendation_state["user_profiles"][user_id]["preferences"].update(preferences)

            # Clear recommendation cache for this user
            cache_keys_to_remove = [
                key
                for key in self.recommendation_state["recommendation_cache"].keys()
                if key.startswith(f"{user_id}_")
            ]
            for key in cache_keys_to_remove:
                del self.recommendation_state["recommendation_cache"][key]

            logger.info(f"Updated preferences for user {user_id}")

        except Exception as e:
            logger.error(f"Preference update failed: {e}")

    async def _handle_user_analysis(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle user analysis request
        """
        try:
            user_id = message.content.get("user_id")

            # Analyze user
            user_analysis = await self._analyze_user(user_id)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "user_analysis_response",
                    "user_id": user_id,
                    "analysis": user_analysis,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"User analysis handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _analyze_user(self, user_id: str) -> dict[str, Any]:
        """
        Analyze user behavior and preferences
        """
        try:
            if user_id not in self.recommendation_state["user_profiles"]:
                return {"error": "User not found"}

            user_profile = self.recommendation_state["user_profiles"][user_id]
            interactions = user_profile.get("interactions", {})

            analysis = {
                "total_interactions": len(interactions),
                "average_rating": 0.0,
                "preferred_categories": {},
                "interaction_patterns": {},
                "engagement_score": 0.0,
                "diversity_score": 0.0,
            }

            if interactions:
                # Calculate average rating
                ratings = list(interactions.values())
                analysis["average_rating"] = sum(ratings) / len(ratings)

                # Analyze preferred categories
                category_counts = defaultdict(int)
                for item_id, rating in interactions.items():
                    if rating >= 4.0:  # Positive interactions
                        item_profile = self.recommendation_state["item_profiles"].get(item_id, {})
                        category = item_profile.get("category", "unknown")
                        category_counts[category] += 1

                analysis["preferred_categories"] = dict(category_counts)

                # Calculate engagement score (based on interaction frequency and recency)
                recent_interactions = [
                    item
                    for item in self.recommendation_state["trending_items"]
                    if item.get("user_id") == user_id
                ]
                analysis["engagement_score"] = min(len(recent_interactions) / 10, 1.0)

                # Calculate diversity score
                unique_categories = len(category_counts)
                analysis["diversity_score"] = min(
                    unique_categories / 5, 1.0
                )  # Normalize to max 5 categories

            return analysis

        except Exception as e:
            logger.error(f"User analysis failed: {e}")
            return {"error": str(e)}

    async def _handle_similar_items(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle similar items request
        """
        try:
            item_id = message.content.get("item_id")
            num_similar = message.content.get("num_similar", 5)
            similarity_type = message.content.get("similarity_type", "content")

            # Find similar items
            similar_items = await self._find_similar_items(item_id, num_similar, similarity_type)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "similar_items_response",
                    "item_id": item_id,
                    "similarity_type": similarity_type,
                    "similar_items": similar_items,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Similar items handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _find_similar_items(
        self, item_id: str, num_similar: int, similarity_type: str
    ) -> list[dict[str, Any]]:
        """
        Find items similar to the given item
        """
        try:
            if item_id not in self.recommendation_state["item_profiles"]:
                return []

            similar_items = []

            if similarity_type == "content":
                # Content-based similarity
                similarity_matrix = self.recommendation_state["similarity_matrices"].get(
                    "content", {}
                )

                for other_item_id in self.recommendation_state["item_profiles"]:
                    if other_item_id != item_id:
                        similarity = similarity_matrix.get((item_id, other_item_id), 0)
                        if similarity > 0:
                            similar_items.append(
                                {"item_id": other_item_id, "similarity_score": similarity}
                            )

            elif similarity_type == "collaborative":
                # Collaborative similarity
                similarity_matrix = self.recommendation_state["similarity_matrices"].get(
                    "collaborative", {}
                )

                for other_item_id in self.recommendation_state["item_profiles"]:
                    if other_item_id != item_id:
                        similarity = similarity_matrix.get((item_id, other_item_id), 0)
                        if similarity > 0:
                            similar_items.append(
                                {"item_id": other_item_id, "similarity_score": similarity}
                            )

            # Sort by similarity score
            similar_items.sort(key=lambda x: x["similarity_score"], reverse=True)

            return similar_items[:num_similar]

        except Exception as e:
            logger.error(f"Similar items search failed: {e}")
            return []

    async def _handle_trending_items(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle trending items request
        """
        try:
            time_window = message.content.get("time_window", "24h")
            num_items = message.content.get("num_items", 10)

            # Get trending items
            trending = await self._get_trending_items(time_window, num_items)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "trending_response",
                    "time_window": time_window,
                    "trending_items": trending,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Trending items handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _get_trending_items(self, time_window: str, num_items: int) -> list[dict[str, Any]]:
        """
        Get trending items based on time window
        """
        try:
            # Parse time window
            if time_window == "1h":
                hours = 1
            elif time_window == "24h":
                hours = 24
            elif time_window == "7d":
                hours = 168
            else:
                hours = 24  # Default

            cutoff_time = datetime.now() - timedelta(hours=hours)

            # Filter recent interactions
            recent_interactions = [
                item
                for item in self.recommendation_state["trending_items"]
                if item.get("timestamp", datetime.min) > cutoff_time
            ]

            # Count item frequencies
            item_counts = defaultdict(int)
            for interaction in recent_interactions:
                item_id = interaction.get("item_id")
                if item_id:
                    item_counts[item_id] += 1

            # Sort by frequency
            sorted_trends = sorted(item_counts.items(), key=lambda x: x[1], reverse=True)

            trending_items = [
                {"item_id": item_id, "trend_score": count, "frequency": count}
                for item_id, count in sorted_trends[:num_items]
            ]

            return trending_items

        except Exception as e:
            logger.error(f"Trending items retrieval failed: {e}")
            return []

    async def _handle_content_personalization(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle content personalization request
        """
        try:
            user_id = message.content.get("user_id")
            content_items = message.content.get("content_items", [])

            # Personalize content
            personalized_content = await self._personalize_content(user_id, content_items)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "personalization_response",
                    "user_id": user_id,
                    "personalized_content": personalized_content,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Content personalization handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _personalize_content(
        self, user_id: str, content_items: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Personalize content items for user
        """
        try:
            personalized_items = []

            for item in content_items:
                item_id = item.get("id")

                # Get personalization score
                personalization_score = await self._calculate_personalization_score(
                    user_id, item_id
                )

                personalized_item = item.copy()
                personalized_item["personalization_score"] = personalization_score

                personalized_items.append(personalized_item)

            # Sort by personalization score
            personalized_items.sort(key=lambda x: x["personalization_score"], reverse=True)

            return personalized_items

        except Exception as e:
            logger.error(f"Content personalization failed: {e}")
            return content_items

    async def _calculate_personalization_score(self, user_id: str, item_id: str) -> float:
        """
        Calculate personalization score for user-item pair
        """
        try:
            if user_id not in self.recommendation_state["user_profiles"]:
                return 0.5  # Neutral score for unknown users

            user_profile = self.recommendation_state["user_profiles"][user_id]
            user_interactions = user_profile.get("interactions", {})

            # Direct interaction score
            if item_id in user_interactions:
                return user_interactions[item_id] / 5.0  # Normalize to 0-1

            # Similarity-based score
            item_profile = self.recommendation_state["item_profiles"].get(item_id, {})
            item_category = item_profile.get("category")

            # Check user's category preferences
            preferred_categories = []
            for interaction_item_id, rating in user_interactions.items():
                if rating >= 4.0:
                    interaction_profile = self.recommendation_state["item_profiles"].get(
                        interaction_item_id, {}
                    )
                    preferred_categories.append(interaction_profile.get("category"))

            if item_category in preferred_categories:
                return 0.7  # High score for preferred categories

            return 0.5  # Default neutral score

        except Exception as e:
            logger.error(f"Personalization score calculation failed: {e}")
            return 0.5

    async def _handle_user_feedback(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle user feedback
        """
        try:
            user_id = message.content.get("user_id")
            item_id = message.content.get("item_id")
            feedback_type = message.content.get("feedback_type")
            rating = message.content.get("rating")

            # Process feedback
            await self._process_user_feedback(user_id, item_id, feedback_type, rating)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "feedback_processed",
                    "user_id": user_id,
                    "item_id": item_id,
                    "feedback_type": feedback_type,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"User feedback handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _process_user_feedback(
        self, user_id: str, item_id: str, feedback_type: str, rating: float | None
    ):
        """
        Process user feedback for learning
        """
        try:
            # Update user profile
            if user_id not in self.recommendation_state["user_profiles"]:
                self.recommendation_state["user_profiles"][user_id] = {
                    "interactions": {},
                    "preferences": {},
                    "profile": {},
                }

            # Update interaction
            if rating is not None:
                self.recommendation_state["user_profiles"][user_id]["interactions"][
                    item_id
                ] = rating

            # Add to feedback loop
            feedback_entry = {
                "user_id": user_id,
                "item_id": item_id,
                "feedback_type": feedback_type,
                "rating": rating,
                "timestamp": datetime.now(),
            }
            self.recommendation_state["feedback_loop"].append(feedback_entry)

            # Add to trending items
            trend_entry = {
                "user_id": user_id,
                "item_id": item_id,
                "interaction_type": feedback_type,
                "timestamp": datetime.now(),
            }
            self.recommendation_state["trending_items"].append(trend_entry)

            # Clear cache for this user
            cache_keys_to_remove = [
                key
                for key in self.recommendation_state["recommendation_cache"].keys()
                if key.startswith(f"{user_id}_")
            ]
            for key in cache_keys_to_remove:
                del self.recommendation_state["recommendation_cache"][key]

            logger.info(f"Processed feedback for user {user_id}, item {item_id}")

        except Exception as e:
            logger.error(f"Feedback processing failed: {e}")

    async def _handle_model_training(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle model training request
        """
        try:
            model_type = message.content.get("model_type", "all")

            # Train models
            training_result = await self._train_recommendation_models(model_type)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "training_response",
                    "model_type": model_type,
                    "result": training_result,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Model training handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _train_recommendation_models(self, model_type: str) -> dict[str, Any]:
        """
        Train recommendation models
        """
        try:
            training_result = {
                "models_trained": [],
                "performance_metrics": {},
                "training_time": 0,
                "status": "success",
            }

            start_time = datetime.now()

            # Prepare training data
            interactions_data = []
            for user_profile in self.recommendation_state["user_profiles"].values():
                for item_id, rating in user_profile.get("interactions", {}).items():
                    interactions_data.append(
                        {
                            "user_id": list(
                                self.recommendation_state["user_profiles"].keys()
                            ).index(user_profile),
                            "item_id": list(
                                self.recommendation_state["item_profiles"].keys()
                            ).index(item_id),
                            "rating": rating,
                        }
                    )

            if not interactions_data:
                return {"error": "No training data available"}

            df = pd.DataFrame(interactions_data)

            if model_type in ["svd", "all"]:
                # Train SVD model
                reader = Reader(rating_scale=(1, 5))
                data = Dataset.load_from_df(df[["user_id", "item_id", "rating"]], reader)
                trainset = data.build_full_trainset()

                self.recommendation_models["svd"].fit(trainset)
                training_result["models_trained"].append("svd")

            if model_type in ["knn", "all"]:
                # Train KNN models
                reader = Reader(rating_scale=(1, 5))
                data = Dataset.load_from_df(df[["user_id", "item_id", "rating"]], reader)

                # User-based KNN
                trainset = data.build_full_trainset()
                self.recommendation_models["knn_user"].fit(trainset)

                # Item-based KNN
                self.recommendation_models["knn_item"].fit(trainset)

                training_result["models_trained"].extend(["knn_user", "knn_item"])

            # Update similarity matrices
            await self._build_similarity_matrices()

            training_result["training_time"] = (datetime.now() - start_time).total_seconds()

            return training_result

        except Exception as e:
            logger.error(f"Model training failed: {e}")
            return {"error": str(e), "status": "training_failed"}

    async def _continuous_model_training(self):
        """
        Continuous model training and updates
        """
        try:
            while True:
                try:
                    # Check if retraining is needed
                    if (
                        len(self.recommendation_state["feedback_loop"]) >= 100
                    ):  # Retrain every 100 feedbacks
                        await self._train_recommendation_models("all")
                        self.recommendation_state["feedback_loop"].clear()

                except Exception as e:
                    logger.error(f"Continuous training error: {e}")

                # Train every 6 hours
                await asyncio.sleep(21600)

        except asyncio.CancelledError:
            logger.info("Continuous training cancelled")
            raise

    async def _continuous_recommendation_updates(self):
        """
        Continuous recommendation updates
        """
        try:
            while True:
                try:
                    # Update trending items
                    await self._update_trending_items()

                    # Refresh recommendation cache
                    await self._refresh_recommendation_cache()

                except Exception as e:
                    logger.error(f"Continuous updates error: {e}")

                # Update every hour
                await asyncio.sleep(3600)

        except asyncio.CancelledError:
            logger.info("Continuous updates cancelled")
            raise

    async def _process_feedback_loop(self):
        """
        Process feedback for continuous learning
        """
        try:
            while True:
                try:
                    # Process accumulated feedback
                    if self.recommendation_state["feedback_loop"]:
                        await self._update_models_from_feedback()

                except Exception as e:
                    logger.error(f"Feedback processing error: {e}")

                # Process every 30 minutes
                await asyncio.sleep(1800)

        except asyncio.CancelledError:
            logger.info("Feedback processing cancelled")
            raise

    # Additional helper methods would continue here...

    async def _load_user_profiles(self):
        """Load user profiles from database"""
        try:
            # Implementation for loading user profiles
            pass
        except Exception as e:
            logger.error(f"User profile loading failed: {e}")

    async def _load_item_profiles(self):
        """Load item profiles from database"""
        try:
            # Implementation for loading item profiles
            pass
        except Exception as e:
            logger.error(f"Item profile loading failed: {e}")

    async def _load_interaction_data(self):
        """Load interaction data"""
        try:
            # Implementation for loading interaction data
            pass
        except Exception as e:
            logger.error(f"Interaction data loading failed: {e}")

    async def _build_similarity_matrices(self):
        """Build similarity matrices"""
        try:
            # Implementation for building similarity matrices
            pass
        except Exception as e:
            logger.error(f"Similarity matrix building failed: {e}")

    async def _log_recommendations(
        self, user_id: str, recommendations: list[dict[str, Any]], rec_type: str
    ):
        """Log recommendations"""
        try:
            log_entry = {
                "user_id": user_id,
                "recommendations": recommendations,
                "type": rec_type,
                "timestamp": datetime.now(),
            }
            self.recommendation_state["recommendation_log"].append(log_entry)
        except Exception as e:
            logger.error(f"Recommendation logging failed: {e}")

    async def _update_trending_items(self):
        """Update trending items"""
        try:
            # Implementation for updating trending items
            pass
        except Exception as e:
            logger.error(f"Trending items update failed: {e}")

    async def _refresh_recommendation_cache(self):
        """Refresh recommendation cache"""
        try:
            # Implementation for cache refresh
            pass
        except Exception as e:
            logger.error(f"Cache refresh failed: {e}")

    async def _update_models_from_feedback(self):
        """Update models from feedback"""
        try:
            # Implementation for feedback-based model updates
            pass
        except Exception as e:
            logger.error(f"Feedback-based model update failed: {e}")


# ========== TEST ==========
if __name__ == "__main__":

    async def test_recommendation_agent():
        # Initialize recommendation agent
        agent = RecommendationAgent()
        await agent.start()

        # Test recommendation generation
        test_message = AgentMessage(
            id="test_rec",
            from_agent="test",
            to_agent="recommendation_agent",
            content={
                "type": "get_recommendations",
                "user_id": "user123",
                "recommendation_type": "hybrid",
                "num_recommendations": 5,
                "context": {"time_of_day": "evening", "location": "home", "device_type": "mobile"},
            },
            timestamp=datetime.now(),
        )

        print("Testing recommendation agent...")
        async for response in agent.process_message(test_message):
            print(f"Recommendation response: {response.content.get('type')}")
            recommendations = response.content.get("result", {}).get("recommendations", [])
            print(f"Generated {len(recommendations)} recommendations")

        # Test user feedback
        feedback_message = AgentMessage(
            id="test_feedback",
            from_agent="test",
            to_agent="recommendation_agent",
            content={
                "type": "feedback",
                "user_id": "user123",
                "item_id": "item456",
                "feedback_type": "rating",
                "rating": 4.5,
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(feedback_message):
            print(f"Feedback response: {response.content.get('type')}")

        # Test similar items
        similar_message = AgentMessage(
            id="test_similar",
            from_agent="test",
            to_agent="recommendation_agent",
            content={
                "type": "find_similar_items",
                "item_id": "item456",
                "num_similar": 3,
                "similarity_type": "content",
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(similar_message):
            print(f"Similar items response: {response.content.get('type')}")
            similar_items = response.content.get("result", {}).get("similar_items", [])
            print(f"Found {len(similar_items)} similar items")

        # Stop agent
        await agent.stop()
        print("Recommendation agent test completed")

    # Run test
    asyncio.run(test_recommendation_agent())
