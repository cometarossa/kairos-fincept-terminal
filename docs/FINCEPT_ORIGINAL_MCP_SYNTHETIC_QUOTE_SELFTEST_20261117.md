# Fincept F1 — vero get_quote MCP con quotazione sintetica in cache

**17 novembre 2026 · PR draft dipendente da Fincept #56 · Solo QA**

## Modifica reale

Il test nativo originale `--selftest-mcp-server` esegue ora una nuova
prova end-to-end nel **vero processo FinceptTerminal e nel vero server
HTTP/MCP**. L'oggetto `McpProvider` e l'handler `get_quote`
registrati dall'applicazione non sono sostituiti da stub.

L'originale `MarketDataService::fetch_quotes()` legge la cache SQLite
prima di richiedere dati al runner Python. Il test prepara, in un profilo
temporaneo, `market:KAIROSQA` con:

- `symbol=KAIROSQA` (ticker intenzionalmente sintetico);
- `price=111.5`, `change=1.0`, `change_pct=0.91`;
- `high=114.0`, `low=110.0`, `volume=1000`;
- `_fincept_local_received_at_utc=2000-01-01T00:00:00.000Z`:
  **metadato fittizio di ricevuta locale**, non timestamp di mercato;
- TTL locale di 30 secondi, categoria `mcp_selftest_synthetic`.

**Fail-closed:** prima di chiamare `get_quote` il test verifica che
`CacheDatabase` sia aperto e che la cache restituisca esattamente
la fixture scritta. Se la scrittura o la lettura falliscono, il test
**non richiama l'handler**, evitando il percorso verso
`yfinance_data.py` e segnalando un fallimento. Al termine elimina
la sola voce `market:KAIROSQA`. Non cancella l'intera cache.

Il tool `get_quote` viene invocato tramite il normale percorso
`tools/call` MCP HTTP autenticato dell'autotest, su porta assegnata
da macOS e in ascolto soltanto in loopback. L'handler reale carica
la fixture tramite `MarketDataService` e genera la sua risposta
`structuredContent` standard.

Cinque nuovi controlli richiedono:

1. Database cache aperto.
2. Fixture sintetica effettivamente disponibile prima dell'invocazione.
3. Risposta MCP reale con simbolo e prezzo corretti, senza errore.
4. `delivery_origin=unexpired_cache_hit`, ricevuta invariata;
   `market_as_of_utc=null` e `market_age_seconds=null`.
5. Tutti i flag `market_as_of_verified`, `freshness_verified`,
   `receipt_clock_verified`, `execution_eligible` e
   `scientific_claim` devono essere `false`.

Il test originale MCP passa così da 41 a **46 assertion**, senza
modifiche alla logica produttiva. Il wrapper QA pubblicato nella
PR madre `test_full_qt_native_selftests.py` ora richiede 46/46 e
la presenza esplicita dei nuovi cinque messaggi di successo; un
vecchio eseguibile che termina a 41 non può essere accettato
silenziosamente.

## Evidenza locale, Qt 6.8.3 esatto

Compilazione incrementale originale con AppleClang 16, CMake 4.0.1,
Qt 6.8.3 EXACT su Mac Intel, a partire dal codice Fincept #56
`90b01d6c898166cded42261b14d3c135cd41f972` più la
**sola differenza CMake** della PR indipendente #57, ancora non
integrata, in un worktree usa-e-getta.

- MOC + compilazione di `McpServerSelfTest.cpp` + link
  `FinceptTerminal.app`: **exit 0**, 3/3 passi incrementali.
- SHA256 del binario di prova:
  `a52ea29a4288d9e76a2496bb2c797d1d68b501fc8ca3d2df3481d2cb3166b788`.
- `--selftest-mcp-server` con HOME/XDG temporanei, Qt offscreen
  e **Seatbelt che nega rete esterna e ammette soltanto loopback**:
  **46/46 PASS, exit 0, 479 ms**, cinque nuovi controlli PASS.
- Wrapper nativo pubblicato (12 suite disponibili, controllo rete,
  test GUI 52 schermate, controlli MCP): **4/4 Python unittest PASS**,
  ~25 secondi, sullo stesso binario modificato.
- Restano non bloccanti il warning linker già noto su md4c e
  l'assenza di firma/distribuzione dell'app sperimentale.

### Come riprodurre

Con un nuovo `FinceptTerminal` costruito dal codice di questa PR
(con Qt6.8.3 e eventuali dipendenze build già predisposte):

```sh
FINCEPT_QT_NATIVE_BINARY=/path/to/new/FinceptTerminal \
  python3 -m unittest discover -s tests/fincept_original \
  -p 'test_full_qt_native_selftests.py' -v
```

Il wrapper **SKIPPA** se non viene selezionato un eseguibile; fallisce
se manca il sandbox macOS o se l'eseguibile non supera i test.
Non scarica dati né accede a provider.

## Limiti espliciti

Questo test verifica **l'handler originale di quotazioni attraverso
il server HTTP originale**, non un server falso. Non verifica che
KAIROS #655 sia già connesso al server Fincept (quel client è una
PR separata e non deployata); non prova la reale invocazione storica
`get_history` con barre sintetiche. Per la storia, il codice
originale invoca direttamente il runner `yfinance_data.py`, quindi
serve un seam/fixture sicuro e separato prima di chiamarlo in QA.

Nessun dato di mercato effettivo, Yahoo, IG, sessione broker,
ordine, API a pagamento, cambiamento di autorizzazione LIVE,
nuovo servizio, merge o deploy. **Quotazione sintetica soltanto.**

## Prossimo F1

Testare con **il client KAIROS #655** il server MCP originale, sempre
con dati sintetici e una tokenizzazione test-only in ascolto su
loopback; sviluppare successivamente una fixture isolata per
`get_history` senza chiamare il runner provider. L'integrazione
multi-host autenticata e Fincept headless/Linux restano gate futuri.


## 2026-11-17 — External original-server KAIROS client QA (companion #655)

This PR now optionally launches the **actual independent KAIROS Python MCP
client** from [KAIROS DRAFT #655](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/pull/655) **while the real Fincept Qt MCP HTTP server is serving requests**.

The original test remains entirely unchanged for operators who do not set
the two explicit test-only environment variables:

- `FINCEPT_KAIROS_QA_CLIENT_SCRIPT`: absolute path to the external
  KAIROS `tests/test_fincept_original_mcp_crossprocess_v1.py`;
- `FINCEPT_KAIROS_QA_PYTHON`: absolute path to the Python interpreter.

The original C++ selftest runs a child process **only after**
`market:KAIROSQA` has been seeded and read back exactly from the real
SQLite cache. If the seed fails, it **never runs the external probe nor
calls `get_quote`**. Invalid or incomplete test-executable paths fail
the requested QA explicitly.

The child inherits **only** a new restricted environment containing
a temporary HOME/TMPDIR, a standard executable PATH,
`PYTHONDONTWRITEBYTECODE=1`, and the per-test ephemeral loopback
port and random selftest Bearer token (`KAIROS_QA_MCP_PORT`,
`KAIROS_QA_MCP_TEST_TOKEN`). It does NOT inherit user Fincept login,
keychain, provider, broker or market tokens from the parent process.
Neither the token nor the quote/provider responses are printed.
The original Qt event loop remains pumped while the Python client is
running. The child has a 20-second execution watchdog and is killed
on timeout. Errors fail the selftest without a retry or trade.

The standalone KAIROS client verifies real `initialize`,
`notifications/initialized`, and `tools/call get_quote` with
strict metadata/provenance checks, denies `live_get_quote` before I/O,
and checks that Fincept's actual HTTP server rejects an invalid
test Bearer token. The matching Fincept native assertion requires
the exact `KAIROS_ORIGINAL_FINCEPT_MCP_CLIENT_PASS` marker and a
zero child exit code. This proves an actual cross-process C++/Python
protocol integration, not only an internal Qt server selftest.

**Native Qt 6.8.3 (AppleClang16) evidence:** incremental MOC,
`McpServerSelfTest.cpp` compile and final link **3/3 PASS**.
The changed unsigned lab binary SHA256 is
`7b7f5625bc68dbd614f478b49d595f7cd4278d1e024eddfe9845af3d3397834d`.
KAIROS opt-in external Python unittest passed **1/1** including
original C++ selftest **47/47**; the test runs in a fresh temporary
HOME/XDG profile under macOS Seatbelt with all external network
denied and localhost only allowed, verified by an `EPERM` socket
preflight. The default Fincept MCP selftest **without opt-in**
remains **46/46**. One prior wrapper run failed only its Python
loopback-bind preflight with `EPERM`: the same macOS Seatbelt profile
can refuse a local `AF_INET` bind to the Python diagnostic binary even
while the actual Qt MCP server can successfully bind on localhost. The
wrapper now requires the Python preflight to attest **outbound external
socket denial** with `EPERM`, while the independently run original Qt
MCP selftest itself proves **positive loopback bind/connect**. It does
**not** expand the sandbox's network permissions.

Still **not verified/authorized**: `get_history` synthetic fixture,
the production KAIROS adapter, real providers, encrypted remote bridge,
Linux headless, data freshness, scientific edge, IG session, or broker
orders. PR #58 depends on unmerged #56; PR #57 is a separate
unmerged build-pin fix. No merge/deploy or authority expansion.
