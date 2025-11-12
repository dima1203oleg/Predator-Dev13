"""
Voice Interface: Speech-to-Text and Text-to-Speech
Whisper STT (Ukrainian) + pyttsx3 TTS
"""

import asyncio
import io
import logging
import os
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pyaudio
import pyttsx3
import torch
import whisper
from pydub import AudioSegment

logger = logging.getLogger(__name__)


class SpeechToText:
    """
    Speech-to-Text using Whisper with Ukrainian support
    """

    def __init__(self, model_size: str = "base", language: str = "uk", device: str = "cpu"):
        self.model_size = model_size
        self.language = language
        self.device = device

        # Load Whisper model
        self.model = None
        self._load_model()

        logger.info(f"STT initialized with {model_size} model on {device}")

    def _load_model(self):
        """Load Whisper model"""
        try:
            self.model = whisper.load_model(self.model_size, device=self.device)
            logger.info("Whisper model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

    async def transcribe_audio(self, audio_path: str, user_id: str = None) -> dict[str, Any]:
        """
        Transcribe audio file to text

        Args:
            audio_path: Path to audio file
            user_id: User ID for logging

        Returns:
            {
                "text": str,
                "confidence": float,
                "language": str,
                "duration": float,
                "processing_time": float
            }
        """
        try:
            import time

            start_time = time.time()

            # Load and preprocess audio
            audio = whisper.load_audio(audio_path)
            audio = whisper.pad_or_trim(audio)

            # Create mel spectrogram
            mel = whisper.log_mel_spectrogram(audio).to(self.model.device)

            # Detect language if not specified
            _, probs = self.model.detect_language(mel)
            detected_lang = max(probs, key=probs.get)

            # Decode audio
            options = whisper.DecodingOptions(
                language=self.language if self.language != "auto" else detected_lang,
                fp16=torch.cuda.is_available(),
            )

            result = whisper.decode(self.model, mel, options)

            processing_time = time.time() - start_time

            # Get audio duration
            audio_segment = AudioSegment.from_file(audio_path)
            duration = len(audio_segment) / 1000.0

            transcription = {
                "text": result.text.strip(),
                "confidence": float(result.avg_logprob),
                "language": detected_lang,
                "duration": duration,
                "processing_time": processing_time,
                "audio_path": audio_path,
                "user_id": user_id,
            }

            logger.info(
                f"Transcription completed: {len(result.text)} chars, "
                f"confidence: {result.avg_logprob:.2f}, "
                f"time: {processing_time:.2f}s"
            )

            return transcription

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {"text": "", "error": str(e), "audio_path": audio_path, "user_id": user_id}

    async def transcribe_stream(self, audio_stream: bytes, user_id: str = None) -> dict[str, Any]:
        """
        Transcribe audio stream (bytes)
        """
        try:
            # Save to temporary file
            temp_path = f"/tmp/stt_{user_id}_{datetime.now().timestamp()}.wav"

            # Convert bytes to audio file
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_stream))
            audio_segment.export(temp_path, format="wav")

            # Transcribe
            result = await self.transcribe_audio(temp_path, user_id)

            # Cleanup
            os.remove(temp_path)

            return result

        except Exception as e:
            logger.error(f"Stream transcription failed: {e}")
            return {"text": "", "error": str(e), "user_id": user_id}

    def record_audio(
        self, duration: int = 5, sample_rate: int = 16000, channels: int = 1
    ) -> bytes | None:
        """
        Record audio from microphone

        Args:
            duration: Recording duration in seconds
            sample_rate: Audio sample rate
            channels: Number of channels

        Returns:
            Audio data as bytes
        """
        try:
            audio = pyaudio.PyAudio()

            stream = audio.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                frames_per_buffer=1024,
            )

            logger.info(f"Recording audio for {duration} seconds...")
            frames = []

            for _ in range(0, int(sample_rate / 1024 * duration)):
                data = stream.read(1024)
                frames.append(data)

            stream.stop_stream()
            stream.close()
            audio.terminate()

            # Convert to bytes
            audio_data = b"".join(frames)
            logger.info(f"Recording completed: {len(audio_data)} bytes")

            return audio_data

        except Exception as e:
            logger.error(f"Audio recording failed: {e}")
            return None


class TextToSpeech:
    """
    Text-to-Speech using pyttsx3 with Ukrainian support
    """

    def __init__(self, voice: str = "ukrainian", rate: int = 180, volume: float = 0.8):
        self.voice = voice
        self.rate = rate
        self.volume = volume

        # Initialize TTS engine
        self.engine = pyttsx3.init()
        self._configure_engine()

        logger.info(f"TTS initialized with {voice} voice")

    def _configure_engine(self):
        """Configure TTS engine"""
        try:
            # Set voice
            voices = self.engine.getProperty("voices")
            ukrainian_voice = None

            for voice in voices:
                if "ukrainian" in voice.name.lower() or "ukr" in voice.name.lower():
                    ukrainian_voice = voice
                    break

            if ukrainian_voice:
                self.engine.setProperty("voice", ukrainian_voice.id)
            else:
                logger.warning("Ukrainian voice not found, using default")

            # Set rate and volume
            self.engine.setProperty("rate", self.rate)
            self.engine.setProperty("volume", self.volume)

        except Exception as e:
            logger.warning(f"TTS configuration failed: {e}")

    async def synthesize_speech(
        self, text: str, user_id: str = None, output_path: str | None = None
    ) -> dict[str, Any]:
        """
        Convert text to speech

        Args:
            text: Text to synthesize
            user_id: User ID for logging
            output_path: Optional output file path

        Returns:
            {
                "audio_path": str,
                "duration": float,
                "processing_time": float,
                "text": str
            }
        """
        try:
            import time

            start_time = time.time()

            # Generate output path if not provided
            if not output_path:
                output_path = f"/tmp/tts_{user_id}_{datetime.now().timestamp()}.wav"

            # Synthesize speech
            self.engine.save_to_file(text, output_path)
            self.engine.runAndWait()

            processing_time = time.time() - start_time

            # Get audio duration
            if os.path.exists(output_path):
                audio_segment = AudioSegment.from_file(output_path)
                duration = len(audio_segment) / 1000.0
            else:
                duration = 0.0

            result = {
                "audio_path": output_path,
                "duration": duration,
                "processing_time": processing_time,
                "text": text,
                "user_id": user_id,
            }

            logger.info(
                f"TTS completed: {len(text)} chars, "
                f"duration: {duration:.2f}s, "
                f"time: {processing_time:.2f}s"
            )

            return result

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return {"text": text, "error": str(e), "user_id": user_id}

    def speak_text(self, text: str) -> bool:
        """
        Speak text directly (blocking)

        Args:
            text: Text to speak

        Returns:
            Success status
        """
        try:
            self.engine.say(text)
            self.engine.runAndWait()
            return True

        except Exception as e:
            logger.error(f"Direct speech failed: {e}")
            return False

    def get_audio_bytes(self, text: str) -> bytes | None:
        """
        Get synthesized speech as bytes

        Args:
            text: Text to synthesize

        Returns:
            Audio data as bytes
        """
        try:
            # Synthesize to temporary file
            temp_path = f"/tmp/tts_temp_{datetime.now().timestamp()}.wav"
            self.engine.save_to_file(text, temp_path)
            self.engine.runAndWait()

            # Read file as bytes
            with open(temp_path, "rb") as f:
                audio_bytes = f.read()

            # Cleanup
            os.remove(temp_path)

            return audio_bytes

        except Exception as e:
            logger.error(f"Audio bytes generation failed: {e}")
            return None


class VoiceInterface:
    """
    Complete voice interface combining STT and TTS
    """

    def __init__(self, stt_model: str = "base", tts_voice: str = "ukrainian"):
        self.stt = SpeechToText(model_size=stt_model, language="uk")
        self.tts = TextToSpeech(voice=tts_voice)

        logger.info("Voice interface initialized")

    async def process_voice_query(
        self,
        audio_data: bytes,
        user_id: str,
        response_callback: Callable[[str], str] | None = None,
    ) -> dict[str, Any]:
        """
        Process voice query: STT -> Text Processing -> TTS Response

        Args:
            audio_data: Audio bytes from user
            user_id: User ID
            response_callback: Function to generate text response

        Returns:
            Complete voice interaction result
        """
        try:
            # Step 1: Speech-to-Text
            logger.info(f"Processing voice query for user {user_id}")
            transcription = await self.stt.transcribe_stream(audio_data, user_id)

            if not transcription.get("text"):
                return {"error": "Speech recognition failed"}

            query_text = transcription["text"]
            logger.info(f"Recognized: {query_text}")

            # Step 2: Generate response (using callback or default)
            if response_callback:
                response_text = response_callback(query_text)
            else:
                response_text = f"Ви сказали: {query_text}"

            # Step 3: Text-to-Speech
            tts_result = await self.tts.synthesize_speech(response_text, user_id=user_id)

            result = {
                "query": {
                    "text": query_text,
                    "audio_duration": transcription.get("duration", 0),
                    "confidence": transcription.get("confidence", 0),
                },
                "response": {
                    "text": response_text,
                    "audio_path": tts_result.get("audio_path"),
                    "audio_duration": tts_result.get("duration", 0),
                },
                "processing_times": {
                    "stt": transcription.get("processing_time", 0),
                    "tts": tts_result.get("processing_time", 0),
                },
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            }

            logger.info(f"Voice interaction completed for user {user_id}")
            return result

        except Exception as e:
            logger.error(f"Voice processing failed: {e}")
            return {"error": str(e), "user_id": user_id}

    async def voice_chat_loop(
        self, user_id: str, response_callback: Callable[[str], str], max_turns: int = 10
    ):
        """
        Continuous voice chat loop
        """
        logger.info(f"Starting voice chat for user {user_id}")

        for turn in range(max_turns):
            try:
                # Record audio
                audio_data = self.stt.record_audio(duration=5)

                if not audio_data:
                    logger.warning("No audio recorded")
                    continue

                # Process interaction
                result = await self.process_voice_query(audio_data, user_id, response_callback)

                if "error" in result:
                    logger.error(f"Interaction error: {result['error']}")
                    break

                # Play response
                if result["response"].get("audio_path"):
                    # In a real implementation, you'd stream the audio
                    logger.info(f"Response ready: {result['response']['text'][:50]}...")

                # Check for exit commands
                query = result["query"]["text"].lower()
                if any(word in query for word in ["вихід", "exit", "quit", "стоп"]):
                    logger.info(f"Exit command detected for user {user_id}")
                    break

            except KeyboardInterrupt:
                logger.info(f"Voice chat interrupted for user {user_id}")
                break
            except Exception as e:
                logger.error(f"Voice chat error: {e}")
                break

        logger.info(f"Voice chat ended for user {user_id}")


# ========== TEST ==========
if __name__ == "__main__":

    async def test_voice():
        # Initialize voice interface
        voice = VoiceInterface()

        # Test TTS
        print("Testing TTS...")
        tts_result = await voice.tts.synthesize_speech("Привіт, це тест голосу!")
        print(f"TTS result: {tts_result}")

        # Test STT with recording
        print("Testing STT (say something)...")
        audio_data = voice.stt.record_audio(duration=3)

        if audio_data:
            transcription = await voice.stt.transcribe_stream(audio_data, "test_user")
            print(f"Transcription: {transcription}")

        print("Voice test completed")

    # Run test
    asyncio.run(test_voice())
