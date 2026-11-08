# Fincept × KAIROS — Addendum audit funzionale VM V1.1

**2026-11-08** · Una nuova prova read-only del fork Fincept, senza GUI restart, broker, ordini, account o download di dati di mercato.

## Risultato 1: harness completo VectorBT sul runtime installato

- Eseguito sulla VM Debian 13 già disponibile, utilizzando il venv-numpy1 esistente, il sorgente/script realmente installato e lo strumento di questa PR: tools/fincept_audit/offline_backtesting_probe.py.
- **18/18 interrogazioni metadata PASS** sui sei provider (strategie, indicatori, opzioni); **1/1 backtest VectorBT PASS** su 320 candele OHLCV fabbricate deterministically, attraverso brokerCandles. Exit code 0.
- L'iniziale falso FAIL del nostro harness era causato dall'uso di Path.resolve() sull'interprete virtuale: sostituiva il link venv/bin/python con il binario globale, perdendo le dipendenze. Corretto e verificato questa volta sulla VM reale.
- Il flag provider usingSyntheticData=false rimane NON una prova di prezzi reali: indica soltanto che non è stato usato il fallback sintetico interno. I dati iniettati nel nostro test sono comunque fittizi.
- Il controllo del blocco socket nell'harness è ora puramente un confronto di identità del patch sitecustomize, **non** tenta alcuna connessione per autoverificarsi. Si tratta di defense in depth Python, non di isolamento OS totale.

## Risultato 2: Backtesting.py reale, seconda famiglia di calcolo

- Nuovo strumento tools/fincept_audit/backtestingpy_fixture_probe.py; importa BacktestingPyProvider dalla installazione esistente e imposta un data-loader **solo nell'istanza di test**, anziché leggere Yahoo. Questo provider non offre oggi una seam brokerCandles pubblica equivalente a quella di VectorBT: **questo test non prova l'integrazione esterna produttiva**.
- Due run sulla stessa serie di **260 barre OHLCV sintetiche** della strategia SMA crossover: con commissioni/slippage zero e poi con commission=0.001 e slippage=0.0005. **Entrambi PASS**, 9 operazioni ciascuno, il capitale finale con costi inferiore a quello senza costi. Niente performance finanziaria pubblicata né affermazione di alpha.
- Fixture SHA256: 33aa75a3f9c784388bc81ff2ad1db0cdc2b0115881b70ba063973b966aa17d00.
- SHA256 del provider installato: d368964e2de586ee7d239dc6bfaf2468bc4421d59ede260759c98b1a8b5ff3f8.
- La simulazione segnala un trade ancora aperto alla fine: la gestione delle posizioni finali resta da verificare. Nel sorgente Backtesting.py Fincept **somma lo slippage alle commissioni** e passa la somma al parametro commission del motore; provare una sensibilità ai costi non dimostra una modellazione realistica di spread, execution price e liquidità.
- Network guard presente; i test sono sintetici e non importano risultati di mercato reali. La fonte è SINTETICA anche se bypassiamo manualmente il data-loader dell'istanza di prova.

## Test di regressione e stato dei sei provider

| Motore | Metadata | Calcolo vero in fixture | Collegamento dati esterni pronto |
|---|---|---|---|
| VectorBT | PASS | PASS 320 barre | brokerCandles esistente, ma occorrono controlli KAIROS |
| Backtesting.py | PASS | PASS 260 barre, test-only loader | NO: override usato solo nel test |
| FastTrade | PASS | NOT_TESTED | NOT_VERIFIED |
| Zipline | PASS | NOT_TESTED | NOT_VERIFIED |
| BT | PASS | NOT_TESTED | NOT_VERIFIED |
| Fincept | PASS | NOT_TESTED | NOT_VERIFIED |

- Due test locali della tool suite: **2/2 PASS**; uno verifica il contratto mock, l'altro verifica che lo strumento Backtesting.py rifiuti di partire senza la guardia.
- Test diretti con gli script aggiornati sulla VM: VectorBT e Backtesting.py PASS. I metodi del provider originale sono stati eseguiti senza modificare i suoi file di produzione.
- Il problema funzionale originario resta: i backtester eseguiti da PythonRunner usano venv-numpy1, mentre yfinance è soltanto in venv-numpy2. Questo addendum **non risolve** il normale caricamento dati dalla GUI.
- Non attribuire questa verifica alla GUI, ai test E2E del modulo Algo C++ o ai gate scientifici KAIROS.

## Conseguenze per KAIROS e priorità

1. Evitare duplicati: PR #13 e #14 si occupano già della provenance OHLCV e del ponte dati sintetico VectorBT. Questa PR #11 è l'audit del funzionamento reale dei motori e i suoi test indipendenti.
2. Continuare la matrice sui quattro altri provider di calcolo, con input deterministici e permessi read-only. Poi verificare il percorso GUI e le librerie AI Quant Lab.
3. Verificare costi realistici, gap, finestre temporali effettive, titoli e valute. Non validare come scientificamente attendibile nessun backtest Fincept soltanto perché ha completato il calcolo.
4. Mantenere inaccessibili al gateway LLM i comandi di trading, deploy, recupero deployment e reset del rischio: la costituzione canonica di KAIROS resta superiore.

**Blocchi:** KAIROS P0 issue #619 OPEN, quarantena CI PR #618 OPEN/DRAFT; Actions fork OFF, licenza/redistribuzione del fork da chiarire. Non è stato modificato alcun servizio ZimaBlade.
