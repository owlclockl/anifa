#!/usr/bin/env python3
"""Генератор макета мобильного приложения «Заметки».

Собирает артборды 390×844 в SVG (для импорта в Figma) из общих компонентов
и дизайн-токенов. Запуск:  python3 design/build_screens.py
PNG-версии:              node design/render-png.cjs
"""
from __future__ import annotations

import math
import os

W, H = 390, 844
FONT = "Inter, 'SF Pro Text', 'Segoe UI', 'DejaVu Sans', sans-serif"

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "svg")
os.makedirs(OUT, exist_ok=True)

LIGHT = {
    "name": "light",
    "bg": "#F4F3F9",
    "surface": "#FFFFFF",
    "alt": "#ECEAF5",
    "ink": "#17161C",
    "ink2": "#55526B",
    "ink3": "#9793AC",
    "primary": "#6C5CE7",
    "primary_dark": "#5546D6",
    "primary_soft": "#ECE9FF",
    "amber": "#F5A524",
    "amber_soft": "#FFF3DC",
    "green": "#1FA971",
    "green_soft": "#E2F5EC",
    "pink": "#E64980",
    "pink_soft": "#FCE7EE",
    "blue": "#3B82F6",
    "blue_soft": "#E4EEFF",
    "divider": "#ECEAF5",
    "shadow": "#17161C",
    "shadow_op": "0.07",
    "on_primary": "#FFFFFF",
}

DARK = {
    "name": "dark",
    "bg": "#121118",
    "surface": "#1D1B25",
    "alt": "#2A2736",
    "ink": "#F4F3FA",
    "ink2": "#B3AEC6",
    "ink3": "#7A748F",
    "primary": "#8B7CFF",
    "primary_dark": "#7B6BF5",
    "primary_soft": "#2B2450",
    "amber": "#FFB443",
    "amber_soft": "#33280F",
    "green": "#3ED598",
    "green_soft": "#122B20",
    "pink": "#FF6FA5",
    "pink_soft": "#33121F",
    "blue": "#71A5FF",
    "blue_soft": "#152742",
    "divider": "#2A2736",
    "shadow": "#000000",
    "shadow_op": "0.35",
    "on_primary": "#FFFFFF",
}

# ---------------------------------------------------------------- базовые фигуры


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def rect(x, y, w, h, r=0, fill="none", stroke=None, sw=1, op=None):
    st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    op = f' opacity="{op}"' if op is not None else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" ry="{r}" fill="{fill}"{st}{op}/>'


def circle(cx, cy, r, fill="none", stroke=None, sw=1, op=None):
    st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    op = f' opacity="{op}"' if op is not None else ""
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"{st}{op}/>'


def line(x1, y1, x2, y2, stroke, sw=1, cap="round", op=None):
    op = f' opacity="{op}"' if op is not None else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
        f'stroke-width="{sw}" stroke-linecap="{cap}"{op}/>'
    )


def path(d, stroke=None, sw=2, fill="none", cap="round", join="round", op=None):
    st = f' stroke="{stroke}" stroke-width="{sw}" stroke-linecap="{cap}" stroke-linejoin="{join}"' if stroke else ""
    op = f' opacity="{op}"' if op is not None else ""
    return f'<path d="{d}" fill="{fill}"{st}{op}/>'


def text(x, y, s, size=15, weight=400, fill="#000", anchor="start", ls=None, op=None):
    ls = f' letter-spacing="{ls}"' if ls else ""
    op = f' opacity="{op}"' if op is not None else ""
    return (
        f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{ls}{op}>{esc(s)}</text>'
    )


def text_w(s: str, size: float, bold=False) -> float:
    """Приблизительная ширина строки (для чипов, подчёркиваний, теней)."""
    return len(s) * size * (0.575 if bold else 0.545)


def shadow_rect(x, y, w, h, r, t):
    return rect(x, y + 4, w, h, r, fill=t["shadow"], op=t["shadow_op"])


# ---------------------------------------------------------------------- иконки
# Иконки в стиле Feather/Lucide: поле 24×24, обводка 2, скруглённые концы.


def icon(name, cx, cy, size, color, sw=1.9):
    g = f'<g transform="translate({cx - size / 2},{cy - size / 2}) scale({size / 24:.4f})" fill="none">'
    p = []
    c = color
    if name == "search":
        p = [circle(11, 11, 7, stroke=c, sw=sw), line(16.6, 16.6, 21, 21, c, sw)]
    elif name == "plus":
        p = [line(12, 5, 12, 19, c, sw), line(5, 12, 19, 12, c, sw)]
    elif name == "chevron-left":
        p = [path("M15 18 L9 12 L15 6", stroke=c, sw=sw)]
    elif name == "chevron-right":
        p = [path("M9 18 L15 12 L9 6", stroke=c, sw=sw)]
    elif name == "x":
        p = [line(18, 6, 6, 18, c, sw), line(6, 6, 18, 18, c, sw)]
    elif name == "star":
        p = [
            path(
                "M12 3 L14.4 8.2 L20 8.9 L15.9 12.9 L17 18.5 L12 15.8 L7 18.5 L8.1 12.9 L4 8.9 L9.6 8.2 Z",
                stroke=c,
                sw=sw,
            )
        ]
    elif name == "pin":
        p = [
            path(
                "M12 16.5 V21 M8.8 10.4 C8.2 11.3 7 11.9 7 13.4 V14.5 H17 V13.4 C17 11.9 15.8 11.3 15.2 10.4 V7.2 H15.5 C15.8 5.7 15.3 4 13.7 3.2 V2.5 H10.3 V3.2 C8.7 4 8.2 5.7 8.5 7.2 H8.8 Z",
                stroke=c,
                sw=sw,
            )
        ]
    elif name == "folder":
        p = [path("M21 19 C21 20.1 20.1 21 19 21 H5 C3.9 21 3 20.1 3 19 V6 C3 4.9 3.9 4 5 4 H9.5 L11.7 7.2 H19 C20.1 7.2 21 8.1 21 9.2 Z", stroke=c, sw=sw)]
    elif name == "gear":
        p = [
            circle(12, 12, 3.1, stroke=c, sw=sw),
            path(
                "M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z",
                stroke=c,
                sw=sw,
            ),
        ]
    elif name == "bell":
        p = [
            path("M18 8.5 C18 4.9 15.3 2.5 12 2.5 C8.7 2.5 6 4.9 6 8.5 C6 14 4 15.5 4 15.5 H20 C20 15.5 18 14 18 8.5", stroke=c, sw=sw),
            path("M10 19 C10.4 20.2 11.1 20.8 12 20.8 C12.9 20.8 13.6 20.2 14 19", stroke=c, sw=sw),
        ]
    elif name == "moon":
        p = [path("M20.4 13.2 C19.4 16.9 16 20 12 20 C7 20 3 16 3 11 C3 7 6.1 3.6 9.8 2.6 C8.7 4.7 8.1 7 8.1 9.4 C8.1 13.4 11 17 15 17.4 C17 17.6 18.9 17 20.4 15.8 C20.7 14.9 20.7 14.1 20.4 13.2 Z", stroke=c, sw=sw)]
    elif name == "lock":
        p = [rect(4, 10.5, 16, 11, 2.6, stroke=c, sw=sw), path("M7.6 10.5 V7.2 C7.6 4.6 9.6 2.6 12 2.6 C14.4 2.6 16.4 4.6 16.4 7.2 V10.5", stroke=c, sw=sw)]
    elif name == "user":
        p = [circle(12, 7.6, 3.8, stroke=c, sw=sw), path("M4.5 21 C5.2 16.9 8.1 14.8 12 14.8 C15.9 14.8 18.8 16.9 19.5 21", stroke=c, sw=sw)]
    elif name == "check":
        p = [path("M20 6.5 L9.6 17.5 L4 12", stroke=c, sw=sw)]
    elif name == "image":
        p = [rect(3, 3.5, 18, 17, 2.6, stroke=c, sw=sw), circle(8.6, 9, 1.7, stroke=c, sw=sw), path("M20.6 15.4 L15.5 10.3 L5 20.8", stroke=c, sw=sw)]
    elif name == "mic":
        p = [
            path("M12 2.6 C10.2 2.6 8.8 4 8.8 5.8 V11.4 C8.8 13.2 10.2 14.6 12 14.6 C13.8 14.6 15.2 13.2 15.2 11.4 V5.8 C15.2 4 13.8 2.6 12 2.6 Z", stroke=c, sw=sw),
            path("M18 11 V11.8 C18 15.2 15.3 17.8 12 17.8 C8.7 17.8 6 15.2 6 11.8 V11", stroke=c, sw=sw),
            line(12, 17.8, 12, 21.2, c, sw),
            line(8.6, 21.2, 15.4, 21.2, c, sw),
        ]
    elif name == "share":
        p = [
            circle(17.6, 5.8, 2.9, stroke=c, sw=sw),
            circle(6.4, 12, 2.9, stroke=c, sw=sw),
            circle(17.6, 18.2, 2.9, stroke=c, sw=sw),
            line(9, 10.7, 15, 7.2, c, sw),
            line(9, 13.3, 15, 16.8, c, sw),
        ]
    elif name == "trash":
        p = [
            line(4, 6.8, 20, 6.8, c, sw),
            path("M18.6 6.8 V19.4 C18.6 20.6 17.6 21.5 16.4 21.5 H7.6 C6.4 21.5 5.4 20.6 5.4 19.4 V6.8", stroke=c, sw=sw),
            path("M9.2 6.8 V5 C9.2 3.9 10.1 3 11.2 3 H12.8 C13.9 3 14.8 3.9 14.8 5 V6.8", stroke=c, sw=sw),
            line(10.2, 11, 10.4, 17.4, c, sw),
            line(13.8, 11, 13.6, 17.4, c, sw),
        ]
    elif name == "archive":
        p = [
            rect(2.8, 3.6, 18.4, 5, 1.4, stroke=c, sw=sw),
            path("M4.6 8.6 V19 C4.6 20.2 5.5 21 6.7 21 H17.3 C18.5 21 19.4 20.2 19.4 19 V8.6", stroke=c, sw=sw),
            line(9.8, 12.6, 14.2, 12.6, c, sw),
        ]
    elif name == "list":
        p = [
            line(8.6, 6, 20.4, 6, c, sw),
            line(8.6, 12, 20.4, 12, c, sw),
            line(8.6, 18, 20.4, 18, c, sw),
            circle(4.2, 6, 1.15, fill=c),
            circle(4.2, 12, 1.15, fill=c),
            circle(4.2, 18, 1.15, fill=c),
        ]
    elif name == "check-square":
        p = [
            path("M9 11.4 L11.6 14 L20.8 4.8", stroke=c, sw=sw),
            path("M20.6 12.4 V18.6 C20.6 19.9 19.6 20.9 18.4 20.9 H5.4 C4.1 20.9 3.2 19.9 3.2 18.6 V5.6 C3.2 4.3 4.1 3.4 5.4 3.4 H16.2", stroke=c, sw=sw),
        ]
    elif name == "tag":
        p = [
            path("M20.2 13.1 L13.1 20.2 C12.2 21.1 10.8 21.1 9.9 20.2 L3.4 13.7 C3 13.4 2.8 12.9 2.8 12.4 V4.2 C2.8 3.4 3.4 2.8 4.2 2.8 H12.4 C12.9 2.8 13.4 3 13.7 3.4 L20.2 9.9 C21.1 10.8 21.1 12.2 20.2 13.1 Z", stroke=c, sw=sw),
            circle(7.6, 7.6, 1.5, fill=c),
        ]
    elif name == "cloud":
        p = [path("M17.6 18.2 H6.9 C4.4 18.2 2.6 16.3 2.6 13.9 C2.6 11.6 4.3 9.8 6.5 9.7 C7 6.6 9.7 4.2 13 4.2 C16.5 4.2 19.4 6.9 19.7 10.3 C21.2 10.7 22.2 12 22.2 13.5 C22.2 16 20.1 18.2 17.6 18.2 Z", stroke=c, sw=sw)]
    elif name == "palette":
        p = [
            path("M12 2.8 C6.9 2.8 2.8 6.9 2.8 12 C2.8 17.1 6.9 21.2 12 21.2 C13.5 21.2 14.6 20.2 14.6 18.9 C14.6 18.2 14.3 17.7 14 17.2 C13.6 16.7 13.4 16.1 13.6 15.5 C13.9 14.8 14.7 14.5 15.5 14.5 H17.8 C19.8 14.5 21.2 13.1 21.2 11.2 C21.1 6.4 17.1 2.8 12 2.8 Z", stroke=c, sw=sw),
            circle(7.8, 10.4, 1.45, fill=c),
            circle(11.4, 7, 1.45, fill=c),
            circle(15.8, 8.2, 1.45, fill=c),
        ]
    elif name == "type":
        p = [line(4, 19.5, 11, 4.5, c, sw), line(11, 4.5, 18, 19.5, c, sw), line(6.6, 13.6, 15.4, 13.6, c, sw)]
    elif name == "file-text":
        p = [
            path("M13.6 2.6 H6.6 C5.3 2.6 4.2 3.7 4.2 5 V19 C4.2 20.3 5.3 21.4 6.6 21.4 H17.4 C18.7 21.4 19.8 20.3 19.8 19 V8.8 Z", stroke=c, sw=sw),
            path("M13.6 2.6 V8.8 H19.8", stroke=c, sw=sw),
            line(8, 13, 16, 13, c, sw),
            line(8, 16.8, 13.4, 16.8, c, sw),
        ]
    elif name == "dots":
        p = [circle(5.4, 12, 1.7, fill=c), circle(12, 12, 1.7, fill=c), circle(18.6, 12, 1.7, fill=c)]
    elif name == "sparkle":
        p = [
            path("M12 3 L13.6 9.2 L19.8 10.8 L13.6 12.4 L12 18.6 L10.4 12.4 L4.2 10.8 L10.4 9.2 Z", stroke=c, sw=sw),
        ]
    elif name == "clock":
        p = [circle(12, 12, 9, stroke=c, sw=sw), path("M12 6.8 V12 L15.6 14.6", stroke=c, sw=sw)]
    else:
        raise ValueError(name)
    return g + "".join(p) + "</g>"


# ------------------------------------------------------------------ компоненты


def status_bar(t, dark=False):
    ink = t["ink"]
    o = []
    o.append(text(54, 36, "9:41", 16, 600, ink, anchor="middle"))
    # сотовая связь — 4 столбика
    bx = 294
    for k in range(4):
        h = 4.5 + k * 2.4
        o.append(rect(bx + k * 5.4, 30.5 - (h - 4.5), 3.3, h + 1.2, 1.1, fill=ink))
    # wifi — три дуги
    wx, wy = 326, 32
    for k, r in enumerate((9.2, 6.0, 2.8)):
        x1, y1 = wx - r * 0.72, wy - r * 0.32 + k * 1.9
        x2, y2 = wx + r * 0.72, wy - r * 0.32 + k * 1.9
        o.append(
            path(f"M{x1:.1f} {y1:.1f} A{r} {r} 0 0 1 {x2:.1f} {y2:.1f}", stroke=ink, sw=2.1 - k * 0.35)
        )
    o.append(circle(wx, wy + 4.6, 1.5, fill=ink))
    # аккумулятор
    o.append(rect(345, 24.5, 23, 11.6, 3.2, stroke=ink, sw=1.2, op="0.45"))
    o.append(rect(347, 26.4, 15.6, 7.8, 1.8, fill=ink))
    o.append(path("M369.6 28.2 C370.8 28.8 370.8 31.8 369.6 32.4", stroke=ink, sw=1.4, op="0.45"))
    return "".join(o)


def home_indicator(t):
    return rect(128, 826, 134, 5, 2.5, fill=t["ink"], op="0.9" if t["name"] == "light" else "0.85")


def tab_bar(t, active):
    o = [rect(0, 760, W, 84, 0, fill=t["surface"]), line(0, 760.5, W, 760.5, t["divider"], 1)]
    items = [
        ("file-text", "Заметки", 49),
        ("folder", "Папки", 146),
        ("search", "Поиск", 244),
        ("gear", "Настройки", 341),
    ]
    for name, label, cx in items:
        on = label == active
        col = t["primary"] if on else t["ink3"]
        if on:
            o.append(rect(cx - 26, 772, 52, 30, 15, fill=t["primary_soft"]))
        o.append(icon(name, cx, 787, 22, col))
        o.append(text(cx, 812, label, 11, 600 if on else 500, col, anchor="middle"))
    return "".join(o)


def chip(t, x, y, label, w, active=False, size=14, h=36, fill=None, color=None):
    bg = t["primary"] if active else (fill or t["surface"])
    fg = t["on_primary"] if active else (color or t["ink2"])
    o = []
    if not active and fill is None:
        o.append(rect(x, y, w, h, h / 2, fill=t["surface"], stroke=t["divider"], sw=1.2))
    else:
        o.append(rect(x, y, w, h, h / 2, fill=bg))
    o.append(text(x + w / 2, y + h / 2 + size * 0.36, label, size, 600 if active else 500, fg, anchor="middle"))
    return "".join(o)


def chip_auto(t, x, y, label, active=False, size=14, h=36, padx=17, **kw):
    bold = kw.pop("bold", False)
    w = round(text_w(label, size, bold=active or bold)) + padx * 2
    return chip(t, x, y, label, w, active, size, h, **kw), w


def section_title(t, x, y, label, right=None):
    o = [text(x, y, label, 17, 700, t["ink"])]
    if right:
        o.append(text(W - 24, y, right, 14, 600, t["primary"], anchor="end"))
    return "".join(o)


def fab(t, cx=322, cy=718, r=29):
    o = [circle(cx, cy + 3, r, fill=t["shadow"], op=t["shadow_op"])]
    o.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{t["primary"]}"/>')
    o.append(icon("plus", cx, cy, 26, t["on_primary"], sw=2.4))
    return "".join(o)


def toggle(t, cx, cy, on=True):
    w, h = 46, 27
    x, y = cx - w / 2, cy - h / 2
    bg = t["primary"] if on else t["alt"]
    knob = t["on_primary"] if on else t["ink3"]
    kx = x + w - h / 2 - 3 if on else x + h / 2 + 3
    return rect(x, y, w, h, h / 2, fill=bg) + circle(kx, cy, 10.2, fill=knob)


def avatar(t, cx, cy, r=18, initials="АК", size=15):
    return circle(cx, cy, r, fill=t["primary_soft"]) + text(cx, cy + size * 0.36, initials, size, 700, t["primary"], anchor="middle")


def pinned_card(t, x, y, w, h, tint, title, body_lines, meta, badge=None):
    pad = 14
    o = [shadow_rect(x, y, w, h, 20, t), rect(x, y, w, h, 20, fill=tint)]
    o.append(text(x + pad, y + 36, title, 14.5, 700, t["ink"]))
    for k, bl in enumerate(body_lines):
        o.append(text(x + pad, y + 60 + k * 20, bl, 12, 400, t["ink2"]))
    # нижний ряд: слева — булавка и дата
    o.append(icon("pin", x + pad + 7, y + h - 21, 14, t["ink3"]))
    o.append(text(x + pad + 19, y + h - 16, meta, 11.5, 500, t["ink3"]))
    if badge:
        by = y + 60 + len(body_lines) * 20 + 2
        o.append(icon(badge[0], x + pad + 6, by, 13, t["ink3"]))
        o.append(text(x + pad + 18, by + 5, badge[1], 11.5, 500, t["ink3"]))
    return "".join(o)


def note_list_card(t, x, y, w, h, title, snippet, meta, tag=None, tag_bg=None, tag_fg=None):
    o = [shadow_rect(x, y, w, h, 18, t), rect(x, y, w, h, 18, fill=t["surface"])]
    o.append(text(x + 18, y + 30, title, 15.5, 700, t["ink"]))
    o.append(text(x + 18, y + 52, snippet, 13, 400, t["ink2"]))
    o.append(text(x + 18, y + h - 15, meta, 11.5, 500, t["ink3"]))
    if tag:
        tw = round(text_w(tag, 11.5, True)) + 18
        o.append(rect(x + w - 18 - tw, y + h - 29, tw, 20, 10, fill=tag_bg))
        o.append(text(x + w - 18 - tw / 2, y + h - 15, tag, 11.5, 600, tag_fg, anchor="middle"))
    return "".join(o)


def result_card(t, x, y, w, h, tspans_title, snippet, meta):
    o = [shadow_rect(x, y, w, h, 18, t), rect(x, y, w, h, 18, fill=t["surface"])]
    o.append(tspans_title)
    o.append(snippet)
    o.append(text(x + 18, y + h - 15, meta, 11.5, 500, t["ink3"]))
    return "".join(o)


def settings_row(t, x, y, w, h, icon_name, icon_tint, icon_soft, label, value=None, toggle_on=None, chevron=False, divider=True):
    o = []
    o.append(rect(x + 14, y + (h - 34) / 2, 34, 34, 10, fill=icon_soft))
    o.append(icon(icon_name, x + 31, y + h / 2, 19, icon_tint))
    o.append(text(x + 62, y + h / 2 + 5, label, 15, 600, t["ink"]))
    if value:
        o.append(text(x + w - 40, y + h / 2 + 5, value, 14, 500, t["ink3"], anchor="end"))
    if chevron:
        o.append(icon("chevron-right", x + w - 24, y + h / 2, 17, t["ink3"]))
    if toggle_on is not None:
        o.append(toggle(t, x + w - 42, y + h / 2, toggle_on))
    if divider:
        o.append(line(x + 62, y + h, x + w - 14, y + h, t["divider"], 1))
    return "".join(o)


def group_label(t, x, y, label):
    return text(x, y, label, 12, 700, t["ink3"], ls="0.08em")


# ---------------------------------------------------------------------- экраны


def screen_home(t):
    o = [rect(0, 0, W, H, 0, fill=t["bg"]), status_bar(t)]
    o.append(text(24, 100, "Заметки", 30, 800, t["ink"]))
    o.append(avatar(t, 348, 88, 19))

    # поиск
    o.append(shadow_rect(24, 122, 342, 48, 24, t))
    o.append(rect(24, 122, 342, 48, 24, fill=t["surface"]))
    o.append(icon("search", 52, 146, 20, t["ink3"]))
    o.append(text(72, 152, "Поиск по заметкам", 15, 400, t["ink3"]))

    # фильтры
    clips = [f'<clipPath id="chips"><rect x="0" y="182" width="{W}" height="48"/></clipPath>', '<g clip-path="url(#chips)">']
    x = 24
    for label, active in [("Все", True), ("Избранные", False), ("Чек-листы", False), ("Фото", False), ("Голос", False)]:
        s, w = chip_auto(t, x, 186, label, active=active)
        clips.append(s)
        x += w + 10
    clips.append("</g>")
    o.extend(clips)

    # закреплённые
    o.append(icon("pin", 34, 262, 17, t["ink"]))
    o.append(text(50, 268, "Закреплённые", 17, 700, t["ink"]))
    o.append(pinned_card(
        t, 24, 288, 166, 168, t["amber_soft"],
        "План на неделю",
        ["Типография: звонок", "Забрать посылку", "Билеты на пятницу"],
        "Вчера",
    ))
    o.append(pinned_card(
        t, 200, 288, 166, 168, t["primary_soft"],
        "Идеи для проекта",
        ["Собрать макет экрана", "Тёмная тема и иконки"],
        "Сегодня",
        badge=("check-square", "3 пункта"),
    ))

    # другие заметки
    o.append(section_title(t, 24, 502, "Другие заметки"))
    o.append(note_list_card(
        t, 24, 514, 342, 86,
        "Список покупок",
        "Молоко, хлеб, кофе, яблоки…",
        "Сегодня, 09:12", "Дом", t["green_soft"], t["green"],
    ))
    o.append(note_list_card(
        t, 24, 606, 342, 86,
        "Конспект встречи",
        "Обсудить сроки и новую палитру",
        "Вчера, 18:40", "Работа", t["blue_soft"], t["blue"],
    ))
    o.append(fab(t))
    o.append(tab_bar(t, "Заметки"))
    o.append(home_indicator(t))
    return "".join(o)


def screen_editor(t):
    o = [rect(0, 0, W, H, 0, fill=t["bg"]), status_bar(t)]
    o.append(icon("chevron-left", 38, 84, 24, t["ink"]))
    o.append(text(66, 89, "Изменено 2 мин назад", 13, 500, t["ink3"]))
    o.append(icon("star", 286, 84, 22, t["primary"]))
    o.append(icon("share", 326, 84, 21, t["ink2"]))
    o.append(icon("dots", 362, 84, 22, t["ink2"]))

    o.append(text(24, 156, "Идеи для проекта", 28, 800, t["ink"]))
    s, w = chip_auto(t, 24, 176, "Проект", size=12.5, h=28, padx=13,
                     fill=t["primary_soft"], color=t["primary"], bold=True)
    o.append(s)
    o.append(text(24 + w + 12, 195, "Сегодня, 14:32", 12.5, 500, t["ink3"]))

    o.append(text(24, 248, "Собрать макет главного экрана", 16, 400, t["ink2"]))
    o.append(text(24, 274, "и проверить тёмную тему.", 16, 400, t["ink2"]))

    items = [
        ("Выбрать палитру", True),
        ("Нарисовать иконки", False),
        ("Собрать прототип", False),
        ("Показать команде", False),
    ]
    y = 316
    for label, done in items:
        if done:
            o.append(rect(24, y - 17, 22, 22, 7, fill=t["primary"]))
            o.append(icon("check", 35, y - 6, 15, t["on_primary"], sw=2.6))
            o.append(text(60, y, label, 15.5, 500, t["ink3"]))
            o.append(rect(60, y - 5.5, round(text_w(label, 15.5)), 1.4, 0.7, fill=t["ink3"]))
        else:
            o.append(rect(24, y - 17, 22, 22, 7, fill="none", stroke=t["ink3"], sw=1.6))
            o.append(text(60, y, label, 15.5, 500, t["ink"]))
        y += 44
    o.append(icon("plus", 32, y + 6, 17, t["primary"], sw=2.2))
    o.append(text(50, y + 11, "Добавить пункт", 15, 600, t["primary"]))

    # нижняя панель инструментов
    o.append(shadow_rect(24, 744, 342, 62, 21, t))
    o.append(rect(24, 744, 342, 62, 21, fill=t["surface"]))
    tools = [("type", 62), ("check-square", 115), ("list", 168), ("image", 221), ("mic", 274), ("dots", 327)]
    for name, cx in tools:
        o.append(icon(name, cx, 775, 21, t["ink2"]))
    o.append(home_indicator(t))
    return "".join(o)


def screen_search(t):
    o = [rect(0, 0, W, H, 0, fill=t["bg"]), status_bar(t)]
    o.append(text(24, 100, "Поиск", 30, 800, t["ink"]))

    o.append(shadow_rect(24, 122, 342, 48, 24, t))
    o.append(rect(24, 122, 342, 48, 24, fill=t["surface"]))
    o.append(icon("search", 52, 146, 20, t["primary"]))
    o.append(text(72, 152, "проект", 15.5, 600, t["ink"]))
    o.append(circle(340, 146, 13, fill=t["alt"]))
    o.append(icon("x", 340, 146, 12, t["ink2"], sw=2.2))

    x = 24
    clip = [f'<clipPath id="schips"><rect x="0" y="182" width="{W}" height="48"/></clipPath>', '<g clip-path="url(#schips)">']
    for label, active in [("Везде", True), ("Заголовки", False), ("Текст", False), ("Метки", False)]:
        s, w = chip_auto(t, x, 186, label, active=active)
        clip.append(s)
        x += w + 10
    clip.append("</g>")
    o.extend(clip)

    o.append(section_title(t, 24, 268, "Недавние запросы"))
    x = 24
    clip2 = [f'<clipPath id="rchip"><rect x="0" y="282" width="{W}" height="46"/></clipPath>', '<g clip-path="url(#rchip)">']
    for label in ("покупки", "встреча", "книги", "рецепты"):
        s, w = chip_auto(t, x, 286, label, size=13, h=34, padx=15, fill=t["alt"], color=t["ink2"])
        clip2.append(s)
        x += w + 9
    clip2.append("</g>")
    o.extend(clip2)

    o.append(section_title(t, 24, 372, "Результаты", right="3 заметки"))

    def hl_text(x, y, size, weight, base, word, t):
        return (
            f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
            f'fill="{base}">{esc_pre(word, t)}</text>'
        )

    def esc_pre(title_parts, t):
        out = []
        for s, hl in title_parts:
            if hl:
                out.append(f'<tspan fill="{t["primary"]}" font-weight="700">{esc(s)}</tspan>')
            else:
                out.append(esc(s))
        return "".join(out)

    cards = [
        ([("Идеи для ", False), ("проекта", True)], "Собрать макет экрана и проверить тему", "Сегодня, 14:32 · Работа"),
        ([("Схема ", False), ("проекта", True)], "Структура экранов и навигация готовы", "Вчера, 11:05 · Работа"),
        ([("План ", False), ("проекта", True)], "Этапы, сроки и роли команды", "12 ноября · Работа"),
    ]
    y = 392
    for parts, snip, meta in cards:
        tt = hl_text(42, y + 32, 15.5, 700, t["ink"], parts, t)
        sn = text(42, y + 54, snip, 13, 400, t["ink2"])
        o.append(result_card(t, 24, y, 342, 84, tt, sn, meta))
        y += 96

    o.append(tab_bar(t, "Поиск"))
    o.append(home_indicator(t))
    return "".join(o)


def screen_folders(t):
    o = [rect(0, 0, W, H, 0, fill=t["bg"]), status_bar(t)]
    o.append(text(24, 100, "Папки", 30, 800, t["ink"]))
    o.append(circle(348, 88, 19, fill=t["primary_soft"]))
    o.append(icon("plus", 348, 88, 19, t["primary"], sw=2.2))

    folders = [
        ("Работа", "12 заметок", t["blue"], t["blue_soft"], 24, 128),
        ("Личное", "8 заметок", t["green"], t["green_soft"], 200, 128),
        ("Идеи", "23 заметки", t["amber"], t["amber_soft"], 24, 264),
        ("Покупки", "5 заметок", t["pink"], t["pink_soft"], 200, 264),
    ]
    for name, count, fg, soft, x, y in folders:
        o.append(shadow_rect(x, y, 166, 122, 20, t))
        o.append(rect(x, y, 166, 122, 20, fill=t["surface"]))
        o.append(rect(x + 18, y + 18, 42, 42, 13, fill=soft))
        o.append(icon("folder", x + 39, y + 39, 23, fg))
        o.append(text(x + 18, y + 88, name, 16, 700, t["ink"]))
        o.append(text(x + 18, y + 108, count, 12.5, 500, t["ink3"]))

    o.append(section_title(t, 24, 438, "Метки"))
    x = 24
    clip = [f'<clipPath id="tchip"><rect x="0" y="452" width="{W}" height="46"/></clipPath>', '<g clip-path="url(#tchip)">']
    for label in ("#проект", "#дом", "#книги", "#финансы"):
        s, w = chip_auto(t, x, 456, label, size=13, h=34, padx=15, fill=t["primary_soft"], color=t["primary"], bold=True)
        clip.append(s)
        x += w + 9
    clip.append("</g>")
    o.extend(clip)

    o.append(section_title(t, 24, 542, "Системные"))
    o.append(shadow_rect(24, 560, 342, 112, 18, t))
    o.append(rect(24, 560, 342, 112, 18, fill=t["surface"]))
    o.append(settings_row(t, 24, 560, 342, 56, "archive", t["blue"], t["blue_soft"], "Архив", value="24", chevron=True, divider=True))
    o.append(settings_row(t, 24, 616, 342, 56, "trash", t["pink"], t["pink_soft"], "Корзина", value="7", chevron=True, divider=False))

    o.append(tab_bar(t, "Папки"))
    o.append(home_indicator(t))
    return "".join(o)


def screen_settings(t):
    o = [rect(0, 0, W, H, 0, fill=t["bg"]), status_bar(t)]
    o.append(text(24, 100, "Настройки", 30, 800, t["ink"]))

    o.append(shadow_rect(24, 122, 342, 76, 18, t))
    o.append(rect(24, 122, 342, 76, 18, fill=t["surface"]))
    o.append(avatar(t, 62, 160, 23, size=17))
    o.append(text(98, 152, "Анна Ковалёва", 16, 700, t["ink"]))
    o.append(text(98, 174, "anna.kovaleva@notes.app", 12.5, 400, t["ink2"]))
    o.append(icon("chevron-right", 342, 160, 18, t["ink3"]))

    def group(y0, label, rows):
        out = [group_label(t, 24, y0, label)]
        card_y = y0 + 12
        out.append(shadow_rect(24, card_y, 342, 52 * len(rows), 18, t))
        out.append(rect(24, card_y, 342, 52 * len(rows), 18, fill=t["surface"]))
        for k, row in enumerate(rows):
            out.append(settings_row(t, 24, card_y + 52 * k, 342, 52, *row))
        return "".join(out), card_y + 52 * len(rows)

    g1, y1 = group(228, "ВНЕШНИЙ ВИД", [
        ("moon", t["primary"], t["primary_soft"], "Тема", "Светлая", None, True, True),
        ("type", t["green"], t["green_soft"], "Размер текста", "Средний", None, True, False),
    ])
    o.append(g1)
    g2, y2 = group(y1 + 28, "СИНХРОНИЗАЦИЯ", [
        ("cloud", t["blue"], t["blue_soft"], "Синхронизация", "Включена", None, False, True),
        ("clock", t["amber"], t["amber_soft"], "Резервные копии", "Ежедневно", None, True, False),
    ])
    o.append(g2)
    g3, y3 = group(y2 + 28, "БЕЗОПАСНОСТЬ", [
        ("user", t["pink"], t["pink_soft"], "Face ID", None, True, False, True),
        ("lock", t["ink2"], t["alt"], "Код-пароль", None, False, False, False),
    ])
    o.append(g3)
    g4, y4 = group(y3 + 28, "УВЕДОМЛЕНИЯ", [
        ("bell", t["primary"], t["primary_soft"], "Уведомления", None, True, False, False),
    ])
    o.append(g4)

    o.append(text(W / 2, y4 + 34, "Версия 1.0.0", 12, 500, t["ink3"], anchor="middle"))
    o.append(tab_bar(t, "Настройки"))
    o.append(home_indicator(t))
    return "".join(o)


def screen_icon():
    """Иконка приложения 1024×1024."""
    o = [
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="#7C6CF0"/><stop offset="1" stop-color="#5546D6"/></linearGradient></defs>',
        rect(0, 0, 1024, 1024, 224, fill="url(#g)"),
        rect(272, 222, 480, 580, 56, fill="#FFFFFF"),
        path("M652 222 L752 322 L652 322 Z", fill="#D8D2FF"),
        rect(342, 402, 340, 36, 18, fill="#C9C2FA"),
        rect(342, 492, 340, 36, 18, fill="#E4E0FF"),
        rect(342, 582, 220, 36, 18, fill="#E4E0FF"),
        circle(760, 760, 128, fill="#FFB443"),
        path("M706 762 L744 800 L812 722", stroke="#FFFFFF", sw=30, cap="round"),
    ]
    return "".join(o)


# ------------------------------------------------------------------------ main


def wrap(inner):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}">{inner}</svg>'
    )


def main():
    files = {
        "notes-home.svg": screen_home(LIGHT),
        "notes-home-dark.svg": screen_home(DARK),
        "notes-editor.svg": screen_editor(LIGHT),
        "notes-search.svg": screen_search(LIGHT),
        "notes-folders.svg": screen_folders(LIGHT),
        "notes-settings.svg": screen_settings(LIGHT),
    }
    for name, inner in files.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(wrap(inner))
        print("svg/", name, sep="")
    icon_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">'
        + screen_icon()
        + "</svg>"
    )
    with open(os.path.join(OUT, "app-icon.svg"), "w", encoding="utf-8") as f:
        f.write(icon_svg)
    print("svg/app-icon.svg")


if __name__ == "__main__":
    main()
