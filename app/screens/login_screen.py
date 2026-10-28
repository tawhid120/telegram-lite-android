"""
MTProto Authentication Screen for Telegram Lite.
Implements the official Telegram login flow:
1. Phone Number entry + Calling Code
2. In-App Telegram Verification Code Entry (or SMS if enabled by Telegram)
3. 2FA Two-Step Verification Password Entry (with Show/Hide toggle)
"""

import time
from typing import Callable, Optional
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
    DARK_CARD,
    DARK_BORDER,
    PRIMARY_BLUE,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    ACCENT_RED,
    ACCENT_GOLD,
    ACCENT_GREEN,
)
from telegram_client.client_wrapper import TelegramClientWrapper
from telegram_client.models import AuthState, CodeDeliveryType, TelegramUser


class LoginScreen(Screen):
    """
    Handles Telegram MTProto authentication workflow.
    """

    def __init__(
        self,
        client_wrapper: TelegramClientWrapper,
        on_login_success: Callable[[TelegramUser], None],
        **kwargs
    ):
        super().__init__(**kwargs)
        self.client = client_wrapper
        self.on_login_success = on_login_success

        self.current_step = "phone"  # "phone", "code", "password"
        self.phone_number = ""
        self.is_password_visible = False
        self.retry_seconds = 0
        self._countdown_event = None

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
        self.container = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            padding=[dp(20), dp(24), dp(20), dp(24)],
            spacing=dp(14),
        )
        self.container.bind(minimum_height=self.container.setter("height"))

        # Header Title
        self.header_box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(70), spacing=dp(4))
        self.title_lbl = Label(
            text="Sign in to Telegram",
            font_size="22sp",
            bold=True,
            color=PRIMARY_BLUE,
            halign="center",
        )
        self.subtitle_lbl = Label(
            text="Connect directly via MTProto",
            font_size="13sp",
            color=TEXT_SECONDARY,
            halign="center",
        )
        self.header_box.add_widget(self.title_lbl)
        self.header_box.add_widget(self.subtitle_lbl)
        self.container.add_widget(self.header_box)

        # Status / Error Banner
        self.status_box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            height=dp(70),
            padding=[dp(10), dp(8), dp(10), dp(8)],
        )
        with self.status_box.canvas.before:
            Color(*DARK_CARD)
            self.status_bg = RoundedRectangle(pos=self.status_box.pos, size=self.status_box.size, radius=[dp(6)])
        self.status_box.bind(
            pos=lambda inst, val: setattr(self.status_bg, "pos", val),
            size=lambda inst, val: setattr(self.status_bg, "size", val),
        )

        self.status_lbl = Label(
            text="Enter your phone number in international format (+1, +44, +880, etc.).",
            font_size="12sp",
            color=TEXT_PRIMARY,
            halign="center",
            valign="middle",
        )
        self.status_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", val))
        self.status_box.add_widget(self.status_lbl)
        self.container.add_widget(self.status_box)

        # Dynamic Form Content Layout
        self.form_box = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(12))
        self.form_box.bind(minimum_height=self.form_box.setter("height"))
        self.container.add_widget(self.form_box)

        scroll.add_widget(self.container)
        self.add_widget(scroll)

        # Render initial step: Phone Input
        self._render_phone_step()

    # -------------------------------------------------------------
    # Step 1: Phone Input
    # -------------------------------------------------------------
    def _render_phone_step(self):
        self.current_step = "phone"
        self.form_box.clear_widgets()

        self.title_lbl.text = "Sign in to Telegram"
        self.subtitle_lbl.text = "Connect directly via MTProto"
        self.status_lbl.text = (
            "Telegram will send the verification code to your active Telegram app "
            "(Desktop, Web, or phone). Check your Telegram chats."
        )

        # Phone row with country code and number
        phone_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(8))

        self.country_code_input = TextInput(
            text="+",
            multiline=False,
            size_hint_x=0.25,
            font_size="16sp",
            background_normal="",
            background_color=DARK_CARD,
            foreground_color=TEXT_PRIMARY,
            cursor_color=PRIMARY_BLUE,
            padding=[dp(8), dp(12), dp(8), dp(12)],
        )
        self.phone_input = TextInput(
            hint_text="Phone number",
            multiline=False,
            size_hint_x=0.75,
            font_size="16sp",
            background_normal="",
            background_color=DARK_CARD,
            foreground_color=TEXT_PRIMARY,
            cursor_color=PRIMARY_BLUE,
            padding=[dp(10), dp(12), dp(10), dp(12)],
            input_filter="int",
        )
        phone_box.add_widget(self.country_code_input)
        phone_box.add_widget(self.phone_input)
        self.form_box.add_widget(phone_box)

        # Continue Button
        self.continue_btn = Button(
            text="Continue",
            bold=True,
            font_size="15sp",
            size_hint_y=None,
            height=dp(48),
            background_normal="",
            background_color=PRIMARY_BLUE,
            color=(1, 1, 1, 1),
        )
        self.continue_btn.bind(on_release=self._on_send_code_clicked)
        self.form_box.add_widget(self.continue_btn)

    def _on_send_code_clicked(self, instance):
        cc = self.country_code_input.text.strip()
        num = self.phone_input.text.strip()
        if not num:
            self.status_lbl.text = "⚠️ Please enter your phone number."
            self.status_lbl.color = ACCENT_RED
            return

        full_phone = cc if cc.startswith("+") else "+" + cc
        full_phone += num
        self.phone_number = full_phone

        self.continue_btn.disabled = True
        self.status_lbl.color = TEXT_PRIMARY
        self.status_lbl.text = "🔄 Requesting login code from Telegram..."

        def _callback(success: bool, message: str, delivery: CodeDeliveryType, timeout: int):
            Clock.schedule_once(lambda dt: self._handle_code_sent_result(success, message, delivery, timeout), 0)

        self.client.request_login_code(full_phone, _callback)

    def _handle_code_sent_result(self, success: bool, message: str, delivery: CodeDeliveryType, timeout: int):
        self.continue_btn.disabled = False
        if success:
            self.retry_seconds = max(timeout, 30)
            self._render_code_step(message, delivery)
        else:
            self.status_lbl.text = f"⚠️ {message}"
            self.status_lbl.color = ACCENT_RED

    # -------------------------------------------------------------
    # Step 2: Verification Code
    # -------------------------------------------------------------
    def _render_code_step(self, info_msg: str, delivery: CodeDeliveryType):
        self.current_step = "code"
        self.form_box.clear_widgets()

        self.title_lbl.text = "Enter Verification Code"
        self.subtitle_lbl.text = f"Sent to {self.phone_number}"
        self.status_lbl.text = info_msg
        self.status_lbl.color = ACCENT_GREEN

        # Code Input Field
        self.code_input = TextInput(
            hint_text="e.g. 12345",
            multiline=False,
            size_hint_y=None,
            height=dp(48),
            font_size="20sp",
            halign="center",
            background_normal="",
            background_color=DARK_CARD,
            foreground_color=TEXT_PRIMARY,
            cursor_color=PRIMARY_BLUE,
            padding=[dp(10), dp(10), dp(10), dp(10)],
            input_filter="int",
        )
        self.form_box.add_widget(self.code_input)

        # Submit Code Button
        self.submit_code_btn = Button(
            text="Verify & Log In",
            bold=True,
            font_size="15sp",
            size_hint_y=None,
            height=dp(48),
            background_normal="",
            background_color=PRIMARY_BLUE,
            color=(1, 1, 1, 1),
        )
        self.submit_code_btn.bind(on_release=self._on_submit_code_clicked)
        self.form_box.add_widget(self.submit_code_btn)

        # Retry Countdown / Back controls
        controls_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40), spacing=dp(10))

        self.back_btn = Button(
            text="← Change Number",
            font_size="13sp",
            size_hint_x=0.5,
            background_normal="",
            background_color=DARK_CARD,
            color=TEXT_SECONDARY,
        )
        self.back_btn.bind(on_release=lambda x: self._render_phone_step())
        controls_row.add_widget(self.back_btn)

        self.resend_lbl = Label(
            text=f"Resend in {self.retry_seconds}s",
            font_size="12sp",
            size_hint_x=0.5,
            color=TEXT_SECONDARY,
        )
        controls_row.add_widget(self.resend_lbl)
        self.form_box.add_widget(controls_row)

        self._start_countdown()

    def _start_countdown(self):
        if self._countdown_event:
            self._countdown_event.cancel()

        def _tick(dt):
            if self.retry_seconds > 0:
                self.retry_seconds -= 1
                self.resend_lbl.text = f"Resend in {self.retry_seconds}s"
            else:
                self.resend_lbl.text = "Resend available"
                if self._countdown_event:
                    self._countdown_event.cancel()

        self._countdown_event = Clock.schedule_interval(_tick, 1.0)

    def _on_submit_code_clicked(self, instance):
        code = self.code_input.text.strip()
        if not code:
            self.status_lbl.text = "⚠️ Please enter the code."
            self.status_lbl.color = ACCENT_RED
            return

        self.submit_code_btn.disabled = True
        self.status_lbl.color = TEXT_PRIMARY
        self.status_lbl.text = "🔄 Verifying code with Telegram..."

        def _cb(success: bool, message: str, state: AuthState):
            Clock.schedule_once(lambda dt: self._handle_code_submit_result(success, message, state), 0)

        self.client.submit_code(code, _cb)

    def _handle_code_submit_result(self, success: bool, message: str, state: AuthState):
        self.submit_code_btn.disabled = False
        if success:
            if state == AuthState.AUTHENTICATED:
                self.status_lbl.text = f"✓ {message}"
                self.status_lbl.color = ACCENT_GREEN
                if self.on_login_success:
                    self.on_login_success(self.client.auth_handler.current_user)
            elif state == AuthState.WAITING_PASSWORD_2FA:
                self._render_2fa_step()
        else:
            self.status_lbl.text = f"⚠️ {message}"
            self.status_lbl.color = ACCENT_RED

    # -------------------------------------------------------------
    # Step 3: Two-Step Verification (2FA Password)
    # -------------------------------------------------------------
    def _render_2fa_step(self):
        self.current_step = "password"
        self.form_box.clear_widgets()

        self.title_lbl.text = "Two-Step Verification"
        self.subtitle_lbl.text = "Your account is protected with a 2FA password"
        self.status_lbl.text = "Please enter your Telegram cloud password."
        self.status_lbl.color = TEXT_PRIMARY

        # Password input row with Show/Hide toggle
        pwd_box = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(48), spacing=dp(6))

        self.pwd_input = TextInput(
            hint_text="Password",
            password=not self.is_password_visible,
            multiline=False,
            size_hint_x=0.75,
            font_size="16sp",
            background_normal="",
            background_color=DARK_CARD,
            foreground_color=TEXT_PRIMARY,
            cursor_color=PRIMARY_BLUE,
            padding=[dp(10), dp(12), dp(10), dp(12)],
        )
        pwd_box.add_widget(self.pwd_input)

        self.toggle_pwd_btn = Button(
            text="👁",
            font_size="16sp",
            size_hint_x=0.25,
            background_normal="",
            background_color=DARK_CARD,
            color=TEXT_PRIMARY,
        )
        self.toggle_pwd_btn.bind(on_release=self._toggle_password_visibility)
        pwd_box.add_widget(self.toggle_pwd_btn)
        self.form_box.add_widget(pwd_box)

        # Submit Password Button
        self.submit_pwd_btn = Button(
            text="Unlock Account",
            bold=True,
            font_size="15sp",
            size_hint_y=None,
            height=dp(48),
            background_normal="",
            background_color=PRIMARY_BLUE,
            color=(1, 1, 1, 1),
        )
        self.submit_pwd_btn.bind(on_release=self._on_submit_password_clicked)
        self.form_box.add_widget(self.submit_pwd_btn)

        # Back control
        back_btn = Button(
            text="← Back to Code Entry",
            font_size="13sp",
            size_hint_y=None,
            height=dp(38),
            background_normal="",
            background_color=DARK_CARD,
            color=TEXT_SECONDARY,
        )
        back_btn.bind(on_release=lambda x: self._render_code_step("Enter your code", CodeDeliveryType.APP_IN_APP))
        self.form_box.add_widget(back_btn)

    def _toggle_password_visibility(self, instance):
        self.is_password_visible = not self.is_password_visible
        self.pwd_input.password = not self.is_password_visible
        self.toggle_pwd_btn.text = "🔒" if self.is_password_visible else "👁"

    def _on_submit_password_clicked(self, instance):
        pwd = self.pwd_input.text
        if not pwd:
            self.status_lbl.text = "⚠️ Password cannot be empty."
            self.status_lbl.color = ACCENT_RED
            return

        self.submit_pwd_btn.disabled = True
        self.status_lbl.color = TEXT_PRIMARY
        self.status_lbl.text = "🔄 Verifying password with Telegram..."

        def _cb(success: bool, message: str, state: AuthState):
            Clock.schedule_once(lambda dt: self._handle_pwd_result(success, message, state), 0)

        self.client.submit_2fa_password(pwd, _cb)

    def _handle_pwd_result(self, success: bool, message: str, state: AuthState):
        self.submit_pwd_btn.disabled = False
        if success and state == AuthState.AUTHENTICATED:
            self.status_lbl.text = f"✓ {message}"
            self.status_lbl.color = ACCENT_GREEN
            if self.on_login_success:
                self.on_login_success(self.client.auth_handler.current_user)
        else:
            self.status_lbl.text = f"⚠️ {message}"
            self.status_lbl.color = ACCENT_RED
