# Искра — Android

Нативная Android-оболочка с офлайн-копией ANSI-тренажёра в `app/src/main/assets/www/`. APK автоматически собирается при изменении файлов этой папки на ветке Arena.

## APK

GitHub Actions workflow `.github/workflows/android-apk.yml` собирает installable debug APK для изменений в `android/` на ветке Arena. Артефакт `iskra-android-apk` содержит `app-debug.apk`. APK подписан debug-ключом и подходит для установки вручную на Android (разрешите установку приложений из источника, откуда скачан файл).

## Локальная сборка

Нужны JDK 17, Android SDK Platform 35 / Build Tools 35.0.0 и Gradle 8.9:

```bash
cd android
gradle --no-daemon :app:assembleDebug
```

Выходной файл: `app/build/outputs/apk/debug/app-debug.apk`.
