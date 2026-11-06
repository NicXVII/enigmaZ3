# EnigmaZ3 — guida alla codebase per l’orale

Questo documento spiega il progetto così come è nel repository, file per file. L’obiettivo è poterlo raccontare a voce: prima l’idea, poi il percorso di una lettera, poi come Z3 e la ricerca ricostruiscono la chiave.

## Cosa dire nei primi 60 secondi

EnigmaZ3 è un simulatore della macchina Enigma a tre rotori e un cracker che, dato un pezzo di testo in chiaro noto (il *crib*) e il cifrato corrispondente, ricostruisce parte della chiave.

La macchina storica è fatta di quattro pezzi: lo **steckerbrett** (plugboard), tre **rotori**, un **riflettore**. Ogni tasto fa avanzare i rotori prima di cifrare. Il segnale entra dal plugboard, attraversa i rotori da destra a sinistra, rimbalza sul riflettore, torna indietro e esce di nuovo dal plugboard.

Due proprietà ci interessano:

1. **Simmetria.** Con la stessa chiave, cifrare due volte restituisce il testo originale. Cifrare e decifrare sono la stessa operazione, a patto di ripartire dalle stesse posizioni.
2. **Una lettera non si cifra mai in sé stessa.** Il riflettore non ha punti fissi, quindi `A` non può diventare `A`.

Il cracker usa queste regole come vincoli. Quando rotori, anelli e plugboard sono noti, modelliamo la cifratura in **Z3**, un solver SMT: gli diamo le tre posizioni iniziali e gli chiediamo un’assegnazione che faccia coincidere crib e ciphertext. Se Z3 non risponde in tempo, una scansione delle 17576 posizioni chiude il caso. Se invece il plugboard è ignoto, le posizioni si provano una a una e i cavi si ricostruiscono con un backtracking.

L’interfaccia web mostra il percorso del segnale nel browser. La ricerca della chiave la fa il server Python.

## Mappa del repository

```text
enigma/          modello della macchina (Python)
cracker/         ricostruzione della chiave (Z3 + ricerca)
scripts/         CLI, server HTTP, demo da terminale
frontend_v2/     pagina web: animazione + chiamata al cracker
docs/            questa guida, API HTTP, note di demo
.github/         CI: pytest, coverage, ruff, mypy
```

Dipendenze di runtime: `z3-solver`. Il server HTTP non usa framework: è `http.server` della libreria standard.

Le lettere sono sempre interi `0..25` (`A=0`). I caratteri che non sono lettere vengono ignorati.

## Come è fatta la chiave

Per la macchina completa la chiave è:

| Pezzo | Valori nel progetto | Ruolo |
|---|---|---|
| Ordine rotori | tre nomi tra `I`–`V`, da lento a veloce | permutazione dei contatti |
| Posizioni | tre interi `0..25` | finestra visibile, avanza a ogni tasto |
| Anelli (Ringstellung) | tre interi `0..25` | sfasano il cablaggio rispetto alla finestra |
| Riflettore | `B` o `C` | rimanda il segnale indietro |
| Plugboard | fino a 13 coppie, storicamente circa 10 | scambia lettere in entrata e in uscita |

Ordine dei rotori nel codice: `[sinistro, medio, destro]`. Il destro è il veloce e avanza sempre. Il medio avanza quando il destro è sulla tacca. Il sinistro avanza quando il medio è sulla tacca. Questo è il **double-stepping**: se il medio è già sulla tacca, al tasto successivo avanzano medio e sinistro insieme, anche se il destro non sta “spingendo” il medio in quel momento.

Percorso di una lettera, dopo lo step:

`plugboard → destro → medio → sinistro → riflettore → sinistro → medio → destro → plugboard`

## Package `enigma/`

È il simulatore. Non conosce Z3. Espone, da `enigma/__init__.py`: `Rotor`, `Reflector`, `Plugboard`, `EnigmaMachine`, `SimpleEnigma`.

### `enigma/rotor.py`

Costanti storiche Wehrmacht:

- `ROTOR_WIRINGS`: la stringa di 26 lettere è la permutazione. La posizione `i` della stringa dice dove va la lettera `i`. Per il rotore I, `E` in prima posizione significa che `A` (indice 0) va in `E`.
- `ROTOR_NOTCHES`: la tacca. I=`Q`, II=`E`, III=`V`, IV=`J`, V=`Z`. Quando la finestra mostra quella lettera, il rotore a sinistra è pronto a scattare al prossimo passo.

`Rotor` conserva:

- `forward_map` e `inverse_map`, precalcolati, così il ritorno del segnale non ricalcola la permutazione inversa ogni volta;
- `notch`, `ring`, `position` come interi `0..25`.

Metodi:

- `from_name("I", ring, position)` costruisce un rotore storico.
- `is_at_notch()` è vero se `position == notch`.
- `step()` ricorda se era sulla tacca, poi fa `(position + 1) % 26`, e restituisce quel booleano. La macchina completa non usa il valore di ritorno: decide gli scatti guardando `is_at_notch()` prima di muovere.
- `forward(c)` è il segnale da destra verso sinistra.
- `backward(c)` è il ritorno, con la mappa inversa.
- `reset(position)` riporta la finestra a una posizione, senza toccare anello né cablaggio.

La formula di `forward` è il punto da saper spiegare:

```text
ingresso_nel_cablaggio = (lettera + posizione - anello) mod 26
uscita_cablaggio = wiring[ingresso_nel_cablaggio]
lettera_in_uscita = (uscita_cablaggio - posizione + anello) mod 26
```

Posizione e anello non cambiano i fili: spostano quale filo è allineato al contatto fisso. `backward` fa la stessa cosa con la permutazione inversa. Se posizione e anello sono gli stessi, `backward(forward(x)) = x`.

### `enigma/reflector.py`

`REFLECTOR_WIRINGS` ha `B` e `C`. `Reflector.reflect(c)` è una lettura diretta della tabella. Il riflettore è un’involuzione senza punti fissi: applica due volte torna all’ingresso, e nessuna lettera resta ferma. È questo che impedisce l’auto-cifratura dell’intera macchina, perché il rimbalzo non può chiudersi sulla stessa lettera.

### `enigma/plugboard.py`

`Plugboard` parte dall’identità (`0→0`, `1→1`, …) e, per ogni coppia `(A,B)`, scambia i due indici. `swap` è quindi un’involuzione: applicarlo due volte, in entrata e in uscita, è coerente con la simmetria di Enigma. Le lettere non cablate restano ferme. Il massimo storico è 13 coppie, perché ogni coppia consuma due lettere.

### `enigma/machine.py`

Due classi, due livelli di fedeltà.

**`SimpleEnigma`** ha un solo rotore e un riflettore. Niente plugboard, niente double-step. Serve come modello didattico e come bersaglio del primo cracker. `encrypt_char` fa: step del rotore, avanti, riflettore, indietro. `process` tiene solo le lettere. `reset` rimette la posizione iniziale, ed è indispensabile per dimostrare la simmetria: dopo la cifratura i rotori sono andati avanti, quindi per decifrare bisogna riportarli all’inizio.

**`EnigmaMachine`** è la macchina a tre rotori. `_step_rotors`:

```text
se il medio è sulla tacca:
    avanza medio e sinistro
altrimenti, se il destro è sulla tacca:
    avanza il medio
avanza sempre il destro
```

Il ramo `elif` evita di far scattare il medio due volte quando sia il medio sia il destro sono sulla tacca: in quel caso il double-step ha già mosso il medio.

`encrypt_char` esegue lo step e poi il percorso completo descritto sopra. `process` e `reset(sinistra, medio, destra)` chiudono l’API.

Frase utile: «Encrypt e decrypt nel programma sono la stessa funzione. La decifratura è una seconda cifratura con le posizioni rimesse a zero.»

## Package `cracker/`

`cracker/__init__.py` esporta:

- `crack_simple_enigma`
- `crack_rotor_positions`
- `crack_with_plugboard`

Il crib è un plaintext noto allineato all’inizio del ciphertext. Più è lungo, più vincoli abbiamo e meno chiavi false sopravvivono. Tutte le funzioni normalizzano il testo in maiuscolo e scartano ciò che non è una lettera.

### `cracker/simple_cracker.py` — un rotore, solo Z3

`crack_simple_enigma(ciphertext, crib, rotor_wiring="I", reflector_wiring="B")` cerca la posizione iniziale di `SimpleEnigma`.

Variabile simbolica: `start_pos`, intero in `0..25`.

Per la lettera di indice `i`, il rotore ha già fatto `i + 1` scatti, quindi la posizione effettiva è `(start_pos + i + 1) mod 26`. L’anello qui è 0.

Z3 non ha una “tabella di permutazione” comoda da indicizzare con un simbolo, e lo spazio è solo 26 valori. Il codice quindi, per ogni lettera del crib, costruisce un `Or` di 26 casi: «se la posizione effettiva vale `v`, allora la cifratura concreta con quel `v` deve essere la lettera cifrata». `Solver.check()` risponde `sat` oppure no. Se è `sat`, `model[start_pos]` è la posizione.

Questo è il cracker più facile da raccontare: una variabile, vincolo di range, un caso per ogni posizione possibile, congiunzione su tutte le lettere del crib.

### `cracker/full_cracker.py` — macchina completa

Il file ha tre livelli di ricerca e un nucleo condiviso che sa cifrare sia in modo simbolico sia in modo numerico. I due nuclei devono coincidere con `EnigmaMachine`, altrimenti il solver troverebbe chiavi che la macchina vera non produce.

#### Tabelle e lookup

- `_wiring`, `_inv_wiring`, `_reflector` sono memoizzati con `lru_cache`: le permutazioni storiche non cambiano.
- `_z3_lookup(table, indice_simbolico)` costruisce una catena di `If`: «se l’indice è 0, tabella[0], altrimenti se è 1, tabella[1], …». È così che una permutazione costante entra in una formula Z3.
- `_z3_mod26` è il modulo 26 sulle espressioni simboliche.

#### Step e cifratura, due volte

`_compute_positions` e `_compute_positions_numeric` applicano lo stesso double-step. La versione Z3 usa `Or` e `If`; la versione numerica usa booleani Python. Per ogni indice del crib producono la posizione di sinistra, medio e destro **dopo** lo scatto di quella lettera.

`_encrypt_char_z3` e `_encrypt_core_numeric` cifrano il nucleo rotori + riflettore, senza plugboard. L’ordine è quello della macchina: destro, medio, sinistro, riflettore, e ritorno. Gli anelli entrano nella stessa formula di `Rotor.forward` / `backward`.

Il plugboard, quando è noto, sta fuori dal nucleo. Dato che è un’involuzione, il vincolo

```text
nucleo(plug(plaintext)) == plug(ciphertext)
```

è equivalente a far passare il segnale nel plugboard in entrata e in uscita. `_build_plug_table` costruisce questa tabella e rifiuta coppie in conflitto.

#### Livello 1 — `crack_rotor_positions`

Cerca solo le tre posizioni iniziali. Rotori, anelli, riflettore e plugboard sono noti (il plugboard può essere vuoto).

Passi, gli stessi che il codice annota come Step 1–7:

1. Normalizza crib e ciphertext. Se il crib è vuoto o il cifrato è più corto, esce.
2. Carica wiring, tacche, anelli.
3. Crea `left0`, `middle0`, `right0`, ciascuna in `0..25`. Lo spazio è `26³ = 17576`.
4. Per ogni lettera del crib aggiunge `cifratura_simbolica == lettera_cifrata`.
5. `s.check()` con un timeout (`solver_timeout_ms`, default 50 ms in questa funzione; la CLI e il server lo alzano).
6. Se Z3 è `sat`, rilegge il modello e lo **riverifica** con `_matches_candidate_numeric`. Se il replay non torna, il candidato viene scartato. Questo controllo esiste perché la formula simbolica e la macchina numerica devono dire la stessa cosa.
7. Se Z3 non risponde in tempo, o il modello non regge, e `allow_numeric_fallback` è vero, scorre le 17576 posizioni (o un sottoinsieme `numeric_search_limit`) e restituisce la prima che cifra il crib nel ciphertext. `_iter_position_candidates`, se il limite è parziale, non parte da `(0,0,0)` in ordine: cammina con passo 7919 modulo 17576, così un budget piccolo non guarda solo le posizioni basse.

Ritorno: `(sinistra, medio, destra)` oppure `None`.

`progress_callback` è opzionale e serve a stampare questi passi, per esempio in una demo.

#### Livello 2 — `crack_with_plugboard`

Qui rotori, anelli e riflettore sono noti. Sono ignoti le posizioni **e** le coppie del plugboard. Si conosce solo `num_plugboard_pairs` (0–13).

Questa funzione **non** costruisce un modello Z3 del plugboard. Lo dice esplicitamente nel docstring: forza bruta sulle posizioni, poi backtracking sui cavi.

Perché: con le posizioni fissate, il nucleo rotori+riflettore è una permutazione nota di 26 lettere. Resta solo da trovare un plugboard compatibile con il crib. Per ogni lettera, se `p` è il chiaro e `c` il cifrato, esiste una lettera interna `x` tale che:

```text
plug(p) = x
nucleo(x) = y
plug(y) = c
```

e il numero di coppie vere (quelle con `a != b`) non supera il massimo.

Dettaglio delle funzioni:

- `_assign_plug_pair` scrive `a↔b` nel mapping parziale. Fallisce se contraddice un cavo già messo, o se servirebbe una coppia in più oltre il massimo.
- `_x_candidates` restringe i valori possibili di `x`: se `p` è già cablata, `x` è obbligato; se le coppie sono esaurite, `x` deve essere `p` (lettera non scambiata); se `c` è già cablata, `x` si ricava invertendo il nucleo.
- `_solve_plugboard_constraints` è il backtracking. Sceglie prima il vincolo più ristretto (quello con un solo candidato) e prova gli `x` possibili. Ha una deadline: se scade, ritorna un marcatore di timeout e la ricerca intera si ferma.

Prima di cercare, se una lettera del crib è uguale alla corrispondente del ciphertext, la funzione ritorna `None`: quella coppia è impossibile per Enigma.

Per non ricalcolare il nucleo, le permutazioni già viste per una terna di posizioni dei rotori stanno in `core_table_cache`.

Ritorno: `((posizioni), [(coppie)])` oppure `None`. `None` significa «non trovata entro il timeout», non sempre «matematicamente impossibile».

Frase utile: «Z3 è il primo tentativo sulle posizioni, preciso e a timeout corto. La scansione delle 17576 posizioni è il piano B. Il plugboard ignoto è un altro algoritmo: backtracking, non SMT. Rotori, anelli e riflettore restano noti.»

## Script

Stanno in `scripts/`. Importano `enigma` e `cracker`, che stanno nella root. Vanno lanciati con la root del repo nel `PYTHONPATH`. Esempio che usiamo in locale:

```bash
PYTHONPATH=. .venv/bin/python scripts/enigma_http_server.py
PYTHONPATH=. .venv/bin/python scripts/enigma_cli.py --help
```

### `scripts/enigma_cli.py`

Parser `argparse` con tre comandi.

- `encrypt` e `decrypt` chiamano **la stessa** funzione `_cmd_encrypt_like`. È voluto: è la dimostrazione della simmetria. Costruiscono `EnigmaMachine` e stampano `process(text)`.
- `crack --mode positions` chiama `crack_rotor_positions` e stampa JSON `{"positions": [s, m, d]}` oppure `null`.
- `crack --mode plugboard` chiama `crack_with_plugboard`. JSON con `positions` e `plugboard_pairs`, oppure `{"result": null}`.

I parser (`_parse_triplet`, `_parse_rotors`, `_parse_pairs`) rifiutano rotori sconosciuti, valori fuori da `0..25`, coppie mal formate e lettere ripetute sul plugboard. Gli errori di validazione escono con codice 2; un’eccezione inattesa con codice 1.

### `scripts/enigma_http_server.py`

API per la pagina web. Nessuna dipendenza oltre a `enigma` e `cracker`.

- `GET /` e `GET /health` → nome del servizio e elenco endpoint.
- `POST /encrypt` → `handle_encrypt` → `{"ciphertext", "ok": true}`.
- `POST /crack` → `handle_crack`.
- `OPTIONS` risponde 204 con gli header CORS, così il browser su un’altra porta (8080) può chiamare la 8765.

`handle_crack` accetta `mode`: `positions` o `plugboard`.

- `positions`: plugboard noto o vuoto, rotori e anelli presi dal JSON.
- `plugboard`: usa `num_plugboard_pairs`. Rotori e anelli restano quelli inviati.

Risposta `sat` con rotori, posizioni, anelli, plugboard e liste `constraints_used`. Risposta `unsat` se non trova nulla o se il crib è inutilizzabile. Un’eccezione diventa HTTP 500 con `{"error": ...}`.

`constraints_used` è un’etichetta per la UI, non un vincolo calcolato a parte. I vincoli veri sono nel codice del cracker. Le cinque etichette sono: plugboard involuzione, riflettore senza punti fissi, double-step, niente auto-cifratura, coerenza crib-ciphertext. In modalità `positions` toglie la voce sul plugboard, perché lì il plugboard non è incognito.

### `scripts/interactive_demo.py`

Demo da terminale, pensata per l’orale. Chiede un messaggio e usa una chiave fissa: rotori I, II, III, posizioni `(5, 10, 20)`, anelli `(0, 0, 0)`, riflettore B, plugboard `A↔Z` e `B↔Y`.

Quattro fasi:

1. Cifra lettera per lettera **senza** chiamare `encrypt_char`. `encrypt_with_manual_trace` fa lo step a mano e poi chiama `plugboard.swap`, `forward`, `reflect`, `backward`. Stampa la catena e controlla che nessuna lettera sia uguale a sé stessa.
2. Ricrea la macchina dalle stesse posizioni e cifra il ciphertext: deve tornare il plaintext.
3. Dimentica le posizioni e chiama `crack_rotor_positions` con il plaintext come crib. Confronta il risultato con `(5, 10, 20)` e misura il tempo.
4. Decifra con le posizioni trovate e mostra che si ritorna al messaggio.

`Ansi` colora input, riflettore e output se il terminale lo supporta. C’è una pausa di 0,05 s tra una lettera e l’altra.

### `scripts/run_quality.sh`

Lancia pytest (con coverage se c’è `pytest-cov`), ruff e mypy. È il controllo di qualità locale, non serve per la demo.

## Frontend `frontend_v2/`

Pagina statica. Va aperta via HTTP, non come file locale, perché `app.js` è un modulo ES. In locale: porta 8080 per la pagina, porta 8765 per l’API.

### `index.html`

Tre momenti, in ordine: scelta della chiave (rotori, finestre, anelli, riflettore, plugboard), cifratura con la striscia del percorso, ricerca Z3 con crib, modalità e numero di coppie. Tailwind è caricato da CDN; `styles.css` definisce la striscia del segnale (nodo acceso, nodo già passato, barra).

### `simulator.js`

È la stessa macchina del package Python, riscritta in JavaScript, con gli stessi wiring e le stesse tacche. Esiste perché l’animazione deve vedere ogni tappa; `encrypt_char` di Python restituisce solo la lettera finale, e chiamare il server per ogni lampadina sarebbe inutile.

Classi: `Rotor`, `Reflector`, `Plugboard`, `EnigmaMachine`. `encryptCharWithTrace` fa lo step e registra nove tappe: plug in, tre rotori in andata, riflettore, tre rotori al ritorno, plug out. Ogni tappa ha `stage`, lettera di ingresso e lettera di uscita. `parsePlugboard` accetta `AZ BY` oppure `AZ,BY`. `buildMachineFromUI` traduce l’oggetto letto dal form.

Il `+ 260000` prima del modulo 26 è solo per non ottenere un resto negativo in JavaScript. Il risultato modulo 26 è lo stesso della formula Python.

### `app.js`

Tiene la macchina corrente e collega i pulsanti.

- `readConfig` legge il form.
- `fillRotorSelects` riempie i tre menu con I–V, default I, II, III.
- `syncPositionLabels` mostra la lettera della finestra accanto allo slider (`0` → `A`).
- `resetMachine` ricostruisce la macchina dalla configurazione corrente, così ogni cifratura riparte dalle posizioni scelte.
- `initPathStrip` disegna i nove nodi. `animateSteps` li accende uno alla volta ogni 70 ms. Il radio `anim` può limitarsi all’ultima lettera senza animazione.

`onEncrypt` **non** chiama il server. Gira `encryptCharWithTrace` nel browser per ogni lettera, scrive il ciphertext nel riquadro e anima l’ultima lettera. Le finestre in alto si aggiornano con la posizione finale dei rotori.

`onCrack` legge il crib e il ciphertext appena prodotto, manda `POST /crack` con la configurazione del form e la modalità scelta (`positions` o `plugboard`). La barra verde è un timer di facciata: sale da sola fino al 92% mentre aspetta la risposta, poi va al 100% quando arriva il JSON. Non è il progresso interno di Z3. Se la risposta è `sat`, mostra rotori, posizioni, anelli e coppie. Se è `unsat` o il server non risponde, lo dice nel riquadro.

### `api.js`

`postEncrypt` e `postCrack` fanno `fetch` verso `http://127.0.0.1:8765`, a meno che la pagina definisca `window.ENIGMA_API_BASE`. Stringa vuota disattiva l’API: l’encrypt locale resta possibile, il crack tira un errore, salvo `window.ENIGMA_USE_MOCK_CRACK`, che restituisce una risposta finta. La pagina attuale usa solo `postCrack`. `postEncrypt` resta disponibile se qualcuno volesse cifrare sul server.

## CI e configurazione

`.github/workflows/ci.yml` su push e pull request, Python 3.12: installa `requirements-dev.txt`, poi pytest con coverage su `enigma` e `cracker`, ruff, mypy.

`pyproject.toml` fissa le opzioni di pytest, coverage, ruff (lunghezza 100, target 3.12) e mypy. `requirements.txt` è solo `z3-solver`. `requirements-dev.txt` aggiunge pytest, coverage, ruff, mypy.

`docs/BACKEND.md` è il contratto JSON di `/encrypt` e `/crack`. `docs/test_orale_proposte.md` è la scaletta dei comandi, non la spiegazione del codice.

## Percorso da raccontare con la demo web

1. Imposto rotori, posizioni, anelli, riflettore, due coppie sul plugboard.
2. Scrivo un messaggio e cifro. Mostro la striscia: il segnale non esce dal rotore veloce e basta, va fino al riflettore e torna. Le finestre sono avanzate.
3. Dico che il ciphertext l’ha calcolato il simulatore JavaScript, gemello di quello Python, così l’animazione non dipende dalla rete.
4. Metto come crib l’inizio del messaggio. Modalità `positions`: Z3, o il fallback numerico, deve ritrovare le tre posizioni. Rotori, anelli e plugboard glieli stiamo dando.
5. Se c’è tempo, modalità `plugboard`: gli nascondiamo i cavi e gli diciamo solo quante coppie ci sono. Lì non è più solo Z3: è una scansione delle posizioni più un backtracking sui cavi.
6. Ricifro il ciphertext con la chiave trovata, dopo aver rimesso le posizioni, e torna il testo.

## Domande probabili, risposte corte

**Perché Z3 e non solo i 17576 cicli?**  
Per le sole posizioni il brute force basta, e infatti c’è. Z3 serve a scrivere la cifratura come formula: double-step, anelli e permutazioni diventano vincoli, e il solver cerca un modello. Il timeout corto evita di restare bloccati; se non risponde, il numerico chiude il caso. Appena l’incognita non è solo la posizione, 17576 non basta più e la formula, o il backtracking, diventano il modo per non enumerare tutto alla cieca.

**Il plugboard lo risolve Z3?**  
No. Con i rotori fissi il nucleo è una tabella. Cerchiamo un’involuzione con al massimo N coppie coerente con ogni lettera del crib, provando prima i vincoli già determinati.

**Come fate a fidarvi del modello Z3?**  
Lo rieseguiamo con la funzione numerica, la stessa aritmetica della macchina. Se non riproduce il crib, lo buttiamo.

**Perché la stessa funzione cifra e decifra?**  
Ogni componente, a rotori fermi, è invertibile lungo lo stesso percorso: il plugboard e il riflettore sono involuzioni, e il ritorno nei rotori è l’inverso dell’andata. Rifacendo il cammino con le stesse posizioni successive si ottiene l’inverso. Bisogna però ricominciare dalle posizioni iniziali, perché durante la cifratura i rotori si sono mossi.

**Cos’è il double-step, in una frase?**  
Il medio, quando è sulla tacca, scatta insieme al sinistro al tasto successivo; il destro scatta sempre. È l’anomalia meccanica della Enigma vera, non un rotore che avanza solo ogni 26 lettere in modo regolare.

**Il frontend e il Python possono divergere?**  
I wiring sono copiati. I test di correttezza stanno sul Python. La pagina usa il JavaScript solo per mostrare il percorso e produrre il ciphertext della demo; la chiave la cerca il server.

**Cosa non ricostruite in generale?**  
Non facciamo un attacco storico completo: ordine dei rotori, anelli e plugboard da dieci coppie restano dati in ingresso, non incognite. Ci serve sempre un crib. Senza crib il problema è un altro, e non è quello che risolve questo programma.

**Cosa significa `unsat` nella UI?**  
Nessuna chiave compatibile è stata trovata entro i vincoli e il tempo. Può essere un crib troppo corto, una configurazione diversa da quella usata per cifrare, o un timeout.

## Limiti da ammettere, se li chiedono

- Il modello è la Enigma a tre rotori Wehrmacht, rotori I–V e riflettori B e C. Non ci sono il quarto rotore navale, il riflettore mobile o l’Uhr.
- `SimpleEnigma` è un modello ridotto, non una macchina storica.
- La barra di avanzamento della pagina non misura Z3.
- `None` del plugboard cracker può essere un timeout.
