"""
Telegram Lite - Main Application Entry Point.
Optimized for Low-RAM Android Go devices.
"""

import sys
import os
import logging

# Ensure root package directory is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, NoTransition, SlideTransition
from kivy.core.window import Window
from kivy.clock import Clock

from app.config import AppConfig
from storage.secure_store import SecureSessionStore
from storage.pin_store import PinStore
from storage.cache_manager import CacheManager
from telegram_client.client_wrapper import TelegramClientWrapper
from telegram_client.models import ChatSummary, TelegramUser
from app.screens.api_setup_screen import ApiSetupScreen
from app.screens.login_screen import LoginScreen
from app.screens.chats_screen import ChatsScreen
from app.screens.conversation_screen import ConversationScreen
from app.screens.settings_screen import SettingsScreen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("TelegramLite")


class TelegramLiteApp(App):
    """
    Main Kivy Application for Telegram Lite.
    """

    title = "Telegram Lite"
    icon = "assets/icon.png"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.secure_store = SecureSessionStore()
        self.pin_store = PinStore()
        self.cache_manager = CacheManager()
        self.app_config = AppConfig(self.secure_store)
        self.client_wrapper: TelegramClientWrapper = None
        self.sm: ScreenManager = None

    def build(self):
        # Configure screen transition: NoTransition is the fastest and saves RAM on Android Go
        self.sm = ScreenManager(transition=NoTransition())

        # Intercept Android back button (keycode 27)
        Window.bind(on_keyboard=self._on_key_down)

        # Check for API Credentials
        api_id, api_hash = self.app_config.get_api_credentials()
        if api_id and api_hash:
            self._setup_client_and_launch(api_id, api_hash)
        else:
            self._show_api_setup_screen()

        return self.sm

    def _show_api_setup_screen(self):
        """Display API credential setup screen."""
        self.api_setup_screen = ApiSetupScreen(
            app_config=self.app_config,
            on_configured_callback=self._on_api_credentials_provided,
            name="api_setup",
        )
        self.sm.add_widget(self.api_setup_screen)
        self.sm.current = "api_setup"

    def _on_api_credentials_provided(self, api_id: int, api_hash: str):
        """Called when user successfully enters API ID & Hash."""
        self._setup_client_and_launch(api_id, api_hash)

    def _setup_client_and_launch(self, api_id: int, api_hash: str):
        """Initialize MTProto client and evaluate session authorization."""
        self.client_wrapper = TelegramClientWrapper(
            api_id=api_id,
            api_hash=api_hash,
            secure_store=self.secure_store,
            pin_store=self.pin_store,
            cache_manager=self.cache_manager,
        )
        self.client_wrapper.start()

        # Build application screens
        self.login_screen = LoginScreen(
            client_wrapper=self.client_wrapper,
            on_login_success=self._on_login_success,
            name="login",
        )
        self.chats_screen = ChatsScreen(
            client_wrapper=self.client_wrapper,
            pin_store=self.pin_store,
            on_chat_selected_callback=self._open_chat,
            on_settings_clicked_callback=self._open_settings,
            name="chats",
        )
        self.conversation_screen = ConversationScreen(
            client_wrapper=self.client_wrapper,
            pin_store=self.pin_store,
            on_back_callback=self._back_to_chats,
            name="conversation",
        )
        self.settings_screen = SettingsScreen(
            client_wrapper=self.client_wrapper,
            pin_store=self.pin_store,
            cache_manager=self.cache_manager,
            app_config=self.app_config,
            on_back_callback=self._back_to_chats,
            on_logout_callback=self._on_logged_out,
            name="settings",
        )

        self.sm.add_widget(self.login_screen)
        self.sm.add_widget(self.chats_screen)
        self.sm.add_widget(self.conversation_screen)
        self.sm.add_widget(self.settings_screen)

        # Check existing saved session
        def _on_init_done(authorized: bool, user: TelegramUser):
            def _ui(dt):
                if authorized:
                    logger.info("Restored authorized session for user: %s", user.full_name)
                    self.sm.current = "chats"
                    self.chats_screen.load_dialogs()
                else:
                    logger.info("No authorized session found. Redirecting to login.")
                    self.sm.current = "login"

            Clock.schedule_once(_ui, 0)

        self.client_wrapper.initialize_client(_on_init_done)

    def _on_login_success(self, user: TelegramUser):
        """Triggered upon successful phone/code/2FA authentication."""
        self.sm.current = "chats"
        self.chats_screen.load_dialogs()

    def _open_chat(self, chat_summary: ChatSummary):
        """Navigate to active conversation view."""
        self.conversation_screen.set_chat(chat_summary)
        self.sm.current = "conversation"

    def _open_settings(self):
        """Navigate to settings view."""
        self.sm.current = "settings"

    def _back_to_chats(self):
        """Return to main conversation list preserving filter."""
        self.sm.current = "chats"
        self.chats_screen.refresh_pinned_section()

    def _on_logged_out(self):
        """Wipe session and return to login screen."""
        self.sm.current = "login"
        self.login_screen._render_phone_step()

    def _on_key_down(self, window, key, scancode, codepoint, modifier):
        """Handle Android back button (keycode 27)."""
        if key == 27:
            if self.sm.current in ("conversation", "settings"):
                self._back_to_chats()
                return True
        return False

    def on_stop(self):
        """App shutdown cleanup."""
        if self.client_wrapper:
            self.client_wrapper.stop()


def main():
    app = TelegramLiteApp()
    app.run()


if __name__ == "__main__":
    main()
