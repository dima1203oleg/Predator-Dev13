"""
Voice Agent: Integration with MAS system
"""
import os
import logging
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator
from pathlib import Path
import asyncio
import json
from datetime import datetime
import uuid

from .voice_interface import VoiceInterface, SpeechToText, TextToSpeech
from .audio_processing import AudioProcessor, VoiceActivityDetector
from ..agents.base_agent import BaseAgent, AgentState, AgentMessage
from ..api.database import get_db_session
from ..api.models import VoiceInteraction, User

logger = logging.getLogger(__name__)


class VoiceAgent(BaseAgent):
    """
    Voice Agent for MAS system integration
    Handles voice interactions and coordinates with other agents
    """
    
    def __init__(
        self,
        agent_id: str = "voice_agent",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(agent_id, config or {})
        
        # Voice components
        self.voice_interface = VoiceInterface()
        self.audio_processor = AudioProcessor()
        self.vad = VoiceActivityDetector()
        
        # Voice settings
        self.max_interaction_time = self.config.get("max_interaction_time", 300)  # 5 minutes
        self.auto_silence_timeout = self.config.get("auto_silence_timeout", 30)  # 30 seconds
        self.language = self.config.get("language", "uk")
        
        # Interaction state
        self.current_interaction = None
        self.interaction_start_time = None
        
        logger.info(f"Voice Agent initialized: {agent_id}")
    
    async def process_message(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Process incoming messages and handle voice interactions
        """
        try:
            message_type = message.content.get("type", "")
            user_id = message.content.get("user_id", "")
            
            if message_type == "voice_query":
                # Handle voice query
                async for response in self._handle_voice_query(message):
                    yield response
                    
            elif message_type == "start_voice_session":
                # Start voice interaction session
                async for response in self._start_voice_session(message):
                    yield response
                    
            elif message_type == "end_voice_session":
                # End voice session
                async for response in self._end_voice_session(message):
                    yield response
                    
            elif message_type == "voice_command":
                # Handle voice commands
                async for response in self._handle_voice_command(message):
                    yield response
                    
            else:
                # Unknown message type
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": f"Unknown message type: {message_type}",
                        "original_message": message.content
                    },
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            logger.error(f"Voice agent message processing failed: {e}")
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
    
    async def _handle_voice_query(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle voice query processing
        """
        try:
            user_id = message.content.get("user_id", "")
            audio_data = message.content.get("audio_data", b"")
            
            if not audio_data:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "No audio data provided"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Process audio
            processed_audio = await self._preprocess_audio(audio_data, user_id)
            
            if not processed_audio:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Audio preprocessing failed"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Transcribe audio
            transcription = await self.voice_interface.stt.transcribe_stream(
                processed_audio,
                user_id
            )
            
            if not transcription.get("text"):
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "voice_response",
                        "status": "no_speech_detected",
                        "user_id": user_id
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Generate response using MAS system
            response_text = await self._generate_response(
                transcription["text"],
                user_id
            )
            
            # Synthesize speech
            tts_result = await self.voice_interface.tts.synthesize_speech(
                response_text,
                user_id=user_id
            )
            
            # Save interaction to database
            await self._save_interaction(
                user_id,
                transcription,
                response_text,
                tts_result
            )
            
            # Return response
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "voice_response",
                    "user_id": user_id,
                    "query": {
                        "text": transcription["text"],
                        "confidence": transcription.get("confidence", 0),
                        "duration": transcription.get("duration", 0)
                    },
                    "response": {
                        "text": response_text,
                        "audio_path": tts_result.get("audio_path"),
                        "duration": tts_result.get("duration", 0)
                    },
                    "processing_times": {
                        "stt": transcription.get("processing_time", 0),
                        "tts": tts_result.get("processing_time", 0)
                    }
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Voice query handling failed: {e}")
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
    
    async def _preprocess_audio(
        self,
        audio_data: bytes,
        user_id: str
    ) -> Optional[bytes]:
        """
        Preprocess audio data
        """
        try:
            # Save to temporary file
            temp_input = f"/tmp/voice_input_{user_id}_{datetime.now().timestamp()}.wav"
            temp_output = f"/tmp/voice_processed_{user_id}_{datetime.now().timestamp()}.wav"
            
            # Write audio data
            with open(temp_input, "wb") as f:
                f.write(audio_data)
            
            # Process audio
            result = self.audio_processor.preprocess_audio(temp_input, temp_output)
            
            if "error" in result:
                logger.error(f"Audio preprocessing error: {result['error']}")
                return None
            
            # Read processed audio
            with open(temp_output, "rb") as f:
                processed_data = f.read()
            
            # Cleanup
            os.remove(temp_input)
            os.remove(temp_output)
            
            return processed_data
            
        except Exception as e:
            logger.error(f"Audio preprocessing failed: {e}")
            return None
    
    async def _generate_response(
        self,
        query_text: str,
        user_id: str
    ) -> str:
        """
        Generate response using MAS system
        """
        try:
            # Route to appropriate agent based on query content
            if any(word in query_text.lower() for word in ["аналіз", "analysis", "дані", "data"]):
                # Route to analytics agent
                response = await self._route_to_analytics_agent(query_text, user_id)
                
            elif any(word in query_text.lower() for word in ["пошук", "search", "знайти", "find"]):
                # Route to search agent
                response = await self._route_to_search_agent(query_text, user_id)
                
            elif any(word in query_text.lower() for word in ["звіт", "report", "результат"]):
                # Route to reporting agent
                response = await self._route_to_reporting_agent(query_text, user_id)
                
            else:
                # General query - route to arbiter
                response = await self._route_to_arbiter_agent(query_text, user_id)
            
            return response or "Вибачте, я не зрозумів ваш запит. Спробуйте перефразувати."
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return "Сталася помилка при обробці запиту."
    
    async def _route_to_analytics_agent(
        self,
        query: str,
        user_id: str
    ) -> Optional[str]:
        """
        Route query to analytics agent
        """
        try:
            # Create message for analytics agent
            message = AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent="miner_agent",  # Analytics/mining agent
                content={
                    "type": "voice_analytics_query",
                    "query": query,
                    "user_id": user_id,
                    "voice_interface": True
                },
                timestamp=datetime.now()
            )
            
            # Send to message queue (would be implemented in full system)
            # For now, return mock response
            return f"Аналізую дані за запитом: {query}"
            
        except Exception as e:
            logger.error(f"Analytics routing failed: {e}")
            return None
    
    async def _route_to_search_agent(
        self,
        query: str,
        user_id: str
    ) -> Optional[str]:
        """
        Route query to search agent
        """
        try:
            message = AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent="retriever_agent",
                content={
                    "type": "voice_search_query",
                    "query": query,
                    "user_id": user_id,
                    "voice_interface": True
                },
                timestamp=datetime.now()
            )
            
            return f"Шукаю інформацію за запитом: {query}"
            
        except Exception as e:
            logger.error(f"Search routing failed: {e}")
            return None
    
    async def _route_to_reporting_agent(
        self,
        query: str,
        user_id: str
    ) -> Optional[str]:
        """
        Route query to reporting agent
        """
        try:
            message = AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent="reporting_agent",
                content={
                    "type": "voice_report_query",
                    "query": query,
                    "user_id": user_id,
                    "voice_interface": True
                },
                timestamp=datetime.now()
            )
            
            return f"Готую звіт за запитом: {query}"
            
        except Exception as e:
            logger.error(f"Reporting routing failed: {e}")
            return None
    
    async def _route_to_arbiter_agent(
        self,
        query: str,
        user_id: str
    ) -> Optional[str]:
        """
        Route query to arbiter agent for general queries
        """
        try:
            message = AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent="arbiter_agent",
                content={
                    "type": "voice_general_query",
                    "query": query,
                    "user_id": user_id,
                    "voice_interface": True
                },
                timestamp=datetime.now()
            )
            
            return f"Обробляю запит: {query}"
            
        except Exception as e:
            logger.error(f"Arbiter routing failed: {e}")
            return None
    
    async def _start_voice_session(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Start voice interaction session
        """
        try:
            user_id = message.content.get("user_id", "")
            
            if self.current_interaction:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "Voice session already active"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Initialize session
            self.current_interaction = {
                "user_id": user_id,
                "session_id": str(uuid.uuid4()),
                "start_time": datetime.now(),
                "interactions": []
            }
            
            self.interaction_start_time = datetime.now()
            
            # Welcome message
            welcome_text = "Голосовий інтерфейс активовано. Говоріть ваш запит."
            tts_result = await self.voice_interface.tts.synthesize_speech(
                welcome_text,
                user_id=user_id
            )
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "voice_session_started",
                    "session_id": self.current_interaction["session_id"],
                    "user_id": user_id,
                    "welcome_message": {
                        "text": welcome_text,
                        "audio_path": tts_result.get("audio_path")
                    }
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Voice session start failed: {e}")
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
    
    async def _end_voice_session(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        End voice interaction session
        """
        try:
            user_id = message.content.get("user_id", "")
            
            if not self.current_interaction:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": "No active voice session"
                    },
                    timestamp=datetime.now()
                )
                return
            
            # Calculate session duration
            session_duration = (datetime.now() - self.current_interaction["start_time"]).total_seconds()
            
            # Save session summary
            await self._save_session_summary(self.current_interaction)
            
            # Goodbye message
            goodbye_text = f"Сесія завершена. Тривалість: {session_duration:.1f} секунд."
            tts_result = await self.voice_interface.tts.synthesize_speech(
                goodbye_text,
                user_id=user_id
            )
            
            session_data = self.current_interaction.copy()
            
            # Clear session
            self.current_interaction = None
            self.interaction_start_time = None
            
            yield AgentMessage(
                id=str(uuid.uuid4()),
                from_agent=self.agent_id,
                to_agent=message.from_agent,
                content={
                    "type": "voice_session_ended",
                    "session_data": session_data,
                    "goodbye_message": {
                        "text": goodbye_text,
                        "audio_path": tts_result.get("audio_path")
                    }
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Voice session end failed: {e}")
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
    
    async def _handle_voice_command(
        self,
        message: AgentMessage
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Handle voice commands (pause, resume, etc.)
        """
        try:
            command = message.content.get("command", "")
            user_id = message.content.get("user_id", "")
            
            if command == "pause":
                # Pause voice interaction
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "voice_command_response",
                        "command": "pause",
                        "status": "paused",
                        "user_id": user_id
                    },
                    timestamp=datetime.now()
                )
                
            elif command == "resume":
                # Resume voice interaction
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "voice_command_response",
                        "command": "resume",
                        "status": "resumed",
                        "user_id": user_id
                    },
                    timestamp=datetime.now()
                )
                
            elif command == "status":
                # Get voice interface status
                status = {
                    "active_session": self.current_interaction is not None,
                    "session_id": self.current_interaction.get("session_id") if self.current_interaction else None,
                    "user_id": self.current_interaction.get("user_id") if self.current_interaction else None,
                    "session_duration": (datetime.now() - self.interaction_start_time).total_seconds() if self.interaction_start_time else 0
                }
                
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "voice_command_response",
                        "command": "status",
                        "status": status,
                        "user_id": user_id
                    },
                    timestamp=datetime.now()
                )
                
            else:
                yield AgentMessage(
                    id=str(uuid.uuid4()),
                    from_agent=self.agent_id,
                    to_agent=message.from_agent,
                    content={
                        "type": "error",
                        "error": f"Unknown voice command: {command}"
                    },
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            logger.error(f"Voice command handling failed: {e}")
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
    
    async def _save_interaction(
        self,
        user_id: str,
        transcription: Dict[str, Any],
        response_text: str,
        tts_result: Dict[str, Any]
    ):
        """
        Save voice interaction to database
        """
        try:
            async with get_db_session() as session:
                interaction = VoiceInteraction(
                    user_id=user_id,
                    query_text=transcription.get("text", ""),
                    query_confidence=transcription.get("confidence", 0),
                    query_duration=transcription.get("duration", 0),
                    response_text=response_text,
                    response_audio_path=tts_result.get("audio_path"),
                    response_duration=tts_result.get("duration", 0),
                    processing_time_stt=transcription.get("processing_time", 0),
                    processing_time_tts=tts_result.get("processing_time", 0),
                    session_id=self.current_interaction.get("session_id") if self.current_interaction else None
                )
                
                session.add(interaction)
                await session.commit()
                
                # Add to current session if active
                if self.current_interaction:
                    self.current_interaction["interactions"].append({
                        "interaction_id": interaction.id,
                        "timestamp": interaction.created_at.isoformat(),
                        "query": interaction.query_text,
                        "response": interaction.response_text
                    })
                
        except Exception as e:
            logger.error(f"Interaction save failed: {e}")
    
    async def _save_session_summary(
        self,
        session_data: Dict[str, Any]
    ):
        """
        Save voice session summary
        """
        try:
            # This would save session summary to database
            # Implementation depends on session model
            logger.info(f"Voice session summary saved: {session_data['session_id']}")
            
        except Exception as e:
            logger.error(f"Session summary save failed: {e}")
    
    async def run_continuous_session(
        self,
        user_id: str,
        max_duration: int = 300
    ):
        """
        Run continuous voice session with timeout
        """
        try:
            logger.info(f"Starting continuous voice session for user {user_id}")
            
            start_time = datetime.now()
            
            while (datetime.now() - start_time).total_seconds() < max_duration:
                try:
                    # Record audio
                    audio_data = self.voice_interface.stt.record_audio(duration=5)
                    
                    if not audio_data:
                        continue
                    
                    # Check for silence timeout
                    if self._check_silence_timeout():
                        break
                    
                    # Process query
                    message = AgentMessage(
                        id=str(uuid.uuid4()),
                        from_agent="system",
                        to_agent=self.agent_id,
                        content={
                            "type": "voice_query",
                            "user_id": user_id,
                            "audio_data": audio_data
                        },
                        timestamp=datetime.now()
                    )
                    
                    # Process through agent
                    async for response in self.process_message(message):
                        if response.content.get("type") == "voice_response":
                            # Play response
                            audio_path = response.content.get("response", {}).get("audio_path")
                            if audio_path and os.path.exists(audio_path):
                                # In real implementation, stream audio
                                logger.info(f"Playing response: {response.content['response']['text'][:50]}...")
                        
                        # Check for exit commands
                        query_text = response.content.get("query", {}).get("text", "").lower()
                        if any(word in query_text for word in ["вихід", "exit", "quit", "стоп"]):
                            return
                    
                except KeyboardInterrupt:
                    logger.info(f"Continuous session interrupted for user {user_id}")
                    break
                except Exception as e:
                    logger.error(f"Continuous session error: {e}")
                    await asyncio.sleep(1)
            
            logger.info(f"Continuous voice session ended for user {user_id}")
            
        except Exception as e:
            logger.error(f"Continuous session failed: {e}")
    
    def _check_silence_timeout(self) -> bool:
        """
        Check if silence timeout exceeded
        """
        if not self.interaction_start_time:
            return False
        
        silence_duration = (datetime.now() - self.interaction_start_time).total_seconds()
        return silence_duration > self.auto_silence_timeout


# ========== TEST ==========
if __name__ == "__main__":
    async def test_voice_agent():
        # Initialize voice agent
        agent = VoiceAgent()
        
        # Test message processing
        test_message = AgentMessage(
            id="test_123",
            from_agent="test",
            to_agent="voice_agent",
            content={
                "type": "start_voice_session",
                "user_id": "test_user"
            },
            timestamp=datetime.now()
        )
        
        print("Testing voice agent...")
        async for response in agent.process_message(test_message):
            print(f"Response: {response.content}")
        
        print("Voice agent test completed")
    
    # Run test
    asyncio.run(test_voice_agent())
