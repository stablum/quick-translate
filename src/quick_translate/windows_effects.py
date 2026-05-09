from __future__ import annotations

import sys

from quick_translate.logging_utils import get_logger


logger = get_logger(__name__)


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


    ACCENT_ENABLE_BLURBEHIND = 3
    ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
    WCA_ACCENT_POLICY = 19
    DWMWA_SYSTEMBACKDROP_TYPE = 38
    DWMSBT_NONE = 1

    windll.user32.SetWindowCompositionAttribute.argtypes = [c_void_p, c_void_p]
    windll.user32.SetWindowCompositionAttribute.restype = c_int
    windll.dwmapi.DwmSetWindowAttribute.argtypes = [c_void_p, c_uint, c_void_p, c_uint]
    windll.dwmapi.DwmSetWindowAttribute.restype = c_int


def _set_accent(hwnd: int, accent_state: int, gradient_color: int, accent_flags: int = 0) -> bool:
    accent = AccentPolicy(
        AccentState=accent_state,
        AccentFlags=accent_flags,
        GradientColor=gradient_color,
        AnimationId=0,
    )
    data = WindowCompositionAttributeData(
        Attribute=WCA_ACCENT_POLICY,
        Data=c_void_p(addressof(accent)),
        SizeOfData=sizeof(accent),
    )
    return bool(windll.user32.SetWindowCompositionAttribute(hwnd, byref(data)))


def _accent_gradient_color(opacity: float, tint: int = 0xFFFFFF) -> int:
    alpha = max(0, min(255, round(255 * opacity)))
    return (alpha << 24) | (tint & 0xFFFFFF)


def enable_blur(hwnd: int, opacity: float = 0.14) -> None:
    if sys.platform != "win32":
        return

    try:
        backdrop_type = c_int(DWMSBT_NONE)
        windll.dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_SYSTEMBACKDROP_TYPE,
            byref(backdrop_type),
            sizeof(backdrop_type),
        )
    except OSError:
        pass

    try:
        gradient_color = _accent_gradient_color(opacity)
        applied = _set_accent(
            hwnd=hwnd,
            accent_state=ACCENT_ENABLE_BLURBEHIND,
            gradient_color=gradient_color,
        )
        if not applied:
            logger.warning("Basic blur was unavailable, falling back to acrylic blur")
            _set_accent(
                hwnd=hwnd,
                accent_state=ACCENT_ENABLE_ACRYLICBLURBEHIND,
                gradient_color=gradient_color,
                accent_flags=2,
            )
    except (AttributeError, OSError):
        logger.exception("Failed to apply Windows blur effects")
