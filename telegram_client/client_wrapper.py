"""
Telethon MTProto Client Wrapper for Android Go.
Manages a single persistent TelegramClient on a background asyncio thread,
dispatches thread-safe UI callbacks, and transforms MTProto data into lightweight models.
"""

import asyncio
import os
import threading
import logging
from datetime import datetime, timezone
from typing import Optional, List, Callable, Dict, Any

from telethon import TelegramClient, events, utils
from telethon.sessions import StringSession
from telethon.tl import types
from telethon.tl.custom import Dialog
from telethon.tl.functions.messages import GetDialogFiltersRequest
from telethon.errors import FloodWaitError

from telegram_client.models import (
    ChatSummary,
    MessageItem,
    ChatType,
    ChatFolder,
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
        self._cached_folders: List[ChatFolder] = []
        self._entity_cache: Dict[int, Any] = {}
        self._is_connected = False

        self.downloads_dir = os.path.join(self.cache_manager.cache_dir, "downloads")
        try:
            os.makedirs(self.downloads_dir, exist_ok=True)
        except Exception:
            pass

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
                app_version="0.1.4",
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
        limit: int = 50,
        offset_date=None,
        offset_id: int = 0,
        append: bool = False,
        on_result: Callable[[List[ChatSummary], Optional[Exception]], None] = None,
    ) -> None:
        """
        Fetch conversations from Telegram MTProto, map to ChatSummary,
        and apply custom local pins from PinStore. Supports pagination.
        """
        async def _fetch():
            pinned_peer_ids = self.pin_store.get_pinned_peer_ids()
            kwargs = {"limit": limit}
            if offset_date:
                kwargs["offset_date"] = offset_date
            if offset_id:
                kwargs["offset_id"] = offset_id

            dialogs = await self.client.get_dialogs(**kwargs)
            summaries: List[ChatSummary] = []

            for d in dialogs:
                # Cache input entity to prevent "Could not find input entity" error on get_messages
                entity_obj = getattr(d, "input_entity", None) or getattr(d, "entity", None)
                if entity_obj:
                    self._entity_cache[d.id] = entity_obj

                summary = self._convert_telethon_dialog(d, pinned_peer_ids)
                summaries.append(summary)

                if entity_obj:
                    self._entity_cache[summary.peer_id] = entity_obj

                # Keep PinStore metadata up to date with user/chat renames
                if summary.peer_id in pinned_peer_ids:
                    self.pin_store.update_chat_metadata(
                        summary.peer_id, summary.title, summary.username
                    )

            if append:
                existing_pids = {c.peer_id for c in self._cached_summaries}
                for s in summaries:
                    if s.peer_id not in existing_pids:
                        self._cached_summaries.append(s)
            else:
                self._cached_summaries = summaries
            return self._cached_summaries

        def _done(res, exc):
            if on_result:
                on_result(res or [], exc)

        self.run_coroutine(_fetch(), _done)

    def load_more_conversations(
        self,
        limit: int = 40,
        on_result: Callable[[List[ChatSummary], Optional[Exception]], None] = None,
    ) -> None:
        """Fetch the next page of conversations and append to cache."""
        offset_date = None
        offset_id = 0
        if self._cached_summaries:
            last = self._cached_summaries[-1]
            if last.last_message_timestamp:
                offset_date = datetime.fromtimestamp(last.last_message_timestamp, tz=timezone.utc)
        self.load_conversations(
            limit=limit,
            offset_date=offset_date,
            offset_id=offset_id,
            append=True,
            on_result=on_result,
        )

    def load_chat_folders(
        self,
        on_result: Optional[Callable[[List[ChatFolder], Optional[Exception]], None]] = None,
    ) -> None:
        """
        Fetch real Telegram chat folders (DialogFilters) from Telegram servers via MTProto.
        """
        async def _fetch():
            if not self.client or not self.client.is_connected():
                return []
            try:
                raw_filters = await self.client(GetDialogFiltersRequest())
                folders: List[ChatFolder] = []
                for f in raw_filters:
                    if isinstance(f, types.DialogFilterDefault):
                        continue
                    if isinstance(f, (types.DialogFilter, types.DialogFilterChatlist)):
                        fid = getattr(f, "id", 0)
                        raw_title = getattr(f, "title", None)
                        if hasattr(raw_title, "text"):
                            title = raw_title.text
                        elif raw_title:
                            title = str(raw_title)
                        else:
                            title = f"Folder {fid}"

                        emoticon = getattr(f, "emoticon", None)

                        pinned = []
                        for p in getattr(f, "pinned_peers", []):
                            try:
                                pinned.append(utils.get_peer_id(p))
                            except Exception:
                                pass

                        include = []
                        for p in getattr(f, "include_peers", []):
                            try:
                                include.append(utils.get_peer_id(p))
                            except Exception:
                                pass

                        exclude = []
                        for p in getattr(f, "exclude_peers", []):
                            try:
                                exclude.append(utils.get_peer_id(p))
                            except Exception:
                                pass

                        folder = ChatFolder(
                            id=fid,
                            title=title,
                            emoticon=emoticon,
                            pinned_peer_ids=pinned,
                            include_peer_ids=include,
                            exclude_peer_ids=exclude,
                            contacts=bool(getattr(f, "contacts", False)),
                            non_contacts=bool(getattr(f, "non_contacts", False)),
                            groups=bool(getattr(f, "groups", False)),
                            broadcasts=bool(getattr(f, "broadcasts", False)),
                            bots=bool(getattr(f, "bots", False)),
                            exclude_muted=bool(getattr(f, "exclude_muted", False)),
                            exclude_read=bool(getattr(f, "exclude_read", False)),
                            exclude_archived=bool(getattr(f, "exclude_archived", False)),
                        )
                        folders.append(folder)
                self._cached_folders = folders
                return folders
            except Exception as e:
                logger.warning("Error fetching dialog filters: %s", e)
                return []

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

    def filter_conversations_by_folder(self, folder: Optional[ChatFolder]) -> List[ChatSummary]:
        """
        Filter in-memory cached conversations based on Telegram chat folder criteria.
        If folder is None or folder.id == 0, returns all chats.
        """
        if not folder or folder.id == 0:
            pinned = [c for c in self._cached_summaries if c.is_pinned_locally]
            unpinned = [c for c in self._cached_summaries if not c.is_pinned_locally]
            return pinned + unpinned

        matched: List[ChatSummary] = []
        folder_pinned: List[ChatSummary] = []

        for chat in self._cached_summaries:
            pid = chat.peer_id

            # 1. Exclusions have highest priority
            if pid in folder.exclude_peer_ids:
                continue
            if folder.exclude_muted and chat.is_muted:
                continue
            if folder.exclude_read and chat.unread_count == 0:
                continue
            if folder.exclude_archived and chat.is_archived:
                continue

            # 2. Check explicit inclusion or folder pins
            is_folder_pinned = pid in folder.pinned_peer_ids
            is_explicit = pid in folder.include_peer_ids or is_folder_pinned

            # 3. Check type-based inclusion
            is_type_match = False
            if folder.contacts and chat.is_contact:
                is_type_match = True
            elif folder.non_contacts and (not chat.is_contact and chat.chat_type == ChatType.PERSONAL):
                is_type_match = True
            elif folder.groups and chat.chat_type == ChatType.GROUP:
                is_type_match = True
            elif folder.broadcasts and chat.chat_type == ChatType.CHANNEL:
                is_type_match = True
            elif folder.bots and chat.is_bot:
                is_type_match = True

            if is_explicit or is_type_match:
                if is_folder_pinned or chat.is_pinned_locally:
                    folder_pinned.append(chat)
                else:
                    matched.append(chat)

        return folder_pinned + matched

    # -------------------------------------------------------------
    # Messages & Messaging
    # -------------------------------------------------------------

    async def _resolve_entity(self, chat_id: int):
        """
        Safely resolve MTProto entity using in-memory cache, get_input_entity, or get_entity.
        Prevents 'Could not find the input entity' failures when opening chats or channels.
        """
        if chat_id in self._entity_cache:
            return self._entity_cache[chat_id]
        try:
            entity = await self.client.get_input_entity(chat_id)
            self._entity_cache[chat_id] = entity
            return entity
        except Exception:
            try:
                entity = await self.client.get_entity(chat_id)
                self._entity_cache[chat_id] = entity
                return entity
            except Exception:
                return chat_id

    def load_messages(
        self,
        chat_id: int,
        limit: int = 50,
        offset_id: int = 0,
        on_result: Callable[[List[MessageItem], Optional[Exception]], None] = None,
    ) -> None:
        """Load message history for a conversation with pagination and error resilience."""
        async def _load():
            entity = await self._resolve_entity(chat_id)
            messages = await self.client.get_messages(
                entity, limit=limit, offset_id=offset_id
            )
            items: List[MessageItem] = []
            for m in messages:
                if not m:
                    continue
                try:
                    item = self._convert_telethon_message(m, fallback_chat_id=chat_id)
                    if item:
                        items.append(item)
                except Exception as err:
                    logger.warning("Error parsing message in chat %s: %s", chat_id, err)
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
            entity = await self._resolve_entity(chat_id)
            sent = await self.client.send_message(
                entity, text, reply_to=reply_to_msg_id
            )
            return self._convert_telethon_message(sent, fallback_chat_id=chat_id)

        def _done(res, exc):
            if on_result:
                on_result(res, exc)

        self.run_coroutine(_send(), _done)

    def download_media(
        self,
        chat_id: int,
        message_id: int,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_result: Optional[Callable[[Optional[str], Optional[Exception]], None]] = None,
    ) -> None:
        """Download media attached to a message and store in downloads directory."""
        async def _dl():
            entity = await self._resolve_entity(chat_id)
            msg = await self.client.get_messages(entity, ids=message_id)
            if not msg or not getattr(msg, "media", None):
                raise ValueError("No media found on message")

            os.makedirs(self.downloads_dir, exist_ok=True)
            fname = None
            if hasattr(msg, "file") and msg.file and getattr(msg.file, "name", None):
                fname = msg.file.name
            elif isinstance(msg.media, types.MessageMediaPhoto):
                fname = f"photo_{chat_id}_{message_id}.jpg"

            target = os.path.join(self.downloads_dir, fname) if fname else self.downloads_dir

            saved_path = await self.client.download_media(
                msg,
                file=target,
                progress_callback=on_progress,
            )
            return saved_path

        def _done(res, exc):
            if on_result:
                on_result(res, exc)

        self.run_coroutine(_dl(), _done)

    def send_file(
        self,
        chat_id: int,
        file_path: str,
        caption: Optional[str] = None,
        reply_to_msg_id: Optional[int] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_result: Optional[Callable[[Optional[MessageItem], Optional[Exception]], None]] = None,
    ) -> None:
        """Upload and send media/file to a chat."""
        async def _upload():
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            entity = await self._resolve_entity(chat_id)
            sent = await self.client.send_file(
                entity,
                file_path,
                caption=caption,
                reply_to=reply_to_msg_id,
                progress_callback=on_progress,
            )
            return self._convert_telethon_message(sent, fallback_chat_id=chat_id)

        def _done(res, exc):
            if on_result:
                on_result(res, exc)

        self.run_coroutine(_upload(), _done)

    def delete_messages(
        self,
        chat_id: int,
        message_ids: List[int],
        on_result: Callable[[bool, Optional[Exception]], None] = None,
    ) -> None:
        """Delete messages by ID."""
        async def _del():
            entity = await self._resolve_entity(chat_id)
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

        is_contact = False
        is_bot = False
        try:
            if getattr(dialog, "entity", None):
                is_contact = bool(getattr(dialog.entity, "contact", False))
                is_bot = bool(getattr(dialog.entity, "bot", False))
        except Exception:
            pass

        is_archived = False
        try:
            is_archived = bool(getattr(dialog, "archived", False) or getattr(dialog, "folder_id", 0) == 1)
        except Exception:
            pass

        # Message preview
        last_text = ""
        last_ts = 0.0
        time_str = ""
        if dialog.message:
            try:
                last_text = dialog.message.raw_text or dialog.message.message or (
                    "[Media]" if getattr(dialog.message, "media", None) else ""
                )
                if getattr(dialog.message, "date", None):
                    dt = dialog.message.date
                    last_ts = dt.timestamp()
                    time_str = dt.strftime("%H:%M")
            except Exception:
                last_text = ""

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
            is_contact=is_contact,
            is_bot=is_bot,
            is_archived=is_archived,
        )

    def _convert_telethon_message(self, msg, fallback_chat_id: int = 0) -> Optional[MessageItem]:
        """Convert a Telethon Message object to a lightweight MessageItem with error protection."""
        if not msg:
            return None
        if isinstance(msg, types.MessageEmpty):
            return None

        sender_name = "Unknown"
        sender_id = getattr(msg, "sender_id", 0) or 0
        try:
            if getattr(msg, "sender", None):
                s = msg.sender
                if hasattr(s, "first_name"):
                    sender_name = s.first_name or ""
                    if getattr(s, "last_name", None):
                        sender_name += f" {s.last_name}"
                elif hasattr(s, "title"):
                    sender_name = s.title or ""
        except Exception:
            sender_name = "Unknown"

        time_str = ""
        ts = 0.0
        try:
            if getattr(msg, "date", None):
                time_str = msg.date.strftime("%H:%M")
                ts = msg.date.timestamp()
        except Exception:
            pass

        # Text extraction (normal text, message, or service action)
        text = ""
        try:
            if getattr(msg, "raw_text", None):
                text = msg.raw_text
            elif getattr(msg, "message", None):
                text = msg.message
            elif getattr(msg, "action", None):
                text = f"[{type(msg.action).__name__}]"
        except Exception:
            text = ""

        # Reply info
        reply_id = None
        reply_text = None
        try:
            if getattr(msg, "reply_to", None):
                reply_id = getattr(msg.reply_to, "reply_to_msg_id", None)
        except Exception:
            pass

        # Media detection
        media_type = None
        media_name = None
        media_size = None
        local_path = None
        try:
            if getattr(msg, "media", None):
                m = msg.media
                if isinstance(m, types.MessageMediaPhoto):
                    media_type = "photo"
                    media_name = f"photo_{getattr(msg, 'chat_id', 0) or fallback_chat_id}_{getattr(msg, 'id', 0)}.jpg"
                elif isinstance(m, types.MessageMediaDocument):
                    media_type = "document"
                    doc = getattr(m, "document", None)
                    if doc and hasattr(doc, "attributes"):
                        for attr in doc.attributes:
                            if isinstance(attr, types.DocumentAttributeFilename):
                                media_name = attr.file_name
                            elif isinstance(attr, types.DocumentAttributeAudio):
                                media_type = "voice" if getattr(attr, "voice", False) else "audio"
                            elif isinstance(attr, types.DocumentAttributeVideo):
                                media_type = "video"
                    size_bytes = getattr(doc, "size", 0) if doc else 0
                    if size_bytes:
                        if size_bytes < 1024 * 1024:
                            media_size = f"{size_bytes / 1024:.1f} KB"
                        else:
                            media_size = f"{size_bytes / (1024*1024):.1f} MB"
                elif isinstance(m, types.MessageMediaWebPage):
                    media_type = "webpage"
                elif isinstance(m, types.MessageMediaGeo):
                    media_type = "location"
                elif isinstance(m, types.MessageMediaContact):
                    media_type = "contact"
                else:
                    media_type = "media"

                if media_name and hasattr(self, "downloads_dir"):
                    candidate = os.path.join(self.downloads_dir, media_name)
                    if os.path.exists(candidate):
                        local_path = candidate
        except Exception:
            pass

        # If both text and media are missing, provide a fallback indicator
        if not text and not media_type and getattr(msg, "action", None):
            text = "[Service Notification]"

        chat_id = getattr(msg, "chat_id", None) or fallback_chat_id or 0
        is_out = bool(getattr(msg, "out", False))
        is_fwd = bool(getattr(msg, "fwd_from", False))
        is_service = False
        try:
            is_service = bool(getattr(msg, "action", False))
        except Exception:
            pass

        return MessageItem(
            id=getattr(msg, "id", 0),
            chat_id=chat_id,
            sender_id=sender_id,
            sender_name=sender_name.strip() or "Unknown",
            text=text,
            time_str=time_str,
            timestamp=ts,
            is_outgoing=is_out,
            reply_to_msg_id=reply_id,
            reply_to_text=reply_text,
            media_type=media_type,
            media_name=media_name,
            media_size_str=media_size,
            is_forwarded=is_fwd,
            is_service=is_service,
            local_media_path=local_path,
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
