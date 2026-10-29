"""
Lightweight data models for Telegram Lite.
Prevents passing heavy MTProto objects into UI widgets to conserve memory on Android Go.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import unicodedata


def sanitize_text(text: Optional[str]) -> str:
    """
    Normalize and clean string for reliable UTF-8 rendering on Android.
    Ensures complex Unicode scripts (e.g. Bangla conjuncts) and UTF-8 strings
    are canonically composed and free of unprintable control codes.
    """
    if not text:
        return ""
    try:
        normalized = unicodedata.normalize("NFC", str(text))
        return "".join(c for c in normalized if c.isprintable() or c in ("\n", "\t", " "))
    except Exception:
        return str(text)


class ChatType(Enum):
    ALL = "all"
    PERSONAL = "personal"
    GROUP = "group"
    CHANNEL = "channel"
    BOT = "bot"


class CodeDeliveryType(Enum):
    APP_IN_APP = "app"
    SMS = "sms"
    CALL = "call"
    FLASH_CALL = "flash_call"
    FRAGMENT_SMS = "fragment_sms"
    UNKNOWN = "unknown"


class AuthState(Enum):
    UNAUTHENTICATED = "unauthenticated"
    WAITING_CODE = "waiting_code"
    WAITING_PASSWORD_2FA = "waiting_password_2fa"
    AUTHENTICATED = "authenticated"
    ERROR = "error"


@dataclass
class ChatSummary:
    """Lightweight representation of a conversation item."""
    peer_id: int
    title: str
    chat_type: ChatType
    last_message_text: str = ""
    last_message_time_str: str = ""
    last_message_timestamp: float = 0.0
    unread_count: int = 0
    is_muted: bool = False
    avatar_path: Optional[str] = None
    username: Optional[str] = None
    is_pinned_locally: bool = False

    def __post_init__(self):
        self.title = sanitize_text(self.title)
        self.last_message_text = sanitize_text(self.last_message_text)

    @property
    def initials(self) -> str:
        """Derive 1-2 character initials for the avatar placeholder."""
        cleaned = self.title.strip()
        if not cleaned:
            return "?"
        parts = cleaned.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return cleaned[:2].upper()

    @property
    def display_preview(self) -> str:
        """Formatted preview truncated to avoid UI overflow."""
        clean = " ".join(self.last_message_text.split())
        if len(clean) > 60:
            return clean[:57] + "..."
        return clean or "No messages yet"


@dataclass
class MessageItem:
    """Lightweight representation of a chat message."""
    id: int
    chat_id: int
    sender_id: int
    sender_name: str
    text: str
    time_str: str
    timestamp: float
    is_outgoing: bool
    reply_to_msg_id: Optional[int] = None
    reply_to_text: Optional[str] = None
    reply_to_sender: Optional[str] = None
    media_type: Optional[str] = None
    media_name: Optional[str] = None
    media_size_str: Optional[str] = None
    is_forwarded: bool = False
    forward_from_name: Optional[str] = None
    is_service: bool = False
    delivery_status: str = "sent"

    def __post_init__(self):
        self.text = sanitize_text(self.text)
        self.sender_name = sanitize_text(self.sender_name)

    @property
    def formatted_time(self) -> str:
        return self.time_str or ""


@dataclass
class TelegramUser:
    """Current logged in user profile."""
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None

    @property
    def full_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name
