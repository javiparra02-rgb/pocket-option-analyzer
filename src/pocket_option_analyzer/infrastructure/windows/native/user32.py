from __future__ import annotations

import ctypes

user32 = ctypes.windll.user32

EnumWindows = user32.EnumWindows
GetWindowTextLengthW = user32.GetWindowTextLengthW
GetWindowTextW = user32.GetWindowTextW
GetWindowRect = user32.GetWindowRect
GetClientRect = user32.GetClientRect
ClientToScreen = user32.ClientToScreen
IsWindowVisible = user32.IsWindowVisible
IsIconic = user32.IsIconic
GetForegroundWindow = user32.GetForegroundWindow
PrintWindow = user32.PrintWindow