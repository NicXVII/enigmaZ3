# enigmaZ3 - Simulatore Enigma + Cracking Z3 (versione semplificata)

Progetto didattico per esame orale:

- simulazione Enigma a 3 rotori (double-stepping, rings, plugboard);
- cracking delle sole posizioni iniziali con SMT/Z3;
- demo interattiva end-to-end da terminale;
- benchmark tempi su scenari coerenti con il cracking Z3.

## Obiettivo del progetto

Mostrare in modo chiaro la catena:

1. simulazione fedele della macchina Enigma;
2. formalizzazione del problema in vincoli SMT;
3. risoluzione con Z3 delle posizioni iniziali `(left, middle, right)`.

## Requisiti

- Python 3.12 consigliato
- dipendenze runtime: `z3-solver`, `matplotlib`

## Installazione

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Per sviluppo/test:

```bash
pip install -r requirements-dev.txt
```

## Uso rapido CLI

Help:

```bash
python enigma_cli.py --help
```

Encrypt:

```bash
python enigma_cli.py encrypt \
  --text "HELLOWORLD" \
  --rotors I,II,III \
  --positions 5,10,20 \
  --rings 0,0,0 \
  --reflector B \
  --plugboard AZ,BY
```

Decrypt:

```bash
python enigma_cli.py decrypt \
  --text "<CIPHERTEXT>" \
  --rotors I,II,III \
  --positions 5,10,20 \
  --rings 0,0,0 \
  --reflector B \
  --plugboard AZ,BY
```

Crack posizioni con Z3:

```bash
python enigma_cli.py crack \
  --ciphertext "XYZ..." \
  --crib "WETTERBERICHT" \
  --rotors I,II,III \
  --rings 0,0,0 \
  --plugboard AZ,BY \
  --timeout-ms 3000
```

Output: JSON con campo `positions`.

## Demo interattiva

```bash
python interactive_demo.py
```

La demo mostra:

- trace del segnale lettera per lettera;
- proprietà di simmetria Enigma;
- cracking Z3 delle posizioni iniziali;
- decifratura finale con chiave trovata.

## Benchmark

```bash
python benchmark.py
```

Output generati:

- `benchmark_results.csv`
- `benchmark_results.png`

## API pubbliche

Package `cracker`:

- `crack_simple_enigma(...)`
- `crack_rotor_positions(...)`

Esempio:

```python
from cracker import crack_rotor_positions

positions = crack_rotor_positions(
    ciphertext="...",
    crib="WETTERBERICHT",
    rotor_names=("I", "II", "III"),
    reflector_name="B",
    ring_settings=(0, 0, 0),
)
print(positions)
```

## Test

```bash
pytest tests/ -v
```

## Struttura progetto

```text
enigmaZ3/
├── enigma/
│   ├── rotor.py
│   ├── reflector.py
│   ├── plugboard.py
│   └── machine.py
├── cracker/
│   ├── simple_cracker.py
│   └── full_cracker.py
├── tests/
│   └── test_enigma.py
├── interactive_demo.py
├── enigma_cli.py
├── benchmark.py
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```
