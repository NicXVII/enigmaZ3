"""
Z3-based cracker for the full Enigma machine (3 rotors + reflector + plugboard).

Three incremental difficulty levels:
1. crack_rotor_positions   — find the 3 rotor start positions (plugboard known / empty)
2. crack_with_plugboard    — find rotor positions + plugboard pairs

The approach: we model each character's encryption path entirely in Z3 using
lookup tables encoded as If-Then-Else chains, combined with modular arithmetic.
"""

from z3 import (
    Int, IntVector, Solver, And, Or, If, Distinct,
    sat, Implies, Not, Function, IntSort,
)

from enigma.machine import EnigmaMachine
from enigma.plugboard import Plugboard
from enigma.rotor import ROTOR_WIRINGS, ROTOR_NOTCHES, Rotor
from enigma.reflector import REFLECTOR_WIRINGS, Reflector


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
    left_name, middle_name, right_name = rotor_names
    machine = EnigmaMachine(
        rotors=[
            Rotor.from_name(left_name, ring=ring_settings[0]),
            Rotor.from_name(middle_name, ring=ring_settings[1]),
            Rotor.from_name(right_name, ring=ring_settings[2]),
        ],
        reflector=Reflector.from_name(reflector_name),
        plugboard=Plugboard(plugboard_pairs),
    )

    # Exhaustive search over all 26^3 start positions.
    # This is fast in practice for crib lengths used in the tests and avoids
    # expensive SMT solving for this specific task.
    for left_pos in range(26):
        for middle_pos in range(26):
            for right_pos in range(26):
                machine.reset((left_pos, middle_pos, right_pos))
                matched = True
                for i, p_char in enumerate(crib):
                    if machine.encrypt_char(p_char) != target[i]:
                        matched = False
                        break
                if matched:
                    return (left_pos, middle_pos, right_pos)
    return None


# ---------------------------------------------------------------------------
# Level 2/3: Crack rotor positions AND plugboard
# ---------------------------------------------------------------------------

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

    This models the plugboard as Z3 variables with the constraint that
    it forms a valid involution (each letter maps to at most one other).

    Parameters
    ----------
    ciphertext, crib : str
    rotor_names : tuple of 3 rotor names
    reflector_name : str
    num_plugboard_pairs : int
        Max number of plugboard pairs to search for.
    ring_settings : tuple of 3 ints

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

    s = Solver()
    if solver_timeout_ms is not None:
        s.set(timeout=solver_timeout_ms)

    # Rotor start positions
    L0 = Int("L0")
    M0 = Int("M0")
    R0 = Int("R0")
    s.add(L0 >= 0, L0 < 26)
    s.add(M0 >= 0, M0 < 26)
    s.add(R0 >= 0, R0 < 26)

    # Plugboard as 26 Int variables
    plug = IntVector("plug", 26)
    for i in range(26):
        s.add(plug[i] >= 0, plug[i] < 26)

    # Plugboard must be an involution: plug[plug[i]] == i
    for i in range(26):
        s.add(_z3_lookup_vec(plug, _z3_lookup_vec(plug, i)) == i)

    # At most num_plugboard_pairs swaps (rest are identity)
    swap_count = sum([If(plug[i] != i, 1, 0) for i in range(26)])
    s.add(swap_count <= 2 * num_plugboard_pairs)

    # Compute symbolic rotor positions
    pos_L, pos_M, pos_R = _compute_positions(L0, M0, R0, n, notches)

    # Plugboard lookup functions
    def plug_in_fn(val):
        if isinstance(val, int):
            return _z3_lookup_vec(plug, val)
        return _z3_lookup_vec(plug, val)

    def plug_out_fn(expr):
        return _z3_lookup_vec(plug, expr)

    # Encryption constraints
    for i in range(n):
        p = ord(crib[i]) - ord("A")
        c = ord(ciphertext[i]) - ord("A")

        encrypted = _encrypt_char_z3(
            p, pos_L[i], pos_M[i], pos_R[i],
            r_fwd, r_inv, refl, rings,
            plug_in_fn=plug_in_fn,
            plug_out_fn=plug_out_fn,
        )

        s.add(encrypted == c)

    if s.check() == sat:
        model = s.model()
        positions = (
            model[L0].as_long(),
            model[M0].as_long(),
            model[R0].as_long(),
        )
        pairs = []
        for i in range(26):
            j = model[plug[i]].as_long()
            if j > i:
                pairs.append((chr(i + ord("A")), chr(j + ord("A"))))
        return positions, pairs
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
