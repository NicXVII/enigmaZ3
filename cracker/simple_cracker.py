"""
Z3-based cracker for the simplified Enigma (single rotor, no plugboard).

Given a ciphertext and a known plaintext (crib), finds the initial rotor position
by modelling the Enigma encryption as constraints over integer arithmetic mod 26.
"""

from z3 import Int, Solver, And, sat

from enigma.rotor import ROTOR_WIRINGS
from enigma.reflector import REFLECTOR_WIRINGS


def _build_wiring_table(wiring_str: str) -> list[int]:
    """Convert a wiring string to a list of ints."""
    return [ord(c) - ord("A") for c in wiring_str]


def crack_simple_enigma(
    ciphertext: str,
    crib: str,
    rotor_wiring: str = "I",
    reflector_wiring: str = "B",
) -> int | None:
    """
    Use Z3 to find the initial rotor position of a SimpleEnigma.

    Parameters
    ----------
    ciphertext : str
        The encrypted message (uppercase A-Z).
    crib : str
        The known plaintext corresponding to the START of the ciphertext.
    rotor_wiring : str
        Name of the rotor wiring to use (e.g. "I").
    reflector_wiring : str
        Name of the reflector (e.g. "B").

    Returns
    -------
    int or None
        The initial rotor position (0-25), or None if no solution found.
    """
    ciphertext = ciphertext.upper().replace(" ", "")
    crib = crib.upper().replace(" ", "")

    rotor_fwd = _build_wiring_table(ROTOR_WIRINGS[rotor_wiring])
    rotor_inv = [0] * 26
    for i, v in enumerate(rotor_fwd):
        rotor_inv[v] = i
    reflector = _build_wiring_table(REFLECTOR_WIRINGS[reflector_wiring])

    s = Solver()
    start_pos = Int("start_pos")
    s.add(start_pos >= 0, start_pos < 26)

    for i, (p_char, c_char) in enumerate(zip(crib, ciphertext)):
        p = ord(p_char) - ord("A")
        c = ord(c_char) - ord("A")

        # The rotor steps BEFORE encrypting, so at step i the effective position
        # is (start_pos + i + 1) % 26  (ring=0 for simplified version)
        pos = start_pos + i + 1  # Z3 expression

        # Forward through rotor: rotor_fwd[(p + pos) % 26] - pos  mod 26
        # We enumerate all 26 possible positions and add the constraint
        # that exactly one matches.
        # Since start_pos is symbolic, we build a lookup:
        # For each candidate position value v (0..25):
        #   if pos % 26 == v, then the encryption must match.
        conditions = []
        for v in range(26):
            # Forward
            after_fwd = rotor_fwd[(p + v) % 26]
            # Reflector
            after_ref = reflector[(after_fwd - v) % 26]
            # Backward
            after_bwd = rotor_inv[(after_ref + v) % 26]
            result = (after_bwd - v) % 26

            conditions.append(
                And(pos % 26 == v, result == c)
            )

        # Exactly one of the conditions must hold
        from z3 import Or
        s.add(Or(*conditions))

    if s.check() == sat:
        model = s.model()
        return model[start_pos].as_long()
    return None
