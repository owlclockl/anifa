# Тихие заметки

Приложение для заметок на Electron и Vite. Заметки сохраняются локально на устройстве, в файле `notes.json` в папке данных приложения Electron; в веб-превью используется localStorage.

Создавайте и редактируйте заметки, ищите их по тексту и закрепляйте важные. Ctrl+N — новая заметка, Ctrl+K — поиск. Сохранение автоматическое.

## Запуск

Установите Node.js 20+, затем:

```bash
npm install
npm run dev
```

Для сборки Windows: `npm run build && npx electron-builder --win --x64 --publish never`. Установщик появится в `release/`. При обычной установке `npm install` также скачивает Electron.
