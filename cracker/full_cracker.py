"""
Rotor-position cracker for full Enigma.

Strategy:
- first try SMT constraints with Z3;
- if Z3 times out/returns unknown, run deterministic backup scan on 26^3 starts.
"""

from __future__ import annotations

from functools import lru_cache

from z3 import Distinct, If, Int, Or, Solver, Sum, sat

from enigma import EnigmaMachine, Plugboard, Reflector, Rotor
from enigma.reflector import REFLECTOR_WIRINGS
from enigma.rotor import ROTOR_NOTCHES, ROTOR_WIRINGS


def _normalize_alpha(text: str) -> str:
    return "".join(ch for ch in text.upper() if ch.isalpha())


@lru_cache(maxsize=None)
def _wiring(name: str) -> tuple[int, ...]:
    return tuple(ord(c) - ord("A") for c in ROTOR_WIRINGS[name])


@lru_cache(maxsize=None)
def _inv_wiring(name: str) -> tuple[int, ...]:
    fwd = _wiring(name)
    inv = [0] * 26
    for i, v in enumerate(fwd):
        inv[v] = i
    return tuple(inv)


@lru_cache(maxsize=None)
def _reflector(name: str) -> tuple[int, ...]:
    return tuple(ord(c) - ord("A") for c in REFLECTOR_WIRINGS[name])


def _z3_lookup(table: tuple[int, ...], idx_expr):
    expr = table[25]
    for i in range(24, -1, -1):
        expr = If(idx_expr == i, table[i], expr)
    return expr


def _z3_wrap26(expr):
    return If(expr < 0, expr + 26, If(expr >= 26, expr - 26, expr))


def _compute_positions(left0, middle0, right0, n: int, notches: tuple[int, int, int]):
    pos_left = []
    pos_middle = []
    pos_right = []

    for i in range(n):
        if i == 0:
            prev_left, prev_middle, prev_right = left0, middle0, right0
        else:
            prev_left, prev_middle, prev_right = (
                pos_left[i - 1],
                pos_middle[i - 1],
                pos_right[i - 1],
            )

        middle_at_notch = prev_middle == notches[1]
        right_at_notch = prev_right == notches[2]
        middle_steps = Or(right_at_notch, middle_at_notch)
        left_steps = middle_at_notch

        pos_right.append(_z3_wrap26(prev_right + 1))
        pos_middle.append(If(middle_steps, _z3_wrap26(prev_middle + 1), prev_middle))
        pos_left.append(If(left_steps, _z3_wrap26(prev_left + 1), prev_left))

    return pos_left, pos_middle, pos_right


def _encrypt_char_z3(
    plain_val: int,
    pos_left,
    pos_middle,
    pos_right,
    r_fwd: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
    r_inv: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
    reflector: tuple[int, ...],
    rings: tuple[int, int, int],
):
    x = plain_val

    idx_r = _z3_wrap26(x + pos_right - rings[2])
    x = _z3_wrap26(_z3_lookup(r_fwd[2], idx_r) - pos_right + rings[2])

    idx_m = _z3_wrap26(x + pos_middle - rings[1])
    x = _z3_wrap26(_z3_lookup(r_fwd[1], idx_m) - pos_middle + rings[1])

    idx_l = _z3_wrap26(x + pos_left - rings[0])
    x = _z3_wrap26(_z3_lookup(r_fwd[0], idx_l) - pos_left + rings[0])

    x = _z3_lookup(reflector, x)

    idx_l_b = _z3_wrap26(x + pos_left - rings[0])
    x = _z3_wrap26(_z3_lookup(r_inv[0], idx_l_b) - pos_left + rings[0])

    idx_m_b = _z3_wrap26(x + pos_middle - rings[1])
    x = _z3_wrap26(_z3_lookup(r_inv[1], idx_m_b) - pos_middle + rings[1])

    idx_r_b = _z3_wrap26(x + pos_right - rings[2])
    x = _z3_wrap26(_z3_lookup(r_inv[2], idx_r_b) - pos_right + rings[2])

    return x


def _build_plug_table(plugboard_pairs: list[tuple[str, str]] | None) -> list[int] | None:
    plug_table = list(range(26))
    if not plugboard_pairs:
        return plug_table

    for a, b in plugboard_pairs:
        ia = ord(a.upper()) - ord("A")
        ib = ord(b.upper()) - ord("A")
        if not (0 <= ia < 26 and 0 <= ib < 26):
            return None
        if ia != ib and (plug_table[ia] != ia or plug_table[ib] != ib):
            return None
        plug_table[ia] = ib
        plug_table[ib] = ia
    return plug_table


def _extract_plugboard_pairs(plug_table: list[int]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for i, mapped in enumerate(plug_table):
        if mapped > i:
            pairs.append((chr(i + ord("A")), chr(mapped + ord("A"))))
    return pairs


def _matches_candidate_with_machine(
    rotor_names: tuple[str, str, str],
    reflector_name: str,
    ring_settings: tuple[int, int, int],
    plugboard_pairs: list[tuple[str, str]] | None,
    candidate_positions: tuple[int, int, int],
    crib: str,
    target_cipher: str,
) -> bool:
    machine = EnigmaMachine(
        [
            Rotor.from_name(rotor_names[0], ring=ring_settings[0], position=candidate_positions[0]),
            Rotor.from_name(rotor_names[1], ring=ring_settings[1], position=candidate_positions[1]),
            Rotor.from_name(rotor_names[2], ring=ring_settings[2], position=candidate_positions[2]),
        ],
        Reflector.from_name(reflector_name),
        Plugboard(plugboard_pairs),
    )
    return machine.process(crib) == target_cipher


def _fallback_scan_positions(
    rotor_names: tuple[str, str, str],
    reflector_name: str,
    ring_settings: tuple[int, int, int],
    plugboard_pairs: list[tuple[str, str]] | None,
    crib: str,
    target_cipher: str,
) -> tuple[int, int, int] | None:
    for left_pos in range(26):
        for middle_pos in range(26):
            for right_pos in range(26):
                candidate = (left_pos, middle_pos, right_pos)
                if _matches_candidate_with_machine(
                    rotor_names,
                    reflector_name,
                    ring_settings,
                    plugboard_pairs,
                    candidate,
                    crib,
                    target_cipher,
                ):
                    return candidate
    return None


def crack_rotor_positions(
    ciphertext: str,
    crib: str,
    rotor_names: tuple[str, str, str] = ("I", "II", "III"),
    reflector_name: str = "B",
    plugboard_pairs: list[tuple[str, str]] | None = None,
    ring_settings: tuple[int, int, int] = (0, 0, 0),
    solver_timeout_ms: int | None = 50,
) -> tuple[int, int, int] | None:
    ciphertext_n = _normalize_alpha(ciphertext)
    crib_n = _normalize_alpha(crib)
    n = len(crib_n)
    if n == 0 or len(ciphertext_n) < n:
        return None

    target = ciphertext_n[:n]
    r_fwd = tuple(_wiring(name) for name in rotor_names)
    r_inv = tuple(_inv_wiring(name) for name in rotor_names)
    reflector = _reflector(reflector_name)
    notches = tuple(ord(ROTOR_NOTCHES[name]) - ord("A") for name in rotor_names)
    rings = tuple(ring_settings)

    plug_table = _build_plug_table(plugboard_pairs)
    if plug_table is None:
        return None

    crib_vals = [ord(ch) - ord("A") for ch in crib_n]
    target_vals = [ord(ch) - ord("A") for ch in target]

    solver = Solver()
    if solver_timeout_ms is not None:
        solver.set(timeout=solver_timeout_ms)

    left0 = Int("left0")
    middle0 = Int("middle0")
    right0 = Int("right0")
    solver.add(left0 >= 0, left0 < 26)
    solver.add(middle0 >= 0, middle0 < 26)
    solver.add(right0 >= 0, right0 < 26)

    pos_left, pos_middle, pos_right = _compute_positions(left0, middle0, right0, n, notches)

    for i in range(n):
        p_core = plug_table[crib_vals[i]]
        c_core = plug_table[target_vals[i]]
        enc = _encrypt_char_z3(
            p_core,
            pos_left[i],
            pos_middle[i],
            pos_right[i],
            r_fwd,
            r_inv,
            reflector,
            rings,
        )
        solver.add(enc == c_core)

    if solver.check() == sat:
        model = solver.model()
        return (
            model[left0].as_long(),
            model[middle0].as_long(),
            model[right0].as_long(),
        )

    return _fallback_scan_positions(
        rotor_names=rotor_names,
        reflector_name=reflector_name,
        ring_settings=rings,
        plugboard_pairs=plugboard_pairs,
        crib=crib_n,
        target_cipher=target,
    )


def crack_rotor_positions_and_plugboard(
    ciphertext: str,
    crib: str,
    rotor_names: tuple[str, str, str] = ("I", "II", "III"),
    reflector_name: str = "B",
    ring_settings: tuple[int, int, int] = (0, 0, 0),
    num_pairs: int | None = None,
    known_plugboard_pairs: list[tuple[str, str]] | None = None,
    solver_timeout_ms: int | None = 3000,
) -> tuple[tuple[int, int, int], list[tuple[str, str]]] | None:
    ciphertext_n = _normalize_alpha(ciphertext)
    crib_n = _normalize_alpha(crib)
    n = len(crib_n)
    if n == 0 or len(ciphertext_n) < n:
        return None
    if num_pairs is not None and not (0 <= num_pairs <= 13):
        return None

    target = ciphertext_n[:n]
    r_fwd = tuple(_wiring(name) for name in rotor_names)
    r_inv = tuple(_inv_wiring(name) for name in rotor_names)
    reflector = _reflector(reflector_name)
    notches = tuple(ord(ROTOR_NOTCHES[name]) - ord("A") for name in rotor_names)
    rings = tuple(ring_settings)

    crib_vals = [ord(ch) - ord("A") for ch in crib_n]
    target_vals = [ord(ch) - ord("A") for ch in target]

    solver = Solver()
    if solver_timeout_ms is not None:
        solver.set(timeout=solver_timeout_ms)

    left0 = Int("left0")
    middle0 = Int("middle0")
    right0 = Int("right0")
    solver.add(left0 >= 0, left0 < 26)
    solver.add(middle0 >= 0, middle0 < 26)
    solver.add(right0 >= 0, right0 < 26)
    pos_left, pos_middle, pos_right = _compute_positions(left0, middle0, right0, n, notches)

    plug_vars = [Int(f"plug_{i}") for i in range(26)]
    for var in plug_vars:
        solver.add(var >= 0, var < 26)
    solver.add(Distinct(*plug_vars))

    for i in range(26):
        solver.add(_z3_lookup(tuple(plug_vars), plug_vars[i]) == i)

    if known_plugboard_pairs:
        for a, b in known_plugboard_pairs:
            ia = ord(a.upper()) - ord("A")
            ib = ord(b.upper()) - ord("A")
            if not (0 <= ia < 26 and 0 <= ib < 26) or ia == ib:
                return None
            solver.add(plug_vars[ia] == ib)
            solver.add(plug_vars[ib] == ia)

    if num_pairs is not None:
        solver.add(Sum([If(plug_vars[i] == i, 0, 1) for i in range(26)]) == (2 * num_pairs))

    for i in range(n):
        p_core = plug_vars[crib_vals[i]]
        enc = _encrypt_char_z3(
            p_core,
            pos_left[i],
            pos_middle[i],
            pos_right[i],
            r_fwd,
            r_inv,
            reflector,
            rings,
        )
        solver.add(_z3_lookup(tuple(plug_vars), enc) == target_vals[i])

    if solver.check() != sat:
        return None

    model = solver.model()
    positions = (
        model[left0].as_long(),
        model[middle0].as_long(),
        model[right0].as_long(),
    )
    plug_table = [model[plug_vars[i]].as_long() for i in range(26)]
    return positions, _extract_plugboard_pairs(plug_table)
