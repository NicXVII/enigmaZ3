/**
 * EnigmaZ3 frontend_v2 — flusso lineare, meno pannelli, testi in italiano.
 */

import { buildMachineFromUI } from "./simulator.js";
import { postCrack } from "./api.js";

const ROTOR_NAMES = ["I", "II", "III", "IV", "V"];

const PATH_DEFS = [
  { stage: "plug_in", label: "Spine", sub: "entrata" },
  { stage: "r3_fwd", label: "Rotore veloce", sub: "avanti" },
  { stage: "r2_fwd", label: "Rotore medio", sub: "avanti" },
  { stage: "r1_fwd", label: "Rotore lento", sub: "avanti" },
  { stage: "refl", label: "Riflettore", sub: "" },
  { stage: "r1_back", label: "Rotore lento", sub: "ritorno" },
  { stage: "r2_back", label: "Rotore medio", sub: "ritorno" },
  { stage: "r3_back", label: "Rotore veloce", sub: "ritorno" },
  { stage: "plug_out", label: "Spine", sub: "uscita" },
];

let machine = null;

function idxToLetter(i) {
  return String.fromCharCode(65 + ((Number(i) % 26) + 26) % 26);
}

function readConfig() {
  return {
    rotorLeft: document.getElementById("rotor-left")?.value || "I",
    rotorMid: document.getElementById("rotor-mid")?.value || "II",
    rotorRight: document.getElementById("rotor-right")?.value || "III",
    posLeft: Number(document.getElementById("pos-left")?.value) || 0,
    posMid: Number(document.getElementById("pos-mid")?.value) || 0,
    posRight: Number(document.getElementById("pos-right")?.value) || 0,
    ringLeft: Number(document.getElementById("ring-left")?.value) || 0,
    ringMid: Number(document.getElementById("ring-mid")?.value) || 0,
    ringRight: Number(document.getElementById("ring-right")?.value) || 0,
    reflector: document.getElementById("reflector")?.value || "B",
    plugboard: document.getElementById("plugboard")?.value || "",
  };
}

function fillRotorSelects() {
  const ids = ["rotor-left", "rotor-mid", "rotor-right"];
  const defaults = ["I", "II", "III"];
  ids.forEach((id, idx) => {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = "";
    for (const n of ROTOR_NAMES) {
      const opt = document.createElement("option");
      opt.value = n;
      opt.textContent = `Rotore ${n}`;
      if (n === defaults[idx]) opt.selected = true;
      sel.appendChild(opt);
    }
  });
}

function syncPositionLabels() {
  const pairs = [
    ["pos-left", "pos-l-lbl"],
    ["pos-mid", "pos-m-lbl"],
    ["pos-right", "pos-r-lbl"],
  ];
  for (const [inpId, lblId] of pairs) {
    const v = document.getElementById(inpId)?.value ?? "0";
    const lbl = document.getElementById(lblId);
    if (lbl) lbl.textContent = idxToLetter(v);
  }
}

function syncWindowsFromMachine() {
  if (!machine) return;
  const set = (id, letter) => {
    const el = document.getElementById(id);
    if (el) el.textContent = letter;
  };
  set("win-left", machine.left.windowLetter());
  set("win-mid", machine.middle.windowLetter());
  set("win-right", machine.right.windowLetter());
}

function resetMachine() {
  machine = buildMachineFromUI(readConfig());
  syncWindowsFromMachine();
}

function initPathStrip() {
  const container = document.getElementById("path-strip");
  if (!container) return;
  container.innerHTML = "";
  PATH_DEFS.forEach((def, i) => {
    if (i > 0) {
      const ar = document.createElement("span");
      ar.className = "path-arrow";
      ar.textContent = "→";
      container.appendChild(ar);
    }
    const node = document.createElement("div");
    node.className = "path-node";
    node.dataset.stage = def.stage;
    const sub = def.sub ? `<span class="block font-normal normal-case opacity-80">${def.sub}</span>` : "";
    node.innerHTML = `<span>${def.label}</span>${sub}<span class="path-letter">—</span>`;
    container.appendChild(node);
  });
}

function setPathIdle() {
  document.querySelectorAll(".path-node").forEach((n) => {
    n.classList.remove("is-on", "is-past");
    const L = n.querySelector(".path-letter");
    if (L) L.textContent = "—";
  });
}

function applyPathEndState(steps) {
  document.querySelectorAll(".path-node").forEach((n) => {
    n.classList.remove("is-on", "is-past");
    const st = n.dataset.stage;
    const step = steps.find((s) => s.stage === st);
    const L = n.querySelector(".path-letter");
    if (L && step) L.textContent = step.to;
  });
}

function animateSteps(steps, delayMs, onDone) {
  let i = 0;

  function tick() {
    if (i >= steps.length) {
      document.querySelectorAll(".path-node").forEach((n) => n.classList.remove("is-on", "is-past"));
      applyPathEndState(steps);
      if (onDone) onDone();
      return;
    }

    const step = steps[i];
    document.querySelectorAll(".path-node").forEach((n) => {
      n.classList.remove("is-on", "is-past");
      const st = n.dataset.stage;
      const si = steps.findIndex((s) => s.stage === st);
      const L = n.querySelector(".path-letter");
      if (si >= 0 && si < i) {
        n.classList.add("is-past");
        if (L) L.textContent = steps[si].to;
      }
      if (st === step.stage) {
        n.classList.add("is-on");
        if (L) L.textContent = step.to;
      }
    });

    i += 1;
    window.setTimeout(tick, delayMs);
  }

  setPathIdle();
  tick();
}

function animMode() {
  const r = document.querySelector('input[name="anim"]:checked');
  return r ? r.value : "last";
}

async function onEncrypt() {
  const outEl = document.getElementById("ciphertext-out");
  const cap = document.getElementById("path-caption");
  const btn = document.getElementById("btn-encrypt");

  const plain = (document.getElementById("plaintext")?.value || "")
    .toUpperCase()
    .replace(/[^A-Z]/g, "");
  if (!plain.length) {
    if (outEl) outEl.textContent = "Inserisci almeno una lettera A–Z.";
    return;
  }

  if (btn) btn.disabled = true;
  if (outEl) outEl.textContent = "…";
  if (cap) cap.textContent = "";

  resetMachine();
  let cipher = "";
  let lastTrace = null;

  for (let k = 0; k < plain.length; k++) {
    const tr = machine.encryptCharWithTrace(plain[k]);
    cipher += tr.outputLetter;
    lastTrace = tr;
  }

  syncWindowsFromMachine();
  if (outEl) outEl.textContent = cipher;

  const mode = animMode();
  if (mode === "none" || !lastTrace) {
    applyPathEndState(lastTrace.steps);
    if (cap) {
      cap.textContent = `Ultima lettera: ${plain.slice(-1)} → ${lastTrace.outputLetter}`;
    }
    if (btn) btn.disabled = false;
    return;
  }

  if (cap) {
    cap.textContent = `Animazione: ultima lettera del messaggio (“${plain.slice(-1)}” → “${lastTrace.outputLetter}”).`;
  }

  animateSteps(lastTrace.steps, 70, () => {
    if (btn) btn.disabled = false;
  });
}

function setZ3Bar(pct) {
  const bar = document.getElementById("z3-bar");
  if (bar) bar.style.width = `${Math.min(100, Math.max(0, pct))}%`;
}

async function onCrack() {
  const btn = document.getElementById("btn-crack");
  const status = document.getElementById("z3-status");
  const resultEl = document.getElementById("z3-result");
  const crib = (document.getElementById("crib")?.value || "").toUpperCase().replace(/[^A-Z]/g, "");
  const ciphertext = (document.getElementById("ciphertext-out")?.textContent || "")
    .toUpperCase()
    .replace(/[^A-Z]/g, "");

  if (!crib.length || !ciphertext.length || ciphertext === "—") {
    if (status) status.textContent = "Servono crib e un testo cifrato (cifra prima il messaggio al punto 2–3).";
    return;
  }

  if (btn) btn.disabled = true;
  if (resultEl) {
    resultEl.classList.add("hidden");
    resultEl.innerHTML = "";
  }
  setZ3Bar(0);
  if (status) status.textContent = "Caricamento vincoli e ricerca nello spazio delle chiavi…";

  let t = 0;
  let progressTimer = window.setInterval(() => {
    t += 4;
    setZ3Bar(t);
    if (t >= 92 && progressTimer) window.clearInterval(progressTimer);
  }, 100);

  const cfg = readConfig();
  const payload = {
    crib,
    ciphertext,
    mode: "positions",
    guess_rotors: [cfg.rotorLeft, cfg.rotorMid, cfg.rotorRight],
    rotors: [cfg.rotorLeft, cfg.rotorMid, cfg.rotorRight],
    positions: [cfg.posLeft, cfg.posMid, cfg.posRight],
    rings: [cfg.ringLeft, cfg.ringMid, cfg.ringRight],
    reflector: cfg.reflector,
    plugboard: cfg.plugboard,
  };

  try {
    const res = await postCrack(payload);
    setZ3Bar(100);
    if (status) {
      status.textContent =
        res.status === "sat"
          ? "Trovata un’assegnazione coerente (demo o server)."
          : `Esito solver: ${res.status}`;
    }
    if (resultEl && res.status === "sat") {
      resultEl.classList.remove("hidden");
      const plug = (res.plugboard || []).map((p) => `${p[0]}↔${p[1]}`).join(", ") || "—";
      resultEl.innerHTML = `
        <p class="font-semibold text-emerald-900">Risultato (esempio se in modalità demo)</p>
        <ul class="mt-2 list-inside list-disc space-y-1 text-slate-700">
          <li><strong>Rotori:</strong> ${(res.rotors || []).join(" · ")}</li>
          <li><strong>Posizioni:</strong> ${(res.positions || []).join(", ")}</li>
          <li><strong>Anelli:</strong> ${(res.rings || []).join(", ")}</li>
          <li><strong>Spine:</strong> ${plug}</li>
        </ul>
        <p class="mt-2 text-xs text-slate-500">Con backend reale (<code>ENIGMA_API_BASE</code>) qui compariranno i valori calcolati da Z3.</p>
      `;
    }
  } catch (e) {
    setZ3Bar(0);
    if (status) status.textContent = `Errore: ${e.message || e}`;
  } finally {
    if (progressTimer) window.clearInterval(progressTimer);
    if (btn) btn.disabled = false;
  }
}

function init() {
  fillRotorSelects();
  initPathStrip();
  setPathIdle();
  resetMachine();
  syncPositionLabels();

  ["pos-left", "pos-mid", "pos-right"].forEach((id) => {
    document.getElementById(id)?.addEventListener("input", syncPositionLabels);
  });

  document.getElementById("btn-encrypt")?.addEventListener("click", () => onEncrypt());
  document.getElementById("btn-crack")?.addEventListener("click", () => onCrack());

  [
    "rotor-left",
    "rotor-mid",
    "rotor-right",
    "reflector",
    "plugboard",
    "ring-left",
    "ring-mid",
    "ring-right",
  ].forEach((id) => {
    document.getElementById(id)?.addEventListener("change", () => {
      resetMachine();
      setPathIdle();
    });
  });
}

init();
