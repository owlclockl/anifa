#!/usr/bin/env python3
"""Галерея макетов: новые приложения и различные дизайны.

Экраны приложений (390×844): «Мелодия» (музыка, тёмный стеклянный стиль),
«Кошелёк» (финансы), «Ритм» (здоровье, Material You), онбординг «Заметок».
Разные форматы: UI-кит дизайн-системы, лендинг 1440×900, промо-баннер 1200×630.

Все палитры проверены на контраст WCAG 2.2 AA (см. check_design.py).
Запуск: python3 design/build_gallery.py
"""
from __future__ import annotations

import math
import os

from build_screens import (
    FONT, H, LIGHT, W, circle, esc, home_indicator, icon, line, path,
    rect, shadow_rect, status_bar, tab_bar, text, text_w, wrap,
)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "svg")
os.makedirs(OUT, exist_ok=True)

# ——— палитры галереи (все пары проверены check_design.py) ———
MUSIC = {
    "name": "music", "bg": "#121212", "surface": "#1E1C26", "glass": "#2A2733",
    "ink": "#F5F3FA", "ink2": "#B9B3C9", "accent": "#B39DFF",
    "pink": "#FF7AB8", "on_accent": "#17141F",
}
FIN = {
    "name": "fin", "bg": "#F6F7FB", "surface": "#FFFFFF", "alt": "#E7EAF2",
    "ink": "#0F1B3D", "ink2": "#4A5578", "ink3": "#4A5578",
    "accent": "#0B6E52", "accent_ui": "#0E8C6A", "accent_soft": "#E0F3EC",
    "card1": "#22306B", "card2": "#2E4A9E", "on_card": "#FFFFFF",
    "red": "#C22B4E", "amber": "#8A5F00", "primary": "#0B6E52",
    "primary_soft": "#E0F3EC", "on_primary": "#FFFFFF",
    "divider": "#E7EAF2", "shadow": "#0F1B3D", "shadow_op": "0.08",
}
HEA = {
    "name": "hea", "bg": "#FBF6FF", "surface": "#FFFFFF", "alt": "#F0E9F7",
    "ink": "#21005D", "ink2": "#4A3F72", "ink3": "#4A3F72",
    "primary": "#6750A4", "primary_soft": "#EADDFF", "on_primary": "#FFFFFF",
    "primary_container": "#EADDFF", "on_container": "#21005D",
    "green": "#0B5C3D", "green_container": "#CDEFD9",
    "orange": "#7A5300", "orange_container": "#FFE0B2",
    "divider": "#EDE6F5", "shadow": "#21005D", "shadow_op": "0.08",
}
LAN = {
    "name": "lan", "bg": "#FAFAFF", "surface": "#FFFFFF",
    "ink": "#111827", "ink2": "#4B5563", "primary": "#5B4BD6",
    "on_primary": "#FFFFFF", "soft": "#ECE9FF",
}


def svg(inner, w, h):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'viewBox="0 0 {w} {h}">{inner}</svg>'
    )


def app_tabbar(t, items, active):
    """Нижняя навигация приложения: свои вкладки и иконки."""
    o = [rect(0, 760, W, 84, 0, fill=t["surface"]), line(0, 760.5, W, 760.5, t["divider"], 1)]
    n = len(items)
    for k, (ic, label) in enumerate(items):
        cx = W / (2 * n) + k * (W / n)
        on = label == active
        col = t["primary"] if on else t["ink3"]
        if on:
            o.append(rect(cx - 26, 772, 52, 30, 15, fill=t["primary_soft"]))
        if ic in ("flame", "pulse", "chart", "wallet", "heart", "drop", "moon-z",
                  "arrow-up-right", "arrow-down-right", "download", "shuffle", "repeat"):
            o.append(gicon(ic, cx, 787, 22, col))
        else:
            o.append(icon(ic, cx, 787, 22, col))
        o.append(text(cx, 812, label, 12, 600 if on else 500, col, anchor="middle"))
    return "".join(o)


def grad(gid, c1, c2, x2=1, y2=1):
    return (
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="{x2}" y2="{y2}">'
        f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/>'
        f'</linearGradient></defs>'
    )


def gicon(name, cx, cy, size, color, sw=2):
    """Локальные иконки плеера/статистики вне набора build_screens."""
    s = size / 24
    g = f'<g transform="translate({cx - size / 2},{cy - size / 2}) scale({s:.4f})">'
    p = []
    if name == "play":
        p = [f'<path d="M8 5.5 L19 12 L8 18.5 Z" fill="{color}"/>']
    elif name == "prev":
        p = [
            f'<path d="M18 6 L18 18" stroke="{color}" stroke-width="{sw + .6}" stroke-linecap="round"/>',
            f'<path d="M16 12 L6 6.2 L6 17.8 Z" fill="{color}"/>',
        ]
    elif name == "next":
        p = [
            f'<path d="M6 6 L6 18" stroke="{color}" stroke-width="{sw + .6}" stroke-linecap="round"/>',
            f'<path d="M8 12 L18 6.2 L18 17.8 Z" fill="{color}"/>',
        ]
    elif name == "shuffle":
        p = [
            f'<path d="M3 6.5 H6.5 C8 6.5 9 7.2 10 8.6 L14 14.4 C15 15.8 16 16.5 17.5 16.5 H21" stroke="{color}" stroke-width="{sw}" fill="none" stroke-linecap="round"/>',
            f'<path d="M3 16.5 H6.5 C8 16.5 9 15.8 10 14.4 L14 8.6 C15 7.2 16 6.5 17.5 6.5 H21" stroke="{color}" stroke-width="{sw}" fill="none" stroke-linecap="round"/>',
            f'<path d="M18.6 3.8 L21.4 6.5 L18.6 9.2 M18.6 13.8 L21.4 16.5 L18.6 19.2" stroke="{color}" stroke-width="{sw}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
        ]
    elif name == "repeat":
        p = [
            f'<path d="M6.5 10 V8.5 A2.5 2.5 0 0 1 9 6 H18 M18 6 L15.4 3.4 M18 6 L15.4 8.6" stroke="{color}" stroke-width="{sw}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
            f'<path d="M17.5 14 V15.5 A2.5 2.5 0 0 1 15 18 H6 M6 18 L8.6 15.4 M6 18 L8.6 20.6" stroke="{color}" stroke-width="{sw}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
        ]
    elif name == "heart":
        p = [
            f'<path d="M12 20 C6 15.6 3.2 12.6 3.2 9.4 A4.2 4.2 0 0 1 12 7.2 A4.2 4.2 0 0 1 20.8 9.4 C20.8 12.6 18 15.6 12 20 Z" stroke="{color}" stroke-width="{sw}" fill="none" stroke-linejoin="round"/>',
        ]
    elif name == "download":
        p = [
            f'<path d="M12 4 V14.5 M7.6 10.6 L12 15 L16.4 10.6" stroke="{color}" stroke-width="{sw}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
            f'<path d="M4.5 19.5 H19.5" stroke="{color}" stroke-width="{sw}" stroke-linecap="round"/>',
        ]
    elif name == "arrow-up-right":
        p = [
            f'<path d="M7 17 L17 7 M8.4 7 H17 V15.6" stroke="{color}" stroke-width="{sw}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
        ]
    elif name == "arrow-down-right":
        p = [
            f'<path d="M7 7 L17 17 M8.4 17 H17 V8.4" stroke="{color}" stroke-width="{sw}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
        ]
    elif name == "wallet":
        p = [
            f'<rect x="3" y="6" width="18" height="13" rx="3" stroke="{color}" stroke-width="{sw}" fill="none"/>',
            f'<path d="M16 12.5 H21 V15 H16 A1.25 1.25 0 0 1 16 12.5 Z" fill="{color}"/>',
        ]
    elif name == "chart":
        p = [
            f'<path d="M4 20 V10 M10 20 V4 M16 20 V13 M21 20 H3" stroke="{color}" stroke-width="{sw}" fill="none" stroke-linecap="round"/>',
        ]
    elif name == "flame":
        p = [
            f'<path d="M12 3 C13.5 6.5 17 8 17 12.2 A5 5 0 0 1 7 12.2 C7 9.8 8.2 8.6 9 7.4 C9.6 8.6 10.6 9 11.2 8.4 C11.8 7.8 11.8 5.6 12 3 Z" stroke="{color}" stroke-width="{sw}" fill="none" stroke-linejoin="round"/>',
        ]
    elif name == "drop":
        p = [
            f'<path d="M12 3.5 C12 3.5 6.5 10 6.5 14 A5.5 5.5 0 0 0 17.5 14 C17.5 10 12 3.5 12 3.5 Z" stroke="{color}" stroke-width="{sw}" fill="none" stroke-linejoin="round"/>',
        ]
    elif name == "moon-z":
        p = [
            f'<path d="M20 13 A8 8 0 1 1 10.8 4 A6.4 6.4 0 0 0 20 13 Z" stroke="{color}" stroke-width="{sw}" fill="none" stroke-linejoin="round"/>',
        ]
    elif name == "pulse":
        p = [
            f'<path d="M3 12 H7 L9.5 6 L13 18 L15.5 12 H21" stroke="{color}" stroke-width="{sw}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>',
        ]
    else:
        raise ValueError(name)
    return g + "".join(p) + "</g>"


# ============================================================ 1. Онбординг
def screen_onboarding():
    t = LIGHT
    o = [rect(0, 0, W, H, 0, fill=t["bg"]), status_bar(t)]
    # декоративные карточки-иллюстрация (сетка 8pt, отступы 24)
    o.append(rect(24, 96, 342, 340, 28, fill=t["primary_soft"]))
    o.append(f'<g transform="rotate(-6 120 220)">' + shadow_rect(64, 156, 150, 116, 18, t) +
             rect(64, 156, 150, 116, 18, fill=t["amber_soft"]) +
             text(80, 188, "Список дел", 14, 700, t["ink"]) +
             text(80, 212, "• Позвонить", 12, 400, t["ink2"]) +
             text(80, 232, "• Купить хлеб", 12, 400, t["ink2"]) + "</g>")
    o.append(f'<g transform="rotate(5 260 250)">' + shadow_rect(190, 188, 150, 116, 18, t) +
             rect(190, 188, 150, 116, 18, fill=t["surface"]) +
             rect(206, 208, 40, 28, 8, fill=t["primary"]) +
             text(206, 262, "Идеи", 14, 700, t["ink"]) +
             text(206, 282, "Макет и темы", 12, 400, t["ink2"]) + "</g>")
    o.append(shadow_rect(96, 292, 180, 116, 18, t) +
             rect(96, 292, 180, 116, 18, fill=t["green_soft"]) +
             icon("check-square", 122, 322, 22, t["green_ui"]) +
             text(116, 360, "Чек-лист готов", 14, 700, t["ink"]) +
             text(116, 380, "3 из 5 пунктов", 12, 400, t["ink2"]))
    # текст
    o.append(text(24, 508, "Все заметки —", 28, 800, t["ink"]))
    o.append(text(24, 542, "в одном месте", 28, 800, t["ink"]))
    o.append(text(24, 582, "Заметки, чек-листы и идеи синхронизируются", 14, 400, t["ink2"]))
    o.append(text(24, 606, "между устройствами. Тёмная тема из коробки.", 14, 400, t["ink2"]))
    # точки
    for k in range(3):
        cx = 24 + 20 + k * 20
        o.append(circle(cx, 652, 4.5, fill=t["primary"] if k == 0 else t["alt"]))
    # кнопка (52px ≥ 44pt tap target)
    o.append(rect(24, 688, 342, 52, 16, fill=t["primary"]))
    o.append(text(195, 720, "Начать", 16, 700, t["on_primary"], anchor="middle"))
    o.append(text(195, 776, "Уже есть аккаунт? Войти", 14, 600, t["primary"], anchor="middle"))
    o.append(home_indicator(t))
    return "".join(o)


# ======================================================= 2. «Мелодия» (музыка)
def screen_music():
    t = MUSIC
    o = [rect(0, 0, W, H, 0, fill=t["bg"]), status_bar(t)]
    # верхняя панель на фоне (контраст текста проверен — не на градиенте)
    o.append(icon("chevron-left", 38, 84, 24, t["ink"]))
    o.append(text(195, 80, "СЕЙЧАС ИГРАЕТ", 12, 600, t["ink2"], anchor="middle", ls="0.08em"))
    o.append(text(195, 98, "альбом «Ночь»", 12, 400, t["ink2"], anchor="middle"))
    o.append(icon("dots", 352, 88, 22, t["ink"]))
    # обложка — градиент + декор
    o.append(grad("alb", "#7C6CF0", "#FF7AB8", x2=1, y2=1))
    o.append(rect(24, 124, 342, 306, 28, fill="url(#alb)"))
    o.append(circle(250, 216, 76, fill="#FFFFFF", op="0.14"))
    o.append(circle(122, 340, 50, fill="#FFFFFF", op="0.12"))
    o.append(circle(292, 372, 26, fill="#FFFFFF", op="0.18"))
    o.append(icon("moon", 160, 230, 88, "#FFFFFF", sw=1.6))
    # название
    o.append(text(24, 486, "Ночные шпили", 24, 800, t["ink"]))
    o.append(text(24, 514, "Мелодия Луны · 2026", 14, 400, t["ink2"]))
    o.append(gicon("heart", 342, 498, 24, t["pink"]))
    # прогресс (зона взаимодействия ≥ 44pt по панели)
    o.append(rect(24, 548, 342, 4, 2, fill=t["glass"]))
    o.append(rect(24, 548, 205, 4, 2, fill=t["accent"]))
    o.append(circle(229, 550, 8, fill=t["accent"]))
    o.append(text(24, 576, "2:14", 12, 500, t["ink2"]))
    o.append(text(366, 576, "3:47", 12, 500, t["ink2"], anchor="end"))
    # стеклянная панель управления (хирургический glassmorphism 2026)
    o.append(rect(24, 600, 342, 112, 28, fill="#FFFFFF", op="0.08"))
    o.append(rect(24, 600, 342, 112, 28, fill="none", stroke="#FFFFFF", sw=1.2, op="0.18"))
    o.append(gicon("shuffle", 72, 656, 24, t["ink2"]))
    o.append(gicon("prev", 136, 656, 30, t["ink"]))
    o.append(circle(210, 656, 34, fill=t["accent"]))
    o.append(gicon("play", 212, 656, 28, t["on_accent"]))
    o.append(gicon("next", 284, 656, 30, t["ink"]))
    o.append(gicon("repeat", 342, 656, 24, t["ink2"]))
    # очередь
    o.append(rect(24, 728, 342, 88, 20, fill=t["surface"]))
    o.append(text(40, 756, "Дальше в очереди", 12, 600, t["ink2"]))
    o.append(rect(40, 768, 36, 36, 12, fill=t["glass"]))
    o.append(gicon("pulse", 58, 786, 17, t["accent"]))
    o.append(text(90, 782, "Тихий двор · 3:12", 14, 600, t["ink"]))
    o.append(text(350, 786, "•••", 14, 600, t["ink2"], anchor="end"))
    o.append(home_indicator(t))
    return "".join(o)


# ====================================================== 3. «Кошелёк» (финансы)
def screen_finance():
    t = FIN
    o = [rect(0, 0, W, H, 0, fill=t["bg"]), status_bar(t)]
    o.append(text(24, 100, "Кошелёк", 28, 800, t["ink"]))
    o.append(circle(348, 88, 19, fill=t["accent_soft"]))
    o.append(icon("bell", 348, 88, 19, t["accent"]))
    # баланс-карта (градиент, текст ≥ 4.5:1 проверен)
    o.append(grad("bal", t["card1"], t["card2"]))
    o.append(rect(24, 124, 342, 168, 24, fill="url(#bal)"))
    o.append(text(48, 164, "Общий баланс", 12, 500, t["on_card"], op="0.85"))
    o.append(text(48, 208, "1 284 500 ₽", 28, 800, t["on_card"]))
    o.append(rect(48, 228, 130, 28, 14, fill="#FFFFFF", op="0.16"))
    o.append(gicon("arrow-up-right", 64, 242, 15, "#CDEFD9", sw=2.2))
    o.append(text(78, 247, "+12% за месяц", 12, 600, "#CDEFD9"))
    o.append(icon("dots", 338, 152, 22, t["on_card"]))
    o.append(gicon("wallet", 322, 262, 26, "#FFFFFF"))
    # график
    o.append(shadow_rect(24, 312, 342, 180, 20, t))
    o.append(rect(24, 312, 342, 180, 20, fill=t["surface"]))
    o.append(text(48, 348, "Расходы по дням", 16, 700, t["ink"]))
    o.append(text(342, 348, "7 дней", 12, 500, t["ink2"], anchor="end"))
    bars = [46, 78, 38, 92, 60, 108, 70]
    for k, bh in enumerate(bars):
        bx = 52 + k * 42
        col = t["accent"] if k == 5 else t["accent_soft"]
        o.append(rect(bx, 460 - bh, 22, bh, 8, fill=col))
        o.append(text(bx + 11, 478, "ПВСЧПСВ"[k], 11, 500, t["ink2"], anchor="middle"))
    # операции
    o.append(text(24, 540, "Последние операции", 20, 700, t["ink"]))
    rows = [
        ("Кофейня «Зерно»", "Сегодня · Еда", "− 480 ₽", t["red"], t["amber"]),
        ("Зарплата", "Вчера · Доход", "+ 210 000 ₽", t["accent"], t["accent_soft"]),
        ("Подписка «Музыка»", "12 ноября · Сервисы", "− 299 ₽", t["red"], t["accent_soft"]),
    ]
    y = 552
    for title, sub, amount, am_col, tile in rows:
        o.append(shadow_rect(24, y, 342, 64, 16, t))
        o.append(rect(24, y, 342, 64, 16, fill=t["surface"]))
        o.append(rect(40, y + 14, 36, 36, 12, fill=tile))
        icon_name = "flame" if "Кофейня" in title else ("download" if "Зарплата" in title else "heart")
        tile_icon = t["amber"] if "Кофейня" in title else t["accent"]
        o.append(gicon(icon_name, 58, y + 32, 18, tile_icon))
        o.append(text(90, y + 28, title, 14, 700, t["ink"]))
        o.append(text(90, y + 48, sub, 12, 400, t["ink2"]))
        o.append(text(350, y + 38, amount, 14, 700, am_col, anchor="end"))
        y += 72
    o.append(app_tabbar(t, [("wallet", "Главная"), ("chart", "Статистика"),
                            ("arrow-up-right", "Переводы"), ("gear", "Профиль")], "Главная"))
    o.append(home_indicator(t))
    return "".join(o)


# ===================================================== 4. «Ритм» (Material You)
def ring_arc(cx, cy, r, frac, color, sw):
    """Дуга активности: frac 0..1, старт сверху."""
    a = -90 + 360 * frac
    x2, y2 = cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))
    large = 1 if frac > 0.5 else 0
    return path(
        f"M {cx} {cy - r} A {r} {r} 0 {large} 1 {x2:.2f} {y2:.2f}",
        stroke=color, sw=sw,
    )


def screen_health():
    t = HEA
    o = [rect(0, 0, W, H, 0, fill=t["bg"]), status_bar(t)]
    o.append(text(24, 100, "Ритм дня", 28, 800, t["ink"]))
    o.append(circle(348, 88, 19, fill=t["primary_container"]))
    o.append(text(348, 94, "АК", 14, 700, t["on_container"], anchor="middle"))
    # hero-карта с кольцами (Material You: radius 28)
    o.append(rect(24, 124, 342, 220, 28, fill=t["primary_container"]))
    cx, cy = 132, 234
    for r, frac, col in ((58, 0.78, t["primary"]), (42, 0.62, t["green"]), (26, 0.45, t["orange"])):
        o.append(circle(cx, cy, r, stroke="#FFFFFF", sw=10, op="0.55"))
        o.append(ring_arc(cx, cy, r, frac, col, 10))
    o.append(text(212, 180, "Активность", 14, 600, t["on_container"]))
    o.append(text(212, 216, "78%", 28, 800, t["on_container"]))
    o.append(text(212, 244, "Калории 420 ккал", 12, 500, t["on_container"]))
    o.append(text(212, 264, "Цель почти закрыта", 12, 500, t["on_container"]))
    o.append(rect(212, 284, 122, 32, 16, fill=t["primary"]))
    o.append(text(273, 305, "Подробнее", 12, 700, t["on_primary"], anchor="middle"))
    # статистика 2×2
    stats = [
        ("Шаги", "8 420", "flame", t["green_container"], t["green"]),
        ("Сон", "7 ч 40 м", "moon-z", t["primary_container"], t["primary"]),
        ("Вода", "1,8 л", "drop", t["orange_container"], t["orange"]),
        ("Пульс", "62 уд/мин", "pulse", t["primary_container"], t["primary"]),
    ]
    for k, (label, value, ic, tile, col) in enumerate(stats):
        x = 24 + (k % 2) * 177
        y = 360 + (k // 2) * 116
        o.append(shadow_rect(x, y, 165, 104, 24, t))
        o.append(rect(x, y, 165, 104, 24, fill=t["surface"]))
        o.append(rect(x + 16, y + 16, 36, 36, 12, fill=tile))
        o.append(gicon(ic, x + 34, y + 34, 18, col))
        o.append(text(x + 16, y + 76, value, 16, 700, t["ink"]))
        o.append(text(x + 16, y + 96, label, 12, 500, t["ink2"]))
    # расширенная FAB-кнопка Material You (высота 56 ≥ 48dp)
    o.append(rect(24, 616, 342, 56, 16, fill=t["primary"]))
    o.append(icon("plus", 116, 644, 20, t["on_primary"], sw=2.4))
    o.append(text(136, 650, "Начать тренировку", 16, 700, t["on_primary"]))
    # совет
    o.append(rect(24, 692, 342, 64, 20, fill=t["green_container"]))
    o.append(gicon("heart", 56, 724, 20, t["green"]))
    o.append(text(84, 718, "Совет дня", 12, 700, t["green"]))
    o.append(text(84, 738, "Прогулка 20 минут снижает стресс", 12, 500, t["on_container"]))
    o.append(app_tabbar(t, [("flame", "День"), ("pulse", "Тренировки"),
                            ("chart", "История"), ("user", "Профиль")], "День"))
    o.append(home_indicator(t))
    return "".join(o)


# ================================================== 5. UI-кит дизайн-системы
def ui_kit():
    KW, KH = 1200, 1620
    t = LIGHT
    o = [rect(0, 0, KW, KH, 0, fill=t["bg"])]
    o.append(text(64, 88, "«Заметки» · Design System", 34, 800, t["ink"]))
    o.append(text(64, 122, "v2 · сетка 4/8pt · типографика по Material 3 · контраст WCAG 2.2 AA", 16, 400, t["ink2"]))
    o.append(rect(1032, 56, 104, 48, 14, fill=t["primary"]))
    o.append(text(1084, 86, "AA ✓", 16, 700, t["on_primary"], anchor="middle"))

    def section(x, y, label):
        return text(x, y, label, 20, 700, t["ink"]) + line(x, y + 16, x + 1072, y + 16, t["divider"], 1)

    # — цвета —
    o.append(section(64, 180, "Цветовые роли"))
    swatches = [
        ("bg", t["bg"], "#F4F3F9"), ("surface", t["surface"], "#FFFFFF"),
        ("alt", t["alt"], "#ECEAF5"), ("ink", t["ink"], "#17161C"),
        ("ink2", t["ink2"], "#55526B"), ("ink3", t["ink3"], "#67627C"),
        ("primary", t["primary"], "#5B4BD6"), ("primary_soft", t["primary_soft"], "#ECE9FF"),
        ("green", t["green"], "#0F6E48"), ("blue", t["blue"], "#1F56D6"),
        ("pink", t["pink"], "#C22B66"), ("amber", t["amber"], "#8A5F00"),
    ]
    for k, (name, color, hexv) in enumerate(swatches):
        x = 64 + (k % 6) * 180
        y = 216 + (k // 6) * 128
        o.append(rect(x, y, 160, 84, 14, fill=color, stroke=t["divider"], sw=1))
        o.append(text(x, y + 106, name, 13, 700, t["ink"]))
        o.append(text(x, y + 124, hexv, 12, 400, t["ink3"]))

    # — типографика —
    o.append(section(64, 500, "Типографическая шкала (Material 3)"))
    type_rows = [
        ("H1 · 28/36 · 800", "Заголовок экрана", 28, 800),
        ("H2 · 20/28 · 700", "Заголовок секции", 20, 700),
        ("Title · 16/24 · 700", "Заголовок карточки", 16, 700),
        ("Body · 14/20 · 400", "Основной текст — заметки и описания", 14, 400),
        ("Label · 12/16 · 500", "Подписи, даты, теги", 12, 500),
    ]
    y = 548
    for spec, sample, size, weight in type_rows:
        o.append(text(64, y + size, sample, size, weight, t["ink"]))
        o.append(text(1136, y + size, spec, 13, 500, t["ink3"], anchor="end"))
        y += 56

    # — сетка и радиусы —
    o.append(section(64, 860, "Сетка 4/8pt и радиусы"))
    for k, sp in enumerate((8, 16, 24, 32, 48)):
        x = 64 + k * 132
        o.append(rect(x, 900, sp, 40, 4, fill=t["primary"]))
        o.append(text(x, 962, f"{sp}px", 13, 600, t["ink2"]))
    for k, r in enumerate((12, 16, 20, 28)):
        x = 760 + k * 96
        o.append(rect(x, 896, 72, 48, r, fill=t["primary_soft"], stroke=t["primary"], sw=1.5))
        o.append(text(x + 36, 962, f"r{r}", 13, 600, t["ink2"], anchor="middle"))

    # — кнопки и поля —
    o.append(section(64, 1010, "Кнопки и поля (tap-target ≥ 44pt)"))
    o.append(rect(64, 1052, 220, 52, 16, fill=t["primary"]))
    o.append(text(174, 1085, "Основная", 16, 700, t["on_primary"], anchor="middle"))
    o.append(rect(308, 1052, 220, 52, 16, fill="none", stroke=t["primary"], sw=1.8))
    o.append(text(418, 1085, "Вторичная", 16, 700, t["primary"], anchor="middle"))
    o.append(rect(552, 1052, 220, 52, 16, fill=t["alt"]))
    o.append(text(662, 1085, "Тихая", 16, 700, t["ink2"], anchor="middle"))
    o.append(rect(796, 1052, 220, 52, 16, fill=t["pink"]))
    o.append(text(906, 1085, "Удалить", 16, 700, "#FFFFFF", anchor="middle"))
    # поле поиска + поле ввода
    o.append(rect(64, 1132, 500, 52, 26, fill=t["surface"], stroke=t["divider"], sw=1.4))
    o.append(icon("search", 96, 1158, 20, t["ink3"]))
    o.append(text(124, 1164, "Поиск по заметкам", 16, 400, t["ink3"]))
    o.append(rect(588, 1132, 500, 52, 14, fill=t["surface"], stroke=t["primary"], sw=1.8))
    o.append(text(612, 1164, "Название заметки", 16, 400, t["ink"]))
    o.append(line(756, 1146, 756, 1170, t["primary"], 2))
    o.append(text(588, 1216, "Активное поле: акцентная обводка 1.8px и курсор", 13, 400, t["ink3"]))

    # — чипы, переключатели, чекбоксы —
    o.append(section(64, 1260, "Состояния компонентов"))
    o.append(rect(64, 1302, 110, 36, 18, fill=t["primary"]))
    o.append(text(119, 1325, "Все", 14, 600, t["on_primary"], anchor="middle"))
    o.append(rect(186, 1302, 150, 36, 18, fill=t["surface"], stroke=t["divider"], sw=1.2))
    o.append(text(261, 1325, "Избранные", 14, 500, t["ink2"], anchor="middle"))
    o.append(rect(348, 1302, 110, 36, 18, fill=t["primary_soft"]))
    o.append(text(403, 1325, "#тег", 14, 600, t["primary"], anchor="middle"))
    # toggle
    o.append(rect(500, 1306, 46, 27, 13.5, fill=t["primary"]) + circle(533, 1319.5, 10, fill=t["on_primary"]))
    o.append(rect(560, 1306, 46, 27, 13.5, fill=t["alt"]) + circle(573, 1319.5, 10, fill=t["ink3"]))
    o.append(text(500, 1362, "вкл · выкл", 13, 500, t["ink3"]))
    # checkbox
    o.append(rect(640, 1304, 22, 22, 7, fill=t["primary"]))
    o.append(icon("check", 651, 1315, 15, t["on_primary"], sw=2.6))
    o.append(rect(680, 1304, 22, 22, 7, fill="none", stroke=t["ink3"], sw=1.6))
    o.append(text(640, 1362, "чекбокс ≥ 22px", 13, 500, t["ink3"]))
    # карточки-примеры теней
    o.append(shadow_rect(800, 1292, 328, 76, 18, t))
    o.append(rect(800, 1292, 328, 76, 18, fill=t["surface"]))
    o.append(text(820, 1322, "Тень карточки", 16, 700, t["ink"]))
    o.append(text(820, 1346, "0 6px 18px · 7% — мягкая, под фон", 12, 400, t["ink3"]))

    # — правила —
    o.append(section(64, 1410, "Правила, по которым собраны макеты"))
    rules = [
        "8pt-сетка: все отступы кратны 4/8px (W3C-практика, Material Design)",
        "Контраст AA: текст 4.5:1, крупный текст и UI 3:1 (WCAG 2.2, SC 1.4.3 / 1.4.11)",
        "Tap-targets: 44×44pt (Apple HIG) / 48×48dp (Material) + 8px между зонами",
        "Одна акцентная кнопка на экран, CTA в нижней трети (thumb zone)",
        "60/30/10 в цвете: нейтраль / поверхности / акцент; near-black вместо #000",
    ]
    y = 1452
    for r in rules:
        o.append(icon("check", 76, y, 16, t["green_ui"]))
        o.append(text(96, y + 5, r, 15, 400, t["ink2"]))
        y += 30
    return svg("".join(o), KW, KH)


# ============================================================ 6. Лендинг
def landing():
    LW, LH = 1440, 900
    t = LAN
    o = [rect(0, 0, LW, LH, 0, fill=t["bg"])]
    # навигация
    o.append(rect(96, 28, 40, 40, 12, fill=t["primary"]))
    o.append(icon("file-text", 116, 48, 22, t["on_primary"]))
    o.append(text(152, 55, "Заметки", 20, 800, t["ink"]))
    for k, label in enumerate(("Возможности", "Дизайн", "Тарифы", "Блог")):
        o.append(text(560 + k * 148, 55, label, 15, 500, t["ink2"]))
    o.append(rect(1176, 24, 168, 48, 14, fill=t["primary"]))
    o.append(text(1260, 55, "Скачать", 15, 700, t["on_primary"], anchor="middle"))
    # герой
    o.append(text(96, 220, "Все мысли —", 56, 800, t["ink"]))
    o.append(text(96, 286, "в одном месте", 56, 800, t["primary"]))
    o.append(text(96, 348, "Заметки, чек-листы и идеи с синхронизацией,", 18, 400, t["ink2"]))
    o.append(text(96, 380, "тёмной темой и продуманным макетом по WCAG 2.2.", 18, 400, t["ink2"]))
    o.append(rect(96, 428, 224, 56, 16, fill=t["primary"]))
    o.append(text(208, 463, "Попробовать", 17, 700, t["on_primary"], anchor="middle"))
    o.append(rect(344, 428, 224, 56, 16, fill="none", stroke=t["primary"], sw=1.8))
    o.append(text(456, 463, "Смотреть макеты", 17, 700, t["primary"], anchor="middle"))
    o.append(text(96, 520, "✓ Бесплатно для личных заметок    ✓ iOS · Android · Web", 14, 500, t["ink2"]))
    # телефон с макетом
    o.append(rect(936, 128, 348, 700, 48, fill="#100E1A"))
    o.append(rect(952, 144, 316, 668, 38, fill=t["soft"]))
    o.append(text(984, 208, "Заметки", 22, 800, t["ink"]))
    o.append(rect(984, 232, 252, 36, 18, fill=t["surface"]))
    o.append(text(1004, 255, "Поиск по заметкам", 11, 400, t["ink3"] if "ink3" in t else t["ink2"]))
    for k, (title, tint) in enumerate((("План на неделю", "#FFF3DC"), ("Идеи проекта", "#ECE9FF"))):
        x = 984 + (k % 2) * 130
        y = 288 + (k // 2) * 0
        o.append(rect(x, y, 122, 104, 14, fill=tint))
        o.append(text(x + 12, y + 28, title, 11, 700, t["ink"]))
        o.append(rect(x + 12, y + 42, 84, 6, 3, fill=t["ink2"], op="0.35"))
        o.append(rect(x + 12, y + 56, 66, 6, 3, fill=t["ink2"], op="0.35"))
        o.append(rect(x + 12, y + 70, 74, 6, 3, fill=t["ink2"], op="0.35"))
    for k, title in enumerate(("Список покупок", "Конспект встречи", "Книги на весну")):
        y = 412 + k * 84
        o.append(rect(984, y, 252, 68, 14, fill=t["surface"]))
        o.append(text(1000, y + 28, title, 12, 700, t["ink"]))
        o.append(rect(1000, y + 40, 150, 6, 3, fill=t["ink2"], op="0.3"))
    o.append(rect(1052, 760, 116, 28, 14, fill=t["primary"]))
    o.append(text(1110, 779, "+  новая", 12, 700, t["on_primary"], anchor="middle"))
    # карточки преимуществ
    feats = [
        ("Сетка 4/8pt", "Все отступы кратны 4px —", "ритм и порядок"),
        ("WCAG 2.2 AA", "Контраст каждой пары цветов", "проверен скриптом"),
        ("Тёмная тема", "Off-black #121212,", "а не чистый чёрный"),
    ]
    for k, (title, sub1, sub2) in enumerate(feats):
        x = 96 + k * 276
        o.append(rect(x, 612, 252, 132, 20, fill=t["surface"]))
        o.append(rect(x + 24, 636, 40, 40, 12, fill=t["soft"]))
        o.append(icon("check", x + 44, 656, 20, t["primary"]))
        o.append(text(x + 24, 706, title, 16, 700, t["ink"]))
        o.append(text(x + 24, 726, sub1, 12, 400, t["ink2"]))
        o.append(text(x + 24, 742, sub2, 12, 400, t["ink2"]))
    # подвал
    o.append(rect(0, 812, LW, 88, 0, fill=t["ink"]))
    o.append(text(96, 862, "© 2026 Заметки", 14, 500, "#FFFFFF"))
    o.append(text(1344, 862, "Дизайн-система · Figma · GitHub", 14, 500, "#FFFFFF", anchor="end"))
    return svg("".join(o), LW, LH)


# ======================================================= 7. Промо-баннер
def banner():
    BW, BH = 1200, 630
    o = [grad("ban", "#5B4BD6", "#8B7CFF"), rect(0, 0, BW, BH, 0, fill="url(#ban)")]
    o.append(circle(140, 560, 180, fill="#FFFFFF", op="0.07"))
    o.append(circle(1080, 80, 140, fill="#FFFFFF", op="0.10"))
    o.append(text(80, 180, "Заметки", 64, 800, "#FFFFFF"))
    o.append(text(80, 240, "Все мысли — в одном месте", 26, 500, "#FFFFFF", op="0.92"))
    for k, chip_t in enumerate(("iOS", "Android", "Web", "Тёмная тема")):
        w = round(text_w(chip_t, 15, True)) + 44
        x = 80 + sum(round(text_w(c, 15, True)) + 44 for c in ("iOS", "Android", "Web", "Тёмная тема")[:k]) + 12 * k
        o.append(rect(x, 300, w, 44, 22, fill="#FFFFFF", op="0.14"))
        o.append(rect(x, 300, w, 44, 22, fill="none", stroke="#FFFFFF", sw=1.2, op="0.5"))
        o.append(text(x + w / 2, 328, chip_t, 15, 600, "#FFFFFF", anchor="middle"))
    o.append(rect(80, 400, 232, 56, 16, fill="#FFFFFF"))
    o.append(text(196, 435, "Скачать бесплатно", 17, 700, "#5B4BD6", anchor="middle"))
    # телефон
    o.append(rect(800, 90, 260, 520, 40, fill="#100E1A"))
    o.append(rect(812, 102, 236, 496, 32, fill="#F4F3F9"))
    o.append(text(832, 150, "Заметки", 18, 800, "#17161C"))
    o.append(rect(832, 168, 196, 30, 15, fill="#FFFFFF"))
    o.append(text(848, 188, "Поиск", 11, 400, "#9793AC"))
    o.append(rect(832, 214, 94, 88, 12, fill="#FFF3DC"))
    o.append(rect(934, 214, 94, 88, 12, fill="#ECE9FF"))
    for k in range(3):
        o.append(rect(832, 318 + k * 66, 196, 52, 12, fill="#FFFFFF"))
        o.append(rect(846, 334 + k * 66, 120, 6, 3, fill="#9793AC"))
    o.append(rect(884, 522, 92, 26, 13, fill="#5B4BD6"))
    o.append(text(930, 540, "+ новая", 11, 700, "#FFFFFF", anchor="middle"))
    return svg("".join(o), BW, BH)


def main():
    files = {
        "notes-onboarding.svg": svg(screen_onboarding(), W, H),
        "app-music.svg": svg(screen_music(), W, H),
        "app-finance.svg": svg(screen_finance(), W, H),
        "app-health.svg": svg(screen_health(), W, H),
        "ui-kit.svg": ui_kit(),
        "landing.svg": landing(),
        "banner.svg": banner(),
    }
    for name, content in files.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(content)
        print("svg/", name, sep="")


if __name__ == "__main__":
    main()
