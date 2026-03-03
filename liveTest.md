# PROMPT: Genera script demo interattivo per progetto Enigma + Z3

## Contesto
Ho un progetto Python che simula la macchina Enigma e usa Z3 (SMT solver) per crackarla.
Il progetto ha questa struttura:

```
enigmaZ3/
├── enigma/
│   ├── __init__.py          # esporta Rotor, Reflector, Plugboard, EnigmaMachine, SimpleEnigma
│   ├── rotor.py             # classe Rotor con forward(), backward(), step(), is_at_notch(), reset()
│   │                        # costanti: ROTOR_WIRINGS = {"I": "EKMF...", ...}, ROTOR_NOTCHES = {"I": "Q", ...}
│   │                        # factory: Rotor.from_name("I", ring=0, position=5)
│   ├── reflector.py         # classe Reflector con reflect(), factory from_name("B")
│   │                        # costante: REFLECTOR_WIRINGS = {"B": "YRUH...", "C": "..."}
│   ├── plugboard.py         # classe Plugboard con swap(int) -> int, init con lista di coppie
│   └── machine.py           # EnigmaMachine(rotors=[left,middle,right], reflector, plugboard)
│                            #   - _step_rotors(): double-stepping mechanism
│                            #   - encrypt_char(c: str) -> str
│                            #   - process(text: str) -> str
│                            #   - reset(positions: tuple[int,int,int])
├── cracker/
│   ├── __init__.py
│   ├── simple_cracker.py    # crack_simple_enigma(ciphertext, crib, rotor_wiring="I", reflector_wiring="B") -> int|None
│   └── full_cracker.py      # crack_rotor_positions(ciphertext, crib, rotor_names, reflector_name, 
│                            #     plugboard_pairs=None, ring_settings=(0,0,0)) -> tuple[int,int,int]|None
│                            # crack_with_plugboard(ciphertext, crib, rotor_names, reflector_name,
│                            #     num_plugboard_pairs, ring_settings, solver_timeout_ms) -> (positions, pairs)|None
```

## Cosa deve fare lo script

Crea un file `interactive_demo.py` nella root del progetto. Lo script è una demo interattiva
da terminale pensata per essere eseguita durante un esame orale universitario.

### Flusso esatto:

**STEP 1 — Input utente**
- Chiedi all'utente di inserire una parola o frase (solo lettere A-Z, converti in maiuscolo)
- Usa configurazione Enigma di default: rotori I,II,III, posizioni (5,10,20), rings (0,0,0), 
  riflettore B, plugboard [("A","Z"), ("B","Y")]
- Stampa un riepilogo della configurazione usata

**STEP 2 — Cifratura con trace del segnale**
- Per OGNI lettera del plaintext, mostra il percorso completo del segnale attraverso Enigma:
  ```
  [1] H  (rotori: F-K-U)
      H → G → P → L → J → T → E → O → Q → G → G
      Input → Plugboard → Rotor III → Rotor II → Rotor I → Reflector → Rotor I → Rotor II → Rotor III → Plugboard → Output
  ```
- Ogni riga mostra: indice, lettera input, posizioni rotori correnti, poi la catena di trasformazioni
- Usa colori ANSI: ciano per input, giallo per reflector, verde per output, dim per passaggi intermedi
- Alla fine mostra plaintext e ciphertext affiancati
- Verifica e stampa che nessuna lettera si è cifrata in sé stessa (proprietà fondamentale di Enigma)

**STEP 3 — Verifica simmetria**
- Ricrea la macchina con la STESSA configurazione
- Cifra il ciphertext ottenuto al passo 2
- Mostra che il risultato è identico al plaintext originale
- Stampa: "✓ Enigma è simmetrica: cifrare con la stessa chiave = decifrare"

**STEP 4 — Cracking con Z3**
- Ora "fingi" di non conoscere le posizioni dei rotori
- Mostra: ciphertext (noto), crib/plaintext (noto), rotori e plugboard (noti), posizioni = ???
- Lancia crack_rotor_positions() con il ciphertext e il plaintext come crib
- Misura il tempo di esecuzione
- Mostra le posizioni trovate da Z3 vs quelle reali
- Se corrispondono stampa: "✓ Z3 ha trovato la configurazione in X.XXXs"

**STEP 5 — Decifratura finale**
- Usa le posizioni trovate da Z3 per costruire una nuova macchina
- Decifra il ciphertext
- Mostra il risultato e conferma che corrisponde al plaintext originale
- Stampa: "✓ Cerchio completo: Input → Cifra → Crack → Decifra → Input originale"

### Requisiti tecnici

- File singolo, nessuna dipendenza esterna oltre a quelle del progetto (enigma, cracker)
- Colori ANSI (con fallback se il terminale non li supporta)
- La trace del segnale deve essere implementata MANUALMENTE accedendo ai componenti 
  (rotor.forward, rotor.backward, reflector.reflect, plugboard.swap) — NON usare 
  encrypt_char() perché non espone i passaggi intermedi
- Il double-stepping dei rotori va replicato prima di ogni lettera:
  ```python
  if middle.is_at_notch():
      middle.step()
      left.step()
  elif right.is_at_notch():
      middle.step()
  right.step()
  ```
- Lo step avviene PRIMA della cifratura (come nella vera Enigma)
- Per il cracking usa crack_rotor_positions() dal modulo cracker.full_cracker
- Gestisci eventuali errori (input vuoto, cracking fallito)
- Aggiungi una piccola pausa (0.05s) tra ogni lettera nella trace per effetto drammatico

### Formato output desiderato

```
══════════════════════════════════════════════
   ENIGMA + Z3 — Demo Interattiva
══════════════════════════════════════════════

Inserisci un messaggio: HELLO

── Configurazione ─────────────────────────────
  Rotori:     I, II, III
  Posizioni:  (5, 10, 20)
  Rings:      (0, 0, 0)
  Riflettore: B
  Plugboard:  A↔Z, B↔Y

── FASE 1: Cifratura ──────────────────────────

  [1] H  (rotori: F-K-U)
      H → G → P → L → J → T → E → O → Q → G → G
  
  [2] E  (rotori: F-K-V)
      E → E → M → ... → X → X

  ...

  Plaintext:  HELLO
  Ciphertext: GXQRO
  ✓ Nessuna lettera si è cifrata in sé stessa

── FASE 2: Verifica simmetria ─────────────────

  Ciphertext → Enigma(stessa chiave) → HELLO
  ✓ Enigma è simmetrica

── FASE 3: Cracking con Z3 ───────────────────

  Conosciamo: ciphertext = GXQRO
              crib       = HELLO
              rotori     = I, II, III
              plugboard  = A↔Z, B↔Y
  Cerchiamo:  posizioni  = ???

  Z3 sta risolvendo... 0.042s
  
  Posizioni trovate: (5, 10, 20)
  Posizioni reali:   (5, 10, 20)
  ✓ Z3 ha trovato la configurazione esatta!

── FASE 4: Decifratura con chiave trovata ─────

  GXQRO → Enigma(5, 10, 20) → HELLO
  ✓ Cerchio completo: Input → Cifra → Crack → Decifra → Input originale

══════════════════════════════════════════════
```

### Note importanti per l'implementazione
- ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" per conversione indice ↔ lettera
- Le posizioni dei rotori si mostrano come lettere (posizione 5 = F)
- Il plugboard con coppie [("A","Z"), ("B","Y")] significa che A e Z sono scambiate, B e Y sono scambiate
- Nella trace, mostra sia le lettere che i nomi degli stadi
- Usa box-drawing characters (═, ─, ║, ╔, ╗, ╚, ╝) per i bordi