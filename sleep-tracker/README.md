# Sleep Tracker

Desktop sleep log for steady nights. Built with Electron + Vite, motion design inspired by [designbookmark.com/motion](https://designbookmark.com/motion) (free to use).

## Run on your PC

Requirements: [Node.js](https://nodejs.org) 20+

```bash
cd sleep-tracker
npm install
npm run electron:dev   # dev mode with hot reload
```

## Build a desktop installer

```bash
npm run dist
```

Output goes to `release/` — `.exe` (Windows), `.dmg` (macOS), `.AppImage` (Linux).

## Web preview

```bash
npm run dev
```

Open http://localhost:5174 — same app, data in browser localStorage.

## Features

- Dashboard with nightly duration chart, sleep debt meter and goal ring
- Sleep timer: press to start, hold to wake up and save
- Log form with time steppers, star rating, tags and live preview
- History with expandable night cards
- Settings: target duration, bedtime, reminder, JSON export/import
- Command palette (`Ctrl+K`)

## Motion components used

Tab pill, segmented control, toggle switch, star rating, jelly range slider, number stepper with rolling digits, stat cards with tweened numbers, storage meter (sleep debt), expand cards, hold-to-confirm, morph island button, loading-to-success save, command palette, magnetic button.

Design follows the unslop skill: ink neutral ramp, one amber accent, Lucide icons, Inter type, one easing curve.
