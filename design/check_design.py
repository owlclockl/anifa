#!/usr/bin/env python3
"""Проверка палитр макетов на контраст по WCAG 2.2 (AA).

Правила (W3C WCAG 2.2, критерии 1.4.3 и 1.4.11):
  * обычный текст  — не ниже 4.5:1;
  * крупный текст  — не ниже 3:1 (≥24px, либо ≥18.66px жирный);
  * UI-элементы и значимые иконки — не ниже 3:1 к соседнему фону.

Запуск: python3 design/check_design.py
Ненулевой код выхода — есть провалившиеся пары.
"""
from __future__ import annotations

import sys


def srgb_lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * srgb_lin(r) + 0.7152 * srgb_lin(g) + 0.0722 * srgb_lin(b)


def contrast(fg: str, bg: str) -> float:
    l1, l2 = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


# ---------------------------------------------------------------- палитры
LIGHT = {
    "bg": "#F4F3F9", "surface": "#FFFFFF", "alt": "#ECEAF5",
    "ink": "#17161C", "ink2": "#55526B", "ink3": "#67627C",
    "primary": "#5B4BD6", "primary_soft": "#ECE9FF", "on_primary": "#FFFFFF",
    "green": "#0F6E48", "green_ui": "#1FA971", "green_soft": "#E2F5EC",
    "blue": "#1F56D6", "blue_ui": "#3B82F6", "blue_soft": "#E4EEFF",
    "pink": "#C22B66", "pink_ui": "#E64980", "pink_soft": "#FCE7EE",
    "amber": "#8A5F00", "amber_ui": "#B97E00", "amber_soft": "#FFF3DC",
}
DARK = {
    "bg": "#121118", "surface": "#1D1B25", "alt": "#2A2736",
    "ink": "#F4F3FA", "ink2": "#B6B1C9", "ink3": "#8F8AA5",
    "primary": "#9C8FFF", "primary_soft": "#2B2450", "on_primary": "#1A1726",
    "green": "#57D9A3", "green_ui": "#3ED598", "green_soft": "#122B20",
    "blue": "#8FB6FF", "blue_ui": "#71A5FF", "blue_soft": "#152742",
    "pink": "#FF8DB8", "pink_ui": "#FF6FA5", "pink_soft": "#33121F",
    "amber": "#FFC96B", "amber_ui": "#FFB443", "amber_soft": "#33280F",
}
# приложения из галереи
MUSIC = {"bg": "#121212", "surface": "#1E1C26", "glass": "#2A2733",
         "ink": "#F5F3FA", "ink2": "#B9B3C9", "accent": "#B39DFF",
         "pink": "#FF7AB8", "on_accent": "#17141F"}
FINANCE = {"bg": "#F6F7FB", "surface": "#FFFFFF", "ink": "#0F1B3D",
           "ink2": "#4A5578", "accent": "#0B6E52", "accent_soft": "#E0F3EC",
           "card1": "#22306B", "card2": "#2E4A9E", "on_card": "#FFFFFF",
           "red": "#C22B4E", "amber": "#8A5F00"}
HEALTH = {"bg": "#FBF6FF", "surface": "#FFFFFF", "ink": "#21005D",
          "ink2": "#4A3F72", "primary": "#6750A4", "primary_container": "#EADDFF",
          "on_primary": "#FFFFFF", "on_container": "#21005D",
          "green": "#0B5C3D", "green_container": "#CDEFD9",
          "orange": "#7A5300", "orange_container": "#FFE0B2"}
LANDING = {"bg": "#FAFAFF", "surface": "#FFFFFF", "ink": "#111827",
           "ink2": "#4B5563", "primary": "#5B4BD6", "on_primary": "#FFFFFF",
           "soft": "#ECE9FF"}

# (fg, bg, минимум, описание)
PAIRS = [
    # — светлая тема «Заметки» —
    ("ink", "bg", 4.5, "текст на фоне"), ("ink", "surface", 4.5, "текст на карточке"),
    ("ink2", "bg", 4.5, "вторичный текст на фоне"), ("ink2", "surface", 4.5, "вторичный текст на карточке"),
    ("ink3", "bg", 4.5, "подписи/даты на фоне"), ("ink3", "surface", 4.5, "подписи/даты на карточке"),
    ("on_primary", "primary", 4.5, "текст на акцентной кнопке"),
    ("primary", "surface", 4.5, "ссылка/активная вкладка на карточке"),
    ("primary", "bg", 4.5, "ссылка на фоне"),
    ("primary", "primary_soft", 4.5, "акцентный текст на мягком акценте"),
    ("green", "green_soft", 4.5, "зелёный текст на мягком зелёном"),
    ("green_ui", "surface", 3.0, "зелёная иконка на карточке (UI 3:1)"),
    ("blue", "blue_soft", 4.5, "синий текст на мягком синем"),
    ("blue_ui", "surface", 3.0, "синяя иконка на карточке (UI 3:1)"),
    ("pink", "pink_soft", 4.5, "розовый текст на мягком розовом"),
    ("pink_ui", "surface", 3.0, "розовая иконка на карточке (UI 3:1)"),
    ("amber", "amber_soft", 4.5, "янтарный текст на мягком янтарном"),
    ("amber_ui", "surface", 3.0, "янтарная иконка на карточке (UI 3:1)"),
    ("ink3", "alt", 4.5, "подпись на приглушённой плашке"),
    # — тёмная тема «Заметки» —
    ("ink", "bg", 4.5, "[тёмная] текст на фоне"), ("ink", "surface", 4.5, "[тёмная] текст на карточке"),
    ("ink2", "bg", 4.5, "[тёмная] вторичный текст"), ("ink3", "bg", 4.5, "[тёмная] подписи"),
    ("primary", "bg", 4.5, "[тёмная] акцентный текст на фоне"),
    ("primary", "surface", 4.5, "[тёмная] акцентный текст на карточке"),
    ("on_primary", "primary", 4.5, "[тёмная] текст на акцентной кнопке"),
    ("green", "green_soft", 4.5, "[тёмная] зелёный на мягком"),
    ("blue", "blue_soft", 4.5, "[тёмная] синий на мягком"),
    ("pink", "pink_soft", 4.5, "[тёмная] розовый на мягком"),
    ("amber", "amber_soft", 4.5, "[тёмная] янтарный на мягком"),
    # — музыка (тёмный, стекло) —
    ("ink", "bg", 4.5, "[музыка] текст на фоне"), ("ink", "surface", 4.5, "[музыка] текст на панели"),
    ("ink", "glass", 4.5, "[музыка] текст на стеклянной панели"),
    ("ink2", "surface", 4.5, "[музыка] вторичный текст на панели"),
    ("on_accent", "accent", 4.5, "[музыка] текст на акцентной кнопке"),
    ("accent", "bg", 4.5, "[музыка] акцентный текст на фоне"),
    ("pink", "bg", 4.5, "[музыка] розовый текст на фоне"),
    # — финансы (светлый) —
    ("ink", "bg", 4.5, "[финансы] текст на фоне"), ("ink", "surface", 4.5, "[финансы] текст на карточке"),
    ("ink2", "surface", 4.5, "[финансы] вторичный текст"),
    ("on_card", "card1", 4.5, "[финансы] текст на баланс-карте (тёмный градиент)"),
    ("on_card", "card2", 4.5, "[финансы] текст на баланс-карте (светлый градиент)"),
    ("accent", "accent_soft", 4.5, "[финансы] зелёный текст на плашке"),
    ("accent", "surface", 3.0, "[финансы] зелёная иконка (UI 3:1)"),
    ("red", "surface", 4.5, "[финансы] текст списания"),
    ("amber", "surface", 4.5, "[финансы] предупреждение"),
    # — здоровье (Material You) —
    ("ink", "bg", 4.5, "[здоровье] текст на фоне"), ("ink", "surface", 4.5, "[здоровье] текст на карточке"),
    ("ink2", "surface", 4.5, "[здоровье] вторичный текст"),
    ("on_primary", "primary", 4.5, "[здоровье] текст на primary (M3)"),
    ("on_container", "primary_container", 4.5, "[здоровье] текст на primary-container (M3)"),
    ("green", "green_container", 4.5, "[здоровье] зелёный на контейнере"),
    ("orange", "orange_container", 4.5, "[здоровье] оранжевый на контейнере"),
    # — лендинг —
    ("ink", "bg", 4.5, "[лендинг] заголовок на фоне"), ("ink2", "bg", 4.5, "[лендинг] текст на фоне"),
    ("on_primary", "primary", 4.5, "[лендинг] текст кнопки CTA"),
    ("primary", "soft", 4.5, "[лендинг] акцент на мягкой плашке"),
]


def main() -> int:
    themes = {"LIGHT": LIGHT, "DARK": DARK, "MUSIC": MUSIC,
              "FINANCE": FINANCE, "HEALTH": HEALTH, "LANDING": LANDING}
    # пары с ключами «тёмной» темы помечены префиксом описания
    failures = 0
    print(f"{'пара':<44} {'факт':>6} {'нужно':>6}  итог")
    print("-" * 72)
    for fg_key, bg_key, need, desc in PAIRS:
        t = DARK if desc.startswith("[тёмная]") else (
            MUSIC if desc.startswith("[музыка]") else (
            FINANCE if desc.startswith("[финансы]") else (
            HEALTH if desc.startswith("[здоровье]") else (
            LANDING if desc.startswith("[лендинг]") else LIGHT))))
        try:
            ratio = contrast(t[fg_key], t[bg_key])
        except KeyError as e:
            print(f"{desc:<44}   нет токена {e}")
            failures += 1
            continue
        ok = ratio >= need
        failures += 0 if ok else 1
        mark = "OK " if ok else "FAIL"
        print(f"{desc:<44} {ratio:>6.2f} {need:>6.1f}  {mark}")
    print("-" * 72)
    print("Провалов:", failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
