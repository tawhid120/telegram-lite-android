"""
API Credentials Setup Screen for Telegram Lite.
Allows the user to safely provide their Telegram MTProto API ID and API Hash from my.telegram.org.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp

from app.ui_constants import (
    DARK_BG,
    DARK_CARD,
    DARK_BORDER,
    PRIMARY_BLUE,
    PRIMARY_BLUE_DARK,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    ACCENT_RED,
    ACCENT_GOLD,
)
from app.config import AppConfig


class ApiSetupScreen(Screen):
    """
    Setup screen displayed when no API credentials are found in the environment or storage.
    """

    def __init__(self, app_config: AppConfig, on_configured_callback, **kwargs):
        super().__init__(**kwargs)
        self.app_config = app_config
        self.on_configured_callback = on_configured_callback

        with self.canvas.before:
            Color(*DARK_BG)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        self._build_ui()

    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def _build_ui(self):
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        container = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=[dp(20), dp(32), dp(20), dp(32)],
            spacing=dp(16),
        )
        container.bind(minimum_height=container.setter("height"))

        # App Icon & Title
        title_box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(90), spacing=dp(6))
        title = Label(
            text="Telegram Lite",
            font_size="24sp",
            bold=True,
            color=PRIMARY_BLUE,
            halign="center",
        )
        subtitle = Label(
            text="MTProto Client Setup for Android Go",
            font_size="13sp",
            color=TEXT_SECONDARY,
            halign="center",
        )
        title_box.add_widget(title)
        title_box.add_widget(subtitle)
        container.add_widget(title_box)

        # Instructions Card
        card = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(110),
            padding=[dp(12), dp(10), dp(12), dp(10)],
            spacing=dp(6),
        )
        with card.canvas.before:
            Color(*DARK_CARD)
            self.card_bg = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(8)])
            Color(*DARK_BORDER)
            self.card_border = RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(8)])
        card.bind(pos=lambda inst, val: self._update_card(inst), size=lambda inst, val: self._update_card(inst))

        card_info = Label(
            text=(
                "To connect directly to Telegram MTProto, enter your App API ID and API Hash "
                "from https://my.telegram.org.\n"
                "• Credentials are saved strictly on this device.\n"
                "• Never share your credentials or session files."
            ),
            font_size="12sp",
            color=TEXT_PRIMARY,
            halign="left",
            valign="middle",
        )
        card_info.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        card.add_widget(card_info)
        container.add_widget(card)

        # Error label
        self.error_label = Label(
            text="",
            font_size="12sp",
            color=ACCENT_RED,
            size_hint_y=None,
            height=dp(20),
            halign="center",
        )
        container.add_widget(self.error_label)

        # Form Fields
        # API ID
        container.add_widget(
            Label(
                text="API ID (Integer):",
                font_size="13sp",
                bold=True,
                color=TEXT_PRIMARY,
                size_hint_y=None,
                height=dp(20),
                halign="left",
            )
        )
        self.api_id_input = TextInput(
            hint_text="e.g. 12345678",
            multiline=False,
            size_hint_y=None,
            height=dp(44),
            background_normal="",
            background_color=DARK_CARD,
            foreground_color=TEXT_PRIMARY,
            cursor_color=PRIMARY_BLUE,
            padding=[dp(10), dp(10), dp(10), dp(10)],
            input_filter="int",
        )
        container.add_widget(self.api_id_input)

        # API HASH
        container.add_widget(
            Label(
                text="API HASH (32 Hex Characters):",
                font_size="13sp",
                bold=True,
                color=TEXT_PRIMARY,
                size_hint_y=None,
                height=dp(20),
                halign="left",
            )
        )
        self.api_hash_input = TextInput(
            hint_text="e.g. 0123456789abcdef0123456789abcdef",
            multiline=False,
            size_hint_y=None,
            height=dp(44),
            background_normal="",
            background_color=DARK_CARD,
            foreground_color=TEXT_PRIMARY,
            cursor_color=PRIMARY_BLUE,
            padding=[dp(10), dp(10), dp(10), dp(10)],
        )
        container.add_widget(self.api_hash_input)

        # Save Button
        self.save_btn = Button(
            text="Save & Continue",
            bold=True,
            font_size="15sp",
            size_hint_y=None,
            height=dp(48),
            background_normal="",
            background_color=PRIMARY_BLUE,
            color=(1, 1, 1, 1),
        )
        self.save_btn.bind(on_release=self._on_save_clicked)
        container.add_widget(self.save_btn)

        scroll.add_widget(container)
        self.add_widget(scroll)

    def _update_card(self, instance):
        if hasattr(self, "card_bg"):
            self.card_bg.pos = instance.pos
            self.card_bg.size = instance.size
            self.card_border.pos = instance.pos
            self.card_border.size = instance.size

    def _on_save_clicked(self, instance):
        api_id_val = self.api_id_input.text.strip()
        api_hash_val = self.api_hash_input.text.strip()

        if not api_id_val or not api_hash_val:
            self.error_label.text = "Please enter both API ID and API Hash."
            return

        try:
            val_id = int(api_id_val)
        except ValueError:
            self.error_label.text = "API ID must be a valid number."
            return

        if not self.app_config.validate_credentials(val_id, api_hash_val):
            self.error_label.text = "Invalid credentials format. Please verify."
            return

        saved = self.app_config.save_api_credentials(val_id, api_hash_val)
        if saved:
            self.error_label.text = ""
            if self.on_configured_callback:
                self.on_configured_callback(val_id, api_hash_val)
        else:
            self.error_label.text = "Failed to write credentials to secure store."
