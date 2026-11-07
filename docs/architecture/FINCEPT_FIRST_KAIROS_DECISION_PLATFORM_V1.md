# Decisione architetturale V1 — Fincept-first con KAIROS come modulo decisionale persistente

**Data:** 2026-11-07. **Tipo:** ADR / scelta progettuale; nessuna autorizzazione al deploy o al trading.  
**Repository:** `cometarossa/kairos-fincept-terminal`, fork di `Fincept-Corporation/FinceptTerminal`, base `7716ee8613249fb44c4d14036c5bc16ed6f34e97`.  
**Sistema esistente da integrare:** `cometarossa/multi-asset-trading-system-hermes-autonomy`, ramo canonico `feature/kairos-autonomous-bridge`.  
**Controlli in sospeso:** issue di sicurezza KAIROS #619 e PR di quarantena CI #618 aperte; LIVE trading non autorizzato. GitHub Actions sul fork Fincept disabilitato.  
**Parere indipendente:** Claude Code (Haiku, 2026-11-07) preferisce l'architettura C qui descritta, con riserve su prestazioni, isolamento e licenza. Parere basato sul contesto fornito, **non** su una nuova verifica autonoma del sorgente. Il rapporto originale rimane privato sul desktop dell'operatore; le valutazioni hardware troppo categoriche non sono recepite come fatti.

## Obiettivo espresso dall'operatore

**Fincept è il prodotto principale**, non un semplice visualizzatore della Control Room KAIROS. Il terminale deve offrire:
- dashboard, grafici, fonti finanziarie, simulazione e laboratori AI/quant;
- modulo integrato **KAIROS** che usa i servizi scientifici, le previsioni, i dataset, gli esperimenti e i controlli già esistenti;
- agenti AI che possano prendere **decisioni quantitative di ricerca e portafoglio** con evidenze, rischio esplicito e registro storico;
- DeepSeek come provider preferito; Claude, Gemini, Ollama/LLM locale come alternative configurabili e budgetate;
- funzionamento continuo su un servizio **headless** inizialmente ospitato dove c'è capacità, senza dipendere dalla finestra Qt, da ChatGPT o dalla presenza dell'operatore;
- integrazione IG solo successiva, inizialmente read-only, poi eventualmente ambiente DEMO in quarantena, con autorizzazione separata e testata. Nessuna esecuzione LIVE.

### Distinzione fondamentale

**Fincept-first NON significa Qt-desktop-monolith-first.** Il prodotto, il workflow dell'utente, le integrazioni modulari e la governance dei job appartengono a Fincept/KAIROS Terminal; i processi di calcolo e decisione girano in un servizio autonomo, indipendente dall'interfaccia. La GUI può essere chiusa senza interrompere ricerca, monitoraggio e decisioni. Il servizio headless può usare componenti Python Fincept solo dopo estrazione e test di dipendenze, più le capacità già presenti in KAIROS. Non è corretto assumere che tutti i moduli Qt/Python siano riutilizzabili lato server senza modifiche.

```
FINCEPT / KAIROS TERMINAL (macOS / Windows / Linux)
+------------------------------------------------------------------+
| GUI Qt + dashboard + AI Quant Lab + Backtesting + Alpha Arena     |
|               KAIROS module: opportunities/decisions/portfolio   |
|               explicit status + risk/evidence + controls          |
+--------------------------+---------------------------------------+
                           | versioned scoped API
                           v
    PERSISTENT FINCEPT × KAIROS DECISION PLANE (headless)
    +------------------------------------------------------------+
    | scheduler / bounded job queue / idempotent task IDs         |
    | provenance + model proposal + scientific admissibility     |
    | portfolio policy, exposure, risk, reconciliation             |
    | deterministic research workers + Fincept Python adapters    |
    | DeepSeek primary; Claude/Gemini/local opt-in with budgets   |
    | immutable decision record: proposed/admissible/rejected     |
    +--------------------------+---------------------------------+
                               | constrained interfaces
                 +-------------+--------------+
                 v                            v
        EXISTING KAIROS                  FUTURE BROKER ACCESS
        scientific services              IG read-only first
        historical and prospective       DEMO after separate gates
        data, evaluation, observability  LIVE permanently disabled
```

## Terminologia sulle autorizzazioni

| Livello | Significato | Autorità attuale proposta |
|---|---|---|
| Osservazione | acquisire dati con fonte e timestamp | read-only, subordinata ai contratti esistenti |
| Ipotesi | proporre opportunità, pesi, coperture e astensione | modello AI con budget e provenienza |
| Valutazione | test PIT, benchmark nulli, net-cost, rischio di rovina | validatore indipendente dai modelli proponenti |
| Decisione | scegliere un'allocazione *teorica* o di paper portfolio e registrarla | servizio headless; non è un ordine |
| Paper simulation | simulare contabilità, esecuzioni e slippage | ambiente isolato senza broker reale |
| DEMO | ordini in conto demo | **non autorizzati da questa decisione**; soltanto dopo sicurezza e gate indipendenti |
| LIVE | ordini con capitale reale | **FALSE**; nessuna strada da Fincept o dall'LLM |

**Mai collegare** la UI Fincept, i tool MCP di trading o gli agenti LLM direttamente a credenziali IG con poteri d'ordine; l'autorità broker è separata da ricerca e decisione. Non sono ammesse scorciatoie attraverso il fork.

## Parere critico di Claude, con correzioni

Claude favorisce il modello **C**: Fincept come piattaforma principale + servizio headless persistente + integrazione documentata dei laboratori e del core scientifico già presente in KAIROS. Rifiuta un unico processo Qt responsabile di decisioni 24/7; ritiene meno coerente con l'obiettivo dell'operatore la soluzione in cui Fincept è solo un viewer. Sottolinea le criticità di manutenzione del fork, rischio licenze, contesa risorse, failover fisico e permessi dei broker.

**Controllo delle affermazioni di Claude:**
- Lo ZimaBlade E3950 ha risorse limitate e già ospita carichi importanti; tuttavia **swap occupata non prova swap-thrashing, OOM killer attivo o impossibilità di eseguire un servizio leggero**. Queste conclusioni, espresse troppo categoricamente nella risposta originale, restano non verificate.
- Un secondo container sullo stesso host non offre alta disponibilità fisica. Per ridondanza reale servono un altro host, copie ripristinabili, regole anti-split-brain e test di failover.
- Non è necessario e non è raccomandato tenere Fincept Qt aperto sullo ZimaBlade. La GUI rimane sul dispositivo desktop dell'operatore.
- I carichi e SLO suggeriti nel parere (150 decisioni/giorno, 100 richieste/s, 500 ms p99) **non discendono dai requisiti** e non sono criteri di accettazione vincolanti. Prima vanno misurati workload realistici.
- La licenza rimane da chiarire: il file `LICENSE` storico di Fincept e `docs/COMMERCIAL_LICENSE.md` non sono pienamente coerenti; si devono mantenere attribuzione e compatibilità AGPL e non trasferire strategie o segreti privati nel fork pubblico.

## Unità operativa e ridondanza

Lo ZimaBlade è nodo iniziale potenziale **per attività leggere**: supervisione, jobs di ricerca con limiti, protocolli read-only, log delle decisioni. Non è ammesso un nuovo carico semplicemente perché il container Ollama è avviato. I servizi KAIROS già attivi (research autopilot, director, ingest e verifiche) devono essere riusati per evitare doppie code e schedulatori concorrenti.

**Preflight di capacità obbligatorio prima di avviare nuove unit:** misurare serie temporali swap-in/swap-out e pressure-stall, memoria realmente disponibile, latenza p95 del dashboard e dei job esistenti, CPU, IO e spazio nel mount target; introdurre limiti CPU/RAM, scratch e timeout, un job concorrente al massimo nei primi esperimenti, zero broker credentials. Il pieno utilizzo dello swap a un singolo istante non dimostra di per sé esaurimento di RAM.

Per i backtest più pesanti, training ML, competizioni LLM e rendering/plot non serve immediatamente un host acceso 24/7: iniziare con benchmark isolati sul desktop o macchina dedicata senza credenziali e scegliere hardware solo dopo un profilo carichi. MATER, essendo cold storage/normalmente spento, può aiutare backup e calcolo pianificato, **non** garantire failover istantaneo. True HA successiva richiede nodo fisico indipendente, ripristino verificato e leader/fencing che impediscano due orchestratori attivi simultaneamente.

## DeepSeek e altri modelli

Il gateway modelli è un **servizio persistente** con identità per modello, versioni, tetti di spesa, privacy/redazione, retry e timeout. Preferenza iniziale DeepSeek per proposte e sintesi, non per autorizzare ordini. Claude/Gemini possono fare challenger e revisione incrociata, un LLM locale può ridurre alcune dipendenze cloud soltanto con risorse sufficienti e isolamento. Ogni decisione conserva input digest, modello/provider/versione, timestamp di inizio/fine, output, costi e validazione scientifica. La mancata disponibilità di un modello deve degradare in astensione, mai in un'autorità di trading inferiore.

## Perché Fincept-first potrebbe fallire

1. **Accoppiamento dei moduli:** se i laboratori utili dipendono da stato GUI, login o servizi commerciali, l'estrazione headless può essere più costosa che riusare il laboratorio KAIROS.
2. **Costo di manutenzione del fork:** cambiamenti Qt/C++ grandi, nuove versioni Fincept, ABI/dipendenze e revisioni licenze potrebbero assorbire più tempo dell'analisi scientifica.
3. **Scarsa affidabilità runtime:** il problema già osservato nell'interfaccia Equity è ancora senza diagnosi; un prodotto che si blocca può compromettere l'usabilità, pur senza fermare l'agente persistente.
4. **Nessun alpha ammesso:** anche una dashboard e una competizione AI perfette non dimostrano che le strategie generino rendimento netto. KAIROS resta tenuto a controlli indipendenti, holdout e astensione.

## Cinque incrementi verificabili, in ordine

1. **Separazione delle responsabilità:** inventario delle funzioni Fincept Python utilizzabili senza Qt e dei servizi KAIROS che forniscono già equivalenti. Criterio: niente duplicazioni, niente import di trading live, risorse/diritti noti.
2. **Modulo KAIROS nel fork, con fixture di sola lettura:** una pagina fincept-qt dedicata a decisioni, evidenze e stato, collegata a mock contrattuali. Criterio: build verificata in ambiente isolato, GUI non blocca, nessuna richiesta broker.
3. **Contratto del decision plane:** API versionata per osservazioni, job submit confinato, stato, risultati, ledger decisionale e policy; test di autenticazione e idempotenza su mock, niente endpoint di esecuzione ordini.
4. **Prova headless di UN laboratorio:** un unico script/modulo Fincept di ricerca con dati sintetici, risultato deterministico, limiti CPU/RAM/tempo; la GUI resta chiusa durante l'esecuzione. Se richiede login/Enterprise/GUI o non è isolabile, rivalutare il riuso.
5. **Soak test e benchmark ZimaBlade non invasivo:** solo dopo P0 e revisione indipendente, test quota minima e monitoraggio dell'impatto su servizi correnti; verificare riavvio recuperando job senza duplicazione. Se l'host peggiora sotto limite concordato, spostare workload su nodo dedicato.

**Stop conditions:** app non verificabile o blocco persistente; API/cloud a credito senza budget; CI/runner security P0 aperta per deploy privilegiato; condizioni licenza irrisolte per copia del codice; falsi risultati scientifici; broker mutation accessibile dal decision plane; stress su host condiviso; assenza di restore/rollback.

## Stato finale di questa ADR

**Selezionata:** Fincept-first come prodotto/Control Room e gateway strumenti, con decision plane autonomo headless e servizi KAIROS scientifici esistenti collegati in modo esplicito. **Non selezionata:** un monolite Fincept sempre aperto, né Fincept come viewer passivo. **Non realizzato:** codice del pannello, deployment, broker, continuità, failover, scoring E2E; richiedono singoli PR e prove.

Ogni implementazione sostanziale deve avvenire su branch separato e, dopo test e review esatti, attraverso PR. Nessuna modifica al ramo canonico KAIROS o ai servizi ZimaBlade deriva da questa decisione architetturale.
