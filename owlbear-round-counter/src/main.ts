import OBR from "@owlbear-rodeo/sdk";
import "./style.css";

const EXTENSION_ID = "com.owlclockl.round-counter";
const METADATA_KEY = `${EXTENSION_ID}/state`;
const MIN_ROUND = 1;
const MAX_ROUND = 9999;

type CounterState = {
  round: number;
  updatedBy: string;
  updatedAt: number;
};

type Theme = Awaited<ReturnType<typeof OBR.theme.getTheme>>;

const roundEl = byId<HTMLOutputElement>("round");
const minusEl = byId<HTMLButtonElement>("minus");
const plusEl = byId<HTMLButtonElement>("plus");
const inputEl = byId<HTMLInputElement>("round-input");
const setEl = byId<HTMLButtonElement>("set");
const resetEl = byId<HTMLButtonElement>("reset");
const roleEl = byId<HTMLElement>("role");
const syncEl = byId<HTMLElement>("sync");

let state: CounterState = { round: MIN_ROUND, updatedBy: "", updatedAt: 0 };
let canEdit = false;

function byId<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) {
    throw new Error(`Missing element #${id}`);
  }
  return element as T;
}

function clampRound(value: number): number {
  if (!Number.isFinite(value)) {
    return MIN_ROUND;
  }
  return Math.min(MAX_ROUND, Math.max(MIN_ROUND, Math.round(value)));
}

function readState(metadata: Record<string, unknown>): CounterState {
  const raw = metadata[METADATA_KEY];
  if (!raw || typeof raw !== "object") {
    return state;
  }
  const value = raw as Partial<CounterState>;
  if (typeof value.round !== "number") {
    return state;
  }
  return {
    round: clampRound(value.round),
    updatedBy: typeof value.updatedBy === "string" ? value.updatedBy : "",
    updatedAt: typeof value.updatedAt === "number" ? value.updatedAt : 0,
  };
}

function render() {
  roundEl.textContent = String(state.round);
  inputEl.value = String(state.round);
  roleEl.textContent = canEdit ? "GM" : "Player";
  syncEl.textContent = state.updatedBy
    ? `Shared by ${state.updatedBy}`
    : "No changes in this scene yet";

  minusEl.disabled = !canEdit || state.round <= MIN_ROUND;
  plusEl.disabled = !canEdit || state.round >= MAX_ROUND;
  setEl.disabled = !canEdit;
  resetEl.disabled = !canEdit || state.round === MIN_ROUND;
  inputEl.disabled = !canEdit;

  void OBR.action.setBadgeText(`R${state.round}`).catch((error) => {
    console.warn("Could not set extension badge", error);
  });
}

async function setRound(value: number) {
  if (!canEdit) {
    return;
  }
  const round = clampRound(value);
  if (round === state.round) {
    return;
  }
  const next: CounterState = {
    round,
    updatedBy: OBR.player.id,
    updatedAt: Date.now(),
  };
  state = next;
  render();
  await OBR.scene
    .setMetadata({ [METADATA_KEY]: next })
    .catch((error) => console.error("Could not save round", error));
}

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.style.setProperty("--bg", theme.background.default);
  root.style.setProperty("--paper", theme.background.paper);
  root.style.setProperty("--line", theme.secondary.main);
  root.style.setProperty("--text", theme.text.primary);
  root.style.setProperty("--muted", theme.text.secondary);
  root.style.setProperty("--accent", theme.primary.main);
  root.style.colorScheme = theme.mode === "DARK" ? "dark" : "light";
}

function bindEvents() {
  minusEl.addEventListener("click", () => void setRound(state.round - 1));
  plusEl.addEventListener("click", () => void setRound(state.round + 1));
  resetEl.addEventListener("click", () => void setRound(MIN_ROUND));
  setEl.addEventListener("click", () => void setRound(Number(inputEl.value)));

  document.addEventListener("keydown", (event) => {
    if (!canEdit) {
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      void setRound(state.round + 1);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      void setRound(state.round - 1);
    } else if (event.key === "Enter") {
      const value = Number(inputEl.value);
      if (Number.isFinite(value)) {
        void setRound(value);
      }
    }
  });
}

OBR.onReady(async () => {
  const [metadata, role, theme] = await Promise.all([
    OBR.scene.getMetadata(),
    OBR.player.getRole(),
    OBR.theme.getTheme(),
  ]);

  state = readState(metadata);
  canEdit = role === "GM";
  applyTheme(theme);
  bindEvents();
  render();

  OBR.scene.onMetadataChange((metadata) => {
    state = readState(metadata);
    render();
  });
  OBR.player.onChange(() => {
    void OBR.player.getRole().then((nextRole) => {
      canEdit = nextRole === "GM";
      render();
    });
  });
  OBR.theme.onChange(applyTheme);
});
