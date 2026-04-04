"""
CLI parser regression tests.
"""

from pathlib import Path
import sys

# Allow direct execution from tests/ by exposing repo root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enigma_cli import _build_parser


def test_crack_mode_positions_is_accepted():
    parser = _build_parser()
    args = parser.parse_args(
        [
            "crack",
            "--mode",
            "positions",
            "--ciphertext",
            "ABC",
            "--crib",
            "ABC",
        ]
    )
    assert args.mode == "positions"


def test_crack_mode_plugboard_and_num_pairs_are_accepted():
    parser = _build_parser()
    args = parser.parse_args(
        [
            "crack",
            "--mode",
            "plugboard",
            "--ciphertext",
            "ABC",
            "--crib",
            "ABC",
            "--num-pairs",
            "3",
        ]
    )
    assert args.mode == "plugboard"
    assert args.num_pairs == 3


def test_benchmark_seed_is_accepted():
    parser = _build_parser()
    args = parser.parse_args(["benchmark", "--seed", "42"])
    assert args.seed == 42
