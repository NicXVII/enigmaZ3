#!/bin/bash

# Script per testare l'API di cracking di EnigmaZ3
# Assicurarsi che il server enigma_http_server.py sia in esecuzione su http://127.0.0.1:8765

# --- Dati di base ---
# Usiamo prima l'endpoint /encrypt per generare un testo cifrato su cui lavorare.
# Configurazione: Rotors I II III, Reflector B, Rings 0 0 0, Positions 5 10 15, Plugboard "AB CD EF"
PLAINTEXT="HELLOWORLDFROMTHECLI"
echo "Cifrando il testo '$PLAINTEXT' per ottenere il ciphertext da usare nei test..."

ENCRYPT_RESPONSE=$(curl -s -X POST http://127.0.0.1:8765/encrypt \
-H "Content-Type: application/json" \
-d '{
  "rotors": ["I", "II", "III"],
  "reflector": "B",
  "rings": [0, 0, 0],
  "positions": [5, 10, 15],
  "plugboard": "AB CD EF",
  "text": "'$PLAINTEXT'"
}')

CIPHERTEXT=$(echo $ENCRYPT_RESPONSE | sed -n 's/.*"ciphertext": *"\([^"]*\)".*/\1/p')

if [ -z "$CIPHERTEXT" ]; then
    echo "Errore: Impossibile ottenere il ciphertext dal server. Verifica che sia in esecuzione."
    exit 1
fi

echo "Testo cifrato ottenuto: $CIPHERTEXT"
echo "-------------------------------------------------"
echo ""


# --- Test 1: Facile (mode: positions) ---
# Rotori, anelli e plugboard noti. Deve trovare solo le posizioni.
echo "Avvio Test 1: Facile (mode=positions)"
echo "Trova solo le posizioni dei rotori. Dovrebbe essere molto veloce."
curl -X POST http://127.0.0.1:8765/crack \
-H "Content-Type: application/json" \
-d '{
  "crib": "'$PLAINTEXT'",
  "ciphertext": "'$CIPHERTEXT'",
  "mode": "positions",
  "rotors": ["I", "II", "III"],
  "reflector": "B",
  "rings": [0, 0, 0],
  "plugboard": "AB CD EF",
  "timeout_ms": 20000
}'
echo ""
echo "-------------------------------------------------"
echo ""


# --- Test 2: Medio (mode: plugboard) ---
# Rotori e anelli noti. Deve trovare il plugboard (3 coppie).
echo "Avvio Test 2: Medio (mode=plugboard)"
echo "Trova il plugboard (3 coppie). Richiederà più tempo."
curl -X POST http://127.0.0.1:8765/crack \
-H "Content-Type: application/json" \
-d '{
  "crib": "'$PLAINTEXT'",
  "ciphertext": "'$CIPHERTEXT'",
  "mode": "plugboard",
  "rotors": ["I", "II", "III"],
  "reflector": "B",
  "rings": [0, 0, 0],
  "positions": [5, 10, 15],
  "num_plugboard_pairs": 3,
  "timeout_ms": 60000
}'
echo ""
echo "-------------------------------------------------"
echo ""


# --- Test 3: Difficile (mode: full, ma semplificato) ---
# Ordine rotori e posizioni sconosciuti, ma plugboard noto.
echo "Avvio Test 3: Difficile ma semplificato (mode=full)"
echo "Trova ordine rotori e posizioni (plugboard noto). Dovrebbe avere successo."
curl -X POST http://127.0.0.1:8765/crack \
-H "Content-Type: application/json" \
-d '{
  "crib": "HELLOWORLD",
  "ciphertext": "'$(echo $CIPHERTEXT | cut -c 1-10)'",
  "mode": "full",
  "rotor_pool": ["I", "II", "III"],
  "reflector": "B",
  "rings": [0, 0, 0],
  "plugboard": "AB CD EF",
  "timeout_ms": 120000
}'
echo ""
echo "-------------------------------------------------"
echo "Tutti i test sono stati inviati."
