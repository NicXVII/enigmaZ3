# enigmaZ3 — Simulatore Enigma + Cracker Ibrido (Z3 + Ricerca)

Simulazione della macchina Enigma in Python con cracking a complessita incrementale.

Stato attuale (aggiornato al 3 marzo 2026):
- `simple_cracker.py`: usa Z3 in modo diretto (SMT puro) per la versione a 1 rotore.
- `full_cracker.py`:
  - `crack_rotor_positions`: tenta prima SMT su posizioni iniziali (`left0`, `middle0`, `right0`) con timeout breve, poi fallback numerico deterministico.
  - `crack_with_plugboard`: ricerca numerica su posizioni rotori + backtracking vincolato per plugboard ignoto.

Nota: questo progetto non implementa la procedura storica completa della Bombe di Turing (menu/cicli elettromeccanici).

## Struttura del progetto

```
enigmaZ3/
├── enigma/                  # Simulatore Enigma
│   ├── __init__.py
│   ├── rotor.py             # Rotori (wirings storici I-V, stepping, ring settings)
│   ├── reflector.py         # Riflettori (B, C)
│   ├── plugboard.py         # Plugboard (Steckerbrett)
│   └── machine.py           # SimpleEnigma (1 rotore) + EnigmaMachine (3 rotori)
├── cracker/                 # Cracker (SMT + ricerca numerica)
│   ├── __init__.py
│   ├── simple_cracker.py    # SMT puro per Enigma semplificata (1 rotore)
│   └── full_cracker.py      # Cracker ibrido per Enigma completa (3 rotori + plugboard)
├── tests/
│   └── test_enigma.py       # Test per tutte le fasi
├── benchmark.py             # Benchmark tempi cracking + grafici matplotlib
├── work.md                  # Piano di lavoro
└── README.md
```

## Requisiti

1. Crea e attiva un virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Installa dipendenze:

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

### Fase 4 — Cracker completo (ibrido)
Tre livelli incrementali:
1. **Solo posizioni rotori** — `crack_rotor_positions` (SMT con fallback numerico)
2. **Rotori + plugboard noto** — stessa funzione, con vincoli plugboard noti
3. **Rotori + plugboard sconosciuto** — `crack_with_plugboard` (ricerca numerica + backtracking)

### Fase 5 — Benchmark e grafici
Misura dei tempi di cracking al variare di:
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

### Crackare posizioni rotori (ibrido)

```python
from cracker import crack_rotor_positions

# Dato un ciphertext e un crib, trova le posizioni dei rotori.
# Strategia: SMT con timeout breve + fallback numerico.
positions = crack_rotor_positions(
    ciphertext="XYZABCDEFG",  # il tuo ciphertext
    crib="WETTERBERIC",       # testo in chiaro noto
    rotor_names=("I", "II", "III"),
    reflector_name="B",
    solver_timeout_ms=50,     # opzionale
)
print(f"Posizioni trovate: {positions}")
```

### Eseguire i test

Dal root del repository:

```bash
pytest tests/ -v
```

Se sei gia dentro `tests/`, usa invece:

```bash
pytest -v
```

`python test_enigma.py` non esegue i test pytest automaticamente.

### Eseguire i benchmark

```bash
python benchmark.py
```

Produce il file `benchmark_results.png` con i grafici dei tempi.

## Come funziona il cracking

### `simple_cracker.py` (1 rotore)
- Modello SMT diretto con Z3.
- Variabile simbolica della posizione iniziale, vincoli per ogni lettera del crib.

### `full_cracker.py` — `crack_rotor_positions`
- Costruisce un modello SMT per le posizioni iniziali dei 3 rotori.
- Modella stepping (double-stepping) e passaggio del segnale con lookup ITE.
- Usa timeout sul solver; se non ottiene un candidato valido in tempo, usa fallback esaustivo numerico (`26^3`) con verifica deterministica.

### `full_cracker.py` — `crack_with_plugboard`
- Cerca posizioni rotori numericamente.
- Per ogni candidato, risolve i vincoli plugboard con backtracking su una mappatura involutiva.
- Include pruning e timeout globale.

## Limitazioni attuali

- Non implementa l'algoritmo storico completo della Bombe (menu/loop/cycle detection).
- Il cracking completo con plugboard ignoto non e modellato interamente in SMT.

## Parametri storici

| Componente | Wiring |
|------------|--------|
| Rotore I   | `EKMFLGDQVZNTOWYHXUSPAIBRCJ` (notch: Q) |
| Rotore II  | `AJDKSIRUXBLHWTMCQGZNPYFVOE` (notch: E) |
| Rotore III | `BDFHJLCPRTXVZNYEIWGAKMUSQO` (notch: V) |
| Riflettore B | `YRUHQSLDPXNGOKMIEBFZCWVJAT` |
