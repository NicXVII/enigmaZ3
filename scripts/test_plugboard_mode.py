"""Complex plugboard-mode test with unknown rotors, rings and pair count."""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cracker.full_cracker import crack_with_plugboard, rank_rotor_configurations
from enigma.machine import EnigmaMachine
from enigma.plugboard import Plugboard
from enigma.reflector import Reflector
from enigma.rotor import Rotor


# Search space known to the attacker/test harness.
ROTOR_POOL = ("I", "II", "III", "IV")
RING_CANDIDATES = [
    (0, 0, 0),
    (1, 1, 1),
    (2, 11, 7),
    (3, 12, 5),
    (7, 7, 7),
    (9, 4, 22),
    (13, 2, 19),
    (25, 25, 25),
]
PAIR_COUNTS = (0, 1, 2, 3, 4, 5, 6)

RANK_TOP_K = 20
RANK_TIMEOUT_MS = 6_000
RANK_PER_CONFIG_TIMEOUT_MS = 80
RANK_HEURISTIC_BUDGET = 700

CRACK_TIMEOUT_MS = 2_500
GLOBAL_TIMEOUT_SECONDS = 90.0


@dataclass(frozen=True)
class Scenario:
    rotor_names: tuple[str, str, str]
    rings: tuple[int, int, int]
    positions: tuple[int, int, int]
    plugboard_pairs: list[tuple[str, str]]
    plaintext: str


def _normalize_pairs(pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
    normalized = []
    for a, b in pairs:
        if a > b:
            a, b = b, a
        normalized.append((a, b))
    normalized.sort()
    return normalized


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


def _build_hidden_scenario() -> Scenario:
    # Hidden key used only to generate the ciphertext.
    return Scenario(
        rotor_names=("III", "I", "II"),
        rings=(2, 11, 7),
        positions=(9, 4, 22),
        plugboard_pairs=[("A", "Z"), ("B", "Y"), ("C", "X"), ("D", "W")],
        plaintext="WETTERBERICHTOBERKOMMANDO",
    )


def _prioritized_configs(
    ciphertext: str,
    plaintext: str,
) -> list[tuple[tuple[str, str, str], tuple[int, int, int]]]:
    ranked = rank_rotor_configurations(
        ciphertext=ciphertext,
        crib=plaintext,
        rotor_pool=ROTOR_POOL,
        reflector_name="B",
        plugboard_pairs=None,  # unknown plugboard in this test
        search_rotor_order=True,
        search_ring_settings=False,
        ring_candidates=RING_CANDIDATES,
        top_k=RANK_TOP_K,
        global_timeout_ms=RANK_TIMEOUT_MS,
        solver_timeout_ms_per_config=RANK_PER_CONFIG_TIMEOUT_MS,
        heuristic_position_budget=RANK_HEURISTIC_BUDGET,
    )

    seen: set[tuple[tuple[str, str, str], tuple[int, int, int]]] = set()
    ordered: list[tuple[tuple[str, str, str], tuple[int, int, int]]] = []

    for candidate in ranked:
        item = (candidate.rotor_names, candidate.ring_settings)
        if item not in seen:
            seen.add(item)
            ordered.append(item)

    for rotor_names in itertools.permutations(ROTOR_POOL, 3):
        for rings in RING_CANDIDATES:
            item = (rotor_names, rings)
            if item not in seen:
                seen.add(item)
                ordered.append(item)
    return ordered


def main() -> int:
    scenario = _build_hidden_scenario()
    encryptor = _make_machine(
        rotor_names=scenario.rotor_names,
        positions=scenario.positions,
        rings=scenario.rings,
        plugboard_pairs=scenario.plugboard_pairs,
    )
    ciphertext = encryptor.process(scenario.plaintext)

    print("=== Test complesso modalita plugboard ===")
    print("Attaccante NON conosce: rotori, rings, posizioni iniziali, numero coppie plugboard.")
    print(f"Ciphertext noto: {ciphertext}")
    print(f"Crib noto:       {scenario.plaintext}")
    print(f"Ricerca su rotor pool: {ROTOR_POOL}")
    print(f"Ring candidates: {len(RING_CANDIDATES)}")
    print(f"Pair counts testati: {PAIR_COUNTS}")
    print()

    configs = _prioritized_configs(ciphertext, scenario.plaintext)
    print(f"Configurazioni rotor/ring da provare: {len(configs)}")

    started = time.perf_counter()
    attempts = 0
    found = None

    # Prioritize medium pair counts first; often faster to resolve than extremes.
    pair_counts = sorted(PAIR_COUNTS, key=lambda n: abs(n - 3))

    for rotor_names, rings in configs:
        if time.perf_counter() - started > GLOBAL_TIMEOUT_SECONDS:
            break
        for num_pairs in pair_counts:
            if time.perf_counter() - started > GLOBAL_TIMEOUT_SECONDS:
                break

            attempts += 1
            result = crack_with_plugboard(
                ciphertext=ciphertext,
                crib=scenario.plaintext,
                rotor_names=rotor_names,
                reflector_name="B",
                num_plugboard_pairs=num_pairs,
                ring_settings=rings,
                solver_timeout_ms=CRACK_TIMEOUT_MS,
            )
            if attempts % 20 == 0:
                elapsed = time.perf_counter() - started
                print(f"Progress: {attempts} tentativi in {elapsed:.1f}s")

            if result is None:
                continue

            found_positions, found_pairs = result
            verify_machine = _make_machine(
                rotor_names=rotor_names,
                positions=found_positions,
                rings=rings,
                plugboard_pairs=found_pairs,
            )
            if verify_machine.process(scenario.plaintext) != ciphertext:
                continue

            found = (rotor_names, rings, found_positions, found_pairs, num_pairs)
            break

        if found is not None:
            break

    elapsed = time.perf_counter() - started
    if found is None:
        print(f"FAIL: nessuna soluzione trovata in {elapsed:.2f}s ({attempts} tentativi).")
        return 1

    found_rotors, found_rings, found_positions, found_pairs, found_count = found

    print()
    print(f"Soluzione trovata in {elapsed:.2f}s dopo {attempts} tentativi")
    print(f"Rotori trovati:    {found_rotors}")
    print(f"Rings trovati:     {found_rings}")
    print(f"Posizioni trovate: {found_positions}")
    print(f"Num coppie trovato:{found_count}")
    print(f"Coppie trovate:    {found_pairs}")

    rotors_ok = found_rotors == scenario.rotor_names
    rings_ok = found_rings == scenario.rings
    positions_ok = found_positions == scenario.positions
    pairs_ok = _normalize_pairs(found_pairs) == _normalize_pairs(scenario.plugboard_pairs)

    print()
    if rotors_ok and rings_ok and positions_ok and pairs_ok:
        print("OK: recupero completo della chiave (rotori + rings + posizioni + plugboard).")
        return 0

    print("WARNING: configurazione trovata valida sul crib ma diversa dalla chiave nascosta.")
    print(f"  rotori esatti:    {rotors_ok}")
    print(f"  rings esatti:     {rings_ok}")
    print(f"  posizioni esatte: {positions_ok}")
    print(f"  plugboard esatto: {pairs_ok}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
