"""
Rotor component for the Enigma machine.

Each rotor has:
- A wiring permutation (26 letters mapped to 26 letters)
- A notch position (triggers the next rotor to step)
- A ring setting (Ringstellung)
- A current position that advances with each keypress

Historical Wehrmacht rotors I-V are provided as constants.
"""

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Historical rotor wirings (Wehrmacht / Kriegsmarine)
ROTOR_WIRINGS = {
    "I":   "EKMFLGDQVZNTOWYHXUSPAIBRCJ",
    "II":  "AJDKSIRUXBLHWTMCQGZNPYFVOE",
    "III": "BDFHJLCPRTXVZNYEIWGAKMUSQO",
    "IV":  "ESOVPZJAYQUIRHXLNFTGKDCMWB",
    "V":   "VZBRGITYUPSDNHLXAWMJQOFECK",
}

# Notch positions (the position at which the next rotor steps)
ROTOR_NOTCHES = {
    "I":   "Q",   # If rotor steps from Q to R, next rotor advances
    "II":  "E",
    "III": "V",
    "IV":  "J",
    "V":   "Z",
}


class Rotor:
    """Single Enigma rotor."""

    def __init__(self, wiring: str, notch: str = "A", ring: int = 0, position: int = 0):
        """
        Parameters
        ----------
        wiring : str
            26-character permutation string (e.g. ROTOR_WIRINGS["I"]).
        notch : str
            Single letter — the notch position.
        ring : int
            Ring setting (Ringstellung), 0-25.
        position : int
            Initial position, 0-25.
        """
        self.wiring_str = wiring
        self.notch = ord(notch) - ord("A")
        self.ring = ring
        self.position = position

        # Pre-compute forward and inverse mappings
        self.forward_map = [ord(c) - ord("A") for c in wiring]
        self.inverse_map = [0] * 26
        for i, c in enumerate(self.forward_map):
            self.inverse_map[c] = i

    @classmethod
    def from_name(cls, name: str, ring: int = 0, position: int = 0) -> "Rotor":
        """Create a rotor from its historical name (I, II, III, IV, V)."""
        return cls(
            wiring=ROTOR_WIRINGS[name],
            notch=ROTOR_NOTCHES[name],
            ring=ring,
            position=position,
        )

    def step(self) -> bool:
        """
        Advance the rotor by one position.
        Returns True if the rotor was at its notch (i.e. the next rotor should step).
        """
        at_notch = self.is_at_notch()
        self.position = (self.position + 1) % 26
        return at_notch

    def is_at_notch(self) -> bool:
        """Check if rotor is currently at its notch position."""
        return self.position == self.notch

    def forward(self, c: int) -> int:
        """Pass a signal through the rotor in the forward direction (right to left)."""
        # Account for position and ring setting
        shifted = (c + self.position - self.ring) % 26
        out = self.forward_map[shifted]
        return (out - self.position + self.ring) % 26

    def backward(self, c: int) -> int:
        """Pass a signal through the rotor in the backward direction (left to right)."""
        shifted = (c + self.position - self.ring) % 26
        out = self.inverse_map[shifted]
        return (out - self.position + self.ring) % 26

    def reset(self, position: int = 0):
        """Reset the rotor to a given position."""
        self.position = position
