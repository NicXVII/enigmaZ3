#!/usr/bin/env python3
"""Interactive Enigma + Z3 demo for oral presentations."""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass

from cracker.full_cracker import crack_rotor_positions
from enigma import EnigmaMachine, Plugboard, Reflector, Rotor

ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

ROTOR_NAMES = ("I", "II", "III")
INITIAL_POSITIONS = (5, 10, 20)
RING_SETTINGS = (0, 0, 0)
REFLECTOR_NAME = "B"
PLUGBOARD_PAIRS = [
    ("A", "B"),
    ("C", "D"),
    ("E", "F"),
    ("G", "H"),
    ("I", "J"),
    ("K", "L"),
    ("M", "N"),
    ("O", "P"),
    ("Q", "R"),
    ("S", "T"),
]
TRACE_DELAY_SECONDS = 0.05
CRACK_TIMEOUT_MS = 50


class Ansi:
    """ANSI color codes with optional no-color fallback."""

    def __init__(self, enabled: bool):
        if enabled:
            self.reset = "\033[0m"
            self.bold = "\033[1m"
            self.dim = "\033[2m"
            self.cyan = "\033[36m"
            self.yellow = "\033[33m"
            self.green = "\033[32m"
            self.red = "\033[31m"
        else:
            self.reset = ""
            self.bold = ""
            self.dim = ""
            self.cyan = ""
            self.yellow = ""
            self.green = ""
            self.red = ""


def supports_ansi() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    if not sys.stdout.isatty():
        return False
    return os.environ.get("TERM", "").lower() != "dumb"


def colorize(text: str, color: str, ansi: Ansi) -> str:
    return f"{color}{text}{ansi.reset}" if color else text


def idx_to_char(value: int) -> str:
    return ALPHA[value % 26]


def sanitize_plaintext(raw: str) -> str:
    return "".join(ch for ch in raw.upper() if ch in ALPHA)


def positions_to_letters(positions: tuple[int, int, int]) -> str:
    return "-".join(idx_to_char(p) for p in positions)


def build_machine(
    positions: tuple[int, int, int],
    rotor_names: tuple[str, str, str] = ROTOR_NAMES,
    ring_settings: tuple[int, int, int] = RING_SETTINGS,
    reflector_name: str = REFLECTOR_NAME,
    plugboard_pairs: list[tuple[str, str]] | None = PLUGBOARD_PAIRS,
) -> EnigmaMachine:
    rotors = [
        Rotor.from_name(rotor_names[0], ring=ring_settings[0], position=positions[0]),
        Rotor.from_name(rotor_names[1], ring=ring_settings[1], position=positions[1]),
        Rotor.from_name(rotor_names[2], ring=ring_settings[2], position=positions[2]),
    ]
    reflector = Reflector.from_name(reflector_name)
    plugboard = Plugboard(plugboard_pairs)
    return EnigmaMachine(rotors, reflector, plugboard)


@dataclass
class TraceResult:
    rotor_positions_before_step: tuple[int, int, int]
    rotor_positions_after_step: tuple[int, int, int]
    stage_outputs: list[tuple[str, str]]
    output: str


def encrypt_with_manual_trace(machine: EnigmaMachine, ch: str) -> TraceResult:
    # Keep positions shown in the trace exactly as "current" before stepping.
    before = (machine.left.position, machine.middle.position, machine.right.position)

    # Real Enigma stepping happens before signal traversal.
    if machine.middle.is_at_notch():
        machine.middle.step()
        machine.left.step()
    elif machine.right.is_at_notch():
        machine.middle.step()
    machine.right.step()
    after = (machine.left.position, machine.middle.position, machine.right.position)

    idx = ord(ch) - ord("A")

    stage_outputs: list[tuple[str, str]] = [("Input", idx_to_char(idx))]

    idx = machine.plugboard.swap(idx)
    stage_outputs.append(("Plugboard IN", idx_to_char(idx)))

    idx = machine.right.forward(idx)
    stage_outputs.append(("Dopo Rotor III (→)", idx_to_char(idx)))

    idx = machine.middle.forward(idx)
    stage_outputs.append(("Dopo Rotor II (→)", idx_to_char(idx)))

    idx = machine.left.forward(idx)
    stage_outputs.append(("Dopo Rotor I (→)", idx_to_char(idx)))

    idx = machine.reflector.reflect(idx)
    stage_outputs.append(("Reflector", idx_to_char(idx)))

    idx = machine.left.backward(idx)
    stage_outputs.append(("Dopo Rotor I (←)", idx_to_char(idx)))

    idx = machine.middle.backward(idx)
    stage_outputs.append(("Dopo Rotor II (←)", idx_to_char(idx)))

    idx = machine.right.backward(idx)
    stage_outputs.append(("Dopo Rotor III (←)", idx_to_char(idx)))

    idx = machine.plugboard.swap(idx)
    stage_outputs.append(("Plugboard OUT", idx_to_char(idx)))
    stage_outputs.append(("Output", idx_to_char(idx)))

    return TraceResult(
        rotor_positions_before_step=before,
        rotor_positions_after_step=after,
        stage_outputs=stage_outputs,
        output=idx_to_char(idx),
    )


def format_plugboard_pairs(pairs: list[tuple[str, str]]) -> str:
    return ", ".join(f"{a}↔{b}" for a, b in pairs) if pairs else "(nessuno)"


def format_plugboard_fixed_letters(pairs: list[tuple[str, str]]) -> str:
    used_letters = {letter for pair in pairs for letter in pair}
    fixed_letters = [letter for letter in ALPHA if letter not in used_letters]
    return ", ".join(fixed_letters) if fixed_letters else "(nessuna)"


def format_chain(letters: list[str], ansi: Ansi) -> str:
    decorated: list[str] = []
    for i, letter in enumerate(letters):
        if i == 0:
            decorated.append(colorize(letter, ansi.cyan, ansi))
        elif i == 5:
            decorated.append(colorize(letter, ansi.yellow, ansi))
        elif i == len(letters) - 1:
            decorated.append(colorize(letter, ansi.green, ansi))
        else:
            decorated.append(colorize(letter, ansi.dim, ansi))
    return " → ".join(decorated)


def format_stage_letter(stage: str, letter: str, ansi: Ansi) -> str:
    if stage == "Input":
        return colorize(letter, ansi.cyan, ansi)
    if stage == "Reflector":
        return colorize(letter, ansi.yellow, ansi)
    if stage == "Output":
        return colorize(letter, ansi.green, ansi)
    return colorize(letter, ansi.dim, ansi)


def print_header(ansi: Ansi):
    print("═" * 46)
    print(f"{ansi.bold}   ENIGMA + Z3 — Demo Interattiva{ansi.reset}")
    print("═" * 46)
    print()


def main() -> int:
    ansi = Ansi(enabled=supports_ansi())

    print_header(ansi)
    raw_message = input("Inserisci un messaggio: ")
    plaintext = sanitize_plaintext(raw_message)

    if not plaintext:
        print()
        print(f"{ansi.red}Errore: inserisci almeno una lettera A-Z.{ansi.reset}")
        return 1

    if plaintext != raw_message.strip().upper():
        print(f"Messaggio normalizzato: {plaintext}")

    print()
    print("── Configurazione " + "─" * 28)
    print(f"  Rotori:     {', '.join(ROTOR_NAMES)}")
    print(f"  Posizioni:  {INITIAL_POSITIONS}")
    print(f"  Rings:      {RING_SETTINGS}")
    print(f"  Riflettore: {REFLECTOR_NAME}")
    print(f"  Plugboard:  {format_plugboard_pairs(PLUGBOARD_PAIRS)}")
    print(f"  Fisse:      {format_plugboard_fixed_letters(PLUGBOARD_PAIRS)}")

    print()
    print("── FASE 1: Cifratura " + "─" * 25)
    print()

    machine = build_machine(INITIAL_POSITIONS)

    ciphertext_chars: list[str] = []
    no_self_encryption = True

    for index, ch in enumerate(plaintext, start=1):
        trace = encrypt_with_manual_trace(machine, ch)
        ciphertext_chars.append(trace.output)

        if trace.output == ch:
            no_self_encryption = False

        rotors_before = positions_to_letters(trace.rotor_positions_before_step)
        rotors_after = positions_to_letters(trace.rotor_positions_after_step)
        chain_letters = [letter for _, letter in trace.stage_outputs]

        print(f"  [{index}] {ch}  (rotori prima: {rotors_before} | dopo step: {rotors_after})")
        print(f"      Catena: {format_chain(chain_letters, ansi)}")
        print("      Uscite intermedie:")
        for stage, letter in trace.stage_outputs:
            colored_letter = format_stage_letter(stage, letter, ansi)
            print(f"        {stage:<18} {colored_letter}")
        print()
        time.sleep(TRACE_DELAY_SECONDS)

    ciphertext = "".join(ciphertext_chars)

    print(f"  Plaintext:  {plaintext}")
    print(f"  Ciphertext: {ciphertext}")
    if no_self_encryption:
        print(f"  {colorize('✓', ansi.green, ansi)} Nessuna lettera si è cifrata in sé stessa")
    else:
        print(f"  {colorize('✗', ansi.red, ansi)} Trovata almeno una auto-cifratura")

    print()
    print("── FASE 2: Verifica simmetria " + "─" * 17)
    print()

    symmetry_machine = build_machine(INITIAL_POSITIONS)
    symmetric_result = symmetry_machine.process(ciphertext)
    print(f"  {ciphertext} → Enigma(stessa chiave) → {symmetric_result}")
    if symmetric_result == plaintext:
        print(
            f"  {colorize('✓', ansi.green, ansi)} Enigma è simmetrica: "
            "cifrare con la stessa chiave = decifrare"
        )
    else:
        print(f"  {colorize('✗', ansi.red, ansi)} Verifica simmetria fallita")

    print()
    print("── FASE 3: Cracking con Z3 " + "─" * 20)
    print()

    print(f"  Conosciamo: ciphertext = {ciphertext}")
    print(f"              crib       = {plaintext}")
    print(f"              rotori     = {', '.join(ROTOR_NAMES)}")
    print(f"              plugboard  = {format_plugboard_pairs(PLUGBOARD_PAIRS)}")
    print(f"              fisse      = {format_plugboard_fixed_letters(PLUGBOARD_PAIRS)}")
    print("  Cerchiamo:  posizioni  = ???")
    print()
    print("  Risoluzione Z3 in corso...")

    start = time.perf_counter()
    found_positions = crack_rotor_positions(
        ciphertext=ciphertext,
        crib=plaintext,
        rotor_names=ROTOR_NAMES,
        reflector_name=REFLECTOR_NAME,
        plugboard_pairs=PLUGBOARD_PAIRS,
        ring_settings=RING_SETTINGS,
        solver_timeout_ms=CRACK_TIMEOUT_MS,
    )
    elapsed = time.perf_counter() - start

    print(f"  Z3 sta risolvendo... {elapsed:.3f}s")
    print()

    if found_positions is None:
        print(f"  {colorize('✗', ansi.red, ansi)} Cracking fallito: nessuna configurazione trovata")
        return 1

    print(f"  Posizioni trovate: {found_positions}")
    print(f"  Posizioni reali:   {INITIAL_POSITIONS}")
    if found_positions == INITIAL_POSITIONS:
        print(f"  {colorize('✓', ansi.green, ansi)} Z3 ha trovato la configurazione in {elapsed:.3f}s")
    else:
        print(f"  {colorize('✗', ansi.red, ansi)} Z3 ha trovato una configurazione diversa")

    print()
    print("── FASE 4: Decifratura con chiave trovata " + "─" * 8)
    print()

    recovered_machine = build_machine(found_positions)
    recovered_plaintext = recovered_machine.process(ciphertext)
    print(
        f"  {ciphertext} → Enigma{found_positions} → {recovered_plaintext}"
    )

    if recovered_plaintext == plaintext:
        print(
            f"  {colorize('✓', ansi.green, ansi)} Cerchio completo: "
            "Input → Cifra → Crack → Decifra → Input originale"
        )
    else:
        print(
            f"  {colorize('✗', ansi.red, ansi)} Decifratura finale non coincide con il plaintext"
        )
        return 1

    print()
    print("═" * 46)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
