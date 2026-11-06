# enigmaZ3 - Enigma simulator and hybrid cracker (Z3 + search)

Progetto Python che combina simulazione Enigma a 3 rotori e cracking basato su Z3, con scansione numerica di riserva e ricerca del plugboard.

## Funzionalita

- Simulatore Enigma completo con double-stepping, ring settings e plugboard.
- Rotori supportati: `I`, `II`, `III`, `IV`, `V`.
- Riflettori supportati: `B`, `C`.
- Cracking posizioni rotori (`crack_rotor_positions`).
- Cracking con plugboard ignoto (`crack_with_plugboard`).
- CLI: `encrypt`, `decrypt`, `crack`.
- Demo interattiva terminale per presentazioni orali (`interactive_demo.py`).

## Requisiti

- Python 3.12 consigliato.
- Dipendenze runtime: `z3-solver`.

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

## API HTTP per il frontend (`frontend_v2/`)

Dopo `pip install -r requirements.txt`, dalla root del repo:

```bash
PYTHONPATH=. python scripts/enigma_http_server.py
python -m http.server 8080 --directory frontend_v2
```

L’API serve `POST /encrypt` e `POST /crack` su `http://127.0.0.1:8765` (porta opzionale: `PYTHONPATH=. python scripts/enigma_http_server.py 9000`). Il frontend usa questa URL **di default** (`frontend_v2/api.js`); apri `http://127.0.0.1:8080`.

Dettagli request/response: `docs/BACKEND.md`.

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

Esempio rapido:

```python
from cracker import crack_rotor_positions

positions = crack_rotor_positions(
    ciphertext="...",
    crib="WETTERBERICHT",
    rotor_names=("I", "II", "III"),
    reflector_name="B",
)
print(positions)
```

## Test e quality

Test:

```bash
pytest tests/ -v
```

Suite locale quality:

```bash
./scripts/run_quality.sh
```

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
├── scripts/
│   ├── enigma_cli.py
│   ├── enigma_http_server.py
│   ├── interactive_demo.py
│   └── run_quality.sh
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```
