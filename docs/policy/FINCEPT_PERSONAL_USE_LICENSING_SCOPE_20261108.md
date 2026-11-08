# FINCEPT × KAIROS — perimetro d'uso personale e priorità LEG-01

**Decisione esplicita dell'operatore: 2026-11-08.** Il prodotto Fincept × KAIROS è sviluppato e utilizzato **esclusivamente per finalità personali, non come software commercializzato o distribuito a clienti**. La UI originale Fincept e gli strumenti utili devono essere preservati, prima verificati e poi connessi ai servizi scientifici KAIROS. Questa decisione non autorizza broker mutation, credenziali o aggiramento di servizi Enterprise.

## Decisione operativa vincolante

**LEG-01 non è più un blocco P0 per sviluppo privato, audit funzionale, esecuzione privata in VM, test sintetici, costruzione di moduli propri e integrazione headless personale.** Il perimetro non commerciale è la premessa operativa dichiarata dal proprietario. Non ripetere una richiesta di autorizzazione commerciale come prerequisito di ogni incremento.

**Rimane un checkpoint LEG-01 mirato (non bloccante di default)** prima di: distribuzione di installatori o fork modificati a terzi; apertura dell'applicazione modificata a utenti di rete terzi; pubblicazione di asset/integrazioni proprietarie; introduzione di credenziali o accesso a dati/provider con condizioni contrattuali; sfruttamento di marchi in modalità vietata. Ogni task deve verificare soltanto le licenze o i diritti effettivamente coinvolti, e non fermare tutto il programma per una questione astratta.

## Fonti verificate al 2026-11-08

1. [Fincept open-source LICENSE](https://github.com/Fincept-Corporation/FinceptTerminal/blob/main/LICENSE): contiene AGPL-3.0-or-later **e** residui di una vecchia comunicazione dual-license, con dichiarazione esplicita di uso personale gratuito. È una discrepanza documentale, **non** un motivo per negare la licenza privata.
2. [Fincept docs/COMMERCIAL_LICENSE.md V3](https://github.com/Fincept-Corporation/FinceptTerminal/blob/main/docs/COMMERCIAL_LICENSE.md), in vigore dal 2026-08-11: afferma che il repository open-source è concesso sotto AGPL-3.0-or-later senza licenza commerciale separata per quel repository. Indica che eseguire/modificare il terminale sulla propria macchina senza distribuirlo **non comporta obbligo di pubblicare le modifiche**. Enterprise è un prodotto separato e closed source. Il testo dichiara espressamente la sostituzione della precedente V2.
3. [Fincept README — license](https://github.com/Fincept-Corporation/FinceptTerminal/blob/main/README.md): conferma AGPL-3.0-or-later e uso personale non distribuito.
4. [GNU/FSF FAQ](https://www.gnu.org/licenses/gpl-faq.en.html): modifiche usate privatamente non richiedono la distribuzione del codice; per versioni AGPL modificate con accesso tramite rete da altri utenti si applica §13.

**Limiti di queste fonti:** nessuna analisi legale indipendente è stata effettuata. Se un comportamento futuro è realmente distributivo, esterno, monetizzato come prodotto/servizio o coinvolge dati commerciali, riverificare i diritti pertinenti; non inferire permessi su provider, dati, marchi o servizi Enterprise dalla sola licenza del codice.

## GitHub pubblico e oneri ridotti ma non nulli

Il fork `cometarossa/kairos-fincept-terminal` è **pubblico**. Ogni modifica di software Fincept effettivamente pubblicata deve rispettare AGPL-3.0-or-later, copyright, note di licenza e attribuzioni. Non pubblicare chiavi, credenziali, dataset privati o copie di asset terzi senza diritti. Le modifiche personali che **non** vengono condivise non richiedono automaticamente la pubblicazione, salvo condizioni che si attivino in situazioni diverse, come l'accesso di altre persone a un servizio AGPL modificato su rete.

Avere una GUI desktop e servizi locali headless non li rende automaticamente un SaaS distribuito. Ma se si cambia la topologia e si concede a **terzi** accesso di rete a un componente AGPL modificato, rivalutare gli obblighi §13. Conservare comunque marchi/attribution appropriati e distinguere il nostro fork dal prodotto originale. La documentazione v3 richiede un branding separato se si diffonde il derivato.

## Conseguenze per roadmap e automazione

- **Risolvere prima i blocchi reali**: KAIROS security [#619](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/issues/619) e CI quarantena [#618](https://github.com/cometarossa/multi-asset-trading-system-hermes-autonomy/pull/618) per runner privilegiati/deploy/broker; affidabilità data provider, provenienza temporale, controllo dei costi, errori reali Backtesting e Algo, e gate indipendenti.
- **Sviluppo privato Fincept-first consentito** in sandbox isolato: test su VM Debian, tool read-only, agenti su fixture, miglioramenti dell'interfaccia senza redesign preventivo, esperimenti con librerie disponibili. Nessun ordine o servizio produttivo per effetto di questo documento.
- **LEG-01 torna P2/CONDITIONAL** rispetto al programma non commerciale. L'inventario source-only [draft PR #4](https://github.com/cometarossa/kairos-fincept-terminal/pull/4) resta utile e non è annullato, ma non impedisce DEV-01, DATA-01, TOOL-01, API-01 e l'audit delle funzioni di procedere su codice/fixture già lecitamente utilizzabili.
- **Audit funzionale prioritario**: [draft PR #11](https://github.com/cometarossa/kairos-fincept-terminal/pull/11) con test effettivi di Backtesting e Algo, come richiesto dall'operatore; poi DATA-01/SCI-01 sul contratto temporale, GUI e AI Quant Lab.
- Qualsiasi task che scopra un nuovo obbligo concreto lo registra come **rischio locale al componente** e non impone un blocco generale senza una base fattuale.
- Questa è una **proposta di governance in PR separata**: finché non viene recepita nella master roadmap [draft PR #3](https://github.com/cometarossa/kairos-fincept-terminal/pull/3), l'automazione deve consultare entrambe, segnalare il contrasto e applicare la decisione esplicita dell'operatore compatibilmente con la costituzione KAIROS.

## Cosa non cambia

- Nessun accesso automatico ai componenti proprietari Fincept Enterprise.
- Nessun diritto automatico ai dataset/API che richiedono abbonamenti.
- Nessuna autorità di trading reale, DEMO, cancel, Square Off, broker order o risk override.
- Nessun superamento della sicurezza P0 o della segregazione scientifica dual-clock/Gate9R.
- Nessun obbligo di stravolgere UI Fincept, rinunciare agli strumenti utili o ricostruire da zero un terminale già funzionante.
