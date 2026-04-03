"""
Tests for all phases of the Enigma project.
Run with: pytest tests/ -v
"""

from pathlib import Path
import sys

# Allow direct execution from tests/ (python test_enigma.py) by exposing repo root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cracker.full_cracker import (
    crack_full_configuration,
    crack_rotor_positions,
    crack_with_plugboard,
    rank_rotor_configurations,
)
from cracker.simple_cracker import crack_simple_enigma
from enigma.machine import EnigmaMachine, SimpleEnigma
from enigma.plugboard import Plugboard
from enigma.reflector import Reflector
from enigma.rotor import Rotor


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

    def test_with_extreme_ring_settings(self):
        """Ring settings at edges should still preserve roundtrip behavior."""
        plaintext = "EXTREMERINGSETTING"
        machine = self._make(positions=(25, 0, 13), rings=(0, 25, 25))
        ciphertext = machine.process(plaintext)

        machine.reset((25, 0, 13))
        decrypted = machine.process(ciphertext)
        assert decrypted == plaintext

    def test_with_many_plugboard_pairs(self):
        """Historically realistic dense plugboard (10 pairs)."""
        pairs = [
            ("A", "B"),
            ("C", "D"),
            ("E", "F"),
            ("G", "H"),
            ("I", "J"),
            ("K", "L"),
            ("M", "N"),
            ("O", "P"),
            ("Q", "R"),
            ("S", "T"),
        ]
        plaintext = "PLUGBOARDDENSITY"
        machine = self._make(positions=(4, 18, 9), rings=(3, 12, 7), plugboard_pairs=pairs)
        ciphertext = machine.process(plaintext)

        machine.reset((4, 18, 9))
        decrypted = machine.process(ciphertext)
        assert decrypted == plaintext

    def test_double_step_middle_at_notch_steps_left(self):
        """If middle rotor is at notch, middle and left must step."""
        machine = self._make(positions=(0, 4, 0))  # II notch is E=4
        machine.encrypt_char("A")
        assert (machine.left.position, machine.middle.position, machine.right.position) == (1, 5, 1)

    def test_double_step_right_notch_steps_middle(self):
        """If right rotor is at notch, middle must step."""
        machine = self._make(positions=(0, 0, 21))  # III notch is V=21
        machine.encrypt_char("A")
        assert (machine.left.position, machine.middle.position, machine.right.position) == (0, 1, 22)

    def test_double_step_sequence_over_two_keys(self):
        """Classic double-step sequence across two consecutive keypresses."""
        machine = self._make(positions=(0, 3, 21))

        machine.encrypt_char("A")
        assert (machine.left.position, machine.middle.position, machine.right.position) == (0, 4, 22)

        machine.encrypt_char("A")
        assert (machine.left.position, machine.middle.position, machine.right.position) == (1, 5, 23)

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

    def test_crack_with_unknown_plugboard_end_to_end(self):
        """Unknown plugboard cracking should return a decryptable configuration."""
        secret_positions = (6, 13, 19)
        secret_pairs = [("A", "Z"), ("B", "Y"), ("C", "X")]

        machine = EnigmaMachine(
            [
                Rotor.from_name("I", position=secret_positions[0]),
                Rotor.from_name("II", position=secret_positions[1]),
                Rotor.from_name("III", position=secret_positions[2]),
            ],
            Reflector.from_name("B"),
            Plugboard(secret_pairs),
        )

        plaintext = "WETTERBERICHT"
        ciphertext = machine.process(plaintext)

        cracked = crack_with_plugboard(
            ciphertext=ciphertext,
            crib=plaintext,
            rotor_names=("I", "II", "III"),
            reflector_name="B",
            num_plugboard_pairs=3,
            solver_timeout_ms=8000,
        )
        assert cracked is not None

        found_positions, found_pairs = cracked
        assert found_positions == secret_positions

        verify_machine = EnigmaMachine(
            [
                Rotor.from_name("I", position=found_positions[0]),
                Rotor.from_name("II", position=found_positions[1]),
                Rotor.from_name("III", position=found_positions[2]),
            ],
            Reflector.from_name("B"),
            Plugboard(found_pairs),
        )
        assert verify_machine.process(plaintext) == ciphertext

    def test_crack_full_configuration_unknown_order_and_rings(self):
        """Complete search should recover order + rings + positions with ranking enabled."""
        secret_order = ("III", "I", "II")
        secret_positions = (9, 4, 22)
        secret_rings = (2, 11, 7)

        machine = EnigmaMachine(
            [
                Rotor.from_name(secret_order[0], ring=secret_rings[0], position=secret_positions[0]),
                Rotor.from_name(secret_order[1], ring=secret_rings[1], position=secret_positions[1]),
                Rotor.from_name(secret_order[2], ring=secret_rings[2], position=secret_positions[2]),
            ],
            Reflector.from_name("B"),
        )

        plaintext = "OBERKOMMANDO"
        ciphertext = machine.process(plaintext)

        ranked = rank_rotor_configurations(
            ciphertext=ciphertext,
            crib=plaintext,
            rotor_pool=("I", "II", "III"),
            reflector_name="B",
            search_rotor_order=True,
            search_ring_settings=False,
            ring_candidates=[(0, 0, 0), (2, 11, 7), (1, 1, 1)],
            top_k=5,
            global_timeout_ms=8000,
            solver_timeout_ms_per_config=120,
            heuristic_position_budget=1200,
        )

        assert ranked
        assert ranked[0].mismatches <= ranked[-1].mismatches

        best = crack_full_configuration(
            ciphertext=ciphertext,
            crib=plaintext,
            rotor_pool=("I", "II", "III"),
            reflector_name="B",
            search_rotor_order=True,
            search_ring_settings=False,
            ring_candidates=[(0, 0, 0), (2, 11, 7), (1, 1, 1)],
            top_k=5,
            global_timeout_ms=8000,
            solver_timeout_ms_per_config=120,
            heuristic_position_budget=1200,
        )

        assert best is not None
        assert best.mismatches == 0
        assert best.rotor_names == secret_order
        assert best.ring_settings == secret_rings
        assert best.positions == secret_positions
