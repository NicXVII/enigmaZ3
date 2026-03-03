# enigmaZ3 - Enigma simulator and hybrid cracker (Z3 + search)

Simulatore Enigma in Python con cracking incrementale:
- simulazione fedele a 3 rotori (double-stepping, ring settings, plugboard)
- cracking posizioni rotori
- cracking con plugboard ignoto
- ricerca configurazione completa con ordine rotori ignoto e ring settings ignoti

## Stato attuale (3 marzo 2026)

1. Test coverage estesa su meccanica Enigma e cracking.
2. Cracker completo con ranking candidati e timeout globale chiaro.
3. Ottimizzazioni prestazionali (cache tabelle core + pruning/early-stop).
4. CLI unica (`encrypt`, `decrypt`, `crack`, `benchmark`) con validazione input.
5. Pipeline quality/release con CI, coverage, lint e type-check.

## Setup rapido

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## CLI

### Encrypt / Decrypt

```bash
python enigma_cli.py encrypt \
  --text "HELLOWORLD" \
  --rotors I,II,III \
  --positions 5,10,20 \
  --rings 0,0,0 \
  --reflector B \
  --plugboard AZ,BY
```

`decrypt` usa gli stessi parametri (Enigma e simmetrica):

```bash
python enigma_cli.py decrypt --text "<CIPHERTEXT>" --rotors I,II,III --positions 5,10,20
```

### Crack

Crack solo posizioni (plugboard noto o assente):

```bash
python enigma_cli.py crack \
  --mode positions \
  --ciphertext "XYZ..." \
  --crib "WETTERBERICHT" \
  --rotors I,II,III \
  --rings 0,0,0 \
  --plugboard AZ,BY
```

Crack con plugboard ignoto:

```bash
python enigma_cli.py crack \
  --mode plugboard \
  --ciphertext "XYZ..." \
  --crib "WETTERBERICHT" \
  --rotors I,II,III \
  --num-pairs 3 \
  --timeout-ms 8000
```

Ricerca completa (ordine rotori + ring ignoti) con ranking:

```bash
python enigma_cli.py crack \
  --mode full \
  --ciphertext "XYZ..." \
  --crib "WETTERBERICHT" \
  --rotor-pool I,II,III \
  --search-rings \
  --top-k 5 \
  --timeout-ms 3000
```

### Benchmark

```bash
python enigma_cli.py benchmark --csv benchmark_results.csv --png benchmark_results.png
```

## API principali

- `crack_rotor_positions(...)`
- `crack_with_plugboard(...)`
- `rank_rotor_configurations(...)`
- `crack_full_configuration(...)`

Esempio Python rapido:

```python
from cracker.full_cracker import crack_full_configuration

best = crack_full_configuration(
    ciphertext="...",
    crib="WETTERBERICHT",
    rotor_pool=("I", "II", "III"),
    search_rotor_order=True,
    search_ring_settings=True,
    global_timeout_ms=5000,
)
print(best)
```

## Test e quality

Test completi:

```bash
pytest tests/ -v
```

Suite quality locale:

```bash
./scripts/run_quality.sh
```

Release check locale (quality + benchmark + profiling):

```bash
./scripts/release.sh
```

Profiling specifico full cracker:

```bash
python scripts/profile_full_cracker.py
```

Output profiling: `profiling/full_cracker_profile.txt`.

## CI

Workflow GitHub Actions in `.github/workflows/ci.yml`:
- test con coverage
- lint (`ruff`)
- type-check (`mypy`)

## Struttura progetto

```
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
├── enigma_cli.py
├── benchmark.py
├── scripts/
│   ├── run_quality.sh
│   ├── release.sh
│   └── profile_full_cracker.py
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
└── .github/workflows/ci.yml
```
