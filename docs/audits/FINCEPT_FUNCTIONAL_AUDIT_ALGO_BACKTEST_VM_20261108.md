# Fincept × KAIROS — Audit funzionale VM V1: Algo, Backtesting, AI Quant Lab

**Data:** 2026-11-08 · **Stato:** prima fase di audit effettivo, NON certificazione completa di tutte le schermate.
**Obiettivo:** preservare il terminale e ogni strumento utile, poi collegarli a un LLM autonomo e ai gate scientifici KAIROS senza duplicare core o autorità trading.

**AGGIORNAMENTO V1.1:** la verifica completa del probe VectorBT sulla VM e il calcolo reale del secondo provider Backtesting.py sono ora PASS. Vedere [Addendum VM V1.1](FINCEPT_BACKTESTING_VM_RUNTIME_V1_1_20261108.md) per prove, limitazioni e riproduzione. I rilievi V1 non ancora aggiornati sono storici e non attestano lo stato finale dei test.

## Ambiente e metodo

- VM Debian GNU/Linux 13 (trixie) su iMac/QEMU, 4 vCPU, 6144 MB RAM, filesystem root 16 GiB con circa 4 GiB liberi. Processo FinceptTerminal v4.5.1 attivo; hash SHA256 del binario osservato b02726f140cde34d4e7a4fae67c60a03bd980c9052edb4b3b1644d41b8271f40.
- Sorgente di confronto: fork Fincept main SHA 7716ee8613249fb44c4d14036c5bc16ed6f34e97. **Non è provata l'identità fra il sorgente esatto e il binario installato.**
- Prove: screenshot della GUI, esame dei log locali, inventario dipendenze dei due venv, 18 chiamate metadata CLI sui sei provider, sei test dati sintetici della bridge VectorBT, e un backtest VectorBT separato su 320 candele sintetiche iniettate. Analisi dei sorgenti C++/Python. **Nessun clic Deploy, nessun broker collegato, ordine, installazione, modifica dei servizi o traffico API di trading richiesto dall'audit.**
- Stato dei controlli: KAIROS issue #619 OPEN, CI quarantine PR #618 OPEN/DRAFT. GitHub Actions del fork Fincept disabilitate. Modalità LIVE del nostro KAIROS non autorizzata. Nessuna nuova autorità viene creata.

## Executive findings

| ID | Priorità | Evidenza verificata | Conseguenza |
|---|---|---|---|
| FB-01 | P1 funzionale | Tutti i file sotto Analytics/backtesting sono instradati da PythonRunner a venv-numpy1. Questo venv contiene i motori Backtesting ma NON yfinance, presente soltanto nel venv-numpy2. Il log VectorBT optimize SPY fallisce per yfinance non installato | Problema di isolamento delle dipendenze/data source, **non prova che tutti i dati manchino** |
| FB-02 | P1 scientifico | Algo Builder nella VM ha completato un backtest su ASIANPAINT 5m, 2.927 barre, 1.439 trade, condizioni Close > 0 (entry e exit), performance mostrata circa -5,55% | Il motore esegue davvero, ma questa strategia dimostrativa non dimostra vantaggio di mercato |
| FB-03 | P0 authority | AlgoEngine implementa paper e LIVE: ramo LIVE richiama UnifiedTrading::place_order; una strategia LIVE può riprendere al riavvio del processo Fincept | **Vietare** l'accesso LLM a deploy/start/recovery/order e a tutti i tool mutanti |
| FB-04 | P1 science | Il BacktestEngine nativo C++ non contabilizza commissioni, spread e slippage nel codice esaminato | Output Algo non utilizzabile da KAIROS come backtest net-cost validato |
| FB-05 | P1 data | CandleDataFetcher limita il lookback storico Yahoo intraday, può sostituire broker con Yahoo e consegna candele senza envelope della fonte effettiva al motore Algo | Finestra promessa, fonte, actual coverage, bar close e disponibilità PIT da verificare |
| FB-06 | P1 data trust | VectorBT accetta candele esterne tramite brokerCandles, sei test fixture PASS; un backtest di 320 barre sintetiche iniettate ha restituito success e status completed | Ottimo punto di ingresso per dataset KAIROS, ma il flag interno usingSyntheticData può risultare false per dati comunque inventati |
| FB-07 | P1 autonomy | AlgoEngine e DeploymentRunner usano thread Qt nel processo desktop, con recupero di righe in running/starting/error/crashed al riavvio | Non sono il servizio headless continuo che richiede KAIROS |
| FB-08 | P1 risk | DeploymentRunner::resume può chiamare reset_daily per rimuovere il blocco giornaliero di perdita; max_daily_loss=0/max_order_value=0 significano nessun limite configurato | Il risk gate KAIROS deve rimanere esterno e superiore a quello del modulo Algo |
| FB-09 | P1 feature | I sei provider Python restituiscono cataloghi strategia/indicatori/opzioni; **529 definizioni strategia** nei cataloghi | Non sono 529 strategie realmente verificate o redditizie |
| FB-10 | P1 architecture | AI Quant Lab ha un terzo backtester Qlib-style, distinto dal BacktestEngine C++ Algo e dal terminale Backtesting Python | Contratti scientifici condivisi, ma non supporre backend equivalenti |
| FB-11 | P1 data | Nei log DataHub/Yahoo precedenti risultano errori ricorrenti su simboli LBS=F e UNI-USD | Necessari test di coverage, fallback ed errori per singola fonte |
| FB-12 | P1 coverage | Il precedente blocco della pagina Equity non è stato diagnosticato | L'audit esteso della UI/servizi resta aperto |

## 1. Algo è davvero un creatore di bot

I sei tab in src/screens/algo_trading/AlgoTradingScreen.cpp sono Builder, My Strategies, Scanner, Alerts, Dashboard e Universe.

- **Builder:** condizioni di ingresso/uscita con AND/OR, regole su OHLC, SMA/EMA, RSI, MACD, ATR, Bollinger, Keltner, Donchian ecc.; timeframe, SL/TP, trailing, sizing e template. Save memorizza le strategie nella tabella SQLite algo_strategies; Backtest calcola sulle regole correnti senza salvarle.
- **My Strategies:** libreria persistente, strategie editabili, edit/backtest.
- **Scanner / Universe / Alerts:** ricerca, applicazione delle condizioni, monitoraggio e segnali.
- **Dashboard:** deploy e metriche/trade/stato via DataHub topic algo:metrics, algo:trade, algo:state.
- **AlgoTradingService:** CRUD e invocazione BacktestEngine::run (C++). **AlgoEngine:** lifecycle dei bot e instradamento ordini. **DeploymentRunner:** warm-up dati e monitoraggio tick/candele, regole/rischio.
- La strategia AlgoStrategy è una **DSL di indicatori JSON**, non un ambiente completo per eseguire modelli Python KAIROS o chiamate LLM arbitrarie. I vecchi riferimenti QuantConnect sono soprattutto residui di compatibilità; Python LEAN/QC non è il runtime dei bot Algo attuali.

### I limiti da non sottovalutare

1. **Paper ≠ no broker:** AlgoDeployDialog richiede un conto broker connesso anche per Paper, perché lo utilizza per ricevere quotazioni; paper simula il fill e non invia ordini.
2. **LIVE è reale:** AlgoEngine::execute_order fa routing al broker via UnifiedTrading.place_order, pur con controlli e alcune conferme Fincept. Il percorso esiste e NON è sottoposto automaticamente alla costituzione KAIROS.
3. **Restart:** recover_orphaned ricarica deploy running/starting/error/crashed. Non delegare mai autonomia persistente del sistema a un processo Qt che può far ripartire LIVE.
4. **Daily loss:** ripresa manuale può azzerare il blocco per perdita giornaliera; per KAIROS sarebbe un bypass di rischio non consentito.
5. **Studio di strategia degenerata:** nello screenshot VM la condizione Close > 0 in entrata e uscita è quasi sempre vera. Dai log risultano 1.439 trade su 2.927 barre. Il backtest funziona, ma quel risultato non è informazione su alpha.
6. **Costi:** in src/algo_engine/BacktestEngine.cpp il profitto è calcolato come differenza di prezzo per quantità, senza commission/slippage; segnale a close della barra i e fill teorico a open di i+1. Per KAIROS classificare il risultato **GROSS_EXPLORATORY**.
7. **Coverage:** la UI mostrava From 2025-11-08, To 2026-11-08 e timeframe 5m; il fetch Yahoo native impone un lookback massimo molto più corto. Un report può quindi analizzare soltanto un sottointervallo recente pur mostrando le date richieste. Registrare sempre requested_from/to e actual_first/last, oltre a valuta e sessioni.
8. **Fonte:** broker-first può ricadere su Yahoo. La callback verso BacktestEngine non riceve una provenance envelope completa. Niente trial KAIROS con fonte sostituita silenziosamente.

## 2. Backtesting — sei motori Python, tre prove differenti

Il terminale Backtesting in src/services/backtesting/BacktestingService.cpp utilizza PythonRunner e i provider in fincept-qt/scripts/Analytics/backtesting. I comandi metadata sono reali, ma non rappresentano una simulazione di mercato.

| Provider | Strategie disponibili | Indicatori metadata | Stato calcolo con serie sintetica |
|---|---:|---:|---|
| VectorBT | 23 | 17 | **PASS**: sei test brokerCandles + un backtest SMA su 320 barre |
| Backtesting.py | 26 | 31 | **PASS, solo fixture con data loader del test**, dettagli addendum V1.1 |
| FastTrade | 20 | 36 | NON TESTATO (pacchetto fasttrade non trovato nel venv1) |
| Zipline | 23 | 17 | NON TESTATO |
| BT | 19 | 17 | NON TESTATO |
| Fincept | 418 | 0 (catalogo indicatore vuoto) | NON TESTATO |

Tutti i **18** comandi metadata (6 provider × get_strategies/get_indicators/get_command_options) hanno restituito le strutture attese nella VM. **Attenzione:** get_indicators torna direttamente con la chiave indicators senza un flag success; verificarlo soltanto come success=true genera falsi negativi.

### Causa riproducibile del backtest VectorBT fallito

Il file src/python/PythonRunner.cpp contiene la stringa "backtesting" nell'elenco kNumpy1Scripts e sceglie il venv con una ricerca per sottostringa. In questa VM, tutti i provider di Analytics/backtesting sono perciò avviati con venv-numpy1, che contiene VectorBT/Backtesting.py/Zipline/BT ma **non yfinance**; quest'ultimo è nel venv-numpy2 insieme a Qlib, XGBoost, LightGBM. Il Python di sistema non è il runtime dei provider.

Nel log del terminale: optimize VectorBT per SPY → errore yfinance is not installed → **rifiuto corretto dell'uso automatico di prezzi sintetici**, non evidenza che tutta l'installazione Fincept sia inutilizzabile.

Non installare ciecamente yfinance nel venv NumPy 1 o spostare VectorBT nel NumPy 2: prima verificare compatibilità, budget e diritti delle fonti. Una soluzione più robusta è un **data adapter read-only** che consegni candele OHLCV con identità, calendario e timestamps attraverso il meccanismo dati esterni già supportato.

### Prove reali e gap di attendibilità

- I 6 test già presenti nel sorgente VectorBT per brokerCandles hanno passato 6/6: single-symbol, multi-symbol, ticker normalization, mancanti, serie troppo corte.
- Un backtest invocato direttamente in venv-numpy1 su 320 barre **fabbricate** KAIROS_FIXTURE ha prodotto success=true, status=completed, con commission 0.001 e slippage 0.0005 dichiarati, dataSource=synthetic-regression-fixture.
- Il provider ha marcato usingSyntheticData=false perché non ha creato lui i prezzi fake: **è falso interpretare quel flag come dimostrazione di dati di mercato reali**. L'adapter KAIROS deve imporre la propria classificazione della fonte, indipendente da Fincept.
- Non è stata validata la fedeltà economica di questo backtest, neppure usando commission/slippage, e non viene qui riportata alcuna performance immaginaria.
- Il nuovo script proposto tools/fincept_audit/offline_backtesting_probe.py serve a ripetere queste verifiche in modalità sintetica, con un guard socket Python di difesa in profondità. **La prima esecuzione falliva per risoluzione del symlink del venv; la correzione e il passaggio integrale sulla VM sono ora VERIFICATI, vedi addendum V1.1.** Le prove manuali dirette sopra sono indipendenti e già PASS. Un test unitario locale **1/1 PASS** su sei provider fittizi verifica il contratto dell'harness, la protezione socket, il caricamento dei metadata, i 320 candle input fittizi e la preservazione del link venv; **non** sostituisce il test completo con i provider installati nella VM.

## 3. AI Quant Lab, Alpha Arena e KAIROS

AI Quant Lab (src/services/ai_quant_lab/AIQuantLabService.cpp) ha un proprio script Qlib-style con run_backtest, separato dagli altri due motori. QuantModulePanel_Backtesting.cpp fa riferimento a simboli Yahoo e può trasferire configurazioni a Backtesting Terminal, ma **non è un motore scientifico KAIROS**. Alpha Arena è un ulteriore sistema competizioni con una superficie LIVE Hyperliquid che non va esposta agli agenti KAIROS.

I laboratori KAIROS esistenti sono progettati per pre-event freeze, separazione storico-as-of vs prospettico, tentativi falliti registrati, valutatore indipendente, net costs, tail/ruin-risk, memoria/evidenze e gate di autorità. Non riprodurre questi sistemi usando il solo motore Algo: usare Fincept come **front-end ricco e catalogo tool**.

**Contratto proposto di integrazione:**

FINCEPT strumenti (Algo DSL/Backtest C++, VectorBT/BT/Python, AI Quant/Qlib, screener, dati, news) → **catalogo tipizzato READ/COMPUTE** con scope/ACL, diritti provider, source_id, actual coverage, available_at, as-of, qualità e budget → LLM (DeepSeek/Claude/GPT/locale) produce ipotesi/esperimenti, non ordini → KAIROS canonical evaluator E0 e ricerca E2, dual-clock PIT, costi, rischio, Gate9R → ledger immutabile e memoria semantica non autorevole → risultato osservabile in FINCEPT/KAIROS UI e queue headless.

**Un sottoinsieme DSL Algo può servire da editor grafico** per proposte KAIROS (entry/exit/indicatori). Modelli ML e piani adattivi avanzati NON sono traducibili automaticamente senza perdita di semantica: conservarli nel laboratorio KAIROS e mostrare in Fincept una descrizione versionata più evidenze. **Non esportare mai al gateway LLM** funzioni start_deployment, order_requested, execute_order, approve, live, broker account/credentials, risk reset o recovery.

Il **servizio di ricerca persistente** deve continuare sul core KAIROS/headless anche quando il processo Qt viene chiuso; AlgoEngine non basta. La sua eventuale funzione di esecuzione resta disaccoppiata dai tool di ricerca.

## 4. Matrice di avanzamento dell'audit COMPLETO

| Area Fincept | Evidenza disponibile | Stato finale attuale |
|---|---|---|
| GUI startup e Builder Algo | Screenshot + processo e log | PASS parziale: una schermata e un backtest |
| Algo strategies/SQLite/scanner/alerts/universe | Sorgenti e navigation wiring | SOURCE-ONLY; CRUD e scanner runtime NOT_TESTED |
| Algo Paper/Live/Recovery | Analisi codice e controlli | REVIEWED SOURCE; non eseguito per sicurezza |
| Algo C++ backtest | Caso Yahoo eseguito | COMPUTE PASS; scientific acceptability FAIL/BLOCKED |
| Backtesting Python 6 motori | 18 metadata PASS | DISCOVERY PASS, non sei backtest |
| VectorBT input dati esterni | 6 test fixture + un backtest 320 barre PASS | FIXTURE PASS, nessuna performance di mercato validata |
| Altri cinque backtest provider | Catalogo e dipendenze | COMPUTE NOT_TESTED |
| AI Quant Lab / Qlib / Deep Agent | Sorgente codice | NOT_TESTED runtime |
| Alpha Arena | Sorgente codice | NOT_TESTED runtime; no live |
| Equity | Freeze precedente, causa ignota | FAIL storicizzato, root cause NOT_VERIFIED |
| MarketData / Dashboard 35 widget / watchlists / news | Log di alcuni ticker mancanti | PASS globale NON VERIFICATO |
| Portfolio/risk/crypto/derivatives/LLM/tools MCP | Censimento parziale statico | NOT_TESTED in questa VM |
| Release parity, CI e 24/7 | Shell e GitHub status | NOT_VERIFIED; GitHub Actions OFF |

**Definizione di un singolo strumento PASS:** risponde, usa la dipendenza corretta, riceve input valido (o fixture dichiarata), rispetta tempi/diritti/provenienza, esegue deterministico, restituisce schema e errori corretti, si visualizza e non può generare mutazioni broker dalla superficie LLM. Un menu caricato non è un test della sua funzione.

## 5. Prossime piccole PR, in ordine

1. **DATA-01 / FB-01:** correggere il percorso dei dati nei 6 backtester senza rovinare gli ambienti NumPy; test offline con candele esterne, distinzione fonte reale vs fixture, fail-closed.
2. **SCI-01 / FB-04/05:** report di copertura effettiva, fees/slippage e valuta nel backtest C++ Algo; marchiare GROSS_EXPLORATORY finché non netto e causalmente valido.
3. **API-01 / FB-03/07/08:** catalogo LLM con regole deny-by-default senza metodi di deploy/ordini/risk reset, anche tramite chiamate dirette MCP.
4. **TOOL-01 / RUN-01:** il primo job KAIROS headless su uno strumento Fincept con fixture e verdict del gate indipendente; chiusura GUI non deve interrompere la ricerca.
5. **QA-LOCAL:** audit sistematico per tutte le schermate e i 35 widget, con tracker PASS / DEGRADED / FAIL / NOT_TESTED e screenshot/log sintetici, senza credenziali.
6. **Legale:** chiarire LICENSE vs COMMERCIAL_LICENSE.md e diritti provider per distribuire il fork, non aggirare servizi a pagamento.

**Stop permanente:** KAIROS security issue #619 e CI quarantine PR #618 aperte, Actions fork disabilitate; nessun deploy IG/demo/live, nessun nuovo servizio privilegiato, nessun broker collegato per test, nessun dato utente o segreto in repo pubblico. L'audit non è autorizzazione di trading.

## Fonti pinned / collegamenti

- Fincept source: https://github.com/cometarossa/kairos-fincept-terminal/tree/7716ee8613249fb44c4d14036c5bc16ed6f34e97/fincept-qt
- Codice centrale: src/screens/algo_trading; src/services/algo_trading; src/algo_engine/AlgoEngine.cpp, BacktestEngine.cpp, CandleDataFetcher.cpp, DeploymentRunner.cpp; src/services/backtesting/BacktestingService.cpp, BacktestingTypes.h; src/python/PythonRunner.cpp; scripts/Analytics/backtesting; src/services/ai_quant_lab/AIQuantLabService.cpp.
- KAIROS canonico SHA 77f0c0cc635945c808cafd581c1bfbcaaddffcac: AGENTS.md, AGENTS_RULES.md, docs/KAIROS_MASTER_ROADMAP.md, PROJECT_STATE.md, docs/KAIROS_DUAL_CLOCK_CONTINUOUS_EDGE_LAB_CHARTER_V1.md, config/kairos_operational_constitution_v1.json.
- Roadmap draft PR #3: https://github.com/cometarossa/kairos-fincept-terminal/pull/3
- LLM tool autonomy draft PR #8: https://github.com/cometarossa/kairos-fincept-terminal/pull/8
- Safe API contract draft PR #9: https://github.com/cometarossa/kairos-fincept-terminal/pull/9
- Linux VM draft PR #10: https://github.com/cometarossa/kairos-fincept-terminal/pull/10
- Sicurezza KAIROS: https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/issues/619 e https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/pull/618
