"""
Root entry point for Buildozer / python-for-android packaging.
Optimized for Android Go and modern Android devices.
Includes top-level exception trapping to prevent silent crashes on startup.
"""

import sys
import os
import traceback
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("MainEntry")


def main():
    try:
        from app.main import TelegramLiteApp
        app = TelegramLiteApp()
        app.run()
    except Exception as e:
        error_details = traceback.format_exc()
        logger.critical("Fatal exception during app execution:\n%s", error_details)

        # Attempt to display an emergency error screen in Kivy
        try:
            from kivy.app import App
            from kivy.uix.label import Label
            from kivy.uix.boxlayout import BoxLayout
            from kivy.uix.textinput import TextInput
            from kivy.graphics import Color, Rectangle

            class ErrorCrashApp(App):
                def build(self):
                    box = BoxLayout(orientation="vertical", padding=16, spacing=10)
                    with box.canvas.before:
                        Color(0.1, 0.1, 0.12, 1)
                        self.rect = Rectangle(size=box.size, pos=box.pos)
                    box.bind(
                        size=lambda inst, val: setattr(self.rect, "size", val),
                        pos=lambda inst, val: setattr(self.rect, "pos", val),
                    )

                    title = Label(
                        text="Telegram Lite - Startup Diagnostic",
                        font_size="16sp",
                        bold=True,
                        color=(1, 0.35, 0.35, 1),
                        size_hint_y=None,
                        height=40,
                    )
                    box.add_widget(title)

                    txt = TextInput(
                        text=f"Startup Error Encountered:\n\n{error_details}",
                        readonly=True,
                        background_color=(0.15, 0.15, 0.18, 1),
                        foreground_color=(1, 0.95, 0.95, 1),
                        font_size="11sp",
                        size_hint=(1, 1),
                    )
                    box.add_widget(txt)
                    return box

            ErrorCrashApp().run()
        except Exception as inner_e:
            logger.critical("Failed to display error screen: %s", inner_e)
        sys.exit(1)


if __name__ == "__main__":
    main()
