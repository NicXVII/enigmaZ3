/**
 * EnigmaZ3 single-page app — wires simulator, UI, API, solver visualization.
 */

import { buildMachineFromUI } from "./simulator.js";
import { postCrack } from "./api.js";
import {
  initSchematic,
  updateSchematicActive,
  flashRotorWindows,
  setStatus,
  setTab,
  bindTabs,
  fillRotorSelects,
  renderResults,
  appendTrace,
  clearTrace,
} from "./ui.js";
import { SolverVisualizer, appendSolverLog } from "./solver-visualizer.js";

let machine = null;
let stepIndex = 0;
let pendingPlain = "";
let visualizer = null;

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

function syncWindowsFromMachine() {
  if (!machine) return;
  const L = machine.left.windowLetter();
  const M = machine.middle.windowLetter();
  const R = machine.right.windowLetter();
  const wl = document.getElementById("win-left");
  const wm = document.getElementById("win-mid");
  const wr = document.getElementById("win-right");
  if (wl) wl.textContent = L;
  if (wm) wm.textContent = M;
  if (wr) wr.textContent = R;
}

function resetMachineFromForm() {
  machine = buildMachineFromUI(readConfig());
  stepIndex = 0;
  syncWindowsFromMachine();
}

function animateLetterTrace(traceResult, onComplete) {
  const { steps, windows } = traceResult;
  let i = 0;

  function next() {
    if (i >= steps.length) {
      updateSchematicActive(null);
      flashRotorWindows(windows);
      syncWindowsFromMachine();
      if (onComplete) onComplete();
      return;
    }
    const s = steps[i];
    updateSchematicActive(s.stage, s.to);
    const curIn = document.getElementById("current-in");
    const curOut = document.getElementById("current-out");
    if (curIn) curIn.textContent = traceResult.inputLetter;
    if (curOut && i === steps.length - 1) curOut.textContent = traceResult.outputLetter;
    else if (curOut && i < steps.length - 1) curOut.textContent = "…";
    i += 1;
    window.setTimeout(next, 95);
  }
  next();
}

async function runSimulate() {
  const traceEl = document.getElementById("trace-panel");
  const plain = (document.getElementById("plaintext")?.value || "")
    .toUpperCase()
    .replace(/[^A-Z]/g, "");
  if (!plain.length) {
    setStatus("idle", "Idle");
    return;
  }

  setButtonsBusy(true);
  setStatus("simulating", "Simulating");
  setTab("signal");
  clearTrace(traceEl);
  resetMachineFromForm();

  const cipherOut = document.getElementById("ciphertext");
  if (cipherOut) cipherOut.value = "";

  let cipherAccum = "";

  for (let k = 0; k < plain.length; k++) {
    const ch = plain[k];
    await new Promise((resolve) => {
      const tr = machine.encryptCharWithTrace(ch);
      appendTrace(traceEl, `\n━━ Letter ${k + 1}/${plain.length}: ${ch} ━━\n`);
      tr.traceLines.forEach((line) => appendTrace(traceEl, line + "\n"));

      const wrapped = {
        ...tr,
        inputLetter: ch,
        outputLetter: tr.outputLetter,
      };

      animateLetterTrace(wrapped, () => {
        cipherAccum += tr.outputLetter;
        if (cipherOut) cipherOut.value = cipherAccum;
        resolve();
      });
    });
  }

  document.getElementById("current-out").textContent = cipherAccum.slice(-1) || "—";
  setStatus("solved", "Done");
  setButtonsBusy(false);
}

async function runStep() {
  const plain = (document.getElementById("plaintext")?.value || "")
    .toUpperCase()
    .replace(/[^A-Z]/g, "");
  if (!plain.length) return;

  if (!machine) resetMachineFromForm();
  if (stepIndex >= plain.length) {
    stepIndex = 0;
    resetMachineFromForm();
    clearTrace(document.getElementById("trace-panel"));
  }

  setStatus("simulating", "Step");
  setTab("signal");
  const ch = plain[stepIndex];
  const tr = machine.encryptCharWithTrace(ch);
  const traceEl = document.getElementById("trace-panel");
  appendTrace(traceEl, `\n━━ Step ${stepIndex + 1}: ${ch} ━━\n`);
  tr.traceLines.forEach((line) => appendTrace(traceEl, line + "\n"));

  const wrapped = { ...tr, inputLetter: ch, outputLetter: tr.outputLetter };
  animateLetterTrace(wrapped, () => {
    const cipherOut = document.getElementById("ciphertext");
    if (cipherOut) {
      cipherOut.value = (cipherOut.value || "") + tr.outputLetter;
    }
    stepIndex += 1;
    if (stepIndex >= plain.length) setStatus("solved", "Done");
    else setStatus("idle", "Idle");
  });
}

function setButtonsBusy(busy) {
  ["btn-simulate", "btn-crack", "btn-step", "btn-reset"].forEach((id) => {
    const b = document.getElementById(id);
    if (b) b.disabled = busy;
  });
}

async function runCrack() {
  const solverLog = document.getElementById("solver-log");
  const phaseEl = document.getElementById("solver-phase");
  if (solverLog) solverLog.innerHTML = "";

  setButtonsBusy(true);
  setStatus("cracking", "Cracking");
  setTab("solver");

  const cfg = readConfig();
  const crib = (document.getElementById("crib")?.value || "").toUpperCase().replace(/[^A-Z]/g, "");
  const ciphertext = (document.getElementById("ciphertext")?.value || "")
    .toUpperCase()
    .replace(/[^A-Z]/g, "");
  const mode = document.getElementById("crack-mode")?.value || "positions";

  if (!ciphertext.length || !crib.length) {
    appendSolverLog(solverLog, "[error] Need ciphertext and crib (A–Z).");
    setStatus("unknown", "Need input");
    setButtonsBusy(false);
    return;
  }

  visualizer = new SolverVisualizer({
    onLog: (line) => appendSolverLog(solverLog, line),
    onPhase: (p) => {
      if (phaseEl) phaseEl.textContent = p;
    },
    constraintEl: document.getElementById("constraint-stream"),
    candidateEl: document.getElementById("candidate-grid"),
  });

  const demo = visualizer.runDemo({
    mode,
    hintRotors: [cfg.rotorRight, cfg.rotorMid, cfg.rotorLeft].map((x) => x),
  });

  const payload = {
    crib,
    ciphertext,
    mode,
    guess_rotors: [cfg.rotorLeft, cfg.rotorMid, cfg.rotorRight],
    rotors: [cfg.rotorLeft, cfg.rotorMid, cfg.rotorRight],
    positions: [cfg.posLeft, cfg.posMid, cfg.posRight],
    rings: [cfg.ringLeft, cfg.ringMid, cfg.ringRight],
    reflector: cfg.reflector,
    plugboard: cfg.plugboard,
  };

  try {
    const [_, result] = await Promise.all([demo, postCrack(payload)]);

    setStatus(result.status === "sat" ? "solved" : result.status === "unsat" ? "unsat" : "unknown", result.status.toUpperCase());
    renderResults({
      status: result.status,
      rotors: result.rotors,
      positions: result.positions,
      rings: result.rings,
      plugboard: result.plugboard,
      plaintext: result.plaintext,
      constraints_used: result.constraints_used,
    });
    appendSolverLog(solverLog, `[z3] result: ${result.status.toUpperCase()} — model emitted.`);

    if (result.status === "sat" && result.rotors) {
      applyRecoveredToForm(result);
    }
  } catch (e) {
    console.error(e);
    appendSolverLog(solverLog, `[error] ${e.message || e}`);
    setStatus("unsat", "Error");
  } finally {
    setButtonsBusy(false);
  }
}

function applyRecoveredToForm(result) {
  const mapSel = (id, val) => {
    const el = document.getElementById(id);
    if (el && val) el.value = val;
  };
  if (result.rotors && result.rotors.length === 3) {
    mapSel("rotor-left", result.rotors[0]);
    mapSel("rotor-mid", result.rotors[1]);
    mapSel("rotor-right", result.rotors[2]);
  }
  if (result.positions && result.positions.length === 3) {
    document.getElementById("pos-left").value = result.positions[0];
    document.getElementById("pos-mid").value = result.positions[1];
    document.getElementById("pos-right").value = result.positions[2];
  }
  if (result.rings && result.rings.length === 3) {
    document.getElementById("ring-left").value = result.rings[0];
    document.getElementById("ring-mid").value = result.rings[1];
    document.getElementById("ring-right").value = result.rings[2];
  }
  if (result.plugboard && result.plugboard.length) {
    const pb = result.plugboard.map((p) => p.join("")).join(" ");
    document.getElementById("plugboard").value = pb;
  }
}

function init() {
  fillRotorSelects();
  bindTabs();
  initSchematic(document.getElementById("schematic"));
  resetMachineFromForm();
  setStatus("idle", "Idle");

  document.getElementById("btn-simulate")?.addEventListener("click", () => runSimulate());
  document.getElementById("btn-crack")?.addEventListener("click", () => runCrack());
  document.getElementById("btn-step")?.addEventListener("click", () => runStep());
  document.getElementById("btn-reset")?.addEventListener("click", () => {
    resetMachineFromForm();
    clearTrace(document.getElementById("trace-panel"));
    const c = document.getElementById("ciphertext");
    if (c) c.value = "";
    document.getElementById("current-in").textContent = "—";
    document.getElementById("current-out").textContent = "—";
    setStatus("idle", "Idle");
  });
}

init();
