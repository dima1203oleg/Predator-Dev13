"""
Image Processing Agent: Computer vision and image analysis
Provides advanced computer vision capabilities for image classification,
object detection, OCR, image similarity, and visual analysis
"""

import asyncio
import base64
import io
import logging
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

import easyocr
import face_recognition
import numpy as np
import pytesseract
import torch
import torchvision.models as models
import torchvision.transforms as transforms
from deepface import DeepFace
from PIL import Image, ImageEnhance, ImageFilter
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from transformers import (
    AutoImageProcessor,
    AutoModelForImageClassification,
    AutoModelForObjectDetection,
    CLIPModel,
    CLIPProcessor,
)
from ultralytics import YOLO

from ..agents.base_agent import AgentMessage, BaseAgent

logger = logging.getLogger(__name__)


class ImageProcessingAgent(BaseAgent):
    """
    Image Processing Agent for computer vision tasks
    Uses multiple CV models and techniques for comprehensive image analysis
    """

    def __init__(
        self, agent_id: str = "image_processing_agent", config: dict[str, Any] | None = None
    ):
        super().__init__(agent_id, config or {})

        # Image processing configuration
        self.image_config = {
            "supported_formats": self.config.get(
                "formats", ["jpg", "jpeg", "png", "bmp", "tiff", "webp", "gif"]
            ),
            "max_image_size": self.config.get("max_size", 10 * 1024 * 1024),  # 10MB
            "processing_methods": self.config.get(
                "methods",
                [
                    "classification",
                    "object_detection",
                    "ocr",
                    "face_recognition",
                    "image_similarity",
                    "segmentation",
                    "enhancement",
                    "analysis",
                ],
            ),
            "model_configs": self.config.get(
                "models",
                {
                    "classification": {
                        "model_name": "google/vit-base-patch16-224",
                        "device": "cpu",
                    },
                    "object_detection": {"model_name": "facebook/detr-resnet-50", "device": "cpu"},
                    "ocr": {"easyocr_langs": ["en", "uk", "ru"], "tesseract_config": "--psm 6"},
                    "clip": {"model_name": "openai/clip-vit-base-patch32", "device": "cpu"},
                },
            ),
            "quality_thresholds": self.config.get(
                "thresholds",
                {
                    "classification_confidence": 0.7,
                    "detection_confidence": 0.5,
                    "similarity_threshold": 0.8,
                    "face_recognition_threshold": 0.6,
                },
            ),
            "processing_options": self.config.get(
                "options",
                {"batch_size": 4, "max_workers": 4, "cache_embeddings": True, "enable_gpu": False},
            ),
        }

        # ML models for image processing
        self.cv_models = {}
        self.feature_extractors = {}
        self.embedding_cache = {}

        # Image processing state
        self.image_state = {
            "processed_images": {},
            "image_embeddings": {},
            "face_database": {},
            "object_templates": {},
            "processing_queue": deque(maxlen=1000),
            "analysis_results": deque(maxlen=5000),
            "performance_metrics": {},
            "model_cache": {},
            "processing_stats": defaultdict(int),
        }

        # Background tasks
        self.image_processing_task = None
        self.model_maintenance_task = None
        self.embedding_update_task = None

        logger.info(f"Image Processing Agent initialized: {agent_id}")

    async def start(self):
        """
        Start the image processing agent
        """
        await super().start()

        # Initialize CV models
        await self._initialize_cv_models()

        # Load image data
        await self._load_image_data()

        # Start background tasks
        self.image_processing_task = asyncio.create_task(self._continuous_image_processing())
        self.model_maintenance_task = asyncio.create_task(self._continuous_model_maintenance())
        self.embedding_update_task = asyncio.create_task(self._continuous_embedding_updates())

        logger.info("Image processing started")

    async def stop(self):
        """
        Stop the image processing agent
        """
        if self.image_processing_task:
            self.image_processing_task.cancel()
            try:
                await self.image_processing_task
            except asyncio.CancelledError:
                pass

        if self.model_maintenance_task:
            self.model_maintenance_task.cancel()
            try:
                await self.model_maintenance_task
            except asyncio.CancelledError:
                pass

        if self.embedding_update_task:
            self.embedding_update_task.cancel()
            try:
                await self.embedding_update_task
            except asyncio.CancelledError:
                pass

        await super().stop()
        logger.info("Image processing agent stopped")

    async def _initialize_cv_models(self):
        """
        Initialize computer vision models
        """
        try:
            # Image classification model
            self.cv_models["classifier"] = {
                "processor": AutoImageProcessor.from_pretrained(
                    self.image_config["model_configs"]["classification"]["model_name"]
                ),
                "model": AutoModelForImageClassification.from_pretrained(
                    self.image_config["model_configs"]["classification"]["model_name"]
                ),
            }

            # Object detection model
            self.cv_models["detector"] = {
                "processor": AutoImageProcessor.from_pretrained(
                    self.image_config["model_configs"]["object_detection"]["model_name"]
                ),
                "model": AutoModelForObjectDetection.from_pretrained(
                    self.image_config["model_configs"]["object_detection"]["model_name"]
                ),
            }

            # OCR models
            self.cv_models["easyocr"] = easyocr.Reader(
                self.image_config["model_configs"]["ocr"]["easyocr_langs"]
            )

            # CLIP model for image-text similarity
            self.cv_models["clip"] = {
                "processor": CLIPProcessor.from_pretrained(
                    self.image_config["model_configs"]["clip"]["model_name"]
                ),
                "model": CLIPModel.from_pretrained(
                    self.image_config["model_configs"]["clip"]["model_name"]
                ),
            }

            # YOLO for object detection (alternative)
            self.cv_models["yolo"] = YOLO("yolov8n.pt")  # nano model

            # Feature extractor for similarity
            self.feature_extractors["resnet"] = models.resnet50(pretrained=True)
            self.feature_extractors["resnet"].eval()

            # Face recognition models
            self.cv_models["face_recognition"] = {
                "face_recognition": face_recognition,
                "deepface": DeepFace,
            }

            logger.info("CV models initialized")

        except Exception as e:
            logger.error(f"CV model initialization failed: {e}")

    async def _load_image_data(self):
        """
        Load existing image data and embeddings
        """
        try:
            # Load face database, object templates, etc.
            await self._load_face_database()
            await self._load_object_templates()
            await self._load_image_embeddings()

            logger.info("Image data loaded")

        except Exception as e:
            logger.error(f"Image data loading failed: {e}")

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process image processing requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "classify_image":
                async for response in self._handle_image_classification(message):
                    yield response

            elif message_type == "detect_objects":
                async for response in self._handle_object_detection(message):
                    yield response

            elif message_type == "extract_text":
                async for response in self._handle_text_extraction(message):
                    yield response

            elif message_type == "recognize_faces":
                async for response in self._handle_face_recognition(message):
                    yield response

            elif message_type == "compare_images":
                async for response in self._handle_image_similarity(message):
                    yield response

            elif message_type == "enhance_image":
                async for response in self._handle_image_enhancement(message):
                    yield response

            elif message_type == "analyze_image":
                async for response in self._handle_image_analysis(message):
                    yield response

            elif message_type == "segment_image":
                async for response in self._handle_image_segmentation(message):
                    yield response

            elif message_type == "generate_caption":
                async for response in self._handle_image_captioning(message):
                    yield response

            elif message_type == "detect_emotions":
                async for response in self._handle_emotion_detection(message):
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
            logger.error(f"Image processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_image_classification(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle image classification request
        """
        try:
            image_data = message.content.get("image_data")
            image_url = message.content.get("image_url")
            top_k = message.content.get("top_k", 5)

            # Classify image
            classification = await self._classify_image(image_data, image_url, top_k)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "image_classification_response",
                    "classification": classification,
                    "top_k": top_k,
                    "confidence_threshold": self.image_config["quality_thresholds"][
                        "classification_confidence"
                    ],
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Image classification handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _classify_image(
        self, image_data: str | None = None, image_url: str | None = None, top_k: int = 5
    ) -> dict[str, Any]:
        """
        Classify image using pre-trained model
        """
        try:
            # Load image
            image = await self._load_image(image_data, image_url)
            if image is None:
                raise ValueError("Could not load image")

            # Preprocess image
            processor = self.cv_models["classifier"]["processor"]
            model = self.cv_models["classifier"]["model"]

            inputs = processor(images=image, return_tensors="pt")

            # Classify
            with torch.no_grad():
                outputs = model(**inputs)
                logits = outputs.logits
                probabilities = torch.nn.functional.softmax(logits, dim=-1)

            # Get top predictions
            top_probs, top_class_ids = torch.topk(probabilities, top_k)

            # Get class labels
            class_labels = []
            for i in range(top_k):
                class_id = top_class_ids[0][i].item()
                probability = top_probs[0][i].item()

                # Get label from config
                label = model.config.id2label.get(class_id, f"class_{class_id}")

                class_labels.append(
                    {"label": label, "confidence": probability, "class_id": class_id}
                )

            classification = {
                "predictions": class_labels,
                "model_used": "vit-base-patch16-224",
                "processing_time": datetime.now(),
            }

            return classification

        except Exception as e:
            logger.error(f"Image classification failed: {e}")
            return {"error": str(e)}

    async def _handle_object_detection(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle object detection request
        """
        try:
            image_data = message.content.get("image_data")
            image_url = message.content.get("image_url")
            confidence_threshold = message.content.get(
                "confidence_threshold",
                self.image_config["quality_thresholds"]["detection_confidence"],
            )

            # Detect objects
            detections = await self._detect_objects(image_data, image_url, confidence_threshold)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "object_detection_response",
                    "detections": detections,
                    "objects_found": len(detections.get("objects", [])),
                    "confidence_threshold": confidence_threshold,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Object detection handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _detect_objects(
        self,
        image_data: str | None = None,
        image_url: str | None = None,
        confidence_threshold: float = 0.5,
    ) -> dict[str, Any]:
        """
        Detect objects in image using DETR or YOLO
        """
        try:
            # Load image
            image = await self._load_image(image_data, image_url)
            if image is None:
                raise ValueError("Could not load image")

            # Use YOLO for faster detection
            yolo_model = self.cv_models["yolo"]

            # Convert PIL to numpy array
            image_np = np.array(image)

            # Run detection
            results = yolo_model(image_np)

            # Process results
            objects = []
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    confidence = box.conf[0].item()
                    if confidence >= confidence_threshold:
                        class_id = int(box.cls[0].item())
                        class_name = result.names[class_id]
                        bbox = box.xyxy[0].tolist()

                        objects.append(
                            {
                                "label": class_name,
                                "confidence": confidence,
                                "bbox": bbox,  # [x1, y1, x2, y2]
                                "class_id": class_id,
                            }
                        )

            detections = {
                "objects": objects,
                "model_used": "yolov8n",
                "image_size": image.size,
                "processing_time": datetime.now(),
            }

            return detections

        except Exception as e:
            logger.error(f"Object detection failed: {e}")
            return {"error": str(e)}

    async def _handle_text_extraction(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle text extraction (OCR) request
        """
        try:
            image_data = message.content.get("image_data")
            image_url = message.content.get("image_url")
            ocr_method = message.content.get("ocr_method", "easyocr")  # easyocr, tesseract, or both

            # Extract text
            ocr_result = await self._extract_text(image_data, image_url, ocr_method)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "text_extraction_response",
                    "ocr_result": ocr_result,
                    "method_used": ocr_method,
                    "text_length": len(ocr_result.get("text", "")),
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Text extraction handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _extract_text(
        self,
        image_data: str | None = None,
        image_url: str | None = None,
        ocr_method: str = "easyocr",
    ) -> dict[str, Any]:
        """
        Extract text from image using OCR
        """
        try:
            # Load image
            image = await self._load_image(image_data, image_url)
            if image is None:
                raise ValueError("Could not load image")

            # Convert to numpy array
            image_np = np.array(image)

            extracted_text = ""
            confidence_scores = []

            if ocr_method in ["easyocr", "both"]:
                # Use EasyOCR
                easyocr_reader = self.cv_models["easyocr"]
                easyocr_results = easyocr_reader.readtext(image_np)

                easyocr_text = ""
                for bbox, text, confidence in easyocr_results:
                    easyocr_text += text + " "
                    confidence_scores.append(confidence)

                extracted_text = easyocr_text.strip()

            if ocr_method in ["tesseract", "both"]:
                # Use Tesseract
                tesseract_config = self.image_config["model_configs"]["ocr"]["tesseract_config"]
                tesseract_text = pytesseract.image_to_string(image_np, config=tesseract_config)

                if ocr_method == "both":
                    # Combine results
                    extracted_text = f"{extracted_text}\n{tesseract_text}".strip()
                else:
                    extracted_text = tesseract_text

            ocr_result = {
                "text": extracted_text,
                "method": ocr_method,
                "confidence": np.mean(confidence_scores) if confidence_scores else 0.0,
                "language": "en",  # Could be detected
                "processing_time": datetime.now(),
            }

            return ocr_result

        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return {"error": str(e)}

    async def _handle_face_recognition(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle face recognition request
        """
        try:
            image_data = message.content.get("image_data")
            image_url = message.content.get("image_url")
            recognition_mode = message.content.get("mode", "detect")  # detect, recognize, verify

            # Recognize faces
            face_result = await self._recognize_faces(image_data, image_url, recognition_mode)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "face_recognition_response",
                    "face_result": face_result,
                    "mode": recognition_mode,
                    "faces_found": len(face_result.get("faces", [])),
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Face recognition handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _recognize_faces(
        self,
        image_data: str | None = None,
        image_url: str | None = None,
        recognition_mode: str = "detect",
    ) -> dict[str, Any]:
        """
        Recognize faces in image
        """
        try:
            # Load image
            image = await self._load_image(image_data, image_url)
            if image is None:
                raise ValueError("Could not load image")

            # Convert to numpy array
            image_np = np.array(image)

            faces = []

            if recognition_mode == "detect":
                # Detect faces
                face_locations = face_recognition.face_locations(image_np)

                for face_location in face_locations:
                    top, right, bottom, left = face_location

                    faces.append(
                        {
                            "bbox": [left, top, right, bottom],
                            "confidence": 0.9,  # face_recognition doesn't provide confidence
                            "landmarks": None,
                        }
                    )

            elif recognition_mode == "recognize":
                # Recognize faces against database
                face_encodings = face_recognition.face_encodings(image_np)
                face_locations = face_recognition.face_locations(image_np)

                for i, (face_encoding, face_location) in enumerate(
                    zip(face_encodings, face_locations)
                ):
                    # Compare with known faces
                    matches = face_recognition.compare_faces(
                        list(self.image_state["face_database"].values()),
                        face_encoding,
                        tolerance=self.image_config["quality_thresholds"][
                            "face_recognition_threshold"
                        ],
                    )

                    face_distances = face_recognition.face_distance(
                        list(self.image_state["face_database"].values()), face_encoding
                    )

                    # Find best match
                    best_match_index = np.argmin(face_distances)
                    if matches[best_match_index]:
                        identity = list(self.image_state["face_database"].keys())[best_match_index]
                        confidence = 1 - face_distances[best_match_index]
                    else:
                        identity = "unknown"
                        confidence = 0.0

                    top, right, bottom, left = face_location

                    faces.append(
                        {
                            "bbox": [left, top, right, bottom],
                            "identity": identity,
                            "confidence": confidence,
                            "encoding": face_encoding.tolist(),
                        }
                    )

            face_result = {
                "faces": faces,
                "mode": recognition_mode,
                "model_used": "face_recognition",
                "processing_time": datetime.now(),
            }

            return face_result

        except Exception as e:
            logger.error(f"Face recognition failed: {e}")
            return {"error": str(e)}

    async def _handle_image_similarity(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle image similarity comparison request
        """
        try:
            image_data_1 = message.content.get("image_data_1")
            image_data_2 = message.content.get("image_data_2")
            image_url_1 = message.content.get("image_url_1")
            image_url_2 = message.content.get("image_url_2")
            similarity_method = message.content.get(
                "method", "embedding"
            )  # embedding, perceptual, hash

            # Compare images
            similarity = await self._compare_images(
                image_data_1, image_data_2, image_url_1, image_url_2, similarity_method
            )

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "image_similarity_response",
                    "similarity": similarity,
                    "method": similarity_method,
                    "threshold": self.image_config["quality_thresholds"]["similarity_threshold"],
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Image similarity handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _compare_images(
        self,
        image_data_1: str | None = None,
        image_data_2: str | None = None,
        image_url_1: str | None = None,
        image_url_2: str | None = None,
        similarity_method: str = "embedding",
    ) -> dict[str, Any]:
        """
        Compare similarity between two images
        """
        try:
            # Load images
            image1 = await self._load_image(image_data_1, image_url_1)
            image2 = await self._load_image(image_data_2, image_url_2)

            if image1 is None or image2 is None:
                raise ValueError("Could not load one or both images")

            similarity_score = 0.0

            if similarity_method == "embedding":
                # Use CLIP embeddings for semantic similarity
                clip_processor = self.cv_models["clip"]["processor"]
                clip_model = self.cv_models["clip"]["model"]

                inputs1 = clip_processor(images=image1, return_tensors="pt")
                inputs2 = clip_processor(images=image2, return_tensors="pt")

                with torch.no_grad():
                    embeddings1 = clip_model.get_image_features(**inputs1)
                    embeddings2 = clip_model.get_image_features(**inputs2)

                # Normalize embeddings
                embeddings1 = embeddings1 / embeddings1.norm(dim=-1, keepdim=True)
                embeddings2 = embeddings2 / embeddings2.norm(dim=-1, keepdim=True)

                # Calculate cosine similarity
                similarity_score = torch.cosine_similarity(embeddings1, embeddings2).item()

            elif similarity_method == "perceptual":
                # Use ResNet features for perceptual similarity
                embedding1 = await self._extract_image_embedding(image1)
                embedding2 = await self._extract_image_embedding(image2)

                similarity_score = cosine_similarity([embedding1], [embedding2])[0][0]

            elif similarity_method == "hash":
                # Use perceptual hashing
                hash1 = await self._calculate_image_hash(image1)
                hash2 = await self._calculate_image_hash(image2)

                # Calculate Hamming distance
                hamming_distance = sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
                max_distance = len(hash1)
                similarity_score = 1 - (hamming_distance / max_distance)

            similarity_result = {
                "similarity_score": similarity_score,
                "method": similarity_method,
                "is_similar": similarity_score
                >= self.image_config["quality_thresholds"]["similarity_threshold"],
                "processing_time": datetime.now(),
            }

            return similarity_result

        except Exception as e:
            logger.error(f"Image similarity comparison failed: {e}")
            return {"error": str(e)}

    async def _extract_image_embedding(self, image: Image.Image) -> np.ndarray:
        """
        Extract image embedding using ResNet
        """
        try:
            # Preprocess image
            preprocess = transforms.Compose(
                [
                    transforms.Resize(256),
                    transforms.CenterCrop(224),
                    transforms.ToTensor(),
                    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                ]
            )

            input_tensor = preprocess(image)
            input_batch = input_tensor.unsqueeze(0)

            # Extract features
            with torch.no_grad():
                features = self.feature_extractors["resnet"](input_batch)

            # Convert to numpy
            embedding = features.squeeze().numpy()

            return embedding

        except Exception as e:
            logger.error(f"Image embedding extraction failed: {e}")
            return np.zeros(2048)  # ResNet50 output size

    async def _calculate_image_hash(self, image: Image.Image) -> str:
        """
        Calculate perceptual hash of image
        """
        try:
            # Resize image to 8x8
            small_image = image.resize((8, 8), Image.Resampling.LANCZOS)

            # Convert to grayscale
            small_image = small_image.convert("L")

            # Get pixel values
            pixels = np.array(small_image.getdata())

            # Calculate average
            avg = pixels.mean()

            # Create hash
            hash_string = ""
            for pixel in pixels:
                if pixel > avg:
                    hash_string += "1"
                else:
                    hash_string += "0"

            return hash_string

        except Exception as e:
            logger.error(f"Image hash calculation failed: {e}")
            return "0" * 64

    async def _handle_image_enhancement(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle image enhancement request
        """
        try:
            image_data = message.content.get("image_data")
            image_url = message.content.get("image_url")
            enhancement_type = message.content.get(
                "enhancement_type", "auto"
            )  # auto, sharpen, denoise, contrast

            # Enhance image
            enhanced_image = await self._enhance_image(image_data, image_url, enhancement_type)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "image_enhancement_response",
                    "enhanced_image": enhanced_image,
                    "enhancement_type": enhancement_type,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Image enhancement handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _enhance_image(
        self,
        image_data: str | None = None,
        image_url: str | None = None,
        enhancement_type: str = "auto",
    ) -> dict[str, Any]:
        """
        Enhance image quality
        """
        try:
            # Load image
            image = await self._load_image(image_data, image_url)
            if image is None:
                raise ValueError("Could not load image")

            enhanced_image = image.copy()

            if enhancement_type == "auto":
                # Auto enhancement
                enhanced_image = ImageEnhance.Contrast(enhanced_image).enhance(1.2)
                enhanced_image = ImageEnhance.Sharpness(enhanced_image).enhance(1.5)
                enhanced_image = enhanced_image.filter(
                    ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3)
                )

            elif enhancement_type == "sharpen":
                # Sharpen image
                enhanced_image = enhanced_image.filter(
                    ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3)
                )

            elif enhancement_type == "denoise":
                # Denoise image
                enhanced_image = enhanced_image.filter(ImageFilter.MedianFilter(size=3))

            elif enhancement_type == "contrast":
                # Enhance contrast
                enhanced_image = ImageEnhance.Contrast(enhanced_image).enhance(1.5)

            # Convert to base64 for response
            buffer = io.BytesIO()
            enhanced_image.save(buffer, format="JPEG")
            enhanced_data = base64.b64encode(buffer.getvalue()).decode()

            enhancement_result = {
                "enhanced_image_data": enhanced_data,
                "original_size": image.size,
                "enhanced_size": enhanced_image.size,
                "enhancement_type": enhancement_type,
                "processing_time": datetime.now(),
            }

            return enhancement_result

        except Exception as e:
            logger.error(f"Image enhancement failed: {e}")
            return {"error": str(e)}

    async def _handle_image_analysis(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle comprehensive image analysis request
        """
        try:
            image_data = message.content.get("image_data")
            image_url = message.content.get("image_url")
            analysis_types = message.content.get(
                "analysis_types", ["classification", "objects", "text"]
            )

            # Analyze image comprehensively
            analysis = await self._analyze_image(image_data, image_url, analysis_types)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "image_analysis_response",
                    "analysis": analysis,
                    "analysis_types": analysis_types,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Image analysis handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _analyze_image(
        self,
        image_data: str | None = None,
        image_url: str | None = None,
        analysis_types: list[str] = None,
    ) -> dict[str, Any]:
        """
        Perform comprehensive image analysis
        """
        try:
            if analysis_types is None:
                analysis_types = ["classification", "objects", "text"]

            analysis_results = {}

            # Load image once
            image = await self._load_image(image_data, image_url)
            if image is None:
                raise ValueError("Could not load image")

            # Perform requested analyses
            if "classification" in analysis_types:
                analysis_results["classification"] = await self._classify_image(
                    image_data, image_url, top_k=3
                )

            if "objects" in analysis_types:
                analysis_results["objects"] = await self._detect_objects(image_data, image_url)

            if "text" in analysis_types:
                analysis_results["text"] = await self._extract_text(image_data, image_url)

            if "faces" in analysis_types:
                analysis_results["faces"] = await self._recognize_faces(image_data, image_url)

            if "colors" in analysis_types:
                analysis_results["colors"] = await self._analyze_image_colors(image)

            if "quality" in analysis_types:
                analysis_results["quality"] = await self._assess_image_quality(image)

            comprehensive_analysis = {
                "results": analysis_results,
                "image_info": {"size": image.size, "mode": image.mode, "format": image.format},
                "processing_time": datetime.now(),
            }

            return comprehensive_analysis

        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return {"error": str(e)}

    async def _load_image(
        self, image_data: str | None = None, image_url: str | None = None
    ) -> Image.Image | None:
        """
        Load image from data or URL
        """
        try:
            if image_data:
                # Decode base64 image data
                image_bytes = base64.b64decode(image_data)
                image = Image.open(io.BytesIO(image_bytes))
            elif image_url:
                # Download from URL (simplified - would need requests)
                # For now, assume local file
                image = Image.open(image_url)
            else:
                return None

            # Validate image size
            image_size = len(image.tobytes())
            if image_size > self.image_config["max_image_size"]:
                raise ValueError(f"Image size {image_size} exceeds maximum allowed size")

            return image

        except Exception as e:
            logger.error(f"Image loading failed: {e}")
            return None

    async def _analyze_image_colors(self, image: Image.Image) -> dict[str, Any]:
        """Analyze dominant colors in image"""
        try:
            # Convert to RGB
            image_rgb = image.convert("RGB")
            image_array = np.array(image_rgb)

            # Reshape for clustering
            pixels = image_array.reshape(-1, 3)

            # Use K-means to find dominant colors
            kmeans = KMeans(n_clusters=5, random_state=42)
            kmeans.fit(pixels)

            # Get dominant colors
            dominant_colors = kmeans.cluster_centers_.astype(int)

            color_analysis = {
                "dominant_colors": dominant_colors.tolist(),
                "color_clusters": len(dominant_colors),
            }

            return color_analysis
        except Exception as e:
            logger.error(f"Color analysis failed: {e}")
            return {}

    async def _assess_image_quality(self, image: Image.Image) -> dict[str, Any]:
        """Assess image quality metrics"""
        try:
            # Convert to grayscale for analysis
            gray_image = image.convert("L")
            image_array = np.array(gray_image)

            # Calculate basic quality metrics
            brightness = np.mean(image_array)
            contrast = np.std(image_array)
            sharpness = np.var(image_array)  # Simple sharpness measure

            quality_assessment = {
                "brightness": brightness,
                "contrast": contrast,
                "sharpness": sharpness,
                "overall_quality": (brightness / 255 + contrast / 128 + sharpness / 1000) / 3,
            }

            return quality_assessment
        except Exception as e:
            logger.error(f"Quality assessment failed: {e}")
            return {}

    # Background processing tasks
    async def _continuous_image_processing(self):
        """
        Continuous image processing from queue
        """
        try:
            while True:
                try:
                    # Process queued images
                    if self.image_state["processing_queue"]:
                        image_task = self.image_state["processing_queue"].popleft()
                        await self._process_image_task(image_task)

                except Exception as e:
                    logger.error(f"Image processing error: {e}")

                # Process every 2 seconds
                await asyncio.sleep(2)

        except asyncio.CancelledError:
            logger.info("Image processing cancelled")
            raise

    async def _continuous_model_maintenance(self):
        """
        Continuous model maintenance and updates
        """
        try:
            while True:
                try:
                    # Update models, clear cache, etc.
                    await self._update_model_cache()
                    await self._cleanup_old_embeddings()

                except Exception as e:
                    logger.error(f"Model maintenance error: {e}")

                # Maintain every hour
                await asyncio.sleep(3600)

        except asyncio.CancelledError:
            logger.info("Model maintenance cancelled")
            raise

    async def _continuous_embedding_updates(self):
        """
        Continuous embedding updates for new images
        """
        try:
            while True:
                try:
                    # Update embeddings for new images
                    await self._update_image_embeddings()

                except Exception as e:
                    logger.error(f"Embedding update error: {e}")

                # Update every 30 minutes
                await asyncio.sleep(1800)

        except asyncio.CancelledError:
            logger.info("Embedding updates cancelled")
            raise

    # Additional helper methods would continue here...

    async def _load_face_database(self):
        """Load face database"""
        try:
            # Implementation for loading face database
            pass
        except Exception as e:
            logger.error(f"Face database loading failed: {e}")

    async def _load_object_templates(self):
        """Load object templates"""
        try:
            # Implementation for loading object templates
            pass
        except Exception as e:
            logger.error(f"Object templates loading failed: {e}")

    async def _load_image_embeddings(self):
        """Load image embeddings"""
        try:
            # Implementation for loading image embeddings
            pass
        except Exception as e:
            logger.error(f"Image embeddings loading failed: {e}")

    async def _process_image_task(self, task: dict[str, Any]):
        """Process queued image task"""
        try:
            # Implementation for processing image task
            pass
        except Exception as e:
            logger.error(f"Image task processing failed: {e}")

    async def _update_model_cache(self):
        """Update model cache"""
        try:
            # Implementation for updating model cache
            pass
        except Exception as e:
            logger.error(f"Model cache update failed: {e}")

    async def _cleanup_old_embeddings(self):
        """Cleanup old embeddings"""
        try:
            # Implementation for cleaning up old embeddings
            pass
        except Exception as e:
            logger.error(f"Embedding cleanup failed: {e}")

    async def _update_image_embeddings(self):
        """Update image embeddings"""
        try:
            # Implementation for updating image embeddings
            pass
        except Exception as e:
            logger.error(f"Image embedding update failed: {e}")


# ========== TEST ==========
if __name__ == "__main__":

    async def test_image_processing_agent():
        # Initialize image processing agent
        agent = ImageProcessingAgent()
        await agent.start()

        # Test image classification
        # Note: Would need actual image data for real testing
        classification_message = AgentMessage(
            id="test_classification",
            from_agent="test",
            to_agent="image_processing_agent",
            content={
                "type": "classify_image",
                "image_url": "path/to/test/image.jpg",  # Would need real image
                "top_k": 3,
            },
            timestamp=datetime.now(),
        )

        print("Testing image processing agent...")
        async for response in agent.process_message(classification_message):
            print(f"Classification response: {response.content.get('type')}")
            classification = response.content.get("result", {}).get("classification")
            print(f"Classification result: {classification}")

        # Test object detection
        detection_message = AgentMessage(
            id="test_detection",
            from_agent="test",
            to_agent="image_processing_agent",
            content={
                "type": "detect_objects",
                "image_url": "path/to/test/image.jpg",  # Would need real image
                "confidence_threshold": 0.5,
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(detection_message):
            print(f"Detection response: {response.content.get('type')}")
            detections = response.content.get("result", {}).get("detections")
            print(f"Detection result: {detections}")

        # Stop agent
        await agent.stop()
        print("Image processing agent test completed")

    # Run test
    asyncio.run(test_image_processing_agent())
