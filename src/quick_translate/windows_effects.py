from __future__ import annotations

import sys


if sys.platform == "win32":
    from ctypes import Structure, addressof, byref, c_int, c_uint, c_void_p, sizeof, windll

    class AccentPolicy(Structure):
        _fields_ = [
            ("AccentState", c_int),
            ("AccentFlags", c_int),
            ("GradientColor", c_uint),
            ("AnimationId", c_int),
        ]


    class WindowCompositionAttributeData(Structure):
        _fields_ = [
            ("Attribute", c_int),
            ("Data", c_void_p),
            ("SizeOfData", c_uint),
        ]


    class Margins(Structure):
        _fields_ = [
            ("left", c_int),
            ("right", c_int),
            ("top", c_int),
            ("bottom", c_int),
        ]


    ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
    WCA_ACCENT_POLICY = 19
    DWMWA_SYSTEMBACKDROP_TYPE = 38
    DWMSBT_TRANSIENTWINDOW = 3


def enable_blur(hwnd: int) -> None:
    if sys.platform != "win32":
        return

    margins = Margins(-1, -1, -1, -1)
    try:
        windll.dwmapi.DwmExtendFrameIntoClientArea(hwnd, byref(margins))
    except OSError:
        pass

    try:
        backdrop_type = c_int(DWMSBT_TRANSIENTWINDOW)
        windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_SYSTEMBACKDROP_TYPE,
            byref(backdrop_type),
            sizeof(backdrop_type),
        )
    except OSError:
        pass

    accent = AccentPolicy(
        AccentState=ACCENT_ENABLE_ACRYLICBLURBEHIND,
        AccentFlags=0,
        GradientColor=0xC8F7F7F7,
        AnimationId=0,
    )
    data = WindowCompositionAttributeData(
        Attribute=WCA_ACCENT_POLICY,
        Data=c_void_p(addressof(accent)),
        SizeOfData=sizeof(accent),
    )
    try:
        windll.user32.SetWindowCompositionAttribute(hwnd, byref(data))
    except (AttributeError, OSError):
        pass

