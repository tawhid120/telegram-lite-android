"""
Custom Important Contacts / Pinned Chats UI Section.
Displays pinned contacts (e.g., A, B, C) in a dedicated top carousel/row.
"""

from typing import List, Callable
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle, Ellipse
from kivy.metrics import dp

from app.ui_constants import (
    DARK_SURFACE,
    DARK_CARD,
    PRIMARY_BLUE,
    ACCENT_GOLD,
    TEXT_PRIMARY,
    TEXT_MUTED,
)
from storage.pin_store import PinnedContact


class PinnedContactBadge(BoxLayout):
    """Circular contact badge for the pinned section."""

    def __init__(
        self,
        contact: PinnedContact,
        on_select_callback: Callable[[PinnedContact], None],
        **kwargs
    ):
        super().__init__(**kwargs)
        self.contact = contact
        self.on_select_callback = on_select_callback

        self.orientation = "vertical"
        self.size_hint = (None, 1)
        self.width = dp(64)
        self.spacing = dp(4)
        self.padding = [dp(4), dp(2), dp(4), dp(2)]

        # Avatar circle
        self.avatar_box = BoxLayout(
            size_hint=(None, None), size=(dp(44), dp(44)), pos_hint={"center_x": 0.5}
        )
        with self.avatar_box.canvas.before:
            Color(*PRIMARY_BLUE)
            self.avatar_circle = Ellipse(
                pos=self.avatar_box.pos, size=self.avatar_box.size
            )
            # Gold star badge on the avatar corner
            Color(*ACCENT_GOLD)
            self.star_badge = Ellipse(
                pos=(self.avatar_box.x + dp(30), self.avatar_box.y),
                size=(dp(14), dp(14)),
            )

        self.avatar_box.bind(
            pos=self._update_avatar_circle, size=self._update_avatar_circle
        )

        # Derive initials
        parts = contact.title.strip().split()
        initials = (
            (parts[0][0] + parts[1][0]).upper()
            if len(parts) >= 2
            else contact.title[:2].upper()
        )
        self.initials_lbl = Label(
            text=initials or "?",
            bold=True,
            font_size="13sp",
            color=(1, 1, 1, 1),
        )
        self.avatar_box.add_widget(self.initials_lbl)
        self.add_widget(self.avatar_box)

        # Title snippet
        display_name = contact.title.split()[0] if contact.title else "Contact"
        if len(display_name) > 8:
            display_name = display_name[:7] + "…"

        self.name_lbl = Label(
            text=display_name,
            font_size="11sp",
            color=TEXT_PRIMARY,
            halign="center",
            valign="top",
            size_hint=(1, None),
            height=dp(16),
            shorten=True,
        )
        self.add_widget(self.name_lbl)

    def _update_avatar_circle(self, instance, value):
        self.avatar_circle.pos = instance.pos
        self.avatar_circle.size = instance.size
        self.star_badge.pos = (instance.x + dp(30), instance.y)

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            if self.on_select_callback:
                self.on_select_callback(self.contact)
            return True
        return super().on_touch_down(touch)


class PinnedSectionWidget(BoxLayout):
    """
    Pinned Contacts header component placed at the top of the chat view.
    Renders contacts A, B, C horizontally in priority order.
    """

    def __init__(
        self,
        on_contact_selected: Callable[[PinnedContact], None],
        **kwargs
    ):
        super().__init__(**kwargs)
        self.on_contact_selected = on_contact_selected
        self.orientation = "vertical"
        self.size_hint_y = None
        self.height = dp(88)
        self.padding = [dp(12), dp(4), dp(12), dp(4)]
        self.spacing = dp(4)

        with self.canvas.before:
            Color(*DARK_SURFACE)
            self.bg_rect = RoundedRectangle(
                pos=self.pos, size=self.size, radius=[dp(8)]
            )
        self.bind(pos=self._update_bg, size=self._update_bg)

        # Header title
        header_row = BoxLayout(size_hint_y=None, height=dp(18), orientation="horizontal")
        star_lbl = Label(
            text="★ IMPORTANT CONTACTS",
            bold=True,
            font_size="11sp",
            color=ACCENT_GOLD,
            halign="left",
            size_hint_x=0.8,
        )
        star_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        header_row.add_widget(star_lbl)
        self.add_widget(header_row)

        # Horizontal ScrollView for pinned contacts
        self.scroll = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=True,
            do_scroll_y=False,
            bar_width=0,
        )
        self.contacts_container = BoxLayout(
            orientation="horizontal",
            size_hint_x=None,
            spacing=dp(8),
            height=dp(64),
        )
        self.contacts_container.bind(minimum_width=self.contacts_container.setter("width"))
        self.scroll.add_widget(self.contacts_container)
        self.add_widget(self.scroll)

    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size

    def update_pinned_contacts(self, contacts: List[PinnedContact]) -> None:
        """Refresh the pinned contact badges."""
        self.contacts_container.clear_widgets()
        if not contacts:
            self.height = 0
            self.opacity = 0
            self.disabled = True
            return

        self.height = dp(92)
        self.opacity = 1
        self.disabled = False

        for contact in contacts:
            badge = PinnedContactBadge(
                contact=contact,
                on_select_callback=self.on_contact_selected,
            )
            self.contacts_container.add_widget(badge)
