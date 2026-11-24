# Правила дизайна и проверки

Все макеты в `design/svg/` собраны по правилам, проверенным по открытым источникам
(ноябрь 2026), и автоматическому чекеру контраста `design/check_design.py`.

## 1. Сетка и отступы — 4/8pt

Все отступы, поля и зазоры кратны **4px или 8px** (8 · 16 · 24 · 32 · 48): это
базовая единица Material Design и Apple HIG; произвольные значения вроде 10 или
22 ломают ритм вёрстки. Межстрочный интервал текста — 1.4–1.6 от кегля.

Источники:
- [Mobile App Design Best Practices — 8pt grid](https://gegobyteapps.com/resources/mobile-app-design-best-practices)
- [8pt Spacing Grid](https://gridmakerpro.com/grids/typography-grids/8pt-spacing-grid/)
- [UI design rules: 6 visual tips, 8 button rules](https://digitalzoomstudio.net/2026/11/6-ui-tips-8-button-rules-and-5-ux-laws-that-make-an-app-feel-right/)

## 2. Контраст — WCAG 2.2 AA

| Что | Минимум | Критерий |
| --- | --- | --- |
| Обычный текст | **4.5:1** | 1.4.3 Contrast (Minimum), AA |
| Крупный текст (≥24px / ≥18.66px bold) | **3:1** | 1.4.3, AA |
| UI-элементы, значимые иконки, фокус | **3:1** | 1.4.11 Non-text Contrast, AA |
| AAA (усиленный) | 7:1 / 4.5:1 | 1.4.6 |

`python3 design/check_design.py` проверяет **56 пар** «текст/фон» и «иконка/фон»
всех шести палитр проекта (светлая, тёмная, музыка, финансы, здоровье, лендинг) —
все пары проходят AA. Светлые акценты специально разделены на два токена:
`green/blue/pink/amber` — тёмные, для мелкого текста на мягких плашках (4.5:1),
`*_ui` — яркие, для иконок рядом с подписью (3:1). В тёмной теме вместо чистого
чёрного используется off-black `#121118` (тренд 2026 и рекомендация Material).

Источники:
- [Color Contrast WCAG 2.2: A Developer's Fix Guide](https://www.a11yflow.dev/blog/color-contrast-wcag-developer-guide)
- [WCAG 2.2 Color Contrast: 4.5:1 AA, 3:1 Large Text](https://web-accessibility-checker.com/en/blog/color-contrast-checker-wcag-guide)
- [All 87 WCAG 2.2 Success Criteria](https://testparty.ai/blog/wcag-22-success-criteria-list)

## 3. Зоны нажатия

Минимум **44×44pt** (Apple HIG) и **48×48dp** (Material Design 3); между зонами —
не менее 8px. Все кнопки в макетах от 44px (кнопки 52–56px, FAB 58px, строки
настроек 52–56px), иконки 22–24px размещены в зонах ≥ 44px.

Источники:
- [iOS Human Interface Guidelines: A Practical Summary](https://www.floow.design/blog/ios-human-interface-guidelines-summary)
- [Touch Targets — UX Glossary](https://uxpatterns.dev/glossary/t/touch-targets)
- [Mobile App Accessibility Guide](https://newly.app/guides/mobile-app-accessibility)

## 4. Типографика — шкала Material 3

Используется сокращённая шкала M3 (Display/Headline/Title/Body/Label):
**28/36 (800)** заголовки экранов · **20/28 (700)** секции · **16/24 (700)**
карточки · **14/20 (400)** текст · **12/16 (500)** подписи. Одна гарнитура
(Inter), ≤ 3 начертаний, текст выровнен по левому краю, вместо `#000` —
near-black `#17161C`.

Источники:
- [Material Design 3 Typography (Android Developers)](https://developer.android.com/develop/ui/compose/designsystems/material3)
- [Material Design 3 Guide: Color, Type, Components](https://www.floow.design/blog/material-design-3-guide)
- [Material Design: Design System Fundamentals](https://devrecall.com/learn/material-design/design-system-fundamentals)

## 5. Цвет и композиция

- Правило **60/30/10**: нейтральный фон → поверхности → акцент.
- Цвета заданы **ролями** (ink / ink2 / ink3 / primary / soft), как в M3, а не
  конкретными hex-значениями в элементах.
- Одна акцентная (заполненная) кнопка на экран, CTA — в нижней трети (thumb zone).
- Вкладок в навигации 3–5, с короткими подписями.

Источники:
- [Mobile App UI Design Skill — 60/30/10, thumb zone, F-pattern](https://skillselion.com/skills/ceorkm/mobile-app-ui-design)
- [10 Mobile App Design Best Practices for 2026](https://market.gluestack.io/blog/mobile-app-design-best-practices)

## 6. Тренды 2026, использованные в галерее

- **Хирургический glassmorphism** — стеклянные панели только там, где слой
  временный (плеер «Мелодия»): полупрозрачная панель управления поверх обложки,
  но весь текст — на непрозрачных слоях с проверенным контрастом.
- **Тёмная тема как базовая** — off-black, не инверсия цветов.
- **Material You / динамический цвет** — экран «Ритм» построен на токенах M3
  (primary / primary-container / on-container), пастельная палитра.
- **Минимализм и мягкая глубина** — одна тень-масштаб `0 6px 18px / 7%`,
  скругления 12/16/20/28 из формы M3.

Источники:
- [Mobile UI Trends 2026: Glassmorphism to Spatial Computing](https://www.sanjaydey.com/mobile-ui-trends-2026-glassmorphism-spatial-computing/)
- [Best 5 Mobile App Design Trends in 2026](https://appbuildchat.inblog.io/best-5-mobile-app-design-trends-in-2026-166566)
- [Mobile App UI Design Inspiration for 2026](https://vp0.com/blogs/mobile-app-ui-design-inspiration-2026)

## Как проверить самостоятельно

```sh
python3 design/check_design.py     # 56 пар, все должны быть OK, код выхода 0
```

Для интерактивной проверки цвета используйте любой WCAG-чекер
(например, [getwcag.com](https://getwcag.com/en/contrast-checker)) — значения
токенов перечислены в `check_design.py` и на артборде `ui-kit.svg`.
