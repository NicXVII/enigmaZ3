#!/bin/bash

# Script per test avanzati (mode=full) dell'API di cracking di EnigmaZ3
# Esegue tre test a complessità crescente senza timeout.
# Assicurarsi che il server enigma_http_server.py sia in esecuzione.

# --- Dati di base ---
# Cifriamo un testo di media lunghezza che useremo come "crib".
# Configurazione: Rotors II IV I, Reflector B, Rings 5 5 5, Positions 10 15 20, Plugboard "AP BI OY"
PLAINTEXT="THEQUICKBROWNFOXJUMPSOVERTHELAZYDOG"
echo "Cifrando il testo '$PLAINTEXT' per ottenere il ciphertext da usare nei test..."

ENCRYPT_RESPONSE=$(curl -s -X POST http://127.0.0.1:8765/encrypt \
-H "Content-Type: application/json" \
-d '{
  "rotors": ["II", "IV", "I"],
  "reflector": "B",
  "rings": [5, 5, 5],
  "positions": [10, 15, 20],
  "plugboard": "AP BI OY",
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


# --- Test 1: Facile (Full Mode) ---
# Deve trovare solo l'ordine e le posizioni di 3 rotori noti. Plugboard e anelli sono forniti.
echo "Avvio Test 1: Facile (Full)"
echo "Incognite: Ordine e posizioni di 3 rotori (pool ristretto)."
curl -X POST http://127.0.0.1:8765/crack \
-H "Content-Type: application/json" \
-d '{
  "crib": "'$PLAINTEXT'",
  "ciphertext": "'$CIPHERTEXT'",
  "mode": "full",
  "rotor_pool": ["I", "II", "IV"],
  "reflector": "B",
  "rings": [5, 5, 5],
  "plugboard": "AP BI OY"
}'
echo ""
echo "-------------------------------------------------"
echo ""


# --- Test 2: Medio (Full Mode) ---
# Deve trovare l'ordine (da un pool di 5), le posizioni e 1 coppia del plugboard.
echo "Avvio Test 2: Medio (Full)"
echo "Incognite: Ordine (da 5 rotori), posizioni, 1 coppia plugboard."
curl -X POST http://127.0.0.1:8765/crack \
-H "Content-Type: application/json" \
-d '{
  "crib": "'$PLAINTEXT'",
  "ciphertext": "'$CIPHERTEXT'",
  "mode": "full",
  "rotor_pool": ["I", "II", "III", "IV", "V"],
  "reflector": "B",
  "rings": [5, 5, 5],
  "num_plugboard_pairs": 1
}'
echo ""
echo "-------------------------------------------------"
echo ""


# --- Test 3: Molto Complesso (Full Mode) ---
# Deve trovare l'ordine (da 5 rotori), le posizioni e 3 coppie del plugboard.
echo "Avvio Test 3: Molto Complesso (Full)"
echo "Incognite: Ordine (da 5 rotori), posizioni, 3 coppie plugboard."
curl -X POST http://127.0.0.1:8765/crack \
-H "Content-Type: application/json" \
-d '{
  "crib": "'$PLAINTEXT'",
  "ciphertext": "'$CIPHERTEXT'",
  "mode": "full",
  "rotor_pool": ["I", "II", "III", "IV", "V"],
  "reflector": "B",
  "rings": [5, 5, 5],
  "num_plugboard_pairs": 3
}'
echo ""
echo "-------------------------------------------------"
echo "Tutti i test sono stati inviati. L'esecuzione potrebbe richiedere molto tempo."
