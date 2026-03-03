"""
Benchmark runner for Enigma crackers.

Outputs:
- benchmark_results.csv
- benchmark_results.png
"""

from __future__ import annotations

import csv
import random
import time
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from cracker.full_cracker import (
    crack_full_configuration,
    crack_rotor_positions,
    crack_with_plugboard,
)
from enigma.machine import EnigmaMachine
from enigma.plugboard import Plugboard
from enigma.reflector import Reflector
from enigma.rotor import Rotor


@dataclass
class BenchmarkRow:
    scenario: str
    parameter: str
    value: int
    seconds: float
    ok: bool


def _random_plugboard_pairs(n: int) -> list[tuple[str, str]]:
    letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    random.shuffle(letters)
    return [(letters[2 * i], letters[2 * i + 1]) for i in range(n)]


def _make_machine(
    rotor_names: tuple[str, str, str],
    positions: tuple[int, int, int],
    rings: tuple[int, int, int] = (0, 0, 0),
    pairs: list[tuple[str, str]] | None = None,
) -> EnigmaMachine:
    rotors = [
        Rotor.from_name(rotor_names[0], ring=rings[0], position=positions[0]),
        Rotor.from_name(rotor_names[1], ring=rings[1], position=positions[1]),
        Rotor.from_name(rotor_names[2], ring=rings[2], position=positions[2]),
    ]
    reflector = Reflector.from_name("B")
    plugboard = Plugboard(pairs)
    return EnigmaMachine(rotors, reflector, plugboard)


def benchmark_crib_length() -> list[BenchmarkRow]:
    rows: list[BenchmarkRow] = []
    crib_lengths = [3, 5, 7, 10, 13, 15]
    plaintext_pool = "WETTERBERICHTZZ"
    secret_pos = (5, 10, 20)

    print("=== Benchmark: Crib length (known configuration, no plugboard) ===")
    for length in crib_lengths:
        plaintext = plaintext_pool[:length]
        machine = _make_machine(("I", "II", "III"), secret_pos)
        ciphertext = machine.process(plaintext)

        t0 = time.perf_counter()
        result = crack_rotor_positions(ciphertext=ciphertext, crib=plaintext)
        elapsed = time.perf_counter() - t0
        ok = result == secret_pos
        rows.append(
            BenchmarkRow(
                scenario="crib_length",
                parameter="length",
                value=length,
                seconds=elapsed,
                ok=ok,
            )
        )
        print(f"  length={length:2d}  time={elapsed:7.3f}s  [{'OK' if ok else 'FAIL'}]")
    return rows


def benchmark_plugboard_pairs() -> list[BenchmarkRow]:
    rows: list[BenchmarkRow] = []
    pair_counts = [0, 1, 2, 3]
    secret_pos = (3, 7, 14)
    plaintext = "WETTERBERICHT"

    print("\n=== Benchmark: Unknown plugboard pairs ===")
    for count in pair_counts:
        pairs = _random_plugboard_pairs(count) if count > 0 else []
        machine = _make_machine(("I", "II", "III"), secret_pos, pairs=pairs)
        ciphertext = machine.process(plaintext)

        t0 = time.perf_counter()
        if count == 0:
            result = crack_rotor_positions(ciphertext=ciphertext, crib=plaintext)
            ok = result == secret_pos
        else:
            cracked = crack_with_plugboard(
                ciphertext=ciphertext,
                crib=plaintext,
                num_plugboard_pairs=count,
            )
            ok = cracked is not None and cracked[0] == secret_pos
        elapsed = time.perf_counter() - t0

        rows.append(
            BenchmarkRow(
                scenario="plugboard_unknown",
                parameter="pairs",
                value=count,
                seconds=elapsed,
                ok=ok,
            )
        )
        print(f"  pairs={count:2d}   time={elapsed:7.3f}s  [{'OK' if ok else 'FAIL'}]")
    return rows


def benchmark_unknown_order_and_rings() -> list[BenchmarkRow]:
    rows: list[BenchmarkRow] = []
    crib_lengths = [6, 8, 10]
    rotor_order = ("III", "I", "II")
    positions = (9, 4, 22)
    rings = (2, 11, 7)
    plaintext_pool = "OBERKOMMANDOTESTWETTER"

    ring_candidates = [(0, 0, 0), (2, 11, 7), (1, 1, 1), (7, 7, 7)]
    print("\n=== Benchmark: Unknown rotor order + ring-candidate ranking ===")
    for length in crib_lengths:
        plaintext = plaintext_pool[:length]
        machine = _make_machine(rotor_order, positions, rings=rings)
        ciphertext = machine.process(plaintext)

        t0 = time.perf_counter()
        result = crack_full_configuration(
            ciphertext=ciphertext,
            crib=plaintext,
            rotor_pool=("I", "II", "III"),
            search_rotor_order=True,
            search_ring_settings=False,
            ring_candidates=ring_candidates,
            top_k=3,
            global_timeout_ms=9000,
            solver_timeout_ms_per_config=70,
            heuristic_position_budget=500,
        )
        elapsed = time.perf_counter() - t0
        ok = (
            result is not None
            and result.mismatches == 0
            and result.rotor_names == rotor_order
            and result.ring_settings == rings
            and result.positions == positions
        )

        rows.append(
            BenchmarkRow(
                scenario="order_rings_unknown",
                parameter="length",
                value=length,
                seconds=elapsed,
                ok=ok,
            )
        )
        print(f"  length={length:2d}  time={elapsed:7.3f}s  [{'OK' if ok else 'FAIL'}]")
    return rows


def write_csv(rows: list[BenchmarkRow], csv_path: Path):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["scenario", "parameter", "value", "seconds", "ok"])
        for row in rows:
            writer.writerow(
                [
                    row.scenario,
                    row.parameter,
                    row.value,
                    f"{row.seconds:.6f}",
                    int(row.ok),
                ]
            )


def plot_results(rows: list[BenchmarkRow], output_png: Path):
    output_png.parent.mkdir(parents=True, exist_ok=True)

    def _series(scenario: str):
        data = [r for r in rows if r.scenario == scenario]
        data.sort(key=lambda r: r.value)
        return [r.value for r in data], [r.seconds for r in data], [r.ok for r in data]

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    for ax, (scenario, title, color) in zip(
        axes,
        [
            ("crib_length", "Known setup vs crib length", "tab:blue"),
            ("plugboard_unknown", "Unknown plugboard pairs", "tab:red"),
            ("order_rings_unknown", "Unknown order and rings", "tab:green"),
        ],
    ):
        xs, ys, oks = _series(scenario)
        ax.plot(xs, ys, marker="o", linewidth=2, color=color)
        for x, y, ok in zip(xs, ys, oks):
            ax.annotate("OK" if ok else "FAIL", (x, y), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=8)
        ax.set_title(title)
        ax.set_xlabel("Parameter")
        ax.set_ylabel("Seconds")
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_png, dpi=150)
    plt.close()


def run_benchmarks(
    csv_path: str = "benchmark_results.csv",
    png_path: str = "benchmark_results.png",
    seed: int = 42,
):
    random.seed(seed)

    rows: list[BenchmarkRow] = []
    rows.extend(benchmark_crib_length())
    rows.extend(benchmark_plugboard_pairs())
    rows.extend(benchmark_unknown_order_and_rings())

    write_csv(rows, Path(csv_path))
    plot_results(rows, Path(png_path))

    print(f"\nCSV saved to: {csv_path}")
    print(f"Plot saved to: {png_path}")


def main():
    run_benchmarks()


if __name__ == "__main__":
    main()
