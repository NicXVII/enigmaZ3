"""End-to-end check for plugboard cracking with unknown rotor positions."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cracker.full_cracker import crack_with_plugboard
from enigma.machine import EnigmaMachine
from enigma.plugboard import Plugboard
from enigma.reflector import Reflector
from enigma.rotor import Rotor


def _make_machine(
    rotor_names: tuple[str, str, str],
    positions: tuple[int, int, int],
    rings: tuple[int, int, int],
    plugboard_pairs: list[tuple[str, str]],
) -> EnigmaMachine:
    rotors = [
        Rotor.from_name(rotor_names[0], ring=rings[0], position=positions[0]),
        Rotor.from_name(rotor_names[1], ring=rings[1], position=positions[1]),
        Rotor.from_name(rotor_names[2], ring=rings[2], position=positions[2]),
    ]
    return EnigmaMachine(rotors, Reflector.from_name("B"), Plugboard(plugboard_pairs))


def main() -> int:
    rotor_names = ("I", "II", "III")
    ring_settings = (0, 0, 0)
    secret_positions = (6, 13, 19)
    secret_pairs = [("A", "Z"), ("B", "Y"), ("C", "X")]
    plaintext = "WETTERBERICHT"

    print("=== Test modalita plugboard (posizioni iniziali ignote) ===")
    print(f"Rotori noti: {rotor_names}")
    print(f"Rings noti: {ring_settings}")
    print(f"Coppie plugboard ignote da stimare: {len(secret_pairs)}")

    encryptor = _make_machine(
        rotor_names=rotor_names,
        positions=secret_positions,
        rings=ring_settings,
        plugboard_pairs=secret_pairs,
    )
    ciphertext = encryptor.process(plaintext)
    print(f"Ciphertext generato: {ciphertext}")

    result = crack_with_plugboard(
        ciphertext=ciphertext,
        crib=plaintext,
        rotor_names=rotor_names,
        reflector_name="B",
        num_plugboard_pairs=len(secret_pairs),
        ring_settings=ring_settings,
        solver_timeout_ms=8_000,
    )

    if result is None:
        print("FAIL: cracking fallito (nessuna soluzione trovata entro timeout).")
        return 1

    found_positions, found_pairs = result
    print(f"Posizioni trovate: {found_positions}")
    print(f"Coppie trovate:    {found_pairs}")

    verify_machine = _make_machine(
        rotor_names=rotor_names,
        positions=found_positions,
        rings=ring_settings,
        plugboard_pairs=found_pairs,
    )
    recovered_plaintext = verify_machine.process(ciphertext)

    positions_ok = found_positions == secret_positions
    plaintext_ok = recovered_plaintext == plaintext

    if positions_ok and plaintext_ok:
        print("OK: posizioni recuperate e decifratura corretta.")
        return 0

    if not positions_ok:
        print(f"FAIL: posizioni errate (attese {secret_positions}).")
    if not plaintext_ok:
        print(f"FAIL: plaintext recuperato errato ({recovered_plaintext}).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
