/**
 * Enigma I–V wirings and notches (Wehrmacht) — aligned with Python enigma/rotor.py
 */
export const ROTOR_WIRINGS = {
  I: "EKMFLGDQVZNTOWYHXUSPAIBRCJ",
  II: "AJDKSIRUXBLHWTMCQGZNPYFVOE",
  III: "BDFHJLCPRTXVZNYEIWGAKMUSQO",
  IV: "ESOVPZJAYQUIRHXLNFTGKDCMWB",
  V: "VZBRGITYUPSDNHLXAWMJQOFECK",
};

export const ROTOR_NOTCHES = {
  I: "Q",
  II: "E",
  III: "V",
  IV: "J",
  V: "Z",
};

export const REFLECTOR_WIRINGS = {
  B: "YRUHQSLDPXNGOKMIEBFZCWVJAT",
  C: "FVPJIAOYEDRZXWGCTKUQSBNMHL",
};

function letterFromIndex(i) {
  return String.fromCharCode(65 + ((i % 26) + 26) % 26);
}

function indexFromLetter(ch) {
  return ch.charCodeAt(0) - 65;
}

export class Rotor {
  constructor(name, ring = 0, position = 0) {
    const wiring = ROTOR_WIRINGS[name];
    if (!wiring) throw new Error(`Unknown rotor ${name}`);
    this.name = name;
    this.wiringStr = wiring;
    this.notch = indexFromLetter(ROTOR_NOTCHES[name]);
    this.ring = ring;
    this.position = position;
    this.forwardMap = [...wiring].map((c) => c.charCodeAt(0) - 65);
    this.inverseMap = new Array(26);
    for (let i = 0; i < 26; i++) {
      this.inverseMap[this.forwardMap[i]] = i;
    }
  }

  isAtNotch() {
    return this.position === this.notch;
  }

  step() {
    this.position = (this.position + 1) % 26;
  }

  forward(c) {
    const shifted = (c + this.position - this.ring + 260000) % 26;
    const out = this.forwardMap[shifted];
    return (out - this.position + this.ring + 260000) % 26;
  }

  backward(c) {
    const shifted = (c + this.position - this.ring + 260000) % 26;
    const out = this.inverseMap[shifted];
    return (out - this.position + this.ring + 260000) % 26;
  }

  reset(position) {
    this.position = position;
  }

  windowLetter() {
    return letterFromIndex(this.position);
  }
}

export class Reflector {
  constructor(name) {
    const w = REFLECTOR_WIRINGS[name];
    if (!w) throw new Error(`Unknown reflector ${name}`);
    this.name = name;
    this.wiring = [...w].map((c) => c.charCodeAt(0) - 65);
  }

  reflect(c) {
    return this.wiring[c];
  }
}

export class Plugboard {
  constructor(pairs) {
    this.mapping = Array.from({ length: 26 }, (_, i) => i);
    if (pairs && pairs.length) {
      for (const [a, b] of pairs) {
        const ia = indexFromLetter(a);
        const ib = indexFromLetter(b);
        this.mapping[ia] = ib;
        this.mapping[ib] = ia;
      }
    }
  }

  swap(c) {
    return this.mapping[c];
  }
}

/**
 * rotors: [left, middle, right] — slow to fast (matches Python EnigmaMachine)
 */
export class EnigmaMachine {
  constructor(rotorNames, rings, positions, reflectorName, plugPairs) {
    this.left = new Rotor(rotorNames[0], rings[0], positions[0]);
    this.middle = new Rotor(rotorNames[1], rings[1], positions[1]);
    this.right = new Rotor(rotorNames[2], rings[2], positions[2]);
    this.reflector = new Reflector(reflectorName);
    this.plugboard = new Plugboard(plugPairs);
  }

  _stepRotors() {
    if (this.middle.isAtNotch()) {
      this.middle.step();
      this.left.step();
    } else if (this.right.isAtNotch()) {
      this.middle.step();
    }
    this.right.step();
  }

  /**
   * Returns { outputLetter, traceLines: string[], steps: object[] }
   */
  encryptCharWithTrace(inputLetter) {
    const lines = [];
    const steps = [];
    let idx = indexFromLetter(inputLetter);

    this._stepRotors();

    const pbIn = this.plugboard.swap(idx);
    lines.push(`Plugboard  ${letterFromIndex(idx)} → ${letterFromIndex(pbIn)}`);
    steps.push({ stage: "plug_in", label: "Plugboard", from: letterFromIndex(idx), to: letterFromIndex(pbIn) });
    idx = pbIn;

    const r3 = this.right.forward(idx);
    lines.push(`R3 (fast)   ${letterFromIndex(idx)} → ${letterFromIndex(r3)}`);
    steps.push({ stage: "r3_fwd", label: "R3", from: letterFromIndex(idx), to: letterFromIndex(r3) });
    idx = r3;

    const r2 = this.middle.forward(idx);
    lines.push(`R2          ${letterFromIndex(idx)} → ${letterFromIndex(r2)}`);
    steps.push({ stage: "r2_fwd", label: "R2", from: letterFromIndex(idx), to: letterFromIndex(r2) });
    idx = r2;

    const r1 = this.left.forward(idx);
    lines.push(`R1 (slow)   ${letterFromIndex(idx)} → ${letterFromIndex(r1)}`);
    steps.push({ stage: "r1_fwd", label: "R1", from: letterFromIndex(idx), to: letterFromIndex(r1) });
    idx = r1;

    const ref = this.reflector.reflect(idx);
    lines.push(`Reflector ${this.reflector.name}  ${letterFromIndex(idx)} → ${letterFromIndex(ref)}`);
    steps.push({ stage: "refl", label: `Reflector ${this.reflector.name}`, from: letterFromIndex(idx), to: letterFromIndex(ref) });
    idx = ref;

    const b1 = this.left.backward(idx);
    lines.push(`R1 back     ${letterFromIndex(idx)} → ${letterFromIndex(b1)}`);
    steps.push({ stage: "r1_back", label: "R1", from: letterFromIndex(idx), to: letterFromIndex(b1) });
    idx = b1;

    const b2 = this.middle.backward(idx);
    lines.push(`R2 back     ${letterFromIndex(idx)} → ${letterFromIndex(b2)}`);
    steps.push({ stage: "r2_back", label: "R2", from: letterFromIndex(idx), to: letterFromIndex(b2) });
    idx = b2;

    const b3 = this.right.backward(idx);
    lines.push(`R3 back     ${letterFromIndex(idx)} → ${letterFromIndex(b3)}`);
    steps.push({ stage: "r3_back", label: "R3", from: letterFromIndex(idx), to: letterFromIndex(b3) });
    idx = b3;

    const pbOut = this.plugboard.swap(idx);
    lines.push(`Plugboard  ${letterFromIndex(idx)} → ${letterFromIndex(pbOut)}`);
    steps.push({ stage: "plug_out", label: "Plugboard", from: letterFromIndex(idx), to: letterFromIndex(pbOut) });
    idx = pbOut;

    const outputLetter = letterFromIndex(idx);
    lines.push(`Output      ${outputLetter}`);

    return {
      outputLetter,
      traceLines: lines,
      steps,
      windows: [this.left.windowLetter(), this.middle.windowLetter(), this.right.windowLetter()],
    };
  }

  process(text) {
    let out = "";
    for (const ch of text.toUpperCase()) {
      if (ch >= "A" && ch <= "Z") {
        const { outputLetter } = this.encryptCharWithTrace(ch);
        out += outputLetter;
      }
    }
    return out;
  }

  reset(positions) {
    this.left.reset(positions[0]);
    this.middle.reset(positions[1]);
    this.right.reset(positions[2]);
  }

  getPositions() {
    return [this.left.position, this.middle.position, this.right.position];
  }
}

/**
 * Parse "AZ BY CX" or "AZ,BY" into [["A","Z"],...]
 */
export function parsePlugboard(str) {
  if (!str || !String(str).trim()) return [];
  const cleaned = String(str)
    .toUpperCase()
    .replace(/[^A-Z]/g, " ");
  const tokens = cleaned.split(/\s+/).filter(Boolean);
  const pairs = [];
  for (const t of tokens) {
    if (t.length === 2) {
      pairs.push([t[0], t[1]]);
    }
  }
  return pairs;
}

export function buildMachineFromUI(config) {
  const rotors = [config.rotorLeft, config.rotorMid, config.rotorRight];
  const rings = [config.ringLeft, config.ringMid, config.ringRight];
  const positions = [config.posLeft, config.posMid, config.posRight];
  const pairs = parsePlugboard(config.plugboard);
  return new EnigmaMachine(rotors, rings, positions, config.reflector, pairs);
}
