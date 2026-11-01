"""
Real Conversation Screen for Telegram Lite.
Implements:
1. Message history with auto-pagination and earlier messages loading
2. Sender names, timestamps, incoming/outgoing bubbles
3. Text message composer with multiline input
4. Media viewing (photos) and downloading (photos, documents, audio, video)
5. Media and file uploading with attachment picker
6. Real-time incoming message updates
7. In-header Star / Pin toggle
"""

import os
from typing import List, Optional, Callable
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.clock import Clock

from app.ui_constants import (
    DARK_BG,
    DARK_SURFACE,
    DARK_CARD,
    DARK_BORDER,
    PRIMARY_BLUE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    ACCENT_GOLD,
    ACCENT_GREEN,
)
from telegram_client.client_wrapper import TelegramClientWrapper
from telegram_client.models import ChatSummary, MessageItem, ChatType
from storage.pin_store import PinStore
from app.components.message_bubble import MessageBubbleWidget


class ConversationScreen(Screen):
    """
    Active chat view displaying message history, media viewer/downloader, and composer with file upload.
    """

    def __init__(
        self,
        client_wrapper: TelegramClientWrapper,
        pin_store: PinStore,
        on_back_callback: Callable[[], None],
        **kwargs
    ):
        super().__init__(**kwargs)
        self.client = client_wrapper
        self.pin_store = pin_store
        self.on_back_callback = on_back_callback

        self.chat_summary: Optional[ChatSummary] = None
        self.messages: List[MessageItem] = []
        self.reply_to_item: Optional[MessageItem] = None
        self._is_loading_earlier = False
        self._has_more_messages = True

        with self.canvas.before:
            Color(*DARK_BG)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        self._build_ui()

    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def _build_ui(self):
        root = BoxLayout(orientation="vertical", size_hint=(1, 1))

        # 1. Header Bar: Back button, Chat Info (Title + status), Pin star
        self.header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(54),
            padding=[dp(6), dp(6), dp(10), dp(6)],
            spacing=dp(8),
        )
        with self.header.canvas.before:
            Color(*DARK_SURFACE)
            self.header_bg = RoundedRectangle(pos=self.header.pos, size=self.header.size)
        self.header.bind(
            pos=lambda inst, val: setattr(self.header_bg, "pos", val),
            size=lambda inst, val: setattr(self.header_bg, "size", val),
        )

        # Back Button
        self.back_btn = Button(
            text="←",
            font_size="20sp",
            bold=True,
            size_hint=(None, 1),
            width=dp(38),
            background_normal="",
            background_color=(0, 0, 0, 0),
            color=TEXT_PRIMARY,
        )
        self.back_btn.bind(on_release=lambda x: self._on_back_pressed())
        self.header.add_widget(self.back_btn)

        # Title & Subtitle column
        title_col = BoxLayout(orientation="vertical", spacing=dp(1))
        self.title_lbl = Label(
            text="Conversation",
            font_size="15sp",
            bold=True,
            color=TEXT_PRIMARY,
            halign="left",
            valign="middle",
            shorten=True,
        )
        self.title_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        self.subtitle_lbl = Label(
            text="offline",
            font_size="11sp",
            color=TEXT_SECONDARY,
            halign="left",
            valign="middle",
        )
        self.subtitle_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        title_col.add_widget(self.title_lbl)
        title_col.add_widget(self.subtitle_lbl)
        self.header.add_widget(title_col)

        # Custom Pin Star Button in Header
        self.pin_btn = Button(
            text="☆",
            font_size="20sp",
            size_hint=(None, 1),
            width=dp(38),
            background_normal="",
            background_color=(0, 0, 0, 0),
            color=TEXT_SECONDARY,
        )
        self.pin_btn.bind(on_release=self._on_pin_header_clicked)
        self.header.add_widget(self.pin_btn)

        root.add_widget(self.header)

        # 2. Messages Scroll Area with auto-pagination
        self.scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.scroll.bind(scroll_y=self._on_scroll_change)

        self.messages_box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(4),
            padding=[dp(6), dp(6), dp(6), dp(6)],
        )
        self.messages_box.bind(minimum_height=self.messages_box.setter("height"))

        # Load earlier messages button
        self.load_more_btn = Button(
            text="Load Earlier Messages",
            font_size="12sp",
            size_hint_y=None,
            height=dp(32),
            background_normal="",
            background_color=DARK_CARD,
            color=TEXT_SECONDARY,
        )
        self.load_more_btn.bind(on_release=lambda x: self._load_earlier_messages())
        self.messages_box.add_widget(self.load_more_btn)

        self.scroll.add_widget(self.messages_box)
        root.add_widget(self.scroll)

        # 3. Reply Banner (Conditional)
        self.reply_banner = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=0,
            opacity=0,
            padding=[dp(12), dp(2), dp(12), dp(2)],
        )
        with self.reply_banner.canvas.before:
            Color(*DARK_CARD)
            self.reply_bg = RoundedRectangle(pos=self.reply_banner.pos, size=self.reply_banner.size)
        self.reply_banner.bind(
            pos=lambda inst, val: setattr(self.reply_bg, "pos", val),
            size=lambda inst, val: setattr(self.reply_bg, "size", val),
        )

        self.reply_lbl = Label(
            text="",
            font_size="11sp",
            color=TEXT_PRIMARY,
            halign="left",
            size_hint_x=0.9,
        )
        self.reply_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        self.reply_banner.add_widget(self.reply_lbl)

        close_reply_btn = Button(
            text="✕",
            font_size="12sp",
            size_hint=(None, 1),
            width=dp(28),
            background_normal="",
            background_color=(0, 0, 0, 0),
            color=TEXT_SECONDARY,
        )
        close_reply_btn.bind(on_release=lambda x: self._cancel_reply())
        self.reply_banner.add_widget(close_reply_btn)
        root.add_widget(self.reply_banner)

        # 4. Message Composer Bottom Bar (with Attachment Button)
        composer = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(52),
            padding=[dp(6), dp(6), dp(6), dp(6)],
            spacing=dp(6),
        )
        with composer.canvas.before:
            Color(*DARK_SURFACE)
            self.composer_bg = RoundedRectangle(pos=composer.pos, size=composer.size)
        composer.bind(
            pos=lambda inst, val: setattr(self.composer_bg, "pos", val),
            size=lambda inst, val: setattr(self.composer_bg, "size", val),
        )

        # Attachment / Upload button
        self.attach_btn = Button(
            text="📎",
            font_size="18sp",
            bold=True,
            size_hint=(None, 1),
            width=dp(38),
            background_normal="",
            background_color=DARK_CARD,
            color=TEXT_PRIMARY,
        )
        self.attach_btn.bind(on_release=lambda x: self._show_upload_dialog())
        composer.add_widget(self.attach_btn)

        self.message_input = TextInput(
            hint_text="Write a message...",
            multiline=True,
            size_hint=(1, 1),
            font_size="14sp",
            background_normal="",
            background_color=DARK_CARD,
            foreground_color=TEXT_PRIMARY,
            cursor_color=PRIMARY_BLUE,
            padding=[dp(10), dp(8), dp(10), dp(8)],
        )
        composer.add_widget(self.message_input)

        self.send_btn = Button(
            text="➤",
            font_size="18sp",
            bold=True,
            size_hint=(None, 1),
            width=dp(42),
            background_normal="",
            background_color=PRIMARY_BLUE,
            color=(1, 1, 1, 1),
        )
        self.send_btn.bind(on_release=self._on_send_clicked)
        composer.add_widget(self.send_btn)

        root.add_widget(composer)
        self.add_widget(root)

        # Listen for real-time messages
        self.client.add_message_listener(self._on_incoming_message)

    def _on_scroll_change(self, instance, val):
        """Auto-trigger earlier message loading when user scrolls near top."""
        if val >= 0.98 and not self._is_loading_earlier and self._has_more_messages and self.messages:
            self._load_earlier_messages()

    def set_chat(self, chat_summary: ChatSummary) -> None:
        """Bind conversation screen to a specific chat."""
        self.chat_summary = chat_summary
        self.messages.clear()
        self._has_more_messages = True
        self._is_loading_earlier = False
        self.load_more_btn.text = "Load Earlier Messages"
        self.title_lbl.text = chat_summary.title
        self.subtitle_lbl.text = chat_summary.chat_type.value.title()

        # Update Pin star state
        is_pinned = self.pin_store.is_pinned(chat_summary.peer_id)
        self.pin_btn.text = "★" if is_pinned else "☆"
        self.pin_btn.color = ACCENT_GOLD if is_pinned else TEXT_SECONDARY

        self._clear_messages_view()
        self._load_initial_messages()

    def _clear_messages_view(self):
        self.messages_box.clear_widgets()
        self.messages_box.add_widget(self.load_more_btn)

    def _show_loading(self):
        self.messages_box.clear_widgets()
        loading_lbl = Label(
            text="Loading messages...",
            font_size="13sp",
            color=TEXT_SECONDARY,
            size_hint_y=None,
            height=dp(50),
            halign="center",
        )
        self.messages_box.add_widget(loading_lbl)

    def _render_error(self, err_text: str):
        self.messages_box.clear_widgets()
        err_box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(110),
            spacing=dp(8),
            padding=[dp(16), dp(10), dp(16), dp(10)],
        )
        err_lbl = Label(
            text=f"Could not load conversation.\n{err_text}",
            font_size="12sp",
            color=(1, 0.4, 0.4, 1),
            halign="center",
        )
        err_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        err_box.add_widget(err_lbl)

        retry_btn = Button(
            text="Tap to Retry",
            size_hint=(None, None),
            size=(dp(130), dp(34)),
            pos_hint={"center_x": 0.5},
            background_normal="",
            background_color=PRIMARY_BLUE,
            color=(1, 1, 1, 1),
        )
        retry_btn.bind(on_release=lambda x: self._load_initial_messages())
        err_box.add_widget(retry_btn)
        self.messages_box.add_widget(err_box)

    def _load_initial_messages(self):
        if not self.chat_summary:
            return

        self._show_loading()

        def _done(items: List[MessageItem], exc: Optional[Exception]):
            def _ui(dt):
                if exc:
                    self._render_error(str(exc))
                elif items:
                    # Sort chronological (oldest to newest)
                    self.messages = list(reversed(items))
                    self._render_messages()
                    # Scroll to bottom
                    Clock.schedule_once(lambda d: setattr(self.scroll, "scroll_y", 0), 0.1)
                else:
                    self.messages = []
                    self._render_messages()
            Clock.schedule_once(_ui, 0)

        self.client.load_messages(self.chat_summary.peer_id, limit=50, on_result=_done)

    def _load_earlier_messages(self):
        if not self.chat_summary or not self.messages or self._is_loading_earlier or not self._has_more_messages:
            return

        self._is_loading_earlier = True
        self.load_more_btn.text = "Loading earlier messages..."
        earliest_id = self.messages[0].id

        def _done(items: List[MessageItem], exc: Optional[Exception]):
            def _ui(dt):
                self._is_loading_earlier = False
                if items:
                    existing_ids = {m.id for m in self.messages}
                    new_items = [m for m in items if m.id not in existing_ids]
                    if new_items:
                        earlier_msgs = list(reversed(new_items))
                        self.messages = earlier_msgs + self.messages
                        self._render_messages()
                        self.load_more_btn.text = "Load Earlier Messages"
                    else:
                        self._has_more_messages = False
                        self.load_more_btn.text = "No earlier messages"
                else:
                    self._has_more_messages = False
                    self.load_more_btn.text = "No earlier messages"
            Clock.schedule_once(_ui, 0)

        self.client.load_messages(
            self.chat_summary.peer_id, limit=50, offset_id=earliest_id, on_result=_done
        )

    def _render_messages(self):
        self._clear_messages_view()
        if not self.messages:
            empty_lbl = Label(
                text="No messages in this conversation yet.",
                font_size="13sp",
                color=TEXT_SECONDARY,
                size_hint_y=None,
                height=dp(50),
                halign="center",
            )
            empty_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            self.messages_box.add_widget(empty_lbl)
            return

        is_group = (
            self.chat_summary.chat_type == ChatType.GROUP if self.chat_summary else False
        )
        for msg in self.messages:
            bubble = MessageBubbleWidget(
                message=msg,
                is_group=is_group,
                on_media_action_callback=self._handle_media_action,
            )
            self.messages_box.add_widget(bubble)

    def _handle_media_action(self, message: MessageItem, action: str):
        """Handle media download or viewing actions."""
        if not self.chat_summary:
            return

        if action == "download":
            message.is_downloading = True
            self._render_messages()

            def _on_download_complete(saved_path: Optional[str], exc: Optional[Exception]):
                def _ui(dt):
                    message.is_downloading = False
                    if saved_path and os.path.exists(saved_path):
                        message.local_media_path = saved_path
                    self._render_messages()
                Clock.schedule_once(_ui, 0)

            self.client.download_media(
                chat_id=self.chat_summary.peer_id,
                message_id=message.id,
                on_result=_on_download_complete,
            )
        elif action == "open":
            self._show_info_popup("Media Saved", f"File saved at:\n{message.local_media_path}")

    def _show_info_popup(self, title: str, message: str):
        content = BoxLayout(orientation="vertical", spacing=dp(10), padding=dp(12))
        lbl = Label(text=message, color=TEXT_PRIMARY, font_size="13sp", halign="center")
        lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        content.add_widget(lbl)
        ok_btn = Button(
            text="OK",
            size_hint_y=None,
            height=dp(36),
            background_normal="",
            background_color=PRIMARY_BLUE,
            color=(1, 1, 1, 1),
        )
        content.add_widget(ok_btn)
        popup = Popup(title=title, content=content, size_hint=(0.85, 0.35))
        ok_btn.bind(on_release=popup.dismiss)
        popup.open()

    def _show_upload_dialog(self):
        """Open dialog for selecting and uploading media/files."""
        if not self.chat_summary:
            return

        start_path = "/sdcard/Download"
        if not os.path.exists(start_path):
            start_path = "/sdcard"
        if not os.path.exists(start_path):
            start_path = os.path.expanduser("~")

        content = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))

        # Quick directory bar
        quick_dir_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(32), spacing=dp(6))
        for name, p in [("Downloads", "/sdcard/Download"), ("DCIM", "/sdcard/DCIM"), ("Internal", "/sdcard"), ("Home", os.path.expanduser("~"))]:
            if os.path.exists(p):
                btn = Button(
                    text=name,
                    size_hint=(None, 1),
                    width=dp(70),
                    background_normal="",
                    background_color=DARK_CARD,
                    font_size="11sp",
                )
                btn.bind(on_release=lambda inst, path=p: setattr(file_chooser, "path", path))
                quick_dir_box.add_widget(btn)
        content.add_widget(quick_dir_box)

        # File Chooser
        file_chooser = FileChooserListView(
            path=start_path,
            size_hint=(1, 0.55),
        )
        content.add_widget(file_chooser)

        # Selected Path TextInput
        path_input = TextInput(
            text="",
            hint_text="Or type/paste full file path...",
            multiline=False,
            size_hint_y=None,
            height=dp(36),
            background_normal="",
            background_color=DARK_CARD,
            foreground_color=TEXT_PRIMARY,
            font_size="12sp",
        )
        file_chooser.bind(selection=lambda inst, val: setattr(path_input, "text", val[0] if val else ""))
        content.add_widget(path_input)

        # Caption TextInput
        caption_input = TextInput(
            hint_text="Caption (optional)...",
            multiline=False,
            size_hint_y=None,
            height=dp(36),
            background_normal="",
            background_color=DARK_CARD,
            foreground_color=TEXT_PRIMARY,
            font_size="12sp",
        )
        content.add_widget(caption_input)

        # Status label
        status_lbl = Label(
            text="",
            size_hint_y=None,
            height=dp(18),
            color=TEXT_SECONDARY,
            font_size="11sp",
        )
        content.add_widget(status_lbl)

        # Action Buttons
        btn_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(38), spacing=dp(8))
        cancel_btn = Button(
            text="Cancel",
            background_normal="",
            background_color=DARK_CARD,
            color=TEXT_SECONDARY,
        )
        upload_btn = Button(
            text="Send / Upload",
            background_normal="",
            background_color=PRIMARY_BLUE,
            color=(1, 1, 1, 1),
            bold=True,
        )
        btn_box.add_widget(cancel_btn)
        btn_box.add_widget(upload_btn)
        content.add_widget(btn_box)

        popup = Popup(
            title="Upload Media or File",
            content=content,
            size_hint=(0.95, 0.85),
            auto_dismiss=False,
        )
        cancel_btn.bind(on_release=popup.dismiss)

        def _do_upload(inst):
            selected = path_input.text.strip()
            if not selected or not os.path.exists(selected):
                status_lbl.text = "Please select a valid existing file."
                status_lbl.color = (1, 0.4, 0.4, 1)
                return

            upload_btn.disabled = True
            upload_btn.text = "Uploading..."
            status_lbl.text = "Uploading file to Telegram..."
            status_lbl.color = PRIMARY_BLUE

            caption = caption_input.text.strip() or None
            reply_id = self.reply_to_item.id if self.reply_to_item else None

            def _on_uploaded(item: Optional[MessageItem], exc: Optional[Exception]):
                def _ui(dt):
                    if exc:
                        upload_btn.disabled = False
                        upload_btn.text = "Send / Upload"
                        status_lbl.text = f"Upload failed: {exc}"
                        status_lbl.color = (1, 0.4, 0.4, 1)
                    else:
                        popup.dismiss()
                        if item:
                            self.messages.append(item)
                            self._render_messages()
                            Clock.schedule_once(lambda d: setattr(self.scroll, "scroll_y", 0), 0.05)
                Clock.schedule_once(_ui, 0)

            self.client.send_file(
                chat_id=self.chat_summary.peer_id,
                file_path=selected,
                caption=caption,
                reply_to_msg_id=reply_id,
                on_result=_on_uploaded,
            )

        upload_btn.bind(on_release=_do_upload)
        popup.open()

    def _on_send_clicked(self, instance):
        text = self.message_input.text.strip()
        if not text or not self.chat_summary:
            return

        reply_id = self.reply_to_item.id if self.reply_to_item else None
        self.message_input.text = ""
        self._cancel_reply()

        def _sent(item: Optional[MessageItem], exc: Optional[Exception]):
            def _ui(dt):
                if item:
                    self.messages.append(item)
                    bubble = MessageBubbleWidget(
                        message=item,
                        is_group=self.chat_summary.chat_type == ChatType.GROUP,
                        on_media_action_callback=self._handle_media_action,
                    )
                    self.messages_box.add_widget(bubble)
                    # Scroll to bottom
                    Clock.schedule_once(lambda d: setattr(self.scroll, "scroll_y", 0), 0.05)
            Clock.schedule_once(_ui, 0)

        self.client.send_text_message(
            chat_id=self.chat_summary.peer_id,
            text=text,
            reply_to_msg_id=reply_id,
            on_result=_sent,
        )

    def _on_pin_header_clicked(self, instance):
        """Toggle custom pin directly from conversation header."""
        if not self.chat_summary:
            return
        is_user = self.chat_summary.chat_type == ChatType.PERSONAL
        now_pinned = self.pin_store.toggle_pin(
            peer_id=self.chat_summary.peer_id,
            title=self.chat_summary.title,
            username=self.chat_summary.username,
            is_user=is_user,
        )
        self.chat_summary.is_pinned_locally = now_pinned
        self.pin_btn.text = "★" if now_pinned else "☆"
        self.pin_btn.color = ACCENT_GOLD if now_pinned else TEXT_SECONDARY

    def _on_incoming_message(self, message: MessageItem):
        """Append incoming message if belonging to current chat."""
        if self.chat_summary and message.chat_id == self.chat_summary.peer_id:
            def _ui(dt):
                self.messages.append(message)
                bubble = MessageBubbleWidget(
                    message=message,
                    is_group=self.chat_summary.chat_type == ChatType.GROUP,
                    on_media_action_callback=self._handle_media_action,
                )
                self.messages_box.add_widget(bubble)
                Clock.schedule_once(lambda d: setattr(self.scroll, "scroll_y", 0), 0.05)
            Clock.schedule_once(_ui, 0)

    def _cancel_reply(self):
        self.reply_to_item = None
        self.reply_banner.height = 0
        self.reply_banner.opacity = 0

    def _on_back_pressed(self):
        self.chat_summary = None
        self._cancel_reply()
        if self.on_back_callback:
            self.on_back_callback()
