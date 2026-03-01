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
    ciphertext = ciphertext.upper().replace(" ", "")
    crib = crib.upper().replace(" ", "")
    n = len(crib)

    # Load wirings
    r_fwd = [_wiring(r) for r in rotor_names]      # [left, mid, right]
    r_inv = [_inv_wiring(r) for r in rotor_names]
    refl = _reflector(reflector_name)
    notches = [ord(ROTOR_NOTCHES[r]) - ord("A") for r in rotor_names]
    rings = list(ring_settings)

    # Plugboard mapping (fixed)
    plug = list(range(26))
    if plugboard_pairs:
        for a, b in plugboard_pairs:
            ia, ib = ord(a) - ord("A"), ord(b) - ord("A")
            plug[ia] = ib
            plug[ib] = ia

    s = Solver()

    # Variables: initial positions
    L0 = Int("L0")  # left rotor start position
    M0 = Int("M0")  # middle rotor start position
    R0 = Int("R0")  # right rotor start position
    s.add(L0 >= 0, L0 < 26)
    s.add(M0 >= 0, M0 < 26)
    s.add(R0 >= 0, R0 < 26)

    # For each character in the crib, simulate the stepping and encryption.
    # Because the stepping depends on whether rotors are at their notch,
    # and the notch depends on the (unknown) starting position, we compute
    # the rotor positions for each step symbolically.
    # However, for the crib length (typically 10-20 chars), we can just
    # enumerate all 26^3 = 17576 combinations via constraint per step.
    # 
    # More efficient: model each step's position symbolically using If-Then-Else
    # for the stepping logic.

    # We'll take a pragmatic approach: pre-compute rotor positions for each 
    # starting combo. But that's 17576 combos × n steps which is large.
    # 
    # Better: For short cribs (< ~26 chars), the right rotor steps every time,
    # middle rotor steps rarely, left rotor almost never.
    # We model this with symbolic stepping.

    # Build symbolic positions for each step
    # pos_L[i], pos_M[i], pos_R[i] = positions at step i (after stepping, before encryption)
    
    # Step 0: before any key press, positions are L0, M0, R0
    # At each key press, we step THEN encrypt.
    
    # For a practical solver, we enumerate per-step conditions symbolically.
    # The right rotor always advances. The middle advances if right was at notch.
    # The left advances if middle was at notch (double-stepping).
    
    # We use Z3 Int variables for positions at each step.
    pos_L = [Int(f"L_{i}") for i in range(n)]
    pos_M = [Int(f"M_{i}") for i in range(n)]
    pos_R = [Int(f"R_{i}") for i in range(n)]

    for i in range(n):
        if i == 0:
            prev_L, prev_M, prev_R = L0, M0, R0
        else:
            prev_L, prev_M, prev_R = pos_L[i - 1], pos_M[i - 1], pos_R[i - 1]

        # Double-stepping logic
        mid_at_notch = (prev_M == notches[1])  # middle rotor condition
        right_at_notch = (prev_R == notches[2])   # right rotor condition

        # Middle steps if: right_at_notch OR mid_at_notch (double-step)
        mid_steps = Or(right_at_notch, mid_at_notch)
        # Left steps if: mid_at_notch
        left_steps = mid_at_notch

        s.add(pos_R[i] == _z3_mod26(prev_R + 1))
        s.add(pos_M[i] == If(mid_steps, _z3_mod26(prev_M + 1), prev_M))
        s.add(pos_L[i] == If(left_steps, _z3_mod26(prev_L + 1), prev_L))

    # Now, for each crib character, add encryption constraints
    for i in range(n):
        p = ord(crib[i]) - ord("A")
        c = ord(ciphertext[i]) - ord("A")

        # Apply plugboard (fixed)
        p_after_plug = plug[p]

        # We need to encode the full path through 3 rotors + reflector + 3 rotors back
        # with symbolic rotor positions. We enumerate all possible position combos.
        # Since there are 26^3 possible position combos at each step, that's too many.
        # Instead, we use nested ITE chains (If-Then-Else).

        # For each rotor, the forward function is:
        #   fwd(x, pos, ring) = (rotor_fwd[(x + pos - ring) % 26] - pos + ring) % 26
        # We encode this as a Z3 expression.

        # Build encryption path as Z3 expressions
        x = p_after_plug  # integer constant

        # Forward through right rotor
        idx_r = _z3_mod26(x + pos_R[i] - rings[2])
        x_after_r_fwd = _z3_mod26(_z3_lookup(r_fwd[2], idx_r, f"rf{i}") - pos_R[i] + rings[2])

        # Forward through middle rotor
        idx_m = _z3_mod26(x_after_r_fwd + pos_M[i] - rings[1])
        x_after_m_fwd = _z3_mod26(_z3_lookup(r_fwd[1], idx_m, f"mf{i}") - pos_M[i] + rings[1])

        # Forward through left rotor
        idx_l = _z3_mod26(x_after_m_fwd + pos_L[i] - rings[0])
        x_after_l_fwd = _z3_mod26(_z3_lookup(r_fwd[0], idx_l, f"lf{i}") - pos_L[i] + rings[0])

        # Reflector
        x_after_refl = _z3_lookup(refl, x_after_l_fwd, f"refl{i}")

        # Backward through left rotor
        idx_l_b = _z3_mod26(x_after_refl + pos_L[i] - rings[0])
        x_after_l_bwd = _z3_mod26(_z3_lookup(r_inv[0], idx_l_b, f"lb{i}") - pos_L[i] + rings[0])

        # Backward through middle rotor
        idx_m_b = _z3_mod26(x_after_l_bwd + pos_M[i] - rings[1])
        x_after_m_bwd = _z3_mod26(_z3_lookup(r_inv[1], idx_m_b, f"mb{i}") - pos_M[i] + rings[1])

        # Backward through right rotor
        idx_r_b = _z3_mod26(x_after_m_bwd + pos_R[i] - rings[2])
        x_after_r_bwd = _z3_mod26(_z3_lookup(r_inv[2], idx_r_b, f"rb{i}") - pos_R[i] + rings[2])

        # Apply plugboard out
        expected = _z3_lookup(plug, x_after_r_bwd, f"plugout{i}")

        s.add(expected == c)

    if s.check() == sat:
        model = s.model()
        return (
            model[L0].as_long(),
            model[M0].as_long(),
            model[R0].as_long(),
        )
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
    ciphertext = ciphertext.upper().replace(" ", "")
    crib = crib.upper().replace(" ", "")
    n = len(crib)

    r_fwd = [_wiring(r) for r in rotor_names]
    r_inv = [_inv_wiring(r) for r in rotor_names]
    refl = _reflector(reflector_name)
    notches = [ord(ROTOR_NOTCHES[r]) - ord("A") for r in rotor_names]
    rings = list(ring_settings)

    s = Solver()

    # Rotor start positions
    L0 = Int("L0")
    M0 = Int("M0")
    R0 = Int("R0")
    s.add(L0 >= 0, L0 < 26)
    s.add(M0 >= 0, M0 < 26)
    s.add(R0 >= 0, R0 < 26)

    # Plugboard as a Z3 function: plug[i] = j means letter i is swapped with j
    # We model it as 26 Int variables
    plug = IntVector("plug", 26)
    for i in range(26):
        s.add(plug[i] >= 0, plug[i] < 26)

    # Plugboard must be an involution: plug[plug[i]] == i
    for i in range(26):
        s.add(_z3_lookup_vec(plug, _z3_lookup_vec(plug, i), f"inv_{i}") == i)

    # At most num_plugboard_pairs swaps (rest are identity)
    # Count the number of letters that are NOT mapped to themselves
    swap_count = sum([If(plug[i] != i, 1, 0) for i in range(26)])
    s.add(swap_count <= 2 * num_plugboard_pairs)

    # Each swapped pair: if plug[i] != i, then plug[i] > i (canonical form to break symmetry)
    # This isn't strictly necessary but helps
    for i in range(26):
        s.add(Implies(plug[i] != i, plug[i] > i))

    # Rotor positions (symbolic stepping)
    pos_L = [Int(f"L_{i}") for i in range(n)]
    pos_M = [Int(f"M_{i}") for i in range(n)]
    pos_R = [Int(f"R_{i}") for i in range(n)]

    for i in range(n):
        prev_L = L0 if i == 0 else pos_L[i - 1]
        prev_M = M0 if i == 0 else pos_M[i - 1]
        prev_R = R0 if i == 0 else pos_R[i - 1]

        mid_at_notch = (prev_M == notches[1])
        right_at_notch = (prev_R == notches[2])
        mid_steps = Or(right_at_notch, mid_at_notch)
        left_steps = mid_at_notch

        s.add(pos_R[i] == _z3_mod26(prev_R + 1))
        s.add(pos_M[i] == If(mid_steps, _z3_mod26(prev_M + 1), prev_M))
        s.add(pos_L[i] == If(left_steps, _z3_mod26(prev_L + 1), prev_L))

    # Encryption constraints for each crib character
    for i in range(n):
        p = ord(crib[i]) - ord("A")
        c = ord(ciphertext[i]) - ord("A")

        # Plugboard in (symbolic)
        x_after_plug_in = _z3_lookup_vec(plug, p, f"plugin_{i}")

        # Forward through right rotor
        idx_r = _z3_mod26(x_after_plug_in + pos_R[i] - rings[2])
        x_after_r_fwd = _z3_mod26(_z3_lookup(r_fwd[2], idx_r, f"rf{i}") - pos_R[i] + rings[2])

        # Forward through middle rotor
        idx_m = _z3_mod26(x_after_r_fwd + pos_M[i] - rings[1])
        x_after_m_fwd = _z3_mod26(_z3_lookup(r_fwd[1], idx_m, f"mf{i}") - pos_M[i] + rings[1])

        # Forward through left rotor
        idx_l = _z3_mod26(x_after_m_fwd + pos_L[i] - rings[0])
        x_after_l_fwd = _z3_mod26(_z3_lookup(r_fwd[0], idx_l, f"lf{i}") - pos_L[i] + rings[0])

        # Reflector
        x_after_refl = _z3_lookup(refl, x_after_l_fwd, f"refl{i}")

        # Backward through left rotor
        idx_l_b = _z3_mod26(x_after_refl + pos_L[i] - rings[0])
        x_after_l_bwd = _z3_mod26(_z3_lookup(r_inv[0], idx_l_b, f"lb{i}") - pos_L[i] + rings[0])

        # Backward through middle rotor
        idx_m_b = _z3_mod26(x_after_l_bwd + pos_M[i] - rings[1])
        x_after_m_bwd = _z3_mod26(_z3_lookup(r_inv[1], idx_m_b, f"mb{i}") - pos_M[i] + rings[1])

        # Backward through right rotor
        idx_r_b = _z3_mod26(x_after_m_bwd + pos_R[i] - rings[2])
        x_after_r_bwd = _z3_mod26(_z3_lookup(r_inv[2], idx_r_b, f"rb{i}") - pos_R[i] + rings[2])

        # Plugboard out (symbolic)
        x_final = _z3_lookup_vec(plug, x_after_r_bwd, f"plugout_{i}")

        s.add(x_final == c)

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
