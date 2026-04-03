# Connecting the EnigmaZ3 frontend to Python

The UI expects a JSON API. Point the browser at the static files **over HTTP** (not `file://`) so ES modules load correctly:

```bash
cd frontend
python3 -m http.server 8080
```

Open `http://localhost:8080`.

## Endpoints

### `POST /encrypt`

**Request (example)**

```json
{
  "rotors": ["I", "II", "III"],
  "positions": [0, 0, 0],
  "rings": [0, 0, 0],
  "reflector": "B",
  "plugboard": [["A", "Z"], ["B", "M"]],
  "text": "HELLO"
}
```

**Response**

```json
{
  "ciphertext": "...",
  "ok": true
}
```

Field names can match your Flask/FastAPI handlers; adjust `api.js` (`payloadToConfig` / `localEncrypt`) if your server uses different keys.

### `POST /crack`

**Request (example)**

```json
{
  "crib": "HELLO",
  "ciphertext": "XJKLM",
  "mode": "positions",
  "rotors": ["I", "II", "III"],
  "positions": [0, 0, 0],
  "rings": [0, 0, 0],
  "reflector": "B",
  "plugboard": "AZ BM"
}
```

**Response** — align with what `renderResults` in `ui.js` expects:

```json
{
  "status": "sat",
  "rotors": ["III", "II", "I"],
  "positions": [5, 10, 20],
  "rings": [0, 0, 0],
  "plugboard": [["A", "Z"], ["B", "M"]],
  "plaintext": "HELLO",
  "constraints_used": [
    "plugboard involution",
    "reflector involution without fixed points",
    "rotor stepping (double-step)",
    "no self-encryption",
    "crib–ciphertext consistency"
  ]
}
```

Use `"status": "unsat"` when no model exists.

## Base URL

Before loading `app.js`, set the API origin:

```html
<script>
  window.ENIGMA_API_BASE = "http://127.0.0.1:5000";
</script>
```

If `ENIGMA_API_BASE` is unset, `api.js` uses the in-browser Enigma implementation for **Simulate** and a **timed mock** for **Crack** so the demo works without a server.

## CORS

If the API is on another origin, enable CORS for `GET/POST` from your dev host (e.g. `http://localhost:8080`).
