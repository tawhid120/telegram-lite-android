"""
UI Constants, Colors, Themes, and Layout Metrics for Telegram Lite.
Specially tuned for narrow, low-RAM Android Go devices.
"""

# Color Palette (RGBA tuples for Kivy)
# Dark Theme (Default for OLED / battery saving on Go devices)
DARK_BG = (0.05, 0.07, 0.09, 1.0)          # #0D1117
DARK_SURFACE = (0.09, 0.11, 0.13, 1.0)     # #161B22
DARK_CARD = (0.13, 0.15, 0.18, 1.0)        # #21262D
DARK_BORDER = (0.19, 0.22, 0.25, 1.0)      # #30363D

# Primary Accent (Telegram Blue)
PRIMARY_BLUE = (0.15, 0.54, 0.94, 1.0)     # #2688EB
PRIMARY_BLUE_DARK = (0.11, 0.40, 0.70, 1.0)
ACCENT_GREEN = (0.18, 0.76, 0.49, 1.0)     # #2ECC71
ACCENT_GOLD = (0.95, 0.77, 0.20, 1.0)      # #F1C40F (Pinned Star)
ACCENT_RED = (0.92, 0.25, 0.20, 1.0)       # #EB4034 (Error / Warning)

# Text Colors
TEXT_PRIMARY = (0.95, 0.96, 0.98, 1.0)
TEXT_SECONDARY = (0.55, 0.58, 0.63, 1.0)
TEXT_MUTED = (0.38, 0.42, 0.46, 1.0)
TEXT_ON_ACCENT = (1.0, 1.0, 1.0, 1.0)

# Chat Bubbles
BUBBLE_INCOMING = (0.13, 0.15, 0.18, 1.0)
BUBBLE_OUTGOING = (0.11, 0.35, 0.60, 1.0)

# Light Theme Options
LIGHT_BG = (0.96, 0.97, 0.98, 1.0)
LIGHT_SURFACE = (1.0, 1.0, 1.0, 1.0)
LIGHT_TEXT = (0.12, 0.14, 0.16, 1.0)
LIGHT_BUBBLE_INCOMING = (0.92, 0.93, 0.95, 1.0)
LIGHT_BUBBLE_OUTGOING = (0.80, 0.90, 1.0, 1.0)

# Touch Target Metrics (DP)
MIN_TOUCH_TARGET_DP = 48
AVATAR_SIZE_LIST_DP = 44
AVATAR_SIZE_HEADER_DP = 36
AVATAR_SIZE_PINNED_DP = 52
BADGE_HEIGHT_DP = 20
PADDING_HORIZONTAL_DP = 12
PADDING_VERTICAL_DP = 8
