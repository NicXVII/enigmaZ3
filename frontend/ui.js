/**
 * Helper DOM: schema, stato, risultati e schede.
 */

const STAGE_ORDER = [
  "plug_in",
  "r3_fwd",
  "r2_fwd",
  "r1_fwd",
  "refl",
  "r1_back",
  "r2_back",
  "r3_back",
  "plug_out",
];

const NODE_META = {
  plug_in: { id: "node-plug", title: "Pannello" },
  r3_fwd: { id: "node-r3", title: "R3" },
  r2_fwd: { id: "node-r2", title: "R2" },
  r1_fwd: { id: "node-r1", title: "R1" },
  refl: { id: "node-refl", title: "Riflettore" },
  r1_back: { id: "node-r1b", title: "R1′" },
  r2_back: { id: "node-r2b", title: "R2′" },
  r3_back: { id: "node-r3b", title: "R3′" },
  plug_out: { id: "node-plug2", title: "Pannello" },
};

export function initSchematic(container) {
  if (!container) return;
  const row1 = document.createElement("div");
  row1.className = "schematic-row";
  const forward = ["plug_in", "r3_fwd", "r2_fwd", "r1_fwd", "refl"];
  row1.appendChild(makeArrow("ING"));
  for (let i = 0; i < forward.length; i++) {
    row1.appendChild(makeNode(forward[i]));
    if (i < forward.length - 1) row1.appendChild(makeArrow("→"));
  }
  container.appendChild(row1);

  const row2 = document.createElement("div");
  row2.className = "schematic-row mt-1";
  const backward = ["r1_back", "r2_back", "r3_back", "plug_out"];
  row2.appendChild(makeArrow("←"));
  for (let i = 0; i < backward.length; i++) {
    row2.appendChild(makeNode(backward[i]));
    if (i < backward.length - 1) row2.appendChild(makeArrow("←"));
  }
  row2.appendChild(makeArrow("USC"));
  container.appendChild(row2);
}

function makeArrow(text) {
  const s = document.createElement("span");
  s.className = "schematic-arrow";
  s.textContent = text;
  return s;
}

function makeNode(stage) {
  const meta = NODE_META[stage];
  const wrap = document.createElement("div");
  wrap.className = "schematic-node";
  wrap.id = meta.id;
  wrap.dataset.stage = stage;
  wrap.innerHTML = `<span>${meta.title}</span><span class="node-sub">—</span>`;
  return wrap;
}

export function updateSchematicActive(stage, letter) {
  document.querySelectorAll(".schematic-node").forEach((el) => {
    el.classList.remove("active", "dim");
    const sub = el.querySelector(".node-sub");
    if (sub) sub.textContent = "—";
  });
  if (!stage) return;

  const orderIdx = STAGE_ORDER.indexOf(stage);
  document.querySelectorAll(".schematic-node").forEach((el) => {
    const s = el.dataset.stage;
    const idx = STAGE_ORDER.indexOf(s);
    if (idx === orderIdx) {
      el.classList.add("active");
      const sub = el.querySelector(".node-sub");
      if (sub && letter) sub.textContent = letter;
    } else {
      el.classList.add("dim");
    }
  });
}

export function flashRotorWindows(positionsLetters) {
  const els = [
    document.getElementById("win-left"),
    document.getElementById("win-mid"),
    document.getElementById("win-right"),
  ];
  const wraps = document.querySelectorAll(".rotor-window");
  wraps.forEach((w) => w.classList.remove("rotor-stepping"));
  if (positionsLetters && positionsLetters.length === 3) {
    els.forEach((el, i) => {
      if (el) el.textContent = positionsLetters[i];
    });
    wraps.forEach((w) => w.classList.add("rotor-stepping"));
    setTimeout(() => wraps.forEach((w) => w.classList.remove("rotor-stepping")), 400);
  }
}

export function setStatus(status, label) {
  const pill = document.getElementById("status-pill");
  const lbl = document.getElementById("status-label");
  if (pill) pill.dataset.status = status;
  if (lbl) lbl.textContent = label;
}

export function setTab(name) {
  const signal = document.getElementById("tab-signal");
  const solver = document.getElementById("tab-solver");
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.toggle("tab-active", b.dataset.tab === name);
  });
  if (signal) signal.classList.toggle("hidden", name !== "signal");
  if (solver) solver.classList.toggle("hidden", name !== "solver");
}

export function bindTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => setTab(btn.dataset.tab));
  });
}

export function fillRotorSelects() {
  const names = ["I", "II", "III", "IV", "V"];
  const left = document.getElementById("rotor-left");
  const mid = document.getElementById("rotor-mid");
  const right = document.getElementById("rotor-right");
  [left, mid, right].forEach((sel, idx) => {
    if (!sel) return;
    sel.innerHTML = "";
    const defaults = ["I", "II", "III"];
    for (const n of names) {
      const opt = document.createElement("option");
      opt.value = n;
      opt.textContent = n;
      if (n === defaults[idx]) opt.selected = true;
      sel.appendChild(opt);
    }
  });
}

export function renderResults(result) {
  const map = {
    "res-status": result.status ? String(result.status).toUpperCase() : "—",
    "res-rotors": result.rotors ? result.rotors.join(" · ") : "—",
    "res-positions": result.positions ? result.positions.join(", ") : "—",
    "res-rings": result.rings ? result.rings.join(", ") : "—",
    "res-plugboard": formatPlug(result.plugboard),
    "res-plaintext": result.plaintext || "—",
  };
  for (const [id, val] of Object.entries(map)) {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  }
  const ul = document.getElementById("res-constraints");
  if (ul) {
    ul.innerHTML = "";
    (result.constraints_used || []).forEach((c) => {
      const li = document.createElement("li");
      li.textContent = c;
      ul.appendChild(li);
    });
  }
}

function formatPlug(pb) {
  if (!pb || !pb.length) return "—";
  if (Array.isArray(pb)) {
    return pb.map((p) => (Array.isArray(p) ? `${p[0]}↔${p[1]}` : p)).join(", ");
  }
  return String(pb);
}

export function appendTrace(textareaOrPre, chunk) {
  const el = textareaOrPre;
  if (!el) return;
  el.textContent += chunk;
  el.scrollTop = el.scrollHeight;
}

export function clearTrace(el) {
  if (el) el.textContent = "";
}
