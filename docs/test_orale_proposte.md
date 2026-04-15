# Proposte Test per Presentazione Orale

## Obiettivo della demo
Mostrare in modo chiaro:
- correttezza della simulazione Enigma;
- efficacia del cracking (Z3 + ricerca);
- qualita tecnica del progetto (test, lint, type-check, benchmarking).

## Pacchetto test consigliato (8-10 minuti)

### 1) Simmetria Enigma (must-have)
Dimostrazione: cifrare e poi decifrare con la stessa chiave.

Comandi:
```bash
python enigma_cli.py encrypt \
  --text "HELLOWORLD" \
  --rotors I,II,III \
  --positions 5,10,20 \
  --rings 0,0,0 \
  --reflector B \
  --plugboard AZ,BY

python enigma_cli.py decrypt \
  --text "<CIPHERTEXT_OUTPUT>" \
  --rotors I,II,III \
  --positions 5,10,20 \
  --rings 0,0,0 \
  --reflector B \
  --plugboard AZ,BY
```
Cosa dire al prof: Enigma e simmetrica, quindi stessa configurazione permette la decifratura.

### 2) Test unitari core macchina
Dimostrazione: esecuzione rapida suite principale.

Comando:
```bash
pytest tests/ -v
```
Cosa dire al prof: i test coprono comportamento dei componenti chiave (rotori, plugboard, macchina).

### 3) Crack modalita positions
Dimostrazione: recupero posizioni iniziali con crib noto.

Comando:
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
Cosa dire al prof: il solver produce un risultato verificabile in output JSON (`positions`).

### 4) Crack modalita plugboard
Dimostrazione: plugboard ignoto con numero coppie noto.

Comando:
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
Cosa dire al prof: problema piu difficile; output con `positions` e `plugboard_pairs`, oppure nessuna soluzione entro il timeout.

### 5) Crack modalita full (ranking)
Dimostrazione: confronto candidati con ordine rotori/rings ignoti.

Comando:
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
Cosa dire al prof: si vede il ranking dei candidati e la strategia ibrida tra ricerca e validazione.

### 6) Benchmark riproducibile
Dimostrazione: performance comparabile con seed fisso.

Comando:
```bash
python enigma_cli.py benchmark --csv benchmark_results.csv --png benchmark_results.png --seed 42
```
Cosa dire al prof: il seed rende il confronto stabile tra run diversi.

## Ordine consigliato durante l orale
1. Simmetria (impatto immediato).
2. Test automatici (`pytest`).
3. Crack `positions`.
4. Crack `plugboard` o `full` (in base al tempo).
5. Benchmark finale.

## Piano B (se qualcosa va storto live)
- Usare `python interactive_demo.py` per mostrare pipeline end-to-end guidata.
- Ridurre timeout e dataset per completare la demo nei tempi.
- Mostrare solo output JSON principali e spiegare i dettagli a voce.

## Checklist pre-presentazione
- Ambiente attivo e dipendenze installate.
- Comandi gia testati localmente almeno una volta.
- Esempi ciphertext/crib pronti da incollare.
- Terminale pulito con cronologia minima.
- Piano B pronto (`interactive_demo.py`).
