# Искра Судоку — Android

Нативная Android-оболочка содержит офлайн-копию Sudoku-игры в `app/src/main/assets/www/`. Игра включает сетку 9×9, четыре сложности, карандашные заметки, проверку ходов, подсказки, отмену и показ ответа.

## APK

GitHub Actions workflow `.github/workflows/android-apk.yml` собирает installable debug APK для изменений в `android/` на ветке Arena. Итоговый файл `apk/iskra.apk` подписан debug-ключом и предназначен для ручной установки на Android 6.0+.

## Локальная сборка

Нужны JDK 17, Android SDK Platform 35 / Build Tools 35.0.0 и Gradle 8.9:

```bash
cd android
gradle --no-daemon :app:assembleDebug
```

APK появится в `app/build/outputs/apk/debug/app-debug.apk`.
