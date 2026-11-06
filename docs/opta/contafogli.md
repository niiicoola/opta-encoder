# Contafogli HESCHEN E3F-DS10P3 su Opta Lite

Un progetto e due modalita' di acquisizione: `rotary_encoder` e `sheet_counter`.
Il profilo JSON sceglie la modalita' **in compilazione**. Non esiste ancora un
parametro modificabile a caldo via rete: cambiare modalita', polarita' o filtri
richiede una nuova release e il riavvio del dispositivo.

Il progetto conserva lo sketch `firmware/opta_encoder_lan`, il server OPC UA,
BootId, le letture coerenti e l'aggiornamento LAN firmato. Il contafogli ha un
namespace e nodi propri: non presenta i fogli come metri, giri o posizione A/B.
I profili rotativi storici rimangono supportati senza modificarne i NodeId.

## Profilo iniziale e limiti

`profiles/heschen-e3f-ds10p3-sheets.json` descrive il sensore PNP NO+NC,
alimentato a 24 V, su I1. La velocita' nominale richiesta e' 50 fogli/minuto,
con fogli separati da un interspazio. Questa velocita' non e' una soglia software
che scarta automaticamente passaggi piu' rapidi.

Filtri iniziali: presenza stabile per 2 ms e assenza stabile per 2 ms. Sono
valori provvisori, non una qualifica: il tempo di risposta del sensore e la
durata effettiva dell'interspazio devono essere verificati. Non basta il numero
medio di fogli/minuto per conoscere la durata minima del segnale.

La pagina HESCHEN dichiara PNP NO+NC, 10-30 V DC, rilevamento diffuso di oggetti
opachi, distanza 10 cm. Contiene descrizioni generiche non uniformi e non
pubblica un tempo di risposta preciso: confermare la variante e il cablaggio.
Fonte: https://heschen.com/products/heschen-e3f-ds10p3

Non rileva doppio foglio, verso di avanzamento, qualita' o scarti. Un foglio
che libera completamente il sensore e ripassa puo' essere contato di nuovo.
Verificare stampa, colore, lucidita' e fondo macchina. Il rilevamento del piano
durante l'interspazio impedisce il riarmo. Un sensore bloccato non viene
distinto automaticamente da una macchina ferma.

Il firmware resta `TestMode=true`, `MeasurementValid=false`: non contabilizzare
automaticamente la produzione. Il totale e' in RAM e riparte da zero al riavvio.
Una lettura o riconnessione del client non azzera il contatore. Non e' presente
un comando remoto di reset.

## Cablaggio funzionale

Eseguire i collegamenti ad alimentazione e USB scollegate. I colori e i pin
devono essere verificati sullo schema fornito con il sensore: non dedurli da
quelli di un altro encoder o sensore.

| Collegamento | Destinazione |
|---|---|
| Positivo alimentatore 24 V DC | Positivo sensore e morsetto + Opta |
| 0 V alimentatore | 0 V sensore e morsetto - Opta |
| Uscita PNP NO | I1 Opta |
| Uscita NC | Scollegata e isolata |
| I2 Opta | Non usato dal profilo contafogli |

Non servono pull-up esterni per questa uscita PNP. NO e NC sono uscite
complementari di presenza, non le due fasi di un encoder. Gli ingressi sono
digitali; i quattro rele' vengono mantenuti spenti.

## Logica e acquisizione

1. All'avvio il dispositivo non e' riarmato: un foglio gia' presente non viene
   contato. Serve prima un'assenza continua di almeno `clear_stable_us`.
2. Dopo il riarmo, una presenza continua di almeno `present_stable_us`
   incrementa il totale una sola volta.
3. Il foglio puo' rimanere fermo davanti al sensore senza nuovi conteggi.
4. Serve un nuovo interspazio stabile per riarmare il dispositivo.

I fronti su I1 sono acquisiti con interrupt `CHANGE`; un timer ogni millisecondo
conferma la stabilita' anche se la rete e' lenta o non disponibile. Nessun filtro
adattivo sulla velocita'. Un impulso breve non viene contato e incrementa la
diagnostica relativa. Anche gli interspazi brevi vengono diagnosticati.
Questi contatori non provano da soli l'assenza di impulsi persi.

I fogli/minuto derivano dall'intervallo fra gli ultimi due conteggi, non da una
finestra di 60 secondi. Dopo il primo foglio la velocita' non e' ancora disponibile;
lo stesso accade dopo 10 secondi senza conteggi. `RateValid=false` distingue
questo caso: il campo numerico viene posto a zero. `InputActive` e' il livello
logico grezzo di presenza; `Armed` indica il riarmo ottenuto dopo il filtro.

## Compilazione e installazione

Eseguire dalla radice del repository:

```sh
python3 tools/build_opta_lan.py --version 0.4.0-lan --profile heschen-e3f-ds10p3-sheets
```

Il comando compila e archivia; non carica il BIN. Una release esistente non viene
sovrascritta. Per modifiche successive scegliere un nuovo numero di versione.
`--encoder-profile` resta un alias di `--profile` per i comandi precedenti.

Modello di registro: `devices/example-sheets.json`. Il campo storico
`encoder_profile` puo' ora selezionare anche un profilo contafogli; il manifest
aggiunge `acquisition_mode` e riporta `counts_per_revolution: null` per i fogli.
La procedura USB rimane quella di `preparazione-serie.md`: prima identificare e
registrare il seriale del nuovo Opta; il caricamento richiede `--apply`.
Non usare il seriale o l'indirizzo della macchina rotativa per un nuovo dispositivo.

La memoria OTA di un Opta nuovo va predisposta solo secondo la procedura
esistente: l'inizializzazione e' consentita esclusivamente su memoria vuota.
Per gli aggiornamenti conservare la chiave privata autorizzata: non rigenerarla
per sostituire quella gia' associata ai dispositivi.

## Lettura e configurazione GERP

Endpoint: `opc.tcp://IP_OPTA:4840`. Namespace URI: `urn:gerp:sheet-counter:v1`.
L'indice numerico `ns` va risolto sul dispositivo, non assunto uguale a 2.

```sh
.venv/bin/python tools/read_sheet_counter_opcua.py opc.tcp://IP_OPTA:4840 --allow-test --diagnostics --samples 10
```

Esempio puramente illustrativo, non letto da un dispositivo:

```json
{
  "SheetCounter.TotalSheets": "50",
  "SheetCounter.SheetsPerMinute": 50.0,
  "SheetCounter.RateValid": true,
  "SheetCounter.InputActive": false,
  "SheetCounter.Armed": true,
  "SheetCounter.TestMode": true,
  "SheetCounter.MeasurementValid": false,
  "Device.AcquisitionMode": "sheet_counter"
}
```

Il lettore verifica BootId e SampleSequence prima/dopo, qualita' OPC UA e
modalita'. I totali a 64 bit sono restituiti come stringhe JSON. Il lettore
encoder e il lettore fogli non accettano il namespace dell'altra modalita'.

| Nodo | Utilizzo |
|---|---|
| SheetCounter.TotalSheets | Totale fogli dal riavvio |
| SheetCounter.SheetsPerMinute | Fogli/minuto; leggere anche RateValid |
| SheetCounter.InputActive | Segnale grezzo di presenza |
| SheetCounter.Armed | Pronto a contare il prossimo foglio |
| SheetCounter.RejectedPresentPulses | Presenze piu' brevi del filtro |
| SheetCounter.RejectedClearPulses | Assenze piu' brevi del filtro |
| SheetCounter.ProfileId | Profilo firmware del sensore |
| SheetCounter.PresentStableUs / ClearStableUs | Filtri effettivi |
| Device.BootId / UptimeMs | Riavvii e aggiornamento delle letture |

Nel generico OPC UA di GERP iniziare con sola dashboard, direzione `out (read)`
e raccordi vuoti. Il totale fogli non va collegato ai metri. Prima dell'uso sulle
commesse servono gestione della baseline, riavvii e qualita' del dato come per
la soluzione rotativa. Il generico non applica automaticamente i controlli del
lettore Python dedicato.

HTTP `:8080/status` conserva i campi OTA e aggiunge modalita' e profilo. In
modalita' contafogli `position` e' `null`, `total` e `sheet_count` sono il numero
di fogli; i rifiuti dei filtri sono separati da `errors`.

## Collaudo prima della produzione

1. Avvio con sensore libero e con foglio gia' presente: nessun conteggio spurio.
2. Passaggio di un numero noto di fogli, prima lento e poi a 50 fogli/minuto.
3. Foglio fermo davanti al sensore: un solo conteggio.
4. Arresti, ripartenze, fogli scuri/lucidi/stampati e minima distanza di interspazio.
5. Disconnessione Ethernet e riconnessione: il totale deve continuare se Opta e
   sensore restano alimentati; il client non deve azzerarlo.
6. Riavvio: BootId cambia e il totale riparte da zero. GERP non deve trattare
   questo evento come un calo della produzione.

Le prove automatiche coprono la logica e un server OPC UA locale. Non qualificano
sensore, cablaggio e ingressi fisici. Non e' stato caricato firmware su hardware
nella preparazione di questa modalita'.
