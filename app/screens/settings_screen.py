"""
Settings, Performance Tuning & Account Screen for Telegram Lite.
Implements:
1. Low-Resource Mode toggle (Android Go RAM saver)
2. Cache footprint display & cache purge
3. Custom Pinned Contacts management
4. Secure Logout with confirmation modal
"""

from typing import Callable
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.switch import Switch
from kivy.uix.popup import Popup
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
    ACCENT_RED,
    ACCENT_GOLD,
)
from telegram_client.client_wrapper import TelegramClientWrapper
from storage.pin_store import PinStore
from storage.cache_manager import CacheManager
from app.config import AppConfig


class SettingsScreen(Screen):
    """
    Settings, cache management, and account settings.
    """

    def __init__(
        self,
        client_wrapper: TelegramClientWrapper,
        pin_store: PinStore,
        cache_manager: CacheManager,
        app_config: AppConfig,
        on_back_callback: Callable[[], None],
        on_logout_callback: Callable[[], None],
        **kwargs
    ):
        super().__init__(**kwargs)
        self.client = client_wrapper
        self.pin_store = pin_store
        self.cache_manager = cache_manager
        self.app_config = app_config
        self.on_back_callback = on_back_callback
        self.on_logout_callback = on_logout_callback

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

        # Header Bar
        header = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(52),
            padding=[dp(6), dp(6), dp(10), dp(6)],
            spacing=dp(8),
        )
        with header.canvas.before:
            Color(*DARK_SURFACE)
            self.header_bg = RoundedRectangle(pos=header.pos, size=header.size)
        header.bind(
            pos=lambda inst, val: setattr(self.header_bg, "pos", val),
            size=lambda inst, val: setattr(self.header_bg, "size", val),
        )

        back_btn = Button(
            text="←",
            font_size="20sp",
            bold=True,
            size_hint=(None, 1),
            width=dp(38),
            background_normal="",
            background_color=(0, 0, 0, 0),
            color=TEXT_PRIMARY,
        )
        back_btn.bind(on_release=lambda x: self.on_back_callback())
        header.add_widget(back_btn)

        title = Label(
            text="Settings & Profile",
            font_size="16sp",
            bold=True,
            color=TEXT_PRIMARY,
            halign="left",
        )
        title.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        header.add_widget(title)
        root.add_widget(header)

        # Scrollable Settings Container
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        self.content = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=[dp(14), dp(12), dp(14), dp(16)],
            spacing=dp(14),
        )
        self.content.bind(minimum_height=self.content.setter("height"))

        # 1. Profile Card
        self.profile_card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(80),
            padding=[dp(12), dp(10), dp(12), dp(10)],
            spacing=dp(4),
        )
        with self.profile_card.canvas.before:
            Color(*DARK_CARD)
            self.p_bg = RoundedRectangle(pos=self.profile_card.pos, size=self.profile_card.size, radius=[dp(8)])
        self.profile_card.bind(
            pos=lambda inst, val: setattr(self.p_bg, "pos", val),
            size=lambda inst, val: setattr(self.p_bg, "size", val),
        )

        self.user_name_lbl = Label(
            text="User Profile",
            font_size="16sp",
            bold=True,
            color=TEXT_PRIMARY,
            halign="left",
        )
        self.user_name_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        self.user_details_lbl = Label(
            text="Telegram Session Connected",
            font_size="12sp",
            color=TEXT_SECONDARY,
            halign="left",
        )
        self.user_details_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))

        self.profile_card.add_widget(self.user_name_lbl)
        self.profile_card.add_widget(self.user_details_lbl)
        self.content.add_widget(self.profile_card)

        # 2. Performance & Low-RAM Mode Section
        self._add_section_header("PERFORMANCE (ANDROID GO)")
        perf_card = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(54),
            padding=[dp(12), dp(8), dp(12), dp(8)],
        )
        with perf_card.canvas.before:
            Color(*DARK_CARD)
            p_rect = RoundedRectangle(pos=perf_card.pos, size=perf_card.size, radius=[dp(8)])
        perf_card.bind(
            pos=lambda inst, val: setattr(p_rect, "pos", val),
            size=lambda inst, val: setattr(p_rect, "size", val),
        )

        perf_label_box = BoxLayout(orientation="vertical")
        perf_title = Label(
            text="Low-Resource Mode",
            font_size="14sp",
            bold=True,
            color=TEXT_PRIMARY,
            halign="left",
        )
        perf_title.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        perf_sub = Label(
            text="Reduces RAM & limits avatar caching",
            font_size="11sp",
            color=TEXT_SECONDARY,
            halign="left",
        )
        perf_sub.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        perf_label_box.add_widget(perf_title)
        perf_label_box.add_widget(perf_sub)
        perf_card.add_widget(perf_label_box)

        self.low_ram_switch = Switch(active=self.cache_manager.low_resource_mode, size_hint=(None, 1), width=dp(60))
        self.low_ram_switch.bind(active=self._on_low_ram_toggled)
        perf_card.add_widget(self.low_ram_switch)
        self.content.add_widget(perf_card)

        # 3. Storage & Cache Section
        self._add_section_header("LOCAL STORAGE")
        cache_card = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(54),
            padding=[dp(12), dp(8), dp(12), dp(8)],
        )
        with cache_card.canvas.before:
            Color(*DARK_CARD)
            c_rect = RoundedRectangle(pos=cache_card.pos, size=cache_card.size, radius=[dp(8)])
        cache_card.bind(
            pos=lambda inst, val: setattr(c_rect, "pos", val),
            size=lambda inst, val: setattr(c_rect, "size", val),
        )

        self.cache_size_lbl = Label(
            text="Calculating cache...",
            font_size="13sp",
            color=TEXT_PRIMARY,
            halign="left",
        )
        self.cache_size_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        cache_card.add_widget(self.cache_size_lbl)

        clear_cache_btn = Button(
            text="Clear Cache",
            font_size="12sp",
            bold=True,
            size_hint=(None, 1),
            width=dp(94),
            background_normal="",
            background_color=DARK_BORDER,
            color=TEXT_PRIMARY,
        )
        clear_cache_btn.bind(on_release=self._on_clear_cache_clicked)
        cache_card.add_widget(clear_cache_btn)
        self.content.add_widget(cache_card)

        # 4. Custom Pinned Contacts Manager Section
        self._add_section_header("CUSTOM PINNED CONTACTS")
        self.pins_container = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(6),
        )
        self.pins_container.bind(minimum_height=self.pins_container.setter("height"))
        self.content.add_widget(self.pins_container)

        # 5. About & Security Section
        self._add_section_header("ABOUT & SECURITY")
        about_card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(70),
            padding=[dp(12), dp(8), dp(12), dp(8)],
            spacing=dp(2),
        )
        with about_card.canvas.before:
            Color(*DARK_CARD)
            a_rect = RoundedRectangle(pos=about_card.pos, size=about_card.size, radius=[dp(8)])
        about_card.bind(
            pos=lambda inst, val: setattr(a_rect, "pos", val),
            size=lambda inst, val: setattr(a_rect, "size", val),
        )
        app_ver = Label(
            text="Telegram Lite v0.1.0 (Android Go Edition)",
            font_size="13sp",
            bold=True,
            color=TEXT_PRIMARY,
            halign="left",
        )
        app_ver.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        sec_info = Label(
            text="Official MTProto direct connection • Android Keystore protected",
            font_size="11sp",
            color=TEXT_SECONDARY,
            halign="left",
        )
        sec_info.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        about_card.add_widget(app_ver)
        about_card.add_widget(sec_info)
        self.content.add_widget(about_card)

        # 6. Logout Button
        self.logout_btn = Button(
            text="Log Out of Telegram",
            font_size="14sp",
            bold=True,
            size_hint_y=None,
            height=dp(46),
            background_normal="",
            background_color=ACCENT_RED,
            color=(1, 1, 1, 1),
        )
        self.logout_btn.bind(on_release=self._confirm_logout)
        self.content.add_widget(self.logout_btn)

        scroll.add_widget(self.content)
        root.add_widget(scroll)
        self.add_widget(root)

    def on_pre_enter(self, *args):
        """Update views when entering screen."""
        self._refresh_profile()
        self._refresh_cache_size()
        self._render_pinned_contacts_list()

    def _add_section_header(self, title: str):
        lbl = Label(
            text=title,
            font_size="11sp",
            bold=True,
            color=TEXT_SECONDARY,
            halign="left",
            size_hint_y=None,
            height=dp(22),
        )
        lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        self.content.add_widget(lbl)

    def _refresh_profile(self):
        user = self.client.auth_handler.current_user
        if user:
            self.user_name_lbl.text = user.full_name
            sub = f"@{user.username}" if user.username else ""
            if user.phone:
                sub += f" • {user.phone}"
            self.user_details_lbl.text = sub or "Active Session"
        else:
            self.user_name_lbl.text = "Active Session"
            self.user_details_lbl.text = "Connected via MTProto"

    def _refresh_cache_size(self):
        sz = self.cache_manager.get_total_cache_size_bytes()
        mb = sz / (1024 * 1024)
        self.cache_size_lbl.text = f"Cache size: {mb:.2f} MB"

    def _on_low_ram_toggled(self, instance, active: bool):
        self.cache_manager.low_resource_mode = active
        self._refresh_cache_size()

    def _on_clear_cache_clicked(self, instance):
        self.cache_manager.clear_cache()
        self._refresh_cache_size()

    def _render_pinned_contacts_list(self):
        self.pins_container.clear_widgets()
        pinned = self.pin_store.get_pinned_chats()
        if not pinned:
            no_pins_lbl = Label(
                text="No contacts pinned. Tap the star (☆) in any chat to pin.",
                font_size="12sp",
                color=TEXT_SECONDARY,
                size_hint_y=None,
                height=dp(28),
                halign="left",
            )
            no_pins_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            self.pins_container.add_widget(no_pins_lbl)
            return

        for p in pinned:
            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(42),
                padding=[dp(10), dp(4), dp(10), dp(4)],
            )
            with row.canvas.before:
                Color(*DARK_CARD)
                r_rect = RoundedRectangle(pos=row.pos, size=row.size, radius=[dp(6)])
            row.bind(
                pos=lambda inst, val: setattr(r_rect, "pos", val),
                size=lambda inst, val: setattr(r_rect, "size", val),
            )

            p_lbl = Label(
                text=f"★ {p.title}",
                font_size="13sp",
                color=TEXT_PRIMARY,
                halign="left",
            )
            p_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            row.add_widget(p_lbl)

            unpin_btn = Button(
                text="Unpin",
                font_size="11sp",
                size_hint=(None, 1),
                width=dp(56),
                background_normal="",
                background_color=(0, 0, 0, 0),
                color=ACCENT_RED,
            )
            unpin_btn.bind(on_release=lambda inst, pid=p.peer_id: self._unpin_contact(pid))
            row.add_widget(unpin_btn)
            self.pins_container.add_widget(row)

    def _unpin_contact(self, peer_id: int):
        self.pin_store.unpin_chat(peer_id)
        self._render_pinned_contacts_list()

    def _confirm_logout(self, instance):
        """Display confirmation dialog before destroying session."""
        content = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(12))
        msg = Label(
            text="Are you sure you want to log out?\nThis will securely wipe all session credentials from this device.",
            font_size="13sp",
            color=TEXT_PRIMARY,
            halign="center",
        )
        msg.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        content.add_widget(msg)

        btns = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint_y=None, height=dp(42))
        cancel_btn = Button(
            text="Cancel",
            font_size="13sp",
            background_normal="",
            background_color=DARK_BORDER,
            color=TEXT_PRIMARY,
        )
        confirm_btn = Button(
            text="Log Out",
            font_size="13sp",
            bold=True,
            background_normal="",
            background_color=ACCENT_RED,
            color=(1, 1, 1, 1),
        )
        btns.add_widget(cancel_btn)
        btns.add_widget(confirm_btn)
        content.add_widget(btns)

        popup = Popup(
            title="Log Out Confirmation",
            content=content,
            size_hint=(0.85, None),
            height=dp(180),
            auto_dismiss=True,
        )
        cancel_btn.bind(on_release=popup.dismiss)

        def _do_logout(x):
            popup.dismiss()
            self._execute_logout()

        confirm_btn.bind(on_release=_do_logout)
        popup.open()

    def _execute_logout(self):
        def _on_lo(success: bool):
            Clock.schedule_once(lambda dt: self.on_logout_callback(), 0)

        self.client.logout(_on_lo)
