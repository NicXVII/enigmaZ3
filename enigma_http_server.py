#!/usr/bin/env python3
"""
HTTP API for the EnigmaZ3 frontends (no extra dependencies).

  POST /encrypt  — simulate Enigma (JSON body)
  POST /crack    — run Z3 cracker from cracker/ (JSON body)

Run from repository root:

  python enigma_http_server.py
  # or: python enigma_http_server.py 8765

Set frontends:  window.ENIGMA_API_BASE = "http://127.0.0.1:8765"
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from cracker import crack_full_configuration, crack_rotor_positions, crack_with_plugboard
from enigma import EnigmaMachine, Plugboard, Reflector, Rotor
from enigma.reflector import REFLECTOR_WIRINGS
from enigma.rotor import ROTOR_WIRINGS

DEFAULT_CONSTRAINTS = [
    "plugboard involution",
    "reflector involution without fixed points",
    "rotor stepping (double-step)",
    "no self-encryption",
    "crib–ciphertext consistency",
]


def _parse_pairs(payload: Any) -> list[tuple[str, str]]:
    """Accept CLI-style 'AZ,BY', space-separated 'AZ BY', or JSON [['A','Z'],...]."""
    if payload is None or payload == "":
        return []
    if isinstance(payload, list):
        out: list[tuple[str, str]] = []
        for item in payload:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                a = str(item[0]).strip().upper()
                b = str(item[1]).strip().upper()
                if len(a) == 1 and len(b) == 1 and a.isalpha() and b.isalpha():
                    out.append((a, b))
        return out
    if isinstance(payload, str):
        raw = payload.replace(",", " ")
        used: set[str] = set()
        pairs: list[tuple[str, str]] = []
        for token in raw.split():
            pair = token.strip().upper()
            if len(pair) != 2 or not pair.isalpha():
                continue
            a, b = pair[0], pair[1]
            if a in used or b in used:
                continue
            used.add(a)
            used.add(b)
            pairs.append((a, b))
        return pairs
    return []


def _build_machine(
    rotors: tuple[str, str, str],
    positions: tuple[int, int, int],
    rings: tuple[int, int, int],
    reflector_name: str,
    pairs: list[tuple[str, str]],
) -> EnigmaMachine:
    if reflector_name not in REFLECTOR_WIRINGS:
        raise ValueError(f"unsupported reflector: {reflector_name}")
    for name in rotors:
        if name not in ROTOR_WIRINGS:
            raise ValueError(f"unsupported rotor: {name}")
    rotor_objs = [
        Rotor.from_name(rotors[0], ring=rings[0], position=positions[0]),
        Rotor.from_name(rotors[1], ring=rings[1], position=positions[1]),
        Rotor.from_name(rotors[2], ring=rings[2], position=positions[2]),
    ]
    reflector = Reflector.from_name(reflector_name)
    plugboard = Plugboard(pairs)
    return EnigmaMachine(rotor_objs, reflector, plugboard)


def handle_encrypt(data: dict[str, Any]) -> dict[str, Any]:
    rotors = data.get("rotors") or ["I", "II", "III"]
    if len(rotors) != 3:
        raise ValueError("rotors must be a list of 3 names")
    positions = tuple(int(x) for x in (data.get("positions") or [0, 0, 0]))
    rings = tuple(int(x) for x in (data.get("rings") or [0, 0, 0]))
    reflector = str(data.get("reflector") or "B").upper()
    pairs = _parse_pairs(data.get("plugboard"))
    text = data.get("text") or data.get("plaintext") or ""
    machine = _build_machine(tuple(rotors), positions, rings, reflector, pairs)
    return {"ciphertext": machine.process(text), "ok": True}


def handle_crack(data: dict[str, Any]) -> dict[str, Any]:
    ciphertext = str(data.get("ciphertext") or "")
    crib = str(data.get("crib") or "")
    mode = str(data.get("mode") or "positions").lower()
    reflector = str(data.get("reflector") or "B").upper()
    rotors_in = data.get("rotors") or data.get("guess_rotors") or ["I", "II", "III"]
    if len(rotors_in) != 3:
        raise ValueError("rotors must be a list of 3 names")
    rotor_names = tuple(str(x).upper() for x in rotors_in)
    rings_list = data.get("rings") or [0, 0, 0]
    rings = tuple(int(x) % 26 for x in rings_list)
    plugboard_pairs = _parse_pairs(data.get("plugboard"))
    plugboard_arg = plugboard_pairs if plugboard_pairs else None

    timeout_positions = int(data.get("timeout_ms_positions") or data.get("timeout_ms") or 30_000)
    timeout_plugboard = int(data.get("timeout_ms_plugboard") or 120_000)
    timeout_full = int(data.get("timeout_ms_full") or 180_000)
    per_config = int(data.get("per_config_timeout_ms") or 120)
    num_pairs = int(data.get("num_plugboard_pairs") or 3)

    rotor_pool_raw = data.get("rotor_pool")
    if rotor_pool_raw and isinstance(rotor_pool_raw, list) and len(rotor_pool_raw) >= 3:
        rotor_pool = tuple(str(x).upper() for x in rotor_pool_raw)
    else:
        rotor_pool = ("I", "II", "III", "IV", "V")

    crib_n = "".join(ch for ch in crib.upper() if ch.isalpha())
    cipher_n = "".join(ch for ch in ciphertext.upper() if ch.isalpha())

    constraints_used = list(DEFAULT_CONSTRAINTS)
    if mode == "positions":
        constraints_used = [c for c in constraints_used if c != "plugboard involution"]

    if not crib_n or len(cipher_n) < len(crib_n):
        return {
            "status": "unsat",
            "error": "empty crib or ciphertext shorter than crib",
            "plaintext": crib_n,
            "ciphertext": cipher_n,
            "constraints_used": constraints_used,
        }

    if mode == "positions":
        result = crack_rotor_positions(
            ciphertext=cipher_n,
            crib=crib_n,
            rotor_names=rotor_names,
            reflector_name=reflector,
            plugboard_pairs=plugboard_arg,
            ring_settings=rings,
            solver_timeout_ms=timeout_positions,
            allow_numeric_fallback=True,
        )
        if result is None:
            return {
                "status": "unsat",
                "plaintext": crib_n,
                "ciphertext": cipher_n[: len(crib_n)],
                "constraints_used": constraints_used,
            }
        return {
            "status": "sat",
            "rotors": list(rotor_names),
            "positions": list(result),
            "rings": list(rings),
            "plugboard": [[a, b] for a, b in plugboard_pairs] if plugboard_pairs else [],
            "plaintext": crib_n,
            "ciphertext": cipher_n[: len(crib_n)],
            "constraints_used": constraints_used,
        }

    if mode == "plugboard":
        constraints_used = list(DEFAULT_CONSTRAINTS)
        result = crack_with_plugboard(
            ciphertext=cipher_n,
            crib=crib_n,
            rotor_names=rotor_names,
            reflector_name=reflector,
            num_plugboard_pairs=num_pairs,
            ring_settings=rings,
            solver_timeout_ms=timeout_plugboard,
        )
        if result is None:
            return {
                "status": "unsat",
                "plaintext": crib_n,
                "ciphertext": cipher_n[: len(crib_n)],
                "constraints_used": constraints_used,
            }
        pos, pairs_found = result
        return {
            "status": "sat",
            "rotors": list(rotor_names),
            "positions": list(pos),
            "rings": list(rings),
            "plugboard": [[a, b] for a, b in pairs_found],
            "plaintext": crib_n,
            "ciphertext": cipher_n[: len(crib_n)],
            "constraints_used": constraints_used,
        }

    if mode == "full":
        best = crack_full_configuration(
            ciphertext=cipher_n,
            crib=crib_n,
            rotor_pool=rotor_pool,
            reflector_name=reflector,
            plugboard_pairs=plugboard_arg,
            search_rotor_order=True,
            search_ring_settings=False,
            ring_candidates=[rings],
            top_k=8,
            global_timeout_ms=timeout_full,
            solver_timeout_ms_per_config=per_config,
            heuristic_position_budget=int(data.get("heuristic_budget") or 1200),
        )
        if best is None or best.positions is None:
            return {
                "status": "unsat",
                "plaintext": crib_n,
                "ciphertext": cipher_n[: len(crib_n)],
                "constraints_used": list(DEFAULT_CONSTRAINTS),
            }
        return {
            "status": "sat",
            "rotors": list(best.rotor_names),
            "positions": list(best.positions),
            "rings": list(best.ring_settings),
            "plugboard": [[a, b] for a, b in plugboard_pairs] if plugboard_pairs else [],
            "plaintext": crib_n,
            "ciphertext": cipher_n[: len(crib_n)],
            "constraints_used": list(DEFAULT_CONSTRAINTS),
            "method": best.method,
        }

    raise ValueError(f"unknown mode: {mode}")


class EnigmaAPIHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def _send_json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path in ("/", "/health"):
            self._send_json(
                200,
                {
                    "service": "enigmaZ3",
                    "endpoints": ["POST /encrypt", "POST /crack"],
                },
            )
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path not in ("/encrypt", "/crack"):
            self._send_json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError as e:
            self._send_json(400, {"error": f"invalid JSON: {e}"})
            return
        try:
            if self.path == "/encrypt":
                out = handle_encrypt(data)
            else:
                out = handle_crack(data)
            self._send_json(200, out)
        except Exception as e:
            self._send_json(500, {"error": str(e), "status": "error"})


def main() -> None:
    port = 8765
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    server = HTTPServer(("127.0.0.1", port), EnigmaAPIHandler)
    print(f"EnigmaZ3 API listening on http://127.0.0.1:{port}", file=sys.stderr)
    print("  POST /encrypt  POST /crack  GET /health", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.", file=sys.stderr)
        server.shutdown()


if __name__ == "__main__":
    main()
