"""
Plugboard (Steckerbrett) component for the Enigma machine.

The plugboard swaps pairs of letters before and after the rotor assembly.
Up to 13 pairs can be connected (historically 10 were used).
"""


class Plugboard:
    """Enigma plugboard."""

    def __init__(self, pairs: list[tuple[str, str]] | None = None):
        """
        Parameters
        ----------
        pairs : list of (str, str)
            Letter pairs to swap, e.g. [("A", "B"), ("C", "D")].
            If None or empty, no swaps are performed.
        """
        self.mapping = list(range(26))
        if pairs:
            for a, b in pairs:
                ia = ord(a) - ord("A")
                ib = ord(b) - ord("A")
                self.mapping[ia] = ib
                self.mapping[ib] = ia

    def swap(self, c: int) -> int:
        """Swap a letter through the plugboard."""
        return self.mapping[c]
