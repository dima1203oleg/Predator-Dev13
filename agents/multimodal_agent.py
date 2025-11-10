"""
Multimodal Agent: Advanced multimodal processing and fusion
Combines text, image, speech, and other modalities for comprehensive analysis
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
import base64
import io
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset as TorchDataset, DataLoader
import torchvision
import torchvision.transforms as T
from transformers import (
    CLIPProcessor, 
    CLIPModel,
    CLIPTokenizer,
    AutoTokenizer,
    AutoModel,
    AutoModelForSequenceClassification,
    pipeline,
    VisionEncoderDecoderModel,
    ViTImageProcessor,
    AutoTokenizer as BertTokenizer,
    AutoModel as BertModel
)
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity
import cv2
from PIL import Image
import librosa
import soundfile as sf

from ..agents.base_agent import BaseAgent, AgentState, AgentMessage
from ..api.database import get_db_session
from ..api.models import MultimodalAnalysis, ModalityFusion, CrossModalRetrieval

logger = logging.getLogger(__name__)


class MultimodalAgent(BaseAgent):
    """
    Multimodal Agent for processing and fusing multiple data modalities
    Combines text, image, speech, and other modalities for comprehensive analysis
    """
    
    def __init__(
        self,
        agent_id: str = "multimodal_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # Multimodal configuration
        self.multimodal_config = {
            "supported_modalities": self.config.get("modalities", [
                "text", "image", "speech", "video", "audio", "structured_data"
            ]),
            "fusion_methods": self.config.get("fusion_methods", [
                "early_fusion", "late_fusion", "cross_attention", "multimodal_transformer"
            ]),
            "embedding_models": self.config.get("embedding_models", {
                "clip": {
                    "model_name": "openai/clip-vit-base-patch32",
                    "max_length": 77
                },
                "bert": {
                    "model_name": "bert-base-multilingual-cased",
                    "max_length": 512
                },
                "wav2vec2": {
                    "model_name": "facebook/wav2vec2-base-960h",
                    "max_length": 16000
                }
            }),
            "fusion_config": self.config.get("fusion_config", {
                "method": "cross_attention",
                "attention_heads": 8,
                "hidden_size": 768,
                "num_layers": 6,
                "dropout": 0.1
            }),
            "processing_options": self.config.get("processing_options", {
                "batch_size": 16,
                "max_sequence_length": 512,
                "image_size": 224,
                "audio_sample_rate": 16000,
                "cache_embeddings": True,
                "enable_gpu": False
            }),
            "task_types": self.config.get("task_types", [
                "classification", "retrieval", "generation", "qa", "captioning",
                "translation", "sentiment", "similarity", "fusion_analysis"
            ])
        }
        
        # Multimodal models and processors
        self.multimodal_models = {}
        self.modality_processors = {}
        self.fusion_models = {}
        
        # Multimodal state
        self.multimodal_state = {
            "modality_embeddings": {},
            "fusion_cache": {},
            "cross_modal_retrieval": {},
            "multimodal_history": deque(maxlen=1000),
            "modality_weights": defaultdict(float),
            "fusion_performance": {},
            "processing_queue": deque(maxlen=500),
            "embedding_cache": {},
            "task_performance": defaultdict(list)
        }
        
        # Background tasks
        self.multimodal_processing_task = None
        self.fusion_update_task = None
        self.model_maintenance_task = None
        
        logger.info(f"Multimodal Agent initialized: {agent_id}")
    
    async def start(self):
        """
        Start the multimodal agent
        """
        await super().start()
        
        # Initialize multimodal models
        await self._initialize_multimodal_models()
        
        # Load multimodal data
        await self._load_multimodal_data()
        
        # Start background tasks
        self.multimodal_processing_task = asyncio.create_task(self._continuous_multimodal_processing())
        self.fusion_update_task = asyncio.create_task(self._continuous_fusion_updates())
        self.model_maintenance_task = asyncio.create_task(self._continuous_model_maintenance())
        
        logger.info("Multimodal agent started")
    
    async def stop(self):
        """
        Stop the multimodal agent
        """
        if self.multimodal_processing_task:
            self.multimodal_processing_task.cancel()
            try:
                await self.multimodal_processing_task
            except asyncio.CancelledError:
                pass
        
        if self.fusion_update_task:
            self.fusion_update_task.cancel()
            try:
                await self.fusion_update_task
            except asyncio.CancelledError:
                pass
        
        if self.model_maintenance_task:
            self.model_maintenance_task.cancel()
            try:
                await self.model_maintenance_task
            except asyncio.CancelledError:
                pass
        
        await super().stop()
        logger.info("Multimodal agent stopped")
    
    async def _initialize_multimodal_models(self):
        """
        Initialize multimodal models and processors
        """
        try:
            # Initialize CLIP for image-text understanding
            clip_model_name = self.multimodal_config["embedding_models"]["clip"]["model_name"]
            self.multimodal_models["clip"] = {
                "model": CLIPModel.from_pretrained(clip_model_name),
                "processor": CLIPProcessor.from_pretrained(clip_model_name),
                "tokenizer": CLIPTokenizer.from_pretrained(clip_model_name)
            }
            
            # Initialize BERT for text processing
            bert_model_name = self.multimodal_config["embedding_models"]["bert"]["model_name"]
            self.multimodal_models["bert"] = {
                "model": BertModel.from_pretrained(bert_model_name),
                "tokenizer": BertTokenizer.from_pretrained(bert_model_name)
            }
            
            # Initialize image processors
            self.modality_processors["image"] = {
                "transforms": T.Compose([
                    T.Resize((224, 224)),
                    T.ToTensor(),
                    T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
                ]),
                "vit_processor": ViTImageProcessor.from_pretrained("google/vit-base-patch16-224")
            }
            
            # Initialize audio processors
            self.modality_processors["audio"] = {
                "sample_rate": 16000,
                "transforms": torchaudio.transforms.MelSpectrogram(
                    sample_rate=16000, n_fft=400, hop_length=160, n_mels=80
                )
            }
            
            # Initialize fusion model (simplified cross-attention)
            fusion_config = self.multimodal_config["fusion_config"]
            self.fusion_models["cross_attention"] = CrossAttentionFusion(
                hidden_size=fusion_config["hidden_size"],
                num_heads=fusion_config["attention_heads"],
                num_layers=fusion_config["num_layers"],
                dropout=fusion_config["dropout"]
            )
            
            # Initialize task-specific models
            self.multimodal_models["captioning"] = VisionEncoderDecoderModel.from_pretrained(
                "nlpconnect/vit-gpt2-image-captioning"
            )
            self.multimodal_models["captioning_processor"] = ViTImageProcessor.from_pretrained(
                "nlpconnect/vit-gpt2-image-captioning"
            )
            self.multimodal_models["captioning_tokenizer"] = AutoTokenizer.from_pretrained(
                "nlpconnect/vit-gpt2-image-captioning"
            )
            
            logger.info("Multimodal models initialized")
            
        except Exception as e:
            logger.error(f"Multimodal model initialization failed: {e}")
    
    async def _load_multimodal_data(self):
        """
        Load existing multimodal data and embeddings
        """
        try:
            # Load modality embeddings, fusion cache, etc.
            await self._load_modality_embeddings()
            await self._load_fusion_cache()
            await self._load_multimodal_history()
            
            logger.info("Multimodal data loaded")
            
        except Exception as e:
            logger.error(f"Multimodal data loading failed: {e}")
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process multimodal requests
        """
        try:
            message_type = message.content.get("type", "")
            
            if message_type == "analyze_multimodal":
                async for response in self._handle_multimodal_analysis(message):
                    yield response
                    
            elif message_type == "fuse_modalities":
                async for response in self._handle_modality_fusion(message):
                    yield response
                    
            elif message_type == "cross_modal_retrieval":
                async for response in self._handle_cross_modal_retrieval(message):
                    yield response
                    
            elif message_type == "generate_caption":
                async for response in self._handle_caption_generation(message):
                    yield response
                    
            elif message_type == "multimodal_qa":
                async for response in self._handle_multimodal_qa(message):
                    yield response
                    
            elif message_type == "multimodal_similarity":
                async for response in self._handle_multimodal_similarity(message):
                    yield response
                    
            elif message_type == "multimodal_translation":
                async for response in self._handle_multimodal_translation(message):
                    yield response
                    
            elif message_type == "analyze_scene":
                async for response in self._handle_scene_analysis(message):
                    yield response
                    
            elif message_type == "multimodal_sentiment":
                async for response in self._handle_multimodal_sentiment(message):
                    yield response
                    
            elif message_type == "generate_multimodal":
                async for response in self._handle_multimodal_generation(message):
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
            logger.error(f"Multimodal processing failed: {e}")
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
    
    async def _handle_multimodal_analysis(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle comprehensive multimodal analysis request
        """
        try:
            modalities_data = message.content.get("modalities", {})
            analysis_types = message.content.get("analysis_types", ["fusion", "similarity", "content"])
            
            # Perform multimodal analysis
            analysis = await self._analyze_multimodal(modalities_data, analysis_types)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "multimodal_analysis_response",
                    "analysis": analysis,
                    "modalities_processed": list(modalities_data.keys()),
                    "analysis_types": analysis_types
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Multimodal analysis handling failed: {e}")
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
    
    async def _analyze_multimodal(
        self,
        modalities_data: Dict[str, Any],
        analysis_types: List[str]
    ) -> Dict[str, Any]:
        """
        Perform comprehensive multimodal analysis
        """
        try:
            analysis_results = {}
            
            # Extract embeddings for each modality
            modality_embeddings = {}
            for modality, data in modalities_data.items():
                embedding = await self._extract_modality_embedding(modality, data)
                if embedding is not None:
                    modality_embeddings[modality] = embedding
            
            if not modality_embeddings:
                return {"error": "No valid modalities provided"}
            
            # Perform requested analyses
            if "fusion" in analysis_types:
                analysis_results["fusion"] = await self._perform_modality_fusion(modality_embeddings)
            
            if "similarity" in analysis_types:
                analysis_results["similarity"] = await self._compute_multimodal_similarity(modality_embeddings)
            
            if "content" in analysis_types:
                analysis_results["content"] = await self._analyze_multimodal_content(modalities_data)
            
            if "sentiment" in analysis_types:
                analysis_results["sentiment"] = await self._analyze_multimodal_sentiment(modalities_data)
            
            if "scene" in analysis_types:
                analysis_results["scene"] = await self._analyze_scene_understanding(modalities_data)
            
            comprehensive_analysis = {
                "results": analysis_results,
                "modalities_analyzed": list(modality_embeddings.keys()),
                "embedding_dimensions": {mod: emb.shape[0] for mod, emb in modality_embeddings.items()},
                "processing_time": datetime.now(),
                "fusion_method": self.multimodal_config["fusion_config"]["method"]
            }
            
            # Cache results
            cache_key = str(hash(str(modalities_data)))
            self.multimodal_state["fusion_cache"][cache_key] = comprehensive_analysis
            
            return comprehensive_analysis
            
        except Exception as e:
            logger.error(f"Multimodal analysis failed: {e}")
            return {"error": str(e)}
    
    async def _extract_modality_embedding(
        self,
        modality: str,
        data: Any
    ) -> Optional[np.ndarray]:
        """
        Extract embedding for a specific modality
        """
        try:
            if modality == "text":
                return await self._extract_text_embedding(data)
            elif modality == "image":
                return await self._extract_image_embedding(data)
            elif modality == "speech" or modality == "audio":
                return await self._extract_audio_embedding(data)
            elif modality == "video":
                return await self._extract_video_embedding(data)
            else:
                logger.warning(f"Unsupported modality: {modality}")
                return None
                
        except Exception as e:
            logger.error(f"Embedding extraction failed for {modality}: {e}")
            return None
    
    async def _extract_text_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Extract text embedding using BERT
        """
        try:
            if not isinstance(text, str) or not text.strip():
                return None
            
            bert_model = self.multimodal_models["bert"]
            tokenizer = bert_model["tokenizer"]
            model = bert_model["model"]
            
            # Tokenize
            inputs = tokenizer(
                text,
                max_length=self.multimodal_config["processing_options"]["max_sequence_length"],
                padding=True,
                truncation=True,
                return_tensors="pt"
            )
            
            # Extract embeddings
            with torch.no_grad():
                outputs = model(**inputs)
                embedding = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
            
            return embedding
            
        except Exception as e:
            logger.error(f"Text embedding extraction failed: {e}")
            return None
    
    async def _extract_image_embedding(self, image_data: Union[str, bytes]) -> Optional[np.ndarray]:
        """
        Extract image embedding using CLIP
        """
        try:
            clip_model = self.multimodal_models["clip"]
            processor = clip_model["processor"]
            model = clip_model["model"]
            
            # Load image
            if isinstance(image_data, str):
                if image_data.startswith("http"):
                    # Load from URL (would need requests)
                    return None
                else:
                    # Load from file path
                    image = Image.open(image_data)
            else:
                # Load from bytes
                image = Image.open(io.BytesIO(image_data))
            
            # Process image
            inputs = processor(images=image, return_tensors="pt")
            
            # Extract embedding
            with torch.no_grad():
                image_features = model.get_image_features(**inputs)
                embedding = image_features.squeeze().numpy()
            
            return embedding
            
        except Exception as e:
            logger.error(f"Image embedding extraction failed: {e}")
            return None
    
    async def _extract_audio_embedding(self, audio_data: Union[str, bytes]) -> Optional[np.ndarray]:
        """
        Extract audio embedding using Wav2Vec2
        """
        try:
            # Placeholder - would use Wav2Vec2 model
            # For now, return a dummy embedding
            return np.random.randn(768)  # Wav2Vec2 hidden size
            
        except Exception as e:
            logger.error(f"Audio embedding extraction failed: {e}")
            return None
    
    async def _extract_video_embedding(self, video_data: Union[str, bytes]) -> Optional[np.ndarray]:
        """
        Extract video embedding (simplified - using frame sampling)
        """
        try:
            # Placeholder - would extract frames and average embeddings
            return np.random.randn(768)
            
        except Exception as e:
            logger.error(f"Video embedding extraction failed: {e}")
            return None
    
    async def _perform_modality_fusion(
        self,
        modality_embeddings: Dict[str, np.ndarray]
    ) -> Dict[str, Any]:
        """
        Perform modality fusion using cross-attention
        """
        try:
            fusion_method = self.multimodal_config["fusion_config"]["method"]
            
            if fusion_method == "cross_attention":
                # Use cross-attention fusion
                fused_embedding = await self._cross_attention_fusion(modality_embeddings)
            elif fusion_method == "early_fusion":
                # Concatenate embeddings
                fused_embedding = np.concatenate(list(modality_embeddings.values()))
            elif fusion_method == "late_fusion":
                # Average embeddings
                fused_embedding = np.mean(list(modality_embeddings.values()), axis=0)
            else:
                fused_embedding = np.mean(list(modality_embeddings.values()), axis=0)
            
            fusion_result = {
                "fused_embedding": fused_embedding.tolist(),
                "fusion_method": fusion_method,
                "modality_contributions": {mod: emb.shape[0] for mod, emb in modality_embeddings.items()},
                "fused_dimension": fused_embedding.shape[0]
            }
            
            return fusion_result
            
        except Exception as e:
            logger.error(f"Modality fusion failed: {e}")
            return {"error": str(e)}
    
    async def _cross_attention_fusion(
        self,
        modality_embeddings: Dict[str, np.ndarray]
    ) -> np.ndarray:
        """
        Perform cross-attention based fusion
        """
        try:
            # Convert to tensors
            embeddings = [torch.from_numpy(emb).float() for emb in modality_embeddings.values()]
            
            # Stack embeddings (batch_size=1, seq_len=1, hidden_size)
            stacked_embeddings = torch.stack(embeddings).unsqueeze(0)  # [1, num_modalities, hidden_size]
            
            # Apply cross-attention fusion
            fusion_model = self.fusion_models["cross_attention"]
            with torch.no_grad():
                fused_output = fusion_model(stacked_embeddings)
            
            # Return fused embedding
            return fused_output.squeeze().numpy()
            
        except Exception as e:
            logger.error(f"Cross-attention fusion failed: {e}")
            # Fallback to averaging
            return np.mean(list(modality_embeddings.values()), axis=0)
    
    async def _compute_multimodal_similarity(
        self,
        modality_embeddings: Dict[str, np.ndarray]
    ) -> Dict[str, Any]:
        """
        Compute similarity between modalities
        """
        try:
            similarities = {}
            modalities = list(modality_embeddings.keys())
            
            for i, mod1 in enumerate(modalities):
                for j, mod2 in enumerate(modalities):
                    if i < j:  # Only compute upper triangle
                        emb1 = modality_embeddings[mod1]
                        emb2 = modality_embeddings[mod2]
                        
                        # Normalize embeddings
                        emb1_norm = emb1 / np.linalg.norm(emb1)
                        emb2_norm = emb2 / np.linalg.norm(emb2)
                        
                        # Compute cosine similarity
                        similarity = np.dot(emb1_norm, emb2_norm)
                        similarities[f"{mod1}_{mod2}"] = float(similarity)
            
            similarity_analysis = {
                "pairwise_similarities": similarities,
                "modalities_compared": modalities,
                "similarity_method": "cosine",
                "average_similarity": np.mean(list(similarities.values())) if similarities else 0
            }
            
            return similarity_analysis
            
        except Exception as e:
            logger.error(f"Multimodal similarity computation failed: {e}")
            return {"error": str(e)}
    
    async def _analyze_multimodal_content(
        self,
        modalities_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze content across modalities
        """
        try:
            content_analysis = {}
            
            # Analyze each modality
            for modality, data in modalities_data.items():
                if modality == "text":
                    content_analysis["text"] = await self._analyze_text_content(data)
                elif modality == "image":
                    content_analysis["image"] = await self._analyze_image_content(data)
                elif modality == "speech":
                    content_analysis["speech"] = await self._analyze_speech_content(data)
            
            # Cross-modal content analysis
            content_analysis["cross_modal"] = await self._analyze_cross_modal_content(modalities_data)
            
            return content_analysis
            
        except Exception as e:
            logger.error(f"Multimodal content analysis failed: {e}")
            return {"error": str(e)}
    
    async def _analyze_text_content(self, text: str) -> Dict[str, Any]:
        """
        Analyze text content
        """
        try:
            # Basic text analysis
            words = text.split()
            sentences = text.split('.')
            
            analysis = {
                "word_count": len(words),
                "sentence_count": len(sentences),
                "avg_word_length": np.mean([len(word) for word in words]),
                "language": "en",  # Would use language detection
                "sentiment": "neutral"  # Would use sentiment analysis
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Text content analysis failed: {e}")
            return {}
    
    async def _analyze_image_content(self, image_data: Union[str, bytes]) -> Dict[str, Any]:
        """
        Analyze image content
        """
        try:
            # Load image
            if isinstance(image_data, str):
                image = Image.open(image_data)
            else:
                image = Image.open(io.BytesIO(image_data))
            
            analysis = {
                "size": image.size,
                "mode": image.mode,
                "format": image.format,
                "dominant_colors": [],  # Would extract dominant colors
                "objects_detected": []  # Would use object detection
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Image content analysis failed: {e}")
            return {}
    
    async def _analyze_speech_content(self, audio_data: Union[str, bytes]) -> Dict[str, Any]:
        """
        Analyze speech content
        """
        try:
            analysis = {
                "duration": 0,  # Would extract duration
                "speakers": 1,  # Would detect speakers
                "language": "en",  # Would detect language
                "sentiment": "neutral"  # Would analyze speech sentiment
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Speech content analysis failed: {e}")
            return {}
    
    async def _analyze_cross_modal_content(
        self,
        modalities_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze relationships between modalities
        """
        try:
            cross_modal_analysis = {
                "text_image_alignment": 0.8,  # Would compute alignment score
                "speech_text_consistency": 0.9,  # Would check consistency
                "multimodal_coherence": 0.85,  # Would assess overall coherence
                "conflicting_information": []  # Would detect conflicts
            }
            
            return cross_modal_analysis
            
        except Exception as e:
            logger.error(f"Cross-modal content analysis failed: {e}")
            return {}
    
    async def _analyze_multimodal_sentiment(
        self,
        modalities_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze sentiment across modalities
        """
        try:
            sentiment_scores = {}
            
            for modality, data in modalities_data.items():
                if modality == "text":
                    sentiment_scores["text"] = await self._analyze_text_sentiment(data)
                elif modality == "speech":
                    sentiment_scores["speech"] = await self._analyze_speech_sentiment(data)
                elif modality == "image":
                    sentiment_scores["image"] = await self._analyze_image_sentiment(data)
            
            # Fuse sentiment scores
            overall_sentiment = await self._fuse_sentiment_scores(sentiment_scores)
            
            sentiment_analysis = {
                "modality_sentiments": sentiment_scores,
                "overall_sentiment": overall_sentiment,
                "sentiment_consistency": 0.9  # Would compute consistency
            }
            
            return sentiment_analysis
            
        except Exception as e:
            logger.error(f"Multimodal sentiment analysis failed: {e}")
            return {"error": str(e)}
    
    async def _analyze_text_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze text sentiment"""
        return {"sentiment": "neutral", "confidence": 0.7}
    
    async def _analyze_speech_sentiment(self, audio_data: Union[str, bytes]) -> Dict[str, Any]:
        """Analyze speech sentiment"""
        return {"sentiment": "neutral", "confidence": 0.6}
    
    async def _analyze_image_sentiment(self, image_data: Union[str, bytes]) -> Dict[str, Any]:
        """Analyze image sentiment"""
        return {"sentiment": "neutral", "confidence": 0.5}
    
    async def _fuse_sentiment_scores(self, sentiment_scores: Dict[str, Dict]) -> Dict[str, Any]:
        """Fuse sentiment scores from different modalities"""
        return {"sentiment": "neutral", "confidence": 0.6}
    
    async def _analyze_scene_understanding(
        self,
        modalities_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Understand scene from multimodal data
        """
        try:
            scene_analysis = {
                "scene_description": "A typical scene",  # Would generate description
                "objects_present": [],  # Would detect objects
                "activities": [],  # Would recognize activities
                "context": "general",  # Would classify context
                "confidence": 0.8
            }
            
            return scene_analysis
            
        except Exception as e:
            logger.error(f"Scene understanding failed: {e}")
            return {"error": str(e)}
    
    # Additional handler methods would continue...
    
    async def _handle_modality_fusion(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle modality fusion request
        """
        try:
            modalities_data = message.content.get("modalities", {})
            fusion_method = message.content.get("fusion_method", "cross_attention")
            
            # Perform modality fusion
            fusion_result = await self._fuse_modalities(modalities_data, fusion_method)
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "modality_fusion_response",
                    "fusion_result": fusion_result,
                    "fusion_method": fusion_method
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Modality fusion handling failed: {e}")
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
    
    async def _fuse_modalities(
        self,
        modalities_data: Dict[str, Any],
        fusion_method: str
    ) -> Dict[str, Any]:
        """
        Fuse multiple modalities
        """
        try:
            # Extract embeddings
            modality_embeddings = {}
            for modality, data in modalities_data.items():
                embedding = await self._extract_modality_embedding(modality, data)
                if embedding is not None:
                    modality_embeddings[modality] = embedding
            
            if not modality_embeddings:
                return {"error": "No valid modalities provided"}
            
            # Perform fusion
            if fusion_method == "cross_attention":
                fused_embedding = await self._cross_attention_fusion(modality_embeddings)
            elif fusion_method == "early_fusion":
                fused_embedding = np.concatenate(list(modality_embeddings.values()))
            elif fusion_method == "late_fusion":
                fused_embedding = np.mean(list(modality_embeddings.values()), axis=0)
            else:
                fused_embedding = np.mean(list(modality_embeddings.values()), axis=0)
            
            fusion_result = {
                "fused_embedding": fused_embedding.tolist(),
                "fusion_method": fusion_method,
                "modalities_fused": list(modality_embeddings.keys()),
                "fused_dimension": fused_embedding.shape[0]
            }
            
            return fusion_result
            
        except Exception as e:
            logger.error(f"Modality fusion failed: {e}")
            return {"error": str(e)}
    
    # Background processing tasks
    async def _continuous_multimodal_processing(self):
        """
        Continuous multimodal processing from queue
        """
        try:
            while True:
                try:
                    # Process queued multimodal tasks
                    if self.multimodal_state["processing_queue"]:
                        multimodal_task = self.multimodal_state["processing_queue"].popleft()
                        await self._process_multimodal_task(multimodal_task)
                    
                except Exception as e:
                    logger.error(f"Multimodal processing error: {e}")
                
                # Process every 3 seconds
                await asyncio.sleep(3)
                
        except asyncio.CancelledError:
            logger.info("Multimodal processing cancelled")
            raise
    
    async def _continuous_fusion_updates(self):
        """
        Continuous fusion model updates
        """
        try:
            while True:
                try:
                    # Update fusion models and weights
                    await self._update_fusion_models()
                    
                except Exception as e:
                    logger.error(f"Fusion update error: {e}")
                
                # Update every 30 minutes
                await asyncio.sleep(1800)
                
        except asyncio.CancelledError:
            logger.info("Fusion updates cancelled")
            raise
    
    async def _continuous_model_maintenance(self):
        """
        Continuous model maintenance and updates
        """
        try:
            while True:
                try:
                    # Update models, clear cache, etc.
                    await self._update_multimodal_models()
                    await self._cleanup_multimodal_cache()
                    
                except Exception as e:
                    logger.error(f"Model maintenance error: {e}")
                
                # Maintain every hour
                await asyncio.sleep(3600)
                
        except asyncio.CancelledError:
            logger.info("Model maintenance cancelled")
            raise
    
    # Additional helper methods would continue here...
    
    async def _load_modality_embeddings(self):
        """Load modality embeddings"""
        try:
            # Implementation for loading modality embeddings
            pass
        except Exception as e:
            logger.error(f"Modality embeddings loading failed: {e}")
    
    async def _load_fusion_cache(self):
        """Load fusion cache"""
        try:
            # Implementation for loading fusion cache
            pass
        except Exception as e:
            logger.error(f"Fusion cache loading failed: {e}")
    
    async def _load_multimodal_history(self):
        """Load multimodal history"""
        try:
            # Implementation for loading multimodal history
            pass
        except Exception as e:
            logger.error(f"Multimodal history loading failed: {e}")
    
    async def _process_multimodal_task(self, task: Dict[str, Any]):
        """Process queued multimodal task"""
        try:
            # Implementation for processing multimodal task
            pass
        except Exception as e:
            logger.error(f"Multimodal task processing failed: {e}")
    
    async def _update_fusion_models(self):
        """Update fusion models"""
        try:
            # Implementation for updating fusion models
            pass
        except Exception as e:
            logger.error(f"Fusion model update failed: {e}")
    
    async def _update_multimodal_models(self):
        """Update multimodal models"""
        try:
            # Implementation for updating multimodal models
            pass
        except Exception as e:
            logger.error(f"Multimodal model update failed: {e}")
    
    async def _cleanup_multimodal_cache(self):
        """Cleanup multimodal cache"""
        try:
            # Implementation for cleaning up multimodal cache
            pass
        except Exception as e:
            logger.error(f"Multimodal cache cleanup failed: {e}")


class CrossAttentionFusion(nn.Module):
    """
    Cross-attention based multimodal fusion model
    """
    
    def __init__(
        self,
        hidden_size: int = 768,
        num_heads: int = 8,
        num_layers: int = 6,
        dropout: float = 0.1
    ):
        super().__init__()
        
        self.hidden_size = hidden_size
        self.num_heads = num_heads
        self.num_layers = num_layers
        
        # Multi-head attention for cross-modal fusion
        self.cross_attention = nn.MultiheadAttention(
            embed_dim=hidden_size,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True
        )
        
        # Feed-forward network
        self.feed_forward = nn.Sequential(
            nn.Linear(hidden_size, hidden_size * 4),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size * 4, hidden_size),
            nn.Dropout(dropout)
        )
        
        # Layer normalization
        self.norm1 = nn.LayerNorm(hidden_size)
        self.norm2 = nn.LayerNorm(hidden_size)
        
        # Modality-specific projections (assuming different input dimensions)
        self.modality_projections = nn.ModuleDict({
            'text': nn.Linear(768, hidden_size),  # BERT base
            'image': nn.Linear(512, hidden_size),  # CLIP ViT
            'speech': nn.Linear(768, hidden_size),  # Wav2Vec2
            'video': nn.Linear(768, hidden_size)   # Video features
        })
    
    def forward(self, modality_embeddings: torch.Tensor) -> torch.Tensor:
        """
        Forward pass for cross-attention fusion
        
        Args:
            modality_embeddings: [batch_size, num_modalities, embedding_dim]
        
        Returns:
            fused_embedding: [batch_size, hidden_size]
        """
        batch_size, num_modalities, embedding_dim = modality_embeddings.shape
        
        # Project each modality to common hidden size
        projected_embeddings = []
        for i in range(num_modalities):
            modality_type = list(self.modality_projections.keys())[i % len(self.modality_projections)]
            projection = self.modality_projections[modality_type]
            projected = projection(modality_embeddings[:, i, :])
            projected_embeddings.append(projected)
        
        projected_embeddings = torch.stack(projected_embeddings, dim=1)  # [batch, num_modalities, hidden]
        
        # Apply cross-attention
        # Use the first modality as query, others as key/value
        query = projected_embeddings[:, 0:1, :]  # [batch, 1, hidden]
        key_value = projected_embeddings  # [batch, num_modalities, hidden]
        
        attn_output, _ = self.cross_attention(query, key_value, key_value)
        
        # Apply feed-forward network
        fused = self.norm1(attn_output.squeeze(1) + query.squeeze(1))
        fused = self.norm2(self.feed_forward(fused) + fused)
        
        return fused


# ========== TEST ==========
if __name__ == "__main__":
    async def test_multimodal_agent():
        # Initialize multimodal agent
        agent = MultimodalAgent()
        await agent.start()
        
        # Test multimodal analysis
        multimodal_message = AgentMessage(
            id="test_multimodal",
            from_agent="test",
            to_agent="multimodal_agent",
            content={
                "type": "analyze_multimodal",
                "modalities": {
                    "text": "A beautiful sunset over the ocean",
                    "image": "path/to/sunset.jpg"  # Would need real image
                },
                "analysis_types": ["fusion", "similarity", "content"]
            },
            timestamp=datetime.now()
        )
        
        print("Testing multimodal agent...")
        async for response in agent.process_message(multimodal_message):
            print(f"Multimodal analysis response: {response.content.get('type')}")
            analysis = response.content.get('analysis')
            print(f"Analysis result: {analysis}")
        
        # Test modality fusion
        fusion_message = AgentMessage(
            id="test_fusion",
            from_agent="test",
            to_agent="multimodal_agent",
            content={
                "type": "fuse_modalities",
                "modalities": {
                    "text": "A cat sitting on a mat",
                    "image": "path/to/cat.jpg"  # Would need real image
                },
                "fusion_method": "cross_attention"
            },
            timestamp=datetime.now()
        )
        
        async for response in agent.process_message(fusion_message):
            print(f"Modality fusion response: {response.content.get('type')}")
            fusion = response.content.get('fusion_result')
            print(f"Fusion result: {fusion}")
        
        # Stop agent
        await agent.stop()
        print("Multimodal agent test completed")
    
    # Run test
    asyncio.run(test_multimodal_agent())
