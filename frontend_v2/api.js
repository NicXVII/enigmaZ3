/**
 * HTTP API verso enigma_http_server.py (cracker Z3 reale in cracker/).
 *
 * Default: http://127.0.0.1:8765 — avvia dalla root: python enigma_http_server.py
 *
 * Override: window.ENIGMA_API_BASE = "http://..."
 * Disattiva API (solo per test): window.ENIGMA_API_BASE = ""
 * Mock solo se esplicito: window.ENIGMA_USE_MOCK_CRACK = true
 */

import { buildMachineFromUI } from "./simulator.js";

const DEFAULT_API_BASE = "http://127.0.0.1:8765";

const DEFAULT_CONSTRAINTS = [
  "plugboard involution",
  "reflector involution without fixed points",
  "rotor stepping (double-step)",
  "no self-encryption",
  "crib–ciphertext consistency",
];

/**
 * Base URL API. Se la proprietà non è definita → default `http://127.0.0.1:8765`.
 * `ENIGMA_API_BASE = ""` disattiva le chiamate (solo mock se `ENIGMA_USE_MOCK_CRACK`).
 */
function getBase() {
  if (typeof window === "undefined") {
    return DEFAULT_API_BASE;
  }
  if (!Object.prototype.hasOwnProperty.call(window, "ENIGMA_API_BASE")) {
    return DEFAULT_API_BASE;
  }
  const raw = window.ENIGMA_API_BASE;
  if (raw === "" || raw === null) return "";
  const s = String(raw).trim();
  if (s === "") return "";
  return s.replace(/\/$/, "");
}

export async function postEncrypt(payload) {
  const base = getBase();
  if (!base) {
    return localEncrypt(payload);
  }
  const res = await fetch(`${base}/encrypt`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`encrypt failed: ${res.status}`);
  return res.json();
}

export async function postCrack(payload) {
  const base = getBase();
  if (!base) {
    if (typeof window !== "undefined" && window.ENIGMA_USE_MOCK_CRACK === true) {
      return mockCrack(payload);
    }
    throw new Error(
      "Cracker disattivato (ENIGMA_API_BASE vuoto). Avvia: python enigma_http_server.py " +
        "oppure rimuovi ENIGMA_API_BASE per usare il default http://127.0.0.1:8765"
    );
  }
  const res = await fetch(`${base}/crack`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    let detail = "";
    try {
      const err = await res.json();
      if (err && err.error) detail = `: ${err.error}`;
    } catch {
      /* ignore */
    }
    throw new Error(`crack failed: ${res.status}${detail}`);
  }
  return res.json();
}

function localEncrypt(payload) {
  const cfg = payloadToConfig(payload);
  const m = buildMachineFromUI(cfg);
  const text = payload.text || payload.plaintext || "";
  const ciphertext = m.process(text);
  return { ciphertext, ok: true };
}

function payloadToConfig(p) {
  const rotors = p.rotors || [];
  return {
    rotorLeft: rotors[0] || "I",
    rotorMid: rotors[1] || "II",
    rotorRight: rotors[2] || "III",
    posLeft: (p.positions && p.positions[0]) ?? 0,
    posMid: (p.positions && p.positions[1]) ?? 0,
    posRight: (p.positions && p.positions[2]) ?? 0,
    ringLeft: (p.rings && p.rings[0]) ?? 0,
    ringMid: (p.rings && p.rings[1]) ?? 0,
    ringRight: (p.rings && p.rings[2]) ?? 0,
    reflector: p.reflector || "B",
    plugboard: formatPlugPairs(p.plugboard),
  };
}

function formatPlugPairs(pb) {
  if (!pb) return "";
  if (typeof pb === "string") return pb;
  if (Array.isArray(pb)) {
    return pb.map((pair) => (Array.isArray(pair) ? pair.join("") : pair)).join(" ");
  }
  return "";
}

/** Solo per sviluppo UI senza Python: window.ENIGMA_USE_MOCK_CRACK = true e ENIGMA_API_BASE = "" */
function mockCrack(payload) {
  const crib = (payload.crib || "").toUpperCase().replace(/[^A-Z]/g, "");
  const cipher = (payload.ciphertext || "").toUpperCase().replace(/[^A-Z]/g, "");
  const mode = payload.mode || "positions";

  const rotors = payload.guess_rotors || ["III", "II", "I"];
  const positions = [5, 10, 20];
  const rings = [0, 0, 0];
  const plugboard = [
    ["A", "Z"],
    ["B", "M"],
  ];

  const constraintsUsed =
    mode === "positions"
      ? DEFAULT_CONSTRAINTS.filter((c) => c !== "plugboard involution")
      : DEFAULT_CONSTRAINTS;

  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        status: "sat",
        rotors,
        positions,
        rings,
        plugboard,
        plaintext: crib || "HELLO",
        ciphertext: cipher,
        constraints_used: constraintsUsed,
        mode,
      });
    }, 400);
  });
}

export { DEFAULT_CONSTRAINTS };
