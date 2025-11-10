"""
Natural Language Processing Agent: Advanced NLP tasks and text processing
Provides comprehensive NLP capabilities including text summarization, question answering,
language translation, entity recognition, and linguistic analysis
"""
import os
import logging
from typing import Dict, Any, List, Optional, Tuple, Union, Set
from pathlib import Path
import asyncio
import json
from datetime import datetime, timedelta
from collections import defaultdict, deque
import uuid
import re
import string
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA, TruncatedSVD
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer, PorterStemmer
from nltk import pos_tag, ne_chunk
import spacy
from spacy.lang.en import English
from spacy.lang.uk import Ukrainian
from transformers import (
    pipeline, AutoTokenizer, AutoModelForSeq2SeqLM, AutoModelForQuestionAnswering,
    AutoModelForTokenClassification, AutoModelForCausalLM, AutoModel
)
from sentence_transformers import SentenceTransformer
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset as TorchDataset, DataLoader

from ..agents.base_agent import BaseAgent, AgentState, AgentMessage
from ..api.database import get_db_session
from ..api.models import Document, TextAnalysis, NLPTask

logger = logging.getLogger(__name__)


class NaturalLanguageProcessingAgent(BaseAgent):
    """
    Advanced NLP Agent for comprehensive text processing and analysis
    Supports multiple languages and NLP tasks
    """
    
    def __init__(
        self,
        agent_id: str = "nlp_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # NLP configuration
        self.nlp_config = {
            "supported_languages": self.config.get("languages", [
                "en", "uk", "ru", "de", "fr", "es", "it", "pl", "cs"
            ]),
            "nlp_tasks": self.config.get("tasks", [
                "summarization", "question_answering", "translation", "entity_recognition",
                "sentiment_analysis", "text_classification", "topic_modeling",
                "language_detection", "text_similarity", "keyword_extraction",
                "text_generation", "grammar_correction", "paraphrasing"
            ]),
            "models": self.config.get("models", {
                "summarization": "facebook/bart-large-cnn",
                "qa": "deepset/roberta-base-squad2",
                "translation": "Helsinki-NLP/opus-mt-uk-en",
                "ner": "dbmdz/bert-large-cased-finetuned-conll03-english",
                "sentiment": "cardiffnlp/twitter-roberta-base-sentiment",
                "embedding": "sentence-transformers/all-MiniLM-L6-v2",
                "generation": "microsoft/DialoGPT-medium"
            }),
            "processing_limits": self.config.get("limits", {
                "max_text_length": 10000,
                "max_summary_length": 150,
                "max_questions": 10,
                "batch_size": 8,
                "cache_size": 1000
            }),
            "quality_settings": self.config.get("quality", {
                "min_confidence": 0.5,
                "use_gpu": torch.cuda.is_available(),
                "enable_caching": True
            })
        }
        
        # NLP models and pipelines
        self.nlp_models = {}
        self.nlp_pipelines = {}
        self.text_processors = {}
        self.language_detectors = {}
        
        # Processing state
        self.nlp_state = {
            "text_cache": {},
            "model_cache": {},
            "processing_stats": defaultdict(int),
            "language_stats": defaultdict(int),
            "task_performance": {},
            "text_embeddings": {},
            "document_index": {},
            "keyword_index": {},
            "entity_index": {},
            "topic_models": {},
            "translation_cache": {},
            "qa_cache": {},
            "summarization_cache": {}
        }
        
        # Background tasks
        self.model_loading_task = None
        self.cache_cleanup_task = None
        self.performance_monitoring_task = None
        
        logger.info(f"NLP Agent initialized: {agent_id}")
    
    async def start(self):
        """
        Start the NLP agent
        """
        await super().start()
        
        # Download NLTK data
        await self._download_nltk_data()
        
        # Initialize NLP models
        await self._initialize_nlp_models()
        
        # Load existing data
        await self._load_nlp_data()
        
        # Start background tasks
        self.model_loading_task = asyncio.create_task(self._continuous_model_loading())
        self.cache_cleanup_task = asyncio.create_task(self._cache_cleanup())
        self.performance_monitoring_task = asyncio.create_task(self._performance_monitoring())
        
        logger.info("NLP processing started")
    
    async def stop(self):
        """
        Stop the NLP agent
        """
        if self.model_loading_task:
            self.model_loading_task.cancel()
            try:
                await self.model_loading_task
            except asyncio.CancelledError:
                pass
        
        if self.cache_cleanup_task:
            self.cache_cleanup_task.cancel()
            try:
                await self.cache_cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self.performance_monitoring_task:
            self.performance_monitoring_task.cancel()
            try:
                await self.performance_monitoring_task
            except asyncio.CancelledError:
                pass
        
        await super().stop()
        logger.info("NLP agent stopped")
    
    async def _download_nltk_data(self):
        """
        Download required NLTK data
        """
        try:
            nltk.download('punkt', quiet=True)
            nltk.download('stopwords', quiet=True)
            nltk.download('wordnet', quiet=True)
            nltk.download('averaged_perceptron_tagger', quiet=True)
            nltk.download('maxent_ne_chunker', quiet=True)
            nltk.download('words', quiet=True)
            
            logger.info("NLTK data downloaded")
            
        except Exception as e:
            logger.error(f"NLTK data download failed: {e}")
    
    async def _initialize_nlp_models(self):
        """
        Initialize NLP models and pipelines
        """
        try:
            # Initialize spaCy models
            for lang in self.nlp_config["supported_languages"]:
                try:
                    if lang == "en":
                        self.text_processors[lang] = spacy.load("en_core_web_sm")
                    elif lang == "uk":
                        # Use Ukrainian model if available, otherwise English fallback
                        try:
                            self.text_processors[lang] = spacy.load("uk_core_news_sm")
                        except:
                            self.text_processors[lang] = spacy.load("en_core_web_sm")
                    else:
                        self.text_processors[lang] = spacy.load("en_core_web_sm")
                except:
                    self.text_processors[lang] = English()
            
            # Initialize transformers pipelines
            device = 0 if self.nlp_config["quality_settings"]["use_gpu"] else -1
            
            # Summarization pipeline
            self.nlp_pipelines["summarization"] = pipeline(
                "summarization",
                model=self.nlp_config["models"]["summarization"],
                device=device
            )
            
            # Question answering pipeline
            self.nlp_pipelines["qa"] = pipeline(
                "question-answering",
                model=self.nlp_config["models"]["qa"],
                device=device
            )
            
            # Named entity recognition
            self.nlp_pipelines["ner"] = pipeline(
                "ner",
                model=self.nlp_config["models"]["ner"],
                device=device,
                aggregation_strategy="simple"
            )
            
            # Sentiment analysis
            self.nlp_pipelines["sentiment"] = pipeline(
                "sentiment-analysis",
                model=self.nlp_config["models"]["sentiment"],
                device=device
            )
            
            # Text generation
            self.nlp_pipelines["generation"] = pipeline(
                "text-generation",
                model=self.nlp_config["models"]["generation"],
                device=device
            )
            
            # Sentence transformer for embeddings
            self.nlp_models["embedding"] = SentenceTransformer(
                self.nlp_config["models"]["embedding"],
                device='cuda' if torch.cuda.is_available() else 'cpu'
            )
            
            # TF-IDF vectorizer for keyword extraction
            self.nlp_models["tfidf"] = TfidfVectorizer(
                max_features=5000,
                stop_words='english',
                ngram_range=(1, 2)
            )
            
            logger.info("NLP models initialized")
            
        except Exception as e:
            logger.error(f"NLP model initialization failed: {e}")
    
    async def _load_nlp_data(self):
        """
        Load existing NLP data
        """
        try:
            # Load document index, embeddings, etc.
            await self._load_document_index()
            await self._load_embeddings()
            await self._load_topic_models()
            
            logger.info("NLP data loaded")
            
        except Exception as e:
            logger.error(f"NLP data loading failed: {e}")
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process NLP requests
        """
        try:
            message_type = message.content.get("type", "")
            
            if message_type == "summarize_text":
                async for response in self._handle_text_summarization(message):
                    yield response
                    
            elif message_type == "answer_questions":
                async for response in self._handle_question_answering(message):
                    yield response
                    
            elif message_type == "translate_text":
                async for response in self._handle_text_translation(message):
                    yield response
                    
            elif message_type == "extract_entities":
                async for response in self._handle_entity_extraction(message):
                    yield response
                    
            elif message_type == "analyze_sentiment":
                async for response in self._handle_sentiment_analysis(message):
                    yield response
                    
            elif message_type == "classify_text":
                async for response in self._handle_text_classification(message):
                    yield response
                    
            elif message_type == "extract_keywords":
                async for response in self._handle_keyword_extraction(message):
                    yield response
                    
            elif message_type == "detect_language":
                async for response in self._handle_language_detection(message):
                    yield response
                    
            elif message_type == "find_similar_texts":
                async for response in self._handle_text_similarity(message):
                    yield response
                    
            elif message_type == "generate_text":
                async for response in self._handle_text_generation(message):
                    yield response
                    
            elif message_type == "correct_grammar":
                async for response in self._handle_grammar_correction(message):
                    yield response
                    
            elif message_type == "paraphrase_text":
                async for response in self._handle_text_paraphrasing(message):
                    yield response
                    
            elif message_type == "analyze_document":
                async for response in self._handle_document_analysis(message):
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
            logger.error(f"NLP processing failed: {e}")
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
    
    async def _handle_text_summarization(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle text summarization request
        """
        try:
            text = message.content.get("text", "")
            max_length = message.content.get("max_length", self.nlp_config["processing_limits"]["max_summary_length"])
            min_length = message.content.get("min_length", 30)
            language = message.content.get("language", "en")
            
            # Check cache
            cache_key = f"summary_{hash(text)}_{max_length}_{language}"
            if cache_key in self.nlp_state["summarization_cache"]:
                cached_result = self.nlp_state["summarization_cache"][cache_key]
                if (datetime.now() - cached_result["timestamp"]).seconds < 3600:  # 1 hour cache
                    yield AgentMessage(
                        id=str(uuid.uuid4()),
                        from_agent=self.agent_id,
                        to_agent=message.from_agent,
                        content={
                            "type": "summarization_response",
                            "summary": cached_result["summary"],
                            "original_length": len(text),
                            "summary_length": len(cached_result["summary"]),
                            "language": language,
                            "cached": True
                        },
                        timestamp=datetime.now()
                    )
                    return
            
            # Generate summary
            summary = await self._summarize_text(text, max_length, min_length, language)
            
            # Cache result
            self.nlp_state["summarization_cache"][cache_key] = {
                "summary": summary,
                "timestamp": datetime.now()
            }
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "summarization_response",
                    "summary": summary,
                    "original_length": len(text),
                    "summary_length": len(summary),
                    "language": language,
                    "cached": False
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Text summarization handling failed: {e}")
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
    
    async def _summarize_text(
        self,
        text: str,
        max_length: int,
        min_length: int,
        language: str
    ) -> str:
        """
        Summarize text using advanced NLP techniques
        """
        try:
            # Preprocess text
            text = self._preprocess_text(text, language)
            
            if len(text) < 100:
                return text  # Too short for summarization
            
            # Use extractive summarization for long texts
            if len(text.split()) > 1000:
                summary = await self._extractive_summarization(text, max_length, language)
            else:
                # Use abstractive summarization
                if "summarization" in self.nlp_pipelines:
                    result = self.nlp_pipelines["summarization"](
                        text,
                        max_length=max_length,
                        min_length=min_length,
                        do_sample=False
                    )
                    summary = result[0]["summary_text"]
                else:
                    summary = await self._extractive_summarization(text, max_length, language)
            
            return summary.strip()
            
        except Exception as e:
            logger.error(f"Text summarization failed: {e}")
            return text[:max_length] + "..." if len(text) > max_length else text
    
    async def _extractive_summarization(
        self,
        text: str,
        max_length: int,
        language: str
    ) -> str:
        """
        Extractive summarization using sentence scoring
        """
        try:
            # Tokenize into sentences
            sentences = sent_tokenize(text)
            if len(sentences) <= 3:
                return text
            
            # Calculate sentence scores
            sentence_scores = {}
            for i, sentence in enumerate(sentences):
                # Score based on position, length, and word frequency
                position_score = 1.0 / (i + 1)  # Prefer earlier sentences
                length_score = min(len(sentence.split()) / 20, 1.0)  # Prefer medium-length sentences
                
                # TF-IDF score
                words = word_tokenize(sentence.lower())
                tfidf_score = sum(self._calculate_word_importance(word, text) for word in words) / len(words)
                
                sentence_scores[sentence] = position_score + length_score + tfidf_score
            
            # Select top sentences
            sorted_sentences = sorted(sentence_scores.items(), key=lambda x: x[1], reverse=True)
            selected_sentences = [sentence for sentence, score in sorted_sentences[:3]]
            
            # Reorder to maintain coherence
            selected_sentences.sort(key=lambda x: sentences.index(x))
            
            summary = ' '.join(selected_sentences)
            return summary[:max_length] + "..." if len(summary) > max_length else summary
            
        except Exception as e:
            logger.error(f"Extractive summarization failed: {e}")
            return text[:max_length] + "..." if len(text) > max_length else text
    
    async def _handle_question_answering(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle question answering request
        """
        try:
            context = message.content.get("context", "")
            questions = message.content.get("questions", [])
            language = message.content.get("language", "en")
            
            if isinstance(questions, str):
                questions = [questions]
            
            # Limit number of questions
            questions = questions[:self.nlp_config["processing_limits"]["max_questions"]]
            
            # Check cache
            cache_key = f"qa_{hash(context)}_{hash(str(questions))}_{language}"
            if cache_key in self.nlp_state["qa_cache"]:
                cached_result = self.nlp_state["qa_cache"][cache_key]
                if (datetime.now() - cached_result["timestamp"]).seconds < 3600:
                    yield AgentMessage(
                        id=str(uuid.uuid4()),
                        from_agent=self.agent_id,
                        to_agent=message.from_agent,
                        content={
                            "type": "qa_response",
                            "answers": cached_result["answers"],
                            "context_length": len(context),
                            "num_questions": len(questions),
                            "language": language,
                            "cached": True
                        },
                        timestamp=datetime.now()
                    )
                    return
            
            # Answer questions
            answers = await self._answer_questions(context, questions, language)
            
            # Cache result
            self.nlp_state["qa_cache"][cache_key] = {
                "answers": answers,
                "timestamp": datetime.now()
            }
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "qa_response",
                    "answers": answers,
                    "context_length": len(context),
                    "num_questions": len(questions),
                    "language": language,
                    "cached": False
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Question answering handling failed: {e}")
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
    
    async def _answer_questions(
        self,
        context: str,
        questions: List[str],
        language: str
    ) -> List[Dict[str, Any]]:
        """
        Answer questions based on context
        """
        try:
            answers = []
            
            for question in questions:
                try:
                    if "qa" in self.nlp_pipelines:
                        result = self.nlp_pipelines["qa"](
                            question=question,
                            context=context
                        )
                        
                        answer = {
                            "question": question,
                            "answer": result["answer"],
                            "confidence": result["score"],
                            "start": result["start"],
                            "end": result["end"]
                        }
                    else:
                        # Fallback: keyword matching
                        answer = await self._keyword_based_qa(question, context)
                    
                    answers.append(answer)
                    
                except Exception as e:
                    logger.error(f"Question answering failed for '{question}': {e}")
                    answers.append({
                        "question": question,
                        "answer": "Unable to find answer",
                        "confidence": 0.0,
                        "error": str(e)
                    })
            
            return answers
            
        except Exception as e:
            logger.error(f"Question answering failed: {e}")
            return []
    
    async def _keyword_based_qa(self, question: str, context: str) -> Dict[str, Any]:
        """
        Keyword-based question answering fallback
        """
        try:
            # Extract keywords from question
            question_keywords = self._extract_keywords_basic(question)
            
            # Find sentences containing keywords
            sentences = sent_tokenize(context)
            best_sentence = ""
            max_score = 0
            
            for sentence in sentences:
                sentence_keywords = self._extract_keywords_basic(sentence)
                score = len(set(question_keywords) & set(sentence_keywords))
                if score > max_score:
                    max_score = score
                    best_sentence = sentence
            
            return {
                "question": question,
                "answer": best_sentence if best_sentence else "No relevant information found",
                "confidence": min(max_score / len(question_keywords), 1.0) if question_keywords else 0.0,
                "method": "keyword_matching"
            }
            
        except Exception as e:
            logger.error(f"Keyword-based QA failed: {e}")
            return {
                "question": question,
                "answer": "Error in processing",
                "confidence": 0.0,
                "error": str(e)
            }
    
    async def _handle_text_translation(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle text translation request
        """
        try:
            text = message.content.get("text", "")
            source_lang = message.content.get("source_language", "auto")
            target_lang = message.content.get("target_language", "en")
            
            # Check cache
            cache_key = f"translate_{hash(text)}_{source_lang}_{target_lang}"
            if cache_key in self.nlp_state["translation_cache"]:
                cached_result = self.nlp_state["translation_cache"][cache_key]
                if (datetime.now() - cached_result["timestamp"]).seconds < 3600:
                    yield AgentMessage(
                        id=str(uuid.uuid4()),
                        from_agent=self.agent_id,
                        to_agent=message.from_agent,
                        content={
                            "type": "translation_response",
                            "translated_text": cached_result["translation"],
                            "source_language": cached_result["source_lang"],
                            "target_language": target_lang,
                            "cached": True
                        },
                        timestamp=datetime.now()
                    )
                    return
            
            # Detect language if auto
            if source_lang == "auto":
                source_lang = await self._detect_language(text)
            
            # Translate text
            translation = await self._translate_text(text, source_lang, target_lang)
            
            # Cache result
            self.nlp_state["translation_cache"][cache_key] = {
                "translation": translation,
                "source_lang": source_lang,
                "timestamp": datetime.now()
            }
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "translation_response",
                    "translated_text": translation,
                    "source_language": source_lang,
                    "target_language": target_lang,
                    "cached": False
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Text translation handling failed: {e}")
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
    
    async def _translate_text(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> str:
        """
        Translate text between languages
        """
        try:
            # For now, use a simple placeholder translation
            # In production, would use translation models like Helsinki-NLP
            if source_lang == target_lang:
                return text
            
            # Basic translation mapping for demo
            translation_map = {
                ("uk", "en"): {
                    "привіт": "hello",
                    "як справи": "how are you",
                    "дякую": "thank you",
                    "так": "yes",
                    "ні": "no"
                },
                ("en", "uk"): {
                    "hello": "привіт",
                    "how are you": "як справи",
                    "thank you": "дякую",
                    "yes": "так",
                    "no": "ні"
                }
            }
            
            key = (source_lang, target_lang)
            if key in translation_map:
                words = text.lower().split()
                translated_words = []
                for word in words:
                    translated_words.append(translation_map[key].get(word, word))
                return ' '.join(translated_words)
            
            # Fallback: return original text with translation note
            return f"[Translation not available] {text}"
            
        except Exception as e:
            logger.error(f"Text translation failed: {e}")
            return text
    
    async def _handle_entity_extraction(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle entity extraction request
        """
        try:
            text = message.content.get("text", "")
            language = message.content.get("language", "en")
            entity_types = message.content.get("entity_types", ["PERSON", "ORG", "GPE", "MONEY", "DATE"])
            
            # Extract entities
            entities = await self._extract_entities(text, language, entity_types)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "entity_extraction_response",
                    "entities": entities,
                    "text_length": len(text),
                    "language": language,
                    "entity_types": entity_types
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Entity extraction handling failed: {e}")
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
    
    async def _extract_entities(
        self,
        text: str,
        language: str,
        entity_types: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Extract named entities from text
        """
        try:
            entities = []
            
            # Use spaCy for entity extraction
            if language in self.text_processors:
                doc = self.text_processors[language](text)
                
                for ent in doc.ents:
                    if ent.label_ in entity_types:
                        entities.append({
                            "text": ent.text,
                            "label": ent.label_,
                            "start": ent.start_char,
                            "end": ent.end_char,
                            "confidence": 1.0  # spaCy doesn't provide confidence scores
                        })
            
            # Use transformers NER as backup
            elif "ner" in self.nlp_pipelines:
                ner_results = self.nlp_pipelines["ner"](text)
                
                for result in ner_results:
                    if result["entity_group"] in entity_types:
                        entities.append({
                            "text": result["word"],
                            "label": result["entity_group"],
                            "start": result["start"],
                            "end": result["end"],
                            "confidence": result["score"]
                        })
            
            # Remove duplicates and merge overlapping entities
            entities = self._merge_overlapping_entities(entities)
            
            return entities
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []
    
    def _merge_overlapping_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge overlapping entities
        """
        try:
            if not entities:
                return entities
            
            # Sort by start position
            entities.sort(key=lambda x: x["start"])
            
            merged = [entities[0]]
            
            for entity in entities[1:]:
                last = merged[-1]
                
                # Check for overlap
                if entity["start"] <= last["end"]:
                    # Merge entities
                    last["end"] = max(last["end"], entity["end"])
                    last["text"] = last["text"] + " " + entity["text"]
                    last["confidence"] = max(last["confidence"], entity["confidence"])
                else:
                    merged.append(entity)
            
            return merged
            
        except Exception as e:
            logger.error(f"Entity merging failed: {e}")
            return entities
    
    async def _handle_sentiment_analysis(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle sentiment analysis request
        """
        try:
            text = message.content.get("text", "")
            language = message.content.get("language", "en")
            
            # Analyze sentiment
            sentiment = await self._analyze_sentiment(text, language)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "sentiment_response",
                    "sentiment": sentiment,
                    "text_length": len(text),
                    "language": language
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
    
    async def _analyze_sentiment(self, text: str, language: str) -> Dict[str, Any]:
        """
        Analyze sentiment of text
        """
        try:
            sentiment_result = {
                "label": "neutral",
                "score": 0.5,
                "confidence": 0.0,
                "method": "rule_based"
            }
            
            # Use transformers sentiment analysis
            if "sentiment" in self.nlp_pipelines:
                result = self.nlp_pipelines["sentiment"](text)
                sentiment_result = {
                    "label": result[0]["label"],
                    "score": result[0]["score"],
                    "confidence": result[0]["score"],
                    "method": "transformer"
                }
            
            # Rule-based fallback for Ukrainian
            elif language == "uk":
                sentiment_result = self._rule_based_sentiment_uk(text)
            
            return sentiment_result
            
        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return {
                "label": "neutral",
                "score": 0.5,
                "confidence": 0.0,
                "error": str(e)
            }
    
    def _rule_based_sentiment_uk(self, text: str) -> Dict[str, Any]:
        """
        Rule-based sentiment analysis for Ukrainian text
        """
        try:
            positive_words = ["добре", "чудово", "відмінно", "прекрасно", "гарно", "класно", "супер"]
            negative_words = ["погано", "жахливо", "терпимо", "негативно", "проблема", "криза"]
            
            words = text.lower().split()
            positive_count = sum(1 for word in words if word in positive_words)
            negative_count = sum(1 for word in words if word in negative_words)
            
            total_sentiment_words = positive_count + negative_count
            
            if total_sentiment_words == 0:
                return {
                    "label": "neutral",
                    "score": 0.5,
                    "confidence": 0.5,
                    "method": "rule_based_uk"
                }
            
            score = (positive_count - negative_count) / total_sentiment_words
            score = (score + 1) / 2  # Normalize to 0-1
            
            if score > 0.6:
                label = "positive"
            elif score < 0.4:
                label = "negative"
            else:
                label = "neutral"
            
            return {
                "label": label,
                "score": score,
                "confidence": min(total_sentiment_words / 10, 1.0),  # Confidence based on sentiment words
                "method": "rule_based_uk"
            }
            
        except Exception as e:
            logger.error(f"Rule-based sentiment analysis failed: {e}")
            return {
                "label": "neutral",
                "score": 0.5,
                "confidence": 0.0,
                "error": str(e)
            }
    
    async def _handle_keyword_extraction(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle keyword extraction request
        """
        try:
            text = message.content.get("text", "")
            language = message.content.get("language", "en")
            num_keywords = message.content.get("num_keywords", 10)
            
            # Extract keywords
            keywords = await self._extract_keywords(text, language, num_keywords)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "keyword_extraction_response",
                    "keywords": keywords,
                    "text_length": len(text),
                    "language": language,
                    "num_keywords": num_keywords
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Keyword extraction handling failed: {e}")
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
    
    async def _extract_keywords(
        self,
        text: str,
        language: str,
        num_keywords: int
    ) -> List[Dict[str, Any]]:
        """
        Extract keywords from text
        """
        try:
            keywords = []
            
            # Method 1: TF-IDF based extraction
            tfidf_keywords = self._extract_keywords_tfidf(text, num_keywords)
            keywords.extend(tfidf_keywords)
            
            # Method 2: RAKE (Rapid Automatic Keyword Extraction)
            rake_keywords = self._extract_keywords_rake(text, num_keywords)
            keywords.extend(rake_keywords)
            
            # Method 3: Position-based extraction
            position_keywords = self._extract_keywords_position(text, num_keywords)
            keywords.extend(position_keywords)
            
            # Remove duplicates and rank
            keyword_dict = {}
            for kw in keywords:
                key = kw["keyword"].lower()
                if key not in keyword_dict:
                    keyword_dict[key] = kw
                else:
                    # Average scores
                    keyword_dict[key]["score"] = (keyword_dict[key]["score"] + kw["score"]) / 2
            
            # Sort by score and return top keywords
            sorted_keywords = sorted(keyword_dict.values(), key=lambda x: x["score"], reverse=True)
            
            return sorted_keywords[:num_keywords]
            
        except Exception as e:
            logger.error(f"Keyword extraction failed: {e}")
            return []
    
    def _extract_keywords_tfidf(self, text: str, num_keywords: int) -> List[Dict[str, Any]]:
        """
        Extract keywords using TF-IDF
        """
        try:
            # Preprocess text
            processed_text = self._preprocess_text(text, "en")
            
            # Fit TF-IDF (would normally be trained on corpus)
            tfidf_matrix = self.nlp_models["tfidf"].fit_transform([processed_text])
            
            # Get feature names and scores
            feature_names = self.nlp_models["tfidf"].get_feature_names_out()
            scores = tfidf_matrix.toarray()[0]
            
            # Get top keywords
            top_indices = scores.argsort()[-num_keywords:][::-1]
            
            keywords = []
            for idx in top_indices:
                if scores[idx] > 0:
                    keywords.append({
                        "keyword": feature_names[idx],
                        "score": float(scores[idx]),
                        "method": "tfidf"
                    })
            
            return keywords
            
        except Exception as e:
            logger.error(f"TF-IDF keyword extraction failed: {e}")
            return []
    
    def _extract_keywords_rake(self, text: str, num_keywords: int) -> List[Dict[str, Any]]:
        """
        Extract keywords using RAKE algorithm
        """
        try:
            # Simple RAKE implementation
            sentences = sent_tokenize(text)
            stop_words = set(stopwords.words('english'))
            
            # Generate candidate keywords
            candidates = []
            for sentence in sentences:
                words = word_tokenize(sentence.lower())
                # Remove punctuation and stop words
                words = [word for word in words if word not in stop_words and word not in string.punctuation]
                
                # Generate n-grams (1-3 words)
                for i in range(len(words)):
                    for j in range(i + 1, min(i + 4, len(words) + 1)):
                        candidate = ' '.join(words[i:j])
                        if len(candidate.split()) <= 3:  # Max 3 words
                            candidates.append(candidate)
            
            # Score candidates
            word_freq = defaultdict(int)
            word_deg = defaultdict(int)
            
            for candidate in candidates:
                words = candidate.split()
                word_freq.update(words)
                word_deg.update(words)
            
            # Calculate scores
            candidate_scores = {}
            for candidate in set(candidates):
                words = candidate.split()
                score = sum(word_deg[word] / word_freq[word] for word in words)
                candidate_scores[candidate] = score
            
            # Get top candidates
            sorted_candidates = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)
            
            keywords = []
            for candidate, score in sorted_candidates[:num_keywords]:
                keywords.append({
                    "keyword": candidate,
                    "score": score,
                    "method": "rake"
                })
            
            return keywords
            
        except Exception as e:
            logger.error(f"RAKE keyword extraction failed: {e}")
            return []
    
    def _extract_keywords_position(self, text: str, num_keywords: int) -> List[Dict[str, Any]]:
        """
        Extract keywords based on position in text
        """
        try:
            sentences = sent_tokenize(text)
            keywords = []
            
            # Focus on first and last sentences
            important_sentences = sentences[:2] + sentences[-2:] if len(sentences) > 2 else sentences
            
            for sentence in important_sentences:
                words = word_tokenize(sentence.lower())
                # Remove stop words and punctuation
                stop_words = set(stopwords.words('english'))
                words = [word for word in words if word not in stop_words and word not in string.punctuation and len(word) > 3]
                
                for word in words:
                    # Score based on position in sentence
                    position_score = 1.0 / (words.index(word) + 1)
                    keywords.append({
                        "keyword": word,
                        "score": position_score,
                        "method": "position"
                    })
            
            # Remove duplicates and average scores
            keyword_dict = {}
            for kw in keywords:
                key = kw["keyword"]
                if key not in keyword_dict:
                    keyword_dict[key] = kw
                else:
                    keyword_dict[key]["score"] = (keyword_dict[key]["score"] + kw["score"]) / 2
            
            sorted_keywords = sorted(keyword_dict.values(), key=lambda x: x["score"], reverse=True)
            
            return sorted_keywords[:num_keywords]
            
        except Exception as e:
            logger.error(f"Position-based keyword extraction failed: {e}")
            return []
    
    async def _handle_language_detection(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle language detection request
        """
        try:
            text = message.content.get("text", "")
            
            # Detect language
            language = await self._detect_language(text)
            confidence = await self._calculate_language_confidence(text, language)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "language_detection_response",
                    "detected_language": language,
                    "confidence": confidence,
                    "text_length": len(text)
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Language detection handling failed: {e}")
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
    
    async def _detect_language(self, text: str) -> str:
        """
        Detect language of text
        """
        try:
            # Simple rule-based language detection
            text_lower = text.lower()
            
            # Ukrainian indicators
            uk_indicators = ["привіт", "як", "дякую", "так", "ні", "це", "що", "де"]
            uk_score = sum(1 for word in text_lower.split() if word in uk_indicators)
            
            # English indicators
            en_indicators = ["the", "and", "or", "but", "in", "on", "at", "to", "for"]
            en_score = sum(1 for word in text_lower.split() if word in en_indicators)
            
            # Russian indicators
            ru_indicators = ["привет", "как", "спасибо", "да", "нет", "это", "что", "где"]
            ru_score = sum(1 for word in text_lower.split() if word in ru_indicators)
            
            # Determine language
            scores = {"uk": uk_score, "en": en_score, "ru": ru_score}
            detected_lang = max(scores, key=scores.get)
            
            # Default to English if no clear indicators
            if scores[detected_lang] == 0:
                detected_lang = "en"
            
            return detected_lang
            
        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            return "en"
    
    async def _calculate_language_confidence(self, text: str, language: str) -> float:
        """
        Calculate confidence in language detection
        """
        try:
            # Simple confidence calculation based on text length and indicators
            if len(text.split()) < 3:
                return 0.5  # Low confidence for short texts
            
            # Count language-specific characters/words
            if language == "uk":
                indicators = ["привіт", "як", "дякую", "і", "та", "це"]
            elif language == "ru":
                indicators = ["привет", "как", "спасибо", "и", "что", "это"]
            else:  # English
                indicators = ["the", "and", "or", "but", "in", "on"]
            
            words = text.lower().split()
            indicator_count = sum(1 for word in words if word in indicators)
            
            confidence = min(indicator_count / len(words), 1.0)
            return max(confidence, 0.1)  # Minimum confidence
            
        except Exception as e:
            logger.error(f"Language confidence calculation failed: {e}")
            return 0.5
    
    async def _handle_text_similarity(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle text similarity request
        """
        try:
            text1 = message.content.get("text1", "")
            text2 = message.content.get("text2", "")
            similarity_type = message.content.get("similarity_type", "semantic")
            
            # Calculate similarity
            similarity = await self._calculate_text_similarity(text1, text2, similarity_type)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "text_similarity_response",
                    "similarity_score": similarity,
                    "similarity_type": similarity_type,
                    "text1_length": len(text1),
                    "text2_length": len(text2)
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Text similarity handling failed: {e}")
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
    
    async def _calculate_text_similarity(
        self,
        text1: str,
        text2: str,
        similarity_type: str
    ) -> float:
        """
        Calculate similarity between two texts
        """
        try:
            if similarity_type == "semantic":
                # Use sentence transformers for semantic similarity
                if "embedding" in self.nlp_models:
                    embeddings = self.nlp_models["embedding"].encode([text1, text2])
                    similarity = cosine_similarity([embeddings[0]], [embeddings[1]])[0][0]
                    return float(similarity)
            
            elif similarity_type == "lexical":
                # Jaccard similarity
                words1 = set(text1.lower().split())
                words2 = set(text2.lower().split())
                intersection = words1 & words2
                union = words1 | words2
                return len(intersection) / len(union) if union else 0.0
            
            elif similarity_type == "tfidf":
                # TF-IDF cosine similarity
                if "tfidf" in self.nlp_models:
                    tfidf_matrix = self.nlp_models["tfidf"].fit_transform([text1, text2])
                    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
                    return float(similarity)
            
            # Default: lexical similarity
            return self._calculate_text_similarity(text1, text2, "lexical")
            
        except Exception as e:
            logger.error(f"Text similarity calculation failed: {e}")
            return 0.0
    
    async def _handle_text_generation(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle text generation request
        """
        try:
            prompt = message.content.get("prompt", "")
            max_length = message.content.get("max_length", 100)
            temperature = message.content.get("temperature", 0.7)
            language = message.content.get("language", "en")
            
            # Generate text
            generated_text = await self._generate_text(prompt, max_length, temperature, language)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "text_generation_response",
                    "generated_text": generated_text,
                    "prompt": prompt,
                    "max_length": max_length,
                    "temperature": temperature,
                    "language": language
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Text generation handling failed: {e}")
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
    
    async def _generate_text(
        self,
        prompt: str,
        max_length: int,
        temperature: float,
        language: str
    ) -> str:
        """
        Generate text using language models
        """
        try:
            if "generation" in self.nlp_pipelines:
                result = self.nlp_pipelines["generation"](
                    prompt,
                    max_length=max_length,
                    temperature=temperature,
                    do_sample=True,
                    pad_token_id=50256  # GPT-2 EOS token
                )
                generated_text = result[0]["generated_text"]
                
                # Remove the prompt from the result
                if generated_text.startswith(prompt):
                    generated_text = generated_text[len(prompt):].strip()
                
                return generated_text
            
            # Fallback: simple text generation
            return f"Generated text based on: {prompt[:50]}..."
            
        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            return f"Error generating text: {str(e)}"
    
    async def _handle_grammar_correction(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle grammar correction request
        """
        try:
            text = message.content.get("text", "")
            language = message.content.get("language", "en")
            
            # Correct grammar
            corrected_text = await self._correct_grammar(text, language)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "grammar_correction_response",
                    "original_text": text,
                    "corrected_text": corrected_text,
                    "language": language
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Grammar correction handling failed: {e}")
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
    
    async def _correct_grammar(self, text: str, language: str) -> str:
        """
        Correct grammar in text
        """
        try:
            # For now, use basic grammar correction
            # In production, would use models like LanguageTool or custom transformers
            
            corrected_text = text
            
            # Basic corrections
            corrections = {
                "i ": "I ",  # Capitalize I
                " i ": " I ",
                "i'm": "I'm",
                "i've": "I've",
                "i'll": "I'll",
                "don't": "don't",  # Keep contractions
                "can't": "can't",
                "won't": "won't",
                "isn't": "isn't",
                "aren't": "aren't",
            }
            
            for wrong, right in corrections.items():
                corrected_text = corrected_text.replace(wrong, right)
            
            # Fix double spaces
            while "  " in corrected_text:
                corrected_text = corrected_text.replace("  ", " ")
            
            return corrected_text.strip()
            
        except Exception as e:
            logger.error(f"Grammar correction failed: {e}")
            return text
    
    async def _handle_text_paraphrasing(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle text paraphrasing request
        """
        try:
            text = message.content.get("text", "")
            style = message.content.get("style", "neutral")
            language = message.content.get("language", "en")
            
            # Paraphrase text
            paraphrased_text = await self._paraphrase_text(text, style, language)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "paraphrasing_response",
                    "original_text": text,
                    "paraphrased_text": paraphrased_text,
                    "style": style,
                    "language": language
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Text paraphrasing handling failed: {e}")
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
    
    async def _paraphrase_text(self, text: str, style: str, language: str) -> str:
        """
        Paraphrase text in different styles
        """
        try:
            # For now, use simple paraphrasing
            # In production, would use T5 or Pegasus models
            
            if style == "formal":
                # Make more formal
                paraphrases = {
                    "hi": "hello",
                    "hey": "greetings",
                    "thanks": "thank you",
                    "ok": "acceptable",
                    "good": "satisfactory",
                    "bad": "unsatisfactory"
                }
            elif style == "casual":
                # Make more casual
                paraphrases = {
                    "hello": "hi",
                    "greetings": "hey",
                    "thank you": "thanks",
                    "acceptable": "ok",
                    "satisfactory": "good",
                    "unsatisfactory": "bad"
                }
            else:  # neutral
                paraphrases = {}
            
            paraphrased = text
            for old, new in paraphrases.items():
                paraphrased = paraphrased.replace(old, new)
            
            return paraphrased
            
        except Exception as e:
            logger.error(f"Text paraphrasing failed: {e}")
            return text
    
    async def _handle_document_analysis(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle document analysis request
        """
        try:
            document_text = message.content.get("document_text", "")
            analysis_types = message.content.get("analysis_types", ["summary", "entities", "sentiment", "keywords"])
            language = message.content.get("language", "en")
            
            # Analyze document
            analysis = await self._analyze_document(document_text, analysis_types, language)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "document_analysis_response",
                    "analysis": analysis,
                    "document_length": len(document_text),
                    "analysis_types": analysis_types,
                    "language": language
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Document analysis handling failed: {e}")
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
    
    async def _analyze_document(
        self,
        document_text: str,
        analysis_types: List[str],
        language: str
    ) -> Dict[str, Any]:
        """
        Perform comprehensive document analysis
        """
        try:
            analysis = {}
            
            for analysis_type in analysis_types:
                if analysis_type == "summary":
                    analysis["summary"] = await self._summarize_text(document_text, 150, 50, language)
                
                elif analysis_type == "entities":
                    analysis["entities"] = await self._extract_entities(document_text, language, [])
                
                elif analysis_type == "sentiment":
                    analysis["sentiment"] = await self._analyze_sentiment(document_text, language)
                
                elif analysis_type == "keywords":
                    analysis["keywords"] = await self._extract_keywords(document_text, language, 10)
                
                elif analysis_type == "language":
                    analysis["detected_language"] = await self._detect_language(document_text)
                
                elif analysis_type == "readability":
                    analysis["readability_score"] = self._calculate_readability(document_text)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Document analysis failed: {e}")
            return {"error": str(e)}
    
    def _calculate_readability(self, text: str) -> float:
        """
        Calculate text readability score
        """
        try:
            sentences = sent_tokenize(text)
            words = word_tokenize(text)
            
            if not sentences or not words:
                return 0.0
            
            avg_words_per_sentence = len(words) / len(sentences)
            avg_syllables_per_word = sum(self._count_syllables(word) for word in words) / len(words)
            
            # Simple readability formula (similar to Flesch-Kincaid)
            readability = 206.835 - 1.015 * avg_words_per_sentence - 84.6 * avg_syllables_per_word
            
            # Normalize to 0-100 scale
            readability = max(0, min(100, readability))
            
            return readability
            
        except Exception as e:
            logger.error(f"Readability calculation failed: {e}")
            return 0.0
    
    def _count_syllables(self, word: str) -> int:
        """
        Count syllables in a word
        """
        try:
            word = word.lower()
            count = 0
            vowels = "aeiouy"
            
            if word[0] in vowels:
                count += 1
            
            for i in range(1, len(word)):
                if word[i] in vowels and word[i - 1] not in vowels:
                    count += 1
            
            if word.endswith("e"):
                count -= 1
            
            return max(1, count)
            
        except:
            return 1
    
    def _preprocess_text(self, text: str, language: str) -> str:
        """
        Preprocess text for NLP tasks
        """
        try:
            # Basic preprocessing
            text = text.strip()
            
            # Remove extra whitespace
            text = re.sub(r'\s+', ' ', text)
            
            # Remove URLs
            text = re.sub(r'http\S+', '', text)
            
            # Remove special characters but keep basic punctuation
            text = re.sub(r'[^\w\s.,!?-]', '', text)
            
            return text
            
        except Exception as e:
            logger.error(f"Text preprocessing failed: {e}")
            return text
    
    def _calculate_word_importance(self, word: str, text: str) -> float:
        """
        Calculate word importance score
        """
        try:
            # Simple TF-IDF like calculation
            word_count = text.lower().count(word.lower())
            total_words = len(text.split())
            
            # Term frequency
            tf = word_count / total_words
            
            # Inverse document frequency (simplified)
            idf = 1.0  # Would be calculated from corpus
            
            return tf * idf
            
        except Exception:
            return 0.0
    
    def _extract_keywords_basic(self, text: str) -> List[str]:
        """
        Basic keyword extraction
        """
        try:
            words = word_tokenize(text.lower())
            stop_words = set(stopwords.words('english'))
            
            keywords = [
                word for word in words
                if word not in stop_words
                and word not in string.punctuation
                and len(word) > 3
            ]
            
            return keywords
            
        except Exception as e:
            logger.error(f"Basic keyword extraction failed: {e}")
            return []
    
    # Background task methods
    async def _continuous_model_loading(self):
        """Continuously load and update models"""
        try:
            while True:
                try:
                    # Load additional models as needed
                    await asyncio.sleep(3600)  # Check every hour
                    
                except Exception as e:
                    logger.error(f"Continuous model loading error: {e}")
                
        except asyncio.CancelledError:
            logger.info("Continuous model loading cancelled")
            raise
    
    async def _cache_cleanup(self):
        """Clean up expired cache entries"""
        try:
            while True:
                try:
                    current_time = datetime.now()
                    
                    # Clean text cache
                    expired_keys = [
                        key for key, data in self.nlp_state["text_cache"].items()
                        if (current_time - data.get("timestamp", current_time)).seconds > 7200  # 2 hours
                    ]
                    for key in expired_keys:
                        del self.nlp_state["text_cache"][key]
                    
                    # Clean other caches similarly
                    for cache_name in ["summarization_cache", "qa_cache", "translation_cache"]:
                        cache = self.nlp_state.get(cache_name, {})
                        expired_keys = [
                            key for key, data in cache.items()
                            if (current_time - data.get("timestamp", current_time)).seconds > 3600  # 1 hour
                        ]
                        for key in expired_keys:
                            del cache[key]
                    
                except Exception as e:
                    logger.error(f"Cache cleanup error: {e}")
                
                await asyncio.sleep(1800)  # Clean every 30 minutes
                
        except asyncio.CancelledError:
            logger.info("Cache cleanup cancelled")
            raise
    
    async def _performance_monitoring(self):
        """Monitor NLP task performance"""
        try:
            while True:
                try:
                    # Update performance statistics
                    self.nlp_state["task_performance"] = dict(self.nlp_state["processing_stats"])
                    
                except Exception as e:
                    logger.error(f"Performance monitoring error: {e}")
                
                await asyncio.sleep(300)  # Monitor every 5 minutes
                
        except asyncio.CancelledError:
            logger.info("Performance monitoring cancelled")
            raise
    
    # Additional helper methods would continue here...
    
    async def _load_document_index(self):
        """Load document index"""
        try:
            # Implementation for loading document index
            pass
        except Exception as e:
            logger.error(f"Document index loading failed: {e}")
    
    async def _load_embeddings(self):
        """Load text embeddings"""
        try:
            # Implementation for loading embeddings
            pass
        except Exception as e:
            logger.error(f"Embeddings loading failed: {e}")
    
    async def _load_topic_models(self):
        """Load topic models"""
        try:
            # Implementation for loading topic models
            pass
        except Exception as e:
            logger.error(f"Topic models loading failed: {e}"


# ========== TEST ==========
if __name__ == "__main__":
    async def test_nlp_agent():
        # Initialize NLP agent
        agent = NaturalLanguageProcessingAgent()
        await agent.start()
        
        # Test text summarization
        summary_message = AgentMessage(
            id="test_summary",
            from_agent="test",
            to_agent="nlp_agent",
            content={
                "type": "summarize_text",
                "text": "Natural Language Processing (NLP) is a subfield of artificial intelligence that focuses on the interaction between computers and humans through natural language. The ultimate goal of NLP is to read, decipher, understand, and make sense of human language in a manner that is valuable. Modern NLP techniques leverage machine learning and deep learning to process and analyze large amounts of natural language data.",
                "max_length": 50,
                "language": "en"
            },
            timestamp=datetime.now()
        )
        
        print("Testing NLP agent...")
        async for response in agent.process_message(summary_message):
            print(f"Summarization response: {response.content.get('type')}")
            summary = response.content.get('result', {}).get('summary', '')
            print(f"Summary: {summary[:100]}...")
        
        # Test entity extraction
        entity_message = AgentMessage(
            id="test_entities",
            from_agent="test",
            to_agent="nlp_agent",
            content={
                "type": "extract_entities",
                "text": "Apple Inc. was founded by Steve Jobs in Cupertino, California on April 1, 1976.",
                "language": "en"
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(entity_message):
            print(f"Entity extraction response: {response.content.get('type')}")
            entities = response.content.get('result', {}).get('entities', [])
            print(f"Found {len(entities)} entities")
        
        # Test sentiment analysis
        sentiment_message = AgentMessage(
            id="test_sentiment",
            from_agent="test",
            to_agent="nlp_agent",
            content={
                "type": "analyze_sentiment",
                "text": "I love this product! It's amazing and works perfectly.",
                "language": "en"
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(sentiment_message):
            print(f"Sentiment analysis response: {response.content.get('type')}")
            sentiment = response.content.get('result', {}).get('sentiment', {})
            print(f"Sentiment: {sentiment.get('label', 'unknown')}")
        
        # Test keyword extraction
        keyword_message = AgentMessage(
            id="test_keywords",
            from_agent="test",
            to_agent="nlp_agent",
            content={
                "type": "extract_keywords",
                "text": "Machine learning is a method of data analysis that automates analytical model building. It is a branch of artificial intelligence based on the idea that systems can learn from data, identify patterns and make decisions with minimal human intervention.",
                "language": "en",
                "num_keywords": 5
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(keyword_message):
            print(f"Keyword extraction response: {response.content.get('type')}")
            keywords = response.content.get('result', {}).get('keywords', [])
            print(f"Keywords: {[kw.get('keyword') for kw in keywords[:5]]}")
        
        # Stop agent
        await agent.stop()
        print("NLP agent test completed")
    
    # Run test
    asyncio.run(test_nlp_agent())
