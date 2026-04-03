# Connecting the EnigmaZ3 frontends to Python

The UI expects a JSON API. Point the browser at the static files **over HTTP** (not `file://`) so ES modules load correctly:

```bash
cd frontend
python3 -m http.server 8080
```

Open `http://localhost:8080` (or use `frontend_v2` on another port).

## Official server: `enigma_http_server.py`

From the **repository root** (with `z3-solver` installed):

```bash
python enigma_http_server.py
```

Listens on `http://127.0.0.1:8765` by default. Exposes `GET /health`, `POST /encrypt`, `POST /crack` and sends CORS headers for local browser use.

By default `api.js` calls **`http://127.0.0.1:8765`** (no HTML change needed). Override if needed:

```html
<script>window.ENIGMA_API_BASE = "http://127.0.0.1:9000";</script>
```

To **disable** the API (e.g. UI-only testing): `window.ENIGMA_API_BASE = ""` before loading `app.js`. For a **fake** crack response only in that case, also set `window.ENIGMA_USE_MOCK_CRACK = true`.

**Simulate** still uses the in-browser Enigma in `simulator.js` (no server required). **Crack** always talks to the Python server unless API is disabled as above.

## Endpoints

### `POST /encrypt`

**Request (example)**

```json
{
  "rotors": ["I", "II", "III"],
  "positions": [0, 0, 0],
  "rings": [0, 0, 0],
  "reflector": "B",
  "plugboard": "AZ BM",
  "text": "HELLO"
}
```

`plugboard` may also be `[["A","Z"],["B","M"]]`.

**Response**

```json
{
  "ciphertext": "...",
  "ok": true
}
```

### `POST /crack`

**`mode`** (required):

| Value | Python API |
|--------|------------|
| `positions` | `crack_rotor_positions` — rotori e anelli noti; plugboard noto o vuoto |
| `plugboard` | `crack_with_plugboard` — plugboard ignoto; usa `num_plugboard_pairs` |
| `full` | `crack_full_configuration` — ordine rotori nel pool `I`–`V`; anelli = quelli inviati in `rings` (un solo candidato) |

**Request (example)**

```json
{
  "crib": "HELLO",
  "ciphertext": "XJKLM",
  "mode": "positions",
  "rotors": ["I", "II", "III"],
  "rings": [0, 0, 0],
  "reflector": "B",
  "plugboard": "AZ BM",
  "timeout_ms": 30000,
  "num_plugboard_pairs": 3
}
```

Optional timeouts: `timeout_ms` / `timeout_ms_positions`, `timeout_ms_plugboard`, `timeout_ms_full`, `per_config_timeout_ms`, `heuristic_budget`. For `full`, optional `rotor_pool`: `["I","II","III","IV","V"]`.

**Response (SAT)**

```json
{
  "status": "sat",
  "rotors": ["I", "II", "III"],
  "positions": [5, 10, 20],
  "rings": [0, 0, 0],
  "plugboard": [["A", "Z"], ["B", "M"]],
  "plaintext": "HELLO",
  "ciphertext": ".....",
  "constraints_used": ["..."]
}
```

**Response (UNSAT)**

```json
{
  "status": "unsat",
  "plaintext": "HELLO",
  "ciphertext": ".....",
  "constraints_used": ["..."],
  "error": "optional message"
}
```

## CORS

The bundled server sets `Access-Control-Allow-Origin: *` for local development.
