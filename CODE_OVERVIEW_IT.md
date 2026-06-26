# ROSM — Panoramica del codice

Server Python a file unico (`dashboard.py`) per la gestione centralizzata di flotte di router MikroTik: dashboard web, backup, monitoraggio, provisioning, aggiornamenti RouterOS sui router. Distribuito come pacchetto installabile per macOS (`.pkg`) e Windows (`.exe`).

Versione italiana di riferimento — `CODE_OVERVIEW_EN.md` è la traduzione inglese di questo file.

## Licenza

GPLv3 — vedi `LICENSE`. Fork e versioni modificate distribuite devono restare open source con licenza GPL. Le dipendenze terze (paramiko, cryptography, pyotp, segno, bcrypt, pynacl, psutil — vedi `requirements.txt`) hanno licenze proprie (MIT/BSD/Apache/LGPL): mantenerne gli avvisi di copyright quando si distribuisce il pacchetto.

## Struttura del repository

- **`dashboard.py`** — l'intera applicazione: server, API, frontend HTML/CSS/JS, logica di business. File unico, nessun framework.
- **`menubar.py`** / **`tray_win.py`** — l'icona nella menu bar (macOS) / system tray (Windows), avviata insieme a `dashboard.py`.
- **`requirements.txt`** — dipendenze Python.
- **`build_mac_pkg.sh`** / **`build_win_pkg.sh`** / **`build_all.sh`** — generano i pacchetti installer. `VERSION=` vicino all'inizio dei primi due; `build_all.sh` li esegue entrambi in sequenza.
- **`version.json`** — `{"version": ..., "date": ..., "changelog": [...]}`, letto dal controllo aggiornamenti in-app.
- **`ztp.py`** — file sandbox per prototipare nuove feature prima di integrarle in `dashboard.py`. Non collegato all'app in esecuzione: non eliminarlo anche se sembra inutilizzato.
- **`LICENSE`** — testo GPLv3.

## Architettura

Tutto passa per `http.server` della stdlib Python (`ThreadingHTTPServer`) — nessun framework web, nessuno step di build, nessun bundler. Il file che leggi è il file che gira.

## Mappa del codice

Cerca `§ NOME` in `dashboard.py` per saltare a una sezione (c'è un blocco indice in cima al file). In ordine, dall'inizio alla fine: costanti versione/changelog → i18n → helper di cifratura → store dati (dispositivi/sedi/utenti) → discovery di rete e fingerprinting → autenticazione/sessioni → helper SSH → backup manager → CSS → template JS frontend → handler delle richieste HTTP (la maggior parte delle route e dei render delle pagine) → avvio del server.

## I dati non vivono mai nel sorgente

Tutti i dati reali (router, utenti, sedi, credenziali, impostazioni, chiave di cifratura, recovery code) vivono in file JSON separati creati al primo avvio, nella stessa cartella di `dashboard.py` (`devices.json`, `users.json`, `config.json`, `.rosm_key`, ecc.) — mai dentro il file sorgente stesso. Un clone nuovo o un'installazione nuova non contengono mai i dati di nessuno.

## Lavorare sul codice

- Modificare sempre `dashboard.py` (o gli script di build) direttamente — mai la copia installata live (tipicamente `/usr/local/rosm/dashboard.py` su macOS). Reinstallare dopo ogni modifica per testare.
- Niente emoji, né nel codice, né nei commenti, né nei messaggi di commit.

## Versioning

`APP_VERSION` in `dashboard.py`, `VERSION=` in `build_mac_pkg.sh`/`build_win_pkg.sh`, e il campo `"version"` di `version.json` devono sempre coincidere — il meccanismo di auto-update (`/api/check-update`) confronta `APP_VERSION` con il `version.json` pubblicato su questo repository. Vanno incrementati insieme.

## Decisioni tecniche e perché

Spiegazioni del "perché" dietro scelte non ovvie leggendo solo il codice — utili per non disfarle per sbaglio.

### Niente `subprocess` per ping/reachability — crash macOS

`dashboard.py` è multi-thread (HTTP server + thread di monitoraggio). Su macOS, quando un processo multi-thread chiama `fork()` (incluso `subprocess.run`/`Popen`/`check_output`), gli atfork handler di Network.framework di Apple possono andare in SIGSEGV nel processo figlio (crash report con `nw_settings_child_has_forked()` / `_os_log_preferences_refresh`). Effetto pratico riscontrato: ping con `subprocess.run(["ping", ...])` faceva apparire router ONLINE come OFFLINE (il processo figlio crashava prima di rispondere) e mostrava il crash reporter di macOS all'utente.

Per questo:
- `_tcp_reachable()` (connessione TCP su porte comuni: 22, 8291, 8728, 80, 443, 23) ha sostituito `subprocess.run(ping)` per il reachability check in `fingerprint_host()` e `_ping_one()`. Nessun fork, nessun crash.
- `_get_mac_from_arp()` salta del tutto la chiamata `subprocess.check_output(["arp", ...])` su macOS (`sys.platform == "darwin"`) — stesso crash (il MAC via ARP è solo cosmetico per il vendor lookup OUI). Resta attiva solo su Windows, dove `subprocess` non fa `fork()` e quindi non c'è il problema. Sui router RouterOS con credenziali SSH configurate il MAC arriva comunque via SSH (`_ssh_connect_creds`), percorso diverso e non a rischio.
- I 3 punti che riavviano il processo (`/settings/access-restart`, `/api/restart`, `/api/do-update`) impostano `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` nell'ambiente passato a `subprocess.Popen(...)`, perché lì il fork è inevitabile (serve davvero lanciare un nuovo processo Python). **Nota:** questa variabile agisce sull'ambiente del processo FIGLIO dopo l'exec — non è certo che prevenga il crash, che avviene dentro `fork()` stesso, prima dell'exec. È rimasta come mitigazione precauzionale su quei 3 punti (dove il fork è obbligatorio e non eliminabile), ma non va considerata una soluzione provata: il pattern collaudato resta "elimina il fork" (vedi `_tcp_reachable`/`_get_mac_from_arp`), non "sopprimi il crash con una env var".
- Se in futuro serve un'altra chiamata `subprocess.*` raggiunta a runtime (non al cold start, quando il processo è ancora single-thread), valutare prima un'alternativa senza fork — non fidarsi di `OBJC_DISABLE_INITIALIZE_FORK_SAFETY` come fix.

### i18n: due meccanismi diversi per Python e JavaScript

- Stringhe in f-string Python: usare `T("testo italiano")` — cerca la traduzione in `_T_EN` (dict vicino a `LANGUAGE`) se `LANGUAGE == "en"`, altrimenti ritorna l'italiano as-is. Se la entry manca in `_T_EN`, l'inglese mostra comunque l'italiano (capitato più volte sui `title=` dei tooltip — controllare sempre che la stringa sia nel dict).
- Stringhe dentro `MAIN_JS_TEMPLATE` (il blocco JS, raw string senza f-string): `T()` non è chiamabile lì, il JS gira nel browser. Pattern usato: variabili JS pre-tradotte iniettate a render time tramite il placeholder `{js_i18n}` (sostituito dove si costruisce `main_js`), nominate `_TJSx` (es. `_TJSC` = "Chiudi"/"Close"). Per aggiungerne una: aggiungere l'entry nella stringa `_js_i18n` dove viene costruita, poi usare `'+_TJSx+'` nel punto giusto del template.

### Bind multi-interfaccia (Frontend Access — wizard e Impostazioni)

Si può scegliere su quali interfacce di rete pubblicare ROSM, anche più di una insieme (non solo "solo localhost" / "tutta la rete").
- Config: `bind_addresses` (lista, es. `["127.0.0.1", "192.168.1.8"]`) ha sostituito `bind_address` (stringa singola). `_get_bind_addresses()` legge la lista nuova con fallback alla stringa legacy, per compatibilità con installazioni esistenti che aggiornano in-place.
- `_list_network_interfaces()` usa `psutil` (dipendenza opzionale, soft-import come `MFA_AVAILABLE` — se non installato, la UI degrada alle sole 2 opzioni originali senza crash). Necessario perché non esiste un modo stdlib-only affidabile e cross-platform (macOS+Windows) per enumerare le IP di tutte le interfacce attive.
- Le checkbox per le interfacce specifiche compaiono in UI solo se ci sono **2 o più** interfacce non-loopback attive — altrimenti non avrebbe senso mostrarle.
- "Tutte le interfacce" (`0.0.0.0`) prevale su qualsiasi altra selezione (`_normalize_bind_addresses()`), perché la include già.
- Al via, viene creato un `ThreadingHTTPServer` per ogni indirizzo selezionato — un socket non può fare bind su più indirizzi specifici insieme — tutti raccolti in `ALL_SERVERS`. Per questo i 3 punti di riavvio chiudono TUTTI i socket in `ALL_SERVERS`, non solo `self.server.socket` (che è solo quello che ha gestito la richiesta corrente di riavvio): altrimenti il nuovo processo non riesce a fare bind sugli altri indirizzi (porta ancora occupata dal processo vecchio).
- Se il bind su un indirizzo salvato fallisce all'avvio (es. interfaccia scollegata), viene loggato e saltato; se TUTTI i bind falliscono, fallback automatico su `0.0.0.0` — non si resta mai irraggiungibili.

### Network Discovery — credenziali SSH opzionali

`fingerprint_host()` funziona anche senza `ssh_user`/`ssh_pass`: rileva comunque IP, porte aperte, tipo dispositivo (via banner SSH/HTTP, OUI del MAC). Le credenziali servono solo per il passo successivo (leggere identity/model RouterOS via SSH) — né il backend (`/api/scan`) né il frontend impongono più credenziali obbligatorie per avviare una scansione.

### App bundle duplicati in /Applications — cartelle "ROSM.localized"

Se un Mac ha installato ROSM in passato con un `CFBundleIdentifier` diverso da quello attuale (retaggio di un vecchio schema di naming — ora è `com.rosm.launcher`), macOS Installer non sovrascrive il bundle esistente allo stesso path: lo dirotta in una cartella ombra `NomeApp.localized/NomeApp.app`. Finder nasconde il suffisso `.localized` (come fa con `.app`), quindi compare come una cartella generica con lo stesso nome dell'app — sintomo visibile: doppioni "ROSM" e "ROSM Uninstaller" oltre alle app vere e proprie.

Fix: `build_mac_pkg.sh` genera anche uno script **preinstall** (oltre al postinstall) che rimuove sempre, prima di installare, qualsiasi `/Applications/ROSM.app`, `/Applications/ROSM Uninstaller.app` e relative cartelle `.localized` pre-esistenti — ogni installazione parte pulita, indipendentemente dall'identificatore del bundle precedente. `pkgbuild` lo individua automaticamente perché sta nella stessa `$SCRIPTS_DIR` già passata con `--scripts`.

Non riguarda mai i dati utente: questi bundle sono solo launcher (script + Info.plist + icona), rigenerati identici ad ogni installazione. I dati reali (`/usr/local/rosm/*.json`, chiave di cifratura, ecc.) non fanno parte del payload del pacchetto e la postinstall non li tocca mai.

Solo macOS: Windows non ha un meccanismo equivalente di identità dei bundle — le shortcut `.lnk` si sovrascrivono semplicemente allo stesso path.

## Indice — dove trovare le cose in `dashboard.py`

- **Versione e changelog**: `APP_VERSION`, `APP_STAGE`, `CHANGELOG` — vicino all'inizio del file (circa righe 60-115).
- **Meccanismo update — costanti**: `UPDATE_REPO`, `_UPDATE_BRANCHES` (mapping canale→branch, `Beta` con la maiuscola), `_update_branch()` — subito dopo `APP_VERSION`.
- **Endpoint update**: `/api/check-update` (GET, legge `version.json`), `/api/do-update` (POST, scarica e installa `dashboard.py`), `/settings/update_channel` (POST, salva solo la preferenza canale, non installa), `/settings/update_enabled` (POST, toggle abilita/disabilita).
- **UI impostazioni update**: commento `# Update section (admin only)` — label IT/EN, toggle di stato, selettore canale, area "Controlla aggiornamenti" con JS (`updCheck`, `updSkip`, `updInstall`, `_buildCL` per il rendering del changelog).
- **Rete/reachability**: `_get_local_ip()`, `_list_network_interfaces()`, `_get_bind_addresses()`, `_normalize_bind_addresses()` (circa righe 130-200), `_tcp_reachable()` (circa riga 1200, vicino a `fingerprint_host()`). `ALL_SERVERS` — lista dei `ThreadingHTTPServer` attivi, creata in fondo al file all'avvio del processo.
- **i18n**: `_T_EN` (dict IT→EN, circa riga 200) e `T()` (circa riga 760) vicino a `LANGUAGE`. Per le stringhe dentro `MAIN_JS_TEMPLATE` vedi il pattern `_TJSx`/`{js_i18n}` sopra in "Decisioni tecniche".
