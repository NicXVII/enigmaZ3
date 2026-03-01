# enigmaZ3 — Simulatore Enigma + Cracker con Z3

Simulazione della macchina Enigma in Python, con Z3 che decifra come la Bombe di Turing.

## Struttura del progetto

```
enigmaZ3/
├── enigma/                  # Simulatore Enigma
│   ├── __init__.py
│   ├── rotor.py             # Rotori (wirings storici I-V, stepping, ring settings)
│   ├── reflector.py         # Riflettori (B, C)
│   ├── plugboard.py         # Plugboard (Steckerbrett)
│   └── machine.py           # SimpleEnigma (1 rotore) + EnigmaMachine (3 rotori)
├── cracker/                 # Cracker Z3
│   ├── __init__.py
│   ├── simple_cracker.py    # Cracker per Enigma semplificata (1 rotore)
│   └── full_cracker.py      # Cracker per Enigma completa (3 rotori + plugboard)
├── tests/
│   └── test_enigma.py       # Test per tutte le fasi
├── benchmark.py             # Benchmark tempi Z3 + grafici matplotlib
├── work.md                  # Piano di lavoro
└── README.md
```

## Requisiti

```bash
pip install z3-solver matplotlib pytest
```

## Fasi del progetto

### Fase 1 — Simulatore Enigma base
Versione semplificata con un solo rotore e riflettore, senza plugboard.
- Cifratura e decifratura sono la stessa operazione (proprietà dell'Enigma)
- Nessuna lettera si cifra in sé stessa

### Fase 2 — Z3 cracker (versione base)
Dato un ciphertext e un crib (testo in chiaro noto), Z3 trova la posizione iniziale del rotore.
Il solver modella la cifratura come vincoli aritmetici modulo 26.

### Fase 3 — Enigma completa
3 rotori (I, II, III) + riflettore B + plugboard con meccanismo di double-stepping.
Parametri storici reali della Wehrmacht.

### Fase 4 — Z3 cracker completo
Tre livelli incrementali:
1. **Solo posizioni rotori** — trova le 3 posizioni iniziali dato un crib
2. **Rotori + plugboard noto** — posizioni con plugboard fornito
3. **Rotori + plugboard sconosciuto** — trova entrambi simultaneamente

### Fase 5 — Benchmark e grafici
Misura dei tempi Z3 al variare di:
- Lunghezza del crib (3-15 caratteri)
- Numero di coppie plugboard (0-3)

## Utilizzo

### Cifrare un messaggio

```python
from enigma import Rotor, Reflector, Plugboard, EnigmaMachine

# Configura: rotori I, II, III — posizioni 5, 10, 20 — riflettore B
rotors = [
    Rotor.from_name("I", position=5),
    Rotor.from_name("II", position=10),
    Rotor.from_name("III", position=20),
]
reflector = Reflector.from_name("B")
plugboard = Plugboard([("A", "Z"), ("B", "Y"), ("C", "X")])

machine = EnigmaMachine(rotors, reflector, plugboard)
ciphertext = machine.process("HELLOWORLD")
print(ciphertext)
```

### Crackare con Z3

```python
from cracker import crack_rotor_positions

# Dato un ciphertext e un crib, Z3 trova le posizioni dei rotori
positions = crack_rotor_positions(
    ciphertext="XYZABCDEFG",  # il tuo ciphertext
    crib="WETTERBERIC",       # testo in chiaro noto
    rotor_names=("I", "II", "III"),
    reflector_name="B",
)
print(f"Posizioni trovate: {positions}")
```

### Eseguire i test

```bash
pytest tests/ -v
```

### Eseguire i benchmark

```bash
python benchmark.py
```

Produce il file `benchmark_results.png` con i grafici dei tempi.

## Come funziona il cracker Z3

Il cracker modella ogni passo della cifratura Enigma come vincoli SMT:
- Le posizioni dei rotori sono **variabili intere** (0-25)
- Lo stepping dei rotori (incluso il double-stepping) è modellato con If-Then-Else
- Il passaggio del segnale attraverso i rotori usa lookup tables codificate come catene ITE
- Il plugboard (quando sconosciuto) è modellato come un'involuzione: `plug[plug[i]] = i`
- Per ogni carattere del crib, si aggiunge il vincolo: `encrypt(plaintext[i]) == ciphertext[i]`

Z3 risolve il sistema di vincoli e restituisce la configurazione della macchina.

## Parametri storici

| Componente | Wiring |
|------------|--------|
| Rotore I   | `EKMFLGDQVZNTOWYHXUSPAIBRCJ` (notch: Q) |
| Rotore II  | `AJDKSIRUXBLHWTMCQGZNPYFVOE` (notch: E) |
| Rotore III | `BDFHJLCPRTXVZNYEIWGAKMUSQO` (notch: V) |
| Riflettore B | `YRUHQSLDPXNGOKMIEBFZCWVJAT` |
