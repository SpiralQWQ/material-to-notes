"""Pick a route from the input kind.

An unknown input returns an empty route, which the caller must treat as
"stop and ask the user" — never guess.
"""

from __future__ import annotations

import os

VIDEO = {".mp4", ".webm", ".mkv", ".mov", ".flv", ".avi"}
AUDIO = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".wma"}
IMAGE = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
DOCUMENT = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".html", ".htm"}

SOURCE = ("terms", "links")
UNKNOWN = "unknown"

_DIRECT = {
    "video": ("media", "clean", "note"),
    "audio": ("media", "clean", "note"),
    "image": ("media", "clean", "note"),
    "album": ("media", "clean", "note"),
    "pdf": ("document", "clean", "note"),
    "docx": ("document", "clean", "note"),
    "pptx": ("document", "clean", "note"),
    "html": ("document", "clean", "note"),
}


def classify(target) -> str:
    """Input kind for a path or URL, or UNKNOWN."""
    text = str(target).strip()
    if not text:
        return UNKNOWN
    if text.startswith(("http://", "https://")):
        return "links"
    if os.path.isdir(text):
        return "album"
    ext = os.path.splitext(text)[1].lower()
    if ext in VIDEO:
        return "video"
    if ext in AUDIO:
        return "audio"
    if ext in IMAGE:
        return "image"
    if ext in DOCUMENT:
        return ext.lstrip(".")
    return UNKNOWN


def route(kind: str) -> tuple:
    """Step chain for a kind; empty tuple means "unknown -> ask the user".

    Source kinds (terms/links) return just ``("fetch",)``: what runs after fetch
    depends on what was actually fetched, so it is decided then.
    """
    if kind in _DIRECT:
        return _DIRECT[kind]
    if kind in SOURCE:
        return ("fetch",)
    return ()


def route_after_fetch(kinds) -> tuple:
    """Steps to run after fetch, given the kinds of what was fetched."""
    kinds = tuple(kinds)
    if any(k in ("video", "audio", "image", "album") for k in kinds):
        return ("media", "clean", "note")
    if any(k in ("pdf", "docx", "pptx", "html") for k in kinds):
        return ("document", "clean", "note")
    return ()
