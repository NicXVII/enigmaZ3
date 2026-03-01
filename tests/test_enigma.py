"""
Tests for all phases of the Enigma project.
Run with: pytest tests/ -v
"""

import pytest
from enigma.rotor import Rotor
from enigma.reflector import Reflector
from enigma.plugboard import Plugboard
from enigma.machine import SimpleEnigma, EnigmaMachine
from cracker.simple_cracker import crack_simple_enigma
from cracker.full_cracker import crack_rotor_positions


# ────────────────────────────────────────────────
# Phase 1: SimpleEnigma (single rotor, no plugboard)
# ────────────────────────────────────────────────

class TestSimpleEnigma:
    def _make(self, position: int = 0) -> SimpleEnigma:
        rotor = Rotor.from_name("I", position=position)
        reflector = Reflector.from_name("B")
        return SimpleEnigma(rotor, reflector)

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypt then decrypt with same key → original message."""
        plaintext = "HELLOWORLD"
        machine = self._make(position=5)
        ciphertext = machine.process(plaintext)

        # A letter must not encrypt to itself (Enigma property)
        for p, c in zip(plaintext, ciphertext):
            assert p != c, f"Letter {p} encrypted to itself!"

        # Reset and decrypt
        machine.reset(5)
        decrypted = machine.process(ciphertext)
        assert decrypted == plaintext

    def test_different_positions_give_different_ciphertexts(self):
        plaintext = "TESTMESSAGE"
        results = set()
        for pos in range(26):
            m = self._make(position=pos)
            results.add(m.process(plaintext))
        # All 26 positions should produce distinct ciphertexts
        assert len(results) == 26

    def test_single_char(self):
        """Single character encryption is self-inverse."""
        m1 = self._make(position=0)
        c = m1.encrypt_char("A")
        m2 = self._make(position=0)
        p = m2.encrypt_char(c)
        assert p == "A"


# ────────────────────────────────────────────────
# Phase 2: Z3 Simple Cracker
# ────────────────────────────────────────────────

class TestSimpleCracker:
    def test_crack_finds_correct_position(self):
        """Z3 should recover the initial rotor position from a crib."""
        secret_pos = 17
        rotor = Rotor.from_name("I", position=secret_pos)
        reflector = Reflector.from_name("B")
        machine = SimpleEnigma(rotor, reflector)

        plaintext = "WETTERBERICHT"
        ciphertext = machine.process(plaintext)

        found_pos = crack_simple_enigma(
            ciphertext=ciphertext,
            crib=plaintext,
            rotor_wiring="I",
            reflector_wiring="B",
        )
        assert found_pos == secret_pos

    def test_crack_all_positions(self):
        """Test cracking works for every starting position."""
        plaintext = "HELLO"
        for pos in range(26):
            rotor = Rotor.from_name("I", position=pos)
            reflector = Reflector.from_name("B")
            machine = SimpleEnigma(rotor, reflector)
            ct = machine.process(plaintext)

            found = crack_simple_enigma(ct, plaintext)
            assert found == pos, f"Failed for position {pos}"


# ────────────────────────────────────────────────
# Phase 3: Full Enigma Machine
# ────────────────────────────────────────────────

class TestFullEnigma:
    def _make(
        self,
        positions: tuple[int, int, int] = (0, 0, 0),
        rings: tuple[int, int, int] = (0, 0, 0),
        plugboard_pairs: list[tuple[str, str]] | None = None,
    ) -> EnigmaMachine:
        rotors = [
            Rotor.from_name("I", ring=rings[0], position=positions[0]),
            Rotor.from_name("II", ring=rings[1], position=positions[1]),
            Rotor.from_name("III", ring=rings[2], position=positions[2]),
        ]
        reflector = Reflector.from_name("B")
        plugboard = Plugboard(plugboard_pairs)
        return EnigmaMachine(rotors, reflector, plugboard)

    def test_encrypt_decrypt_roundtrip(self):
        """Full machine: encrypt then decrypt with same settings."""
        plaintext = "THEQUICKBROWNFOXJUMPSOVERTHELAZYDOG"
        machine = self._make(positions=(3, 12, 21))
        ciphertext = machine.process(plaintext)

        # No letter should encrypt to itself
        for p, c in zip(plaintext, ciphertext):
            assert p != c

        # Decrypt
        machine.reset((3, 12, 21))
        decrypted = machine.process(ciphertext)
        assert decrypted == plaintext

    def test_with_plugboard(self):
        """Full machine with plugboard pairs."""
        plaintext = "ENIGMAMACHINETEST"
        pairs = [("A", "B"), ("C", "D"), ("E", "F")]
        machine = self._make(positions=(7, 14, 22), plugboard_pairs=pairs)
        ciphertext = machine.process(plaintext)

        machine.reset((7, 14, 22))
        decrypted = machine.process(ciphertext)
        assert decrypted == plaintext

    def test_with_ring_settings(self):
        """Full machine with ring settings."""
        plaintext = "RINGSTELLUNGTEST"
        machine = self._make(positions=(0, 0, 0), rings=(1, 5, 10))
        ciphertext = machine.process(plaintext)

        machine.reset((0, 0, 0))
        decrypted = machine.process(ciphertext)
        assert decrypted == plaintext

    def test_known_vector(self):
        """
        Test against a known Enigma result.
        Settings: Rotors I II III, Reflector B, positions AAA, no plugboard.
        Input: AAAAAAAAAA
        Expected: from standard implementations.
        """
        machine = self._make(positions=(0, 0, 0))
        result = machine.process("AAAAAAAAAA")
        # Computed from verified Enigma implementations
        # Rotors I II III, Reflector B, positions A A A, rings 0 0 0, no plugboard
        # Input AAAAAAAAAA → BDZGOWCXLT
        assert result == "BDZGOWCXLT"


# ────────────────────────────────────────────────
# Phase 4: Full Z3 Cracker — rotor positions
# ────────────────────────────────────────────────

class TestFullCracker:
    def test_crack_rotor_positions_no_plugboard(self):
        """Z3 should find 3 rotor positions from a crib (no plugboard)."""
        secret_positions = (5, 10, 20)
        rotors = [
            Rotor.from_name("I", position=secret_positions[0]),
            Rotor.from_name("II", position=secret_positions[1]),
            Rotor.from_name("III", position=secret_positions[2]),
        ]
        reflector = Reflector.from_name("B")
        machine = EnigmaMachine(rotors, reflector)

        plaintext = "WETTERBERICHT"
        ciphertext = machine.process(plaintext)

        found = crack_rotor_positions(
            ciphertext=ciphertext,
            crib=plaintext,
            rotor_names=("I", "II", "III"),
            reflector_name="B",
        )
        assert found == secret_positions

    def test_crack_rotor_positions_with_known_plugboard(self):
        """Z3 should find rotor positions when plugboard is given."""
        secret_positions = (2, 15, 8)
        pairs = [("A", "Z"), ("B", "Y")]
        rotors = [
            Rotor.from_name("I", position=secret_positions[0]),
            Rotor.from_name("II", position=secret_positions[1]),
            Rotor.from_name("III", position=secret_positions[2]),
        ]
        reflector = Reflector.from_name("B")
        plugboard = Plugboard(pairs)
        machine = EnigmaMachine(rotors, reflector, plugboard)

        plaintext = "OBERKOMMANDO"
        ciphertext = machine.process(plaintext)

        found = crack_rotor_positions(
            ciphertext=ciphertext,
            crib=plaintext,
            rotor_names=("I", "II", "III"),
            reflector_name="B",
            plugboard_pairs=pairs,
        )
        assert found == secret_positions
