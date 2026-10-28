"""
Real Conversation Screen for Telegram Lite.
Implements:
1. Message history with pagination
2. Sender names, timestamps, incoming/outgoing bubbles
3. Text message composer with multiline input
4. Real-time incoming message updates
5. In-header Star / Pin toggle
"""

from typing import List, Optional, Callable
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
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
)
from telegram_client.client_wrapper import TelegramClientWrapper
from telegram_client.models import ChatSummary, MessageItem, ChatType
from storage.pin_store import PinStore
from app.components.message_bubble import MessageBubbleWidget


class ConversationScreen(Screen):
    """
    Active chat view displaying message history and composer.
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

        # 2. Messages Scroll Area
        self.scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
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

        # 4. Message Composer Bottom Bar
        composer = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(52),
            padding=[dp(8), dp(6), dp(8), dp(6)],
            spacing=dp(6),
        )
        with composer.canvas.before:
            Color(*DARK_SURFACE)
            self.composer_bg = RoundedRectangle(pos=composer.pos, size=composer.size)
        composer.bind(
            pos=lambda inst, val: setattr(self.composer_bg, "pos", val),
            size=lambda inst, val: setattr(self.composer_bg, "size", val),
        )

        self.message_input = TextInput(
            hint_text="Write a message...",
            multiline=True,
            size_hint=(0.85, 1),
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
            size_hint=(0.15, 1),
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

    def set_chat(self, chat_summary: ChatSummary) -> None:
        """Bind conversation screen to a specific chat."""
        self.chat_summary = chat_summary
        self.messages.clear()
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

    def _load_initial_messages(self):
        if not self.chat_summary:
            return

        def _done(items: List[MessageItem], exc: Optional[Exception]):
            def _ui(dt):
                if items:
                    # Sort chronological (oldest to newest)
                    self.messages = list(reversed(items))
                    self._render_messages()
                    # Scroll to bottom
                    Clock.schedule_once(lambda d: setattr(self.scroll, "scroll_y", 0), 0.1)
            Clock.schedule_once(_ui, 0)

        self.client.load_messages(self.chat_summary.peer_id, limit=30, on_result=_done)

    def _load_earlier_messages(self):
        if not self.chat_summary or not self.messages:
            return
        earliest_id = self.messages[0].id

        def _done(items: List[MessageItem], exc: Optional[Exception]):
            def _ui(dt):
                if items:
                    earlier_msgs = list(reversed(items))
                    self.messages = earlier_msgs + self.messages
                    self._render_messages()
            Clock.schedule_once(_ui, 0)

        self.client.load_messages(
            self.chat_summary.peer_id, limit=30, offset_id=earliest_id, on_result=_done
        )

    def _render_messages(self):
        self._clear_messages_view()
        is_group = (
            self.chat_summary.chat_type == ChatType.GROUP if self.chat_summary else False
        )
        for msg in self.messages:
            bubble = MessageBubbleWidget(message=msg, is_group=is_group)
            self.messages_box.add_widget(bubble)

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
