"""
Sentiment Analyzer Agent: Advanced sentiment analysis and NLP processing
Analyzes text sentiment, emotions, and linguistic patterns using ML and rule-based methods
"""
import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
import asyncio
import json
from datetime import datetime, timedelta
from collections import defaultdict, deque
import uuid
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score, f1_score
import xgboost as xgb
import lightgbm as lgb
from textblob import TextBlob
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import spacy
import transformers
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
import torch
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer as VaderSentiment
import re
from collections import Counter
import networkx as nx
from wordcloud import WordCloud
import matplotlib.pyplot as plt

from ..agents.base_agent import BaseAgent, AgentState, AgentMessage
from ..api.database import get_db_session
from ..api.models import SentimentAnalysis, TextProcessing, EmotionDetection

logger = logging.getLogger(__name__)

# Download required NLTK data
try:
    nltk.download('vader_lexicon', quiet=True)
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('wordnet', quiet=True)
except Exception as e:
    logger.warning(f"NLTK download failed: {e}")


class SentimentAnalyzerAgent(BaseAgent):
    """
    Sentiment Analyzer Agent for comprehensive text analysis and NLP processing
    Uses multiple ML models and linguistic analysis for sentiment, emotion, and text understanding
    """
    
    def __init__(
        self,
        agent_id: str = "sentiment_analyzer_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # Sentiment analysis configuration
        self.sentiment_config = {
            "analysis_methods": self.config.get("analysis_methods", [
                "rule_based", "ml_models", "transformer_models", "lexical_analysis",
                "emotion_detection", "aspect_sentiment", "contextual_analysis"
            ]),
            "supported_languages": self.config.get("supported_languages", [
                "en", "uk", "ru", "de", "fr", "es", "it", "pt", "zh", "ja"
            ]),
            "sentiment_classes": self.config.get("sentiment_classes", [
                "very_negative", "negative", "neutral", "positive", "very_positive"
            ]),
            "emotion_classes": self.config.get("emotion_classes", [
                "joy", "sadness", "anger", "fear", "surprise", "disgust", "trust", "anticipation"
            ]),
            "confidence_threshold": self.config.get("confidence_threshold", 0.6),
            "batch_size": self.config.get("batch_size", 32),
            "max_text_length": self.config.get("max_text_length", 512)
        }
        
        # NLP models and pipelines
        self.sentiment_models = {}
        self.emotion_models = {}
        self.transformer_pipelines = {}
        self.scalers = {}
        self.label_encoders = {}
        
        # Linguistic analysis tools
        self.nlp_tools = {}
        
        # Text processing storage
        self.text_cache = defaultdict(dict)
        self.sentiment_history = defaultdict(list)
        self.emotion_patterns = defaultdict(list)
        
        # Analysis results storage
        self.analysis_results = defaultdict(dict)
        
        # Background tasks
        self.model_update_task = None
        self.language_detection_task = None
        self.pattern_analysis_task = None
        
        logger.info(f"Sentiment Analyzer Agent initialized: {agent_id}")
    
    async def start(self):
        """
        Start the sentiment analyzer agent
        """
        await super().start()
        
        # Initialize NLP tools and models
        await self._initialize_nlp_tools()
        await self._initialize_sentiment_models()
        await self._initialize_transformer_models()
        
        # Start background tasks
        self.model_update_task = asyncio.create_task(self._model_update_loop())
        self.language_detection_task = asyncio.create_task(self._language_detection_loop())
        self.pattern_analysis_task = asyncio.create_task(self._pattern_analysis_loop())
        
        logger.info("Sentiment analysis monitoring started")
    
    async def stop(self):
        """
        Stop the sentiment analyzer agent
        """
        if self.model_update_task:
            self.model_update_task.cancel()
            try:
                await self.model_update_task
            except asyncio.CancelledError:
                pass
        
        if self.language_detection_task:
            self.language_detection_task.cancel()
            try:
                await self.language_detection_task
            except asyncio.CancelledError:
                pass
        
        if self.pattern_analysis_task:
            self.pattern_analysis_task.cancel()
            try:
                await self.pattern_analysis_task
            except asyncio.CancelledError:
                pass
        
        await super().stop()
        logger.info("Sentiment analyzer agent stopped")
    
    async def _initialize_nlp_tools(self):
        """
        Initialize NLP tools and libraries
        """
        try:
            # NLTK tools
            self.nlp_tools["vader"] = VaderSentiment()
            self.nlp_tools["lemmatizer"] = WordNetLemmatizer()
            self.nlp_tools["stopwords"] = set(stopwords.words('english'))
            
            # spaCy models (for multiple languages)
            spacy_models = {
                "en": "en_core_web_sm",
                "de": "de_core_news_sm",
                "fr": "fr_core_news_sm",
                "es": "es_core_news_sm"
            }
            
            for lang, model_name in spacy_models.items():
                try:
                    self.nlp_tools[f"spacy_{lang}"] = spacy.load(model_name)
                except OSError:
                    logger.warning(f"spaCy model {model_name} not available")
            
            # TextBlob
            self.nlp_tools["textblob"] = TextBlob
            
            logger.info("NLP tools initialized")
            
        except Exception as e:
            logger.error(f"NLP tools initialization failed: {e}")
    
    async def _initialize_sentiment_models(self):
        """
        Initialize traditional ML sentiment models
        """
        try:
            # Ensemble models for sentiment classification
            self.sentiment_models = {
                "random_forest": RandomForestClassifier(
                    n_estimators=100,
                    random_state=42
                ),
                "gradient_boosting": GradientBoostingClassifier(
                    n_estimators=100,
                    random_state=42
                ),
                "xgboost": xgb.XGBClassifier(
                    n_estimators=100,
                    random_state=42
                ),
                "lightgbm": lgb.LGBMClassifier(
                    n_estimators=100,
                    random_state=42
                )
            }
            
            # Emotion detection models
            self.emotion_models = {
                "emotion_rf": RandomForestClassifier(
                    n_estimators=100,
                    random_state=42
                ),
                "emotion_xgb": xgb.XGBClassifier(
                    n_estimators=100,
                    random_state=42
                )
            }
            
            # Initialize scalers and encoders
            for model_name in self.sentiment_models:
                self.scalers[model_name] = StandardScaler()
                self.label_encoders[model_name] = LabelEncoder()
            
            for model_name in self.emotion_models:
                self.scalers[model_name] = StandardScaler()
                self.label_encoders[model_name] = LabelEncoder()
            
            logger.info("Sentiment models initialized")
            
        except Exception as e:
            logger.error(f"Sentiment models initialization failed: {e}")
    
    async def _initialize_transformer_models(self):
        """
        Initialize transformer-based models
        """
        try:
            # Sentiment analysis pipelines
            sentiment_models = {
                "cardiffnlp/twitter-roberta-base-sentiment": "cardiffnlp/twitter-roberta-base-sentiment",
                "nlptown/bert-base-multilingual-uncased-sentiment": "nlptown/bert-base-multilingual-uncased-sentiment",
                "j-hartmann/emotion-english-distilroberta-base": "j-hartmann/emotion-english-distilroberta-base"
            }
            
            for model_name, model_path in sentiment_models.items():
                try:
                    self.transformer_pipelines[model_name] = pipeline(
                        "sentiment-analysis" if "sentiment" in model_name else "text-classification",
                        model=model_path,
                        tokenizer=model_path,
                        return_all_scores=True,
                        truncation=True,
                        max_length=self.sentiment_config["max_text_length"]
                    )
                    logger.info(f"Loaded transformer model: {model_name}")
                    
                except Exception as e:
                    logger.warning(f"Failed to load transformer model {model_name}: {e}")
            
            # Custom emotion detection pipeline
            try:
                emotion_tokenizer = AutoTokenizer.from_pretrained("j-hartmann/emotion-english-distilroberta-base")
                emotion_model = AutoModelForSequenceClassification.from_pretrained("j-hartmann/emotion-english-distilroberta-base")
                self.transformer_pipelines["emotion_detection"] = pipeline(
                    "text-classification",
                    model=emotion_model,
                    tokenizer=emotion_tokenizer,
                    return_all_scores=True
                )
            except Exception as e:
                logger.warning(f"Failed to load emotion detection model: {e}")
            
            logger.info("Transformer models initialized")
            
        except Exception as e:
            logger.error(f"Transformer models initialization failed: {e}")
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process sentiment analysis requests
        """
        try:
            message_type = message.content.get("type", "")
            
            if message_type == "analyze_sentiment":
                async for response in self._handle_sentiment_analysis(message):
                    yield response
                    
            elif message_type == "detect_emotion":
                async for response in self._handle_emotion_detection(message):
                    yield response
                    
            elif message_type == "analyze_text":
                async for response in self._handle_text_analysis(message):
                    yield response
                    
            elif message_type == "aspect_sentiment":
                async for response in self._handle_aspect_sentiment(message):
                    yield response
                    
            elif message_type == "linguistic_analysis":
                async for response in self._handle_linguistic_analysis(message):
                    yield response
                    
            elif message_type == "sentiment_trends":
                async for response in self._handle_sentiment_trends(message):
                    yield response
                    
            elif message_type == "text_processing":
                async for response in self._handle_text_processing(message):
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
            logger.error(f"Sentiment analysis processing failed: {e}")
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
    
    async def _model_update_loop(self):
        """
        Periodic model update and retraining loop
        """
        try:
            while True:
                try:
                    # Update models with new data
                    await self._update_sentiment_models()
                    
                    # Retrain emotion models
                    await self._update_emotion_models()
                    
                except Exception as e:
                    logger.error(f"Model update error: {e}")
                
                # Wait for update interval
                await asyncio.sleep(3600)  # Update every hour
                
        except asyncio.CancelledError:
            logger.info("Model update loop cancelled")
            raise
    
    async def _language_detection_loop(self):
        """
        Language detection and processing loop
        """
        try:
            while True:
                try:
                    # Process multilingual content
                    await self._process_multilingual_content()
                    
                except Exception as e:
                    logger.error(f"Language detection error: {e}")
                
                # Wait for processing interval
                await asyncio.sleep(1800)  # Process every 30 minutes
                
        except asyncio.CancelledError:
            logger.info("Language detection loop cancelled")
            raise
    
    async def _pattern_analysis_loop(self):
        """
        Pattern analysis and trend detection loop
        """
        try:
            while True:
                try:
                    # Analyze sentiment patterns
                    await self._analyze_sentiment_patterns()
                    
                    # Detect emerging trends
                    await self._detect_emerging_trends()
                    
                except Exception as e:
                    logger.error(f"Pattern analysis error: {e}")
                
                # Wait for analysis interval
                await asyncio.sleep(900)  # Analyze every 15 minutes
                
        except asyncio.CancelledError:
            logger.info("Pattern analysis loop cancelled")
            raise
    
    async def _handle_sentiment_analysis(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle sentiment analysis request
        """
        try:
            text = message.content.get("text", "")
            method = message.content.get("method", "ensemble")
            language = message.content.get("language", "auto")
            
            if not text:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Text content required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Detect language if auto
            if language == "auto":
                language = self._detect_language(text)
            
            # Perform sentiment analysis
            sentiment_result = await self._analyze_sentiment(text, method, language)
            
            # Cache result
            text_hash = hash(text)
            self.text_cache[text_hash] = {
                "text": text,
                "sentiment": sentiment_result,
                "language": language,
                "analyzed_at": datetime.now()
            }
            
            # Store in history
            self.sentiment_history[language].append({
                "text_hash": text_hash,
                "sentiment": sentiment_result,
                "timestamp": datetime.now()
            })
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "sentiment_analysis_response",
                    "text_hash": text_hash,
                    "language": language,
                    "sentiment": sentiment_result
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Sentiment analysis handling failed: {e}")
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
    
    async def _analyze_sentiment(self, text: str, method: str, language: str) -> Dict[str, Any]:
        """
        Analyze sentiment using specified method
        """
        try:
            results = {}
            
            if method == "rule_based" or method == "ensemble":
                results["rule_based"] = self._rule_based_sentiment(text, language)
            
            if method == "ml_models" or method == "ensemble":
                results["ml_models"] = await self._ml_sentiment_analysis(text)
            
            if method == "transformer" or method == "ensemble":
                results["transformer"] = await self._transformer_sentiment_analysis(text)
            
            if method == "lexical" or method == "ensemble":
                results["lexical"] = self._lexical_sentiment_analysis(text)
            
            # Ensemble result
            if method == "ensemble" and len(results) > 1:
                ensemble_result = self._calculate_ensemble_sentiment(results)
                results["ensemble"] = ensemble_result
            
            # Add metadata
            final_result = results.get(method, results.get("ensemble", {}))
            final_result.update({
                "method_used": method,
                "language": language,
                "text_length": len(text),
                "confidence_score": self._calculate_confidence_score(results),
                "analyzed_at": datetime.now()
            })
            
            return final_result
            
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return {"error": str(e), "sentiment": "neutral", "confidence": 0.0}
    
    def _rule_based_sentiment(self, text: str, language: str) -> Dict[str, Any]:
        """
        Rule-based sentiment analysis
        """
        try:
            results = {}
            
            # TextBlob analysis
            blob = TextBlob(text)
            results["textblob"] = {
                "polarity": blob.sentiment.polarity,
                "subjectivity": blob.sentiment.subjectivity,
                "sentiment": self._polarity_to_sentiment(blob.sentiment.polarity)
            }
            
            # VADER analysis (English)
            if language == "en":
                vader = self.nlp_tools.get("vader")
                if vader:
                    vader_scores = vader.polarity_scores(text)
                    results["vader"] = {
                        "compound": vader_scores["compound"],
                        "positive": vader_scores["pos"],
                        "negative": vader_scores["neg"],
                        "neutral": vader_scores["neu"],
                        "sentiment": self._compound_to_sentiment(vader_scores["compound"])
                    }
            
            # Average results
            polarities = [r.get("polarity", r.get("compound", 0)) for r in results.values()]
            avg_polarity = np.mean(polarities) if polarities else 0
            
            return {
                "method": "rule_based",
                "polarity": float(avg_polarity),
                "sentiment": self._polarity_to_sentiment(avg_polarity),
                "components": results,
                "confidence": min(0.9, 0.5 + abs(avg_polarity) * 0.4)
            }
            
        except Exception as e:
            logger.error(f"Rule-based sentiment analysis failed: {e}")
            return {"error": str(e), "sentiment": "neutral", "polarity": 0.0}
    
    def _polarity_to_sentiment(self, polarity: float) -> str:
        """Convert polarity score to sentiment label"""
        if polarity > 0.3:
            return "very_positive"
        elif polarity > 0.1:
            return "positive"
        elif polarity > -0.1:
            return "neutral"
        elif polarity > -0.3:
            return "negative"
        else:
            return "very_negative"
    
    def _compound_to_sentiment(self, compound: float) -> str:
        """Convert VADER compound score to sentiment label"""
        if compound > 0.5:
            return "very_positive"
        elif compound > 0.05:
            return "positive"
        elif compound > -0.05:
            return "neutral"
        elif compound > -0.5:
            return "negative"
        else:
            return "very_negative"
    
    async def _ml_sentiment_analysis(self, text: str) -> Dict[str, Any]:
        """
        ML-based sentiment analysis using ensemble models
        """
        try:
            # Extract features
            features = self._extract_sentiment_features(text)
            
            if not features:
                return {"error": "Feature extraction failed"}
            
            features_array = np.array([features])
            predictions = {}
            
            # Get predictions from each model
            for model_name, model in self.sentiment_models.items():
                try:
                    scaler = self.scalers.get(model_name)
                    if scaler:
                        scaled_features = scaler.transform(features_array)
                        probs = model.predict_proba(scaled_features)[0]
                        
                        # Map probabilities to sentiment classes
                        sentiment_idx = np.argmax(probs)
                        sentiment_label = self.sentiment_config["sentiment_classes"][sentiment_idx]
                        
                        predictions[model_name] = {
                            "sentiment": sentiment_label,
                            "probabilities": {cls: float(prob) for cls, prob in zip(self.sentiment_config["sentiment_classes"], probs)},
                            "confidence": float(probs[sentiment_idx])
                        }
                        
                except Exception as e:
                    logger.error(f"ML model prediction failed for {model_name}: {e}")
            
            # Ensemble prediction
            if predictions:
                sentiment_votes = Counter([pred["sentiment"] for pred in predictions.values()])
                ensemble_sentiment = sentiment_votes.most_common(1)[0][0]
                
                avg_confidence = np.mean([pred["confidence"] for pred in predictions.values()])
                
                return {
                    "method": "ml_models",
                    "ensemble_sentiment": ensemble_sentiment,
                    "model_predictions": predictions,
                    "confidence": float(avg_confidence),
                    "agreement_score": sentiment_votes[ensemble_sentiment] / len(predictions)
                }
            
            return {"error": "No model predictions available"}
            
        except Exception as e:
            logger.error(f"ML sentiment analysis failed: {e}")
            return {"error": str(e)}
    
    def _extract_sentiment_features(self, text: str) -> Optional[List[float]]:
        """
        Extract features for ML sentiment analysis
        """
        try:
            features = []
            
            # Basic text features
            features.extend([
                len(text),  # Text length
                len(text.split()),  # Word count
                len(sent_tokenize(text)),  # Sentence count
                text.count('!'),  # Exclamation marks
                text.count('?'),  # Question marks
                text.count(':)'),  # Emoticons
                text.count(':('),  # Sad emoticons
            ])
            
            # Sentiment word counts
            positive_words = ['good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic', 'love', 'like', 'best']
            negative_words = ['bad', 'terrible', 'awful', 'hate', 'worst', 'horrible', 'disappointing', 'poor']
            
            words = text.lower().split()
            features.append(sum(1 for word in words if word in positive_words))
            features.append(sum(1 for word in words if word in negative_words))
            
            # Capitalization features
            features.extend([
                sum(1 for c in text if c.isupper()) / len(text) if text else 0,  # Uppercase ratio
                len([word for word in words if word.isupper()])  # All caps words
            ])
            
            # Punctuation features
            features.extend([
                text.count('...'),  # Ellipsis
                text.count('!!'),  # Double exclamation
                text.count('??'),  # Double question
            ])
            
            return features
            
        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return None
    
    async def _transformer_sentiment_analysis(self, text: str) -> Dict[str, Any]:
        """
        Transformer-based sentiment analysis
        """
        try:
            results = {}
            
            # Use available transformer pipelines
            for model_name, pipeline_func in self.transformer_pipelines.items():
                if "sentiment" in model_name.lower():
                    try:
                        predictions = pipeline_func(text)
                        
                        # Process predictions
                        sentiment_scores = {}
                        for pred in predictions[0] if isinstance(predictions, list) and predictions else predictions:
                            if isinstance(pred, dict):
                                label = pred.get("label", "").lower()
                                score = pred.get("score", 0)
                                
                                # Map to our sentiment classes
                                if "positive" in label or "pos" in label:
                                    if score > 0.5:
                                        sentiment_scores["positive" if score > 0.7 else "very_positive"] = score
                                    else:
                                        sentiment_scores["neutral"] = score
                                elif "negative" in label or "neg" in label:
                                    if score > 0.5:
                                        sentiment_scores["negative" if score > 0.7 else "very_negative"] = score
                                    else:
                                        sentiment_scores["neutral"] = score
                                else:
                                    sentiment_scores["neutral"] = score
                        
                        results[model_name] = {
                            "predictions": predictions,
                            "sentiment_scores": sentiment_scores,
                            "top_sentiment": max(sentiment_scores.items(), key=lambda x: x[1]) if sentiment_scores else ("neutral", 0.5)
                        }
                        
                    except Exception as e:
                        logger.error(f"Transformer model {model_name} failed: {e}")
            
            # Aggregate results
            if results:
                all_scores = {}
                for model_result in results.values():
                    for sentiment, score in model_result["sentiment_scores"].items():
                        all_scores[sentiment] = all_scores.get(sentiment, []) + [score]
                
                # Average scores across models
                avg_scores = {sent: np.mean(scores) for sent, scores in all_scores.items()}
                
                if avg_scores:
                    top_sentiment = max(avg_scores.items(), key=lambda x: x[1])
                    
                    return {
                        "method": "transformer",
                        "top_sentiment": top_sentiment[0],
                        "sentiment_scores": avg_scores,
                        "confidence": float(top_sentiment[1]),
                        "model_results": results
                    }
            
            return {"error": "No transformer results available"}
            
        except Exception as e:
            logger.error(f"Transformer sentiment analysis failed: {e}")
            return {"error": str(e)}
    
    def _lexical_sentiment_analysis(self, text: str) -> Dict[str, Any]:
        """
        Lexical-based sentiment analysis
        """
        try:
            # Simple lexicon-based approach
            positive_lexicon = {
                'good': 1, 'great': 2, 'excellent': 2, 'amazing': 2, 'wonderful': 2,
                'fantastic': 2, 'love': 2, 'like': 1, 'best': 1, 'awesome': 2,
                'perfect': 2, 'brilliant': 2, 'outstanding': 2, 'superb': 2
            }
            
            negative_lexicon = {
                'bad': -1, 'terrible': -2, 'awful': -2, 'hate': -2, 'worst': -1,
                'horrible': -2, 'disappointing': -1, 'poor': -1, 'awful': -2,
                'terrible': -2, 'hate': -2, 'worst': -1, 'horrible': -2
            }
            
            words = text.lower().split()
            positive_score = sum(positive_lexicon.get(word, 0) for word in words)
            negative_score = sum(abs(negative_lexicon.get(word, 0)) for word in words)
            
            total_score = positive_score - negative_score
            total_words = len([w for w in words if w in positive_lexicon or w in negative_lexicon])
            
            if total_words == 0:
                return {"sentiment": "neutral", "score": 0, "confidence": 0.5}
            
            normalized_score = total_score / total_words
            
            sentiment = self._polarity_to_sentiment(normalized_score / 2)  # Scale down
            
            return {
                "method": "lexical",
                "sentiment": sentiment,
                "score": float(normalized_score),
                "positive_words": positive_score,
                "negative_words": negative_score,
                "matched_words": total_words,
                "confidence": min(0.9, 0.3 + abs(normalized_score) * 0.6)
            }
            
        except Exception as e:
            logger.error(f"Lexical sentiment analysis failed: {e}")
            return {"error": str(e), "sentiment": "neutral"}
    
    def _calculate_ensemble_sentiment(self, results: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Calculate ensemble sentiment from multiple methods
        """
        try:
            sentiment_votes = Counter()
            polarity_scores = []
            confidence_scores = []
            
            for method, result in results.items():
                if "sentiment" in result:
                    sentiment = result["sentiment"]
                    sentiment_votes[sentiment] += 1
                    
                    # Extract polarity if available
                    if "polarity" in result:
                        polarity_scores.append(result["polarity"])
                    elif "score" in result:
                        polarity_scores.append(result["score"])
                    
                    # Extract confidence
                    if "confidence" in result:
                        confidence_scores.append(result["confidence"])
            
            # Determine ensemble sentiment
            if sentiment_votes:
                ensemble_sentiment = sentiment_votes.most_common(1)[0][0]
            else:
                ensemble_sentiment = "neutral"
            
            # Calculate average polarity and confidence
            avg_polarity = np.mean(polarity_scores) if polarity_scores else 0
            avg_confidence = np.mean(confidence_scores) if confidence_scores else 0.5
            
            return {
                "sentiment": ensemble_sentiment,
                "polarity": float(avg_polarity),
                "confidence": float(avg_confidence),
                "method_agreement": sentiment_votes[ensemble_sentiment] / len(results) if results else 0,
                "components": results
            }
            
        except Exception as e:
            logger.error(f"Ensemble sentiment calculation failed: {e}")
            return {"sentiment": "neutral", "confidence": 0.0}
    
    def _calculate_confidence_score(self, results: Dict[str, Dict]) -> float:
        """
        Calculate overall confidence score
        """
        try:
            confidences = []
            
            for result in results.values():
                if "confidence" in result:
                    confidences.append(result["confidence"])
                elif "polarity" in result:
                    # Estimate confidence from polarity strength
                    confidences.append(min(0.9, 0.5 + abs(result["polarity"]) * 0.4))
            
            return float(np.mean(confidences)) if confidences else 0.5
            
        except Exception as e:
            return 0.5
    
    def _detect_language(self, text: str) -> str:
        """
        Simple language detection
        """
        try:
            # Basic language detection using character patterns
            cyrillic_chars = sum(1 for c in text if ord(c) > 1024 and ord(c) < 1328)
            latin_chars = sum(1 for c in text if ord(c) < 128)
            
            if cyrillic_chars > latin_chars * 0.3:
                return "uk" if "ї" in text.lower() or "є" in text.lower() else "ru"
            else:
                return "en"  # Default to English
                
        except Exception as e:
            return "en"
    
    async def _handle_emotion_detection(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle emotion detection request
        """
        try:
            text = message.content.get("text", "")
            
            if not text:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Text content required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Detect emotions
            emotions = await self._detect_emotions(text)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "emotion_detection_response",
                    "text_hash": hash(text),
                    "emotions": emotions
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Emotion detection handling failed: {e}")
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
    
    async def _detect_emotions(self, text: str) -> Dict[str, Any]:
        """
        Detect emotions in text
        """
        try:
            emotions = {}
            
            # Use transformer model for emotion detection
            emotion_pipeline = self.transformer_pipelines.get("emotion_detection")
            if emotion_pipeline:
                try:
                    predictions = emotion_pipeline(text)
                    
                    for pred in predictions[0] if isinstance(predictions, list) else predictions:
                        emotion = pred.get("label", "").lower()
                        score = pred.get("score", 0)
                        emotions[emotion] = float(score)
                        
                except Exception as e:
                    logger.error(f"Transformer emotion detection failed: {e}")
            
            # Rule-based emotion detection as fallback
            rule_emotions = self._rule_based_emotion_detection(text)
            
            if not emotions:
                emotions = rule_emotions
            else:
                # Combine with rule-based results
                for emotion, score in rule_emotions.items():
                    emotions[emotion] = emotions.get(emotion, 0) * 0.7 + score * 0.3
            
            # Normalize scores
            total_score = sum(emotions.values())
            if total_score > 0:
                emotions = {k: v/total_score for k, v in emotions.items()}
            
            # Get top emotions
            top_emotions = sorted(emotions.items(), key=lambda x: x[1], reverse=True)[:3]
            
            return {
                "emotions": emotions,
                "top_emotions": top_emotions,
                "primary_emotion": top_emotions[0][0] if top_emotions else "neutral",
                "emotion_intensity": top_emotions[0][1] if top_emotions else 0.0,
                "detected_at": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Emotion detection failed: {e}")
            return {"error": str(e), "primary_emotion": "neutral"}
    
    def _rule_based_emotion_detection(self, text: str) -> Dict[str, float]:
        """
        Rule-based emotion detection
        """
        try:
            emotion_lexicons = {
                "joy": ['happy', 'joy', 'delight', 'pleasure', 'excited', 'wonderful', 'amazing', 'great'],
                "sadness": ['sad', 'unhappy', 'depressed', 'sorry', 'disappointed', 'miserable', 'gloomy'],
                "anger": ['angry', 'furious', 'mad', 'annoyed', 'irritated', 'frustrated', 'hate'],
                "fear": ['fear', 'afraid', 'scared', 'terrified', 'anxious', 'worried', 'nervous'],
                "surprise": ['surprise', 'amazed', 'astonished', 'shocked', 'unexpected', 'wow'],
                "disgust": ['disgust', 'disgusted', 'repulsive', 'gross', 'nasty', 'awful'],
                "trust": ['trust', 'reliable', 'honest', 'faithful', 'confident', 'believe'],
                "anticipation": ['hope', 'expect', 'wait', 'anticipate', 'look forward', 'excited']
            }
            
            words = text.lower().split()
            emotions = {}
            
            for emotion, keywords in emotion_lexicons.items():
                count = sum(1 for word in words if word in keywords)
                emotions[emotion] = min(1.0, count / len(words) * 10) if words else 0.0
            
            return emotions
            
        except Exception as e:
            logger.error(f"Rule-based emotion detection failed: {e}")
            return {}
    
    async def _handle_text_analysis(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle comprehensive text analysis request
        """
        try:
            text = message.content.get("text", "")
            
            if not text:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Text content required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Perform comprehensive analysis
            analysis = await self._comprehensive_text_analysis(text)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "text_analysis_response",
                    "text_hash": hash(text),
                    "analysis": analysis
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Text analysis handling failed: {e}")
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
    
    async def _comprehensive_text_analysis(self, text: str) -> Dict[str, Any]:
        """
        Perform comprehensive text analysis
        """
        try:
            analysis = {
                "basic_stats": self._get_text_statistics(text),
                "linguistic_features": self._extract_linguistic_features(text),
                "sentiment": await self._analyze_sentiment(text, "ensemble", "auto"),
                "emotions": await self._detect_emotions(text),
                "readability": self._calculate_readability(text),
                "topics": self._extract_topics(text),
                "entities": self._extract_entities(text),
                "analyzed_at": datetime.now()
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Comprehensive text analysis failed: {e}")
            return {"error": str(e)}
    
    def _get_text_statistics(self, text: str) -> Dict[str, Any]:
        """
        Get basic text statistics
        """
        try:
            sentences = sent_tokenize(text)
            words = word_tokenize(text)
            
            return {
                "char_count": len(text),
                "word_count": len(words),
                "sentence_count": len(sentences),
                "avg_word_length": np.mean([len(word) for word in words]) if words else 0,
                "avg_sentence_length": len(words) / len(sentences) if sentences else 0,
                "unique_words": len(set(words)),
                "lexical_diversity": len(set(words)) / len(words) if words else 0
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _extract_linguistic_features(self, text: str) -> Dict[str, Any]:
        """
        Extract linguistic features
        """
        try:
            words = word_tokenize(text.lower())
            stop_words = self.nlp_tools.get("stopwords", set())
            
            # Remove stopwords
            content_words = [w for w in words if w not in stop_words and w.isalnum()]
            
            # POS tagging (simplified)
            pos_counts = {}
            for word in words:
                if word.endswith('ing'):
                    pos_counts['gerund'] = pos_counts.get('gerund', 0) + 1
                elif word.endswith('ed'):
                    pos_counts['past_tense'] = pos_counts.get('past_tense', 0) + 1
                elif word.endswith('ly'):
                    pos_counts['adverb'] = pos_counts.get('adverb', 0) + 1
            
            return {
                "content_words": len(content_words),
                "stop_words": len([w for w in words if w in stop_words]),
                "pos_distribution": pos_counts,
                "capitalized_words": sum(1 for w in words if w[0].isupper()),
                "numeric_tokens": sum(1 for w in words if w.isdigit())
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _calculate_readability(self, text: str) -> Dict[str, Any]:
        """
        Calculate text readability metrics
        """
        try:
            sentences = sent_tokenize(text)
            words = word_tokenize(text)
            
            if not sentences or not words:
                return {"flesch_score": 0, "grade_level": 0}
            
            # Simplified Flesch Reading Ease
            avg_sentence_length = len(words) / len(sentences)
            avg_syllables_per_word = np.mean([self._count_syllables(word) for word in words])
            
            flesch_score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
            flesch_score = max(0, min(100, flesch_score))
            
            # Grade level estimation
            grade_level = 0.39 * avg_sentence_length + 11.8 * avg_syllables_per_word - 15.59
            
            return {
                "flesch_score": float(flesch_score),
                "grade_level": float(grade_level),
                "avg_sentence_length": float(avg_sentence_length),
                "avg_syllables_per_word": float(avg_syllables_per_word),
                "readability_level": "easy" if flesch_score > 60 else "standard" if flesch_score > 30 else "difficult"
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _count_syllables(self, word: str) -> int:
        """
        Count syllables in a word (simplified)
        """
        word = word.lower()
        count = 0
        vowels = "aeiouy"
        prev_vowel = False
        
        for char in word:
            if char in vowels:
                if not prev_vowel:
                    count += 1
                prev_vowel = True
            else:
                prev_vowel = False
        
        if word.endswith("e"):
            count -= 1
        if count == 0:
            count += 1
            
        return count
    
    def _extract_topics(self, text: str) -> List[str]:
        """
        Extract topics from text (simplified keyword extraction)
        """
        try:
            words = word_tokenize(text.lower())
            stop_words = self.nlp_tools.get("stopwords", set())
            
            # Remove stopwords and punctuation
            keywords = [w for w in words if w not in stop_words and w.isalnum() and len(w) > 3]
            
            # Get most common words
            word_freq = Counter(keywords)
            topics = [word for word, freq in word_freq.most_common(10)]
            
            return topics
            
        except Exception as e:
            return []
    
    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract named entities from text
        """
        try:
            entities = {"persons": [], "organizations": [], "locations": []}
            
            # Use spaCy if available
            nlp = self.nlp_tools.get("spacy_en")
            if nlp:
                doc = nlp(text)
                
                for ent in doc.ents:
                    if ent.label_ == "PERSON":
                        entities["persons"].append(ent.text)
                    elif ent.label_ == "ORG":
                        entities["organizations"].append(ent.text)
                    elif ent.label_ == "GPE" or ent.label_ == "LOC":
                        entities["locations"].append(ent.text)
            
            # Fallback: simple pattern matching
            if not any(entities.values()):
                # Simple person detection (capitalized words)
                words = text.split()
                potential_persons = [w for w in words if w[0].isupper() and len(w) > 1]
                entities["persons"] = list(set(potential_persons))[:5]
            
            return entities
            
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_aspect_sentiment(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle aspect-based sentiment analysis
        """
        try:
            text = message.content.get("text", "")
            aspects = message.content.get("aspects", [])
            
            if not text:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Text content required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Perform aspect-based sentiment analysis
            aspect_sentiments = await self._analyze_aspect_sentiment(text, aspects)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "aspect_sentiment_response",
                    "text_hash": hash(text),
                    "aspect_sentiments": aspect_sentiments
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Aspect sentiment handling failed: {e}")
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
    
    async def _analyze_aspect_sentiment(self, text: str, aspects: List[str]) -> Dict[str, Any]:
        """
        Analyze sentiment for specific aspects
        """
        try:
            aspect_results = {}
            
            if not aspects:
                # Auto-extract aspects
                aspects = self._extract_topics(text)[:5]
            
            sentences = sent_tokenize(text)
            
            for aspect in aspects:
                aspect_sentences = []
                aspect_sentiments = []
                
                # Find sentences containing the aspect
                for sentence in sentences:
                    if aspect.lower() in sentence.lower():
                        aspect_sentences.append(sentence)
                        
                        # Analyze sentiment of the sentence
                        sent_result = await self._analyze_sentiment(sentence, "ensemble", "auto")
                        aspect_sentiments.append(sent_result)
                
                if aspect_sentiments:
                    # Aggregate sentiment for this aspect
                    polarities = [s.get("polarity", 0) for s in aspect_sentiments]
                    avg_polarity = np.mean(polarities)
                    
                    aspect_results[aspect] = {
                        "sentiment": self._polarity_to_sentiment(avg_polarity),
                        "polarity": float(avg_polarity),
                        "confidence": float(np.mean([s.get("confidence", 0.5) for s in aspect_sentiments])),
                        "mention_count": len(aspect_sentences),
                        "sample_sentences": aspect_sentences[:3]
                    }
                else:
                    aspect_results[aspect] = {
                        "sentiment": "neutral",
                        "polarity": 0.0,
                        "confidence": 0.0,
                        "mention_count": 0,
                        "sample_sentences": []
                    }
            
            return {
                "aspects_analyzed": aspects,
                "aspect_results": aspect_results,
                "overall_sentiment": self._calculate_overall_aspect_sentiment(aspect_results),
                "analyzed_at": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Aspect sentiment analysis failed: {e}")
            return {"error": str(e)}
    
    def _calculate_overall_aspect_sentiment(self, aspect_results: Dict[str, Dict]) -> Dict[str, Any]:
        """
        Calculate overall sentiment from aspect sentiments
        """
        try:
            polarities = [result.get("polarity", 0) for result in aspect_results.values()]
            avg_polarity = np.mean(polarities) if polarities else 0
            
            return {
                "overall_sentiment": self._polarity_to_sentiment(avg_polarity),
                "average_polarity": float(avg_polarity),
                "aspect_count": len(aspect_results)
            }
            
        except Exception as e:
            return {"overall_sentiment": "neutral", "average_polarity": 0.0}
    
    async def _handle_linguistic_analysis(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle linguistic analysis request
        """
        try:
            text = message.content.get("text", "")
            
            if not text:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Text content required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Perform linguistic analysis
            linguistic_analysis = self._perform_linguistic_analysis(text)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "linguistic_analysis_response",
                    "text_hash": hash(text),
                    "linguistic_analysis": linguistic_analysis
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Linguistic analysis handling failed: {e}")
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
    
    def _perform_linguistic_analysis(self, text: str) -> Dict[str, Any]:
        """
        Perform detailed linguistic analysis
        """
        try:
            analysis = {
                "syntax": self._analyze_syntax(text),
                "semantics": self._analyze_semantics(text),
                "pragmatics": self._analyze_pragmatics(text),
                "discourse": self._analyze_discourse(text),
                "stylistics": self._analyze_stylistics(text)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Linguistic analysis failed: {e}")
            return {"error": str(e)}
    
    def _analyze_syntax(self, text: str) -> Dict[str, Any]:
        """Analyze syntactic structure"""
        try:
            sentences = sent_tokenize(text)
            words = word_tokenize(text)
            
            return {
                "sentence_types": self._classify_sentences(sentences),
                "clause_structure": len(sentences),
                "word_order_patterns": "SVO",  # Simplified
                "grammatical_complexity": len(words) / len(sentences) if sentences else 0
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _classify_sentences(self, sentences: List[str]) -> Dict[str, int]:
        """Classify sentence types"""
        types = {"declarative": 0, "interrogative": 0, "exclamatory": 0, "imperative": 0}
        
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence.endswith('?'):
                types["interrogative"] += 1
            elif sentence.endswith('!'):
                types["exclamatory"] += 1
            elif sentence.lower().startswith(('please', 'do', 'can you', 'will you')):
                types["imperative"] += 1
            else:
                types["declarative"] += 1
        
        return types
    
    def _analyze_semantics(self, text: str) -> Dict[str, Any]:
        """Analyze semantic content"""
        try:
            words = word_tokenize(text.lower())
            
            return {
                "semantic_density": len(set(words)) / len(words) if words else 0,
                "concept_categories": self._extract_semantic_categories(text),
                "meaning_coherence": self._calculate_coherence(text)
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _extract_semantic_categories(self, text: str) -> Dict[str, int]:
        """Extract semantic categories (simplified)"""
        categories = {
            "positive": ['good', 'great', 'excellent', 'amazing', 'wonderful'],
            "negative": ['bad', 'terrible', 'awful', 'hate', 'worst'],
            "technical": ['system', 'data', 'analysis', 'processing', 'algorithm'],
            "business": ['company', 'market', 'sales', 'revenue', 'profit']
        }
        
        words = text.lower().split()
        category_counts = {}
        
        for category, keywords in categories.items():
            count = sum(1 for word in words if word in keywords)
            if count > 0:
                category_counts[category] = count
        
        return category_counts
    
    def _calculate_coherence(self, text: str) -> float:
        """Calculate text coherence (simplified)"""
        try:
            sentences = sent_tokenize(text)
            if len(sentences) < 2:
                return 1.0
            
            # Simple coherence based on word overlap
            coherence_scores = []
            
            for i in range(len(sentences) - 1):
                words1 = set(sentences[i].lower().split())
                words2 = set(sentences[i + 1].lower().split())
                
                overlap = len(words1.intersection(words2))
                union = len(words1.union(words2))
                
                if union > 0:
                    coherence_scores.append(overlap / union)
            
            return float(np.mean(coherence_scores)) if coherence_scores else 0.5
            
        except Exception as e:
            return 0.5
    
    def _analyze_pragmatics(self, text: str) -> Dict[str, Any]:
        """Analyze pragmatic aspects"""
        try:
            return {
                "speech_acts": self._identify_speech_acts(text),
                "implicature": self._detect_implicature(text),
                "context_dependency": self._assess_context_dependency(text)
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _identify_speech_acts(self, text: str) -> List[str]:
        """Identify speech acts (simplified)"""
        acts = []
        
        text_lower = text.lower()
        if '?' in text:
            acts.append("questioning")
        if any(word in text_lower for word in ['please', 'could you', 'would you']):
            acts.append("requesting")
        if any(word in text_lower for word in ['thank', 'thanks', 'appreciate']):
            acts.append("thanking")
        if '!' in text:
            acts.append("exclaiming")
        
        return acts if acts else ["stating"]
    
    def _detect_implicature(self, text: str) -> str:
        """Detect conversational implicature (simplified)"""
        # Very basic implicature detection
        if "obviously" in text.lower() or "clearly" in text.lower():
            return "sarcastic_implicature"
        elif "well" in text.lower() and "?" in text:
            return "hedging_implicature"
        else:
            return "literal_meaning"
    
    def _assess_context_dependency(self, text: str) -> str:
        """Assess context dependency"""
        pronouns = ['it', 'this', 'that', 'these', 'those', 'he', 'she', 'they', 'we']
        pronoun_count = sum(1 for word in text.lower().split() if word in pronouns)
        
        if pronoun_count > len(text.split()) * 0.1:
            return "high_context_dependency"
        else:
            return "low_context_dependency"
    
    def _analyze_discourse(self, text: str) -> Dict[str, Any]:
        """Analyze discourse structure"""
        try:
            sentences = sent_tokenize(text)
            
            return {
                "cohesion": self._measure_cohesion(sentences),
                "coherence": self._measure_coherence(sentences),
                "discourse_markers": self._find_discourse_markers(text)
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _measure_cohesion(self, sentences: List[str]) -> float:
        """Measure textual cohesion"""
        if len(sentences) < 2:
            return 1.0
        
        cohesion_scores = []
        
        for i in range(len(sentences) - 1):
            words1 = set(sentences[i].lower().split())
            words2 = set(sentences[i + 1].lower().split())
            
            # Remove stopwords for better cohesion measurement
            stop_words = self.nlp_tools.get("stopwords", set())
            words1 = words1 - stop_words
            words2 = words2 - stop_words
            
            if words1 and words2:
                overlap = len(words1.intersection(words2))
                cohesion_scores.append(overlap / len(words1.union(words2)))
        
        return float(np.mean(cohesion_scores)) if cohesion_scores else 0.0
    
    def _measure_coherence(self, sentences: List[str]) -> float:
        """Measure discourse coherence"""
        # Simplified coherence based on sentence length consistency
        lengths = [len(sent.split()) for sent in sentences]
        
        if len(lengths) < 2:
            return 1.0
        
        # Coefficient of variation (lower = more coherent)
        cv = np.std(lengths) / np.mean(lengths) if np.mean(lengths) > 0 else 0
        
        # Convert to coherence score (0-1, higher = more coherent)
        coherence = 1 / (1 + cv)
        
        return float(coherence)
    
    def _find_discourse_markers(self, text: str) -> List[str]:
        """Find discourse markers"""
        markers = [
            'however', 'therefore', 'moreover', 'furthermore', 'consequently',
            'nevertheless', 'accordingly', 'similarly', 'likewise', 'instead',
            'although', 'though', 'despite', 'because', 'since', 'as',
            'and', 'but', 'or', 'so', 'then', 'after', 'before', 'while'
        ]
        
        found_markers = []
        words = text.lower().split()
        
        for marker in markers:
            if marker in words:
                found_markers.append(marker)
        
        return list(set(found_markers))
    
    def _analyze_stylistics(self, text: str) -> Dict[str, Any]:
        """Analyze stylistic features"""
        try:
            return {
                "lexical_richness": self._calculate_lexical_richness(text),
                "sentence_variety": self._analyze_sentence_variety(text),
                "figurative_language": self._detect_figurative_language(text),
                "tone": self._determine_tone(text)
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _calculate_lexical_richness(self, text: str) -> float:
        """Calculate lexical richness (diversity)"""
        words = [w.lower() for w in word_tokenize(text) if w.isalnum()]
        
        if not words:
            return 0.0
        
        unique_words = len(set(words))
        total_words = len(words)
        
        # TTR (Type-Token Ratio)
        ttr = unique_words / total_words
        
        # Corrected TTR for text length
        if total_words > 0:
            cttr = unique_words / np.sqrt(2 * total_words)
        else:
            cttr = 0.0
        
        return float(cttr)
    
    def _analyze_sentence_variety(self, text: str) -> Dict[str, Any]:
        """Analyze sentence variety"""
        sentences = sent_tokenize(text)
        
        if not sentences:
            return {"variety_score": 0.0}
        
        lengths = [len(sent.split()) for sent in sentences]
        
        return {
            "avg_length": float(np.mean(lengths)),
            "length_std": float(np.std(lengths)),
            "variety_score": float(1 / (1 + np.std(lengths) / np.mean(lengths))) if np.mean(lengths) > 0 else 0.0
        }
    
    def _detect_figurative_language(self, text: str) -> List[str]:
        """Detect figurative language (simplified)"""
        figures = []
        
        text_lower = text.lower()
        
        # Metaphor detection (very basic)
        if any(phrase in text_lower for phrase in ['like a', 'as a', 'is a']):
            figures.append("metaphor")
        
        # Hyperbole detection
        if any(word in text_lower for word in ['amazing', 'incredible', 'unbelievable', 'fantastic']):
            figures.append("hyperbole")
        
        # Irony/sarcasm indicators
        if 'obviously' in text_lower and '?' in text:
            figures.append("sarcasm")
        
        return figures
    
    def _determine_tone(self, text: str) -> str:
        """Determine overall tone"""
        sentiment = self._rule_based_sentiment(text, "en")
        polarity = sentiment.get("polarity", 0)
        
        if polarity > 0.3:
            return "positive"
        elif polarity < -0.3:
            return "negative"
        else:
            return "neutral"
    
    async def _handle_sentiment_trends(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle sentiment trends analysis request
        """
        try:
            time_window = message.content.get("time_window", 3600)  # seconds
            language = message.content.get("language", "all")
            
            # Analyze sentiment trends
            trends = await self._analyze_sentiment_trends(time_window, language)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "sentiment_trends_response",
                    "time_window_seconds": time_window,
                    "language": language,
                    "trends": trends
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Sentiment trends handling failed: {e}")
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
    
    async def _analyze_sentiment_trends(self, time_window: int, language: str) -> Dict[str, Any]:
        """
        Analyze sentiment trends over time
        """
        try:
            cutoff_time = datetime.now() - timedelta(seconds=time_window)
            
            # Filter sentiment history
            relevant_history = []
            
            for lang, sentiments in self.sentiment_history.items():
                if language == "all" or lang == language:
                    recent_sentiments = [
                        s for s in sentiments 
                        if s.get("timestamp", datetime.min) > cutoff_time
                    ]
                    relevant_history.extend(recent_sentiments)
            
            if not relevant_history:
                return {"status": "no_data"}
            
            # Group by time intervals (e.g., 5-minute windows)
            interval_minutes = 5
            intervals = {}
            
            for sentiment_data in relevant_history:
                timestamp = sentiment_data.get("timestamp", datetime.now())
                
                # Round to nearest interval
                interval_start = timestamp.replace(
                    minute=(timestamp.minute // interval_minutes) * interval_minutes,
                    second=0,
                    microsecond=0
                )
                
                interval_key = interval_start.isoformat()
                
                if interval_key not in intervals:
                    intervals[interval_key] = []
                
                intervals[interval_key].append(sentiment_data)
            
            # Calculate sentiment for each interval
            trend_data = []
            
            for interval, sentiments in sorted(intervals.items()):
                polarities = []
                
                for sentiment_data in sentiments:
                    sentiment_result = sentiment_data.get("sentiment", {})
                    if isinstance(sentiment_result, dict) and "polarity" in sentiment_result:
                        polarities.append(sentiment_result["polarity"])
                    elif isinstance(sentiment_result, str):
                        # Convert sentiment label to polarity
                        polarity_map = {
                            "very_positive": 1.0, "positive": 0.5, "neutral": 0.0,
                            "negative": -0.5, "very_negative": -1.0
                        }
                        polarities.append(polarity_map.get(sentiment_result, 0.0))
                
                if polarities:
                    avg_polarity = np.mean(polarities)
                    trend_data.append({
                        "timestamp": interval,
                        "avg_polarity": float(avg_polarity),
                        "sentiment": self._polarity_to_sentiment(avg_polarity),
                        "sample_count": len(polarities),
                        "polarity_std": float(np.std(polarities))
                    })
            
            # Calculate trend metrics
            if len(trend_data) > 1:
                polarities = [d["avg_polarity"] for d in trend_data]
                slope, intercept, r_value, p_value, std_err = linregress(
                    range(len(polarities)), polarities
                )
                
                trend_direction = "increasing" if slope > 0.01 else "decreasing" if slope < -0.01 else "stable"
                
                return {
                    "trend_data": trend_data,
                    "overall_trend": {
                        "direction": trend_direction,
                        "slope": float(slope),
                        "r_squared": float(r_value ** 2),
                        "significance": float(p_value),
                        "volatility": float(np.std(polarities))
                    },
                    "summary": {
                        "total_samples": len(relevant_history),
                        "time_intervals": len(trend_data),
                        "avg_sentiment": float(np.mean(polarities)),
                        "sentiment_volatility": float(np.std(polarities))
                    }
                }
            
            return {"status": "insufficient_data", "samples": len(relevant_history)}
            
        except Exception as e:
            logger.error(f"Sentiment trends analysis failed: {e}")
            return {"error": str(e)}
    
    async def _handle_text_processing(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle text processing request
        """
        try:
            text = message.content.get("text", "")
            operations = message.content.get("operations", ["normalize"])
            
            if not text:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Text content required"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Process text
            processed_text = await self._process_text(text, operations)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "text_processing_response",
                    "original_text_hash": hash(text),
                    "processed_text": processed_text,
                    "operations_applied": operations
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Text processing handling failed: {e}")
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
    
    async def _process_text(self, text: str, operations: List[str]) -> Dict[str, Any]:
        """
        Process text with specified operations
        """
        try:
            result = {"original_text": text}
            current_text = text
            
            for operation in operations:
                if operation == "normalize":
                    current_text = self._normalize_text(current_text)
                    result["normalized"] = current_text
                    
                elif operation == "tokenize":
                    tokens = word_tokenize(current_text)
                    result["tokens"] = tokens
                    current_text = " ".join(tokens)
                    
                elif operation == "lemmatize":
                    lemmatizer = self.nlp_tools.get("lemmatizer")
                    if lemmatizer:
                        tokens = word_tokenize(current_text)
                        lemmas = [lemmatizer.lemmatize(token) for token in tokens]
                        result["lemmas"] = lemmas
                        current_text = " ".join(lemmas)
                    
                elif operation == "remove_stopwords":
                    stop_words = self.nlp_tools.get("stopwords", set())
                    tokens = word_tokenize(current_text)
                    filtered_tokens = [t for t in tokens if t.lower() not in stop_words]
                    result["filtered_tokens"] = filtered_tokens
                    current_text = " ".join(filtered_tokens)
                    
                elif operation == "extract_keywords":
                    keywords = self._extract_keywords(current_text)
                    result["keywords"] = keywords
                    
                elif operation == "summarize":
                    summary = self._summarize_text(current_text)
                    result["summary"] = summary
            
            result["final_text"] = current_text
            
            return result
            
        except Exception as e:
            logger.error(f"Text processing failed: {e}")
            return {"error": str(e), "original_text": text}
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove punctuation (optional)
        text = re.sub(r'[^\w\s]', '', text)
        
        return text.strip()
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        try:
            words = word_tokenize(text.lower())
            stop_words = self.nlp_tools.get("stopwords", set())
            
            # Remove stopwords and punctuation
            keywords = [w for w in words if w not in stop_words and w.isalnum() and len(w) > 3]
            
            # Get most frequent words
            word_freq = Counter(keywords)
            top_keywords = [word for word, freq in word_freq.most_common(10)]
            
            return top_keywords
            
        except Exception as e:
            return []
    
    def _summarize_text(self, text: str) -> str:
        """Simple text summarization (extractive)"""
        try:
            sentences = sent_tokenize(text)
            
            if len(sentences) <= 3:
                return text
            
            # Simple scoring based on sentence position and length
            scored_sentences = []
            
            for i, sentence in enumerate(sentences):
                # Position score (prefer first and last sentences)
                position_score = 1.0 if i == 0 or i == len(sentences) - 1 else 0.5
                
                # Length score (prefer medium-length sentences)
                word_count = len(sentence.split())
                length_score = 1.0 if 10 <= word_count <= 30 else 0.5
                
                total_score = position_score * length_score
                scored_sentences.append((sentence, total_score))
            
            # Select top sentences
            scored_sentences.sort(key=lambda x: x[1], reverse=True)
            selected_sentences = [s[0] for s in scored_sentences[:3]]
            
            # Reorder to maintain original sequence
            original_order = []
            for sentence in sentences:
                if sentence in selected_sentences:
                    original_order.append(sentence)
            
            return " ".join(original_order)
            
        except Exception as e:
            return text[:200] + "..." if len(text) > 200 else text
    
    async def _update_sentiment_models(self):
        """
        Update sentiment models with new training data
        """
        try:
            # Placeholder - would implement actual model retraining
            logger.info("Sentiment models update completed")
            
        except Exception as e:
            logger.error(f"Sentiment models update failed: {e}")
    
    async def _update_emotion_models(self):
        """
        Update emotion models with new training data
        """
        try:
            # Placeholder - would implement actual model retraining
            logger.info("Emotion models update completed")
            
        except Exception as e:
            logger.error(f"Emotion models update failed: {e}")
    
    async def _process_multilingual_content(self):
        """
        Process multilingual content
        """
        try:
            # Placeholder - would process content in different languages
            logger.info("Multilingual content processing completed")
            
        except Exception as e:
            logger.error(f"Multilingual content processing failed: {e}")
    
    async def _analyze_sentiment_patterns(self):
        """
        Analyze sentiment patterns and trends
        """
        try:
            # Analyze patterns in sentiment data
            for language, sentiments in self.sentiment_history.items():
                if len(sentiments) > 10:
                    recent_sentiments = sentiments[-50:]  # Last 50 analyses
                    
                    # Extract patterns
                    polarities = []
                    for s in recent_sentiments:
                        sentiment_result = s.get("sentiment", {})
                        if isinstance(sentiment_result, dict) and "polarity" in sentiment_result:
                            polarities.append(sentiment_result["polarity"])
                    
                    if polarities:
                        pattern = {
                            "avg_polarity": float(np.mean(polarities)),
                            "volatility": float(np.std(polarities)),
                            "trend": "improving" if polarities[-1] > polarities[0] else "declining",
                            "analyzed_at": datetime.now()
                        }
                        
                        self.sentiment_patterns[language].append(pattern)
            
        except Exception as e:
            logger.error(f"Sentiment pattern analysis failed: {e}")
    
    async def _detect_emerging_trends(self):
        """
        Detect emerging sentiment trends
        """
        try:
            # Simple trend detection
            for language, patterns in self.sentiment_patterns.items():
                if len(patterns) > 5:
                    recent_patterns = patterns[-10:]
                    polarities = [p["avg_polarity"] for p in recent_patterns]
                    
                    # Check for significant changes
                    if len(polarities) >= 3:
                        recent_avg = np.mean(polarities[-3:])
                        earlier_avg = np.mean(polarities[:-3])
                        
                        change = recent_avg - earlier_avg
                        
                        if abs(change) > 0.2:  # Significant change threshold
                            trend = {
                                "language": language,
                                "change": float(change),
                                "direction": "positive" if change > 0 else "negative",
                                "magnitude": "strong" if abs(change) > 0.3 else "moderate",
                                "detected_at": datetime.now()
                            }
                            
                            logger.info(f"Emerging sentiment trend detected: {trend}")
            
        except Exception as e:
            logger.error(f"Emerging trend detection failed: {e}")


# ========== TEST ==========
if __name__ == "__main__":
    async def test_sentiment_analyzer_agent():
        # Initialize sentiment analyzer agent
        agent = SentimentAnalyzerAgent()
        await agent.start()
        
        # Test sentiment analysis
        test_text = "I love this amazing product! It's fantastic and works perfectly."
        
        analysis_message = AgentMessage(
            id="test_analyze",
            from_agent="test",
            to_agent="sentiment_analyzer_agent",
            content={
                "type": "analyze_sentiment",
                "text": test_text,
                "method": "ensemble"
            },
            timestamp=datetime.now()
        )
        
        print("Testing sentiment analyzer agent...")
        async for response in agent.process_message(analysis_message):
            print(f"Sentiment analysis response: {response.content.get('type')}")
            if response.content.get("type") == "sentiment_analysis_response":
                sentiment = response.content.get("sentiment", {})
                print(f"Sentiment: {sentiment.get('sentiment')}, Polarity: {sentiment.get('polarity', 'N/A'):.3f}")
        
        # Test emotion detection
        emotion_message = AgentMessage(
            id="test_emotion",
            from_agent="test",
            to_agent="sentiment_analyzer_agent",
            content={
                "type": "detect_emotion",
                "text": "I'm so excited about this new opportunity! It's going to be amazing."
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(emotion_message):
            print(f"Emotion detection response: {response.content.get('type')}")
            if response.content.get("type") == "emotion_detection_response":
                emotions = response.content.get("emotions", {})
                print(f"Primary emotion: {emotions.get('primary_emotion', 'N/A')}")
        
        # Test text analysis
        analysis_message = AgentMessage(
            id="test_text_analysis",
            from_agent="test",
            to_agent="sentiment_analyzer_agent",
            content={
                "type": "analyze_text",
                "text": test_text
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(analysis_message):
            print(f"Text analysis response: {response.content.get('type')}")
        
        # Stop agent
        await agent.stop()
        print("Sentiment analyzer agent test completed")
    
    # Run test
    asyncio.run(test_sentiment_analyzer_agent())
