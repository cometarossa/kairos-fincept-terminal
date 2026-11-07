# Revisione critica Claude Code — Master Roadmap V1 → V1.1

**2026-11-07 · Revisore:** Claude Code CLI 2.1.63, Haiku, risposta generata in singola richiesta senza strumenti, a partire dal testo completo di roadmap, AGENTS e project state con numeri di riga. **Validazione successiva:** ChatGPT ha confrontato le osservazioni con i file e con le regole KAIROS recuperate direttamente da GitHub. **Limite:** Claude non ha effettuato questa volta una nuova ispezione GitHub, del sorgente o del runtime; la review NON equivale a CI, legal opinion, root-of-trust assessment o autorizzazione di merge.

## Esito

Claude considera coerente la scelta Fincept-first con decision plane headless, il ruolo indipendente del KAIROS core, la separazione di memoria/ledger e il divieto di trading. Ha proposto diverse precisazioni di dipendenza. La critica è stata applicata in modo selettivo: non ripetere gli errori dei precedenti audit Claude su MCP, scraper e presenza CI.

| Obiezione di Claude | Decisione | Perché / modifica V1.1 |
|---|---|---|
| Licenza upstream conflittuale deve avere priorità | **ACCOLTA CON LIMITE** | LEG-01 diventa inventario source-only P0; DEV-00 può documentare moduli con stato LICENSE_UNRESOLVED, ma NON integrare/distribuire asset ambigui senza chiarimento |
| Manca contratto temporale scientifico esplicito | **ACCOLTA** | Aggiunto API-SCI-00 per identità dei dati, PIT, historical-as-of, freeze prospettico e confine evaluator, prima di DATA-01/SCI-01 |
| QA-01 mescola smoke locali con CI GitHub privilegiata | **ACCOLTA** | Separato QA-LOCAL (macOS/VM senza host privileged) da QA-CI bloccata da #619/#618 e ulteriore review |
| Il fork non deve inventare autorizzazioni broker | **ACCOLTA** | AGENTS esplicita precedenza costituzione/Gate9R, STOP on conflict; IG read-only richiede approvazione esplicita dell'operatore più security/terms review |
| Memoria fixture non equivale al backend semantico live | **GIÀ DOCUMENTATO** | PR #2: 14 test Mac e mock Hindsight, nessun Hindsight/Mem0 real service, niente memoria ChatGPT connessa |
| Possibile duplicazione di componenti KAIROS | **ACCOLTA SENZA TASK EXTRA** | DEV-00 comprende inventorario di sovrapposizioni e ownership, anziché avviare un ulteriore backlog parallelo |
| PORT-01 ha metriche di successo insufficienti | **ACCOLTA** | Specificati HOLD/astensione, tail-loss, drawdown, expected shortfall, correlazione, stress, turnover; soglie solo dopo evidence contract, no alpha promesso |
| Servono controlli risorse Zima prima del runtime | **GIÀ PRESENTE, RAFFORZATO** | OPS-01 è measurement-only, no nuovo servizio finché la sicurezza/CI non è verificata |
| Tre cicli logici renderebbero impossibile il DAG | **NON DIMOSTRATO** | Le dipendenze citate sono gate/assenze di schema, non cicli grafici. Chiarite precedenze senza affermare DAG inconsistente |
| Swap piena significherebbe crash sicuro di RUN-01 | **NON SUPPORTATO** | Swap occupata è un dato, non evidenza di thrashing/OOM. Verificare pressure, IO e latenza prima di decidere |
| Creare un Security Review Board | **NON ADOTTATO** | Nessun Board è documentato. Valgono costituzione KAIROS, controlli indipendenti e autorizzazione esplicita dell'operatore, non istituzioni inventate |
| Aggiungere nuova autorizzazione IG LIVE | **RESPINTO** | Contraddice l'obiettivo e l'autorità vigente: LIVE false; nessun percorso mutante aggiunto |

## Controlli ancora indipendenti da eseguire

1. Questo documento e le tre fonti master devono essere pubblicati su un branch isolato in una **PR draft**, con source/structural checks e Actions **disabilitate**. Nessuna PR può essere automaticamente considerata merged.
2. Prima della prima milestone DEV-00, iniziare LEG-01 **source-only** e distinguere moduli utilizzabili, terze parti e componenti commerciali; l'inventario resta possibile senza parere legale finale, il riuso operativo no.
3. Il contratto API-SCI-00 va verificato contro il sorgente reale KAIROS e le policy dual-clock, non inventato dalla GUI.
4. Non attivare job in background su ZimaBlade: attualmente #619 e PR #618 sono aperti. Fincept fork Actions restano spenti.
5. Il vero confronto Hindsight vs Mem0 e il recupero memoria da questa chat sono **non verificati**; MEM-01 resta un workstream separato ma nella STESSA automazione generale, precedentemente chiamata Memory Lab. Il cambiamento di scheduling è stato successivo alla review Claude e non costituisce review indipendente della nuova configurazione.

## Come controllare l'evoluzione della roadmap

La review di Claude è un input, non fonte di verità per timestamp, permessi, Git status o performance. Al prossimo run rileggere direttamente i quattro file canonici KAIROS, il master roadmap del fork, le PR e gli SHA attuali. Reportare un solo incremento su branch/PR, esito dei test e prossimo ID. Non aggiungere filoni nuovi per ogni idea: prima verificare se un task esistente la comprende.
