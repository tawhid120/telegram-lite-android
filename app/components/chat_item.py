"""
High-performance conversation row widget for low-RAM Android Go.
Uses lightweight canvas drawing and minimal nested widgets.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle, Ellipse
from kivy.metrics import dp

from app.ui_constants import (
    DARK_CARD,
    DARK_BORDER,
    PRIMARY_BLUE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    ACCENT_GOLD,
    BADGE_HEIGHT_DP,
)
from telegram_client.models import ChatSummary


class ChatItemWidget(BoxLayout):
    """
    A single conversation item in the chat list.
    Displays avatar initials, title, message preview, timestamp, unread badge, and pin star.
    """

    def __init__(
        self,
        summary: ChatSummary,
        on_click_callback,
        on_pin_toggle_callback,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.summary = summary
        self.on_click_callback = on_click_callback
        self.on_pin_toggle_callback = on_pin_toggle_callback

        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(68)
        self.padding = [dp(10), dp(8), dp(10), dp(8)]
        self.spacing = dp(12)

        # Background canvas
        with self.canvas.before:
            Color(*DARK_CARD)
            self.bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[dp(8)]
            )
            Color(*DARK_BORDER)
            self.border_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[dp(8)]
            )
        self.bind(pos=self._update_rect, size=self._update_rect)

        # 1. Avatar circle with initials
        self.avatar_box = BoxLayout(size_hint=(None, None), size=(dp(48), dp(48)))
        with self.avatar_box.canvas.before:
            Color(*PRIMARY_BLUE)
            self.avatar_circle = Ellipse(
                pos=self.avatar_box.pos, size=self.avatar_box.size
            )
        self.avatar_box.bind(
            pos=self._update_avatar_circle, size=self._update_avatar_circle
        )

        self.avatar_label = Label(
            text=summary.initials,
            bold=True,
            font_size="15sp",
            color=(1, 1, 1, 1),
            size_hint=(1, 1),
        )
        self.avatar_box.add_widget(self.avatar_label)
        self.add_widget(self.avatar_box)

        # 2. Middle column: Title + Preview
        mid_box = BoxLayout(orientation="vertical", spacing=dp(2))

        # Title row
        title_row = BoxLayout(orientation="horizontal")
        self.title_label = Label(
            text=summary.title,
            bold=True,
            font_size="15sp",
            color=TEXT_PRIMARY,
            halign="left",
            valign="middle",
            shorten=True,
            shorten_from="right",
            size_hint_x=0.85,
        )
        self.title_label.bind(size=self._setter("text_size"))
        title_row.add_widget(self.title_label)

        mid_box.add_widget(title_row)

        # Preview row
        self.preview_label = Label(
            text=summary.display_preview,
            font_size="13sp",
            color=TEXT_SECONDARY,
            halign="left",
            valign="middle",
            shorten=True,
            shorten_from="right",
        )
        self.preview_label.bind(size=self._setter("text_size"))
        mid_box.add_widget(self.preview_label)

        self.add_widget(mid_box)

        # 3. Right column: Time, Unread Badge, Pin Star Action
        right_box = BoxLayout(
            orientation="vertical", size_hint_x=None, width=dp(54), spacing=dp(4)
        )

        # Time label
        self.time_label = Label(
            text=summary.last_message_time_str,
            font_size="11sp",
            color=TEXT_SECONDARY,
            halign="right",
            valign="top",
            size_hint_y=0.45,
        )
        self.time_label.bind(size=self._setter("text_size"))
        right_box.add_widget(self.time_label)

        # Action / Badge row
        actions_row = BoxLayout(orientation="horizontal", size_hint_y=0.55, spacing=dp(2))

        # Custom Pin star button
        star_char = "★" if summary.is_pinned_locally else "☆"
        star_color = ACCENT_GOLD if summary.is_pinned_locally else TEXT_SECONDARY
        self.pin_btn = Button(
            text=star_char,
            font_size="17sp",
            color=star_color,
            background_normal="",
            background_color=(0, 0, 0, 0),
            size_hint=(None, 1),
            width=dp(26),
        )
        self.pin_btn.bind(on_release=self._on_pin_clicked)
        actions_row.add_widget(self.pin_btn)

        # Unread badge
        if summary.unread_count > 0:
            badge_text = (
                str(summary.unread_count) if summary.unread_count < 100 else "99+"
            )
            self.badge_label = Label(
                text=badge_text,
                font_size="11sp",
                bold=True,
                color=(1, 1, 1, 1),
                size_hint=(None, None),
                size=(dp(22), dp(BADGE_HEIGHT_DP)),
            )
            with self.badge_label.canvas.before:
                Color(*PRIMARY_BLUE)
                self.badge_bg = RoundedRectangle(
                    pos=self.badge_label.pos,
                    size=self.badge_label.size,
                    radius=[dp(10)],
                )
            self.badge_label.bind(
                pos=self._update_badge, size=self._update_badge
            )
            actions_row.add_widget(self.badge_label)

        right_box.add_widget(actions_row)
        self.add_widget(right_box)

    def _update_rect(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size
        self.border_rect.pos = instance.pos
        self.border_rect.size = instance.size

    def _update_avatar_circle(self, instance, value):
        self.avatar_circle.pos = instance.pos
        self.avatar_circle.size = instance.size

    def _update_badge(self, instance, value):
        if hasattr(self, "badge_bg"):
            self.badge_bg.pos = instance.pos
            self.badge_bg.size = instance.size

    def _setter(self, prop_name):
        return lambda instance, value: setattr(instance, prop_name, value)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            # Check if pin button was touched
            if self.pin_btn.collide_point(*touch.pos):
                return super().on_touch_down(touch)
            # Otherwise, item was clicked
            if self.on_click_callback:
                self.on_click_callback(self.summary)
            return True
        return super().on_touch_down(touch)

    def _on_pin_clicked(self, instance):
        if self.on_pin_toggle_callback:
            self.on_pin_toggle_callback(self.summary)
