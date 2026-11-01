"""
Lightweight Chat Message Bubble Widget for Android Go.
Renders incoming and outgoing messages with reply previews, media preview/download, and timestamps.
"""

import os
from typing import Optional, Callable
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp

from app.ui_constants import (
    BUBBLE_INCOMING,
    BUBBLE_OUTGOING,
    DARK_CARD,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    PRIMARY_BLUE,
    PRIMARY_BLUE_DARK,
    ACCENT_GREEN,
)
from telegram_client.models import MessageItem


class MessageBubbleWidget(BoxLayout):
    """
    Message bubble layout with responsive alignment (left for incoming, right for outgoing)
    and full support for viewing photos and downloading documents/videos/media.
    """

    def __init__(
        self,
        message: MessageItem,
        is_group: bool = False,
        on_media_action_callback: Optional[Callable[[MessageItem, str], None]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.message = message
        self.is_group = is_group
        self.on_media_action_callback = on_media_action_callback

        self.orientation = "horizontal"
        self.size_hint_y = None
        self.padding = [dp(8), dp(3), dp(8), dp(3)]

        # Outer container for bubble alignment
        if message.is_outgoing:
            # Spacer on left, bubble on right
            self.add_widget(BoxLayout(size_hint_x=0.2))

        # Main bubble box
        self.bubble = BoxLayout(
            orientation="vertical",
            size_hint_x=0.8,
            size_hint_y=None,
            padding=[dp(10), dp(6), dp(10), dp(6)],
            spacing=dp(3),
        )

        # Bubble background
        bubble_color = BUBBLE_OUTGOING if message.is_outgoing else BUBBLE_INCOMING
        with self.bubble.canvas.before:
            Color(*bubble_color)
            self.bg_rect = RoundedRectangle(
                pos=self.bubble.pos,
                size=self.bubble.size,
                radius=[dp(12), dp(12), dp(2 if message.is_outgoing else 12), dp(12 if message.is_outgoing else 2)],
            )
        self.bubble.bind(pos=self._update_bubble_bg, size=self._update_bubble_bg)

        # Group Sender name (if incoming in a group)
        if not message.is_outgoing and is_group and message.sender_name:
            sender_lbl = Label(
                text=message.sender_name,
                bold=True,
                font_size="12sp",
                color=PRIMARY_BLUE,
                halign="left",
                size_hint_y=None,
                height=dp(16),
            )
            sender_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            self.bubble.add_widget(sender_lbl)

        # Reply banner (if message is a reply)
        if message.reply_to_msg_id:
            reply_box = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                height=dp(28),
                padding=[dp(6), dp(2), dp(6), dp(2)],
            )
            with reply_box.canvas.before:
                Color(*DARK_CARD)
                RoundedRectangle(
                    pos=reply_box.pos, size=reply_box.size, radius=[dp(4)]
                )
            rep_text = message.reply_to_text or "Original message"
            if len(rep_text) > 40:
                rep_text = rep_text[:37] + "..."
            rep_lbl = Label(
                text=f"↳ {rep_text}",
                font_size="11sp",
                color=TEXT_SECONDARY,
                halign="left",
            )
            rep_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            reply_box.add_widget(rep_lbl)
            self.bubble.add_widget(reply_box)

        # Media section
        if message.media_type:
            media_box = BoxLayout(
                orientation="vertical",
                size_hint_y=None,
                spacing=dp(4),
                padding=[dp(4), dp(4), dp(4), dp(4)],
            )
            media_box.bind(minimum_height=media_box.setter("height"))

            media_label_text = f"[{message.media_type.upper()}]"
            if message.media_name:
                media_label_text += f" {message.media_name}"
            if message.media_size_str:
                media_label_text += f" ({message.media_size_str})"

            media_lbl = Label(
                text=media_label_text,
                font_size="12sp",
                bold=True,
                color=PRIMARY_BLUE,
                halign="left",
                size_hint_y=None,
                height=dp(20),
            )
            media_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
            media_box.add_widget(media_lbl)

            # Check if media file is already downloaded and present on disk
            has_local = bool(message.local_media_path and os.path.exists(message.local_media_path))

            if has_local:
                # If image, show photo thumbnail/preview
                is_image = message.media_type == "photo" or (
                    message.media_name and message.media_name.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
                )
                if is_image:
                    img_widget = Image(
                        source=message.local_media_path,
                        size_hint=(1, None),
                        height=dp(170),
                        allow_stretch=True,
                        keep_ratio=True,
                    )
                    media_box.add_widget(img_widget)

                # Open / View button
                open_btn = Button(
                    text="👁 Open / View Media",
                    font_size="12sp",
                    bold=True,
                    size_hint_y=None,
                    height=dp(30),
                    background_normal="",
                    background_color=ACCENT_GREEN,
                    color=(1, 1, 1, 1),
                )
                open_btn.bind(on_release=lambda x: self._on_media_clicked("open"))
                media_box.add_widget(open_btn)
            else:
                # Download button
                btn_text = "⏳ Downloading..." if message.is_downloading else f"📥 Download ({message.media_size_str or 'Media'})"
                dl_btn = Button(
                    text=btn_text,
                    font_size="12sp",
                    bold=True,
                    size_hint_y=None,
                    height=dp(32),
                    background_normal="",
                    background_color=DARK_CARD if message.is_downloading else PRIMARY_BLUE,
                    color=(1, 1, 1, 1),
                    disabled=message.is_downloading,
                )
                dl_btn.bind(on_release=lambda x: self._on_media_clicked("download"))
                media_box.add_widget(dl_btn)

            self.bubble.add_widget(media_box)

        # Message text
        if message.text:
            self.text_label = Label(
                text=message.text,
                font_size="14sp",
                color=TEXT_PRIMARY,
                halign="left",
                valign="top",
                size_hint_y=None,
            )
            self.text_label.bind(
                width=lambda *x: self.text_label.setter("text_size")(self.text_label, (self.text_label.width, None)),
                texture_size=lambda *x: setattr(self.text_label, "height", self.text_label.texture_size[1]),
            )
            self.bubble.add_widget(self.text_label)

        # Metadata row: Timestamp + Status tick
        meta_row = BoxLayout(
            orientation="horizontal",
            size_hint_y=None,
            height=dp(16),
            spacing=dp(4),
        )
        meta_row.add_widget(BoxLayout())  # Push to right

        time_text = message.formatted_time
        if message.is_outgoing:
            status_symbol = " ✓" if message.delivery_status == "sent" else " ⏳"
            time_text += status_symbol

        meta_lbl = Label(
            text=time_text,
            font_size="10sp",
            color=TEXT_SECONDARY,
            halign="right",
            size_hint_x=None,
            width=dp(50),
        )
        meta_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        meta_row.add_widget(meta_lbl)
        self.bubble.add_widget(meta_row)

        # Dynamic height binding
        self.bubble.bind(minimum_height=self._set_bubble_height)
        self.add_widget(self.bubble)

        if not message.is_outgoing:
            # Spacer on right for incoming messages
            self.add_widget(BoxLayout(size_hint_x=0.2))

        self.height = dp(60)  # Default fallback height

    def _on_media_clicked(self, action: str):
        if self.on_media_action_callback:
            self.on_media_action_callback(self.message, action)

    def _update_bubble_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def _set_bubble_height(self, instance, value):
        self.bubble.height = value
        self.height = value + dp(8)
