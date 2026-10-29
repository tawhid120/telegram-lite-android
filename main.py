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
            from kivy.uix.scrollview import ScrollView
            from kivy.graphics import Color, Rectangle

            class ErrorCrashApp(App):
                def build(self):
                    box = BoxLayout(orientation="vertical", padding=20)
                    with box.canvas.before:
                        Color(0.1, 0.1, 0.12, 1)
                        self.rect = Rectangle(size=box.size, pos=box.pos)
                    box.bind(
                        size=lambda inst, val: setattr(self.rect, "size", val),
                        pos=lambda inst, val: setattr(self.rect, "pos", val),
                    )

                    title = Label(
                        text="Telegram Lite - Startup Diagnostic",
                        font_size="18sp",
                        bold=True,
                        color=(1, 0.3, 0.3, 1),
                        size_hint_y=None,
                        height=50,
                    )
                    box.add_widget(title)

                    scroll = ScrollView()
                    lbl = Label(
                        text=f"The application encountered an unexpected error on launch:\n\n{error_details}",
                        font_size="12sp",
                        color=(0.9, 0.9, 0.9, 1),
                        size_hint_y=None,
                        halign="left",
                        valign="top",
                    )
                    lbl.bind(texture_size=lbl.setter("size"))
                    scroll.add_widget(lbl)
                    box.add_widget(scroll)
                    return box

            ErrorCrashApp().run()
        except Exception as inner_e:
            logger.critical("Failed to display error screen: %s", inner_e)
        sys.exit(1)


if __name__ == "__main__":
    main()
