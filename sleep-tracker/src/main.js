import "./style.css";

/* ---------- Storage ---------- */
const STORAGE_KEY = "sleep-tracker-data-v1";

function defaultData() {
  return {
    entries: [],
    settings: { targetHours: 7.5, bedtime: "23:00", reminder: true },
    timer: { active: false, startedAt: null },
  };
}

async function loadData() {
  if (window.sleepAPI?.load) {
    try {
      const data = await window.sleepAPI.load();
      if (data) return { ...defaultData(), ...data };
    } catch { /* fall through */ }
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...defaultData(), ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return defaultData();
}

async function saveData() {
  if (window.sleepAPI?.save) {
    try { await window.sleepAPI.save(state); } catch { /* ignore */ }
  }
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch { /* ignore */ }
}

/* ---------- Helpers ---------- */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function pad(n) { return String(n).padStart(2, "0"); }
function fmtDuration(min) {
  if (!Number.isFinite(min) || min < 0) return "—";
  const h = Math.floor(min / 60);
  const m = Math.round(min % 60);
  return `${h}h ${pad(m)}m`;
}
function fmtClock(min) {
  const total = ((min % 1440) + 1440) % 1440;
  return `${pad(Math.floor(total / 60))}:${pad(total % 60)}`;
}
function parseTime(str) {
  const [h, m] = String(str || "00:00").split(":").map(Number);
  return (Number.isFinite(h) ? h : 0) * 60 + (Number.isFinite(m) ? m : 0);
}
function durationBetween(bed, wake) {
  let d = wake - bed;
  if (d <= 0) d += 1440;
  return d;
}
function todayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
function addDays(dateStr, delta) {
  const d = new Date(dateStr + "T12:00:00");
  d.setDate(d.getDate() + delta);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}
function fmtDateShort(dateStr) {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
}
function fmtDateLong(dateStr) {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });
}
function uid() { return Math.random().toString(36).slice(2, 10) + Date.now().toString(36); }

function seedIfEmpty() {
  if (state.entries.length > 0) return;
  const patterns = [
    { bed: "22:45", wake: "06:30", q: 4 },
    { bed: "23:15", wake: "07:00", q: 4 },
    { bed: "23:50", wake: "06:45", q: 3 },
    { bed: "00:20", wake: "07:15", q: 3 },
    { bed: "23:00", wake: "07:30", q: 5 },
    { bed: "22:30", wake: "06:15", q: 4 },
    { bed: "23:40", wake: "07:05", q: 4 },
    { bed: "00:10", wake: "06:50", q: 2 },
    { bed: "23:05", wake: "07:20", q: 5 },
    { bed: "22:55", wake: "06:40", q: 4 },
    { bed: "23:25", wake: "07:10", q: 4 },
    { bed: "23:10", wake: "06:55", q: 3 },
    { bed: "22:40", wake: "07:00", q: 4 },
    { bed: "23:00", wake: "07:15", q: 4 },
  ];
  const today = todayStr();
  state.entries = patterns.map((p, i) => {
    const date = addDays(today, -(patterns.length - 1 - i));
    return {
      id: uid() + i,
      date,
      bedtime: p.bed,
      wakeTime: p.wake,
      durationMin: durationBetween(parseTime(p.bed), parseTime(p.wake)),
      quality: p.q,
      notes: i === 4 ? "Early night, felt rested" : i === 7 ? "Late screen time" : "",
      tags: i % 6 === 5 ? ["weekend"] : [],
    };
  });
}

/* ---------- State ---------- */
let state = defaultData();
let chartRange = 14;
let historyFilter = "all";
let formQuality = 0;
let formTags = new Set();
let timerInterval = null;
let holdTimeout = null;
let holdRaf = null;

/* ---------- Toast ---------- */
let toastTimer = null;
function showToast(text) {
  const toast = $("#toast");
  $("#toastText").textContent = text;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.hidden = true; }, 2600);
}

/* ---------- Navigation (tab pill) ---------- */
const viewTitles = {
  dashboard: ["Dashboard", "Last 14 nights"],
  log: ["Log sleep", "Add a night to your log"],
  history: ["History", "Every night you have recorded"],
  settings: ["Settings", "Target, reminders and data"],
};

function movePill(pill, container, activeBtn) {
  if (!pill || !activeBtn) return;
  pill.style.width = `${activeBtn.offsetWidth}px`;
  pill.style.transform = `translateX(${activeBtn.offsetLeft - 4}px)`;
}

function switchView(name) {
  $$(".nav-item").forEach((b) => b.classList.toggle("is-active", b.dataset.view === name));
  $$(".view").forEach((v) => v.classList.toggle("is-active", v.id === `view-${name}`));
  const active = $(`.nav-item[data-view="${name}"]`);
  movePill($("#navPill"), $("#nav"), active);
  const [title, sub] = viewTitles[name] || ["", ""];
  $("#viewTitle").textContent = title;
  $("#viewSubtitle").textContent = sub;
  if (name === "dashboard") renderDashboard();
  if (name === "history") renderHistory();
  if (name === "log") updatePreview();
}

/* ---------- Dashboard ---------- */
function entriesInLastDays(days) {
  const cutoff = addDays(todayStr(), -(days - 1));
  return state.entries.filter((e) => e.date >= cutoff).sort((a, b) => a.date.localeCompare(b.date));
}

function tweenNumber(el, to, formatter) {
  const from = Number(el.dataset.value || 0);
  const start = performance.now();
  const dur = 500;
  function step(now) {
    const t = Math.min(1, (now - start) / dur);
    const eased = 1 - Math.pow(1 - t, 3);
    const val = from + (to - from) * eased;
    el.textContent = formatter(val);
    if (t < 1) requestAnimationFrame(step);
    else el.dataset.value = to;
  }
  requestAnimationFrame(step);
}

function renderDashboard() {
  const targetMin = Math.round(state.settings.targetHours * 60);
  $("#legendTarget").textContent = fmtDuration(targetMin);
  const sorted = [...state.entries].sort((a, b) => b.date.localeCompare(a.date));
  const last = sorted[0];
  const last7 = entriesInLastDays(7);

  if (last) {
    tweenNumber($("#statLast"), last.durationMin, (v) => fmtDuration(v));
    $("#statLastChange").textContent = `${fmtDateShort(last.date)} · quality ${last.quality}/5`;
    $("#statLastChange").className = "stat-change";
  } else {
    $("#statLast").textContent = "—";
    $("#statLastChange").textContent = "No entries yet";
  }

  if (last7.length) {
    const avg = last7.reduce((s, e) => s + e.durationMin, 0) / last7.length;
    tweenNumber($("#statAvg"), avg, (v) => fmtDuration(v));
    const diff = avg - targetMin;
    $("#statAvgChange").textContent = diff >= 0
      ? `${fmtDuration(diff)} above target`
      : `${fmtDuration(-diff)} below target`;
    $("#statAvgChange").className = `stat-change ${diff >= 0 ? "is-good" : "is-bad"}`;
  } else {
    $("#statAvg").textContent = "—";
    $("#statAvgChange").textContent = "—";
  }

  const debt = last7.reduce((s, e) => s + Math.max(0, targetMin - e.durationMin), 0);
  tweenNumber($("#statDebt"), debt, (v) => fmtDuration(v));
  $("#statDebtChange").textContent = debt === 0 ? "No shortfall this week" : "Shortfall vs target, 7 days";
  $("#statDebtChange").className = `stat-change ${debt === 0 ? "is-good" : ""}`;

  if (last7.length) {
    const onTarget = last7.filter((e) => e.durationMin >= targetMin).length;
    const pct = Math.round((onTarget / last7.length) * 100);
    tweenNumber($("#statOnTarget"), pct, (v) => `${Math.round(v)}%`);
    $("#statOnTargetChange").textContent = `${onTarget} of ${last7.length} nights`;
  } else {
    $("#statOnTarget").textContent = "—";
    $("#statOnTargetChange").textContent = "—";
  }

  renderChart(targetMin);
  renderDebt(debt);
  renderTimer();
}

function renderChart(targetMin) {
  const chart = $("#chart");
  chart.innerHTML = "";
  const days = entriesInLastDays(chartRange);
  const byDate = new Map(days.map((e) => [e.date, e]));
  const maxHours = 11;
  const dates = [];
  for (let i = chartRange - 1; i >= 0; i--) dates.push(addDays(todayStr(), -i));

  const tooltip = $("#chartTooltip");
  dates.forEach((date) => {
    const entry = byDate.get(date);
    const col = document.createElement("div");
    col.className = "bar-col";
    const track = document.createElement("div");
    track.className = "bar-track";
    const bar = document.createElement("div");
    bar.className = "bar";
    const h = entry ? entry.durationMin / 60 : 0;
    bar.style.height = entry ? `${Math.min(100, (h / maxHours) * 100)}%` : "12%";
    if (!entry) bar.classList.add("is-empty");
    else if (entry.durationMin >= targetMin) bar.classList.add("is-target");
    bar.dataset.date = date;
    if (entry) {
      bar.addEventListener("mouseenter", () => {
        tooltip.hidden = false;
        tooltip.innerHTML = `<strong>${fmtDuration(entry.durationMin)}</strong>${fmtDateShort(date)} · ${entry.bedtime} → ${entry.wakeTime}`;
        const rect = bar.getBoundingClientRect();
        const wrap = chart.getBoundingClientRect();
        tooltip.style.left = `${rect.left - wrap.left + rect.width / 2 - 40}px`;
        tooltip.style.top = `${rect.top - wrap.top - 56}px`;
      });
      bar.addEventListener("mouseleave", () => { tooltip.hidden = true; });
    }
    track.appendChild(bar);
    const label = document.createElement("span");
    label.className = "bar-label";
    const d = new Date(date + "T12:00:00");
    label.textContent = chartRange > 14 ? d.getDate() : d.toLocaleDateString("en-GB", { weekday: "narrow" });
    col.appendChild(track);
    col.appendChild(label);
    chart.appendChild(col);
  });

  // Target line
  const line = document.createElement("div");
  line.className = "chart-target-line";
  line.style.bottom = `${(targetMin / 60 / maxHours) * 100}%`;
  chart.style.position = "relative";
  chart.appendChild(line);
}

function renderDebt(debt) {
  const pct = Math.min(100, (debt / (6 * 60)) * 100);
  $("#debtMiniValue").textContent = fmtDuration(debt);
  $("#debtMiniFill").style.width = `${pct}%`;
  $("#debtMiniNote").textContent = debt === 0 ? "On track for tonight" : "Try an earlier bedtime tonight";
  $("#debtBigValue").textContent = fmtDuration(debt);
  $("#debtBigFill").style.width = `${pct}%`;
  $("#debtBigNote").textContent = debt === 0
    ? "No debt recorded this week"
    : debt < 120 ? "A small shortfall. One good night clears it."
    : debt < 300 ? "Building up. Aim for your target tonight."
    : "High debt. Prioritise sleep this week.";
}

/* ---------- Timer (morph island + hold to wake) ---------- */
const RING_C = 464.96;

function renderTimer() {
  const active = state.timer.active;
  const btn = $("#timerButton");
  const label = $("#timerButtonLabel");
  const chip = $("#timerChip");
  btn.classList.toggle("is-running", active);
  chip.hidden = !active;
  if (!active) {
    $("#timerRingTime").textContent = "00:00";
    $("#timerRingLabel").textContent = "Not started";
    $("#timerRingFill").style.strokeDashoffset = RING_C;
    label.textContent = "Start sleep";
    $("#timerHint").textContent = "Press to start. Hold to wake up and save.";
    return;
  }
  label.textContent = "Hold to wake up";
  $("#timerHint").textContent = "Hold the button for a moment to wake up and save the night.";
  tickTimer();
}

function tickTimer() {
  clearInterval(timerInterval);
  const update = () => {
    if (!state.timer.active || !state.timer.startedAt) return;
    const elapsedMin = (Date.now() - state.timer.startedAt) / 60000;
    const h = Math.floor(elapsedMin / 60);
    const m = Math.floor(elapsedMin % 60);
    const s = Math.floor((Date.now() - state.timer.startedAt) / 1000 % 60);
    $("#timerRingTime").textContent = `${pad(h)}:${pad(m)}`;
    $("#timerRingLabel").textContent = "Sleeping";
    $("#timerChipTime").textContent = `${pad(h)}:${pad(m)}:${pad(s)}`;
    const targetMin = Math.round(state.settings.targetHours * 60);
    const pct = Math.min(1, elapsedMin / targetMin);
    $("#timerRingFill").style.strokeDashoffset = RING_C * (1 - pct);
  };
  update();
  timerInterval = setInterval(update, 1000);
}

function startTimer() {
  state.timer = { active: true, startedAt: Date.now() };
  saveData();
  renderTimer();
  showToast("Sleep timer started");
}

function finishTimer() {
  const started = new Date(state.timer.startedAt);
  const now = new Date();
  const bed = `${pad(started.getHours())}:${pad(started.getMinutes())}`;
  const wake = `${pad(now.getHours())}:${pad(now.getMinutes())}`;
  const durationMin = Math.max(1, Math.round((now - started) / 60000));
  const entry = {
    id: uid(),
    date: todayStr(),
    bedtime: bed,
    wakeTime: wake,
    durationMin,
    quality: 0,
    notes: "Logged with the timer",
    tags: [],
  };
  state.entries.push(entry);
  state.timer = { active: false, startedAt: null };
  clearInterval(timerInterval);
  saveData();
  renderTimer();
  showToast(`Saved ${fmtDuration(durationMin)} of sleep`);
}

function bindTimer() {
  const btn = $("#timerButton");
  btn.addEventListener("click", () => {
    if (!state.timer.active) startTimer();
  });
  const beginHold = (e) => {
    if (!state.timer.active) return;
    e.preventDefault();
    btn.classList.add("is-holding");
    holdTimeout = setTimeout(() => {
      btn.classList.remove("is-holding");
      finishTimer();
    }, 1200);
  };
  const cancelHold = () => {
    btn.classList.remove("is-holding");
    clearTimeout(holdTimeout);
  };
  btn.addEventListener("pointerdown", beginHold);
  btn.addEventListener("pointerup", cancelHold);
  btn.addEventListener("pointerleave", cancelHold);
}

/* ---------- Log form ---------- */
function getFormValues() {
  return {
    date: $("#fieldDate").value || todayStr(),
    bedtime: $("#bedtimeInput").value || "23:00",
    wakeTime: $("#waketimeInput").value || "07:00",
    notes: $("#fieldNotes").value.trim(),
  };
}

function updatePreview() {
  const v = getFormValues();
  const dur = durationBetween(parseTime(v.bedtime), parseTime(v.wakeTime));
  const targetMin = Math.round(state.settings.targetHours * 60);
  const pct = Math.min(100, Math.round((dur / targetMin) * 100));
  $("#durationPreview").textContent = fmtDuration(dur);
  $("#previewDate").textContent = fmtDateLong(v.date);
  $("#previewDuration").textContent = fmtDuration(dur);
  $("#previewTimes").textContent = `${v.bedtime} → ${v.wakeTime}`;
  $("#previewNotes").textContent = v.notes || "No notes yet";
  $("#previewGoalPct").textContent = `${pct}%`;
  $("#previewGoalFill").style.width = `${pct}%`;
  $("#previewMoon").style.opacity = String(0.25 + 0.75 * Math.min(1, dur / targetMin));
  renderPreviewStars();
}

function renderPreviewStars() {
  const wrap = $("#previewStars");
  wrap.innerHTML = "";
  for (let i = 1; i <= 5; i++) {
    const s = document.createElement("span");
    s.className = i <= formQuality ? "is-filled" : "";
    s.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z"/></svg>`;
    wrap.appendChild(s);
  }
}

function setStepperValue(which, timeStr) {
  const timeEl = $(`#${which}Value`);
  const rollEl = $(`#${which}Roll`);
  const inputEl = $(`#${which}Input`);
  inputEl.value = timeStr;
  rollEl.textContent = timeStr;
  timeEl.classList.add("is-rolling");
  rollEl.classList.add("is-in");
  setTimeout(() => {
    timeEl.textContent = timeStr;
    timeEl.classList.remove("is-rolling");
    rollEl.classList.remove("is-in");
  }, 200);
  updatePreview();
}

function bindSteppers() {
  $$(".stepper").forEach((stepper) => {
    const which = stepper.dataset.stepper;
    stepper.addEventListener("click", (e) => {
      const btn = e.target.closest(".stepper-btn");
      if (!btn) return;
      const delta = Number(btn.dataset.step);
      const input = $(`#${which}Input`);
      const next = fmtClock(parseTime(input.value) + delta);
      setStepperValue(which, next);
    });
  });
  $("#bedtimeInput").addEventListener("change", (e) => setStepperValue("bedtime", e.target.value));
  $("#waketimeInput").addEventListener("change", (e) => setStepperValue("waketime", e.target.value));
  $("#fieldDate").addEventListener("change", updatePreview);
  $("#fieldNotes").addEventListener("input", updatePreview);
}

function bindStars() {
  const qualityLabels = ["", "Rough night", "Below average", "Average", "Good night", "Great night"];
  $$("#stars .star").forEach((star) => {
    star.addEventListener("click", () => {
      formQuality = Number(star.dataset.value);
      $$("#stars .star").forEach((s) => {
        const filled = Number(s.dataset.value) <= formQuality;
        s.classList.toggle("is-filled", filled);
        s.setAttribute("aria-checked", String(Number(s.dataset.value) === formQuality));
      });
      star.classList.remove("is-popping");
      void star.offsetWidth;
      star.classList.add("is-popping");
      $("#qualityNote").textContent = qualityLabels[formQuality] || "Tap a star to rate the night";
      updatePreview();
    });
  });
}

function bindTags() {
  $$("#tags .tag").forEach((tag) => {
    tag.addEventListener("click", () => {
      const t = tag.dataset.tag;
      if (formTags.has(t)) { formTags.delete(t); tag.classList.remove("is-active"); }
      else { formTags.add(t); tag.classList.add("is-active"); }
      updatePreview();
    });
  });
}

function bindForm() {
  $("#sleepForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const err = $("#formError");
    const v = getFormValues();
    if (!v.date) { err.textContent = "Choose a wake date."; err.hidden = false; return; }
    if (state.entries.some((x) => x.date === v.date)) {
      err.textContent = "An entry for this date already exists. Delete it from History first.";
      err.hidden = false;
      return;
    }
    err.hidden = true;
    const btn = $("#saveButton");
    btn.disabled = true;
    btn.classList.add("is-loading");
    setTimeout(() => {
      const entry = {
        id: uid(),
        date: v.date,
        bedtime: v.bedtime,
        wakeTime: v.wakeTime,
        durationMin: durationBetween(parseTime(v.bedtime), parseTime(v.wakeTime)),
        quality: formQuality,
        notes: v.notes,
        tags: [...formTags],
      };
      state.entries.push(entry);
      saveData();
      btn.classList.remove("is-loading");
      btn.classList.add("is-success");
      btn.disabled = false;
      setTimeout(() => {
        btn.classList.remove("is-success");
        $("#sleepForm").reset();
        $("#fieldDate").value = todayStr();
        $("#bedtimeInput").value = "23:00";
        $("#waketimeInput").value = "07:00";
        $("#bedtimeValue").textContent = "23:00";
        $("#waketimeValue").textContent = "07:00";
        formQuality = 0;
        formTags.clear();
        $$("#stars .star").forEach((s) => s.classList.remove("is-filled"));
        $$("#tags .tag").forEach((t) => t.classList.remove("is-active"));
        $("#qualityNote").textContent = "Tap a star to rate the night";
        updatePreview();
        showToast("Entry saved");
      }, 900);
    }, 700);
  });
}

/* ---------- History ---------- */
function filteredEntries() {
  const sorted = [...state.entries].sort((a, b) => b.date.localeCompare(a.date));
  if (historyFilter === "week") {
    const cutoff = addDays(todayStr(), -6);
    return sorted.filter((e) => e.date >= cutoff);
  }
  if (historyFilter === "month") {
    const cutoff = addDays(todayStr(), -29);
    return sorted.filter((e) => e.date >= cutoff);
  }
  return sorted;
}

function starRow(quality) {
  let html = "";
  for (let i = 1; i <= 5; i++) {
    html += `<span class="${i <= quality ? "is-filled" : ""}"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11.525 2.295a.53.53 0 0 1 .95 0l2.31 4.679a2.123 2.123 0 0 0 1.595 1.16l5.166.756a.53.53 0 0 1 .294.904l-3.736 3.638a2.123 2.123 0 0 0-.611 1.878l.882 5.14a.53.53 0 0 1-.771.56l-4.618-2.428a2.122 2.122 0 0 0-1.973 0L6.396 21.01a.53.53 0 0 1-.77-.56l.881-5.139a2.122 2.122 0 0 0-.611-1.879L2.16 9.795a.53.53 0 0 1 .294-.906l5.165-.755a2.122 2.122 0 0 0 1.597-1.16z"/></svg></span>`;
  }
  return html;
}

function renderHistory() {
  const list = $("#historyList");
  const entries = filteredEntries();
  $("#historyCount").textContent = `${entries.length} ${entries.length === 1 ? "entry" : "entries"}`;
  $("#historyEmpty").hidden = entries.length > 0;
  list.innerHTML = "";
  entries.forEach((e) => {
    const item = document.createElement("article");
    item.className = "history-item";
    item.dataset.id = e.id;
    item.innerHTML = `
      <button class="history-row" aria-expanded="false">
        <span class="history-date"><strong>${fmtDateShort(e.date)}</strong><span>${new Date(e.date + "T12:00:00").toLocaleDateString("en-GB", { weekday: "long" })}</span></span>
        <span class="history-times mono">${e.bedtime} → ${e.wakeTime}</span>
        <span class="history-duration">${fmtDuration(e.durationMin)}</span>
        <span class="history-stars">${starRow(e.quality)}</span>
        <svg class="history-chevron" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
      </button>
      <div class="history-detail">
        <div class="history-detail-inner">
          <div class="history-detail-content">
            <p class="history-notes">${e.notes ? escapeHtml(e.notes) : "No notes for this night."}</p>
            ${e.tags.length ? `<div class="history-tags">${e.tags.map((t) => `<span class="history-tag">${escapeHtml(t)}</span>`).join("")}</div>` : ""}
            <div class="history-actions">
              <button class="history-delete">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                <span>Delete</span>
              </button>
            </div>
          </div>
        </div>
      </div>`;
    const row = item.querySelector(".history-row");
    row.addEventListener("click", () => {
      const open = item.classList.toggle("is-open");
      row.setAttribute("aria-expanded", String(open));
    });
    item.querySelector(".history-delete").addEventListener("click", () => {
      state.entries = state.entries.filter((x) => x.id !== e.id);
      saveData();
      renderHistory();
      showToast("Entry deleted");
    });
    list.appendChild(item);
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ---------- Settings ---------- */
function bindSettings() {
  const slider = $("#targetSlider");
  slider.value = state.settings.targetHours;
  $("#targetValue").textContent = fmtDuration(Math.round(state.settings.targetHours * 60));
  slider.addEventListener("input", () => {
    state.settings.targetHours = Number(slider.value);
    $("#targetValue").textContent = fmtDuration(Math.round(state.settings.targetHours * 60));
    saveData();
  });
  slider.addEventListener("change", () => showToast("Target updated"));

  const bedtime = $("#bedtimeSetting");
  bedtime.value = state.settings.bedtime;
  bedtime.addEventListener("change", () => {
    state.settings.bedtime = bedtime.value || "23:00";
    saveData();
    showToast("Bedtime updated");
  });

  const toggle = $("#reminderToggle");
  toggle.setAttribute("aria-checked", String(!!state.settings.reminder));
  toggle.addEventListener("click", () => {
    state.settings.reminder = !state.settings.reminder;
    toggle.setAttribute("aria-checked", String(state.settings.reminder));
    saveData();
    showToast(state.settings.reminder ? "Reminder on" : "Reminder off");
  });

  $("#exportButton").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sleep-tracker-${todayStr()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showToast("Data exported");
  });

  $("#importButton").addEventListener("click", () => $("#importFile").click());
  $("#importFile").addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(reader.result);
        if (!parsed || !Array.isArray(parsed.entries)) throw new Error("bad file");
        state = { ...defaultData(), ...parsed };
        saveData();
        syncSettingsUI();
        showToast("Data imported");
      } catch {
        showToast("Import failed: invalid file");
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  });

  $("#clearButton").addEventListener("click", () => {
    if (!confirm("Delete all sleep entries? This cannot be undone.")) return;
    state.entries = [];
    state.timer = { active: false, startedAt: null };
    saveData();
    renderDashboard();
    renderHistory();
    showToast("All data cleared");
  });
}

function syncSettingsUI() {
  $("#targetSlider").value = state.settings.targetHours;
  $("#targetValue").textContent = fmtDuration(Math.round(state.settings.targetHours * 60));
  $("#bedtimeSetting").value = state.settings.bedtime;
  $("#reminderToggle").setAttribute("aria-checked", String(!!state.settings.reminder));
}

/* ---------- Segmented controls ---------- */
function bindSegmented(containerId, pillId, onChange) {
  const container = $(`#${containerId}`);
  const pill = $(`#${pillId}`);
  const move = () => {
    const active = container.querySelector(".segmented-btn.is-active");
    if (active) movePill(pill, container, active);
  };
  container.addEventListener("click", (e) => {
    const btn = e.target.closest(".segmented-btn");
    if (!btn) return;
    container.querySelectorAll(".segmented-btn").forEach((b) => b.classList.remove("is-active"));
    btn.classList.add("is-active");
    move();
    onChange(btn.dataset.range || btn.dataset.filter);
  });
  requestAnimationFrame(move);
  window.addEventListener("resize", move);
}

/* ---------- Command palette ---------- */
const commands = [
  { id: "go-dashboard", label: "Go to Dashboard", hint: "View", run: () => switchView("dashboard") },
  { id: "go-log", label: "Log sleep", hint: "View", run: () => switchView("log") },
  { id: "go-history", label: "Open History", hint: "View", run: () => switchView("history") },
  { id: "go-settings", label: "Open Settings", hint: "View", run: () => switchView("settings") },
  { id: "timer-start", label: "Start sleep timer", hint: "Timer", run: () => { switchView("dashboard"); if (!state.timer.active) startTimer(); } },
  { id: "timer-stop", label: "Wake up and save", hint: "Timer", run: () => { if (state.timer.active) finishTimer(); else showToast("Timer is not running"); } },
  { id: "export", label: "Export data as JSON", hint: "Data", run: () => $("#exportButton").click() },
];

let paletteIndex = 0;
let paletteItems = [];

function openPalette() {
  $("#paletteBackdrop").hidden = false;
  $("#paletteInput").value = "";
  renderPalette("");
  setTimeout(() => $("#paletteInput").focus(), 30);
}
function closePalette() {
  $("#paletteBackdrop").hidden = true;
}
function renderPalette(query) {
  const q = query.trim().toLowerCase();
  paletteItems = commands.filter((c) => c.label.toLowerCase().includes(q));
  paletteIndex = 0;
  const list = $("#paletteList");
  list.innerHTML = "";
  if (!paletteItems.length) {
    list.innerHTML = `<li class="palette-empty">No matching commands</li>`;
    return;
  }
  paletteItems.forEach((c, i) => {
    const li = document.createElement("li");
    li.innerHTML = `<button class="palette-item${i === 0 ? " is-selected" : ""}" data-index="${i}">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></svg>
      <span>${c.label}</span>
      <span class="palette-hint-key"><kbd>${c.hint}</kbd></span>
    </button>`;
    list.appendChild(li);
  });
  list.querySelectorAll(".palette-item").forEach((btn) => {
    btn.addEventListener("click", () => runPalette(Number(btn.dataset.index)));
  });
}
function runPalette(i) {
  const cmd = paletteItems[i];
  if (!cmd) return;
  closePalette();
  cmd.run();
}
function bindPalette() {
  $("#searchBtn").addEventListener("click", openPalette);
  $("#paletteHint").addEventListener("click", openPalette);
  $("#paletteBackdrop").addEventListener("click", (e) => {
    if (e.target === e.currentTarget) closePalette();
  });
  $("#paletteInput").addEventListener("input", (e) => renderPalette(e.target.value));
  $("#paletteInput").addEventListener("keydown", (e) => {
    const items = $$("#paletteList .palette-item");
    if (e.key === "ArrowDown") {
      e.preventDefault();
      paletteIndex = Math.min(paletteItems.length - 1, paletteIndex + 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      paletteIndex = Math.max(0, paletteIndex - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      runPalette(paletteIndex);
      return;
    } else if (e.key === "Escape") {
      closePalette();
      return;
    } else return;
    items.forEach((el, i) => el.classList.toggle("is-selected", i === paletteIndex));
  });
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      $("#paletteBackdrop").hidden ? openPalette() : closePalette();
    }
    if (e.key === "Escape" && !$("#paletteBackdrop").hidden) closePalette();
  });
}

/* ---------- Magnetic button ---------- */
function bindMagnetic() {
  const btn = $("#saveButton");
  if (!btn || matchMedia("(hover: none)").matches) return;
  btn.addEventListener("pointermove", (e) => {
    const r = btn.getBoundingClientRect();
    const x = e.clientX - r.left - r.width / 2;
    const y = e.clientY - r.top - r.height / 2;
    btn.style.transform = `translate(${x * 0.08}px, ${y * 0.12}px)`;
  });
  btn.addEventListener("pointerleave", () => { btn.style.transform = ""; });
}

/* ---------- Init ---------- */
async function init() {
  state = await loadData();
  seedIfEmpty();
  await saveData();

  $("#fieldDate").value = todayStr();
  $("#bedtimeInput").value = "23:00";
  $("#waketimeInput").value = "07:00";

  $$(".nav-item").forEach((b) => b.addEventListener("click", () => switchView(b.dataset.view)));
  $$("[data-goto]").forEach((b) => b.addEventListener("click", () => switchView(b.dataset.goto)));
  requestAnimationFrame(() => {
    const active = $(".nav-item.is-active");
    movePill($("#navPill"), $("#nav"), active);
  });
  window.addEventListener("resize", () => {
    const active = $(".nav-item.is-active");
    movePill($("#navPill"), $("#nav"), active);
  });

  bindSegmented("rangeSegmented", "rangePill", (v) => { chartRange = Number(v); renderChart(Math.round(state.settings.targetHours * 60)); });
  bindSegmented("historySegmented", "historyPill", (v) => { historyFilter = v; renderHistory(); });

  bindTimer();
  bindSteppers();
  bindStars();
  bindTags();
  bindForm();
  bindSettings();
  bindPalette();
  bindMagnetic();

  renderDashboard();
  renderHistory();
  updatePreview();
  if (state.timer.active) tickTimer();
}

init();
