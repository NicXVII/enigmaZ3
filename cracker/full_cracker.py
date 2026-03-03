"""
Z3-based cracker for the full Enigma machine (3 rotors + reflector + plugboard).

Three incremental difficulty levels:
1. crack_rotor_positions   — find the 3 rotor start positions (plugboard known / empty)
2. crack_with_plugboard    — find rotor positions + plugboard pairs

The approach: we model each character's encryption path entirely in Z3 using
lookup tables encoded as If-Then-Else chains, combined with modular arithmetic.
"""

import time

from z3 import (
    Int, Solver, Or, If, sat,
)

from enigma.rotor import ROTOR_WIRINGS, ROTOR_NOTCHES
from enigma.reflector import REFLECTOR_WIRINGS


def _wiring(name: str) -> list[int]:
    return [ord(c) - ord("A") for c in ROTOR_WIRINGS[name]]


def _inv_wiring(name: str) -> list[int]:
    fwd = _wiring(name)
    inv = [0] * 26
    for i, v in enumerate(fwd):
        inv[v] = i
    return inv


def _reflector(name: str) -> list[int]:
    return [ord(c) - ord("A") for c in REFLECTOR_WIRINGS[name]]


def _z3_lookup(table: list[int], idx_expr, name: str = "lut"):
    """
    Build a Z3 expression that looks up table[idx_expr] using a chain of If-Then-Else.
    idx_expr should be a Z3 Int expression that evaluates to 0..25.
    """
    expr = table[25]  # default (last element)
    for i in range(24, -1, -1):
        expr = If(idx_expr == i, table[i], expr)
    return expr


def _z3_mod26(expr):
    """Return expr % 26 in Z3 (always non-negative)."""
    return expr % 26


def _compute_positions(L0, M0, R0, n, notches):
    """
    Compute rotor positions for n steps as Z3 expressions.
    Returns lists of Z3 expressions (pos_L, pos_M, pos_R) each of length n.
    Positions are AFTER stepping (ready for encryption).
    """
    pos_L = []
    pos_M = []
    pos_R = []

    for i in range(n):
        if i == 0:
            prev_L, prev_M, prev_R = L0, M0, R0
        else:
            prev_L, prev_M, prev_R = pos_L[i - 1], pos_M[i - 1], pos_R[i - 1]

        # Double-stepping logic
        mid_at_notch = (prev_M == notches[1])
        right_at_notch = (prev_R == notches[2])
        mid_steps = Or(right_at_notch, mid_at_notch)
        left_steps = mid_at_notch

        pos_R.append(_z3_mod26(prev_R + 1))
        pos_M.append(If(mid_steps, _z3_mod26(prev_M + 1), prev_M))
        pos_L.append(If(left_steps, _z3_mod26(prev_L + 1), prev_L))

    return pos_L, pos_M, pos_R


def _encrypt_char_z3(p_val, pL, pM, pR, r_fwd, r_inv, refl, rings,
                     plug_in_fn=None, plug_out_fn=None, suffix=""):
    """
    Build a Z3 expression for encrypting plaintext value p_val through
    the 3-rotor Enigma with given symbolic positions.

    Parameters
    ----------
    p_val : int
        Plaintext letter (0-25).
    pL, pM, pR : Z3 expressions
        Rotor positions (after stepping).
    r_fwd, r_inv : list[list[int]]
        Forward and inverse wiring tables [left, mid, right].
    refl : list[int]
        Reflector wiring.
    rings : list[int]
        Ring settings [left, mid, right].
    plug_in_fn, plug_out_fn : callable or None
        Functions that take a Z3 expression and return plugboard-swapped expression.
        If None, identity is used.
    suffix : str
        Name suffix for Z3 expressions (for debugging).

    Returns
    -------
    Z3 expression representing the encrypted letter (0-25).
    """
    # Plugboard in
    if plug_in_fn is not None:
        x = plug_in_fn(p_val)
    else:
        x = p_val  # integer constant, no plugboard

    # Forward through right rotor
    idx_r = _z3_mod26(x + pR - rings[2])
    x = _z3_mod26(_z3_lookup(r_fwd[2], idx_r) - pR + rings[2])

    # Forward through middle rotor
    idx_m = _z3_mod26(x + pM - rings[1])
    x = _z3_mod26(_z3_lookup(r_fwd[1], idx_m) - pM + rings[1])

    # Forward through left rotor
    idx_l = _z3_mod26(x + pL - rings[0])
    x = _z3_mod26(_z3_lookup(r_fwd[0], idx_l) - pL + rings[0])

    # Reflector
    x = _z3_lookup(refl, x)

    # Backward through left rotor
    idx_l_b = _z3_mod26(x + pL - rings[0])
    x = _z3_mod26(_z3_lookup(r_inv[0], idx_l_b) - pL + rings[0])

    # Backward through middle rotor
    idx_m_b = _z3_mod26(x + pM - rings[1])
    x = _z3_mod26(_z3_lookup(r_inv[1], idx_m_b) - pM + rings[1])

    # Backward through right rotor
    idx_r_b = _z3_mod26(x + pR - rings[2])
    x = _z3_mod26(_z3_lookup(r_inv[2], idx_r_b) - pR + rings[2])

    # Plugboard out
    if plug_out_fn is not None:
        x = plug_out_fn(x)

    return x


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
) -> tuple[int, int, int] | None:
    """
    Find the initial positions of 3 rotors given a crib.

    Parameters
    ----------
    ciphertext, crib : str
    rotor_names : tuple of 3 rotor names (left, middle, right)
    reflector_name : str
    plugboard_pairs : optional plugboard pairs (if known)
    ring_settings : tuple of 3 ring settings

    Returns
    -------
    tuple (left_pos, mid_pos, right_pos) or None
    """
    ciphertext = "".join(ch for ch in ciphertext.upper() if ch.isalpha())
    crib = "".join(ch for ch in crib.upper() if ch.isalpha())
    n = len(crib)
    if n == 0 or len(ciphertext) < n:
        return None

    target = ciphertext[:n]
    r_fwd = [_wiring(r) for r in rotor_names]
    r_inv = [_inv_wiring(r) for r in rotor_names]
    refl = _reflector(reflector_name)
    notches = [ord(ROTOR_NOTCHES[r]) - ord("A") for r in rotor_names]
    rings = list(ring_settings)

    plug_table = list(range(26))
    if plugboard_pairs:
        for a, b in plugboard_pairs:
            ia = ord(a.upper()) - ord("A")
            ib = ord(b.upper()) - ord("A")
            if not (0 <= ia < 26 and 0 <= ib < 26):
                return None
            plug_table[ia] = ib
            plug_table[ib] = ia

    crib_vals = [ord(ch) - ord("A") for ch in crib]
    target_vals = [ord(ch) - ord("A") for ch in target]

    s = Solver()
    left0 = Int("left0")
    middle0 = Int("middle0")
    right0 = Int("right0")
    s.add(left0 >= 0, left0 < 26)
    s.add(middle0 >= 0, middle0 < 26)
    s.add(right0 >= 0, right0 < 26)

    pos_left, pos_middle, pos_right = _compute_positions(
        left0,
        middle0,
        right0,
        n,
        notches,
    )

    for i in range(n):
        # With known plugboard P, c = P(core(P(p))) so we constrain:
        # core(P(p)) == P(c), where core is rotors+reflector only.
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

    if s.check() == sat:
        m = s.model()
        return (
            m[left0].as_long(),
            m[middle0].as_long(),
            m[right0].as_long(),
        )
    return None


# ---------------------------------------------------------------------------
# Level 2/3: Crack rotor positions AND plugboard
# ---------------------------------------------------------------------------

def _compute_positions_numeric(
    left0: int,
    middle0: int,
    right0: int,
    n: int,
    notches: list[int],
) -> tuple[list[int], list[int], list[int]]:
    """
    Numeric version of rotor stepping (same logic as _compute_positions).
    Returns positions after stepping for each character index.
    """
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
    r_fwd: list[list[int]],
    r_inv: list[list[int]],
    refl: list[int],
    rings: list[int],
) -> int:
    """
    Encrypt one letter through rotors+reflector only (no plugboard), numerically.
    """
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


def _assign_plug_pair(
    mapping: dict[int, int],
    a: int,
    b: int,
    pairs_used: int,
    max_pairs: int,
) -> int | None:
    """
    Add/validate plugboard constraint P(a)=b and P(b)=a.
    Returns updated pairs_used, or None on contradiction.
    """
    map_a = mapping.get(a)
    map_b = mapping.get(b)

    if map_a is not None and map_a != b:
        return None
    if map_b is not None and map_b != a:
        return None
    if map_a == b and map_b == a:
        return pairs_used

    if a != b:
        # This search keeps assignments symmetric; a half-known non-trivial mapping
        # indicates contradiction in our partial state.
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
    """
    Candidate values for x = P(plain_val) in one constraint:
      P(core[P(plain_val)]) = cipher_val
    """
    if plain_val in mapping:
        return [mapping[plain_val]]

    if pairs_used >= max_pairs:
        return [plain_val]

    if cipher_val in mapping:
        return [core_inv[mapping[cipher_val]]]

    # Identity-first ordering tends to prune quickly for low pair counts.
    return [plain_val] + [x for x in range(26) if x != plain_val]


def _solve_plugboard_constraints(
    constraints: list[tuple[int, int, list[int], list[int]]],
    max_pairs: int,
    deadline: float | None,
):
    """
    Solve plugboard constraints for fixed rotor positions.

    Parameters
    ----------
    constraints : list of tuples (p, c, core_table, core_inv_table)
    max_pairs : int
    deadline : absolute perf_counter time, or None

    Returns
    -------
    dict[int, int] | None | timeout_marker
    """
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
    Find rotor positions AND plugboard pairs.

    Two-phase strategy:
    1) brute-force rotor start positions;
    2) for each rotor candidate, solve only the plugboard constraints
       with backtracking over an involution mapping.

    Parameters
    ----------
    ciphertext, crib : str
    rotor_names : tuple of 3 rotor names
    reflector_name : str
    num_plugboard_pairs : int
        Max number of plugboard pairs to search for.
    ring_settings : tuple of 3 ints
    solver_timeout_ms : int | None
        Global timeout budget for the whole search.

    Returns
    -------
    tuple of (positions, plugboard_pairs) or None
    """
    ciphertext = "".join(ch for ch in ciphertext.upper() if ch.isalpha())
    crib = "".join(ch for ch in crib.upper() if ch.isalpha())
    n = len(crib)
    if n == 0 or len(ciphertext) < n:
        return None

    # Enigma invariant: a letter cannot encrypt to itself (with reflector path).
    # If violated at any crib position, no configuration can satisfy constraints.
    for i in range(n):
        if crib[i] == ciphertext[i]:
            return None

    r_fwd = [_wiring(r) for r in rotor_names]
    r_inv = [_inv_wiring(r) for r in rotor_names]
    refl = _reflector(reflector_name)
    notches = [ord(ROTOR_NOTCHES[r]) - ord("A") for r in rotor_names]
    rings = list(ring_settings)
    crib_vals = [ord(ch) - ord("A") for ch in crib]
    cipher_vals = [ord(ch) - ord("A") for ch in ciphertext[:n]]

    deadline = None
    if solver_timeout_ms is not None:
        deadline = time.perf_counter() + (solver_timeout_ms / 1000.0)

    # Phase 1: brute-force rotor positions.
    # Phase 2 (for each candidate): solve only plugboard constraints.
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
                    core_table = [
                        _encrypt_core_numeric(
                            x,
                            pos_left[i],
                            pos_middle[i],
                            pos_right[i],
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


def _z3_lookup_vec(vec, idx_expr, name: str = "lut"):
    """
    Build a Z3 If-Then-Else chain to look up vec[idx_expr]
    where vec is a Z3 IntVector (list of Z3 Int variables).
    """
    expr = vec[25]
    for i in range(24, -1, -1):
        expr = If(idx_expr == i, vec[i], expr)
    return expr
