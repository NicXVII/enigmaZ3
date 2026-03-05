"""
Enigma machine — assembles rotors, reflector, and plugboard.

Two classes:
- SimpleEnigma: single rotor + reflector (Phase 1)
- EnigmaMachine: 3 rotors + reflector + plugboard (Phase 3)
"""

from .rotor import Rotor
from .reflector import Reflector    
from .plugboard import Plugboard


class SimpleEnigma:
    """
    Simplified Enigma with a single rotor and a reflector.
    No plugboard, no double-stepping. Used for Phase 1 / Phase 2.
    """

    def __init__(self, rotor: Rotor, reflector: Reflector):
        self.rotor = rotor
        self.reflector = reflector

    def encrypt_char(self, c: str) -> str:
        """Encrypt a single uppercase letter."""
        idx = ord(c) - ord("A")

        # Step the rotor BEFORE encrypting (like the real Enigma)
        self.rotor.step()

        # Forward through rotor
        idx = self.rotor.forward(idx)
        # Reflector
        idx = self.reflector.reflect(idx)
        # Backward through rotor
        idx = self.rotor.backward(idx)

        return chr(idx + ord("A"))

    def process(self, text: str) -> str:
        """Encrypt/decrypt a message (only uppercase A-Z, spaces/other chars are stripped)."""
        result = []
        for ch in text.upper():
            if ch.isalpha():
                result.append(self.encrypt_char(ch))
        return "".join(result)

    def reset(self, position: int = 0):
        """Reset rotor position."""
        self.rotor.reset(position)


class EnigmaMachine:
    """
    Full Enigma machine with 3 rotors, reflector, and plugboard.
    Implements the double-stepping mechanism.
    
    Rotor order: right (fast), middle, left (slow).
    Signal path: plugboard → right → middle → left → reflector → left → middle → right → plugboard
    """

    def __init__(
        self,
        rotors: list[Rotor],
        reflector: Reflector,
        plugboard: Plugboard | None = None,
    ):
        """
        Parameters
        ----------
        rotors : list[Rotor]
            Three rotors in order [left, middle, right] (slow to fast).
        reflector : Reflector
        plugboard : Plugboard, optional
        """
        assert len(rotors) == 3, "EnigmaMachine requires exactly 3 rotors"
        self.left = rotors[0]
        self.middle = rotors[1]
        self.right = rotors[2]
        self.reflector = reflector
        self.plugboard = plugboard or Plugboard()

    def _step_rotors(self):
        """
        Advance rotors with the double-stepping mechanism.
        
        1. If the middle rotor is at its notch, both the middle and left rotors step.
        2. If the right rotor is at its notch, the middle rotor steps.
        3. The right rotor always steps.
        """
        # Double stepping: middle rotor steps if it's at its notch
        if self.middle.is_at_notch():
            self.middle.step()
            self.left.step()
        elif self.right.is_at_notch():
            self.middle.step()

        # Right rotor always steps
        self.right.step()

    def encrypt_char(self, c: str) -> str:
        """Encrypt a single uppercase letter."""
        idx = ord(c) - ord("A")

        # Step rotors BEFORE encrypting
        self._step_rotors()

        # Plugboard in
        idx = self.plugboard.swap(idx)

        # Forward through rotors: right → middle → left
        idx = self.right.forward(idx)
        idx = self.middle.forward(idx)
        idx = self.left.forward(idx)

        # Reflector
        idx = self.reflector.reflect(idx)

        # Backward through rotors: left → middle → right
        idx = self.left.backward(idx)
        idx = self.middle.backward(idx)
        idx = self.right.backward(idx)

        # Plugboard out
        idx = self.plugboard.swap(idx)

        return chr(idx + ord("A"))

    def process(self, text: str) -> str:
        """Encrypt/decrypt a message (uppercase A-Z only)."""
        result = []
        for ch in text.upper():
            if ch.isalpha():
                result.append(self.encrypt_char(ch))
        return "".join(result)

    def reset(self, positions: tuple[int, int, int] = (0, 0, 0)):
        """Reset all rotors to given positions (left, middle, right)."""
        self.left.reset(positions[0])
        self.middle.reset(positions[1])
        self.right.reset(positions[2])
