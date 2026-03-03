"""Profile hot paths in cracker.full_cracker and export pstats text."""

from __future__ import annotations

import cProfile
import pstats
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cracker.full_cracker import (
    crack_full_configuration,
    crack_rotor_positions,
    crack_with_plugboard,
)
from enigma.machine import EnigmaMachine
from enigma.plugboard import Plugboard
from enigma.reflector import Reflector
from enigma.rotor import Rotor


def _make_cipher(
    plaintext: str,
    positions: tuple[int, int, int],
    rotor_names: tuple[str, str, str] = ("I", "II", "III"),
    rings: tuple[int, int, int] = (0, 0, 0),
    pairs: list[tuple[str, str]] | None = None,
) -> str:
    rotors = [
        Rotor.from_name(rotor_names[0], ring=rings[0], position=positions[0]),
        Rotor.from_name(rotor_names[1], ring=rings[1], position=positions[1]),
        Rotor.from_name(rotor_names[2], ring=rings[2], position=positions[2]),
    ]
    machine = EnigmaMachine(rotors, Reflector.from_name("B"), Plugboard(pairs))
    return machine.process(plaintext)


def run_profile(output_file: str = "profiling/full_cracker_profile.txt"):
    profile = cProfile.Profile()

    plain1 = "WETTERBERICHT"
    cipher1 = _make_cipher(plain1, (5, 10, 20))

    plain2 = "OBERKOMMANDO"
    pairs2 = [("A", "Z"), ("B", "Y")]
    cipher2 = _make_cipher(plain2, (2, 15, 8), pairs=pairs2)

    plain3 = "WETTERBER"
    order3 = ("III", "I", "II")
    rings3 = (3, 11, 7)
    pos3 = (9, 4, 22)
    cipher3 = _make_cipher(plain3, pos3, rotor_names=order3, rings=rings3)

    profile.enable()
    crack_rotor_positions(ciphertext=cipher1, crib=plain1)
    crack_with_plugboard(ciphertext=cipher2, crib=plain2, num_plugboard_pairs=2, solver_timeout_ms=3000)
    crack_full_configuration(
        ciphertext=cipher3,
        crib=plain3,
        rotor_pool=("I", "II", "III"),
        search_rotor_order=True,
        search_ring_settings=True,
        top_k=3,
        global_timeout_ms=3000,
    )
    profile.disable()

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        stats = pstats.Stats(profile, stream=handle).sort_stats("cumtime")
        stats.print_stats(60)

    print(f"Profile written to: {output_path}")


if __name__ == "__main__":
    run_profile()
