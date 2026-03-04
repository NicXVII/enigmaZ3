"""
Minimal benchmark runner for rotor-position cracking.

Outputs:
- benchmark_results.csv
- benchmark_results.png
"""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from cracker.full_cracker import crack_rotor_positions
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


PAIR_POOL = [
    ("A", "Z"),
    ("B", "Y"),
    ("C", "X"),
    ("D", "W"),
    ("E", "V"),
    ("F", "U"),
]


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
    return EnigmaMachine(rotors, Reflector.from_name("B"), Plugboard(pairs))


def benchmark_crib_length() -> list[BenchmarkRow]:
    rows: list[BenchmarkRow] = []
    crib_lengths = [3, 5, 7, 10, 13, 15]
    plaintext_pool = "WETTERBERICHTZZ"
    secret_pos = (5, 10, 20)

    print("=== Benchmark: crib length ===")
    for length in crib_lengths:
        plaintext = plaintext_pool[:length]
        machine = _make_machine(("I", "II", "III"), secret_pos)
        ciphertext = machine.process(plaintext)

        t0 = time.perf_counter()
        result = crack_rotor_positions(ciphertext=ciphertext, crib=plaintext)
        elapsed = time.perf_counter() - t0
        ok = result == secret_pos
        rows.append(BenchmarkRow("crib_length", "length", length, elapsed, ok))
        print(f"  length={length:2d}  time={elapsed:7.3f}s  [{'OK' if ok else 'FAIL'}]")
    return rows


def benchmark_known_plugboard() -> list[BenchmarkRow]:
    rows: list[BenchmarkRow] = []
    pair_counts = [0, 2, 4, 6]
    secret_pos = (3, 7, 14)
    plaintext = "WETTERBERICHT"

    print("\n=== Benchmark: known plugboard pairs ===")
    for count in pair_counts:
        pairs = PAIR_POOL[:count]
        machine = _make_machine(("I", "II", "III"), secret_pos, pairs=pairs)
        ciphertext = machine.process(plaintext)

        t0 = time.perf_counter()
        result = crack_rotor_positions(
            ciphertext=ciphertext,
            crib=plaintext,
            plugboard_pairs=pairs if pairs else None,
        )
        elapsed = time.perf_counter() - t0
        ok = result == secret_pos
        rows.append(BenchmarkRow("plugboard_known", "pairs", count, elapsed, ok))
        print(f"  pairs={count:2d}   time={elapsed:7.3f}s  [{'OK' if ok else 'FAIL'}]")
    return rows


def write_csv(rows: list[BenchmarkRow], csv_path: Path):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["scenario", "parameter", "value", "seconds", "ok"])
        for row in rows:
            writer.writerow(
                [row.scenario, row.parameter, row.value, f"{row.seconds:.6f}", int(row.ok)]
            )


def plot_results(rows: list[BenchmarkRow], output_png: Path):
    output_png.parent.mkdir(parents=True, exist_ok=True)

    def _series(scenario: str):
        data = [r for r in rows if r.scenario == scenario]
        data.sort(key=lambda r: r.value)
        return [r.value for r in data], [r.seconds for r in data], [r.ok for r in data]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    plots = [
        ("crib_length", "Crib length vs time", "tab:blue", "Length"),
        ("plugboard_known", "Known plugboard pairs vs time", "tab:orange", "Pairs"),
    ]

    for ax, (scenario, title, color, xlabel) in zip(axes, plots):
        xs, ys, oks = _series(scenario)
        ax.plot(xs, ys, marker="o", linewidth=2, color=color)
        for x, y, ok in zip(xs, ys, oks):
            ax.annotate(
                "OK" if ok else "FAIL",
                (x, y),
                textcoords="offset points",
                xytext=(0, 6),
                ha="center",
                fontsize=8,
            )
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Seconds")
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_png, dpi=150)
    plt.close()


def run_benchmarks(
    csv_path: str = "benchmark_results.csv",
    png_path: str = "benchmark_results.png",
):
    rows: list[BenchmarkRow] = []
    rows.extend(benchmark_crib_length())
    rows.extend(benchmark_known_plugboard())

    write_csv(rows, Path(csv_path))
    plot_results(rows, Path(png_path))

    print(f"\nCSV saved to: {csv_path}")
    print(f"Plot saved to: {png_path}")


def main():
    run_benchmarks()


if __name__ == "__main__":
    main()
