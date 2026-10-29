"""
Main Chats Screen for Telegram Lite.
Implements:
1. Four tab filters: All, Personal, Groups, Channels (instant in-memory filtering)
2. Custom Important Contacts / Pinned Chats Section (pins A, B, C locally via PinStore)
3. Live conversation list with unread badges, timestamps, previews
4. Debounced search across conversations
5. Low-RAM optimizations for Android Go
"""

from typing import List, Callable, Optional
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
    PRIMARY_BLUE_DARK,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_MUTED,
    ACCENT_GOLD,
)
from telegram_client.client_wrapper import TelegramClientWrapper
from telegram_client.models import ChatSummary, ChatType
from storage.pin_store import PinStore, PinnedContact
from app.components.chat_item import ChatItemWidget
from app.components.pinned_section import PinnedSectionWidget
from app.components.status_bar import StatusBarWidget


class ChatsScreen(Screen):
    """
    Primary chats overview screen.
    """

    def __init__(
        self,
        client_wrapper: TelegramClientWrapper,
        pin_store: PinStore,
        on_chat_selected_callback: Callable[[ChatSummary], None],
        on_settings_clicked_callback: Callable[[], None],
        **kwargs
    ):
        super().__init__(**kwargs)
        self.client = client_wrapper
        self.pin_store = pin_store
        self.on_chat_selected_callback = on_chat_selected_callback
        self.on_settings_clicked_callback = on_settings_clicked_callback

        self.current_filter = ChatType.ALL
        self.search_query = ""
        self._search_debounce_event = None

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

        # 1. Top Header Bar: App branding, Search toggle, Settings button
        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(52),
            padding=[dp(14), dp(6), dp(10), dp(6)],
            spacing=dp(10),
        )
        with header.canvas.before:
            Color(*DARK_SURFACE)
            self.header_bg = RoundedRectangle(pos=header.pos, size=header.size)
        header.bind(
            pos=lambda inst, val: setattr(self.header_bg, "pos", val),
            size=lambda inst, val: setattr(self.header_bg, "size", val),
        )

        app_title = Label(
            text="Telegram Lite",
            font_size="18sp",
            bold=True,
            color=PRIMARY_BLUE,
            halign="left",
            size_hint_x=0.55,
        )
        app_title.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        header.add_widget(app_title)

        # Refresh button
        self.refresh_btn = Button(
            text="🔄",
            font_size="16sp",
            size_hint=(None, 1),
            width=dp(38),
            background_normal="",
            background_color=(0, 0, 0, 0),
            color=TEXT_PRIMARY,
        )
        self.refresh_btn.bind(on_release=lambda x: self.load_dialogs())
        header.add_widget(self.refresh_btn)

        # Settings button
        self.settings_btn = Button(
            text="⚙",
            font_size="18sp",
            size_hint=(None, 1),
            width=dp(38),
            background_normal="",
            background_color=(0, 0, 0, 0),
            color=TEXT_PRIMARY,
        )
        self.settings_btn.bind(on_release=lambda x: self.on_settings_clicked_callback())
        header.add_widget(self.settings_btn)

        root.add_widget(header)

        # 2. Status Banner (Network/Flood)
        self.status_bar = StatusBarWidget()
        root.add_widget(self.status_bar)

        # 3. Search Bar
        search_box = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(40),
            padding=[dp(12), dp(4), dp(12), dp(4)],
        )
        self.search_input = TextInput(
            hint_text="Search chats or contacts...",
            multiline=False,
            size_hint=(1, 1),
            font_size="13sp",
            background_normal="",
            background_color=DARK_CARD,
            foreground_color=TEXT_PRIMARY,
            cursor_color=PRIMARY_BLUE,
            padding=[dp(10), dp(6), dp(10), dp(6)],
        )
        self.search_input.bind(text=self._on_search_text_changed)
        search_box.add_widget(self.search_input)
        root.add_widget(search_box)

        # 4. Tab Navigation: [All] [Personal] [Groups] [Channels]
        tabs_box = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(38),
            padding=[dp(8), dp(2), dp(8), dp(2)],
            spacing=dp(6),
        )
        self.tab_buttons: dict[ChatType, Button] = {}
        for tab_type, tab_label in [
            (ChatType.ALL, "All"),
            (ChatType.PERSONAL, "Personal"),
            (ChatType.GROUP, "Groups"),
            (ChatType.CHANNEL, "Channels"),
        ]:
            btn = Button(
                text=tab_label,
                font_size="13sp",
                bold=True,
                background_normal="",
                background_color=PRIMARY_BLUE if tab_type == self.current_filter else DARK_CARD,
                color=(1, 1, 1, 1) if tab_type == self.current_filter else TEXT_SECONDARY,
            )
            btn.bind(on_release=lambda inst, t=tab_type: self.select_tab(t))
            self.tab_buttons[tab_type] = btn
            tabs_box.add_widget(btn)

        root.add_widget(tabs_box)

        # 5. Dedicated Important Contacts Section (Pinned contacts A, B, C)
        self.pinned_section = PinnedSectionWidget(
            on_contact_selected=self._on_pinned_contact_selected
        )
        root.add_widget(self.pinned_section)

        # 6. Scrollable Chat List Container
        self.scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.chat_list_box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(4),
            padding=[dp(8), dp(4), dp(8), dp(8)],
        )
        self.chat_list_box.bind(minimum_height=self.chat_list_box.setter("height"))
        self.scroll.add_widget(self.chat_list_box)
        root.add_widget(self.scroll)

        self.add_widget(root)

        # Register message listener for real-time list update
        self.client.add_message_listener(self._on_new_message_arrived)

    def select_tab(self, tab_type: ChatType) -> None:
        """
        Instant tab filter switch.
        Zero network latency; filters cached summaries in-memory.
        """
        self.current_filter = tab_type
        for t_type, btn in self.tab_buttons.items():
            if t_type == tab_type:
                btn.background_color = PRIMARY_BLUE
                btn.color = (1, 1, 1, 1)
            else:
                btn.background_color = DARK_CARD
                btn.color = TEXT_SECONDARY

        # Show pinned section only on ALL and PERSONAL tabs
        if tab_type in (ChatType.ALL, ChatType.PERSONAL):
            pinned_contacts = self.pin_store.get_pinned_chats()
            self.pinned_section.update_pinned_contacts(pinned_contacts)
        else:
            self.pinned_section.update_pinned_contacts([])

        self.render_conversations()

    def load_dialogs(self) -> None:
        """Fetch conversations from MTProto server."""
        self.refresh_btn.disabled = True

        def _on_done(summaries: List[ChatSummary], exc: Optional[Exception]):
            def _ui(dt):
                self.refresh_btn.disabled = False
                if exc:
                    self.status_bar.show_reconnecting()
                else:
                    self.status_bar.hide()
                    self.refresh_pinned_section()
                    self.render_conversations()

            Clock.schedule_once(_ui, 0)

        self.client.load_conversations(limit=40, on_result=_on_done)

    def refresh_pinned_section(self) -> None:
        """Reload custom pinned contacts from SQLite storage."""
        if self.current_filter in (ChatType.ALL, ChatType.PERSONAL):
            pinned = self.pin_store.get_pinned_chats()
            self.pinned_section.update_pinned_contacts(pinned)
        else:
            self.pinned_section.update_pinned_contacts([])

    def render_conversations(self) -> None:
        """Render the list of conversations based on current tab filter and search query."""
        self.chat_list_box.clear_widgets()

        summaries = self.client.filter_cached_conversations(self.current_filter)

        # Apply search filter if query is present
        if self.search_query:
            q = self.search_query.lower()
            summaries = [
                s for s in summaries
                if q in s.title.lower() or (s.username and q in s.username.lower()) or q in s.last_message_text.lower()
            ]

        if not summaries:
            empty_lbl = Label(
                text=f"No conversations in {self.current_filter.value.title()}",
                color=TEXT_MUTED,
                font_size="14sp",
                size_hint_y=None,
                height=dp(100),
                halign="center",
            )
            self.chat_list_box.add_widget(empty_lbl)
            return

        for summary in summaries:
            widget = ChatItemWidget(
                summary=summary,
                on_click_callback=self._on_chat_clicked,
                on_pin_toggle_callback=self._on_pin_toggled,
            )
            self.chat_list_box.add_widget(widget)

    def _on_chat_clicked(self, summary: ChatSummary) -> None:
        if self.on_chat_selected_callback:
            self.on_chat_selected_callback(summary)

    def _on_pinned_contact_selected(self, contact: PinnedContact) -> None:
        """Handle tap on a contact badge in the Important Contacts section."""
        # Find matching ChatSummary or construct one
        matching = next(
            (c for c in self.client._cached_summaries if c.peer_id == contact.peer_id),
            None,
        )
        if not matching:
            matching = ChatSummary(
                peer_id=contact.peer_id,
                title=contact.title,
                chat_type=ChatType.PERSONAL if contact.is_user else ChatType.GROUP,
                username=contact.username,
                is_pinned_locally=True,
            )
        if self.on_chat_selected_callback:
            self.on_chat_selected_callback(matching)

    def _on_pin_toggled(self, summary: ChatSummary) -> None:
        """
        Toggle custom pin state for a conversation.
        Persists into local SQLite PinStore without sending any network request to Telegram.
        """
        is_user = summary.chat_type == ChatType.PERSONAL
        now_pinned = self.pin_store.toggle_pin(
            peer_id=summary.peer_id,
            title=summary.title,
            username=summary.username,
            is_user=is_user,
        )
        summary.is_pinned_locally = now_pinned
        self.refresh_pinned_section()
        self.render_conversations()

    def _on_search_text_changed(self, instance, text: str) -> None:
        """Debounced search to save CPU cycles on Android Go."""
        if self._search_debounce_event:
            self._search_debounce_event.cancel()

        def _do_search(dt):
            self.search_query = text.strip()
            self.render_conversations()

        self._search_debounce_event = Clock.schedule_once(_do_search, 0.25)

    def _on_new_message_arrived(self, message) -> None:
        """Update conversation list item when a new message arrives."""
        Clock.schedule_once(lambda dt: self.load_dialogs(), 0)
