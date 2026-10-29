"""
Telethon MTProto Client Wrapper for Android Go.
Manages a single persistent TelegramClient on a background asyncio thread,
dispatches thread-safe UI callbacks, and transforms MTProto data into lightweight models.
"""

import asyncio
import threading
import logging
from datetime import datetime, timezone
from typing import Optional, List, Callable, Dict, Any

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl import types
from telethon.tl.custom import Dialog
from telethon.errors import FloodWaitError

from telegram_client.models import (
    ChatSummary,
    MessageItem,
    ChatType,
    TelegramUser,
    AuthState,
    CodeDeliveryType,
)
from telegram_client.auth_handler import AuthHandler
from storage.secure_store import SecureSessionStore
from storage.pin_store import PinStore
from storage.cache_manager import CacheManager

logger = logging.getLogger("ClientWrapper")


class TelegramClientWrapper:
    """
    High-performance MTProto manager. Runs an asyncio event loop in a background daemon thread.
    Guarantees no UI freezing on Android Go devices.
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        secure_store: SecureSessionStore,
        pin_store: PinStore,
        cache_manager: CacheManager,
    ):
        self.api_id = api_id
        self.api_hash = api_hash
        self.secure_store = secure_store
        self.pin_store = pin_store
        self.cache_manager = cache_manager

        self.auth_handler = AuthHandler(secure_store)
        self.client: Optional[TelegramClient] = None

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._is_running = False
        self._lock = threading.Lock()

        # Listeners for real-time message updates
        self._new_message_callbacks: List[Callable[[MessageItem], None]] = []
        self._connection_state_callbacks: List[Callable[[bool, str], None]] = []

        # Cached in-memory dialogs for instant tab switching
        self._cached_summaries: List[ChatSummary] = []
        self._is_connected = False

    def start(self) -> None:
        """Start background worker thread with asyncio event loop."""
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._thread = threading.Thread(
                target=self._run_event_loop, name="TelegramMTProtoWorker", daemon=True
            )
            self._thread.start()

    def _run_event_loop(self) -> None:
        """Background thread worker loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    def run_coroutine(self, coro, callback: Optional[Callable[[Any, Optional[Exception]], None]] = None):
        """
        Execute an async coroutine on the background worker thread
        and deliver the result or exception to the callback.
        """
        if not self._loop or not self._is_running:
            if asyncio.iscoroutine(coro):
                coro.close()
            if callback:
                callback(None, RuntimeError("Worker loop is not running"))
            return

        async def _wrapper():
            res, exc = None, None
            try:
                res = await coro
            except Exception as e:
                exc = e
                logger.error("Async task error: %s", e)
            if callback:
                callback(res, exc)

        asyncio.run_coroutine_threadsafe(_wrapper(), self._loop)

    def initialize_client(self, on_complete: Callable[[bool, Optional[TelegramUser]], None]) -> None:
        """
        Initialize or restore TelegramClient using saved session.
        """
        async def _init():
            saved = self.secure_store.load_session()
            session_str = saved[0] if saved else ""
            session = StringSession(session_str)

            # Prevent recreating duplicate client instances
            if self.client:
                try:
                    await self.client.disconnect()
                except Exception:
                    pass

            self.client = TelegramClient(
                session,
                self.api_id,
                self.api_hash,
                device_model="Android Go Edition",
                system_version="Android 13 Go",
                app_version="0.1.2",
                lang_code="en",
                system_lang_code="en",
                flood_sleep_threshold=30,
            )

            await self.client.connect()
            self._is_connected = True

            # Register MTProto real-time update handler
            self._register_event_handlers()

            # Check if existing session is authorized
            auth_ok, user = await self.auth_handler.check_saved_session(self.client)
            return auth_ok, user

        self.run_coroutine(
            _init(),
            lambda res, exc: on_complete(res[0] if res else False, res[1] if res else None),
        )

    def _register_event_handlers(self) -> None:
        """Attach real-time MTProto event listeners."""
        if not self.client:
            return

        @self.client.on(events.NewMessage)
        async def _on_new_message(event):
            try:
                msg_item = self._convert_telethon_message(event.message)
                for cb in self._new_message_callbacks:
                    try:
                        cb(msg_item)
                    except Exception as e:
                        logger.error("Error in message callback: %s", e)
            except Exception as e:
                logger.error("Error handling incoming message event: %s", e)

    def add_message_listener(self, cb: Callable[[MessageItem], None]) -> None:
        if cb not in self._new_message_callbacks:
            self._new_message_callbacks.append(cb)

    def remove_message_listener(self, cb: Callable[[MessageItem], None]) -> None:
        if cb in self._new_message_callbacks:
            self._new_message_callbacks.remove(cb)

    # -------------------------------------------------------------
    # Authentication Methods
    # -------------------------------------------------------------

    def request_login_code(
        self,
        phone: str,
        on_result: Callable[[bool, str, CodeDeliveryType, int], None],
    ) -> None:
        """Request phone verification code."""
        async def _req():
            if not self.client or not self.client.is_connected():
                if self.client:
                    await self.client.connect()
            return await self.auth_handler.send_code(self.client, phone)

        def _done(res, exc):
            if exc:
                on_result(False, str(exc), CodeDeliveryType.UNKNOWN, 0)
            elif res:
                on_result(res[0], res[1], res[2], res[3])

        self.run_coroutine(_req(), _done)

    def submit_code(
        self,
        code: str,
        on_result: Callable[[bool, str, AuthState], None],
    ) -> None:
        """Submit SMS / In-App verification code."""
        async def _submit():
            return await self.auth_handler.sign_in_with_code(self.client, code)

        def _done(res, exc):
            if exc:
                on_result(False, str(exc), AuthState.ERROR)
            elif res:
                on_result(res[0], res[1], res[2])

        self.run_coroutine(_submit(), _done)

    def submit_2fa_password(
        self,
        password: str,
        on_result: Callable[[bool, str, AuthState], None],
    ) -> None:
        """Submit 2FA Two-Step Verification password."""
        async def _sub():
            return await self.auth_handler.sign_in_with_password(self.client, password)

        def _done(res, exc):
            if exc:
                on_result(False, str(exc), AuthState.ERROR)
            elif res:
                on_result(res[0], res[1], res[2])

        self.run_coroutine(_sub(), _done)

    def logout(self, on_result: Callable[[bool], None]) -> None:
        """Log out and wipe local credentials."""
        async def _lo():
            res = await self.auth_handler.logout(self.client)
            self._cached_summaries.clear()
            return res

        def _done(res, exc):
            on_result(bool(res and not exc))

        self.run_coroutine(_lo(), _done)

    # -------------------------------------------------------------
    # Conversation Loading & Filtering
    # -------------------------------------------------------------

    def load_conversations(
        self,
        limit: int = 30,
        on_result: Callable[[List[ChatSummary], Optional[Exception]], None] = None,
    ) -> None:
        """
        Fetch conversations from Telegram MTProto, map to ChatSummary,
        and apply custom local pins from PinStore.
        """
        async def _fetch():
            pinned_peer_ids = self.pin_store.get_pinned_peer_ids()
            dialogs = await self.client.get_dialogs(limit=limit)
            summaries: List[ChatSummary] = []

            for d in dialogs:
                summary = self._convert_telethon_dialog(d, pinned_peer_ids)
                summaries.append(summary)

                # Keep PinStore metadata up to date with user/chat renames
                if summary.peer_id in pinned_peer_ids:
                    self.pin_store.update_chat_metadata(
                        summary.peer_id, summary.title, summary.username
                    )

            self._cached_summaries = summaries
            return summaries

        def _done(res, exc):
            if on_result:
                on_result(res or [], exc)

        self.run_coroutine(_fetch(), _done)

    def filter_cached_conversations(self, filter_type: ChatType) -> List[ChatSummary]:
        """
        Instant in-memory filtering for All, Personal, Groups, Channels tabs.
        Zero network latency and minimal memory overhead.
        """
        if filter_type == ChatType.ALL:
            filtered = list(self._cached_summaries)
        elif filter_type == ChatType.PERSONAL:
            filtered = [c for c in self._cached_summaries if c.chat_type == ChatType.PERSONAL]
        elif filter_type == ChatType.GROUP:
            filtered = [c for c in self._cached_summaries if c.chat_type == ChatType.GROUP]
        elif filter_type == ChatType.CHANNEL:
            filtered = [c for c in self._cached_summaries if c.chat_type == ChatType.CHANNEL]
        else:
            filtered = list(self._cached_summaries)

        # Custom pinned items are prioritized at the top
        pinned = [c for c in filtered if c.is_pinned_locally]
        unpinned = [c for c in filtered if not c.is_pinned_locally]
        return pinned + unpinned

    # -------------------------------------------------------------
    # Messages & Messaging
    # -------------------------------------------------------------

    def load_messages(
        self,
        chat_id: int,
        limit: int = 30,
        offset_id: int = 0,
        on_result: Callable[[List[MessageItem], Optional[Exception]], None] = None,
    ) -> None:
        """Load message history for a conversation with pagination."""
        async def _load():
            entity = await self.client.get_input_entity(chat_id)
            messages = await self.client.get_messages(
                entity, limit=limit, offset_id=offset_id
            )
            items = [self._convert_telethon_message(m) for m in messages if m]
            return items

        def _done(res, exc):
            if on_result:
                on_result(res or [], exc)

        self.run_coroutine(_load(), _done)

    def send_text_message(
        self,
        chat_id: int,
        text: str,
        reply_to_msg_id: Optional[int] = None,
        on_result: Callable[[Optional[MessageItem], Optional[Exception]], None] = None,
    ) -> None:
        """Send text message with optional reply_to ID."""
        async def _send():
            entity = await self.client.get_input_entity(chat_id)
            sent = await self.client.send_message(
                entity, text, reply_to=reply_to_msg_id
            )
            return self._convert_telethon_message(sent)

        def _done(res, exc):
            if on_result:
                on_result(res, exc)

        self.run_coroutine(_send(), _done)

    def delete_messages(
        self,
        chat_id: int,
        message_ids: List[int],
        on_result: Callable[[bool, Optional[Exception]], None] = None,
    ) -> None:
        """Delete messages by ID."""
        async def _del():
            entity = await self.client.get_input_entity(chat_id)
            await self.client.delete_messages(entity, message_ids)
            return True

        def _done(res, exc):
            if on_result:
                on_result(bool(res), exc)

        self.run_coroutine(_del(), _done)

    # -------------------------------------------------------------
    # Conversions: MTProto -> Dataclasses
    # -------------------------------------------------------------

    def _convert_telethon_dialog(
        self, dialog: Dialog, pinned_ids: set
    ) -> ChatSummary:
        """Convert a Telethon Dialog object to a lightweight ChatSummary."""
        peer_id = dialog.id
        title = dialog.name or "Untitled Chat"
        is_user = dialog.is_user
        is_group = dialog.is_group
        is_channel = dialog.is_channel and not is_group

        if is_user:
            c_type = ChatType.PERSONAL
        elif is_group:
            c_type = ChatType.GROUP
        elif is_channel:
            c_type = ChatType.CHANNEL
        else:
            c_type = ChatType.ALL

        # Message preview
        last_text = ""
        last_ts = 0.0
        time_str = ""
        if dialog.message:
            last_text = dialog.message.raw_text or (
                "[Media]" if dialog.message.media else ""
            )
            if dialog.message.date:
                dt = dialog.message.date
                last_ts = dt.timestamp()
                time_str = dt.strftime("%H:%M")

        username = None
        if hasattr(dialog.entity, "username") and dialog.entity.username:
            username = dialog.entity.username

        return ChatSummary(
            peer_id=peer_id,
            title=title,
            chat_type=c_type,
            last_message_text=last_text,
            last_message_time_str=time_str,
            last_message_timestamp=last_ts,
            unread_count=dialog.unread_count or 0,
            is_muted=dialog.dialog.notify_settings.mute_until is not None
            if hasattr(dialog.dialog, "notify_settings")
            else False,
            username=username,
            is_pinned_locally=(peer_id in pinned_ids),
        )

    def _convert_telethon_message(self, msg) -> MessageItem:
        """Convert a Telethon Message object to a lightweight MessageItem."""
        sender_name = "Unknown"
        sender_id = msg.sender_id or 0
        if msg.sender:
            if hasattr(msg.sender, "first_name"):
                sender_name = msg.sender.first_name or ""
                if getattr(msg.sender, "last_name", None):
                    sender_name += f" {msg.sender.last_name}"
            elif hasattr(msg.sender, "title"):
                sender_name = msg.sender.title or ""

        time_str = ""
        ts = 0.0
        if msg.date:
            time_str = msg.date.strftime("%H:%M")
            ts = msg.date.timestamp()

        # Reply info
        reply_id = None
        reply_text = None
        if msg.reply_to:
            reply_id = msg.reply_to.reply_to_msg_id

        # Media detection
        media_type = None
        media_name = None
        media_size = None
        if msg.media:
            if isinstance(msg.media, types.MessageMediaPhoto):
                media_type = "photo"
            elif isinstance(msg.media, types.MessageMediaDocument):
                media_type = "document"
                if hasattr(msg.media.document, "attributes"):
                    for attr in msg.media.document.attributes:
                        if isinstance(attr, types.DocumentAttributeFilename):
                            media_name = attr.file_name
                size_bytes = getattr(msg.media.document, "size", 0)
                if size_bytes:
                    media_size = f"{size_bytes / (1024*1024):.1f} MB"

        return MessageItem(
            id=msg.id,
            chat_id=msg.chat_id or 0,
            sender_id=sender_id,
            sender_name=sender_name,
            text=msg.raw_text or "",
            time_str=time_str,
            timestamp=ts,
            is_outgoing=bool(msg.out),
            reply_to_msg_id=reply_id,
            reply_to_text=reply_text,
            media_type=media_type,
            media_name=media_name,
            media_size_str=media_size,
            is_forwarded=bool(msg.fwd_from),
            is_service=isinstance(msg.action, types.TypeMessageAction)
            if hasattr(msg, "action")
            else False,
        )

    def stop(self) -> None:
        """Gracefully disconnect and terminate background thread."""
        with self._lock:
            if not self._is_running:
                return
            self._is_running = False

            if self.client and self._loop and self._loop.is_running():
                async def _disc():
                    try:
                        await self.client.disconnect()
                    except Exception:
                        pass
                asyncio.run_coroutine_threadsafe(_disc(), self._loop)

            if self._loop:
                self._loop.call_soon_threadsafe(self._loop.stop)

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2.0)
