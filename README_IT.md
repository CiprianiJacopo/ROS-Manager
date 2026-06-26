[English](README.md) | [Italiano](README_IT.md)

# ROSM — Router OS Manager

![License](https://img.shields.io/github/license/CiprianiJacopo/ROS-Manager)
![Release](https://img.shields.io/github/v/release/CiprianiJacopo/ROS-Manager)

Server Python a file unico per la gestione centralizzata di flotte di router MikroTik — senza dover aprire Winbox su ogni singolo dispositivo.

## Cosa fa

- **Dashboard** — stato, modello, uptime e porte aperte di ogni router a colpo d'occhio
- **Network Discovery** — scansiona una subnet e importa i router automaticamente, con o senza credenziali SSH
- **Backup** — backup `.rsc` automatici e programmati per ogni router
- **Monitoraggio** — ping in tempo reale, scansione porte, storico online/offline
- **Aggiornamenti RouterOS** — controlla e distribuisce aggiornamenti RouterOS ai router via SSH
- **Multi-utente** — ruoli admin/viewer, 2FA opzionale (TOTP)
- **Storage cifrato** — credenziali e backup cifrati su disco
- **Auto-aggiornamento** — controlla GitHub per nuove versioni e si aggiorna con un click

## Installazione

Scarica l'ultimo installer dalle [Releases](https://github.com/CiprianiJacopo/ROS-Manager/releases):
- **macOS** — `ROSM-X.Y.Z.pkg`
- **Windows** — `ROSM-X.Y.Z-Setup.exe`

Avvialo, segui il wizard di configurazione, e ROSM si apre nel browser su `http://localhost:8080`.

## Canali

Questo repository ha due branch:
- `main` — **stable**, quello descritto in questo README.
- `Beta` — canale di test, più avanti rispetto a stable, può contenere bug. Vedi il proprio README su quel branch.

Puoi cambiare canale in qualsiasi momento dalle Impostazioni di ROSM.

## Documentazione

Per architettura, struttura del codice e il perché di alcune scelte non ovvie, vedi [CODE_OVERVIEW_IT.md](CODE_OVERVIEW_IT.md) (o [CODE_OVERVIEW_EN.md](CODE_OVERVIEW_EN.md) in inglese).

## Licenza

GPLv3 — vedi [LICENSE](LICENSE).

## Supporto

Se ROSM ti è utile, puoi [offrire una birra all'autore su Ko-fi](https://ko-fi.com/rosm).

Domande o feedback: Rosman.mail@icloud.com
