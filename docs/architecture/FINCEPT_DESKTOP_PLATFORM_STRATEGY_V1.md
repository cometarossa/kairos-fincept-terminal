# Fincept × KAIROS — strategia desktop Linux VM / Windows EXE (V1)

**Data:** 2026-11-08 · **Stato:** proposta architetturale, NON una build o un deploy.

## Decisione operativa

**Primo ambiente: riutilizzare la VM Linux Debian già disponibile per integrare e collaudare Fincept, preservando la GUI e TUTTI gli strumenti.** Windows x64 con eseguibile e installer nativo rimane un target di distribuzione successivo, non una precondizione. Conservare compatibilità Linux, macOS e Windows.

Il desktop Fincept deve restare distinto dal decision plane headless persistente (catalogo strumenti, agenti LLM, code e memoria) e dai servizi scientifici/rischio KAIROS già esistenti. La GUI può essere chiusa senza fermare i job. Il sistema operativo del desktop NON concede autorità broker. Un LLM può leggere soltanto strumenti Fincept esplicitamente autorizzati e le proprie decisioni devono attraversare i gate KAIROS, mai comandare ordini direttamente.

## Evidenze verificate

- Fork Fincept main SHA **7716ee8613249fb44c4d14036c5bc16ed6f34e97**: fincept-qt/CMakePresets.json presenta win-dev, win-release, linux-release e macos-release; CMake contiene windeployqt e installer Qt Installer Framework/CPack IFW. Sono percorsi nel sorgente, **non build verificate**.
- Packaging Linux AppImage e flatpak presente nel sorgente; pipeline upstream .github/workflows/build-cpp.yml contiene Windows x64/ARM64, Linux x64 e macOS. GitHub Actions nel fork restano **DISABILITATE**, senza riattivazione sui runner privilegiati.
- VM verificata in sola lettura il 2026-11-08: Debian GNU/Linux 13 sotto QEMU/HVF su iMac, 4 vCPU, **6144 MB RAM**, root **16 GB / circa 4 GB liberi**, processo FinceptTerminal presente. Non è una compilazione verificata del fork e non dimostra che ogni modulo funzioni. Nessun processo è stato riavviato né installato.
- **Capacità**: con soli 4 GB liberi, NON presumere che la VM corrente possa ospitare l'intera build Qt/C++, dipendenze e installer. Usare un builder Linux separato o dimensionare la VM dopo misure/backup. La VM sull'iMac non offre ridondanza fisica o uptime 24/7.
- KAIROS issue P0 #619 OPEN, quarantena CI PR #618 OPEN/DRAFT. Nessun nuovo servizio sullo ZimaBlade, integrazione IG, DEMO/LIVE, account, credenziali o broker mutation.

## Confronto per lo sviluppo

| Opzione | Uso raccomandato ora | Evoluzione |
|---|---|---|
| VM Linux Debian sul Mac, già disponibile | **Smoke test GUI e strumenti Fincept**, debugging isolato e verifiche del modulo KAIROS | Builder Linux dimensionato, AppImage o installer quando legale e testato |
| Windows EXE nativo | Non prioritario per primi test: richiede macchina Windows, Qt, MSVC, librerie, packaging WebEngine/Python | Release Windows x64 su macchina dedicata (per es. DEKU quando online) con test di regressione e installer |
| GUI Linux sullo ZimaBlade | Non necessaria; può contendere risorse ai servizi KAIROS | Mantenere ZimaBlade headless; upgrade hardware solo dopo misure |
| Nodo separato per training / laboratorio pesante | Da pianificare dopo benchmark | CPU/RAM/GPU e isolamento adeguati, indipendenti dalla GUI |

## Percorso di accettazione

1. DEV-00: inventario dei componenti Fincept realmente disponibili, loro entitlement, costi, permessi, dipendenze ed equivalenti KAIROS; non eliminare widget per aggirare bug.
2. DEV-01 / QA-LOCAL: preparare una build riproducibile Linux del fork su builder isolato e verificare l'eseguibile, plugin Qt/WebEngine, Python, dashboard, Equity, laboratori AI/Quant e backtest, segnando per ogni funzione PASS/DEGRADED/FAIL.
3. API-01 / API-SCI-00: sviluppare gateway di tool read-only con provenance, timestamp e validazione dei dati; negare tutti i tool di trading mutanti. La connessione IG è esclusa da questo POC.
4. UI-01 / TOOL-01: integrare il modulo KAIROS nella GUI Fincept, riutilizzando strumenti e servizi senza duplicarli; primo tool scientifico verificato su dati sintetici.
5. RUN-01: dimostrare che un job simulato degli agenti continua dopo la chiusura della GUI e che il ripristino non duplica risultati.
6. Solo dopo, testare il packaging Windows nativo con gli stessi gate e una matrice di funzionalità confrontabile.

**Stop:** licenze non chiarite, plugin o dipendenze mancanti, dati non PIT/provenance grade, build che blocca il desktop, accesso broker mutante, CI privilegiata non isolata, degrado dello ZimaBlade o spese provider non autorizzate.

**Roadmap:** collegare questa decisione alla [PR #3 Master Roadmap](https://github.com/cometarossa/kairos-fincept-terminal/pull/3), e alla [PR #8 accesso LLM ai tool e gate](https://github.com/cometarossa/kairos-fincept-terminal/pull/8). Non sostituisce Gate9R e non autorizza alcun deploy.
