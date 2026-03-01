"""
Reflector component for the Enigma machine.

The reflector is a fixed wiring that pairs letters.
Historical reflectors B and C are provided.
"""

REFLECTOR_WIRINGS = {
    "B": "YRUHQSLDPXNGOKMIEBFZCWVJAT",
    "C": "FVPJIAOYEDRZXWGCTKUQSBNMHL",
}


class Reflector:
    """Enigma reflector (Umkehrwalze)."""

    def __init__(self, wiring: str):
        self.wiring = [ord(c) - ord("A") for c in wiring]

    @classmethod
    def from_name(cls, name: str) -> "Reflector":
        """Create a reflector from its historical name (B or C)."""
        return cls(REFLECTOR_WIRINGS[name])

    def reflect(self, c: int) -> int:
        """Pass a signal through the reflector."""
        return self.wiring[c]
