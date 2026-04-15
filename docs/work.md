Fase 1 — Simulatore Enigma (base)
Costruiamo prima una versione funzionante di Enigma in Python puro, senza Z3. L'obiettivo è avere una macchina che cifra e decifra correttamente. Partiamo con una versione semplificata (un solo rotore, niente plugboard) e poi aggiungiamo i pezzi. Alla fine di questa fase abbiamo un test che verifica: cifra un messaggio, decifra con la stessa chiave, ottieni il messaggio originale.
Fase 2 — Z3 cracker (versione base)
Prendiamo la versione semplificata di Enigma (un rotore, no plugboard) e modelliamo la decrittazione in Z3. Dato un ciphertext e un crib, Z3 deve trovare la posizione iniziale del rotore. È il proof of concept: se funziona qui, funziona anche con la versione completa.
Fase 3 — Enigma completa
Estendiamo il simulatore a 3 rotori + riflettore + plugboard. Testiamo che tutto funzioni con i parametri storici reali (rotori I, II, III della Wehrmacht, riflettore B).
Fase 4 — Z3 cracker completo
Estendiamo il solver Z3 per gestire i 3 rotori e il plugboard. Qui è dove lavoriamo sulla modellazione dei vincoli. Facciamo 3 livelli incrementali: solo posizioni rotori → rotori + poche coppie plugboard → plugboard pieno.
Fase 5 — Benchmark e grafici
Misuriamo i tempi di Z3 al variare della complessità (numero coppie plugboard, lunghezza crib). Generiamo grafici con matplotlib che mostrano la crescita dei tempi.
Fase 6 — Documentazione e pulizia
README, commenti nel codice, eventuale relazione. Tu studi il codice e ti prepari a spiegarlo.