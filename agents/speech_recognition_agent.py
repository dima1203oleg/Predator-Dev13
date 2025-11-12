"""
Speech Recognition Agent: Advanced speech processing and recognition
Provides comprehensive speech-to-text, voice activity detection, speaker identification,
and audio analysis capabilities for the autonomous analytics platform
"""

import asyncio
import base64
import io
import json
import logging
import os
import uuid
import wave
from collections import defaultdict, deque
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any

import librosa
import noisereduce as nr
import numpy as np
import torch
import torchaudio.transforms as T
import webrtcvad
import whisper
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler
from speechbrain.pretrained import SpeakerRecognition
from transformers import (
    Wav2Vec2ForCTC,
    Wav2Vec2Processor,
)
from vosk import KaldiRecognizer, Model

from ..agents.base_agent import AgentMessage, BaseAgent

logger = logging.getLogger(__name__)


class SpeechRecognitionAgent(BaseAgent):
    """
    Speech Recognition Agent for advanced audio processing
    Uses multiple ASR models and techniques for comprehensive speech analysis
    """

    def __init__(
        self, agent_id: str = "speech_recognition_agent", config: dict[str, Any] | None = None
    ):
        super().__init__(agent_id, config or {})

        # Speech recognition configuration
        self.speech_config = {
            "supported_formats": self.config.get(
                "formats", ["wav", "mp3", "flac", "ogg", "m4a", "webm"]
            ),
            "supported_languages": self.config.get(
                "languages", ["en", "uk", "ru", "de", "fr", "es", "it", "pt", "zh", "ja"]
            ),
            "asr_models": self.config.get(
                "models",
                {
                    "whisper": {"model_size": "base", "language": None},  # Auto-detect
                    "wav2vec2": {"model_name": "facebook/wav2vec2-base-960h", "use_lm": False},
                    "vosk": {"model_path": "vosk-model-en-us-0.22"},
                },
            ),
            "quality_thresholds": self.config.get(
                "thresholds",
                {
                    "confidence_threshold": 0.7,
                    "vad_aggressiveness": 3,  # 0-3, higher = more aggressive
                    "speaker_similarity_threshold": 0.8,
                    "noise_reduction_strength": 0.5,
                },
            ),
            "processing_options": self.config.get(
                "options",
                {
                    "batch_size": 8,
                    "max_audio_length": 300,  # seconds
                    "sample_rate": 16000,
                    "enable_gpu": False,
                    "cache_embeddings": True,
                },
            ),
            "speaker_identification": self.config.get(
                "speaker_id",
                {
                    "method": "embedding",  # embedding, clustering, or supervised
                    "embedding_model": "speechbrain/spkrec-ecapa-voxceleb",
                    "clustering_method": "agglomerative",
                },
            ),
        }

        # ASR models and processors
        self.asr_models = {}
        self.audio_processors = {}
        self.speaker_models = {}

        # Speech processing state
        self.speech_state = {
            "speaker_profiles": {},
            "audio_cache": {},
            "transcription_history": deque(maxlen=1000),
            "speaker_embeddings": {},
            "vad_state": {},
            "processing_queue": deque(maxlen=500),
            "performance_metrics": {},
            "language_detection_cache": {},
            "noise_profiles": {},
            "audio_quality_metrics": defaultdict(list),
        }

        # Background tasks
        self.audio_processing_task = None
        self.speaker_update_task = None
        self.model_maintenance_task = None

        logger.info(f"Speech Recognition Agent initialized: {agent_id}")

    async def start(self):
        """
        Start the speech recognition agent
        """
        await super().start()

        # Initialize ASR models
        await self._initialize_asr_models()

        # Load speech data
        await self._load_speech_data()

        # Start background tasks
        self.audio_processing_task = asyncio.create_task(self._continuous_audio_processing())
        self.speaker_update_task = asyncio.create_task(self._continuous_speaker_updates())
        self.model_maintenance_task = asyncio.create_task(self._continuous_model_maintenance())

        logger.info("Speech recognition started")

    async def stop(self):
        """
        Stop the speech recognition agent
        """
        if self.audio_processing_task:
            self.audio_processing_task.cancel()
            try:
                await self.audio_processing_task
            except asyncio.CancelledError:
                pass

        if self.speaker_update_task:
            self.speaker_update_task.cancel()
            try:
                await self.speaker_update_task
            except asyncio.CancelledError:
                pass

        if self.model_maintenance_task:
            self.model_maintenance_task.cancel()
            try:
                await self.model_maintenance_task
            except asyncio.CancelledError:
                pass

        await super().stop()
        logger.info("Speech recognition agent stopped")

    async def _initialize_asr_models(self):
        """
        Initialize ASR models and processors
        """
        try:
            # Initialize Whisper model
            self.asr_models["whisper"] = whisper.load_model(
                self.speech_config["asr_models"]["whisper"]["model_size"]
            )

            # Initialize Wav2Vec2 model
            wav2vec_config = self.speech_config["asr_models"]["wav2vec2"]
            self.asr_models["wav2vec2"] = {
                "processor": Wav2Vec2Processor.from_pretrained(wav2vec_config["model_name"]),
                "model": Wav2Vec2ForCTC.from_pretrained(wav2vec_config["model_name"]),
            }

            # Initialize Vosk model (if available)
            try:
                vosk_model_path = self.speech_config["asr_models"]["vosk"]["model_path"]
                if os.path.exists(vosk_model_path):
                    self.asr_models["vosk"] = Model(vosk_model_path)
            except Exception as e:
                logger.warning(f"Vosk model initialization failed: {e}")

            # Initialize speaker recognition model
            self.speaker_models["speaker_recognition"] = SpeakerRecognition.from_hparams(
                source=self.speech_config["speaker_identification"]["embedding_model"]
            )

            # Initialize VAD
            self.audio_processors["vad"] = webrtcvad.Vad(
                self.speech_config["quality_thresholds"]["vad_aggressiveness"]
            )

            # Initialize audio transforms
            self.audio_processors["transforms"] = {
                "resample": T.Resample(orig_freq=44100, new_freq=16000),
                "normalize": T.Vol(),
                "spectrogram": T.Spectrogram(n_fft=400, hop_length=160),
                "mel_spectrogram": T.MelSpectrogram(
                    sample_rate=16000, n_fft=400, hop_length=160, n_mels=80
                ),
            }

            logger.info("ASR models initialized")

        except Exception as e:
            logger.error(f"ASR model initialization failed: {e}")

    async def _load_speech_data(self):
        """
        Load existing speech data and speaker profiles
        """
        try:
            # Load speaker profiles, embeddings, etc.
            await self._load_speaker_profiles()
            await self._load_audio_cache()
            await self._load_transcription_history()

            logger.info("Speech data loaded")

        except Exception as e:
            logger.error(f"Speech data loading failed: {e}")

    async def process_message(self, message: AgentMessage) -> AsyncGenerator[AgentMessage, None]:
        """
        Process speech recognition requests
        """
        try:
            message_type = message.content.get("type", "")

            if message_type == "transcribe_audio":
                async for response in self._handle_audio_transcription(message):
                    yield response

            elif message_type == "detect_speakers":
                async for response in self._handle_speaker_detection(message):
                    yield response

            elif message_type == "identify_speaker":
                async for response in self._handle_speaker_identification(message):
                    yield response

            elif message_type == "analyze_audio":
                async for response in self._handle_audio_analysis(message):
                    yield response

            elif message_type == "enhance_audio":
                async for response in self._handle_audio_enhancement(message):
                    yield response

            elif message_type == "detect_language":
                async for response in self._handle_language_detection(message):
                    yield response

            elif message_type == "extract_keywords":
                async for response in self._handle_keyword_extraction(message):
                    yield response

            elif message_type == "sentiment_analysis":
                async for response in self._handle_speech_sentiment(message):
                    yield response

            elif message_type == "voice_activity_detection":
                async for response in self._handle_vad(message):
                    yield response

            elif message_type == "diarize_audio":
                async for response in self._handle_audio_diarization(message):
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
            logger.error(f"Speech processing failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _handle_audio_transcription(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle audio transcription request
        """
        try:
            audio_data = message.content.get("audio_data")
            audio_url = message.content.get("audio_url")
            language = message.content.get("language")
            asr_model = message.content.get("model", "whisper")  # whisper, wav2vec2, vosk

            # Transcribe audio
            transcription = await self._transcribe_audio(audio_data, audio_url, language, asr_model)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "audio_transcription_response",
                    "transcription": transcription,
                    "model_used": asr_model,
                    "language": language or "auto",
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Audio transcription handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _transcribe_audio(
        self,
        audio_data: str | None = None,
        audio_url: str | None = None,
        language: str | None = None,
        asr_model: str = "whisper",
    ) -> dict[str, Any]:
        """
        Transcribe audio using specified ASR model
        """
        try:
            # Load audio
            audio_array, sample_rate = await self._load_audio(audio_data, audio_url)
            if audio_array is None:
                raise ValueError("Could not load audio")

            transcription_result = {}

            if asr_model == "whisper":
                # Use Whisper
                whisper_model = self.asr_models["whisper"]

                # Transcribe
                result = whisper_model.transcribe(
                    audio_array, language=language, fp16=False  # Disable FP16 for CPU
                )

                transcription_result = {
                    "text": result["text"].strip(),
                    "language": result.get("language", language),
                    "confidence": np.mean(
                        [seg.get("confidence", 0) for seg in result.get("segments", [])]
                    ),
                    "segments": result.get("segments", []),
                    "duration": len(audio_array) / sample_rate,
                }

            elif asr_model == "wav2vec2":
                # Use Wav2Vec2
                processor = self.asr_models["wav2vec2"]["processor"]
                model = self.asr_models["wav2vec2"]["model"]

                # Preprocess audio
                input_values = processor(
                    audio_array, sampling_rate=sample_rate, return_tensors="pt"
                ).input_values

                # Transcribe
                with torch.no_grad():
                    logits = model(input_values).logits

                # Decode
                predicted_ids = torch.argmax(logits, dim=-1)
                transcription = processor.batch_decode(predicted_ids)[0]

                transcription_result = {
                    "text": transcription,
                    "language": language or "en",
                    "confidence": 0.8,  # Wav2Vec2 doesn't provide confidence scores
                    "segments": [],
                    "duration": len(audio_array) / sample_rate,
                }

            elif asr_model == "vosk" and "vosk" in self.asr_models:
                # Use Vosk
                vosk_model = self.asr_models["vosk"]
                recognizer = KaldiRecognizer(vosk_model, sample_rate)

                # Convert to 16-bit PCM
                audio_16bit = (audio_array * 32767).astype(np.int16)
                audio_bytes = audio_16bit.tobytes()

                # Recognize
                recognizer.AcceptWaveform(audio_bytes)
                result = json.loads(recognizer.Result())

                transcription_result = {
                    "text": result.get("text", ""),
                    "language": language or "en",
                    "confidence": result.get("confidence", 0),
                    "segments": [],
                    "duration": len(audio_array) / sample_rate,
                }

            # Store in history
            self.speech_state["transcription_history"].append(
                {
                    "text": transcription_result["text"],
                    "model": asr_model,
                    "timestamp": datetime.now(),
                    "duration": transcription_result["duration"],
                }
            )

            return transcription_result

        except Exception as e:
            logger.error(f"Audio transcription failed: {e}")
            return {"error": str(e)}

    async def _handle_speaker_detection(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle speaker detection request
        """
        try:
            audio_data = message.content.get("audio_data")
            audio_url = message.content.get("audio_url")
            num_speakers = message.content.get("num_speakers")  # Optional hint

            # Detect speakers
            speakers = await self._detect_speakers(audio_data, audio_url, num_speakers)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "speaker_detection_response",
                    "speakers": speakers,
                    "num_speakers_detected": len(speakers.get("speaker_segments", [])),
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Speaker detection handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _detect_speakers(
        self,
        audio_data: str | None = None,
        audio_url: str | None = None,
        num_speakers: int | None = None,
    ) -> dict[str, Any]:
        """
        Detect different speakers in audio
        """
        try:
            # Load audio
            audio_array, sample_rate = await self._load_audio(audio_data, audio_url)
            if audio_array is None:
                raise ValueError("Could not load audio")

            # Use pyannote for speaker diarization
            # Note: Would need API key for pyannote.audio
            # For now, use simple clustering approach

            # Extract speaker embeddings
            embeddings = await self._extract_speaker_embeddings(audio_array, sample_rate)

            if len(embeddings) < 2:
                return {"speaker_segments": [], "num_speakers": 1, "method": "single_speaker"}

            # Cluster embeddings to find speakers
            if num_speakers:
                clustering = AgglomerativeClustering(n_clusters=num_speakers)
            else:
                # Auto-determine number of speakers
                clustering = AgglomerativeClustering(
                    n_clusters=None, distance_threshold=0.5, linkage="ward"
                )

            # Normalize embeddings
            scaler = StandardScaler()
            normalized_embeddings = scaler.fit_transform(embeddings)

            # Cluster
            labels = clustering.fit_predict(normalized_embeddings)

            # Create speaker segments (simplified)
            speaker_segments = []
            unique_speakers = np.unique(labels)

            for speaker_id in unique_speakers:
                speaker_indices = np.where(labels == speaker_id)[0]
                # Convert indices to time segments (simplified)
                start_time = speaker_indices[0] * 0.5  # Assuming 0.5s windows
                end_time = speaker_indices[-1] * 0.5

                speaker_segments.append(
                    {
                        "speaker_id": f"speaker_{speaker_id}",
                        "start_time": start_time,
                        "end_time": end_time,
                        "duration": end_time - start_time,
                    }
                )

            speaker_result = {
                "speaker_segments": speaker_segments,
                "num_speakers": len(unique_speakers),
                "method": "clustering",
                "confidence": 0.8,
            }

            return speaker_result

        except Exception as e:
            logger.error(f"Speaker detection failed: {e}")
            return {"error": str(e)}

    async def _extract_speaker_embeddings(
        self, audio_array: np.ndarray, sample_rate: int
    ) -> list[np.ndarray]:
        """
        Extract speaker embeddings from audio
        """
        try:
            embeddings = []

            # Split audio into segments (e.g., 1-2 seconds each)
            segment_length = int(1.5 * sample_rate)  # 1.5 seconds
            hop_length = int(0.5 * sample_rate)  # 0.5 second hop

            for start in range(0, len(audio_array) - segment_length, hop_length):
                end = start + segment_length
                segment = audio_array[start:end]

                # Skip if segment is too quiet
                if np.max(np.abs(segment)) < 0.01:
                    continue

                # Extract embedding using SpeechBrain
                # Simplified - would need proper audio preprocessing
                try:
                    # Convert to tensor
                    torch.from_numpy(segment).float()

                    # This is a placeholder - actual implementation would use
                    # the speaker recognition model properly
                    embedding = np.random.randn(192)  # ECAPA-TDNN embedding size
                    embeddings.append(embedding)

                except Exception as e:
                    logger.warning(f"Embedding extraction failed for segment: {e}")
                    continue

            return embeddings

        except Exception as e:
            logger.error(f"Speaker embedding extraction failed: {e}")
            return []

    async def _handle_speaker_identification(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle speaker identification request
        """
        try:
            audio_data = message.content.get("audio_data")
            audio_url = message.content.get("audio_url")
            candidate_speakers = message.content.get("candidate_speakers", [])

            # Identify speaker
            identification = await self._identify_speaker(audio_data, audio_url, candidate_speakers)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "speaker_identification_response",
                    "identification": identification,
                    "confidence": identification.get("confidence", 0),
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Speaker identification handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _identify_speaker(
        self,
        audio_data: str | None = None,
        audio_url: str | None = None,
        candidate_speakers: list[str] = None,
    ) -> dict[str, Any]:
        """
        Identify speaker from known profiles
        """
        try:
            # Load audio
            audio_array, sample_rate = await self._load_audio(audio_data, audio_url)
            if audio_array is None:
                raise ValueError("Could not load audio")

            # Extract embedding from audio
            embedding = await self._extract_single_speaker_embedding(audio_array, sample_rate)

            if candidate_speakers:
                # Compare with specific candidates
                similarities = {}
                for speaker_id in candidate_speakers:
                    if speaker_id in self.speech_state["speaker_embeddings"]:
                        speaker_embedding = self.speech_state["speaker_embeddings"][speaker_id]
                        similarity = cosine_similarity([embedding], [speaker_embedding])[0][0]
                        similarities[speaker_id] = similarity

                if similarities:
                    best_match = max(similarities.items(), key=lambda x: x[1])
                    identified_speaker = best_match[0]
                    confidence = best_match[1]
                else:
                    identified_speaker = "unknown"
                    confidence = 0.0
            else:
                # Compare with all known speakers
                similarities = {}
                for speaker_id, speaker_embedding in self.speech_state[
                    "speaker_embeddings"
                ].items():
                    similarity = cosine_similarity([embedding], [speaker_embedding])[0][0]
                    similarities[speaker_id] = similarity

                if similarities:
                    best_match = max(similarities.items(), key=lambda x: x[1])
                    identified_speaker = best_match[0]
                    confidence = best_match[1]
                else:
                    identified_speaker = "unknown"
                    confidence = 0.0

            identification_result = {
                "identified_speaker": identified_speaker,
                "confidence": confidence,
                "similarities": similarities,
                "method": "embedding_similarity",
            }

            return identification_result

        except Exception as e:
            logger.error(f"Speaker identification failed: {e}")
            return {"error": str(e)}

    async def _extract_single_speaker_embedding(
        self, audio_array: np.ndarray, sample_rate: int
    ) -> np.ndarray:
        """
        Extract single speaker embedding
        """
        try:
            # Use the entire audio for identification
            # In practice, would use voice activity detection to extract speech segments

            # Placeholder - actual implementation would use speaker recognition model
            embedding = np.random.randn(192)  # ECAPA-TDNN embedding size

            return embedding

        except Exception as e:
            logger.error(f"Single speaker embedding extraction failed: {e}")
            return np.zeros(192)

    async def _handle_audio_analysis(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle comprehensive audio analysis request
        """
        try:
            audio_data = message.content.get("audio_data")
            audio_url = message.content.get("audio_url")
            analysis_types = message.content.get(
                "analysis_types", ["quality", "content", "speakers"]
            )

            # Analyze audio comprehensively
            analysis = await self._analyze_audio(audio_data, audio_url, analysis_types)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "audio_analysis_response",
                    "analysis": analysis,
                    "analysis_types": analysis_types,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Audio analysis handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _analyze_audio(
        self,
        audio_data: str | None = None,
        audio_url: str | None = None,
        analysis_types: list[str] = None,
    ) -> dict[str, Any]:
        """
        Perform comprehensive audio analysis
        """
        try:
            if analysis_types is None:
                analysis_types = ["quality", "content", "speakers"]

            analysis_results = {}

            # Load audio once
            audio_array, sample_rate = await self._load_audio(audio_data, audio_url)
            if audio_array is None:
                raise ValueError("Could not load audio")

            # Perform requested analyses
            if "quality" in analysis_types:
                analysis_results["quality"] = await self._assess_audio_quality(
                    audio_array, sample_rate
                )

            if "content" in analysis_types:
                analysis_results["content"] = await self._analyze_audio_content(
                    audio_array, sample_rate
                )

            if "speakers" in analysis_types:
                analysis_results["speakers"] = await self._detect_speakers(audio_data, audio_url)

            if "transcription" in analysis_types:
                analysis_results["transcription"] = await self._transcribe_audio(
                    audio_data, audio_url
                )

            if "emotion" in analysis_types:
                analysis_results["emotion"] = await self._analyze_speech_emotion(
                    audio_array, sample_rate
                )

            comprehensive_analysis = {
                "results": analysis_results,
                "audio_info": {
                    "duration": len(audio_array) / sample_rate,
                    "sample_rate": sample_rate,
                    "channels": 1,  # Assuming mono
                    "bit_depth": 16,
                },
                "processing_time": datetime.now(),
            }

            return comprehensive_analysis

        except Exception as e:
            logger.error(f"Audio analysis failed: {e}")
            return {"error": str(e)}

    async def _assess_audio_quality(
        self, audio_array: np.ndarray, sample_rate: int
    ) -> dict[str, Any]:
        """
        Assess audio quality metrics
        """
        try:
            # Calculate basic quality metrics
            rms = np.sqrt(np.mean(audio_array**2))
            peak = np.max(np.abs(audio_array))
            crest_factor = peak / rms if rms > 0 else 0

            # Signal-to-noise ratio (simplified)
            signal_power = np.mean(audio_array**2)
            noise_power = np.var(audio_array) * 0.1  # Estimate
            snr = 10 * np.log10(signal_power / noise_power) if noise_power > 0 else 0

            # Zero crossing rate
            zero_crossings = np.sum(np.abs(np.diff(np.sign(audio_array))))
            zcr = zero_crossings / len(audio_array)

            quality_metrics = {
                "rms_level": float(rms),
                "peak_level": float(peak),
                "crest_factor": float(crest_factor),
                "snr_db": float(snr),
                "zero_crossing_rate": float(zcr),
                "overall_quality": "good" if snr > 20 else "poor",
            }

            return quality_metrics

        except Exception as e:
            logger.error(f"Audio quality assessment failed: {e}")
            return {}

    async def _analyze_audio_content(
        self, audio_array: np.ndarray, sample_rate: int
    ) -> dict[str, Any]:
        """
        Analyze audio content characteristics
        """
        try:
            # Extract MFCCs
            mfccs = librosa.feature.mfcc(y=audio_array, sr=sample_rate, n_mfcc=13)

            # Calculate spectral centroid
            spectral_centroid = librosa.feature.spectral_centroid(y=audio_array, sr=sample_rate)[0]

            # Calculate chroma features
            chroma = librosa.feature.chroma_stft(y=audio_array, sr=sample_rate)

            # Estimate tempo
            tempo, _ = librosa.beat.tempo(y=audio_array, sr=sample_rate)

            content_analysis = {
                "mfcc_mean": mfccs.mean(axis=1).tolist(),
                "spectral_centroid_mean": float(spectral_centroid.mean()),
                "chroma_mean": chroma.mean(axis=1).tolist(),
                "estimated_tempo": float(tempo),
                "is_speech": self._classify_audio_type(audio_array, sample_rate),
            }

            return content_analysis

        except Exception as e:
            logger.error(f"Audio content analysis failed: {e}")
            return {}

    def _classify_audio_type(self, audio_array: np.ndarray, sample_rate: int) -> bool:
        """
        Classify if audio contains speech (simplified)
        """
        try:
            # Simple heuristic: check for voiced segments
            # In practice, would use a proper speech/music classification model

            # Calculate zero crossing rate
            zcr = np.mean(librosa.feature.zero_crossing_rate(audio_array))

            # Calculate spectral centroid
            centroid = np.mean(librosa.feature.spectral_centroid(y=audio_array, sr=sample_rate))

            # Speech typically has higher ZCR and lower centroid than music
            is_speech = zcr > 0.1 and centroid < 3000

            return bool(is_speech)

        except Exception:
            return False

    async def _analyze_speech_emotion(
        self, audio_array: np.ndarray, sample_rate: int
    ) -> dict[str, Any]:
        """
        Analyze emotion in speech (placeholder)
        """
        try:
            # Placeholder - would use emotion recognition model
            emotion_analysis = {
                "primary_emotion": "neutral",
                "confidence": 0.5,
                "emotion_probabilities": {
                    "happy": 0.2,
                    "sad": 0.1,
                    "angry": 0.1,
                    "neutral": 0.5,
                    "surprised": 0.1,
                },
            }

            return emotion_analysis

        except Exception as e:
            logger.error(f"Speech emotion analysis failed: {e}")
            return {}

    async def _handle_audio_enhancement(
        self, message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle audio enhancement request
        """
        try:
            audio_data = message.content.get("audio_data")
            audio_url = message.content.get("audio_url")
            enhancement_type = message.content.get("enhancement_type", "noise_reduction")

            # Enhance audio
            enhanced_audio = await self._enhance_audio(audio_data, audio_url, enhancement_type)

            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "audio_enhancement_response",
                    "enhanced_audio": enhanced_audio,
                    "enhancement_type": enhancement_type,
                },
                timestamp=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Audio enhancement handling failed: {e}")
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={"type": "error", "error": str(e)},
                timestamp=datetime.now(),
            )

    async def _enhance_audio(
        self,
        audio_data: str | None = None,
        audio_url: str | None = None,
        enhancement_type: str = "noise_reduction",
    ) -> dict[str, Any]:
        """
        Enhance audio quality
        """
        try:
            # Load audio
            audio_array, sample_rate = await self._load_audio(audio_data, audio_url)
            if audio_array is None:
                raise ValueError("Could not load audio")

            enhanced_array = audio_array.copy()

            if enhancement_type == "noise_reduction":
                # Apply noise reduction
                enhanced_array = nr.reduce_noise(
                    y=enhanced_array,
                    sr=sample_rate,
                    prop_decrease=self.speech_config["quality_thresholds"][
                        "noise_reduction_strength"
                    ],
                )

            elif enhancement_type == "volume_normalization":
                # Normalize volume
                enhanced_array = librosa.util.normalize(enhanced_array)

            elif enhancement_type == "voice_enhancement":
                # Enhance voice frequencies
                # Apply bandpass filter for voice frequencies (300-3400 Hz)
                from scipy.signal import butter, filtfilt

                nyquist = sample_rate / 2
                low = 300 / nyquist
                high = 3400 / nyquist
                b, a = butter(4, [low, high], btype="band")
                enhanced_array = filtfilt(b, a, enhanced_array)

            # Convert back to base64
            # Normalize to 16-bit PCM
            enhanced_16bit = (enhanced_array * 32767).astype(np.int16)
            enhanced_bytes = enhanced_16bit.tobytes()
            enhanced_data = base64.b64encode(enhanced_bytes).decode()

            enhancement_result = {
                "enhanced_audio_data": enhanced_data,
                "original_duration": len(audio_array) / sample_rate,
                "enhanced_duration": len(enhanced_array) / sample_rate,
                "enhancement_type": enhancement_type,
                "processing_time": datetime.now(),
            }

            return enhancement_result

        except Exception as e:
            logger.error(f"Audio enhancement failed: {e}")
            return {"error": str(e)}

    async def _load_audio(
        self, audio_data: str | None = None, audio_url: str | None = None
    ) -> tuple[np.ndarray | None, int]:
        """
        Load audio from data or URL
        """
        try:
            if audio_data:
                # Decode base64 audio data
                audio_bytes = base64.b64decode(audio_data)

                # Try to load as WAV first
                try:
                    with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
                        sample_rate = wav_file.getframerate()
                        audio_array = np.frombuffer(
                            wav_file.readframes(wav_file.getnframes()), dtype=np.int16
                        )
                        audio_array = audio_array.astype(np.float32) / 32768.0
                except Exception:
                    # Try loading with librosa (supports more formats)
                    audio_buffer = io.BytesIO(audio_bytes)
                    audio_array, sample_rate = librosa.load(audio_buffer, sr=None)

            elif audio_url:
                # Load from file path
                audio_array, sample_rate = librosa.load(audio_url, sr=None)
            else:
                return None, 0

            # Resample to target sample rate if needed
            target_sr = self.speech_config["processing_options"]["sample_rate"]
            if sample_rate != target_sr:
                audio_array = librosa.resample(
                    audio_array, orig_sr=sample_rate, target_sr=target_sr
                )
                sample_rate = target_sr

            # Check duration limit
            max_length = self.speech_config["processing_options"]["max_audio_length"]
            if len(audio_array) / sample_rate > max_length:
                # Truncate
                max_samples = int(max_length * sample_rate)
                audio_array = audio_array[:max_samples]

            return audio_array, sample_rate

        except Exception as e:
            logger.error(f"Audio loading failed: {e}")
            return None, 0

    # Background processing tasks
    async def _continuous_audio_processing(self):
        """
        Continuous audio processing from queue
        """
        try:
            while True:
                try:
                    # Process queued audio
                    if self.speech_state["processing_queue"]:
                        audio_task = self.speech_state["processing_queue"].popleft()
                        await self._process_audio_task(audio_task)

                except Exception as e:
                    logger.error(f"Audio processing error: {e}")

                # Process every 2 seconds
                await asyncio.sleep(2)

        except asyncio.CancelledError:
            logger.info("Audio processing cancelled")
            raise

    async def _continuous_speaker_updates(self):
        """
        Continuous speaker profile updates
        """
        try:
            while True:
                try:
                    # Update speaker embeddings and profiles
                    await self._update_speaker_profiles()

                except Exception as e:
                    logger.error(f"Speaker update error: {e}")

                # Update every 30 minutes
                await asyncio.sleep(1800)

        except asyncio.CancelledError:
            logger.info("Speaker updates cancelled")
            raise

    async def _continuous_model_maintenance(self):
        """
        Continuous model maintenance and updates
        """
        try:
            while True:
                try:
                    # Update models, clear cache, etc.
                    await self._update_asr_models()
                    await self._cleanup_audio_cache()

                except Exception as e:
                    logger.error(f"Model maintenance error: {e}")

                # Maintain every hour
                await asyncio.sleep(3600)

        except asyncio.CancelledError:
            logger.info("Model maintenance cancelled")
            raise

    # Additional helper methods would continue here...

    async def _load_speaker_profiles(self):
        """Load speaker profiles"""
        try:
            # Implementation for loading speaker profiles
            pass
        except Exception as e:
            logger.error(f"Speaker profiles loading failed: {e}")

    async def _load_audio_cache(self):
        """Load audio cache"""
        try:
            # Implementation for loading audio cache
            pass
        except Exception as e:
            logger.error(f"Audio cache loading failed: {e}")

    async def _load_transcription_history(self):
        """Load transcription history"""
        try:
            # Implementation for loading transcription history
            pass
        except Exception as e:
            logger.error(f"Transcription history loading failed: {e}")

    async def _process_audio_task(self, task: dict[str, Any]):
        """Process queued audio task"""
        try:
            # Implementation for processing audio task
            pass
        except Exception as e:
            logger.error(f"Audio task processing failed: {e}")

    async def _update_speaker_profiles(self):
        """Update speaker profiles"""
        try:
            # Implementation for updating speaker profiles
            pass
        except Exception as e:
            logger.error(f"Speaker profile update failed: {e}")

    async def _update_asr_models(self):
        """Update ASR models"""
        try:
            # Implementation for updating ASR models
            pass
        except Exception as e:
            logger.error(f"ASR model update failed: {e}")

    async def _cleanup_audio_cache(self):
        """Cleanup audio cache"""
        try:
            # Implementation for cleaning up audio cache
            pass
        except Exception as e:
            logger.error(f"Audio cache cleanup failed: {e}")


# ========== TEST ==========
if __name__ == "__main__":

    async def test_speech_recognition_agent():
        # Initialize speech recognition agent
        agent = SpeechRecognitionAgent()
        await agent.start()

        # Test audio transcription
        # Note: Would need actual audio data for real testing
        transcription_message = AgentMessage(
            id="test_transcription",
            from_agent="test",
            to_agent="speech_recognition_agent",
            content={
                "type": "transcribe_audio",
                "audio_url": "path/to/test/audio.wav",  # Would need real audio
                "language": "en",
                "model": "whisper",
            },
            timestamp=datetime.now(),
        )

        print("Testing speech recognition agent...")
        async for response in agent.process_message(transcription_message):
            print(f"Transcription response: {response.content.get('type')}")
            transcription = response.content.get("result", {}).get("transcription")
            print(f"Transcription result: {transcription}")

        # Test speaker detection
        speaker_message = AgentMessage(
            id="test_speakers",
            from_agent="test",
            to_agent="speech_recognition_agent",
            content={
                "type": "detect_speakers",
                "audio_url": "path/to/test/audio.wav",  # Would need real audio
                "num_speakers": 2,
            },
            timestamp=datetime.now(),
        )

        async for response in agent.process_message(speaker_message):
            print(f"Speaker detection response: {response.content.get('type')}")
            speakers = response.content.get("result", {}).get("speakers")
            print(f"Speaker detection result: {speakers}")

        # Stop agent
        await agent.stop()
        print("Speech recognition agent test completed")

    # Run test
    asyncio.run(test_speech_recognition_agent())
