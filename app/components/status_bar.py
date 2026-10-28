"""
Network & Connectivity Status Banner for Telegram Lite.
Displays offline notices, reconnecting states, and flood wait countdowns.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp

from app.ui_constants import ACCENT_RED, ACCENT_GOLD, DARK_CARD, TEXT_PRIMARY


class StatusBarWidget(BoxLayout):
    """Notification bar displayed at the top or bottom of the screen."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = 0
        self.opacity = 0
        self.padding = [dp(12), dp(4), dp(12), dp(4)]

        with self.canvas.before:
            self.color_instruction = Color(*DARK_CARD)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        self.label = Label(
            text="",
            font_size="12sp",
            bold=True,
            color=TEXT_PRIMARY,
            halign="center",
            valign="middle",
        )
        self.label.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        self.add_widget(self.label)

    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def show_offline(self) -> None:
        self.color_instruction.rgba = ACCENT_RED
        self.label.text = "⚠️ Network unavailable. Working in offline mode."
        self.height = dp(28)
        self.opacity = 1

    def show_reconnecting(self) -> None:
        self.color_instruction.rgba = ACCENT_GOLD
        self.label.text = "🔄 Connecting to Telegram MTProto..."
        self.height = dp(28)
        self.opacity = 1

    def show_flood_wait(self, seconds: int) -> None:
        self.color_instruction.rgba = ACCENT_RED
        self.label.text = f"⏳ Telegram Rate Limit: Please wait {seconds}s..."
        self.height = dp(28)
        self.opacity = 1

    def hide(self) -> None:
        self.height = 0
        self.opacity = 0
