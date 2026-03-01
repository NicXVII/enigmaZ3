"""
Phase 5 — Benchmark and plots.

Measures Z3 solving time as a function of:
1. Number of plugboard pairs (0, 2, 4, 6, 8, 10)
2. Crib length (3, 5, 7, 10, 13, 15)

Generates two matplotlib charts saved as PNG files.
"""

import time
import random
import string
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt

from enigma.rotor import Rotor
from enigma.reflector import Reflector
from enigma.plugboard import Plugboard
from enigma.machine import EnigmaMachine
from cracker.full_cracker import crack_rotor_positions, crack_with_plugboard


def _random_plugboard_pairs(n: int) -> list[tuple[str, str]]:
    """Generate n random non-overlapping plugboard pairs."""
    letters = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    random.shuffle(letters)
    pairs = []
    for i in range(n):
        a, b = letters[2 * i], letters[2 * i + 1]
        pairs.append((a, b))
    return pairs


def _make_machine(positions, pairs=None, rings=(0, 0, 0)):
    rotors = [
        Rotor.from_name("I", ring=rings[0], position=positions[0]),
        Rotor.from_name("II", ring=rings[1], position=positions[1]),
        Rotor.from_name("III", ring=rings[2], position=positions[2]),
    ]
    reflector = Reflector.from_name("B")
    plugboard = Plugboard(pairs)
    return EnigmaMachine(rotors, reflector, plugboard)


def benchmark_crib_length():
    """Benchmark Z3 solve time vs crib length (no plugboard)."""
    crib_lengths = [3, 5, 7, 10, 13, 15]
    times = []

    base_plain = "WETTERBERICHT"  # 13 chars, extend if needed
    # Extend to 15 chars
    base_plain = "WETTERBERICHTZZ"

    secret_pos = (5, 10, 20)

    print("=== Benchmark: Crib Length (no plugboard) ===")
    for length in crib_lengths:
        plaintext = base_plain[:length]
        machine = _make_machine(secret_pos)
        ciphertext = machine.process(plaintext)

        start = time.time()
        result = crack_rotor_positions(
            ciphertext=ciphertext,
            crib=plaintext,
        )
        elapsed = time.time() - start
        times.append(elapsed)
        status = "OK" if result == secret_pos else "FAIL"
        print(f"  crib_len={length:2d}  time={elapsed:6.2f}s  [{status}]")

    return crib_lengths, times


def benchmark_plugboard_pairs():
    """Benchmark Z3 solve time vs number of plugboard pairs."""
    pair_counts = [0, 1, 2, 3]
    times = []

    secret_pos = (3, 7, 14)
    plaintext = "WETTERBERICHT"

    print("\n=== Benchmark: Plugboard Pairs ===")
    for np in pair_counts:
        pairs = _random_plugboard_pairs(np) if np > 0 else []
        machine = _make_machine(secret_pos, pairs=pairs)
        ciphertext = machine.process(plaintext)

        start = time.time()
        if np == 0:
            result = crack_rotor_positions(
                ciphertext=ciphertext,
                crib=plaintext,
            )
            ok = result == secret_pos
        else:
            result = crack_with_plugboard(
                ciphertext=ciphertext,
                crib=plaintext,
                num_plugboard_pairs=np,
            )
            if result is not None:
                found_pos, found_pairs = result
                ok = found_pos == secret_pos
            else:
                ok = False
        elapsed = time.time() - start
        times.append(elapsed)
        status = "OK" if ok else "FAIL"
        print(f"  pairs={np:2d}  time={elapsed:6.2f}s  [{status}]")

    return pair_counts, times


def plot_results(crib_data, plug_data):
    """Generate and save benchmark plots."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Plot 1: Crib length
    crib_lengths, crib_times = crib_data
    ax1.plot(crib_lengths, crib_times, "bo-", linewidth=2, markersize=8)
    ax1.set_xlabel("Lunghezza del crib (caratteri)", fontsize=12)
    ax1.set_ylabel("Tempo di risoluzione Z3 (s)", fontsize=12)
    ax1.set_title("Tempo Z3 vs Lunghezza Crib\n(3 rotori, no plugboard)", fontsize=13)
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(crib_lengths)

    # Plot 2: Plugboard pairs
    pair_counts, plug_times = plug_data
    ax2.plot(pair_counts, plug_times, "rs-", linewidth=2, markersize=8)
    ax2.set_xlabel("Numero coppie plugboard", fontsize=12)
    ax2.set_ylabel("Tempo di risoluzione Z3 (s)", fontsize=12)
    ax2.set_title("Tempo Z3 vs Coppie Plugboard\n(3 rotori, crib 13 caratteri)", fontsize=13)
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(pair_counts)

    plt.tight_layout()
    plt.savefig("benchmark_results.png", dpi=150)
    print(f"\nPlot salvato in: benchmark_results.png")
    plt.close()


if __name__ == "__main__":
    random.seed(42)
    crib_data = benchmark_crib_length()
    plug_data = benchmark_plugboard_pairs()
    plot_results(crib_data, plug_data)
    print("\nBenchmark completato!")
