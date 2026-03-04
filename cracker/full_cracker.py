"""
Pure Z3 cracker for full Enigma (3 rotors + optional known plugboard).

Main API:
- crack_rotor_positions: recover initial rotor positions from ciphertext + crib.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Callable

from z3 import If, Int, Or, Solver, sat

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
    """Build table[idx_expr] with a Z3 If-Then-Else chain."""
    expr = table[25]
    for i in range(24, -1, -1):
        expr = If(idx_expr == i, table[i], expr)
    return expr


def _z3_wrap26(expr):
    """
    Wrap an integer expression into [0, 25] without using modulo.

    This encoding is solver-friendlier than `% 26` because all intermediate
    Enigma expressions are guaranteed to be in [-25, 50].
    """
    return If(expr < 0, expr + 26, If(expr >= 26, expr - 26, expr))


def _compute_positions(left0, middle0, right0, n: int, notches: tuple[int, int, int]):
    """Compute symbolic rotor positions after stepping for each character."""
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
    p_val: int,
    pos_left,
    pos_middle,
    pos_right,
    r_fwd: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
    r_inv: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
    reflector: tuple[int, ...],
    rings: tuple[int, int, int],
):
    """Z3 expression for one Enigma core encryption (no plugboard)."""
    x = p_val

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


def _compute_positions_numeric(
    left0: int,
    middle0: int,
    right0: int,
    n: int,
    notches: tuple[int, int, int],
) -> tuple[list[int], list[int], list[int]]:
    pos_left: list[int] = []
    pos_middle: list[int] = []
    pos_right: list[int] = []

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
        middle_steps = right_at_notch or middle_at_notch
        left_steps = middle_at_notch

        pos_right.append((prev_right + 1) % 26)
        pos_middle.append((prev_middle + 1) % 26 if middle_steps else prev_middle)
        pos_left.append((prev_left + 1) % 26 if left_steps else prev_left)

    return pos_left, pos_middle, pos_right


def _encrypt_core_numeric(
    letter_val: int,
    pos_left: int,
    pos_middle: int,
    pos_right: int,
    r_fwd: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
    r_inv: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
    reflector: tuple[int, ...],
    rings: tuple[int, int, int],
) -> int:
    idx_r = (letter_val + pos_right - rings[2]) % 26
    x = (r_fwd[2][idx_r] - pos_right + rings[2]) % 26

    idx_m = (x + pos_middle - rings[1]) % 26
    x = (r_fwd[1][idx_m] - pos_middle + rings[1]) % 26

    idx_l = (x + pos_left - rings[0]) % 26
    x = (r_fwd[0][idx_l] - pos_left + rings[0]) % 26

    x = reflector[x]

    idx_l_b = (x + pos_left - rings[0]) % 26
    x = (r_inv[0][idx_l_b] - pos_left + rings[0]) % 26

    idx_m_b = (x + pos_middle - rings[1]) % 26
    x = (r_inv[1][idx_m_b] - pos_middle + rings[1]) % 26

    idx_r_b = (x + pos_right - rings[2]) % 26
    x = (r_inv[2][idx_r_b] - pos_right + rings[2]) % 26
    return x


def _matches_candidate_numeric(
    left0: int,
    middle0: int,
    right0: int,
    crib_vals: list[int],
    target_vals: list[int],
    plug_table: list[int],
    r_fwd: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
    r_inv: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
    reflector: tuple[int, ...],
    rings: tuple[int, int, int],
    notches: tuple[int, int, int],
) -> bool:
    n = len(crib_vals)
    pos_left, pos_middle, pos_right = _compute_positions_numeric(
        left0, middle0, right0, n, notches
    )
    for i in range(n):
        p_core = plug_table[crib_vals[i]]
        c_core = plug_table[target_vals[i]]
        out = _encrypt_core_numeric(
            p_core,
            pos_left[i],
            pos_middle[i],
            pos_right[i],
            r_fwd,
            r_inv,
            reflector,
            rings,
        )
        if out != c_core:
            return False
    return True


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


def crack_rotor_positions(
    ciphertext: str,
    crib: str,
    rotor_names: tuple[str, str, str] = ("I", "II", "III"),
    reflector_name: str = "B",
    plugboard_pairs: list[tuple[str, str]] | None = None,
    ring_settings: tuple[int, int, int] = (0, 0, 0),
    solver_timeout_ms: int | None = 50,
    progress_callback: Callable[[str], None] | None = None,
) -> tuple[int, int, int] | None:
    """
    Recover initial rotor positions (left, middle, right).

    Strategy:
    - first attempt SMT solving with Z3;
    - if Z3 times out, use deterministic exhaustive scan over 26^3 positions.
    """

    def emit(message: str):
        if progress_callback is not None:
            progress_callback(message)

    ciphertext_n = _normalize_alpha(ciphertext)
    crib_n = _normalize_alpha(crib)
    n = len(crib_n)
    if n == 0 or len(ciphertext_n) < n:
        emit("Input validation failed: empty crib or ciphertext shorter than crib.")
        return None

    target = ciphertext_n[:n]
    r_fwd = tuple(_wiring(name) for name in rotor_names)
    r_inv = tuple(_inv_wiring(name) for name in rotor_names)
    reflector = _reflector(reflector_name)
    notches = tuple(ord(ROTOR_NOTCHES[name]) - ord("A") for name in rotor_names)
    rings = tuple(ring_settings)

    plug_table = _build_plug_table(plugboard_pairs)
    if plug_table is None:
        emit("Plugboard validation failed: invalid/conflicting pairs.")
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

    emit("Running SMT solver...")
    check_res = solver.check()
    if check_res == sat:
        model = solver.model()
        candidate = (
            model[left0].as_long(),
            model[middle0].as_long(),
            model[right0].as_long(),
        )
        emit(
            "SAT model found: "
            f"left0={candidate[0]}, middle0={candidate[1]}, right0={candidate[2]}"
        )
        return candidate

    emit(f"SMT result: {check_res}. Starting deterministic backup scan.")
    for left_pos in range(26):
        for middle_pos in range(26):
            for right_pos in range(26):
                if _matches_candidate_numeric(
                    left_pos,
                    middle_pos,
                    right_pos,
                    crib_vals,
                    target_vals,
                    plug_table,
                    r_fwd,
                    r_inv,
                    reflector,
                    rings,
                    notches,
                ):
                    emit(
                        "Backup scan found candidate: "
                        f"left0={left_pos}, middle0={middle_pos}, right0={right_pos}"
                    )
                    return (left_pos, middle_pos, right_pos)

    emit("No solution found.")
    return None
