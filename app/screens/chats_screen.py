"""
Main Chats Screen for Telegram Lite.
Implements:
1. Dynamic Telegram Chat Folders (fetched directly from user's Telegram account)
2. Horizontally scrollable folder tabs
3. Chat pagination and infinite scroll ("Load More Chats")
4. Custom Important Contacts / Pinned Chats Section (pins A, B, C locally via PinStore)
5. Live conversation list with unread badges, timestamps, previews
6. Debounced search across conversations
7. Low-RAM optimizations for Android Go
"""

from typing import List, Callable, Optional, Any
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
from telegram_client.models import ChatSummary, ChatType, ChatFolder
from storage.pin_store import PinStore, PinnedContact
from app.components.chat_item import ChatItemWidget
from app.components.pinned_section import PinnedSectionWidget
from app.components.status_bar import StatusBarWidget


class ChatsScreen(Screen):
    """
    Primary chats overview screen with real Telegram chat folders and paginated chats.
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
        self.current_folder: Optional[ChatFolder] = None
        self.folder_tab_buttons: dict[Any, Button] = {}
        self.tab_buttons: dict[Any, Button] = {}
        self.search_query = ""
        self._search_debounce_event = None
        self._is_loading_more_chats = False
        self._has_more_chats = True

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

        # 1. Top Header Bar: App branding, Refresh button, Settings button
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

        # 4. Horizontally Scrollable Dynamic Folder Navigation
        self.tabs_scroll = ScrollView(
            size_hint=(1, None),
            height=dp(42),
            do_scroll_x=True,
            do_scroll_y=False,
            bar_color=(0, 0, 0, 0),
            bar_inactive_color=(0, 0, 0, 0),
        )
        self.tabs_box = BoxLayout(
            orientation="horizontal",
            size_hint=(None, 1),
            padding=[dp(8), dp(3), dp(8), dp(3)],
            spacing=dp(6),
        )
        self.tabs_box.bind(minimum_width=self.tabs_box.setter("width"))
        self.tabs_scroll.add_widget(self.tabs_box)
        root.add_widget(self.tabs_scroll)
        self._rebuild_folder_tabs()

        # 5. Dedicated Important Contacts Section (Pinned contacts A, B, C)
        self.pinned_section = PinnedSectionWidget(
            on_contact_selected=self._on_pinned_contact_selected
        )
        root.add_widget(self.pinned_section)

        # 6. Scrollable Chat List Container with auto-pagination
        self.scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.scroll.bind(scroll_y=self._on_chat_scroll)
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

    def _rebuild_folder_tabs(self):
        """Build dynamic tabs for user's real Telegram chat folders."""
        self.tabs_box.clear_widgets()
        self.folder_tab_buttons.clear()
        self.tab_buttons.clear()

        # 'All' tab is always the first tab
        all_btn = Button(
            text="All",
            font_size="13sp",
            bold=True,
            size_hint=(None, 1),
            width=dp(64),
            background_normal="",
            background_color=PRIMARY_BLUE if (self.current_folder is None and self.current_filter == ChatType.ALL) else DARK_CARD,
            color=(1, 1, 1, 1) if (self.current_folder is None and self.current_filter == ChatType.ALL) else TEXT_SECONDARY,
        )
        all_btn.bind(on_release=lambda inst: self.select_folder(None))
        self.folder_tab_buttons[None] = all_btn
        self.tab_buttons[ChatType.ALL] = all_btn
        self.tabs_box.add_widget(all_btn)

        # Real Telegram Account folders
        user_folders = getattr(self.client, "_cached_folders", [])
        if user_folders:
            for folder in user_folders:
                tab_title = f"{folder.emoticon} {folder.title}" if folder.emoticon else folder.title
                btn_w = max(dp(72), dp(len(tab_title) * 9 + 26))
                is_selected = (self.current_folder and self.current_folder.id == folder.id)
                btn = Button(
                    text=tab_title,
                    font_size="13sp",
                    bold=True,
                    size_hint=(None, 1),
                    width=btn_w,
                    background_normal="",
                    background_color=PRIMARY_BLUE if is_selected else DARK_CARD,
                    color=(1, 1, 1, 1) if is_selected else TEXT_SECONDARY,
                )
                btn.bind(on_release=lambda inst, f=folder: self.select_folder(f))
                self.folder_tab_buttons[folder.id] = btn
                self.tabs_box.add_widget(btn)
        else:
            # Fallback only when account has zero custom folders configured
            for fb_type, fb_label in [
                (ChatType.PERSONAL, "Personal"),
                (ChatType.GROUP, "Groups"),
                (ChatType.CHANNEL, "Channels"),
            ]:
                is_sel = (self.current_filter == fb_type and self.current_folder is None)
                btn = Button(
                    text=fb_label,
                    font_size="13sp",
                    bold=True,
                    size_hint=(None, 1),
                    width=dp(80),
                    background_normal="",
                    background_color=PRIMARY_BLUE if is_sel else DARK_CARD,
                    color=(1, 1, 1, 1) if is_sel else TEXT_SECONDARY,
                )
                btn.bind(on_release=lambda inst, t=fb_type: self.select_tab(t))
                self.folder_tab_buttons[fb_type] = btn
                self.tab_buttons[fb_type] = btn
                self.tabs_box.add_widget(btn)

    def select_folder(self, folder: Optional[ChatFolder]) -> None:
        """
        Instant folder switch based on real Telegram account folders.
        Zero network reload; filters cached dialogs in-memory.
        """
        self.current_folder = folder
        self.current_filter = ChatType.ALL

        for fid, btn in self.folder_tab_buttons.items():
            if (folder is None and fid is None) or (folder and fid == folder.id):
                btn.background_color = PRIMARY_BLUE
                btn.color = (1, 1, 1, 1)
            else:
                btn.background_color = DARK_CARD
                btn.color = TEXT_SECONDARY

        # Show pinned carousel on All tab
        if folder is None:
            pinned_contacts = self.pin_store.get_pinned_chats()
            self.pinned_section.update_pinned_contacts(pinned_contacts)
        else:
            self.pinned_section.update_pinned_contacts([])

        self.render_conversations()

    def select_tab(self, tab_type: ChatType) -> None:
        """
        Fallback tab selector for backward compatibility.
        """
        self.current_filter = tab_type
        self.current_folder = None
        for key, btn in self.folder_tab_buttons.items():
            if key == tab_type or (tab_type == ChatType.ALL and key is None):
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
        """Fetch conversations and real Telegram chat folders from MTProto server."""
        self.refresh_btn.disabled = True
        self._has_more_chats = True

        def _on_folders_done(folders: List[ChatFolder], exc: Optional[Exception]):
            def _ui_folders(dt):
                self._rebuild_folder_tabs()
            Clock.schedule_once(_ui_folders, 0)

        # Load real Telegram account chat folders
        if hasattr(self.client, "load_chat_folders"):
            self.client.load_chat_folders(on_result=_on_folders_done)

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

        self.client.load_conversations(limit=50, on_result=_on_done)

    def _on_chat_scroll(self, instance, val):
        """Auto load more chats when user reaches bottom of chat list."""
        if val <= 0.05 and not self._is_loading_more_chats and self._has_more_chats:
            self._load_more_chats()

    def _load_more_chats(self):
        """Fetch next page of dialogs and append."""
        if self._is_loading_more_chats or not self._has_more_chats:
            return
        self._is_loading_more_chats = True
        self.render_conversations()

        def _on_more_done(summaries: List[ChatSummary], exc: Optional[Exception]):
            def _ui(dt):
                self._is_loading_more_chats = False
                prev_count = len(self.client._cached_summaries)
                if exc or not summaries or len(summaries) <= prev_count:
                    self._has_more_chats = False
                self.render_conversations()
            Clock.schedule_once(_ui, 0)

        self.client.load_more_conversations(limit=40, on_result=_on_more_done)

    def refresh_pinned_section(self) -> None:
        """Reload custom pinned contacts from SQLite storage."""
        if (self.current_folder is None) and self.current_filter in (ChatType.ALL, ChatType.PERSONAL):
            pinned = self.pin_store.get_pinned_chats()
            self.pinned_section.update_pinned_contacts(pinned)
        else:
            self.pinned_section.update_pinned_contacts([])

    def render_conversations(self) -> None:
        """Render the list of conversations based on current folder/tab filter and search query."""
        self.chat_list_box.clear_widgets()

        if self.current_folder is not None and hasattr(self.client, "filter_conversations_by_folder"):
            summaries = self.client.filter_conversations_by_folder(self.current_folder)
        else:
            summaries = self.client.filter_cached_conversations(self.current_filter)

        # Apply search filter if query is present
        if self.search_query:
            q = self.search_query.lower()
            summaries = [
                s for s in summaries
                if q in s.title.lower() or (s.username and q in s.username.lower()) or q in s.last_message_text.lower()
            ]

        if not summaries:
            folder_title = self.current_folder.title if self.current_folder else self.current_filter.value.title()
            empty_lbl = Label(
                text=f"No conversations in {folder_title}",
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

        # 'Load More Chats' pagination button at bottom of list
        if self._has_more_chats and not self.search_query:
            btn_text = "⏳ Loading more chats..." if self._is_loading_more_chats else "Load More Chats"
            more_btn = Button(
                text=btn_text,
                size_hint_y=None,
                height=dp(38),
                background_normal="",
                background_color=DARK_CARD,
                color=PRIMARY_BLUE,
                font_size="13sp",
                bold=True,
                disabled=self._is_loading_more_chats,
            )
            more_btn.bind(on_release=lambda x: self._load_more_chats())
            self.chat_list_box.add_widget(more_btn)

    def _on_chat_clicked(self, summary: ChatSummary) -> None:
        if self.on_chat_selected_callback:
            self.on_chat_selected_callback(summary)

    def _on_pinned_contact_selected(self, contact: PinnedContact) -> None:
        """Handle tap on a contact badge in the Important Contacts section."""
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
