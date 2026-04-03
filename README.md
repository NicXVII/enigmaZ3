# enigmaZ3 - Enigma simulator and hybrid cracker (Z3 + search)

Progetto Python che combina simulazione Enigma a 3 rotori e cracking incrementale basato su Z3, fallback numerico e ranking euristico.

## Funzionalita

- Simulatore Enigma completo con double-stepping, ring settings e plugboard.
- Rotori supportati: `I`, `II`, `III`, `IV`, `V`.
- Riflettori supportati: `B`, `C`.
- Cracking posizioni rotori (`crack_rotor_positions`).
- Cracking con plugboard ignoto (`crack_with_plugboard`).
- Ricerca completa con ordine rotori e ring settings ignoti (`rank_rotor_configurations`, `crack_full_configuration`).
- CLI unificata: `encrypt`, `decrypt`, `crack`, `benchmark`.
- Demo interattiva terminale per presentazioni orali (`interactive_demo.py`).

## Requisiti

- Python 3.12 consigliato.
- Dipendenze runtime: `z3-solver`, `matplotlib`.

## Installazione

Setup minimo:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Setup sviluppo (test, coverage, lint, type-check):

```bash
pip install -r requirements-dev.txt
```

## API HTTP per i frontend (`frontend/`, `frontend_v2/`)

Dopo `pip install -r requirements.txt`, dalla root del repo:

```bash
python enigma_http_server.py
```

Serve `POST /encrypt` e `POST /crack` su `http://127.0.0.1:8765` (porta opzionale: `python enigma_http_server.py 9000`). I frontend usano questa URL **di default** (`frontend/api.js`); avvia il server e apri la pagina statica.

Dettagli request/response: `frontend/BACKEND.md`.

## Uso CLI

Help generale:

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

Decrypt usa gli stessi parametri (Enigma e simmetrica):

```bash
python enigma_cli.py decrypt \
  --text "<CIPHERTEXT>" \
  --rotors I,II,III \
  --positions 5,10,20 \
  --rings 0,0,0 \
  --reflector B \
  --plugboard AZ,BY
```

Crack modalita `positions` (plugboard noto o assente):

```bash
python enigma_cli.py crack \
  --mode positions \
  --ciphertext "XYZ..." \
  --crib "WETTERBERICHT" \
  --rotors I,II,III \
  --rings 0,0,0 \
  --plugboard AZ,BY \
  --timeout-ms 3000
```

Output: JSON con campo `positions`.

Crack modalita `plugboard` (plugboard ignoto, numero coppie noto):

```bash
python enigma_cli.py crack \
  --mode plugboard \
  --ciphertext "XYZ..." \
  --crib "WETTERBERICHT" \
  --rotors I,II,III \
  --rings 0,0,0 \
  --num-pairs 3 \
  --timeout-ms 8000
```

Output: JSON con `positions` e `plugboard_pairs` (oppure `result: null`).

Crack modalita `full` (ordine rotori/rings ignoti con ranking):

```bash
python enigma_cli.py crack \
  --mode full \
  --ciphertext "XYZ..." \
  --crib "WETTERBERICHT" \
  --rotor-pool I,II,III,IV \
  --ring-candidates 0,0,0 \
  --ring-candidates 2,11,7 \
  --top-k 5 \
  --timeout-ms 8000 \
  --per-config-timeout-ms 120 \
  --heuristic-budget 1200
```

Output: JSON con `best` e lista `ranked`.

Benchmark:

```bash
python enigma_cli.py benchmark --csv benchmark_results.csv --png benchmark_results.png --seed 42
```

## Demo interattiva

Script pensato per demo orale end-to-end:

```bash
python interactive_demo.py
```

La demo mostra:

- cifratura lettera per lettera con trace completo del segnale;
- verifica di simmetria (stessa chiave = decifratura);
- cracking posizioni con Z3 e tempo di risoluzione;
- decifratura finale con chiave trovata.

Configurazione demo di default in `interactive_demo.py`:

- rotori `I,II,III`
- posizioni iniziali `(5, 10, 20)`
- rings `(0, 0, 0)`
- riflettore `B`
- plugboard con 10 coppie (`A-B`, `C-D`, ..., `S-T`)

## API principali

Export pubblici dal package `cracker`:

- `crack_simple_enigma(...)`
- `crack_rotor_positions(...)`
- `crack_with_plugboard(...)`
- `rank_rotor_configurations(...)`
- `crack_full_configuration(...)`
- `CrackCandidate`

Esempio rapido:

```python
from cracker import crack_full_configuration

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

## Test, quality e profiling

Test:

```bash
pytest tests/ -v
```

Suite locale quality:

```bash
./scripts/run_quality.sh
```

Release check locale (quality + benchmark + profiling):

```bash
./scripts/release.sh
```

Profiling full cracker:

```bash
python scripts/profile_full_cracker.py
```

Output profiling: `profiling/full_cracker_profile.txt`.

## CI

Workflow GitHub Actions: `.github/workflows/ci.yml`.

- test + coverage
- lint (`ruff`)
- type-check (`mypy`)

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
├── scripts/
│   ├── run_quality.sh
│   ├── release.sh
│   └── profile_full_cracker.py
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```
