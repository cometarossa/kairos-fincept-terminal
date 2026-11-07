# Fincept × KAIROS: memoria persistente, verificabile e condivisa tra agenti — shortlist e POC

**Data:** 2026-11-07 (Europe/Rome). **Stato:** research + design, NON installato. **Architettura:** Fincept è il prodotto/Control Room; il servizio memoria è headless, persistente, separato da Qt e dai processi di broker. **Autorità di trading:** nessuna. **Controlli prioritari:** KAIROS P0 #619 e CI draft PR #618 aperti. **Fork GitHub Actions:** spento.

## Risposta al ricordo originale: Graphify

Il servizio che avevamo già esaminato come indice dei repository è **Graphify** [Graphify-Labs/graphify-mcp](https://github.com/Graphify-Labs/graphify-mcp). Il suo grafo del codice permette di cercare simboli, dipendenze, caller, test correlati e conoscenze di repository. Il repository pubblico contiene documentazione d'accesso al **servizio hosted con OAuth**, non il server indicizzatore installabile. Verifica live via Graphify MCP 2026-11-07: workspace `Emiliano's workspace` esistente, ma `list_repositories` risponde `FORBIDDEN: no repositories enabled for agents yet`. **Non considerarlo un indice disponibile finché la configurazione non è verificata**. Graphify, anche quando attivo, NON sostituisce memoria episodica, decisionale e di portafoglio.

Distinguere **Graphify** (indice di codice hosted) da **Graphiti** ([getzep/graphiti](https://github.com/getzep/graphiti), temporal knowledge graph open-source con DB a grafo), che è un progetto diverso.

## Candidati GitHub verificati dalle istruzioni dei rispettivi maintainer

| Progetto / sorgente | Funzione principale | Self-host / connettori | Punti critici e conclusione |
|---|---|---|---|
| [Hindsight — vectorize-io/hindsight](https://github.com/vectorize-io/hindsight) | Memoria episodica e sintetica `retain / recall / reflect`, banche di memoria, ricerca semantica e riflessione | MIT, Python+server, Postgres embedded o esterno, REST e MCP per banca; [provider Hermes](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/memory-providers.md); provider LLM `deepseek` e `ollama` | **Prima scelta per POC**: ottimo incastro decisioni/esperimenti e DeepSeek. DeepSeek non eroga embeddings; usare encoder locale calibrato. **MCP è privo di autenticazione di default**: abilitare `ApiKeyTenantExtension`, autorizzazioni per banca, e non esporre la porta al LAN/WAN. Carico Postgres/embeddings da misurare. |
| [Mem0 — mem0ai/mem0](https://github.com/mem0ai/mem0) | Memorie semantiche estratte da conversazioni e fatti | Apache-2.0, SDK Python/TS, self-host server con auth di default e dashboard; configurazione LLM/vector store | **Fallback da benchmark**: API semplice, ma il server e vector store possono aggiungere processi. Non è fonte veritiera per stato di portafoglio. |
| [Supermemory — supermemoryai/supermemory](https://github.com/supermemoryai/supermemory) | Richiamo di memoria multiagente, profilo, contesto per progetto; Hermes/Claude Code/Codex/OpenCode; server locale su porta 6767 | SDK e MCP pubblici; **server locale scaricabile come binario la cui implementazione è in una codebase non pubblica** ([self-hosting overview](https://github.com/supermemoryai/supermemory/blob/main/apps/docs/self-hosting/overview.mdx)), pur con root repo MIT | Ottimo per operatività rapida; meno adatto quando la revisione completa del backend di memoria è un requisito. Nessuna installazione via `curl|bash` su Zima senza revisione/pinning e sandbox. |
| [OpenViking — volcengine/OpenViking](https://github.com/volcengine/OpenViking) | Memoria+documenti+skill come filesystem `viking://`, L0/L1/L2, richiami parsimoniosi in token | AGPL-3.0, self-hosted, integrazioni Hermes/Claude/Codex/MCP | **Forte candidato per conoscenza e skill**, ma aggiunge semantica e licenza diverse; valutare maturità operativa e costi d'indicizzazione. |
| [Graphiti — getzep/graphiti](https://github.com/getzep/graphiti) | Grafo temporale di entità/relazioni ed eventi | Python, FalkorDB/Neo4j, provider LLM e MCP esempio | Più adatto per timeline complessa quando serve il grafo; **MCP e REST di esempio privi di auth/autorizzazione e difesa prompt injection** secondo README. Non adottare come server di produzione direttamente. |
| [Memvid — memvid/memvid](https://github.com/memvid/memvid) | Archivio portabile, append-only, ricerca e versioni in file unico | Locale/offline e indipendente dal modello | Interessante come export/snapshot di memoria o documenti; controllare multiwriter/snapshot consistenti prima di usarlo come unica memoria condivisa in rete. |
| [Letta Code — letta-ai/letta-code](https://github.com/letta-ai/letta-code) | Agente con identità, memoria e autoapprendimento | Runtime agente, CLI/server cloud/local, Git MemFS | Potrebbe sostituire parti di Hermes, ma obiettivo attuale è memoria comune, **non creare un secondo orchestratore concorrente**. |

**Valutazioni di qualità/velocità:** benchmark dichiarati dai produttori sono indicativi e NON sostituiscono un benchmark indipendente sui nostri documenti, versioni, modelli, hardware e requisiti privacy.

## Scelta proposta (reversibile, subordinata a benchmark)

**Hindsight come prima implementazione candidata**, **Mem0 come alternativa fully-source con API semplice**, **OpenViking come possibile livello per conoscenza gerarchica**, Graphify separato per indice del codice solo dopo abilitazione effettiva del workspace. Non istallare tre motori simultaneamente sullo ZimaBlade per provare un'idea. Tutte le integrazioni passano attraverso un nostro contratto `MemoryAdapter` neutrale al prodotto, testabile senza backend.

### TRE fonti di verità, NON una sola memoria generativa

1. **Git/GitHub:** codice, regole, commit, PR, issue, roadmap. Ogni memoria sul codice è referenziata a SHA/ref e può scadere quando il branch avanza. Graphify è un indice, non la verità.
2. **Ledger append-only deterministico:** identità e cronologia di osservazioni, previsioni congelate prima degli eventi, esperimenti, versioni modello, portafoglio teorico, decisioni, riconciliazioni e conseguenze. Deve conservare timestamp, fonte, oggetto originale/hash, revisioni, causale, controllo di accesso e provenienza. LLM **non possono riscrivere** il ledger.
3. **Memoria semantica/operativa:** Hindsight memorizza sintesi e recupera episodi/relazioni; il risultato è un suggerimento con riferimento all'originale e flag `stale/conflict/unverified`. Mai usare un ricordo come prezzo reale, autorizzazione o stato broker.

### API del Memory Adapter

- `remember(event, scope, source_ref, observed_at, expires_at, visibility, confidence)` — data minimization, provenance e deduplicazione;
- `recall(query, scope, max_tokens, as_of)` — per default `max_tokens` limitato, riporta fonte, timestamp, completezza e incertezza;
- `get_original(memory_id)` — risale al documento/ledger/Git SHA, senza usare il summary come prova;
- `supersede(old_id, correction, reason)` — conserva il precedente e mostra la revisione, senza cancellare il contesto storico;
- `forget(memory_id, scope)` — controlli privacy e revoca su tutte le copie/backup secondo policy;
- `health` / `export` / `restore_test` — operatività e backup.
- **NON ESISTONO** tool `place_order`, `cancel_order`, `enable_live` o `set_risk_override` nel servizio memoria.

**Ambiti separati:** `fincept:code`, `kairos:architecture`, `kairos:research`, `kairos:decisions`, `kairos:incidents`, `user:private`. Le banche di un vendor o la metadata tag NON sono di per sé un firewall fra ruoli: applicare ACL nell'adapter/gateway. Non inviare all'LLM token di accesso, cookie, PIN, segreti e dati account in chiaro.

### Come tutti gli agenti leggerebbero la stessa memoria

- **Hermes:** scegliere un provider memoria esterno supportato da Hermes, ma **verificare lo stato corrente** prima di sostituire quello attivo. Hermes mantiene memoria `MEMORY.md/USER.md` come fallback. Secondo la documentazione supporta Hindsight, Mem0, Supermemory, OpenViking. **Un solo provider esterno attivo alla volta**.
- **DeepSeek/Claude/Gemini:** gli LLM, come modelli, non conservano questa memoria. La richiama il servizio headless prima della chiamata al modello e conserva gli eventi dopo (nessun richiamo non autorizzato). Usare lo stesso adapter e ruoli specifici, non la stessa credenziale.
- **Fincept:** pannello `KAIROS > Memory & Evidence` per richiamare memoria + fonte + obsolescenza, senza poter modificare lo stato di portafoglio o broker.
- **ChatGPT / Work:** accesso alla memoria condivisa **solo se** un'app/plugin connesso, un MCP gateway autorizzato o un'integrazione supportata espone gli strumenti in questa sessione. Non confondere memoria privata di ChatGPT e servizio Hindsight. Verifica 2026-11-07: ricerca Directory plugin per Hindsight e Supermemory non ha restituito un plug-in installabile. L'accesso automatico da questa chat è **NON DISPONIBILE / NON CONFIGURATO**; nel frattempo GitHub già connesso può fungere da fonte autorevole del progetto.
- **Graphify:** connettore già installato ma nessun repository attualmente abilitato; è un acceleratore opzionale delle analisi di codice, non un prerequisito del POC.

## Test POC obbligatorio PRIMA dello ZimaBlade

1. **Isolamento:** clonare e fissare release/commit del candidato, usare Mac/VM di test e dati sintetici; nessun download/install `latest` su host KAIROS, nessuna credenziale di broker e porte esposte all'esterno.
2. **Corpus iniziale:** 100–500 episodi sintetici sulle roadmap e su incidenti simulati, con 20–30 interrogazioni da valutare manualmente su esattezza, fonte, obsolescenza, conflitti cronologici, privacy e recupero da due agenti.
3. **Prestazioni:** registrare p50/p95 di recall e ingest, crescita RAM/swap/CPU/disco, bytes di memoria, token aggiunti e costo DeepSeek. Non usare numeri marketing come SLO.
4. **Prova critica:** cambiare un fatto, chiedere "qual era lo stato prima e dopo?", verificare che il sistema non confonda una decisione simulata con un ordine reale; estrarre e ignorare istruzioni malevole nascoste nelle memorie; testare ACL progetto/persona e delete+backup.
5. **Recovery:** snapshot persistente, riavvio, ripristino, controllo conteggi e hash. Nessun multiwriter inconsistente.
6. **Stop:** indisponibilità della fonte, false informazioni di portafoglio, fuga dati cross-scope, uso non controllato di tool mutanti, egress o API costi imprevisti, memoria non ripristinabile.

**Solo dopo**: benchmark minimo controllato sullo ZimaBlade con un processo a quota limitata e senza interferire con CI/run critici. La macchina verificata ha Atom E3950 4 core, 16 GiB RAM, swap quasi piena in snapshot e /DATA ~81 GiB liberi; swap occupata NON prova thrashing. Misurare PSI e vmstat prima. MATER cold-storage/normalmente spento non costituisce failover attivo.

## Sicurezza e release policy

P0 #619 e PR #618 rimangono aperti nel repository canonico; questo documento non modifica i runner. Il fork Fincept è pubblico e GitHub Actions disabilitato: **non** committare segreti, memoria privata, portafoglio reale, nomi di banche segrete, esempi di strategie proprietarie o dump di conversazioni. Il servizio memoria non va esposto direttamente a LAN o Internet e deve avere autenticazione sin dal primo giorno, soprattutto perché Hindsight MCP **default open**. Qualsiasi successiva PR di codice deve documentare build, test mock, limiti di accesso, rollback, e non abilitare mutazioni IG.
