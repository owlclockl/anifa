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
cargo install --git https://github.com/makepad/makepad --rev 506ec05105b9adb08d1d21f9879df181b5244ea7 --package cargo-makepad
cd android-browser
cargo makepad android --abi=aarch64 toolchain-install
cargo makepad android --abi=aarch64 --package-name=com.owlclockl.slate.browser --app-label="Slate Browser" build --release
```

APK появится в `android-browser/target/makepad-android-apk/`. В репозитории
есть workflow `.github/workflows/build-slate-browser.yml`, который делает то
же самое в GitHub Actions и выкладывает APK артефактом.

## Настройка

Значения по умолчанию и списки сайтов заданы константами в `src/main.rs`
(`SITES`, `ENGINES`, `Settings::default`). Пользовательские настройки меняются
в интерфейсе: кнопка шестерёнки в нижней части правого рельса.

Пакет: `com.owlclockl.slate.browser`, приложение: `Slate Browser`.
