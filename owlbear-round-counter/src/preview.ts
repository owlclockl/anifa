import "./style.css";

// Standalone preview used by the Vite dev server and the built index.html.
// The real popover uses main.ts and talks to Owlbear through the SDK.

const MIN_ROUND = 1;
const MAX_ROUND = 9999;

const roundEl = document.getElementById("round") as HTMLOutputElement;
const minusEl = document.getElementById("minus") as HTMLButtonElement;
const plusEl = document.getElementById("plus") as HTMLButtonElement;
const inputEl = document.getElementById("round-input") as HTMLInputElement;
const setEl = document.getElementById("set") as HTMLButtonElement;
const resetEl = document.getElementById("reset") as HTMLButtonElement;

let round = MIN_ROUND;

function clamp(value: number): number {
  if (!Number.isFinite(value)) return MIN_ROUND;
  return Math.min(MAX_ROUND, Math.max(MIN_ROUND, Math.round(value)));
}

function render() {
  roundEl.textContent = String(round);
  inputEl.value = String(round);
  minusEl.disabled = round <= MIN_ROUND;
  plusEl.disabled = round >= MAX_ROUND;
  resetEl.disabled = round === MIN_ROUND;
}

function setRound(value: number) {
  round = clamp(value);
  render();
}

minusEl.addEventListener("click", () => setRound(round - 1));
plusEl.addEventListener("click", () => setRound(round + 1));
resetEl.addEventListener("click", () => setRound(MIN_ROUND));
setEl.addEventListener("click", () => setRound(Number(inputEl.value)));

document.addEventListener("keydown", (event) => {
  if (event.key === "ArrowUp") {
    event.preventDefault();
    setRound(round + 1);
  } else if (event.key === "ArrowDown") {
    event.preventDefault();
    setRound(round - 1);
  }
});

render();
