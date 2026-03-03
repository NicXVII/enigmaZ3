"""
Z3-based and numeric crackers for the full Enigma machine.

Main APIs:
- crack_rotor_positions      : find rotor positions (known/empty plugboard)
- crack_with_plugboard       : find rotor positions + unknown plugboard pairs
- rank_rotor_configurations  : rank candidates with unknown rotor order/rings
- crack_full_configuration   : return best exact candidate from ranked search
"""

from __future__ import annotations

import itertools
import time
from dataclasses import dataclass
from functools import lru_cache

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


def _z3_mod26(expr):
    return expr % 26


def _compute_positions(L0, M0, R0, n: int, notches: tuple[int, int, int]):
    """
    Compute symbolic rotor positions after stepping for each character index.
    """
    pos_L = []
    pos_M = []
    pos_R = []

    for i in range(n):
        if i == 0:
            prev_L, prev_M, prev_R = L0, M0, R0
        else:
            prev_L, prev_M, prev_R = pos_L[i - 1], pos_M[i - 1], pos_R[i - 1]

        mid_at_notch = prev_M == notches[1]
        right_at_notch = prev_R == notches[2]
        mid_steps = Or(right_at_notch, mid_at_notch)
        left_steps = mid_at_notch

        pos_R.append(_z3_mod26(prev_R + 1))
        pos_M.append(If(mid_steps, _z3_mod26(prev_M + 1), prev_M))
        pos_L.append(If(left_steps, _z3_mod26(prev_L + 1), prev_L))

    return pos_L, pos_M, pos_R


def _encrypt_char_z3(
    p_val: int,
    pL,
    pM,
    pR,
    r_fwd: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
    r_inv: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
    refl: tuple[int, ...],
    rings,
):
    """Z3 expression for one Enigma core encryption (no plugboard)."""
    x = p_val

    idx_r = _z3_mod26(x + pR - rings[2])
    x = _z3_mod26(_z3_lookup(r_fwd[2], idx_r) - pR + rings[2])

    idx_m = _z3_mod26(x + pM - rings[1])
    x = _z3_mod26(_z3_lookup(r_fwd[1], idx_m) - pM + rings[1])

    idx_l = _z3_mod26(x + pL - rings[0])
    x = _z3_mod26(_z3_lookup(r_fwd[0], idx_l) - pL + rings[0])

    x = _z3_lookup(refl, x)

    idx_l_b = _z3_mod26(x + pL - rings[0])
    x = _z3_mod26(_z3_lookup(r_inv[0], idx_l_b) - pL + rings[0])

    idx_m_b = _z3_mod26(x + pM - rings[1])
    x = _z3_mod26(_z3_lookup(r_inv[1], idx_m_b) - pM + rings[1])

    idx_r_b = _z3_mod26(x + pR - rings[2])
    x = _z3_mod26(_z3_lookup(r_inv[2], idx_r_b) - pR + rings[2])

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
    refl: tuple[int, ...],
    rings: tuple[int, int, int],
) -> int:
    idx_r = (letter_val + pos_right - rings[2]) % 26
    x = (r_fwd[2][idx_r] - pos_right + rings[2]) % 26

    idx_m = (x + pos_middle - rings[1]) % 26
    x = (r_fwd[1][idx_m] - pos_middle + rings[1]) % 26

    idx_l = (x + pos_left - rings[0]) % 26
    x = (r_fwd[0][idx_l] - pos_left + rings[0]) % 26

    x = refl[x]

    idx_l_b = (x + pos_left - rings[0]) % 26
    x = (r_inv[0][idx_l_b] - pos_left + rings[0]) % 26

    idx_m_b = (x + pos_middle - rings[1]) % 26
    x = (r_inv[1][idx_m_b] - pos_middle + rings[1]) % 26

    idx_r_b = (x + pos_right - rings[2]) % 26
    x = (r_inv[2][idx_r_b] - pos_right + rings[2]) % 26
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


def _iter_position_candidates(limit: int | None = None):
    total = 26 * 26 * 26
    if limit is None or limit >= total:
        for value in range(total):
            yield value // 676, (value // 26) % 26, value % 26
        return

    # Deterministic pseudo-random walk, helps ranking with small budgets.
    step = 7919
    for i in range(limit):
        value = (i * step) % total
        yield value // 676, (value // 26) % 26, value % 26


def _count_mismatches_candidate(
    left0: int,
    middle0: int,
    right0: int,
    crib_vals: list[int],
    cipher_vals: list[int],
    plug_table: list[int],
    r_fwd: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
    r_inv: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
    refl: tuple[int, ...],
    rings: tuple[int, int, int],
    notches: tuple[int, int, int],
    max_mismatches: int | None = None,
) -> int:
    n = len(crib_vals)
    pos_left, pos_middle, pos_right = _compute_positions_numeric(
        left0, middle0, right0, n, notches
    )

    mismatches = 0
    for i in range(n):
        p_core = plug_table[crib_vals[i]]
        c_core = plug_table[cipher_vals[i]]
        out = _encrypt_core_numeric(
            p_core,
            pos_left[i],
            pos_middle[i],
            pos_right[i],
            r_fwd,
            r_inv,
            refl,
            rings,
        )
        if out != c_core:
            mismatches += 1
            if max_mismatches is not None and mismatches > max_mismatches:
                return mismatches
    return mismatches


def _matches_candidate_numeric(
    left0: int,
    middle0: int,
    right0: int,
    crib_vals: list[int],
    cipher_vals: list[int],
    plug_table: list[int],
    r_fwd: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
    r_inv: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
    refl: tuple[int, ...],
    rings: tuple[int, int, int],
    notches: tuple[int, int, int],
) -> bool:
    return (
        _count_mismatches_candidate(
            left0,
            middle0,
            right0,
            crib_vals,
            cipher_vals,
            plug_table,
            r_fwd,
            r_inv,
            refl,
            rings,
            notches,
            max_mismatches=0,
        )
        == 0
    )


# ---------------------------------------------------------------------------
# Level 1: Crack rotor positions only (no plugboard or known plugboard)
# ---------------------------------------------------------------------------


def crack_rotor_positions(
    ciphertext: str,
    crib: str,
    rotor_names: tuple[str, str, str] = ("I", "II", "III"),
    reflector_name: str = "B",
    plugboard_pairs: list[tuple[str, str]] | None = None,
    ring_settings: tuple[int, int, int] = (0, 0, 0),
    solver_timeout_ms: int | None = 50,
    allow_numeric_fallback: bool = True,
    numeric_search_limit: int | None = None,
) -> tuple[int, int, int] | None:
    """
    Find initial positions of 3 rotors given a crib.

    `allow_numeric_fallback=False` can be used for fast, timeout-bounded probing.
    """
    ciphertext_n = _normalize_alpha(ciphertext)
    crib_n = _normalize_alpha(crib)
    n = len(crib_n)
    if n == 0 or len(ciphertext_n) < n:
        return None

    target = ciphertext_n[:n]
    r_fwd = tuple(_wiring(r) for r in rotor_names)
    r_inv = tuple(_inv_wiring(r) for r in rotor_names)
    refl = _reflector(reflector_name)
    notches = tuple(ord(ROTOR_NOTCHES[r]) - ord("A") for r in rotor_names)
    rings = tuple(ring_settings)

    plug_table = _build_plug_table(plugboard_pairs)
    if plug_table is None:
        return None

    crib_vals = [ord(ch) - ord("A") for ch in crib_n]
    target_vals = [ord(ch) - ord("A") for ch in target]

    s = Solver()
    if solver_timeout_ms is not None:
        s.set(timeout=solver_timeout_ms)

    left0 = Int("left0")
    middle0 = Int("middle0")
    right0 = Int("right0")
    s.add(left0 >= 0, left0 < 26)
    s.add(middle0 >= 0, middle0 < 26)
    s.add(right0 >= 0, right0 < 26)

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
            refl,
            rings,
        )
        s.add(enc == c_core)

    check_res = s.check()
    if check_res == sat:
        model = s.model()
        candidate = (
            model[left0].as_long(),
            model[middle0].as_long(),
            model[right0].as_long(),
        )
        if _matches_candidate_numeric(
            candidate[0],
            candidate[1],
            candidate[2],
            crib_vals,
            target_vals,
            plug_table,
            r_fwd,
            r_inv,
            refl,
            rings,
            notches,
        ):
            return candidate

    if not allow_numeric_fallback:
        return None

    for left_pos, middle_pos, right_pos in _iter_position_candidates(numeric_search_limit):
        if _matches_candidate_numeric(
            left_pos,
            middle_pos,
            right_pos,
            crib_vals,
            target_vals,
            plug_table,
            r_fwd,
            r_inv,
            refl,
            rings,
            notches,
        ):
            return (left_pos, middle_pos, right_pos)
    return None


# ---------------------------------------------------------------------------
# Level 2/3: Crack rotor positions AND plugboard
# ---------------------------------------------------------------------------


def _assign_plug_pair(
    mapping: dict[int, int],
    a: int,
    b: int,
    pairs_used: int,
    max_pairs: int,
) -> int | None:
    map_a = mapping.get(a)
    map_b = mapping.get(b)

    if map_a is not None and map_a != b:
        return None
    if map_b is not None and map_b != a:
        return None
    if map_a == b and map_b == a:
        return pairs_used

    if a != b:
        if (map_a is None) != (map_b is None):
            return None
        if map_a is None and map_b is None:
            pairs_used += 1
            if pairs_used > max_pairs:
                return None

    mapping[a] = b
    mapping[b] = a
    return pairs_used


def _x_candidates(
    mapping: dict[int, int],
    pairs_used: int,
    max_pairs: int,
    plain_val: int,
    cipher_val: int,
    core_inv: list[int],
) -> list[int]:
    if plain_val in mapping:
        return [mapping[plain_val]]

    if pairs_used >= max_pairs:
        return [plain_val]

    if cipher_val in mapping:
        return [core_inv[mapping[cipher_val]]]

    return [plain_val] + [x for x in range(26) if x != plain_val]


def _solve_plugboard_constraints(
    constraints: list[tuple[int, int, list[int], list[int]]],
    max_pairs: int,
    deadline: float | None,
):
    timeout_marker = object()
    n = len(constraints)

    def choose_index(remaining: list[int], mapping: dict[int, int], pairs_used: int) -> int:
        best = remaining[0]
        best_size = 27
        for idx in remaining:
            p, c, _, _ = constraints[idx]
            if p in mapping or pairs_used >= max_pairs or c in mapping:
                size = 1
            else:
                size = 26
            if size < best_size:
                best = idx
                best_size = size
                if size == 1:
                    break
        return best

    def backtrack(
        remaining: list[int],
        mapping: dict[int, int],
        pairs_used: int,
    ):
        if deadline is not None and time.perf_counter() > deadline:
            return timeout_marker

        if not remaining:
            return mapping

        idx = choose_index(remaining, mapping, pairs_used)
        p, c, core_table, core_inv = constraints[idx]
        next_remaining = [j for j in remaining if j != idx]

        for x in _x_candidates(mapping, pairs_used, max_pairs, p, c, core_inv):
            mapping_next = dict(mapping)
            pairs_after_plain = _assign_plug_pair(
                mapping_next,
                p,
                x,
                pairs_used,
                max_pairs,
            )
            if pairs_after_plain is None:
                continue

            y = core_table[x]
            pairs_after_cipher = _assign_plug_pair(
                mapping_next,
                y,
                c,
                pairs_after_plain,
                max_pairs,
            )
            if pairs_after_cipher is None:
                continue

            result = backtrack(next_remaining, mapping_next, pairs_after_cipher)
            if result is timeout_marker:
                return timeout_marker
            if result is not None:
                return result
        return None

    return backtrack(list(range(n)), {}, 0), timeout_marker


def crack_with_plugboard(
    ciphertext: str,
    crib: str,
    rotor_names: tuple[str, str, str] = ("I", "II", "III"),
    reflector_name: str = "B",
    num_plugboard_pairs: int = 3,
    ring_settings: tuple[int, int, int] = (0, 0, 0),
    solver_timeout_ms: int | None = 10_000,
) -> tuple[tuple[int, int, int], list[tuple[str, str]]] | None:
    """
    Find rotor positions AND plugboard pairs via rotor brute-force + constrained backtracking.
    """
    ciphertext_n = _normalize_alpha(ciphertext)
    crib_n = _normalize_alpha(crib)
    n = len(crib_n)
    if n == 0 or len(ciphertext_n) < n:
        return None
    if num_plugboard_pairs < 0 or num_plugboard_pairs > 13:
        return None

    for i in range(n):
        if crib_n[i] == ciphertext_n[i]:
            return None

    r_fwd = tuple(_wiring(r) for r in rotor_names)
    r_inv = tuple(_inv_wiring(r) for r in rotor_names)
    refl = _reflector(reflector_name)
    notches = tuple(ord(ROTOR_NOTCHES[r]) - ord("A") for r in rotor_names)
    rings = tuple(ring_settings)
    crib_vals = [ord(ch) - ord("A") for ch in crib_n]
    cipher_vals = [ord(ch) - ord("A") for ch in ciphertext_n[:n]]

    deadline = None
    if solver_timeout_ms is not None:
        deadline = time.perf_counter() + (solver_timeout_ms / 1000.0)

    # Cache core tables by stepped rotor state; substantial speed-up when
    # exploring many candidates.
    core_table_cache: dict[tuple[int, int, int], tuple[list[int], list[int]]] = {}

    for left0 in range(26):
        for middle0 in range(26):
            for right0 in range(26):
                if deadline is not None and time.perf_counter() > deadline:
                    return None

                pos_left, pos_middle, pos_right = _compute_positions_numeric(
                    left0, middle0, right0, n, notches
                )

                constraints: list[tuple[int, int, list[int], list[int]]] = []
                for i in range(n):
                    state = (pos_left[i], pos_middle[i], pos_right[i])
                    cached = core_table_cache.get(state)
                    if cached is None:
                        core_table = [
                            _encrypt_core_numeric(
                                x,
                                state[0],
                                state[1],
                                state[2],
                                r_fwd,
                                r_inv,
                                refl,
                                rings,
                            )
                            for x in range(26)
                        ]
                        core_inv = [0] * 26
                        for x, y in enumerate(core_table):
                            core_inv[y] = x
                        core_table_cache[state] = (core_table, core_inv)
                    else:
                        core_table, core_inv = cached

                    constraints.append((crib_vals[i], cipher_vals[i], core_table, core_inv))

                maybe_mapping, timeout_marker = _solve_plugboard_constraints(
                    constraints,
                    num_plugboard_pairs,
                    deadline,
                )
                if maybe_mapping is timeout_marker:
                    return None
                if maybe_mapping is None:
                    continue

                pairs = []
                for i in range(26):
                    j = maybe_mapping.get(i, i)
                    if j > i:
                        pairs.append((chr(i + ord("A")), chr(j + ord("A"))))
                return (left0, middle0, right0), pairs
    return None


# ---------------------------------------------------------------------------
# Complete search: unknown rotor order and unknown ring settings
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CrackCandidate:
    rotor_names: tuple[str, str, str]
    ring_settings: tuple[int, int, int]
    positions: tuple[int, int, int] | None
    mismatches: int
    matched_chars: int
    method: str
    elapsed_ms: float


def _iter_rotor_orders(
    rotor_pool: tuple[str, ...],
    search_rotor_order: bool,
):
    if search_rotor_order:
        for order in itertools.permutations(rotor_pool, 3):
            yield order
    else:
        if len(rotor_pool) != 3:
            raise ValueError("rotor_pool must contain exactly 3 rotors when search_rotor_order=False")
        yield (rotor_pool[0], rotor_pool[1], rotor_pool[2])


def _iter_ring_settings(
    search_ring_settings: bool,
    ring_candidates: list[tuple[int, int, int]] | None,
):
    if ring_candidates is not None:
        seen: set[tuple[int, int, int]] = set()
        for ring in ring_candidates:
            ring_t = tuple(int(v) % 26 for v in ring)
            if ring_t not in seen:
                seen.add(ring_t)
                yield ring_t
        return

    if search_ring_settings:
        for ring in itertools.product(range(26), repeat=3):
            yield ring
    else:
        yield (0, 0, 0)


def _best_partial_for_config(
    crib_vals: list[int],
    cipher_vals: list[int],
    plug_table: list[int],
    r_fwd: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
    r_inv: tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]],
    refl: tuple[int, ...],
    rings: tuple[int, int, int],
    notches: tuple[int, int, int],
    position_budget: int,
    deadline: float | None,
) -> tuple[tuple[int, int, int] | None, int]:
    best_pos: tuple[int, int, int] | None = None
    best_mismatches = len(crib_vals) + 1

    for left0, middle0, right0 in _iter_position_candidates(position_budget):
        if deadline is not None and time.perf_counter() > deadline:
            break

        mismatches = _count_mismatches_candidate(
            left0,
            middle0,
            right0,
            crib_vals,
            cipher_vals,
            plug_table,
            r_fwd,
            r_inv,
            refl,
            rings,
            notches,
            max_mismatches=best_mismatches - 1,
        )
        if mismatches < best_mismatches:
            best_mismatches = mismatches
            best_pos = (left0, middle0, right0)
            if mismatches == 0:
                break

    if best_pos is None:
        return None, len(crib_vals)
    return best_pos, best_mismatches


def rank_rotor_configurations(
    ciphertext: str,
    crib: str,
    rotor_pool: tuple[str, ...] = ("I", "II", "III"),
    reflector_name: str = "B",
    plugboard_pairs: list[tuple[str, str]] | None = None,
    search_rotor_order: bool = True,
    search_ring_settings: bool = False,
    ring_candidates: list[tuple[int, int, int]] | None = None,
    top_k: int = 5,
    global_timeout_ms: int = 10_000,
    solver_timeout_ms_per_config: int = 80,
    heuristic_position_budget: int = 700,
    exact_numeric_fallback_limit: int | None = None,
) -> list[CrackCandidate]:
    """
    Rank rotor/ring/position candidates.

    - Exact candidates are found with timeout-bounded SMT (`mismatches=0`).
    - If SMT times out/does not solve, a deterministic heuristic search provides
      approximate candidates ranked by mismatch count.
    """
    if len(rotor_pool) < 3:
        raise ValueError("rotor_pool must include at least 3 rotors")
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    ciphertext_n = _normalize_alpha(ciphertext)
    crib_n = _normalize_alpha(crib)
    n = len(crib_n)
    if n == 0 or len(ciphertext_n) < n:
        return []

    plug_table = _build_plug_table(plugboard_pairs)
    if plug_table is None:
        return []

    crib_vals = [ord(ch) - ord("A") for ch in crib_n]
    target_vals = [ord(ch) - ord("A") for ch in ciphertext_n[:n]]

    deadline = time.perf_counter() + (global_timeout_ms / 1000.0)
    rotor_orders = list(_iter_rotor_orders(rotor_pool, search_rotor_order))

    # In manageable search spaces, run an exact numeric fallback when SMT
    # cannot return a candidate quickly.
    numeric_fallback_limit = exact_numeric_fallback_limit
    if numeric_fallback_limit is None:
        if ring_candidates is not None and len(ring_candidates) <= 8 and len(rotor_orders) <= 24:
            numeric_fallback_limit = 26 * 26 * 26
        else:
            numeric_fallback_limit = 0

    ranked: list[CrackCandidate] = []

    for rotor_names in rotor_orders:
        for rings in _iter_ring_settings(search_ring_settings, ring_candidates):
            if time.perf_counter() > deadline:
                ranked.sort(key=lambda c: (c.mismatches, -c.matched_chars, c.elapsed_ms))
                return ranked[:top_k]

            started = time.perf_counter()

            candidate = crack_rotor_positions(
                ciphertext=ciphertext_n,
                crib=crib_n,
                rotor_names=rotor_names,
                reflector_name=reflector_name,
                plugboard_pairs=plugboard_pairs,
                ring_settings=rings,
                solver_timeout_ms=solver_timeout_ms_per_config,
                allow_numeric_fallback=False,
            )

            if candidate is not None:
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                ranked.append(
                    CrackCandidate(
                        rotor_names=rotor_names,
                        ring_settings=rings,
                        positions=candidate,
                        mismatches=0,
                        matched_chars=n,
                        method="smt",
                        elapsed_ms=elapsed_ms,
                    )
                )
            else:
                if numeric_fallback_limit:
                    exact_numeric = crack_rotor_positions(
                        ciphertext=ciphertext_n,
                        crib=crib_n,
                        rotor_names=rotor_names,
                        reflector_name=reflector_name,
                        plugboard_pairs=plugboard_pairs,
                        ring_settings=rings,
                        solver_timeout_ms=solver_timeout_ms_per_config,
                        allow_numeric_fallback=True,
                        numeric_search_limit=numeric_fallback_limit,
                    )
                    if exact_numeric is not None:
                        elapsed_ms = (time.perf_counter() - started) * 1000.0
                        ranked.append(
                            CrackCandidate(
                                rotor_names=rotor_names,
                                ring_settings=rings,
                                positions=exact_numeric,
                                mismatches=0,
                                matched_chars=n,
                                method="numeric_exact",
                                elapsed_ms=elapsed_ms,
                            )
                        )
                        if len(ranked) > top_k * 6:
                            ranked.sort(
                                key=lambda c: (c.mismatches, -c.matched_chars, c.elapsed_ms)
                            )
                            ranked = ranked[: top_k * 4]
                        continue

                partial_deadline = min(
                    deadline,
                    time.perf_counter() + (solver_timeout_ms_per_config / 1000.0),
                )
                r_fwd = tuple(_wiring(r) for r in rotor_names)
                r_inv = tuple(_inv_wiring(r) for r in rotor_names)
                refl = _reflector(reflector_name)
                notches = tuple(ord(ROTOR_NOTCHES[r]) - ord("A") for r in rotor_names)

                best_pos, mismatches = _best_partial_for_config(
                    crib_vals,
                    target_vals,
                    plug_table,
                    r_fwd,
                    r_inv,
                    refl,
                    rings,
                    notches,
                    heuristic_position_budget,
                    partial_deadline,
                )
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                ranked.append(
                    CrackCandidate(
                        rotor_names=rotor_names,
                        ring_settings=rings,
                        positions=best_pos,
                        mismatches=mismatches,
                        matched_chars=n - mismatches,
                        method="heuristic",
                        elapsed_ms=elapsed_ms,
                    )
                )

            # Keep list bounded while preserving best candidates.
            if len(ranked) > top_k * 6:
                ranked.sort(key=lambda c: (c.mismatches, -c.matched_chars, c.elapsed_ms))
                ranked = ranked[: top_k * 4]

    ranked.sort(key=lambda c: (c.mismatches, -c.matched_chars, c.elapsed_ms))
    return ranked[:top_k]


def crack_full_configuration(
    ciphertext: str,
    crib: str,
    rotor_pool: tuple[str, ...] = ("I", "II", "III"),
    reflector_name: str = "B",
    plugboard_pairs: list[tuple[str, str]] | None = None,
    search_rotor_order: bool = True,
    search_ring_settings: bool = True,
    ring_candidates: list[tuple[int, int, int]] | None = None,
    top_k: int = 5,
    global_timeout_ms: int = 12_000,
    solver_timeout_ms_per_config: int = 80,
    heuristic_position_budget: int = 700,
) -> CrackCandidate | None:
    """
    Return the best exact candidate (if any) while supporting unknown order/rings.
    """
    ranking_window = max(top_k * 8, 24)
    ranked = rank_rotor_configurations(
        ciphertext=ciphertext,
        crib=crib,
        rotor_pool=rotor_pool,
        reflector_name=reflector_name,
        plugboard_pairs=plugboard_pairs,
        search_rotor_order=search_rotor_order,
        search_ring_settings=search_ring_settings,
        ring_candidates=ring_candidates,
        top_k=ranking_window,
        global_timeout_ms=global_timeout_ms,
        solver_timeout_ms_per_config=solver_timeout_ms_per_config,
        heuristic_position_budget=heuristic_position_budget,
        exact_numeric_fallback_limit=0,
    )
    for candidate in ranked:
        if candidate.mismatches == 0 and candidate.positions is not None:
            return candidate

    # Second pass: exact numeric refinement on best-ranked configurations.
    started = time.perf_counter()
    deadline = started + (global_timeout_ms / 1000.0)
    for candidate in ranked:
        if time.perf_counter() > deadline:
            break
        exact_positions = crack_rotor_positions(
            ciphertext=ciphertext,
            crib=crib,
            rotor_names=candidate.rotor_names,
            reflector_name=reflector_name,
            plugboard_pairs=plugboard_pairs,
            ring_settings=candidate.ring_settings,
            solver_timeout_ms=solver_timeout_ms_per_config,
            allow_numeric_fallback=True,
            numeric_search_limit=26 * 26 * 26,
        )
        if exact_positions is not None:
            return CrackCandidate(
                rotor_names=candidate.rotor_names,
                ring_settings=candidate.ring_settings,
                positions=exact_positions,
                mismatches=0,
                matched_chars=len(_normalize_alpha(crib)),
                method="numeric_refine",
                elapsed_ms=(time.perf_counter() - started) * 1000.0,
            )
    return None
