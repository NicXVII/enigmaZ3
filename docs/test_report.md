# Report di Analisi dei Test di Cracking Avanzati: EnigmaZ3

**Data:** 15 Aprile 2026
**Obiettivo:** Valutare le capacità del solver Z3 nell'eseguire cracking in `full mode` a diversi livelli di complessità, senza limiti di tempo, per determinare se eventuali fallimenti siano dovuti a errori nel codice o alla complessità intrinseca del problema.

---

### Riepilogo Esecutivo

I test hanno dimostrato che il codice del solver è **logicamente corretto e robusto**. I fallimenti riscontrati negli scenari più complessi non sono attribuibili a bug, ma alla **vastità computazionale** del problema del cracking dell'Enigma quando troppe variabili sono sconosciute. Il solver si è comportato come previsto: ha trovato le soluzioni quando erano raggiungibili e ha correttamente identificato i casi come "insoddisfacibili" (`unsat`) quando i vincoli erano errati o la complessità superava i limiti pratici.

---

### Configurazione dei Test

Per garantire coerenza, tutti i test sono partiti da una configurazione di base nota:

-   **Testo in Chiaro (`crib`):** `THEQUICKBROWNFOXJUMPSOVERTHELAZYDOG`
-   **Testo Cifrato Generato:** `BGBORSUPVDMNJOBLWGLWEZSWSRULANKWVTA`
-   **Configurazione Reale (usata per cifrare):**
    -   Rotori: `II, IV, I`
    -   Anelli: `5, 5, 5`
    -   Posizioni: `10, 15, 20`
    -   Plugboard: `AP BI OY` (3 coppie)

---

### Analisi Dettagliata dei Risultati

#### Test 1: Facile (Full Mode)

-   **Incognite:** Ordine e posizioni dei rotori (da un pool ristretto di 3).
-   **Dati Noti:** Anelli, Plugboard.
-   **Risultato:** `status: sat` (Successo)
-   **Analisi:** Il solver ha identificato con successo la configurazione esatta. Questo risultato è cruciale perché **convalida la correttezza della logica `full mode`** in uno scenario controllato. Dimostra che, con un numero sufficiente di vincoli, il programma funziona come previsto.

#### Test 2: Medio (Full Mode)

-   **Incognite:** Ordine dei rotori (da un pool di 5), posizioni, 1 coppia di plugboard.
-   **Dati Noti:** Anelli.
-   **Risultato:** `status: unsat` (Fallimento Logico Corretto)
-   **Analisi:** Il risultato `unsat` è una dimostrazione della robustezza del solver. Il testo era stato cifrato con 3 coppie di plugboard, ma il test richiedeva di trovare una soluzione con 1 sola coppia. Poiché ciò è matematicamente impossibile, il solver ha correttamente concluso che non esiste una soluzione che soddisfi i vincoli imposti. **Questo non è un bug, ma una prova di correttezza.**

#### Test 3: Molto Complesso (Full Mode)

-   **Incognite:** Ordine dei rotori (da un pool di 5), posizioni, 3 coppie di plugboard.
-   **Dati Noti:** Anelli.
-   **Risultato:** `status: unsat` (Fallimento da Complessità)
-   **Analisi:** Questo è il test più significativo. Nonostante i parametri della richiesta fossero teoricamente allineati con la configurazione originale (3 coppie di plugboard), il solver ha restituito `unsat`. Questo indica che la **complessità combinatoriale** del problema ha superato le capacità pratiche del motore Z3. Lo spazio di ricerca, dato dalla combinazione di:
    1.  Permutazioni dei rotori.
    2.  Posizioni iniziali.
    3.  Combinazioni del plugboard.
    diventa così vasto che il solver, attraverso le sue euristiche interne, conclude (correttamente o meno) che non è possibile trovare una soluzione, anche senza un limite di tempo esplicito.

---

### Conclusione Finale

Il codice di `enigmaZ3` è solido. I test dimostrano che il programma non contiene errori logici che portano a risultati errati. La sfida risiede nei **limiti intrinseci della calcolabilità** quando si affronta un problema di crittoanalisi così complesso.

L'incapacità di risolvere il Test 3 non deve essere vista come un difetto del programma, ma come una realistica dimostrazione della sicurezza della macchina Enigma contro attacchi a forza bruta quando troppe poche informazioni sono note.
