/**
 * Orchestrates a staged SMT/Z3 visualization: constraints, candidates, pruning, SAT/UNSAT.
 * Runs independently of whether the backend returns only a final model — this layer adds meaning.
 */

import { DEFAULT_CONSTRAINTS } from "./api.js";

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function randomSubset(arr, n) {
  const copy = [...arr];
  const out = [];
  while (copy.length && out.length < n) {
    const i = Math.floor(Math.random() * copy.length);
    out.push(copy.splice(i, 1)[0]);
  }
  return out;
}

export class SolverVisualizer {
  constructor(options) {
    this.onLog = options.onLog || (() => {});
    this.onPhase = options.onPhase || (() => {});
    this.constraintEl = options.constraintEl;
    this.candidateEl = options.candidateEl;
    this.abortFlag = false;
  }

  abort() {
    this.abortFlag = true;
  }

  reset() {
    this.abortFlag = false;
    if (this.constraintEl) this.constraintEl.innerHTML = "";
    if (this.candidateEl) this.candidateEl.innerHTML = "";
  }

  log(line) {
    this.onLog(line);
  }

  async runDemo({ mode = "positions", hintRotors = ["III", "II", "I"] }) {
    this.reset();
    this.abortFlag = false;

    await this.phaseLoadConstraints();
    if (this.abortFlag) return;

    await this.phaseCandidates(hintRotors, mode);
    if (this.abortFlag) return;

    await this.phasePrune();
    if (this.abortFlag) return;

    await this.phaseFinalCheck();
  }

  async phaseLoadConstraints() {
    this.onPhase("constraints loaded");
    this.log("[z3] initializing context");
    await sleep(120);

    const list = [...DEFAULT_CONSTRAINTS];
    for (const c of list) {
      if (this.abortFlag) return;
      const div = document.createElement("div");
      div.className = "constraint-card";
      div.textContent = c;
      div.dataset.name = c;
      if (this.constraintEl) this.constraintEl.appendChild(div);
      this.log(`[z3] assert: ${c}`);
      await sleep(80 + Math.random() * 40);
    }

    await sleep(150);
    for (const el of this.constraintEl?.querySelectorAll(".constraint-card") || []) {
      el.classList.add("satisfied");
    }
    this.log("[z3] constraint set closed — search starting");
  }

  async phaseCandidates(hintRotors, mode) {
    this.onPhase("enumerating candidates");
    this.log("[search] expanding rotor order / window space");

    const orders = [
      ["III", "II", "I"],
      ["IV", "III", "II"],
      ["II", "I", "V"],
      [hintRotors[0], hintRotors[1], hintRotors[2]],
    ];

    const cells = [];
    if (this.candidateEl) {
      this.candidateEl.innerHTML = "";
      let id = 0;
      for (const ord of orders) {
        for (let k = 0; k < 4; k++) {
          const label = `${ord.join("")}·${(id * 7) % 26}${(id * 3) % 26}${(id * 5) % 26}`;
          const cell = document.createElement("div");
          cell.className = "candidate-cell";
          cell.textContent = label;
          cell.dataset.id = String(id++);
          this.candidateEl.appendChild(cell);
          cells.push(cell);
        }
      }
    }

    await sleep(200);
    for (let i = 0; i < cells.length; i++) {
      if (this.abortFlag) return;
      cells[i].classList.add("highlight");
      await sleep(35);
      if (i > 2) cells[i - 3].classList.remove("highlight");
    }
    for (const c of cells) c.classList.remove("highlight");

    if (mode !== "positions") {
      this.log("[search] plugboard pair hypotheses: " + randomSubset(["AB", "CD", "EF", "GH"], 2).join(", "));
    }
  }

  async phasePrune() {
    this.onPhase("pruning branches");
    this.log("[z3] UNSAT cores — eliminating inconsistent rotor windows");

    const cells = [...(this.candidateEl?.querySelectorAll(".candidate-cell") || [])];
    const toPrune = randomSubset(cells, Math.max(0, cells.length - 3));

    for (const cell of toPrune) {
      if (this.abortFlag) return;
      cell.classList.add("pruned");
      await sleep(45);
    }

    await sleep(120);
    this.log("[z3] remaining candidates: " + (cells.length - toPrune.length));
  }

  async phaseFinalCheck() {
    this.onPhase("model check");
    this.log("[z3] checking partial assignment consistency with crib…");

    const cards = [...(this.constraintEl?.querySelectorAll(".constraint-card") || [])];
    for (const card of cards) {
      if (this.abortFlag) return;
      card.classList.remove("satisfied");
      card.classList.add("checking");
      await sleep(120);
      card.classList.remove("checking");
      card.classList.add("satisfied");
    }

    this.onPhase("awaiting solver result");
    await sleep(200);
  }
}

export function appendSolverLog(container, line, maxLines = 80) {
  if (!container) return;
  const row = document.createElement("div");
  row.textContent = line;
  container.appendChild(row);
  while (container.children.length > maxLines) {
    container.removeChild(container.firstChild);
  }
  container.scrollTop = container.scrollHeight;
}
