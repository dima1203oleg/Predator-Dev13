"""
Audio Processing: Noise Reduction and Preprocessing
"""

import logging
from typing import Any

import librosa
import noisereduce as nr
import numpy as np
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range, normalize

logger = logging.getLogger(__name__)


class AudioProcessor:
    """
    Audio preprocessing and noise reduction
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        noise_reduce: bool = True,
        normalize_audio: bool = True,
        compress_dynamic: bool = False,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.noise_reduce = noise_reduce
        self.normalize_audio = normalize_audio
        self.compress_dynamic = compress_dynamic

        logger.info("Audio processor initialized")

    def preprocess_audio(
        self, audio_path: str, output_path: str | None = None
    ) -> dict[str, Any]:
        """
        Preprocess audio file

        Args:
            audio_path: Input audio file path
            output_path: Output file path (optional)

        Returns:
            Processing results with metadata
        """
        try:
            if not output_path:
                output_path = audio_path.replace(".wav", "_processed.wav")

            # Load audio
            audio = AudioSegment.from_file(audio_path)

            # Convert to mono if needed
            if audio.channels > 1 and self.channels == 1:
                audio = audio.set_channels(1)

            # Resample if needed
            if audio.frame_rate != self.sample_rate:
                audio = audio.set_frame_rate(self.sample_rate)

            # Apply processing
            if self.noise_reduce:
                audio = self._reduce_noise(audio)

            if self.normalize_audio:
                audio = normalize(audio)

            if self.compress_dynamic:
                audio = compress_dynamic_range(audio)

            # Save processed audio
            audio.export(output_path, format="wav")

            # Get audio stats
            samples = np.array(audio.get_array_of_samples())
            duration = len(audio) / 1000.0

            # Calculate RMS and peak levels
            rms = np.sqrt(np.mean(samples**2))
            peak = np.max(np.abs(samples))

            result = {
                "input_path": audio_path,
                "output_path": output_path,
                "duration": duration,
                "sample_rate": audio.frame_rate,
                "channels": audio.channels,
                "rms_level": float(rms),
                "peak_level": float(peak),
                "processing_applied": {
                    "noise_reduction": self.noise_reduce,
                    "normalization": self.normalize_audio,
                    "compression": self.compress_dynamic,
                },
            }

            logger.info(f"Audio preprocessing completed: {output_path}")
            return result

        except Exception as e:
            logger.error(f"Audio preprocessing failed: {e}")
            return {"error": str(e), "input_path": audio_path}

    def _reduce_noise(self, audio: AudioSegment, noise_duration: float = 0.5) -> AudioSegment:
        """
        Apply noise reduction using noisereduce

        Args:
            audio: Audio segment
            noise_duration: Duration of noise sample (seconds)

        Returns:
            Noise-reduced audio
        """
        try:
            # Convert to numpy array
            samples = np.array(audio.get_array_of_samples())

            # Get noise profile from beginning of audio
            noise_samples = int(noise_duration * audio.frame_rate)
            noise_profile = samples[:noise_samples]

            # Apply noise reduction
            reduced_samples = nr.reduce_noise(
                y=samples.astype(np.float32),
                sr=audio.frame_rate,
                y_noise=noise_profile.astype(np.float32),
                stationary=True,
            )

            # Convert back to AudioSegment
            reduced_audio = AudioSegment(
                reduced_samples.astype(np.int16).tobytes(),
                frame_rate=audio.frame_rate,
                sample_width=2,
                channels=audio.channels,
            )

            return reduced_audio

        except Exception as e:
            logger.warning(f"Noise reduction failed: {e}")
            return audio

    def extract_features(self, audio_path: str) -> dict[str, Any]:
        """
        Extract audio features for analysis

        Args:
            audio_path: Audio file path

        Returns:
            Audio features
        """
        try:
            # Load audio with librosa
            y, sr = librosa.load(audio_path, sr=self.sample_rate)

            # Extract features
            features = {
                "duration": librosa.get_duration(y=y, sr=sr),
                "rms": float(librosa.feature.rms(y=y).mean()),
                "zero_crossing_rate": float(librosa.feature.zero_crossing_rate(y).mean()),
                "spectral_centroid": float(librosa.feature.spectral_centroid(y=y, sr=sr).mean()),
                "spectral_bandwidth": float(librosa.feature.spectral_bandwidth(y=y, sr=sr).mean()),
                "chroma_stft": librosa.feature.chroma_stft(y=y, sr=sr).mean(axis=1).tolist(),
                "mfcc": librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13).mean(axis=1).tolist(),
            }

            # Voice activity detection (simple threshold)
            rms_threshold = 0.01
            voice_frames = np.sum(librosa.feature.rms(y=y) > rms_threshold)
            total_frames = len(librosa.feature.rms(y=y)[0])
            features["voice_activity_ratio"] = float(voice_frames / total_frames)

            return features

        except Exception as e:
            logger.error(f"Feature extraction failed: {e}")
            return {"error": str(e)}

    def detect_silence(
        self, audio_path: str, threshold: float = -40.0, min_silence_len: float = 0.5
    ) -> list[tuple[float, float]]:
        """
        Detect silent segments in audio

        Args:
            audio_path: Audio file path
            threshold: Silence threshold in dBFS
            min_silence_len: Minimum silence length in seconds

        Returns:
            List of (start, end) silence segments
        """
        try:
            audio = AudioSegment.from_file(audio_path)

            # Detect silence
            silence_segments = []
            current_silence_start = None

            # Process in chunks
            chunk_size = 100  # ms
            for i in range(0, len(audio), chunk_size):
                chunk = audio[i : i + chunk_size]
                if chunk.dBFS < threshold:
                    if current_silence_start is None:
                        current_silence_start = i / 1000.0
                else:
                    if current_silence_start is not None:
                        silence_end = i / 1000.0
                        silence_duration = silence_end - current_silence_start
                        if silence_duration >= min_silence_len:
                            silence_segments.append((current_silence_start, silence_end))
                        current_silence_start = None

            # Handle silence at end
            if current_silence_start is not None:
                silence_end = len(audio) / 1000.0
                silence_duration = silence_end - current_silence_start
                if silence_duration >= min_silence_len:
                    silence_segments.append((current_silence_start, silence_end))

            return silence_segments

        except Exception as e:
            logger.error(f"Silence detection failed: {e}")
            return []

    def trim_silence(
        self,
        audio_path: str,
        output_path: str | None = None,
        threshold: float = -40.0,
        buffer: float = 0.1,
    ) -> dict[str, Any]:
        """
        Trim silence from audio

        Args:
            audio_path: Input audio file
            output_path: Output file path
            threshold: Silence threshold in dBFS
            buffer: Buffer around speech (seconds)

        Returns:
            Trimming results
        """
        try:
            if not output_path:
                output_path = audio_path.replace(".wav", "_trimmed.wav")

            audio = AudioSegment.from_file(audio_path)

            # Detect silence
            silence_segments = self.detect_silence(
                audio_path, threshold=threshold, min_silence_len=0.1
            )

            if not silence_segments:
                # No silence detected, copy file
                audio.export(output_path, format="wav")
                return {
                    "input_path": audio_path,
                    "output_path": output_path,
                    "trimmed_duration": len(audio) / 1000.0,
                    "original_duration": len(audio) / 1000.0,
                    "silence_removed": 0.0,
                }

            # Find speech segments (gaps between silence)
            speech_segments = []
            prev_end = 0

            for start, end in silence_segments:
                if start > prev_end:
                    speech_segments.append((prev_end, start))
                prev_end = end

            # Add final segment
            if prev_end < len(audio) / 1000.0:
                speech_segments.append((prev_end, len(audio) / 1000.0))

            # Trim with buffer
            trimmed_audio = AudioSegment.empty()
            buffer * 1000

            for start, end in speech_segments:
                start_ms = max(0, (start - buffer) * 1000)
                end_ms = min(len(audio), (end + buffer) * 1000)
                segment = audio[start_ms:end_ms]
                trimmed_audio += segment

            # Export
            trimmed_audio.export(output_path, format="wav")

            result = {
                "input_path": audio_path,
                "output_path": output_path,
                "original_duration": len(audio) / 1000.0,
                "trimmed_duration": len(trimmed_audio) / 1000.0,
                "silence_removed": (len(audio) - len(trimmed_audio)) / 1000.0,
                "speech_segments": len(speech_segments),
            }

            logger.info(f"Audio trimming completed: {result}")
            return result

        except Exception as e:
            logger.error(f"Audio trimming failed: {e}")
            return {"error": str(e), "input_path": audio_path}

    def convert_audio_format(
        self, input_path: str, output_path: str, format: str = "wav", **kwargs
    ) -> bool:
        """
        Convert audio to different format

        Args:
            input_path: Input file path
            output_path: Output file path
            format: Output format
            **kwargs: Additional format options

        Returns:
            Success status
        """
        try:
            audio = AudioSegment.from_file(input_path)
            audio.export(output_path, format=format, **kwargs)
            logger.info(f"Audio conversion completed: {input_path} -> {output_path}")
            return True

        except Exception as e:
            logger.error(f"Audio conversion failed: {e}")
            return False


class VoiceActivityDetector:
    """
    Voice Activity Detection (VAD)
    """

    def __init__(
        self,
        threshold: float = 0.3,
        min_speech_duration: float = 0.3,
        max_silence_duration: float = 0.5,
    ):
        self.threshold = threshold
        self.min_speech_duration = min_speech_duration
        self.max_silence_duration = max_silence_duration

        logger.info("Voice Activity Detector initialized")

    def detect_activity(self, audio_path: str) -> list[tuple[float, float]]:
        """
        Detect voice activity segments

        Args:
            audio_path: Audio file path

        Returns:
            List of (start, end) voice segments
        """
        try:
            # Load audio
            y, sr = librosa.load(audio_path, sr=16000)

            # Compute RMS energy
            rms = librosa.feature.rms(y=y, frame_length=512, hop_length=256)[0]

            # Normalize RMS
            rms = rms / np.max(rms)

            # Apply threshold
            voice_frames = rms > self.threshold

            # Find voice segments
            voice_segments = []
            start_idx = None

            for i, is_voice in enumerate(voice_frames):
                if is_voice and start_idx is None:
                    start_idx = i
                elif not is_voice and start_idx is not None:
                    end_idx = i
                    duration = (end_idx - start_idx) * 256 / sr

                    if duration >= self.min_speech_duration:
                        start_time = start_idx * 256 / sr
                        end_time = end_idx * 256 / sr
                        voice_segments.append((start_time, end_time))

                    start_idx = None

            # Handle segment at end
            if start_idx is not None:
                end_idx = len(voice_frames)
                duration = (end_idx - start_idx) * 256 / sr

                if duration >= self.min_speech_duration:
                    start_time = start_idx * 256 / sr
                    end_time = end_idx * 256 / sr
                    voice_segments.append((start_time, end_time))

            # Merge close segments
            merged_segments = []
            if voice_segments:
                current_start, current_end = voice_segments[0]

                for start, end in voice_segments[1:]:
                    if start - current_end <= self.max_silence_duration:
                        current_end = end
                    else:
                        merged_segments.append((current_start, current_end))
                        current_start, current_end = start, end

                merged_segments.append((current_start, current_end))

            return merged_segments

        except Exception as e:
            logger.error(f"VAD failed: {e}")
            return []


# ========== TEST ==========
if __name__ == "__main__":
    # Test audio processing
    processor = AudioProcessor()

    # Create test audio file (you would normally have a real file)
    test_audio_path = "/tmp/test_audio.wav"

    # Test features extraction (would work with real audio)
    print("Audio processor initialized")
    print("Note: Real testing requires audio files")
