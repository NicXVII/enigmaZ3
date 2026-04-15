"""Command-line interface for enigmaZ3."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from benchmark import run_benchmarks
from cracker import (
    crack_full_configuration,
    crack_rotor_positions,
    crack_with_plugboard,
    rank_rotor_configurations,
)
from enigma import EnigmaMachine, Plugboard, Reflector, Rotor
from enigma.reflector import REFLECTOR_WIRINGS
from enigma.rotor import ROTOR_WIRINGS

LOGGER = logging.getLogger("enigma_cli")


def _parse_triplet(raw: str, field_name: str) -> tuple[int, int, int]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) != 3:
        raise ValueError(f"{field_name} must contain exactly 3 comma-separated integers")
    values = tuple(int(v) for v in parts)
    for value in values:
        if value < 0 or value > 25:
            raise ValueError(f"{field_name} values must be in range 0..25")
    return values[0], values[1], values[2]


def _parse_rotors(raw: str) -> tuple[str, str, str]:
    parts = [p.strip().upper() for p in raw.split(",") if p.strip()]
    if len(parts) != 3:
        raise ValueError("rotors must contain exactly 3 comma-separated names")
    for name in parts:
        if name not in ROTOR_WIRINGS:
            raise ValueError(f"unsupported rotor: {name}")
    return parts[0], parts[1], parts[2]


def _parse_rotor_pool(raw: str) -> tuple[str, ...]:
    parts = [p.strip().upper() for p in raw.split(",") if p.strip()]
    if len(parts) < 3:
        raise ValueError("rotor pool must contain at least 3 rotor names")
    for name in parts:
        if name not in ROTOR_WIRINGS:
            raise ValueError(f"unsupported rotor: {name}")
    return tuple(parts)


def _parse_pairs(raw: str | None) -> list[tuple[str, str]]:
    if raw is None or raw.strip() == "":
        return []
    pairs: list[tuple[str, str]] = []
    used: set[str] = set()
    for token in raw.split(","):
        pair = token.strip().upper()
        if pair == "":
            continue
        if len(pair) != 2 or not pair.isalpha():
            raise ValueError(f"invalid plugboard pair: {token}")
        a, b = pair[0], pair[1]
        if a in used or b in used:
            raise ValueError(f"duplicate letter in plugboard pairs: {token}")
        used.add(a)
        used.add(b)
        pairs.append((a, b))
    if len(pairs) > 13:
        raise ValueError("plugboard supports at most 13 pairs")
    return pairs


def _build_machine(
    rotors: tuple[str, str, str],
    positions: tuple[int, int, int],
    rings: tuple[int, int, int],
    reflector_name: str,
    pairs: list[tuple[str, str]],
) -> EnigmaMachine:
    if reflector_name not in REFLECTOR_WIRINGS:
        raise ValueError(f"unsupported reflector: {reflector_name}")

    rotor_objs = [
        Rotor.from_name(rotors[0], ring=rings[0], position=positions[0]),
        Rotor.from_name(rotors[1], ring=rings[1], position=positions[1]),
        Rotor.from_name(rotors[2], ring=rings[2], position=positions[2]),
    ]
    reflector = Reflector.from_name(reflector_name)
    plugboard = Plugboard(pairs)
    return EnigmaMachine(rotor_objs, reflector, plugboard)


def _cmd_encrypt_like(args: argparse.Namespace) -> int:
    rotors = _parse_rotors(args.rotors)
    positions = _parse_triplet(args.positions, "positions")
    rings = _parse_triplet(args.rings, "rings")
    pairs = _parse_pairs(args.plugboard)

    machine = _build_machine(rotors, positions, rings, args.reflector.upper(), pairs)
    output = machine.process(args.text)
    print(output)
    return 0


def _cmd_crack(args: argparse.Namespace) -> int:
    pairs = _parse_pairs(args.plugboard)

    if args.mode == "positions":
        rotors = _parse_rotors(args.rotors)
        rings = _parse_triplet(args.rings, "rings")
        result = crack_rotor_positions(
            ciphertext=args.ciphertext,
            crib=args.crib,
            rotor_names=rotors,
            reflector_name=args.reflector.upper(),
            plugboard_pairs=pairs if pairs else None,
            ring_settings=rings,
            solver_timeout_ms=args.timeout_ms,
        )
        print(json.dumps({"positions": result}, ensure_ascii=True))
        return 0

    if args.mode == "plugboard":
        rotors = _parse_rotors(args.rotors)
        rings = _parse_triplet(args.rings, "rings")
        result = crack_with_plugboard(
            ciphertext=args.ciphertext,
            crib=args.crib,
            rotor_names=rotors,
            reflector_name=args.reflector.upper(),
            num_plugboard_pairs=args.num_pairs,
            ring_settings=rings,
            solver_timeout_ms=args.timeout_ms,
        )
        payload: dict[str, Any]
        if result is None:
            payload = {"result": None}
        else:
            payload = {
                "positions": result[0],
                "plugboard_pairs": result[1],
            }
        print(json.dumps(payload, ensure_ascii=True))
        return 0

    rotor_pool = _parse_rotor_pool(args.rotor_pool)
    ring_candidates = None
    if args.ring_candidates:
        ring_candidates = [_parse_triplet(raw, "ring candidate") for raw in args.ring_candidates]

    ranked = rank_rotor_configurations(
        ciphertext=args.ciphertext,
        crib=args.crib,
        rotor_pool=rotor_pool,
        reflector_name=args.reflector.upper(),
        plugboard_pairs=pairs if pairs else None,
        search_rotor_order=not args.fixed_order,
        search_ring_settings=args.search_rings,
        ring_candidates=ring_candidates,
        top_k=args.top_k,
        global_timeout_ms=args.timeout_ms,
        solver_timeout_ms_per_config=args.per_config_timeout_ms,
        heuristic_position_budget=args.heuristic_budget,
    )
    best = crack_full_configuration(
        ciphertext=args.ciphertext,
        crib=args.crib,
        rotor_pool=rotor_pool,
        reflector_name=args.reflector.upper(),
        plugboard_pairs=pairs if pairs else None,
        search_rotor_order=not args.fixed_order,
        search_ring_settings=args.search_rings,
        ring_candidates=ring_candidates,
        top_k=args.top_k,
        global_timeout_ms=args.timeout_ms,
        solver_timeout_ms_per_config=args.per_config_timeout_ms,
        heuristic_position_budget=args.heuristic_budget,
    )

    payload = {
        "best": None if best is None else {
            "rotor_names": best.rotor_names,
            "ring_settings": best.ring_settings,
            "positions": best.positions,
            "mismatches": best.mismatches,
            "method": best.method,
        },
        "ranked": [
            {
                "rotor_names": c.rotor_names,
                "ring_settings": c.ring_settings,
                "positions": c.positions,
                "mismatches": c.mismatches,
                "matched_chars": c.matched_chars,
                "method": c.method,
                "elapsed_ms": round(c.elapsed_ms, 3),
            }
            for c in ranked
        ],
    }
    print(json.dumps(payload, ensure_ascii=True))
    return 0


def _cmd_benchmark(args: argparse.Namespace) -> int:
    run_benchmarks(csv_path=args.csv, png_path=args.png, seed=args.seed)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="enigmaZ3 CLI")
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="logging level",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    common_crypto = argparse.ArgumentParser(add_help=False)
    common_crypto.add_argument("--text", required=True, help="input text")
    common_crypto.add_argument("--rotors", default="I,II,III", help="left,middle,right rotor names")
    common_crypto.add_argument("--positions", default="0,0,0", help="left,middle,right positions")
    common_crypto.add_argument("--rings", default="0,0,0", help="left,middle,right ring settings")
    common_crypto.add_argument("--reflector", default="B", help="reflector name (B/C)")
    common_crypto.add_argument("--plugboard", default="", help="plugboard pairs format: AB,CD,EF")

    p_encrypt = sub.add_parser("encrypt", parents=[common_crypto], help="encrypt text")
    p_encrypt.set_defaults(func=_cmd_encrypt_like)

    p_decrypt = sub.add_parser("decrypt", parents=[common_crypto], help="decrypt text")
    p_decrypt.set_defaults(func=_cmd_encrypt_like)

    p_crack = sub.add_parser("crack", help="crack ciphertext")
    p_crack.add_argument("--mode", choices=["positions", "plugboard", "full"], default="positions")
    p_crack.add_argument("--ciphertext", required=True)
    p_crack.add_argument("--crib", required=True)
    p_crack.add_argument("--reflector", default="B")
    p_crack.add_argument("--timeout-ms", type=int, default=3000)
    p_crack.add_argument("--plugboard", default="", help="known plugboard pairs format: AB,CD")

    p_crack.add_argument("--rotors", default="I,II,III", help="used by positions/plugboard mode")
    p_crack.add_argument("--rings", default="0,0,0", help="used by positions/plugboard mode")
    p_crack.add_argument("--num-pairs", type=int, default=3, help="used by plugboard mode")

    p_crack.add_argument("--rotor-pool", default="I,II,III", help="used by full mode")
    p_crack.add_argument("--search-rings", action="store_true", help="used by full mode")
    p_crack.add_argument("--fixed-order", action="store_true", help="used by full mode")
    p_crack.add_argument("--ring-candidates", action="append", help="used by full mode; repeatable, format x,y,z")
    p_crack.add_argument("--top-k", type=int, default=5, help="used by full mode")
    p_crack.add_argument("--per-config-timeout-ms", type=int, default=80, help="used by full mode")
    p_crack.add_argument("--heuristic-budget", type=int, default=700, help="used by full mode")
    p_crack.set_defaults(func=_cmd_crack)

    p_benchmark = sub.add_parser("benchmark", help="run benchmark suite")
    p_benchmark.add_argument("--csv", default="benchmark_results.csv")
    p_benchmark.add_argument("--png", default="benchmark_results.png")
    p_benchmark.add_argument("--seed", type=int, default=42)
    p_benchmark.set_defaults(func=_cmd_benchmark)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level))

    try:
        return int(args.func(args))
    except ValueError as exc:
        LOGGER.error(str(exc))
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        LOGGER.exception("unexpected error")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
