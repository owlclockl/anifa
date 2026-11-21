# Slate Browser

Браузер для Android, полностью написанный на Rust. Весь интерфейс — это
Makepad UI (Rust + Splash DSL); страницы рендерит нативный Android WebView,
подключённый через Makepad native layer. Свой JNI-код не нужен.

## Что здесь есть

- **Правая колонка сайтов на всю высоту экрана.** Шесть крупных иконок
  (56 dp) в узком рельсе 64/72/84 dp; страница занимает всё оставшееся место.
- **Три вкладки** в верхней строке, адресная строка, назад/вперёд/перезагрузка/домой.
- **Стартовая страница** с поиском и частыми сайтами — чистый экран, без пляша.
- **История** (24 последних адреса) и **настройки**: тема, акцент, ширина
  рельса, подписи и поисковая система. Всё сохраняется через Makepad Storage.
- **Аппаратная кнопка «Назад»** сначала ведёт по истории страницы, потом
  возвращает на стартовую страницу.

Дизайн следует скиллу `unslop`: спокойный хром, один акцент, никаких
градиентов, свечений и эмодзи; насыщенность отдана содержимому сайтов.

## Сборка

Локально нужны Rust и Android toolchain Makepad:

```sh
cargo install --git https://github.com/makepad/makepad --rev 506ec05105b9adb08d1d21f9879df181b5244ea7 cargo-makepad
cd android-browser
cargo makepad android --abi=aarch64 toolchain-install
cargo makepad android --abi=aarch64 --package-name=com.owlclockl.slate.browser --app-label="Slate Browser" build -p slate-browser --release
```

APK появится в `android-browser/target/makepad-android-apk/`. В репозитории
есть workflow `.github/workflows/build-slate-browser.yml`, который делает то
же самое в GitHub Actions и выкладывает APK артефактом.

## Настройка

Значения по умолчанию и списки сайтов заданы константами в `src/main.rs`
(`SITES`, `ENGINES`, `Settings::default`). Пользовательские настройки меняются
в интерфейсе: кнопка шестерёнки в нижней части правого рельса.

Пакет: `com.owlclockl.slate.browser`, приложение: `Slate Browser`.

## Готовая сборка

Готовый ARM64 APK (minSdk 26) лежит в пре-релизе:
https://github.com/owlclockl/anifa/releases/tag/slate-browser-latest

Прямая ссылка на файл:
https://github.com/owlclockl/anifa/releases/download/slate-browser-latest/slate-browser.apk

SHA-256: `b3e8ffe42c67533c8a1e0d53d4f700c70387bd0d9476a64bde35786c57a41a8d`

Сборка делается workflow GitHub Actions; каждый успешный запуск обновляет этот релиз.

Перед публикацией CI проверяет APK: целостность ZIP, подпись apksigner (v2 и v3),
пакет, версию, minSdk/targetSdk и ABI. Публикуется только выровненный и подписанный
файл — промежуточный `.unaligned.apk` в релиз не попадает.
