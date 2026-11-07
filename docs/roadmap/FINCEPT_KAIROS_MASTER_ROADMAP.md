# FINCEPT × KAIROS — MASTER ROADMAP V1.1 (Claude-reviewed candidate)

**Data:** 2026-11-07. **Stato:** candidate, Claude's critical review completed and amendments applied; independent security/legal/CI approval still pending.
**Prodotto principale:** [Fincept fork](https://github.com/cometarossa/kairos-fincept-terminal).
**Core scientifico canonico:** [KAIROS](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy), branch feature/kairos-autonomous-bridge.
**Autorità:** il canonico KAIROS, le sue costituzioni e Gate9R prevalgono su questa roadmap e sugli agenti.

## 1. Obiettivo e architettura vincolante

FINCEPT È LA PIATTAFORMA PRINCIPALE: terminale Qt, dashboard, AI Quant Lab, Backtesting, Alpha Arena, Agent Studio, collegamento a strumenti e agenti AI. I servizi scientifici KAIROS già esistenti devono essere **integrati in Fincept**, non ricreati indiscriminatamente né relegati a semplici pannelli passivi. Il componente KAIROS integrato deve presentare opportunità, evidenze, portafoglio teorico, rischi, decisioni, lavoro autonomo e stato del sistema.

**Fincept-first non significa tenere accesa la GUI per operare.** L'orchestrazione, i laboratori scelti, la memoria, gli esperimenti, la valutazione e il lavoro degli agenti devono essere headless e persistenti; il terminale può essere chiuso senza arrestarli. Un servizio persistente può riutilizzare moduli Python Fincept soltanto dopo verifica di dipendenze, costi, diritti e funzionamento senza Qt/login. Il core KAIROS su ZimaBlade resta autonomo, con interfacce versionate verso il prodotto.

DeepSeek è il provider LLM preferito iniziale per costo/prestazioni; Claude, Gemini e LLM locale sono challenger e revisori opzionali. Il modello propone ipotesi, non certifica i propri risultati, non gestisce segreti e non ha autorità di ordine. Le decisioni autonome di portafoglio sono inizialmente **proposte teoriche tracciate**, non istruzioni di broker. L'obiettivo finale è gestione quantitativa autonoma risk-adjusted e verificabile, senza pretendere profitti garantiti o alpha scientifico già dimostrato.

**Trading:** nessun ordine, annullamento, Square Off, modifica del broker o rischio; LIVE=false. KAIROS #619 sicurezza e CI PR #618 restano aperte. IG soltanto read-only dopo la verifica della sicurezza e delle condizioni d'uso; eventuali DEMO futuri richiedono un altro processo di autorizzazione indipendente. Non creare una scorciatoia dai widget o tool MCP mutanti Fincept.

## 2. Topologia funzionale

- **FINCEPT TERMINAL (Mac/Windows/Linux):** UI, configurazione agente, viste laboratorio, decisioni, allarmi, incidenti, memory viewer, stato e audit.
- **FINCEPT DECISION PLANE (headless):** queue/scheduler versionati, identità e permessi dei tool, budget, idempotenza, retries, health, gateway LLM, catalogo processi Python Fincept e job affidabili.
- **KAIROS SCIENTIFIC CORE (esistente):** dati di mercato, dual-clock research, predizioni prospettiche congelate prima dell'esito, valutatore indipendente, evidenze, rischio, audit e Gate9R.
- **MEMORY/EVIDENCE:** Git come verità del codice, ledger autorevole per decisioni ed esperimenti, memory FTS5 come indice lessicale, Hindsight/Mem0 come indice semantico NON autorevole; scope, ACL, fonte, scadenza, as-of e diritto alla cancellazione prima dell'uso personale.
- **FUTURE IG:** isolamento credenziali, osservazione/snapshot e riconciliazione; mutation gateway non implementato e non autorizzato.
- **INFRA:** ZimaBlade può ospitare servizi leggeri soltanto dopo misure e budget; ML e backtest pesanti su host apposito se giustificato. La GUI non è un server. MATER spento è cold storage, non failover 24/7; un secondo container sullo stesso host non è ridondanza.

## 3. Stato verificato vs documentato

| Check | Evidenza verificata 2026-11-07 | Limite |
|---|---|---|
| Fincept fork main | 7716ee8613249fb44c4d14036c5bc16ed6f34e97, Actions disabled | Non implica build e2e |
| Fincept architecture | [PR #1](https://github.com/cometarossa/kairos-fincept-terminal/pull/1) OPEN DRAFT | ADR non merged |
| Memory spike | [PR #2](https://github.com/cometarossa/kairos-fincept-terminal/pull/2) OPEN DRAFT, 14 test Mac PASS | Non Hindsight reale né servizio multiagente |
| KAIROS canonical | 77f0c0cc635945c808cafd581c1bfbcaaddffcac | Rileggere a ogni iterazione |
| Security KAIROS | [#619](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/issues/619) OPEN e [PR #618](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/pull/618) DRAFT OPEN | Priorità P0, niente runner privilegiati |
| GUI Fincept | 6 preset applicati/salvati nel precedente test; Equity bloccato in runtime | Non prova funzionamento tools, GUI non diagnosticata |
| Scientific stack | KAIROS dual-clock/precog documentati; ultimo runtime verificato separatamente | Nessuna nuova strategia ammessa provata |
| ZimaBlade | Atom E3950, ~16 GB, swap quasi piena al precedente snapshot, ~81GB DATA liberi, carichi importanti | Swap occupata non prova thrashing; nuove quote/daemon sospesi |
| Licensing | Contrasto file LICENSE e docs/COMMERCIAL_LICENSE.md upstream | Chiarire prima di distribuire/fondere codice |
| DeepSeek, IG, Hindsight, Mem0 | Moduli e adapter documentati, ma funzionamento e costi end-to-end NON VERIFICATI | Non chiamarli integrati |

Non presentare PR aperte come completate, test su fixture come prova di mercato né documenti come conferma live. Nessuna chiave, account o strategia riservata nel fork pubblico.

## 4. Backlog globale: ID, responsabilità, dipendenze e verifica

**P0** blocco security/authority; **P1** minimo prodotto funzionante; **P2** evoluzione subordinata a prove. Ogni milestone richiede prove all'exact SHA e revisione; la selezione operativa privilegia il primo task P0/P1 *non bloccato* e senza duplicazioni con altre PR. La classificazione P0 non autorizza modifiche operative. Una policy più restrittiva KAIROS o Gate9R prevale anche se il task del fork appare OPEN.

| ID | Pri | Risultato misurabile | Dipendenze e criterio di completamento | Stato |
|---|---|---|---|---|
| SEC-00 | P0 | Chiudere P0 #619 e quarantena CI #618 nel KAIROS canonico | Revisione indipendente dei runner, root of trust, gate esistenti | **BLOCKED / OPEN** |
| GOV-01 | P0 | Questa roadmap unica + AGENTS + checkpoint e ownership | PR dedicata, Claude review, agenti vi si allineano | **IN PROGRESS** |
| LEG-01 | P0 | Inventario license/asset commerciali, richiesta chiarimento a monte se necessario | Audit source-only subito; parere appropriato prima di distribuzione/riuso asset non chiari. DEV-00 può catalogare con campo LICENSE_UNRESOLVED, non integrare o pubblicare asset ambigui | **OPEN / NEXT P0 SOURCE** |
| DEV-00 | P1 | Inventario Fincept tools vs KAIROS servizi già esistenti (no duplicated integrations) | Percorsi Qt/Python, limiti di licenza, costi, auth, mutazioni, headless, equivalenti KAIROS e codice già esistente; LICENSE_UNRESOLVED non riusato | **NEXT AFTER GOV-01 / LEG-01 INVENTORY** |
| DEV-01 | P1 | Build Qt riproducibile e bug Equity isolato | Mac/VM dedicata, test smoke no credenziali, log, repro, failure handling | **OPEN** |
| API-01 | P1 | Contratto API Fincept–KAIROS read-only, ACL e capability map | Schema e mocks versionati, 401/403, timeouts, no broker routes; deploy vietato da SEC-00 | **MOCK ONLY** |
| UI-01 | P1 | Modulo KAIROS nella navigazione Fincept e viste ricerca/portafoglio | DEV-00+API-01, build & GUI smoke, status non bloccante, roll back | **OPEN** |
| TOOL-01 | P1 | Un tool Fincept quant headless con fixture dati sintetici | DEV-00, sandbox, timeout, provenance, risultato deterministico, zero ordini | **OPEN** |
| RUN-01 | P1 | Servizio persistent decision plane, durable queue, idempotenza, recovery | TOOL-01+API-01; mock test crash/restart; host deploy blocked da SEC-00 | **SOURCE ONLY** |
| MEM-01 | P1 | Memoria condivisa deterministica e semantica con tenant ACL | PR #2 PENDING; Hindsight/Mem0 non testati live, nessun uso privato | **PR #2 DRAFT / SAME AUTOMATION** |
| AI-01 | P1 | DeepSeek gateway primario, Claude/Gemini/locali opzionali | Budget e timeout, provider version, reviewer indipendente, abstention fallback | **OPEN** |
| API-SCI-00 | P1 | Contratto scientifico versionato fra Fincept e KAIROS, distinto dall'API UI | Schema mock di source identity, observed/available/frozen time, historical vs prospective, allowed vs protected outcomes, attempt IDs; NON una route per accedere al holdout | **OPEN / PREREQUISITE DATA-01** |
| DATA-01 | P1 | Data-source identity, timestamp, entitlement, PIT and staleness | API-SCI-00; allineamento al dual-clock canonico, no contaminazione holdout, licenze | **OPEN** |
| SCI-01 | P1 | Laboratory Fincept+KAIROS integrato con valutazione indipendente | TOOL-01+DATA-01; null models, net fees/slippage, all trials incl failed, prospective freeze/resolve | **INTEGRATION OPEN** |
| PORT-01 | P1 | Portafoglio teorico e policy di rischio/sopravvivenza | SCI-01+API-01; decision ledger di HOLD/astensione, limiti drawdown/tail-loss/expected shortfall, esposizione/correlazioni, stress e turnover; definire soglie su fixture prima di usare dati ammessi. Valore economico NON dichiarato senza validazione prospettica net-cost | **OPEN** |
| ARENA-01 | P2 | Gara multi-LLM e comparative research validata | AI-01+SCI-01; stesso input freeze, costi, safety, no Hyperliquid live | **OPEN** |
| IG-01 | P2 | IG SOLO osservazione, senza ordini, se autorizzato | SEC-00+LEG-01+API-01+PORT-01 e autorizzazione esplicita dell'operatore quando verrà richiesta; vault/scopes/terms/mock reconciliation, review indipendente, nessuna mutation | **BLOCKED** |
| IG-02 | GATE | Qualsiasi IG DEMO aggiuntivo | Autorizzazione indipendente Gate9R, nuova richiesta e prove | **NOT AUTHORIZED** |
| OPS-01 | P1 | Metriche ZimaBlade, risorse isolate, backup e recovery | No nuovi workload su host; vmstat/PSI/IO/CPU, quote, latenza servizi esistenti, capacità/backup. Swap occupata DA SOLA non prova thrashing; nessun deployment RUN-01 senza esito | **MEASUREMENT ONLY** |
| HA-01 | P2 | Ridondanza fisica, restore e fencing leader | RUN-01+OPS-01, host fisico distinto, no split brain, DR rehearsals | **OPEN** |
| QA-LOCAL | P1 | Test off-host locali e smoke Qt/Python riproducibili | Subito permessi su Mac/VM isolato; niente GitHub Actions/host privilegiato, no secrets, exact local SHA | **OPEN** |
| QA-CI | P1 | Eventuale CI esterna non privilegiata, release parity e independent review | SEC-00+DEV-01+QA-LOCAL e autorizzazione separata all'attivazione Actions; finché gate aperto non accendere runner | **BLOCKED FOR CI** |
| REL-01 | P2 | Release su macchina isolata con monitor e rollback | Tutti i gate pertinenti, prove end-to-end, gestione incidenti | **BLOCKED** |

## 5. Percorso critico e filoni paralleli

1. **Sicurezza e scelte prodotto:** SEC-00 (nel canonico), GOV-01 e LEG-01 source-only; QA-LOCAL testabile su Mac/VM. Chiarimento licensing blocca distribuzione/riuso asset, non la lettura/inventario del sorgente pubblico. Host/runner/broker modifiche NO.
2. **Prodotto minimo Fincept-first:** DEV-00 → DEV-01, API-01 mocks → UI-01 → TOOL-01; QA-LOCAL attraversa tutto il percorso. Primo risultato visibile: modulo KAIROS dentro Fincept con prove sintetiche e un tool Fincept reale isolato, senza trading.
3. **Autonomia persistente:** RUN-01 e AI-01, coordinando jobs esistenti, senza dipendere dalla GUI o reinventare scheduler già KAIROS.
4. **Metodo scientifico:** API-SCI-00 → DATA-01 → SCI-01 → PORT-01; dual-clock storico-as-of distinto da prospettico congelato prima del futuro; model pretraining non accreditato a blind historical replay senza evidenza.
5. **Conoscenza:** MEM-01 è un workstream distinto ma assegnato alla STESSA automazione generale, non a un secondo processo concorrente; ledger originale autorevole, recall semantico non autorevole; Graphify può indicizzare codice, non decisioni di portafoglio.
6. **Trading solo successivo:** IG-01 read-only dopo gate; IG-02 è un gate futuro NON autorizzato, LIVE false.
7. **Affidabilità e crescita:** OPS-01 measure-only → HA-01 se nuovi hardware e workload lo giustificano; no monolite Qt sempre acceso.

## 6. Dieci incrementi piccoli e sequenziali

1. **GOV-01:** pubblica e revisiona questa roadmap, crea checkpoint e AGENTS, mantieni PR draft; segue LEG-01 source-only come primo P0 indipendente.
2. **DEV-00:** dopo inventario preliminare LEG-01, mappa 15–25 moduli Fincept source-backed con entrypoint, provider, costi, privilegi, headless, equivalente KAIROS, licenza e priorità.
3. **DEV-01:** test di build minimo e diagnostica del blocco Equity sulla sandbox senza broker.
4. **API-01 e API-SCI-00:** schema UI read-only e schema scientifico temporale separato, con mock e test 401/403, PIT, as-of e fail closed.
5. **UI-01:** collega la pagina KAIROS al routing e alla ricerca Fincept, build+smoke Qt e QA-LOCAL.
6. **TOOL-01:** estrai UN backend Fincept di backtest per dati sintetici e validate exact output.
7. **AI-01:** mocks DeepSeek, Claude/Gemini/local, budget e failure-mode tests senza credenziali.
8. **MEM-01:** nello stesso orchestratore automatico, quando diventa il prossimo task non bloccato, confronta Hindsight e Mem0 in sandbox senza dati privati; PR #2 è già aperta e va verificata senza duplicati.
9. **SCI-01:** vista/adattatore delle evidenze E0/E2, no read di holdout non ammessi e no fake edge.
10. **OPS-01:** benchmark host/Zima senza nuovi daemon, preflight per il futuro hardware.

**Una iterazione = UN solo task testabile, una PR per change, preferibilmente draft e non concorrente.** Nessuna automazione interpreta questo backlog come permesso di eseguirlo tutto in una singola run. Nessun lavoro sullo stesso file/branch di un'altra automazione.

## 7. Protocollo permanente per ogni agente (incluso Claude)

A ogni nuovo run: leggere AGENTS.md e questo documento, il checkpoint sotto docs/roadmap; leggere **live** AGENTS.md, AGENTS_RULES.md, docs/KAIROS_MASTER_ROADMAP.md, PROJECT_STATE.md e roadmap pertinenti dal canonico KAIROS. Verificare SHA, PR, issues, CI/Actions e stato runtime solo se pertinente/autorizzato. Confrontare implementazioni già esistenti prima di introdurre servizi. Classificare **VERIFIED_NOW**, **DOCUMENTED**, **NOT_VERIFIED**, **BLOCKED**. Prendere solo il prossimo task non bloccato. Eseguire test locali in sandbox e commit su branch isolato, proporre PR draft e riportare test/commit/rischi; non effettuare merge o deploy non autorizzato.

Ownership: l'automazione autonoma KAIROS segue SEC-00 nel canonico; UNICA automazione Fincept–KAIROS Roadmap Autonoma (già Memory Lab, aggiornata il 2026-11-07) segue tutti i task del fork inclusa MEM-01 e PR #2, scegliendo UNA sola priorità per run e senza concorrenza sullo stesso branch. Non creare nuove automazioni che duplicano i lavori: limite piano 5 attività già occupate. Claude fa review critica con source evidence ma può sbagliare: verificare ogni affermazione prima di accettarla.

### STOP CONDITIONS

- P0 non chiuso per qualsiasi privilegio/runner/deploy/IG/broker.
- Licenze non chiarite per riuso o distribuzione di componenti interessati.
- Identità dei dati, timestamp PIT, fonte o risk validation assente.
- Uso di chiavi/token utente, portafogli reali, dati personali nel fork pubblico.
- Fincept Equity freeze, GUI blocca decision jobs, tool muove soldi o attiva credenziali.
- CI disabled interpretato come green o PR aperta chiamata completata.
- Host Zima degrade e nessun piano restore/rollback. Il criterio prioritario è **sicurezza > prove > riuso > continuità > nuove funzionalità**.

## 8. Fonti e puntatori

[Fincept architecture — draft PR #1](https://github.com/cometarossa/kairos-fincept-terminal/pull/1).
[Memory POC — draft PR #2](https://github.com/cometarossa/kairos-fincept-terminal/pull/2).
[Claude audit generale con correzioni](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/blob/research/fincept-ui-orderflow-spike-20261106/docs/research/CLAUDE_FINCEPT_GENERAL_AUDIT_REVIEWED_20261107.md).
[KAIROS constitution](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/blob/feature/kairos-autonomous-bridge/AGENTS.md).
[Dual clock charter](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/blob/feature/kairos-autonomous-bridge/docs/KAIROS_DUAL_CLOCK_CONTINUOUS_EDGE_LAB_CHARTER_V1.md).
