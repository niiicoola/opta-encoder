# Guida del tecnico: preparare, verificare e aggiornare un Opta Lite

Procedura per **Arduino Opta Lite AFX00003**, con firmware Arduino/C++ di questo
repository. Non usare Arduino PLC IDE per caricare questo progetto.
Eseguire i comandi dalla radice del repository, su macOS o Linux.

## 1. Cosa può fare il tecnico e cosa deve ricevere

Il tecnico può installare una release via USB, predisporre OTA, fissare
l'indirizzo con una prenotazione DHCP e verificare HTTP/OPC UA. In seguito può
aggiornare via LAN, senza USB, se il firmware continua ad avviarsi e la memoria
OTA è pronta. Il recupero di un aggiornamento che impedisce l'avvio della rete
richiede ancora accesso fisico e USB: non c'è rollback automatico.

La versione attuale è **diagnostica**, anche dopo un'installazione riuscita:
`TestMode=true`, `MeasurementValid=false`, contatori in RAM azzerati al riavvio.
Il collaudo della misura e la gestione dei riavvii in GERP sono attività
distinte. Il contafogli è compilato e provato con test software, ma non ancora
collaudato su un Opta con sensore fisico.

Prima di iniziare, il responsabile deve consegnare:

- commit/tag approvato e profilo da usare, modello e schema del sensore;
- identificativo dell'unità, sede e macchina associata;
- rete, subnet, gateway, DNS e indirizzo assegnato dal referente IT;
- accesso al router DHCP oppure indicazioni per il caso statico del punto 6;
- chiave di firma autorizzata, oppure pacchetto BIN già compilato e relativo
  manifesto. Un BIN permette l'installazione USB; per aggiornare via LAN serve
  anche la chiave privata corrispondente a quella pubblica nel dispositivo;
- autorizzazione a sostituire l'applicazione precedente, se la scheda è usata.

Il solo clone Git non contiene chiavi, BIN, inventario reale o rapporti:
questi elementi sono esclusi dal repository e vanno consegnati separatamente.
Non pubblicare la chiave privata, neppure se il repository è privato.

Materiale: cavo USB **dati**, Ethernet verso switch/router con DHCP,
alimentatore DC adatto all'Opta e al sensore, cablaggio verificato.
Per il collaudo fisico alimentare dai morsetti secondo le specifiche dei due
dispositivi; la USB non sostituisce l'alimentazione del sensore.
Eseguire i collegamenti elettrici ad alimentazioni scollegate.

## 2. Preparare il computer

Servono Git, Python >= 3.9, OpenSSL e Arduino CLI. Installare Arduino CLI dalle
[istruzioni ufficiali](https://arduino.github.io/arduino-cli/latest/installation/).
Su macOS viene cercato anche il CLI incluso in Arduino IDE; su Linux deve
essere nel PATH, oppure indicato con la variabile `ARDUINO_CLI`.
Gli strumenti seriali usano `termios`/`fcntl`: questa procedura non supporta
Windows nativo. Su Linux l'utente deve avere accesso alla porta seriale,
secondo le regole della distribuzione; non eseguire tutta la procedura con sudo.

```sh
git clone --branch codex/opta-provisioning https://github.com/niiicoola/opta-encoder.git
cd opta-encoder
git status
git rev-parse HEAD
python3 tools/setup_opta.py
python3 tools/setup_opta.py --install
```

Confrontare il commit con quello approvato prima di compilare. Il branch può
evolvere: un clone futuro non garantisce da solo la stessa release.
Il primo comando di setup mostra il piano; `--install` prepara core, ambiente
Python e dipendenze. La prima compilazione scarica anche le librerie fissate in
`firmware/opta_encoder_lan/sketch.yaml`. Serve Internet in questa fase.
Non copiare il file `arduino-cli.yaml` di un altro computer: contiene percorsi
locali. Se assente, il setup lo crea nella nuova postazione.

## 3. Scegliere il profilo e preparare la release

| Profilo disponibile | Modalità | Riferimento |
|---|---|---|
| `lika-ir65-2500-x4` | Encoder A/B, 10000 conteggi/giro | Lika IR65 storico, 2500 PPR |
| `e38s6g5-600b-g24n-x4` | Encoder A/B, 2400 conteggi/giro | Prototipo NPN con pull-up esterni |
| `heschen-e3f-ds10p3-sheets` | Contafogli su I1 | PNP NO, filtri iniziali di 2 ms |

Non usare il profilo IR65 per un Lika IR01 da 250 PPR o per un SICK con diversa
risoluzione: servono un profilo specifico e una verifica dell'interfaccia.
Il campo storico `encoder_profile` nel registro accetta anche il contafogli.
Profili, polarità e filtri sono inclusi **in compilazione**, non configurabili
a caldo. Vedere [contafogli](contafogli.md) e [preparazione serie](preparazione-serie.md).

Per aggiornare unità esistenti, ripristinare prima la chiave originale in
`.secrets/opta-ota-private.pem`, con directory accessibile solo all'operatore e
file con permessi 0600. Per una nuova serie, il responsabile può creare una
nuova identità. Il comando seguente riusa una chiave esistente, altrimenti ne
genera una: **non eseguirlo su una copia nuova pensando che recuperi la vecchia**.

```sh
python3 tools/provision_ota_key.py
```

Scegliere un numero di versione nuovo. Gli esempi seguenti usano `0.4.2-lan`
e Lika IR65: sono valori di esempio da concordare, non una release approvata.

```sh
python3 tools/build_opta_lan.py --version 0.4.2-lan --profile lika-ir65-2500-x4
```

Non viene caricato alcun firmware. Conservare tutta la cartella
`.build/releases/0.4.2-lan/`, compresi `firmware.bin`, `manifest.json` e profili,
insieme al commit dei sorgenti. Non usare il BIN della cartella temporanea di
compilazione: potrebbe appartenere all'ultimo profilo compilato.
Una release già presente non viene sovrascritta. Se il responsabile consegna
un pacchetto approvato, ripristinarlo in quella cartella senza ricompilarlo.

## 4. Identificare e registrare una sola unità

Collegare una sola Opta via USB dati, chiudere il Monitor seriale e verificare
AFX00003 sull'etichetta. Il riconoscimento USB identifica la famiglia Opta,
non certifica da solo la variante Lite.

```sh
python3 tools/provision_opta.py discover
```

Annotare `port.address`, `port.properties.serialNumber` e il FQBN
`arduino:mbed_opta:opta`. La porta può cambiare dopo un riavvio: rilevarla di nuovo.
Negli esempi `SERIALE_USB_REALE`, `PORTA_USB_REALE` e l'IP devono essere
sostituiti. `192.168.10.50` è soltanto un esempio, non l'indirizzo del prototipo.

```sh
python3 tools/provision_opta.py new opta-001 \
  --serial SERIALE_USB_REALE --site officina \
  --profile lika-ir65-2500-x4 --version 0.4.2-lan \
  --maintenance-url http://192.168.10.50:8080 \
  --opcua-endpoint opc.tcp://192.168.10.50:4840
python3 tools/provision_opta.py validate devices/local/opta-001.json \
  --release .build/releases/0.4.2-lan
```

Risultato atteso: `release_valid`. Il JSON è un registro **sul computer**:
scrivere un IP qui non cambia la rete dell'Opta. Per un'unità già registrata
aggiornare il suo file, senza inventare un nuovo seriale o duplicare l'unità.

## 5. Prima installazione USB e predisposizione OTA

Collegare anche Ethernet a una rete con DHCP e l'alimentazione prevista.
La versione corrente avvia il servizio manutenzione dopo aver ottenuto la
rete: senza DHCP può funzionare l'acquisizione, ma non è disponibile il servizio
OTA e l'inizializzazione USB della memoria non viene completata.

Mostrare il piano e poi applicarlo, dopo aver verificato unità e pacchetto:

```sh
python3 tools/provision_opta.py install-usb devices/local/opta-001.json \
  --release .build/releases/0.4.2-lan --port PORTA_USB_REALE
python3 tools/provision_opta.py install-usb devices/local/opta-001.json \
  --release .build/releases/0.4.2-lan --port PORTA_USB_REALE --apply
```

Il piano non comunica via USB. L'applicazione controlla il seriale e carica il
BIN; il riavvio azzera i contatori. `uploaded_not_yet_verified` significa
caricamento eseguito, non collaudo completato.

Leggere la console, lasciando chiuso il Monitor seriale:

```sh
python3 tools/provision_opta.py discover
python3 tools/read_usb_console.py PORTA_USB_REALE --seconds 20
```

Annotare l'IP assegnato e interrogare lo stato con quell'indirizzo:

```sh
python3 tools/opta_lan.py 192.168.10.50 status
```

| Stato | Azione |
|---|---|
| `ota_ready=true`, `storage_result=0` | Memoria già pronta: non inizializzarla di nuovo |
| `ota_ready=false`, `storage_result=-4` | MBR assente: tentare l'inizializzazione protetta sotto |
| Altro risultato o memoria non vuota | Consultare il recupero al punto 10; non forzare la formattazione |

Solo nel caso previsto per memoria vuota:

```sh
python3 tools/init_ota_storage.py PORTA_USB_REALE
python3 tools/opta_lan.py 192.168.10.50 status
```

Attendere `OTA_INIT_RESULT=0`, poi `ota_ready=true`. Il firmware controlla i
primi 6 MiB e rifiuta l'operazione se non sono vuoti. Non cancella automaticamente
un'applicazione precedente. In alternativa, su unità sicuramente nuove si può
aggiungere `--init-ota` al comando `install-usb`, dopo aver predisposto DHCP.

Un timeout di `init_ota_storage.py` **non prova un guasto**: il comando non
riceve conferma se la rete non è pronta o se la memoria era già inizializzata.
Controllare prima HTTP e console, senza ripetere upload o cancellazioni alla cieca.

## 6. Mantenere un indirizzo fisso

### Metodo consigliato e già supportato: prenotazione DHCP

1. Collegare una sola nuova unità e leggere l'IP dalla console.
2. Nel router individuare la relativa concessione DHCP e il MAC Ethernet.
   Il servizio HTTP attuale non espone il MAC o il seriale USB: non usare
   `BootId` come identificativo hardware, perché cambia a ogni avvio.
3. Prenotare per quel MAC l'indirizzo concordato con il referente IT. Verificare
   che non sia assegnato a un'altra macchina; non copiare l'IP del prototipo.
4. Riavviare l'Opta, rileggere la console e provare `status` al nuovo indirizzo.
5. Aggiornare `maintenance_url` e `opcua_endpoint` nel registro locale e in GERP.
   Salvare MAC e prenotazione anche nell'inventario IT separato.

L'indirizzo resta fisso grazie al router, mentre il firmware continua a usare
DHCP. Dopo un'interruzione di alimentazione serve quindi ancora il server DHCP.
Una connessione diretta computer–Opta senza DHCP non equivale a questa procedura.

### Se è obbligatorio un IP statico nel dispositivo

Non esiste ancora un comando `set-ip`, una pagina web o un parametro di build.
Serve una modifica del sorgente e una release dedicata. Nel core fissato 4.6.0
è disponibile `Ethernet.begin(ip, dns, gateway, subnet)`. Il blocco DHCP in
`runServer()` di `firmware/opta_encoder_lan/opta_encoder_lan.ino` può essere
sostituito, da chi mantiene il firmware, con un blocco come questo:

```cpp
  const IPAddress ip(192, 168, 10, 50);
  const IPAddress dns(192, 168, 10, 1);
  const IPAddress gateway(192, 168, 10, 1);
  const IPAddress subnet(255, 255, 255, 0);
  while (!Ethernet.begin(ip, dns, gateway, subnet)) {
    Serial.println("Attendo Ethernet con configurazione statica.");
    Ethernet.end();
    delay(2000);
  }
```

Questa è una ricetta di modifica, **non codice già applicato o collaudato su
hardware**. Usare i valori reali della sede, evitare conflitti e assegnare una
nuova versione, archiviando modifica e binario. Ogni IP diverso produce un BIN
diverso: non replicarlo su più unità nella stessa rete. Non caricare da remoto
una configurazione di rete non verificata senza possibilità di recupero USB.
Per una serie con IP statici configurabili senza ricompilazione serve prima
sviluppare e collaudare una configurazione persistente dedicata.

## 7. Verifica via LAN e prova del sensore

Dal computer che deve leggere l'Opta:

```sh
curl --noproxy '*' --connect-timeout 5 --max-time 10 http://192.168.10.50:8080/status
.venv/bin/python tools/provision_opta.py verify devices/local/opta-001.json \
  --allow-test --samples 10
```

Attesi: versione e profilo corretti, modalità corretta, `ota_ready=true`,
`diagnostic_read_ok` e rapporto in `reports/opta-001/`. La verifica confronta
HTTP e OPC UA e controlla aggiornamento dei campioni e coerenza dei valori.
Non certifica l'identità hardware remota né la precisione della misura.

Per osservare i dati mentre si muove il sensore, scegliere **uno** dei lettori:

```sh
.venv/bin/python tools/read_encoder_opcua.py opc.tcp://192.168.10.50:4840 \
  --allow-test --diagnostics --samples 60 --interval 1
.venv/bin/python tools/read_sheet_counter_opcua.py opc.tcp://192.168.10.50:4840 \
  --allow-test --diagnostics --samples 60 --interval 1
```

L'output è JSON, un campione per riga; i totali a 64 bit sono stringhe.
Per l'encoder verificare più giri noti avanti/indietro, ritorno alla posizione
iniziale e velocità massima. Per il contafogli usare un numero noto di fogli,
presenza mantenuta, interspazio minimo, arresti e ripartenze; seguire il
[collaudo specifico](contafogli.md#collaudo-prima-della-produzione).
Ripetere con rete scollegata e riconnessa, mantenendo l'alimentazione.
Registrare risultati e anomalie: zero errori software non prova zero impulsi persi.

## 8. Aggiornare via LAN

Fermare il collaudo/produzione, annotare i contatori e verificare IP, unità,
profilo, versione corrente e `ota_ready=true`. Mantenere alimentazione stabile.
Ripristinare la chiave autorizzata prima di compilare un nuovo firmware.

```sh
python3 tools/opta_lan.py 192.168.10.50 status
python3 tools/build_opta_lan.py --version 0.4.3-lan --profile lika-ir65-2500-x4
python3 tools/opta_lan.py 192.168.10.50 upload \
  .build/releases/0.4.3-lan/firmware.bin --expect-version 0.4.3-lan
```

La firma è eseguita dallo strumento con la chiave locale. Attendere nuova
versione, nuovo `BootId` e OTA pronta dopo il riavvio; i contatori ripartono da
zero. Aggiornare `firmware_version` nel registro locale alla versione installata,
poi ripetere `verify` del punto 7 e il controllo funzionale. Conservare anche
il pacchetto precedente per il recupero, che non avviene automaticamente.

Non rimuovere il servizio OTA caricando uno sketch diverso. Per replicare una
release usare lo stesso pacchetto approvato e procedere un dispositivo alla
volta, dopo aver collaudato l'esemplare pilota.

## 9. GERP e accesso da un'altra rete

Il **server che esegue il client GERP**, non solo il browser dell'utente, deve
raggiungere TCP 4840 dell'Opta. Per manutenzione serve anche TCP 8080.
Non è obbligatoria la stessa sottorete: sono sufficienti routing e firewall
corretti, tramite LAN o VPN. Il firmware non contiene un client VPN.
OPC UA è attualmente anonimo senza cifratura di sessione; HTTP trasferisce in
chiaro, mentre gli aggiornamenti firmware sono firmati. Usare una rete
controllata/VPN, senza pubblicare queste porte su Internet.

Esempio di tunnel, da eseguire sul computer che lancia il lettore, con un host
SSH che raggiunge realmente la LAN dell'Opta. Sostituire tutti gli indirizzi
con quelli della propria installazione e lasciare questo terminale aperto:

```sh
ssh -N -T -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
  -L 127.0.0.1:14840:192.168.10.50:4840 \
  -L 127.0.0.1:18080:192.168.10.50:8080 UTENTE@HOST_UFFICIO
```

In un secondo terminale, dalla cartella del progetto:

```sh
.venv/bin/python tools/provision_opta.py verify devices/local/opta-001.json \
  --maintenance-url http://127.0.0.1:18080 \
  --opcua-endpoint opc.tcp://127.0.0.1:14840 --allow-test --samples 10
```

Un tunnel sul portatile non rende l'Opta raggiungibile da un diverso server GERP.
Per un servizio continuativo il referente IT deve predisporre sul server
instradamento VPN o un tunnel persistente con riavvio automatico e monitoraggio;
questa configurazione non viene installata dagli script del repository.
L'installazione firmware non configura automaticamente il driver GERP.
Iniziare con letture in dashboard: il driver generico non applica da solo tutti
i controlli del lettore dedicato e il totale fogli non deve essere collegato ai metri.

## 10. Reset e recupero di una scheda usata

| Operazione | Effetto | Quando usarla |
|---|---|---|
| RESET singolo / spegnimento | Riavvio, contatori RAM azzerati; firmware e QSPI restano | Riavvio controllato |
| RESET due volte rapidamente | Modalità bootloader per upload USB; non cancella tutto | Sketch bloccato o upload normale impossibile |
| Nuovo upload USB | Sostituisce l'applicazione; non equivale a cancellare QSPI | Prima installazione o recupero OTA |
| Ripartizionamento QSPI | Può cancellare dati, certificati e partizioni precedenti | Solo recupero pianificato di memoria incompatibile |

Per il recupero USB: scollegare gli attuatori della precedente applicazione,
collegare una sola Opta, chiudere il Monitor seriale, provare il doppio RESET e
rieseguire `discover`. Usare porta e seriale rilevati, poi il pacchetto approvato
con `install-usb`. Se l'installatore non riconosce il seriale in bootloader,
fermarsi: non falsificare il registro per saltare la verifica d'identità.
Seguire le [indicazioni Arduino sul reset](https://support.arduino.cc/hc/en-us/articles/5779192727068-Reset-your-board)
e, se necessario, il recupero USB con Arduino IDE dell'applicazione approvata.

Per una scheda proveniente da PLC IDE o con QSPI incompatibile, il repository
**non offre un comando universale di ripristino di fabbrica**. Salvare prima
applicazione, chiavi/configurazioni recuperabili e ottenere autorizzazione alla
cancellazione. Arduino documenta lo sketch `QSPIFormat` nella
[procedura ufficiale di ripartizionamento](https://docs.arduino.cc/software/plc-ide/tutorials/memory-partitioning/).
La formattazione è distruttiva: seguirne consapevolmente le richieste, poi
ricaricare il firmware di questo progetto via USB e ricontrollare lo stato OTA.
Se la partizione è già riconosciuta, non ripetere `init_ota_storage.py`.
Non è stato collaudato il recupero di ogni possibile layout precedente:
un risultato diverso da `ota_ready=true` va risolto prima della consegna.

## 11. Risoluzione dei problemi

| Sintomo | Controllo e passo successivo |
|---|---|
| Nessuna USB | Cavo dati, connessione diretta, alimentazione, `discover`, doppio RESET se necessario |
| Porta occupata | Chiudere Monitor seriale e altri lettori; una sola sessione per porta |
| Linux: accesso negato alla seriale | Verificare gruppo e regole della distribuzione; riaprire la sessione dopo le modifiche |
| IP `0.0.0.0` / attesa DHCP | Ethernet, porta switch, VLAN, DHCP; il servizio LAN non è ancora avviato |
| `No route to host` / timeout | IP attuale, subnet, VPN, firewall e, su macOS, permesso Rete locale dell'app che esegue il comando; confrontare con curl |
| HTTP funziona, OPC UA no | Raggiungibilità TCP 4840, endpoint e profilo del lettore; HTTP 8080 da solo non prova OPC UA |
| `cryptography is not installed` | Avviso del client OPC UA senza crypto; non spiega da solo un errore di rete. Non abilita cifratura installando solo il pacchetto |
| `ota_ready=false` | Leggere `storage_result`; applicare punto 5 o recupero controllato, non forzare l'upload |
| OTA rifiuta la firma | Verificare chiave autorizzata. Generarne un'altra non sblocca la scheda; possibile recupero USB con nuova identità pianificata |
| Release già esistente | Usare il pacchetto archiviato oppure una nuova versione, non sovrascriverlo |
| Profilo/versione non coerenti | Confrontare registro, manifesto e firmware; non ignorare la verifica |
| A/B fissi o fogli non contati | Alimentazione sensore, massa comune, pinout, tipo di uscita, presenza/interspazio e filtri; non dedurre un guasto dal solo log |

## 12. Verbale di consegna e backup

Compilare un verbale privato con: tecnico/data, ID unità, seriale USB, MAC,
sede/macchina, IP/subnet/gateway/DNS e prenotazione DHCP, modalità/profilo,
versione e SHA-256 del BIN, commit sorgenti, identificativo della chiave usata
(non il contenuto), rapporto di verifica e risultati della prova fisica.

- [ ] Unità e cablaggio identificati; profilo coerente con il sensore.
- [ ] IP riservato e raggiungibile anche dopo riavvio; nessun conflitto.
- [ ] USB, HTTP e OPC UA verificati; `ota_ready=true`.
- [ ] Aggiornamento LAN di prova riuscito sull'esemplare pilota.
- [ ] Accesso verificato dal vero server GERP, se compreso nella consegna.
- [ ] Comportamento al riavvio e limiti diagnostici comunicati al responsabile.
- [ ] Backup protetto di chiave, pacchetti, inventario e `reports/` disponibile.
- [ ] Recupero USB possibile e documentato per la sede.

Un verbale completo attesta preparazione e prove eseguite; non trasforma il
firmware diagnostico in una soluzione già qualificata per la produzione.
