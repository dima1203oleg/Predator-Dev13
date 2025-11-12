"""
Telegram Parser: Extract messages and mentions from Telegram channels
"""

import hashlib
import logging
import os
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from telethon import TelegramClient
from telethon.tl.types import Channel, Message

logger = logging.getLogger(__name__)


class TelegramParser:
    """
    Parse Telegram channels for OSINT data:
    - Message extraction
    - Entity mentions (companies, EDRPOU codes)
    - Channel metadata
    - Rate limiting and retry logic
    """

    def __init__(
        self,
        api_id: str | None = None,
        api_hash: str | None = None,
        session_name: str = "predator_telegram",
    ):
        self.api_id = api_id or os.getenv("TELEGRAM_API_ID")
        self.api_hash = api_hash or os.getenv("TELEGRAM_API_HASH")
        self.session_name = session_name

        self.client = None
        self.is_connected = False

        logger.info("TelegramParser initialized")

    async def connect(self) -> bool:
        """Connect to Telegram API"""
        try:
            if not self.api_id or not self.api_hash:
                raise ValueError("Telegram API credentials not provided")

            self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
            await self.client.start()

            self.is_connected = True
            logger.info("Connected to Telegram")
            return True

        except Exception as e:
            logger.error(f"Telegram connection failed: {e}")
            return False

    async def disconnect(self):
        """Disconnect from Telegram"""
        if self.client:
            await self.client.disconnect()
            self.is_connected = False
            logger.info("Disconnected from Telegram")

    async def parse_channel(
        self,
        channel_username: str,
        days_back: int = 30,
        max_messages: int = 1000,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        """
        Parse Telegram channel

        Args:
            channel_username: @channelname or https://t.me/channelname
            days_back: How many days back to search
            max_messages: Maximum messages to retrieve

        Returns:
            {
                "channel_info": {...},
                "messages": [...],
                "entities": [...],  # Extracted entities
                "statistics": {...}
            }
        """
        if not self.is_connected:
            success = await self.connect()
            if not success:
                return {"error": "Failed to connect to Telegram"}

        try:
            logger.info(f"Parsing channel: {channel_username}")

            # Get channel entity
            channel = await self.client.get_entity(channel_username)

            if not isinstance(channel, Channel):
                return {"error": "Not a channel"}

            channel_info = {
                "id": channel.id,
                "username": channel.username,
                "title": channel.title,
                "participants_count": channel.participants_count,
                "description": channel.about,
                "verified": getattr(channel, "verified", False),
                "megagroup": getattr(channel, "megagroup", False),
            }

            # Calculate date range
            since_date = datetime.now() - timedelta(days=days_back)

            # Get messages
            messages = []
            entities = []

            async for message in self.client.iter_messages(
                channel, limit=max_messages, offset_date=since_date
            ):
                if message.message:  # Skip empty messages
                    msg_data = self._process_message(message)
                    messages.append(msg_data)

                    # Extract entities
                    msg_entities = self._extract_entities(message)
                    entities.extend(msg_entities)

                # Progress callback
                if progress_callback and len(messages) % 100 == 0:
                    progress_callback(len(messages), max_messages)

            # Statistics
            statistics = {
                "total_messages": len(messages),
                "date_range": {"from": since_date.isoformat(), "to": datetime.now().isoformat()},
                "unique_entities": len(set(e["text"] for e in entities)),
                "entity_types": {},
            }

            # Count entity types
            for entity in entities:
                etype = entity.get("type", "unknown")
                statistics["entity_types"][etype] = statistics["entity_types"].get(etype, 0) + 1

            logger.info(
                f"Parsed {len(messages)} messages, {len(entities)} entities from {channel_username}"
            )

            return {
                "channel_info": channel_info,
                "messages": messages,
                "entities": entities,
                "statistics": statistics,
            }

        except Exception as e:
            logger.error(f"Channel parsing failed: {e}")
            return {"error": str(e)}

    def _process_message(self, message: Message) -> dict[str, Any]:
        """Process individual message"""
        return {
            "id": message.id,
            "date": message.date.isoformat(),
            "text": message.message,
            "views": getattr(message, "views", 0),
            "forwards": getattr(message, "forwards", 0),
            "replies": getattr(message, "replies", {}).get("replies", 0) if message.replies else 0,
            "edit_date": message.edit_date.isoformat() if message.edit_date else None,
            "post_author": getattr(message, "post_author", None),
            "grouped_id": getattr(message, "grouped_id", None),
            "restriction_reason": getattr(message, "restriction_reason", []),
            "media": self._extract_media_info(message),
        }

    def _extract_entities(self, message: Message) -> list[dict[str, Any]]:
        """Extract entities from message text"""
        entities = []
        text = message.message or ""

        # EDRPOU codes (8-10 digits)
        import re

        edrpou_matches = re.findall(r"\b\d{8,10}\b", text)
        for match in edrpou_matches:
            entities.append(
                {"type": "edrpou", "text": match, "message_id": message.id, "confidence": 0.9}
            )

        # Company names (Ukrainian patterns)
        # Simple heuristic: capitalized words 3+ chars
        words = re.findall(r"\b[A-ZА-Я][a-zа-я]{2,}\b", text)
        for word in words:
            if len(word) > 3:  # Skip common words
                entities.append(
                    {
                        "type": "company_name",
                        "text": word,
                        "message_id": message.id,
                        "confidence": 0.6,
                    }
                )

        # HS codes (4-10 digits)
        hs_matches = re.findall(r"\b\d{4,10}\b", text)
        for match in hs_matches:
            if 4 <= len(match) <= 10:
                entities.append(
                    {"type": "hs_code", "text": match, "message_id": message.id, "confidence": 0.8}
                )

        return entities

    def _extract_media_info(self, message: Message) -> dict[str, Any] | None:
        """Extract media information"""
        if not message.media:
            return None

        media_info = {"type": type(message.media).__name__}

        # Photo
        if hasattr(message.media, "photo"):
            media_info.update(
                {
                    "width": getattr(message.media.photo, "w", 0),
                    "height": getattr(message.media.photo, "h", 0),
                    "size": getattr(message.media.photo, "size", 0),
                }
            )

        # Document
        elif hasattr(message.media, "document"):
            doc = message.media.document
            media_info.update(
                {
                    "file_name": getattr(doc, "file_name", ""),
                    "mime_type": getattr(doc, "mime_type", ""),
                    "size": getattr(doc, "size", 0),
                }
            )

        return media_info

    def convert_to_records(
        self, parse_result: dict[str, Any], source_channel: str
    ) -> list[dict[str, Any]]:
        """
        Convert Telegram entities to standardized records format
        """
        records = []
        seen_hashes = set()

        for entity in parse_result.get("entities", []):
            try:
                # Base record
                record = {
                    "source_channel": source_channel,
                    "source_type": "telegram",
                    "message_id": entity["message_id"],
                    "entity_type": entity["type"],
                    "entity_text": entity["text"],
                    "confidence": entity["confidence"],
                    "date": (
                        parse_result["messages"][0]["date"]
                        if parse_result.get("messages")
                        else datetime.now().isoformat()
                    ),
                }

                # Map entity types to standard fields
                if entity["type"] == "edrpou":
                    record["edrpou"] = entity["text"]
                elif entity["type"] == "company_name":
                    record["company_name"] = entity["text"]
                elif entity["type"] == "hs_code":
                    record["hs_code"] = entity["text"]

                # Generate PK and dedupe
                pk = f"telegram_{source_channel}_{entity['message_id']}_{entity['type']}_{entity['text']}"
                record["pk"] = pk

                op_hash = hashlib.sha256(pk.encode()).hexdigest()[:16]
                if op_hash not in seen_hashes:
                    record["op_hash"] = op_hash
                    records.append(record)
                    seen_hashes.add(op_hash)

            except Exception as e:
                logger.warning(f"Entity conversion failed: {e}")

        logger.info(f"Converted {len(records)} Telegram entities to records")
        return records


# ========== TEST ==========
if __name__ == "__main__":
    # Mock test (would need real API credentials)
    parser = TelegramParser()

    # Mock result
    mock_result = {
        "channel_info": {"id": 123456, "username": "test_channel", "title": "Test Channel"},
        "messages": [
            {
                "id": 1,
                "date": "2023-01-15T10:00:00",
                "text": "Компанія ТОВ 'Тест' з кодом 12345678 імпортує товар 8418",
            }
        ],
        "entities": [
            {"type": "company_name", "text": "ТОВ", "message_id": 1, "confidence": 0.6},
            {"type": "edrpou", "text": "12345678", "message_id": 1, "confidence": 0.9},
            {"type": "hs_code", "text": "8418", "message_id": 1, "confidence": 0.8},
        ],
        "statistics": {"total_messages": 1, "unique_entities": 3},
    }

    records = parser.convert_to_records(mock_result, "@test_channel")
    print(f"Converted {len(records)} records")
    print(f"Sample: {records[0] if records else 'None'}")
