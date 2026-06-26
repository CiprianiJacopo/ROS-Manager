# ╔══════════════════════════════════════════════════════════════════╗
# ║  dashboard.py — ROSM Router OS Manager                          ║
# ║  Server web Python monolitico — tutto in un unico file.         ║
# ╠══════════════════════════════════════════════════════════════════╣
# ║  INDICE  (cerca "§ NOME" per saltare alla sezione)              ║
# ║  ──────────────────────────────────────────────────────────────  ║
# ║  § Imports & paths             ~   62   Dipendenze, costanti     ║
# ║  § Version & changelog         ~   67   APP_VERSION, CHANGELOG   ║
# ║  § i18n                        ~  834   Dizionario traduzioni     ║
# ║  § Encryption                  ~ 1442   Fernet / AES-128         ║
# ║  § Core helpers                ~ 1554   Funzioni di base         ║
# ║  § Devices store               ~ 1575   devices.json             ║
# ║  § Discovery & fingerprinting  ~ 1688   Scansione rete           ║
# ║  § Auth & sessions             ~ 2101   Login, token, sessioni   ║
# ║  § Role helpers                ~ 2178   Ruoli e permessi         ║
# ║  § MFA (TOTP)                  ~ 2223   Autenticazione 2FA       ║
# ║  § Companies & sites           ~ 2283   Aziende, sedi            ║
# ║  § Runtime state & locks       ~ 2334   Stato globale, lock      ║
# ║  § Port scanning               ~ 2425   Porte TCP aperte         ║
# ║  § Routers list builder        ~ 2470   DEVICES + STATE → list   ║
# ║  § SSH helpers                 ~ 2578   Connessione, info SSH     ║
# ║  § Custom SSH columns          ~ 2683   Colonne custom via SSH   ║
# ║  § Backup manager              ~ 2704   Backup automatici        ║
# ║  § Credential sets             ~ 2711   Set credenziali SSH      ║
# ║  § SSH script runner           ~ 2953   Esecuzione script SSH    ║
# ║  § Ping & port scan engine     ~ 3010   Ping parallelo           ║
# ║  § Upload helpers              ~ 3115   Caricamento file         ║
# ║  § CSS & design tokens         ~ 3200   COMMON_CSS               ║
# ║  § Frontend JS                 ~ 3645   MAIN_JS (no f-string)    ║
# ║  § Tour overlay                ~ 4555   Tour guidato in-app      ║
# ║  § HTTP server                 ~ 5004   Handler + render_*       ║
# ║  § Startup                     ~14433   Avvio server             ║
# ╚══════════════════════════════════════════════════════════════════╝
#
#  Per trovare una sezione:  grep -n "§ NOME" dashboard.py
#  Esempio:                  grep -n "§ Backup" dashboard.py
#
# Copyright (C) 2026 Jacopo Cipriani
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess, threading, time, json, os, re, uuid, hashlib, secrets, socket, ipaddress, sys, select as _select
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from collections import deque
from datetime import datetime, timedelta as _td
import urllib.parse
import paramiko
import cgi
import io as _io
from http.server import ThreadingHTTPServer
try:
    import pyotp, segno
    MFA_AVAILABLE = True
except ImportError:
    MFA_AVAILABLE = False
try:
    import psutil as _psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

# ─────────────────────────────────────────────────────────────────
# § Imports & paths
# ─────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────────────────────────
# § Version & changelog
# ─────────────────────────────────────────────────────────────────
APP_VERSION = "2.1.2"
APP_STAGE   = "Beta"      # shown after version number in UI
# GitHub repository used for auto-update checks (public repo — no token needed)
UPDATE_REPO      = "CiprianiJacopo/ROS-Manager"
_UPDATE_BRANCHES = {"stable": "main", "beta": "Beta"}  # channel → branch

def _update_branch() -> str:
    """Return the GitHub branch for the currently configured update channel."""
    ch = _app_cfg.get("update_channel", "stable")
    return _UPDATE_BRANCHES.get(ch, "main")
CHANGELOG = [
    ("2.1.2", "2026-06-25", [
        "Prima versione distribuita ufficialmente: licenza GPLv3, repository pubblico su GitHub, pacchetti scaricabili da chiunque tramite GitHub Releases.",
        "[Test] Testato su macOS 26.5.1 e Windows 11 Pro 25H2 (build 26200)",
    ]),
]

FAVICON_SVG = (
    'data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20viewBox%3D%220%200%2032%2032%22%3E'
    '%3Crect%20width%3D%2232%22%20height%3D%2232%22%20rx%3D%227%22%20fill%3D%22%231b3a6b%22/%3E'
    '%3Ccircle%20cx%3D%229%22%20cy%3D%2210%22%20r%3D%224%22%20fill%3D%22%23c0392b%22/%3E'
    '%3Ccircle%20cx%3D%2223%22%20cy%3D%2210%22%20r%3D%222.8%22%20fill%3D%22rgba(255%2C255%2C255%2C0.6)%22/%3E'
    '%3Ccircle%20cx%3D%2216%22%20cy%3D%2223%22%20r%3D%223.5%22%20fill%3D%22rgba(255%2C255%2C255%2C0.9)%22/%3E'
    '%3Cline%20x1%3D%229%22%20y1%3D%2210%22%20x2%3D%2216%22%20y2%3D%2223%22%20stroke%3D%22rgba(255%2C255%2C255%2C0.55)%22%20stroke-width%3D%221.6%22/%3E'
    '%3Cline%20x1%3D%2223%22%20y1%3D%2210%22%20x2%3D%2216%22%20y2%3D%2223%22%20stroke%3D%22rgba(255%2C255%2C255%2C0.55)%22%20stroke-width%3D%221.6%22/%3E'
    '%3Cline%20x1%3D%229%22%20y1%3D%2210%22%20x2%3D%2223%22%20y2%3D%2210%22%20stroke%3D%22rgba(255%2C255%2C255%2C0.3)%22%20stroke-width%3D%221.2%22/%3E'
    '%3C/svg%3E'
)
FAVICON_TAG = f'<link rel="icon" type="image/svg+xml" href="{FAVICON_SVG}">'

STATE_FILE          = os.path.join(BASE_DIR, "state.json")
SITES_FILE          = os.path.join(BASE_DIR, "sites.json")
CUSTOM_COLS_FILE    = os.path.join(BASE_DIR, "custom_columns.json")
BACKUP_DIR          = os.path.join(BASE_DIR, "backups")
BACKUP_CONFIG_FILE  = os.path.join(BASE_DIR, "backup_config.json")
CRED_SETS_FILE      = os.path.join(BASE_DIR, "cred_sets.json")
OUI_CACHE_FILE      = os.path.join(BASE_DIR, "oui_cache.json")
os.makedirs(BACKUP_DIR, exist_ok=True)
UPLOADS_LOG_FILE    = os.path.join(BASE_DIR, "uploads_log.json")
RUNS_LOG_FILE    = os.path.join(BASE_DIR, "runs_log.json")
ROUTERS_FILE     = os.path.join(BASE_DIR, "routers.txt")

# ─────────────────────────────────────────────────────────────────
# § i18n
# ─────────────────────────────────────────────────────────────────
CONFIG_FILE        = os.path.join(BASE_DIR, "config.json")
FIRST_RUN_FILE     = os.path.join(BASE_DIR, ".first_run_done")
RECOVERY_KEY_FILE  = os.path.join(BASE_DIR, ".rosm_recovery")

def _load_app_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def _save_app_config(cfg):
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_FILE)

_app_cfg  = _load_app_config()
LANGUAGE  = _app_cfg.get("language", "en")   # default: English
FIRST_RUN_DONE = os.path.exists(FIRST_RUN_FILE)

def _get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"

def _list_network_interfaces():
    """Active non-loopback IPv4 interfaces as [{'name':..,'ip':..}]. Empty if psutil unavailable."""
    out = []
    if not _PSUTIL_AVAILABLE:
        return out
    try:
        stats = _psutil.net_if_stats()
        for iface, addrs in _psutil.net_if_addrs().items():
            if not stats.get(iface) or not stats[iface].isup:
                continue
            for a in addrs:
                if a.family == socket.AF_INET and not a.address.startswith("127."):
                    out.append({"name": iface, "ip": a.address})
                    break
    except Exception:
        pass
    return out

def _get_bind_addresses(cfg=None):
    cfg = cfg if cfg is not None else _app_cfg
    addrs = cfg.get("bind_addresses")
    if isinstance(addrs, list) and addrs:
        return addrs
    legacy = cfg.get("bind_address")
    return [legacy] if legacy else ["0.0.0.0"]

def _normalize_bind_addresses(raw):
    valid_ips = {i["ip"] for i in _list_network_interfaces()}
    seen, out = set(), []
    for a in raw:
        a = (a or "").strip()
        if a and a not in seen and (a in ("127.0.0.1", "0.0.0.0") or a in valid_ips):
            seen.add(a); out.append(a)
    if not out:
        return ["0.0.0.0"]
    return ["0.0.0.0"] if "0.0.0.0" in out else out

def _get_or_create_recovery_code():
    if os.path.exists(RECOVERY_KEY_FILE):
        try:
            code = open(RECOVERY_KEY_FILE).read().strip()
            if len(code) >= 8:
                return code
        except Exception:
            pass
    code = secrets.token_urlsafe(18)[:20]
    with open(RECOVERY_KEY_FILE, "w") as f:
        f.write(code)
    try:
        os.chmod(RECOVERY_KEY_FILE, 0o600)
    except Exception:
        pass
    return code

RECOVERY_CODE = _get_or_create_recovery_code()

# Translation dict: English values, Italian keys
_T_EN: dict = {
    # ── Navigation ──────────────────────────────────────────
    "Home": "Home", "Dashboard": "Dashboard",
    "Site Manager": "Site Manager", "Network Discovery": "Network Discovery",
    "Statistiche": "Statistics", "Carica Script": "Upload Script",
    "Guida": "Guide",
    "Funzioni, ruoli e istruzioni rapide": "Features, roles and quick instructions",
    "Credential Manager": "Credential Manager", "Backup Manager": "Backup Manager",
    "Utenti": "Users", "Riavvia": "Restart", "Logout": "Logout",
    "Impostazioni": "Settings", "Log": "Log",
    # ── Log page ─────────────────────────────────────────────
    "Tutti": "All", "Sicurezza": "Security", "Sistema": "System", "Errori": "Errors",
    "Orario": "Time", "Categoria": "Category", "Livello": "Level", "Messaggio": "Message",
    "Log attività": "Activity Log",
    "eventi registrati": "events logged",
    # ── Users page ───────────────────────────────────────────
    "Permessi per ruolo": "Permissions by role",
    "Sezione": "Section",
    "Credenziali": "Credentials",
    "sito/i": "site(s)",
    "Rivela": "Reveal",
    "Rivela credenziali": "Reveal credentials",
    "Sblocca": "Unlock",
    "Inserisci il recovery code": "Enter the recovery code",
    "Chiudi questa finestra appena hai copiato le credenziali.":
        "Close this window as soon as you have copied the credentials.",
    # ── Log page extras ──────────────────────────────────────
    # NOTE: short/common substrings like "di", "Data" are intentionally excluded
    # from _T_EN because _apply_translations does plain html.replace() and would
    # corrupt <div>, display:, data-* attributes, etc.
    # Those strings are handled via T() calls directly in render_report_page.
    "Dalle": "From", "Alle": "To",
    "Per pagina": "Per page", "Cerca": "Search", "Azzera filtri": "Reset filters",
    "Mostrati": "Showing",
    "filtrati": "filtered",
    "eventi in memoria": "events in memory",
    "Max archiviati": "Max archived",
    "Nessun evento trovato con i filtri selezionati.":
        "No events found with the selected filters.",
    "eventi in memoria": "events in memory",
    "aggiornato alle": "updated at",
    "auto-refresh ogni 15s": "auto-refresh every 15s",
    "↺ Aggiorna ora": "↺ Refresh now",
    "Svuota log": "Clear log",
    "Svuotare il log degli eventi?": "Clear the event log?",
    "Nessun evento registrato. Avvia un ping o un'operazione SSH per popolare il log.":
        "No events recorded. Run a ping or SSH operation to populate the log.",
    # ── app_log messages ─────────────────────────────────────
    "Ping avviato": "Ping started",
    "Ping completato": "Ping completed",
    "ONLINE su": "ONLINE out of",
    "OFFLINE su": "OFFLINE out of",
    "Connessione SSH avviata": "SSH connection started",
    "Dati aggiornati": "Data updated",
    "modello:": "model:",
    "uptime:": "uptime:",
    "Errore SSH:": "SSH error:",
    "Backup avviato": "Backup started",
    "Backup completato": "Backup completed",
    "router target": "target routers",
    "OK su": "OK out of",
    "errori su": "errors out of",
    "Backup salvato:": "Backup saved:",
    "Errore backup:": "Backup error:",
    "Output vuoto o troppo corto": "Empty or too short output",
    "MAC auto-discovered:": "MAC auto-discovered:",
    "MAC mismatch — atteso": "MAC mismatch — expected",
    "rilevato": "detected",
    "ROSM avviato su porta 8080": "ROSM started on port 8080",
    "istanza precedente terminata": "previous instance terminated",
    "riavvio...": "restarting...",
    # ── Common actions ───────────────────────────────────────
    "Salva": "Save", "Annulla": "Cancel", "Elimina": "Delete",
    "Modifica": "Edit", "Chiudi": "Close", "Aggiorna": "Refresh",
    "Aggiungi": "Add", "Crea": "Create", "Conferma": "Confirm",
    "Errore": "Error", "Successo": "Success", "Attenzione": "Warning",
    "Caricamento…": "Loading…", "Pulisci": "Clear",
    "Seleziona tutti": "Select all", "Deseleziona": "Deselect",
    "↺ Aggiorna": "↺ Refresh", "↺ Riavvia": "↺ Restart",
    "Scarica": "Download", "v Scarica": "v Download",
    # ── Login ────────────────────────────────────────────────
    "Accesso": "Login", "ROSM — Accesso": "ROSM — Login",
    "Username": "Username", "Password": "Password",
    "Accedi →": "Sign in →", "Sessione 24h": "Session 24h",
    "Credenziali non valide. Riprova.": "Invalid credentials. Try again.",
    "Accesso negato: richiesto ruolo Admin": "Access denied: Admin role required",
    "Password dimenticata?": "Forgot password?",
    "Reimposta Password": "Reset Password",
    "Codice di recupero": "Recovery code",
    "Nuova password": "New password",
    "Conferma nuova password": "Confirm new password",
    "Codice non valido.": "Invalid recovery code.",
    "Le password non coincidono.": "Passwords do not match.",
    "Password aggiornata con successo.": "Password updated successfully.",
    "Inserisci il codice di recupero": "Enter your recovery code",
    "Il recovery code si trova in Impostazioni, sezione Recovery code (solo da admin). Se perso, l'accesso non e recuperabile.":
        "The recovery code is in Settings, Recovery code section (admin only). If lost, access cannot be recovered.",
    # ── Home page ────────────────────────────────────────────
    "by Jacopo Cipriani": "by Jacopo Cipriani",
    "Changelog": "Changelog",
    # ── Dashboard (main page) ────────────────────────────────
    "Stato": "Status", "Nome": "Name", "IP": "IP", "Modello": "Model",
    "Versione": "Version", "Uptime": "Uptime", "Tag": "Tags",
    "Sito": "Site", "Porte Aperte": "Open Ports",
    "Ultimo Online": "Last Online", "SSH": "SSH", "Azioni": "Actions",
    "ONLINE": "ONLINE", "OFFLINE": "OFFLINE",
    "Credenziali SSH mancanti — clicca per configurare": "SSH credentials missing — click to configure",
    "Modifica credenziali SSH": "Edit SSH credentials",
    "Modifica tag e gruppo": "Edit tags and group",
    "Rimuovi dalla lista": "Remove from list",
    "Cerca…": "Search…", "IP…": "IP…", "Nome…": "Name…",
    "Modello…": "Model…", "Tag/Gruppo…": "Tag/Group…", "Sito…": "Site…",
    "Pulisci filtri": "Clear filters",
    "Esci": "Log out",
    "Ping tutti i router": "Ping all routers",
    "SSH su tutti: nome, modello, versione": "SSH all: name, model, version",
    "Esporta tabella visibile come CSV": "Export visible table as CSV",
    "Attiva Real Time Monitoring (1 ping/sec)": "Enable Real Time Monitoring (1 ping/sec)",
    "Real Time Monitoring attivo — clicca per disattivare": "Real Time Monitoring active — click to disable",
    "RTM Attivo": "RTM Active",
    "Ricarica la pagina per aggiornare l'elenco": "Reload the page to refresh the list",
    "Clicca per rimuovere": "Click to remove",
    "Clicca per aggiungere": "Click to add",
    "Elimina tag predefinito": "Remove preset tag",
    "! Anomalia rilevata": "! Anomaly detected",
    "Tag &amp; Gruppo — ": "Tags &amp; Group — ",
    "Gruppo (cliente / azienda)": "Group (client / company)",
    "Tag predefiniti": "Predefined tags",
    "Tag assegnati a questo router": "Tags assigned to this router",
    "Colonne SSH personalizzate": "Custom SSH columns",
    "Aggiungi nuova colonna": "Add new column",
    "Definisci colonna": "Define column",
    "Ping massivo": "Bulk ping",
    "Aggiorna SSH": "Refresh SSH",
    "Elimina selezionati": "Delete selected",
    "Delete selected": "Delete selected",
    "Seleziona Router": "Select Router",
    "Caricamento router…": "Loading routers…",
    # ── Site Manager ─────────────────────────────────────────
    "Lista sedi": "Site list", "Mappa rete": "Network map",
    "sedi": "sites", "device assegnati": "devices assigned",
    "non assegnati": "unassigned", "Device non assegnati": "Unassigned devices",
    "+ Nuova Sede": "+ New Site", "Nuova Sede": "New Site",
    "Modifica Sede": "Edit Site", "Assegnazione massiva": "Bulk assignment",
    "Città / Luogo": "City / Location", "Descrizione": "Description",
    "Assegna Device": "Assign Device", "Sede": "Site",
    "Ruolo": "Role", "Device padre (upstream)": "Parent device (upstream)",
    "Assegna": "Assign", "Modifica assegnazione": "Edit assignment",
    "Settoriale": "Sectorial", "Cliente/CPE": "Client/CPE",
    "Personalizzato...": "Custom...", "Etichetta": "Label",
    "Gateway": "Gateway", "Router": "Router", "Core": "Core",
    "Switch": "Switch", "Altro": "Other", "Personalizzato": "Custom",
    "Tutti i device sono assegnati.": "All devices are assigned.",
    "Nessuna sede.": "No sites.", "Nessun device assegnato.": "No devices assigned.",
    "Nessun device.": "No devices.", "selezionati": "selected",
    "Sede destinazione *": "Destination site *",
    "Assegnazione Massiva Device": "Bulk Device Assignment",
    "Seleziona device, poi scegli sede e ruolo.": "Select devices, then choose site and role.",
    "Cerca": "Search", "Stato": "Status", "Sede attuale": "Current site",
    "Tutte": "All", "Non assegnati": "Unassigned",
    "Dev": "Dev", "On": "On", "Off": "Off",
    "Auto-layout": "Auto-layout", "Centra": "Center",
    "Online": "Online", "Offline": "Offline", "Sconosciuto": "Unknown",
    # ── Backup Manager ───────────────────────────────────────
    "Configurazione schedule": "Schedule configuration",
    "Backup automatico": "Automatic backup",
    "Attivo": "Active", "Disattivo": "Inactive",
    "Intervallo (ore)": "Interval (hours)",
    "Data retention (giorni, 0 = illimitato)": "Data retention (days, 0 = unlimited)",
    "I backup più vecchi vengono rimossi automaticamente": "Older backups are removed automatically",
    "Salva configurazione": "Save configuration",
    "Configurazione salvata": "Configuration saved",
    "Ultimo backup:": "Last backup:", "Prossimo backup:": "Next backup:",
    "Avvia Backup": "Run Backup", "Avvia Backup Manuale": "Run Manual Backup",
    "Backup in corso…": "Backup in progress…",
    "Avvia un backup per vedere il log.": "Run a backup to see the log.",
    "Nessuna operazione eseguita. Avvia un backup per vedere il log.":
        "No operations performed. Run a backup to see the log.",
    "Log operazioni": "Operations log", "Log pulito.": "Log cleared.",
    "Archivio backup": "Backup archive",
    "Seleziona i router": "Select routers", "Seleziona le credenziali SSH": "Select SSH credentials",
    "Apri Credential Manager": "Open Credential Manager",
    "Tutti i router ONLINE": "All routers ONLINE",
    "Senza backup esistente": "Without existing backup",
    "Backup più vecchio di": "Backup older than",
    "Per Sede": "By Site", "Per Gruppo": "By Group", "Singolo router": "Single router",
    "DIMENSIONE": "SIZE", "DATA": "DATE", "FILE": "FILE", "AZIONI": "ACTIONS",
    "Dimensione": "Size", "Data": "Date", "Azioni": "Actions",
    "Dimensione": "Size",
    "Nessun file in archivio.": "No files in archive.",
    # ── Credential Manager ───────────────────────────────────
    "+ Nuove credenziali": "+ New credentials",
    "Nuove credenziali": "New credentials",
    "Modifica credenziali": "Edit credentials",
    "Nome *": "Name *", "Username SSH *": "SSH Username *",
    "Password SSH": "SSH Password",
    "Nessun set credenziali.": "No credential sets.",
    "Utilizzo": "Usage", "Credenziali": "Credentials",
    "Assegnazione ai Siti": "Site Assignment",
    "Credenziali assegnate": "Assigned credentials",
    "Nessun sito configurato.": "No sites configured.",
    "-- Credenziali del singolo router --": "-- Single router credentials --",
    "Salvato": "Saved",
    # ── Network Discovery ────────────────────────────────────
    "Subnet da scansionare": "Subnet to scan",
    "Nome cliente / gruppo": "Client / group name",
    "Credenziali SSH RouterOS": "RouterOS SSH credentials",
    "Credenziali salvate": "Saved credentials",
    "— Inserisci manualmente —": "— Enter manually —",
    "Avvia Scansione": "Start Scan",
    "Scansione in corso…": "Scanning…",
    "Dispositivi trovati": "Devices found",
    "Tipo": "Type", "MAC": "MAC", "In lista": "In list",
    "Avvia una scansione per trovare dispositivi.": "Run a scan to find devices.",
    "Aggiungi Selezionati": "Add Selected", "Aggiungi Tutti": "Add All",
    # ── Upload Script ────────────────────────────────────────
    "File script (.rsc)": "Script file (.rsc)",
    "Username SSH": "SSH Username", "Password SSH": "SSH Password",
    "Avvia caricamento": "Start Upload",
    # ── Statistics ───────────────────────────────────────────
    "Totale": "Total", "Tot": "Tot",
    "Nessuna sede configurata in Site Manager.": "No sites configured in Site Manager.",
    "↺ Aggiorna ora": "↺ Refresh now",
    # ── Users ────────────────────────────────────────────────
    "Utenti registrati": "Registered users",
    "Cambia Password": "Change password",
    "Viewer — solo lettura": "Viewer — read only",
    "Admin — accesso completo": "Admin — full access",
    "x Elimina": "x Delete",
    # ── Wizard ──────────────────────────────────────────────
    "Configurazione iniziale": "Initial setup",
    "Benvenuto in ROSM": "Welcome to ROSM",
    "Lingua": "Language", "Italiano": "Italian", "Inglese": "English",
    "Sicurezza": "Security", "Pronto": "Ready",
    "Avanti →": "Next →", "← Indietro": "← Back",
    "Completa configurazione": "Complete setup",
    "Cambia la password amministratore": "Change admin password",
    "Codice di recupero account": "Account recovery code",
    "Salva questo codice in un posto sicuro.": "Save this code somewhere safe.",
    "Configurazione completata!": "Setup complete!",
    "Vai all'applicazione →": "Go to application →",
    # ── Settings ─────────────────────────────────────────────
    "Impostazioni applicazione": "Application settings",
    "Lingua interfaccia": "Interface language",
    "Sicurezza account": "Account security",
    "Password attuale": "Current password",
    "Nuova password": "New password",
    "Conferma password": "Confirm password",
    "Salva impostazioni": "Save settings",
    "Impostazioni salvate.": "Settings saved.",
    "Nome aggiornato.": "Name updated.",
    "Display name": "Display name",
    "Nome visualizzato": "Display name",
    # ── Page titles ──────────────────────────────────────────
    "Gestione Utenti": "Users",
    "Runs Log": "Runs Log", "Uploads Log": "Uploads Log",
    "Carica Script — ": "Upload Script — ",
    # ── Card headers & section titles ────────────────────────
    "Configurazione schedule": "Schedule configuration",
    "Avvia Backup": "Run Backup", "Avvia caricamento": "Start Upload",
    "Archivio backup": "Backup archive", "Log operazioni": "Operations log",
    "Assegnazione ai Siti": "Site assignment",
    "Credenziali salvate": "Saved credentials",
    "Dispositivi trovati": "Devices found",
    "Subnet da scansionare": "Subnet to scan",
    "Carica Script": "Upload Script",
    "Info SSH": "SSH Info",
    "Colonne": "Columns",
    # ── Buttons ──────────────────────────────────────────────
    "Cambia": "Change",
    "Carica": "Upload",
    "Assegna": "Assign",
    "+ Aggiungi": "+ Add",
    "+ Crea": "+ Create",
    "Crea": "Create",
    "Creds": "Creds",
    "Nuovo utente": "New user",
    "Delete selected": "Delete selected",
    "x Pulisci": "x Clear",
    "&#8635; Auto-layout": "↻ Auto-layout",
    "&#8982; Centra": "⌘ Center",
    # ── Form labels ──────────────────────────────────────────
    "Citta / Luogo": "City / Location",
    "Città / Luogo": "City / Location",
    "Hostname / Identity ↕": "Hostname / Identity ↕",
    "IP ↕": "IP ↕",
    "Ruolo (opzionale)": "Role (optional)",
    "Tag / Gruppo": "Tag / Group",
    "Tag assegnati a questo router": "Tags assigned to this router",
    "Nessun tag assegnato": "No tags assigned",
    "Nessun tag predefinito — creane uno ↓": "No predefined tags — create one ↓",
    "Nome cliente / gruppo": "Client / group name",
    "Password *": "Password *",
    "Username *": "Username *",
    "Output": "Output", "Script": "Script",
    "In lista": "In list",
    # ── Status messages & placeholders ───────────────────────
    "Nessun dato disponibile.": "No data available.",
    "Nessun dispositivo trovato.": "No devices found.",
    "Nessun router trovato.": "No routers found.",
    "Nessun set credenziali. Premi &quot;+ Nuove credenziali&quot; per iniziare.":
        "No credential sets. Press &quot;+ New Credentials&quot; to begin.",
    "Non assegnato": "Unassigned",
    "Tutti": "All",
    "Siti": "Sites",
    "Avvia un ping dalla Dashboard per popolare il grafico.":
        "Run a ping from the Dashboard to populate the graph.",
    "Definisci una colonna con un comando RouterOS. Il risultato SSH verrà mostrato nella colonna selezionabile.":
        "Define a column with a RouterOS command. The SSH result will be shown in the selectable column.",
    "File script (.rsc) — verrà caricato su tutti i router delle aziende selezionate":
        "Script file (.rsc) — will be uploaded to all routers of the selected companies",
    # ── Dashboard (main page) strings ────────────────────────
    "Ping": "Ping",
    "Gruppo": "Group",
    "Aggiungi": "Add",
    "Configurazione": "Configuration",
    "connessione": "connection",
    "Versione ROS": "ROS Version",
    "Porte aperte": "Open ports",
    "Ultimo ping": "Last ping",
    "Riavvia il server ROSM? La pagina si ricaricherà automaticamente.":
        "Restart the ROSM server? The page will reload automatically.",
    "Riavviare il server ROSM? La pagina si ricaricherà automaticamente.":
        "Restart the ROSM server? The page will reload automatically.",
    "Esci": "Sign out",
    "Sessione 24h": "24h session",
    # ── Users page ───────────────────────────────────────────
    "Ruolo (opzionale)": "Role (optional)",
    "Aggiungi utente": "Add user",
    "Nessun utente.": "No users.",
    "Username o password vuoti.": "Username or password are empty.",
    "Username già esistente.": "Username already exists.",
    "Non puoi eliminare il tuo stesso account.": "You cannot delete your own account.",
    "Utente creato.": "User created.",
    "Utente eliminato.": "User deleted.",
    "Password aggiornata.": "Password updated.",
    "Nuova password…": "New password…",
    " (tu)": " (you)",
    # ── Credential Manager ───────────────────────────────────
    "Nessun set credenziali configurato. Crea un set nel pannello a destra.":
        "No credential sets configured. Create one in the right panel.",
    "Apri Credential Manager →": "Open Credential Manager →",
    "— Automatico: usa le credenziali del sito o del router —":
        "— Automatic: use site or router credentials —",
    "Verranno usate le credenziali assegnate a ciascun sito":
        "Credentials assigned to each site will be used",
    # ── Statistics ───────────────────────────────────────────
    "Online:": "Online:",
    "Nessuna sede configurata in Site Manager.": "No sites configured in Site Manager.",
    # ── Site Manager extras ───────────────────────────────────
    "Assegnazione Massiva Device": "Bulk Device Assignment",
    "Seleziona device, poi scegli sede e ruolo.": "Select devices, then choose site and role.",
    "Sede attuale": "Current site",
    "-- Nessuna sede --": "-- No site --",
    "-- Nessuno (radice) --": "-- None (root) --",
    "Nessuna sede.": "No sites.",
    "router ONLINE": "routers ONLINE",
    "router completati": "routers completed",
    "Es: 24 = ogni giorno, 168 = settimanale": "E.g.: 24 = daily, 168 = weekly",
    "I backup più vecchi vengono rimossi automaticamente": "Older backups are removed automatically",
    "Attivo": "Active", "Disattivo": "Inactive",
    "Avvia un backup per vedere il log.": "Run a backup to see the log.",
    "Log pulito.": "Log cleared.",
    "Nessuna operazione eseguita. Avvia un backup per vedere il log.":
        "No operations performed. Run a backup to see the log.",
    "Backup in corso…": "Backup in progress…",
    "Backup avviato — attendo il completamento…": "Backup started — waiting for completion…",
    # ── JS-generated strings with dynamic content ─────────────
    "ONLINE su ": "ONLINE out of ",
    " totali verranno backuppati": " total will be backed up",
    "verranno backuppati": "will be backed up",
    "(impostabili nella sezione qui sotto) o, in mancanza, quelle configurate per il singolo router.":
        "(configurable in the section below), or else those configured for the individual router.",
    "Nessun router ONLINE al momento. Verifica che i dispositivi siano raggiungibili o avvia un ping dalla Dashboard.":
        "No routers ONLINE at the moment. Check that devices are reachable or run a ping from the Dashboard.",
    # ── Dashboard table headers & labels ─────────────────────
    "Ruolo": "Role", "Cambia Password": "Change password",
    "Nome": "Name", "Modello": "Model",
    "Porte Aperte": "Open Ports",
    "Ultimo Online": "Last online", "Sito": "Site",
    "Hostname / Identity ↕": "Hostname / Identity ↕",
    "Tag / Gruppo": "Tag / Group",
    "Stato": "Status",
    # ── Dashboard action / status labels ─────────────────────
    "Avvia un ping dalla Dashboard per popolare il grafico.":
        "Run a ping from the Dashboard to populate the graph.",
    "IN CORSO": "IN PROGRESS", "WORKING": "WORKING",
    "Caricamento router…": "Loading routers…",
    "Seleziona un set credenziali o inserisci username e password prima di aggiungere i dispositivi.":
        "Select a credential set or enter username and password before adding devices.",
    "dispositivi aggiunti": "devices added",
    "→ Vai alla lista": "→ Go to list",
    "Aggiorna SSH": "Refresh SSH",
    "Avvia un ping": "Run ping",
    "Ping massivo": "Bulk ping",
    "Credenziali non presenti. Configurale per il router nel pannello laterale.":
        "Credentials not set. Configure them for this router in the side panel.",
    "No creds": "No creds",
    "Non assegnato": "Unassigned",
    # ── Users page ───────────────────────────────────────────
    "Utilizzo": "Usage",
    "Credenziali assegnate": "Assigned credentials",
    "Password *": "Password *", "Username *": "Username *",
    "Apri Credential Manager": "Open Credential Manager",
    # ── Uploads/Runs log pages ────────────────────────────────
    "File caricato": "File uploaded",
    "Script eseguito": "Script run",
    "Nessun log disponibile.": "No logs available.",
    # ── Home page cards ───────────────────────────────────────
    "sedi configurate": "sites configured",
    "archivi salvati": "archives saved",
    "Gestisci accessi e ruoli": "Manage access and roles",
    "Scansiona la rete per trovare router RouterOS": "Scan the network to find RouterOS routers",
    "Gestisci sedi e topologia di rete": "Manage sites and network topology",
    "Carica script .rsc su più router contemporaneamente":
        "Upload .rsc scripts to multiple routers simultaneously",
    "Statistiche sedi, device online/offline": "Site statistics, devices online/offline",
    # ── Generic ──────────────────────────────────────────────
    "Tipo": "Type",
    "Nessun dato.": "No data.",
    "Nessun risultato.": "No results.",
    "Cerca…": "Search…",
    "Errore di rete: ": "Network error: ",
    "Errore: ": "Error: ",
    " selezionati": " selected",
    "Apri Credential Manager →": "Open Credential Manager →",
    "Impostazioni": "Settings",
    # ── Home page ─────────────────────────────────────────────
    "Lingua, password, recupero account": "Language, password, recovery code",
    "Upgrade RouterOS": "Upgrade RouterOS",
    "Aggiornamento RouterOS": "RouterOS Upgrade",
    "Aggiornamento firmware da remoto": "Remote firmware upgrade",
    "Carica script .rsc sui router": "Upload .rsc scripts to routers",
    "Ciao, admin": "Hello, admin",
    "Ciao,": "Hello,",
    "Scegli cosa vuoi fare": "Choose what you'd like to do",
    "Scansiona e aggiungi dispositivi": "Scan and add devices",
    "Grafici e metriche di rete": "Network graphs and metrics",
    "Upload script .rsc sui router": "Upload .rsc scripts to routers",
    "Carica script .rsc sui router": "Upload .rsc scripts to routers",
    "sui router": "to routers",
    "set configurati": "credential sets",
    "set configurato": "credential set",
    "router online": "routers online",
    "archivi salvati": "backup archives saved",
    "sedi configurate": "sites configured",
    "sede configurata": "site configured",
    # ── Dropdown options ──────────────────────────────────────
    "-- Nessun ruolo --": "-- No role --",
    "-- Nessuno --": "-- None --",
    # ── Statistics page ───────────────────────────────────────
    "Città": "City",
    "Sedi — stato dispositivi": "Sites — device status",
    # ── Misc remaining Italian ────────────────────────────────
    "Nessun sito configurato. Crea siti in Site Manager prima.":
        "No sites configured. Create sites in Site Manager first.",
    "Nessun set credenziali. Premi": "No credential sets. Press",
    "per iniziare.": "to begin.",
    # ── Dashboard status ─────────────────────────────────────
    "inattivo": "inactive",
    "● IN CORSO": "● IN PROGRESS",
    "porta…": "ports…",
    "Pulisci filtri": "Clear filters",
    # ── Dashboard stat bar & tooltips ─────────────────────────
    "SSH attive": "Active SSH",
    "SSH in coda": "Queued SSH",
    "Ping tutti i router": "Ping all routers",
    "SSH su tutti: nome, modello, versione": "SSH all: name, model, version",
    "Ping ogni": "Ping every",
    "Leggi info SSH": "Read SSH info",
    # ── Dashboard table / modals ──────────────────────────────
    "Modello (dup.)": "Model (dup.)",
    "Crea nuovo tag…": "Create new tag…",
    "Colonne SSH Personalizzate": "Custom SSH Columns",
    "Carica Script per Azienda": "Upload Script by Company",
    "Credenziali SSH": "SSH Credentials",
    "— Nessuna (usa default di sito/globale) —": "— None (use site/global default) —",
    "I set si gestiscono in": "Sets are managed in",
    # ── Statistics cards & KPIs ───────────────────────────────
    "Stato rete": "Network status",
    "Online nel tempo": "Online over time",
    "Versione firmware RouterOS": "RouterOS firmware version",
    "Distribuzione uptime": "Uptime distribution",
    "Copertura info SSH": "SSH info coverage",
    "Copertura backup": "Backup coverage",
    "Script assegnati": "Assigned scripts",
    "Risultati ultima esecuzione": "Last run results",
    "Risultati ultimo ping": "Last ping results",
    "Info disponibili": "Info available",
    "Senza dati SSH": "Without SSH data",
    "Con backup": "With backup",
    "Senza backup": "Without backup",
    "Con script": "With script",
    "Senza script": "Without script",
    "Mai eseguito": "Never run",
    "Dispositivi": "Devices",
    "nel registro": "in registry",
    "Backup archiviati": "Archived backups",
    "< 1 giorno": "< 1 day",
    "1–7 giorni": "1–7 days",
    "1–4 settimane": "1–4 weeks",
    "1–3 mesi": "1–3 months",
    "> 3 mesi": "> 3 months",
    "N/D": "N/A",
    "totale": "total",
    "Aggiornato alle": "Updated at",
    "dispositivi": "devices",
    "Siti": "Sites",
    "sito/i": "site(s)",
    "Nessun set credenziali configurato.": "No credential sets configured.",
    # ── Credential Manager ────────────────────────────────────
    "Crea set nominati di credenziali riutilizzabili. Selezionali da Backup Manager, Upload Script e Network Discovery.":
        "Create named reusable credential sets. Select them from Backup Manager, Upload Script, and Network Discovery.",
    "Associa un set di credenziali a ciascun sito. Il Backup Manager le usera automaticamente per tutti i router di quel sito.":
        "Associate a credential set with each site. Backup Manager will use them automatically for all routers of that site.",
    "Eliminare questo set? Verra rimosso da tutti i siti a cui e assegnato.":
        "Delete this set? It will be removed from all sites it is assigned to.",
    "Inserisci un nome per questo set di credenziali.": "Enter a name for this credential set.",
    "Inserisci lo username SSH.": "Enter the SSH username.",
    "Inserisci la password SSH.": "Enter the SSH password.",
    "(vuoto = non cambiare)": "(empty = keep unchanged)",
    "Errore durante la cancellazione.": "Error while deleting.",
    "— Credenziali del singolo router —": "— Single router credentials —",
    # ── Users page ────────────────────────────────────────────
    "Crea utente": "Add user",
    "Solo lettere, numeri, _ e -": "Letters, numbers, _ and - only",
    "Min. 8 caratteri": "Min. 8 characters",
    "es. mario": "e.g. mario",
    "Operazione completata.": "Operation completed.",
    "Errore sconosciuto.": "Unknown error.",
    # ── Network Discovery ─────────────────────────────────────
    "Rilevata automaticamente dalla rete locale. Consigliato /24 (256 IP).":
        "Auto-detected from local network. /24 (256 IPs) recommended.",
    "Le credenziali vengono salvate per ciascun router aggiunto e usate per tutte le operazioni SSH successive.":
        "Credentials are saved for each added router and used for all subsequent SSH operations.",
    "Opzionali — la scansione funziona anche senza: rileva comunque IP, porte aperte e tipo dispositivo. Servono solo per leggere identity e modello RouterOS via SSH.":
        "Optional — the scan also works without them: it still detects IP, open ports and device type. They're only needed to read RouterOS identity and model via SSH.",
    "opzionale": "optional",
    # ── Upload Script / Credential common ────────────────────
    "Seleziona un set salvato oppure inserisci le credenziali manualmente.":
        "Select a saved set or enter credentials manually.",
    "Cerca per IP o nome…": "Search by IP or name…",
    "Seleziona tutti visibili": "Select all visible",
    # ── Backup Manager ────────────────────────────────────────
    "Selezione intelligente": "Smart selection",
    "creds: predefinite": "creds: default",
    "Ricarica la pagina per aggiornare l'elenco": "Reload the page to update the list",
    "Dimensione totale": "Total size",
    # ── Keep some already-correct English strings (no-op) ────
    "Home": "Home", "Dashboard": "Dashboard",
    "Network Discovery": "Network Discovery",
    "Upload Script": "Upload Script",
    "Backup Manager": "Backup Manager",
    "Site Manager": "Site Manager",
    "Credential Manager": "Credential Manager",
}

def T(s: str) -> str:
    """Return translated string. Falls back to input."""
    if LANGUAGE == "it":
        return s
    return _T_EN.get(s, s)

def _set_language(lang: str):
    global LANGUAGE
    LANGUAGE = lang
    cfg = _load_app_config()
    cfg["language"] = lang
    _save_app_config(cfg)
UPLOAD_DIR       = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────────
# § Encryption  (Fernet / AES-128-CBC + HMAC-SHA256)
# ─────────────────────────────────────────────────────────────────
import base64 as _b64
try:
    from cryptography.fernet import Fernet as _Fernet, InvalidToken as _InvalidToken
    _FERNET_AVAILABLE = True
except ImportError:
    _FERNET_AVAILABLE = False

_ROSM_KEY_FILE = os.path.join(BASE_DIR, ".rosm_key")

def _load_or_create_key():
    if os.path.exists(_ROSM_KEY_FILE):
        with open(_ROSM_KEY_FILE, "rb") as f:
            return f.read().strip()
    key = _Fernet.generate_key() if _FERNET_AVAILABLE else None
    if key:
        with open(_ROSM_KEY_FILE, "wb") as f:
            f.write(key)
        # Restrict permissions on Unix
        try:
            os.chmod(_ROSM_KEY_FILE, 0o600)
        except Exception:
            pass
    return key

_FERNET_INSTANCE = None
def _fernet():
    global _FERNET_INSTANCE
    if _FERNET_INSTANCE is None and _FERNET_AVAILABLE:
        k = _load_or_create_key()
        if k:
            _FERNET_INSTANCE = _Fernet(k)
    return _FERNET_INSTANCE

def _encrypt(s: str) -> str:
    """Encrypt with Fernet. Falls back to legacy XOR if unavailable."""
    if not s:
        return ""
    f = _fernet()
    if f:
        return "F:" + f.encrypt(s.encode()).decode()
    return _e_legacy(s)

def _decrypt(token: str) -> str:
    """Decrypt. Handles Fernet tokens (prefix F:) and legacy XOR tokens."""
    if not token:
        return ""
    if token.startswith("F:"):
        f = _fernet()
        if f:
            try:
                return f.decrypt(token[2:].encode()).decode()
            except Exception:
                return ""
        return ""
    # Legacy XOR+base64
    return _e_legacy_d(token)

# Legacy XOR — kept for backward-compat with existing devices.json / state.json
_SSH_KEY = b"r0sch3ck!"
def _e_legacy_d(s: str) -> str:
    try:
        raw = _b64.b64decode(s)
        return bytes(a ^ _SSH_KEY[i % len(_SSH_KEY)] for i, a in enumerate(raw)).decode()
    except Exception:
        return ""
def _e_legacy(s: str) -> str:
    raw = s.encode()
    return _b64.b64encode(bytes(a ^ _SSH_KEY[i % len(_SSH_KEY)] for i, a in enumerate(raw))).decode()

# Aliases used throughout the codebase for device credentials (stay with legacy for compat)
def _d(s: str) -> str: return _e_legacy_d(s)
def _e(s: str) -> str: return _e_legacy(s)

# ── File-level encryption (optional, for backups + state) ─────
_ENC_MARKER = "ROSM_ENC:"

def _encrypt_file_content(content: str) -> str:
    """Encrypt a file's text content. Returns ROSM_ENC:<token> string."""
    if not _FERNET_AVAILABLE:
        return content
    f = _fernet()
    if not f:
        return content
    return _ENC_MARKER + f.encrypt(content.encode("utf-8")).decode()

def _decrypt_file_content(content: str) -> str:
    """Decrypt file content if it was encrypted with _encrypt_file_content."""
    if not content.startswith(_ENC_MARKER):
        return content
    f = _fernet()
    if not f:
        return content
    try:
        return f.decrypt(content[len(_ENC_MARKER):].encode()).decode("utf-8")
    except Exception:
        return content

def _is_file_encrypted(path: str) -> bool:
    """Return True if the file at path was encrypted with ROSM_ENC."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(len(_ENC_MARKER)) == _ENC_MARKER
    except Exception:
        return False

SSH_TIMEOUT      = 8   # seconds

# ─────────────────────────────────────────────────────────────────
# § Core helpers
# ─────────────────────────────────────────────────────────────────
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

# ─────────────────────────────────────────────────────────────────
# § Devices store
# ─────────────────────────────────────────────────────────────────
DEVICES_FILE  = os.path.join(BASE_DIR, "devices.json")
PREDEFINED_TAGS_FILE = os.path.join(BASE_DIR, "predefined_tags.json")
DEVICES       = {}
DEVICES_LOCK  = threading.Lock()

def _load_predefined_tags():
    return load_json(PREDEFINED_TAGS_FILE, [])

def _save_predefined_tags(tags):
    save_json_atomic(PREDEFINED_TAGS_FILE, tags)

def _make_device(ip, tags=None, group="", ssh_user=None, ssh_pass=None, mac="", note="",
                  site_id="", parent_ip="", device_role="", device_role_label="",
                  link_type=""):
    return {
        "ip":               ip,
        "tags":             tags or [],
        "group":            group,
        "credential_id":    "",                           # named credential set (preferred)
        "ssh_user":         ssh_user or "",               # legacy per-device (kept for compat)
        "ssh_pass_enc":     _encrypt(ssh_pass) if ssh_pass else "",
        "mac":              mac,
        "added":            now_str(),
        "note":             note,
        "site_id":          site_id,
        "parent_ip":        parent_ip,
        "device_role":      device_role,
        "device_role_label":device_role_label,
        "link_type":        link_type,         # type of link to parent_ip
    }

def _load_devices():
    global DEVICES
    if os.path.exists(DEVICES_FILE):
        try:
            with open(DEVICES_FILE) as f:
                DEVICES = json.load(f)
            return
        except Exception:
            pass
    # Migrate from routers.txt if it exists
    DEVICES = {}
    if os.path.exists(ROUTERS_FILE):
        with open(ROUTERS_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                ip = line.split(",")[0].strip()
                if ip:
                    DEVICES[ip] = _make_device(ip)
        print(f"Migrated {len(DEVICES)} devices from routers.txt → devices.json")
    save_json_atomic(DEVICES_FILE, DEVICES)

def _save_devices():
    save_json_atomic(DEVICES_FILE, DEVICES)

def device_update(ip, **kwargs):
    with DEVICES_LOCK:
        if ip not in DEVICES:
            DEVICES[ip] = _make_device(ip)
        DEVICES[ip].update(kwargs)
        _save_devices()

def device_add(ip, tags=None, group="", ssh_user=None, ssh_pass=None, mac="", note=""):
    with DEVICES_LOCK:
        existed = ip in DEVICES
        if not existed:
            DEVICES[ip] = _make_device(ip, tags, group, ssh_user, ssh_pass, mac, note)
            _save_devices()
        return not existed

def device_remove(ip):
    with DEVICES_LOCK:
        if ip in DEVICES:
            del DEVICES[ip]
            _save_devices()
            return True
        return False

def _get_device_creds(ip):
    """Return (ssh_user, ssh_password) for a device.
    Priority: named credential_id → per-device ssh_user/pass → site credential."""
    dev = DEVICES.get(ip, {})
    # 1. Named credential set assigned to device
    cred_id = dev.get("credential_id", "")
    if cred_id:
        user, passwd = _resolve_cred_id(cred_id)
        if user:
            return user, passwd
    # 2. Legacy per-device credentials
    user   = dev.get("ssh_user", "") or ""
    enc    = dev.get("ssh_pass_enc", "") or ""
    passwd = _decrypt(enc) if enc else ""
    if user and passwd:
        return user, passwd
    # 3. Site credential set
    site_id = dev.get("site_id", "")
    if site_id:
        user, passwd = _get_creds_for_site(site_id)
        if user:
            return user, passwd
    return "", ""

def _device_has_creds(ip):
    """True if the device has credentials configured (named set or per-device)."""
    dev = DEVICES.get(ip, {})
    return bool(dev.get("credential_id")) or (bool(dev.get("ssh_user")) and bool(dev.get("ssh_pass_enc")))

# ─────────────────────────────────────────────────────────────────
# § Discovery & fingerprinting
# ─────────────────────────────────────────────────────────────────
SCAN_JOBS      = {}   # job_id → {status, total, done, results, group, subnet}
SCAN_JOBS_LOCK = threading.Lock()

# ── OUI database (MAC prefix → vendor) ──────────────────────────────────────
# Covers the most common manufacturers encountered in network scans.
# ── OUI database: loaded from cache or downloaded from IEEE ──────────────────
_OUI_DB: dict = {}          # "AA:BB:CC" → "Vendor Name"
_OUI_LOCK = threading.Lock()

# Minimal fallback (used before download completes or if offline)
_OUI_FALLBACK = {
    "00:0C:42":"MikroTik","4C:5E:0C":"MikroTik","48:8F:5A":"MikroTik",
    "B8:69:F4":"MikroTik","E4:8D:8C":"MikroTik","6C:3B:6B":"MikroTik",
    "DC:2C:6E":"MikroTik","2C:C8:1B":"MikroTik","CC:2D:E0":"MikroTik",
    "18:FD:74":"MikroTik","74:4D:28":"MikroTik","D4:CA:6D":"MikroTik",
    "00:27:22":"Ubiquiti","04:18:D6":"Ubiquiti","18:E8:29":"Ubiquiti",
    "24:A4:3C":"Ubiquiti","44:D9:E7":"Ubiquiti","68:72:51":"Ubiquiti",
    "DC:9F:DB":"Ubiquiti","F4:92:BF":"Ubiquiti","FC:EC:DA":"Ubiquiti",
    "00:00:0C":"Cisco","00:1A:A1":"Cisco","00:1B:54":"Cisco",
    "58:BC:27":"Cisco","70:69:5A":"Cisco","F8:7B:20":"Cisco",
    "00:0B:86":"Aruba","04:BD:88":"Aruba","84:D4:7E":"Aruba",
    "B8:27:EB":"Raspberry Pi","DC:A6:32":"Raspberry Pi","E4:5F:01":"Raspberry Pi",
    "00:0C:29":"VMware","00:50:56":"VMware","08:00:27":"VirtualBox",
    "00:11:32":"Synology","00:08:9B":"QNAP",
}

def _oui_lookup(mac: str) -> str:
    """Return vendor name for a MAC address. Uses full IEEE database if loaded."""
    if not mac:
        return ""
    clean = mac.upper().replace("-", ":").replace(".", ":")
    parts = clean.split(":")
    if len(parts) < 3:
        return ""
    prefix = ":".join(parts[:3])
    with _OUI_LOCK:
        if _OUI_DB:
            return _OUI_DB.get(prefix, "")
    return _OUI_FALLBACK.get(prefix, "")

def _load_oui_cache():
    """Load cached OUI database from disk."""
    global _OUI_DB
    try:
        if os.path.exists(OUI_CACHE_FILE):
            data = load_json(OUI_CACHE_FILE, {})
            if data:
                with _OUI_LOCK:
                    _OUI_DB.update(data)
                print(f"OUI database loaded: {len(_OUI_DB):,} entries from cache")
                return True
    except Exception as e:
        print(f"OUI cache load error: {e}")
    return False

def _download_oui_db():
    """Download the full IEEE OUI database and cache locally.
    Called in a background thread at startup."""
    global _OUI_DB
    import urllib.request
    if _OUI_DB:
        return  # already loaded from cache
    # IEEE MA-L OUI CSV — ~30 000 entries, ~2.5 MB
    url = "https://standards-oui.ieee.org/oui/oui.csv"
    try:
        print("Downloading IEEE OUI database…")
        req = urllib.request.Request(url, headers={"User-Agent": "ROSM/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        _NORM = {
            "routerboard":"MikroTik","mikrotik":"MikroTik",
            "ubiquiti":"Ubiquiti",
            "apple":"Apple",
            "samsung":"Samsung",
            "huawei":"Huawei",
            "cisco":"Cisco",
            "tp-link":"TP-Link","tp-link corporation":"TP-Link",
            "netgear":"Netgear",
            "raspberry pi":"Raspberry Pi",
            "vmware":"VMware","oracle virtualbox":"VirtualBox",
            "hewlett packard":"HP","hp inc":"HP",
            "aruba":"Aruba",
            "synology":"Synology","qnap":"QNAP",
            "intel":"Intel",
            "realtek":"Realtek",
            "espressif":"Espressif (ESP32)",
            "d-link":"D-Link",
            "zyxel":"Zyxel",
            "asus":"ASUS","asustek":"ASUS",
            "dell":"Dell",
            "lenovo":"Lenovo",
        }
        def _norm_vendor(name):
            low = name.lower()
            for k, v in _NORM.items():
                if k in low:
                    return v
            return name
        db = {}
        for line in raw.splitlines()[1:]:   # skip header
            parts = line.split(",")
            if len(parts) >= 3:
                # Format: Registry,Assignment,Organization Name,...
                oui_hex = parts[1].strip().strip('"')   # e.g. "DC2C6E"
                vendor  = _norm_vendor(parts[2].strip().strip('"'))
                if len(oui_hex) == 6:
                    prefix = ":".join(oui_hex[i:i+2].upper() for i in range(0,6,2))
                    db[prefix] = vendor
        if db:
            with _OUI_LOCK:
                _OUI_DB.update(db)
            save_json_atomic(OUI_CACHE_FILE, db)
            print(f"OUI database updated: {len(db):,} entries")
    except Exception as e:
        print(f"OUI download failed: {e} — using fallback database")
        with _OUI_LOCK:
            if not _OUI_DB:
                _OUI_DB.update(_OUI_FALLBACK)

def _normalize_mac(raw: str) -> str:
    """Normalize a MAC address string to XX:XX:XX:XX:XX:XX uppercase.
    Handles macOS format that omits leading zeros (e.g. '4:f4:1c:...')."""
    sep = "-" if "-" in raw else ":"
    parts = raw.split(sep)
    if len(parts) != 6:
        return ""
    try:
        return ":".join(f"{int(p, 16):02X}" for p in parts)
    except ValueError:
        return ""

def _get_mac_from_arp(ip: str) -> str:
    """Read the MAC address for an IP from the OS ARP cache."""
    # macOS: subprocess.check_output() forks the multi-threaded server process,
    # which can crash (see _tcp_reachable). Skip there; RouterOS devices still
    # get their MAC via SSH (_ssh_connect_creds) when credentials are set.
    if sys.platform != "darwin":
        try:
            arp_flag = "-a" if _IS_WINDOWS else "-n"
            out = subprocess.check_output(
                ["arp", arp_flag, ip], stderr=subprocess.DEVNULL, timeout=2
            ).decode(errors="ignore")
            for line in out.splitlines():
                if "(incomplete)" in line:
                    continue
                for part in line.split():
                    # Match both full (AA:BB:CC:DD:EE:FF) and macOS short (A:BB:CC:DD:EE:FF)
                    if re.match(r'^([0-9A-Fa-f]{1,2}[:\-]){5}[0-9A-Fa-f]{1,2}$', part):
                        normalized = _normalize_mac(part)
                        if normalized:
                            return normalized
        except Exception:
            pass
    # Fallback: /proc/net/arp (Linux)
    try:
        with open("/proc/net/arp") as f:
            for line in f:
                cols = line.split()
                if len(cols) >= 4 and cols[0] == ip:
                    mac = cols[3]
                    if mac != "00:00:00:00:00:00" and ":" in mac:
                        return mac.upper()
    except Exception:
        pass
    return ""



TAG_COLORS = [
    "#4f8ef7","#2adf8a","#f7c44f","#f74f6a","#9b7ef7",
    "#f78a4f","#4fd4f7","#df2a7e","#f7f74f","#2ad4df",
]

_IS_WINDOWS = (os.name == "nt")

def _ping_cmd(ip, timeout_s=2):
    """Cross-platform ping: 1 echo request, timeout in seconds.
    Windows usa -n/-w (ms), POSIX usa -c/-W (s)."""
    if _IS_WINDOWS:
        return ["ping", "-n", "1", "-w", str(int(timeout_s * 1000)), ip]
    return ["ping", "-c", "1", "-W", str(int(timeout_s)), ip]

def _tcp_reachable(ip: str, timeout: float = 2.0) -> bool:
    """Reachability check via TCP connect — no fork(), no subprocess.
    Avoids the macOS atfork crash (SIGSEGV in nw_settings_child_has_forked)
    that subprocess.run(ping) triggers in a multi-threaded process.
    Tries ports common on MikroTik and generic LAN devices.
    Returns True if the host responds (port open or RST) on any port."""
    import errno as _en
    _ports = (22, 8291, 8728, 80, 443, 23)
    _per = max(0.2, timeout / len(_ports))
    for _p in _ports:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as _s:
                _s.settimeout(_per)
                if _s.connect_ex((ip, _p)) in (0, _en.ECONNREFUSED):
                    return True
        except OSError:
            pass
    return False

def fingerprint_host(ip, ssh_user=None, ssh_pass=None, timeout=1.5):
    """Fingerprint a host: ping → ports → SSH banner → HTTP → reverse DNS."""
    result = {
        "ip": ip, "responding": False,
        "device_type": "unknown", "vendor": "",
        "model": "", "hostname": "", "ports": [],
        "ros_identity": "", "ssh_ok": False, "mac": "",
        "details": "",
    }
    # Ping (TCP-based to avoid macOS fork crash in multi-threaded server)
    if not _tcp_reachable(ip, 1.0):
        return result
    result["responding"] = True

    # MAC address from ARP cache (populated by the ping above)
    mac = _get_mac_from_arp(ip)
    if mac:
        result["mac"] = mac
        vendor = _oui_lookup(mac)
        if vendor:
            result["vendor"] = vendor
            # Set device_type from OUI if not already known
            if result["device_type"] == "unknown":
                low = vendor.lower()
                if "mikrotik" in low:
                    result["device_type"] = "routeros"
                elif "ubiquiti" in low:
                    result["device_type"] = "ubiquiti"
                elif "cisco" in low or "aruba" in low:
                    result["device_type"] = "cisco"
                elif "apple" in low:
                    result["device_type"] = "other"

    # Port scan
    CHECK_PORTS = [22, 23, 80, 443, 8080, 8291, 8728, 8443]
    open_ports  = []
    for port in CHECK_PORTS:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            if s.connect_ex((ip, port)) == 0:
                open_ports.append(port)
            s.close()
        except Exception:
            pass
    result["ports"] = open_ports

    # RouterOS: Winbox port 8291 is definitive
    if 8291 in open_ports:
        result["device_type"] = "routeros"
        result["vendor"]      = "MikroTik"

    # SSH banner analysis
    if 22 in open_ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            s.connect((ip, 22))
            banner = s.recv(256).decode("utf-8", errors="ignore").strip()
            s.close()
            bl = banner.lower()
            if "routeros" in bl or "mikrotik" in bl:
                result["device_type"] = "routeros"; result["vendor"] = "MikroTik"
            elif "ubnt" in bl or "ubiquiti" in bl:
                result["device_type"] = "ubiquiti"; result["vendor"] = "Ubiquiti"
            elif "cisco" in bl:
                result["device_type"] = "cisco";    result["vendor"] = "Cisco"
            elif "juniper" in bl:
                result["device_type"] = "juniper";  result["vendor"] = "Juniper"
            elif "openssh" in bl and result["device_type"] == "unknown":
                result["device_type"] = "linux"
            result["details"] = banner[:80]
        except Exception:
            pass

        # If RouterOS and credentials provided → fetch identity/model/mac
        if result["device_type"] == "routeros" and ssh_user and ssh_pass:
            try:
                ssh = _ssh_connect_creds(ip, ssh_user, ssh_pass)
                identity = _exec(ssh, ":put [/system identity get name]")
                model    = (_exec(ssh, ":put [/system routerboard get model]")
                            or _exec(ssh, ":put [/system resource get board-name]"))
                mac      = _exec(ssh, ":put [/interface ethernet get ether1 mac-address]")
                ssh.close()
                result["ros_identity"] = identity
                result["model"]        = model
                result["mac"]          = mac
                result["ssh_ok"]       = True
            except Exception:
                pass

        # Generic SSH: try to get hostname for non-RouterOS devices
        if result["device_type"] != "routeros" and ssh_user and ssh_pass:
            for cmd in ["hostname -s", "hostname", "cat /etc/hostname",
                        "uname -n", "sysctl kern.hostname | awk '{print $2}'"]:
                try:
                    ssh = _ssh_connect_creds(ip, ssh_user, ssh_pass)
                    out = _exec(ssh, cmd)
                    ssh.close()
                    if out and len(out.strip()) > 0 and "\n" not in out.strip():
                        result["hostname"] = out.strip()
                        result["ssh_ok"]   = True
                        break
                except Exception:
                    break

    # HTTP fingerprinting (quick header grab)
    for port in [80, 8080]:
        if port in open_ports and result["vendor"] == "":
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(timeout)
                s.connect((ip, port))
                s.send(b"GET / HTTP/1.0\r\nHost: " + ip.encode() + b"\r\n\r\n")
                resp = s.recv(1024).decode("utf-8", errors="ignore").lower()
                s.close()
                if "mikrotik" in resp or "routeros" in resp:
                    result["device_type"] = "routeros"; result["vendor"] = "MikroTik"
                elif "ubnt" in resp or "ubiquiti" in resp or "airmax" in resp:
                    result["device_type"] = "ubiquiti"; result["vendor"] = "Ubiquiti"
                elif "cisco" in resp:
                    result["device_type"] = "cisco";    result["vendor"] = "Cisco"
                elif "synology" in resp:
                    result["device_type"] = "nas";      result["vendor"] = "Synology"
            except Exception:
                pass
            break

    # ── Hostname resolution (stessa logica di Angry IP Scanner) ─
    def _clean(n):
        if not n or n == ip: return ""
        n = n.split(".")[0] if "." in n else n
        return n.strip().strip("\x00") or ""

    # 1. mDNS PTR — ogni device LAN si annuncia su 224.0.0.251:5353
    if not result["hostname"]:
        try:
            rev   = ".".join(reversed(ip.split("."))) + ".in-addr.arpa"
            qname = b""
            for part in rev.split("."):
                qname += bytes([len(part)]) + part.encode()
            qname += b"\x00"
            pkt = (b"\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00"
                   + qname + b"\x00\x0c\x00\x01")
            sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sk.settimeout(0.8)
            sk.sendto(pkt, ("224.0.0.251", 5353))
            sk.sendto(pkt, (ip, 5353))
            try:
                resp = sk.recv(512)
                # Walk answer section: find first non-numeric DNS label
                i = len(pkt)
                while i < len(resp):
                    ln = resp[i]
                    if ln == 0: break
                    if ln & 0xC0 == 0xC0: i += 2; continue
                    lbl = resp[i+1:i+1+ln].decode("ascii", errors="ignore")
                    if lbl and not lbl.replace("-","").replace("_","").isdigit():
                        h = _clean(lbl)
                        if h: result["hostname"] = h; break
                    i += 1 + ln
            except Exception:
                pass
            sk.close()
        except Exception:
            pass

    # 2. Reverse DNS (il router conosce i lease DHCP)
    if not result["hostname"]:
        try:
            h = _clean(socket.gethostbyaddr(ip)[0])
            if h: result["hostname"] = h
        except Exception:
            pass

    # 3. NetBIOS NBSTAT (Windows/Samba, nessuna credenziale)
    if not result["hostname"]:
        try:
            nb_pkt = (b"\xab\xcd\x00\x10\x00\x01\x00\x00\x00\x00\x00\x00"
                      b"\x20CKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\x00\x00\x21\x00\x01")
            sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sk.settimeout(0.8)
            sk.sendto(nb_pkt, (ip, 137))
            data = sk.recv(1024)
            sk.close()
            if len(data) > 57:
                num = data[56]; off = 57
                for _ in range(min(num, 10)):
                    if off + 18 > len(data): break
                    flag = data[off + 15]
                    if not (flag & 0x80):   # unique name = workstation/server
                        h = _clean(data[off:off+15].decode("ascii", errors="ignore"))
                        if h and h not in ("MSBROWSE__","__MSBROWSE__"):
                            result["hostname"] = h; break
                    off += 18
        except Exception:
            pass

    return result

def start_scan_job(subnet_str, ssh_user, ssh_pass_enc, group_name):
    try:
        net   = ipaddress.ip_network(subnet_str, strict=False)
        hosts = list(net.hosts())
    except ValueError:
        return None, "Subnet non valida"

    ssh_pass = _decrypt(ssh_pass_enc) if ssh_pass_enc else ""
    job_id   = str(uuid.uuid4())
    total    = len(hosts)

    with SCAN_JOBS_LOCK:
        SCAN_JOBS[job_id] = {
            "status":  "running",
            "total":   total,
            "done":    0,
            "results": [],
            "group":   group_name,
            "subnet":  subnet_str,
        }

    def _worker():
        BATCH = 64
        for i in range(0, len(hosts), BATCH):
            batch   = hosts[i:i+BATCH]
            threads = [threading.Thread(target=_scan_one, args=(str(h),)) for h in batch]
            for t in threads: t.start()
            for t in threads: t.join()
        with SCAN_JOBS_LOCK:
            SCAN_JOBS[job_id]["status"] = "done"

    def _scan_one(ip_str):
        r = fingerprint_host(ip_str, ssh_user, ssh_pass)
        with SCAN_JOBS_LOCK:
            SCAN_JOBS[job_id]["results"].append(r)
            SCAN_JOBS[job_id]["done"] += 1

    threading.Thread(target=_worker, daemon=True).start()
    return job_id, None

# ─────────────────────────────────────────────────────────────────
# § Auth & sessions
# ─────────────────────────────────────────────────────────────────
USERS_FILE    = os.path.join(BASE_DIR, "users.json")
SESSIONS      = {}   # token -> {username, role}
SESSIONS_LOCK = threading.Lock()

DEFAULT_ADMIN_PASS  = "Admin@RosCheck1!"
DEFAULT_VIEWER_PASS = "Viewer@RosCheck1"

def _hash_pwd(pwd: str) -> str:
    salt = secrets.token_hex(16)
    h    = hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt.encode(), 200_000)
    return salt + ":" + h.hex()

def _verify_pwd(pwd: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":", 1)
        return hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt.encode(), 200_000).hex() == h
    except Exception:
        return False

def _get_display_name(username: str) -> str:
    """Return the display name for a user, falling back to the username."""
    return USERS.get(username, {}).get("display_name") or username

def _set_display_name(username: str, name: str) -> None:
    if username in USERS:
        USERS[username]["display_name"] = name.strip()
        save_json_atomic(USERS_FILE, USERS)

def _load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    # First run: create defaults and print passwords to console
    users = {
        "admin":  {"hash": _hash_pwd(DEFAULT_ADMIN_PASS),  "role": "admin"},
        "viewer": {"hash": _hash_pwd(DEFAULT_VIEWER_PASS), "role": "viewer"},
    }
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)
    print("=" * 50)
    print("Utenti creati (prima esecuzione):")
    print(f"  admin  → {DEFAULT_ADMIN_PASS}")
    print(f"  viewer → {DEFAULT_VIEWER_PASS}")
    print("=" * 50)
    return users

USERS = _load_users()

def _get_session(handler):
    for part in handler.headers.get("Cookie", "").split(";"):
        p = part.strip()
        if p.startswith("session="):
            token = p[8:]
            with SESSIONS_LOCK:
                return SESSIONS.get(token)
    return None

def _new_session(username: str, role: str) -> str:
    token = secrets.token_urlsafe(32)
    with SESSIONS_LOCK:
        SESSIONS[token] = {"username": username, "role": role}
    return token

def _del_session(handler):
    for part in handler.headers.get("Cookie", "").split(";"):
        p = part.strip()
        if p.startswith("session="):
            token = p[8:]
            with SESSIONS_LOCK:
                SESSIONS.pop(token, None)

# ─────────────────────────────────────────────────────────────────
# § Role helpers
# ─────────────────────────────────────────────────────────────────
ELEVATED_ROLES = frozenset({"admin", "manager", "technician"})
VALID_ROLES    = frozenset({"admin", "manager", "technician", "custom", "viewer"})

# Permissions available to custom-role users (key, Italian label, English label)
CUSTOM_PERMS = [
    ("backup",          "Backup",              "Backup"),
    ("credentials",     "Credenziali",         "Credentials"),
    ("log_write",       "Cancella Log",        "Clear log"),
    ("upload",          "Script Upload",       "Script Upload"),
    ("device_write",    "Gestione device",     "Device management"),
    ("discovery_write", "Network Discovery",   "Network Discovery"),
    ("users_write",     "Gestione Utenti",     "User management"),
    ("admin_mgmt",      "Gestione Admin",      "Admin management"),
]

def _is_admin(session) -> bool:
    return (session or {}).get("role") == "admin"

def _can_do(session, perm: str) -> bool:
    """Check if a session has a specific capability."""
    role = (session or {}).get("role", "viewer")
    if role == "admin":
        return True
    if role == "manager":
        return perm in {"backup", "credentials", "log_write", "users_write", "upgrade"}
    if role == "technician":
        return perm in {"credentials"}
    if role == "custom":
        u = USERS.get((session or {}).get("username", ""), {})
        return bool(u.get("permissions", {}).get(perm))
    return False

def _is_elevated(session) -> bool:
    """True for admin/manager/technician, or custom user with any permission."""
    role = (session or {}).get("role", "viewer")
    if role in ELEVATED_ROLES:
        return True
    if role == "custom":
        u = USERS.get((session or {}).get("username", ""), {})
        return any(u.get("permissions", {}).values())
    return False

# ─────────────────────────────────────────────────────────────────
# § MFA (TOTP)
# ─────────────────────────────────────────────────────────────────
MFA_PENDING      = {}   # token -> {username, role, expires_at, temp_secret?}
MFA_PENDING_LOCK = threading.Lock()
MFA_USED_CODES   = {}   # username -> (code, expires_at) — anti-replay

def _new_mfa_pending(username: str, role: str) -> str:
    token = secrets.token_urlsafe(32)
    now   = time.time()
    with MFA_PENDING_LOCK:
        expired = [t for t, v in MFA_PENDING.items() if v["expires_at"] < now]
        for t in expired:
            del MFA_PENDING[t]
        MFA_PENDING[token] = {"username": username, "role": role, "expires_at": now + 300}
    return token

def _get_mfa_pending(handler):
    for part in handler.headers.get("Cookie", "").split(";"):
        p = part.strip()
        if p.startswith("mfa_pending="):
            token = p[12:]
            with MFA_PENDING_LOCK:
                entry = MFA_PENDING.get(token)
                if entry and entry["expires_at"] > time.time():
                    return {**entry, "token": token}
    return None

def _del_mfa_pending(handler):
    for part in handler.headers.get("Cookie", "").split(";"):
        p = part.strip()
        if p.startswith("mfa_pending="):
            token = p[12:]
            with MFA_PENDING_LOCK:
                MFA_PENDING.pop(token, None)

def _mfa_generate_secret() -> str:
    return pyotp.random_base32()

def _mfa_provisioning_uri(username: str, secret: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="ROSM")

def _mfa_verify_code(secret: str, code: str, username: str) -> bool:
    if not (code and len(code) == 6 and code.isdigit()):
        return False
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        return False
    now  = time.time()
    used = MFA_USED_CODES.get(username)
    if used and used[0] == code and used[1] > now:
        return False
    MFA_USED_CODES[username] = (code, now + 90)
    return True

def _mfa_qr_svg(uri: str) -> str:
    qr  = segno.make(uri, error="M")
    buf = _io.BytesIO()
    qr.save(buf, kind="svg", scale=5, border=2)
    return buf.getvalue().decode("utf-8")

# ─────────────────────────────────────────────────────────────────
# § Companies & sites
# ─────────────────────────────────────────────────────────────────
COMPANIES = {}

# Sites: id → {name, city, description}; device has site_id + parent_ip
SITES: dict = load_json(SITES_FILE, {}) if os.path.exists(SITES_FILE) else {}
SITES_LOCK = threading.Lock()

# ─────────────────────────────────────────────────────────────────────────────
# § ZTP DATA STORE
# ─────────────────────────────────────────────────────────────────────────────

ZTP_TEMPLATES_FILE = os.path.join(BASE_DIR, "ztp_templates.json")
ZTP_DEVICES_FILE   = os.path.join(BASE_DIR, "ztp_devices.json")
ZTP_LOG_FILE       = os.path.join(BASE_DIR, "ztp_log.json")

ZTP_TEMPLATES: dict = {}
ZTP_DEVICES:   dict = {}
ZTP_LOG:       list = []

ZTP_TEMPLATES_LOCK = threading.Lock()
ZTP_DEVICES_LOCK   = threading.Lock()
ZTP_LOG_LOCK       = threading.Lock()

ZTP_LOG_MAX = 500

def _load_ztp():
    global ZTP_TEMPLATES, ZTP_DEVICES, ZTP_LOG
    ZTP_TEMPLATES = load_json(ZTP_TEMPLATES_FILE, {})
    ZTP_DEVICES   = load_json(ZTP_DEVICES_FILE,   {})
    ZTP_LOG       = load_json(ZTP_LOG_FILE,        [])

def _save_ztp_templates():
    save_json_atomic(ZTP_TEMPLATES_FILE, ZTP_TEMPLATES)

def _save_ztp_devices():
    save_json_atomic(ZTP_DEVICES_FILE, ZTP_DEVICES)

def _save_ztp_log():
    save_json_atomic(ZTP_LOG_FILE, ZTP_LOG)

def _mac_normalize(mac: str) -> str:
    digits = re.sub(r"[^0-9a-fA-F]", "", mac)
    if len(digits) != 12:
        return ""
    return ":".join(digits[i:i+2].upper() for i in range(0, 12, 2))

def ztp_template_save(template_id: str, name: str, site_id: str,
                      script: str, extra_vars: dict) -> str:
    tid = template_id or str(uuid.uuid4())[:8]
    with ZTP_TEMPLATES_LOCK:
        existing = ZTP_TEMPLATES.get(tid, {})
        ZTP_TEMPLATES[tid] = {
            "id":         tid,
            "name":       name.strip(),
            "site_id":    site_id,
            "script":     script,
            "extra_vars": extra_vars,
            "created":    existing.get("created", now_str()),
            "updated":    now_str(),
        }
        _save_ztp_templates()
    return tid

def ztp_template_delete(template_id: str) -> bool:
    with ZTP_TEMPLATES_LOCK:
        if template_id not in ZTP_TEMPLATES:
            return False
        del ZTP_TEMPLATES[template_id]
        _save_ztp_templates()
    return True

def ztp_device_register(mac: str, hostname_hint: str, factory_pass: str,
                        site_id: str, cred_id: str, note: str) -> tuple:
    mac_n = _mac_normalize(mac)
    if not mac_n:
        return False, "MAC non valido"
    if not factory_pass:
        return False, "Factory password obbligatoria"
    with ZTP_DEVICES_LOCK:
        ZTP_DEVICES[mac_n] = {
            "mac":               mac_n,
            "hostname_hint":     hostname_hint.strip(),
            "factory_pass_enc":  _encrypt(factory_pass),
            "site_id":           site_id,
            "cred_id":           cred_id,
            "note":              note.strip(),
            "registered_at":     ZTP_DEVICES.get(mac_n, {}).get("registered_at", now_str()),
            "updated_at":        now_str(),
            "applied":           ZTP_DEVICES.get(mac_n, {}).get("applied", False),
            "applied_at":        ZTP_DEVICES.get(mac_n, {}).get("applied_at", ""),
        }
        _save_ztp_devices()
    return True, mac_n

def ztp_device_remove(mac: str) -> bool:
    mac_n = _mac_normalize(mac)
    with ZTP_DEVICES_LOCK:
        if mac_n not in ZTP_DEVICES:
            return False
        del ZTP_DEVICES[mac_n]
        _save_ztp_devices()
    return True

def _ztp_find_device_by_mac(mac: str) -> dict:
    mac_n = _mac_normalize(mac)
    return ZTP_DEVICES.get(mac_n, {})

# ─────────────────────────────────────────────────────────────────────────────
# § ZTP BACKEND
# ─────────────────────────────────────────────────────────────────────────────

_AUTO_VAR_KEYS = {"ip", "mac", "site_name", "site_id", "date", "hostname"}

def _extract_extra_vars(script: str) -> dict:
    out = {}
    for line in script.splitlines():
        m = re.match(r"^\s*#\s*VAR\s*:\s*(\w+)\s*:\s*(.*)", line)
        if m:
            key, default = m.group(1).strip(), m.group(2).strip()
            if key not in _AUTO_VAR_KEYS:
                out[key] = default
    return out

def _render_script(script: str, context: dict) -> str:
    def replacer(m):
        key = m.group(1).strip()
        return context.get(key, m.group(0))
    return re.sub(r"\{\{(\w+)\}\}", replacer, script)

def _build_apply_context(ip: str, mac: str, hostname: str,
                          template: dict, extra_overrides: dict) -> dict:
    site_id   = DEVICES.get(ip, {}).get("site_id", "")
    site_name = SITES.get(site_id, {}).get("name", site_id) if site_id else ""
    ctx: dict = {}
    ctx["ip"]        = ip
    ctx["mac"]       = mac
    ctx["site_id"]   = site_id
    ctx["site_name"] = site_name
    ctx["date"]      = datetime.now().strftime("%Y-%m-%d")
    ctx["hostname"]  = hostname or ip.replace(".", "_")
    ctx.update(template.get("extra_vars", {}))
    ctx.update({k: v for k, v in extra_overrides.items() if v != ""})
    return ctx

def _ztp_apply_worker(job_id: str, ip: str, mac: str, hostname: str,
                       template_id: str, extra_overrides: dict,
                       factory_pass: str, cred_id_after: str):
    result = {"ok": False, "msg": ""}
    try:
        template = ZTP_TEMPLATES.get(template_id)
        if not template:
            raise ValueError(f"Template '{template_id}' non trovato")

        if factory_pass:
            ssh_user = "admin"
            ssh_pass = factory_pass
        elif cred_id_after:
            ssh_user, ssh_pass = _resolve_cred_id(cred_id_after)
        else:
            ssh_user, ssh_pass = _get_device_creds(ip)

        if not ssh_user:
            raise ValueError("Nessuna credenziale disponibile per " + ip)

        ctx    = _build_apply_context(ip, mac, hostname, template, extra_overrides)
        script = _render_script(template["script"], ctx)

        tmp_dir  = os.path.join(BASE_DIR, "uploads")
        os.makedirs(tmp_dir, exist_ok=True)
        fname    = f"ztp_{ip.replace('.','_')}_{job_id[:6]}.rsc"
        tmp_path = os.path.join(tmp_dir, fname)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(script)

        ssh  = _ssh_connect_creds(ip, ssh_user, ssh_pass)
        sftp = ssh.open_sftp()
        sftp.put(tmp_path, fname)
        sftp.close()

        _, stdout, stderr = ssh.exec_command(f"/import file-name={fname}", timeout=60)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        ssh.close()

        msg    = out if out else (err if err else "OK")
        result = {"ok": True, "msg": msg}

        mac_n = _mac_normalize(mac)
        if mac_n and mac_n in ZTP_DEVICES:
            with ZTP_DEVICES_LOCK:
                ZTP_DEVICES[mac_n]["applied"]    = True
                ZTP_DEVICES[mac_n]["applied_at"] = now_str()
                _save_ztp_devices()

        app_log("ztp", "info",
                f"Template '{template['name']}' applicato a {ip} ({hostname})", ip, hostname)

    except Exception as exc:
        result = {"ok": False, "msg": _ssh_err_str(exc)}
        app_log("ztp", "error", f"Errore apply su {ip}: {result['msg']}", ip)

    finally:
        with JOBS_LOCK:
            JOBS[job_id]["results"].append({
                "ip":   ip,
                "name": hostname,
                "ok":   result["ok"],
                "msg":  result["msg"],
            })
            JOBS[job_id]["done"] += 1

        with ZTP_LOG_LOCK:
            tname = ZTP_TEMPLATES.get(template_id, {}).get("name", template_id)
            ZTP_LOG.insert(0, {
                "ts":            now_str(),
                "ip":            ip,
                "hostname":      hostname,
                "template_id":   template_id,
                "template_name": tname,
                "ok":            result["ok"],
                "msg":           result["msg"],
            })
            if len(ZTP_LOG) > ZTP_LOG_MAX:
                ZTP_LOG[:] = ZTP_LOG[:ZTP_LOG_MAX]
            _save_ztp_log()

def ztp_apply(ip: str, mac: str, hostname: str, template_id: str,
              extra_overrides: dict, factory_pass: str = "",
              cred_id_after: str = "") -> str:
    job_id = str(uuid.uuid4())
    with JOBS_LOCK:
        JOBS[job_id] = {"done": 0, "total": 1, "results": []}
    threading.Thread(
        target=_ztp_apply_worker,
        args=(job_id, ip, mac, hostname, template_id, extra_overrides,
              factory_pass, cred_id_after),
        daemon=True,
    ).start()
    return job_id

# ─────────────────────────────────────────────────────────────────────────────
# § SITE AUTO-SCAN
# ─────────────────────────────────────────────────────────────────────────────

_SITE_SCAN_CHECK_SEC = 60
_SITE_SCAN_TIMEOUT   = 600

def site_scan_configure(sid: str, subnet: str, interval_min: int,
                        auto_add: bool) -> tuple:
    if sid not in SITES:
        return False, "Sito non trovato"
    subnet = subnet.strip()
    if subnet:
        try:
            ipaddress.ip_network(subnet, strict=False)
        except ValueError:
            return False, f"Subnet non valida: {subnet}"
    interval_min = max(0, int(interval_min))
    with SITES_LOCK:
        site       = SITES[sid]
        old_subnet = site.get("scan_subnet", "")
        old_itvl   = site.get("scan_interval", 0)
        if subnet != old_subnet or interval_min != old_itvl:
            if interval_min > 0 and subnet:
                next_run = (datetime.now() + _td(minutes=interval_min)
                            ).strftime("%Y-%m-%d %H:%M:%S")
            else:
                next_run = ""
        else:
            next_run = site.get("scan_next_run", "")
        site.update({
            "scan_subnet":   subnet,
            "scan_interval": interval_min,
            "scan_auto_add": bool(auto_add),
            "scan_next_run": next_run,
        })
        save_json_atomic(SITES_FILE, SITES)
    return True, ""

def _launch_site_scan(sid: str, manual: bool = False) -> tuple:
    site    = SITES.get(sid, {})
    subnet  = site.get("scan_subnet", "").strip()
    cred_id = site.get("credential_id", "")
    if not subnet:
        return False, "Nessuna subnet configurata"
    if site.get("scan_status") == "running":
        return False, "Scansione già in corso"
    ssh_user, ssh_pass = ("", "")
    if cred_id:
        ssh_user, ssh_pass = _resolve_cred_id(cred_id)
    ssh_pass_enc = _encrypt(ssh_pass) if ssh_pass else ""
    interval = site.get("scan_interval", 0)
    if not manual and interval > 0:
        next_run = (datetime.now() + _td(minutes=interval)
                    ).strftime("%Y-%m-%d %H:%M:%S")
    else:
        next_run = site.get("scan_next_run", "")
    with SITES_LOCK:
        SITES[sid].update({
            "scan_status":     "running",
            "scan_last_run":   now_str(),
            "scan_next_run":   next_run,
            "scan_job_id":     "",
            "scan_last_error": "",
        })
        save_json_atomic(SITES_FILE, SITES)
    job_id, err = start_scan_job(subnet, ssh_user, ssh_pass_enc, "")
    if err:
        with SITES_LOCK:
            SITES[sid].update({"scan_status": "error", "scan_last_error": err})
            save_json_atomic(SITES_FILE, SITES)
        app_log("site_scan", "error",
                f"Errore avvio scansione '{site.get('name', sid)}': {err}")
        return False, err
    with SITES_LOCK:
        SITES[sid]["scan_job_id"] = job_id
        save_json_atomic(SITES_FILE, SITES)
    threading.Thread(target=_site_scan_worker, args=(sid, job_id),
                     daemon=True).start()
    return True, job_id

def _site_scan_worker(sid: str, job_id: str):
    deadline = time.time() + _SITE_SCAN_TIMEOUT
    while time.time() < deadline:
        time.sleep(3)
        with SCAN_JOBS_LOCK:
            status = SCAN_JOBS.get(job_id, {}).get("status", "")
        if status == "done":
            break
    else:
        with SITES_LOCK:
            SITES[sid].update({
                "scan_status":     "error",
                "scan_last_error": "Timeout scansione",
            })
            save_json_atomic(SITES_FILE, SITES)
        return
    with SCAN_JOBS_LOCK:
        results = list(SCAN_JOBS.get(job_id, {}).get("results", []))
    found    = [r for r in results if r.get("device_type") == "routeros" or r.get("ssh_ok")]
    auto_add = SITES.get(sid, {}).get("scan_auto_add", False)
    added    = 0
    if auto_add:
        for r in found:
            ip = r.get("ip", "")
            if ip and ip not in DEVICES:
                if device_add(ip):
                    device_update(ip, site_id=sid)
                    added += 1
    site_name = SITES.get(sid, {}).get("name", sid)
    app_log("site_scan", "info",
            f"Scansione '{site_name}' OK — {len(found)} MikroTik, {added} aggiunti")
    with SITES_LOCK:
        SITES[sid].update({
            "scan_status":      "done",
            "scan_last_found":  len(found),
            "scan_last_added":  added,
            "scan_last_error":  "",
        })
        save_json_atomic(SITES_FILE, SITES)

def _site_scan_tick():
    now = datetime.now()
    for sid, site in list(SITES.items()):
        if site.get("scan_status") == "running":
            continue
        interval = site.get("scan_interval", 0)
        subnet   = site.get("scan_subnet", "")
        if not interval or not subnet:
            continue
        next_str = site.get("scan_next_run", "")
        if not next_str:
            _launch_site_scan(sid)
            continue
        try:
            if now >= datetime.strptime(next_str, "%Y-%m-%d %H:%M:%S"):
                _launch_site_scan(sid)
        except ValueError:
            pass

def _site_scan_monitor():
    while True:
        try:
            _site_scan_tick()
        except Exception as exc:
            app_log("site_scan", "error", f"Monitor: {exc}")
        time.sleep(_SITE_SCAN_CHECK_SEC)

# ─────────────────────────────────────────────────────────────────────────────

def _save_sites():
    save_json_atomic(SITES_FILE, SITES)

def site_add(name, city="", description=""):
    sid = "s_" + str(int(time.time() * 1000))
    with SITES_LOCK:
        SITES[sid] = {"id": sid, "name": name, "city": city, "description": description, "credential_id": ""}
        _save_sites()
    return sid

def site_update(sid, **kwargs):
    with SITES_LOCK:
        if sid in SITES:
            SITES[sid].update(kwargs)
            _save_sites()

def site_remove(sid):
    with SITES_LOCK:
        SITES.pop(sid, None)
        _save_sites()
    # Unassign devices that belonged to this site (persistent store)
    with DEVICES_LOCK:
        for dev in DEVICES.values():
            if dev.get("site_id") == sid:
                dev["site_id"] = ""
        save_json_atomic(DEVICES_FILE, DEVICES)
    # Also update in-memory ROUTERS list so the change is immediately visible
    for r in ROUTERS:
        if r.get("site_id") == sid:
            r["site_id"] = ""

# Background jobs: job_id → {done, total, results:[{ip,name,ok,msg}]}
JOBS      = {}
JOBS_LOCK = threading.Lock()

# ─────────────────────────────────────────────────────────────────
# § Runtime state & locks
# ─────────────────────────────────────────────────────────────────
STATE_LOCK = threading.Lock()

PING_RUNNING = False
SSH_ACTIVE   = 0

PING_HISTORY_FILE = os.path.join(BASE_DIR, "ping_history.json")
_PING_HISTORY_DAYS_OPTIONS = [1, 3, 7, 14, 30, 90]  # days

def _ping_history_maxlen() -> int:
    """Return max entries based on configured days and current ping interval."""
    days = _app_cfg.get("ping_history_days", 7)
    if days not in _PING_HISTORY_DAYS_OPTIONS:
        days = 7
    try:
        interval = max(10, AUTO_INTERVAL)
    except NameError:
        interval = 30   # AUTO_INTERVAL not yet defined at startup
    return max(100, min(100000, int(days * 86400 / interval)))

PING_HISTORY: deque = deque(maxlen=_ping_history_maxlen())

# Detected changes during ping (MAC mismatch, etc.) — shown as notifications in the UI
CHANGE_LOG: deque = deque(maxlen=200)

# Unified application log — all processes write here for the /report page
APP_LOG_FILE = os.path.join(BASE_DIR, "app_log.json")
APP_LOG: deque = deque(maxlen=_app_cfg.get("app_log_maxlen", 2000))

def app_log(category: str, level: str, msg: str, ip: str = "", name: str = ""):
    """Append an entry to the unified application log.
    category: ping | ssh | backup | script | security | system | error
    level:    info | warn | error
    """
    APP_LOG.append({
        "ts":       now_str(),
        "category": category,
        "level":    level,
        "ip":       ip,
        "name":     name,
        "msg":      msg,
    })

def _load_app_log():
    global APP_LOG
    _max = _app_cfg.get("app_log_maxlen", 2000)
    APP_LOG = deque(maxlen=_max)
    try:
        if os.path.exists(APP_LOG_FILE):
            with open(APP_LOG_FILE) as f:
                data = json.load(f)
            APP_LOG.extend(data[-_max:])
    except Exception:
        pass

def _save_app_log():
    try:
        save_json_atomic(APP_LOG_FILE, list(APP_LOG))
    except Exception:
        pass

def _resize_app_log(new_max: int):
    """Rebuild APP_LOG deque with a new maxlen, preserving the most recent entries."""
    global APP_LOG
    APP_LOG = deque(list(APP_LOG)[-new_max:], maxlen=new_max)
    _save_app_log()

_load_app_log()

def _load_ping_history():
    global PING_HISTORY
    ml = _ping_history_maxlen()
    PING_HISTORY = deque(maxlen=ml)
    try:
        if os.path.exists(PING_HISTORY_FILE):
            with open(PING_HISTORY_FILE) as f:
                data = json.load(f)
            PING_HISTORY.extend(data[-ml:])
    except Exception:
        pass

def _save_ping_history():
    try:
        save_json_atomic(PING_HISTORY_FILE, list(PING_HISTORY))
    except Exception:
        pass

_load_ping_history()

# ─────────────────────────────────────────────────────────────────
# § Port scanning
# ─────────────────────────────────────────────────────────────────
SCAN_PORTS   = [22, 80, 443, 8080, 8291, 8728, 8729, 8443]
PORT_LABELS  = {22: "SSH", 80: "HTTP", 443: "HTTPS", 8080: "HTTP-alt",
                8291: "Winbox", 8728: "API", 8729: "API-SSL", 8443: "HTTPS-alt"}
PORT_CACHE: dict = {}   # {ip: [port, ...]}  — in-memory, also saved in state
PORT_CACHE_LOCK = threading.Lock()

AUTO_ENABLED  = True
AUTO_INTERVAL = 30   # seconds (default, user-configurable)
RTM_THREAD: threading.Thread = None  # Real-Time Monitoring thread (1 ping/sec)

def _save_state_file():
    """Write STATE to STATE_FILE, encrypting if encrypt_devices is enabled."""
    content = json.dumps(STATE, indent=2, ensure_ascii=False)
    if _app_cfg.get("encrypt_devices") and _FERNET_AVAILABLE:
        content = _encrypt_file_content(content)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(content)
    os.replace(tmp, STATE_FILE)

def _load_state_file() -> dict:
    """Load STATE from STATE_FILE, decrypting if necessary."""
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
        raw = _decrypt_file_content(raw)
        return json.loads(raw)
    except Exception:
        return {}

STATE       = _load_state_file()
UPLOADS_LOG = load_json(UPLOADS_LOG_FILE, {})
RUNS_LOG    = load_json(RUNS_LOG_FILE,    [])
CUSTOM_COLS: list = load_json(CUSTOM_COLS_FILE, [])  # [{id, name, cmd}]
CUSTOM_COL_DATA: dict = {}  # {ip: {col_id: value}}
CUSTOM_COLS_LOCK = threading.Lock()

# Load devices (migrates from routers.txt on first run)
_load_devices()

# ─────────────────────────────────────────────────────────────────
# § Routers list builder  (DEVICES + STATE → ROUTERS)
# ─────────────────────────────────────────────────────────────────
def _sort_ip(r):
    try:
        return tuple(int(x) for x in r["ip"].split("."))
    except Exception:
        return (0,)

def _build_routers():
    routers = []
    for ip, dev in DEVICES.items():
        saved = STATE.get(ip, {})
        routers.append({
            "ip":          ip,
            "tags":        dev.get("tags", []),
            "group":       dev.get("group", ""),
            "site_id":           dev.get("site_id", ""),
            "parent_ip":         dev.get("parent_ip", ""),
            "device_role":       dev.get("device_role", ""),
            "device_role_label": dev.get("device_role_label", ""),
            "link_type":         dev.get("link_type", ""),
            "mac":         dev.get("mac") or saved.get("mac", ""),

            "status":      saved.get("status", ""),
            "last_ping":   saved.get("last_ping", ""),
            "last_online": saved.get("last_online", ""),

            "name":             saved.get("name", ""),
            "version":          saved.get("version", ""),
            "model":            saved.get("model", ""),
            "uptime":           saved.get("uptime", ""),
            "last_name_update": saved.get("last_name_update", ""),
            "packages":         saved.get("packages", ""),
            "note_full":        saved.get("note_full", ""),

            "script":             saved.get("script", ""),
            "script_uploaded_at": saved.get("script_uploaded_at", ""),
            "last_run_result":    saved.get("last_run_result", ""),
            "last_run_ok":        saved.get("last_run_ok", None),
            "last_run_at":        saved.get("last_run_at", ""),

            "open_ports": saved.get("open_ports", []),

            "ssh_status": "IDLE",
            "ssh_error":  "",
            "run_status": "IDLE",
        })
    routers.sort(key=_sort_ip)
    return routers

ROUTERS = _build_routers()

def extract_version(text: str) -> str:
    m = re.search(r"[Vv]\d+(\.\d+)+", text or "")
    return m.group(0) if m else ""

def is_data_missing(r):
    return not all([r["name"], r["model"], r["version"], r["uptime"], r["packages"]])

def _render_ports_html(ports):
    """Render open ports as small colored badges."""
    if not ports:
        return '<span style="color:var(--text3);font-size:10px;">—</span>'
    # Color coding per port category
    def _port_color(p):
        if p == 8291: return ("#1b3a6b", "Winbox")   # navy — MikroTik-specific
        if p in (8728, 8729): return ("#7c3aed", PORT_LABELS.get(p, str(p)))  # purple — API
        if p == 22:  return ("#16a34a", "SSH")        # green
        if p in (80, 8080): return ("#d97706", PORT_LABELS.get(p, str(p)))    # yellow
        if p in (443, 8443): return ("#2650a0", PORT_LABELS.get(p, str(p)))   # blue
        return ("#8896ab", str(p))
    badges = []
    for p in sorted(ports):
        col, label = _port_color(p)
        badges.append(
            f'<span title=":{p}" style="display:inline-block;padding:1px 5px;border-radius:3px;'
            f'background:{col}18;color:{col};border:1px solid {col}44;'
            f'font-size:9px;font-weight:700;font-family:var(--mono);white-space:nowrap;">'
            f'{label}</span>'
        )
    return '<span style="display:flex;flex-wrap:wrap;gap:2px;">' + "".join(badges) + "</span>"

def state_merge(ip, **kwargs):
    with STATE_LOCK:
        cur = STATE.get(ip, {})
        cur.update(kwargs)
        STATE[ip] = cur
        _save_state_file()

def uploads_log_append(filename, ip, name):
    entry = {"when": now_str(), "ip": ip, "name": name or ""}
    with STATE_LOCK:
        UPLOADS_LOG.setdefault(filename, []).append(entry)
        save_json_atomic(UPLOADS_LOG_FILE, UPLOADS_LOG)

def runs_log_append(ip, name, script, result, ok):
    entry = {"when": now_str(), "ip": ip, "name": name or "", "script": script, "result": result, "ok": ok}
    with STATE_LOCK:
        RUNS_LOG.append(entry)
        # keep last 2000 entries
        while len(RUNS_LOG) > 2000:
            RUNS_LOG.pop(0)
        save_json_atomic(RUNS_LOG_FILE, RUNS_LOG)
    lvl = "info" if ok else "error"
    snippet = (result or "")[:80].replace("\n", " ")
    app_log("script", lvl,
            f"{'OK' if ok else 'FAIL'} — {script}: {snippet}", ip, name or "")

# ─────────────────────────────────────────────────────────────────
# § SSH helpers
# ─────────────────────────────────────────────────────────────────
def _ssh_err_str(exc: Exception) -> str:
    """Convert any SSH/network exception to a human-readable message (language-aware)."""
    en   = (LANGUAGE == "en")
    name = type(exc).__name__
    msg  = str(exc)
    ml   = msg.lower()
    # Authentication
    if "Authentication" in name or "AuthenticationException" in name:
        return ("Wrong SSH credentials (authentication failed)"
                if en else "Credenziali SSH errate (autenticazione fallita)")
    # Wrong username / key
    if "invalid username" in ml or "invalid user" in ml:
        return "Invalid SSH username" if en else "Nome utente SSH non valido"
    # Connection refused / port closed
    if "NoValidConnections" in name or isinstance(exc, ConnectionRefusedError):
        return ("SSH not active — connection refused on port 22"
                if en else "SSH non attivo — connessione rifiutata sulla porta 22")
    # Timeout
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return ("Timeout — host unreachable or too slow"
                if en else "Timeout — host non raggiungibile o troppo lento")
    # DNS / hostname not found
    if isinstance(exc, socket.gaierror):
        return (f"Host not found — check the IP address ({msg[:80]})"
                if en else f"Host non risolvibile — controlla l'indirizzo IP ({msg[:80]})")
    # Connection reset / dropped
    if isinstance(exc, ConnectionResetError) or "connection reset" in ml:
        return ("Connection dropped by router during SSH handshake"
                if en else "Connessione interrotta dal router durante l'handshake SSH")
    # SSH banner missing — port open but not SSH
    if "banner" in ml:
        return ("Port 22 reachable but no SSH service responded (missing banner)"
                if en else "Porta 22 raggiungibile ma nessun servizio SSH risponde (banner SSH assente)")
    # Key exchange / algorithm mismatch
    if "key exchange" in ml or "kex" in ml or "algorithm" in ml:
        return ("SSH negotiation failed — incompatible algorithms"
                if en else "Negoziazione SSH fallita — algoritmi SSH incompatibili")
    # Host key mismatch
    if "BadHostKey" in name or "host key" in ml:
        return ("SSH host key mismatch — possible MITM or router replaced"
                if en else "Chiave host SSH diversa da quella attesa — possibile MITM o router cambiato")
    # Channel / execution error
    if "Channel" in name:
        return (f"SSH channel error: {msg[:120]}"
                if en else f"Errore canale SSH: {msg[:120]}")
    # OSError / network-level
    if isinstance(exc, OSError):
        return (f"Network error: {msg[:120]}"
                if en else f"Errore di rete: {msg[:120]}")
    # Generic SSHException with readable message
    if "SSHException" in name or "ssh" in name.lower():
        return (f"SSH error: {msg[:120]}"
                if en else f"Errore SSH: {msg[:120]}")
    # Fallback
    return f"{name}: {msg[:120]}"

def _ssh_connect(ip):
    """Connect for READ — uses per-device credentials."""
    user, passwd = _get_device_creds(ip)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username=user, password=passwd, timeout=SSH_TIMEOUT,
                look_for_keys=False, allow_agent=False,
                banner_timeout=SSH_TIMEOUT + 2, auth_timeout=SSH_TIMEOUT + 2)
    return ssh

def _ssh_connect_creds(ip, username, password):
    """Connect with explicit credentials — used for WRITE operations (upload/run)."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        ip,
        username=username,
        password=password,
        timeout=SSH_TIMEOUT,
        look_for_keys=False,
        allow_agent=False,
        banner_timeout=SSH_TIMEOUT + 2,
        auth_timeout=SSH_TIMEOUT + 2,
    )
    return ssh

def _read_ssh_channel(channel, timeout: float = 20.0) -> str:
    """Read from a Paramiko channel with a hard wall-clock deadline.

    Uses select() on POSIX; falls back to polling on Windows because
    select.select() requires valid file descriptors which paramiko channels
    do not provide on Windows (socket.socketpair() unavailable before Py 3.12).
    """
    deadline = time.monotonic() + timeout
    buf = bytearray()
    if _IS_WINDOWS:
        while True:
            if time.monotonic() >= deadline:
                break
            if channel.recv_ready():
                chunk = channel.recv(4096)
                if not chunk:
                    break
                buf.extend(chunk)
                continue
            if channel.exit_status_ready():
                # Retry recv_ready several times: the last packet can arrive
                # slightly after exit_status on Windows due to TCP buffering.
                for _ in range(8):
                    if channel.recv_ready():
                        chunk = channel.recv(4096)
                        if not chunk:
                            break
                        buf.extend(chunk)
                    else:
                        time.sleep(0.025)
                break
            time.sleep(0.05)
    else:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            ready, _, _ = _select.select([channel], [], [], min(remaining, 0.5))
            if ready:
                if channel.recv_ready():
                    chunk = channel.recv(4096)
                    if not chunk:
                        break
                    buf.extend(chunk)
                if channel.exit_status_ready() and not channel.recv_ready():
                    break
            else:
                if channel.exit_status_ready():
                    while channel.recv_ready():
                        chunk = channel.recv(4096)
                        if not chunk:
                            break
                        buf.extend(chunk)
                    break
    return buf.decode(errors="ignore")

def _exec(ssh, cmd):
    try:
        _, stdout, _ = ssh.exec_command(cmd, timeout=SSH_TIMEOUT)
        return stdout.read().decode(errors="ignore").strip()
    except Exception:
        return ""

def refresh_router(r):
    global SSH_ACTIVE
    if r["ssh_status"] == "WORKING":
        return

    r["ssh_status"] = "WORKING"
    state_merge(r["ip"], ssh_status="WORKING")

    with STATE_LOCK:
        SSH_ACTIVE += 1

    _ssh_err_msg = ""
    try:
        app_log("ssh", "info", "Connessione SSH avviata", r["ip"], r.get("name", ""))
        ssh = _ssh_connect(r["ip"])

        name    = _exec(ssh, ":put [/system identity get name]")
        note    = _exec(ssh, ":put [/system note get note]")
        # Prefer /system routerboard get model (exact product name as on mikrotik.com)
        # Fallback to board-name for CHR / devices without routerboard
        model   = (_exec(ssh, ":put [/system routerboard get model]")
                   or _exec(ssh, ":put [/system resource get board-name]"))
        uptime  = _exec(ssh, ":put [/system resource get uptime]")

        # Fetch ROS version directly from system resource
        ros_ver_raw = _exec(ssh, ":put [/system resource get version]")
        ros_version = ros_ver_raw.split(" ")[0].strip() if ros_ver_raw else ""

        # MAC address from ether1
        mac = _exec(ssh, ":put [/interface ethernet get ether1 mac-address]")

        if name:
            r["name"]             = name
            r["version"]          = extract_version(note)
            r["note_full"]        = note or ""
            r["model"]            = model
            r["uptime"]           = uptime
            r["packages"]         = ros_version
            r["last_name_update"] = now_str()
            if mac:
                r["mac"] = mac
                device_update(r["ip"], mac=mac)
            state_merge(r["ip"],
                name=r["name"], version=r["version"], note_full=r["note_full"],
                model=r["model"], uptime=r["uptime"], packages=r["packages"],
                mac=mac, last_name_update=r["last_name_update"])
            app_log("ssh", "info",
                    f"Dati aggiornati — modello: {model or '—'}, ROS: {ros_version or '—'}, uptime: {uptime or '—'}",
                    r["ip"], name)

        ssh.close()
    except Exception as _ssh_exc:
        import traceback as _tb
        _full = _tb.format_exc()
        _ssh_err_msg = _ssh_err_str(_ssh_exc)
        app_log("ssh", "error", f"Errore SSH: {type(_ssh_exc).__name__}: {str(_ssh_exc)[:200]}", r["ip"], r.get("name", ""))
        if _IS_WINDOWS:
            try:
                _log_path = os.path.join(BASE_DIR, "rosm.log")
                with open(_log_path, "a", encoding="utf-8") as _lf:
                    _lf.write(f"\n[SSH ERROR {r['ip']}]\n{_full}\n")
            except Exception:
                pass

    if _ssh_err_msg:
        r["ssh_status"] = "ERROR"
        r["ssh_error"]  = _ssh_err_msg
        state_merge(r["ip"], ssh_status="ERROR", ssh_error=_ssh_err_msg)
    else:
        r["ssh_status"] = "IDLE"
        r["ssh_error"]  = ""
        state_merge(r["ip"], ssh_status="IDLE", ssh_error="")
    _save_app_log()

    with STATE_LOCK:
        SSH_ACTIVE -= 1

def refresh_all():
    for r in ROUTERS:
        if r["ssh_status"] in ("IDLE", "ERROR"):
            r["ssh_status"] = "PENDING"
            state_merge(r["ip"], ssh_status="PENDING")
    for r in ROUTERS:
        if r["ssh_status"] == "PENDING":
            threading.Thread(target=refresh_router, args=(r,), daemon=True).start()

# ─────────────────────────────────────────────────────────────────
# § Custom SSH columns
# ─────────────────────────────────────────────────────────────────
def fetch_custom_col(col_id, cmd, ips=None):
    """SSH to online routers and populate CUSTOM_COL_DATA[ip][col_id]."""
    targets = [r for r in ROUTERS if r["status"] == "ONLINE" and (ips is None or r["ip"] in ips)]
    def _do(r):
        try:
            ssh = _ssh_connect(r["ip"])
            val = _exec(ssh, cmd)
            ssh.close()
        except Exception:
            val = ""
        with CUSTOM_COLS_LOCK:
            CUSTOM_COL_DATA.setdefault(r["ip"], {})[col_id] = val or ""
    threads = [threading.Thread(target=_do, args=(r,), daemon=True) for r in targets]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

# ─────────────────────────────────────────────────────────────────
# § Backup manager
# ─────────────────────────────────────────────────────────────────
_BACKUP_CONFIG_DEFAULTS = {"enabled": False, "interval_hours": 24, "retention_days": 30,
                            "last_run": "", "next_run_ts": 0,
                            "show_sensitive": True, "keep_on_router": False}
BACKUP_CONFIG: dict = {**_BACKUP_CONFIG_DEFAULTS, **load_json(BACKUP_CONFIG_FILE, {})}

# ─────────────────────────────────────────────────────────────────
# § Credential sets
# ─────────────────────────────────────────────────────────────────
CRED_SETS: list = load_json(CRED_SETS_FILE, [])  # [{id, name, username_enc, password_enc}]
CRED_SETS_LOCK = threading.Lock()
# Migrate on load: encrypt any plaintext username fields from old format

def _save_cred_sets():
    save_json_atomic(CRED_SETS_FILE, CRED_SETS)

def _migrate_cred_sets_encrypt():
    """Encrypt any plaintext 'username' fields left in cred_sets.json (one-time migration)."""
    changed = False
    for cs in CRED_SETS:
        if "username" in cs and "username_enc" not in cs:
            cs["username_enc"] = _encrypt(cs.pop("username"))
            changed = True
    if changed:
        _save_cred_sets()

_migrate_cred_sets_encrypt()

def cred_set_add(name, username, password):
    cid = "cs_" + str(int(time.time() * 1000))
    entry = {
        "id": cid, "name": name,
        "username_enc": _encrypt(username),
        "password_enc": _encrypt(password),
    }
    with CRED_SETS_LOCK:
        CRED_SETS.append(entry)
        _save_cred_sets()
    return cid

def cred_set_update(cid, name=None, username=None, password=None):
    with CRED_SETS_LOCK:
        for cs in CRED_SETS:
            if cs["id"] == cid:
                if name     is not None: cs["name"]         = name
                if username is not None:
                    cs["username_enc"] = _encrypt(username)
                    cs.pop("username", None)   # remove old plaintext field if present
                if password is not None: cs["password_enc"]  = _encrypt(password)
                break
        _save_cred_sets()

def cred_set_remove(cid):
    with CRED_SETS_LOCK:
        CRED_SETS[:] = [c for c in CRED_SETS if c["id"] != cid]
        _save_cred_sets()
    # Unassign from sites
    with SITES_LOCK:
        for site in SITES.values():
            if site.get("credential_id") == cid:
                site["credential_id"] = ""
        _save_sites()

def _cred_set_username(cs: dict) -> str:
    """Decrypt the username from a credential set entry (supports old plaintext and new encrypted)."""
    if "username_enc" in cs:
        return _decrypt(cs["username_enc"])
    return cs.get("username", "")   # legacy plaintext fallback

def _resolve_cred_id(cred_id):
    """Return (username, password) for a named credential set, or ('','') if not found."""
    if not cred_id:
        return "", ""
    cs = next((c for c in CRED_SETS if c["id"] == cred_id), None)
    if not cs:
        return "", ""
    return _cred_set_username(cs), _decrypt(cs.get("password_enc", ""))

def _get_creds_for_site(site_id):
    """Return (user, pass) from the credential set assigned to a site, or ('','')."""
    site = SITES.get(site_id, {})
    cid  = site.get("credential_id", "")
    if not cid:
        return "", ""
    cs = next((c for c in CRED_SETS if c["id"] == cid), None)
    if not cs:
        return "", ""
    return _cred_set_username(cs), _decrypt(cs.get("password_enc", ""))
BACKUP_RUNNING  = False
BACKUP_LOCK     = threading.Lock()
BACKUP_LAST_RESULTS: list = []   # [{ip, name, file, size, ok, msg, ts}]

def _save_backup_config():
    save_json_atomic(BACKUP_CONFIG_FILE, BACKUP_CONFIG)

def _backup_filename(router_name, ip, show_sensitive=False):
    """RouterName_YYYYMMDD-HHmm[_S].rsc  (safe for filesystems)"""
    safe = re.sub(r'[^\w\-]', '_', router_name or ip.replace(".", "_"))
    ts   = datetime.now().strftime("%Y%m%d-%H%M")
    sens = "_S" if show_sensitive else ""
    return f"{safe}_{ts}{sens}.rsc"

def backup_router(r, ssh_user=None, ssh_pass=None, show_sensitive=True, keep_on_router=False):
    """SSH to one router, run /export [show-sensitive], save .rsc file.
    Credential priority: explicit override (user+pass) → site credential set → per-router creds → global default."""
    ip = r["ip"]
    try:
        # Resolve credentials: site lookup only when no complete override is provided
        if not (ssh_user and ssh_pass):
            site_id = r.get("site_id", "")
            if site_id:
                u, p = _get_creds_for_site(site_id)
                if u and p:
                    ssh_user, ssh_pass = u, p
        if ssh_user and ssh_pass:
            ssh = _ssh_connect_creds(ip, ssh_user, ssh_pass)
        else:
            ssh = _ssh_connect(ip)  # falls back to per-router or global default
        export_cmd = "/export show-sensitive" if show_sensitive else "/export"
        _, _out, _ = ssh.exec_command(export_cmd)
        _out.channel.settimeout(90)
        try:
            output = _out.read().decode(errors="ignore")
        except socket.timeout:
            output = ""
        # While SSH is still open, refresh the router name and optionally save on router
        live_name = _exec(ssh, ":put [/system identity get name]")
        if keep_on_router:
            _rname = re.sub(r'[^\w\-]', '_', live_name or r.get("name","") or ip.replace(".", "_"))
            _ts_r  = datetime.now().strftime("%Y%m%d-%H%M")
            _keep_cmd = f"/export file={_rname}_{_ts_r}"
            try:
                _, _ko, _ = ssh.exec_command(_keep_cmd)
                _ko.channel.settimeout(30)
                _ko.read()
            except Exception:
                pass
        ssh.close()
        if not output or len(output) < 10:
            app_log("backup", "error", "Output vuoto o troppo corto", ip, r.get("name",""))
            return {"ip": ip, "name": r.get("name",""), "ok": False,
                    "msg": "Output vuoto o troppo corto", "file": "", "size": 0,
                    "ts": now_str()}
        # Update name before building filename so file and dashboard stay in sync
        if live_name and live_name != r.get("name",""):
            r["name"] = live_name
            state_merge(r["ip"], name=live_name)
        fname = _backup_filename(live_name or r.get("name",""), ip, show_sensitive)
        enc   = _app_cfg.get("encrypt_backups") and _FERNET_AVAILABLE
        if enc:
            fname += ".enc"
        fpath = os.path.join(BACKUP_DIR, fname)
        write_content = _encrypt_file_content(output) if enc else output
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(write_content)
        app_log("backup", "info",
                f"Backup salvato: {fname} ({len(output):,} bytes){' [cifrato]' if enc else ''}", ip, r.get("name", ip))
        return {"ip": ip, "name": r.get("name", ip), "ok": True,
                "msg": f"{len(output):,} bytes salvati", "file": fname,
                "size": len(output), "ts": now_str()}
    except Exception as e:
        _emsg = _ssh_err_str(e)
        app_log("backup", "error", f"Errore backup: {_emsg}", ip, r.get("name",""))
        return {"ip": ip, "name": r.get("name",""), "ok": False,
                "msg": _emsg, "file": "", "size": 0, "ts": now_str()}

def backup_apply_retention():
    """Remove .rsc / .rsc.enc files older than retention_days."""
    days = BACKUP_CONFIG.get("retention_days", 30)
    if days <= 0:
        return 0
    cutoff  = time.time() - days * 86400
    removed = 0
    for fname in os.listdir(BACKUP_DIR):
        if not (fname.endswith(".rsc") or fname.endswith(".rsc.enc")):
            continue
        fpath = os.path.join(BACKUP_DIR, fname)
        try:
            if os.path.getmtime(fpath) < cutoff:
                os.remove(fpath)
                removed += 1
        except Exception:
            pass
    return removed

def backup_all(ips=None, ssh_user=None, ssh_pass=None, show_sensitive=None, keep_on_router=None):
    """Run backup on all ONLINE routers (or a subset by IP list)."""
    global BACKUP_RUNNING, BACKUP_LAST_RESULTS
    # Fall back to stored config values when not specified (automatic scheduler path)
    if show_sensitive  is None: show_sensitive  = BACKUP_CONFIG.get("show_sensitive",  True)
    if keep_on_router  is None: keep_on_router  = BACKUP_CONFIG.get("keep_on_router",  False)
    with BACKUP_LOCK:
        if BACKUP_RUNNING:
            return
        BACKUP_RUNNING = True
    try:
        targets = [r for r in ROUTERS
                   if r.get("status") == "ONLINE"
                   and (ips is None or r["ip"] in ips)]
        app_log("backup", "info", f"Backup avviato — {len(targets)} router target")
        results    = []
        res_lock   = threading.Lock()
        def _do(r):
            res = backup_router(r, ssh_user, ssh_pass, show_sensitive, keep_on_router)
            with res_lock:
                results.append(res)
        threads = [threading.Thread(target=_do, args=(r,), daemon=True) for r in targets]
        for t in threads: t.start()
        for t in threads: t.join(timeout=90)
        BACKUP_LAST_RESULTS = results
        ok_count  = sum(1 for res in results if res.get("ok"))
        err_count = len(results) - ok_count
        app_log("backup", "info" if err_count == 0 else "warn",
                f"Backup completato — {ok_count} OK, {err_count} errori su {len(targets)}")
        BACKUP_CONFIG["last_run"] = now_str()
        interval_h = BACKUP_CONFIG.get("interval_hours", 24)
        BACKUP_CONFIG["next_run_ts"] = time.time() + interval_h * 3600
        _save_backup_config()
        backup_apply_retention()
        _save_app_log()
    finally:
        BACKUP_RUNNING = False

def backup_monitor():
    """Background thread: runs backup_all() on schedule."""
    while True:
        try:
            time.sleep(60)   # check every minute
            if not BACKUP_CONFIG.get("enabled", False):
                continue
            next_ts = BACKUP_CONFIG.get("next_run_ts", 0)
            now = time.time()
            if now >= next_ts:
                if BACKUP_RUNNING:
                    app_log("backup", "warn",
                            "Scheduler: backup in corso (avviato manualmente) — salto il ciclo automatico")
                    continue
                online_count = sum(1 for r in ROUTERS if r.get("status") == "ONLINE")
                app_log("backup", "info",
                        f"Scheduler: avvio ciclo automatico — {online_count} router ONLINE")
                backup_all()
        except Exception as e:
            app_log("backup", "error", f"Scheduler: errore non catturato — {e}")
            print(f"[backup_monitor] errore non catturato: {e}")

def backup_index_by_router():
    """Return {key: latest_mtime_ts} from files in BACKUP_DIR.
    Keys include both the filename safe_name AND the normalized IP (for files created before
    the router had a name, e.g. '192_168_1_1_...' → also indexed as '192.168.1.1')."""
    idx = {}
    for fname in os.listdir(BACKUP_DIR):
        m = re.match(r'^(.+)_(\d{8}-\d{4})(?:_S)?\.rsc(?:\.enc)?$', fname)
        if not m:
            continue
        safe_name = m.group(1)
        fpath = os.path.join(BACKUP_DIR, fname)
        try:
            mtime = os.path.getmtime(fpath)
        except Exception:
            continue
        if safe_name not in idx or mtime > idx[safe_name]:
            idx[safe_name] = mtime
        # Also index by normalized IP if the prefix looks like an IPv4 address
        ip_m = re.match(r'^(\d{1,3})_(\d{1,3})_(\d{1,3})_(\d{1,3})$', safe_name)
        if ip_m:
            ip_key = '.'.join(ip_m.groups())
            if ip_key not in idx or mtime > idx[ip_key]:
                idx[ip_key] = mtime
    return idx

def router_safe_name(r):
    """Same logic as _backup_filename to generate the safe prefix for a router."""
    return re.sub(r'[^\w\-]', '_', r.get("name","") or r["ip"].replace(".", "_"))

def router_has_backup(r, bk_idx):
    """True if bk_idx contains a backup for this router — checks by safe name OR by IP."""
    return router_safe_name(r) in bk_idx or r["ip"] in bk_idx

def backup_list_files():
    """Return list of dicts for all .rsc files in BACKUP_DIR, sorted newest first."""
    files = []
    for fname in os.listdir(BACKUP_DIR):
        if not fname.endswith(".rsc"):
            continue
        fpath = os.path.join(BACKUP_DIR, fname)
        try:
            stat  = os.stat(fpath)
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            files.append({"file": fname, "size": stat.st_size, "mtime": mtime,
                           "mtime_ts": stat.st_mtime})
        except Exception:
            pass
    files.sort(key=lambda x: x["mtime_ts"], reverse=True)
    return files

# ─────────────────────────────────────────────────────────────────
# § SSH script runner
# ─────────────────────────────────────────────────────────────────
def run_script_on_router(r):
    """Upload the script via SFTP and execute it via SSH."""
    if r["run_status"] == "RUNNING":
        return
    if not r["script"] or not os.path.exists(r["script"]):
        return

    r["run_status"] = "RUNNING"
    state_merge(r["ip"], run_status="RUNNING")

    ok     = False
    result = ""
    try:
        ssh = _ssh_connect(r["ip"])

        # SFTP: upload script to /tmp/
        remote_path = "/tmp/" + os.path.basename(r["script"])
        sftp = ssh.open_sftp()
        sftp.put(r["script"], remote_path)
        sftp.close()

        # Execute
        _, stdout, stderr = ssh.exec_command(f":import {remote_path}", timeout=30)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        result = out if out else (err if err else "OK")
        ok = True

        ssh.close()
    except Exception as e:
        result = _ssh_err_str(e)
        ok = False

    r["last_run_result"] = result[:300]
    r["last_run_ok"]     = ok
    r["last_run_at"]     = now_str()
    r["run_status"]      = "IDLE"
    state_merge(r["ip"],
        last_run_result=r["last_run_result"],
        last_run_ok=r["last_run_ok"],
        last_run_at=r["last_run_at"],
        run_status="IDLE")

    runs_log_append(r["ip"], r["name"], os.path.basename(r["script"]), result[:300], ok)

def run_all_scripts():
    for r in ROUTERS:
        if r["status"] == "ONLINE" and r["script"] and r["run_status"] == "IDLE":
            threading.Thread(target=run_script_on_router, args=(r,), daemon=True).start()

def ensure_data(r):
    if r["status"] == "ONLINE" and is_data_missing(r) and r["ssh_status"] == "IDLE":
        threading.Thread(target=refresh_router, args=(r,), daemon=True).start()

# ─────────────────────────────────────────────────────────────────
# § Ping & port scan engine
# ─────────────────────────────────────────────────────────────────
def _scan_ports(r):
    """Quick TCP connect scan on SCAN_PORTS. Updates r['open_ports'] and state."""
    ip = r["ip"]
    found = []
    for port in SCAN_PORTS:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.4)
            if s.connect_ex((ip, port)) == 0:
                found.append(port)
            s.close()
        except Exception:
            pass
    r["open_ports"] = found
    with PORT_CACHE_LOCK:
        PORT_CACHE[ip] = found
    state_merge(ip, open_ports=found)

def _ping_one(r):
    prev_status = r.get("status", "")
    _online = _tcp_reachable(r["ip"], 2.0)
    now = now_str()
    r["status"] = "ONLINE" if _online else "OFFLINE"
    if r["status"] == "ONLINE":
        r["last_online"] = now
        threading.Thread(target=_scan_ports, args=(r,), daemon=True).start()
    # Log status transitions
    if r["status"] != prev_status and prev_status in ("ONLINE", "OFFLINE"):
        lvl = "info" if r["status"] == "ONLINE" else "warn"
        app_log("ping", lvl,
                f"{prev_status} → {r['status']}",
                r["ip"], r.get("name", ""))
    r["last_ping"] = now
    state_merge(r["ip"], status=r["status"], last_ping=r["last_ping"], last_online=r["last_online"])

def ping_all():
    global PING_RUNNING
    if PING_RUNNING:
        return
    PING_RUNNING = True
    app_log("ping", "info", f"Ping avviato — {len(ROUTERS)} dispositivi")
    threads = [threading.Thread(target=_ping_one, args=(r,), daemon=True) for r in ROUTERS]
    for t in threads: t.start()
    for t in threads: t.join()
    PING_RUNNING = False
    online_now = sum(1 for r in ROUTERS if r["status"] == "ONLINE")
    offline_now = len(ROUTERS) - online_now
    PING_HISTORY.append({"ts": now_str(), "online": online_now, "total": len(ROUTERS)})
    _save_ping_history()
    app_log("ping", "info",
            f"Ping completato — {online_now} ONLINE, {offline_now} OFFLINE su {len(ROUTERS)}")
    _save_app_log()

def monitor():
    while True:
        if AUTO_ENABLED:
            ping_all()
        time.sleep(AUTO_INTERVAL)

def _rtm_loop():
    """Real-Time Monitoring: triggers ping every second while rtm_enabled."""
    while _app_cfg.get("rtm_enabled"):
        threading.Thread(target=ping_all, daemon=True).start()
        time.sleep(1)

def _start_rtm():
    """Start RTM background thread if not already running."""
    global RTM_THREAD
    if RTM_THREAD is None or not RTM_THREAD.is_alive():
        RTM_THREAD = threading.Thread(target=_rtm_loop, daemon=True)
        RTM_THREAD.start()

# ─────────────────────────────────────────────────────────────────
# § Upload helpers
# ─────────────────────────────────────────────────────────────────
def _save_upload(fileitem):
    filename = os.path.basename(fileitem.filename)
    path     = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(fileitem.file.read())
    return filename, path

def _update_router_script(ip, path, filename):
    """Update local script reference for a router (for the 'Run' button)."""
    for r in ROUTERS:
        if r["ip"] == ip:
            r["script"]             = path
            r["script_uploaded_at"] = now_str()
            state_merge(ip, script=path, script_uploaded_at=r["script_uploaded_at"])
            uploads_log_append(filename, ip, r["name"])
            return r["name"]
    return ""

def sftp_push(ip, username, password, local_path):
    """Push file to router /tmp/ via SFTP with provided credentials. Returns (ok, msg)."""
    try:
        ssh = _ssh_connect_creds(ip, username, password)
        remote = "/tmp/" + os.path.basename(local_path)
        sftp = ssh.open_sftp()
        sftp.put(local_path, remote)
        sftp.close()
        ssh.close()
        return True, "OK"
    except Exception as e:
        return False, _ssh_err_str(e)

def _bulk_job_worker(job_id, local_path, filename, targets):
    """Background worker: push file to list of (ip, username, password) targets."""
    for ip, username, password in targets:
        ok, msg = sftp_push(ip, username, password, local_path)
        name = _update_router_script(ip, local_path, filename) if ok else ""
        with JOBS_LOCK:
            JOBS[job_id]["results"].append({"ip": ip, "name": name, "ok": ok, "msg": msg})
            JOBS[job_id]["done"] += 1

def _upload_import_worker(job_id, local_path, filename, ips, run_after=True, cred_id=""):
    """Background worker: SFTP push, then /import if run_after is True.
    Credentials: if cred_id is provided it overrides per-device auto-resolve."""
    remote = filename   # RouterOS SFTP root = flash
    for ip in ips:
        name = ""
        try:
            if cred_id:
                username, password = _resolve_cred_id(cred_id)
            else:
                username, password = _get_device_creds(ip)
            ssh  = _ssh_connect_creds(ip, username, password)
            sftp = ssh.open_sftp()
            sftp.put(local_path, remote)
            sftp.close()
            if run_after:
                _, stdout, stderr = ssh.exec_command(f"/import file-name={remote}", timeout=30)
                out = stdout.read().decode().strip()
                err = stderr.read().decode().strip()
                msg = out if out else (err if err else "OK")
            else:
                msg = "Uploaded"
            ssh.close()
            ok   = True
            name = _update_router_script(ip, local_path, filename)
        except Exception as e:
            ok  = False
            msg = _ssh_err_str(e)
        with JOBS_LOCK:
            JOBS[job_id]["results"].append({"ip": ip, "name": name, "ok": ok, "msg": msg})
            JOBS[job_id]["done"] += 1

def start_upload_import_job(local_path, filename, ips, run_after=True, cred_id=""):
    job_id = str(uuid.uuid4())
    with JOBS_LOCK:
        JOBS[job_id] = {"done": 0, "total": len(ips), "results": []}
    threading.Thread(target=_upload_import_worker,
                     args=(job_id, local_path, filename, ips),
                     kwargs={"run_after": run_after, "cred_id": cred_id}, daemon=True).start()
    return job_id

def start_bulk_job(local_path, filename, targets):
    """Start a background bulk-upload job. Returns job_id."""
    job_id = str(uuid.uuid4())
    with JOBS_LOCK:
        JOBS[job_id] = {"done": 0, "total": len(targets), "results": []}
    t = threading.Thread(target=_bulk_job_worker,
                         args=(job_id, local_path, filename, targets), daemon=True)
    t.start()
    return job_id

# ─────────────────────────────────────────────────────────────────
# § CSS & design tokens
# ─────────────────────────────────────────────────────────────────
COMMON_CSS = """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── MikroTik palette (light) ────────────────────────────────── */
:root {
  /* Backgrounds — white/very-light-grey */
  --bg:      #f4f6f9;
  --bg2:     #ffffff;
  --bg3:     #eef1f6;
  --bg4:     #e4e8f0;
  /* Borders */
  --border:  #dde2eb;
  --border2: #c8d0de;
  /* Text */
  --text:    #1a2236;
  --text2:   #3d4f68;
  --text3:   #6b7a94;
  /* MikroTik navy blue (primary brand) */
  --accent:  #1b3a6b;
  --accent2: #2650a0;
  --accent3: rgba(27,58,107,.08);
  /* MikroTik red (secondary brand) */
  --red-brand: #c0392b;
  /* Semantic colours */
  --green:   #16a34a;
  --red:     #dc2626;
  --yellow:  #d97706;
  --purple:  #7c3aed;
  --mono:    'JetBrains Mono', monospace;
  --sans:    'Inter', sans-serif;
  --r:       5px;
  --r2:      8px;
  --r3:      12px;
  --shadow:  0 2px 12px rgba(27,58,107,.10);
}
/* ── Dark mode ─────────────────────────────────────────────── */
[data-theme="dark"] {
  --bg:      #0d1117;
  --bg2:     #161b22;
  --bg3:     #21262d;
  --bg4:     #30363d;
  --border:  #30363d;
  --border2: #484f58;
  --text:    #e6edf3;
  --text2:   #8b949e;
  --text3:   #6e7681;
  --accent:  #2650a0;
  --accent2: #388bfd;
  --accent3: rgba(56,139,253,.12);
  --shadow:  0 2px 12px rgba(0,0,0,.4);
}
[data-theme="dark"] body { background: var(--bg); }
[data-theme="dark"] .header-top-bar { background: #161b22; border-bottom:1px solid var(--border); }
[data-theme="dark"] .topbar-accent  { background: linear-gradient(90deg,#2650a0,#388bfd); }
[data-theme="dark"] .subnav-bar     { background: var(--bg2); border-bottom-color: var(--border); }
[data-theme="dark"] .subnav-active  { color: var(--accent2) !important; border-bottom-color: var(--accent2) !important; }
[data-theme="dark"] input, [data-theme="dark"] select, [data-theme="dark"] textarea {
  background: var(--bg3); border-color: var(--border2); color: var(--text);
}
[data-theme="dark"] .modal-overlay { background: rgba(0,0,0,.7); }
[data-theme="dark"] .home-card { box-shadow: 0 2px 8px rgba(0,0,0,.3); }
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { -webkit-font-smoothing: antialiased; }
body {
  font-family: var(--mono);
  background: var(--bg);
  color: var(--text);
  font-size: 12px;
  min-height: 100vh;
  line-height: 1.5;
}
a { color: var(--accent2); text-decoration: none; transition: color .15s; }
a:hover { color: var(--accent); }

/* ── Buttons ─────────────────────────────────────────────────── */
.btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 11px; border-radius: var(--r);
  border: 1px solid var(--border2);
  background: var(--bg2); color: var(--text2);
  font-family: var(--mono); font-size: 11px; font-weight: 500;
  cursor: pointer; white-space: nowrap; line-height: 1.4;
  transition: all .15s;
  text-decoration: none; letter-spacing: .2px;
  box-shadow: 0 1px 2px rgba(0,0,0,.06);
}
.btn:hover {
  border-color: var(--accent); color: var(--accent);
  background: var(--bg3); box-shadow: 0 0 0 2px var(--accent3);
}
.btn:active { transform: translateY(1px); }
.btn-primary {
  background: var(--accent); border-color: var(--accent); color: #fff;
  font-weight: 600; letter-spacing: .3px;
}
.btn-primary:hover {
  background: var(--accent2); border-color: var(--accent2);
  color: #fff; box-shadow: 0 0 0 3px rgba(27,58,107,.22);
}
.btn-danger  { border-color: var(--red);   color: var(--red); }
.btn-danger:hover  { background: var(--red);   color: #fff; border-color: var(--red); box-shadow: 0 0 0 3px rgba(220,38,38,.18); }
.btn-success { border-color: var(--green); color: var(--green); }
.btn-success:hover { background: var(--green); color: #fff; border-color: var(--green); box-shadow: 0 0 0 3px rgba(22,163,74,.18); }
.btn-icon {
  padding: 4px 7px; border-radius: var(--r); border: 1px solid transparent;
  background: transparent; color: var(--text3); cursor: pointer; font-size: 12px;
  transition: all .15s; line-height: 1;
}
.btn-icon:hover { background: var(--bg4); color: var(--red); border-color: var(--border2); }

/* ── Status pills ─────────────────────────────────────────────── */
.pill {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 2px 8px; border-radius: 20px;
  font-size: 10px; font-weight: 700; letter-spacing: .6px;
}
.pill::before { content: ''; width: 5px; height: 5px; border-radius: 50%; flex-shrink: 0; }
.pill-green  { background: rgba(22,163,74,.10);  color: var(--green);  border: 1px solid rgba(22,163,74,.28);  }
.pill-green::before  { background: var(--green); box-shadow: 0 0 4px var(--green); }
.pill-red    { background: rgba(220,38,38,.08);   color: var(--red);    border: 1px solid rgba(220,38,38,.22);   }
.pill-red::before    { background: var(--red); }
.pill-yellow { background: rgba(217,119,6,.09);   color: var(--yellow); border: 1px solid rgba(217,119,6,.22);  }
.pill-yellow::before { background: var(--yellow); }
.pill-blue   { background: rgba(27,58,107,.08);   color: var(--accent); border: 1px solid rgba(27,58,107,.20);  }
.pill-blue::before   { background: var(--accent); }
.pill-gray   { background: rgba(136,150,171,.09); color: var(--text2);  border: 1px solid var(--border2); }
.pill-gray::before   { background: var(--text3); }

/* ── Inputs ──────────────────────────────────────────────────── */
input[type=text], input[type=number], input[type=password], input[type=file], select {
  background: var(--bg2); border: 1px solid var(--border2);
  color: var(--text); font-family: var(--mono); font-size: 11px;
  border-radius: var(--r); padding: 5px 9px;
  transition: border-color .15s, box-shadow .15s;
  outline: none;
}
input[type=text]:focus, input[type=number]:focus,
input[type=password]:focus, select:focus {
  border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent3);
}
input[type=checkbox] { accent-color: var(--accent); width: 13px; height: 13px; cursor: pointer; }
input::placeholder { color: var(--text3); }
select option { background: var(--bg2); color: var(--text); }

/* ── Table ───────────────────────────────────────────────────── */
table { width: 100%; border-collapse: collapse; }
th, td {
  padding: 7px 11px; border-bottom: 1px solid var(--border);
  white-space: nowrap; vertical-align: middle; text-align: left;
}
th {
  color: var(--text2); font-weight: 600; font-size: 10px;
  letter-spacing: .9px; text-transform: uppercase;
  background: var(--bg3); cursor: pointer; user-select: none;
  border-bottom: 2px solid var(--border2);
  transition: color .15s;
}
th:hover { color: var(--accent); }
tbody tr { transition: background .08s; background: var(--bg2); }
tbody tr:hover { background: var(--bg3); }
tbody tr:hover .sticky-col { background: var(--bg3); }

.sticky-col {
  position: sticky; left: 0; background: var(--bg2); z-index: 2;
  border-right: 1px solid var(--border2);
  box-shadow: 2px 0 8px rgba(27,58,107,.07);
}

/* ── Header — two-row layout ─────────────────────────────────── */
.header-sticky-wrap {
  position: sticky;
  top: 0;
  z-index: 1000;
}
.topbar-accent {
  height: 4px;
  background: linear-gradient(90deg, var(--accent) 0%, var(--red-brand) 100%);
}

/* Row 1: brand + user/logout — navy background */
.header-top-bar {
  background: var(--accent);
  padding: 8px 18px;
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px;
}
.header-brand {
  font-family: var(--sans); font-size: 17px; font-weight: 800;
  color: #fff; letter-spacing: -.4px;
  display: flex; align-items: center; gap: 10px;
}
.logo-rosm  { color: var(--red-brand); font-weight: 900; letter-spacing: -.5px; }
.header-version {
  font-family: var(--mono); font-size: 10px; color: rgba(255,255,255,.5);
  cursor: pointer; padding: 2px 7px; border-radius: 10px;
  border: 1px solid rgba(255,255,255,.18); transition: background .15s;
}
.header-version:hover { background: rgba(255,255,255,.12); color: #fff; }
.header-logout-btn {
  background: rgba(255,255,255,.12) !important;
  border-color: rgba(255,255,255,.22) !important;
  color: rgba(255,255,255,.9) !important;
  font-size: 11px; padding: 4px 10px;
}
.header-logout-btn:hover {
  background: rgba(255,255,255,.22) !important;
  color: #fff !important; box-shadow: none !important;
}

/* Row 2: navigation — white/light sub-nav */
.subnav-bar {
  background: #fff;
  border-bottom: 2px solid var(--border);
  padding: 0 18px;
  display: flex; align-items: stretch; justify-content: space-between;
  gap: 0; min-height: 38px;
  box-shadow: 0 2px 8px rgba(27,58,107,.06);
}
.subnav-links {
  display: flex; align-items: stretch; gap: 0;
}
.subnav-item {
  display: inline-flex; align-items: center;
  padding: 0 14px; font-size: 12px; font-weight: 500;
  color: var(--text2); text-decoration: none;
  border-bottom: 3px solid transparent;
  transition: color .15s, border-color .15s;
  white-space: nowrap; cursor: pointer;
  font-family: var(--sans);
}
a.subnav-item:hover { color: var(--accent); border-bottom-color: var(--accent); }
.subnav-active {
  color: var(--accent) !important;
  border-bottom-color: var(--accent) !important;
  font-weight: 700;
}
.subnav-extra {
  display: flex; align-items: center; gap: 6px; padding: 4px 0;
}

/* old .header kept for compat — points to top-bar */
.header { background: var(--accent); }

/* ── Stat bar ─────────────────────────────────────────────────── */
.stat-bar {
  display: flex; gap: 0; align-items: stretch;
  background: var(--bg2); border-bottom: 2px solid var(--border);
  font-size: 11px; overflow-x: auto;
  box-shadow: 0 1px 4px rgba(27,58,107,.06);
}
.stat {
  display: flex; flex-direction: column; justify-content: center;
  padding: 6px 14px; border-right: 1px solid var(--border);
  gap: 1px; flex-shrink: 0;
}
.stat-label { font-size: 9px; text-transform: uppercase; letter-spacing: .8px; color: var(--text2); }
.stat-val   { color: var(--text); font-weight: 700; font-size: 12px; }

/* ── Cards (used in sub-pages) ───────────────────────────────── */
.container { padding: 16px; }
.card {
  background: var(--bg2); border: 1px solid var(--border);
  border-radius: var(--r2); margin-bottom: 14px; overflow: hidden;
  box-shadow: var(--shadow);
}
.card-header {
  padding: 10px 14px; border-bottom: 1px solid var(--border);
  font-weight: 600; font-size: 11px; color: var(--text2);
  display: flex; align-items: center; justify-content: space-between;
  background: var(--bg3);
}
.card-body { padding: 12px 14px; }

/* ── Tags ─────────────────────────────────────────────────────── */
.tag-wrap { display: flex; flex-wrap: wrap; gap: 3px; align-items: center; min-width: 60px; }
.tag-pill {
  display: inline-block; padding: 1px 7px; border-radius: 20px; font-size: 10px;
  font-weight: 600; cursor: default; white-space: nowrap; border: 1px solid transparent;
}
.tag-group {
  background: rgba(27,58,107,.10); color: var(--accent);
  border-color: rgba(27,58,107,.22); font-weight: 700;
}
.tag-edit-btn {
  opacity: 0; transition: opacity .15s; cursor: pointer;
  background: none; border: none; color: var(--text3); font-size: 11px; padding: 1px 4px;
}
.tag-cell:hover .tag-edit-btn { opacity: 1; }

/* ── Bulk bar ─────────────────────────────────────────────────── */
.bulk-bar {
  display: none; align-items: center; gap: 8px;
  padding: 6px 16px;
  background: linear-gradient(90deg, rgba(27,58,107,.07) 0%, transparent 100%);
  border-bottom: 1px solid rgba(27,58,107,.12);
  font-size: 11px; color: var(--accent2);
}
.bulk-bar .bulk-count {
  font-weight: 700; min-width: 120px; color: var(--accent);
}
.row-cb { cursor: pointer; accent-color: var(--accent); width: 13px; height: 13px; }

/* ── Ports cell ──────────────────────────────────────────────── */
.ports-cell { min-width: 120px; max-width: 200px; white-space: normal !important; }

/* ── Animations ──────────────────────────────────────────────── */
@keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:.35;} }
.pulse { animation: pulse 1.4s infinite; }

/* ── Filter row ──────────────────────────────────────────────── */
thead tr.filter-row th { background: var(--bg3); padding: 4px 6px; border-bottom: 2px solid var(--border2); }
thead tr.filter-row th input,
thead tr.filter-row th select {
  width: 100%; font-size: 12px; padding: 4px 8px;
  border-radius: var(--r); border: 1px solid var(--border2);
  background: var(--bg2); color: var(--text);
}

/* ── Sort arrows ─────────────────────────────────────────────── */
th.asc::after  { content: " ▲"; font-size: 8px; color: var(--accent); }
th.desc::after { content: " ▼"; font-size: 8px; color: var(--accent); }

/* ── Row counter ─────────────────────────────────────────────── */
.row-counter { font-size: 10px; color: var(--text2); }
.row-counter span { color: var(--text); font-weight: 700; }

/* ── Live IP links ───────────────────────────────────────────── */
.live-ips { margin-left: 4px; display: inline-flex; gap: 4px; flex-wrap: wrap; }
.live-ip {
  font-size: 10px; font-family: var(--mono); font-weight: 600;
  padding: 1px 5px; border-radius: 4px;
  background: rgba(27,58,107,.07); border: 1px solid rgba(27,58,107,.18);
  text-decoration: none; color: var(--accent2);
  transition: background .12s;
}
.live-ip:hover { background: rgba(27,58,107,.15); color: var(--accent); }

/* ── Inline form ─────────────────────────────────────────────── */
.inline-form { display: flex; gap: 5px; align-items: center; }

/* ── Global modal overlay ────────────────────────────────────── */
.modal-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.55);
  z-index: 9999;
  align-items: center;
  justify-content: center;
}
.modal-overlay.modal-show { display: flex; }

/* ── Version badge / footer ──────────────────────────────────── */
.version-footer {
  text-align: center; padding: 10px; font-size: 10px;
  color: var(--text3); border-top: 1px solid var(--border);
  margin-top: 12px; background: var(--bg2);
}
.version-footer a { color: var(--text3); }
.version-footer a:hover { color: var(--accent); }

/* ── Changelog modal ─────────────────────────────────────────── */
#changelogModal { display:none; position:fixed; inset:0; background:rgba(0,0,0,.45);
  z-index:9999; align-items:center; justify-content:center; }
#changelogModal.open { display:flex; }
.changelog-box {
  background: var(--bg2); border: 1px solid var(--border2);
  border-radius: var(--r3); padding: 24px; width: 540px;
  max-width: 96vw; max-height: 80vh; overflow-y: auto;
  box-shadow: 0 8px 40px rgba(27,58,107,.18);
}
.changelog-box h2 { font-size: 15px; font-weight: 800; color: var(--accent);
  margin-bottom: 16px; font-family: var(--sans); }
.cl-version { margin-bottom: 14px; }
.cl-tag { display:inline-block; background:var(--accent); color:#fff;
  font-size:10px; font-weight:700; padding:2px 8px; border-radius:10px;
  font-family:var(--mono); margin-right:6px; }
.cl-tag-latest { background:var(--red-brand); }
.cl-date { font-size:10px; color:var(--text3); }
.cl-list { margin-top:6px; padding-left:16px; }
.cl-list li { font-size:11px; color:var(--text2); margin-bottom:3px; }

/* ── Responsive ──────────────────────────────────────────────── */
@media (max-width: 900px) {
  .btn { padding: 4px 8px; font-size: 10px; }
  .stat { padding: 5px 10px; }
  .subnav-item { padding: 0 9px; font-size: 11px; }
}
@media (max-width: 640px) {
  .header-top-bar { flex-wrap: wrap; gap: 6px; }
  .subnav-bar { flex-wrap: wrap; overflow-x: auto; }
  .subnav-links { flex-wrap: nowrap; overflow-x: auto; }
  .stat-bar { flex-wrap: wrap; }
  .bulk-bar { flex-wrap: wrap; gap: 6px; }
  th:nth-child(n+8):not(:last-child), td:nth-child(n+8):not(:last-child) { display: none; }
}
/* ── Change notifications ──────────────────────────────── */
#changeLogPanel {
  position:fixed; bottom:18px; right:18px; z-index:8000;
  display:flex; flex-direction:column; gap:8px;
  max-width:370px; pointer-events:none;
}
.chg-toast {
  background:var(--bg2); border:1px solid var(--border2);
  border-left:4px solid var(--yellow);
  border-radius:10px; padding:10px 12px 10px 14px;
  box-shadow:0 4px 18px rgba(0,0,0,.25);
  display:flex; flex-direction:column; gap:4px;
  pointer-events:all; animation:chg-in .22s ease;
  cursor:pointer;
}
.chg-toast:hover { border-color:var(--accent); }
@keyframes chg-in { from{opacity:0;transform:translateX(24px);} to{opacity:1;transform:none;} }
.chg-toast-hd {
  display:flex; align-items:center; justify-content:space-between;
  font-size:10px; font-weight:700; color:var(--yellow);
  text-transform:uppercase; letter-spacing:.6px;
}
.chg-toast-ip  { font-size:12px; font-weight:700; color:var(--text); font-family:var(--mono); }
.chg-toast-msg { font-size:11px; color:var(--text2); line-height:1.45; }
.chg-toast-mac { font-family:var(--mono); font-size:10px; color:var(--text3); }
.chg-toast-mac span { color:var(--red); }
.chg-dismiss {
  background:none; border:none; cursor:pointer; color:var(--text3);
  font-size:14px; line-height:1; padding:0; margin-left:6px; flex-shrink:0;
  transition:color .1s;
}
.chg-dismiss:hover { color:var(--text); }

/* ── Frontend Access cards (wizard + settings) ──────────────── */
.wz-access-opts{display:flex;flex-direction:column;gap:10px;margin-bottom:16px;}
.wz-access-row{display:flex;align-items:center;gap:14px;padding:14px 16px;
  border:1.5px solid var(--border2);border-radius:10px;cursor:pointer;
  transition:border-color .15s,background .15s;}
.wz-access-row:hover{border-color:var(--accent);}
.wz-access-sel{border-color:var(--accent)!important;background:rgba(79,142,247,.07);}
.wz-access-row input[type=radio]{display:none;}
.wz-access-row input[type=checkbox]{display:none;}
.wz-access-ico{flex-shrink:0;display:flex;align-items:center;color:var(--text2);}
.wz-access-body{flex:1;}
.wz-access-row strong{display:block;font-size:13px;font-weight:700;color:var(--text);margin-bottom:2px;}
.wz-access-row span{font-size:11.5px;color:var(--text2);line-height:1.5;}
.wz-access-dot{width:18px;height:18px;border-radius:50%;border:2px solid var(--border2);
  flex-shrink:0;transition:all .15s;}
.wz-access-sel .wz-access-dot{background:var(--accent);border-color:var(--accent);}
"""

# ─────────────────────────────────────────────────────────────────
# § Frontend JS  (injected via .replace() — plain string, no f-string)
# ─────────────────────────────────────────────────────────────────
MAIN_JS_TEMPLATE = r"""
var ROSM_LANG='{rosm_lang}';
{js_i18n}
// ================================================================
// Modal helpers
// ================================================================
function openModal(id)  { document.getElementById(id).classList.add('open'); }
function closeModal(id) {
  document.getElementById(id).classList.remove('open');
  if (id === 'backdropUpload') {
    document.getElementById('uploadProgressWrap').classList.remove('visible');
    document.getElementById('uploadProgressMsg').textContent = '';
    document.getElementById('uploadProgressMsg').className = 'progress-msg';
    document.getElementById('uploadFile').value = '';
    document.getElementById('uploadSubmitBtn').disabled = false;
  }
  if (id === 'backdropBulk') {
    document.getElementById('bulkProgressWrap').classList.remove('visible');
    document.getElementById('bulkProgressBar').style.width = '0%';
    document.getElementById('bulkProgressMsg').textContent = '';
    document.getElementById('bulkFile').value = '';
    document.getElementById('bulkSubmitBtn').disabled = false;
  }
}
var _uploadIP = '';
function openUploadModal(ip) {
  _uploadIP = ip;
  document.getElementById('uploadModalIP').textContent = ip;
  openModal('backdropUpload');
  document.getElementById('uploadUser').focus();
}
async function submitSingleUpload() {
  var file = document.getElementById('uploadFile').files[0];
  var user = document.getElementById('uploadUser').value.trim();
  var pass = document.getElementById('uploadPass').value;
  var msg  = document.getElementById('uploadProgressMsg');
  var bar  = document.getElementById('uploadProgressWrap');
  var btn  = document.getElementById('uploadSubmitBtn');
  if (!file) { msg.textContent = 'Seleziona un file.'; msg.className='progress-msg fail'; return; }
  if (!user) { msg.textContent = 'Inserisci username.'; msg.className='progress-msg fail'; return; }
  if (!pass) { msg.textContent = 'Inserisci password.'; msg.className='progress-msg fail'; return; }
  btn.disabled = true;
  bar.classList.add('visible');
  document.getElementById('uploadProgressBar').classList.add('indeterminate');
  msg.textContent = 'Connessione…'; msg.className = 'progress-msg';
  var fd = new FormData();
  fd.append('ip', _uploadIP); fd.append('username', user);
  fd.append('password', pass); fd.append('file', file);
  try {
    var res  = await fetch('/upload_ssh', { method: 'POST', body: fd });
    var data = await res.json();
    document.getElementById('uploadProgressBar').classList.remove('indeterminate');
    document.getElementById('uploadProgressBar').style.width = '100%';
    msg.textContent = data.msg;
    msg.className   = 'progress-msg ' + (data.ok ? 'ok' : 'fail');
    if (data.ok) setTimeout(function() { closeModal('backdropUpload'); }, 1800);
    else btn.disabled = false;
  } catch(e) { msg.textContent='Errore: '+e; msg.className='progress-msg fail'; btn.disabled=false; }
}
async function openBulkModal() {
  openModal('backdropBulk');
  var grid = document.getElementById('companyGrid');
  grid.innerHTML = '<div style="color:var(--text2);font-size:11px;">Caricamento…</div>';
  var companies = await fetch('/api/companies').then(function(r) { return r.json(); });
  grid.innerHTML = '';
  Object.entries(companies).forEach(function(entry) {
    var name = entry[0], info = entry[1];
    var row = document.createElement('div');
    row.className = 'company-row';
    row.innerHTML =
      '<label class="company-header">'
      + '<input type="checkbox" onchange="toggleCompany(this)">'
      + '<span class="company-name">' + name + '</span>'
      + '<span class="company-meta">' + info.prefix + 'x.x &nbsp;&middot;&nbsp; ' + info.count + ' router</span>'
      + '</label>'
      + '<div class="company-creds">'
      + '<input type="text" placeholder="Username SSH" class="cred-user" autocomplete="off">'
      + '<input type="password" placeholder="Password SSH" class="cred-pass" autocomplete="off">'
      + '</div>';
    row.dataset.name = name;
    grid.appendChild(row);
  });
}
function toggleCompany(cb) {
  var row = cb.closest('.company-row');
  row.classList.toggle('selected', cb.checked);
  if (cb.checked) row.querySelector('.cred-user').focus();
}
var _bulkPollTimer = null;
async function submitBulkUpload() {
  var file = document.getElementById('bulkFile').files[0];
  var btn  = document.getElementById('bulkSubmitBtn');
  var msg  = document.getElementById('bulkProgressMsg');
  var bar  = document.getElementById('bulkProgressBar');
  var wrap = document.getElementById('bulkProgressWrap');
  if (!file) { msg.textContent='Seleziona un file.'; msg.className='progress-msg fail'; return; }
  var selected = [];
  document.querySelectorAll('#companyGrid .company-row.selected').forEach(function(row) {
    selected.push({name:row.dataset.name, username:row.querySelector('.cred-user').value.trim(), password:row.querySelector('.cred-pass').value});
  });
  if (!selected.length) { msg.textContent="Seleziona un'azienda."; msg.className='progress-msg fail'; return; }
  var missing = selected.find(function(s){ return !s.username||!s.password; });
  if (missing) { msg.textContent='Credenziali mancanti per '+missing.name+'.'; msg.className='progress-msg fail'; return; }
  btn.disabled=true; wrap.classList.add('visible'); bar.style.width='0%';
  msg.textContent='Avvio…'; msg.className='progress-msg';
  var fd=new FormData();
  fd.append('file',file); fd.append('companies',JSON.stringify(selected));
  try {
    var res=await fetch('/upload_bulk',{method:'POST',body:fd});
    var data=await res.json();
    if (!data.ok){msg.textContent=data.msg;msg.className='progress-msg fail';btn.disabled=false;return;}
    _pollBulkJob(data.job_id,data.total,bar,msg,btn);
  } catch(e){msg.textContent='Errore:'+e;msg.className='progress-msg fail';btn.disabled=false;}
}
function _pollBulkJob(job_id,total,bar,msg,btn) {
  clearTimeout(_bulkPollTimer);
  _bulkPollTimer=setTimeout(async function(){
    try {
      var j=await fetch('/api/job?id='+job_id).then(function(r){return r.json();});
      var pct=total>0?Math.round(j.done/total*100):0;
      bar.style.width=pct+'%';
      var ok=j.results.filter(function(r){return r.ok;}).length;
      var fail=j.results.filter(function(r){return !r.ok;}).length;
      msg.textContent=j.done+' / '+total+' router  OK '+ok+'  x '+fail;
      msg.className=fail>0?'progress-msg fail':'progress-msg';
      if(j.done<total) _pollBulkJob(job_id,total,bar,msg,btn);
      else{msg.className=fail===0?'progress-msg ok':'progress-msg fail';msg.textContent+='  — Completato';btn.disabled=false;}
    } catch(e){_pollBulkJob(job_id,total,bar,msg,btn);}
  },600);
}

// ================================================================
// Live DOM update
// ================================================================
var lastState = {};
var DASH = '<span style="color:var(--text3)">—</span>';
function _pill(c,l){return '<span class="pill pill-'+c+'">'+l+'</span>';}
function renderStatus(s){if(s==='ONLINE')return _pill('green','ONLINE');if(s==='OFFLINE')return _pill('red','OFFLINE');return _pill('gray','—');}
function renderSSH(s,err){
  if(s==='WORKING') return _pill('blue pulse','WORKING');
  if(s==='PENDING') return _pill('yellow','PENDING');
  if(s==='ERROR'){
    var msg=err||'Errore SSH';
    var safe=msg.replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    return '<span class="pill pill-red" style="cursor:pointer" title="'+safe+'" onclick="showSSHError(this)">error</span>';
  }
  return _pill('gray','IDLE');
}
function showSSHError(el){alert('Errore SSH:\n\n'+(el.title||'Errore sconosciuto'));}
function _renderPortsHtml(ports){
  if(!ports||!ports.length) return '<span style="color:var(--text3);font-size:10px;">—</span>';
  var LABELS={22:'SSH',80:'HTTP',443:'HTTPS',8080:'HTTP-alt',8291:'Winbox',8728:'API',8729:'API-SSL',8443:'HTTPS-alt'};
  function _col(p){if(p===8291)return '#1b3a6b';if(p===8728||p===8729)return '#7c3aed';if(p===22)return '#16a34a';if(p===80||p===8080)return '#d97706';if(p===443||p===8443)return '#2650a0';return '#8896ab';}
  var out='<span style="display:flex;flex-wrap:wrap;gap:2px;">';
  ports.slice().sort(function(a,b){return a-b;}).forEach(function(p){
    var c=_col(p), l=LABELS[p]||String(p);
    out+='<span title=":'+p+'" style="display:inline-block;padding:1px 5px;border-radius:3px;background:'+c+'18;color:'+c+';border:1px solid '+c+'44;font-size:9px;font-weight:700;font-family:var(--mono);">'+l+'</span>';
  });
  return out+'</span>';
}

// ================================================================
// Change notifications (MAC mismatch etc.)
// ================================================================
var _seenChanges = 0;
function _handleChangeLog(entries) {
  if (!entries || !entries.length) return;
  var newEntries = entries.slice(_seenChanges);
  _seenChanges = entries.length;
  newEntries.forEach(function(e) { _showChangeToast(e); });
}
function _showChangeToast(e) {
  var panel = document.getElementById('changeLogPanel');
  if (!panel) return;
  var ip = e.ip || '';
  var name = e.name ? ' <span style="color:var(--text2);">('+e.name+')</span>' : '';
  var msg = '', detail = '';
  if (e.type === 'mac_mismatch') {
    msg = 'MAC diverso — marcato <strong style="color:var(--red)">OFFLINE</strong>';
    detail = '<div class="chg-toast-mac">precedente: '+e.old_mac+'<br>rilevato: <span>'+e.new_mac+'</span></div>';
  }
  var t = document.createElement('div');
  t.className = 'chg-toast';
  t.innerHTML =
    '<div class="chg-toast-hd"><span>'+_TJSANM+'</span>'
    +'<button class="chg-dismiss" title="'+_TJSC+'" onclick="event.stopPropagation();this.closest(\'.chg-toast\').remove()">×</button></div>'
    +'<div class="chg-toast-ip">'+ip+name+'</div>'
    +'<div class="chg-toast-msg">'+msg+'</div>'
    +detail
    +'<div style="font-size:9px;color:var(--text3);margin-top:4px;">'+e.ts.slice(0,16)+'</div>';
  t.addEventListener('click', function(ev) {
    if (ev.target.classList.contains('chg-dismiss')) return;
    if (typeof scrollToRow === 'function') scrollToRow(ip);
  });
  panel.insertBefore(t, panel.firstChild);
  // keep at most 5 toasts visible
  var toasts = panel.querySelectorAll('.chg-toast');
  if (toasts.length > 5) toasts[toasts.length - 1].remove();
  // auto-dismiss after 60 s (important event — longer than usual)
  setTimeout(function() { if (t.parentNode) t.remove(); }, 60000);
}

// ================================================================
// Status-change toasts (ONLINE / OFFLINE)
// ================================================================
var _statusToastSuppressInit = true;  // ignore the first full-state snapshot
(function(){ setTimeout(function(){ _statusToastSuppressInit=false; }, 4000); })();

function _showStatusToast(ip, name, oldStatus, newStatus) {
  if (_statusToastSuppressInit) return;
  var panel = document.getElementById('changeLogPanel');
  if (!panel) return;
  var online = newStatus === 'ONLINE';
  var color  = online ? 'var(--green)' : 'var(--red)';
  var label  = online ? 'ONLINE' : 'OFFLINE';
  var nameHtml = name ? ' <span style="color:var(--text2);">('+name+')</span>' : '';
  var t = document.createElement('div');
  t.className = 'chg-toast';
  t.style.borderLeftColor = color;
  t.innerHTML =
    '<div class="chg-toast-hd" style="color:'+color+'">'
    +'<span>'+(online ? 'Router online' : 'Router offline')+'</span>'
    +'<button class="chg-dismiss" onclick="event.stopPropagation();this.closest(\'.chg-toast\').remove()">×</button></div>'
    +'<div class="chg-toast-ip">'+ip+nameHtml+'</div>'
    +'<div class="chg-toast-msg">Stato: <strong style="color:'+color+'">'+label+'</strong>'
    +(oldStatus ? ' <span style="color:var(--text3);font-size:9px;">(era '+oldStatus+')</span>' : '')+'</div>';
  t.addEventListener('click', function(ev) {
    if (ev.target.classList.contains('chg-dismiss')) return;
    if (typeof scrollToRow === 'function') scrollToRow(ip);
  });
  panel.insertBefore(t, panel.firstChild);
  var toasts = panel.querySelectorAll('.chg-toast');
  if (toasts.length > 5) toasts[toasts.length - 1].remove();
  setTimeout(function() { if (t.parentNode) t.remove(); }, 12000);
}

// ================================================================
// Column resize
// ================================================================
function initColResize() {
  var ths = document.querySelectorAll('thead tr.label-row th');
  ths.forEach(function(th) {
    var handle = document.createElement('div');
    handle.className = 'col-resizer';
    th.appendChild(handle);
    var startX, startW;
    handle.addEventListener('mousedown', function(e) {
      e.preventDefault();
      e.stopPropagation();
      startX = e.pageX;
      startW = th.offsetWidth;
      handle.classList.add('col-resizing');
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    });
    function onMove(e) {
      var delta = e.pageX - startX;
      th.style.minWidth = Math.max(40, startW + delta) + 'px';
      th.style.width    = Math.max(40, startW + delta) + 'px';
    }
    function onUp() {
      handle.classList.remove('col-resizing');
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      _saveColWidths();
    }
  });
  _restoreColWidths();
}

function _saveColWidths() {
  var ths = document.querySelectorAll('thead tr.label-row th');
  var widths = Array.from(ths).map(function(th){ return th.style.width || ''; });
  try { sessionStorage.setItem('col_widths', JSON.stringify(widths)); } catch(e) {}
}

function _restoreColWidths() {
  try {
    var saved = JSON.parse(sessionStorage.getItem('col_widths') || 'null');
    if (!saved) return;
    var ths = document.querySelectorAll('thead tr.label-row th');
    ths.forEach(function(th, i) {
      if (saved[i]) { th.style.width = saved[i]; th.style.minWidth = saved[i]; }
    });
  } catch(e) {}
}

document.addEventListener('DOMContentLoaded', function(){ initColResize(); });

function applyState(data) {
  var pingEl=document.getElementById('stat-ping');
  if(pingEl){pingEl.textContent=data.ping_running?(ROSM_LANG==='en'?'● IN PROGRESS':'● IN CORSO'):(ROSM_LANG==='en'?'inactive':'inattivo');pingEl.style.color=data.ping_running?'var(--yellow)':'var(--text2)';}
  _updStat('stat-ssh-w',data.ssh_working_ips,'var(--accent)');
  _updStat('stat-ssh-p',data.ssh_pending_ips,'var(--yellow)');
  if(data.ping_history) renderSparkline(data.ping_history);
  if(data.change_log)   _handleChangeLog(data.change_log);
  if(data.custom_cols) _applyCustomCols(data.custom_cols, data.custom_col_data || {});
  data.routers.forEach(function(r){
    var row=document.getElementById('row-'+r.ip.replaceAll('.', '-'));
    if(!row) return;
    var prev=lastState[r.ip]||{};
    var ch=function(k){return r[k]!==prev[k];};
    // Border highlight on SSH activity
    if(ch('ssh_status')||ch('ssh_error')){
      if(r.ssh_status==='WORKING') row.style.borderLeft='3px solid var(--accent)';
      else if(r.ssh_status==='PENDING') row.style.borderLeft='3px solid var(--yellow)';
      else if(r.ssh_status==='ERROR') row.style.borderLeft='3px solid var(--red)';
      else row.style.borderLeft='3px solid transparent';
    }
    // Cols: 0=CB 1=IP 2=Stato 3=Nome 4=Modello 5=DynaCol 6=Tags 7=Sito 8=SSH 9=Porte 10=Azioni
    if(ch('status')){
      row.cells[2].innerHTML=renderStatus(r.status);
      if(prev.status && prev.status!==r.status) _showStatusToast(r.ip, r.name||'', prev.status, r.status);
    }
    if(ch('name'))        row.cells[3].innerHTML=r.name?'<span style="color:var(--text);font-weight:600">'+r.name+'</span>':DASH;
    if(ch('model'))       row.cells[4].innerHTML=r.model||DASH;
    // dyna column
    var dynaKey=typeof DYNA_COL!=='undefined'?DYNA_COL:'packages';
    var dynaVal=DYNA_OPTIONS[dynaKey]?DYNA_OPTIONS[dynaKey].get(r):'';
    if(ch(dynaKey)||ch('note_full')||ch('packages')||ch('uptime')||ch('last_online')||ch('mac')||ch('model')){
      row.cells[5].innerHTML=dynaVal?_dynaHtml(dynaKey,dynaVal):DASH;
    }
    // cells[6] = Tags — managed by tag editor
    // cells[7] = Sito — managed server-side (static per page load)
    if(ch('ssh_status')||ch('ssh_error'))  row.cells[8].innerHTML=renderSSH(r.ssh_status,r.ssh_error);
    if(ch('open_ports'))  row.cells[9].innerHTML=_renderPortsHtml(r.open_ports||[]);
    lastState[r.ip]=r;
  });
}
function _updStat(id,ips,color){
  var el=document.getElementById(id); if(!el) return;
  el.textContent=ips.length;
  el.style.color=ips.length?color:'var(--text2)';
  // show clickable IPs in stat bar below the number
  var badgeId=id+'-badges';
  var existing=document.getElementById(badgeId);
  if(!ips.length){if(existing)existing.remove();return;}
  if(!existing){
    existing=document.createElement('div');
    existing.id=badgeId;
    existing.style.cssText='display:flex;flex-wrap:wrap;gap:3px;margin-top:2px;';
    el.parentNode.appendChild(existing);
  }
  existing.innerHTML=ips.slice(0,6).map(function(ip){
    return '<a href="#" onclick="scrollToRow(\''+ip+'\');return false;" class="live-ip">'+ip+'</a>';
  }).join('')+(ips.length>6?'<span style="color:var(--text3);font-size:9px;">+' +(ips.length-6)+'</span>':'');
}

// ================================================================
// Sparkline (online/offline over time)
// ================================================================
function renderSparkline(history) {
  var el = document.getElementById('sparkline');
  if (!el || !history.length) return;
  var W=96, H=28, pad=2;
  var n = history.length;
  var maxT = Math.max.apply(null, history.map(function(h){return h.total||1;}));
  function x(i){ return pad + (i/(Math.max(n-1,1)))*(W-2*pad); }
  function y(v,tot){ return H-pad - ((v/(tot||1))*(H-2*pad)); }
  // Green area (online)
  var pts = history.map(function(h,i){return x(i)+','+y(h.online,h.total||1);}).join(' ');
  var first=history[0], last=history[n-1];
  var area = 'M '+x(0)+','+(H-pad)+' L '+pts.split(' ').map(function(p,i){return (i===0?'L ':'')+ p;}).join(' L ')
           + ' L '+x(n-1)+','+(H-pad)+' Z';
  // Recompute properly
  var areaPoints = history.map(function(h,i){return x(i)+','+y(h.online,h.total||1);});
  var areaPath = 'M '+x(0)+','+(H-pad)+' '
    + areaPoints.map(function(p){return 'L '+p;}).join(' ')
    + ' L '+x(n-1)+','+(H-pad)+' Z';
  var linePath = areaPoints.map(function(p,i){return (i===0?'M ':'L ')+p;}).join(' ');
  el.innerHTML = '<svg width="'+W+'" height="'+H+'" viewBox="0 0 '+W+' '+H+'" style="display:block;">'
    + '<path d="'+areaPath+'" fill="rgba(42,223,138,.15)"/>'
    + '<path d="'+linePath+'" fill="none" stroke="var(--green)" stroke-width="1.5" stroke-linejoin="round"/>'
    + '<circle cx="'+x(n-1)+'" cy="'+y(last.online,last.total||1)+'" r="2.5" fill="var(--green)"/>'
    + '</svg>';
  el.title = 'Online: '+last.online+'/'+last.total+' — '+last.ts;
}

// ================================================================
// SSE live update (replaces polling)
// ================================================================
(function startSSE(){
  var es = new EventSource('/api/events');
  es.onmessage = function(e){
    try { applyState(JSON.parse(e.data)); } catch(ex){}
  };
  es.onerror = function(){
    // Auto-reconnects per spec; log silently
  };
})();

// ================================================================
// Scroll helpers
// ================================================================
function scrollToRow(ip){var el=document.getElementById('row-'+ip.replaceAll('.', '-'));if(el)el.scrollIntoView({behavior:'smooth',block:'center'});}
(function(){
  var wrap=document.getElementById('tableWrap');
  var saved=sessionStorage.getItem('scrollTop');
  if(wrap&&saved) wrap.scrollTop=+saved;
  var focus=new URLSearchParams(window.location.search).get('focus');
  if(focus){var el=document.getElementById('row-'+focus.replaceAll('.', '-'));if(el)el.scrollIntoView({behavior:'instant',block:'center'});history.replaceState({},'','/');}
})();
window.addEventListener('beforeunload',function(){var wrap=document.getElementById('tableWrap');if(wrap)sessionStorage.setItem('scrollTop',wrap.scrollTop);});

// ================================================================
// Filter
// ================================================================
function filterTable(){
  var active=[];
  var inputs=document.querySelectorAll('.filter');
  for(var i=0;i<inputs.length;i++){
    var el=inputs[i];
    var col=parseInt(el.getAttribute('data-col'));
    var val=(el.value||'').trim().toLowerCase();
    if(!isNaN(col)&&val!=='') active.push({col:col,val:val});
  }
  var rows=document.querySelectorAll('tbody tr');
  var visible=0;
  for(var r=0;r<rows.length;r++){
    var row=rows[r];
    var show=true;
    for(var f=0;f<active.length;f++){
      var flt=active[f];
      var cell=row.cells[flt.col];
      var text=cell?(cell.innerText||'').toLowerCase():'';
      if(text.indexOf(flt.val)===-1){show=false;break;}
    }
    row.style.display=show?'':'none';
    if(show) visible++;
  }
  var c=document.getElementById('rowCounter');
  if(c) c.innerHTML='<span>'+visible+'</span> / '+rows.length+' router';
  _saveFilters();
}
function _saveFilters(){
  var out={};
  var inputs=document.querySelectorAll('.filter');
  for(var i=0;i<inputs.length;i++){var el=inputs[i];var col=el.getAttribute('data-col');if(col&&el.value)out[col]=el.value;}
  try{sessionStorage.setItem('filters',JSON.stringify(out));}catch(e){}
}
function clearFilters(){
  var inputs=document.querySelectorAll('.filter');
  for(var i=0;i<inputs.length;i++){var el=inputs[i];if(el.tagName==='SELECT')el.selectedIndex=0;else el.value='';}
  try{sessionStorage.removeItem('filters');}catch(e){}
  filterTable();
}
(function(){
  try{
    var saved=JSON.parse(sessionStorage.getItem('filters')||'{}');
    var inputs=document.querySelectorAll('.filter');
    for(var i=0;i<inputs.length;i++){var el=inputs[i];var col=el.getAttribute('data-col');if(col&&saved[col]!==undefined)el.value=saved[col];}
  }catch(e){}
  filterTable();
})();

// ================================================================
// Sort
// ================================================================
// ================================================================
// Row selection + bulk actions
// ================================================================
var _bulkIPs = [];

function toggleSelectAll(cb){
  document.querySelectorAll('.row-cb').forEach(function(c){
    var row=c.closest('tr');
    if(row&&row.style.display!=='none') c.checked=cb.checked;
  });
  _updateBulkBar();
}

function onRowCheck(){
  _updateBulkBar();
  var all=document.querySelectorAll('.row-cb');
  var vis=Array.from(all).filter(function(c){return c.closest('tr').style.display!=='none';});
  var chk=vis.filter(function(c){return c.checked;});
  var sa=document.getElementById('selectAll');
  if(sa){sa.checked=chk.length>0&&chk.length===vis.length;sa.indeterminate=chk.length>0&&chk.length<vis.length;}
}

function _getSelectedIPs(){
  return Array.from(document.querySelectorAll('.row-cb:checked')).map(function(c){return c.dataset.ip;});
}

function _updateBulkBar(){
  var sel=_getSelectedIPs();
  var bar=document.getElementById('bulkTagBar');
  if(!bar) return;
  bar.style.display=sel.length>0?'flex':'none';
  var cEl=document.getElementById('bulkCount');
  if(cEl) cEl.textContent=sel.length+' selezionati';
  var delBtn=document.getElementById('bulkDeleteBtn');
  if(delBtn) delBtn.style.display=sel.length>=2?'':'none';
}

async function bulkDelete(){
  var ips=_getSelectedIPs();
  if(ips.length<2){return;}
  if(!confirm('Eliminare '+ips.length+' router dalla lista?\n\nQuesta operazione rimuove i device dalla dashboard e da devices.json. Non influisce sui dispositivi fisici.')) return;
  var errors=[];
  for(var i=0;i<ips.length;i++){
    try{
      var r=await fetch('/api/device/remove',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ip:ips[i]})});
      var j=await r.json();
      if(!j.ok) errors.push(ips[i]);
      else {
        var row=document.getElementById('row-'+ips[i].replaceAll('.', '-'));
        if(row){row.style.opacity='0';row.style.transform='translateX(20px)';setTimeout(function(rr){return function(){rr.remove();filterTable();};}(row),300);}
      }
    }catch(e){errors.push(ips[i]);}
  }
  deselectAll();
  if(errors.length) alert('Errore nell\'eliminazione di: '+errors.join(', '));
}

async function bulkPing(){
  var ips=_getSelectedIPs(); if(!ips.length) return;
  var btn=document.getElementById('bulkPingBtn');
  btn.disabled=true; btn.textContent='Ping…';
  await fetch('/api/bulk_ping',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ips:ips})});
  setTimeout(function(){btn.disabled=false;btn.textContent='Ping';},3000);
}

async function bulkRefresh(){
  var ips=_getSelectedIPs(); if(!ips.length) return;
  var btn=document.getElementById('bulkRefreshBtn');
  btn.disabled=true; btn.textContent='Avviato…';
  await fetch('/api/bulk_refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ips:ips})});
  setTimeout(function(){btn.disabled=false;btn.textContent='Info SSH';},3000);
}

function openBulkTagEditor(){
  var ips=_getSelectedIPs();
  if(!ips.length){alert('Seleziona almeno un router.');return;}
  _tagIP=null;
  _bulkIPs=ips;
  _assignedTags=[];
  document.getElementById('tagModalIP').textContent=ips.length+' router selezionati';
  document.getElementById('tagGroup').value='';
  _renderPredefined();
  _renderAssigned();
  openModal('backdropTag');
  document.getElementById('tagGroup').focus();
}

function deselectAll(){
  document.querySelectorAll('.row-cb').forEach(function(c){c.checked=false;});
  var sa=document.getElementById('selectAll');
  if(sa){sa.checked=false;sa.indeterminate=false;}
  _updateBulkBar();
}

// ================================================================
// Sort (col 0 = checkbox, skip it; sort uses actual cell index)
// ================================================================
function sortTable(th,n){
  var tbody=document.querySelector('tbody');
  if(!tbody) return;
  var asc=th.getAttribute('data-asc')!=='true';
  var ths=document.querySelectorAll('thead tr.label-row th');
  for(var i=0;i<ths.length;i++){ths[i].classList.remove('asc','desc');ths[i].removeAttribute('data-asc');}
  th.classList.add(asc?'asc':'desc');
  th.setAttribute('data-asc',String(asc));
  var items=[];
  for(var i=0;i<tbody.rows.length;i++){
    var row=tbody.rows[i];
    var key=row.cells[n]?(row.cells[n].innerText||'').trim():'';
    items.push({html:row.outerHTML,key:key});
  }
  items.sort(function(a,b){
    if(n===0){
      var pa=a.key.split('.'),pb=b.key.split('.');
      for(var i=0;i<4;i++){var d=(parseInt(pa[i])||0)-(parseInt(pb[i])||0);if(d!==0)return asc?d:-d;}
      return 0;
    }
    var ka=a.key.toLowerCase(),kb=b.key.toLowerCase();
    if(ka<kb)return asc?-1:1;if(ka>kb)return asc?1:-1;return 0;
  });
  tbody.innerHTML=items.map(function(x){return x.html;}).join('');
  filterTable();
  var wrap=document.getElementById('tableWrap');
  if(wrap) wrap.scrollTop=0;
}

// ================================================================
// CSV Export
// ================================================================
function exportCSV(){
  // Derive dynamic column label from the selector
  var dynaKey = typeof DYNA_COL !== 'undefined' ? DYNA_COL : 'packages';
  var dynaSel = document.getElementById('dynaColSelect');
  var dynaLabel = dynaSel && dynaSel.selectedOptions[0] ? dynaSel.selectedOptions[0].text : dynaKey;

  // Cols: 1=IP 2=Stato 3=Nome 4=Modello 5=DynaCol 6=Tag/Gruppo 7=Sito 8=SSH 9=Porte
  // Skipped: 0=Checkbox, 10=Azioni
  var headers = ['IP','Stato','Nome','Modello',dynaLabel,'Tag/Gruppo','Sito','SSH','Porte'];

  function _q(s){ return '"' + String(s||'').replace(/\n/g,' ').trim().replace(/"/g,'""') + '"'; }

  var rowsEl = document.querySelectorAll('tbody tr');
  var lines = [headers.map(_q).join(',')];
  for(var i=0;i<rowsEl.length;i++){
    var row = rowsEl[i];
    if(row.style.display === 'none') continue;
    var ip = row.cells[1] ? (row.cells[1].innerText||'').trim() : '';
    var r  = lastState[ip] || {};
    // Build row using lastState for clean data, fallback to innerText
    var vals = [
      ip,
      r.status || (row.cells[2] ? (row.cells[2].innerText||'').trim() : ''),
      r.name   || (row.cells[3] ? (row.cells[3].innerText||'').trim() : ''),
      r.model  || (row.cells[4] ? (row.cells[4].innerText||'').trim() : ''),
      (DYNA_OPTIONS[dynaKey] && r.ip ? DYNA_OPTIONS[dynaKey].get(r) : '') || (row.cells[5] ? (row.cells[5].innerText||'').trim() : ''),
      row.cells[6] ? (row.cells[6].innerText||'').replace(/\s+/g,' ').trim() : '',
      row.cells[7] ? (row.cells[7].innerText||'').trim() : '',
      r.ssh_status || (row.cells[8] ? (row.cells[8].innerText||'').trim() : ''),
      (r.open_ports||[]).join(' ')  || (row.cells[9] ? (row.cells[9].innerText||'').trim() : '')
    ];
    lines.push(vals.map(_q).join(','));
  }
  var blob = new Blob([''+lines.join('\r\n')], {type:'text/csv;charset=utf-8;'});
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'rosm_'+new Date().toISOString().slice(0,19).replace(/[T:]/g,'-')+'.csv';
  a.click();
}

// ================================================================
// Configurable column
// ================================================================
var DYNA_OPTIONS = {
  'packages':   {label:'ROS Ver.',     get:function(r){return r.packages||'';}},
  'note_full':  {label:'System Note',  get:function(r){return r.note_full||'';}},
  'uptime':     {label:'Uptime',       get:function(r){return r.uptime||'';}},
  'last_online':{label:'Ult. Online',  get:function(r){return r.last_online||'';}},
  'mac':        {label:'MAC',          get:function(r){return r.mac||'';}},
  'model':      {label:'Modello',      get:function(r){return r.model||'';}}
};
var _savedDyna = sessionStorage.getItem('dynacol');
// migrate old 'version' key to 'packages'
if(_savedDyna === 'version') { _savedDyna = 'packages'; sessionStorage.setItem('dynacol','packages'); }
var DYNA_COL = (_savedDyna && DYNA_OPTIONS[_savedDyna]) ? _savedDyna : 'packages';
(function(){
  var sel = document.getElementById('dynaColSelect');
  if(sel) sel.value = DYNA_COL;
})();

function _dynaHtml(key, val) {
  if(!val) return DASH;
  if(key==='packages') return '<span style="color:var(--accent2);font-weight:700;">'+val+'</span>';
  if(key==='mac')      return '<span style="font-size:10px;color:var(--text2);letter-spacing:.5px">'+val+'</span>';
  if(key==='last_online') return '<span style="color:var(--text2);">'+val+'</span>';
  return val;
}

function setDynaCol(val) {
  DYNA_COL = val;
  sessionStorage.setItem('dynacol', val);
  Object.entries(lastState).forEach(function(entry){
    var ip=entry[0], r=entry[1];
    var row=document.getElementById('row-'+ip.replaceAll('.', '-'));
    if(!row||!row.cells[5]) return;
    var v=DYNA_OPTIONS[val]?DYNA_OPTIONS[val].get(r):'';
    row.cells[5].innerHTML=v?_dynaHtml(val,v):DASH;
  });
}

// ================================================================
// Custom SSH columns
// ================================================================
var _customColsData = {};  // {ip: {col_id: value}}

function _applyCustomCols(cols, colData) {
  // Sync DYNA_OPTIONS with custom cols
  cols.forEach(function(c) {
    if(!DYNA_OPTIONS[c.id]) {
      DYNA_OPTIONS[c.id] = {label: c.name, get: function(r) {
        return (_customColsData[r.ip] || {})[c.id] || '';
      }};
      // add option to dropdown if missing
      var sel = document.getElementById('dynaColSelect');
      if(sel && !sel.querySelector('option[value="'+c.id+'"]')) {
        var opt = document.createElement('option');
        opt.value = c.id; opt.textContent = c.name;
        sel.appendChild(opt);
      }
    }
  });
  // Remove options that no longer exist
  var colIds = cols.map(function(c){return c.id;});
  Object.keys(DYNA_OPTIONS).forEach(function(key) {
    if(key.startsWith('cc_') && !colIds.includes(key)) {
      delete DYNA_OPTIONS[key];
      var sel = document.getElementById('dynaColSelect');
      var opt = sel && sel.querySelector('option[value="'+key+'"]');
      if(opt) opt.remove();
    }
  });
  _customColsData = colData || {};
}

function openCustomColsModal() {
  document.getElementById('customColsModal').style.display = 'flex';
  _renderCustomColsList();
}
function closeCustomColsModal() {
  document.getElementById('customColsModal').style.display = 'none';
}
function _renderCustomColsList() {
  var ul = document.getElementById('customColsList');
  if(!ul) return;
  var cols = Object.entries(DYNA_OPTIONS).filter(function(e){return e[0].startsWith('cc_');});
  if(cols.length === 0) { ul.innerHTML = '<li style="color:var(--text2);font-style:italic">Nessuna colonna personalizzata</li>'; return; }
  ul.innerHTML = cols.map(function(e) {
    var id=e[0], opt=e[1];
    return '<li style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border);">'
      +'<span style="flex:1;color:var(--text)">'+opt.label+'</span>'
      +'<button onclick="refreshCustomCol(\''+id+'\')" style="background:var(--bg4);border:1px solid var(--border2);color:var(--text2);padding:3px 10px;border-radius:4px;cursor:pointer;font-size:11px;">↺ Aggiorna</button>'
      +'<button onclick="deleteCustomCol(\''+id+'\')" style="background:transparent;border:none;color:var(--red);cursor:pointer;font-size:16px;padding:0 4px;">x</button>'
      +'</li>';
  }).join('');
}
async function addCustomCol() {
  var name = document.getElementById('newColName').value.trim();
  var cmd  = document.getElementById('newColCmd').value.trim();
  if(!name || !cmd) { alert('Inserisci nome e comando SSH'); return; }
  var r = await fetch('/api/custom_cols/add', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name:name, cmd:cmd})});
  var j = await r.json();
  if(j.ok) {
    document.getElementById('newColName').value = '';
    document.getElementById('newColCmd').value = '';
    _renderCustomColsList();
  } else { alert('Errore: '+j.msg); }
}
async function deleteCustomCol(id) {
  if(!confirm('Rimuovere questa colonna?')) return;
  await fetch('/api/custom_cols/remove', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:id})});
  _renderCustomColsList();
}
async function refreshCustomCol(id) {
  await fetch('/api/custom_cols/fetch', {method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({id:id})});
}

// ================================================================
// Remove device
// ================================================================
async function removeDevice(ip) {
  if(!confirm('Rimuovere '+ip+' dalla lista?')) return;
  try {
    await fetch('/api/device/remove',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({ip:ip})});
    var row=document.getElementById('row-'+ip.replaceAll('.', '-'));
    if(row) {
      row.style.transition='opacity .3s,transform .3s';
      row.style.opacity='0'; row.style.transform='translateX(20px)';
      setTimeout(function(){row.remove(); filterTable();},300);
    }
    delete lastState[ip];
  } catch(e){ alert('Errore: '+e); }
}

// ================================================================
// Predefined tags + Tag editor
// ================================================================
var PREDEFINED_TAGS = {predefined_tags_js};
var _tagIP       = '';
var _assignedTags = [];

var TAG_COLORS_JS = ["#4f8ef7","#2adf8a","#f7c44f","#f74f6a","#9b7ef7","#f78a4f","#4fd4f7","#df2a7e","#f7f74f","#2ad4df"];
function _tagColor(t) {
  var ci = t.split('').reduce(function(a,c){return a+c.charCodeAt(0);},0) % TAG_COLORS_JS.length;
  return TAG_COLORS_JS[ci];
}

function _renderPredefined() {
  var el = document.getElementById('predTagsList');
  if (!el) return;
  if (!PREDEFINED_TAGS.length) {
    el.innerHTML = '<span style="color:var(--text3);font-size:10px;">Nessun tag predefinito — creane uno ↓</span>';
    return;
  }
  el.innerHTML = PREDEFINED_TAGS.map(function(t) {
    var col = _tagColor(t);
    var assigned = _assignedTags.indexOf(t) >= 0;
    return '<span class="tag-pill" '
      + 'style="background:'+col+'22;color:'+col+';border-color:'+col+'44;cursor:pointer;'
      + (assigned ? 'outline:2px solid '+col+';' : 'opacity:.65;') + '" '
      + 'onclick="toggleAssignedTag(\''+t+'\')" '
      + 'title="'+(assigned?_TJSR:_TJSA)+'">'+t+'</span> '
      + '<span style="color:var(--text3);cursor:pointer;font-size:10px;" '
      + 'onclick="removePredefinedTag(\''+t+'\')" title="'+_TJSD+'">x</span> ';
  }).join('');
}

function _renderAssigned() {
  var el = document.getElementById('assignedTagsList');
  if (!el) return;
  if (!_assignedTags.length) {
    el.innerHTML = '<span style="color:var(--text3);font-size:10px;">'+_TJSN+'</span>';
    return;
  }
  el.innerHTML = _assignedTags.map(function(t) {
    var col = _tagColor(t);
    return '<span class="tag-pill" '
      + 'style="background:'+col+'22;color:'+col+';border-color:'+col+'44;cursor:pointer;" '
      + 'onclick="toggleAssignedTag(\''+t+'\')" title="'+_TJSR+'">'+t+' x</span>';
  }).join(' ');
}

function toggleAssignedTag(t) {
  var idx = _assignedTags.indexOf(t);
  if (idx >= 0) _assignedTags.splice(idx, 1);
  else _assignedTags.push(t);
  _renderPredefined();
  _renderAssigned();
}

async function addNewPredefinedTag() {
  var inp = document.getElementById('newTagInput');
  var tag = (inp.value || '').trim();
  if (!tag) return;
  try {
    var res = await fetch('/api/tags/add', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({tag: tag})
    });
    var data = await res.json();
    if (data.ok) {
      PREDEFINED_TAGS = data.tags;
      inp.value = '';
      // Auto-assign the new tag
      if (_assignedTags.indexOf(tag) < 0) _assignedTags.push(tag);
      _renderPredefined();
      _renderAssigned();
    }
  } catch(e) { alert('Errore: ' + e); }
}

async function removePredefinedTag(tag) {
  try {
    var res = await fetch('/api/tags/remove', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({tag: tag})
    });
    var data = await res.json();
    if (data.ok) {
      PREDEFINED_TAGS = data.tags;
      _renderPredefined();
    }
  } catch(e) { alert('Errore: ' + e); }
}

function openTagEditor(ip) {
  _tagIP = ip;
  document.getElementById('tagModalIP').textContent = ip;
  // Load current tags/group from DOM
  var wrap = document.getElementById('tags-' + ip.replaceAll('.','_'));
  _assignedTags = [];
  if (wrap) {
    var pills = wrap.querySelectorAll('.tag-pill:not(.tag-group)');
    pills.forEach(function(p) {
      var t = p.textContent.trim();
      if (t) _assignedTags.push(t);
    });
    var grpPill = wrap.querySelector('.tag-group');
    document.getElementById('tagGroup').value = grpPill ? grpPill.textContent.trim() : '';
  }
  _renderPredefined();
  _renderAssigned();
  openModal('backdropTag');
  document.getElementById('tagGroup').focus();
}

async function submitTagEditor() {
  var group = document.getElementById('tagGroup').value.trim();
  var ips = _tagIP ? [_tagIP] : _bulkIPs;
  if (!ips.length) return;

  try {
    // Send one request per router (could batch, but simpler this way)
    await Promise.all(ips.map(function(ip) {
      return fetch('/api/device/tag', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ip: ip, tags: _assignedTags, group: group})
      });
    }));

    // Update each row's tag cell in the table
    ips.forEach(function(ip) {
      var wrap = document.getElementById('tags-' + ip.replaceAll('.','_'));
      if (!wrap) return;
      var html = '';
      if (group) html += '<span class="tag-pill tag-group">' + group + '</span>';
      _assignedTags.forEach(function(t) {
        var col = _tagColor(t);
        html += '<span class="tag-pill" style="background:'+col+'22;color:'+col+';border-color:'+col+'44">'+t+'</span>';
      });
      html += '<button class="tag-edit-btn" onclick="openTagEditor(\''+ip+'\')" title="'+_TJSE+'">Edit</button>';
      wrap.innerHTML = html;
    });

    closeModal('backdropTag');
    if (ips.length > 1) deselectAll();
  } catch(e) {
    alert('Errore salvataggio: ' + e);
  }
}
"""

# ─────────────────────────────────────────────────────────────────
# § Tour overlay
# ─────────────────────────────────────────────────────────────────
def _user_dark_mode(session=None):
    """Return True if dark mode is enabled for the session user (per-user setting)."""
    if session:
        uname = session.get("username", "")
        if uname and uname in USERS:
            return bool(USERS[uname].get("dark_mode", False))
    return False


def _get_tour_js(tour_step_str):
    """Return a <script> block that renders the spotlight tour on the live page, or ''."""
    try:
        ts = int(tour_step_str)
    except Exception:
        return ""
    if ts not in (2, 3, 4, 5, 6):
        return ""

    lang_en = LANGUAGE == "en"

    if ts == 2:                      # ── Credentials (first step: create creds)
        next_url = "/topology?tour=3"
        prev_url = "/onboarding?step=1"
        steps = [
            {"sel": 'button[onclick="openCredModal()"]',
             "title": ("Step 1 — Create credentials" if lang_en else "Passo 1 — Crea le credenziali"),
             "desc": ("Start here: create at least one credential set before doing anything else. Give it a name, enter the SSH username and password used to access your routers."
                      if lang_en else
                      "Inizia da qui: crea almeno un set di credenziali prima di fare qualsiasi altra cosa. Dagli un nome, inserisci l'username SSH e la password che usi per accedere ai tuoi router.")},
            {"sel": '#credTable',
             "title": ("Your credential sets" if lang_en else "I tuoi set di credenziali"),
             "desc": ("Each row is a named username/password pair. Backups, script deploys and SSH operations all pick the right set automatically based on which site a router belongs to."
                      if lang_en else
                      "Ogni riga è una coppia nome/utente/password. Backup, deploy di script e operazioni SSH scelgono automaticamente il set giusto in base al sito di ogni router.")},
            {"sel": '#siteCredsTable', "fallback": '.card + .card',
             "title": ("Assign to a site" if lang_en else "Collega a un sito"),
             "desc": ("A credential set becomes useful when you assign it to a site. Every router in that site then uses those credentials for all operations — change the password once here and every router in the site picks it up."
                      if lang_en else
                      "Un set di credenziali diventa utile quando lo colleghi a un sito. Tutti i router di quel sito useranno quelle credenziali per tutte le operazioni — cambia la password qui una volta e tutti i router del sito si aggiornano.")},
            {"sel": 'button[onclick^="openRevealModal"]', "fallback": 'button[data-demo-reveal]',
             "title": ("Encrypted storage" if lang_en else "Archiviazione cifrata"),
             "desc": ("Passwords are encrypted with AES-128 and never shown in the UI. To reveal one you need the admin recovery code — find it in Settings → Recovery code."
                      if lang_en else
                      "Le password sono cifrate con AES-128 e non vengono mai mostrate nell'interfaccia. Per rivelarle serve il recovery code admin — trovalo in Impostazioni → Recovery code.")},
        ]
    elif ts == 3:                    # ── Site Manager
        next_url = "/discovery?tour=4"
        prev_url = "/credentials?tour=2"
        steps = [
            {"sel": 'button[onclick="openSite()"]', "fallback": '.sm-toolbar',
             "title": ("Step 2 — Create a site" if lang_en else "Passo 2 — Crea un sito"),
             "desc": ("Sites group your routers by location or customer. Once created, assign a credential set to the site — every router you import into that site will use those credentials automatically."
                      if lang_en else
                      "I siti raggruppano i router per sede o cliente. Dopo averlo creato, collega un set di credenziali al sito — ogni router che importi in quel sito userà automaticamente quelle credenziali.")},
            {"sel": '.sm-site-hdr', "fallback": '.sm-toolbar',
             "title": ("Site overview" if lang_en else "Panoramica sito"),
             "desc": ("Each site shows its name, city, the credential set in use, and a live count of online/offline routers. Click the header to expand and see the devices inside."
                      if lang_en else
                      "Ogni sito mostra nome, città, il set di credenziali attivo e il conteggio live di router online/offline. Clicca l'intestazione per espandere e vedere i dispositivi.")},
            {"sel": '.sm-site-cred', "fallback": '.sm-site-hdr',
             "title": ("Credentials badge" if lang_en else "Badge credenziali"),
             "desc": ("The badge shows which credential set is active for this site. All routers assigned here will use it for backups, SSH and scripts — override is still possible per-router from the Dashboard."
                      if lang_en else
                      "Il badge mostra quale set di credenziali è attivo per questo sito. Tutti i router assegnati useranno quelle credenziali per backup, SSH e script — puoi comunque sovrascriverle per singolo router dalla Dashboard.")},
            {"sel": '.sm-unassigned', "fallback": '.sm-toolbar',
             "title": ("Unassigned routers" if lang_en else "Router non assegnati"),
             "desc": ("Routers imported without a site appear here. Drag them into a site block or use 'Assign bulk' to move multiple devices at once."
                      if lang_en else
                      "I router importati senza sito appaiono qui. Trascinali in un blocco sito o usa 'Assegna in blocco' per spostarne più di uno insieme.")},
        ]
    elif ts == 4:                    # ── Network Discovery
        next_url = "/dashboard?tour=5"
        prev_url = "/topology?tour=3"
        steps = [
            {"sel": '#discSubnet',
             "title": ("Step 3 — Enter the subnet" if lang_en else "Passo 3 — Inserisci la subnet"),
             "desc": ("Type a CIDR subnet to scan — for example 10.0.0.0/24 for 256 addresses. ROSM auto-detects the local subnet. A /24 takes 30–60 seconds."
                      if lang_en else
                      "Inserisci una subnet in formato CIDR da scansionare — ad esempio 10.0.0.0/24 per 256 indirizzi. ROSM rileva automaticamente la subnet locale. Una /24 richiede 30–60 secondi.")},
            {"sel": '#discCredPicker',
             "title": ("Assign credentials now" if lang_en else "Assegna le credenziali subito"),
             "desc": ("Select a credential set before scanning — it will be saved with each discovered router so backups and SSH work immediately after import without any extra configuration."
                      if lang_en else
                      "Seleziona un set di credenziali prima di scansionare — verrà salvato con ogni router scoperto in modo che backup e SSH funzionino immediatamente dopo l'import senza ulteriore configurazione.")},
            {"sel": '#discBtn',
             "title": ("Scan and import" if lang_en else "Scansiona e importa"),
             "desc": ("Click Scan. Results appear in the table on the right — check the box on any row you want, then click 'Add selected'. Those routers go straight into ROSM and will be visible on the Dashboard."
                      if lang_en else
                      "Clicca Scansiona. I risultati appaiono nella tabella a destra — spunta le righe che vuoi, poi clicca 'Aggiungi selezionati'. Quei router entrano subito in ROSM e saranno visibili sulla Dashboard.")},
            {"sel": '#discAddPanel', "fallback": '#discAddSelBtn',
             "title": ("Import to ROSM" if lang_en else "Importa in ROSM"),
             "desc": ("After the scan, select the routers you want and click 'Add selected'. After importing, you are taken to the Site Manager to assign them to a site — that's how credentials get linked to routers automatically."
                      if lang_en else
                      "Dopo la scansione, seleziona i router che vuoi e clicca 'Aggiungi selezionati'. Dopo l'import, verrai portato al Site Manager per assegnarli a un sito — è così che le credenziali si collegano automaticamente ai router.")},
        ]
    elif ts == 5:                    # ── Dashboard
        next_url = "/backup?tour=6"
        prev_url = "/discovery?tour=4"
        steps = [
            {"sel": '.kpi-bar',
             "title": ("Step 4 — Your fleet" if lang_en else "Passo 4 — La tua flotta"),
             "desc": ("Imported routers appear here. The bar at the top shows total, online, offline, and active SSH sessions — updated every 30 seconds automatically."
                      if lang_en else
                      "I router importati appaiono qui. La barra in cima mostra totale, online, offline e sessioni SSH aperte — aggiornata automaticamente ogni 30 secondi.")},
            {"sel": 'tr.filter-row',
             "title": ("Live filtering" if lang_en else "Filtro live"),
             "desc": ("Each column has its own filter — type to narrow the list instantly. Filter by IP, name, model, tag, group or site at the same time. Use × to clear all filters."
                      if lang_en else
                      "Ogni colonna ha il suo filtro — scrivi per restringere la lista all'istante. Filtra per IP, nome, modello, tag, gruppo o sede contemporaneamente. Usa × per azzerare tutto.")},
            {"sel": '.tag-pill', "fallback": '.tag-wrap',
             "title": ("Tags for bulk operations" if lang_en else "Tag per operazioni di massa"),
             "desc": ("Tag routers at import time ('core', 'branch', 'group-x') — later you can target an entire group for backups or script deployment with a single click."
                      if lang_en else
                      "Etichetta i router all'import ('core', 'sede', 'gruppo-x') — potrai poi fare backup o deploy di script su un intero gruppo con un solo click.")},
            {"sel": '.act-btn', "fallback": '.act-group',
             "title": ("Per-router actions" if lang_en else "Azioni per router"),
             "desc": ("SSH reads live info from the router: hostname, ROS version, uptime, CPU. Creds overrides the site credentials for that specific device only."
                      if lang_en else
                      "SSH legge le info live dal router: hostname, versione ROS, uptime, CPU. Creds sovrascrive le credenziali del sito solo per quel dispositivo specifico.")},
            {"sel": 'a[href="/ping"]',
             "title": ("Ping All" if lang_en else "Ping tutto"),
             "desc": ("Forces an immediate status check on every router. Use this to refresh the fleet state after a network change or a power event."
                      if lang_en else
                      "Forza un controllo immediato su ogni router. Usalo per aggiornare lo stato della flotta dopo una modifica di rete o un evento di alimentazione.")},
        ]
    else:                            # ts == 6 — Backup
        next_url = "/onboarding?step=7"
        prev_url = "/dashboard?tour=5"
        steps = [
            {"sel": 'label.toggle-sw',
             "title": ("Step 5 — Enable automatic backup" if lang_en else "Passo 5 — Abilita il backup automatico"),
             "desc": ("Turn on the scheduler. Set how often to run (in hours) and how many days to keep files. ROSM takes care of the rest — no manual intervention needed."
                      if lang_en else
                      "Attiva il pianificatore. Imposta ogni quante ore girare e per quanti giorni tenere i file. ROSM fa il resto — nessun intervento manuale necessario.")},
            {"sel": '#bkInterval',
             "title": ("Backup interval" if lang_en else "Intervallo backup"),
             "desc": ("Hours between backup cycles. 24 is the recommended default for daily production use."
                      if lang_en else
                      "Ore tra un ciclo e l'altro. 24 è il valore consigliato per un uso giornaliero in produzione.")},
            {"sel": '#bkTarget',
             "title": ("Choose the target" if lang_en else "Scegli il target"),
             "desc": ("Pick which routers to include: all online, those with no backup yet, stale ones, by site or by group. The 'no backup yet' filter is the one to use on day one."
                      if lang_en else
                      "Scegli quali router includere: tutti gli online, quelli senza backup, quelli scaduti, per sito o per gruppo. Il filtro 'senza backup' è quello da usare il primo giorno.")},
            {"sel": '#bkManShowSens', "fallback": '#btnAvviaBackup',
             "title": ("Backup options" if lang_en else "Opzioni backup"),
             "desc": ("Show-sensitive includes passwords and keys in the exported config — recommended for a complete restore. Leave-on-router saves an extra copy in the router's flash memory."
                      if lang_en else
                      "Show-sensitive include password e chiavi nella config esportata — consigliato per un ripristino completo. Lascia-sul-router salva una copia extra nella memoria flash del router.")},
            {"sel": '#btnAvviaBackup',
             "title": ("Test it now" if lang_en else "Testalo adesso"),
             "desc": ("Run a manual backup on one online router first. If it succeeds, your credentials and connectivity are correct and the scheduler will work the same way."
                      if lang_en else
                      "Prima esegui un backup manuale su un router online. Se va a buon fine, credenziali e connettività sono corrette e il pianificatore funzionerà allo stesso modo.")},
        ]

    lbl_prev = json.dumps("← Back"      if lang_en else "← Indietro")
    lbl_next = json.dumps("Next →"      if lang_en else "Avanti →")
    lbl_skip = json.dumps("Skip"        if lang_en else "Salta")
    steps_j  = json.dumps(steps, ensure_ascii=False)
    next_j   = json.dumps(next_url)
    prev_j   = json.dumps(prev_url)
    is_final = json.dumps(ts == 6)   # true/false JS boolean

    # Section metadata for banners and transition screen
    sect_names = {
        2: ("Credentials" if lang_en else "Credenziali"),
        3: "Site Manager",
        4: "Network Discovery",
        5: "Dashboard",
        6: "Backup",
    }
    next_sect_names = {
        2: "Site Manager",
        3: "Network Discovery",
        4: "Dashboard",
        5: "Backup",
        6: ("You're all set!" if lang_en else "Sei pronto!"),
    }
    lbl_sect     = json.dumps(f"{'Section' if lang_en else 'Sezione'} {ts-1}/5 — {sect_names[ts]}")
    lbl_next_pg  = json.dumps(("Next section" if lang_en else "Prossima sezione") + ": " + next_sect_names[ts] + " →")
    lbl_next_nm  = json.dumps(next_sect_names[ts])
    lbl_cont_btn = json.dumps(("Continue →" if lang_en else "Continua →"))

    # ── Per-section demo-data injection JS ──────────────────────────────
    _lbl_demo_banner = (
        "&#128065; Demo data — no routers imported yet. Add them via Network Discovery."
        if lang_en else
        "&#128065; Dati demo — nessun router ancora importato. Aggiungili da Network Discovery."
    )
    _lbl_cred_banner = (
        "&#128065; Demo data — no credential sets yet. Create one with the button above."
        if lang_en else
        "&#128065; Dati demo — nessun set di credenziali. Creane uno con il pulsante qui sopra."
    )
    _lbl_ssh   = "SSH"
    _lbl_creds = "Creds"
    _lbl_reveal = "Reveal" if lang_en else "Rivela"
    _lbl_edit   = "Edit"   if lang_en else "Modifica"
    _lbl_delete = "Delete" if lang_en else "Elimina"
    _lbl_cred_name = "Main Credentials" if lang_en else "Credenziali Sede 1"

    if ts == 2:   # Credentials: inject fake credential row if credTable empty
        # Build the credential row HTML as a Python string first, then embed safely via json.dumps
        _cred_row_html = (
            '<td style="font-weight:600;color:var(--accent);">' + _lbl_cred_name + '</td>'
            '<td style="font-size:11px;color:var(--text2);">ad••'
            ' <span style="color:var(--text3);letter-spacing:1px;">/ ••••••••</span></td>'
            '<td style="font-size:11px;color:var(--text3);">0 siti · 0 router</td>'
            '<td style="white-space:nowrap;">'
            '<button class="btn _tour-reveal" data-demo-reveal="1"'
            ' style="padding:2px 8px;font-size:10px;margin-right:4px;">' + _lbl_reveal + '</button>'
            '<button class="btn" style="padding:2px 8px;font-size:10px;margin-right:4px;">' + _lbl_edit + '</button>'
            '<button class="btn btn-danger" style="padding:2px 8px;font-size:10px;">' + _lbl_delete + '</button>'
            '</td>'
        )
        _cred_ban_html = (
            '<td colspan="4" style="background:rgba(251,191,36,.1);'
            'border-bottom:1px solid rgba(251,191,36,.22);color:#92400e;font-size:10.5px;'
            'font-weight:600;padding:7px 14px;text-align:center;letter-spacing:.01em;">'
            + _lbl_cred_banner + '</td>'
        )
        _demo_js = (
            '  var _demoNodes=[];\n'
            '  function cleanupDemo(){\n'
            '    _demoNodes.forEach(function(n){if(n&&n.parentNode)n.parentNode.removeChild(n);});\n'
            '    _demoNodes=[];\n'
            '  }\n'
            '  var _CREDROW=' + json.dumps(_cred_row_html, ensure_ascii=False) + ';\n'
            '  var _CREDBAN=' + json.dumps(_cred_ban_html, ensure_ascii=False) + ';\n'
            '  function injectDemo(){\n'
            '    var ct=document.getElementById("credTable");\n'
            '    var _hasReal=ct&&Array.from(ct.rows).some(function(r){return r.cells.length>1;});\n'
            '    if(!ct||_hasReal)return;\n'
            '    var ban=document.createElement("tr");\n'
            '    ban.setAttribute("data-tour-demo","1");\n'
            '    ban.innerHTML=_CREDBAN;\n'
            '    ct.insertBefore(ban,ct.firstChild);\n'
            '    _demoNodes.push(ban);\n'
            '    var row=document.createElement("tr");\n'
            '    row.setAttribute("data-tour-demo","1");\n'
            '    row.innerHTML=_CREDROW;\n'
            '    ct.appendChild(row);\n'
            '    _demoNodes.push(row);\n'
            '  }\n'
        )
    elif ts == 5:  # Dashboard: inject fake router row if tbody empty
        _demo_js = (
            '  var _demoNodes=[];\n'
            '  function cleanupDemo(){\n'
            '    _demoNodes.forEach(function(n){if(n&&n.parentNode)n.parentNode.removeChild(n);});\n'
            '    _demoNodes=[];\n'
            '  }\n'
            '  function injectDemo(){\n'
            '    var tbody=document.querySelector("table tbody");\n'
            '    if(!tbody||tbody.rows.length>0)return;\n'
            '    var ban=document.createElement("tr");\n'
            '    ban.setAttribute("data-tour-demo","1");\n'
            '    ban.innerHTML=\'<td colspan="11" style="background:rgba(251,191,36,.1);'
            'border-bottom:1px solid rgba(251,191,36,.22);color:#92400e;font-size:10.5px;'
            'font-weight:600;padding:7px 14px;text-align:center;letter-spacing:.01em;">'
            + _lbl_demo_banner + '</td>\';\n'
            '    tbody.insertBefore(ban,tbody.firstChild);\n'
            '    _demoNodes.push(ban);\n'
            '    var row=document.createElement("tr");\n'
            '    row.setAttribute("data-tour-demo","1");\n'
            '    row.innerHTML=\n'
            '      \'<td style="width:32px;text-align:center;padding:0 8px;"><input type="checkbox" class="row-cb"></td>\'\n'
            '      +\'<td class="sticky-col" style="font-weight:700;color:var(--accent);letter-spacing:.3px;">192.168.88.1</td>\'\n'
            '      +\'<td><span class="sd"><span class="sd-dot on"></span><span class="sd-lbl on">ONLINE</span></span></td>\'\n'
            '      +\'<td style="color:var(--text);font-weight:600">MikroTik</td>\'\n'
            '      +\'<td style="color:var(--text2)">RB750Gr3</td>\'\n'
            '      +\'<td class="dyna-col">RouterOS 7.14</td>\'\n'
            '      +\'<td class="tag-cell"><div class="tag-wrap" id="tags-demo">\'\n'
            '      +\'<span class="tag-pill" style="background:#1b9ef722;color:#1b9ef7;border-color:#1b9ef744">core</span>\'\n'
            '      +\'<span class="tag-pill" style="background:#16a34a22;color:#16a34a;border-color:#16a34a44">branch</span>\'\n'
            '      +\'</div></td>\'\n'
            '      +\'<td><span style="color:var(--text3)">—</span></td>\'\n'
            '      +\'<td><span class="pill pill-gray">IDLE</span></td>\'\n'
            '      +\'<td class="ports-cell"></td>\'\n'
            '      +\'<td style="white-space:nowrap;"><div class="act-group">\'\n'
            '      +\'<a class="act-btn" href="#" onclick="return false">' + _lbl_ssh + '</a>\'\n'
            '      +\'<button class="act-btn" onclick="return false">' + _lbl_creds + '</button>\'\n'
            '      +\'</div></td>\';\n'
            '    tbody.appendChild(row);\n'
            '    _demoNodes.push(row);\n'
            '  }\n'
        )
    else:   # ts == 3, 4 or 6: no demo data needed
        _demo_js = (
            '  function cleanupDemo(){}\n'
            '  function injectDemo(){}\n'
        )

    # Plain Python string (NOT an f-string) — JS braces are literal, no escaping needed.
    return (
        '\n<script>\n'
        '(function(){\n'
        '  var ST='      + steps_j    + ';\n'
        '  var NX='      + next_j     + ';\n'
        '  var PV='      + prev_j     + ';\n'   # prev section URL (or "" for first)
        '  var FN='      + is_final   + ';\n'   # true when this is the last tour section
        '  var LP='      + lbl_prev   + ';\n'
        '  var LN='      + lbl_next   + ';\n'
        '  var LC='      + lbl_cont_btn + ';\n'
        '  var LS='      + lbl_skip   + ';\n'
        '  var SB='      + lbl_sect   + ';\n'   # section banner label
        '  var SN='      + lbl_next_pg + ';\n'  # "Prossima sezione: X →"
        '  var NS='      + lbl_next_nm + ';\n'  # next section name only
        '  var cur=0, bg, spot, tip, arr;\n'
        + _demo_js
        + '  function mk(cls){var d=document.createElement("div");d.className=cls;document.body.appendChild(d);return d;}\n'
        '\n'
        '  // ── Section header banner (fades out after 2.5 s) ──────────────\n'
        '  function showBanner(){\n'
        '    var b=document.createElement("div");\n'
        '    b.style.cssText="position:fixed;top:0;left:0;right:0;z-index:100010;background:#1b3a6b;"\n'
        '      +"color:#fff;font-size:12px;font-weight:700;letter-spacing:.04em;text-align:center;"\n'
        '      +"padding:8px 16px;box-shadow:0 2px 10px rgba(0,0,0,.35);"\n'
        '      +"font-family:-apple-system,BlinkMacSystemFont,sans-serif;transition:opacity .6s;";\n'
        '    b.textContent=" "+SB;\n'
        '    document.body.appendChild(b);\n'
        '    setTimeout(function(){b.style.opacity="0";},2200);\n'
        '    setTimeout(function(){b.remove();},2900);\n'
        '  }\n'
        '\n'
        '  // ── Transition overlay when crossing to next page ───────────────\n'
        '  function goNext(){\n'
        '    cleanupDemo();\n'
        '    // Final section: skip overlay, navigate immediately\n'
        '    if(FN){location.href=NX;return;}\n'
        '    var ov=document.createElement("div");\n'
        '    ov.style.cssText="position:fixed;inset:0;z-index:100020;display:flex;align-items:center;"\n'
        '      +"justify-content:center;background:rgba(27,58,107,.93);"\n'
        '      +"font-family:-apple-system,BlinkMacSystemFont,sans-serif;";\n'
        '    var sp=document.createElement("style");\n'
        '    sp.textContent="@keyframes tspin{to{transform:rotate(360deg)}}";\n'
        '    document.head.appendChild(sp);\n'
        '    ov.innerHTML="<div style=\'text-align:center;color:#fff;padding:32px;\'>"\n'
        '      +"<div style=\'font-size:12px;opacity:.65;margin-bottom:10px;letter-spacing:.05em;\'>"+SN+"</div>"\n'
        '      +"<div style=\'font-size:30px;font-weight:900;margin-bottom:24px;\'>"+NS+"</div>"\n'
        '      +"<div style=\'display:inline-block;width:28px;height:28px;border-radius:50%;"\n'
        '      +"border:3px solid rgba(255,255,255,.25);border-top-color:#fff;"\n'
        '      +"animation:tspin .75s linear infinite;\'></div>"\n'
        '      +"</div>";\n'
        '    document.body.appendChild(ov);\n'
        '    setTimeout(function(){location.href=NX;},1400);\n'
        '  }\n'
        '\n'
        '  function init(){\n'
        '    var s=document.createElement("style");\n'
        '    s.textContent=\n'
        '     ".t-bg{position:fixed;inset:0;z-index:100000;background:transparent;pointer-events:all;}"\n'
        '    +".t-sp{position:fixed;border-radius:11px;z-index:100001;pointer-events:none;"\n'
        '      +"box-shadow:0 0 0 9999px rgba(0,0,0,.74),0 0 0 3px #ef4444;transition:all .3s cubic-bezier(.4,0,.2,1);}"\n'
        '    +".t-tp{position:fixed;z-index:100002;background:#fff;border-radius:14px;pointer-events:all;"\n'
        '      +"box-shadow:0 20px 60px rgba(0,0,0,.38);padding:18px 20px 14px;width:330px;"\n'
        '      +"font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;transition:top .3s cubic-bezier(.4,0,.2,1),left .3s cubic-bezier(.4,0,.2,1);}"\n'
        '    +".t-hd{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;}"\n'
        '    +".t-ti{font-size:14px;font-weight:800;color:#1b3a6b;line-height:1.2;}"\n'
        '    +".t-dots{display:flex;gap:4px;align-items:center;}"\n'
        '    +".t-d{width:7px;height:7px;border-radius:50%;background:#e2e8f0;transition:background .2s;}"\n'
        '    +".t-d.on{background:#1b3a6b;transform:scale(1.2);}"\n'
        '    +".t-de{font-size:12.5px;color:#4a5568;line-height:1.6;margin-bottom:14px;}"\n'
        '    +".t-div{height:1px;background:#f1f5f9;margin:0 -20px 12px;}"\n'
        '    +".t-nv{display:flex;align-items:center;gap:7px;}"\n'
        '    +".t-bt{padding:7px 14px;border-radius:8px;border:1px solid #d1d5db;background:#f8fafc;"\n'
        '      +"color:#374151;font-size:11.5px;font-weight:600;cursor:pointer;font-family:inherit;"\n'
        '      +"text-decoration:none;display:inline-block;transition:background .15s,border-color .15s;}"\n'
        '    +".t-bt:hover{background:#f1f5f9;border-color:#94a3b8;}"\n'
        '    +".t-pr{background:#1b3a6b;color:#fff;border-color:#1b3a6b;}"\n'
        '    +".t-pr:hover{background:#243f7a;border-color:#243f7a;}"\n'
        '    +".t-fin{background:#16a34a;color:#fff;border-color:#16a34a;}"\n'
        '    +".t-fin:hover{background:#15803d;border-color:#15803d;}"\n'
        '    +".t-sk{font-size:10.5px;color:#94a3b8;background:none;border:none;cursor:pointer;"\n'
        '      +"margin-left:auto;padding:0;font-family:inherit;white-space:nowrap;transition:color .15s;}"\n'
        '    +".t-sk:hover{color:#64748b;}"\n'
        '    +".t-ar{position:fixed;z-index:100001;pointer-events:none;"\n'
        '      +"animation:tba .65s ease-in-out infinite alternate;}"\n'
        '    +"@keyframes tba{from{transform:translateY(0);}to{transform:translateY(-10px);}}";\n'
        '    document.head.appendChild(s);\n'
        '    bg=mk("t-bg"); spot=mk("t-sp"); arr=mk("t-ar"); tip=mk("t-tp");\n'
        '    document.addEventListener("keydown",function(e){\n'
        '      if(!bg||!bg.parentNode)return;\n'
        '      if(e.key==="ArrowRight"||e.key==="ArrowDown"){e.preventDefault();__t.go(1);}\n'
        '      else if(e.key==="ArrowLeft"||e.key==="ArrowUp"){e.preventDefault();__t.go(-1);}\n'
        '      else if(e.key==="Escape"){__t.skip();}\n'
        '    });\n'
        '    injectDemo();\n'
        '    showBanner();\n'
        '    show(0);\n'
        '  }\n'
        '\n'
        '  function show(i){\n'
        '    if(i<0||i>=ST.length)return;\n'
        '    cur=i;\n'
        '    var s=ST[i];\n'
        '    var e=document.querySelector(s.sel)||(s.fallback&&document.querySelector(s.fallback))||null;\n'
        '    if(!e){if(i+1<ST.length)show(i+1);else goNext();return;}\n'
        '    e.scrollIntoView({behavior:"smooth",block:"center"});\n'
        '    setTimeout(function(){\n'
        '      var r=e.getBoundingClientRect(),p=10;\n'
        '      spot.style.cssText="position:fixed;border-radius:11px;z-index:100001;pointer-events:none;"\n'
        '        +"box-shadow:0 0 0 9999px rgba(0,0,0,.74),0 0 0 3px #ef4444;transition:all .3s cubic-bezier(.4,0,.2,1);"\n'
        '        +"top:"+(r.top-p)+"px;left:"+(r.left-p)+"px;"\n'
        '        +"width:"+(r.width+p*2)+"px;height:"+(r.height+p*2)+"px;";\n'
        '      var last=(i===ST.length-1);\n'
        '      // Progress dots\n'
        '      var dotsH="";\n'
        '      for(var d=0;d<ST.length;d++)dotsH+="<span class=\'t-d"+(d===i?" on":"")+"\'></span>";\n'
        '      // Back button: within-section when i>0, cross-section when i===0 and PV set\n'
        '      var ph=i>0\n'
        '        ?"<button class=\'t-bt\' onclick=\'__t.go(-1)\'>"+LP+"</button>"\n'
        '        :(PV?"<a class=\'t-bt\' href=\'"+PV+"\'>"+LP+"</a>":"");\n'
        '      var nh=last\n'
        '        ?"<button class=\'t-bt t-fin\' onclick=\'__t.goNext()\'>"+LC+"</button>"\n'
        '        :"<button class=\'t-bt t-pr\' onclick=\'__t.go(1)\'>"+LN+"</button>";\n'
        '      tip.innerHTML=\n'
        '        "<div class=\'t-hd\'>"\n'
        '        +"<div class=\'t-ti\'>"+s.title+"</div>"\n'
        '        +"<div class=\'t-dots\'>"+dotsH+"</div>"\n'
        '        +"</div>"\n'
        '        +"<div class=\'t-de\'>"+s.desc+"</div>"\n'
        '        +"<div class=\'t-div\'></div>"\n'
        '        +"<div class=\'t-nv\'>"+ph+nh\n'
        '        +"<button onclick=\'__t.skip()\' class=\'t-sk\'>"+LS+"</button>"\n'
        '        +"</div>";\n'
        '      var tw=330,th=160;\n'
        '      // Position tooltip: prefer below element, fall back to above\n'
        '      var tx=Math.max(8,Math.min(r.left+(r.width/2)-(tw/2),window.innerWidth-tw-8));\n'
        '      var ty=r.bottom+p+18;\n'
        '      if(ty+th>window.innerHeight-8)ty=r.top-p-th-18;\n'
        '      ty=Math.max(8,ty);\n'
        '      tip.style.top=ty+"px";tip.style.left=tx+"px";\n'
        '      // Arrow: centered on the spotlight element horizontally\n'
        '      var below=(ty>r.bottom);\n'
        '      var ax=Math.max(8,Math.min(r.left+r.width/2-12,window.innerWidth-32));\n'
        '      var ay=below?(r.bottom+p+2):(ty+th+4);\n'
        '      var svgU="<svg width=24 height=24 viewBox=\'0 0 24 24\' fill=none><path d=\'M12 4l-8 10h5v6h6v-6h5z\' fill=\'#ef4444\'/></svg>";\n'
        '      var svgD="<svg width=24 height=24 viewBox=\'0 0 24 24\' fill=none><path d=\'M12 20l8-10h-5V4H9v6H4z\' fill=\'#ef4444\'/></svg>";\n'
        '      arr.innerHTML=below?svgU:svgD;\n'
        '      arr.style.left=ax+"px";\n'
        '      arr.style.top=ay+"px";\n'
        '    },350);\n'
        '  }\n'
        '\n'
        '  window.__t={\n'
        '    go:function(d){show(cur+d);},\n'
        '    goNext:goNext,\n'
        '    skip:function(){\n'
        '      cleanupDemo();\n'
        '      [bg,spot,tip,arr].forEach(function(x){if(x&&x.parentNode)x.remove();});\n'
        '      history.replaceState({},"",location.pathname);\n'
        '    }\n'
        '  };\n'
        '\n'
        '  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);\n'
        '  else setTimeout(init,600);\n'
        '})();\n'
        '</script>\n'
    )


# ─────────────────────────────────────────────────────────────────
# § HTTP server  (Handler + all render_* pages)
# ─────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # suppress default access logs

    def do_GET(self):
        global AUTO_ENABLED, AUTO_INTERVAL

        parsed = urllib.parse.urlparse(self.path)
        qs     = urllib.parse.parse_qs(parsed.query)

        # ── Public routes (no auth needed) ──────────────────────────
        if parsed.path == "/api/ping":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return

        if parsed.path == "/login":
            return self.respond(self.render_login_page())

        # ── MFA (public — require mfa_pending cookie) ────────────────
        if parsed.path == "/mfa/verify":
            pending = _get_mfa_pending(self)
            if not pending:
                return self.redirect("/login")
            return self.respond(self.render_mfa_verify_page())

        if parsed.path == "/mfa/setup":
            pending = _get_mfa_pending(self)
            if not pending:
                return self.redirect("/login")
            username = pending["username"]
            # Use or generate a temp secret stored in the pending entry
            with MFA_PENDING_LOCK:
                entry = MFA_PENDING.get(pending["token"])
                if entry and not entry.get("temp_secret"):
                    entry["temp_secret"] = _mfa_generate_secret()
                temp_secret = (entry or {}).get("temp_secret", "")
            return self.respond(self.render_mfa_setup_page(temp_secret))

        # ── Wizard (first run — public) ──────────────────────────────
        if parsed.path == "/setup":
            step = int(qs.get("step", ["1"])[0]) if qs else 1
            return self.respond(self.render_wizard_page(step=step))

        # ── Language switcher (public, before login) ─────────────────
        if parsed.path.startswith("/language/"):
            lang = parsed.path.split("/")[-1]
            if lang in ("en", "it"):
                _set_language(lang)
            ref = self.headers.get("Referer", "/login")
            # Only redirect back to safe local pages
            if not ref.startswith("http://") and not ref.startswith("https://"):
                ref = "/login"
            self.send_response(302)
            self.send_header("Location", "/login")
            self.end_headers()
            return

        # ── Forgot password (public) ─────────────────────────────────
        if parsed.path == "/forgot-password":
            return self.respond(self.render_forgot_password_page())

        if parsed.path == "/logout":
            _del_session(self)
            self.send_response(302)
            self.send_header("Set-Cookie", "session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict")
            self.send_header("Location", "/login")
            self.end_headers()
            return

        # ── Auth check ───────────────────────────────────────────────
        session = _get_session(self)
        if not session:
            # Redirect to wizard on first run, else to login
            if not FIRST_RUN_DONE:
                return self.redirect("/setup")
            return self.redirect("/login")

        role = session.get("role", "viewer")

        # ── Admin-only actions ───────────────────────────────────────
        ADMIN_PATHS  = {"/run", "/run_all", "/config"}
        _PERM_PATHS  = {
            "/backup":      "backup",
            "/credentials": "credentials",
            "/upload":      "upload",
            "/upgrade":     "upgrade",
            "/users":       "users_write",
            "/provision":   "upload",
            "/site-scan":   "upload",
        }
        if parsed.path in ADMIN_PATHS and role != "admin":
            return self.respond(self._forbidden_page(session))
        _req = _PERM_PATHS.get(parsed.path)
        if _req and not _can_do(session, _req):
            return self.respond(self._forbidden_page(session))
        # Settings: accessible to any elevated user (admin/manager/technician/custom-with-perms)
        if parsed.path == "/settings" and not _is_elevated(session):
            return self.respond(self._forbidden_page(session))

        if parsed.path == "/home":
            return self.respond(self.render_home_page(session))

        if parsed.path == "/settings":
            ok_key = (qs.get("ok") or [""])[0]
            ok_msgs = {
                "lang": T("Impostazioni salvate."),
                "pwd":  T("Password aggiornata con successo."),
                "name": T("Nome aggiornato."),
            }
            ctx = {"ok": ok_msgs[ok_key]} if ok_key in ok_msgs else {}
            return self.respond(self.render_settings_page(session, ctx=ctx))

        if parsed.path == "/topology":
            return self.respond(self.render_topology_page(session))

        if parsed.path == "/backup":
            return self.respond(self.render_backup_page(session))

        if parsed.path == "/credentials":
            return self.respond(self.render_credentials_page(session))

        if parsed.path == "/backup/download":
            fname = qs.get("file", [""])[0]
            fname = os.path.basename(fname)   # strip any path traversal
            fpath = os.path.join(BACKUP_DIR, fname)
            if not (fname.endswith(".rsc") or fname.endswith(".rsc.enc")) or not os.path.isfile(fpath):
                self.send_response(404); self.end_headers(); return
            raw = open(fpath, "r", encoding="utf-8", errors="replace").read()
            # Decrypt on the fly if encrypted; serve as plain .rsc regardless
            content = _decrypt_file_content(raw)
            dl_name = fname[:-4] if fname.endswith(".enc") else fname  # strip .enc from download name
            data    = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{dl_name}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if parsed.path == "/ping":
            threading.Thread(target=ping_all, daemon=True).start()
            return self.redirect("/")

        if parsed.path == "/refresh_all":
            refresh_all()
            return self.redirect("/")

        if parsed.path == "/refresh":
            ip    = qs.get("ip", [""])[0]
            focus = qs.get("focus", [""])[0] or ip
            for r in ROUTERS:
                if r["ip"] == ip:
                    threading.Thread(target=refresh_router, args=(r,), daemon=True).start()
                    break
            return self.redirect("/?focus=" + urllib.parse.quote(focus))

        if parsed.path == "/run":
            ip    = qs.get("ip", [""])[0]
            focus = qs.get("focus", [""])[0] or ip
            for r in ROUTERS:
                if r["ip"] == ip:
                    threading.Thread(target=run_script_on_router, args=(r,), daemon=True).start()
                    break
            return self.redirect("/?focus=" + urllib.parse.quote(focus))

        if parsed.path == "/run_all":
            run_all_scripts()
            return self.redirect("/")

        if parsed.path == "/config":
            AUTO_ENABLED = "enabled" in qs
            try:
                AUTO_INTERVAL = max(2, int(qs.get("secs", [str(AUTO_INTERVAL)])[0]))
            except Exception:
                pass
            return self.redirect("/")

        if parsed.path == "/upload":
            return self.respond(self.render_upload_page(session))

        if parsed.path == "/provision":
            return self.respond(self.render_provision_page(session))

        if parsed.path == "/site-scan":
            return self.redirect("/topology")

        if parsed.path == "/api/site_scan/status":
            sid = qs.get("sid", [""])[0]
            return self.handle_site_scan_get(sid)

        if parsed.path == "/upgrade":
            return self.respond(self.render_upgrade_page(session))

        if parsed.path == "/users":
            return self.respond(self.render_users_page(session))

        if parsed.path == "/discovery":
            return self.respond(self.render_discovery_page(session))

        # ── API: scan job status ─────────────────────────────────
        if parsed.path == "/api/scan_job":
            job_id = qs.get("id", [""])[0]
            with SCAN_JOBS_LOCK:
                job = dict(SCAN_JOBS.get(job_id, {"status":"not_found","done":0,"total":0,"results":[]}))
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps(job).encode())
            return

        if parsed.path == "/api/tags":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps(_load_predefined_tags()).encode())
            return

        # ── Viewer-accessible routes ─────────────────────────────────
        if parsed.path == "/uploads":
            return self.respond(self.render_uploads_page(session))

        if parsed.path == "/guide":
            return self.respond(self.render_guide_page(session))

        if parsed.path == "/welcome":
            if not session:
                return self.redirect("/login")
            return self.respond(self.render_welcome_page(session))

        if parsed.path == "/onboarding":
            _ob_qs = urllib.parse.parse_qs(parsed.query)
            try:    _ob_step = max(1, min(7, int(_ob_qs.get("step", ["1"])[0])))
            except: _ob_step = 1
            # Steps 2-6: redirect to the real page with ?tour=N overlay injected
            _ob_tour_map = {2: "/", 3: "/credentials", 4: "/backup", 5: "/users", 6: "/upgrade"}
            if _ob_step in _ob_tour_map:
                self.send_response(302)
                self.send_header("Location", _ob_tour_map[_ob_step] + "?tour=" + str(_ob_step))
                self.end_headers()
                return
            # Steps 1 and 6: render standalone card page
            return self.respond(self.render_onboarding_page(session, _ob_step))

        if parsed.path == "/stats":
            return self.respond(self.render_stats_page(session))

        if parsed.path == "/log":
            _valid_cats = {"all","ping","ssh","backup","script","security","system","error"}
            qs = urllib.parse.parse_qs(parsed.query)
            self._log_cat     = qs.get("cat",  ["all"])[0]
            if self._log_cat not in _valid_cats: self._log_cat = "all"
            self._log_date    = qs.get("date", [""])[0][:10]   # YYYY-MM-DD
            self._log_tf      = qs.get("tf",   [""])[0][:5]    # HH:MM from
            self._log_tt      = qs.get("tt",   [""])[0][:5]    # HH:MM to
            try:    self._log_per_page = max(10, min(500, int(qs.get("pp", ["50"])[0])))
            except: self._log_per_page = 50
            try:    self._log_page = max(1, int(qs.get("p", ["1"])[0]))
            except: self._log_page = 1
            return self.respond(self.render_report_page(session))

        if parsed.path == "/runs":
            return self.respond(self.render_runs_page(session))

        if parsed.path == "/api/job":
            job_id = qs.get("id", [""])[0]
            with JOBS_LOCK:
                job = JOBS.get(job_id, {"done": 0, "total": 0, "results": []})
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps(job).encode())
            return

        if parsed.path == "/api/companies":
            out = {}
            for name, prefix in COMPANIES.items():
                count = sum(1 for r in ROUTERS if r["ip"].startswith(prefix))
                out[name] = {"prefix": prefix, "count": count}
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(out).encode())
            return

        if parsed.path == "/api/creds":
            # Return cred sets without passwords
            safe = [{"id": c["id"], "name": c["name"]} for c in CRED_SETS]
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps(safe).encode())
            return

        if parsed.path == "/api/backup/status":
            payload = {
                "running":      BACKUP_RUNNING,
                "last_run":     BACKUP_CONFIG.get("last_run", ""),
                "next_run_ts":  BACKUP_CONFIG.get("next_run_ts", 0),
                "last_results": BACKUP_LAST_RESULTS,
                "files":        backup_list_files(),
                "config":       {k: v for k, v in BACKUP_CONFIG.items() if k != "next_run_ts"},
                # Include live data so the backup page can refresh without reloading
                "sites":        {sid: {"name": s.get("name",""), "city": s.get("city","")}
                                 for sid, s in SITES.items()},
                "groups":       sorted({r.get("group","") for r in ROUTERS if r.get("group","")}),
            }
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
            return

        if parsed.path == "/api/events":
            self._handle_sse()
            return

        if parsed.path == "/api/state":
            payload = self._build_state_payload()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())
            return

        if parsed.path == "/api/check-update":
            if not _is_admin(session):
                return self._json({"ok": False, "error": T("Accesso negato: richiesto ruolo Admin")})
            import urllib.request as _ureq
            try:
                _gh_token = _app_cfg.get("update_gh_token", "").strip()
                _ck_headers = {"User-Agent": f"ROSM/{APP_VERSION}", "Cache-Control": "no-cache"}
                if _gh_token:
                    _ck_headers["Authorization"] = f"token {_gh_token}"
                # Fetch version.json — small metadata file with version + changelog
                _meta_url = (f"https://raw.githubusercontent.com/"
                             f"{UPDATE_REPO}/{_update_branch()}/version.json")
                _ck_req = _ureq.Request(_meta_url, headers=_ck_headers)
                with _ureq.urlopen(_ck_req, timeout=12) as _ck_r:
                    _ck_data = json.loads(_ck_r.read().decode(errors="replace"))
                _remote_ver = str(_ck_data.get("version", "")).strip()
                if not _remote_ver:
                    return self._json({"ok": False,
                        "error": "Campo 'version' mancante in version.json. "
                                 "Verifica che il repo contenga il file version.json corretto."})
                def _ver(v):
                    try:
                        clean = re.sub(r'[^0-9.].*$', '', v.split("-")[0])
                        return tuple(int(x) for x in clean.split(".") if x)
                    except:
                        return (0,)
                _ver_remote = _ver(_remote_ver)
                _ver_local  = _ver(APP_VERSION)
                _upd_avail = _ver_remote > _ver_local
                _raw_cl = _ck_data.get("changelog", [])
                if _upd_avail:
                    _new_cl = [e for e in _raw_cl
                               if _ver(str(e.get("version", "0"))) > _ver_local]
                else:
                    _new_cl = []
                _upd_result = {
                    "ok": True,
                    "current": APP_VERSION,
                    "latest": _remote_ver,
                    "update_available": _upd_avail,
                    "changelog": _new_cl if _upd_avail else [],
                }
                return self._json(_upd_result)
            except json.JSONDecodeError:
                return self._json({"ok": False,
                    "error": "version.json non valido o non trovato. "
                             "Assicurati che il file esista nel repository e sia JSON valido."})
            except Exception as _upd_exc:
                return self._json({"ok": False, "error": str(_upd_exc)})

        if parsed.path == "/api/recovery_code":
            if not _is_admin(session):
                return self._json({"ok": False, "error": T("Accesso negato: richiesto ruolo Admin")})
            _rc_uname   = session.get("username", "admin")
            _rc_udata   = USERS.get(_rc_uname, {})
            _rc_mfa_on  = (MFA_AVAILABLE
                           and _rc_udata.get("mfa_enabled")
                           and bool(_rc_udata.get("totp_secret")))
            if _rc_mfa_on:
                _totp = qs.get("totp", [""])[0].strip()
                if not _mfa_verify_code(_rc_udata["totp_secret"], _totp, f"rc_{_rc_uname}"):
                    return self._json({"ok": False, "error": T("Codice non valido.")})
            return self._json({"ok": True, "code": RECOVERY_CODE})

        return self.respond(self.render_main_page(session))

    def do_POST(self):
        import traceback
        post_path = urllib.parse.urlparse(self.path).path

        # Public POST endpoints
        if post_path == "/login":
            return self._handle_login()
        if post_path == "/setup":
            return self._handle_setup()
        if post_path == "/forgot-password":
            return self._handle_forgot_password()

        # MFA POST — require valid mfa_pending cookie
        if post_path in ("/mfa/verify", "/mfa/setup"):
            pending = _get_mfa_pending(self)
            if not pending:
                return self.redirect("/login")
            username = pending["username"]
            user     = USERS.get(username, {})
            length   = int(self.headers.get("Content-Length", 0))
            params   = urllib.parse.parse_qs(self.rfile.read(length).decode(errors="replace"))
            code     = params.get("code", [""])[0].strip().replace(" ", "")

            if post_path == "/mfa/verify":
                secret = user.get("totp_secret", "")
                if secret and _mfa_verify_code(secret, code, username):
                    _del_mfa_pending(self)
                    token = _new_session(username, user["role"])
                    _mfa_dest = "/home" if USERS.get(username, {}).get("tour_dismissed") else "/onboarding?step=1"
                    self.send_response(302)
                    self.send_header("Set-Cookie", "mfa_pending=; Path=/; HttpOnly; Max-Age=0")
                    self.send_header("Set-Cookie",
                        f"session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400")
                    self.send_header("Location", _mfa_dest)
                    self.end_headers()
                else:
                    self.send_response(302)
                    self.send_header("Location", "/mfa/verify?error=1")
                    self.end_headers()

            else:  # /mfa/setup
                with MFA_PENDING_LOCK:
                    entry = MFA_PENDING.get(pending["token"])
                    temp_secret = (entry or {}).get("temp_secret", "")
                if temp_secret and _mfa_verify_code(temp_secret, code, username):
                    USERS[username]["totp_secret"] = temp_secret
                    save_json_atomic(USERS_FILE, USERS)
                    _del_mfa_pending(self)
                    token = _new_session(username, user["role"])
                    _mfa_setup_dest = "/home" if USERS.get(username, {}).get("tour_dismissed") else "/onboarding?step=1"
                    self.send_response(302)
                    self.send_header("Set-Cookie", "mfa_pending=; Path=/; HttpOnly; Max-Age=0")
                    self.send_header("Set-Cookie",
                        f"session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400")
                    self.send_header("Location", _mfa_setup_dest)
                    self.end_headers()
                else:
                    self.send_response(302)
                    self.send_header("Location", "/mfa/setup?error=1")
                    self.end_headers()
            return

        # Authenticated POST — role-based guard
        session = _get_session(self)
        if not session:
            return self._json({"ok": False, "msg": T("Accesso negato: richiesto ruolo Admin")})
        role = session.get("role", "viewer")

        # Map POST paths to required permission (None = any authenticated user)
        _POST_PERM_MAP = {
            "/log/clear":           "log_write",
            "/api/backup/run":      "backup",
            "/api/backup/config":   "backup",
            "/api/backup/delete":   "backup",
            "/api/creds/add":       "credentials",
            "/api/creds/update":    "credentials",
            "/api/creds/remove":    "credentials",
            "/api/creds/reveal":    "credentials",
            "/api/sites/set_creds": "credentials",
            "/upload_ssh":                  "upload",
            "/upload_import":               "upload",
            "/upload_bulk":                 "upload",
            "/upload_npk":                  "upgrade",
            "/api/ztp/template/save":       "upload",
            "/api/ztp/template/delete":     "upload",
            "/api/ztp/device/register":     "upload",
            "/api/ztp/device/remove":       "upload",
            "/api/ztp/apply":               "upload",
            "/api/site_scan/config":        "upload",
            "/api/site_scan/now":           "upload",
            "/api/ros-check-start":     "upgrade",
            "/api/ros-download":        "upgrade",
            "/api/ros-install":         "upgrade",
            "/settings/password":     None,
            "/settings/profile":      None,
            "/api/tour_dismiss":      None,
            "/users/add":             "users_write",
            "/users/delete":          "users_write",
            "/users/change_password": "users_write",
            "/users/mfa_toggle":      "users_write",
            "/users/mfa_reset":       "users_write",
            "/users/toggle_disabled": "users_write",
        }
        if role != "admin":
            if post_path in _POST_PERM_MAP:
                req = _POST_PERM_MAP[post_path]
                if req and not _can_do(session, req):
                    return self._json({"ok": False, "msg": T("Accesso negato: richiesto ruolo Admin")})
            else:
                return self._json({"ok": False, "msg": T("Accesso negato: richiesto ruolo Admin")})

        # Settings (form-based, not JSON)
        if post_path == "/settings/language":
            return self._handle_settings_language()
        if post_path == "/settings/password":
            return self._handle_settings_password(session)
        if post_path == "/settings/profile":
            return self._handle_settings_profile(session)
        if post_path == "/settings/ping_history":
            return self._handle_settings_ping_history()
        if post_path == "/settings/darkmode":
            _dm_uname = (session or {}).get("username", "")
            if _dm_uname and _dm_uname in USERS:
                USERS[_dm_uname]["dark_mode"] = not bool(USERS[_dm_uname].get("dark_mode", False))
                save_json_atomic(USERS_FILE, USERS)
            self.send_response(302)
            self.send_header("Location", "/settings")
            self.end_headers()
            return
        if post_path == "/settings/update_enabled":
            _app_cfg["update_enabled"] = not bool(_app_cfg.get("update_enabled", False))
            _save_app_config(_app_cfg)
            self.send_response(302)
            self.send_header("Location", "/settings")
            self.end_headers()
            return

        if post_path == "/settings/update_channel":
            if not _is_admin(session):
                return self._send_json({"ok": False, "error": "forbidden"})
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length).decode(errors="replace")
            params = urllib.parse.parse_qs(body)
            ch = (params.get("channel", ["stable"])[0] or "stable").strip()
            if ch not in _UPDATE_BRANCHES:
                ch = "stable"
            _app_cfg["update_channel"] = ch
            _save_app_config(_app_cfg)
            app_log("system", "info",
                    f"Canale aggiornamenti impostato su '{ch}' da "
                    f"'{(session or {}).get('username','unknown')}'.")
            return self._json({"ok": True, "switched": False,
                               "msg": f"Canale salvato: {ch}"})
        if post_path == "/settings/update_token":
            if not self._check_role(session, "admin"):
                return self._send_json({"ok": False, "error": "forbidden"})
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length).decode(errors="replace")
            params = urllib.parse.parse_qs(body)
            _tok = (params.get("token", [""])[0] or "").strip()
            _app_cfg["update_gh_token"] = _tok
            _save_app_config(_app_cfg)
            return self._send_json({"ok": True})
        if post_path == "/settings/encryption":
            if not self._check_role(session, "admin"):
                return self._send_json({"ok": False, "error": "forbidden"})
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length).decode(errors="replace")
            params = urllib.parse.parse_qs(body)
            new_enc_dev = bool(params.get("encrypt_devices", [""])[0])
            new_enc_bk  = bool(params.get("encrypt_backups", [""])[0])
            _app_cfg["encrypt_devices"] = new_enc_dev
            _app_cfg["encrypt_backups"] = new_enc_bk
            _save_app_config(_app_cfg)
            _save_state_file()  # re-write with new encryption flag
            return self._send_json({"ok": True})

        if post_path in ("/settings/access", "/settings/access-restart"):
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length).decode(errors="replace")
            params = urllib.parse.parse_qs(body)
            _app_cfg["bind_addresses"] = _normalize_bind_addresses(params.get("bind_address", []))
            _app_cfg.pop("bind_address", None)
            _save_app_config(_app_cfg)
            if post_path == "/settings/access-restart":
                self._send_json({"ok": True})
                _usr = (_get_session(self) or {}).get("username", "system")
                def _do_restart():
                    time.sleep(0.8)
                    for _s in ALL_SERVERS:
                        try:    _s.socket.close()
                        except Exception: pass
                    _argv = [a for a in sys.argv if not a.startswith("--restarted-by=")]
                    _argv.append(f"--restarted-by={_usr}[access-change]")
                    import subprocess as _sp
                    _env = os.environ.copy()
                    _env["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
                    _sp.Popen([sys.executable] + _argv, close_fds=True, start_new_session=True, env=_env)
                    os._exit(0)
                threading.Thread(target=_do_restart, daemon=False).start()
                return
            self.send_response(302)
            self.send_header("Location", "/settings")
            self.end_headers()
            return
        if post_path == "/log/clear":
            APP_LOG.clear()
            _save_app_log()
            self.send_response(302)
            self.send_header("Location", "/log")
            self.end_headers()
            return
        if post_path == "/log/settings":
            params = urllib.parse.parse_qs(self.rfile.read(
                int(self.headers.get("Content-Length", 0))).decode())
            try:
                new_max = int(params.get("log_maxlen", ["2000"])[0])
                new_max = max(100, min(20000, new_max))
            except Exception:
                new_max = 2000
            _app_cfg["app_log_maxlen"] = new_max
            _save_app_config(_app_cfg)
            _resize_app_log(new_max)
            self.send_response(302)
            self.send_header("Location", "/log")
            self.end_headers()
            return

        if post_path == "/api/rtm_toggle":
            if not _is_admin(session):
                return self._json({"ok": False, "msg": T("Accesso negato: richiesto ruolo Admin")})
            _app_cfg["rtm_enabled"] = not bool(_app_cfg.get("rtm_enabled", False))
            _save_app_config(_app_cfg)
            if _app_cfg["rtm_enabled"]:
                _start_rtm()
            app_log("system", "info",
                    f"Real Time Monitoring {'attivato' if _app_cfg['rtm_enabled'] else 'disattivato'} "
                    f"da '{(session or {}).get('username','?')}'")
            return self._json({"ok": True, "rtm_enabled": _app_cfg["rtm_enabled"]})

        if post_path == "/api/tour_dismiss":
            _td_username = (session or {}).get("username", "")
            if _td_username and _td_username in USERS:
                USERS[_td_username]["tour_dismissed"] = True
                save_json_atomic(USERS_FILE, USERS)
            return self._json({"ok": True})

        try:
            self._handle_post()
        except Exception as e:
            traceback.print_exc()
            try:
                self._json({"ok": False, "msg": "Errore server: " + str(e)})
            except Exception:
                pass

    def _handle_setup(self):
        global FIRST_RUN_DONE
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode(errors="replace")
        params = urllib.parse.parse_qs(body)
        qs_path = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        step = int(qs_path.get("step", ["1"])[0])

        def _p(k): return (params.get(k, [""])[0] or "").strip()

        if step == 1:
            lang = _p("language")
            if lang in ("en", "it"):
                _set_language(lang)
            self.send_response(302)
            self.send_header("Location", "/setup?step=2")
            self.end_headers()
            return

        if step == 2:
            # Profile: save display name
            name = _p("display_name")
            _set_display_name("admin", name)
            self.send_response(302)
            self.send_header("Location", "/setup?step=3")
            self.end_headers()
            return

        if step == 3:
            new_pw  = _p("new_password")
            conf_pw = _p("confirm_password")
            if len(new_pw) < 8:
                return self.respond(self.render_wizard_page(step=3,
                    ctx={"error": T("Nuova password") + " troppo corta (min 8 caratteri)."}))
            if new_pw != conf_pw:
                return self.respond(self.render_wizard_page(step=3,
                    ctx={"error": T("Le password non coincidono.")}))
            if "admin" in USERS:
                USERS["admin"]["hash"] = _hash_pwd(new_pw)
                save_json_atomic(USERS_FILE, USERS)
            self.send_response(302)
            self.send_header("Location", "/setup?step=4")
            self.end_headers()
            return

        if step == 4:
            # Save data-protection preferences
            _app_cfg["encrypt_backups"] = bool(_p("encrypt_backups"))
            _app_cfg["encrypt_devices"] = bool(_p("encrypt_devices"))
            _save_app_config(_app_cfg)
            self.send_response(302)
            self.send_header("Location", "/setup?step=5")
            self.end_headers()
            return

        if step == 5:
            # Save bind address preference
            _app_cfg["bind_addresses"] = _normalize_bind_addresses(params.get("bind_address", []))
            _app_cfg.pop("bind_address", None)
            _save_app_config(_app_cfg)
            self.send_response(302)
            self.send_header("Location", "/setup?step=6")
            self.end_headers()
            return

        if step == 6:
            # Save auto-update preference
            _app_cfg["update_enabled"] = (_p("update_enabled") == "1")
            _save_app_config(_app_cfg)
            self.send_response(302)
            self.send_header("Location", "/setup?step=7")
            self.end_headers()
            return

        if step == 7:
            # Mark first run complete, auto-login admin, redirect to /welcome
            with open(FIRST_RUN_FILE, "w") as f:
                f.write("done")
            FIRST_RUN_DONE = True
            token = _new_session("admin", USERS.get("admin", {}).get("role", "admin"))
            self.send_response(302)
            self.send_header("Set-Cookie",
                f"session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400")
            self.send_header("Location", "/welcome")
            self.end_headers()
            return

        self.send_response(302)
        self.send_header("Location", "/setup")
        self.end_headers()

    def _handle_forgot_password(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode(errors="replace")
        params = urllib.parse.parse_qs(body)
        def _p(k): return (params.get(k, [""])[0] or "").strip()

        phase = _p("phase")

        if phase == "enter_code":
            code = _p("recovery_code")
            if not code or code != RECOVERY_CODE:
                return self.respond(self.render_forgot_password_page(
                    ctx={"phase": "enter_code", "error": T("Codice non valido.")}))
            # Code correct: show new password form
            return self.respond(self.render_forgot_password_page(
                ctx={"phase": "new_password", "token": RECOVERY_CODE}))

        if phase == "new_password":
            token = _p("token")
            if token != RECOVERY_CODE:
                return self.respond(self.render_forgot_password_page(
                    ctx={"phase": "enter_code", "error": T("Codice non valido.")}))
            new_pw  = _p("new_password")
            conf_pw = _p("confirm_password")
            if len(new_pw) < 8:
                return self.respond(self.render_forgot_password_page(
                    ctx={"phase": "new_password", "token": token,
                         "error": "Password troppo corta (min 8 caratteri)."}))
            if new_pw != conf_pw:
                return self.respond(self.render_forgot_password_page(
                    ctx={"phase": "new_password", "token": token,
                         "error": T("Le password non coincidono.")}))
            # Reset admin password
            if "admin" in USERS:
                USERS["admin"]["hash"] = _hash_pwd(new_pw)
                save_json_atomic(USERS_FILE, USERS)
            return self.respond(self.render_forgot_password_page(
                ctx={"phase": "done"}))

        self.send_response(302)
        self.send_header("Location", "/forgot-password")
        self.end_headers()

    def _handle_settings_language(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode(errors="replace")
        params = urllib.parse.parse_qs(body)
        lang   = (params.get("language", ["en"])[0] or "en").strip()
        if lang in ("en", "it"):
            _set_language(lang)
        session = _get_session(self)
        self.send_response(302)
        self.send_header("Location", "/settings?ok=lang")
        self.end_headers()

    def _handle_settings_ping_history(self):
        global PING_HISTORY
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode(errors="replace")
        params = urllib.parse.parse_qs(body)
        try:
            days = int((params.get("ping_history_days", ["7"])[0] or "7").strip())
        except ValueError:
            days = 7
        if days not in _PING_HISTORY_DAYS_OPTIONS:
            days = 7
        cfg = _load_app_config()
        cfg["ping_history_days"] = days
        cfg.pop("ping_history_maxlen", None)   # remove old key if present
        _save_app_config(cfg)
        _app_cfg["ping_history_days"] = days
        _app_cfg.pop("ping_history_maxlen", None)
        # Resize the deque using new maxlen
        new_max  = _ping_history_maxlen()
        old_data = list(PING_HISTORY)
        PING_HISTORY = deque(old_data[-new_max:], maxlen=new_max)
        self.send_response(302)
        self.send_header("Location", "/settings?ok=ping_history")
        self.end_headers()

    def _handle_settings_password(self, session):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode(errors="replace")
        params = urllib.parse.parse_qs(body)
        def _p(k): return (params.get(k, [""])[0] or "").strip()
        cur = _p("current_password")
        new_pw = _p("new_password")
        conf   = _p("confirm_password")
        uname  = session.get("username", "admin")
        user   = USERS.get(uname, {})
        if not _verify_pwd(cur, user.get("hash", "")):
            return self.respond(self.render_settings_page(session,
                ctx={"error": T("Password attuale") + " non corretta."}))
        if len(new_pw) < 8:
            return self.respond(self.render_settings_page(session,
                ctx={"error": "Password troppo corta (min 8 caratteri)."}))
        if new_pw != conf:
            return self.respond(self.render_settings_page(session,
                ctx={"error": T("Le password non coincidono.")}))
        USERS[uname]["hash"] = _hash_pwd(new_pw)
        save_json_atomic(USERS_FILE, USERS)
        self.send_response(302)
        self.send_header("Location", "/settings?ok=pwd")
        self.end_headers()

    def _handle_settings_profile(self, session):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode(errors="replace")
        params = urllib.parse.parse_qs(body)
        name   = (params.get("display_name", [""])[0] or "").strip()
        uname  = (session or {}).get("username", "admin")
        _set_display_name(uname, name)
        self.send_response(302)
        self.send_header("Location", "/settings?ok=name")
        self.end_headers()

    def _handle_login(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode(errors="replace")
        params = urllib.parse.parse_qs(body)
        username = params.get("username", [""])[0].strip()
        password = params.get("password", [""])[0]
        # Optional post-login redirect (e.g. /onboarding after setup wizard)
        _post_login_next = params.get("next", [""])[0]
        if not _post_login_next.startswith("/"):
            _post_login_next = ""
        _login_dest = _post_login_next or "/home"

        user = USERS.get(username)
        if user and _verify_pwd(password, user["hash"]):
            if user.get("disabled"):
                self.send_response(302)
                self.send_header("Location", "/login?error=disabled")
                self.end_headers()
                return
            if MFA_AVAILABLE and user.get("mfa_enabled"):
                # Password OK — MFA required
                pending_token = _new_mfa_pending(username, user["role"])
                dest = "/mfa/setup" if not user.get("totp_secret") else "/mfa/verify"
                self.send_response(302)
                self.send_header("Set-Cookie",
                    f"mfa_pending={pending_token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=300")
                self.send_header("Location", dest)
                self.end_headers()
            else:
                token = _new_session(username, user["role"])
                self.send_response(302)
                self.send_header("Set-Cookie",
                    f"session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=86400")
                # Auto-tour: show onboarding on every login unless user dismissed it
                if not _post_login_next and not USERS.get(username, {}).get("tour_dismissed"):
                    _login_dest = "/onboarding?step=1"
                self.send_header("Location", _login_dest)
                self.end_headers()
        else:
            self.send_response(302)
            self.send_header("Location", "/login?error=1")
            self.end_headers()

    def _handle_post(self):
        import sys
        length = int(self.headers.get("Content-Length", 0) or 0)
        ctype  = self.headers.get("Content-Type", "")
        # Use parsed path to strip any query string
        path   = urllib.parse.urlparse(self.path).path

        # ── Debug info endpoint (admin only) ──────────────────────────
        if path == "/api/debug":
            _dbg_sess = _get_session(self)
            if (_dbg_sess or {}).get("role") != "admin":
                self._json_err(403, "Non autorizzato"); return
            import sys as _sys, platform as _platform
            _now = time.time()
            _nx  = BACKUP_CONFIG.get("next_run_ts", 0)
            _last_bk_log = [e for e in reversed(list(APP_LOG))
                            if e.get("cat") in ("backup", "error")][:20]
            _info = {
                "version": APP_VERSION,
                "python":  _sys.version,
                "platform": _platform.platform(),
                "backup": {
                    "enabled":       BACKUP_CONFIG.get("enabled", False),
                    "interval_hours": BACKUP_CONFIG.get("interval_hours", 24),
                    "show_sensitive": BACKUP_CONFIG.get("show_sensitive", True),
                    "keep_on_router": BACKUP_CONFIG.get("keep_on_router", False),
                    "last_run":      BACKUP_CONFIG.get("last_run", "—"),
                    "next_run_ts":   _nx,
                    "next_run_in_s": round(_nx - _now, 1) if _nx else None,
                    "next_run_human": (
                        datetime.fromtimestamp(_nx).strftime("%Y-%m-%d %H:%M:%S") if _nx else "—"
                    ),
                    "backup_running": BACKUP_RUNNING,
                },
                "routers": {
                    "total":   len(ROUTERS),
                    "online":  sum(1 for r in ROUTERS if r.get("status") == "ONLINE"),
                    "offline": sum(1 for r in ROUTERS if r.get("status") == "OFFLINE"),
                },
                "recent_backup_log": _last_bk_log,
            }
            _dbg_body = json.dumps(_info, ensure_ascii=False, indent=2, default=str).encode()
            self.send_response(200)
            self.send_header("Content-type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(_dbg_body)))
            self.end_headers()
            self.wfile.write(_dbg_body)
            return

        # ── Restart endpoint (admin only, no body needed) ─────────────
        if path == "/api/restart":
            _rs_session  = _get_session(self)
            _rs_username = (_rs_session or {}).get("username", "unknown")
            _rs_role     = (_rs_session or {}).get("role", "?")
            app_log("system", "info",
                    f"Riavvio applicazione richiesto da '{_rs_username}' (ruolo: {_rs_role})")
            _save_app_log()
            body = json.dumps({"ok": True, "msg": "Riavvio in corso…"}).encode()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            self.wfile.flush()
            _restart_arg = f"--restarted-by={_rs_username}"
            def _do_restart():
                time.sleep(0.8)
                for _s in ALL_SERVERS:
                    try:
                        _s.socket.close()   # libera la porta 8080
                    except Exception:
                        pass
                import subprocess
                # Avvia il nuovo processo senza ereditare i file descriptor;
                # passa --restarted-by per distinguere il riavvio da un avvio freddo nel log.
                _new_argv = [a for a in sys.argv if not a.startswith("--restarted-by=")]
                _new_argv.append(_restart_arg)
                _env = os.environ.copy()
                _env["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
                subprocess.Popen(
                    [sys.executable] + _new_argv,
                    close_fds=True,
                    start_new_session=True,
                    env=_env,
                )
                os._exit(0)   # termina il processo corrente immediatamente
            threading.Thread(target=_do_restart, daemon=False).start()
            return

        # ── Auto-update endpoint (admin only) ─────────────────────
        if path == "/api/do-update":
            import urllib.request as _ureq, shutil as _shutil
            _updu_session = _get_session(self)
            _updu_user    = (_updu_session or {}).get("username", "unknown")
            try:
                _raw_url = (f"https://raw.githubusercontent.com/"
                            f"{UPDATE_REPO}/{_update_branch()}/dashboard.py")
                # 1. Download new file
                _dl_gh_tok = _app_cfg.get("update_gh_token", "").strip()
                _dl_hdrs = {"User-Agent": f"ROSM/{APP_VERSION}", "Cache-Control": "no-cache"}
                if _dl_gh_tok:
                    _dl_hdrs["Authorization"] = f"token {_dl_gh_tok}"
                _dl_req = _ureq.Request(_raw_url, headers=_dl_hdrs)
                with _ureq.urlopen(_dl_req, timeout=30) as _dl_r:
                    _new_bytes = _dl_r.read()
                # 2. Basic sanity check
                if len(_new_bytes) < 10_000:
                    raise ValueError(
                        f"File scaricato troppo piccolo ({len(_new_bytes)} B) — aggiornamento annullato")
                # 3. Parse new version from downloaded content
                _ver_m = re.search(r'APP_VERSION\s*=\s*["\']([^"\']+)["\']',
                                   _new_bytes[:16384].decode(errors="replace"))
                _new_ver = _ver_m.group(1).strip() if _ver_m else "?"
                # 4. Backup current file, then replace
                _cur_path = os.path.abspath(__file__)
                _bak_path = _cur_path + ".bak"
                _shutil.copy2(_cur_path, _bak_path)
                with open(_cur_path, "wb") as _wf:
                    _wf.write(_new_bytes)
                app_log("system", "info",
                        f"Aggiornamento a v{_new_ver} installato da '{_updu_user}'. "
                        f"Backup: {_bak_path}")
                _save_app_log()
            except Exception as _updu_exc:
                return self._json({"ok": False, "msg": f"Aggiornamento fallito: {_updu_exc}"})
            # 5. Send response, then restart
            _updu_body = json.dumps({"ok": True,
                "msg": f"Aggiornamento a v{_new_ver} installato. Riavvio in corso…",
                "version": _new_ver}).encode()
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(_updu_body)))
            self.end_headers()
            self.wfile.write(_updu_body)
            self.wfile.flush()
            def _do_restart_after_update():
                time.sleep(1.2)
                for _s in ALL_SERVERS:
                    try:   _s.socket.close()
                    except Exception: pass
                import subprocess
                _argv = [a for a in sys.argv if not a.startswith("--restarted-by=")]
                _argv.append(f"--restarted-by={_updu_user}[update-v{_new_ver}]")
                _env = os.environ.copy()
                _env["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] = "YES"
                subprocess.Popen([sys.executable] + _argv, close_fds=True, start_new_session=True, env=_env)
                os._exit(0)
            threading.Thread(target=_do_restart_after_update, daemon=False).start()
            return

        # ── JSON body endpoints — handle BEFORE cgi.FieldStorage ────
        # FieldStorage consumes rfile; JSON endpoints must read first and return early.
        JSON_PATHS = {"/api/scan", "/api/add_devices",
                      "/api/device/tag", "/api/device/creds", "/api/device/remove",
                      "/api/tags/add", "/api/tags/remove",
                      "/api/bulk_ping", "/api/bulk_refresh",
                      "/api/custom_cols/add", "/api/custom_cols/remove", "/api/custom_cols/fetch",
                      "/api/sites/add", "/api/sites/update", "/api/sites/remove",
                      "/api/sites/assign_bulk", "/api/device/topology", "/api/device/link_type",
                      "/api/backup/run", "/api/backup/config", "/api/backup/delete",
                      "/api/creds/add", "/api/creds/update", "/api/creds/remove",
                      "/api/sites/set_creds"}
        if path in JSON_PATHS:
            raw  = self.rfile.read(length) if length > 0 else b""
            body = raw.decode(errors="replace")
            try:
                params = json.loads(body) if body.strip() else {}
            except Exception:
                return self._json({"ok": False, "msg": "JSON non valido nel body"})

            # Discovery: start subnet scan
            if path == "/api/scan":
                subnet     = params.get("subnet", "")
                ssh_user   = params.get("ssh_user", "")
                ssh_pass   = params.get("ssh_pass", "")
                cred_id    = params.get("cred_id", "")
                group_name = params.get("group", "")
                if cred_id:
                    ssh_user, ssh_pass = _resolve_cred_id(cred_id)
                if not subnet:
                    return self._json({"ok": False, "msg": "Subnet mancante"})
                ssh_pass_enc = _encrypt(ssh_pass) if ssh_pass else ""
                job_id, err = start_scan_job(subnet, ssh_user, ssh_pass_enc, group_name)
                if err:
                    return self._json({"ok": False, "msg": err})
                with SCAN_JOBS_LOCK:
                    _total = SCAN_JOBS.get(job_id, {}).get("total", 0)
                return self._json({"ok": True, "job_id": job_id, "total": _total})

            # Discovery: add devices
            if path == "/api/add_devices":
                devices_in = params.get("devices", [])
                # Top-level cred_id: resolve once and apply to all devices
                top_cred_id = params.get("cred_id", "")
                top_ssh_user, top_ssh_pass = ("", "")
                if top_cred_id:
                    top_ssh_user, top_ssh_pass = _resolve_cred_id(top_cred_id)
                added = 0
                for d in devices_in:
                    ip = d.get("ip", "")
                    if not ip:
                        continue
                    ssh_u = d.get("ssh_user") or top_ssh_user or ""
                    ssh_p = d.get("ssh_pass") or top_ssh_pass or ""
                    site_id_d = d.get("site_id", "")
                    existed = not device_add(
                        ip,
                        tags      = d.get("tags", []),
                        group     = d.get("group", ""),
                        ssh_user  = ssh_u,
                        ssh_pass  = ssh_p,
                        mac       = d.get("mac", ""),
                    )
                    if not existed:
                        if site_id_d and site_id_d in SITES:
                            with DEVICES_LOCK:
                                if ip in DEVICES:
                                    DEVICES[ip]["site_id"] = site_id_d
                            _save_devices()
                        saved = STATE.get(ip, {})
                        ROUTERS.append({
                            "ip": ip,
                            "tags":    d.get("tags", []),
                            "group":   d.get("group", ""),
                            "site_id": site_id_d,
                            "mac":     d.get("mac", ""),
                            "status": "", "last_ping": "", "last_online": "",
                            "name": saved.get("name", d.get("ros_identity", "")),
                            "version": saved.get("version", ""),
                            "model":   saved.get("model", d.get("model", "")),
                            "uptime": "", "last_name_update": "",
                            "packages": saved.get("packages", ""),
                            "note_full": saved.get("note_full", ""),
                            "open_ports": saved.get("open_ports", []),
                            "script": "", "script_uploaded_at": "",
                            "last_run_result": "", "last_run_ok": None, "last_run_at": "",
                            "ssh_status": "IDLE", "ssh_error": "", "run_status": "IDLE",
                        })
                        ROUTERS.sort(key=_sort_ip)
                        added += 1
                return self._json({"ok": True, "added": added})

            # Update tags
            if path == "/api/device/tag":
                ip    = params.get("ip", "")
                tags  = params.get("tags", [])
                group = params.get("group", "")
                if ip:
                    device_update(ip, tags=tags, group=group)
                    for r in ROUTERS:
                        if r["ip"] == ip:
                            r["tags"]  = tags
                            r["group"] = group
                            break
                return self._json({"ok": True})

            # Update credentials
            if path == "/api/device/creds":
                ip      = params.get("ip", "")
                cred_id = params.get("cred_id", "")
                if ip:
                    device_update(ip, credential_id=cred_id)
                return self._json({"ok": True})

            # Remove device
            if path == "/api/device/remove":
                ip = params.get("ip", "")
                if ip:
                    device_remove(ip)
                    ROUTERS[:] = [r for r in ROUTERS if r["ip"] != ip]
                return self._json({"ok": True})

            # Add predefined tag
            if path == "/api/tags/add":
                tag = params.get("tag", "").strip()
                if tag:
                    existing = _load_predefined_tags()
                    if tag not in existing:
                        existing.append(tag)
                        existing.sort()
                        _save_predefined_tags(existing)
                return self._json({"ok": True, "tags": _load_predefined_tags()})

            # Remove predefined tag
            if path == "/api/tags/remove":
                tag = params.get("tag", "").strip()
                existing = _load_predefined_tags()
                _save_predefined_tags([t for t in existing if t != tag])
                return self._json({"ok": True, "tags": _load_predefined_tags()})

            # Bulk ping on selected IPs
            if path == "/api/bulk_ping":
                ips = set(params.get("ips", []))
                targets = [r for r in ROUTERS if r["ip"] in ips]
                for r in targets:
                    threading.Thread(target=_ping_one, args=(r,), daemon=True).start()
                return self._json({"ok": True, "count": len(targets)})

            # Bulk SSH refresh on selected IPs
            if path == "/api/bulk_refresh":
                ips = set(params.get("ips", []))
                targets = [r for r in ROUTERS if r["ip"] in ips and r["ssh_status"] == "IDLE"]
                for r in targets:
                    r["ssh_status"] = "PENDING"
                    threading.Thread(target=refresh_router, args=(r,), daemon=True).start()
                return self._json({"ok": True, "count": len(targets)})

            if path == "/api/custom_cols/add":
                col_name = (params.get("name") or [""])[0].strip()
                col_cmd  = (params.get("cmd")  or [""])[0].strip()
                if not col_name or not col_cmd:
                    return self._json({"ok": False, "msg": "name e cmd richiesti"})
                col_id = "cc_" + str(int(time.time() * 1000))
                entry = {"id": col_id, "name": col_name, "cmd": col_cmd}
                with CUSTOM_COLS_LOCK:
                    CUSTOM_COLS.append(entry)
                    save_json_atomic(CUSTOM_COLS_FILE, CUSTOM_COLS)
                threading.Thread(target=fetch_custom_col, args=(col_id, col_cmd), daemon=True).start()
                return self._json({"ok": True, "col": entry})

            if path == "/api/custom_cols/remove":
                col_id = (params.get("id") or [""])[0].strip()
                with CUSTOM_COLS_LOCK:
                    before = len(CUSTOM_COLS)
                    CUSTOM_COLS[:] = [c for c in CUSTOM_COLS if c["id"] != col_id]
                    if len(CUSTOM_COLS) < before:
                        save_json_atomic(CUSTOM_COLS_FILE, CUSTOM_COLS)
                    for ip_data in CUSTOM_COL_DATA.values():
                        ip_data.pop(col_id, None)
                return self._json({"ok": True})

            if path == "/api/custom_cols/fetch":
                col_id = (params.get("id") or [""])[0].strip()
                col = next((c for c in CUSTOM_COLS if c["id"] == col_id), None)
                if not col:
                    return self._json({"ok": False, "msg": "colonna non trovata"})
                ips_param = params.get("ips")
                ips = set(ips_param) if ips_param else None
                threading.Thread(target=fetch_custom_col, args=(col_id, col["cmd"], ips), daemon=True).start()
                return self._json({"ok": True})

            # ── Sites management ─────────────────────────────────────────
            # helper: extract a plain string value from JSON params (not list)
            def _p(key, default=""):
                v = params.get(key, default)
                return (str(v) if not isinstance(v, list) else (v[0] if v else default)).strip()

            if path == "/api/sites/add":
                name = _p("name")
                city = _p("city")
                desc = _p("description")
                if not name:
                    return self._json({"ok": False, "msg": "nome richiesto"})
                sid = site_add(name, city, desc)
                return self._json({"ok": True, "id": sid, "site": SITES[sid]})

            if path == "/api/sites/update":
                sid  = _p("id")
                name = _p("name")
                city = _p("city")
                desc = _p("description")
                if not sid or sid not in SITES:
                    return self._json({"ok": False, "msg": "sede non trovata"})
                upd = {"city": city, "description": desc}
                if name: upd["name"] = name
                site_update(sid, **upd)
                return self._json({"ok": True})

            if path == "/api/sites/remove":
                sid = _p("id")
                site_remove(sid)
                return self._json({"ok": True})

            # ── Device topology fields ───────────────────────────────────
            if path == "/api/device/topology":
                ip               = _p("ip")
                site_id          = _p("site_id")
                parent_ip        = _p("parent_ip")
                device_role      = _p("device_role")
                device_role_label= _p("device_role_label")
                link_type        = _p("link_type")
                if not ip:
                    return self._json({"ok": False, "msg": "ip richiesto"})
                device_update(ip, site_id=site_id, parent_ip=parent_ip,
                              device_role=device_role, device_role_label=device_role_label,
                              link_type=link_type)
                for r in ROUTERS:
                    if r["ip"] == ip:
                        r["site_id"]           = site_id
                        r["parent_ip"]         = parent_ip
                        r["device_role"]       = device_role
                        r["device_role_label"] = device_role_label
                        r["link_type"]         = link_type
                        break
                return self._json({"ok": True})

            if path == "/api/device/link_type":
                ip        = _p("ip")
                link_type = _p("link_type")
                if not ip:
                    return self._json({"ok": False, "msg": "ip richiesto"})
                device_update(ip, link_type=link_type)
                for r in ROUTERS:
                    if r["ip"] == ip:
                        r["link_type"] = link_type
                        break
                return self._json({"ok": True})

            # ── Bulk site assignment ──────────────────────────────────────
            if path == "/api/sites/assign_bulk":
                ips_in           = params.get("ips", [])
                site_id          = _p("site_id")
                device_role      = _p("device_role")
                device_role_label= _p("device_role_label")
                if not isinstance(ips_in, list):
                    return self._json({"ok": False, "msg": "ips deve essere una lista"})
                count = 0
                for ip in ips_in:
                    ip = str(ip).strip()
                    if not ip:
                        continue
                    device_update(ip, site_id=site_id, device_role=device_role,
                                  device_role_label=device_role_label)
                    for r in ROUTERS:
                        if r["ip"] == ip:
                            r["site_id"]           = site_id
                            r["device_role"]       = device_role
                            r["device_role_label"] = device_role_label
                            break
                    count += 1
                return self._json({"ok": True, "count": count})

            # ── Backup endpoints ──────────────────────────────────────────
            if path == "/api/backup/run":
                if BACKUP_RUNNING:
                    return self._json({"ok": False, "msg": "Backup già in corso"})
                ips_param     = params.get("ips")
                ips           = set(ips_param) if ips_param else None
                cred_id_over  = _p("cred_id")
                if cred_id_over:
                    ssh_user_over, ssh_pass_over = _resolve_cred_id(cred_id_over)
                    ssh_user_over = ssh_user_over or None
                    ssh_pass_over = ssh_pass_over or None
                else:
                    ssh_user_over = _p("ssh_user") or None
                    ssh_pass_over = _p("ssh_pass") or None
                    if not (ssh_user_over and ssh_pass_over):
                        ssh_user_over = None
                        ssh_pass_over = None
                _bk_show_sens    = bool(params.get("show_sensitive", True))
                _bk_keep_router  = bool(params.get("keep_on_router", False))
                threading.Thread(
                    target=backup_all,
                    args=(ips, ssh_user_over, ssh_pass_over, _bk_show_sens, _bk_keep_router),
                    daemon=True
                ).start()
                return self._json({"ok": True})

            if path == "/api/backup/config":
                try:
                    BACKUP_CONFIG["enabled"]         = bool(params.get("enabled", False))
                    BACKUP_CONFIG["interval_hours"]  = max(0.01, float(params.get("interval_hours", 24)))
                    BACKUP_CONFIG["retention_days"]  = max(0, int(params.get("retention_days", 30)))
                    BACKUP_CONFIG["show_sensitive"]  = bool(params.get("show_sensitive", True))
                    BACKUP_CONFIG["keep_on_router"]  = bool(params.get("keep_on_router", False))
                    if BACKUP_CONFIG["enabled"]:
                        BACKUP_CONFIG["next_run_ts"] = time.time() + BACKUP_CONFIG["interval_hours"] * 3600
                    _save_backup_config()
                    return self._json({"ok": True, "config": dict(BACKUP_CONFIG)})
                except Exception as e:
                    return self._json({"ok": False, "msg": str(e)})

            if path == "/api/backup/delete":
                _bk_raw = params.get("file") or ""
                fname = os.path.basename(_bk_raw if isinstance(_bk_raw, str) else (_bk_raw[0] if _bk_raw else ""))
                if not fname.endswith(".rsc"):
                    return self._json({"ok": False, "msg": "File non valido"})
                fpath = os.path.join(BACKUP_DIR, fname)
                if os.path.isfile(fpath):
                    os.remove(fpath)
                return self._json({"ok": True})

            # ── Credential sets CRUD ─────────────────────────────────────
            if path == "/api/creds/add":
                cs_name  = _p("name")
                username = _p("username")
                password = _p("password")
                if not cs_name or not username or not password:
                    return self._json({"ok": False, "msg": "nome, username e password richiesti"})
                cid = cred_set_add(cs_name, username, password)
                return self._json({"ok": True, "id": cid,
                                   "cred": {"id": cid, "name": cs_name}})

            if path == "/api/creds/update":
                cid      = _p("id")
                cs_name  = _p("name")  or None
                username = _p("username") or None
                password = _p("password") or None
                cred_set_update(cid, name=cs_name, username=username, password=password)
                return self._json({"ok": True})

            if path == "/api/creds/remove":
                cid = _p("id")
                cred_set_remove(cid)
                return self._json({"ok": True})

            if path == "/api/creds/reveal":
                cid      = _p("id")
                rc_input = _p("recovery_code").strip()
                if rc_input != RECOVERY_CODE:
                    return self._json({"ok": False, "msg": T("Codice di recupero non valido.")})
                cs = next((c for c in CRED_SETS if c["id"] == cid), None)
                if not cs:
                    return self._json({"ok": False, "msg": "Set non trovato."})
                return self._json({
                    "ok":       True,
                    "username": _cred_set_username(cs),
                    "password": _decrypt(cs.get("password_enc", "")),
                })

            if path == "/api/sites/set_creds":
                sid = _p("site_id")
                cid = _p("credential_id")   # may be "" to unassign
                if sid not in SITES:
                    return self._json({"ok": False, "msg": "sede non trovata"})
                site_update(sid, credential_id=cid)
                return self._json({"ok": True})

            return self._json({"ok": False, "msg": "Endpoint non trovato"})

        # ---- User management (urlencoded) ──────────────────────────
        _cur_session = _get_session(self)

        def _admin_protected(target_uname):
            """Return True (and send 403 JSON) if target is admin and caller lacks admin_mgmt."""
            if target_uname == "admin" and not _can_do(_cur_session, "admin_mgmt"):
                self._json({"ok": False, "msg": "Cannot modify admin — requires Admin management permission"})
                return True
            return False

        if path in ("/users/mfa_toggle", "/users/mfa_reset"):
            body   = self.rfile.read(length).decode(errors="replace")
            params = urllib.parse.parse_qs(body)
            target = params.get("username", [""])[0].strip()
            if target not in USERS:
                return self._json({"ok": False, "msg": "User not found"})
            if _admin_protected(target):
                return
            if path == "/users/mfa_toggle":
                enabled = params.get("enabled", [""])[0] == "1"
                USERS[target]["mfa_enabled"] = enabled
                if not enabled:
                    USERS[target].pop("totp_secret", None)
            else:  # mfa_reset
                USERS[target].pop("totp_secret", None)
                USERS[target]["mfa_enabled"] = True
            save_json_atomic(USERS_FILE, USERS)
            return self._json({"ok": True})

        if path == "/users/toggle_disabled":
            body   = self.rfile.read(length).decode(errors="replace")
            params = urllib.parse.parse_qs(body)
            target = params.get("username", [""])[0].strip()
            if target not in USERS:
                return self._json({"ok": False, "msg": "User not found"})
            if _admin_protected(target):
                return
            current_user = (_cur_session or {}).get("username")
            if target == current_user:
                return self._json({"ok": False, "msg": "Cannot disable yourself"})
            USERS[target]["disabled"] = not USERS[target].get("disabled", False)
            if USERS[target]["disabled"]:
                # Invalidate active sessions for this user
                with SESSIONS_LOCK:
                    for t in [t for t, s in SESSIONS.items() if s.get("username") == target]:
                        del SESSIONS[t]
            save_json_atomic(USERS_FILE, USERS)
            return self._json({"ok": True, "disabled": USERS[target]["disabled"]})

        if path in ("/users/add", "/users/delete", "/users/change_password"):
            body   = self.rfile.read(length).decode(errors="replace")
            params = urllib.parse.parse_qs(body)
            def p(k): return params.get(k, [""])[0].strip()

            if path == "/users/add":
                new_user = p("username")
                new_pass = p("password")
                new_role = p("role") if p("role") in VALID_ROLES else "viewer"
                if not new_user or not new_pass:
                    return self.redirect("/users?error=empty")
                if new_user in USERS:
                    return self.redirect("/users?error=exists")
                entry = {"hash": _hash_pwd(new_pass), "role": new_role}
                if new_role == "custom":
                    entry["permissions"] = {
                        k: bool(params.get(f"perm_{k}", [""])[0])
                        for k, _, _ in CUSTOM_PERMS
                    }
                USERS[new_user] = entry
                save_json_atomic(USERS_FILE, USERS)
                return self.redirect("/users?ok=added")

            if path == "/users/delete":
                target  = p("username")
                current = (_cur_session or {}).get("username")
                if target == current:
                    return self.redirect("/users?error=self")
                if target == "admin" and not _can_do(_cur_session, "admin_mgmt"):
                    return self.redirect("/users?error=adminprotected")
                if target in USERS:
                    del USERS[target]
                    with SESSIONS_LOCK:
                        to_del = [t for t, s in SESSIONS.items() if s.get("username") == target]
                        for t in to_del:
                            del SESSIONS[t]
                    save_json_atomic(USERS_FILE, USERS)
                return self.redirect("/users?ok=deleted")

            if path == "/users/change_password":
                target   = p("username")
                new_pass = p("password")
                if not new_pass or target not in USERS:
                    return self.redirect("/users?error=empty")
                if target == "admin" and not _can_do(_cur_session, "admin_mgmt"):
                    return self.redirect("/users?error=adminprotected")
                USERS[target]["hash"] = _hash_pwd(new_pass)
                save_json_atomic(USERS_FILE, USERS)
                return self.redirect("/users?ok=changed")

        # ---- Multipart form data (file uploads) ────────────────────
        env = {
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE":   ctype,
            "CONTENT_LENGTH": str(length),
        }
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ=env)

        # ── RouterOS upgrade: job-based check (terminal monitor) ──────
        if path == "/api/ros-check-start":
            ips_raw    = form.getvalue("ips", "")
            cred_id_ck = form.getvalue("cred_id", "")
            channel_ck = form.getvalue("channel", "").strip()
            ips_chk = [ip.strip() for ip in ips_raw.split(",") if ip.strip()]
            if not ips_chk:
                return self._json({"ok": False, "msg": "Nessun router selezionato"})
            job_id_chk = str(uuid.uuid4())
            with JOBS_LOCK:
                JOBS[job_id_chk] = {"done": 0, "total": len(ips_chk), "results": []}
            def _run_ros_check_job(jid, ip_list, _cred_id=cred_id_ck, _channel=channel_ck):
                def _one(ip_):
                    name_ = next((rr.get("name","") for rr in ROUTERS if rr["ip"] == ip_), "")
                    if _cred_id:
                        u, p = _resolve_cred_id(_cred_id)
                    else:
                        u, p = _get_device_creds(ip_)
                    if not u:
                        return {"ip": ip_, "name": name_, "ok": False,
                                "msg": "Credenziali SSH non configurate"}
                    try:
                        ssh = _ssh_connect_creds(ip_, u, p)
                        if _channel:
                            _, _co, _ = ssh.exec_command(
                                f"/system package update set channel={_channel}")
                            _co.channel.settimeout(10)
                            try: _co.read()
                            except Exception: pass
                        # Blocking reads are safe here (thread pool worker).
                        # Use settimeout + read() instead of _read_ssh_channel
                        # to avoid the Windows polling race condition where
                        # exit_status_ready() fires before recv_ready() catches
                        # the last packet, causing an empty read.
                        _, out, _ = ssh.exec_command("/system resource print")
                        out.channel.settimeout(15)
                        try:
                            resource = out.read().decode(errors="ignore")
                        except socket.timeout:
                            resource = ""
                        _, out, _ = ssh.exec_command(
                            "/system package update check-for-updates")
                        out.channel.settimeout(40)
                        try:
                            update_out = out.read().decode(errors="ignore")
                        except socket.timeout:
                            update_out = ""
                        try: ssh.close()
                        except Exception: pass
                        ver_m  = re.search(r'version\s*:\s*(\S+)', resource, re.I)
                        cur_v  = ver_m.group(1) if ver_m else "?"
                        lat_m  = re.search(r'latest-version\s*:\s*(\S+)', update_out, re.I)
                        lat_v  = lat_m.group(1) if lat_m else "?"
                        stat_m = re.search(r'status\s*:\s*(.+)', update_out, re.I)
                        status = stat_m.group(1).strip() if stat_m else ""
                        return {"ip": ip_, "name": name_, "ok": True,
                                "current": cur_v, "latest": lat_v, "status": status}
                    except Exception as e_:
                        return {"ip": ip_, "name": name_, "ok": False, "msg": _ssh_err_str(e_)}
                ex = ThreadPoolExecutor(max_workers=min(len(ip_list), 16))
                try:
                    futs = {ex.submit(_one, ip): ip for ip in ip_list}
                    try:
                        for fut in as_completed(futs, timeout=50):
                            try: res = fut.result()
                            except Exception as e_:
                                ip_ = futs[fut]
                                name_ = next((rr.get("name","") for rr in ROUTERS
                                              if rr["ip"] == ip_), "")
                                res = {"ip": ip_, "name": name_, "ok": False, "msg": _ssh_err_str(e_)}
                            with JOBS_LOCK:
                                JOBS[jid]["results"].append(res)
                                JOBS[jid]["done"] += 1
                    except FuturesTimeout:
                        for fut, ip_ in futs.items():
                            if not fut.done():
                                name_ = next((rr.get("name","") for rr in ROUTERS
                                              if rr["ip"] == ip_), "")
                                with JOBS_LOCK:
                                    JOBS[jid]["results"].append(
                                        {"ip": ip_, "name": name_, "ok": False, "msg": "Timeout"})
                                    JOBS[jid]["done"] += 1
                finally:
                    ex.shutdown(wait=False)
            threading.Thread(target=_run_ros_check_job,
                             args=(job_id_chk, ips_chk), daemon=True).start()
            return self._json({"ok": True, "job_id": job_id_chk, "total": len(ips_chk)})

        if path == "/api/ros-install":
            ips_raw    = form.getvalue("ips", "")
            cred_id_in = form.getvalue("cred_id", "")
            channel_in = form.getvalue("channel", "").strip()
            ips = [ip.strip() for ip in ips_raw.split(",") if ip.strip()]
            if not ips:
                return self._json({"ok": False, "msg": "Nessun router selezionato"})
            def _ros_install_one(ip_, _cred_id=cred_id_in, _channel=channel_in):
                name_ = next((rr.get("name","") for rr in ROUTERS if rr["ip"] == ip_), "")
                if _cred_id:
                    u, p = _resolve_cred_id(_cred_id)
                else:
                    u, p = _get_device_creds(ip_)
                if not u:
                    return {"ip": ip_, "name": name_, "ok": False,
                            "msg": "Credenziali SSH non configurate"}
                try:
                    ssh = _ssh_connect_creds(ip_, u, p)
                    if _channel:
                        _, _ci, _ = ssh.exec_command(
                            f"/system package update set channel={_channel}")
                        _ci.channel.settimeout(10)
                        try: _ci.read()
                        except Exception: pass
                    _, out, _ = ssh.exec_command("/system package update download")
                    _read_ssh_channel(out.channel, timeout=90)
                    _, out, _ = ssh.exec_command("/system package update install")
                    _read_ssh_channel(out.channel, timeout=15)
                    try:
                        ssh.close()
                    except Exception:
                        pass
                    app_log("system", "info", f"RouterOS upgrade install avviato su {ip_}")
                    return {"ip": ip_, "name": name_, "ok": True,
                            "msg": "Update avviato — il router si riavvierà"}
                except Exception as e_:
                    return {"ip": ip_, "name": name_, "ok": False, "msg": _ssh_err_str(e_)}
            results = []
            _ex2 = ThreadPoolExecutor(max_workers=min(len(ips), 16))
            try:
                futs = {_ex2.submit(_ros_install_one, ip): ip for ip in ips}
                try:
                    for fut in as_completed(futs, timeout=120):
                        try:
                            results.append(fut.result())
                        except Exception as e_:
                            ip_ = futs[fut]
                            name_ = next((rr.get("name","") for rr in ROUTERS
                                          if rr["ip"] == ip_), "")
                            results.append({"ip": ip_, "name": name_,
                                            "ok": False, "msg": _ssh_err_str(e_)})
                except FuturesTimeout:
                    for fut, ip_ in futs.items():
                        if not fut.done():
                            name_ = next((rr.get("name","") for rr in ROUTERS
                                          if rr["ip"] == ip_), "")
                            results.append({"ip": ip_, "name": name_,
                                            "ok": False, "msg": "Timeout"})
            finally:
                _ex2.shutdown(wait=False)
            return self._json({"ok": True, "results": results})

        if path == "/api/ros-download":
            # Download only — no install/reboot
            ips_raw    = form.getvalue("ips", "")
            cred_id_dl = form.getvalue("cred_id", "")
            channel_dl = form.getvalue("channel", "").strip()
            ips = [ip.strip() for ip in ips_raw.split(",") if ip.strip()]
            if not ips:
                return self._json({"ok": False, "msg": "Nessun router selezionato"})
            def _ros_download_one(ip_, _channel=channel_dl):
                name_ = next((rr.get("name","") for rr in ROUTERS if rr["ip"] == ip_), "")
                if cred_id_dl:
                    u, p = _resolve_cred_id(cred_id_dl)
                else:
                    u, p = _get_device_creds(ip_)
                if not u:
                    return {"ip": ip_, "name": name_, "ok": False,
                            "msg": "Credenziali SSH non configurate"}
                try:
                    ssh = _ssh_connect_creds(ip_, u, p)
                    if _channel:
                        _, _cd, _ = ssh.exec_command(
                            f"/system package update set channel={_channel}")
                        _cd.channel.settimeout(10)
                        try: _cd.read()
                        except Exception: pass
                    _, out, _ = ssh.exec_command("/system package update download")
                    _read_ssh_channel(out.channel, timeout=90)
                    try: ssh.close()
                    except Exception: pass
                    app_log("system", "info", f"RouterOS download avviato su {ip_}")
                    return {"ip": ip_, "name": name_, "ok": True,
                            "msg": "Download completato — pronto per installazione"}
                except Exception as e_:
                    return {"ip": ip_, "name": name_, "ok": False, "msg": _ssh_err_str(e_)}
            results_dl = []
            _ex_dl = ThreadPoolExecutor(max_workers=min(len(ips), 16))
            try:
                futs_dl = {_ex_dl.submit(_ros_download_one, ip): ip for ip in ips}
                try:
                    for fut in as_completed(futs_dl, timeout=120):
                        try:   results_dl.append(fut.result())
                        except Exception as e_:
                            ip_ = futs_dl[fut]
                            name_ = next((rr.get("name","") for rr in ROUTERS
                                          if rr["ip"] == ip_), "")
                            results_dl.append({"ip": ip_, "name": name_,
                                               "ok": False, "msg": _ssh_err_str(e_)})
                except FuturesTimeout:
                    for fut, ip_ in futs_dl.items():
                        if not fut.done():
                            name_ = next((rr.get("name","") for rr in ROUTERS
                                          if rr["ip"] == ip_), "")
                            results_dl.append({"ip": ip_, "name": name_,
                                               "ok": False, "msg": "Timeout"})
            finally:
                _ex_dl.shutdown(wait=False)
            return self._json({"ok": True, "results": results_dl})

        # ── RouterOS upgrade via .npk upload ───────────────────────────
        if path == "/upload_npk":
            fileitem     = form["file"] if "file" in form else None
            ips_raw      = form.getvalue("ips", "")
            reboot       = bool(form.getvalue("reboot", ""))
            cred_id_npk  = form.getvalue("cred_id", "")
            if fileitem is None or not getattr(fileitem, "filename", ""):
                return self._json({"ok": False, "msg": "Nessun file selezionato"})
            ips = [ip.strip() for ip in ips_raw.split(",") if ip.strip()]
            if not ips:
                return self._json({"ok": False, "msg": "Nessun router selezionato"})
            filename_npk, local_path_npk = _save_upload(fileitem)
            job_id = str(uuid.uuid4())
            with JOBS_LOCK:
                JOBS[job_id] = {"done": 0, "total": len(ips), "results": []}
            def _npk_worker(_cred=cred_id_npk):
                for ip in ips:
                    try:
                        if _cred:
                            u_npk, p_npk = _resolve_cred_id(_cred)
                        else:
                            u_npk, p_npk = _get_device_creds(ip)
                        ssh  = _ssh_connect_creds(ip, u_npk, p_npk)
                        sftp = ssh.open_sftp()
                        sftp.put(local_path_npk, filename_npk)
                        sftp.close()
                        msg = "Pacchetto caricato"
                        if reboot:
                            ssh.exec_command("/system reboot", timeout=5)
                            msg = "Pacchetto caricato — riavvio in corso"
                        ssh.close()
                        ok = True
                    except Exception as e_:
                        ok  = False
                        msg = str(e_)
                    with JOBS_LOCK:
                        name_ = next((r.get("name","") for r in ROUTERS if r["ip"] == ip), "")
                        JOBS[job_id]["results"].append({"ip": ip, "name": name_, "ok": ok, "msg": msg})
                        JOBS[job_id]["done"] += 1
            threading.Thread(target=_npk_worker, daemon=True).start()
            return self._json({"ok": True, "job_id": job_id, "total": len(ips)})

        # ---- Upload + Import: SFTP push then :import on each router ----
        if path == "/upload_import":
            fileitem   = form["file"] if "file" in form else None
            ips_raw    = form.getvalue("ips", "")
            cred_id_ui = form.getvalue("cred_id", "")

            if fileitem is None or not getattr(fileitem, "filename", ""):
                return self._json({"ok": False, "msg": "Nessun file selezionato"})
            if not ips_raw:
                return self._json({"ok": False, "msg": "Nessun router selezionato"})

            ips       = [ip.strip() for ip in ips_raw.split(",") if ip.strip()]
            run_after = bool(form.getvalue("run_after", ""))
            filename, local_path = _save_upload(fileitem)
            job_id    = start_upload_import_job(local_path, filename, ips,
                                                run_after=run_after, cred_id=cred_id_ui)
            return self._json({"ok": True, "job_id": job_id, "total": len(ips)})

        # ---- Single router SFTP upload ----
        if path == "/upload_ssh":
            ip        = form.getvalue("ip", "")
            cred_id_f = form.getvalue("cred_id", "")
            username  = form.getvalue("username", "")
            password  = form.getvalue("password", "")
            if cred_id_f:
                username, password = _resolve_cred_id(cred_id_f)
            fileitem = form["file"] if "file" in form else None

            if not ip:
                return self._json({"ok": False, "msg": "IP mancante"})
            if fileitem is None or not getattr(fileitem, "filename", ""):
                return self._json({"ok": False, "msg": "Nessun file selezionato"})
            if not username or not password:
                return self._json({"ok": False, "msg": "Credenziali mancanti"})

            filename, local_path = _save_upload(fileitem)
            ok, msg = sftp_push(ip, username, password, local_path)
            if ok:
                name = _update_router_script(ip, local_path, filename)
                return self._json({"ok": True, "msg": "Caricato su " + ip + " (" + (name or ip) + ")"})
            else:
                return self._json({"ok": False, "msg": "Errore SSH: " + msg})

        # ---- Bulk SFTP upload by company ----
        if path == "/upload_bulk":
            fileitem       = form["file"] if "file" in form else None
            companies_raw  = form.getvalue("companies", "[]")

            if fileitem is None or not getattr(fileitem, "filename", ""):
                return self._json({"ok": False, "msg": "Nessun file selezionato"})

            try:
                companies_data = json.loads(companies_raw)
            except Exception:
                return self._json({"ok": False, "msg": "Dati aziende non validi"})

            filename, local_path = _save_upload(fileitem)

            targets = []
            for cd in companies_data:
                name     = cd.get("name", "")
                username = cd.get("username", "")
                password = cd.get("password", "")
                prefix   = COMPANIES.get(name, "")
                if not prefix or not username or not password:
                    continue
                for r in ROUTERS:
                    if r["ip"].startswith(prefix):
                        targets.append((r["ip"], username, password))

            if not targets:
                return self._json({"ok": False, "msg": "Nessun router trovato per le aziende selezionate"})

            job_id = start_bulk_job(local_path, filename, targets)
            return self._json({"ok": True, "job_id": job_id, "total": len(targets)})

        if post_path.startswith("/api/ztp/"):
            return self.handle_ztp_post(post_path, form)

        if post_path.startswith("/api/site_scan/"):
            return self.handle_site_scan_post(post_path, form)

        return self.redirect("/")

    def render_users_page(self, session=None):
        qs      = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        current = (session or {}).get("username", "")

        # Feedback banner
        banner = ""
        if "ok" in qs:
            msgs = {"added": T("Utente creato."), "deleted": T("Utente eliminato."),
                    "changed": T("Password aggiornata.")}
            banner = ('<div style="background:rgba(42,223,138,.1);border:1px solid rgba(42,223,138,.25);'
                      'border-radius:6px;padding:10px 14px;color:var(--green);font-size:12px;margin-bottom:16px;">'
                      'OK ' + msgs.get(qs["ok"][0], T("Operazione completata.")) + '</div>')
        if "error" in qs:
            errs = {
                "empty":          T("Username o password vuoti."),
                "exists":         T("Username già esistente."),
                "self":           T("Non puoi eliminare il tuo stesso account."),
                "adminprotected": ("Cannot modify the admin account — requires Admin management permission."
                                   if LANGUAGE == "en" else
                                   "Non puoi modificare l'account admin — richiede il permesso Gestione Admin."),
            }
            banner = ('<div style="background:rgba(247,79,106,.1);border:1px solid rgba(247,79,106,.25);'
                      'border-radius:6px;padding:10px 14px;color:var(--red);font-size:12px;margin-bottom:16px;">'
                      '! ' + errs.get(qs["error"][0], T("Errore sconosciuto.")) + '</div>')

        # Users table
        lang_en = LANGUAGE == "en"
        rows = ""
        for uname, udata in USERS.items():
            role      = udata.get("role", "viewer")
            if role == "admin":
                role_html = '<span class="pill pill-green">ADMIN</span>'
            elif role == "manager":
                role_html = '<span class="pill pill-blue">MANAGER</span>'
            elif role == "technician":
                role_html = '<span class="pill pill-blue">TECH</span>'
            elif role == "custom":
                perms     = udata.get("permissions", {})
                perm_tags = " ".join(
                    f'<span style="font-size:9px;background:var(--accent3);color:var(--accent2);'
                    f'border:1px solid var(--accent3);border-radius:3px;padding:1px 5px;white-space:nowrap;">'
                    f'{lbl_en if lang_en else lbl_it}</span>'
                    for k, lbl_it, lbl_en in CUSTOM_PERMS if perms.get(k)
                ) or '<span style="color:var(--text3);font-size:10px;">—</span>'
                role_html = (
                    f'<span class="pill pill-gray" style="margin-right:4px;">CUSTOM</span>'
                    f'<div style="display:flex;flex-wrap:wrap;gap:3px;margin-top:3px;">{perm_tags}</div>'
                )
            else:
                role_html = '<span class="pill pill-gray">VIEWER</span>'
            is_self    = uname == current
            is_disabled = udata.get("disabled", False)
            can_touch_admin = uname != "admin" or _can_do(session, "admin_mgmt")
            dis_btn = ""
            if not is_self and can_touch_admin:
                _dis_lbl = ("Enable" if is_disabled else "Disable") if lang_en else ("Abilita" if is_disabled else "Disabilita")
                _dis_cls = "btn btn-success" if is_disabled else "btn"
                dis_btn  = (f'<button class="{_dis_cls}" style="padding:2px 7px;font-size:10px;" '
                            f'onclick="toggleDisabled(\'{uname}\')">{_dis_lbl}</button>')
            del_btn = ""
            if not is_self and can_touch_admin:
                del_btn = (f'<form method="POST" action="/users/delete" style="display:inline;">'
                           f'<input type="hidden" name="username" value="{uname}">'
                           f'<button class="btn btn-danger" onclick="return confirm(\'Eliminare {uname}?\')">x Elimina</button>'
                           f'</form>')
            you_badge = f' <span style="font-size:10px;color:var(--text3);">{T("(tu)")}</span>' if is_self else ''
            dis_badge = (' <span class="pill pill-red" style="font-size:9px;letter-spacing:.3px;">DISABLED</span>'
                        if is_disabled else "")

            # MFA cell
            if MFA_AVAILABLE:
                mfa_on  = udata.get("mfa_enabled", False)
                has_sec = bool(udata.get("totp_secret"))
                if mfa_on and has_sec:
                    mfa_badge = '<span class="pill pill-green">2FA</span>'
                    mfa_hint  = ''
                elif mfa_on:
                    mfa_badge = ('<span class="pill pill-yellow">'
                                 + ('Setup needed' if lang_en else 'Setup richiesto')
                                 + '</span>')
                    mfa_hint  = ''
                else:
                    mfa_badge = '<span class="pill pill-gray">' + ('Off' if lang_en else 'Off') + '</span>'
                    mfa_hint  = ''
                if can_touch_admin:
                    toggle_lbl = ('Disable' if mfa_on else 'Enable') if lang_en else ('Disabilita' if mfa_on else 'Abilita')
                    toggle_val = '0' if mfa_on else '1'
                    toggle_cls = 'btn btn-danger' if mfa_on else 'btn btn-success'
                    reset_btn  = (f'<button class="btn" style="padding:2px 7px;font-size:10px;" '
                                  f'onclick="mfaReset(\'{uname}\')">'
                                  + 'Reset QR'
                                  + '</button>') if mfa_on and has_sec else ''
                    mfa_buttons = (f'<button class="{toggle_cls}" style="padding:2px 7px;font-size:10px;margin-left:6px;" '
                                   f'onclick="mfaToggle(\'{uname}\',{toggle_val})">{toggle_lbl}</button>'
                                   + reset_btn)
                else:
                    mfa_buttons = ''
                mfa_cell = f'{mfa_badge}{mfa_hint}{mfa_buttons}'
            else:
                mfa_cell = '<span style="color:var(--text3);font-size:10px;">N/A</span>'

            pwd_form = (
                f'<form method="POST" action="/users/change_password" style="display:flex;gap:6px;align-items:center;">'
                f'<input type="hidden" name="username" value="{uname}">'
                f'<input type="password" name="password" placeholder="{T("Nuova password…")}" style="width:160px;">'
                f'<button class="btn">{T("Cambia")}</button>'
                f'</form>'
            ) if can_touch_admin else (
                f'<span style="font-size:10px;color:var(--text3);">—</span>'
            )
            rows += (f'<tr>'
                     f'<td style="color:var(--text);font-weight:600">{uname}{you_badge}{dis_badge}</td>'
                     f'<td>{role_html}</td>'
                     f'<td>{mfa_cell}</td>'
                     f'<td>{pwd_form}</td>'
                     f'<td style="white-space:nowrap;">{dis_btn} {del_btn}</td>'
                     f'</tr>')

        # Build permissions table — 5 separate columns
        # (section, admin, manager, technician, custom-label, viewer)
        _PERM_ROWS = [
            ("Dashboard",                                     True,  True,  True,  True),
            ("Site Manager",                                  True,  True,  True,  True),
            ("Backup",                                        True,  True,  False, False),
            ("Network Discovery",                             True,  True,  True,  True),
            (T("Statistiche"),                                True,  True,  True,  True),
            (T("Utenti"),                                     True,  True,  False, False),
            ("Log",                                           True,  True,  True,  True),
            ("Clear Log" if lang_en else "Svuota Log",        True,  True,  False, False),
            (T("Impostazioni"),                               True,  False, False, False),
            ("Script Upload",                                 True,  False, False, False),
            (T("Upgrade RouterOS"),                           True,  True,  False, False),
            ("Credentials",                                   True,  True,  True,  False),
        ]
        _ok  = '<span style="color:var(--green);font-size:15px;">&#10003;</span>'
        _no  = '<span style="color:var(--text3);font-size:13px;">&#8212;</span>'
        _perm_rows_html = "".join(
            f'<tr style="border-bottom:1px solid var(--border);">'
            f'<td style="padding:9px 14px;color:var(--text);font-weight:500;">{lbl}</td>'
            f'<td style="padding:9px 14px;text-align:center;">{_ok}</td>'
            f'<td style="padding:9px 14px;text-align:center;">{_ok if mgr else _no}</td>'
            f'<td style="padding:9px 14px;text-align:center;">{_ok if tech else _no}</td>'
            f'<td style="padding:9px 14px;text-align:center;">{_ok if viewer else _no}</td>'
            f'</tr>'
            for lbl, _adm, mgr, tech, viewer in _PERM_ROWS
        )
        _th  = ('padding:8px 14px;font-weight:700;font-size:9px;text-transform:uppercase;'
                'letter-spacing:.5px;border-bottom:1px solid var(--border);')
        _perm_table_html = (
            f'<div style="margin-top:20px;">'
            f'<div style="font-size:11px;font-weight:700;color:var(--text2);text-transform:uppercase;'
            f'letter-spacing:.7px;margin-bottom:10px;">{T("Permessi per ruolo")}</div>'
            f'<div style="background:var(--bg2);border:1px solid var(--border);border-radius:10px;overflow:hidden;">'
            f'<table style="width:100%;border-collapse:collapse;font-size:11px;">'
            f'<thead><tr style="background:var(--bg3);">'
            f'<th style="{_th}text-align:left;color:var(--text2);">{T("Sezione")}</th>'
            f'<th style="{_th}text-align:center;color:#4f8ef7;">Admin</th>'
            f'<th style="{_th}text-align:center;color:#16a34a;">Manager</th>'
            f'<th style="{_th}text-align:center;color:#0891b2;">Technician</th>'
            f'<th style="{_th}text-align:center;color:var(--text2);">Viewer</th>'
            f'</tr></thead>'
            f'<tbody>{_perm_rows_html}</tbody>'
            f'</table></div></div>'
        )

        content = f"""
{banner}

<div style="display:grid;grid-template-columns:1fr 360px;gap:20px;align-items:start;">

  <!-- Tabella utenti -->
  <div class="card">
    <div class="card-header">
      <span>{T("Utenti registrati")} ({len(USERS)})</span>
    </div>
    <table>
      <thead><tr>
        <th>Username</th><th>{T("Ruolo")}</th><th>2FA</th><th>{T("Cambia Password")}</th><th>{T("Azioni")}</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>

  <!-- Form nuovo utente -->
  <div class="card">
    <div class="card-header"><span>{T("Nuovo utente")}</span></div>
    <div class="card-body">
      <form method="POST" action="/users/add" id="addUserForm">
        <div style="margin-bottom:12px;">
          <label style="font-size:11px;color:var(--text2);display:block;margin-bottom:4px;">Username</label>
          <input type="text" name="username" required placeholder="{T('es. utente1')}" style="width:100%;"
                 autocomplete="off" pattern="[a-zA-Z0-9_\\-]+" title="{T('Solo lettere, numeri, _ e -')}">
        </div>
        <div style="margin-bottom:12px;">
          <label style="font-size:11px;color:var(--text2);display:block;margin-bottom:4px;">{T("Password")}</label>
          <input type="password" name="password" required placeholder="{T('Min. 8 caratteri')}"
                 minlength="8" style="width:100%;" autocomplete="new-password">
        </div>
        <div style="margin-bottom:10px;">
          <label style="font-size:11px;color:var(--text2);display:block;margin-bottom:4px;">{T("Ruolo")}</label>
          <select name="role" id="newUserRole" style="width:100%;" onchange="toggleCustomPerms(this.value)">
            <option value="viewer" selected>{T("Viewer — solo lettura")}</option>
            <option value="manager">{'Manager — backup, credentials, log' if lang_en else 'Manager — backup, credenziali, log'}</option>
            <option value="technician">{'Technician — credentials' if lang_en else 'Technician — credenziali'}</option>
            <option value="custom">{'Custom — choose permissions' if lang_en else 'Custom — scegli permessi'}</option>
            <option value="admin">{T("Admin — accesso completo")}</option>
          </select>
        </div>
        <div id="customPermsBox" style="display:none;margin-bottom:14px;padding:10px 12px;
          background:var(--bg3);border:1px solid var(--border2);border-radius:8px;">
          <div style="font-size:10px;font-weight:700;color:var(--text2);text-transform:uppercase;
            letter-spacing:.6px;margin-bottom:8px;">{'Permissions' if lang_en else 'Permessi'}</div>
          {''.join(
            f'<label style="display:flex;align-items:center;gap:7px;font-size:11px;color:var(--text);'
            f'margin-bottom:6px;cursor:pointer;">'
            f'<input type="checkbox" name="perm_{key}" value="1" style="accent-color:var(--accent);">'
            f'{lbl_en if lang_en else lbl_it}</label>'
            for key, lbl_it, lbl_en in CUSTOM_PERMS
          )}
        </div>
        <button type="submit" class="btn btn-primary" style="width:100%;justify-content:center;padding:9px;">
          {T("Crea utente")}
        </button>
      </form>
    </div>
  </div>

</div>


{_perm_table_html}

<div style="margin-top:14px;padding:14px 18px;background:var(--bg2);border:1px solid var(--border);
     border-radius:10px;font-size:11px;color:var(--text2);line-height:1.85;">
  <strong style="color:var(--text);display:block;margin-bottom:8px;font-size:12px;letter-spacing:.2px;">
    {'Notes' if lang_en else 'Note'}
  </strong>
  <ul style="margin:0;padding-left:18px;display:flex;flex-direction:column;gap:5px;">
    <li>
      {'Active sessions are immediately invalidated when a user is deleted or disabled. You cannot delete or disable your own account.' if lang_en else 'Le sessioni attive vengono invalidate immediatamente quando un utente viene eliminato o disabilitato. Non è possibile eliminare o disabilitare il proprio account.'}
    </li>
    <li>
      {'Account passwords are hashed with <strong style="color:var(--text);">PBKDF2-HMAC-SHA256</strong> — 200,000 iterations with a unique random salt per account. They are never stored in plaintext.' if lang_en else 'Le password degli account vengono derivate con <strong style="color:var(--text);">PBKDF2-HMAC-SHA256</strong> — 200 000 iterazioni con un salt casuale univoco per ogni account. Non vengono mai memorizzate in chiaro.'}
    </li>
    <li>
      {'SSH credentials (username and password) are symmetrically encrypted with <strong style="color:var(--text);">AES-128 (Fernet)</strong>. The encryption key is generated locally at first startup and never transmitted.' if lang_en else 'Le credenziali SSH (username e password) sono cifrate simmetricamente con <strong style="color:var(--text);">AES-128 (Fernet)</strong>. La chiave di cifratura viene generata localmente al primo avvio e non viene mai trasmessa.'}
    </li>
  </ul>
</div>

<script>
function toggleCustomPerms(role) {{
  document.getElementById('customPermsBox').style.display = role === 'custom' ? 'block' : 'none';
}}
async function toggleDisabled(username) {{
  const isDisabled = document.querySelector('[data-uname="' + username + '"]')?.dataset.disabled === 'true';
  const msg = isDisabled
    ? {json.dumps("Enable account for " if lang_en else "Riabilitare l'account di ")} + username + '?'
    : {json.dumps("Disable account for " if lang_en else "Disabilitare l'account di ")} + username + '?';
  if (!confirm(msg)) return;
  const r = await fetch('/users/toggle_disabled', {{method:'POST',
    headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
    body:'username='+encodeURIComponent(username)}});
  const j = await r.json();
  if (j.ok) location.reload(); else alert(j.msg);
}}
async function mfaToggle(username, enable) {{
  const _en = {json.dumps("Enable 2FA for " if lang_en else "Abilitare 2FA per ")};
  const _qr = {json.dumps("? The user will need to scan a QR code on next login." if lang_en else "? L'utente dovra scansionare un QR code al prossimo accesso.")};
  const _di = {json.dumps("Disable 2FA for " if lang_en else "Disabilitare 2FA per ")};
  const _rm = {json.dumps("? The TOTP secret will be removed." if lang_en else "? Il segreto TOTP verra rimosso.")};
  const msg = enable ? (_en + username + _qr) : (_di + username + _rm);
  if (!confirm(msg)) return;
  const r = await fetch('/users/mfa_toggle', {{method:'POST',
    headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
    body:'username='+encodeURIComponent(username)+'&enabled='+enable}});
  const j = await r.json();
  if (j.ok) location.reload(); else alert('Error: ' + j.msg);
}}
async function mfaReset(username) {{
  const _rs = {json.dumps("Reset TOTP for " if lang_en else "Resettare il TOTP per ")};
  const _rq = {json.dumps("? They will need to scan a new QR code on next login." if lang_en else "? Dovra scansionare un nuovo QR code al prossimo accesso.")};
  if (!confirm(_rs + username + _rq)) return;
  const r = await fetch('/users/mfa_reset', {{method:'POST',
    headers:{{'Content-Type':'application/x-www-form-urlencoded'}},
    body:'username='+encodeURIComponent(username)}});
  const j = await r.json();
  if (j.ok) location.reload(); else alert('Error: ' + j.msg);
}}
</script>
"""
        return self._page_shell("Gestione Utenti", content, session=session, page_key="users")

    # ------------------------------------------------------------------
    def render_mfa_verify_page(self):
        qs    = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        err   = "error" in qs
        lang_en = LANGUAGE == "en"
        _dark = ' data-theme="dark"' if _app_cfg.get("dark_mode") else ''
        err_html = (
            '<div style="background:rgba(220,38,38,.08);border:1px solid rgba(220,38,38,.3);'
            'border-radius:6px;padding:10px 14px;color:var(--red);font-size:12px;margin-bottom:16px;">'
            + ('! Invalid code. Try again.' if lang_en else '! Codice non valido. Riprova.')
            + '</div>'
        ) if err else ""
        title  = "Two-factor authentication"      if lang_en else "Autenticazione a due fattori"
        sub    = "Enter the 6-digit code from your authenticator app." if lang_en else "Inserisci il codice a 6 cifre dalla tua app di autenticazione."
        label  = "Verification code"              if lang_en else "Codice di verifica"
        ph     = "000 000"
        btn    = "Verify →"                        if lang_en else "Verifica →"
        back   = "← Back to login"                if lang_en else "← Torna al login"
        return f"""<!DOCTYPE html>
<html lang="{LANGUAGE}"{_dark}>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ROSM — 2FA</title>
{FAVICON_TAG}
<style>
{COMMON_CSS}
html,body{{height:100%;margin:0;display:flex;align-items:center;justify-content:center;
  background:var(--accent) !important;}}
.mfa-wrap{{width:400px;max-width:96vw;}}
.mfa-logo{{width:100%;background:var(--accent);padding:24px 40px 20px;
  border-radius:16px 16px 0 0;text-align:center;border-bottom:3px solid var(--red-brand);}}
.mfa-logo .rosm-word{{font-family:var(--sans);font-size:32px;font-weight:900;
  color:var(--red-brand);letter-spacing:-1px;line-height:1;}}
.mfa-logo .mfa-sub{{font-family:var(--sans);font-size:11px;font-weight:600;
  color:rgba(255,255,255,.8);margin-top:6px;letter-spacing:.5px;text-transform:uppercase;}}
.mfa-card{{width:100%;background:var(--bg2);border:1px solid var(--border2);
  border-radius:0 0 16px 16px;padding:28px 36px 24px;box-shadow:0 16px 56px rgba(0,0,0,.18);}}
.mfa-code-input{{width:100%;padding:14px;font-size:24px;font-family:var(--mono);
  text-align:center;letter-spacing:8px;border-radius:8px;}}
.mfa-footer{{margin-top:14px;text-align:center;font-size:10px;color:rgba(255,255,255,.5);}}
</style>
</head>
<body>
<div class="mfa-wrap">
  <div class="mfa-logo">
    <div class="rosm-word">ROSM</div>
    <div class="mfa-sub">{title}</div>
  </div>
  <div class="mfa-card">
    {err_html}
    <p style="font-size:12px;color:var(--text2);margin-bottom:20px;line-height:1.5;">{sub}</p>
    <form method="POST" action="/mfa/verify">
      <div style="margin-bottom:18px;">
        <label style="display:block;font-size:10px;font-weight:700;color:var(--text2);
          text-transform:uppercase;letter-spacing:.6px;margin-bottom:7px;">{label}</label>
        <input type="text" name="code" class="mfa-code-input"
               inputmode="numeric" pattern="[0-9 ]{{6,7}}" maxlength="7"
               autocomplete="one-time-code" autofocus placeholder="{ph}" required>
      </div>
      <button type="submit"
        style="width:100%;padding:11px;border-radius:8px;background:var(--accent);
               border:none;color:#fff;font-family:var(--sans);font-size:14px;
               font-weight:700;cursor:pointer;letter-spacing:.3px;">{btn}</button>
    </form>
    <div style="text-align:center;margin-top:14px;">
      <a href="/login" style="font-size:11px;color:var(--text2);text-decoration:none;opacity:.75;">{back}</a>
    </div>
  </div>
  <div class="mfa-footer">ROSM v{APP_VERSION} {APP_STAGE}</div>
</div>
</body>
</html>"""

    # ------------------------------------------------------------------
    def render_mfa_setup_page(self, secret: str):
        qs    = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        err   = "error" in qs
        lang_en = LANGUAGE == "en"
        _dark = ' data-theme="dark"' if _app_cfg.get("dark_mode") else ''
        err_html = (
            '<div style="background:rgba(220,38,38,.08);border:1px solid rgba(220,38,38,.3);'
            'border-radius:6px;padding:10px 14px;color:var(--red);font-size:12px;margin-bottom:14px;">'
            + ('! Invalid code. Make sure your authenticator is in sync and try again.'
               if lang_en else
               '! Codice non valido. Assicurati che l\'app sia sincronizzata e riprova.')
            + '</div>'
        ) if err else ""
        uri    = _mfa_provisioning_uri("ROSM", secret)
        qr_svg = _mfa_qr_svg(uri)
        title  = "Set up two-factor authentication" if lang_en else "Configura l'autenticazione a due fattori"
        step1  = "1. Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.)" if lang_en else "1. Scansiona questo QR code con la tua app di autenticazione (Google Authenticator, Authy, ecc.)"
        step2  = "2. Enter the 6-digit code shown by the app to confirm setup." if lang_en else "2. Inserisci il codice a 6 cifre mostrato dall'app per confermare la configurazione."
        manual_lbl = "Can't scan? Enter this key manually:" if lang_en else "Non riesci a scansionare? Inserisci questa chiave manualmente:"
        label  = "Verification code"              if lang_en else "Codice di verifica"
        btn    = "Confirm and continue →"          if lang_en else "Conferma e continua →"
        back   = "← Back to login"                if lang_en else "← Torna al login"
        return f"""<!DOCTYPE html>
<html lang="{LANGUAGE}"{_dark}>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ROSM — 2FA Setup</title>
{FAVICON_TAG}
<style>
{COMMON_CSS}
html,body{{height:100%;margin:0;display:flex;align-items:center;justify-content:center;
  background:var(--accent) !important;overflow-y:auto;}}
.mfa-wrap{{width:460px;max-width:96vw;margin:auto;}}
.mfa-logo{{width:100%;background:var(--accent);padding:22px 36px 18px;
  border-radius:16px 16px 0 0;text-align:center;border-bottom:3px solid var(--red-brand);}}
.mfa-logo .rosm-word{{font-family:var(--sans);font-size:28px;font-weight:900;
  color:var(--red-brand);letter-spacing:-1px;}}
.mfa-logo .mfa-sub{{font-family:var(--sans);font-size:10px;font-weight:600;
  color:rgba(255,255,255,.8);margin-top:5px;letter-spacing:.5px;text-transform:uppercase;}}
.mfa-card{{width:100%;background:var(--bg2);border:1px solid var(--border2);
  border-radius:0 0 16px 16px;padding:24px 32px 22px;box-shadow:0 16px 56px rgba(0,0,0,.18);}}
.qr-wrap{{display:flex;justify-content:center;margin:14px 0;}}
.qr-wrap svg{{border-radius:8px;border:6px solid #fff;}}
.secret-box{{background:var(--bg3);border:1px solid var(--border2);border-radius:6px;
  padding:8px 12px;font-family:var(--mono);font-size:12px;color:var(--accent2);
  letter-spacing:2px;text-align:center;word-break:break-all;margin-bottom:14px;}}
.mfa-code-input{{width:100%;padding:12px;font-size:20px;font-family:var(--mono);
  text-align:center;letter-spacing:8px;border-radius:8px;}}
.step-text{{font-size:12px;color:var(--text2);margin-bottom:10px;line-height:1.5;}}
.mfa-footer{{margin-top:12px;text-align:center;font-size:10px;color:rgba(255,255,255,.5);}}
</style>
</head>
<body>
<div class="mfa-wrap">
  <div class="mfa-logo">
    <div class="rosm-word">ROSM</div>
    <div class="mfa-sub">{title}</div>
  </div>
  <div class="mfa-card">
    {err_html}
    <p class="step-text">{step1}</p>
    <div class="qr-wrap">{qr_svg}</div>
    <p class="step-text" style="margin-top:2px;">{manual_lbl}</p>
    <div class="secret-box">{secret}</div>
    <p class="step-text">{step2}</p>
    <form method="POST" action="/mfa/setup">
      <div style="margin-bottom:16px;">
        <label style="display:block;font-size:10px;font-weight:700;color:var(--text2);
          text-transform:uppercase;letter-spacing:.6px;margin-bottom:7px;">{label}</label>
        <input type="text" name="code" class="mfa-code-input"
               inputmode="numeric" pattern="[0-9 ]{{6,7}}" maxlength="7"
               autocomplete="one-time-code" autofocus placeholder="000 000" required>
      </div>
      <button type="submit"
        style="width:100%;padding:11px;border-radius:8px;background:var(--accent);
               border:none;color:#fff;font-family:var(--sans);font-size:13px;
               font-weight:700;cursor:pointer;letter-spacing:.3px;">{btn}</button>
    </form>
    <div style="text-align:center;margin-top:12px;">
      <a href="/login" style="font-size:11px;color:var(--text2);text-decoration:none;opacity:.75;">{back}</a>
    </div>
  </div>
  <div class="mfa-footer">ROSM v{APP_VERSION} {APP_STAGE}</div>
</div>
</body>
</html>"""

    def render_login_page(self, error=False):
        qs        = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        err_type  = (qs.get("error") or [""])[0]
        _login_next = (qs.get("next") or [""])[0]
        # Sanitise: only allow local paths starting with /
        if not _login_next.startswith("/"):
            _login_next = ""
        _next_hidden = (
            f'<input type="hidden" name="next" value="{_login_next}">'
            if _login_next else ""
        )
        if err_type == "disabled":
            _err_msg = ("Account disabled. Contact the administrator."
                        if LANGUAGE == "en" else "Account disabilitato. Contatta l'amministratore.")
        elif err_type:
            _err_msg = T("Credenziali non valide. Riprova.")
        else:
            _err_msg = ""
        err_html = (
            '<div style="background:rgba(192,57,43,.08);border:1px solid rgba(192,57,43,.3);'
            'border-radius:6px;padding:10px 14px;color:var(--red);font-size:12px;margin-bottom:16px;">'
            f'! {_err_msg}</div>'
        ) if _err_msg else ""
        lang_html = LANGUAGE  # "en" or "it"
        _dark = ' data-theme="dark"' if _app_cfg.get("dark_mode") else ''
        return f"""<!DOCTYPE html>
<html lang="{lang_html}"{_dark}>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ROSM — {T("Accesso")}</title>
{FAVICON_TAG}
<style>
{COMMON_CSS}
html,body{{height:100%;margin:0;display:flex;align-items:center;justify-content:center;
  background:var(--accent) !important;}}
.login-wrap{{
  display:flex;flex-direction:column;align-items:center;gap:0;
  width:420px;max-width:96vw;
}}
.login-logo{{
  width:100%;background:var(--accent);
  padding:32px 40px 24px;
  border-radius:16px 16px 0 0;
  text-align:center;
  border-bottom:3px solid var(--red-brand);
}}
.login-logo .rosm-word{{
  font-family:var(--sans);font-size:42px;font-weight:900;
  color:var(--red-brand);letter-spacing:-1px;line-height:1;
}}
.login-logo .rosm-full{{
  font-family:var(--sans);font-size:13px;font-weight:500;
  color:rgba(255,255,255,.7);margin-top:4px;letter-spacing:.5px;
}}
.login-card{{
  width:100%;background:var(--bg2);border:1px solid var(--border2);
  border-radius:0 0 16px 16px;padding:32px 40px 28px;
  box-shadow:0 16px 56px rgba(0,0,0,.18);
}}
.field{{margin-bottom:14px;}}
.field label{{display:block;font-size:11px;font-weight:600;color:var(--text2);
  margin-bottom:5px;text-transform:uppercase;letter-spacing:.6px;}}
.field input{{width:100%;padding:10px 13px;font-size:13px;border-radius:7px;}}
.submit-btn{{
  width:100%;padding:11px;margin-top:8px;border-radius:8px;
  background:var(--accent);border:none;color:#fff;font-family:var(--sans);
  font-size:14px;font-weight:700;cursor:pointer;transition:background .15s;
  letter-spacing:.3px;
}}
.submit-btn:hover{{background:var(--accent2);}}
.login-footer{{margin-top:16px;text-align:center;font-size:10px;color:rgba(255,255,255,.5);}}
</style>
</head>
<body>
<div class="login-wrap">
  <div class="login-logo">
    <div class="rosm-word">ROSM</div>
    <div class="rosm-full">Router OS Manager</div>
  </div>
  <div class="login-card">
    {err_html}
    <form method="POST" action="/login">
      {_next_hidden}
      <div class="field">
        <label>{T("Username")}</label>
        <input type="text" name="username" autocomplete="username" autofocus required>
      </div>
      <div class="field">
        <label>{T("Password")}</label>
        <input type="password" name="password" autocomplete="current-password" required>
      </div>
      <button type="submit" class="submit-btn">{T("Accedi →")}</button>
    </form>
    <div style="text-align:center;margin-top:14px;">
      <a href="/forgot-password" style="font-size:11px;color:var(--text2);text-decoration:none;opacity:.75;">
        {T("Password dimenticata?")}
      </a>
    </div>
    <!-- Language switcher -->
    <div style="display:flex;justify-content:center;align-items:center;gap:0;margin-top:18px;
      border-top:1px solid var(--border);padding-top:14px;">
      <a href="/language/it" style="padding:4px 14px;font-size:11px;font-weight:700;
        text-decoration:none;border-radius:5px 0 0 5px;border:1px solid var(--border2);
        background:{'var(--accent)' if LANGUAGE=='it' else 'transparent'};
        color:{'#fff' if LANGUAGE=='it' else 'var(--text2)'};">IT</a>
      <a href="/language/en" style="padding:4px 14px;font-size:11px;font-weight:700;
        text-decoration:none;border-radius:0 5px 5px 0;border:1px solid var(--border2);
        border-left:none;
        background:{'var(--accent)' if LANGUAGE=='en' else 'transparent'};
        color:{'#fff' if LANGUAGE=='en' else 'var(--text2)'};">EN</a>
    </div>
  </div>
  <div class="login-footer">by Jacopo Cipriani &nbsp;·&nbsp; v{APP_VERSION} {APP_STAGE} &nbsp;·&nbsp; {T("Sessione 24h")}</div>
</div>
</body>
</html>"""

    # ──────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────
    # Guide page
    # ──────────────────────────────────────────────────────────
    def render_guide_page(self, session=None):
        lang_en = LANGUAGE == "en"
        role    = (session or {}).get("role", "viewer")

        def sec(anchor, color, icon_svg, title, subtitle, items, tip=None):
            """Render a guide section card."""
            items_html = "".join(
                f'<li style="padding:4px 0;border-bottom:1px solid var(--border);font-size:12px;">'
                f'<span style="color:{color};font-weight:700;margin-right:6px;">›</span>{it}</li>'
                for it in items
            )
            tip_html = (
                f'<div style="margin-top:14px;padding:10px 14px;background:{color}11;'
                f'border-left:3px solid {color};border-radius:0 6px 6px 0;font-size:11px;'
                f'color:var(--text2);line-height:1.7;">'
                f'<strong style="color:{color};">Tip</strong> — {tip}</div>'
            ) if tip else ""
            return (
                f'<div id="{anchor}" class="gd-card" style="border-top:3px solid {color};">'
                f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">'
                f'<div style="width:38px;height:38px;border-radius:9px;background:{color};'
                f'display:flex;align-items:center;justify-content:center;flex-shrink:0;">'
                f'{icon_svg}</div>'
                f'<div><div style="font-size:15px;font-weight:800;color:var(--text);">{title}</div>'
                f'<div style="font-size:11px;color:var(--text2);margin-top:1px;">{subtitle}</div>'
                f'</div></div>'
                f'<ul style="margin:0;padding-left:0;list-style:none;">{items_html}</ul>'
                f'{tip_html}'
                f'</div>'
            )

        # ── SVG icons (small, for section headers) ────────────────────
        ico_dash   = '<svg viewBox="0 0 20 20" fill="none" width="22" height="22"><rect x="2" y="2" width="7" height="7" rx="1.5" fill="white"/><rect x="11" y="2" width="7" height="7" rx="1.5" fill="white" opacity=".7"/><rect x="2" y="11" width="7" height="7" rx="1.5" fill="white" opacity=".7"/><rect x="11" y="11" width="7" height="7" rx="1.5" fill="white" opacity=".5"/></svg>'
        ico_site   = '<svg viewBox="0 0 20 20" fill="none" width="22" height="22"><circle cx="10" cy="6" r="3" stroke="white" stroke-width="1.8"/><path d="M4 17c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="white" stroke-width="1.8" stroke-linecap="round"/><line x1="14" y1="12" x2="18" y2="8" stroke="white" stroke-width="1.5" stroke-linecap="round"/><circle cx="18" cy="7" r="2" fill="white" opacity=".6"/></svg>'
        ico_backup = '<svg viewBox="0 0 20 20" fill="none" width="22" height="22"><path d="M10 3v9" stroke="white" stroke-width="2" stroke-linecap="round"/><path d="M6 8l4 4 4-4" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><rect x="3" y="14" width="14" height="3" rx="1.5" fill="white" opacity=".5"/></svg>'
        ico_disc   = '<svg viewBox="0 0 20 20" fill="none" width="22" height="22"><circle cx="10" cy="10" r="7" stroke="white" stroke-width="1.8"/><circle cx="10" cy="10" r="2.5" fill="white"/><line x1="10" y1="3" x2="10" y2="6" stroke="white" stroke-width="1.8" stroke-linecap="round"/><line x1="10" y1="14" x2="10" y2="17" stroke="white" stroke-width="1.8" stroke-linecap="round"/><line x1="3" y1="10" x2="6" y2="10" stroke="white" stroke-width="1.8" stroke-linecap="round"/><line x1="14" y1="10" x2="17" y2="10" stroke="white" stroke-width="1.8" stroke-linecap="round"/></svg>'
        ico_script = '<svg viewBox="0 0 20 20" fill="none" width="22" height="22"><rect x="3" y="3" width="14" height="14" rx="2" stroke="white" stroke-width="1.8"/><path d="M7 7l3 3-3 3" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><line x1="12" y1="13" x2="16" y2="13" stroke="white" stroke-width="1.8" stroke-linecap="round"/></svg>'
        ico_creds  = '<svg viewBox="0 0 20 20" fill="none" width="22" height="22"><rect x="6" y="8" width="8" height="8" rx="1.5" stroke="white" stroke-width="1.8"/><path d="M8 8V6a2 2 0 014 0v2" stroke="white" stroke-width="1.8" stroke-linecap="round"/><circle cx="10" cy="12" r="1.2" fill="white"/></svg>'
        ico_log    = '<svg viewBox="0 0 20 20" fill="none" width="22" height="22"><rect x="4" y="3" width="12" height="14" rx="2" stroke="white" stroke-width="1.8"/><line x1="7" y1="8" x2="13" y2="8" stroke="white" stroke-width="1.5" stroke-linecap="round"/><line x1="7" y1="11" x2="11" y2="11" stroke="white" stroke-width="1.5" stroke-linecap="round" opacity=".7"/><line x1="7" y1="14" x2="13" y2="14" stroke="white" stroke-width="1.5" stroke-linecap="round" opacity=".5"/></svg>'
        ico_users  = '<svg viewBox="0 0 20 20" fill="none" width="22" height="22"><circle cx="8" cy="7" r="3" stroke="white" stroke-width="1.8"/><path d="M2 17c0-3.3 2.7-6 6-6" stroke="white" stroke-width="1.8" stroke-linecap="round"/><circle cx="15" cy="10" r="2" stroke="white" stroke-width="1.5"/><path d="M11.5 17c0-2 1.6-3.5 3.5-3.5s3.5 1.5 3.5 3.5" stroke="white" stroke-width="1.5" stroke-linecap="round"/></svg>'
        ico_sett   = '<svg viewBox="0 0 20 20" fill="none" width="22" height="22"><circle cx="10" cy="10" r="2.5" stroke="white" stroke-width="1.8"/><path d="M10 2v2M10 16v2M2 10h2M16 10h2M4.2 4.2l1.4 1.4M14.4 14.4l1.4 1.4M4.2 15.8l1.4-1.4M14.4 5.6l1.4-1.4" stroke="white" stroke-width="1.5" stroke-linecap="round"/></svg>'
        ico_start  = '<svg viewBox="0 0 20 20" fill="none" width="22" height="22"><circle cx="10" cy="10" r="8" stroke="white" stroke-width="1.8"/><path d="M7 10l2.5 2.5L13 7" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>'
        ico_faq    = '<svg viewBox="0 0 20 20" fill="none" width="22" height="22"><circle cx="10" cy="10" r="8" stroke="white" stroke-width="1.8"/><path d="M10 13v1" stroke="white" stroke-width="2" stroke-linecap="round"/><path d="M10 7a2 2 0 011.732 3C11.2 10.5 10 11 10 12" stroke="white" stroke-width="1.7" stroke-linecap="round"/></svg>'
        ico_trouble= '<svg viewBox="0 0 20 20" fill="none" width="22" height="22"><path d="M10 3L2 17h16L10 3z" stroke="white" stroke-width="1.8" stroke-linejoin="round"/><path d="M10 9v4" stroke="white" stroke-width="2" stroke-linecap="round"/><circle cx="10" cy="14.5" r="1" fill="white"/></svg>'
        ico_upgrade= '<svg viewBox="0 0 20 20" fill="none" width="22" height="22"><path d="M10 14V6" stroke="white" stroke-width="2" stroke-linecap="round"/><path d="M6 10l4-4 4 4" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="M4 16h12" stroke="white" stroke-width="1.6" stroke-linecap="round" opacity=".6"/></svg>'

        # ── Sections ─────────────────────────────────────────────────
        if lang_en:
            sections = [
                sec("dashboard", "#4f8ef7", ico_dash,
                    "Dashboard",
                    "The screen you'll look at most every day",
                    [
                        "This is your main control panel. Once you've imported routers from Network Discovery, they all show up here in a table with their real-time status.",
                        "Status colors: <strong>green = ONLINE</strong> (responded to the last ping), <strong>red = OFFLINE</strong> (no response), <strong>grey = never pinged yet</strong> (just imported).",
                        "ROSM pings every router automatically every 30 seconds. You don't have to do anything — the table updates on its own. Hit <strong>↺ Refresh</strong> for an immediate update. When you're actively working on the network and want second-by-second status changes, enable <strong>Real Time Monitoring</strong> from the Dashboard toolbar — it pings all devices every second and shows a prominent red banner until you turn it off.",
                        "The KPI bar at the top shows totals at a glance: how many routers you have, how many are online right now, how many are offline, and how many SSH sessions are active.",
                        "The search box works in real time as you type — filter by IP address, router name, tag, group or site. No page reload needed.",
                        "<strong>Tags</strong> are the most powerful thing on this page. When you import a router, give it a tag like 'core', 'branch', 'isp' or the client name. Later, when you want to backup just one client's routers or deploy a script to all branch devices, you just filter by tag and you're done.",
                        "The <strong>SSH</strong> button on each row connects to that router and reads its live data: hostname, RouterOS version, uptime, CPU, memory, and active interfaces. You don't need a terminal open.",
                        "The <strong>Creds</strong> button lets you assign a specific credential set to that single router — useful if it has a different password from the rest of the site.",
                        "<strong>Export CSV</strong> saves exactly what you see on screen, with all your current filters applied. Good for sending a client a list of their devices, or archiving a site inventory.",
                    ],
                    tip="Tag every router when you import it, even with just 'core' or 'edge'. You'll thank yourself later when you need to run an operation on a specific group and everything is already filtered."),
                sec("sitemanager", "#2adf8a", ico_site,
                    "Site Manager",
                    "Group your routers by physical location",
                    [
                        "A site is just a label for a physical location — 'London HQ', 'Milan DC', 'Client A'. Nothing complex about it.",
                        "The main reason to use sites is credentials: you can assign one SSH credential set to a site and every router there will use it automatically for backups and scripts. No need to specify credentials each time.",
                        "If you manage 10 different clients, create a site per client. Backups, scripts and filters all work per-site — it keeps everything tidy.",
                        "Create sites before running Network Discovery — during import you can assign each device to a site in the same step, saving you from reassigning them manually afterwards.",
                        "You can also assign a router to a site from the Dashboard at any time — just click the site column on the router's row.",
                        "If some routers in the same site use different SSH passwords, assign credentials directly to those specific routers from the Dashboard. The site credential is just the default.",
                        "The <strong>topology map</strong> gives you a visual overview of all your sites and their connected devices. More useful once you have 5+ sites.",
                    ],
                    tip="Don't skip sites even if you manage only one location. Having a site set up from the start means your credential assignment, backup targeting and filtering will all work correctly as soon as you add more sites later."),
                sec("backup", "#f7c44f", ico_backup,
                    "Backup",
                    "Automated and on-demand configuration backups",
                    [
                        "RouterOS stores your router configuration as a text file. If a router gets factory-reset, hit by a power failure, or replaced, you lose everything — VLANs, firewall rules, routing, the lot. A backup is that file, saved before disaster strikes.",
                        "ROSM saves configurations as <code>.rsc</code> files — plain text, readable in any editor. One file per router per backup run.",
                        "To automate: enable the <strong>scheduler</strong>, set how often to run it (in hours) and how many days to keep old files. ROSM handles everything in the background from that point on.",
                        "<strong>Interval tip:</strong> set the interval to <strong>0.01</strong> hours (about 1 minute) to quickly test that credentials and connectivity are working — then switch to 24 for daily production runs.",
                        "<strong>Retention</strong> is how long you keep backup files before they're automatically deleted. 30 days is a reasonable minimum; 60 gives you more history without taking up much space.",
                        "<strong>Show-sensitive</strong> checkbox: when enabled, the backup uses <code>/export show-sensitive</code> which includes passwords, keys and other sensitive config in the exported file. Recommended for a complete restore. Available in both manual and automatic backup.",
                        "<strong>Leave copy on router</strong> checkbox: when enabled, ROSM also runs <code>/export file=...</code> on the router before disconnecting, saving an extra copy of the backup in the router's own flash memory. Available in both manual and automatic backup.",
                        "When running a backup (manual or automatic), you choose the <strong>target</strong>: all online routers, only those with no backup yet, only stale ones, all routers in a specific site, or a custom group. You can combine these.",
                        'The <strong>"No backup"</strong> filter is where to start on day one — it shows every router you have never saved. Run a backup on all of them before setting up the scheduler.',
                        "The <strong>stale filter</strong> shows routers whose last backup is older than N days — even if they're currently online. Use this to catch devices that keep failing silently.",
                        "After a backup run, the results appear in the <strong>archive</strong> at the bottom of the page. Each file shows the router name, date, and size. You can download any file or delete multiple ones at once.",
                        "You can override the SSH credentials for any manual backup session without changing the permanent site configuration — useful when testing new credentials.",
                    ],
                    tip="On day one: run a manual backup on one router to confirm credentials work. If it succeeds, you know the automatic scheduler will work the same way. If it fails, the error appears immediately in the Log."),
                sec("discovery", "#f74fc8", ico_disc,
                    "Network Discovery",
                    "This is how you add routers to ROSM",
                    [
                        "This is the only way to add routers. You don't type them in manually — you scan the network and import what you find.",
                        "Enter a <strong>CIDR subnet</strong> — for example <code>192.168.1.0/24</code> means 'scan all 254 addresses from .1 to .254 on the 192.168.1.x network'. If your routers are on 10.0.0.x, enter <code>10.0.0.0/24</code>.",
                        "The scan checks ports 8291 (Winbox), 22 (SSH) and 80/443 (HTTP/S) on every address in the range. Anything that responds shows up in the results table.",
                        "The results table shows IP, open ports and whether the device is already in ROSM or not. Already-imported devices are highlighted so you don't accidentally add duplicates.",
                        "Before importing, you can assign SSH credentials to the discovered devices — either pick a saved credential set or enter a username and password right there for this scan.",
                        "Select the routers you want, optionally assign them to a site, and click <strong>Import</strong>. They appear on the Dashboard within seconds.",
                        "If you have routers on multiple subnets, run a separate scan for each one. You can do this as many times as you need.",
                        "Run a new scan whenever you install new routers on a site — it takes a minute and adds everything in one shot.",
                    ],
                    tip="If a device doesn't appear in the scan but you know it's up, check whether a firewall is blocking ports 22 or 8291 between the machine running ROSM and that subnet. This is the most common reason a scan comes back empty."),
                sec("upload", "#a78bfa", ico_script,
                    "Script Upload",
                    "Push RouterOS scripts to one or many routers at once",
                    [
                        "A <code>.rsc</code> script is a plain text file containing RouterOS commands — the same commands you'd type in a terminal or Winbox. ROSM takes that file and runs it on every router you choose.",
                        "The typical use case: you need to change a firewall rule, add a DNS entry, or update a setting across 30 routers. Write the script once, upload it here, select all 30 routers, click Send. Done in under a minute.",
                        "Upload one or more <code>.rsc</code> files from your computer. You can queue multiple scripts and run them in sequence.",
                        "Choose your target routers: all of them, filtered by tag, by site, or pick them manually one by one.",
                        "ROSM pushes the file via SFTP and runs it with <code>/import</code> on each device. This is exactly what you'd do manually — ROSM just does it in parallel across all selected devices.",
                        "Results appear in real time in the upload panel — you see OK or the error message for each router as it finishes. Everything is also saved in the Log under the SSH category.",
                        "If a router is offline when you run the upload, it gets skipped. Check the Log afterwards to see which devices received the script and which were missed.",
                        "RouterOS scripts can be sensitive — a typo can misconfigure a router. Always test on a single, non-critical device first, read the result, then deploy to the rest.",
                    ],
                    tip="Keep your scripts short and focused. One script = one task. It's much easier to debug 'add DNS entry' than 'update everything'. You can always run multiple uploads in sequence."),
                sec("upgrade", "#38bdf8", ico_upgrade,
                    "Upgrade RouterOS",
                    "Update firmware across one or many routers at once",
                    [
                        "ROSM can check for RouterOS updates and install them on your routers — without opening Winbox or a terminal on each one.",
                        "There are two methods: <strong>Online update</strong> (the router downloads the update from MikroTik's server) and <strong>.npk upload</strong> (you upload the package file manually via SFTP).",
                        "<strong>Online update — Check versions:</strong> select the routers you want to check, click 'Check versions'. ROSM connects via SSH, runs <code>/system package update check-for-updates</code> on each one, and shows the current version, the available version, and whether an update is available. This is read-only — nothing changes on the router.",
                        "<strong>Online update — Download + Install:</strong> after checking, click 'Download + Install'. ROSM runs <code>/system package update download</code> then <code>/system package update install</code>. The router downloads the package and reboots to apply the update. Do not click this on routers you don't want to update.",
                        "<strong>.npk upload:</strong> if you have the package file on your computer (downloaded from mikrotik.com/download), select it, choose the target routers, and click Upload. ROSM sends the file via SFTP. The router installs it on the next reboot. You can also tick 'Reboot immediately' to trigger the reboot right after the upload.",
                        "SSH credentials are resolved automatically — from the device's credential assignment, the site credential, or the global default. No need to enter them manually.",
                        "The results list shows the status for each router as operations complete. A yellow indicator means an update is available; green means already up to date.",
                        "Click the <strong>Changelog</strong> link next to a version number to open MikroTik's official changelog for that release.",
                        "The install operation reboots the router. Plan this during a maintenance window. The router will be unreachable for 1–3 minutes during the reboot.",
                        "Only Admin and Manager accounts can run upgrades. Technician and Viewer accounts do not have access to this feature.",
                    ],
                    tip="Check all your routers before upgrading. If they're all already up to date, there's nothing to do. If only some need the update, select just those — you don't have to update everything at once."),
                sec("credentials", "#f78a4f", ico_creds,
                    "Credentials",
                    "SSH credential sets for routers",
                    [
                        "ROSM needs SSH credentials to connect to your routers — for backups, SSH reads and script deployment. Without credentials, none of that works.",
                        "A <strong>credential set</strong> is just a name, an SSH username, and a password. Give it a recognisable name like 'Client A admin' or 'Site London'.",
                        "You can have as many sets as you need — one per site, one per client, or one for everything if all your routers share the same password.",
                        "The cleanest setup is one credential set per site: create the set, assign it to the site, and from that point every backup and script on that site uses it automatically.",
                        "If individual routers have different passwords, assign a credential set directly to that router from the Dashboard. The router-level assignment overrides the site default.",
                        "During Network Discovery, you can assign credentials to devices before importing them — this means they're ready to use immediately after import.",
                        "Passwords are stored encrypted with AES-128. They are never shown in the interface, never sent over the network in plaintext, and never included in exports.",
                        "If you need to see a stored password — for example to give it to a colleague — you need the admin recovery code to reveal it. This is a deliberate security measure.",
                        "You can override credentials for any single backup session without touching the permanent configuration — useful when testing new SSH passwords before making them permanent.",
                    ],
                    tip="If a site's SSH password changes, update the credential set once and every future operation on that site will use the new password automatically. You don't have to touch individual routers."),
                sec("log", "#2adf8a", ico_log,
                    "Log",
                    "Every operation, recorded",
                    [
                        "The Log records everything ROSM does: pings, SSH connections, backup runs, script deployments, login attempts, scheduler events. If something happened, it's here.",
                        "Logs are split into categories: <strong>Ping</strong> (status changes), <strong>SSH</strong> (connections and script results), <strong>Backup</strong> (runs, results, errors), <strong>Script</strong> (upload activity), <strong>Security</strong> (logins), <strong>System</strong> (app starts, restarts), <strong>Errors</strong> (anything unexpected).",
                        "When a backup or SSH operation fails, open the Log and filter by <strong>Errors</strong> or <strong>Backup</strong>. The full error message is always there — wrong password, connection refused, timeout, whatever it is.",
                        "Filter by category, date or keyword. Combine them: for example 'Backup + yesterday + 192.168.1.5' to see exactly what happened on that router last night.",
                        "The <strong>System</strong> tab shows when ROSM started, when it was restarted and who requested the restart. Useful for tracking unexpected restarts.",
                        "The <strong>Security</strong> tab records every login attempt with IP address and result — successful, wrong password, account locked. Check this if you suspect unauthorised access.",
                        "Only Admin and Manager accounts can clear the log. Technician and Viewer accounts can read it but cannot delete entries.",
                        "The maximum log size is set in Settings (default 2 000 entries, maximum 20 000). When the limit is reached, older entries are discarded automatically.",
                        "If something went wrong overnight and you don't know why, the Log is always the first place to check. The answer is almost always there.",
                    ],
                    tip="Set the log size to at least 5 000 entries. With a fleet of 20+ routers and automatic ping every 30 seconds, a small log fills up quickly and you lose history."),
                sec("users", "#f74f6a", ico_users,
                    "Users & Roles",
                    "Who can do what in ROSM",
                    [
                        "ROSM uses roles to control what each account can see and do. The idea is simple: give people access to what they actually need, nothing more.",
                        "<strong>Admin</strong> — full access with no restrictions. Can manage users, change settings, see and use the recovery code, and clear the log. There should only be one or two admin accounts.",
                        "<strong>Manager</strong> — can do everything operational: view and manage routers, run and schedule backups, manage credentials, read and clear the log. Cannot modify admin accounts or access the recovery code.",
                        "<strong>Technician</strong> — can use SSH to connect to routers and manage credentials. Cannot run backups, cannot clear the log, cannot change settings.",
                        "<strong>Viewer</strong> — read-only access to the Dashboard, Site Manager, Network Discovery, Statistics and Log. Cannot make any changes at all. Good for clients or monitoring staff who just need visibility.",
                        "<strong>Custom</strong> — if none of the standard roles fits, you can assign individual permissions from the full list. Useful for unusual situations.",
                        "To add a user: go to Users, fill in the username, password and role. Share the credentials with the person. They can change their password on first login.",
                        "You can enable <strong>2FA (two-factor authentication)</strong> on any account. Once enabled, the next login will require a time-based code from Google Authenticator or any compatible app.",
                        "If you disable an account, all active sessions for that user are terminated immediately — the person is logged out wherever they are. Useful when someone leaves the team.",
                    ],
                    tip="Create a Viewer account for anyone who needs to monitor the fleet but shouldn't be able to change anything. It takes 30 seconds to set up and removes a whole category of risk."),
                sec("settings", "#8896ab", ico_sett,
                    "Settings",
                    "Personalisation, security and system options",
                    [
                        "<strong>Display name</strong>: the name shown next to your avatar in the navbar. It's just cosmetic — it doesn't change your login username.",
                        "<strong>Language</strong>: switch between Italian and English. The whole interface changes immediately — no reload needed.",
                        "<strong>Dark mode</strong>: the toggle is the first item on the Settings page. Applies instantly to all pages and persists across sessions.",
                        "<strong>Ping interval</strong>: how often ROSM automatically pings every router. The default is 30 seconds. Lower values give more up-to-date status but generate more network traffic. If you have hundreds of routers on a slow link, increase this.",
                        "<strong>Ping history</strong>: how many days of ping data to keep for the Statistics charts. 7 days is fine for a quick overview; 30 days lets you spot recurring outages over time.",
                        "<strong>Log max size</strong>: the maximum number of log entries to keep. Once the limit is reached, older entries are discarded. Set this based on how much history you need.",
                        "<strong>Change password</strong>: you can change your account password here. You'll need to enter your current password first as a security check.",
                        "<strong>Auto-update</strong> (admin only): ROSM can check for updates automatically and apply them with one click. Enable it in Settings and choose the update channel (stable or beta). After an update the server restarts automatically and the page reloads.",
                        "<strong>Restart Server</strong> (admin only): the Restart Server button at the bottom of Settings restarts the ROSM process cleanly. The page shows a live status and reloads automatically when the server is back.",
                        "<strong>Recovery code</strong> (admin only): a special one-time code that lets you reset a locked-out admin account. It should be written down and stored somewhere safe — outside of ROSM. If you lose it and get locked out, there is no other way back in.",
                    ]),
                sec("firstrun", "#1b9ef7", ico_start,
                    "Getting Started",
                    "The recommended setup order — do this on day one",
                    [
                        "<strong>① Create credentials.</strong> Go to <em>Credentials</em> and create at least one SSH credential set. Everything else depends on this — without credentials, ROSM cannot connect to any router.",
                        "<strong>② Create a site in Site Manager.</strong> Go to <em>Site Manager</em>, create a site and assign the credential set to it. This makes every subsequent operation (backups, scripts, SSH) automatic for all routers in that site.",
                        "<strong>③ Run Network Discovery.</strong> Go to <em>Network Discovery</em>, enter your subnet in CIDR format, click Scan. Select the routers you find and click Import — ROSM takes you to Site Manager so you can assign them to the site immediately.",
                        "<strong>④ Check the Dashboard.</strong> Imported routers appear here. They'll be grey at first — wait 30 seconds or press Refresh. They should turn green (online) or red (offline).",
                        "<strong>⑤ Run a test backup.</strong> On the Backup page, select one online router and run a manual backup. Tick <em>Show-sensitive</em> for a complete backup. If it succeeds, credentials are correct and the scheduler will work.",
                        "<strong>⑥ Enable the backup scheduler.</strong> Set interval to 0.01 h (1 min) for a quick test, then switch to 24 h for daily production. Set retention to 30 days.",
                        "<strong>⑦ Create team accounts.</strong> Add a Manager account for colleagues who operate the system, and a Viewer account for anyone who just needs read-only visibility. Never share the admin account.",
                    ],
                    tip="Follow this exact order: Credentials → Site Manager → Discovery → Dashboard → Backup. If something breaks at any step, the Log will tell you what went wrong. You don't have to guess."),
                sec("faq", "#64748b", ico_faq,
                    "FAQ",
                    "The most common questions",
                    [
                        "<strong>My routers don't show up in the scan.</strong> Most common causes: a firewall between ROSM and that subnet is blocking port 22 or 8291; the subnet you entered is wrong; the routers are off. Test with <code>ping &lt;ip&gt;</code> from the machine running ROSM first.",
                        "<strong>Backup fails with 'Authentication failed'.</strong> The username or password in the credential set is wrong. Verify the user exists on the router with <code>/user print</code> in Winbox. Update the credential set and retry.",
                        "<strong>Backup fails with 'Connection refused'.</strong> SSH is disabled on the router or is running on a non-standard port. Check <code>/ip service print</code> in Winbox. Enable SSH (port 22) or update the port in your credential set.",
                        "<strong>A router shows OFFLINE but I know it's up.</strong> ROSM pings via ICMP. If ICMP is filtered on the router (<code>/ip firewall filter</code>), ROSM can't reach it. Also check that port 22 is reachable from the ROSM server.",
                        "<strong>I forgot the ROSM admin password.</strong> Go to <code>/login</code> and click 'Forgot password'. You will need the recovery code shown in Settings &rarr; Recovery code (when logged in as admin). If you have lost the recovery code, access cannot be recovered — keep it in a safe place.",
                        "<strong>ROSM won't start after installation.</strong> Open <strong>ROSM.app</strong> from Applications or click the ROSM menu bar icon and choose 'Open Dashboard'. If the app doesn't appear in Applications, re-run the installer package. If the browser opens but shows 'connection refused', wait a few seconds — the server may still be starting.",
                        "<strong>Discovery finds devices but doesn't identify models.</strong> ROSM identifies devices from open ports during the scan. Model and hostname are read via SSH <em>after</em> import — click SSH on a router row in the Dashboard to fetch the details.",
                        "<strong>After an auto-update ROSM doesn't come back.</strong> The update replaces the server file and restarts the process automatically. Wait 10–15 seconds — the page should reload on its own. If it doesn't, open ROSM.app from Applications or restart it from the menu bar icon. The updated file is already in place.",
                        "<strong>Can I use ROSM with RouterOS v6?</strong> Yes. SSH and SFTP work the same on v6 and v7. The only difference is that some command output formats may vary — backups and script imports work identically.",
                    ],
                    tip="For SSH problems, always test first with a standard SSH client from the same machine running ROSM: ssh admin@IP. If that fails, ROSM can't work either — the problem is network or credentials, not ROSM."),
                sec("troubleshooting", "#f74f4f", ico_trouble,
                    "Troubleshooting",
                    "Diagnosis and fixes for the most common issues",
                    [
                        "<strong>Backup → 'No route to host'</strong> — ROSM can't reach the router's IP. Check routing, active VPN, or firewall rules on the ROSM server's network.",
                        "<strong>Backup → 'SSH timeout'</strong> — The SSH connection opens but doesn't respond in time. The router may be under load or the link is unstable. Retry after a few minutes; if it keeps happening, check the router's CPU with <code>/system resource print</code>.",
                        "<strong>Script upload → 'Import failed on router X'</strong> — The <code>.rsc</code> file contains a RouterOS syntax error. Test it manually in Winbox: <code>/import file-name=yourscript.rsc</code>. Fix the error, re-upload.",
                        "<strong>Dashboard → router permanently grey (UNKNOWN)</strong> — The automatic ping has never completed for that device. Wait 30 seconds after import. If it stays grey, ICMP may be blocked — test <code>ping &lt;ip&gt;</code> from the ROSM server.",
                        "<strong>Log → 'PermissionError' on .rsc files</strong> — ROSM doesn't have write permission on the folder where it saves backups. Check folder permissions with <code>ls -la</code> and fix with <code>chmod</code> or <code>chown</code>.",
                        "<strong>Log → 'Disk quota exceeded'</strong> — The ROSM server's disk is full. Reduce backup retention (Backup → Scheduler), bulk-delete old backups from the archive, or free up space on the disk.",
                        "<strong>Credentials &rarr; 'Reveal' button does nothing</strong> — Viewing saved passwords requires the admin recovery code. Make sure you are logged in as Admin. If you have lost the recovery code, it cannot be recovered — keep it in a safe place.",
                        "<strong>Site Manager → topology map is empty</strong> — The map only shows routers that have been assigned to a site. Assign routers to sites from the Dashboard (click the site column on each row), then reload the topology page.",
                    ],
                    tip="Most problems fall into two categories: network/firewall (ROSM can't reach the router) or credentials (wrong username or password). Check one at a time. The Log always shows the exact error — read it before guessing."),
            ]
        else:
            sections = [
                sec("dashboard", "#4f8ef7", ico_dash,
                    "Dashboard",
                    "La schermata che guarderai ogni giorno",
                    [
                        "Questa è la tua centrale di controllo. Una volta importati i router da Network Discovery, compaiono tutti qui in una tabella con il loro stato in tempo reale.",
                        "Colori dello stato: <strong>verde = ONLINE</strong> (ha risposto all'ultimo ping), <strong>rosso = OFFLINE</strong> (nessuna risposta), <strong>grigio = non ancora pingato</strong> (appena importato).",
                        "ROSM fa il ping automaticamente ogni 30 secondi. Non devi fare niente — la tabella si aggiorna da sola. Puoi anche attivare il <strong>Real Time Monitoring</strong>: 1 ping al secondo verso tutti i dispositivi, con un banner ben visibile su ogni pagina finché non lo disattivi. Utile quando stai lavorando sulla rete e vuoi vedere i cambiamenti di stato in tempo reale.",
                        "La barra KPI in cima mostra i totali a colpo d'occhio: quanti router hai, quanti sono online adesso, quanti offline, e quante sessioni SSH sono aperte.",
                        "Il campo ricerca funziona mentre scrivi — filtra per indirizzo IP, nome del router, tag, gruppo o sede. Non serve ricaricare la pagina.",
                        "I <strong>tag</strong> sono la cosa più potente di questa schermata. Quando importi un router, dagli un tag come 'core', 'branch', 'isp' o il nome del cliente. Più avanti, quando vorrai fare il backup solo dei router di un cliente o mandare uno script a tutte le filiali, filtri per tag e hai già tutto selezionato.",
                        "Il pulsante <strong>SSH</strong> su ogni riga si connette a quel router e legge i suoi dati live: hostname, versione RouterOS, uptime, CPU, memoria, interfacce attive. Non ti serve aprire un terminale.",
                        "Il pulsante <strong>Creds</strong> ti permette di assegnare un set di credenziali specifico a quel singolo router — utile se ha una password diversa dal resto della sede.",
                        "<strong>Esporta CSV</strong> salva esattamente quello che vedi a schermo, con tutti i filtri già applicati. Utile per mandare a un cliente la lista dei suoi dispositivi, o per archiviare l'inventario di una sede.",
                    ],
                    tip="Aggiungi un tag a ogni router appena lo importi, anche solo 'core' o 'edge'. Te ne accorgerai quando devi fare un'operazione su un gruppo specifico e trovi tutto già filtrato."),
                sec("sitemanager", "#2adf8a", ico_site,
                    "Site Manager",
                    "Raggruppa i router per sede fisica",
                    [
                        "Una sede è solo un'etichetta per un luogo fisico — 'Roma Ufficio', 'Milano DC', 'Cliente A'. Non c'è niente di complicato.",
                        "Il motivo principale per usare le sedi è la gestione delle credenziali: assegni un set di credenziali SSH a una sede e tutti i router lì dentro le useranno automaticamente per backup e script. Niente da specificare ogni volta.",
                        "Se gestisci 10 clienti diversi, crea una sede per cliente. Backup, script e filtri funzionano tutti per sede — mantiene tutto ordinato.",
                        "Crea le sedi prima di fare Network Discovery — durante l'import puoi assegnare ogni dispositivo a una sede nello stesso passaggio, così non devi riassegnarli dopo.",
                        "Puoi anche assegnare un router a una sede dalla Dashboard in qualsiasi momento — clicca sulla colonna sede nella riga del router.",
                        "Se alcuni router nella stessa sede usano password SSH diverse, assegna le credenziali direttamente a quei router specifici dalla Dashboard. Le credenziali di sede sono solo il valore di default.",
                        "La <strong>mappa topologica</strong> ti dà una vista visiva di tutte le sedi e i dispositivi collegati. Diventa utile quando hai 5 o più sedi.",
                    ],
                    tip="Non saltare le sedi anche se gestisci un'unica sede. Averle impostate dall'inizio significa che credenziali, target di backup e filtri funzioneranno correttamente non appena aggiungi nuove sedi."),
                sec("backup", "#f7c44f", ico_backup,
                    "Backup",
                    "Backup automatici e manuali delle configurazioni",
                    [
                        "RouterOS salva la configurazione del router in un file di testo. Se un router viene resettato di fabbrica, colpito da un'interruzione di corrente o sostituito, perdi tutto — VLAN, regole firewall, routing, tutto quanto. Un backup è quel file, salvato prima del disastro.",
                        "ROSM salva le configurazioni come file <code>.rsc</code> — testo semplice, leggibile con qualsiasi editor. Un file per router per ogni ciclo di backup.",
                        "Per automatizzare: abilita il <strong>pianificatore</strong>, imposta ogni quante ore farlo girare e per quanti giorni conservare i vecchi file. Da quel momento ROSM gestisce tutto in background.",
                        "<strong>Consiglio sull'intervallo:</strong> imposta l'intervallo a <strong>0.01</strong> ore (circa 1 minuto) per verificare rapidamente che credenziali e connettività funzionino — poi passa a 24 per la produzione giornaliera.",
                        "La <strong>retention</strong> è per quanto tempo tieni i file prima che vengano eliminati automaticamente. 30 giorni è un minimo ragionevole; 60 ti dà più storico senza occupare molto spazio.",
                        "<strong>Checkbox Show-sensitive</strong>: quando abilitata, il backup usa <code>/export show-sensitive</code> che include password, chiavi e altra configurazione sensibile nel file esportato. Consigliata per un ripristino completo. Disponibile sia nel backup manuale che in quello automatico.",
                        "<strong>Checkbox Lascia sul router</strong>: quando abilitata, ROSM esegue anche <code>/export file=...</code> sul router prima di disconnettersi, salvando una copia extra del backup nella flash del router. Disponibile sia nel backup manuale che in quello automatico.",
                        "Quando fai un backup (manuale o automatico) scegli il <strong>target</strong>: tutti i router online, solo quelli senza backup, solo quelli scaduti, tutti i router di una sede, o un gruppo personalizzato. Puoi combinare questi criteri.",
                        'Il filtro <strong>"Senza backup"</strong> è da dove iniziare il primo giorno — mostra ogni router che non hai mai salvato. Fai un backup su tutti prima di impostare il pianificatore.',
                        "Il <strong>filtro scaduti</strong> mostra i router il cui ultimo backup è più vecchio di N giorni — anche se sono attualmente online. Usalo per individuare i dispositivi che continuano a fallire silenziosamente.",
                        "Dopo un ciclo di backup, i risultati appaiono nell'<strong>archivio</strong> in fondo alla pagina. Ogni file mostra il nome del router, la data e la dimensione. Puoi scaricare qualsiasi file o eliminarne più di uno insieme.",
                        "Puoi sovrascrivere le credenziali SSH per qualsiasi sessione di backup manuale senza toccare la configurazione permanente — utile quando stai testando nuove credenziali.",
                    ],
                    tip="Il primo giorno: fai un backup manuale su un router per verificare che le credenziali funzionino. Se va a buon fine, sai che il pianificatore automatico funzionerà allo stesso modo. Se fallisce, l'errore appare subito nel Log."),
                sec("discovery", "#f74fc8", ico_disc,
                    "Network Discovery",
                    "Da qui si aggiungono i router a ROSM",
                    [
                        "Questo è l'unico modo per aggiungere router. Non li inserisci manualmente — scansioni la rete e importi quello che trovi.",
                        "Inserisci una <strong>subnet CIDR</strong> — per esempio <code>192.168.1.0/24</code> significa 'scansiona tutti i 254 indirizzi da .1 a .254 sulla rete 192.168.1.x'. Se i tuoi router sono su 10.0.0.x, inserisci <code>10.0.0.0/24</code>.",
                        "La scansione verifica le porte 8291 (Winbox), 22 (SSH) e 80/443 (HTTP/S) su ogni indirizzo nel range. Qualsiasi cosa risponde compare nella tabella dei risultati — puoi usarla anche solo per vedere cosa è aperto su una subnet, utile per trovare vulnerabilità o servizi lasciati attivi per errore.",
                        "La tabella dei risultati mostra IP, porte aperte e se il dispositivo è già in ROSM o no. I dispositivi già importati vengono evidenziati così non crei duplicati per sbaglio.",
                        "Prima di importare puoi assegnare credenziali SSH ai dispositivi trovati — scegli un set salvato o inserisci username e password lì al momento per quella scansione.",
                        "Seleziona i router che vuoi, assegnali eventualmente a una sede, e clicca <strong>Importa</strong>. Appaiono sulla Dashboard in pochi secondi.",
                        "Se hai router su più subnet, fai una scansione separata per ognuna. Puoi farlo tutte le volte che vuoi.",
                        "Fai una nuova scansione ogni volta che installi nuovi router in una sede — ci vuole un minuto e aggiunge tutto in un colpo solo.",
                    ],
                    tip="Se un dispositivo non compare nella scansione ma sai che è acceso, verifica che un firewall non stia bloccando le porte 22 o 8291 tra la macchina su cui gira ROSM e quella subnet. È la causa più comune di una scansione che torna vuota."),
                sec("upload", "#a78bfa", ico_script,
                    "Script Upload",
                    "Manda script RouterOS a uno o più router in una volta sola",
                    [
                        "Uno script <code>.rsc</code> è un file di testo con comandi RouterOS — gli stessi che scriveresti nel terminale o in Winbox. ROSM prende quel file e lo esegue su tutti i router che scegli.",
                        "Il caso d'uso tipico: devi cambiare una regola firewall, aggiungere un DNS entry, o aggiornare un'impostazione su 30 router. Scrivi lo script una volta, caricalo qui, seleziona i 30 router, clicca Invia. Fatto in meno di un minuto.",
                        "Carica uno o più file <code>.rsc</code> dal tuo computer. Puoi mettere in coda più script ed eseguirli in sequenza.",
                        "Scegli i router target: tutti, filtrati per tag, per sede, o selezionali manualmente uno per uno.",
                        "ROSM invia il file via SFTP e lo esegue con <code>/import</code> su ogni dispositivo. È esattamente quello che faresti a mano — ROSM lo fa in parallelo su tutti i dispositivi selezionati.",
                        "I risultati appaiono in tempo reale nel pannello upload — vedi OK o il messaggio di errore per ogni router man mano che finisce. Tutto viene anche salvato nel Log nella categoria SSH.",
                        "Se un router è offline quando esegui l'upload, viene saltato. Controlla il Log dopo per vedere quali dispositivi hanno ricevuto lo script e quali sono stati mancati.",
                        "Gli script RouterOS possono essere delicati — un errore di battitura può misconfigurare un router. Testa sempre su un singolo dispositivo non critico prima, leggi il risultato, poi fai il deploy agli altri.",
                    ],
                    tip="Tieni gli script corti e focalizzati. Uno script = un'operazione. È molto più facile fare debug di 'aggiungi DNS entry' che di 'aggiorna tutto'. Puoi sempre fare più upload in sequenza."),
                sec("upgrade", "#38bdf8", ico_upgrade,
                    "Upgrade RouterOS",
                    "Aggiornamento firmware su uno o più router in una volta sola",
                    [
                        "ROSM può controllare gli aggiornamenti RouterOS e installarli sui tuoi router — senza aprire Winbox o un terminale su ognuno.",
                        "Ci sono due metodi: <strong>Aggiornamento online</strong> (il router scarica l'aggiornamento dal server MikroTik) e <strong>Upload .npk</strong> (carichi il pacchetto manualmente via SFTP).",
                        "<strong>Aggiornamento online — Controlla versioni:</strong> seleziona i router che vuoi controllare e clicca 'Controlla versioni'. ROSM si connette via SSH, esegue <code>/system package update check-for-updates</code> su ognuno e mostra la versione attuale, quella disponibile e se c'è un aggiornamento. Questa operazione è in sola lettura — non cambia nulla sul router.",
                        "<strong>Aggiornamento online — Scarica + Installa:</strong> dopo il controllo, clicca 'Scarica + Installa'. ROSM esegue <code>/system package update download</code> poi <code>/system package update install</code>. Il router scarica il pacchetto e si riavvia per applicare l'aggiornamento. Non cliccare questo pulsante su router che non vuoi aggiornare.",
                        "<strong>Upload .npk:</strong> se hai il file del pacchetto sul tuo computer (scaricato da mikrotik.com/download), selezionalo, scegli i router target e clicca Carica. ROSM invia il file via SFTP. Il router lo installa al prossimo riavvio. Puoi anche spuntare 'Riavvia subito dopo il caricamento' per avviare il riavvio subito dopo l'upload.",
                        "Le credenziali SSH vengono risolte automaticamente — dall'assegnazione delle credenziali del dispositivo, dalla credenziale della sede, o dal default globale. Non devi inserirle manualmente.",
                        "La lista dei risultati mostra lo stato per ogni router man mano che le operazioni si completano. Un indicatore giallo significa che è disponibile un aggiornamento; verde significa che è già aggiornato.",
                        "Clicca il link <strong>Changelog</strong> accanto a un numero di versione per aprire il changelog ufficiale MikroTik per quella release.",
                        "L'operazione di installazione riavvia il router. Pianificala durante una finestra di manutenzione. Il router non sarà raggiungibile per 1–3 minuti durante il riavvio.",
                        "Solo gli account Admin e Manager possono eseguire gli upgrade. Gli account Technician e Viewer non hanno accesso a questa funzione.",
                    ],
                    tip="Controlla tutti i tuoi router prima di aggiornare. Se sono già tutti aggiornati, non c'è niente da fare. Se solo alcuni hanno bisogno dell'aggiornamento, seleziona solo quelli — non devi aggiornare tutto in una volta."),
                sec("credentials", "#f78a4f", ico_creds,
                    "Credenziali SSH",
                    "I set di credenziali per i tuoi router",
                    [
                        "ROSM ha bisogno di credenziali SSH per connettersi ai tuoi router — per i backup, le letture SSH e il deploy degli script. Senza credenziali, niente di tutto questo funziona.",
                        "Un <strong>set di credenziali</strong> è solo un nome, un username SSH e una password. Dagli un nome riconoscibile come 'Admin Cliente A' o 'Sede Londra'.",
                        "Puoi avere quanti set vuoi — uno per sede, uno per cliente, o uno solo se tutti i tuoi router condividono la stessa password. Puoi anche creare due account sulle routerboard: uno solo lettura e uno lettura/scrittura, così tieni ancora più sotto controllo cosa fa ROSM in autonomia.",
                        "La configurazione più pulita è un set di credenziali per sede: crei il set, lo assegni alla sede, e da quel momento ogni backup e script su quella sede lo usa automaticamente.",
                        "Se singoli router hanno password diverse, assegna un set direttamente a quel router dalla Dashboard. L'assegnazione a livello di router sovrascrive il default della sede.",
                        "Durante Network Discovery puoi assegnare credenziali ai dispositivi prima di importarli — questo significa che sono pronti all'uso immediatamente dopo l'import.",
                        "Le password sono salvate cifrate con AES-128. Non vengono mai mostrate nell'interfaccia, mai inviate in chiaro sulla rete, e mai incluse negli export.",
                        "Se hai bisogno di vedere una password salvata — per esempio per darla a un collega — hai bisogno del recovery code admin per rivelarla. Ogni rivelazione viene registrata nel Log.",
                        "Puoi sovrascrivere le credenziali per qualsiasi sessione di backup singola senza toccare la configurazione permanente — utile quando stai testando nuove password SSH prima di renderle definitive.",
                    ],
                    tip="Se non hai ancora un account di sola lettura sulle routerboard, puoi usare Script Upload per crearlo su tutta la flotta in un colpo solo — scrivi lo script una volta, lo mandi a tutti. Poi usa quell'account per backup e ping, e tieni il full-access solo per le operazioni che ne hanno davvero bisogno."),
                sec("log", "#2adf8a", ico_log,
                    "Log",
                    "Ogni operazione, registrata",
                    [
                        "Il Log registra tutto quello che fa ROSM: ping, connessioni SSH, cicli di backup, deploy di script, tentativi di login, eventi dello scheduler. Se è successo qualcosa, è qui.",
                        "I log sono divisi in categorie: <strong>Ping</strong> (cambi di stato), <strong>SSH</strong> (connessioni e risultati script), <strong>Backup</strong> (esecuzioni, risultati, errori), <strong>Script</strong> (attività upload), <strong>Sicurezza</strong> (login), <strong>Sistema</strong> (avvii, riavvii), <strong>Errori</strong> (tutto l'inatteso).",
                        "Quando un backup o una sessione SSH fallisce, apri il Log e filtra per <strong>Errori</strong> o <strong>Backup</strong>. Il messaggio di errore completo è sempre lì — password sbagliata, connessione rifiutata, timeout, qualunque cosa sia.",
                        "Filtra per categoria, data o parola chiave. Combinali: per esempio 'Backup + ieri + 192.168.1.5' per vedere esattamente cosa è successo su quel router la notte scorsa.",
                        "Il tab <strong>Sistema</strong> mostra quando ROSM è partito, quando è stato riavviato e chi ha richiesto il riavvio. Utile per tracciare riavvii inattesi.",
                        "Il tab <strong>Sicurezza</strong> registra ogni tentativo di login con indirizzo IP e risultato — riuscito, password sbagliata, account bloccato. Controllalo se sospetti accessi non autorizzati.",
                        "Solo gli account Admin e Manager possono svuotare il log. Technician e Viewer possono leggerlo ma non cancellare le voci.",
                        "La dimensione massima del log si imposta nelle Impostazioni (default 2 000 voci, massimo 20 000). Quando si raggiunge il limite, le voci più vecchie vengono scartate automaticamente.",
                        "Se qualcosa è andato storto durante la notte e non sai perché, il Log è sempre il primo posto dove guardare. La risposta è quasi sempre lì.",
                    ],
                    tip="Imposta la dimensione del log ad almeno 5 000 voci. Con una flotta di 20+ router e il ping automatico ogni 30 secondi, un log piccolo si riempie in fretta e perdi lo storico."),
                sec("users", "#f74f6a", ico_users,
                    "Utenti e Ruoli",
                    "Chi può fare cosa in ROSM",
                    [
                        "ROSM usa i ruoli per controllare cosa può vedere e fare ogni account. L'idea è semplice: dai alle persone l'accesso a quello di cui hanno davvero bisogno, niente di più.",
                        "<strong>Admin</strong> — accesso completo senza restrizioni. Può gestire utenti, cambiare impostazioni, vedere e usare il recovery code, svuotare il log. Dovrebbero esserci solo uno o due account admin.",
                        "<strong>Manager</strong> — può fare tutto quello che è operativo: visualizzare e gestire router, eseguire e pianificare backup, gestire credenziali, leggere e svuotare il log. Non può modificare gli account admin né accedere al recovery code.",
                        "<strong>Technician</strong> — può usare SSH per connettersi ai router e gestire le credenziali. Non può fare backup, non può svuotare il log, non può cambiare le impostazioni.",
                        "<strong>Viewer</strong> — accesso in sola lettura alla Dashboard, Site Manager, Network Discovery, Statistiche e Log. Non può fare nessuna modifica. Adatto per clienti o personale di monitoraggio che ha solo bisogno di visibilità.",
                        "<strong>Custom</strong> — se nessun ruolo standard va bene, puoi assegnare permessi singoli dalla lista completa. Utile per situazioni particolari.",
                        "Per aggiungere un utente: vai su Utenti, compila username, password e ruolo. Condividi le credenziali con la persona. Può cambiare la password al primo accesso.",
                        "Puoi abilitare il <strong>2FA (autenticazione a due fattori)</strong> su qualsiasi account. Una volta abilitato, al login successivo verrà richiesto un codice temporale da Google Authenticator o da qualsiasi app compatibile.",
                        "Se disabiliti un account, tutte le sessioni attive per quell'utente vengono terminate immediatamente — la persona viene disconnessa ovunque si trovi. Utile quando qualcuno lascia il team.",
                    ],
                    tip="Crea un account Viewer per chiunque abbia bisogno di monitorare la flotta senza poter cambiare nulla. Ci vogliono 30 secondi e si elimina un'intera categoria di rischio."),
                sec("settings", "#8896ab", ico_sett,
                    "Impostazioni",
                    "Personalizzazione, sicurezza e opzioni di sistema",
                    [
                        "<strong>Nome visualizzato</strong>: il nome mostrato accanto all'icona utente nella navbar. È solo estetico — non cambia il tuo username di login.",
                        "<strong>Lingua</strong>: passa da Italiano a English. Tutta l'interfaccia cambia immediatamente, senza ricaricare la pagina.",
                        "<strong>Dark Mode</strong>: il toggle si trova come prima voce nella pagina Impostazioni. Si attiva subito su tutte le pagine e persiste tra le sessioni.",
                        "<strong>Intervallo ping</strong>: ogni quanti secondi ROSM fa il ping automatico a tutti i router. Il default è 30 secondi. Valori più bassi ti danno uno stato più aggiornato ma generano più traffico di rete. Se hai centinaia di router su un link lento, aumentalo.",
                        "<strong>Storico Ping</strong>: quanti giorni di dati di ping tenere per i grafici nelle Statistiche. 7 giorni va bene per una panoramica rapida; 30 giorni ti permette di identificare interruzioni ricorrenti nel tempo.",
                        "<strong>Dimensione massima log</strong>: il numero massimo di voci da conservare. Quando si raggiunge il limite, le voci più vecchie vengono scartate. Impostalo in base a quanto storico ti serve.",
                        "<strong>Cambia password</strong>: puoi cambiare la password del tuo account da qui. Dovrai inserire prima la password attuale come verifica di sicurezza.",
                        "<strong>Aggiornamento automatico</strong> (solo admin): ROSM può controllare gli aggiornamenti e applicarli con un clic. Abilitalo nelle Impostazioni e scegli il canale (stabile o beta). Dopo un aggiornamento il server si riavvia automaticamente e la pagina si ricarica.",
                        "<strong>Riavvia Server</strong> (solo admin): il pulsante 'Riavvia Server' in fondo alle Impostazioni riavvia il processo ROSM in modo pulito. La pagina mostra lo stato live e si ricarica automaticamente quando il server torna online.",
                        "<strong>Recovery code</strong> (solo admin): un codice speciale che ti permette di recuperare un account admin bloccato. Scrivilo e conservalo da qualche parte sicura — fuori da ROSM. Se lo perdi e rimani bloccato, non c'è altro modo per rientrare.",
                    ]),
                sec("firstrun", "#1b9ef7", ico_start,
                    "Primo Avvio",
                    "L'ordine consigliato per iniziare — fai così il primo giorno",
                    [
                        "<strong>① Crea le credenziali.</strong> Vai su <em>Credenziali SSH</em> e crea almeno un set con username e password dei tuoi router. Tutto il resto dipende da questo — senza credenziali ROSM non si connette a nessun router.",
                        "<strong>② Crea una sede nel Site Manager.</strong> Vai su <em>Site Manager</em>, crea una sede e assegna il set di credenziali appena creato. In questo modo ogni operazione successiva (backup, script, SSH) userà automaticamente le credenziali giuste per tutti i router di quella sede.",
                        "<strong>③ Fai la scansione.</strong> Vai su <em>Network Discovery</em>, inserisci la subnet in formato CIDR, clicca Scansiona. Seleziona i router trovati e clicca Importa — ROSM ti porta al Site Manager per assegnarli subito alla sede.",
                        "<strong>④ Controlla la Dashboard.</strong> I router importati appaiono qui grigi — aspetta 30 secondi o premi Aggiorna. Diventano verdi (ONLINE) o rossi (OFFLINE). Se vuoi uno stato in tempo reale, premi Real Time Monitoring.",
                        "<strong>⑤ Fai un backup di prova.</strong> Nella pagina Backup seleziona un router online e fai un backup manuale. Spunta <em>Show-sensitive</em> per un backup completo. Se va a buon fine, le credenziali sono corrette e il pianificatore funzionerà.",
                        "<strong>⑥ Abilita il pianificatore backup.</strong> Imposta l'intervallo a 0.01 ore (1 min) per un test rapido, poi passa a 24 ore per la produzione. Imposta la retention a 30 giorni.",
                        "<strong>⑦ Crea gli account per il team.</strong> Aggiungi un account Manager per i colleghi che operano sul sistema, Viewer per chi deve solo monitorare. Non condividere mai l'account admin.",
                    ],
                    tip="L'ordine è importante: Credenziali → Site Manager → Discovery → Dashboard → Backup. Se qualcosa non va in un passaggio, apri il Log — ti dice l'errore esatto. Non devi indovinare."),
                sec("faq", "#64748b", ico_faq,
                    "FAQ",
                    "Le domande più frequenti",
                    [
                        "<strong>I miei router non compaiono nella scansione.</strong> Cause più comuni: un firewall blocca la porta 22 o 8291 tra il server ROSM e la subnet; la subnet inserita è sbagliata; i router non sono accesi. Prima di tutto testa <code>ping &lt;ip&gt;</code> dalla macchina dove gira ROSM.",
                        "<strong>Il backup fallisce con 'Authentication failed'.</strong> Username o password nel set di credenziali sono sbagliati. Verifica che l'utente SSH esista sul router con <code>/user print</code> in Winbox. Aggiorna il set e riprova.",
                        "<strong>Il backup fallisce con 'Connection refused'.</strong> SSH è disabilitato sul router o è su una porta diversa. Controlla in Winbox: <code>/ip service print</code>. Abilita SSH sulla porta 22 o aggiorna la porta nel set di credenziali.",
                        "<strong>Un router è OFFLINE sulla Dashboard ma so che è acceso.</strong> ROSM usa ping ICMP. Se l'ICMP è filtrato sul router (<code>/ip firewall filter</code>), lo stato rimane OFFLINE. Verifica anche che la porta 22 sia raggiungibile dal server ROSM.",
                        "<strong>Ho dimenticato la password admin di ROSM.</strong> Vai su <code>/login</code> e clicca 'Password dimenticata'. Ti verrà chiesto il recovery code, che trovi nelle Impostazioni &rarr; Recovery code (da admin loggato). Se hai perso il recovery code, l'accesso non è recuperabile — conservalo in un posto sicuro.",
                        "<strong>ROSM non si avvia dopo l'installazione.</strong> Apri <strong>ROSM.app</strong> dalla cartella Applicazioni o clicca sull'icona ROSM nella barra menu e scegli 'Apri Dashboard'. Se l'app non compare in Applicazioni, riesegui il pacchetto di installazione. Se il browser si apre ma mostra 'connection refused', aspetta qualche secondo — il server potrebbe ancora essere in avvio.",
                        "<strong>La scansione trova dispositivi ma non riconosce i modelli.</strong> ROSM identifica i dispositivi dalle porte aperte durante la scansione. Modello e hostname vengono letti via SSH <em>dopo</em> l'import — clicca SSH sulla riga del router in Dashboard per caricare i dettagli.",
                        "<strong>Dopo l'aggiornamento automatico ROSM non torna online.</strong> L'aggiornamento sostituisce il file del server e riavvia il processo automaticamente. Aspetta 10–15 secondi — la pagina dovrebbe ricaricarsi da sola. Se non lo fa, apri ROSM.app dalla cartella Applicazioni o riavvialo dall'icona nella barra menu. Il file aggiornato è già al suo posto.",
                        "<strong>Posso usare ROSM con RouterOS v6?</strong> Sì. SSH e SFTP funzionano allo stesso modo su v6 e v7. L'unica differenza è che alcuni formati di output dei comandi variano — backup e import degli script funzionano in modo identico.",
                    ],
                    tip="Per i problemi SSH testa sempre prima con un client SSH standard dalla stessa macchina che esegue ROSM: <code>ssh admin@IP</code>. Se non funziona lì, ROSM non può funzionare — il problema è di rete o credenziali, non di ROSM."),
                sec("troubleshooting", "#f74f4f", ico_trouble,
                    "Problemi Comuni",
                    "Diagnosi e soluzioni per gli errori tipici",
                    [
                        "<strong>Backup → 'No route to host'</strong> — ROSM non riesce a raggiungere l'IP del router. Controlla il routing, la VPN attiva, o le regole firewall sulla rete del server ROSM.",
                        "<strong>Backup → 'SSH timeout'</strong> — La connessione SSH si apre ma non risponde in tempo. Il router potrebbe essere sotto carico o il link è instabile. Riprova tra qualche minuto; se continua, controlla la CPU del router con <code>/system resource print</code>.",
                        "<strong>Script Upload → 'Import failed su router X'</strong> — Il file <code>.rsc</code> contiene un errore di sintassi RouterOS. Testalo a mano in Winbox: <code>/import file-name=script.rsc</code>. Correggi l'errore e ri-carica.",
                        "<strong>Dashboard → router perennemente grigio (UNKNOWN)</strong> — Il ping automatico non è mai completato per quel dispositivo. Aspetta 30 secondi dall'import. Se rimane grigio, l'ICMP potrebbe essere bloccato — testa <code>ping &lt;ip&gt;</code> dal server ROSM.",
                        "<strong>Log → 'PermissionError' sui file .rsc</strong> — ROSM non ha i permessi di scrittura nella cartella dove salva i backup. Controlla con <code>ls -la</code> e correggi con <code>chmod</code> o <code>chown</code>.",
                        "<strong>Log → 'Disk quota exceeded'</strong> — Il disco del server ROSM è pieno. Riduci la retention (Backup → Pianificatore), elimina i backup vecchi dall'archivio, o libera spazio sul disco.",
                        "<strong>Credenziali &rarr; il pulsante 'Mostra' non funziona</strong> — Vedere le password salvate richiede il recovery code admin. Assicurati di essere loggato come Admin. Se hai perso il recovery code, non è recuperabile — conservalo in un posto sicuro.",
                        "<strong>Site Manager → la mappa topologica è vuota</strong> — La mappa mostra solo i router assegnati a una sede. Assegna i router alle sedi dalla Dashboard (colonna sede su ogni riga), poi ricarica la pagina della topologia.",
                    ],
                    tip="La maggior parte dei problemi rientra in due categorie: rete/firewall (ROSM non raggiunge il router) o credenziali (username o password sbagliati). Controlla uno per volta. Il Log mostra sempre l'errore esatto — leggilo prima di fare ipotesi."),
            ]

        # ── Sidebar groups ────────────────────────────────────────────
        if lang_en:
            sb_groups = [
                ("Sections",       [
                    ("dashboard",      "Dashboard",         "#4f8ef7"),
                    ("sitemanager",    "Site Manager",      "#2adf8a"),
                    ("backup",         "Backup",            "#f7c44f"),
                    ("discovery",      "Network Discovery", "#f74fc8"),
                    ("upload",         "Script Upload",     "#a78bfa"),
                    ("upgrade",        "Upgrade RouterOS",  "#38bdf8"),
                    ("credentials",    "Credentials",       "#f78a4f"),
                    ("log",            "Log",               "#2adf8a"),
                    ("users",          "Users & Roles",     "#f74f6a"),
                    ("settings",       "Settings",          "#8896ab"),
                ]),
                ("Reference",      [
                    ("firstrun",       "Getting Started",   "#1b9ef7"),
                    ("faq",            "FAQ",               "#64748b"),
                    ("troubleshooting","Troubleshooting",   "#f74f4f"),
                ]),
            ]
        else:
            sb_groups = [
                ("Sezioni",        [
                    ("dashboard",      "Dashboard",         "#4f8ef7"),
                    ("sitemanager",    "Site Manager",      "#2adf8a"),
                    ("backup",         "Backup",            "#f7c44f"),
                    ("discovery",      "Network Discovery", "#f74fc8"),
                    ("upload",         "Script Upload",     "#a78bfa"),
                    ("upgrade",        "Upgrade RouterOS",  "#38bdf8"),
                    ("credentials",    "Credenziali SSH",   "#f78a4f"),
                    ("log",            "Log",               "#2adf8a"),
                    ("users",          "Utenti e Ruoli",    "#f74f6a"),
                    ("settings",       "Impostazioni",      "#8896ab"),
                ]),
                ("Riferimento",    [
                    ("firstrun",       "Primo Avvio",       "#1b9ef7"),
                    ("faq",            "FAQ",               "#64748b"),
                    ("troubleshooting","Problemi Comuni",   "#f74f4f"),
                ]),
            ]

        # Build sidebar HTML (groups + links)
        sb_parts = []
        for grp_label, grp_items in sb_groups:
            sb_parts.append(
                f'<div class="gd-sb-group">{grp_label}</div>'
            )
            for anchor, label, col in grp_items:
                sb_parts.append(
                    f'<a href="#{anchor}" class="gd-sb-link" data-anchor="{anchor}" '
                    f'style="--ac:{col};">'
                    f'<span class="gd-sb-dot" style="background:{col};"></span>{label}</a>'
                )
        sb_parts.append(
            f'<div style="margin-top:10px;border-top:1px solid var(--border);padding-top:8px;">'
            f'<a href="#" onclick="window.scrollTo({{top:0,behavior:\'smooth\'}});return false;" '
            f'class="gd-sb-link" style="color:var(--text3);font-size:10px;">↑ '
            + ("Back to top" if lang_en else "Torna su") +
            f'</a></div>'
        )
        sidebar_html = "\n".join(sb_parts)
        sections_html = "\n".join(sections)

        title_page = "Guide — ROSM" if lang_en else "Guida — ROSM"
        intro = (
            "Everything you need, section by section. Written by someone who uses it every day."
            if lang_en else
            "Tutto quello che ti serve, sezione per sezione. Scritto da chi lo usa ogni giorno."
        )

        content = f"""
<style>
.gd-layout{{display:grid;grid-template-columns:220px 1fr;gap:28px;align-items:start;max-width:1140px;}}
@media(max-width:820px){{.gd-layout{{grid-template-columns:1fr;}}
  .gd-sidebar{{position:static!important;margin-bottom:16px;}}}}
.gd-sidebar{{position:sticky;top:68px;background:var(--bg2);border:1px solid var(--border);
  border-radius:12px;padding:14px 10px;max-height:calc(100vh - 90px);overflow-y:auto;}}
.gd-sb-group{{font-size:9px;font-weight:700;color:var(--text3);text-transform:uppercase;
  letter-spacing:.7px;padding:10px 12px 4px;margin-top:2px;}}
.gd-sb-group:first-child{{padding-top:2px;}}
.gd-sb-link{{display:flex;align-items:center;gap:8px;padding:6px 10px;border-radius:7px;
  font-size:11.5px;font-weight:500;color:var(--text2);text-decoration:none;
  transition:all .14s;border-left:2px solid transparent;margin-bottom:1px;}}
.gd-sb-link:hover{{background:var(--bg3);color:var(--text);}}
.gd-sb-link.gd-active{{background:color-mix(in srgb,var(--ac,var(--accent)) 12%,transparent);
  color:var(--text);font-weight:700;border-left-color:var(--ac,var(--accent));}}
.gd-sb-dot{{width:7px;height:7px;border-radius:50%;flex-shrink:0;opacity:.7;transition:opacity .14s;}}
.gd-sb-link.gd-active .gd-sb-dot{{opacity:1;}}
.gd-card{{background:var(--bg2);border:1px solid var(--border);border-radius:12px;
  padding:22px 24px;margin-bottom:22px;scroll-margin-top:80px;}}
.gd-sections{{min-width:0;}}
</style>

<div style="margin-bottom:20px;display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap;">
  <div>
    <div style="font-size:21px;font-weight:800;color:var(--text);margin-bottom:4px;">{title_page}</div>
    <div style="font-size:12px;color:var(--text2);">{intro}</div>
  </div>
  <a href="/onboarding" style="display:inline-flex;align-items:center;gap:7px;padding:9px 18px;
    background:var(--accent);color:#fff;border-radius:8px;font-size:12px;font-weight:700;
    text-decoration:none;flex-shrink:0;transition:opacity .15s;" onmouseover="this.style.opacity='.85'"
    onmouseout="this.style.opacity='1'">
    <svg viewBox="0 0 16 16" fill="none" width="14" height="14"><path d="M8 1l2 5h5l-4 3 1.5 5L8 11l-4.5 3L5 9 1 6h5z" stroke="white" stroke-width="1.5" stroke-linejoin="round"/></svg>
    {"Quick Start" if lang_en else "Guida rapida"}
  </a>
</div>

<div style="max-width:1140px;margin-bottom:22px;display:flex;align-items:center;gap:14px;
            background:color-mix(in srgb,var(--accent) 7%,var(--bg2));
            border:1px solid color-mix(in srgb,var(--accent) 35%,transparent);
            border-radius:12px;padding:14px 20px;">
  <svg viewBox="0 0 24 24" fill="none" width="26" height="26" style="flex-shrink:0;">
    <rect x="2" y="5" width="20" height="14" rx="2.5" stroke="var(--accent)" stroke-width="1.8"/>
    <path d="M3 7l9 6 9-6" stroke="var(--accent)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>
  <div style="min-width:0;">
    <div style="font-size:12.5px;font-weight:700;color:var(--text);margin-bottom:2px;">
      {"Want to report a missing feature? Found a bug? Or simply have a tip for us?" if lang_en
        else "Vuoi segnalare una funzione che manca? Hai trovato un bug? Oppure vuoi semplicemente darci qualche dritta?"}
    </div>
    <div style="font-size:12px;color:var(--text2);">
      {"Write to us at:" if lang_en else "Scrivici a:"}
      <a href="mailto:Rosman.mail@icloud.com"
         style="color:var(--accent);font-weight:700;text-decoration:none;">Rosman.mail@icloud.com</a>
    </div>
  </div>
</div>

<div class="gd-layout">
  <nav class="gd-sidebar" id="gd-sidebar">
    {sidebar_html}
  </nav>
  <div class="gd-sections" id="gd-sections">
    {sections_html}
  </div>
</div>

<script>
(function(){{
  var links = document.querySelectorAll('.gd-sb-link[data-anchor]');
  var cards = document.querySelectorAll('.gd-card[id]');
  if(!links.length || !cards.length || !window.IntersectionObserver) return;

  function setActive(id){{
    links.forEach(function(l){{
      var isActive = l.getAttribute('data-anchor') === id;
      l.classList.toggle('gd-active', isActive);
    }});
    // scroll sidebar link into view if needed
    var activeLink = document.querySelector('.gd-sb-link.gd-active');
    if(activeLink){{
      var sb = document.getElementById('gd-sidebar');
      if(sb){{
        var lTop = activeLink.offsetTop;
        var lH   = activeLink.offsetHeight;
        var sTop = sb.scrollTop;
        var sH   = sb.clientHeight;
        if(lTop < sTop + 16) sb.scrollTop = lTop - 16;
        else if(lTop + lH > sTop + sH - 16) sb.scrollTop = lTop + lH - sH + 16;
      }}
    }}
  }}

  var observer = new IntersectionObserver(function(entries){{
    entries.forEach(function(e){{
      if(e.isIntersecting) setActive(e.target.id);
    }});
  }}, {{rootMargin: '-15% 0px -70% 0px', threshold: 0}});

  cards.forEach(function(c){{ observer.observe(c); }});

  // highlight first section on load
  if(cards.length) setActive(cards[0].id);
}})();
</script>
"""
        return self._page_shell(T("Guida"), content, session=session, page_key="guide")

    # ──────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────
    # Welcome page — shown after first-run setup wizard
    # ──────────────────────────────────────────────────────────
    def render_welcome_page(self, session):
        lang_en = LANGUAGE == "en"
        rec     = RECOVERY_CODE
        _dark   = ' data-theme="dark"' if _user_dark_mode(session) else ''

        if lang_en:
            _title    = "Welcome to ROSM"
            _sub      = "Your installation is ready. Before you start, read these four things."
            _tips = [
                ("<strong>This is your recovery code.</strong> It's the only way to regain access if you forget the admin password. "
                 "Write it down in a password manager or print it. Once you leave this page it won't be shown again during setup."),
                ("<strong>Never share the admin account.</strong> Create separate accounts for colleagues — use Manager for anyone "
                 "who operates the system, Viewer for anyone who just needs to monitor. It takes 30 seconds and removes a whole category of risk."),
                ("<strong>The encryption code protects your data.</strong> All SSH credentials and optionally backup files are "
                 "encrypted with it. It is generated automatically — copy it and keep it somewhere safe."),
                ("<strong>The tour that follows shows you every section of the app.</strong> It takes about 3 minutes "
                 "and creates demo data so you can see everything even on a fresh install. You can skip it or disable it permanently."),
            ]
            _rec_title = "Recovery code — save it now"
            _rec_warn  = "Copy it, write it down, store it in a password manager. Do not skip this."
            _btn_lbl   = "I've saved the code — start the tour →"
            _skip_lbl  = "Skip tour, go to app"
        else:
            _title    = "Benvenuto in ROSM"
            _sub      = "L'installazione è pronta. Prima di iniziare, leggi queste quattro cose."
            _tips = [
                ("<strong>Questo è il tuo codice di recupero.</strong> È l'unico modo per rientrare se dimentichi la password admin. "
                 "Scrivilo in un password manager o stampalo. Una volta uscito da questa pagina non ti verrà più mostrato durante il setup."),
                ("<strong>Non condividere mai l'account admin.</strong> Crea account separati per i colleghi — usa Manager per chi "
                 "opera sul sistema, Viewer per chi deve solo monitorare. Ci vogliono 30 secondi e si elimina un'intera categoria di rischio."),
                ("<strong>Il codice di cifratura protegge i tuoi dati.</strong> Tutte le credenziali SSH e, se hai abilitato la cifratura, i backup "
                 "sono protetti con esso. Viene generato automaticamente — copialo e conservalo in un posto sicuro."),
                ("<strong>Il tour che segue ti mostra ogni sezione dell'app.</strong> Dura circa 3 minuti "
                 "e crea dati demo così puoi vedere tutto anche su un'installazione vuota. Puoi saltarlo o disattivarlo per sempre."),
            ]
            _rec_title = "Codice di recupero — salvalo adesso"
            _rec_warn  = "Copialo, scrivilo, mettilo in un password manager. Non saltare questo passaggio."
            _btn_lbl   = "Ho salvato il codice — inizia il tour →"
            _skip_lbl  = "Salta il tour, vai all'app"

        tips_html = "".join(
            f'<li style="padding:10px 0;border-bottom:1px solid var(--border);font-size:12.5px;'
            f'display:flex;align-items:baseline;gap:10px;line-height:1.55;">'
            f'<span style="color:var(--accent);font-weight:900;font-size:15px;flex-shrink:0;">›</span>'
            f'<span>{t}</span></li>'
            for t in _tips
        )

        return f"""<!DOCTYPE html>
<html lang="{LANGUAGE}"{_dark}>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ROSM — {_title}</title>
{FAVICON_TAG}
<style>
{COMMON_CSS}
html,body{{height:100%;margin:0;display:flex;align-items:center;justify-content:center;
  background:var(--bg)!important;padding:16px;box-sizing:border-box;}}
.wl-outer{{display:flex;flex-direction:column;align-items:center;gap:0;width:600px;max-width:100%;}}
.wl-logo-area{{display:flex;flex-direction:column;align-items:center;padding:24px 0 14px;gap:6px;}}
.wl-logo-title{{font-size:26px;font-weight:900;color:var(--text);letter-spacing:-.5px;}}
.wl-wrap{{width:100%;background:var(--bg2);border-radius:18px;
  box-shadow:0 24px 72px rgba(0,0,0,.22);overflow:hidden;}}
.wl-ver-foot{{font-size:11px;color:var(--text3);padding:10px 0 0;text-align:center;}}
.wl-header{{background:var(--accent);padding:24px 36px 18px;}}
.wl-title{{font-size:20px;font-weight:900;color:#fff;margin-bottom:4px;}}
.wl-sub{{font-size:12.5px;color:rgba(255,255,255,.8);line-height:1.5;}}
.wl-body{{padding:24px 36px 28px;}}
.wl-rec{{background:rgba(217,119,6,.07);border:1.5px solid rgba(217,119,6,.4);
  border-radius:12px;padding:18px 20px;margin-bottom:20px;}}
.wl-rec-title{{font-size:11px;font-weight:800;color:#b45309;text-transform:uppercase;
  letter-spacing:.7px;margin-bottom:10px;}}
.wl-rec-code{{font-family:var(--mono);font-size:22px;font-weight:900;color:var(--text);
  letter-spacing:3px;text-align:center;background:var(--bg3);border:1px solid var(--border2);
  border-radius:8px;padding:12px 10px;margin-bottom:10px;cursor:pointer;user-select:all;
  transition:background .15s;}}
.wl-rec-code:hover{{background:var(--bg);}}
.wl-rec-warn{{font-size:11.5px;color:var(--text2);line-height:1.5;}}
.wl-copy-btn{{display:block;width:100%;margin-top:10px;padding:7px;font-size:11px;
  font-weight:700;background:rgba(217,119,6,.15);border:1px solid rgba(217,119,6,.35);
  color:#b45309;border-radius:6px;cursor:pointer;transition:all .15s;}}
.wl-copy-btn:hover{{background:rgba(217,119,6,.25);}}
.wl-tips{{list-style:none;margin:0 0 20px;padding:0;}}
.wl-actions{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;}}
.wl-btn{{padding:11px 22px;font-size:13px;font-weight:700;background:var(--accent);
  color:#fff;border:none;border-radius:8px;cursor:pointer;text-decoration:none;
  display:inline-flex;align-items:center;transition:opacity .15s;}}
.wl-btn:hover{{opacity:.87;color:#fff;text-decoration:none;}}
.wl-skip{{font-size:11px;color:var(--text3);text-decoration:none;margin-left:auto;padding:4px;}}
</style>
</head>
<body>
<div class="wl-outer">
  <div class="wl-logo-area">
    <svg width="80" height="80" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="64" height="64" rx="16" fill="#2563EB"/>
      <rect x="10" y="16" width="44" height="30" rx="4" fill="none" stroke="white" stroke-width="3"/>
      <path d="M20 46 L44 46" stroke="white" stroke-width="3" stroke-linecap="round"/>
      <path d="M32 46 L32 52" stroke="white" stroke-width="3" stroke-linecap="round"/>
      <circle cx="24" cy="26" r="4" fill="white"/>
      <rect x="30" y="24" width="16" height="2.5" rx="1.25" fill="white" opacity=".7"/>
      <rect x="30" y="29" width="10" height="2.5" rx="1.25" fill="white" opacity=".5"/>
    </svg>
    <div class="wl-logo-title">ROSM</div>
  </div>
  <div class="wl-wrap">
  <div class="wl-header">
    <div class="wl-title">{_title}</div>
    <div class="wl-sub">{_sub}</div>
  </div>
  <div class="wl-body">
    <div class="wl-rec">
      <div class="wl-rec-title">{_rec_title}</div>
      <div class="wl-rec-code" id="rec-code" title="Click to select">{rec}</div>
      <div class="wl-rec-warn">{_rec_warn}</div>
      <button class="wl-copy-btn" onclick="copyRec()">Copia</button>
    </div>
    <ul class="wl-tips">{tips_html}</ul>
    <div class="wl-actions">
      <a href="/onboarding?step=1" class="wl-btn">{_btn_lbl}</a>
      <a href="/home" class="wl-skip">{_skip_lbl}</a>
    </div>
  </div>
  </div>
  <div class="wl-ver-foot">ROSM v{APP_VERSION}</div>
</div>
<script>
function copyRec(){{
  var code = document.getElementById('rec-code').textContent.trim();
  navigator.clipboard.writeText(code).then(function(){{
    var b = document.querySelector('.wl-copy-btn');
    var old = b.textContent;
    b.textContent = '{"Copied!" if lang_en else "Copiato!"}';
    setTimeout(function(){{b.textContent=old;}}, 2000);
  }});
}}
</script>
</body>
</html>"""

    # Onboarding wizard  (/onboarding?step=1..7)
    # ──────────────────────────────────────────────────────────
    def render_onboarding_page(self, session, step=1):
        lang_en = LANGUAGE == "en"
        steps_total = 7

        # Progress dots — pre-computed outside f-string
        _ob_dots = "".join(
            '<span style="display:inline-block;width:9px;height:9px;border-radius:50%;margin:0 4px;background:'
            + ("#fff" if i == step else "rgba(255,255,255,.4)")
            + ';transition:background .2s;"></span>'
            for i in range(1, steps_total + 1)
        )

        # Per-step accent colour
        _ob_colors = {1: "#1b3a6b", 2: "#4f8ef7", 3: "#f78a4f",
                      4: "#f7b24f", 5: "#a78bfa", 6: "#38bdf8", 7: "#2adf8a"}
        _ob_color = _ob_colors.get(step, "#1b3a6b")

        # SVG icons (60×60, white strokes on transparent bg)
        _ob_icons = {
            1: '<svg viewBox="0 0 60 60" fill="none" width="60" height="60">'
               '<path d="M10 48 Q30 8 50 48" stroke="white" stroke-width="3" stroke-linecap="round"/>'
               '<circle cx="30" cy="28" r="6" fill="white" opacity=".9"/>'
               '<line x1="30" y1="34" x2="30" y2="48" stroke="white" stroke-width="2.5" stroke-linecap="round"/>'
               '<line x1="18" y1="42" x2="30" y2="48" stroke="white" stroke-width="2" stroke-linecap="round" opacity=".6"/>'
               '<line x1="42" y1="42" x2="30" y2="48" stroke="white" stroke-width="2" stroke-linecap="round" opacity=".6"/>'
               '</svg>',
            2: '<svg viewBox="0 0 60 60" fill="none" width="60" height="60">'
               '<rect x="6" y="6" width="22" height="22" rx="4" fill="white" opacity=".9"/>'
               '<rect x="32" y="6" width="22" height="22" rx="4" fill="white" opacity=".65"/>'
               '<rect x="6" y="32" width="22" height="22" rx="4" fill="white" opacity=".65"/>'
               '<rect x="32" y="32" width="22" height="22" rx="4" fill="white" opacity=".4"/>'
               '</svg>',
            3: '<svg viewBox="0 0 60 60" fill="none" width="60" height="60">'
               '<rect x="16" y="26" width="28" height="24" rx="5" stroke="white" stroke-width="3"/>'
               '<path d="M22 26V20a8 8 0 0116 0v6" stroke="white" stroke-width="3" stroke-linecap="round"/>'
               '<circle cx="30" cy="38" r="4" fill="white"/>'
               '<line x1="30" y1="42" x2="30" y2="46" stroke="white" stroke-width="2.5" stroke-linecap="round"/>'
               '</svg>',
            4: '<svg viewBox="0 0 60 60" fill="none" width="60" height="60">'
               '<path d="M30 8v28" stroke="white" stroke-width="3" stroke-linecap="round"/>'
               '<path d="M18 24l12 12 12-12" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
               '<rect x="10" y="44" width="40" height="8" rx="3" fill="white" opacity=".5"/>'
               '</svg>',
            5: '<svg viewBox="0 0 60 60" fill="none" width="60" height="60">'
               '<circle cx="22" cy="20" r="9" stroke="white" stroke-width="3"/>'
               '<path d="M6 52c0-8.8 7.2-16 16-16" stroke="white" stroke-width="3" stroke-linecap="round"/>'
               '<circle cx="42" cy="28" r="7" stroke="white" stroke-width="2.5"/>'
               '<path d="M28 52c0-7.7 6.3-14 14-14s14 6.3 14 14" stroke="white" stroke-width="2.5" stroke-linecap="round"/>'
               '</svg>',
            6: '<svg viewBox="0 0 60 60" fill="none" width="60" height="60">'
               '<path d="M30 52V20" stroke="white" stroke-width="3" stroke-linecap="round"/>'
               '<path d="M18 32l12-12 12 12" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
               '<rect x="10" y="8" width="40" height="6" rx="3" fill="white" opacity=".5"/>'
               '</svg>',
            7: '<svg viewBox="0 0 60 60" fill="none" width="60" height="60">'
               '<circle cx="30" cy="30" r="24" stroke="white" stroke-width="3"/>'
               '<path d="M18 30l8 8 16-16" stroke="white" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/>'
               '</svg>',
        }
        _ob_icon = _ob_icons.get(step, _ob_icons[1])

        # Nav-bar mockup helper — shows app menu chips with one highlighted
        _nav_chips_it = [
            ("Dashboard","Dashboard"), ("Siti","Sites"), ("Backup","Backup"),
            ("Credenziali","Credentials"), ("Log","Log"), ("Utenti","Users"),
        ]
        def _nav_bar(active_idx, color):
            _lbl = "Navigation" if lang_en else "Navigazione"
            _html = (
                '<div style="background:var(--bg3);border:1px solid var(--border);'
                'border-radius:9px;padding:10px 14px;margin-bottom:14px;">'
                '<div style="font-size:9px;font-weight:700;color:var(--text3);'
                'text-transform:uppercase;letter-spacing:.8px;margin-bottom:9px;">'
                + _lbl + '</div>'
                '<div style="display:flex;flex-wrap:wrap;gap:5px;align-items:center;">'
            )
            for _i, (_it, _en) in enumerate(_nav_chips_it):
                _chip = _en if lang_en else _it
                if _i == active_idx:
                    _html += (
                        '<span style="display:inline-flex;align-items:center;gap:5px;'
                        'padding:5px 12px;border-radius:7px;font-size:10.5px;font-weight:700;'
                        'background:' + color + ';color:#fff;'
                        'box-shadow:0 2px 10px ' + color + '44;">'
                        + _chip +
                        '<span style="font-size:8px;opacity:.8;margin-left:2px;">◀</span></span>'
                    )
                else:
                    _html += (
                        '<span style="padding:5px 11px;border-radius:7px;font-size:10.5px;'
                        'color:var(--text3);background:var(--bg2);border:1px solid var(--border);">'
                        + _chip + '</span>'
                    )
            _html += '</div></div>'
            return _html

        # Per-step content (title, subtitle, items, prev, next, next_label)
        if step == 1:
            _ob_title    = "Welcome to ROSM" if lang_en else "Benvenuto in ROSM"
            _ob_subtitle = ("You manage MikroTik routers. ROSM puts them all in one place."
                            if lang_en else
                            "Gestisci router MikroTik. ROSM li mette tutti in un posto solo.")
            _ob_items = (
                [
                    "The basic flow is simple: set up <strong>credentials</strong> → <strong>scan the network</strong> in Network Discovery → <strong>import</strong> what you find → your routers appear on the Dashboard.",
                    "From the Dashboard you monitor everything: live status, last ping, open SSH sessions — all in one screen, updating every 30 seconds.",
                    "Set up automatic backups once — ROSM runs them on a schedule, keeps the last N days and cleans up old files by itself.",
                    "Need to push a script to 40 routers? Three clicks. No manual SSH into each one.",
                    "There are different access levels with different privileges — from read-only monitoring to full admin control.",
                ] if lang_en else [
                    "Il flusso base è semplice: configuri le <strong>credenziali</strong> → <strong>scansioni la rete</strong> con Network Discovery → <strong>importi</strong> quello che hai trovato → i router appaiono sulla Dashboard.",
                    "Dalla Dashboard monitori tutto: stato live, ultimo ping, sessioni SSH aperte — tutto su una schermata, aggiornato ogni 30 secondi.",
                    "Configuri i backup automatici una volta sola — ROSM li fa su pianificazione, conserva gli ultimi N giorni e pulisce i vecchi file da solo.",
                    "Devi mandare uno script su 40 router? Tre click. Senza entrare manualmente su nessuno di essi.",
                    "Ci sono tipologie di accesso con privilegi differenti — dalla visibilità in sola lettura fino al controllo admin completo.",
                ]
            )
            _ob_prev     = None
            _ob_next     = "/credentials?tour=2"
            _ob_next_lbl = "Next →" if lang_en else "Avanti →"
            _ob_nav_html = ""
        elif step == 2:
            _ob_title    = "SSH Credentials" if lang_en else "Credenziali SSH"
            _ob_subtitle = ("First thing first: create your credentials before anything else."
                            if lang_en else
                            "Prima cosa: crea le credenziali prima di qualsiasi altra operazione.")
            _ob_items = (
                [
                    "Credentials are how ROSM connects to your routers. Without them, no SSH, no backups and no script deployment.",
                    'Click <strong>"+ New credentials"</strong>, give it a name, then enter the SSH username and password.',
                    "You can create multiple sets — one per customer or one per network — and assign each one to a site.",
                    "Passwords are encrypted with AES-128. They are never shown in the interface and can only be revealed with the admin recovery code.",
                    "Tip: create your credentials here first, then go to Site Manager to create a site and link the credentials to it.",
                ] if lang_en else [
                    "Le credenziali sono il modo in cui ROSM si connette ai router. Senza, niente SSH, backup e script.",
                    'Clicca <strong>"+ Nuove credenziali"</strong>, dagli un nome, poi inserisci username SSH e password.',
                    "Puoi creare più set — uno per cliente o uno per rete — e assegnarne uno a ciascun sito.",
                    "Le password sono cifrate con AES-128. Non vengono mai mostrate nell'interfaccia e si possono rivelare solo con il recovery code admin.",
                    "Consiglio: crea le credenziali qui prima, poi vai al Site Manager per creare un sito e collegare le credenziali.",
                ]
            )
            _ob_prev     = "/onboarding?step=1"
            _ob_next     = "/onboarding?step=3"
            _ob_next_lbl = "Next →" if lang_en else "Avanti →"
            _ob_nav_html = _nav_bar(3, _ob_color)   # Credenziali/Credentials highlighted
        elif step == 3:
            _ob_title    = "Site Manager" if lang_en else "Site Manager"
            _ob_subtitle = ("Group routers by site and assign credentials to them."
                            if lang_en else
                            "Raggruppa i router per sede e associa le credenziali.")
            _ob_items = (
                [
                    "A <strong>site</strong> is a named group of routers — for example a branch office, a data centre, or a customer network.",
                    "Click <strong>'+ New Site'</strong>, give it a name, then assign a credential set to it. Every router you put in this site will use those credentials automatically.",
                    "This is the step that makes everything automatic: once credentials are tied to a site, backups, scripts and SSH operations all pick them up without any extra configuration.",
                    "Routers imported without a site appear in the <em>Unassigned</em> section — you can drag or bulk-assign them into a site at any time.",
                    "After creating the site, go to Network Discovery to scan your subnet and import routers directly into it.",
                ] if lang_en else [
                    "Un <strong>sito</strong> è un gruppo di router con un nome — ad esempio una sede, un datacenter o la rete di un cliente.",
                    "Clicca <strong>'+ Nuova Sede'</strong>, dagli un nome, poi associa un set di credenziali. Ogni router che inserisci in questo sito userà quelle credenziali automaticamente.",
                    "Questo è il passaggio che rende tutto automatico: una volta che le credenziali sono collegate al sito, backup, script e SSH le usano senza ulteriori configurazioni.",
                    "I router importati senza sito appaiono nella sezione <em>Non assegnati</em> — puoi spostarli in un sito in blocco o uno alla volta.",
                    "Dopo aver creato il sito, vai su Network Discovery per scansionare la subnet e importare i router direttamente.",
                ]
            )
            _ob_prev     = "/onboarding?step=2"
            _ob_next     = "/onboarding?step=4"
            _ob_next_lbl = "Next →" if lang_en else "Avanti →"
            _ob_nav_html = _nav_bar(1, _ob_color)   # Siti/Sites highlighted
        elif step == 4:
            _ob_title    = "Network Discovery" if lang_en else "Network Discovery"
            _ob_subtitle = ("Scan your subnet and import routers into ROSM."
                            if lang_en else
                            "Scansiona la subnet e importa i router in ROSM.")
            _ob_items = (
                [
                    "Enter a CIDR subnet and click <strong>Scan</strong>. ROSM pings every address and checks for open ports — a /24 takes about 30–60 seconds.",
                    "<strong>Select a credential set before importing</strong> — the credentials are saved with each router so everything works immediately after import.",
                    "Results appear in the table on the right. Check the boxes on the rows you want, then click <strong>'Add selected'</strong>.",
                    "After importing, ROSM takes you to the Site Manager so you can assign the new routers to a site right away.",
                    "Run Discovery as many times as needed — on different subnets or after adding new hardware.",
                ] if lang_en else [
                    "Inserisci una subnet CIDR e clicca <strong>Scansiona</strong>. ROSM fa ping a ogni indirizzo e controlla le porte aperte — una /24 richiede circa 30–60 secondi.",
                    "<strong>Seleziona un set di credenziali prima di importare</strong> — le credenziali vengono salvate con ogni router in modo che tutto funzioni subito dopo l'import.",
                    "I risultati appaiono nella tabella a destra. Spunta le righe che vuoi, poi clicca <strong>'Aggiungi selezionati'</strong>.",
                    "Dopo l'import, ROSM ti porta al Site Manager per poter subito assegnare i nuovi router a un sito.",
                    "Esegui Discovery tutte le volte che vuoi — su subnet diverse o dopo aver aggiunto nuovo hardware.",
                ]
            )
            _ob_prev     = "/onboarding?step=3"
            _ob_next     = "/onboarding?step=5"
            _ob_next_lbl = "Next →" if lang_en else "Avanti →"
            _ob_nav_html = ""   # Discovery has no nav bar entry
        elif step == 5:
            _ob_title    = "Dashboard" if lang_en else "Dashboard"
            _ob_subtitle = ("Your imported routers are here. Monitor the whole fleet at a glance."
                            if lang_en else
                            "I router importati sono qui. Monitora tutta la flotta in un colpo d'occhio.")
            _ob_items = (
                [
                    "Every imported router appears here with live status: ONLINE, OFFLINE, or not pinged yet. Status updates every 30 seconds.",
                    "The bar at the top shows total routers, online, offline, and active SSH sessions right now.",
                    "Filter by IP, name, tag, group or site as you type — use <strong>Tags</strong> to group routers and target them for bulk backups or script deploys.",
                    "Click <strong>SSH</strong> on any row to read live info from that router: hostname, ROS version, uptime, CPU.",
                    "<strong>Ping All</strong> forces an immediate status refresh on the whole fleet. Use it after a network change or a power event.",
                ] if lang_en else [
                    "Ogni router importato appare qui con lo stato live: ONLINE, OFFLINE, o non ancora pingato. Lo stato si aggiorna ogni 30 secondi.",
                    "La barra in cima mostra router totali, online, offline e sessioni SSH aperte adesso.",
                    "Filtra per IP, nome, tag, gruppo o sede mentre scrivi — usa i <strong>Tag</strong> per raggruppare i router e usarli come target per backup o script di massa.",
                    "Clicca <strong>SSH</strong> su una riga per leggere le info live dal router: hostname, versione ROS, uptime, CPU.",
                    "<strong>Ping All</strong> forza un aggiornamento immediato su tutta la flotta. Usalo dopo una modifica di rete o un evento di alimentazione.",
                ]
            )
            _ob_prev     = "/onboarding?step=4"
            _ob_next     = "/onboarding?step=6"
            _ob_next_lbl = "Next →" if lang_en else "Avanti →"
            _ob_nav_html = _nav_bar(0, _ob_color)   # Dashboard highlighted
        elif step == 6:
            _ob_title    = "Automated Backup" if lang_en else "Backup automatico"
            _ob_subtitle = ("Configure once, forget about it. Backups run by themselves."
                            if lang_en else
                            "Configuri una volta, dimentichi. I backup girano da soli.")
            _ob_items = (
                [
                    "Enable the scheduler, set how often to run (in hours) and how many days to keep files. ROSM does the rest.",
                    "Set interval to <strong>0.01</strong> (about 1 minute) to test that credentials and connectivity are correct — then switch to 24 for daily.",
                    '<strong>Show-sensitive</strong> includes passwords and keys in the exported config — recommended for a complete restore.',
                    '<strong>Leave on router</strong> saves an extra copy in the router\'s flash memory using <code>/export file=...</code>.',
                    "Run a manual backup first: if it succeeds, your credentials are correct and the automatic scheduler will work the same way.",
                    "Retention deletes files older than N days after each cycle — configure it once and forget about it.",
                ] if lang_en else [
                    "Abilita il pianificatore, imposta ogni quante ore girare e per quanti giorni tenere i file. ROSM fa il resto.",
                    "Imposta l'intervallo a <strong>0.01</strong> (circa 1 minuto) per verificare che credenziali e connettività siano corrette — poi passa a 24 per il giornaliero.",
                    '<strong>Show-sensitive</strong> include password e chiavi nella config esportata — consigliato per un ripristino completo.',
                    '<strong>Lascia sul router</strong> salva una copia extra nella flash del router tramite <code>/export file=...</code>.',
                    "Prima esegui un backup manuale: se funziona, le credenziali sono corrette e il pianificatore funzionerà allo stesso modo.",
                    "La retention elimina i file più vecchi di N giorni dopo ogni ciclo — configurala una volta e non ci pensare più.",
                ]
            )
            _ob_prev     = "/onboarding?step=5"
            _ob_next     = "/onboarding?step=7"
            _ob_next_lbl = "Next →" if lang_en else "Avanti →"
            _ob_nav_html = _nav_bar(2, _ob_color)   # Backup highlighted
        else:  # step 7 — final card
            _ob_title    = "You're all set!" if lang_en else "Sei pronto!"
            _ob_subtitle = ("Here's a quick recap of the recommended setup flow."
                            if lang_en else
                            "Ecco un riepilogo del flusso di configurazione consigliato.")
            _ob_items = (
                [
                    "① <strong>Credentials</strong>: create at least one SSH credential set. Everything else depends on this.",
                    "② <strong>Site Manager</strong>: create a site and assign the credential set to it.",
                    "③ <strong>Network Discovery</strong>: scan your subnet, pick the routers you found, import them. ROSM takes you to Site Manager so you can assign them.",
                    "④ <strong>Dashboard</strong>: verify the routers appear ONLINE and SSH works on at least one.",
                    "⑤ <strong>Backup</strong>: run a manual backup on one router. If it works, enable the scheduler.",
                    "Something not working? Check the <strong>Log</strong> — every operation is recorded with the full error detail.",
                ] if lang_en else [
                    "① <strong>Credenziali</strong>: crea almeno un set di credenziali SSH. Tutto il resto dipende da questo.",
                    "② <strong>Site Manager</strong>: crea un sito e associa il set di credenziali.",
                    "③ <strong>Network Discovery</strong>: scansiona la subnet, scegli i router trovati, importali. ROSM ti porta al Site Manager per assegnarli.",
                    "④ <strong>Dashboard</strong>: verifica che i router siano ONLINE e che SSH funzioni su almeno uno.",
                    "⑤ <strong>Backup</strong>: fai un backup manuale su un router. Se funziona, abilita il pianificatore.",
                    "Qualcosa non funziona? Controlla il <strong>Log</strong> — ogni operazione è tracciata con il dettaglio completo.",
                ]
            )
            _ob_prev     = "/onboarding?step=6"
            _ob_next     = "/home"
            _ob_next_lbl = "Go to Dashboard →" if lang_en else "Vai al Dashboard →"
            _ob_nav_html = ""

        # Build items HTML (no f-string — avoids quote conflicts)
        _ob_items_html = ""
        for _it in _ob_items:
            _ob_items_html += (
                '<li style="padding:8px 0;border-bottom:1px solid var(--border);font-size:12.5px;'
                'display:flex;align-items:baseline;gap:9px;">'
                '<span style="color:' + _ob_color + ';font-weight:900;font-size:14px;flex-shrink:0;line-height:1;">›</span>'
                '<span style="line-height:1.55;">' + _it + '</span>'
                '</li>'
            )

        # Previous button (or empty spacer)
        if _ob_prev:
            _ob_prev_html = (
                '<a href="' + _ob_prev + '" class="btn" style="font-size:12px;padding:9px 18px;">'
                + ("← Back" if lang_en else "← Indietro") + '</a>'
            )
        else:
            _ob_prev_html = '<span></span>'

        # "Read guide" button on last step
        _ob_guide_html = (
            '<a href="/guide" class="btn" style="font-size:12px;padding:9px 18px;">'
            + ("Full guide →" if lang_en else "Guida completa →") + '</a>'
        ) if step == steps_total else ""

        # Skip link (all steps except last)
        _ob_skip_html = (
            '<a href="/home" style="font-size:11px;color:var(--text3);text-decoration:none;'
            'margin-left:auto;padding:9px 4px;">'
            + ("Skip" if lang_en else "Salta") + '</a>'
        ) if step < steps_total else ""

        # Step 1: auto-tour dismiss checkbox + JS intercept on navigation
        _ob_dismiss_html = ""
        _ob_next_onclick = ""
        _ob_step1_script = ""
        if step == 1:
            _dismiss_lbl = "Don't show this tour again" if lang_en else "Non visualizzare più questo tour"
            _ob_dismiss_html = (
                '<label style="display:flex;align-items:center;gap:8px;font-size:12px;'
                'color:var(--text3);cursor:pointer;margin-bottom:2px;padding:10px 0 4px;">'
                '<input type="checkbox" id="ob-dismiss" style="accent-color:var(--text3);'
                'width:14px;height:14px;cursor:pointer;flex-shrink:0;">'
                + _dismiss_lbl + '</label>'
            )
            # Override skip link with JS version
            _ob_skip_html = (
                '<a href="javascript:void(0)" onclick="obSkip()" '
                'style="font-size:11px;color:var(--text3);text-decoration:none;'
                'margin-left:auto;padding:9px 4px;cursor:pointer;">'
                + ("Skip" if lang_en else "Salta") + '</a>'
            )
            _ob_next_onclick = ' onclick="obNext();return false;"'
            _ob_step1_script = (
                '<script>'
                'function obNext(){'
                'var cb=document.getElementById("ob-dismiss");'
                'if(cb&&cb.checked){'
                'fetch("/api/tour_dismiss",{method:"POST"}).then(function(){location.href="/onboarding?step=2";});'
                '}else{location.href="/onboarding?step=2";}}'
                'function obSkip(){'
                'var cb=document.getElementById("ob-dismiss");'
                'if(cb&&cb.checked){'
                'fetch("/api/tour_dismiss",{method:"POST"}).then(function(){location.href="/home";});'
                '}else{location.href="/home";}}'
                '</script>'
            )

        # Step counter label
        _ob_counter = f'{step} / {steps_total}'

        _dark = ' data-theme="dark"' if _user_dark_mode(session) else ''
        _ob_page_title = "Quick Start — ROSM" if lang_en else "Guida rapida — ROSM"

        return f"""<!DOCTYPE html>
<html lang="{LANGUAGE}"{_dark}>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_ob_page_title}</title>
{FAVICON_TAG}
<style>
{COMMON_CSS}
html,body{{height:100%;margin:0;display:flex;align-items:center;justify-content:center;
  background:var(--bg) !important;padding:16px;box-sizing:border-box;}}
.ob-wrap{{width:560px;max-width:100%;background:var(--bg2);border-radius:18px;
  box-shadow:0 24px 72px rgba(0,0,0,.22);overflow:hidden;}}
.ob-header{{background:{_ob_color};padding:30px 36px 26px;text-align:center;}}
.ob-dots{{margin-bottom:14px;display:flex;justify-content:center;align-items:center;gap:0;}}
.ob-counter{{font-size:10px;font-weight:700;color:rgba(255,255,255,.55);
  letter-spacing:.6px;margin-bottom:12px;text-transform:uppercase;}}
.ob-icon{{display:flex;align-items:center;justify-content:center;margin-bottom:12px;}}
.ob-title{{font-size:21px;font-weight:900;color:#fff;margin-bottom:5px;letter-spacing:-.2px;}}
.ob-sub{{font-size:12.5px;color:rgba(255,255,255,.8);line-height:1.5;}}
.ob-body{{padding:24px 36px 22px;}}
.ob-items{{list-style:none;margin:0 0 18px;padding:0;}}
.ob-actions{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}}
.ob-next{{padding:10px 22px;font-size:12.5px;font-weight:700;background:{_ob_color};
  color:#fff;border:none;border-radius:8px;cursor:pointer;text-decoration:none;
  display:inline-flex;align-items:center;letter-spacing:.2px;transition:opacity .15s;}}
.ob-next:hover{{opacity:.87;}}
</style>
</head>
<body>
<div class="ob-wrap">
  <div class="ob-header">
    <div class="ob-dots">{_ob_dots}</div>
    <div class="ob-counter">{_ob_counter}</div>
    <div class="ob-icon">{_ob_icon}</div>
    <div class="ob-title">{_ob_title}</div>
    <div class="ob-sub">{_ob_subtitle}</div>
  </div>
  <div class="ob-body">
    {_ob_nav_html}<ul class="ob-items">{_ob_items_html}</ul>
    {_ob_dismiss_html}
    <div class="ob-actions">
      {_ob_prev_html}
      {_ob_guide_html}
      {_ob_skip_html}
      <a href="{_ob_next}" class="ob-next"{_ob_next_onclick}>{_ob_next_lbl}</a>
    </div>
  </div>
</div>
{_ob_step1_script}
</body>
</html>"""

    # ──────────────────────────────────────────────────────────
    # Setup Wizard
    # ──────────────────────────────────────────────────────────
    def render_wizard_page(self, step=1, ctx=None):
        ctx = ctx or {}
        lang_en = LANGUAGE == "en"
        rec_code = RECOVERY_CODE
        steps_total = 7
        step_labels = {
            1: ("1", "Language"   if lang_en else "Lingua"),
            2: ("2", "Profile"    if lang_en else "Profilo"),
            3: ("3", "Security"   if lang_en else "Sicurezza"),
            4: ("4", "Data"       if lang_en else "Dati"),
            5: ("5", "Frontend Access" if lang_en else "Accesso Frontend"),
            6: ("6", "Updates"    if lang_en else "Aggiornamenti"),
            7: ("7", "Ready"      if lang_en else "Pronto"),
        }
        _dots = ""
        for i, (ico, lbl) in step_labels.items():
            dot_cls = "wz-dot-active" if i == step else ("wz-dot-done" if i < step else "")
            dot_txt = "✓" if i < step else ico
            _dots += f'<div class="wz-dot {dot_cls}">{dot_txt}</div>'
            if i < len(step_labels):
                line_cls = "wz-line-done" if i < step else ""
                _dots += f'<div class="wz-line {line_cls}"></div>'
        steps_html = (f'<div class="wz-dots-row">{_dots}</div>'
                      f'<div class="wz-active-lbl">{step_labels[step][1]}</div>')
        err_html = f'<div class="wz-err">{ctx.get("error","")}</div>' if ctx.get("error") else ""

        if step == 1:
            body = f"""
<div class="wz-title">{"Welcome to ROSM" if lang_en else "Benvenuto in ROSM"}</div>
<p class="wz-sub">{"Choose your interface language. You can change it later in Settings." if lang_en else "Scegli la lingua dell'interfaccia. Potrai cambiarla in seguito nelle Impostazioni."}</p>
<div class="lang-grid">
  <label class="lang-card {"lang-sel" if not lang_en else ""}">
    <input type="radio" name="language" value="it" {"checked" if not lang_en else ""}>
    <span class="lang-flag" style="font-size:20px;font-weight:800;color:var(--accent);">IT</span>
    <span class="lang-name">Italiano</span>
  </label>
  <label class="lang-card {"lang-sel" if lang_en else ""}">
    <input type="radio" name="language" value="en" {"checked" if lang_en else ""}>
    <span class="lang-flag" style="font-size:20px;font-weight:800;color:var(--accent);">EN</span>
    <span class="lang-name">English</span>
  </label>
</div>
<form method="POST" action="/setup?step=1">
  <input type="hidden" name="language" id="langHidden" value="{"en" if lang_en else "it"}">
  <div class="wz-actions">
    <button type="submit" class="btn btn-primary wz-btn">{"Next →" if lang_en else "Avanti →"}</button>
  </div>
</form>
<script>
document.querySelectorAll('.lang-card input').forEach(function(r){{
  r.addEventListener('change',function(){{
    document.querySelectorAll('.lang-card').forEach(function(c){{c.classList.remove('lang-sel');}});
    this.closest('.lang-card').classList.add('lang-sel');
    document.getElementById('langHidden').value=this.value;
  }});
}});
</script>
<div style="margin-top:18px;border-top:1px solid var(--border);padding-top:14px;text-align:center;">
  <p style="font-size:11px;color:var(--text3);line-height:1.75;margin-bottom:5px;">
    {"ROSM is a completely free project. Have a suggestion or idea?" if lang_en
      else "ROSM e un progetto completamente gratuito. Hai un suggerimento o un'idea?"}
  </p>
  <a href="mailto:Rosman.mail@icloud.com"
     style="font-size:12px;color:var(--accent);font-weight:700;text-decoration:none;">Rosman.mail@icloud.com</a>
  <p style="font-size:10px;color:var(--text3);margin-top:8px;line-height:1.65;">
    {"If you want, you could offer me a " if lang_en else "Se ti va, puoi offrirmi "}
    <span style="text-decoration:line-through;color:#e05252;font-style:italic;
                 text-decoration-thickness:2px;text-decoration-color:#e05252;">{"a coffee" if lang_en else "un caffe"}</span>
    <a href="https://buymeacoffee.com/rosm" target="_blank" rel="noopener"
       style="text-decoration:none;color:inherit;">{" a beer" if lang_en else " una birra"}</a>
    <span style="font-size:9px;"> {"(just kidding — but I am definitely more of a beer person)" if lang_en
      else "(ovviamente si scherza — ma sono decisamente piu un tipo da birra)"}</span>
  </p>
</div>"""

        elif step == 2:
            cur_name = _get_display_name("admin")
            if cur_name == "admin":
                cur_name = ""
            body = f"""
<div class="wz-title">{"Profile" if lang_en else "Profilo"}</div>
<p class="wz-sub">{"How should ROSM greet you? You can change this later in Settings." if lang_en else "Come vuoi che ROSM ti saluti? Potrai cambiarlo in seguito nelle Impostazioni."}</p>
{err_html}
<form method="POST" action="/setup?step=2">
  <div class="wz-field">
    <label>{"Your name" if lang_en else "Il tuo nome"}</label>
    <input type="text" name="display_name" maxlength="50" autocomplete="name"
           value="{cur_name}"
           placeholder="{"e.g. your display name" if lang_en else "es. nome visualizzato"}">
    <div style="font-size:10px;color:var(--text3);margin-top:4px;">
      {"Leave empty to keep using your username." if lang_en else "Lascia vuoto per usare il nome utente."}
    </div>
  </div>
  <div class="wz-actions">
    <a href="/setup?step=1" class="btn">{"← Back" if lang_en else "← Indietro"}</a>
    <button type="submit" class="btn btn-primary wz-btn">{"Next →" if lang_en else "Avanti →"}</button>
  </div>
</form>"""

        elif step == 3:
            body = f"""
<div class="wz-title">{"Security" if lang_en else "Sicurezza"}</div>
<p class="wz-sub">{"Set a strong admin password and save your recovery code." if lang_en else "Imposta una password sicura per l'admin e salva il tuo codice di recupero."}</p>
{err_html}
<form method="POST" action="/setup?step=3">
  <div class="wz-field">
    <label>{"New admin password" if lang_en else "Nuova password admin"}</label>
    <input type="password" name="new_password" minlength="8" required
           placeholder="{"Min 8 characters" if lang_en else "Minimo 8 caratteri"}">
  </div>
  <div class="wz-field">
    <label>{"Confirm password" if lang_en else "Conferma password"}</label>
    <input type="password" name="confirm_password" required
           placeholder="{"Repeat the password" if lang_en else "Ripeti la password"}">
  </div>

  <div class="wz-recovery-box">
    <div class="wz-recovery-title">
      {"Account recovery code" if lang_en else "Codice di recupero account"}
    </div>
    <div class="wz-recovery-code">{rec_code}</div>
    <div class="wz-recovery-sub">
      {"! Save this code somewhere safe (password manager, printed paper). It is your only way to reset the password if you forget it." if lang_en else "! Salva questo codice in un posto sicuro (password manager, foglio stampato). E l'unico modo per reimpostare la password se la dimentichi."}
    </div>
    <button type="button" onclick="copyCode()" class="btn" style="margin-top:8px;font-size:11px;">
      {"Copy" if lang_en else "Copia"}
    </button>
  </div>

  <div class="wz-actions">
    <a href="/setup?step=2" class="btn">{"← Back" if lang_en else "← Indietro"}</a>
    <button type="submit" class="btn btn-primary wz-btn">{"Next →" if lang_en else "Avanti →"}</button>
  </div>
</form>
<script>
function copyCode() {{
  navigator.clipboard.writeText("{rec_code}").then(function(){{
    var b = document.querySelector("button[onclick=\\'copyCode()\\']");
    if(b) {{ b.textContent = "{"Copied" if lang_en else "Copiato"}"; setTimeout(function(){{b.textContent="{"Copy" if lang_en else "Copia"}";}},2000); }}
  }});
}}
</script>"""

        elif step == 4:
            _enc_bk = bool(_app_cfg.get("encrypt_backups"))
            _enc_dv = bool(_app_cfg.get("encrypt_devices"))
            if lang_en:
                body = f"""
<div class="wz-title">Data Protection</div>
<p class="wz-sub">Choose what to encrypt on disk. Credentials are always encrypted — these options cover additional data.</p>
<form method="POST" action="/setup?step=4">
  <div class="wz-enc-opts">
    <label class="wz-enc-row">
      <input type="checkbox" name="encrypt_backups" value="1" {"checked" if _enc_bk else ""}>
      <div>
        <strong>Backup files</strong>
        <span>.rsc files saved locally are encrypted and readable only through ROSM.</span>
      </div>
    </label>
    <label class="wz-enc-row">
      <input type="checkbox" name="encrypt_devices" value="1" {"checked" if _enc_dv else ""}>
      <div>
        <strong>Device data</strong>
        <span>MAC addresses, firmware versions, hostnames and hardware info are saved encrypted on disk.</span>
      </div>
    </label>
  </div>
  <div class="wz-enc-warn">
    <strong>Important</strong> — Encryption uses a code generated automatically at first startup.
    Copy it and keep it somewhere safe — you will need it if you ever reinstall ROSM.
  </div>
  <p style="font-size:11px;color:var(--text3);margin:0 0 4px;">Both options can be changed later in Settings.</p>
  <div class="wz-actions">
    <a href="/setup?step=3" class="btn">← Back</a>
    <button type="submit" class="btn btn-primary wz-btn">Next →</button>
  </div>
</form>"""
            else:
                body = f"""
<div class="wz-title">Protezione dati</div>
<p class="wz-sub">Scegli cosa cifrare su disco. Le credenziali SSH sono sempre cifrate — queste opzioni coprono i dati aggiuntivi.</p>
<form method="POST" action="/setup?step=4">
  <div class="wz-enc-opts">
    <label class="wz-enc-row">
      <input type="checkbox" name="encrypt_backups" value="1" {"checked" if _enc_bk else ""}>
      <div>
        <strong>File di backup</strong>
        <span>I file .rsc salvati localmente vengono cifrati e sono leggibili solo attraverso ROSM.</span>
      </div>
    </label>
    <label class="wz-enc-row">
      <input type="checkbox" name="encrypt_devices" value="1" {"checked" if _enc_dv else ""}>
      <div>
        <strong>Dati dispositivi</strong>
        <span>MAC address, firmware, hostname e informazioni hardware vengono salvati cifrati su disco. Puoi ancora vederli nell'interfaccia ROSM, ma non leggendo il file JSON direttamente.</span>
      </div>
    </label>
  </div>
  <div class="wz-enc-warn">
    <strong>Importante</strong> — La cifratura usa un codice generato automaticamente al primo avvio.
    Copialo e conservalo in un posto sicuro — ti servirà se reinstalli ROSM.
  </div>
  <p style="font-size:11px;color:var(--text3);margin:0 0 4px;">Puoi modificare queste impostazioni in qualsiasi momento dalle Impostazioni.</p>
  <div class="wz-actions">
    <a href="/setup?step=3" class="btn">← Indietro</a>
    <button type="submit" class="btn btn-primary wz-btn">Avanti →</button>
  </div>
</form>"""

        elif step == 5:
            _local_ip   = _get_local_ip()
            _cur_binds  = _get_bind_addresses(_app_cfg)
            _chk_local  = "127.0.0.1" in _cur_binds
            _chk_net    = "0.0.0.0" in _cur_binds
            _all_ifaces = _list_network_interfaces()
            _ifaces     = _all_ifaces if len(_all_ifaces) >= 2 else []
            _iface_rows_html = "".join(
                '<label class="wz-access-row '
                + ("wz-access-sel" if _if["ip"] in _cur_binds else "") + '">'
                + '<input type="checkbox" name="bind_address" value="' + _if["ip"] + '" '
                + ("checked" if _if["ip"] in _cur_binds else "") + ' onchange="selOpt(this)">'
                + '<div class="wz-access-ico"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20"/></svg></div>'
                + '<div class="wz-access-body"><strong>' + _if["name"] + '</strong><span>' + _if["ip"] + '</span></div>'
                + '<div class="wz-access-dot"></div></label>'
                for _if in _ifaces
            )
            if lang_en:
                body = f"""
<div class="wz-title">Frontend Access</div>
<p class="wz-sub">Where do you want to access ROSM from?</p>
<form method="POST" action="/setup?step=5">
  <div class="wz-access-opts">
    <label class="wz-access-row {"wz-access-sel" if _chk_local else ""}">
      <input type="checkbox" name="bind_address" value="127.0.0.1" {"checked" if _chk_local else ""}
             onchange="selOpt(this)">
      <div class="wz-access-ico"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg></div>
      <div class="wz-access-body">
        <strong>Only this Mac (localhost)</strong>
        <span>ROSM is reachable at <code>http://localhost:8080</code> only from this machine.</span>
      </div>
      <div class="wz-access-dot"></div>
    </label>
    <label class="wz-access-row {"wz-access-sel" if _chk_net else ""}">
      <input type="checkbox" name="bind_address" value="0.0.0.0" {"checked" if _chk_net else ""}
             onchange="selOpt(this)">
      <div class="wz-access-ico"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20"/></svg></div>
      <div class="wz-access-body">
        <strong>Any device on the network</strong>
        <span>Also reachable at <code>http://{_local_ip}:8080</code> from phones, tablets and other computers.
        Useful for managing routers from multiple devices.</span>
      </div>
      <div class="wz-access-dot"></div>
    </label>
    {_iface_rows_html}
  </div>
  <div class="wz-actions">
    <a href="/setup?step=4" class="btn">← Back</a>
    <button type="submit" class="btn btn-primary wz-btn">Next →</button>
  </div>
</form>
<script>
function selOpt(r){{r.closest('.wz-access-row').classList.toggle('wz-access-sel', r.checked);}}
</script>"""
            else:
                body = f"""
<div class="wz-title">Accesso Frontend</div>
<p class="wz-sub">Da dove vuoi accedere a ROSM?</p>
<form method="POST" action="/setup?step=5">
  <div class="wz-access-opts">
    <label class="wz-access-row {"wz-access-sel" if _chk_local else ""}">
      <input type="checkbox" name="bind_address" value="127.0.0.1" {"checked" if _chk_local else ""}
             onchange="selOpt(this)">
      <div class="wz-access-ico"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg></div>
      <div class="wz-access-body">
        <strong>Solo da questo Mac (localhost)</strong>
        <span>ROSM è raggiungibile su <code>http://localhost:8080</code> solo da questa macchina.</span>
      </div>
      <div class="wz-access-dot"></div>
    </label>
    <label class="wz-access-row {"wz-access-sel" if _chk_net else ""}">
      <input type="checkbox" name="bind_address" value="0.0.0.0" {"checked" if _chk_net else ""}
             onchange="selOpt(this)">
      <div class="wz-access-ico"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20"/></svg></div>
      <div class="wz-access-body">
        <strong>Anche da altri dispositivi</strong>
        <span>Raggiungibile anche su <code>http://{_local_ip}:8080</code> da telefoni, tablet e altri computer.
        Utile per gestire i router da più dispositivi.</span>
      </div>
      <div class="wz-access-dot"></div>
    </label>
    {_iface_rows_html}
  </div>
  <div class="wz-actions">
    <a href="/setup?step=4" class="btn">← Indietro</a>
    <button type="submit" class="btn btn-primary wz-btn">Avanti →</button>
  </div>
</form>
<script>
function selOpt(r){{r.closest('.wz-access-row').classList.toggle('wz-access-sel', r.checked);}}
</script>"""

        elif step == 6:
            _upd = bool(_app_cfg.get("update_enabled", False))
            if lang_en:
                body = f"""
<div class="wz-title">Automatic Updates</div>
<p class="wz-sub">Should ROSM check for new versions automatically and let you install them with one click?</p>
<form method="POST" action="/setup?step=6">
  <div class="wz-access-opts">
    <label class="wz-access-row {"wz-access-sel" if _upd else ""}">
      <input type="radio" name="update_enabled" value="1" {"checked" if _upd else ""}
             onchange="selOpt(this)">
      <div>
        <strong>Yes, check for updates</strong>
        <span>ROSM checks for new versions once a week. You decide when to install them — nothing is installed automatically.</span>
      </div>
    </label>
    <label class="wz-access-row {"wz-access-sel" if not _upd else ""}">
      <input type="radio" name="update_enabled" value="0" {"checked" if not _upd else ""}
             onchange="selOpt(this)">
      <div>
        <strong>No, skip update checks</strong>
        <span>ROSM will not check for updates automatically. You can enable it later in Settings, or run a manual check at any time.</span>
      </div>
    </label>
  </div>
  <div class="wz-actions">
    <a href="/setup?step=5" class="btn">← Back</a>
    <button type="submit" class="btn btn-primary wz-btn">Next →</button>
  </div>
</form>
<script>
function selOpt(r){{document.querySelectorAll('.wz-access-row').forEach(function(el){{el.classList.remove('wz-access-sel');}});r.closest('.wz-access-row').classList.add('wz-access-sel');}}
</script>"""
            else:
                body = f"""
<div class="wz-title">Aggiornamenti automatici</div>
<p class="wz-sub">Vuoi che ROSM controlli automaticamente la disponibilità di nuove versioni e ti permetta di installarle con un clic?</p>
<form method="POST" action="/setup?step=6">
  <div class="wz-access-opts">
    <label class="wz-access-row {"wz-access-sel" if _upd else ""}">
      <input type="radio" name="update_enabled" value="1" {"checked" if _upd else ""}
             onchange="selOpt(this)">
      <div>
        <strong>Sì, controlla gli aggiornamenti</strong>
        <span>ROSM verifica la disponibilità di nuove versioni una volta a settimana. Puoi anche avviare un controllo manuale in qualsiasi momento dalle Impostazioni.</span>
      </div>
    </label>
    <label class="wz-access-row {"wz-access-sel" if not _upd else ""}">
      <input type="radio" name="update_enabled" value="0" {"checked" if not _upd else ""}
             onchange="selOpt(this)">
      <div>
        <strong>No, non controllare</strong>
        <span>ROSM non controllerà gli aggiornamenti in modo automatico. Puoi abilitarlo in seguito dalle Impostazioni, oppure eseguire una verifica manuale in qualsiasi momento.</span>
      </div>
    </label>
  </div>
  <div class="wz-actions">
    <a href="/setup?step=5" class="btn">← Indietro</a>
    <button type="submit" class="btn btn-primary wz-btn">Avanti →</button>
  </div>
</form>
<script>
function selOpt(r){{document.querySelectorAll('.wz-access-row').forEach(function(el){{el.classList.remove('wz-access-sel');}});r.closest('.wz-access-row').classList.add('wz-access-sel');}}
</script>"""

        else:  # step 7
            display_name_set = _get_display_name("admin")
            _bind_l = _get_bind_addresses(_app_cfg)
            _access_lbl = ("localhost only" if lang_en else "solo localhost") if _bind_l == ["127.0.0.1"] \
                          else ("network" if lang_en else "rete locale")
            _upd_lbl = ("enabled" if lang_en else "abilitati") if _app_cfg.get("update_enabled") \
                       else ("disabled" if lang_en else "disabilitati")
            body = f"""
<div class="wz-done-icon" style="font-size:13px;font-weight:800;text-align:center;margin-bottom:12px;
  color:var(--accent);letter-spacing:.4px;">DONE</div>
<div class="wz-title">{"Setup complete!" if lang_en else "Configurazione completata!"}</div>
<p class="wz-sub">{"ROSM is ready. You can change all settings anytime in the Settings page." if lang_en else "ROSM è pronto. Puoi modificare tutto nelle Impostazioni."}</p>
<div class="wz-summary">
  <div class="wz-sum-row"><span>{"Language" if lang_en else "Lingua"}</span><strong>{"English" if lang_en else "Italiano"}</strong></div>
  <div class="wz-sum-row"><span>{"Name" if lang_en else "Nome"}</span><strong>{display_name_set}</strong></div>
  <div class="wz-sum-row"><span>{"Admin password" if lang_en else "Password admin"}</span><strong>{"Updated OK" if lang_en else "Aggiornata OK"}</strong></div>
  <div class="wz-sum-row"><span>{"Recovery code" if lang_en else "Codice recupero"}</span><strong>{"Saved OK" if lang_en else "Salvato OK"}</strong></div>
  <div class="wz-sum-row"><span>{"Access" if lang_en else "Accesso"}</span><strong>{_access_lbl}</strong></div>
  <div class="wz-sum-row"><span>{"Updates" if lang_en else "Aggiornamenti"}</span><strong>{_upd_lbl}</strong></div>
</div>
<form method="POST" action="/setup?step=7">
  <div class="wz-actions" style="justify-content:space-between;">
    <a href="/setup?step=6" class="btn">{"← Back" if lang_en else "← Indietro"}</a>
    <button type="submit" class="btn btn-primary wz-btn" style="min-width:200px;">
      {"Go to application →" if lang_en else "Vai all'applicazione →"}
    </button>
  </div>
</form>"""

        _dark = ' data-theme="dark"' if _app_cfg.get("dark_mode") else ''
        return f"""<!DOCTYPE html>
<html lang="{LANGUAGE}"{_dark}>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ROSM — {"Initial Setup" if lang_en else "Configurazione iniziale"}</title>
{FAVICON_TAG}
<style>
{COMMON_CSS}
html,body{{height:100%;margin:0;background:var(--accent) !important;display:flex;
  align-items:center;justify-content:center;}}
.wz-wrap{{width:520px;max-width:96vw;background:var(--bg2);border-radius:16px;
  box-shadow:0 20px 60px rgba(0,0,0,.25);overflow:hidden;}}
.wz-progress{{background:var(--accent);padding:14px 28px 10px;}}
.wz-dots-row{{display:flex;align-items:center;}}
.wz-dot{{width:26px;height:26px;border-radius:50%;flex-shrink:0;display:flex;
  align-items:center;justify-content:center;font-size:11px;font-weight:800;
  background:rgba(255,255,255,.2);color:rgba(255,255,255,.5);transition:all .2s;}}
.wz-dot.wz-dot-done{{background:rgba(255,255,255,.55);color:var(--accent);}}
.wz-dot.wz-dot-active{{background:#fff;color:var(--accent);box-shadow:0 0 0 3px rgba(255,255,255,.3);}}
.wz-line{{flex:1;height:2px;background:rgba(255,255,255,.2);}}
.wz-line.wz-line-done{{background:rgba(255,255,255,.55);}}
.wz-active-lbl{{text-align:center;margin-top:7px;font-size:10px;font-weight:700;
  text-transform:uppercase;letter-spacing:.7px;color:rgba(255,255,255,.9);}}
.wz-body{{padding:36px 40px 28px;}}
.wz-title{{font-size:22px;font-weight:800;color:var(--text);margin-bottom:6px;}}
.wz-sub{{font-size:13px;color:var(--text2);margin-bottom:24px;line-height:1.5;}}
.wz-field{{margin-bottom:14px;}}
.wz-field label{{display:block;font-size:10px;font-weight:700;color:var(--text2);
  text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px;}}
.wz-field input{{width:100%;box-sizing:border-box;padding:10px 13px;font-size:13px;border-radius:7px;}}
.wz-actions{{display:flex;gap:10px;justify-content:flex-end;margin-top:24px;}}
.wz-btn{{min-width:120px;padding:10px 22px;font-size:13px;font-weight:700;}}
.wz-err{{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);border-radius:6px;
  padding:8px 12px;color:var(--red);font-size:12px;margin-bottom:14px;}}
.wz-recovery-box{{background:rgba(217,119,6,.06);border:1px solid rgba(217,119,6,.3);
  border-radius:10px;padding:16px 18px;margin:18px 0;}}
.wz-recovery-title{{font-size:12px;font-weight:700;color:var(--yellow);margin-bottom:8px;}}
.wz-recovery-code{{font-family:var(--mono);font-size:18px;font-weight:800;
  color:var(--text);letter-spacing:2px;text-align:center;padding:10px;
  background:var(--bg3);border-radius:6px;border:1px solid var(--border2);margin-bottom:8px;}}
.wz-recovery-sub{{font-size:11px;color:var(--text2);line-height:1.5;}}
.lang-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px;}}
.lang-card{{display:flex;flex-direction:column;align-items:center;gap:8px;
  padding:20px;border:2px solid var(--border2);border-radius:12px;cursor:pointer;
  transition:all .15s;}}
.lang-card:hover{{border-color:var(--accent);}}
.lang-card.lang-sel{{border-color:var(--accent);background:rgba(27,58,107,.06);}}
.lang-card input{{display:none;}}
.lang-flag{{font-size:32px;}}
.lang-name{{font-weight:700;font-size:14px;color:var(--text);}}
.wz-done-icon{{font-size:52px;text-align:center;margin-bottom:12px;}}
.wz-summary{{background:var(--bg3);border-radius:10px;padding:14px 18px;margin:16px 0;}}
.wz-sum-row{{display:flex;justify-content:space-between;padding:6px 0;font-size:12px;
  border-bottom:1px solid var(--border);}}
.wz-sum-row:last-child{{border-bottom:none;}}
.wz-enc-opts{{display:flex;flex-direction:column;gap:10px;margin-bottom:16px;}}
.wz-enc-row{{display:flex;align-items:flex-start;gap:12px;padding:12px 14px;
  border:1px solid var(--border2);border-radius:9px;cursor:pointer;transition:border-color .15s;}}
.wz-enc-row:hover{{border-color:var(--accent);}}
.wz-enc-row input{{margin-top:3px;accent-color:var(--accent);width:16px;height:16px;flex-shrink:0;cursor:pointer;}}
.wz-enc-row strong{{display:block;font-size:13px;color:var(--text);margin-bottom:2px;}}
.wz-enc-row span{{font-size:11.5px;color:var(--text2);line-height:1.5;}}
.wz-enc-warn{{background:rgba(239,68,68,.07);border:1px solid rgba(239,68,68,.3);
  border-radius:8px;padding:12px 14px;font-size:11.5px;color:var(--text2);
  line-height:1.6;margin-bottom:14px;}}
.wz-enc-warn strong{{color:var(--red);}}
.wz-access-opts{{display:flex;flex-direction:column;gap:10px;margin-bottom:16px;}}
.wz-access-row{{display:flex;align-items:center;gap:14px;padding:14px 16px;
  border:1.5px solid var(--border2);border-radius:10px;cursor:pointer;
  transition:border-color .15s,background .15s;}}
.wz-access-row:hover{{border-color:var(--accent);}}
.wz-access-sel{{border-color:var(--accent)!important;background:rgba(79,142,247,.07);}}
.wz-access-row input[type=radio]{{display:none;}}
.wz-access-row input[type=checkbox]{{display:none;}}
.wz-access-ico{{font-size:24px;flex-shrink:0;line-height:1;}}
.wz-access-body{{flex:1;}}
.wz-access-row strong{{display:block;font-size:13px;font-weight:700;color:var(--text);margin-bottom:2px;}}
.wz-access-row span{{font-size:11.5px;color:var(--text2);line-height:1.5;}}
.wz-access-dot{{width:18px;height:18px;border-radius:50%;border:2px solid var(--border2);
  flex-shrink:0;transition:all .15s;}}
.wz-access-sel .wz-access-dot{{background:var(--accent);border-color:var(--accent);}}
.wz-outer{{display:flex;flex-direction:column;align-items:center;}}
.wz-logo-area{{text-align:center;margin-bottom:22px;}}
.wz-main-title{{font-size:34px;font-weight:900;color:#fff;letter-spacing:5px;
  margin-top:14px;text-transform:uppercase;}}
.wz-ver-foot{{color:rgba(255,255,255,.4);font-size:11px;font-family:var(--mono);
  margin-top:14px;letter-spacing:.5px;}}
</style>
</head>
<body>
<div class="wz-outer">
  <div class="wz-logo-area">
    <svg width="80" height="80" viewBox="0 0 32 32">
      <rect width="32" height="32" rx="7" fill="rgba(255,255,255,0.18)"/>
      <line x1="9" y1="10" x2="16" y2="23" stroke="rgba(255,255,255,0.65)" stroke-width="1.6"/>
      <line x1="23" y1="10" x2="16" y2="23" stroke="rgba(255,255,255,0.65)" stroke-width="1.6"/>
      <line x1="9" y1="10" x2="23" y2="10" stroke="rgba(255,255,255,0.35)" stroke-width="1.2"/>
      <circle cx="9" cy="10" r="4" fill="#c0392b"/>
      <circle cx="23" cy="10" r="2.8" fill="rgba(255,255,255,0.75)"/>
      <circle cx="16" cy="23" r="3.5" fill="rgba(255,255,255,0.92)"/>
    </svg>
    <div class="wz-main-title">ROSM</div>
  </div>
  <div class="wz-wrap">
    <div class="wz-progress">{steps_html}</div>
    <div class="wz-body">{body}</div>
  </div>
  <div class="wz-ver-foot">v{APP_VERSION} {APP_STAGE}</div>
</div>
</body>
</html>"""

    # ──────────────────────────────────────────────────────────
    # Settings page
    # ──────────────────────────────────────────────────────────
    def render_settings_page(self, session, ctx=None):
        is_admin = (session or {}).get("role") == "admin"
        ctx = ctx or {}
        lang_en = LANGUAGE == "en"
        ok_msg   = ctx.get("ok", "")
        err_msg  = ctx.get("error", "")

        ok_html  = (f'<div class="settings-ok">OK {ok_msg}</div>') if ok_msg else ""
        err_html = (f'<div class="settings-err">x {err_msg}</div>') if err_msg else ""

        uname        = (session or {}).get("username", "admin")
        cur_disp     = _get_display_name(uname)
        _adm_data    = USERS.get(uname, {})
        admin_mfa_enabled = (MFA_AVAILABLE
                             and _adm_data.get("mfa_enabled")
                             and bool(_adm_data.get("totp_secret")))

        # Recovery code section — rendered only for admin, pre-computed to avoid
        # f-string brace-escaping issues with embedded JavaScript.
        if is_admin:
            _lbl_show   = "Show recovery code" if lang_en else "Mostra recovery code"
            _lbl_copy   = "Copy"  if lang_en else "Copia"
            _lbl_hide   = "Hide"  if lang_en else "Nascondi"
            _lbl_copied = "Copied!" if lang_en else "Copiato!"
            _lbl_err    = "Invalid code" if lang_en else "Codice non valido"
            _lbl_desc   = ("This code lets you reset your password if you forget it. Keep it safe."
                           if lang_en else
                           "Questo codice ti permette di reimpostare la password se la dimentichi. Custodiscilo.")
            _mfa_modal  = ""
            if admin_mfa_enabled:
                _lbl_2fa  = "2FA Verification" if lang_en else "Verifica 2FA"
                _lbl_hint = ("Enter your authenticator code to view the recovery code."
                             if lang_en else
                             "Inserisci il codice authenticator per visualizzare il recovery code.")
                _lbl_vrfy = "Verify"  if lang_en else "Verifica"
                _lbl_cncl = "Cancel"  if lang_en else "Annulla"
                _mfa_modal = (
                    '<div id="rc-mfa-modal" style="display:none;position:fixed;inset:0;'
                    'background:rgba(0,0,0,.55);z-index:9999;align-items:center;justify-content:center;">'
                    '<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;'
                    'padding:28px;max-width:330px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,.25);">'
                    f'<h3 style="margin:0 0 6px;font-size:14px;color:var(--text);">{_lbl_2fa}</h3>'
                    f'<p style="font-size:12px;color:var(--text2);margin:0 0 14px;line-height:1.5;">{_lbl_hint}</p>'
                    '<input type="text" id="rc-totp-input" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" '
                    'placeholder="000000" style="width:100%;box-sizing:border-box;font-size:20px;'
                    'font-family:var(--mono);text-align:center;padding:10px;border-radius:7px;'
                    'letter-spacing:4px;margin-bottom:8px;">'
                    '<div id="rc-mfa-err" style="color:var(--red);font-size:11px;min-height:16px;margin-bottom:10px;"></div>'
                    '<div style="display:flex;gap:8px;">'
                    f'<button class="btn btn-primary" style="flex:1;font-size:12px;" onclick="rcMfaSubmit()">{_lbl_vrfy}</button>'
                    f'<button class="btn" style="flex:1;font-size:12px;" onclick="rcMfaCancel()">{_lbl_cncl}</button>'
                    '</div></div></div>'
                )
            _rc_js_hasmfa = "true" if admin_mfa_enabled else "false"
            _rc_section = (
                '<div class="settings-card">'
                f'<h3>{"Recovery code" if lang_en else "Codice di recupero"}</h3>'
                f'<p style="font-size:12px;color:var(--text2);margin:0 0 12px;line-height:1.5;">{_lbl_desc}</p>'
                '<div id="rc-masked" style="font-family:var(--mono);font-size:15px;font-weight:800;letter-spacing:3px;'
                'background:var(--bg3);border:1px solid var(--border2);border-radius:7px;'
                'padding:10px 14px;text-align:center;color:var(--text3);margin-bottom:10px;">••••••••••••••••••••</div>'
                '<div id="rc-revealed" style="display:none;font-family:var(--mono);font-size:15px;font-weight:800;'
                'letter-spacing:2px;background:var(--bg3);border:1px solid var(--border2);border-radius:7px;'
                'padding:10px 14px;text-align:center;color:var(--text);margin-bottom:10px;"></div>'
                '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
                f'<button id="rc-show-btn" class="btn" style="font-size:11px;" onclick="rcShow()">{_lbl_show}</button>'
                f'<button id="rc-copy-btn" class="btn" style="font-size:11px;display:none;" onclick="rcCopy()">{_lbl_copy}</button>'
                f'<button id="rc-hide-btn" class="btn" style="font-size:11px;display:none;" onclick="rcHide()">{_lbl_hide}</button>'
                '</div>'
                '</div>'
                + _mfa_modal +
                '<script>'
                '(function() {'
                f'var _hasMfa={_rc_js_hasmfa};'
                f'var _lbCopied={json.dumps(_lbl_copied)};'
                f'var _lbCopy={json.dumps(_lbl_copy)};'
                f'var _lbErr={json.dumps(_lbl_err)};'
                'window.rcShow=function(){'
                '  if(_hasMfa){'
                '    var m=document.getElementById("rc-mfa-modal");'
                '    m.style.display="flex";'
                '    document.getElementById("rc-totp-input").value="";'
                '    document.getElementById("rc-mfa-err").textContent="";'
                '    setTimeout(function(){document.getElementById("rc-totp-input").focus();},80);'
                '  }else{'
                '    fetch("/api/recovery_code").then(function(r){return r.json();}).then(function(d){'
                '      if(d.ok)_rcReveal(d.code);'
                '    });'
                '  }'
                '};'
                'window.rcHide=function(){'
                '  document.getElementById("rc-revealed").style.display="none";'
                '  document.getElementById("rc-masked").style.display="";'
                '  document.getElementById("rc-show-btn").style.display="";'
                '  document.getElementById("rc-copy-btn").style.display="none";'
                '  document.getElementById("rc-hide-btn").style.display="none";'
                '};'
                'window.rcCopy=function(){'
                '  var code=document.getElementById("rc-revealed").textContent.trim();'
                '  navigator.clipboard.writeText(code).then(function(){'
                '    var btn=document.getElementById("rc-copy-btn");'
                '    btn.textContent=_lbCopied;'
                '    setTimeout(function(){btn.textContent=_lbCopy;},2000);'
                '  });'
                '};'
                'window.rcMfaSubmit=function(){'
                '  var code=document.getElementById("rc-totp-input").value.trim();'
                '  document.getElementById("rc-mfa-err").textContent="";'
                '  fetch("/api/recovery_code?totp="+encodeURIComponent(code))'
                '    .then(function(r){return r.json();})'
                '    .then(function(d){'
                '      if(d.ok){document.getElementById("rc-mfa-modal").style.display="none";_rcReveal(d.code);}'
                '      else{document.getElementById("rc-mfa-err").textContent=d.error||_lbErr;}'
                '    });'
                '};'
                'window.rcMfaCancel=function(){'
                '  var m=document.getElementById("rc-mfa-modal");'
                '  if(m)m.style.display="none";'
                '};'
                'function _rcReveal(code){'
                '  document.getElementById("rc-revealed").textContent=code;'
                '  document.getElementById("rc-revealed").style.display="";'
                '  document.getElementById("rc-masked").style.display="none";'
                '  document.getElementById("rc-show-btn").style.display="none";'
                '  document.getElementById("rc-copy-btn").style.display="";'
                '  document.getElementById("rc-hide-btn").style.display="";'
                '}'
                'document.addEventListener("keydown",function(e){'
                '  var modal=document.getElementById("rc-mfa-modal");'
                '  if(!modal)return;'
                '  if(modal.style.display==="flex"){'
                '    if(e.key==="Enter")rcMfaSubmit();'
                '    if(e.key==="Escape")rcMfaCancel();'
                '  }'
                '});'
                '})();'
                '</script>'
            )
        else:
            _rc_section = ""

        # ── Encryption section (admin only) ──────────────────────────
        if is_admin:
            _ck_dev  = "checked" if _app_cfg.get("encrypt_devices") else ""
            _ck_bk   = "checked" if _app_cfg.get("encrypt_backups")  else ""
            _enc_h3  = "data encryption" if lang_en else "Cifratura dati"
            _enc_lbl_dev = "Device state" if lang_en else "Stato dispositivi"
            _enc_lbl_bk  = "Backup files" if lang_en else "File di backup"
            _enc_prog    = "Saving..." if lang_en else "Salvataggio..."
            _enc_section = (
                f'<div class="settings-card" id="enc-card"><h3>{_enc_h3}</h3>'
                f'<div style="display:flex;flex-direction:column;gap:10px;margin-bottom:14px;">'
                f'<label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;">'
                f'<input type="checkbox" id="enc-devices" {_ck_dev}>{_enc_lbl_dev}</label>'
                f'<label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;">'
                f'<input type="checkbox" id="enc-backups" {_ck_bk}>{_enc_lbl_bk}</label>'
                f'</div>'
                f'<button type="button" class="btn btn-primary" onclick="saveEncryption()" id="enc-save-btn">'
                f'{T("Salva")}</button>'
                f'<div id="enc-prog" style="display:none;font-size:11px;color:var(--text2);margin-top:8px;">{_enc_prog}</div>'
                f'</div>'
                '<script>function saveEncryption(){'
                'var d=document.getElementById("enc-devices").checked?"1":"";'
                'var b=document.getElementById("enc-backups").checked?"1":"";'
                'var btn=document.getElementById("enc-save-btn");'
                'var pg=document.getElementById("enc-prog");'
                'btn.disabled=true;pg.style.display="block";'
                'var body="encrypt_devices="+encodeURIComponent(d)+"&encrypt_backups="+encodeURIComponent(b);'
                'fetch("/settings/encryption",{method:"POST",headers:{"Content-Type":"application/x-www-form-urlencoded"},body:body})'
                '.then(function(r){return r.json();})'
                '.then(function(){pg.style.display="none";btn.disabled=false;})'
                '.catch(function(){pg.style.display="none";btn.disabled=false;});'
                '}</script>'
            )
        else:
            _enc_section = ""

        # ── Update section (admin only) ──────────────────────────────
        if is_admin:
            _upd_enabled = bool(_app_cfg.get("update_enabled", False))

            # Labels — IT / EN
            if lang_en:
                _u_title        = "ROSM Updates"
                _u_enabled_lbl  = "Updates enabled"
                _u_disabled_lbl = "Updates disabled"
                _u_enable_btn   = "Enable"
                _u_disable_btn  = "Disable"
                _u_how_title    = "What happens when you install an update:"
                _u_steps        = [
                    "① ROSM contacts the update server to check if a newer version is available.",
                    "② If an update is found, the release notes appear with the <strong>Download &amp; Install</strong> button.",
                    "③ On confirm, ROSM downloads the update package.",
                    "④ A backup of the current installation is saved automatically.",
                    "⑤ The update is applied.",
                    "⑥ ROSM restarts automatically. Active sessions will be interrupted for ~5–10 seconds.",
                ]
                _u_warn         = "No data is sent during the check."
                _u_freq         = "The check only runs when you click this button."
                _u_check        = "Check for updates"
                _u_chking       = "Checking…"
                _u_ok           = "You are up to date."
                _u_new          = "New version available:"
                _u_cl_lbl       = "Release notes:"
                _u_install      = "Download & Install"
                _u_skip         = "Not now"
                _u_instlng      = "Installing…"
                _u_done         = ("Update installed. ROSM is restarting — "
                                   "reconnect in a few seconds.")
                _u_reconn       = "Reconnect →"
                _u_bkp          = "A backup of the previous version has been saved automatically."
                _u_errpfx       = "Error: "
                _u_ch_lbl       = "Update channel"
            else:
                _u_title        = "Aggiornamenti ROSM"
                _u_enabled_lbl  = "Aggiornamenti abilitati"
                _u_disabled_lbl = "Aggiornamenti disabilitati"
                _u_enable_btn   = "Abilita"
                _u_disable_btn  = "Disabilita"
                _u_how_title    = "Cosa succede quando installi un aggiornamento:"
                _u_steps        = [
                    "① ROSM contatta il server di aggiornamento per verificare se è disponibile una versione più recente.",
                    "② Se viene trovato un aggiornamento, compaiono le note di rilascio con il pulsante <strong>Scarica e installa</strong>.",
                    "③ Alla conferma, ROSM scarica il pacchetto di aggiornamento.",
                    "④ Un backup dell'installazione corrente viene salvato automaticamente.",
                    "⑤ L'aggiornamento viene applicato.",
                    "⑥ ROSM si riavvia automaticamente. Le sessioni attive saranno interrotte per ~5–10 secondi.",
                ]
                _u_warn         = "Nessun dato viene inviato durante il controllo."
                _u_freq         = "Il controllo avviene solo quando clicchi questo pulsante."
                _u_check        = "Controlla aggiornamenti"
                _u_chking       = "Controllo in corso…"
                _u_ok           = "Sei già aggiornato."
                _u_new          = "Nuova versione disponibile:"
                _u_cl_lbl       = "Note di rilascio:"
                _u_install      = "Scarica e installa"
                _u_skip         = "Non ora"
                _u_instlng      = "Installazione in corso…"
                _u_done         = ("Aggiornamento installato. ROSM si sta riavviando — "
                                   "riconnettiti tra qualche secondo.")
                _u_reconn       = "Riconnetti →"
                _u_bkp          = ("Un backup della versione precedente è stato salvato automaticamente. "
                                   "Puoi eliminarla una volta verificato l'aggiornamento.")
                _u_errpfx       = "Errore: "
                _u_ch_lbl       = "Canale aggiornamenti"

            # Status row (toggle)
            if _upd_enabled:
                _u_status_dot   = ('<span style="display:inline-flex;align-items:center;gap:6px;'
                                   'font-size:12px;font-weight:700;color:var(--green);">'
                                   '<span style="width:8px;height:8px;border-radius:50%;'
                                   'background:var(--green);display:inline-block;"></span>'
                                   + _u_enabled_lbl + '</span>')
                _u_toggle_btn   = (f'<form method="POST" action="/settings/update_enabled" style="display:inline;">'
                                   f'<button type="submit" class="btn" style="font-size:11px;">'
                                   f'{_u_disable_btn}</button></form>')
            else:
                _u_status_dot   = ('<span style="display:inline-flex;align-items:center;gap:6px;'
                                   'font-size:12px;font-weight:600;color:var(--text3);">'
                                   '<span style="width:8px;height:8px;border-radius:50%;'
                                   'background:var(--text3);display:inline-block;"></span>'
                                   + _u_disabled_lbl + '</span>')
                _u_toggle_btn   = (f'<form method="POST" action="/settings/update_enabled" style="display:inline;">'
                                   f'<button type="submit" class="btn btn-primary" style="font-size:11px;">'
                                   f'{_u_enable_btn}</button></form>')

            # Channel selector
            _cur_ch  = _app_cfg.get("update_channel", "stable")
            _opt_st  = 'selected' if _cur_ch == "stable" else ''
            _opt_bt  = 'selected' if _cur_ch == "beta"   else ''
            _u_ch_html = (
                f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">'
                f'<span style="font-size:12px;color:var(--text2);">{_u_ch_lbl}:</span>'
                f'<select onchange="saveChannel(this.value)"'
                f' style="font-size:12px;padding:4px 8px;border:1px solid var(--border);'
                f'border-radius:6px;background:var(--bg3);color:var(--text);">'
                f'<option value="stable" {_opt_st}>Stable</option>'
                f'<option value="beta" {_opt_bt}>Beta</option>'
                f'</select>'
                f'</div>'
                f'<div id="ch-switch-info" style="display:none;font-size:11px;margin-bottom:12px;"></div>'
            )
            _u_ch_saving_lbl    = "Saving…" if lang_en else "Salvataggio…"
            _u_ch_saved_lbl     = "Channel saved. Use 'Check for updates' to install." if lang_en else "Canale salvato. Usa 'Controlla aggiornamenti' per installare."
            _sav_ing = json.dumps(_u_ch_saving_lbl)
            _sav_txt = json.dumps(_u_ch_saved_lbl)
            _u_ch_js = (
                '<script>window.saveChannel=function(v){'
                'var info=document.getElementById("ch-switch-info");'
                'if(info){info.style.display="";info.textContent=' + _sav_ing + ';info.style.color="var(--text2)";}'
                'fetch("/settings/update_channel",{method:"POST",'
                'headers:{"Content-Type":"application/x-www-form-urlencoded"},'
                'body:"channel="+encodeURIComponent(v)})'
                '.then(function(r){return r.json();})'
                '.then(function(d){'
                'if(d.ok){'
                'if(info){info.textContent=' + _sav_txt + ';info.style.color="var(--text3)";}'
                '}else{'
                'if(info){info.textContent=(d.error||"Error");info.style.color="var(--red)";}'
                '}'
                '})'
                '.catch(function(e){'
                'if(info){info.textContent="Error: "+e;info.style.color="var(--red)";}'
                '});'
                '};</script>'
            )

            # Process steps HTML
            _u_steps_html = "".join(
                f'<li style="margin-bottom:5px;">{s}</li>' for s in _u_steps
            )

            # Check+install area (always available, independent of the auto-update toggle)
            _u_check_area = (
                '<div style="padding-top:16px;margin-top:4px;border-top:1px solid var(--border);">'
                f'<button id="upd-check-btn" class="btn btn-primary" onclick="updCheck()" style="font-size:12px;">{_u_check}</button>'
                f'<span style="margin-left:10px;font-size:11px;color:var(--text3);">{_u_freq}</span>'
                '<div id="upd-result" style="margin-top:12px;display:none;"></div>'
                '</div>'
            )
            _u_js = (
                '<script>(function(){'
                f'var LC={json.dumps(_u_check)};'
                f'var LCK={json.dumps(_u_chking)};'
                f'var LOK={json.dumps(_u_ok)};'
                f'var LNW={json.dumps(_u_new)};'
                f'var LCL={json.dumps(_u_cl_lbl)};'
                f'var LIN={json.dumps(_u_install)};'
                f'var LSK={json.dumps(_u_skip)};'
                f'var LIG={json.dumps(_u_instlng)};'
                f'var LDN={json.dumps(_u_done)};'
                f'var LRC={json.dumps(_u_reconn)};'
                f'var LBK={json.dumps(_u_bkp)};'
                f'var LER={json.dumps(_u_errpfx)};'
                'function _buildCL(cl){'
                '  if(!cl||!cl.length)return "";'
                '  var h=\'<div style="margin-bottom:12px;">\';'
                '  for(var i=0;i<cl.length;i++){'
                '    var e=cl[i];'
                '    h+=\'<div style="margin-bottom:8px;">\';'
                '    h+=\'<div style="font-size:11px;font-weight:700;color:var(--text2);margin-bottom:3px;">v\'+e.version+(e.date?" — "+e.date:"")+\'</div>\';'
                '    if(e.notes&&e.notes.length){'
                '      h+=\'<ul style="margin:0;padding-left:16px;font-size:11px;color:var(--text2);line-height:1.7;">\';'
                '      for(var j=0;j<e.notes.length;j++)h+=\'<li>\'+e.notes[j]+\'</li>\';'
                '      h+=\'</ul>\';'
                '    }'
                '    h+=\'</div>\';'
                '  }'
                '  return h+\'</div>\';'
                '}'
                'window.updCheck=function(){'
                '  var btn=document.getElementById("upd-check-btn");'
                '  var res=document.getElementById("upd-result");'
                '  btn.disabled=true; btn.textContent=LCK; res.style.display="none";'
                '  fetch("/api/check-update").then(function(r){return r.json();}).then(function(d){'
                '    btn.disabled=false; btn.textContent=LC; res.style.display="";'
                '    if(!d.ok){'
                '      res.innerHTML=\'<div style="color:var(--red);font-size:12px;padding:8px 0;">\'+LER+(d.error||"?")+\'</div>\';'
                '      return;'
                '    }'
                '    if(!d.update_available){'
                '      res.innerHTML=\'<div style="color:var(--green);font-size:13px;font-weight:700;padding:6px 0;">\\u2713 \'+LOK+\'</div>\';'
                '      return;'
                '    }'
                '    var clHtml=_buildCL(d.changelog);'
                '    res.innerHTML='
                '      \'<div style="background:rgba(79,142,247,.08);border:1px solid rgba(79,142,247,.25);\'+'
                '      \'border-radius:8px;padding:14px 16px;margin-bottom:10px;">\''
                '      +\'<div style="font-size:13px;font-weight:700;color:var(--text);margin-bottom:10px;">\'+LNW+'
                '      \' <span style="color:var(--accent);font-family:var(--mono);">\'+d.latest+\'</span></div>\''
                '      +(clHtml?\'<div style="font-size:10px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;">\'+LCL+\'</div>\'+clHtml:"")'
                '      +\'<div style="font-size:11px;color:var(--text3);margin-bottom:12px;">\'+LBK+\'</div>\''
                '      +\'<div style="display:flex;gap:8px;align-items:center;">\''
                '      +\'<button class="btn btn-primary" id="upd-inst-btn" onclick="updInstall()" style="font-size:12px;">\'+LIN+\'</button>\''
                '      +\'<button class="btn" id="upd-skip-btn" onclick="updSkip()" style="font-size:12px;">\'+LSK+\'</button>\''
                '      +\'</div>\''
                '      +\'</div>\';'
                '  }).catch(function(e){'
                '    btn.disabled=false; btn.textContent=LC; res.style.display="";'
                '    res.innerHTML=\'<div style="color:var(--red);font-size:12px;padding:8px 0;">\'+LER+e+\'</div>\';'
                '  });'
                '};'
                'window.updSkip=function(){'
                '  var res=document.getElementById("upd-result");'
                '  var btn=document.getElementById("upd-check-btn");'
                '  res.style.display="none"; res.innerHTML="";'
                '  btn.disabled=false; btn.textContent=LC;'
                '};'
                'window.updInstall=function(){'
                '  var btn=document.getElementById("upd-inst-btn");'
                '  var skp=document.getElementById("upd-skip-btn");'
                '  var res=document.getElementById("upd-result");'
                '  if(btn){btn.disabled=true; btn.textContent=LIG;}'
                '  if(skp){skp.disabled=true;}'
                '  fetch("/api/do-update",{method:"POST",headers:{"Content-Type":"application/json"},body:"{}"})'
                '    .then(function(r){return r.json();})'
                '    .then(function(d){'
                '      if(d.ok){'
                '        res.innerHTML='
                '          \'<div style="background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.3);\'+'
                '          \'border-radius:8px;padding:14px 16px;">\''
                '          +\'<div style="color:var(--green);font-size:13px;font-weight:700;margin-bottom:10px;">\\u2713 \'+LDN+\'</div>\''
                '          +\'<a href="/" class="btn btn-primary" style="font-size:12px;">\'+LRC+\'</a>\''
                '          +\'</div>\';'
                '        setTimeout(function(){window.location.href="/";},7000);'
                '      }else{'
                '        if(btn){btn.disabled=false; btn.textContent=LIN;}'
                '        if(skp){skp.disabled=false;}'
                '        res.innerHTML+=\'<div style="color:var(--red);font-size:12px;margin-top:8px;">\'+LER+(d.msg||"?")+\'</div>\';'
                '      }'
                '    }).catch(function(e){'
                '      if(btn){btn.disabled=false; btn.textContent=LIN;}'
                '      if(skp){skp.disabled=false;}'
                '      res.innerHTML+=\'<div style="color:var(--red);font-size:12px;margin-top:8px;">\'+LER+e+\'</div>\';'
                '    });'
                '};'
                '})();</script>'
            )

            _upd_section = (
                '<div class="settings-card" style="grid-column:1/-1;">'

                # Header: title + version badge
                '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;">'
                f'<h3 style="margin:0;">{_u_title}</h3>'
                f'<span style="font-size:11px;font-family:var(--mono);background:var(--bg3);'
                f'border:1px solid var(--border2);border-radius:5px;padding:2px 8px;color:var(--text2);">'
                f'v{APP_VERSION}</span>'
                '</div>'

                # Toggle row + channel selector
                '<div style="display:flex;align-items:center;gap:14px;margin-bottom:10px;">'
                + _u_status_dot + _u_toggle_btn +
                '</div>'
                + _u_ch_html +

                # Separator before steps
                '<div style="border-top:1px solid var(--border);padding-top:16px;margin-bottom:14px;">'

                # Process steps
                f'<div style="font-size:11px;font-weight:700;color:var(--text2);'
                f'text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px;">{_u_how_title}</div>'
                f'<ol style="margin:0 0 12px 0;padding-left:0;list-style:none;font-size:12px;'
                f'color:var(--text2);line-height:1.7;">{_u_steps_html}</ol>'

                # Privacy note
                f'<div style="font-size:11px;color:var(--text3);font-style:italic;">{_u_warn}</div>'
                '</div>'

                + _u_check_area
                + _u_ch_js
                + _u_js
                + '</div>'
            )
        else:
            _upd_section = ""

        _cur_binds_s  = _get_bind_addresses(_app_cfg)
        _all_ifaces_s = _list_network_interfaces()
        _ifaces_s     = _all_ifaces_s if len(_all_ifaces_s) >= 2 else []
        _iface_rows_settings = "".join(
            '<label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;">'
            + '<input type="checkbox" name="acc_bind" value="' + _if["ip"] + '" '
            + ("checked" if _if["ip"] in _cur_binds_s else "") + '>'
            + _if["name"]
            + '<span style="font-size:11px;color:var(--text3);margin-left:4px;">http://' + _if["ip"] + ':8080</span>'
            + '</label>'
            for _if in _ifaces_s
        )

        return self._page_shell(T("Impostazioni"), f"""
<style>
.settings-grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;max-width:860px;}}
@media(max-width:680px){{.settings-grid{{grid-template-columns:1fr;}}}}
.settings-card{{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:24px;}}
.settings-card h3{{font-size:13px;font-weight:700;margin:0 0 16px;color:var(--text);}}
.s-field{{margin-bottom:14px;}}
.s-field label{{display:block;font-size:10px;font-weight:700;color:var(--text2);
  text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px;}}
.s-field input,.s-field select{{width:100%;box-sizing:border-box;font-size:13px;}}
.settings-ok{{background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.3);border-radius:7px;
  padding:10px 14px;color:var(--green);font-size:12px;margin-bottom:16px;}}
.settings-err{{background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);border-radius:7px;
  padding:10px 14px;color:var(--red);font-size:12px;margin-bottom:16px;}}
</style>

{ok_html}{err_html}

<div class="settings-grid">

  <!-- ① Dark Mode — card compatta -->
  <div class="settings-card" style="padding:16px 20px;">
    <h3 style="margin-bottom:10px;">Dark Mode</h3>
    <form method="POST" action="/settings/darkmode" style="display:inline;">
      <button type="submit"
              class="btn{'  btn-primary' if bool(USERS.get(uname, {}).get('dark_mode', False)) else ''}"
              style="padding:7px 18px;font-size:13px;">
        {('Disable' if lang_en else 'Disattiva') if bool(USERS.get(uname, {}).get('dark_mode', False)) else ('Enable' if lang_en else 'Attiva')} Dark Mode
      </button>
    </form>
    <div style="font-size:10px;color:var(--text3);margin-top:8px;">
      {"Preference saved per account." if lang_en else "Preferenza salvata per questo account."}
    </div>
  </div>

  <!-- ② Lingua — card compatta, dropdown con salvataggio immediato -->
  <div class="settings-card" style="padding:16px 20px;">
    <h3 style="margin-bottom:10px;">{T("Lingua interfaccia")}</h3>
    <form method="POST" action="/settings/language">
      <select name="language" onchange="this.form.submit()"
              style="width:100%;box-sizing:border-box;font-size:13px;padding:7px 10px;">
        <option value="it" {"selected" if not lang_en else ""}>IT — Italiano</option>
        <option value="en" {"selected" if lang_en else ""}>EN — English</option>
      </select>
    </form>
  </div>

  <!-- ③ Profilo -->
  <div class="settings-card">
    <h3>{"Profile" if lang_en else "Profilo"}</h3>
    <form method="POST" action="/settings/profile">
      <div class="s-field">
        <label>{"Display name" if lang_en else "Nome visualizzato"}</label>
        <input type="text" name="display_name" maxlength="50" autocomplete="name"
               value="{cur_disp if cur_disp != uname else ""}"
               placeholder="{"e.g. your display name" if lang_en else "es. nome visualizzato"}">
        <div style="font-size:10px;color:var(--text3);margin-top:4px;">
          {"Shown in the top bar and home page greeting. Leave blank to use the username." if lang_en else "Mostrato nella barra e nel saluto home. Lascia vuoto per usare il nome utente."}
        </div>
      </div>
      <button type="submit" class="btn btn-primary">{T("Salva")}</button>
    </form>
  </div>

  <!-- ③ Sicurezza account -->
  <div class="settings-card">
    <h3>{T("Sicurezza account")}</h3>
    <form method="POST" action="/settings/password">
      <div class="s-field">
        <label>{T("Password attuale")}</label>
        <input type="password" name="current_password" autocomplete="current-password" required>
      </div>
      <div class="s-field">
        <label>{T("Nuova password")}</label>
        <input type="password" name="new_password" minlength="8" autocomplete="new-password" required>
      </div>
      <div class="s-field">
        <label>{T("Conferma password")}</label>
        <input type="password" name="confirm_password" autocomplete="new-password" required>
      </div>
      <button type="submit" class="btn btn-primary">{T("Salva")}</button>
    </form>
  </div>

  <!-- ③b Data encryption (admin only) -->
  {_enc_section}

  <!-- ⑤ Storico Ping -->
  <div class="settings-card">
    <h3>{"Ping History" if lang_en else "Storico Ping"}</h3>
    <form method="POST" action="/settings/ping_history">
      <div class="s-field" style="margin-bottom:10px;">
        <label>{"Ping History" if lang_en else "Storico Ping"}</label>
        <select name="ping_history_days">
          {''.join(f'<option value="{d}" {"selected" if _app_cfg.get("ping_history_days",7)==d else ""}>{lbl}</option>' for d, lbl in [
            (1,  ("Last 1 day"    if lang_en else "Ultimo 1 giorno")),
            (3,  ("Last 3 days"   if lang_en else "Ultimi 3 giorni")),
            (7,  ("Last 7 days"   if lang_en else "Ultimi 7 giorni")),
            (14, ("Last 14 days"  if lang_en else "Ultimi 14 giorni")),
            (30, ("Last 30 days"  if lang_en else "Ultimi 30 giorni")),
            (90, ("Last 90 days"  if lang_en else "Ultimi 90 giorni")),
          ])}
        </select>
        <div style="font-size:10px;color:var(--text3);margin-top:4px;">
          {("Currently " if lang_en else "Attualmente ") + str(len(PING_HISTORY)) + (" entries — interval: " if lang_en else " voci — intervallo: ") + str(AUTO_INTERVAL) + "s"}
        </div>
      </div>
      <button type="submit" class="btn btn-primary">{T("Salva")}</button>
    </form>
  </div>

  <!-- ⑥ Frontend Access -->
  <div class="settings-card">
    <h3>{"Frontend Access" if lang_en else "Accesso Frontend"}</h3>
    <div style="display:flex;flex-direction:column;gap:10px;margin-bottom:16px;">
      <label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;">
        <input type="checkbox" name="acc_bind" id="acc-local" value="127.0.0.1"
               {"checked" if "127.0.0.1" in _cur_binds_s else ""}>
        {"Localhost only" if lang_en else "Solo localhost"}
        <span style="font-size:11px;color:var(--text3);margin-left:4px;">http://localhost:8080</span>
      </label>
      <label style="display:flex;align-items:center;gap:8px;font-size:13px;cursor:pointer;">
        <input type="checkbox" name="acc_bind" id="acc-net" value="0.0.0.0"
               {"checked" if "0.0.0.0" in _cur_binds_s else ""}>
        {"Local network" if lang_en else "Rete locale"}
        <span style="font-size:11px;color:var(--text3);margin-left:4px;">http://{_get_local_ip()}:8080</span>
      </label>
      {_iface_rows_settings}
    </div>
    <div style="display:flex;align-items:center;gap:12px;">
      <button type="button" class="btn btn-primary" id="acc-btn" onclick="saveAccess()">
        {"Save + Restart" if lang_en else "Salva + Riavvia"}
      </button>
      <span id="acc-msg" style="font-size:11px;color:var(--text2);"></span>
    </div>
  </div>
  <script>
  function saveAccess() {{
    var checked = document.querySelectorAll('input[name="acc_bind"]:checked');
    if (!checked.length) return;
    var btn = document.getElementById('acc-btn');
    var msg = document.getElementById('acc-msg');
    btn.disabled = true;
    msg.textContent = '{"Restarting..." if lang_en else "Riavvio in corso..."}';
    var qs = Array.prototype.map.call(checked, function(c){{ return 'bind_address=' + encodeURIComponent(c.value); }}).join('&');
    fetch('/settings/access-restart', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/x-www-form-urlencoded'}},
      body: qs
    }}).catch(function(){{}});
    setTimeout(function() {{
      window.location.href = '/settings';
    }}, 4000);
  }}
  </script>

  <!-- ⑦ Aggiornamenti (admin, full-width) -->
  {_upd_section}

  <!-- ⑧ Recovery code (admin, full-width) -->
  {_rc_section}

  <!-- ⑨ Restart Server + Debug Mode (admin, full-width) -->
  {'<div class="settings-card" style="grid-column:1/-1;"><h3>' + ("Server" if lang_en else "Server") + '</h3><div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;"><button class="btn" id="restart-srv-btn" onclick="settingsRestart()" style="background:var(--red);color:#fff;border-color:var(--red);padding:7px 18px;">' + ("Restart Server" if lang_en else "Riavvia Server") + '</button><button class="btn" onclick="showDebugMode()" style="padding:7px 18px;">' + ("Debug Mode" if lang_en else "Debug Mode") + '</button><span id="restart-srv-msg" style="font-size:12px;color:var(--text2);"></span></div><div style="font-size:10px;color:var(--text3);margin-top:8px;">' + ("Restarts the ROSM process. The page reloads automatically once the server is back." if lang_en else "Riavvia il processo ROSM. La pagina si ricarica automaticamente non appena il server torna online.") + '</div></div><script>async function settingsRestart(){{if(!confirm(' + json.dumps("Restart ROSM server?" if lang_en else "Riavviare il server ROSM?") + '))return;var btn=document.getElementById("restart-srv-btn");var msg=document.getElementById("restart-srv-msg");btn.disabled=true;btn.textContent="…";msg.style.color="var(--text2)";msg.textContent=' + json.dumps("Restarting..." if lang_en else "Riavvio in corso...") + ';try{{await fetch("/api/restart",{{method:"POST"}});}}catch(e){{}}var attempts=0;var poll=setInterval(async function(){{attempts++;try{{var r=await fetch("/api/ping",{{method:"GET",cache:"no-store"}});if(r.ok){{clearInterval(poll);msg.style.color="var(--green)";msg.textContent=' + json.dumps("Back online — reloading…" if lang_en else "Online — ricarico…") + ';setTimeout(function(){{location.reload();}},600);}}}catch(e){{if(attempts>30){{clearInterval(poll);btn.disabled=false;btn.textContent=' + json.dumps("Restart Server" if lang_en else "Riavvia Server") + ';msg.style.color="var(--red)";msg.textContent=' + json.dumps("Timeout — reload manually" if lang_en else "Timeout — ricarica manualmente") + ';}}}}}},800);}}function showDebugMode(){{sessionStorage.setItem("rosm_debug_mode","1");if(document.getElementById("_dbg_active_bar"))return;var bar=document.createElement("div");bar.id="_dbg_active_bar";bar.style.cssText="position:fixed;top:0;left:0;right:0;z-index:99990;background:#d97706;color:#fff;font-size:12px;font-weight:700;padding:7px 16px;display:flex;align-items:center;gap:10px;font-family:var(--sans);box-shadow:0 2px 8px rgba(0,0,0,.25);letter-spacing:.03em;";var sp=document.createElement("span");sp.textContent="Debug mode active";var btn=document.createElement("button");btn.textContent="Disattiva e scarica";btn.style.cssText="margin-left:auto;background:rgba(0,0,0,.25);color:#fff;border:1px solid rgba(255,255,255,.5);border-radius:6px;padding:3px 12px;font-size:11px;cursor:pointer;font-weight:700;font-family:inherit;";btn.onclick=window._rosmDbgDeactivate;bar.appendChild(sp);bar.appendChild(btn);document.body.insertBefore(bar,document.body.firstChild);document.body.style.paddingTop=(parseInt(document.body.style.paddingTop||0)+36)+"px";}}</script>' if is_admin else ''}

</div>
""", session=session, page_key="settings")

    # ──────────────────────────────────────────────────────────
    # Forgot / Reset password page
    # ──────────────────────────────────────────────────────────
    def render_forgot_password_page(self, ctx=None):
        ctx = ctx or {}
        lang_en = LANGUAGE == "en"
        err_msg  = ctx.get("error", "")
        ok_msg   = ctx.get("ok", "")
        phase    = ctx.get("phase", "enter_code")   # "enter_code" | "new_password" | "done"
        token    = ctx.get("token", "")

        if phase == "done":
            body = f"""
<div style="text-align:center;font-size:13px;font-weight:800;color:var(--green);margin-bottom:12px;letter-spacing:.4px;">OK</div>
<div style="font-size:18px;font-weight:700;color:var(--text);margin-bottom:8px;">
  {"Password updated!" if lang_en else "Password aggiornata!"}
</div>
<p style="color:var(--text2);font-size:13px;margin-bottom:20px;">
  {"You can now sign in with your new password." if lang_en else "Ora puoi accedere con la nuova password."}
</p>
<a href="/login" class="btn btn-primary" style="display:block;text-align:center;padding:11px;">
  {"Sign in →" if lang_en else "Accedi →"}
</a>"""
        elif phase == "new_password":
            err_html = f'<div style="color:var(--red);font-size:12px;margin-bottom:10px;">! {err_msg}</div>' if err_msg else ""
            body = f"""
<div style="font-size:16px;font-weight:700;color:var(--text);margin-bottom:6px;">
  {"Set new password" if lang_en else "Imposta nuova password"}
</div>
<p style="color:var(--text2);font-size:12px;margin-bottom:16px;">
  {"Enter your new password below." if lang_en else "Inserisci la tua nuova password."}
</p>
{err_html}
<form method="POST" action="/forgot-password">
  <input type="hidden" name="phase" value="new_password">
  <input type="hidden" name="token" value="{token}">
  <div style="margin-bottom:12px;">
    <label style="display:block;font-size:10px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px;">
      {"New password (min 8 chars)" if lang_en else "Nuova password (min 8 caratteri)"}
    </label>
    <input type="password" name="new_password" minlength="8" required
      style="width:100%;box-sizing:border-box;padding:10px 13px;font-size:13px;border-radius:7px;">
  </div>
  <div style="margin-bottom:16px;">
    <label style="display:block;font-size:10px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px;">
      {"Confirm password" if lang_en else "Conferma password"}
    </label>
    <input type="password" name="confirm_password" required
      style="width:100%;box-sizing:border-box;padding:10px 13px;font-size:13px;border-radius:7px;">
  </div>
  <button type="submit" class="btn btn-primary" style="width:100%;padding:11px;font-size:14px;font-weight:700;">
    {"Reset password" if lang_en else "Reimposta password"}
  </button>
</form>"""
        else:  # enter_code
            err_html = f'<div style="color:var(--red);font-size:12px;margin-bottom:10px;">! {err_msg}</div>' if err_msg else ""
            body = f"""
<div style="font-size:16px;font-weight:700;color:var(--text);margin-bottom:6px;">
  {"Forgot your password?" if lang_en else "Hai dimenticato la password?"}
</div>
<p style="color:var(--text2);font-size:12px;margin-bottom:16px;line-height:1.5;">
  {"The recovery code is shown in Settings &rarr; Recovery code (admin only). If you have lost it, access cannot be recovered." if lang_en else "Il recovery code si trova in Impostazioni &rarr; Recovery code (solo da admin). Se lo hai perso, non puoi recuperare l'accesso."}
</p>
{err_html}
<form method="POST" action="/forgot-password">
  <input type="hidden" name="phase" value="enter_code">
  <div style="margin-bottom:16px;">
    <label style="display:block;font-size:10px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px;">
      {T("Codice di recupero")}
    </label>
    <input type="text" name="recovery_code" required autocomplete="off" spellcheck="false"
      style="width:100%;box-sizing:border-box;padding:10px 13px;font-size:14px;font-family:var(--mono);
             border-radius:7px;letter-spacing:1px;"
      placeholder="xxxx-xxxx-xxxx">
  </div>
  <button type="submit" class="btn btn-primary" style="width:100%;padding:11px;font-size:14px;font-weight:700;">
    {"Verify →" if lang_en else "Verifica →"}
  </button>
</form>
<div style="text-align:center;margin-top:14px;">
  <a href="/login" style="font-size:11px;color:var(--text2);text-decoration:none;">
    ← {"Back to login" if lang_en else "Torna al login"}
  </a>
</div>"""

        _dark = ' data-theme="dark"' if _app_cfg.get("dark_mode") else ''
        return f"""<!DOCTYPE html>
<html lang="{LANGUAGE}"{_dark}>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ROSM — {T("Reimposta Password")}</title>
{FAVICON_TAG}
<style>
{COMMON_CSS}
html,body{{height:100%;margin:0;background:var(--accent) !important;display:flex;
  align-items:center;justify-content:center;}}
.fp-wrap{{width:400px;max-width:96vw;background:var(--bg2);border-radius:14px;
  padding:32px 36px;box-shadow:0 16px 56px rgba(0,0,0,.22);}}
.fp-brand{{text-align:center;margin-bottom:22px;}}
.fp-brand .rosm-word{{font-size:28px;font-weight:900;color:var(--red-brand);}}
</style>
</head>
<body>
<div class="fp-wrap">
  <div class="fp-brand"><div class="rosm-word">ROSM</div></div>
  {body}
</div>
</body>
</html>"""

    def _forbidden_page(self, session):
        username = session.get("username", "?")
        return f"""<!DOCTYPE html>
<html lang="it"><head><meta charset="UTF-8"><title>Accesso negato</title>
<style>{COMMON_CSS}
body{{display:flex;align-items:center;justify-content:center;height:100vh;}}
.box{{text-align:center;}}
</style></head>
<body><div class="box">
  <div style="font-size:48px;margin-bottom:16px;"></div>
  <div style="font-size:18px;font-weight:700;color:var(--text);margin-bottom:8px;">Accesso negato</div>
  <div style="font-size:12px;color:var(--text2);margin-bottom:24px;">
    L'utente <strong style="color:var(--accent2)">{username}</strong> (viewer)
    non ha i permessi per questa azione.
  </div>
  <a href="/home" class="btn" style="margin-right:8px;">Home</a>
  <a href="/" class="btn btn-primary">← Dashboard</a>
</div></body></html>"""

    def render_home_page(self, session):
        username     = (session or {}).get("username", "")
        role         = (session or {}).get("role", "viewer")
        is_admin     = (role == "admin")
        display_name = _get_display_name(username)

        online = sum(1 for r in ROUTERS if r.get("status") == "ONLINE")
        total  = len(ROUTERS)

        # ── Group 1: main operational cards (big) ─────────────────────
        # 5th element: None = always visible, string = permission key via _can_do
        main_cards = [
            ("/",         self._home_icon_dashboard(), "Dashboard",         f"{online}/{total} router online",            None),
            ("/topology", self._home_icon_topology(),  "Site Manager",      f"{len(SITES)} sedi configurate",             None),
            ("/backup",   self._home_icon_backup(),    "Backup",    f"{len(backup_list_files())} archivi salvati","backup"),
            ("/discovery",self._home_icon_discovery(), "Network Discovery", "Scansiona e aggiungi dispositivi",           None),
            ("/upload",     self._home_icon_upload(),      "Script Upload",     T("Carica script .rsc sui router"),         "upload"),
        ]

        # ── Group 2: management/admin cards (smaller) ─────────────────
        mgmt_cards = [
            ("/stats",       self._home_icon_stats(),       "Statistiche",       "Grafici e metriche di rete",                 None),
            ("/upgrade",     self._home_icon_upgrade(),     T("Upgrade RouterOS"), T("Aggiornamento firmware da remoto"),      "upgrade"),
            ("/users",       self._home_icon_users(),       "Utenti",            "Gestisci accessi e ruoli",                   "users_write"),
            ("/settings",    self._home_icon_settings(),    T("Impostazioni"),   T("Lingua, password, recupero account"),      "__elevated__"),
            ("/log",         self._home_icon_report(),      "Log",               f"{len(APP_LOG)} {T('eventi registrati')}",  None),
            ("/credentials", self._home_icon_credentials(), "Credentials",       f"{len(CRED_SETS)} set configurati",          "credentials"),
            ("/guide",       self._home_icon_guide(),       T("Guida"),          T("Funzioni, ruoli e istruzioni rapide"),      None),
        ]

        def _show_card(perm):
            if perm is None: return True
            if perm == "__elevated__": return _is_elevated(session)
            return _can_do(session, perm)

        def _card(href, icon, title, subtitle, big=True):
            cls = "home-card" if big else "home-card home-card-sm"
            return (f'<a href="{href}" class="{cls}">'
                    f'<div class="{"home-icon" if big else "home-icon-sm"}">{icon}</div>'
                    f'<div class="home-card-title">{title}</div>'
                    f'<div class="home-card-sub">{subtitle}</div>'
                    f'</a>')

        main_html = "".join(
            _card(h, ic, ti, su, big=True)
            for h, ic, ti, su, perm in main_cards
            if _show_card(perm)
        )
        mgmt_html = "".join(
            _card(h, ic, ti, su, big=False)
            for h, ic, ti, su, perm in mgmt_cards
            if _show_card(perm)
        )

        sep_label    = "Gestione" if LANGUAGE == "it" else "Management"
        lbl_greeting = "Ciao" if LANGUAGE == "it" else "Hello"
        lbl_choose   = "Scegli cosa vuoi fare" if LANGUAGE == "it" else "Choose what you'd like to do"
        _dark        = ' data-theme="dark"' if _user_dark_mode(session) else ''

        # MFA suggestion banner (shown if MFA available but not enabled for this user)
        # Dismissal is keyed by session token so it reappears on every new login.
        user_data = USERS.get(username, {})
        mfa_banner = ""
        if MFA_AVAILABLE and not user_data.get("mfa_enabled"):
            if LANGUAGE == "it":
                _mfa_txt   = "Proteggi il tuo account abilitando l'autenticazione a due fattori (2FA)."
                _mfa_link  = "Abilita 2FA &nbsp;›"
                _mfa_close = "Ignora"
            else:
                _mfa_txt   = "Protect your account by enabling two-factor authentication (2FA)."
                _mfa_link  = "Enable 2FA &nbsp;›"
                _mfa_close = "Dismiss"
            _mfa_users_href = "/users" if is_admin else "#"
            # Extract raw session token so we can key the dismissal to this login session
            _raw_tok = ""
            for _cp in self.headers.get("Cookie", "").split(";"):
                _cp = _cp.strip()
                if _cp.startswith("session="):
                    _raw_tok = _cp[8:][:32]   # keep first 32 chars as key (safe, no secret info)
                    break
            _mfa_sk = f"mfa_skip_{_raw_tok}"
            mfa_banner = f"""<div id="mfaBanner" style="display:flex;align-items:center;gap:12px;
  background:rgba(217,119,6,.08);border:1px solid rgba(217,119,6,.3);
  border-radius:8px;padding:10px 14px;margin-bottom:20px;font-size:12px;color:var(--text2);">
  <span style="font-size:10px;font-weight:800;color:var(--yellow);background:rgba(217,119,6,.15);
    border:1px solid rgba(217,119,6,.3);border-radius:4px;padding:2px 6px;flex-shrink:0;letter-spacing:.4px;">2FA</span>
  <span style="flex:1;">{_mfa_txt}</span>
  {'<a href="' + _mfa_users_href + '" class="btn" style="font-size:11px;padding:4px 10px;white-space:nowrap;color:var(--yellow);border-color:var(--yellow)44;">' + _mfa_link + '</a>' if is_admin else ''}
  <button onclick="this.closest(\'#mfaBanner\').style.display=\'none\';sessionStorage.setItem(\'{_mfa_sk}\',\'1\')"
    style="background:none;border:none;color:var(--text3);cursor:pointer;font-size:11px;">{_mfa_close}</button>
</div>
<script>if(sessionStorage.getItem('{_mfa_sk}'))document.getElementById('mfaBanner').style.display='none';</script>"""

        return f"""<!DOCTYPE html>
<html lang="{LANGUAGE}"{_dark}>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ROSM — Home</title>
{FAVICON_TAG}
<style>
{COMMON_CSS}
html,body{{min-height:100%;margin:0;background:var(--bg);}}
.home-body{{padding:40px 32px;max-width:1120px;margin:0 auto;}}
.home-greeting{{font-family:var(--sans);font-size:22px;font-weight:700;color:var(--text);margin-bottom:8px;}}
.home-sub{{font-size:12px;color:var(--text2);margin-bottom:36px;}}
.home-grid{{
  display:flex;flex-wrap:wrap;gap:18px;
  justify-content:center;
}}
.home-grid-sm{{
  display:flex;flex-wrap:wrap;gap:14px;
  justify-content:center;
}}
.home-card{{
  background:var(--bg2);border:1px solid var(--border);border-radius:14px;
  padding:26px 18px 22px;width:195px;flex-shrink:0;
  display:flex;flex-direction:column;align-items:center;gap:10px;
  text-decoration:none;transition:all .18s;
  box-shadow:0 2px 8px rgba(27,58,107,.06);
}}
.home-card-sm{{
  padding:18px 14px 16px !important;width:160px !important;
  border-radius:12px !important;gap:8px !important;
}}
.home-card:hover{{
  border-color:var(--accent);
  box-shadow:0 6px 24px rgba(27,58,107,.14);
  transform:translateY(-3px);
}}
.home-icon{{
  width:68px;height:68px;
  background:linear-gradient(135deg,var(--accent) 0%,var(--accent2) 100%);
  border-radius:16px;
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 4px 14px rgba(27,58,107,.20);
}}
.home-icon svg{{width:34px;height:34px;}}
.home-icon-sm{{
  width:48px;height:48px;
  background:linear-gradient(135deg,var(--accent) 0%,var(--accent2) 100%);
  border-radius:12px;
  display:flex;align-items:center;justify-content:center;
  box-shadow:0 3px 10px rgba(27,58,107,.18);
}}
.home-icon-sm svg{{width:24px;height:24px;}}
.home-card-title{{
  font-family:var(--sans);font-size:14px;font-weight:700;color:var(--text);
  text-align:center;
}}
.home-card-sm .home-card-title{{font-size:12px !important;}}
.home-card-sub{{
  font-size:11px;color:var(--text2);text-align:center;line-height:1.4;
}}
.home-card-sm .home-card-sub{{font-size:10px !important;}}
.home-sep{{
  display:flex;align-items:center;gap:12px;
  margin:28px 0 18px;
}}
.home-sep-line{{
  flex:1;height:2px;
  background:linear-gradient(90deg,var(--accent) 0%,var(--accent2) 100%);
  border-radius:2px;opacity:.55;
}}
.home-sep-label{{
  font-size:10px;font-weight:700;color:var(--accent);
  text-transform:uppercase;letter-spacing:1px;white-space:nowrap;
}}
.home-footer{{
  text-align:center;margin-top:40px;font-size:10px;color:var(--text3);
  padding-bottom:24px;
}}
</style>
</head>
<body>
{self._shared_header_html(session, active_page='home')}

<div id="changeLogPanel"></div>

{self._changelog_modal_html()}

<div class="home-body">
  <div class="home-greeting">{lbl_greeting}, {display_name}</div>
  <div class="home-sub">{lbl_choose}</div>
  {mfa_banner}

  <div class="home-grid">
    {main_html}
  </div>

  <div class="home-sep">
    <div class="home-sep-line"></div>
    <div class="home-sep-label">{sep_label}</div>
    <div class="home-sep-line"></div>
  </div>

  <div class="home-grid-sm">
    {mgmt_html}
  </div>

  <div class="home-footer">
    ROSM v{APP_VERSION} {APP_STAGE} &nbsp;·&nbsp; by Jacopo Cipriani &nbsp;·&nbsp;
    <a href="#" onclick="document.getElementById('changelogModal').classList.add('open');return false;" style="color:var(--text3);text-decoration:none;">Changelog</a>
    &nbsp;·&nbsp;
    <a href="#" onclick="document.getElementById('creditsModal').style.display='flex';return false;" style="color:var(--text3);text-decoration:none;">Credits</a>
  </div>
</div>
</body>
</html>"""

    # ── Home page SVG icons ──────────────────────────────────────────────
    def _home_icon_dashboard(self):
        return """<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="4" y="4" width="12" height="12" rx="2" fill="rgba(255,255,255,.9)"/>
  <rect x="20" y="4" width="12" height="12" rx="2" fill="rgba(255,255,255,.6)"/>
  <rect x="4" y="20" width="12" height="12" rx="2" fill="rgba(255,255,255,.6)"/>
  <rect x="20" y="20" width="12" height="12" rx="2" fill="rgba(255,255,255,.9)"/>
</svg>"""

    def _home_icon_upload(self):
        return """<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="6" y="24" width="24" height="5" rx="2" fill="rgba(255,255,255,.5)"/>
  <path d="M18 6 L18 22" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M11 13 L18 6 L25 13" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>"""

    def _home_icon_provision(self):
        return """<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="5" y="8" width="26" height="14" rx="3" fill="rgba(255,255,255,.45)"/>
  <path d="M12 12 L16 16 L24 10" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  <rect x="5" y="26" width="10" height="3" rx="1.5" fill="rgba(255,255,255,.6)"/>
  <rect x="18" y="26" width="13" height="3" rx="1.5" fill="rgba(255,255,255,.3)"/>
</svg>"""

    def _home_icon_site_scan(self):
        return """<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="18" cy="18" r="12" stroke="rgba(255,255,255,.35)" stroke-width="1.5" fill="none"/>
  <circle cx="18" cy="18" r="7"  stroke="rgba(255,255,255,.6)"  stroke-width="2"   fill="none"/>
  <circle cx="18" cy="18" r="3"  fill="white"/>
  <path d="M18 6 L18 11"  stroke="rgba(255,255,255,.5)" stroke-width="2" stroke-linecap="round"/>
  <path d="M18 25 L18 30" stroke="rgba(255,255,255,.5)" stroke-width="2" stroke-linecap="round"/>
  <path d="M6 18 L11 18"  stroke="rgba(255,255,255,.5)" stroke-width="2" stroke-linecap="round"/>
  <path d="M25 18 L30 18" stroke="rgba(255,255,255,.5)" stroke-width="2" stroke-linecap="round"/>
  <circle cx="28" cy="28" r="5"  fill="rgba(255,255,255,.9)"/>
  <path d="M26 28 L28 30 L31 26" stroke="#1e3a5f" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
</svg>"""

    def _home_icon_upgrade(self):
        return """<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="6" y="6" width="24" height="16" rx="3" fill="rgba(255,255,255,.5)"/>
  <path d="M18 9 L18 19" stroke="white" stroke-width="2" stroke-linecap="round"/>
  <path d="M13 13 L18 8 L23 13" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  <path d="M6 26 L30 26" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
  <circle cx="18" cy="30" r="2" fill="rgba(255,255,255,.8)"/>
</svg>"""

    def _home_icon_users(self):
        return """<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="13" cy="13" r="5" fill="rgba(255,255,255,.9)"/>
  <circle cx="24" cy="12" r="4" fill="rgba(255,255,255,.55)"/>
  <path d="M4 28 C4 22 8 19 13 19 C18 19 22 22 22 28" stroke="white" stroke-width="2.5" stroke-linecap="round" fill="none"/>
  <path d="M24 17 C28 17 32 19 32 24" stroke="rgba(255,255,255,.55)" stroke-width="2" stroke-linecap="round" fill="none"/>
</svg>"""

    def _home_icon_discovery(self):
        return """<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
  <circle cx="18" cy="18" r="13" stroke="rgba(255,255,255,.4)" stroke-width="2" fill="none"/>
  <circle cx="18" cy="18" r="8"  stroke="rgba(255,255,255,.6)" stroke-width="2" fill="none"/>
  <circle cx="18" cy="18" r="3"  fill="white"/>
  <path d="M18 5 L18 7" stroke="rgba(255,255,255,.7)" stroke-width="2" stroke-linecap="round"/>
  <path d="M18 29 L18 31" stroke="rgba(255,255,255,.7)" stroke-width="2" stroke-linecap="round"/>
  <path d="M5 18 L7 18"  stroke="rgba(255,255,255,.7)" stroke-width="2" stroke-linecap="round"/>
  <path d="M29 18 L31 18" stroke="rgba(255,255,255,.7)" stroke-width="2" stroke-linecap="round"/>
</svg>"""

    def _home_icon_stats(self):
        return """<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="5"  y="22" width="6" height="10" rx="1.5" fill="rgba(255,255,255,.6)"/>
  <rect x="15" y="14" width="6" height="18" rx="1.5" fill="rgba(255,255,255,.85)"/>
  <rect x="25" y="8"  width="6" height="24" rx="1.5" fill="white"/>
</svg>"""

    # ── Backup Manager page ──────────────────────────────────────────────
    def render_backup_page(self, session):
        is_admin = _is_admin(session)

        cfg            = BACKUP_CONFIG
        interval_h     = cfg.get("interval_hours", 24)
        retention      = cfg.get("retention_days", 30)
        enabled        = cfg.get("enabled", False)
        last_run       = cfg.get("last_run", "—")
        next_ts        = cfg.get("next_run_ts", 0)
        next_run       = datetime.fromtimestamp(next_ts).strftime("%Y-%m-%d %H:%M") if next_ts and enabled else "—"
        bk_show_sens   = cfg.get("show_sensitive",  True)
        bk_keep_router = cfg.get("keep_on_router",  False)

        # ── Build target <select> options SERVER-SIDE ──────────────────
        online_count  = sum(1 for r in ROUTERS if r.get("status") == "ONLINE")
        bk_idx        = backup_index_by_router()   # {safe_name: latest_mtime_ts}
        now_ts        = time.time()
        stale_days    = 7  # "backup scaduto" threshold

        # Smart filters
        no_backup_ips = [r["ip"] for r in ROUTERS
                         if r.get("status") == "ONLINE"
                         and not router_has_backup(r, bk_idx)]
        stale_ips     = [r["ip"] for r in ROUTERS
                         if router_has_backup(r, bk_idx)
                         and (now_ts - bk_idx.get(router_safe_name(r),
                              bk_idx.get(r["ip"], now_ts))) > stale_days * 86400]

        select_html  = f'<option value="all_online">{T("Tutti i router ONLINE")} ({online_count})</option>'
        select_html += f'<optgroup label="{T("Selezione intelligente")}">'
        select_html += f'<option value="no_backup">{T("Senza backup esistente")} ({len(no_backup_ips)} router)</option>'
        select_html += f'<option value="stale_backup">{T("Backup più vecchio di")} {stale_days} {"giorni" if LANGUAGE=="it" else "days"} ({len(stale_ips)} router)</option>'
        select_html += '</optgroup>'

        # Per Sede
        if SITES:
            select_html += '<optgroup label="Per Sede">'
            for sid, site in sorted(SITES.items(), key=lambda x: x[1].get("name","")):
                sname = site.get("name", sid)
                scity = site.get("city", "")
                cid   = site.get("credential_id", "")
                cname = next((c["name"] for c in CRED_SETS if c["id"] == cid), "")
                creds_badge = f" [creds: {cname}]" if cname else f" [{T('creds: predefinite')}]"
                label = sname + (f" ({scity})" if scity else "")
                n_online = sum(1 for r in ROUTERS
                               if r.get("site_id") == sid and r.get("status") == "ONLINE")
                select_html += f'<option value="site:{sid}">{label} — {n_online} online{creds_badge}</option>'
            select_html += '</optgroup>'

        # Per Gruppo
        groups = sorted({r.get("group","") for r in ROUTERS if r.get("group","")})
        if groups:
            select_html += '<optgroup label="Per Gruppo">'
            for g in groups:
                n = sum(1 for r in ROUTERS if r.get("group") == g and r.get("status") == "ONLINE")
                select_html += f'<option value="group:{g}">{g} — {n} online</option>'
            select_html += '</optgroup>'

        # Singolo router
        if ROUTERS:
            select_html += '<optgroup label="Singolo router">'
            for r in sorted(ROUTERS, key=lambda x: x["ip"]):
                dot = "●" if r.get("status") == "ONLINE" else "○"
                lbl = f'{dot} {r["ip"]}'
                if r.get("name"): lbl += f' ({r["name"]})'
                select_html += f'<option value="ip:{r["ip"]}">{lbl}</option>'
            select_html += '</optgroup>'

        # JS data for _resolveTargetIPs
        routers_js      = json.dumps([
            {"ip": r["ip"], "name": r.get("name",""), "status": r.get("status",""),
             "group": r.get("group",""), "site_id": r.get("site_id","")}
            for r in ROUTERS
        ])
        no_backup_js    = json.dumps(no_backup_ips)
        stale_backup_js = json.dumps(stale_ips)
        # Cred sets for the credential assignment UI (name only, no credentials)
        cred_sets_js    = json.dumps([{"id": c["id"], "name": c["name"]} for c in CRED_SETS])

        # ── Server-side file list ──────────────────────────────────────
        bk_files = backup_list_files()
        def _fmt_size(n):
            if n >= 1024*1024: return f"{n/1024/1024:.1f} MB"
            if n >= 1024:      return f"{n/1024:.1f} KB"
            return f"{n} B"
        total_bk_size   = sum(f["size"] for f in bk_files)
        total_bk_size_s = _fmt_size(total_bk_size) if bk_files else ""
        files_js        = json.dumps(bk_files)
        files_count_html = f'{len(bk_files)} file' if bk_files else ''

        return self._page_shell("Backup", f"""
<style>
.bk-grid    {{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:18px;}}
.bk-grid1   {{grid-column:1/-1;}}
@media(max-width:700px){{.bk-grid{{grid-template-columns:1fr;}}}}
.bk-field   {{margin-bottom:12px;}}
.bk-field label{{display:block;font-size:10px;font-weight:700;color:var(--text2);
  text-transform:uppercase;letter-spacing:.7px;margin-bottom:5px;}}
.bk-toggle  {{display:flex;align-items:center;gap:10px;}}
.toggle-sw  {{position:relative;width:40px;height:22px;flex-shrink:0;}}
.toggle-sw input{{opacity:0;width:0;height:0;}}
.toggle-track{{position:absolute;inset:0;background:var(--border2);border-radius:11px;
  cursor:pointer;transition:background .2s;}}
.toggle-sw input:checked+.toggle-track{{background:var(--green);}}
.toggle-track::after{{content:'';position:absolute;left:3px;top:3px;
  width:16px;height:16px;border-radius:50%;background:#fff;
  transition:transform .2s;box-shadow:0 1px 3px rgba(0,0,0,.2);}}
.toggle-sw input:checked+.toggle-track::after{{transform:translateX(18px);}}
.status-ok  {{color:var(--green);font-weight:700;}}
.status-fail{{color:var(--red);font-weight:700;}}
.bk-run-row {{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:18px;}}
.bk-spinner {{display:none;width:16px;height:16px;border:2px solid var(--border2);
  border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite;}}
@keyframes spin{{to{{transform:rotate(360deg);}}}}
.bk-spinner.active{{display:inline-block;}}
.bk-file-table td,.bk-file-table th{{padding:7px 10px;font-size:11px;}}
.bk-size   {{color:var(--text2);font-family:var(--mono);}}
.bk-date   {{color:var(--text3);font-family:var(--mono);}}
.bk-router-grid{{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px;}}
.bk-router-chip{{background:var(--bg3);border:1px solid var(--border2);border-radius:6px;
  padding:5px 10px;font-size:11px;cursor:pointer;transition:all .15s;user-select:none;
  display:flex;align-items:center;gap:5px;}}
.bk-router-chip.sel{{background:rgba(27,58,107,.12);border-color:var(--accent);color:var(--accent);}}
.bk-router-chip.online::before{{content:'';width:7px;height:7px;border-radius:50%;
  background:var(--green);flex-shrink:0;}}
.bk-router-chip.offline::before{{content:'';width:7px;height:7px;border-radius:50%;
  background:var(--red);flex-shrink:0;}}
</style>

<div class="bk-grid">

  <!-- ── Config card ──────────────────────────────────── -->
  <div class="card">
    <div class="card-header">Configurazione schedule</div>
  <div id="bkJsErrBanner" style="display:none;background:#fee2e2;border:1px solid #fca5a5;padding:8px 12px;font-size:11px;color:#991b1b;"></div>
    <div class="card-body">
      <div class="bk-field">
        <label>Backup automatico</label>
        <div class="bk-toggle">
          <label class="toggle-sw">
            <input type="checkbox" id="bkEnabled" {'checked' if enabled else ''} onchange="onEnabledChange(this)">
            <div class="toggle-track"></div>
          </label>
          <span id="bkEnabledLbl" style="font-size:12px;color:var(--text2);">{'Attivo' if enabled else 'Disattivo'}</span>
        </div>
      </div>
      <div class="bk-field">
        <label>Intervallo (ore)</label>
        <input type="text" id="bkInterval" value="{interval_h}"
               style="width:100px;">
      </div>
      <div class="bk-field">
        <label>Data retention (giorni, 0 = illimitato)</label>
        <input type="number" id="bkRetention" value="{retention}" min="0"
               style="width:100px;">
        <span style="font-size:10px;color:var(--text3);margin-left:8px;">
          I backup più vecchi vengono rimossi automaticamente
        </span>
      </div>
      <div style="margin-top:10px;margin-bottom:10px;">
        <label style="display:flex;align-items:center;gap:7px;font-size:11px;cursor:pointer;margin-bottom:6px;">
          <input type="checkbox" id="bkAutoShowSens" {'checked' if bk_show_sens else ''}>
          Backup completo (show-sensitive — include password e chiavi)
        </label>
        <label style="display:flex;align-items:center;gap:7px;font-size:11px;cursor:pointer;">
          <input type="checkbox" id="bkAutoKeepOnRouter" {'checked' if bk_keep_router else ''}>
          Lascia copia del backup anche sul router
        </label>
      </div>
      <div style="margin-top:6px;display:flex;align-items:center;gap:10px;">
        <button class="btn btn-primary" onclick="saveConfig()">Salva configurazione</button>
        <span id="cfgMsg" style="font-size:11px;color:var(--text2);"></span>
      </div>
      <div style="margin-top:14px;padding-top:12px;border-top:1px solid var(--border);
                  font-size:11px;color:var(--text2);display:flex;flex-direction:column;gap:4px;">
        <div>Ultimo backup: <strong id="lastRunLbl">{last_run}</strong></div>
        <div>Prossimo backup: <strong id="nextRunLbl">{next_run}</strong></div>
      </div>
    </div>
  </div>

  <!-- ── Target + Credenziali card ───────────────────────── -->
  <div class="card">
    <div class="card-header" style="display:flex;align-items:center;justify-content:space-between;">
      <span>{T("Avvia Backup Manuale")}</span>
      <a class="btn" href="/backup" style="padding:2px 8px;font-size:10px;" title="{T("Ricarica la pagina per aggiornare l'elenco")}">↺ Aggiorna</a>
    </div>
    <div class="card-body">

      <!-- STEP 1: Target -->
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
        <span style="background:var(--accent);color:#fff;border-radius:50%;width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;flex-shrink:0;">1</span>
        <label style="font-size:10px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.7px;margin:0;">Seleziona i router</label>
      </div>
      <select id="bkTarget" style="width:100%;box-sizing:border-box;font-size:12px;margin-bottom:4px;"
              onchange="onTargetChange()">
        {select_html}
      </select>
      <div id="bkTargetInfo" style="margin-bottom:16px;font-size:11px;color:var(--text2);min-height:14px;"></div>

      <!-- STEP 2: Credenziali -->
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
        <span style="background:var(--accent);color:#fff;border-radius:50%;width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;flex-shrink:0;">2</span>
        <label style="font-size:10px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.7px;margin:0;">Seleziona le credenziali SSH</label>
        <a href="/credentials" style="margin-left:auto;font-size:10px;color:var(--accent);text-decoration:none;font-weight:600;white-space:nowrap;">
          Apri Credential Manager →
        </a>
      </div>
      <select id="bkCredPicker" onchange="applyBkCred(this.value)" style="width:100%;box-sizing:border-box;font-size:12px;margin-bottom:4px;">
        <option value="">— Automatico: usa le credenziali del sito o del router —</option>
        {chr(10).join(f'        <option value="{c["id"]}">{c["name"]}</option>' for c in CRED_SETS)}
      </select>
      {'<div style="margin-bottom:4px;font-size:10px;color:var(--text3);font-style:italic;">Nessun set credenziali configurato. <a href="/credentials" style="color:var(--accent);">Creane uno nel Credential Manager →</a></div>' if not CRED_SETS else ''}
      <div id="bkCredInfo" style="margin-bottom:16px;font-size:11px;min-height:14px;padding:6px 10px;border-radius:6px;background:var(--bg3);border:1px solid var(--border);display:none;"></div>

      <!-- STEP 3: Opzioni -->
      <div style="margin-bottom:12px;">
        <label style="display:flex;align-items:center;gap:7px;font-size:11px;cursor:pointer;margin-bottom:6px;">
          <input type="checkbox" id="bkManShowSens" checked>
          Backup completo (show-sensitive — include password e chiavi)
        </label>
        <label style="display:flex;align-items:center;gap:7px;font-size:11px;cursor:pointer;">
          <input type="checkbox" id="bkManKeepOnRouter">
          Lascia copia del backup anche sul router
        </label>
      </div>

      <!-- STEP 4: Avvia -->
      <div style="border-top:1px solid var(--border);padding-top:14px;display:flex;align-items:center;gap:12px;">
        <span style="background:var(--accent);color:#fff;border-radius:50%;width:20px;height:20px;display:inline-flex;align-items:center;justify-content:center;font-size:10px;font-weight:800;flex-shrink:0;">3</span>
        <button type="button" class="btn btn-primary" id="btnAvviaBackup" onclick="runBackup()" style="padding:8px 22px;font-size:13px;font-weight:700;">
          {T("Avvia Backup Manuale")}
        </button>
        <div class="bk-spinner" id="bkSpinner"></div>
        <span id="bkRunMsg" style="font-size:11px;color:var(--text2);"></span>
      </div>
    </div>
  </div>

  <!-- ── Log terminale backup ──────────────────────────── -->
  <div class="card bk-grid1">
    <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
      <span>Log operazioni</span>
      <div style="display:flex;gap:8px;align-items:center;">
        <span id="bkResultCount" style="color:var(--text3);font-size:10px;"></span>
        <button class="btn" onclick="clearBkLog()" style="padding:2px 8px;font-size:10px;">x Pulisci</button>
      </div>
    </div>
    <div id="bkTerminal" style="
      background:#0d1117;border-radius:0 0 8px 8px;
      font-family:var(--mono);font-size:11px;
      min-height:120px;max-height:320px;overflow-y:auto;
      padding:12px 16px;line-height:1.7;
    ">
      <span class="bk-log-placeholder" style="color:#6e7681;">Nessuna operazione eseguita. Avvia un backup per vedere il log.</span>
    </div>
  </div>

  <!-- ── Archivio file ─────────────────────────────────── -->
  <div class="card bk-grid1">
    <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;">
      <span>{T("Archivio backup")}</span>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
        <span id="bkFileCount" style="color:var(--text3);font-size:10px;">{files_count_html}{(' &nbsp;·&nbsp; ' + T('Dimensione totale') + ': <strong>' + total_bk_size_s + '</strong>') if total_bk_size_s else ''}</span>
        <button id="bkDelSelBtn" class="btn btn-danger" onclick="deleteBulkBk()"
          style="padding:2px 10px;font-size:10px;display:none;">
          {'[X] Delete selected' if LANGUAGE=='en' else '[X] Elimina selezionati'}
        </button>
        <button class="btn" onclick="refreshFiles()" style="padding:2px 8px;font-size:10px;">↺ {T("Aggiorna")}</button>
      </div>
    </div>
    <!-- Filter bar -->
    <div style="display:flex;gap:8px;align-items:center;padding:8px 12px;
      border-bottom:1px solid var(--border);flex-wrap:wrap;">
      <input type="text" id="bkFileFilter" placeholder="{'Filter by filename…' if LANGUAGE=='en' else 'Filtra per nome file…'}"
        oninput="_bkPage=0;applyBkFilter()" style="flex:1;min-width:140px;font-size:11px;">
      <input type="date" id="bkDateFilter" title="{'Filter by date' if LANGUAGE=='en' else 'Filtra per data'}"
        oninput="_bkPage=0;applyBkFilter()" style="font-size:11px;">
      <select id="bkPerPage" onchange="_bkPage=0;applyBkFilter()"
        style="font-size:11px;padding:4px 8px;border-radius:var(--r);
          border:1px solid var(--border2);background:var(--bg2);color:var(--text);">
        <option value="10">10</option>
        <option value="25" selected>25</option>
        <option value="50">50</option>
        <option value="9999">{'All' if LANGUAGE=='en' else 'Tutti'}</option>
      </select>
    </div>
    <div class="table-wrap">
      <table class="bk-file-table">
        <thead>
          <tr class="label-row">
            <th style="width:30px;text-align:center;"><input type="checkbox" id="bkSelAll" title="{'Select all' if LANGUAGE=='en' else 'Seleziona tutti'}" onchange="toggleBkSelAll(this)"></th>
            <th>File</th><th>{'Size' if LANGUAGE=='en' else 'Dimensione'}</th><th>{'Date' if LANGUAGE=='en' else 'Data'}</th><th style="width:120px;">{'Actions' if LANGUAGE=='en' else 'Azioni'}</th>
          </tr>
        </thead>
        <tbody id="bkFilesTbody"></tbody>
      </table>
    </div>
    <div id="bkPagination" style="display:flex;align-items:center;gap:6px;
      padding:8px 12px;border-top:1px solid var(--border);font-size:11px;color:var(--text2);"></div>
  </div>


</div>

<script>
// Router data for target resolution (server-rendered, always up-to-date on page load)
var ROUTERS_BK      = {routers_js};
var NO_BACKUP_IPS   = {no_backup_js};
var STALE_IPS       = {stale_backup_js};
var CRED_SETS_DATA  = {cred_sets_js};
var BK_INIT_FILES   = {files_js};
var _bkCredId       = '';
var _bkAllFiles     = [];
var _bkPage         = 0;
var _bkFilteredCount = 0;
var _BK_LOG_KEY     = 'rosm_bk_log_v1';

function escHtml(s) {{
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

function applyBkCred(credId) {{
  _bkCredId = credId;
  var info = document.getElementById('bkCredInfo');
  if(!info) return;
  if(credId) {{
    var c = CRED_SETS_DATA.find(function(x){{return x.id===credId;}});
    info.style.display = 'block';
    info.style.color   = 'var(--green)';
    info.innerHTML = c
      ? 'OK <strong>' + escHtml(c.name) + '</strong> &nbsp;·&nbsp; username: <code style="font-family:var(--mono);">' + escHtml(c.username) + '</code>'
      : '! Set credenziali non trovato.';
  }} else {{
    info.style.display = 'block';
    info.style.color   = 'var(--text2)';
    info.innerHTML = 'ℹ Verranno usate le credenziali assegnate a ciascun sito (impostabili nella sezione qui sotto) o, in mancanza, quelle configurate per il singolo router.';
  }}
}}

function _resolveTargetIPs() {{
  var val = document.getElementById('bkTarget').value;
  if(val === 'all_online')    return ROUTERS_BK.filter(function(r){{return r.status==='ONLINE';}}).map(function(r){{return r.ip;}});
  if(val === 'no_backup')     return NO_BACKUP_IPS;
  if(val === 'stale_backup')  return STALE_IPS;
  if(val.startsWith('site:')) {{
    var sid = val.slice(5);
    return ROUTERS_BK.filter(function(r){{return r.site_id===sid && r.status==='ONLINE';}}).map(function(r){{return r.ip;}});
  }}
  if(val.startsWith('group:')) {{
    var grp = val.slice(6);
    return ROUTERS_BK.filter(function(r){{return r.group===grp && r.status==='ONLINE';}}).map(function(r){{return r.ip;}});
  }}
  if(val.startsWith('ip:')) return [val.slice(3)];
  return [];
}}

function onTargetChange() {{
  var ips = _resolveTargetIPs();
  var info = document.getElementById('bkTargetInfo');
  if(!info) return;
  var val = document.getElementById('bkTarget').value;
  var all  = val.startsWith('ip:') ? 1 :
             ROUTERS_BK.filter(function(r) {{
               if(val==='all_online') return true;
               if(val.startsWith('site:'))  return r.site_id===val.slice(5);
               if(val.startsWith('group:')) return r.group===val.slice(6);
               return false;
             }}).length;
  if(val.startsWith('ip:')) {{
    var r = ROUTERS_BK.find(function(x){{return x.ip===val.slice(3);}});
    info.textContent = r ? (r.status==='ONLINE'?'● ONLINE':'○ OFFLINE') + (r.name?' — '+r.name:'') : '';
  }} else {{
    info.textContent = ips.length + ' router ONLINE su ' + all + ' totali verranno backuppati';
  }}
}}

// Aggiorna etichetta Attivo/Disattivo al cambio del toggle
function onEnabledChange(chk) {{
  var lbl = document.getElementById('bkEnabledLbl');
  if(lbl) lbl.textContent = chk.checked ? 'Attivo' : 'Disattivo';
}}

async function saveConfig() {{
  var msg = document.getElementById('cfgMsg');
  msg.textContent = '…';
  msg.style.color = 'var(--text2)';
  try {{
    var enabled = document.getElementById('bkEnabled').checked;
    var _bkRaw = (document.getElementById('bkInterval').value||'').trim();
    var interval_hours = _bkRaw.toUpperCase()==='TEST' ? (5/60) : (parseFloat(_bkRaw)||24);
    var retention_days = parseInt(document.getElementById('bkRetention').value) || 30;
    var show_sensitive   = document.getElementById('bkAutoShowSens') ? document.getElementById('bkAutoShowSens').checked : true;
    var keep_on_router   = document.getElementById('bkAutoKeepOnRouter') ? document.getElementById('bkAutoKeepOnRouter').checked : false;
    var body = {{ enabled: enabled, interval_hours: interval_hours, retention_days: retention_days, show_sensitive: show_sensitive, keep_on_router: keep_on_router }};
    var r = await fetch('/api/backup/config', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify(body)
    }});
    var j = await r.json();
    if(j.ok) {{
      // Aggiorna tutti gli elementi visibili del riquadro
      msg.textContent = 'OK Configurazione salvata';
      msg.style.color = 'var(--green)';
      var lbl = document.getElementById('bkEnabledLbl');
      if(lbl) {{ lbl.textContent = enabled ? 'Attivo' : 'Disattivo'; lbl.style.color = enabled ? 'var(--green)' : 'var(--text2)'; }}
      var nextLbl = document.getElementById('nextRunLbl');
      if(nextLbl) {{
        nextLbl.textContent = (j.config && j.config.enabled && j.config.next_run_ts)
          ? new Date(j.config.next_run_ts * 1000).toLocaleString('it-IT')
          : '—';
      }}
      setTimeout(function(){{ msg.textContent = ''; if(lbl) lbl.style.color = ''; }}, 5000);
    }} else {{
      msg.textContent = 'x Errore: ' + (j.msg || 'risposta non valida');
      msg.style.color = 'var(--red)';
    }}
  }} catch(e) {{
    msg.textContent = 'x Errore di rete: ' + e;
    msg.style.color = 'var(--red)';
  }}
}}

// ── Terminal log (persistent via localStorage) ────────────
function _ts() {{
  return new Date().toLocaleTimeString('it-IT',{{hour:'2-digit',minute:'2-digit',second:'2-digit'}});
}}
function logLine(text, color) {{
  var term = document.getElementById('bkTerminal');
  if(!term) return;
  var ph = term.querySelector('.bk-log-placeholder');
  if(ph) term.innerHTML = '';
  var line = document.createElement('div');
  line.style.color = color || '#e6edf3';
  line.innerHTML = '<span style="color:#484f58;">[' + _ts() + ']</span> ' + text;
  term.appendChild(line);
  term.scrollTop = term.scrollHeight;
  try {{
    var stored = JSON.parse(localStorage.getItem(_BK_LOG_KEY) || '[]');
    stored.push(line.outerHTML);
    if(stored.length > 500) stored = stored.slice(-500);
    localStorage.setItem(_BK_LOG_KEY, JSON.stringify(stored));
  }} catch(e) {{}}
}}
function logOk(text)   {{ logLine('OK  ' + text, '#3fb950'); }}
function logErr(text)  {{ logLine('ERR ' + text, '#f85149'); }}
function logInfo(text) {{ logLine('&bull; ' + text, '#79c0ff'); }}
function logWarn(text) {{ logLine('WARN ' + text, '#d29922'); }}
function clearBkLog()  {{
  var term = document.getElementById('bkTerminal');
  if(term) term.innerHTML = '<span class="bk-log-placeholder" style="color:#6e7681;">Log pulito.</span>';
  document.getElementById('bkResultCount').textContent = '';
  try {{ localStorage.removeItem(_BK_LOG_KEY); }} catch(e) {{}}
}}
(function restoreBkLog() {{
  try {{
    var stored = JSON.parse(localStorage.getItem(_BK_LOG_KEY) || '[]');
    if(!stored.length) return;
    var term = document.getElementById('bkTerminal');
    if(!term) return;
    term.innerHTML = '';
    stored.forEach(function(h) {{ term.insertAdjacentHTML('beforeend', h); }});
    term.scrollTop = term.scrollHeight;
  }} catch(e) {{}}
}})();

async function runBackup() {{
  // Immediate visual feedback — first thing, before anything else
  logInfo('Avvio backup richiesto…');
  var btn = document.getElementById('btnAvviaBackup');
  if(btn) btn.disabled = true;
  var spinner = document.getElementById('bkSpinner');
  var msg     = document.getElementById('bkRunMsg');
  if(spinner) spinner.classList.add('active');
  if(msg) msg.textContent = 'Backup in corso…';

  try {{
    var val = document.getElementById('bkTarget') ? document.getElementById('bkTarget').value : 'all_online';
    var targetIPs = _resolveTargetIPs();
    var body = {{}};
    if(val !== 'all_online') body.ips = targetIPs;
    body.show_sensitive  = document.getElementById('bkManShowSens') ? document.getElementById('bkManShowSens').checked : true;
    body.keep_on_router  = document.getElementById('bkManKeepOnRouter') ? document.getElementById('bkManKeepOnRouter').checked : false;

    if(_bkCredId) {{
      body.cred_id = _bkCredId;
      var credName = (CRED_SETS_DATA.find(function(c){{return c.id===_bkCredId;}})||{{}}).name||_bkCredId;
      logInfo('Credenziali: <strong>' + escHtml(credName) + '</strong>');
    }} else {{
      logInfo('Credenziali: automatiche (sito / router)');
    }}

    if(!targetIPs.length && val !== 'all_online') {{
      logWarn('Nessun router ONLINE nel target selezionato — operazione annullata.');
      if(spinner) spinner.classList.remove('active');
      if(msg) msg.textContent = '';
      if(btn) btn.disabled = false;
      return;
    }}
    var targetDesc = val === 'all_online' ? 'tutti i router ONLINE (' + targetIPs.length + ')' : targetIPs.length + ' router selezionati';
    logInfo('Target: <strong>' + targetDesc + '</strong>');
    if(targetIPs.length === 0 && val === 'all_online') {{
      logWarn('Nessun router ONLINE al momento. Verifica che i dispositivi siano raggiungibili o avvia un ping dalla Dashboard.');
      if(spinner) spinner.classList.remove('active');
      if(msg) msg.textContent = '';
      if(btn) btn.disabled = false;
      return;
    }}

    var resp = await fetch('/api/backup/run', {{method:'POST',
      headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(body)}});
    var kickoff = await resp.json();
    if(!kickoff.ok) {{
      logErr('Il server ha rifiutato la richiesta: ' + (kickoff.msg||'errore sconosciuto'));
      if(spinner) spinner.classList.remove('active');
      if(msg) msg.textContent = '';
      if(btn) btn.disabled = false;
      return;
    }}
    logInfo('Backup avviato — attendo il completamento…');

    // Poll until done
    var poll = setInterval(async function() {{
      try {{
        var s = await fetch('/api/backup/status').then(function(r){{return r.json();}});
        if(!s.running) {{
          clearInterval(poll);
          if(spinner) spinner.classList.remove('active');
          if(btn) btn.disabled = false;
          renderResults(s.last_results);
          renderFiles(s.files);
          // Refresh the file archive table
          var tc = document.getElementById('bkFileCount');
          if(tc && s.files) tc.textContent = s.files.length + ' file';
          var lrl = document.getElementById('lastRunLbl');
          if(lrl) lrl.textContent = s.last_run || '—';
          var ok  = (s.last_results||[]).filter(function(x){{return x.ok;}}).length;
          var tot = (s.last_results||[]).length;
          if(tot === 0) {{
            logWarn('Nessun router raggiunto (0 target online).');
          }}
          if(msg) msg.textContent = tot ? ok + '/' + tot + ' completati' : '';
        }}
      }} catch(e) {{
        logErr('Errore durante il polling: ' + e);
        clearInterval(poll);
        if(spinner) spinner.classList.remove('active');
        if(btn) btn.disabled = false;
      }}
    }}, 1500);

  }} catch(e) {{
    logErr('Errore imprevisto in runBackup: ' + e);
    if(spinner) spinner.classList.remove('active');
    if(msg) msg.textContent = '';
    if(btn) btn.disabled = false;
  }}
}}

function renderResults(results) {{
  var count = document.getElementById('bkResultCount');
  if(!results || !results.length) {{ if(count) count.textContent = ''; return; }}
  var ok = results.filter(function(x){{return x.ok;}}).length;
  if(count) count.textContent = ok + '/' + results.length + ' OK';
  results.forEach(function(r) {{
    var label = (r.name || r.ip);
    if(r.ok) {{
      var kb = r.size >= 1024 ? (r.size/1024).toFixed(1) + ' KB' : r.size + ' B';
      logOk('<strong>' + label + '</strong> — ' + r.file + ' (' + kb + ')');
    }} else {{
      logErr('<strong>' + label + '</strong> — ' + r.msg);
    }}
  }});
  logLine('─────────────────────────────────────────────', '#484f58');
  if(ok === results.length) logOk('<strong>Backup completato con successo: ' + ok + '/' + results.length + '</strong>');
  else if(ok === 0) logErr('<strong>Backup fallito: 0/' + results.length + ' router completati</strong>');
  else logWarn('<strong>Backup parziale: ' + ok + '/' + results.length + ' completati</strong>');
}}

function renderFiles(files) {{
  _bkAllFiles = files || [];
  _bkPage = 0;
  applyBkFilter();
}}

function _bkRowHtml(f) {{
  var size = f.size >= 1024*1024 ? (f.size/1024/1024).toFixed(1)+' MB'
           : f.size >= 1024      ? (f.size/1024).toFixed(1)+' KB'
           :                       f.size+' B';
  var fname = f.file;
  var safeOnclick = 'deleteFile(' + JSON.stringify(fname) + ')';
  return '<tr>'
    +'<td style="text-align:center;padding:0 8px;">'
    +'<input type="checkbox" class="bk-sel" value="'+escHtml(fname)+'" onchange="updateBkDelBtn()"></td>'
    +'<td style="font-family:var(--mono);font-size:11px;color:var(--text);">'+escHtml(fname)+'</td>'
    +'<td class="bk-size">'+size+'</td>'
    +'<td class="bk-date">'+escHtml(f.mtime)+'</td>'
    +'<td><div style="display:flex;gap:4px;">'
    +'<a class="btn" href="/backup/download?file='+encodeURIComponent(fname)+'" '
    +'style="padding:2px 8px;font-size:10px;" download>{'Download' if LANGUAGE=='en' else 'Scarica'}</a>'
    +'<button class="btn btn-danger" onclick="'+escHtml(safeOnclick)+'" '
    +'style="padding:2px 8px;font-size:10px;">✕</button>'
    +'</div></td>'
    +'</tr>';
}}

function updateBkDelBtn() {{
  var n = document.querySelectorAll('.bk-sel:checked').length;
  var btn = document.getElementById('bkDelSelBtn');
  if(btn) btn.style.display = n > 0 ? '' : 'none';
  var all = document.getElementById('bkSelAll');
  if(all) {{
    var tot = document.querySelectorAll('.bk-sel').length;
    all.indeterminate = (n > 0 && n < tot);
    all.checked = (tot > 0 && n === tot);
  }}
}}

function toggleBkSelAll(cb) {{
  document.querySelectorAll('.bk-sel').forEach(function(c){{c.checked=cb.checked;}});
  updateBkDelBtn();
}}

async function deleteBulkBk() {{
  var checked = Array.from(document.querySelectorAll('.bk-sel:checked')).map(function(c){{return c.value;}});
  if(!checked.length) return;
  var confirmMsg = {'("Delete " + checked.length + " backup files?")' if LANGUAGE=='en' else '("Eliminare " + checked.length + " file di backup?")' };
  if(!confirm(confirmMsg)) return;
  var btn = document.getElementById('bkDelSelBtn');
  if(btn){{btn.disabled=true;btn.textContent='…';}}
  var ok=0, fail=0;
  for(var i=0;i<checked.length;i++) {{
    try {{
      var r = await fetch('/api/backup/delete', {{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify({{file:checked[i]}})
      }});
      var j = await r.json();
      if(j.ok) ok++; else fail++;
    }} catch(e) {{ fail++; }}
  }}
  await refreshFiles();
  if(btn){{btn.disabled=false;btn.style.display='none';}}
  var allChk=document.getElementById('bkSelAll');
  if(allChk) allChk.checked=false;
  if(fail) alert({'("Impossibile eliminare "+fail+" file(s).")' if LANGUAGE!='en' else '("Failed to delete "+fail+" file(s).")'});
}}

function applyBkFilter() {{
  var tbody = document.getElementById('bkFilesTbody');
  if(!tbody) return;
  var nameF   = (document.getElementById('bkFileFilter') || {{}}).value || '';
  var dateF   = (document.getElementById('bkDateFilter') || {{}}).value || '';
  var perPage = parseInt(((document.getElementById('bkPerPage') || {{}}).value) || '25') || 25;
  var countEl = document.getElementById('bkFileCount');

  if(!_bkAllFiles || !_bkAllFiles.length) {{
    tbody.innerHTML = '<tr><td colspan="4" style="color:var(--text3);font-style:italic;padding:14px;">{'No files in archive.' if LANGUAGE=='en' else 'Nessun file in archivio.'}</td></tr>';
    if(countEl) countEl.textContent = '';
    _renderBkPag(0,0,0); return;
  }}

  var filtered = _bkAllFiles.filter(function(item) {{
    if(nameF && item.file.toLowerCase().indexOf(nameF.toLowerCase()) === -1) return false;
    if(dateF && item.mtime.indexOf(dateF) === -1) return false;
    return true;
  }});
  _bkFilteredCount = filtered.length;
  var pages = Math.max(1, Math.ceil(filtered.length / perPage));
  if(_bkPage >= pages) _bkPage = pages - 1;
  var start = _bkPage * perPage;
  var pageSlice = filtered.slice(start, start + perPage);

  if(countEl) countEl.textContent = filtered.length + ' / ' + _bkAllFiles.length + ' file';
  tbody.innerHTML = pageSlice.map(_bkRowHtml).join('');
  _renderBkPag(start+1, Math.min(start+perPage, filtered.length), filtered.length);
  // Reset bulk-select UI after render
  var bkSelAll = document.getElementById('bkSelAll');
  if(bkSelAll) {{ bkSelAll.checked=false; bkSelAll.indeterminate=false; }}
  var bkDelBtn = document.getElementById('bkDelSelBtn');
  if(bkDelBtn) bkDelBtn.style.display='none';
}}

function _renderBkPag(from, to, total) {{
  var pg = document.getElementById('bkPagination');
  if(!pg) return;
  if(total <= 0) {{ pg.innerHTML=''; return; }}
  var perPage = parseInt(((document.getElementById('bkPerPage') || {{}}).value) || '25') || 25;
  var pages = Math.ceil(total/perPage);
  var info  = '<span>'+from+'&ndash;'+to+' / '+total+'</span>';
  var nav   = pages > 1
    ? ' &nbsp;<button class="btn" onclick="bkPgPrev()" style="padding:2px 7px;font-size:10px;">&lsaquo;</button>'
    +'<button class="btn" onclick="bkPgNext()" style="padding:2px 7px;font-size:10px;">&rsaquo;</button>'
    +'<span style="color:var(--text3);font-size:10px;">'+(_bkPage+1)+'/'+pages+'</span>'
    : '';
  pg.innerHTML = info + nav;
}}
function bkPgPrev() {{ if(_bkPage>0){{ _bkPage--; applyBkFilter(); }} }}
function bkPgNext() {{
  var pp = parseInt(((document.getElementById('bkPerPage') || {{}}).value) || '25') || 25;
  if(_bkPage < Math.ceil(_bkFilteredCount/pp)-1){{ _bkPage++; applyBkFilter(); }}
}}

async function deleteFile(fname) {{
  if(!confirm('Eliminare ' + fname + '?')) return;
  await fetch('/api/backup/delete', {{method:'POST',
    headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{file:fname}})}});
  refreshFiles();
}}

async function refreshFiles() {{
  // Called manually (↺ button) or after a backup run to update the file list
  try {{
    var s = await fetch('/api/backup/status').then(function(r){{return r.json();}});
    renderFiles(s.files);
    var lrl = document.getElementById('lastRunLbl');
    if(lrl && s.last_run) lrl.textContent = s.last_run;
  }} catch(e) {{
    logErr('Errore aggiornamento archivio: ' + e);
  }}
}}

// On load: render initial archive, then check if backup is running
(function() {{
  renderFiles(BK_INIT_FILES);
  fetch('/api/backup/status').then(function(r){{return r.json();}}).then(function(s) {{
    if(s.running) {{
      var spinner = document.getElementById('bkSpinner');
      if(spinner) spinner.classList.add('active');
      var msg = document.getElementById('bkRunMsg');
      if(msg) msg.textContent = 'Backup in corso…';
      logInfo('Rilevato backup in corso — attendo il completamento…');
      var poll = setInterval(function() {{
        fetch('/api/backup/status').then(function(r){{return r.json();}}).then(function(s2) {{
          if(!s2.running) {{
            clearInterval(poll);
            if(spinner) spinner.classList.remove('active');
            if(msg) msg.textContent = '';
            renderFiles(s2.files);
            renderResults(s2.last_results);
          }}
        }});
      }}, 1500);
    }} else if(s.last_results && s.last_results.length) {{
      logInfo("Risultati dell'ultimo backup:");
      renderResults(s.last_results);
    }}
  }}).catch(function(){{}});
}})();

// Cattura errori JS e li mostra nel banner
window.onerror = function(msg, src, line, col, err) {{
  var b = document.getElementById('bkJsErrBanner');
  if(b) {{ b.style.display = 'block'; b.textContent = 'Errore JS: ' + msg + ' (riga ' + line + ')'; }}
  return false;
}};

// Inizializzazione al caricamento della pagina
applyBkCred('');
onTargetChange();
// Colora il label enabled in base allo stato iniziale
(function() {{
  var lbl = document.getElementById('bkEnabledLbl');
  var chk = document.getElementById('bkEnabled');
  if(lbl && chk && chk.checked) lbl.style.color = 'var(--green)';
}})();
</script>
""", session=session, page_key="backup")

    # ── Credentials Manager page ─────────────────────────────────────────
    def render_credentials_page(self, session):
        is_admin = _is_admin(session)

        cred_rows = ""
        for c in CRED_SETS:
            # Count usage in sites AND devices
            site_usage   = sum(1 for s in SITES.values() if s.get("credential_id") == c["id"])
            device_usage = sum(1 for d in DEVICES.values() if d.get("credential_id") == c["id"])
            total_usage  = site_usage + device_usage
            if total_usage:
                usage_txt = f'{site_usage} {T("sito/i")}, {device_usage} {T("device")}'
            else:
                usage_txt = f'<span style="color:var(--text3)">{T("Non assegnato")}</span>'
            # Show first 2 chars of username (decrypted server-side), rest hidden
            uname_full    = _cred_set_username(c)
            uname_preview = (uname_full[:2] + "••••") if len(uname_full) >= 2 else ("••••" if uname_full else "—")
            cred_rows += (
                f'<tr>'
                f'<td style="font-weight:600;color:var(--text);">{c["name"]}</td>'
                f'<td style="font-family:var(--mono);font-size:12px;color:var(--text2);">'
                f'{uname_preview}'
                f'<span style="color:var(--text3);margin-left:6px;letter-spacing:1px;font-size:10px;">/ ••••••••</span>'
                f'</td>'
                f'<td style="font-size:11px;">{usage_txt}</td>'
                f'<td style="white-space:nowrap;">'
                f'<button class="btn" onclick="openRevealModal(\'{c["id"]}\',\'{c["name"]}\')" '
                f'style="padding:2px 8px;font-size:10px;margin-right:4px;" title="{T("Rivela credenziali con recovery code")}">{T("Rivela")}</button>'
                f'<button class="btn" onclick="openCredModal(\'{c["id"]}\')" style="padding:2px 8px;font-size:10px;margin-right:4px;">{T("Modifica")}</button>'
                f'<button class="btn btn-danger" onclick="deleteCredSet(\'{c["id"]}\')" style="padding:2px 8px;font-size:10px;">{T("Elimina")}</button>'
                f'</td>'
                f'</tr>'
            )

        cred_sets_js = json.dumps([{"id": c["id"], "name": c["name"]} for c in CRED_SETS])

        # Build site-credential assignment rows (avoid nested triple-quoted f-strings for Python 3.9 compat)
        if not SITES:
            site_creds_rows = f'<tr><td colspan="3" style="padding:16px;color:var(--text3);font-style:italic;text-align:center;">{T("Nessun sito configurato. Crea siti in Site Manager prima.")}</td></tr>'
        else:
            site_creds_rows = ""
            for sid, s in sorted(SITES.items(), key=lambda x: x[1].get("name", "")):
                opts = '<option value="">— Credenziali del singolo router —</option>'
                for c in CRED_SETS:
                    sel = ' selected' if s.get("credential_id") == c["id"] else ''
                    opts += f'<option value="{c["id"]}"{sel}>{c["name"]}</option>'
                city_span = f' <span style="font-size:10px;color:var(--text3);font-weight:400;">({s.get("city","")})</span>' if s.get("city") else ""
                site_creds_rows += (
                    f'<tr style="border-bottom:1px solid var(--border);">'
                    f'<td style="padding:8px 12px;font-weight:600;color:var(--text);">{s.get("name",sid)}{city_span}</td>'
                    f'<td style="padding:8px 12px;"><select onchange="assignSiteCreds(\'{sid}\',this.value)" style="font-size:11px;width:100%;max-width:320px;">{opts}</select></td>'
                    f'<td style="padding:8px 12px;font-size:11px;color:var(--green);" id="scs_{sid}"></td>'
                    f'</tr>'
                )

        return self._page_shell("Credentials", f"""
<div class="card" style="max-width:860px;">
  <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
    <div>
      <div style="font-weight:700;color:var(--text);">Credential Manager</div>
      <div style="font-size:11px;color:var(--text2);margin-top:2px;">
        {T("Crea set nominati di credenziali riutilizzabili. Selezionali da Backup Manager, Upload Script e Network Discovery.")}
      </div>
    </div>
    <button class="btn btn-primary" onclick="openCredModal()">+ Nuove credenziali</button>
  </div>
  <div class="card-body" style="padding:0;">
    <table style="width:100%;border-collapse:collapse;">
      <thead>
        <tr style="background:var(--bg3);">
          <th style="padding:9px 14px;text-align:left;font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:.7px;font-weight:700;border-bottom:1px solid var(--border);">{T("Nome")}</th>
          <th style="padding:9px 14px;text-align:left;font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:.7px;font-weight:700;border-bottom:1px solid var(--border);">{T("Credenziali")}</th>
          <th style="padding:9px 14px;text-align:left;font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:.7px;font-weight:700;border-bottom:1px solid var(--border);">{T("Utilizzo")}</th>
          <th style="padding:9px 14px;border-bottom:1px solid var(--border);width:160px;"></th>
        </tr>
      </thead>
      <tbody id="credTable">
        {f'<tr><td colspan="5" style="padding:20px;color:var(--text3);font-style:italic;text-align:center;">{T("Nessun set credenziali. Premi &quot;+ Nuove credenziali&quot; per iniziare.")}</td></tr>' if not CRED_SETS else cred_rows}
      </tbody>
    </table>
  </div>
</div>

<div class="card" style="max-width:860px;margin-top:16px;">
  <div class="card-header">{T("Assegnazione ai Siti")}</div>
  <div class="card-body">
    <p style="font-size:11px;color:var(--text2);margin-bottom:14px;line-height:1.6;">
      {T("Associa un set di credenziali a ciascun sito. Il Backup Manager le usera automaticamente per tutti i router di quel sito.")}
    </p>
    <table style="width:100%;border-collapse:collapse;font-size:12px;">
      <thead>
        <tr style="background:var(--bg3);">
          <th style="padding:8px 12px;text-align:left;font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:.7px;font-weight:700;">{T("Sito")}</th>
          <th style="padding:8px 12px;text-align:left;font-size:10px;color:var(--text2);text-transform:uppercase;letter-spacing:.7px;font-weight:700;">{T("Credenziali assegnate")}</th>
          <th style="width:80px;"></th>
        </tr>
      </thead>
      <tbody id="siteCredsTable">
        {site_creds_rows}
      </tbody>
    </table>
  </div>
</div>

<script>
var CRED_SETS_DATA = {cred_sets_js};

async function assignSiteCreds(siteId, credId) {{
  var r = await fetch('/api/sites/set_creds', {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{site_id: siteId, credential_id: credId}})
  }});
  var j = await r.json();
  var el = document.getElementById('scs_'+siteId);
  if(j.ok) {{
    if(el) {{ el.textContent='Salvato'; setTimeout(function(){{el.textContent='';}},1800); }}
  }} else if(el) el.textContent = 'Errore';
}}

function openCredModal(cid) {{
  document.getElementById('credModalId').value = cid||'';
  var isEdit = !!cid;
  document.getElementById('credModalTitle').textContent = isEdit ? '{T("Modifica credenziali")}' : '{T("Nuove credenziali")}';
  document.getElementById('credModalPassRow').style.display = '';
  document.getElementById('credModalPassHint').style.display = isEdit ? 'inline' : 'none';
  if(isEdit) {{
    var c = CRED_SETS_DATA.find(function(x){{return x.id===cid;}});
    document.getElementById('credModalName').value = c ? c.name : '';
    document.getElementById('credModalUser').value = '';   // username not sent to client for security
    document.getElementById('credModalPass').value = '';
  }} else {{
    document.getElementById('credModalName').value = '';
    document.getElementById('credModalUser').value = '';
    document.getElementById('credModalPass').value = '';
  }}
  document.getElementById('credModal').classList.add('modal-show');
  setTimeout(function(){{document.getElementById('credModalName').focus();}},80);
}}
function closeCredModal() {{ document.getElementById('credModal').classList.remove('modal-show'); }}

async function saveCredModal() {{
  var cid      = document.getElementById('credModalId').value;
  var name     = document.getElementById('credModalName').value.trim();
  var username = document.getElementById('credModalUser').value.trim();
  var password = document.getElementById('credModalPass').value;
  if(!name)     {{ alert('{T("Inserisci un nome per questo set di credenziali.")}'); return; }}
  if(!username) {{ alert('{T("Inserisci lo username SSH.")}'); return; }}
  if(!cid && !password) {{ alert('{T("Inserisci la password SSH.")}'); return; }}
  var body = {{name:name, username:username}};
  if(password) body.password = password;
  if(cid) body.id = cid;
  var url = cid ? '/api/creds/update' : '/api/creds/add';
  var r = await fetch(url, {{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
  var j = await r.json();
  if(j.ok) {{
    closeCredModal();
    window.location.reload();
  }} else alert('{T("Errore: ")}' + (j.msg || 'unknown'));
}}

async function deleteCredSet(cid) {{
  if(!confirm('{T("Eliminare questo set? Verra rimosso da tutti i siti a cui e assegnato.")}')) return;
  var r = await fetch('/api/creds/remove',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id:cid}})}});
  var j = await r.json();
  if(j.ok) window.location.reload();
  else alert('Errore durante la cancellazione.');
}}

function openRevealModal(cid, name) {{
  document.getElementById('revealCredId').value = cid;
  document.getElementById('revealModalSub').textContent = name;
  document.getElementById('revealCode').value = '';
  document.getElementById('revealErr').style.display = 'none';
  document.getElementById('revealInputArea').style.display = '';
  document.getElementById('revealResultArea').style.display = 'none';
  document.getElementById('revealModal').classList.add('modal-show');
  setTimeout(function(){{document.getElementById('revealCode').focus();}}, 80);
}}
function closeRevealModal() {{
  document.getElementById('revealModal').classList.remove('modal-show');
  document.getElementById('revealUser').textContent = '';
  document.getElementById('revealPass').textContent = '';
}}
async function doReveal() {{
  var cid  = document.getElementById('revealCredId').value;
  var code = document.getElementById('revealCode').value;
  var r = await fetch('/api/creds/reveal', {{
    method:'POST', headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify({{id: cid, recovery_code: code}})
  }});
  var j = await r.json();
  var errEl = document.getElementById('revealErr');
  if(j.ok) {{
    errEl.style.display = 'none';
    document.getElementById('revealUser').textContent = j.username;
    document.getElementById('revealPass').textContent = j.password;
    document.getElementById('revealInputArea').style.display = 'none';
    document.getElementById('revealResultArea').style.display = '';
  }} else {{
    errEl.textContent = j.msg || 'Errore';
    errEl.style.display = '';
    document.getElementById('revealCode').select();
  }}
}}
</script>
""", session=session, page_key="credentials", body_modals=f"""
<div id="credModal" class="modal-overlay">
  <div style="background:var(--bg2);border:1px solid var(--border2);border-radius:14px;
       padding:28px;width:420px;max-width:96vw;box-shadow:0 8px 40px rgba(0,0,0,.2);">
    <div style="font-family:var(--sans);font-size:15px;font-weight:700;color:var(--text);
         margin-bottom:20px;" id="credModalTitle">{T("Nuove credenziali")}</div>
    <input type="hidden" id="credModalId">
    <div style="margin-bottom:12px;">
      <label style="font-size:10px;font-weight:700;color:var(--text2);display:block;
             margin-bottom:5px;text-transform:uppercase;letter-spacing:.6px;">{T("Nome *")}</label>
      <input type="text" id="credModalName" placeholder="{'es. Admin default, SSH rete A...' if LANGUAGE=='it' else 'e.g. Default Admin, Network A SSH...'}"
             style="width:100%;box-sizing:border-box;">
    </div>
    <div style="margin-bottom:12px;">
      <label style="font-size:10px;font-weight:700;color:var(--text2);display:block;
             margin-bottom:5px;text-transform:uppercase;letter-spacing:.6px;">{T("Username SSH *")}</label>
      <input type="text" id="credModalUser" placeholder="Username"
             style="width:100%;box-sizing:border-box;" autocomplete="off">
    </div>
    <div id="credModalPassRow" style="margin-bottom:20px;">
      <label style="font-size:10px;font-weight:700;color:var(--text2);display:block;
             margin-bottom:5px;text-transform:uppercase;letter-spacing:.6px;">
        {T("Password SSH")} *
        <span id="credModalPassHint" style="font-weight:400;text-transform:none;
              color:var(--text3);letter-spacing:0;">{T("(vuoto = non cambiare)")}</span>
      </label>
      <input type="password" id="credModalPass" placeholder="{T('Password SSH')}"
             style="width:100%;box-sizing:border-box;" autocomplete="new-password">
    </div>
    <div style="display:flex;gap:8px;justify-content:flex-end;">
      <button onclick="closeCredModal()" class="btn">{T("Annulla")}</button>
      <button onclick="saveCredModal()" class="btn btn-primary">{T("Salva")}</button>
    </div>
  </div>
</div>

<!-- Reveal modal -->
<div id="revealModal" class="modal-overlay">
  <div style="background:var(--bg2);border:1px solid var(--border2);border-radius:14px;
       padding:28px;width:420px;max-width:96vw;box-shadow:0 8px 40px rgba(0,0,0,.2);">
    <div style="font-size:15px;font-weight:700;color:var(--text);margin-bottom:4px;">
      {T("Rivela credenziali")}
    </div>
    <div id="revealModalSub" style="font-size:11px;color:var(--text2);margin-bottom:18px;"></div>
    <input type="hidden" id="revealCredId">
    <div id="revealInputArea">
      <div style="margin-bottom:12px;">
        <label style="font-size:10px;font-weight:700;color:var(--text2);display:block;
               margin-bottom:5px;text-transform:uppercase;letter-spacing:.6px;">{T("Codice di recupero")}</label>
        <input type="password" id="revealCode" placeholder="{T('Inserisci il recovery code')}"
               style="width:100%;box-sizing:border-box;" autocomplete="off"
               onkeydown="if(event.key==='Enter')doReveal()">
      </div>
      <div id="revealErr" style="font-size:11px;color:var(--red);margin-bottom:10px;display:none;"></div>
      <div style="display:flex;gap:8px;justify-content:flex-end;">
        <button onclick="closeRevealModal()" class="btn">{T("Annulla")}</button>
        <button onclick="doReveal()" class="btn btn-primary">{T("Sblocca")}</button>
      </div>
    </div>
    <div id="revealResultArea" style="display:none;">
      <div style="margin-bottom:10px;">
        <div style="font-size:10px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.6px;margin-bottom:4px;">Username</div>
        <div style="display:flex;gap:6px;align-items:center;">
          <code id="revealUser" style="flex:1;background:var(--bg3);border:1px solid var(--border2);
                border-radius:6px;padding:7px 10px;font-size:13px;color:var(--text);font-family:var(--mono);"></code>
          <button class="btn" style="padding:3px 8px;font-size:10px;"
                  onclick="navigator.clipboard.writeText(document.getElementById('revealUser').textContent)">⎘</button>
        </div>
      </div>
      <div style="margin-bottom:20px;">
        <div style="font-size:10px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.6px;margin-bottom:4px;">{T("Password")}</div>
        <div style="display:flex;gap:6px;align-items:center;">
          <code id="revealPass" style="flex:1;background:var(--bg3);border:1px solid var(--border2);
                border-radius:6px;padding:7px 10px;font-size:13px;color:var(--text);font-family:var(--mono);"></code>
          <button class="btn" style="padding:3px 8px;font-size:10px;"
                  onclick="navigator.clipboard.writeText(document.getElementById('revealPass').textContent)">⎘</button>
        </div>
      </div>
      <div style="font-size:10px;color:var(--text3);margin-bottom:14px;">
        ! {T("Chiudi questa finestra appena hai copiato le credenziali.")}
      </div>
      <div style="display:flex;justify-content:flex-end;">
        <button onclick="closeRevealModal()" class="btn btn-primary">{T("Chiudi")}</button>
      </div>
    </div>
  </div>
</div>
""")

    def _home_icon_credentials(self):
        return """<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
  <rect x="4" y="14" width="28" height="18" rx="3" fill="rgba(255,255,255,.3)"/>
  <circle cx="18" cy="23" r="3" fill="white"/>
  <path d="M18 23 L18 27" stroke="white" stroke-width="2" stroke-linecap="round"/>
  <path d="M11 14 L11 10 Q11 5 18 5 Q25 5 25 10 L25 14" stroke="white" stroke-width="2.2"
        stroke-linecap="round" fill="none"/>
</svg>"""

    def _home_icon_backup(self):
        return """<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M4 10 Q4 8 6 8 L14 8 L16 10 L30 10 Q32 10 32 12 L32 28 Q32 30 30 30 L6 30 Q4 30 4 28 Z"
        fill="rgba(255,255,255,.3)"/>
  <line x1="18" y1="15" x2="18" y2="24" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M13 20 L18 25 L23 20" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
  <line x1="12" y1="26" x2="24" y2="26" stroke="rgba(255,255,255,.7)" stroke-width="2" stroke-linecap="round"/>
</svg>"""

    def _home_icon_settings(self):
        return """<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- slider track 1 -->
  <line x1="5" y1="11" x2="31" y2="11" stroke="rgba(255,255,255,.45)" stroke-width="2" stroke-linecap="round"/>
  <!-- slider knob 1 -->
  <circle cx="13" cy="11" r="4" fill="white"/>
  <!-- slider track 2 -->
  <line x1="5" y1="18" x2="31" y2="18" stroke="rgba(255,255,255,.45)" stroke-width="2" stroke-linecap="round"/>
  <!-- slider knob 2 -->
  <circle cx="23" cy="18" r="4" fill="white"/>
  <!-- slider track 3 -->
  <line x1="5" y1="25" x2="31" y2="25" stroke="rgba(255,255,255,.45)" stroke-width="2" stroke-linecap="round"/>
  <!-- slider knob 3 -->
  <circle cx="15" cy="25" r="4" fill="white"/>
</svg>"""

    def _home_icon_report(self):
        return """<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- document body -->
  <rect x="7" y="4" width="22" height="28" rx="3" fill="rgba(255,255,255,.15)" stroke="white" stroke-width="2"/>
  <!-- lines (log entries) -->
  <line x1="12" y1="12" x2="24" y2="12" stroke="white" stroke-width="2" stroke-linecap="round"/>
  <line x1="12" y1="17" x2="22" y2="17" stroke="rgba(255,255,255,.7)" stroke-width="2" stroke-linecap="round"/>
  <line x1="12" y1="22" x2="24" y2="22" stroke="rgba(255,255,255,.7)" stroke-width="2" stroke-linecap="round"/>
  <!-- status dot (event indicator) -->
  <circle cx="12" cy="27" r="2" fill="#f7c44f"/>
  <line x1="16" y1="27" x2="24" y2="27" stroke="rgba(255,255,255,.5)" stroke-width="2" stroke-linecap="round"/>
</svg>"""

    def _home_icon_guide(self):
        return """<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- open book -->
  <path d="M18 8 C14 6 8 6 6 8 L6 28 C8 26 14 26 18 28 C22 26 28 26 30 28 L30 8 C28 6 22 6 18 8 Z"
        fill="rgba(255,255,255,.15)" stroke="white" stroke-width="2" stroke-linejoin="round"/>
  <!-- spine -->
  <line x1="18" y1="8" x2="18" y2="28" stroke="white" stroke-width="1.5" stroke-linecap="round"/>
  <!-- left lines -->
  <line x1="10" y1="14" x2="16" y2="13" stroke="rgba(255,255,255,.7)" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="10" y1="18" x2="16" y2="17" stroke="rgba(255,255,255,.5)" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="10" y1="22" x2="16" y2="21" stroke="rgba(255,255,255,.4)" stroke-width="1.5" stroke-linecap="round"/>
  <!-- right lines -->
  <line x1="20" y1="13" x2="26" y2="14" stroke="rgba(255,255,255,.7)" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="20" y1="17" x2="26" y2="18" stroke="rgba(255,255,255,.5)" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="20" y1="21" x2="26" y2="22" stroke="rgba(255,255,255,.4)" stroke-width="1.5" stroke-linecap="round"/>
</svg>"""

    def _home_icon_topology(self):
        return """<svg viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- root node -->
  <circle cx="18" cy="7" r="4" fill="white"/>
  <!-- left branch node -->
  <circle cx="9" cy="21" r="3.5" fill="rgba(255,255,255,.85)"/>
  <!-- right branch node -->
  <circle cx="27" cy="21" r="3.5" fill="rgba(255,255,255,.85)"/>
  <!-- left child -->
  <circle cx="6" cy="31" r="2.5" fill="rgba(255,255,255,.55)"/>
  <!-- right child -->
  <circle cx="30" cy="31" r="2.5" fill="rgba(255,255,255,.55)"/>
  <!-- center child -->
  <circle cx="18" cy="31" r="2.5" fill="rgba(255,255,255,.55)"/>
  <!-- edges -->
  <line x1="18" y1="11" x2="9"  y2="18" stroke="rgba(255,255,255,.6)" stroke-width="1.5"/>
  <line x1="18" y1="11" x2="27" y2="18" stroke="rgba(255,255,255,.6)" stroke-width="1.5"/>
  <line x1="9"  y1="24.5" x2="6"  y2="28.5" stroke="rgba(255,255,255,.4)" stroke-width="1.2"/>
  <line x1="9"  y1="24.5" x2="18" y2="28.5" stroke="rgba(255,255,255,.4)" stroke-width="1.2"/>
  <line x1="27" y1="24.5" x2="30" y2="28.5" stroke="rgba(255,255,255,.4)" stroke-width="1.2"/>
</svg>"""

    # ── Site Manager page ─────────────────────────────────────────────────
    def render_topology_page(self, session):
        is_admin = (session or {}).get("role") == "admin"
        sites_json   = json.dumps(dict(SITES))
        routers_json = json.dumps([
            {k: v for k, v in r.items() if k not in ("password",)}
            for r in ROUTERS
        ])
        role_labels_js = json.dumps({
            "gateway":   T("Gateway"),
            "router":    T("Router"),
            "core":      T("Core"),
            "switch":    T("Switch"),
            "sectorial": T("Settoriale"),
            "ap":        T("Access Point"),
            "client":    T("Cliente/CPE"),
            "cpe":       "CPE",
            "other":     T("Altro"),
            "custom":    T("Personalizzato"),
            "": "—"})
        cred_sets_js = json.dumps([
            {"id": c["id"], "name": c["name"]}
            for c in CRED_SETS])
        groups_js = json.dumps(sorted({r.get("group","") for r in ROUTERS if r.get("group","")}))
        scan_sites_js = json.dumps({
            sid: {
                "id":               sid,
                "name":             s.get("name", sid),
                "city":             s.get("city", ""),
                "scan_subnet":      s.get("scan_subnet", ""),
                "scan_interval":    s.get("scan_interval", 0),
                "scan_auto_add":    s.get("scan_auto_add", False),
                "scan_status":      s.get("scan_status", "idle"),
                "scan_last_run":    s.get("scan_last_run", ""),
                "scan_next_run":    s.get("scan_next_run", ""),
                "scan_last_found":  s.get("scan_last_found", 0),
                "scan_last_added":  s.get("scan_last_added", 0),
                "scan_last_error":  s.get("scan_last_error", ""),
                "scan_job_id":      s.get("scan_job_id", ""),
            }
            for sid, s in sorted(SITES.items(), key=lambda x: x[1].get("name", ""))
        })

        return self._page_shell("Site Manager", f"""
<style>
.sm-tab{{display:inline-block;padding:9px 18px;cursor:pointer;font-size:12px;font-weight:600;color:var(--text2);border-bottom:2px solid transparent;transition:all .15s;user-select:none;}}
.sm-tab:hover{{color:var(--text);}}
.sm-tab.active{{border-color:var(--accent);color:var(--accent);}}
.sm-toolbar{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:20px;}}
.sm-site-block{{background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:14px;}}
.sm-site-hdr{{display:flex;align-items:center;gap:10px;padding:14px 16px;background:linear-gradient(135deg,var(--accent) 0%,var(--accent2) 100%);cursor:pointer;user-select:none;}}
.sm-site-name{{font-weight:700;font-size:14px;color:#fff;}}
.sm-site-city{{font-size:11px;color:rgba(255,255,255,.75);margin-left:2px;}}
.sm-site-cred{{font-size:10px;color:rgba(255,255,255,.85);background:rgba(255,255,255,.15);border-radius:10px;padding:2px 8px;margin-left:4px;white-space:nowrap;}}
.sm-stats{{display:flex;gap:14px;margin-left:auto;flex-shrink:0;}}
.sm-stat{{text-align:center;}}
.sm-stat-n{{font-size:15px;font-weight:800;color:#fff;}}
.sm-stat-n.on{{color:#86efac;}} .sm-stat-n.off{{color:#fca5a5;}}
.sm-stat-l{{font-size:9px;color:rgba(255,255,255,.6);text-transform:uppercase;letter-spacing:.5px;}}
.sm-site-acts{{display:flex;gap:4px;margin-left:8px;flex-shrink:0;}}
.sm-btn-ic{{background:rgba(255,255,255,.18);border:none;color:#fff;border-radius:5px;cursor:pointer;padding:3px 9px;font-size:12px;}}
.sm-btn-ic:hover{{background:rgba(255,255,255,.35);}}
.sm-dev-table{{width:100%;border-collapse:collapse;font-size:12px;}}
.sm-dev-table th{{padding:7px 14px;font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:var(--text3);font-weight:700;background:var(--bg3);border-bottom:1px solid var(--border);text-align:left;}}
.sm-dev-table td{{padding:8px 14px;border-bottom:1px solid var(--border);vertical-align:middle;}}
.sm-dev-table tr:last-child td{{border-bottom:none;}}
.sm-dev-table tr:hover td{{background:var(--bg3);}}
.sm-dot{{width:8px;height:8px;border-radius:50%;display:inline-block;}}
.sm-dot.on{{background:var(--green);box-shadow:0 0 4px var(--green);}}
.sm-dot.off{{background:var(--red);}} .sm-dot.uk{{background:var(--text3);}}
.role-badge{{font-size:9px;font-weight:700;padding:2px 8px;border-radius:10px;text-transform:uppercase;letter-spacing:.4px;white-space:nowrap;}}
.rb-gw{{background:rgba(27,58,107,.1);color:var(--accent);border:1px solid rgba(27,58,107,.2);}}
.rb-ro{{background:rgba(38,80,160,.1);color:#2650a0;border:1px solid rgba(38,80,160,.2);}}
.rb-core{{background:rgba(190,18,60,.1);color:#be123c;border:1px solid rgba(190,18,60,.2);}}
.rb-sw{{background:rgba(15,118,110,.1);color:#0f766e;border:1px solid rgba(15,118,110,.2);}}
.rb-sec{{background:rgba(124,58,237,.1);color:var(--purple);border:1px solid rgba(124,58,237,.2);}}
.rb-cli{{background:rgba(22,163,74,.1);color:var(--green);border:1px solid rgba(22,163,74,.2);}}
.rb-ap{{background:rgba(217,119,6,.1);color:var(--yellow);border:1px solid rgba(217,119,6,.2);}}
.rb-oth{{background:var(--bg4);color:var(--text2);border:1px solid var(--border2);}}
.sm-unassigned{{background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:14px;}}
.sm-unassigned-hdr{{padding:12px 16px;background:var(--bg3);border-bottom:1px solid var(--border);font-size:11px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.6px;display:flex;align-items:center;justify-content:space-between;}}
.sm-unassigned-list{{display:flex;flex-wrap:wrap;gap:8px;padding:12px 16px;}}
.sm-chip{{background:var(--bg3);border:1px solid var(--border2);border-radius:6px;padding:5px 10px;font-size:11px;display:flex;align-items:center;gap:6px;cursor:pointer;transition:all .15s;}}
.sm-chip:hover{{border-color:var(--accent);background:var(--accent3);color:var(--accent);}}
.sm-empty{{padding:24px;text-align:center;color:var(--text3);font-size:12px;font-style:italic;}}
.topo-client-card{{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px;cursor:pointer;transition:all .15s;}}
.topo-client-card:hover{{border-color:var(--accent);box-shadow:0 4px 16px rgba(27,58,107,.12);transform:translateY(-2px);}}
#linkPanel{{position:absolute;z-index:30;background:var(--bg2);border:1px solid var(--border2);border-radius:12px;padding:14px 16px;box-shadow:0 6px 28px rgba(0,0,0,.2);min-width:220px;font-size:11px;}}
.lp-header{{font-weight:700;color:var(--text);margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;}}
.lp-endpoints{{font-family:var(--mono);font-size:10px;color:var(--text2);margin-bottom:10px;}}
.lp-type-btn{{display:flex;align-items:center;gap:7px;width:100%;padding:5px 8px;border-radius:6px;border:1px solid var(--border);background:none;cursor:pointer;font-size:11px;color:var(--text);margin-bottom:4px;transition:background .12s;text-align:left;}}
.lp-type-btn:hover{{background:var(--bg3);}}
.lp-type-btn.active{{border-color:var(--accent);background:var(--accent3);color:var(--accent);font-weight:700;}}
.lp-swatch{{width:28px;height:3px;border-radius:2px;flex-shrink:0;}}
.topo-client-name{{font-size:14px;font-weight:700;color:var(--text);margin-bottom:4px;}}
.topo-client-city{{font-size:11px;color:var(--text3);margin-bottom:10px;}}
.topo-client-stats{{display:flex;gap:12px;}}
.topo-client-stat{{text-align:center;}}
.topo-cs-n{{font-size:18px;font-weight:800;}}
.topo-cs-l{{font-size:9px;color:var(--text3);text-transform:uppercase;letter-spacing:.5px;}}
.lbl-col{{width:18px;height:18px;border-radius:50%;cursor:pointer;border:2px solid transparent;transition:border-color .1s;}}
.lbl-col:hover,.lbl-col.active{{border-color:var(--accent);}}
.lbl-sz.active{{background:var(--accent);color:#fff;border-color:var(--accent);}}
dialog{{border:none;border-radius:14px;padding:0;background:var(--bg2);box-shadow:0 8px 40px rgba(0,0,0,.3);max-width:96vw;max-height:92vh;overflow:auto;color:var(--text);}}
dialog::backdrop{{background:rgba(0,0,0,.55);}}
.dlg-body{{padding:28px;}}
.dlg-title{{font-size:15px;font-weight:700;color:var(--text);margin-bottom:20px;}}
.dlg-field{{margin-bottom:14px;}}
.dlg-field label{{display:block;font-size:10px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.6px;margin-bottom:5px;}}
.dlg-field input,.dlg-field select{{width:100%;box-sizing:border-box;font-size:13px;}}
.dlg-actions{{display:flex;gap:8px;justify-content:flex-end;margin-top:8px;}}
.dlg-msg{{font-size:11px;min-height:14px;margin-bottom:8px;color:var(--red);}}
.ss-header {{
  display:flex; align-items:center; justify-content:space-between;
  flex-wrap:wrap; gap:10px; margin-bottom:18px;
}}
.ss-title {{ font-size:14px; font-weight:700; color:var(--text); }}
.ss-subtitle {{ font-size:11px; color:var(--text3); margin-top:2px; }}
.ss-grid {{
  display:grid;
  grid-template-columns:repeat(auto-fill, minmax(340px, 1fr));
  gap:14px;
}}
.ss-card {{
  background:var(--bg2); border:1.5px solid var(--border);
  border-radius:var(--r3); padding:16px; display:flex; flex-direction:column; gap:12px;
  transition:box-shadow .15s;
}}
.ss-card:hover {{ box-shadow:var(--shadow); }}
.ss-card-head {{
  display:flex; align-items:center; justify-content:space-between; gap:8px;
}}
.ss-site-name {{ font-weight:700; font-size:13px; color:var(--text); }}
.ss-site-city {{ font-size:10px; color:var(--text3); margin-top:1px; }}
.ss-status-pill {{
  display:inline-flex; align-items:center; gap:5px;
  padding:3px 9px; border-radius:20px; font-size:10px; font-weight:700;
}}
.st-idle    {{ background:var(--bg3); color:var(--text3); border:1px solid var(--border2); }}
.st-running {{ background:rgba(217,119,6,.12); color:var(--yellow); border:1px solid rgba(217,119,6,.3); }}
.st-done    {{ background:rgba(22,163,74,.10); color:var(--green); border:1px solid rgba(22,163,74,.25); }}
.st-error   {{ background:rgba(220,38,38,.08); color:var(--red);   border:1px solid rgba(220,38,38,.22); }}
.ss-row {{
  display:grid; grid-template-columns:1fr 1fr; gap:8px;
}}
.ss-field {{ display:flex; flex-direction:column; gap:4px; }}
.ss-label {{
  font-size:10px; font-weight:700; color:var(--text3);
  text-transform:uppercase; letter-spacing:.7px;
}}
.ss-input {{
  padding:6px 9px; font-size:11px; width:100%;
  border:1px solid var(--border2); border-radius:var(--r);
  background:var(--bg3); color:var(--text); font-family:var(--mono);
  transition:border-color .15s;
}}
.ss-input:focus {{ outline:none; border-color:var(--accent2); }}
.ss-toggle-row {{
  display:flex; align-items:center; gap:8px;
}}
.ss-toggle-label {{ font-size:11px; color:var(--text2); }}
.ss-info-row {{
  display:flex; gap:14px; flex-wrap:wrap;
  font-size:10px; color:var(--text3); border-top:1px solid var(--border);
  padding-top:8px;
}}
.ss-info-item {{ display:flex; flex-direction:column; gap:2px; }}
.ss-info-val {{ color:var(--text2); font-weight:600; }}
.ss-actions {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
.ss-msg {{ font-size:11px; color:var(--text3); }}
.ss-results {{
  font-size:11px; font-family:var(--mono);
  background:var(--bg3); border-radius:var(--r); padding:8px 10px;
  color:var(--text2); border:1px solid var(--border);
  display:none;
}}
.ss-results.visible {{ display:block; }}
.ss-empty {{
  text-align:center; padding:48px 24px; color:var(--text3);
  font-size:12px;
}}
@keyframes ss-spin {{ to {{ transform:rotate(360deg); }} }}
.ss-spinner {{
  display:inline-block; width:10px; height:10px;
  border:2px solid rgba(217,119,6,.3); border-top-color:var(--yellow);
  border-radius:50%; animation:ss-spin .8s linear infinite;
}}
</style>

<div id="smErrBanner" style="display:none;background:#fee2e2;border:1px solid #fca5a5;border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:12px;color:#991b1b;"></div>

<!-- Tab bar + toolbar -->
<div style="display:flex;align-items:center;gap:0;border-bottom:1px solid var(--border);margin-bottom:16px;flex-wrap:wrap;">
  <div class="sm-tab active" id="tabLista" onclick="switchTab('lista')">&#9776; Lista sedi</div>
  <div class="sm-tab" id="tabMappa" onclick="switchTab('mappa')">&#9678; Mappa rete</div>
  <div class="sm-tab" id="tabScan" onclick="switchTab('scan')">&#9851; Site Auto-Scan</div>
  <div class="sm-toolbar" style="margin-left:auto;margin-bottom:0;border-bottom:none;padding-bottom:8px;">
    {'<button class="btn btn-primary" onclick="openSite()">+ Nuova Sede</button>' if is_admin else ''}
    {'<button class="btn" onclick="openBulk()">Assegnazione massiva</button>' if is_admin else ''}
    <span style="font-size:11px;color:var(--text2);">
      <strong id="smSiteCount">0</strong> sedi &nbsp;&middot;&nbsp;
      <strong id="smDevCount">0</strong> device assegnati &nbsp;&middot;&nbsp;
      <strong id="smUnCount">0</strong> non assegnati
    </span>
  </div>
</div>

<!-- VIEW: Lista -->
<div id="viewLista">
<div id="smSiteList"></div>
<div class="sm-unassigned">
  <div class="sm-unassigned-hdr">
    <span>Device non assegnati</span>
    <span id="smUnBadge" style="font-weight:400;color:var(--text3);font-size:10px;"></span>
  </div>
  <div id="smUnassignedList" class="sm-unassigned-list"></div>
</div>
</div>

<!-- VIEW: Mappa rete -->
<div id="viewMappa" style="display:none;">

  <!-- ── Client selector ────────────────────────────────────── -->
  <div id="topoClientSel">
    <div style="font-size:13px;font-weight:700;color:var(--text);margin-bottom:16px;">
      {'Seleziona un cliente per visualizzare la sua mappa di rete' if LANGUAGE=='it' else 'Select a client to view its network map'}
    </div>
    <div id="topoClientGrid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:14px;"></div>
  </div>

  <!-- ── Map view (shown after client selection) ─────────────── -->
  <div id="topoMapView" style="display:none;">
    <div id="topoToolbar" style="display:flex;gap:6px;align-items:center;margin-bottom:8px;flex-wrap:wrap;">
      <button onclick="backToClients()" class="btn" style="font-size:11px;">&#8592; {'Clienti' if LANGUAGE=='it' else 'Clients'}</button>
      <button onclick="topoAutoLayout(true)" class="btn" style="font-size:11px;">&#8635; {'Auto-layout' if LANGUAGE=='it' else 'Auto-layout'}</button>
      <button onclick="topoFitView()" class="btn" style="font-size:11px;">&#8982; {'Centra' if LANGUAGE=='it' else 'Center'}</button>
      <button onclick="topoZoom(1.25)" class="btn" style="padding:3px 9px;font-size:13px;font-weight:700;">+</button>
      <button onclick="topoZoom(0.8)" class="btn" style="padding:3px 9px;font-size:13px;font-weight:700;">-</button>
      <!-- Label style panel -->
      <div style="position:relative;display:inline-block;">
        <button class="btn" style="font-size:11px;" onclick="toggleLabelPanel(event)">Aa &#9660;</button>
        <div id="lblPanel" style="display:none;position:absolute;top:110%;left:0;z-index:50;
             background:var(--bg2);border:1px solid var(--border2);border-radius:10px;
             padding:14px;min-width:200px;box-shadow:0 6px 24px rgba(0,0,0,.18);">
          <div style="font-size:10px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.6px;margin-bottom:8px;">
            {'Stile etichette' if LANGUAGE=='it' else 'Label style'}
          </div>
          <div style="margin-bottom:8px;">
            <div style="font-size:10px;color:var(--text2);margin-bottom:4px;">{'Dimensione' if LANGUAGE=='it' else 'Size'}</div>
            <div style="display:flex;gap:4px;">
              <button class="btn lbl-sz" data-sz="7"  onclick="setLabelSize(7)"  style="font-size:9px;">S</button>
              <button class="btn lbl-sz" data-sz="9"  onclick="setLabelSize(9)"  style="font-size:11px;">M</button>
              <button class="btn lbl-sz" data-sz="11" onclick="setLabelSize(11)" style="font-size:13px;">L</button>
              <button class="btn lbl-sz" data-sz="14" onclick="setLabelSize(14)" style="font-size:15px;">XL</button>
            </div>
          </div>
          <div style="margin-bottom:8px;">
            <label style="display:flex;align-items:center;gap:6px;font-size:11px;cursor:pointer;">
              <input type="checkbox" id="lblBoldChk" onchange="setLabelBold(this.checked)">
              <span style="font-weight:700;">{'Grassetto' if LANGUAGE=='it' else 'Bold'}</span>
            </label>
          </div>
          <div>
            <div style="font-size:10px;color:var(--text2);margin-bottom:4px;">{'Colore' if LANGUAGE=='it' else 'Color'}</div>
            <div style="display:flex;gap:6px;flex-wrap:wrap;">
              <div class="lbl-col" data-col="" title="{'Default' if LANGUAGE=='it' else 'Default'}" style="background:var(--text2);" onclick="setLabelColor('')"></div>
              <div class="lbl-col" data-col="#1b3a6b" title="Navy" style="background:#1b3a6b;" onclick="setLabelColor('#1b3a6b')"></div>
              <div class="lbl-col" data-col="#111111" title="{'Nero' if LANGUAGE=='it' else 'Black'}" style="background:#111;" onclick="setLabelColor('#111111')"></div>
              <div class="lbl-col" data-col="#16a34a" title="{'Verde' if LANGUAGE=='it' else 'Green'}" style="background:#16a34a;" onclick="setLabelColor('#16a34a')"></div>
              <div class="lbl-col" data-col="#dc2626" title="{'Rosso' if LANGUAGE=='it' else 'Red'}" style="background:#dc2626;" onclick="setLabelColor('#dc2626')"></div>
              <div class="lbl-col" data-col="#7c3aed" title="{'Viola' if LANGUAGE=='it' else 'Purple'}" style="background:#7c3aed;" onclick="setLabelColor('#7c3aed')"></div>
              <div class="lbl-col" data-col="#d97706" title="{'Arancio' if LANGUAGE=='it' else 'Orange'}" style="background:#d97706;" onclick="setLabelColor('#d97706')"></div>
            </div>
          </div>
        </div>
      </div>
      <span style="font-size:10px;color:var(--text3);margin-left:2px;">
        <span style="color:var(--green);font-weight:700;">&#9679;</span> Online &nbsp;
        <span style="color:var(--red);font-weight:700;">&#9679;</span> Offline &nbsp;
        <span style="color:var(--text3);font-weight:700;">&#9679;</span> {'Sconosciuto' if LANGUAGE=='it' else 'Unknown'}
      </span>
      <span id="topoZoomLbl" style="font-size:10px;color:var(--text3);margin-left:4px;"></span>
      <span id="topoClientLbl" style="font-size:11px;font-weight:700;color:var(--accent);margin-left:4px;"></span>
    </div>
    <div id="topoWrap" style="position:relative;border:1px solid var(--border);border-radius:10px;overflow:hidden;background:var(--bg);height:calc(100vh - 250px);">
      <svg id="topoSvg" width="100%" height="100%" style="display:block;cursor:default;">
        <defs></defs>
        <g id="topoCanvas"></g>
      </svg>
      <!-- Link type editor panel -->
      <div id="linkPanel" style="display:none;top:40px;left:40px;">
        <div class="lp-header">
          <span>{'Tipo collegamento' if LANGUAGE=='it' else 'Link type'}</span>
          <button onclick="closeLinkPanel()" style="background:none;border:none;cursor:pointer;color:var(--text3);font-size:14px;padding:0 2px;">&#10005;</button>
        </div>
        <div class="lp-endpoints" id="lpEndpoints"></div>
        <div id="lpTypes"></div>
      </div>
      <!-- Info panel -->
      <div id="topoPanel" style="position:absolute;top:10px;right:10px;width:210px;background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:14px;font-size:11px;display:none;z-index:10;box-shadow:0 4px 20px rgba(0,0,0,.15);">
        <button onclick="document.getElementById('topoPanel').style.display='none'" style="position:absolute;top:8px;right:8px;background:none;border:none;cursor:pointer;color:var(--text3);font-size:14px;">&#10005;</button>
        <div id="topoPanelContent"></div>
      </div>
    </div>
  </div>
</div>

<!-- VIEW: Site Auto-Scan -->
<div id="viewScan" style="display:none;">
  <div class="ss-header">
    <div>
      <div class="ss-title">Site Auto-Scan</div>
      <div class="ss-subtitle">
        Assegna una subnet a ogni sede — ROSM la scansiona automaticamente e
        aggiunge i router MikroTik trovati.
      </div>
    </div>
  </div>

  <div id="ssGrid" class="ss-grid">
    <div class="ss-empty" id="ssEmpty" style="display:none;">
      Nessuna sede configurata.<br>
      <span style="font-size:10px;">Crea le sedi nel Site Manager prima di configurare la scansione.</span>
    </div>
  </div>
</div>

<!-- Dialog: Nuova / Modifica Sede -->
<dialog id="dlgSite">
  <div class="dlg-body" style="width:440px;">
    <div id="dlgSiteTitle" class="dlg-title">Nuova Sede</div>
    <input type="hidden" id="dlgSiteId">
    <div class="dlg-field"><label>Nome *</label>
      <input type="text" id="dlgSiteName" placeholder="es. Sede A, Ufficio Nord..." autocomplete="off"></div>
    <div class="dlg-field"><label>Citta / Luogo</label>
      <input type="text" id="dlgSiteCity" placeholder="es. Città, Regione..." autocomplete="off"></div>
    <div class="dlg-field"><label>Descrizione</label>
      <input type="text" id="dlgSiteDesc" placeholder="es. 10 router, link fibra..." autocomplete="off"></div>
    <div class="dlg-field">
      <label>Credenziali SSH &nbsp;<a href="/credentials" style="font-weight:400;text-transform:none;letter-spacing:0;font-size:10px;color:var(--accent);">Apri Credential Manager</a></label>
      <select id="dlgSiteCred">
        <option value="">-- Credenziali del singolo router --</option>
        {"".join(f'<option value="{c["id"]}">{c["name"]}</option>' for c in CRED_SETS)}
      </select></div>
    <div id="dlgSiteMsg" class="dlg-msg"></div>
    <div class="dlg-actions">
      <button class="btn" type="button" onclick="document.getElementById('dlgSite').close()">Annulla</button>
      <button class="btn btn-primary" type="button" onclick="saveSite()">Salva</button>
    </div>
  </div>
</dialog>

<!-- Dialog: Assegna Device -->
<dialog id="dlgAssign">
  <div class="dlg-body" style="width:420px;">
    <div class="dlg-title">Assegna Device</div>
    <div id="dlgAssignSub" style="font-size:12px;color:var(--text2);margin-bottom:18px;font-family:var(--mono);"></div>
    <div class="dlg-field"><label>Sede</label>
      <select id="dlgAssignSite" onchange="refreshParentOpts(this.value,'')"></select></div>
    <div class="dlg-field"><label>Ruolo</label>
      <select id="dlgAssignRole" onchange="document.getElementById('dlgAssignLabelWrap').style.display=this.value==='custom'?'block':'none'">
        <option value="">-- Nessun ruolo --</option>
        <optgroup label="Infrastruttura">
          <option value="core">Core</option>
          <option value="gateway">Gateway</option>
          <option value="router">Router</option>
          <option value="switch">Switch</option>
        </optgroup>
        <optgroup label="Wireless">
          <option value="sectorial">Settoriale</option>
          <option value="ap">Access Point</option>
        </optgroup>
        <optgroup label="Cliente / Altro">
          <option value="client">Cliente/CPE</option>
          <option value="cpe">CPE</option>
          <option value="other">Altro</option>
          <option value="custom">Personalizzato...</option>
        </optgroup>
      </select></div>
    <div id="dlgAssignLabelWrap" style="display:none;" class="dlg-field"><label>Etichetta</label>
      <input type="text" id="dlgAssignLabel" placeholder="es. Gateway, Core..."></div>
    <div class="dlg-field"><label>Device padre (upstream)</label>
      <select id="dlgAssignParent"></select></div>
    <div id="dlgAssignMsg" class="dlg-msg"></div>
    <div class="dlg-actions">
      <button class="btn" type="button" onclick="document.getElementById('dlgAssign').close()">Annulla</button>
      <button class="btn btn-primary" type="button" onclick="saveAssign()">Salva</button>
    </div>
  </div>
</dialog>

<!-- Dialog: Assegnazione Massiva -->
<dialog id="dlgBulk">
  <div class="dlg-body" style="width:660px;display:flex;flex-direction:column;max-height:82vh;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;flex-shrink:0;">
      <div><div class="dlg-title" style="margin-bottom:2px;">Assegnazione Massiva Device</div>
        <div style="font-size:11px;color:var(--text2);">Seleziona device, poi scegli sede e ruolo.</div></div>
      <button type="button" onclick="document.getElementById('dlgBulk').close()" style="background:none;border:none;color:var(--text2);font-size:20px;cursor:pointer;">&#x2715;</button>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:8px;flex-shrink:0;">
      <div><label style="font-size:10px;font-weight:600;color:var(--text2);display:block;margin-bottom:3px;text-transform:uppercase;">Cerca</label>
        <input id="bmSearch" type="text" placeholder="IP o nome" oninput="renderBulkList()" style="width:100%;box-sizing:border-box;font-size:11px;"></div>
      <div><label style="font-size:10px;font-weight:600;color:var(--text2);display:block;margin-bottom:3px;text-transform:uppercase;">Stato</label>
        <select id="bmStatus" onchange="renderBulkList()" style="width:100%;box-sizing:border-box;font-size:11px;">
          <option value="">Tutti</option><option value="ONLINE">ONLINE</option><option value="OFFLINE">OFFLINE</option></select></div>
      <div><label style="font-size:10px;font-weight:600;color:var(--text2);display:block;margin-bottom:3px;text-transform:uppercase;">Sede attuale</label>
        <select id="bmSite2" onchange="renderBulkList()" style="width:100%;box-sizing:border-box;font-size:11px;">
          <option value="">Tutte</option><option value="__none__">Non assegnati</option></select></div>
    </div>
    <div style="display:flex;gap:8px;align-items:center;margin-bottom:6px;flex-shrink:0;">
      <button class="btn" type="button" onclick="bmAll()" style="padding:3px 10px;font-size:10px;">Seleziona tutti</button>
      <button class="btn" type="button" onclick="bmNone()" style="padding:3px 10px;font-size:10px;">Deseleziona</button>
      <span id="bmCount" style="font-size:11px;font-weight:700;color:var(--accent);"></span>
    </div>
    <ul id="bmList" style="list-style:none;margin:0;padding:0;overflow-y:auto;flex:1;border:1px solid var(--border);border-radius:8px;min-height:120px;background:var(--bg3);"></ul>
    <div style="margin-top:14px;padding-top:14px;border-top:1px solid var(--border);flex-shrink:0;">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px;">
        <div><label style="font-size:10px;font-weight:700;color:var(--text2);display:block;margin-bottom:4px;text-transform:uppercase;">Sede destinazione *</label>
          <select id="bmDestSite" style="width:100%;box-sizing:border-box;font-size:12px;"></select></div>
        <div><label style="font-size:10px;font-weight:700;color:var(--text2);display:block;margin-bottom:4px;text-transform:uppercase;">Ruolo (opzionale)</label>
          <select id="bmRole" style="width:100%;box-sizing:border-box;font-size:12px;">
            <option value="">-- Nessuno --</option>
            <optgroup label="Infrastruttura"><option value="core">Core</option><option value="gateway">Gateway</option><option value="router">Router</option><option value="switch">Switch</option></optgroup>
            <optgroup label="Wireless"><option value="sectorial">Settoriale</option><option value="ap">Access Point</option></optgroup>
            <optgroup label="Cliente / Altro"><option value="client">Cliente/CPE</option><option value="cpe">CPE</option><option value="other">Altro</option></optgroup>
          </select></div>
      </div>
      <div id="bmMsg" class="dlg-msg"></div>
      <div class="dlg-actions">
        <button type="button" onclick="document.getElementById('dlgBulk').close()" class="btn">Annulla</button>
        <button type="button" onclick="saveBulk()" class="btn btn-primary">Assegna</button>
      </div>
    </div>
  </div>
</dialog>

<script>
var SD={sites_json},RD={routers_json},CS={cred_sets_js},RL={role_labels_js};
var IA={'true' if is_admin else 'false'},_exp={{}},_aip=null;

function esc(s){{return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}}
function dot(st){{return '<span class="sm-dot '+(st==='ONLINE'?'on':st==='OFFLINE'?'off':'uk')+'"></span>';}}
function badge(r){{
  var role=r.device_role||'',lbl=r.device_role_label||RL[role]||role;
  if(!lbl||lbl==='--')return '';
  var cmap={{'gateway':'rb-gw','router':'rb-ro','core':'rb-core','switch':'rb-sw',
             'sectorial':'rb-sec','client':'rb-cli','cpe':'rb-cli','ap':'rb-ap'}};
  var c=cmap[role]||'rb-oth';
  return '<span class="role-badge '+c+'">'+esc(lbl)+'</span>';
}}

function render(){{
  var sl=document.getElementById('smSiteList'),ul=document.getElementById('smUnassignedList');
  var sites=Object.values(SD),unass=RD.filter(function(r){{return !r.site_id;}});
  document.getElementById('smSiteCount').textContent=sites.length;
  document.getElementById('smDevCount').textContent=RD.filter(function(r){{return r.site_id;}}).length;
  document.getElementById('smUnCount').textContent=unass.length;
  document.getElementById('smUnBadge').textContent=unass.length+' device';
  ul.innerHTML='';
  if(!unass.length){{ul.innerHTML='<div class="sm-empty">Tutti i device sono assegnati.</div>';}}
  else{{unass.forEach(function(r){{
    var ch=document.createElement('div');ch.className='sm-chip';
    ch.innerHTML=dot(r.status)+' <span style="font-family:var(--mono);font-weight:700;color:var(--accent);">'+r.ip+'</span>'+(r.name?' <span style="color:var(--text2);">'+esc(r.name)+'</span>':'')+(IA?' <span style="font-size:10px;color:var(--accent);">Assegna</span>':'');
    if(IA)ch.addEventListener('click',function(){{openAssign(r.ip);}});
    ul.appendChild(ch);
  }});}}
  sl.innerHTML='';
  if(!sites.length){{
    sl.innerHTML='<div class="sm-empty" style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;margin-bottom:14px;">'+(IA?'Nessuna sede. Usa <strong>+ Nuova Sede</strong>.':'Nessuna sede.')+'</div>';
    return;
  }}
  sites.sort(function(a,b){{return (a.name||'').localeCompare(b.name||'');}});
  sites.forEach(function(s){{
    var devs=RD.filter(function(r){{return r.site_id===s.id;}}),on=devs.filter(function(r){{return r.status==='ONLINE';}}).length;
    var cr=CS.find(function(c){{return c.id===s.credential_id;}}),open=!!_exp[s.id];
    var blk=document.createElement('div');blk.className='sm-site-block';
    var hdr=document.createElement('div');hdr.className='sm-site-hdr';
    hdr.innerHTML='<span style="font-size:11px;color:rgba(255,255,255,.8);transition:transform .2s;'+(open?'transform:rotate(180deg)':'')+'">&#9660;</span>'+
      '<div style="flex:1;min-width:0;overflow:hidden;">'+
        '<span class="sm-site-name">'+esc(s.name)+'</span>'+(s.city?' <span class="sm-site-city">'+esc(s.city)+'</span>':'')+
        (cr?' <span class="sm-site-cred">'+esc(cr.name)+'</span>':'')+
      '</div>'+
      '<div class="sm-stats">'+
        '<div class="sm-stat"><div class="sm-stat-n">'+devs.length+'</div><div class="sm-stat-l">Dev</div></div>'+
        '<div class="sm-stat"><div class="sm-stat-n on">'+on+'</div><div class="sm-stat-l">On</div></div>'+
        '<div class="sm-stat"><div class="sm-stat-n off">'+(devs.length-on)+'</div><div class="sm-stat-l">Off</div></div>'+
      '</div>'+
      (IA?'<div class="sm-site-acts">'+
        '<button class="sm-btn-ic" data-a="edit" data-id="'+s.id+'">&#9998;</button>'+
        '<button class="sm-btn-ic" data-a="del" data-id="'+s.id+'">&#10005;</button>'+
      '</div>':'');
    hdr.addEventListener('click',function(e){{
      var b=e.target.closest('[data-a]');
      if(b){{e.stopPropagation();if(b.dataset.a==='edit')openSite(b.dataset.id);else delSite(b.dataset.id);return;}}
      _exp[s.id]=!_exp[s.id];render();
    }});
    blk.appendChild(hdr);
    var body=document.createElement('div');body.style.display=open?'':'none';
    if(!devs.length){{body.innerHTML='<div class="sm-empty">Nessun device assegnato.</div>';}}
    else{{
      var ro={{'core':0,'gateway':1,'router':1,'switch':2,'sectorial':3,'ap':4,'client':5,'cpe':5,'other':6,'':7}};
      devs.sort(function(a,b){{return (ro[a.device_role||'']||5)-(ro[b.device_role||'']||5)||(a.ip>b.ip?1:-1);}});
      var rows=devs.map(function(r){{
        return '<tr><td style="width:14px;">'+dot(r.status)+'</td>'+
          '<td><span style="font-family:var(--mono);font-weight:700;color:var(--accent);">'+r.ip+'</span></td>'+
          '<td style="font-weight:600;color:var(--text);">'+(r.name?esc(r.name):'<span style="color:var(--text3);">-</span>')+'</td>'+
          '<td style="font-size:11px;color:var(--text2);">'+(r.model?esc(r.model):'')+'</td>'+
          '<td>'+badge(r)+'</td>'+
          (IA?'<td><button class="btn" style="padding:2px 8px;font-size:10px;" onclick="openAssign(\\''+r.ip+'\\')" >Modifica</button></td>':'<td></td>')+
          '</tr>';
      }}).join('');
      body.innerHTML='<table class="sm-dev-table"><thead><tr><th></th><th>IP</th><th>Nome</th><th>Modello</th><th>Ruolo</th><th style="width:80px;"></th></tr></thead><tbody>'+rows+'</tbody></table>';
    }}
    blk.appendChild(body);sl.appendChild(blk);
  }});
}}

function openSite(id){{
  document.getElementById('dlgSiteId').value=id||'';
  document.getElementById('dlgSiteTitle').textContent=id?'Modifica Sede':'Nuova Sede';
  document.getElementById('dlgSiteMsg').textContent='';
  if(id&&SD[id]){{var s=SD[id];
    document.getElementById('dlgSiteName').value=s.name||'';
    document.getElementById('dlgSiteCity').value=s.city||'';
    document.getElementById('dlgSiteDesc').value=s.description||'';
    document.getElementById('dlgSiteCred').value=s.credential_id||'';
  }}else{{
    document.getElementById('dlgSiteName').value='';document.getElementById('dlgSiteCity').value='';
    document.getElementById('dlgSiteDesc').value='';document.getElementById('dlgSiteCred').value='';
  }}
  document.getElementById('dlgSite').showModal();
  setTimeout(function(){{document.getElementById('dlgSiteName').focus();}},80);
}}
async function saveSite(){{
  var id=document.getElementById('dlgSiteId').value,nm=document.getElementById('dlgSiteName').value.trim();
  var ci=document.getElementById('dlgSiteCity').value.trim(),de=document.getElementById('dlgSiteDesc').value.trim();
  var cr=document.getElementById('dlgSiteCred').value,msg=document.getElementById('dlgSiteMsg');
  if(!nm){{msg.textContent='Nome obbligatorio.';return;}}
  var url=id?'/api/sites/update':'/api/sites/add',body={{name:nm,city:ci,description:de}};
  if(id)body.id=id;
  try{{
    var r=await fetch(url,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
    var j=await r.json();if(!j.ok){{msg.textContent=j.msg||'Errore.';return;}}
    var sid=id||j.id;
    if(cr!==(id&&SD[id]?SD[id].credential_id||'':''))
      await fetch('/api/sites/set_creds',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{site_id:sid,credential_id:cr}})}});
    if(!id)SD[j.id]=Object.assign({{credential_id:cr}},j.site);
    else Object.assign(SD[id],{{name:nm,city:ci,description:de,credential_id:cr}});
    document.getElementById('dlgSite').close();render();
  }}catch(e){{msg.textContent='Errore di rete: '+e;}}
}}
async function delSite(id){{
  if(!confirm('Eliminare "'+((SD[id]&&SD[id].name)||id)+'"?'))return;
  try{{
    var r=await fetch('/api/sites/remove',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{id:id}})}});
    var j=await r.json();if(!j.ok){{alert('Errore');return;}}
    delete SD[id];RD.forEach(function(r){{if(r.site_id===id)r.site_id='';}});render();
  }}catch(e){{alert('Errore: '+e);}}
}}

function openAssign(ip){{
  _aip=ip;var r=RD.find(function(x){{return x.ip===ip;}})||{{}};
  document.getElementById('dlgAssignSub').textContent=ip+(r.name?' - '+r.name:'');
  document.getElementById('dlgAssignMsg').textContent='';
  var sel=document.getElementById('dlgAssignSite');
  sel.innerHTML='<option value="">-- Nessuna sede --</option>';
  Object.values(SD).sort(function(a,b){{return (a.name||'').localeCompare(b.name||'');}}).forEach(function(s){{
    var o=document.createElement('option');o.value=s.id;o.textContent=s.name+(s.city?' ('+s.city+')':'');
    if(r.site_id===s.id)o.selected=true;sel.appendChild(o);
  }});
  document.getElementById('dlgAssignRole').value=r.device_role||'';
  document.getElementById('dlgAssignLabelWrap').style.display=r.device_role==='custom'?'block':'none';
  document.getElementById('dlgAssignLabel').value=r.device_role_label||'';
  refreshParentOpts(sel.value,r.parent_ip||'');
  document.getElementById('dlgAssign').showModal();
}}
function refreshParentOpts(sid,cur){{
  var sel=document.getElementById('dlgAssignParent');
  sel.innerHTML='<option value="">-- Nessuno (radice) --</option>';
  if(!sid)return;
  RD.filter(function(r){{return r.site_id===sid&&r.ip!==_aip;}}).sort(function(a,b){{return a.ip>b.ip?1:-1;}}).forEach(function(r){{
    var o=document.createElement('option');o.value=r.ip;o.textContent=r.ip+(r.name?' ('+r.name+')':'');
    if(r.ip===cur)o.selected=true;sel.appendChild(o);
  }});
}}
async function saveAssign(){{
  var msg=document.getElementById('dlgAssignMsg');
  var _dev=RD.find(function(x){{return x.ip===_aip;}})||{{}};
  var body={{ip:_aip,site_id:document.getElementById('dlgAssignSite').value,device_role:document.getElementById('dlgAssignRole').value,device_role_label:document.getElementById('dlgAssignLabel').value.trim(),parent_ip:document.getElementById('dlgAssignParent').value,link_type:_dev.link_type||''}};
  try{{
    var r=await fetch('/api/device/topology',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
    var j=await r.json();if(!j.ok){{msg.textContent='Errore: '+(j.msg||'');return;}}
    var dev=RD.find(function(x){{return x.ip===_aip;}});
    if(dev){{dev.site_id=body.site_id;dev.device_role=body.device_role;dev.device_role_label=body.device_role_label;dev.parent_ip=body.parent_ip;}}
    document.getElementById('dlgAssign').close();render();
  }}catch(e){{msg.textContent='Errore: '+e;}}
}}

function openBulk(){{
  var ds=document.getElementById('bmDestSite'),s2=document.getElementById('bmSite2');
  ds.innerHTML='<option value="">-- Seleziona sede --</option>';
  s2.innerHTML='<option value="">Tutte</option><option value="__none__">Non assegnati</option>';
  Object.values(SD).sort(function(a,b){{return (a.name||'').localeCompare(b.name||'');}}).forEach(function(s){{
    var o1=document.createElement('option'),o2=document.createElement('option');
    o1.value=o2.value=s.id;o1.textContent=o2.textContent=s.name+(s.city?' ('+s.city+')':'');
    ds.appendChild(o1);s2.appendChild(o2);
  }});
  document.getElementById('bmMsg').textContent='';renderBulkList();
  document.getElementById('dlgBulk').showModal();
}}
function renderBulkList(){{
  var search=(document.getElementById('bmSearch').value||'').toLowerCase();
  var fst=document.getElementById('bmStatus').value,fs2=document.getElementById('bmSite2').value;
  var list=document.getElementById('bmList');
  var filtered=RD.filter(function(r){{
    if(search&&!(r.ip+' '+(r.name||'')).toLowerCase().includes(search))return false;
    if(fst&&r.status!==fst)return false;
    if(fs2==='__none__'&&r.site_id)return false;
    if(fs2&&fs2!=='__none__'&&r.site_id!==fs2)return false;
    return true;
  }});
  list.innerHTML='';
  filtered.forEach(function(r){{
    var li=document.createElement('li');li.style.cssText='display:flex;align-items:center;gap:8px;padding:6px 12px;border-bottom:1px solid var(--border);cursor:pointer;';
    var cb=document.createElement('input');cb.type='checkbox';cb.value=r.ip;cb.addEventListener('change',updBulkCount);
    var sn=r.site_id&&SD[r.site_id]?' <span style="font-size:10px;color:var(--text3);">['+esc(SD[r.site_id].name)+']</span>':'';
    var sp=document.createElement('span');sp.innerHTML=dot(r.status)+' <span style="font-family:var(--mono);font-weight:700;color:var(--accent);">'+r.ip+'</span>'+(r.name?' <span style="color:var(--text);">'+esc(r.name)+'</span>':'')+sn;
    li.appendChild(cb);li.appendChild(sp);li.addEventListener('click',function(e){{if(e.target!==cb){{cb.checked=!cb.checked;updBulkCount();}}}});
    list.appendChild(li);
  }});
  if(!filtered.length)list.innerHTML='<li style="padding:14px;color:var(--text3);font-style:italic;font-size:11px;">Nessun device.</li>';
  updBulkCount();
}}
function updBulkCount(){{document.getElementById('bmCount').textContent=document.querySelectorAll('#bmList input:checked').length+' selezionati';}}
function bmAll(){{document.querySelectorAll('#bmList input').forEach(function(c){{c.checked=true;}});updBulkCount();}}
function bmNone(){{document.querySelectorAll('#bmList input').forEach(function(c){{c.checked=false;}});updBulkCount();}}
async function saveBulk(){{
  var ips=Array.from(document.querySelectorAll('#bmList input:checked')).map(function(c){{return c.value;}});
  var sid=document.getElementById('bmDestSite').value,role=document.getElementById('bmRole').value,msg=document.getElementById('bmMsg');
  if(!ips.length){{msg.textContent='Seleziona almeno un device.';return;}}
  if(!sid){{msg.textContent='Seleziona una sede.';return;}}
  try{{
    var r=await fetch('/api/sites/assign_bulk',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{ips:ips,site_id:sid,device_role:role}})}});
    var j=await r.json();if(!j.ok){{msg.textContent='Errore: '+(j.msg||'');return;}}
    ips.forEach(function(ip){{var d=RD.find(function(x){{return x.ip===ip;}});if(d){{d.site_id=sid;d.device_role=role;}}}});
    document.getElementById('dlgBulk').close();render();
  }}catch(e){{msg.textContent='Errore: '+e;}}
}}

window.onerror=function(msg,src,line,col,err){{
  var b=document.getElementById('smErrBanner');
  if(b){{b.style.display='block';b.textContent='Errore JavaScript: '+msg+' (linea '+line+')';}}
  return false;
}};
render();

// ══ TAB SWITCHER ════════════════════════════════════════════
function switchTab(name) {{
  document.getElementById('tabLista').classList.toggle('active', name==='lista');
  document.getElementById('tabMappa').classList.toggle('active', name==='mappa');
  document.getElementById('tabScan').classList.toggle('active', name==='scan');
  document.getElementById('viewLista').style.display = name==='lista' ? '' : 'none';
  document.getElementById('viewMappa').style.display = name==='mappa' ? '' : 'none';
  document.getElementById('viewScan').style.display  = name==='scan'  ? '' : 'none';
  if(name==='mappa') {{ renderClientGrid(); }}
}}

// ══ SITE AUTO-SCAN (tab) ════════════════════════════════════
const SCAN_SITES_DATA = {scan_sites_js};
let scanSitesMap = {{}};

const SCAN_INTERVALS = [
  [0,   "Disabilitata"],
  [5,   "ogni 5 minuti"],
  [15,  "ogni 15 minuti"],
  [30,  "ogni 30 minuti"],
  [60,  "ogni ora"],
  [120, "ogni 2 ore"],
  [360, "ogni 6 ore"],
  [720, "ogni 12 ore"],
  [1440,"ogni 24 ore"],
];

function scanActivePill(interval, sid) {{
  const active = (interval || 0) > 0;
  const cls   = active ? 'st-done' : 'st-idle';
  const label = active ? '● Attiva' : '○ Inattiva';
  return `<span class="ss-status-pill ${{cls}}" style="cursor:pointer;" onclick="toggleScanActive('${{sid}}')" title="Clicca per attivare/disattivare la scansione automatica">${{label}}</span>`;
}}

function scanIntervalOpts(current) {{
  return SCAN_INTERVALS.map(([v, l]) =>
    `<option value="${{v}}" ${{v===current?'selected':''}}>${{l}}</option>`
  ).join('');
}}

function renderScanCard(s) {{
  const found   = s.scan_last_found  ?? 0;
  const added   = s.scan_last_added  ?? 0;
  const lastRun = s.scan_last_run  || '—';
  const nextRun = s.scan_next_run  || '—';
  const isRunning = s.scan_status === 'running';

  return `
  <div class="ss-card" id="card-${{s.id}}">
    <div class="ss-card-head">
      <div>
        <div class="ss-site-name">${{esc(s.name)}}</div>
        ${{s.city ? `<div class="ss-site-city">${{esc(s.city)}}</div>` : ''}}
      </div>
      ${{scanActivePill(s.scan_interval, s.id)}}
    </div>

    <div class="ss-row">
      <div class="ss-field">
        <span class="ss-label">Subnet CIDR</span>
        <input class="ss-input" id="subnet-${{s.id}}"
               value="${{esc(s.scan_subnet)}}"
               placeholder="es. 10.0.1.0/24">
      </div>
      <div class="ss-field">
        <span class="ss-label">Scansione automatica</span>
        <select class="ss-input" id="itvl-${{s.id}}">
          ${{scanIntervalOpts(s.scan_interval)}}
        </select>
      </div>
    </div>

    <div class="ss-toggle-row">
      <input type="checkbox" id="autoadd-${{s.id}}" ${{s.scan_auto_add ? 'checked' : ''}}>
      <label class="ss-toggle-label" for="autoadd-${{s.id}}">
        Auto-aggiungi i router MikroTik trovati a questa sede
      </label>
    </div>

    <div class="ss-info-row">
      <div class="ss-info-item">
        <span>Ultima scansione</span>
        <span class="ss-info-val" id="lastrun-${{s.id}}">${{lastRun}}</span>
      </div>
      <div class="ss-info-item">
        <span>Prossima</span>
        <span class="ss-info-val" id="nextrun-${{s.id}}">${{nextRun}}</span>
      </div>
      <div class="ss-info-item">
        <span>MikroTik trovati</span>
        <span class="ss-info-val" id="found-${{s.id}}">${{found}}</span>
      </div>
      <div class="ss-info-item">
        <span>Auto-aggiunti</span>
        <span class="ss-info-val" id="added-${{s.id}}">${{added}}</span>
      </div>
    </div>

    <div class="ss-actions">
      <button class="btn btn-primary" onclick="scanSaveConfig('${{s.id}}')">Salva</button>
      <button class="btn" id="scanbtn-${{s.id}}"
              onclick="scanNow('${{s.id}}')"
              ${{isRunning ? 'disabled' : ''}}>
        ${{isRunning ? '⏳ Scansione…' : '▶ Scan ora'}}
      </button>
      <span class="ss-msg" id="msg-${{s.id}}"></span>
    </div>

    <div class="ss-results" id="results-${{s.id}}"></div>
  </div>`;
}}

function renderScanAll() {{
  const grid  = document.getElementById('ssGrid');
  const empty = document.getElementById('ssEmpty');
  const ids   = Object.keys(SCAN_SITES_DATA);
  if (!ids.length) {{
    empty.style.display = 'block';
    return;
  }}
  ids.forEach(sid => {{
    scanSitesMap[sid] = SCAN_SITES_DATA[sid];
    const div = document.createElement('div');
    div.innerHTML = renderScanCard(SCAN_SITES_DATA[sid]);
    grid.appendChild(div.firstElementChild);
  }});
}}

function updateScanActivePill(sid, interval) {{
  const card = document.getElementById(`card-${{sid}}`);
  if (!card) return;
  const pill = card.querySelector('.ss-status-pill');
  if (!pill) return;
  const active = (interval || 0) > 0;
  pill.className   = `ss-status-pill ${{active ? 'st-done' : 'st-idle'}}`;
  pill.textContent = active ? '● Attiva' : '○ Inattiva';
}}

async function scanSaveConfig(sid, silent) {{
  const subnet   = document.getElementById(`subnet-${{sid}}`).value.trim();
  const interval = parseInt(document.getElementById(`itvl-${{sid}}`).value) || 0;
  const autoAdd  = document.getElementById(`autoadd-${{sid}}`).checked;
  const msg      = document.getElementById(`msg-${{sid}}`);
  if (!silent) {{
    msg.style.color = 'var(--text3)';
    msg.textContent = 'Salvataggio…';
  }}

  const fd = new FormData();
  fd.append('sid',      sid);
  fd.append('subnet',   subnet);
  fd.append('interval', interval);
  fd.append('auto_add', autoAdd ? '1' : '0');

  const r = await fetch('/api/site_scan/config', {{ method:'POST', body:fd }});
  const j = await r.json();
  if (j.ok) {{
    if (scanSitesMap[sid]) scanSitesMap[sid].scan_interval = interval;
    updateScanActivePill(sid, interval);
    document.getElementById(`nextrun-${{sid}}`).textContent = j.next_run || '—';
    if (!silent) {{
      msg.style.color = 'var(--green)';
      msg.textContent = '✓ Salvato';
      setTimeout(() => {{ msg.textContent = ''; }}, 2500);
    }}
  }} else {{
    msg.style.color = 'var(--red)';
    msg.textContent = j.msg;
  }}
  return j.ok;
}}

async function toggleScanActive(sid) {{
  const sel     = document.getElementById(`itvl-${{sid}}`);
  const current = parseInt(sel.value) || 0;
  const next    = current > 0 ? 0 : 60;   // off -> on (default: ogni ora), on -> off
  sel.value = String(next);
  await scanSaveConfig(sid, true);
  const msg = document.getElementById(`msg-${{sid}}`);
  msg.style.color = 'var(--text3)';
  msg.textContent = next > 0 ? 'Scansione automatica attivata' : 'Scansione automatica disattivata';
  setTimeout(() => {{ msg.textContent = ''; }}, 2500);
}}

async function scanNow(sid) {{
  const msg     = document.getElementById(`msg-${{sid}}`);
  const btn     = document.getElementById(`scanbtn-${{sid}}`);
  const results = document.getElementById(`results-${{sid}}`);
  msg.style.color = 'var(--text3)';
  msg.textContent = 'Avvio…';

  // Salva sempre la subnet/intervallo correnti prima di lanciare — evita scansioni
  // "a vuoto" se l'utente ha digitato la subnet senza premere Salva.
  const saved = await scanSaveConfig(sid, true);
  if (!saved) {{
    msg.style.color = 'var(--red)';
    msg.textContent = 'Impossibile salvare la configurazione prima della scansione';
    return;
  }}

  btn.disabled = true;
  btn.textContent = '⏳ Scansione…';

  const fd = new FormData();
  fd.append('sid', sid);
  const r = await fetch('/api/site_scan/now', {{ method:'POST', body:fd }});
  const j = await r.json();

  if (!j.ok) {{
    msg.style.color = 'var(--red)';
    msg.textContent = j.msg;
    results.classList.add('visible');
    results.innerHTML = `<span style="color:var(--red);">✗ ${{esc(j.msg)}}</span>`;
    btn.disabled = false;
    btn.textContent = '▶ Scan ora';
    return;
  }}
  msg.textContent = '';
  if (j.job_id) pollScan(sid, j.job_id);
}}

async function pollScan(sid, jobId) {{
  const results = document.getElementById(`results-${{sid}}`);
  results.classList.add('visible');
  results.textContent = 'Scansione in corso…';

  for (let i = 0; i < 200; i++) {{
    await new Promise(r => setTimeout(r, 2000));
    const r = await fetch(`/api/site_scan/status?sid=${{sid}}`);
    const j = await r.json();
    const s = j.site || {{}};

    if (s.scan_status === 'running') {{
      if (jobId) {{
        const jr = await fetch(`/api/scan_job?id=${{jobId}}`);
        const jj = await jr.json();
        const done  = jj.done  ?? 0;
        const total = jj.total ?? 0;
        const pct   = total ? Math.round(done/total*100) : 0;
        results.textContent = `Scansione: ${{done}}/${{total}} IP (${{pct}}%)`;
      }}
      continue;
    }}

    document.getElementById(`lastrun-${{sid}}`).textContent = s.scan_last_run || '—';
    document.getElementById(`nextrun-${{sid}}`).textContent = s.scan_next_run || '—';
    document.getElementById(`found-${{sid}}`).textContent   = s.scan_last_found ?? 0;
    document.getElementById(`added-${{sid}}`).textContent   = s.scan_last_added ?? 0;

    const btn = document.getElementById(`scanbtn-${{sid}}`);
    btn.disabled    = false;
    btn.textContent = '▶ Scan ora';

    if (s.scan_status === 'done') {{
      const f = s.scan_last_found ?? 0;
      const a = s.scan_last_added ?? 0;
      results.innerHTML = `<span style="color:var(--green);">✓ Scansione completata — `+
        `${{f}} MikroTik trovati` + (a ? `, ${{a}} aggiunti al sito` : '') + `.</span>`;
    }} else if (s.scan_status === 'error') {{
      results.innerHTML = `<span style="color:var(--red);">✗ ${{esc(s.scan_last_error)}}</span>`;
    }}
    break;
  }}
}}

renderScanAll();
Object.values(SCAN_SITES_DATA).forEach(s => {{
  if (s.scan_status === 'running' && s.scan_job_id) {{
    pollScan(s.id, s.scan_job_id);
  }}
}});

// ══ TOPOLOGY VIEW ═══════════════════════════════════════════
var _tpos = {{}};        // {{ip: {{x,y}}}} — node positions
var _tvw  = {{x:0,y:0,k:1}};  // pan/zoom transform
var _tsel = null;       // selected node IP
var _tpan  = null;      // pan state
var _topoReady = false;
var _topoSiteId = null; // currently shown client/site

// Label style (persisted in localStorage)
var _lblStyle = (function() {{
  try {{ return JSON.parse(localStorage.getItem('rosm_lbl_style')||'{{}}'); }}
  catch(e) {{ return {{}}; }}
}})();
function _lblSize()  {{ return _lblStyle.size  || 9; }}
function _lblBold()  {{ return _lblStyle.bold  || false; }}
function _lblColor() {{ return _lblStyle.color || 'var(--text2)'; }}

var SITE_PAL = ['#1b3a6b','#7c3aed','#0369a1','#166534','#b45309','#be123c','#0f766e','#92400e'];

// Link type styles (color, stroke-width, dash-array, display label)
var LINK_STYLES = {{
  '':      {{label:'{'Generico' if LANGUAGE=='it' else 'Generic'}',    color:'#8896ab', width:1.5, dash:''}},
  'radio': {{label:'Radio',                                             color:'#2650a0', width:2,   dash:'10,5'}},
  'fiber': {{label:'{'Fibra ottica' if LANGUAGE=='it' else 'Fiber'}',  color:'#f59e0b', width:3,   dash:''}},
  'gige':  {{label:'GigaEthernet',                                     color:'#16a34a', width:2,   dash:''}},
  'faste': {{label:'FastEthernet',                                     color:'#d97706', width:1.5, dash:'5,4'}},
  'ptp':   {{label:'Point-to-Point',                                   color:'#7c3aed', width:2,   dash:'12,4'}},
  'lag':   {{label:'Link Aggregation',                                  color:'#be123c', width:3.5, dash:''}},
}};

// Currently edited link
var _lpChild = null, _lpParent = null;

// SVG icon path data for each role (drawn at node center, ±8px, stroke-only)
var ROLE_ICONS = {{
  // Gateway: box with bidirectional horizontal arrows
  'gateway': [{{tag:'path', d:'M-5,-2.5h10v5h-10z M-9,0h4 M-7.5,-1.5l2.5,1.5-2.5,1.5 M5,0h4 M7.5,-1.5l-2.5,1.5 2.5,1.5'}}],
  // Router: gateway + uplink arrow on top
  'router':  [{{tag:'path', d:'M-5,-2.5h10v5h-10z M-8.5,0h3.5 M5,0h3.5 M0,-2.5v-4.5 M-1.8,-5.5l1.8,-2 1.8,2'}}],
  // Core: hub with 8 spokes radiating + center dot
  'core':    [{{tag:'path', d:'M0,-7.5v3.5 M5.3,-5.3l-2.5,2.5 M7.5,0h-3.5 M5.3,5.3l-2.5,-2.5 M0,7.5v-3.5 M-5.3,5.3l2.5,-2.5 M-7.5,0h3.5 M-5.3,-5.3l2.5,2.5'}}, {{tag:'circle', r:'2.2'}}],
  // Switch: flat box with 4 downward port lines
  'switch':  [{{tag:'path', d:'M-7,-3h14v6h-14z M-4.5,3v4 M-1,3v4 M2.5,3v4 M6,3v4 M-5.5,-0.5h1.5 M-5.5,1h1.5'}}],
  // Sectorial: triangle (sector antenna pointing up)
  'sectorial':[{{tag:'path', d:'M0,-8l7,13h-14z'}}],
  // Access Point: WiFi arcs + dot
  'ap':      [{{tag:'path', d:'M-3.5,2a5.5,5.5,0,0,1,7,0 M-6.5,-1.5a10,10,0,0,1,13,0'}}, {{tag:'circle', r:'1.6', cy:'5.5'}}],
  // Client/PC: monitor + stand
  'client':  [{{tag:'path', d:'M-5.5,-6h11v9h-11z M-3,3h6 M0,3v3 M-3.5,6h7'}}],
  // CPE: box with small antenna
  'cpe':     [{{tag:'path', d:'M-5,-4h10v8h-10z M0,-4v-4 M-2,-6.5l2,-2 2,2'}}],
  // Other: rounded square
  'other':   [{{tag:'path', d:'M-5,-5h10v10h-10z'}}],
  // Custom/empty: small dot
  'custom':  [{{tag:'circle', r:'2.5'}}],
  '':        [],
}};

// ── Client selector ─────────────────────────────────────────
function renderClientGrid() {{
  document.getElementById('topoClientSel').style.display = '';
  document.getElementById('topoMapView').style.display = 'none';
  var grid = document.getElementById('topoClientGrid');
  grid.innerHTML = '';
  var sites = Object.values(SD).sort(function(a,b){{return (a.name||'').localeCompare(b.name||'');}});
  if(!sites.length) {{
    grid.innerHTML = '<div style="color:var(--text3);font-style:italic;padding:24px;">{'Nessun cliente configurato. Crea siti in Site Manager.' if LANGUAGE=='it' else 'No clients configured. Create sites in Site Manager.'}</div>';
    return;
  }}
  sites.forEach(function(s, si) {{
    var devs = RD.filter(function(r){{return r.site_id===s.id;}});
    var on   = devs.filter(function(r){{return r.status==='ONLINE';}}).length;
    var off  = devs.length - on;
    var color = SITE_PAL[si % SITE_PAL.length];
    var card = document.createElement('div');
    card.className = 'topo-client-card';
    card.style.borderTopColor = color;
    card.style.borderTopWidth = '3px';
    card.innerHTML =
      '<div class="topo-client-name">'+esc(s.name)+'</div>'+
      (s.city ? '<div class="topo-client-city">'+esc(s.city)+'</div>' : '<div style="height:16px;"></div>')+
      '<div class="topo-client-stats">'+
        '<div class="topo-client-stat"><div class="topo-cs-n" style="color:var(--text)">'+devs.length+'</div><div class="topo-cs-l">Dev</div></div>'+
        '<div class="topo-client-stat"><div class="topo-cs-n" style="color:var(--green)">'+on+'</div><div class="topo-cs-l">Online</div></div>'+
        '<div class="topo-client-stat"><div class="topo-cs-n" style="color:var(--red)">'+off+'</div><div class="topo-cs-l">Offline</div></div>'+
      '</div>';
    card.addEventListener('click', function(){{ openTopoForClient(s.id, s.name, color); }});
    grid.appendChild(card);
  }});
}}

function openTopoForClient(siteId, siteName, color) {{
  _topoSiteId = siteId;
  _topoReady = false;
  document.getElementById('topoClientSel').style.display = 'none';
  document.getElementById('topoMapView').style.display = '';
  document.getElementById('topoPanel').style.display = 'none';
  document.getElementById('topoClientLbl').textContent = siteName || '';
  document.getElementById('topoClientLbl').style.color = color || 'var(--accent)';
  topoInit();
}}

function backToClients() {{
  _topoSiteId = null;
  _tsel = null;
  document.getElementById('topoMapView').style.display = 'none';
  document.getElementById('topoClientSel').style.display = '';
}}

function getVisibleRouters() {{
  if(!_topoSiteId) return RD;
  return RD.filter(function(r){{ return r.site_id === _topoSiteId; }});
}}

// ── Label style controls ────────────────────────────────────
function toggleLabelPanel(e) {{
  if(e) e.stopPropagation();
  var p = document.getElementById('lblPanel');
  p.style.display = p.style.display==='none' ? '' : 'none';
  if(p.style.display!=='none') syncLabelPanelUI();
}}
document.addEventListener('click', function(){{
  var p = document.getElementById('lblPanel');
  if(p) p.style.display = 'none';
}});
function syncLabelPanelUI() {{
  document.querySelectorAll('.lbl-sz').forEach(function(b){{
    b.classList.toggle('active', parseInt(b.dataset.sz)===_lblSize());
  }});
  var chk = document.getElementById('lblBoldChk');
  if(chk) chk.checked = _lblBold();
  document.querySelectorAll('.lbl-col').forEach(function(d){{
    d.classList.toggle('active', d.dataset.col===(_lblStyle.color||''));
  }});
}}
function setLabelSize(sz) {{
  _lblStyle.size = sz;
  localStorage.setItem('rosm_lbl_style', JSON.stringify(_lblStyle));
  syncLabelPanelUI();
  topoRender();
}}
function setLabelBold(v) {{
  _lblStyle.bold = v;
  localStorage.setItem('rosm_lbl_style', JSON.stringify(_lblStyle));
  topoRender();
}}
function setLabelColor(col) {{
  _lblStyle.color = col;
  localStorage.setItem('rosm_lbl_style', JSON.stringify(_lblStyle));
  syncLabelPanelUI();
  topoRender();
}}

function topoInit() {{
  if(!_topoReady) {{
    try {{
      var key = 'rosm_topo' + (_topoSiteId ? '_'+_topoSiteId : '');
      _tpos = JSON.parse(localStorage.getItem(key)||'{{}}');
    }} catch(e) {{ _tpos = {{}}; }}
    topoAutoLayout(false);
    setupTopoEvents();
    _topoReady = true;
  }}
  topoRender();
  setTimeout(topoFitView, 60);
}}

function _topoSpacing(vis) {{
  // Compute horizontal and vertical spacing that avoids label overlaps.
  // Horizontal: based on longest label (name or IP) × estimated char width.
  // Vertical:   based on node diameter + label height + gap.
  var fontSize = _lblSize();
  var charW = fontSize * 0.62;   // approx proportional char width
  var maxLen = 2;
  vis.forEach(function(r) {{
    var lbl = r.name || r.ip;
    if(lbl.length > maxLen) maxLen = lbl.length;
  }});
  var labelPx  = maxLen * charW;
  var SX = Math.max(52, Math.ceil(labelPx) + 20); // label width + 20px gap
  var SY = Math.max(52, Math.ceil(fontSize * 0.5) + 44); // node (26px) + label + gap
  return {{SX: SX, SY: SY}};
}}

function topoAutoLayout(force) {{
  var PAD=14, HDR=44, COLS=8, GAP=30;
  var vis = getVisibleRouters();
  var sp  = _topoSpacing(vis);
  var SX  = sp.SX, SY = sp.SY;
  var sites = Object.values(SD).sort(function(a,b){{return (a.name||'').localeCompare(b.name||'');}});
  var cx = 30;
  sites.forEach(function(site) {{
    var devs = vis.filter(function(r){{return r.site_id===site.id;}});
    if(!devs.length) return;
    var cols = Math.min(COLS, devs.length);
    devs.forEach(function(r,i) {{
      if(force || !_tpos[r.ip]) {{
        _tpos[r.ip] = {{
          x: cx + PAD + (i%cols)*SX + SX/2,
          y: HDR + PAD + Math.floor(i/cols)*SY + SY/2
        }};
      }}
    }});
    cx += Math.max(cols,1)*SX + PAD*2 + GAP;
  }});
  // Unassigned in a separate row at bottom (only shown if no filter)
  if(!_topoSiteId) {{
    var unass = RD.filter(function(r){{return !r.site_id;}});
    var maxY = 0;
    Object.values(_tpos).forEach(function(p){{if(p.y>maxY)maxY=p.y;}});
    var uy = maxY + 80;
    unass.forEach(function(r,i) {{
      if(force || !_tpos[r.ip]) {{
        _tpos[r.ip] = {{x: 30+(i%12)*SX+SX/2, y: uy+Math.floor(i/12)*SY}};
      }}
    }});
  }}
  topoSavePos();
}}

function topoRender() {{
  var ns = 'http://www.w3.org/2000/svg';
  var canvas = document.getElementById('topoCanvas');
  canvas.innerHTML = '';
  var vis = getVisibleRouters();
  var sites = Object.values(SD).sort(function(a,b){{return (a.name||'').localeCompare(b.name||'');}});

  // ── Site background boxes ────────────────────────────────
  sites.forEach(function(site,si) {{
    var devs = vis.filter(function(r){{return r.site_id===site.id;}});
    if(!devs.length) return;
    var color = SITE_PAL[si % SITE_PAL.length];
    var NODE_R=13, PAD=18, HDR=44;
    var xs = devs.map(function(r){{return (_tpos[r.ip]||{{x:0}}).x;}});
    var ys = devs.map(function(r){{return (_tpos[r.ip]||{{y:0}}).y;}});
    // Extend box to include labels below nodes (approx label height = fontSize + 6)
    var lblExtra = _lblSize() + 6;
    var minX=Math.min.apply(null,xs)-NODE_R-PAD, maxX=Math.max.apply(null,xs)+NODE_R+PAD;
    var minY=Math.min.apply(null,ys)-NODE_R-PAD, maxY=Math.max.apply(null,ys)+NODE_R+PAD+lblExtra;

    // Background
    var bg = document.createElementNS(ns,'rect');
    bg.setAttribute('x',minX); bg.setAttribute('y',minY-HDR);
    bg.setAttribute('width',maxX-minX); bg.setAttribute('height',maxY-minY+HDR);
    bg.setAttribute('rx','10'); bg.setAttribute('fill',color);
    bg.setAttribute('fill-opacity','0.06'); bg.setAttribute('stroke',color);
    bg.setAttribute('stroke-opacity','0.3'); bg.setAttribute('stroke-width','1.5');
    canvas.appendChild(bg);

    // Header strip
    var hdr = document.createElementNS(ns,'rect');
    hdr.setAttribute('x',minX); hdr.setAttribute('y',minY-HDR);
    hdr.setAttribute('width',maxX-minX); hdr.setAttribute('height',HDR);
    hdr.setAttribute('rx','10'); hdr.setAttribute('fill',color);
    hdr.setAttribute('fill-opacity','0.18');
    canvas.appendChild(hdr);

    var on = devs.filter(function(r){{return r.status==='ONLINE';}}).length;
    // Site name
    var t1 = document.createElementNS(ns,'text');
    t1.setAttribute('x',(minX+maxX)/2); t1.setAttribute('y',minY-HDR+18);
    t1.setAttribute('text-anchor','middle'); t1.setAttribute('fill',color);
    t1.setAttribute('font-size','13'); t1.setAttribute('font-weight','700');
    t1.setAttribute('font-family','inherit');
    t1.textContent = (site.name||'')+(site.city?' • '+site.city:'');
    canvas.appendChild(t1);
    // Online count
    var t2 = document.createElementNS(ns,'text');
    t2.setAttribute('x',(minX+maxX)/2); t2.setAttribute('y',minY-HDR+33);
    t2.setAttribute('text-anchor','middle'); t2.setAttribute('fill',color);
    t2.setAttribute('fill-opacity','0.75'); t2.setAttribute('font-size','10');
    t2.setAttribute('font-family','inherit');
    t2.textContent = on+'/'+devs.length+' online';
    canvas.appendChild(t2);
  }});

  // Unassigned label (only when not filtered to a specific client)
  var unass = _topoSiteId ? [] : RD.filter(function(r){{return !r.site_id;}});
  if(unass.length) {{
    var uys = unass.map(function(r){{return (_tpos[r.ip]||{{y:0}}).y;}});
    var uxs = unass.map(function(r){{return (_tpos[r.ip]||{{x:0}}).x;}});
    var ux=Math.min.apply(null,uxs)-30, uy=Math.min.apply(null,uys)-20;
    var ul = document.createElementNS(ns,'text');
    ul.setAttribute('x',ux); ul.setAttribute('y',uy);
    ul.setAttribute('fill','#888'); ul.setAttribute('font-size','11');
    ul.setAttribute('font-weight','600'); ul.setAttribute('font-family','inherit');
    ul.textContent = 'Device non assegnati ('+unass.length+')';
    canvas.appendChild(ul);
  }}

  // ── Edges (parent_ip lines) — styled, circle-to-circle, clickable ──
  var NODE_R = 13;
  vis.forEach(function(r) {{
    if(!r.parent_ip) return;
    var p1=_tpos[r.ip], p2=_tpos[r.parent_ip];
    if(!p1||!p2) return;
    var dx=p2.x-p1.x, dy=p2.y-p1.y;
    var dist=Math.sqrt(dx*dx+dy*dy);
    if(dist<1) return;
    var ux=dx/dist, uy=dy/dist;
    var x1=(p1.x+NODE_R*ux).toFixed(1), y1=(p1.y+NODE_R*uy).toFixed(1);
    var x2=(p2.x-NODE_R*ux).toFixed(1), y2=(p2.y-NODE_R*uy).toFixed(1);
    var st = LINK_STYLES[r.link_type||''] || LINK_STYLES[''];

    // Visible styled line
    var vl = document.createElementNS(ns,'line');
    vl.setAttribute('x1',x1); vl.setAttribute('y1',y1);
    vl.setAttribute('x2',x2); vl.setAttribute('y2',y2);
    vl.setAttribute('stroke', st.color); vl.setAttribute('stroke-opacity','0.75');
    vl.setAttribute('stroke-width', String(st.width));
    if(st.dash) vl.setAttribute('stroke-dasharray', st.dash);
    canvas.appendChild(vl);

    // Invisible wide hit-area for easy clicking
    (function(childIp, parentIp) {{
      var hit = document.createElementNS(ns,'line');
      hit.setAttribute('x1',x1); hit.setAttribute('y1',y1);
      hit.setAttribute('x2',x2); hit.setAttribute('y2',y2);
      hit.setAttribute('stroke','transparent'); hit.setAttribute('stroke-width','12');
      hit.style.cursor = 'pointer';
      hit.addEventListener('click', function(e) {{
        e.stopPropagation();
        openLinkPanel(e, childIp, parentIp);
      }});
      canvas.appendChild(hit);
    }})(r.ip, r.parent_ip);
  }});

  // ── Nodes ───────────────────────────────────────────────
  vis.forEach(function(r) {{
    var pos = _tpos[r.ip];
    if(!pos) return;

    var g = document.createElementNS(ns,'g');
    g.setAttribute('class','topo-node');
    g.setAttribute('data-ip',r.ip);
    g.setAttribute('transform','translate('+pos.x+','+pos.y+')');
    g.style.cursor = 'pointer';

    // Outer glow ring for selected
    if(_tsel===r.ip) {{
      var glow = document.createElementNS(ns,'circle');
      glow.setAttribute('r','18'); glow.setAttribute('fill','none');
      glow.setAttribute('stroke','var(--accent)'); glow.setAttribute('stroke-width','2');
      glow.setAttribute('stroke-opacity','0.8'); glow.setAttribute('stroke-dasharray','4,2');
      g.appendChild(glow);
    }}

    var fill = r.status==='ONLINE'?'#22c55e':r.status==='OFFLINE'?'#ef4444':'#6b7280';

    // Background circle
    var cbg = document.createElementNS(ns,'circle');
    cbg.setAttribute('r','13'); cbg.setAttribute('fill',fill); cbg.setAttribute('fill-opacity','0.13');
    cbg.setAttribute('stroke',fill); cbg.setAttribute('stroke-width','2');
    g.appendChild(cbg);

    // Role icon inside the circle
    var iconSpecs = ROLE_ICONS[r.device_role||''] || ROLE_ICONS[''];
    iconSpecs.forEach(function(spec) {{
      var el = document.createElementNS(ns, spec.tag);
      el.setAttribute('fill', spec.tag==='circle' ? fill : 'none');
      el.setAttribute('fill-opacity', spec.tag==='circle' ? '0.7' : '1');
      el.setAttribute('stroke', fill);
      el.setAttribute('stroke-width', '1.4');
      el.setAttribute('stroke-linecap', 'round');
      el.setAttribute('stroke-linejoin', 'round');
      if(spec.d)  el.setAttribute('d', spec.d);
      if(spec.r)  el.setAttribute('r', String(spec.r));
      if(spec.cx) el.setAttribute('cx', String(spec.cx));
      if(spec.cy) el.setAttribute('cy', String(spec.cy));
      g.appendChild(el);
    }});

    // Label below — full name, no truncation, user-configurable style
    var lbl = r.name||r.ip;
    var tl = document.createElementNS(ns,'text');
    tl.setAttribute('text-anchor','middle'); tl.setAttribute('y','23');
    tl.setAttribute('font-size', String(_lblSize()));
    tl.setAttribute('fill', _lblColor());
    tl.setAttribute('font-weight', _lblBold() ? '700' : '400');
    tl.setAttribute('font-family','inherit');
    tl.textContent = lbl;
    g.appendChild(tl);

    g.addEventListener('mousedown',function(e){{topoNodeDown(e,r.ip);}});
    g.addEventListener('click',function(e){{e.stopPropagation();topoSelectNode(r.ip);}});
    g.addEventListener('dblclick',function(e){{e.stopPropagation();if(IA)openAssign(r.ip);}});

    canvas.appendChild(g);
  }});

  topoApplyTransform();
}}

function topoApplyTransform() {{
  var canvas = document.getElementById('topoCanvas');
  if(canvas) canvas.setAttribute('transform','translate('+_tvw.x+','+_tvw.y+') scale('+_tvw.k+')');
}}

function topoSelectNode(ip) {{
  _tsel = ip;
  var r = RD.find(function(x){{return x.ip===ip;}});
  if(!r) return;
  var site = (r.site_id&&SD[r.site_id]) ? esc(SD[r.site_id].name) : '&mdash;';
  var fill = r.status==='ONLINE'?'var(--green)':r.status==='OFFLINE'?'var(--red)':'var(--text3)';
  var html =
    '<div style="font-weight:700;color:var(--accent);font-family:var(--mono);margin-bottom:6px;word-break:break-all;">'+esc(r.ip)+'</div>'+
    (r.name?'<div style="font-size:12px;font-weight:600;margin-bottom:4px;">'+esc(r.name)+'</div>':'')+
    (r.model?'<div style="color:var(--text3);margin-bottom:2px;font-size:10px;">'+esc(r.model)+'</div>':'')+
    '<div style="margin-bottom:4px;">Sede: <strong>'+site+'</strong></div>'+
    (badge(r)?'<div style="margin-bottom:6px;">'+badge(r)+'</div>':'')+
    '<div style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;background:'+(r.status==='ONLINE'?'rgba(34,197,94,.12)':'rgba(239,68,68,.12)')+';color:'+fill+';">'+
      (r.status||'UNKNOWN')+'</div>'+
    (r.version?'<div style="color:var(--text3);font-size:10px;margin-top:4px;">ROS '+esc(r.version)+'</div>':'')+
    (IA?'<div style="margin-top:10px;"><button class="btn" style="width:100%;font-size:10px;padding:5px 0;" onclick="openAssign(\\''+ip+'\\')">Modifica assegnazione</button></div>':'');
  document.getElementById('topoPanelContent').innerHTML = html;
  document.getElementById('topoPanel').style.display = 'block';
  topoRender();  // redraw to show selection ring
}}

function topoNodeDown(e, ip) {{
  e.stopPropagation(); e.preventDefault();
  var startMX=e.clientX, startMY=e.clientY;
  var startPX=_tpos[ip].x, startPY=_tpos[ip].y;
  var moved=false;
  function onMove(ev) {{
    moved=true;
    var dx=(ev.clientX-startMX)/_tvw.k, dy=(ev.clientY-startMY)/_tvw.k;
    _tpos[ip]={{x:startPX+dx, y:startPY+dy}};
    topoRender();
  }}
  function onUp() {{
    if(moved) topoSavePos();
    document.removeEventListener('mousemove',onMove);
    document.removeEventListener('mouseup',onUp);
  }}
  document.addEventListener('mousemove',onMove);
  document.addEventListener('mouseup',onUp);
}}

function setupTopoEvents() {{
  var svg=document.getElementById('topoSvg');
  var wrap=document.getElementById('topoWrap');

  // Pan
  svg.addEventListener('mousedown',function(e) {{
    if(e.target===svg||e.target.tagName.toLowerCase()==='svg'||e.target.id==='topoCanvas') {{
      _tpan={{sx:e.clientX-_tvw.x, sy:e.clientY-_tvw.y}};
      svg.style.cursor='grabbing';
    }}
  }});
  window.addEventListener('mousemove',function(e) {{
    if(_tpan) {{
      _tvw.x=e.clientX-_tpan.sx; _tvw.y=e.clientY-_tpan.sy;
      topoApplyTransform();
    }}
  }});
  window.addEventListener('mouseup',function() {{
    _tpan=null; if(svg)svg.style.cursor='default';
  }});

  // Zoom on wheel
  wrap.addEventListener('wheel',function(e) {{
    e.preventDefault();
    var factor=e.deltaY<0?1.12:0.89;
    var rect=svg.getBoundingClientRect();
    var mx=e.clientX-rect.left, my=e.clientY-rect.top;
    _tvw.x=mx-(mx-_tvw.x)*factor;
    _tvw.y=my-(my-_tvw.y)*factor;
    _tvw.k=Math.max(0.1,Math.min(5,_tvw.k*factor));
    topoApplyTransform();
    document.getElementById('topoZoomLbl').textContent='Zoom: '+Math.round(_tvw.k*100)+'%';
  }},{{passive:false}});

  // Click on empty = deselect
  svg.addEventListener('click',function(e) {{
    if(e.target===svg||e.target.id==='topoCanvas') {{
      _tsel=null;
      document.getElementById('topoPanel').style.display='none';
      topoRender();
    }}
  }});
}}

function topoZoom(factor) {{
  var svg=document.getElementById('topoSvg');
  var rect=svg.getBoundingClientRect();
  var cx=rect.width/2, cy=rect.height/2;
  _tvw.x=cx-(cx-_tvw.x)*factor;
  _tvw.y=cy-(cy-_tvw.y)*factor;
  _tvw.k=Math.max(0.1,Math.min(5,_tvw.k*factor));
  topoApplyTransform();
  document.getElementById('topoZoomLbl').textContent='Zoom: '+Math.round(_tvw.k*100)+'%';
}}

function topoFitView() {{
  var vis = getVisibleRouters();
  var visIPs = vis.reduce(function(m,r){{m[r.ip]=1;return m;}},{{}});
  var all = Object.entries(_tpos).filter(function(e){{return visIPs[e[0]];}}).map(function(e){{return e[1];}});
  if(!all.length) return;
  var xs=all.map(function(p){{return p.x;}}), ys=all.map(function(p){{return p.y;}});
  var minX=Math.min.apply(null,xs)-30, maxX=Math.max.apply(null,xs)+30;
  var minY=Math.min.apply(null,ys)-50, maxY=Math.max.apply(null,ys)+30;
  var svg=document.getElementById('topoSvg');
  var rect=svg.getBoundingClientRect();
  if(!rect.width) return;
  var scale=Math.min(rect.width/(maxX-minX), rect.height/(maxY-minY), 1.5);
  _tvw.k=scale;
  _tvw.x=(rect.width-(maxX+minX)*scale)/2;
  _tvw.y=(rect.height-(maxY+minY)*scale)/2;
  topoApplyTransform();
  document.getElementById('topoZoomLbl').textContent='Zoom: '+Math.round(_tvw.k*100)+'%';
}}

// ══ LINK PANEL ══════════════════════════════════════════════
function openLinkPanel(e, childIp, parentIp) {{
  _lpChild = childIp; _lpParent = parentIp;
  var wrap = document.getElementById('topoWrap');
  var rect = wrap.getBoundingClientRect();
  var px = Math.min(e.clientX - rect.left + 10, rect.width  - 240);
  var py = Math.min(e.clientY - rect.top  + 10, rect.height - 260);
  var panel = document.getElementById('linkPanel');
  panel.style.left = px + 'px';
  panel.style.top  = py + 'px';

  // Endpoints label
  var child  = RD.find(function(r){{return r.ip===childIp;}}) || {{}};
  var parent = RD.find(function(r){{return r.ip===parentIp;}}) || {{}};
  document.getElementById('lpEndpoints').textContent =
    (child.name  || childIp)  + '  →  ' + (parent.name || parentIp);

  // Type buttons
  var cur = child.link_type || '';
  var typesEl = document.getElementById('lpTypes');
  typesEl.innerHTML = '';
  Object.keys(LINK_STYLES).forEach(function(k) {{
    var st = LINK_STYLES[k];
    var act = k === cur ? ' active' : '';
    var swatchStyle = 'background:' + st.color + ';height:' + Math.max(2, st.width) + 'px;';
    if(st.dash) swatchStyle += 'background:repeating-linear-gradient(90deg,' + st.color + ' 0,' + st.color + ' 8px,transparent 8px,transparent 13px);';
    var btn = document.createElement('button');
    btn.className = 'lp-type-btn' + act;
    btn.innerHTML = '<span class="lp-swatch" style="' + swatchStyle + '"></span>' + esc(st.label);
    (function(type){{ btn.onclick = function(){{ setLinkType(type); }}; }})(k);
    typesEl.appendChild(btn);
  }});
  panel.style.display = '';
}}

function closeLinkPanel() {{
  document.getElementById('linkPanel').style.display = 'none';
  _lpChild = null; _lpParent = null;
}}

async function setLinkType(type) {{
  if(!_lpChild) return;
  try {{
    var resp = await fetch('/api/device/link_type', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{ip: _lpChild, link_type: type}})
    }});
    var j = await resp.json();
    if(!j.ok) {{ alert('Errore salvataggio link type'); return; }}
    // Update local data
    var dev = RD.find(function(r){{return r.ip===_lpChild;}});
    if(dev) dev.link_type = type;
    closeLinkPanel();
    topoRender();  // redraw with new style
  }} catch(ex) {{ alert('Errore: ' + ex); }}
}}

// Close link panel on background click
document.addEventListener('click', function(e) {{
  var panel = document.getElementById('linkPanel');
  if(panel && panel.style.display !== 'none' && !panel.contains(e.target)) {{
    closeLinkPanel();
  }}
}});
// ════════════════════════════════════════════════════════════

function topoSavePos() {{
  try {{
    var key = 'rosm_topo' + (_topoSiteId ? '_'+_topoSiteId : '');
    localStorage.setItem(key, JSON.stringify(_tpos));
  }} catch(e) {{}}
}}
</script>
""", session=session, page_key="topology")


    def _json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    def render_main_page(self, session=None):
        _s       = session or {}
        is_admin = _s.get("role", "viewer") == "admin"

        total   = len(ROUTERS)
        online  = sum(1 for r in ROUTERS if r["status"] == "ONLINE")
        offline = total - online

        # Credential sets for the device credentials modal (name only, no passwords)
        cred_sets_js = json.dumps([{"id": c["id"], "name": c["name"]} for c in CRED_SETS])

        # In-app tour overlay (injected when ?tour=2 is in the URL)
        _qs_main = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _tour_block_main = _get_tour_js((_qs_main.get("tour") or [""])[0])


        # ---- table rows ----
        rows = ""
        for r in ROUTERS:
            row_id = "row-" + r["ip"].replace(".", "-")

            # row left-border highlight for active operations
            if r["ssh_status"] == "WORKING":
                row_style = 'style="border-left:3px solid var(--accent);"'
            elif r["ssh_status"] == "PENDING":
                row_style = 'style="border-left:3px solid var(--yellow);"'
            elif r["run_status"] == "RUNNING":
                row_style = 'style="border-left:3px solid var(--green);"'
            else:
                row_style = 'style="border-left:3px solid transparent;"'

            # status dot + label
            if r["status"] == "ONLINE":
                status_html = '<span class="sd"><span class="sd-dot on"></span><span class="sd-lbl on">ONLINE</span></span>'
            elif r["status"] == "OFFLINE":
                status_html = '<span class="sd"><span class="sd-dot off"></span><span class="sd-lbl off">OFFLINE</span></span>'
            else:
                status_html = '<span class="sd"><span class="sd-dot unk"></span><span class="sd-lbl unk">—</span></span>'

            # ssh status pill
            if r["ssh_status"] == "ERROR":
                _serr = (r.get("ssh_error") or "Errore SSH").replace('"', '&quot;').replace("'", "&#39;")
                ssh_html = (f'<span class="pill pill-red" style="cursor:pointer" title="{_serr}" '
                            f'onclick="showSSHError(this)">'
                            f'error</span>')
            else:
                ssh_map = {"IDLE": ("pill-gray","IDLE"), "PENDING": ("pill-yellow","PENDING"), "WORKING": ("pill-blue pulse","WORKING")}
                ssh_cls, ssh_label = ssh_map.get(r["ssh_status"], ("pill-gray", r["ssh_status"]))
                ssh_html = '<span class="pill ' + ssh_cls + '">' + ssh_label + '</span>'

            # Tags + Group
            tags_html = '<div class="tag-wrap" id="tags-' + r["ip"].replace(".","_") + '">'
            group = r.get("group", "")
            if group:
                tags_html += '<span class="tag-pill tag-group">' + group + '</span>'
            for tag in r.get("tags", []):
                # deterministic color from tag text
                col_idx = sum(ord(c) for c in tag) % len(TAG_COLORS)
                col = TAG_COLORS[col_idx]
                tags_html += ('<span class="tag-pill" style="background:' + col + '22;color:' + col
                              + ';border-color:' + col + '44">' + tag + '</span>')
            if is_admin:
                tags_html += ('<button class="tag-edit-btn" onclick="openTagEditor(\'' + r["ip"] + '\')" '
                              'title="' + T('Modifica tag e gruppo') + '">Edit</button>')
            tags_html += '</div>'

            # Open ports badges
            ports_html = _render_ports_html(r.get("open_ports", []))

            # Actions
            ip_q = urllib.parse.quote(r["ip"])
            ip_js = r["ip"].replace("'", "\\'")
            if is_admin:
                has_creds  = _device_has_creds(r["ip"])
                creds_warn = (
                    '<button class="act-btn act-warn" '
                    'onclick="openCredsModal(\'' + ip_js + '\')" title="No SSH credentials">No creds</button>'
                    if not has_creds else ''
                )
                info_btn   = '<a class="act-btn" href="/refresh?ip=' + ip_q + '&focus=' + ip_q + '" title="Read SSH info">SSH</a>'
                creds_btn  = ('<button class="act-btn" '
                              'onclick="openCredsModal(\'' + ip_js + '\')" title="SSH credentials">Creds</button>')
                rem_btn    = ('<button class="act-del" onclick="removeDevice(\'' + ip_js + '\')" '
                              'title="Remove from list">&#10005;</button>')
                action_td  = ('<td style="white-space:nowrap;"><div class="act-group">'
                              + creds_warn + info_btn + creds_btn + rem_btn + '</div></td>')
            else:
                action_td = '<td></td>'

            dash = '<span style="color:var(--text3)">—</span>'

            # Initial value for configurable column (packages=ROS version by default; JS will update)
            dyna_val = r.get("packages", "") or dash

            # Site name cell
            site_id   = r.get("site_id", "")
            site_name = SITES.get(site_id, {}).get("name", "") if site_id else ""
            site_html = ('<span style="font-size:10px;background:var(--accent3);color:var(--accent);'
                         'padding:1px 6px;border-radius:4px;font-weight:600;">' + site_name + '</span>'
                         if site_name else dash)

            rows += (
                '<tr id="' + row_id + '" ' + row_style + '>'
                '<td style="width:32px;text-align:center;padding:0 8px;"><input type="checkbox" class="row-cb" data-ip="' + r["ip"] + '" onclick="onRowCheck()"></td>'
                '<td class="sticky-col" style="font-weight:700;color:var(--accent);letter-spacing:.3px;">' + r["ip"] + '</td>'
                '<td>' + status_html + '</td>'
                '<td style="color:var(--text);font-weight:600">'  + (r["name"]  or dash) + '</td>'
                '<td style="color:var(--text2)">'          + (r["model"] or dash) + '</td>'
                '<td class="dyna-col">'                    + dyna_val + '</td>'
                '<td class="tag-cell">'                    + tags_html + '</td>'
                '<td>' + site_html + '</td>'
                '<td>' + ssh_html + '</td>'
                '<td class="ports-cell">' + ports_html + '</td>'
                + action_td +
                '</tr>\n'
            )

        checked = "checked" if AUTO_ENABLED else ""

        predefined_tags_js = json.dumps(_load_predefined_tags())
        _js_i18n = (
            f'var _TJSC={json.dumps(T("Chiudi"))};'
            f'var _TJSANM={json.dumps(T("! Anomalia rilevata"))};'
            f'var _TJSR={json.dumps(T("Clicca per rimuovere"))};'
            f'var _TJSA={json.dumps(T("Clicca per aggiungere"))};'
            f'var _TJSD={json.dumps(T("Elimina tag predefinito"))};'
            f'var _TJSN={json.dumps(T("Nessun tag assegnato"))};'
            f'var _TJSE={json.dumps(T("Modifica tag e gruppo"))};'
        )
        main_js = (MAIN_JS_TEMPLATE
            .replace('{predefined_tags_js}', predefined_tags_js)
            .replace('{rosm_lang}', LANGUAGE)
            .replace('{js_i18n}', _js_i18n)
        )

        username  = _s.get("username", "?")
        role      = _s.get("role", "viewer")

        role_badge = ('<span style="background:rgba(42,223,138,.12);color:var(--green);border:1px solid '
                      'rgba(42,223,138,.25);border-radius:20px;padding:2px 8px;font-size:10px;font-weight:700;">ADMIN</span>'
                      if is_admin else
                      '<span style="background:rgba(122,129,150,.08);color:var(--text2);border:1px solid var(--border);'
                      'border-radius:20px;padding:2px 8px;font-size:10px;font-weight:700;">VIEWER</span>')

        user_widget = (f'<span style="font-size:11px;color:var(--text2);">{username}</span>'
                       f'{role_badge}'
                       f'<a class="btn" href="/logout" title="{T("Esci")}">Logout</a>')

        admin_controls = ""  # now handled via _shared_header_html

        def _ip_badges(ip_list, color):
            if not ip_list:
                return ""
            badges = " ".join(
                '<a href="#" onclick="scrollToRow(\'' + ip + '\');return false;"'
                ' class="live-ip">' + ip + '</a>'
                for ip in ip_list
            )
            return '<span class="live-ips" style="color:' + color + '">' + badges + '</span>'

        pct_on  = round(online / total * 100) if total else 0
        pct_off = round(offline / total * 100) if total else 0

        ping_running = PING_RUNNING
        ping_lbl_str = (T("● IN CORSO") if ping_running else T("inattivo"))
        _lbl_en = LANGUAGE == "en"

        _dark = ' data-theme="dark"' if _user_dark_mode(session) else ''
        return f"""<!DOCTYPE html>
<html lang="{LANGUAGE}"{_dark}>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ROSM — Router OS Manager</title>
{FAVICON_TAG}
<style>
{COMMON_CSS}

/* ================================================================
   Layout: flex column — topbar fisso, tabella scrollabile
   Sovrascrive COMMON_CSS dove necessario
   ================================================================ */
html {{ height: 100%; }}
body {{
  min-height: 0 !important;   /* override COMMON_CSS min-height:100vh */
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}}
.header-top-bar {{ position: static; }}
.subnav-bar      {{ flex-shrink: 0; }}
.topbar          {{ flex-shrink: 0; }}

.table-wrap {{
  flex: 1 1 0;
  overflow: auto;
  min-height: 0;
}}

/* thead sticky dentro .table-wrap (che è il vero scroll container) */
thead {{ position: sticky; top: 0; z-index: 50; }}
thead tr.label-row th  {{ background: var(--bg2); border-bottom: 1px solid var(--border2); }}
thead tr.filter-row th {{ background: var(--bg);  border-bottom: 2px solid var(--border2); padding: 4px 6px; }}

th.asc::after  {{ content: " ▲"; font-size: 9px; color: var(--accent); }}
th.desc::after {{ content: " ▼"; font-size: 9px; color: var(--accent); }}

/* Package chips */
.pkg-cell {{ max-width: 240px; white-space: normal; line-height: 1.6; }}
.pkg-chip {{
  display: inline-block; padding: 1px 7px; margin: 1px 2px;
  border-radius: 10px; font-size: 10px; font-weight: 500;
  background: rgba(79,142,247,.1); border: 1px solid rgba(79,142,247,.2);
  color: var(--accent2);
}}

/* Row counter */
.row-counter {{
  font-size: 11px; color: var(--text2); margin-left: auto; padding-right: 4px;
}}
.row-counter span {{ color: var(--text); font-weight: 600; }}

/* ---- Modals ---- */
.modal-backdrop {{
  display: none; position: fixed; inset: 0; z-index: 500;
  background: rgba(0,0,0,.72); backdrop-filter: blur(4px);
  align-items: center; justify-content: center;
}}
.modal-backdrop.open {{ display: flex; }}
.modal {{
  background: var(--bg2); border: 1px solid var(--border2);
  border-radius: 12px; padding: 24px; width: 480px; max-width: 95vw;
  box-shadow: 0 8px 48px rgba(0,0,0,.7); animation: modalIn .15s ease;
}}
.modal.wide {{ width: 700px; }}
@keyframes modalIn {{ from {{ transform:translateY(-12px);opacity:0; }} to {{ transform:none;opacity:1; }} }}
.modal-title {{ font-family:var(--sans);font-size:15px;font-weight:700;color:var(--text);margin-bottom:16px; }}
.modal-field {{ margin-bottom:11px; }}
.modal-field label {{ display:block;font-size:11px;color:var(--text2);margin-bottom:4px; }}
.modal-field input[type=text],
.modal-field input[type=password],
.modal-field input[type=file] {{ width:100%;padding:7px 10px;font-size:12px; }}
.modal-row {{ display:flex;gap:8px; }}
.modal-row .modal-field {{ flex:1; }}
.modal-actions {{ display:flex;gap:8px;justify-content:flex-end;margin-top:18px; }}

/* Progress */
.progress-wrap {{ margin-top:14px;display:none;background:var(--bg3);border-radius:6px;overflow:hidden;height:7px; }}
.progress-wrap.visible {{ display:block; }}
.progress-bar {{ height:100%;width:0%;background:var(--accent);transition:width .3s;border-radius:6px; }}
.progress-bar.indeterminate {{ width:35%;animation:indeterminate 1.1s infinite ease-in-out; }}
@keyframes indeterminate {{ 0%{{margin-left:-35%;}} 100%{{margin-left:100%;}} }}
.progress-msg {{ font-size:11px;color:var(--text2);margin-top:6px;min-height:16px; }}
.progress-msg.ok   {{ color:var(--green); }}
.progress-msg.fail {{ color:var(--red); }}

/* Company rows in bulk modal */
.company-grid {{ display:flex;flex-direction:column;gap:10px;margin-bottom:14px;max-height:55vh;overflow-y:auto; }}
.company-row {{
  border:1px solid var(--border);border-radius:8px;padding:10px 12px;transition:border-color .15s;
}}
.company-row.selected {{ border-color:var(--accent);background:rgba(79,142,247,.05); }}
.company-header {{ display:flex;align-items:center;gap:8px;cursor:pointer; }}
.company-header input[type=checkbox] {{ accent-color:var(--accent);width:14px;height:14px;flex-shrink:0; }}
.company-name {{ font-weight:600;color:var(--text);font-size:12px; }}
.company-meta {{ font-size:10px;color:var(--text3);margin-left:auto; }}
.company-creds {{ display:none;margin-top:10px; }}
.company-row.selected .company-creds {{ display:flex;gap:8px; }}
.company-creds input {{ flex:1; }}

/* ── KPI bar ───────────────────────────────────────────────── */
.kpi-bar {{
  display:flex;align-items:stretch;background:var(--bg2);
  border-bottom:2px solid var(--border);flex-shrink:0;overflow-x:auto;
  box-shadow:0 2px 8px rgba(27,58,107,.06);
}}
.kpi {{
  display:flex;flex-direction:column;justify-content:center;
  padding:10px 20px;border-right:1px solid var(--border);gap:3px;flex-shrink:0;
}}
.kpi-n {{
  font-size:22px;font-weight:800;font-family:var(--sans);line-height:1;color:var(--text);
}}
.kpi-l {{
  font-size:9px;text-transform:uppercase;letter-spacing:.9px;color:var(--text3);font-weight:600;
}}
.kpi-ratio-wrap {{
  height:4px;border-radius:3px;background:var(--bg4);width:140px;display:flex;overflow:hidden;margin-top:4px;
}}
.kpi-ratio-on  {{ background:var(--green);border-radius:3px 0 0 3px;transition:width .6s ease; }}
.kpi-ratio-off {{ background:var(--red);transition:width .6s ease; }}
.kpi-counts {{ font-size:10px;display:flex;gap:8px;margin-top:2px; }}
.kpi-c-on  {{ color:var(--green);font-weight:700; }}
.kpi-c-off {{ color:var(--red);font-weight:700; }}
.kpi-ping-row {{ display:flex;align-items:center;gap:6px;font-size:11px; }}
.kpi-ping-dot {{
  width:8px;height:8px;border-radius:50%;flex-shrink:0;
  background:var(--text3);transition:background .3s;
}}
.kpi-ping-dot.active {{
  background:var(--yellow);
  animation:kpi-pulse 1.4s infinite;
}}
@keyframes kpi-pulse {{
  0%,100% {{ box-shadow:0 0 0 0 rgba(217,119,6,.5); }}
  50%     {{ box-shadow:0 0 0 6px rgba(217,119,6,.0); }}
}}
.kpi-spacer {{ flex:1; }}
.kpi-autoping {{
  display:flex;align-items:center;padding:0 16px;border-left:1px solid var(--border);
  flex-shrink:0;gap:8px;
}}

/* ── Status dot ────────────────────────────────────────────── */
.sd {{ display:inline-flex;align-items:center;gap:5px; }}
.sd-dot {{ width:6px;height:6px;border-radius:50%;flex-shrink:0; }}
.sd-dot.on  {{ background:var(--green);animation:sd-pulse 2.5s ease-in-out infinite; }}
.sd-dot.off {{ background:var(--red); }}
.sd-dot.unk {{ background:var(--text3); }}
@keyframes sd-pulse {{
  0%,100% {{ box-shadow:0 0 0 0 rgba(22,163,74,.4); }}
  60%     {{ box-shadow:0 0 0 4px rgba(22,163,74,.0); }}
}}
.sd-lbl {{ font-size:10px;font-weight:700;letter-spacing:.5px; }}
.sd-lbl.on  {{ color:var(--green); }}
.sd-lbl.off {{ color:var(--red); }}
.sd-lbl.unk {{ color:var(--text3); }}

/* ── Action buttons ────────────────────────────────────────── */
.act-group {{ display:flex;gap:3px;align-items:center; }}
.act-btn {{
  display:inline-flex;align-items:center;padding:3px 9px;border-radius:5px;
  font-size:10px;font-weight:600;letter-spacing:.2px;cursor:pointer;
  border:1px solid var(--border2);background:var(--bg2);color:var(--text2);
  transition:all .12s;text-decoration:none;white-space:nowrap;
}}
.act-btn:hover {{ border-color:var(--accent);color:var(--accent);background:var(--accent3); }}
.act-warn {{ border-color:rgba(220,38,38,.35);color:var(--red);background:rgba(220,38,38,.04); }}
.act-warn:hover {{ background:var(--red);color:#fff;border-color:var(--red); }}
.act-del {{
  padding:3px 7px;border-radius:5px;border:1px solid transparent;
  background:none;color:var(--text3);cursor:pointer;font-size:11px;
  transition:all .12s;line-height:1;
}}
.act-del:hover {{ background:rgba(220,38,38,.08);color:var(--red);border-color:rgba(220,38,38,.2); }}

/* ── Table improvements ────────────────────────────────────── */
.dash-ip {{
  font-weight:700;color:var(--accent);letter-spacing:.3px;font-size:12px;
}}
tbody tr {{ transition:background .07s; }}
tbody tr:nth-child(even) {{ background:rgba(var(--accent-rgb,79,142,247),.03); }}
tbody tr:hover {{ background:var(--bg3) !important; }}
tbody tr:hover .dash-ip {{ color:var(--accent2); }}
tbody td {{ padding:7px 11px;font-size:12px; }}
thead tr.label-row th {{
  font-size:10px;letter-spacing:.7px;text-transform:uppercase;font-weight:700;
  color:var(--text3);padding:8px 11px;position:relative;user-select:none;
}}

/* ── Column resize handle ───────────────────────────────────── */
.col-resizer {{
  position:absolute;right:0;top:0;bottom:0;width:5px;cursor:col-resize;
  z-index:10;border-right:1px solid transparent;transition:border-color .1s;
}}
.col-resizer:hover, .col-resizing {{ border-right-color:var(--accent) !important; }}

</style>
</head>
<body>

{self._shared_header_html(_s, active_page='dashboard', extra_controls=
        '<a class="btn btn-primary" href="/ping" style="padding:4px 12px;font-size:11px;" title="' + T('Ping tutti i router') + '">Ping All</a>'
        + '<a class="btn" href="/refresh_all" style="padding:4px 10px;font-size:11px;" title="' + T('SSH su tutti: nome, modello, versione') + '">Info SSH</a>'
        + '<button class="btn" onclick="openCustomColsModal()" style="padding:4px 10px;font-size:11px;" title="' + T('Colonne SSH personalizzate') + '">Colonne</button>'
        + '<button class="btn" onclick="exportCSV()" style="padding:4px 10px;font-size:11px;" title="' + T('Esporta tabella visibile come CSV') + '">CSV</button>'
        + (
        ('<button class="btn" onclick="toggleRTM()" style="padding:4px 12px;font-size:11px;'
         + ('background:#c0392b;color:#fff;border-color:#c0392b;" title="' + T('Real Time Monitoring attivo — clicca per disattivare') + '">● ' + T('RTM Attivo') + '</button>'
            if _app_cfg.get("rtm_enabled") else
            '" title="' + T('Attiva Real Time Monitoring (1 ping/sec)') + '">Real Time Monitoring</button>'))
        + '<form class="inline-form" action="/config" method="get" style="gap:4px;margin-left:4px;">'
        '<label style="display:flex;gap:4px;align-items:center;color:var(--text2);font-size:11px;">'
        '<input type="checkbox" name="enabled" ' + checked + ' style="accent-color:var(--accent);"> Ping ogni</label>'
        '<input type="number" name="secs" value="' + str(AUTO_INTERVAL) + '" min="5"'
        ' style="width:46px;font-size:11px;padding:3px 5px;">'
        '<span style="color:var(--text3);font-size:11px;">s</span>'
        '<input class="btn" type="submit" value="OK" style="padding:3px 8px;font-size:11px;"></form>'
        if is_admin else '')
    )}

<div class="topbar">
<div class="kpi-bar">

  <!-- Devices total + ratio bar -->
  <div class="kpi">
    <div class="kpi-n">{total}</div>
    <div class="kpi-l">{'Devices' if _lbl_en else 'Device'}</div>
    <div class="kpi-ratio-wrap">
      <div class="kpi-ratio-on"  id="kpi-ratio-on"  style="width:{pct_on}%"></div>
      <div class="kpi-ratio-off" id="kpi-ratio-off" style="width:{pct_off}%"></div>
    </div>
    <div class="kpi-counts">
      <span class="kpi-c-on"  id="kpi-c-on">{online}</span>
      <span style="color:var(--text3)">online</span>
      <span style="color:var(--border)">·</span>
      <span class="kpi-c-off" id="kpi-c-off">{offline}</span>
      <span style="color:var(--text3)">offline</span>
    </div>
  </div>

  <!-- Ping -->
  <div class="kpi">
    <div class="kpi-l">Ping</div>
    <div class="kpi-ping-row">
      <span class="kpi-ping-dot{'active' if ping_running else ''}" id="kpi-ping-dot"></span>
      <span id="stat-ping" style="font-size:11px;color:var(--text2);">{ping_lbl_str}</span>
    </div>
  </div>

  <!-- SSH active -->
  <div class="kpi">
    <div class="kpi-n" id="stat-ssh-w" style="font-size:18px;">0</div>
    <div class="kpi-l">SSH {'active' if _lbl_en else 'attive'}</div>
  </div>

  <!-- SSH pending -->
  <div class="kpi" id="kpi-ssh-p-wrap" style="display:none;">
    <div class="kpi-n" id="stat-ssh-p" style="font-size:18px;color:var(--yellow);">0</div>
    <div class="kpi-l" style="color:var(--yellow);">{'queued' if _lbl_en else 'in coda'}</div>
  </div>

  <!-- Spacer -->
  <div class="kpi-spacer"></div>

  <!-- Live IP badges (shown during operations) -->
  <div id="kpiLiveArea" style="display:flex;align-items:center;gap:8px;padding:0 14px;
    border-left:1px solid var(--border);font-size:10px;color:var(--text2);flex-shrink:0;overflow:hidden;max-width:340px;">
  </div>

</div>
</div>

<div class="bulk-bar" id="bulkTagBar">
  <span id="bulkCount"></span>
  <button id="bulkPingBtn"    class="btn" onclick="bulkPing()"         style="padding:3px 10px;">Ping</button>
  <button id="bulkRefreshBtn" class="btn" onclick="bulkRefresh()"      style="padding:3px 10px;">Info SSH</button>
  <button                     class="btn btn-primary" onclick="openBulkTagEditor()" style="padding:3px 10px;">Tag</button>
  <button id="bulkDeleteBtn"  class="btn btn-danger"  onclick="bulkDelete()"        style="padding:3px 10px;display:none;">Delete selected</button>
  <button                     class="btn" onclick="deselectAll()"      style="padding:3px 10px;">x</button>
</div>

<div class="table-wrap" id="tableWrap">
<table>
  <thead>
    <tr class="label-row">
      <th style="width:32px;text-align:center;padding:0 8px;"><input type="checkbox" id="selectAll" onclick="toggleSelectAll(this)"></th>
      <th onclick="sortTable(this,1)" style="min-width:110px;">IP</th>
      <th onclick="sortTable(this,2)" style="min-width:90px;">Stato</th>
      <th onclick="sortTable(this,3)">Nome</th>
      <th onclick="sortTable(this,4)">Modello</th>
      <th id="dynaColHead" onclick="sortTable(this,5)" style="min-width:130px;">
        <select id="dynaColSelect" onchange="setDynaCol(this.value);event.stopPropagation();"
                style="border:none;background:transparent;color:var(--text3);font-size:10px;
                       font-family:var(--mono);font-weight:600;letter-spacing:.9px;
                       text-transform:uppercase;cursor:pointer;padding:0;outline:none;width:100%;">
          <option value="packages">ROS Ver.</option>
          <option value="note_full">System Note</option>
          <option value="uptime">Uptime</option>
          <option value="last_online">Ultimo Online</option>
          <option value="mac">MAC</option>
          <option value="model">Modello (dup.)</option>
        </select>
      </th>
      <th>Tag / Gruppo</th>
      <th onclick="sortTable(this,7)">Sito</th>
      <th onclick="sortTable(this,8)">SSH</th>
      <th>Porte Aperte</th>
      <th style="width:90px;">Azioni</th>
    </tr>
    <tr class="filter-row">
      <th></th>
      <th><input class="filter" oninput="filterTable()" placeholder="IP…" data-col="1"></th>
      <th>
        <select class="filter" onchange="filterTable()" data-col="2">
          <option value="">Tutti</option>
          <option>ONLINE</option>
          <option>OFFLINE</option>
        </select>
      </th>
      <th><input class="filter" oninput="filterTable()" placeholder="Nome…"    data-col="3"></th>
      <th><input class="filter" oninput="filterTable()" placeholder="Modello…" data-col="4"></th>
      <th><input class="filter" oninput="filterTable()" placeholder="Cerca…"   data-col="5"></th>
      <th><input class="filter" oninput="filterTable()" placeholder="Tag/Gruppo…" data-col="6"></th>
      <th><input class="filter" oninput="filterTable()" placeholder="Sito…"    data-col="7"></th>
      <th>
        <select class="filter" onchange="filterTable()" data-col="8">
          <option value="">Tutti</option>
          <option>IDLE</option>
          <option>PENDING</option>
          <option>WORKING</option>
        </select>
      </th>
      <th><input class="filter" oninput="filterTable()" placeholder="{T('porta…')}" data-col="9"></th>
      <th style="text-align:right;vertical-align:middle;">
        <span class="row-counter" id="rowCounter"></span>
        <button class="btn-icon" onclick="clearFilters()" title="{T("Pulisci filtri")}" style="font-size:11px;">x</button>
      </th>
    </tr>
  </thead>
  <tbody>
    {rows}
  </tbody>
</table>
</div>

<!-- ══ Modal: tag editor ══ -->
<div class="modal-backdrop" id="backdropTag" onclick="if(event.target===this)closeModal('backdropTag')">
  <div class="modal" style="width:460px;max-width:96vw;">
    <div class="modal-title">Tag &amp; Gruppo — <span id="tagModalIP" style="color:var(--accent2)"></span></div>

    <div class="modal-field">
      <label>Gruppo (cliente / azienda)</label>
      <input type="text" id="tagGroup" placeholder="{'es. Cliente1, Cliente2…' if LANGUAGE=='it' else 'e.g. Client1, Client2…'}" autocomplete="off" style="width:100%">
    </div>

    <div class="modal-field">
      <label>Tag predefiniti</label>
      <div id="predTagsList" style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:6px;min-height:24px;"></div>
    </div>

    <div class="modal-field">
      <label>Tag assegnati a questo router</label>
      <div id="assignedTagsList" style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:6px;min-height:24px;"></div>
    </div>

    <div class="modal-field" style="display:flex;gap:6px;align-items:center;">
      <input type="text" id="newTagInput" placeholder="Crea nuovo tag…" style="flex:1" autocomplete="off"
             onkeydown="if(event.key==='Enter'){{addNewPredefinedTag();event.preventDefault();}}">
      <button class="btn btn-primary" onclick="addNewPredefinedTag()" style="white-space:nowrap;">+ Crea</button>
    </div>

    <div class="modal-actions">
      <button class="btn" onclick="closeModal('backdropTag')">Annulla</button>
      <button class="btn btn-primary" onclick="submitTagEditor()">Salva</button>
    </div>
  </div>
</div>
<div class="modal-backdrop" id="backdropUpload" onclick="if(event.target===this)closeModal('backdropUpload')">
  <div class="modal">
    <div class="modal-title">Script Upload — <span id="uploadModalIP" style="color:var(--accent2)"></span></div>

    <div class="modal-field">
      <label>File script (.rsc)</label>
      <input type="file" id="uploadFile" accept=".rsc,.txt">
    </div>
    <div class="modal-row">
      <div class="modal-field">
        <label>Username SSH</label>
        <input type="text" id="uploadUser" placeholder="es. admin" autocomplete="username">
      </div>
      <div class="modal-field">
        <label>Password SSH</label>
        <input type="password" id="uploadPass" placeholder="••••••••" autocomplete="current-password">
      </div>
    </div>

    <div class="progress-wrap" id="uploadProgressWrap">
      <div class="progress-bar indeterminate" id="uploadProgressBar"></div>
    </div>
    <div class="progress-msg" id="uploadProgressMsg"></div>

    <div class="modal-actions">
      <button class="btn" onclick="closeModal('backdropUpload')">Annulla</button>
      <button class="btn btn-primary" id="uploadSubmitBtn" onclick="submitSingleUpload()">Carica</button>
    </div>
  </div>
</div>

<!-- ══ Modal: upload per azienda ══ -->
<div class="modal-backdrop" id="backdropBulk" onclick="if(event.target===this)closeModal('backdropBulk')">
  <div class="modal wide">
    <div class="modal-title">Script Upload by Company</div>

    <div class="modal-field">
      <label>File script (.rsc) — verrà caricato su tutti i router delle aziende selezionate</label>
      <input type="file" id="bulkFile" accept=".rsc,.txt">
    </div>

    <div class="company-grid" id="companyGrid">
      <!-- populated by JS -->
    </div>

    <div class="progress-wrap" id="bulkProgressWrap">
      <div class="progress-bar" id="bulkProgressBar"></div>
    </div>
    <div class="progress-msg" id="bulkProgressMsg"></div>

    <div class="modal-actions">
      <button class="btn" onclick="closeModal('backdropBulk')">Chiudi</button>
      <button class="btn btn-primary" id="bulkSubmitBtn" onclick="submitBulkUpload()">Avvia caricamento</button>
    </div>
  </div>
</div>

<div id="customColsModal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:9000;align-items:center;justify-content:center;">
  <div style="background:var(--bg2);border:1px solid var(--border2);border-radius:12px;padding:24px;width:480px;max-width:96vw;max-height:85vh;overflow-y:auto;">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;">
      <span style="font-size:15px;font-weight:700;color:var(--text)">Colonne SSH Personalizzate</span>
      <button onclick="closeCustomColsModal()" style="background:none;border:none;color:var(--text2);font-size:20px;cursor:pointer;line-height:1;">x</button>
    </div>
    <p style="color:var(--text2);font-size:12px;margin:0 0 16px;">Definisci una colonna con un comando RouterOS. Il risultato SSH verrà mostrato nella colonna selezionabile.</p>
    <ul id="customColsList" style="list-style:none;margin:0 0 16px;padding:0;"></ul>
    <div style="border-top:1px solid var(--border);padding-top:16px;">
      <div style="font-size:12px;font-weight:600;color:var(--text2);margin-bottom:8px;text-transform:uppercase;letter-spacing:.8px;">Aggiungi nuova colonna</div>
      <input id="newColName" placeholder="Nome colonna (es. Free RAM)" style="width:100%;box-sizing:border-box;background:var(--bg3);border:1px solid var(--border2);color:var(--text);border-radius:6px;padding:8px 10px;font-size:13px;margin-bottom:8px;">
      <input id="newColCmd"  placeholder="Comando SSH (es. :put [/system resource get free-memory])" style="width:100%;box-sizing:border-box;background:var(--bg3);border:1px solid var(--border2);color:var(--text);border-radius:6px;padding:8px 10px;font-size:13px;margin-bottom:12px;font-family:var(--mono);">
      <button onclick="addCustomCol()" style="background:var(--accent);border:none;color:#fff;font-weight:700;padding:8px 20px;border-radius:6px;cursor:pointer;font-size:13px;">+ Aggiungi</button>
    </div>
  </div>
</div>

<div class="version-footer">
  ROSM v{APP_VERSION} {APP_STAGE} &nbsp;·&nbsp;
  <a href="#" onclick="document.getElementById('changelogModal').classList.add('open');return false;">Changelog</a>
  &nbsp;·&nbsp;
  <a href="#" onclick="document.getElementById('creditsModal').style.display='flex';return false;">Credits</a>
</div>

{self._changelog_modal_html()}

<!-- Credenziali SSH per router -->
<div id="credsModal" class="modal-overlay">
  <div style="background:var(--bg2);border:1px solid var(--border2);border-radius:14px;
       padding:28px;width:400px;max-width:96vw;box-shadow:0 8px 40px rgba(0,0,0,.22);">
    <div style="font-family:var(--sans);font-size:15px;font-weight:700;color:var(--text);margin-bottom:4px;">
      Credenziali SSH
    </div>
    <div id="credsModalSub" style="font-size:11px;color:var(--text2);margin-bottom:18px;"></div>
    <input type="hidden" id="credsModalIp">
    <div style="margin-bottom:20px;">
      <label style="font-size:10px;font-weight:700;color:var(--text2);display:block;margin-bottom:6px;text-transform:uppercase;letter-spacing:.6px;">Set credenziali</label>
      <select id="credsSelect" style="width:100%;box-sizing:border-box;font-size:13px;padding:8px 10px;border-radius:7px;border:1px solid var(--border2);background:var(--bg3);color:var(--text);">
        <option value="">— Nessuna (usa default di sito/globale) —</option>
      </select>
      <div style="font-size:10px;color:var(--text3);margin-top:6px;">
        I set si gestiscono in <a href="/credentials" style="color:var(--accent);">Credential Manager</a>.
      </div>
    </div>
    <div style="display:flex;gap:8px;justify-content:flex-end;">
      <button onclick="closeCredsModal()" class="btn">Annulla</button>
      <button onclick="saveCredsModal()" class="btn btn-primary">Salva</button>
    </div>
  </div>
</div>

<script>
{main_js}
</script>
<script>
var _CRED_SETS_DASH = {cred_sets_js};
function openCredsModal(ip) {{
  document.getElementById('credsModalIp').value = ip;
  document.getElementById('credsModalSub').textContent = 'Router: ' + ip;
  var sel = document.getElementById('credsSelect');
  sel.innerHTML = '<option value="">— Nessuna (usa default di sito/globale) —</option>';
  _CRED_SETS_DASH.forEach(function(c) {{
    var opt = document.createElement('option');
    opt.value = c.id; opt.textContent = c.name;
    sel.appendChild(opt);
  }});
  // Pre-select current cred if available
  var row = document.getElementById('row-' + ip.replaceAll('.', '-'));
  if (row && row.dataset.credId) sel.value = row.dataset.credId;
  document.getElementById('credsModal').classList.add('modal-show');
}}
function closeCredsModal() {{
  document.getElementById('credsModal').classList.remove('modal-show');
}}
async function saveCredsModal() {{
  var ip      = document.getElementById('credsModalIp').value;
  var credId  = document.getElementById('credsSelect').value;
  var r = await fetch('/api/device/creds', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{ ip: ip, cred_id: credId }})
  }});
  var j = await r.json();
  if (j.ok) {{
    closeCredsModal();
    var row = document.getElementById('row-' + ip.replaceAll('.', '-'));
    if (row) {{
      row.dataset.credId = credId;
      var btn = row.querySelector('.btn-danger[onclick*="openCredsModal"]');
      if (btn && credId) btn.className = btn.className.replace('btn-danger','');
    }}
  }} else {{
    alert('Errore: ' + (j.msg || 'sconosciuto'));
  }}
}}
</script>

{_tour_block_main}
</body>
</html>
"""
    # ------------------------------------------------------------------
    def render_discovery_page(self, session=None):
        devices_js = json.dumps({ip: {"group": d.get("group",""), "tags": d.get("tags",[])}
                                  for ip, d in DEVICES.items()})
        disc_cred_sets_js = json.dumps([{"id": c["id"], "name": c["name"], "username": _cred_set_username(c)} for c in CRED_SETS])
        sites_for_disc_js = json.dumps([
            {"id": sid, "name": s.get("name", sid)}
            for sid, s in sorted(SITES.items(), key=lambda x: x[1].get("name", ""))
        ])
        # Auto-detect local subnet
        def _local_subnet():
            try:
                import socket, struct
                # Connect to a public address (no data sent) to find the outbound interface IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                # Build /24 subnet from the local IP
                parts = local_ip.rsplit(".", 1)
                return f"{parts[0]}.0/24"
            except Exception:
                return "192.168.1.0/24"
        default_subnet = _local_subnet()
        return self._page_shell("Network Discovery", f"""
<style>
.disc-layout {{ display:grid; grid-template-columns:340px 1fr; gap:16px; height:calc(100vh - 90px); }}
.disc-panel {{ background:var(--bg2);border:1px solid var(--border);border-radius:10px;padding:16px;display:flex;flex-direction:column;gap:12px; }}
.disc-results {{ display:flex;flex-direction:column;gap:0;overflow:hidden; }}
.disc-results .card {{ flex:1;min-height:0;display:flex;flex-direction:column; }}
.disc-table-wrap {{ flex:1;overflow:auto; }}
.dtype-icon {{ font-size:18px; }}
.port-badge {{ font-size:9px;padding:1px 5px;border-radius:3px;background:var(--bg3);color:var(--text2);border:1px solid var(--border); }}
.port-8291 {{ color:var(--accent);border-color:var(--accent)44; }}
.progress-subnet {{ background:var(--bg3);border-radius:6px;height:5px;overflow:hidden;margin-top:4px; }}
.progress-subnet-bar {{ height:100%;background:var(--accent);border-radius:6px;transition:width .3s; }}
</style>

<div class="disc-layout">

  <!-- ═══ PANNELLO IMPOSTAZIONI ═══ -->
  <div class="disc-panel">
    <div style="font-family:var(--sans);font-size:14px;font-weight:700;color:var(--text);">Network Discovery</div>

    <div>
      <label style="font-size:11px;color:var(--text2);display:block;margin-bottom:4px;">{T("Subnet da scansionare")}</label>
      <input type="text" id="discSubnet" value="{default_subnet}"
             placeholder="es. 10.0.0.0/24" style="width:100%;">
      <div style="font-size:10px;color:var(--text3);margin-top:3px;">{T("Rilevata automaticamente dalla rete locale. Consigliato /24 (256 IP).")}</div>
    </div>

    <div>
      <label style="font-size:11px;color:var(--text2);display:block;margin-bottom:4px;">{T("Tag")}</label>
      <input type="text" id="discTag" placeholder="{'es. core, branch, ufficio…' if LANGUAGE=='it' else 'e.g. core, branch, office…'}" style="width:100%;">
    </div>

    <div>
      <label style="font-size:11px;color:var(--text2);display:block;margin-bottom:4px;">{T("Sito")}</label>
      <select id="discSite" style="width:100%;">
        <option value="">— {T("Nessun sito")} —</option>
      </select>
    </div>

    <div style="border-top:1px solid var(--border);padding-top:10px;">
      <div style="font-size:11px;font-weight:600;color:var(--text);margin-bottom:4px;">{T("Credenziali SSH RouterOS")}</div>
      <div style="font-size:10px;color:var(--text3);margin-bottom:8px;line-height:1.5;">
        {T("Opzionali — la scansione funziona anche senza: rileva comunque IP, porte aperte e tipo dispositivo. Servono solo per leggere identity e modello RouterOS via SSH.")}
      </div>
      <div style="margin-bottom:8px;">
        <label style="font-size:10px;font-weight:600;color:var(--text2);display:block;margin-bottom:3px;text-transform:uppercase;letter-spacing:.5px;">{T("Credenziali salvate")}</label>
        <select id="discCredPicker" onchange="applyDiscCred(this.value)" style="width:100%;">
          <option value="">— Inserisci manualmente —</option>
        </select>
      </div>
      <div id="discManualCreds" style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
        <div>
          <label style="font-size:10px;font-weight:600;color:var(--text2);display:block;margin-bottom:3px;text-transform:uppercase;letter-spacing:.5px;">Username</label>
          <input type="text" id="discUser" placeholder="Username SSH ({T('opzionale')})" style="width:100%;" autocomplete="off">
        </div>
        <div>
          <label style="font-size:10px;font-weight:600;color:var(--text2);display:block;margin-bottom:3px;text-transform:uppercase;letter-spacing:.5px;">Password</label>
          <input type="password" id="discPass" placeholder="Password SSH ({T('opzionale')})" style="width:100%;" autocomplete="off">
        </div>
      </div>
    </div>

    <button class="btn btn-primary" onclick="startDiscovery()"
            id="discBtn" style="width:100%;justify-content:center;padding:9px;font-size:13px;">
      {T("Avvia Scansione")}
    </button>

    <div id="discProgress" style="display:none;">
      <div style="font-size:11px;color:var(--text2);" id="discProgressMsg">{T("Scansione in corso…")}</div>
      <div class="progress-subnet">
        <div class="progress-subnet-bar" id="discProgressBar" style="width:0%"></div>
      </div>
    </div>

    <div id="discSummary" style="display:none;font-size:11px;line-height:1.7;color:var(--text2);">
    </div>

    <div id="discAddPanel" style="display:none;border-top:1px solid var(--border);padding-top:10px;">
      <div style="display:flex;gap:8px;">
        <button class="btn btn-primary" onclick="addSelected()" id="discAddSelBtn" style="flex:1;justify-content:center;">
          {T("Aggiungi Selezionati")}
        </button>
        <button class="btn" onclick="addAll()" style="flex:1;justify-content:center;">
          {T("Aggiungi Tutti")}
        </button>
      </div>
      <div id="discAddResult" style="font-size:11px;color:var(--text2);margin-top:8px;"></div>
    </div>
  </div>

  <!-- ═══ RISULTATI ═══ -->
  <div class="disc-results">
    <div class="card">
      <div class="card-header">
        <span>Dispositivi trovati</span>
        <span id="discFoundCount" style="color:var(--text3)">—</span>
      </div>
      <div class="disc-table-wrap">
        <table>
          <thead>
            <tr>
              <th style="width:36px;"><input type="checkbox" id="discSelectAll" onclick="toggleDiscAll(this)"></th>
              <th onclick="discSort(1)" style="cursor:pointer">IP ↕</th>
              <th>Tipo</th>
              <th onclick="discSort(3)" style="cursor:pointer">Hostname / Identity ↕</th>
              <th>{T("Modello")}</th>
              <th>{T("Porte aperte")}</th>
              <th>{T("In lista")}</th>
            </tr>
          </thead>
          <tbody id="discTbody">
            <tr><td colspan="7" style="text-align:center;color:var(--text3);padding:40px;">
              {T("Avvia una scansione per trovare dispositivi.")}
            </td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<script>
const EXISTING_DEVICES  = {devices_js};
const DISC_CRED_SETS    = {disc_cred_sets_js};
const DISC_SITES        = {sites_for_disc_js};
var _discResults = [];
var _discPollTimer = null;
var _discSshUser = '';
var _discSshPass = '';
var _discCredId  = '';
var _discTag     = '';
var _discSite    = '';

// Populate discovery credential picker
(function() {{
  var sel = document.getElementById('discCredPicker');
  if(!sel) return;
  DISC_CRED_SETS.forEach(function(c) {{
    var opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = c.name + ' (' + c.username + ')';
    sel.appendChild(opt);
  }});
}})();

// Populate site picker
(function() {{
  var sel = document.getElementById('discSite');
  if(!sel) return;
  DISC_SITES.forEach(function(s) {{
    var opt = document.createElement('option');
    opt.value = s.id;
    opt.textContent = s.name;
    sel.appendChild(opt);
  }});
}})();

function applyDiscCred(credId) {{
  _discCredId = credId;
  var manual = document.getElementById('discManualCreds');
  if(credId) {{
    manual.style.display = 'none';
    document.getElementById('discUser').value = '';
    document.getElementById('discPass').value = '';
  }} else {{
    manual.style.display = 'grid';
  }}
}}

const DTYPE_ICONS = {{
  routeros: '', ubiquiti: '', cisco: '',
  linux: '', nas: '', unknown: '[ ]'
}};
const DTYPE_LABELS = {{
  routeros:'RouterOS / MikroTik', ubiquiti:'Ubiquiti',
  cisco:'Cisco', linux:'Linux', nas:'NAS', unknown:'Sconosciuto'
}};

async function startDiscovery() {{
  var subnet = document.getElementById('discSubnet').value.trim();
  var tag    = document.getElementById('discTag').value.trim();
  var siteId = document.getElementById('discSite').value;
  var user   = _discCredId ? '' : document.getElementById('discUser').value.trim();
  var pass   = _discCredId ? '' : document.getElementById('discPass').value;
  if (!subnet) {{ alert('Inserisci una subnet.'); return; }}

  _discSshUser = user;
  _discSshPass = pass;
  _discTag     = tag;
  _discSite    = siteId;

  document.getElementById('discBtn').disabled      = true;
  document.getElementById('discProgress').style.display = 'block';
  document.getElementById('discSummary').style.display  = 'none';
  document.getElementById('discAddPanel').style.display = 'none';
  document.getElementById('discProgressBar').style.width = '0%';
  document.getElementById('discProgressMsg').textContent = 'Avvio scansione…';
  document.getElementById('discTbody').innerHTML =
    '<tr><td colspan="8" style="text-align:center;color:var(--text3);padding:30px;">Scansione in corso…</td></tr>';
  document.getElementById('discFoundCount').textContent = '—';
  _discResults = [];

  var scanBody = {{ subnet: subnet, group: tag }};
  if(_discCredId) {{
    scanBody.cred_id = _discCredId;
  }} else {{
    scanBody.ssh_user = user;
    scanBody.ssh_pass = pass;
  }}

  try {{
    var resp = await fetch('/api/scan', {{
      method: 'POST',
      headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify(scanBody)
    }});
    var data = await resp.json();
    if (!data.ok) {{ alert('Errore: ' + data.msg); document.getElementById('discBtn').disabled=false; return; }}
    pollScanJob(data.job_id, data.total || 256);
  }} catch(e) {{
    alert('Errore di rete: ' + e);
    document.getElementById('discBtn').disabled = false;
  }}
}}

function pollScanJob(job_id, total) {{
  clearTimeout(_discPollTimer);
  _discPollTimer = setTimeout(async function() {{
    var j = await fetch('/api/scan_job?id=' + job_id).then(function(r){{return r.json();}});
    var pct = total > 0 ? Math.round(j.done / total * 100) : 0;
    document.getElementById('discProgressBar').style.width = pct + '%';
    document.getElementById('discProgressMsg').textContent =
      'Scansionati ' + j.done + ' / ' + total + ' IP…';

    // Update results table progressively
    var responding = (j.results || []).filter(function(r){{return r.responding;}});
    _discResults = responding;
    renderDiscResults(responding);
    document.getElementById('discFoundCount').textContent = responding.length + ' trovati';

    if (j.status === 'done') {{
      document.getElementById('discProgressMsg').textContent =
        'Completato — ' + responding.length + ' dispositivi trovati su ' + total + ' IP';
      document.getElementById('discBtn').disabled = false;
      document.getElementById('discAddPanel').style.display = responding.length > 0 ? 'block' : 'none';
      renderDiscSummary(responding);
    }} else {{
      pollScanJob(job_id, total);
    }}
  }}, 800);
}}

function renderDiscResults(results) {{
  if (!results.length) {{
    document.getElementById('discTbody').innerHTML =
      '<tr><td colspan="7" style="text-align:center;color:var(--text3);padding:30px;">Nessun dispositivo trovato.</td></tr>';
    return;
  }}
  var html = results.map(function(r, i) {{
    var icon   = DTYPE_ICONS[r.device_type] || '[ ]';
    var label  = DTYPE_LABELS[r.device_type] || r.device_type;
    var exists = EXISTING_DEVICES[r.ip] !== undefined;
    var name   = r.ros_identity || r.hostname || '—';
    var model  = r.model || '—';
    var mac    = r.mac || '';
    var vendorDisp = r.vendor || label;
    var vendorCell = mac
      ? '<span title="MAC: ' + mac + '">' + icon + ' ' + vendorDisp + '</span>'
        + '<div style="font-size:9px;color:var(--text3);font-family:var(--mono);margin-top:1px;" title="OUI lookup">' + mac + '</div>'
      : '<span title="' + label + '">' + icon + ' ' + vendorDisp + '</span>';
    var ports  = (r.ports || []).map(function(p) {{
      return '<span class="port-badge' + (p===8291?' port-8291':'') + '">' + p + '</span>';
    }}).join(' ');
    var inList = exists
      ? '<span class="pill pill-green" style="font-size:9px">In lista</span>'
      : '<span class="pill pill-gray" style="font-size:9px">—</span>';
    return '<tr data-ip="' + r.ip + '">'
      + '<td><input type="checkbox" class="disc-cb" data-idx="' + i + '"' + (exists?' checked':'') + '></td>'
      + '<td style="font-weight:600;color:var(--accent2)">' + r.ip + '</td>'
      + '<td>' + vendorCell + '</td>'
      + '<td>' + name + '</td>'
      + '<td style="color:var(--text2)">' + model + '</td>'
      + '<td>' + ports + '</td>'
      + '<td>' + inList + '</td>'
      + '</tr>';
  }}).join('');
  document.getElementById('discTbody').innerHTML = html;
}}

function renderDiscSummary(results) {{
  var types = {{}};
  results.forEach(function(r) {{ types[r.device_type] = (types[r.device_type]||0)+1; }});
  var lines = Object.entries(types).map(function(e) {{
    return (DTYPE_ICONS[e[0]]||'?') + ' ' + (DTYPE_LABELS[e[0]]||e[0]) + ': <strong>' + e[1] + '</strong>';
  }}).join('<br>');
  var s = document.getElementById('discSummary');
  s.innerHTML = lines;
  s.style.display = 'block';
}}

function toggleDiscAll(cb) {{
  document.querySelectorAll('.disc-cb').forEach(function(c){{ c.checked = cb.checked; }});
}}

function getSelectedResults() {{
  var selected = [];
  document.querySelectorAll('.disc-cb:checked').forEach(function(cb) {{
    var idx = parseInt(cb.dataset.idx);
    if (_discResults[idx]) selected.push(_discResults[idx]);
  }});
  return selected;
}}

async function addSelected() {{
  var sel = getSelectedResults();
  if (!sel.length) {{ alert('Nessun dispositivo selezionato.'); return; }}
  await doAddDevices(sel);
}}

async function addAll() {{
  if (!_discResults.length) {{ alert('Nessun risultato.'); return; }}
  await doAddDevices(_discResults);
}}

async function doAddDevices(results) {{
  var btn = document.getElementById('discAddSelBtn');
  if(!_discSshUser && !_discCredId) {{
    document.getElementById('discAddResult').innerHTML =
      '<span style="color:var(--red);">Seleziona un set credenziali o inserisci username e password prima di aggiungere i dispositivi.</span>';
    return;
  }}
  btn.disabled = true;
  var devices = results.map(function(r) {{
    return {{
      ip:           r.ip,
      tags:         [],
      group:        _discTag,
      site_id:      _discSite,
      mac:          r.mac || '',
      ros_identity: r.ros_identity || '',
      model:        r.model || '',
    }};
  }});
  var payload = {{ devices: devices }};
  if(_discCredId) {{
    payload.cred_id = _discCredId;
  }} else {{
    devices.forEach(function(d) {{ d.ssh_user = _discSshUser; d.ssh_pass = _discSshPass; }});
  }}
  try {{
    var resp = await fetch('/api/add_devices', {{
      method: 'POST',
      headers: {{'Content-Type':'application/json'}},
      body: JSON.stringify(payload)
    }});
    var data = await resp.json();
    document.getElementById('discAddResult').innerHTML =
      data.added + ' dispositivi aggiunti. <a href="/topology" style="color:var(--accent)">→ Vai al Site Manager</a>';
    // Update "In lista" column
    renderDiscResults(_discResults);
  }} catch(e) {{
    document.getElementById('discAddResult').textContent = 'Errore: ' + e;
  }}
  btn.disabled = false;
}}

var _discSortDir = {{}};
function discSort(col) {{
  var asc = !_discSortDir[col];
  _discSortDir[col] = asc;
  _discResults.sort(function(a, b) {{
    var A = col===1 ? a.ip : (a.ros_identity||a.hostname||'');
    var B = col===1 ? b.ip : (b.ros_identity||b.hostname||'');
    if (col===1) {{
      var pa=A.split('.').map(Number), pb=B.split('.').map(Number);
      for(var i=0;i<4;i++){{var d=pa[i]-pb[i];if(d!==0)return asc?d:-d;}}
      return 0;
    }}
    return asc ? A.localeCompare(B) : B.localeCompare(A);
  }});
  renderDiscResults(_discResults);
}}
</script>
""", session=session, page_key="discovery")

    def render_upload_page(self, session=None):
        # Sites for filtering: [{id, name}]
        sites_for_upload = json.dumps([
            {"id": sid, "name": s.get("name", sid)}
            for sid, s in sorted(SITES.items(), key=lambda x: x[1].get("name",""))
        ])
        companies_js = json.dumps(COMPANIES)  # kept for bulk upload modal
        return self._page_shell("Script Upload", f"""
<style>
.upload-layout {{
  display: flex; gap: 16px; height: calc(100vh - 80px);
}}
.panel-left {{
  width: 420px; flex-shrink: 0;
  display: flex; flex-direction: column; gap: 10px;
}}
.panel-right {{
  flex: 1; display: flex; flex-direction: column; gap: 14px;
}}
.search-box {{ width: 100%; padding: 8px 10px; font-size: 12px; }}
.company-btn {{
  padding: 4px 10px; border-radius: 5px; font-size: 11px; cursor: pointer;
  border: 1px solid var(--border2); background: var(--bg3); color: var(--text2);
  font-family: var(--mono); transition: all .15s;
}}
.company-btn:hover, .company-btn.active {{
  border-color: var(--accent); color: var(--accent); background: rgba(79,142,247,.08);
}}
.router-list {{
  flex: 1; overflow-y: auto;
  border: 1px solid var(--border); border-radius: 8px; background: var(--bg2);
}}
.router-item {{
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px; border-bottom: 1px solid var(--border);
  cursor: pointer; transition: background .1s;
}}
.router-item:last-child {{ border-bottom: none; }}
.router-item:hover {{ background: var(--bg3); }}
.router-item.selected {{ background: rgba(79,142,247,.08); border-left: 3px solid var(--accent); }}
.router-item input[type=checkbox] {{ flex-shrink: 0; }}
.router-ip {{ font-weight: 600; color: var(--accent2); min-width: 110px; }}
.router-name {{ color: var(--text); font-size: 11px; }}
.router-status {{ margin-left: auto; }}
.sel-count {{ font-size: 11px; color: var(--text2); }}
.sel-count span {{ color: var(--accent); font-weight: 700; }}
.result-list {{
  flex: 1; overflow-y: auto; border: 1px solid var(--border); border-radius: 8px;
  background: var(--bg2); display: none;
}}
.result-list.visible {{ display: block; }}
.result-item {{
  display: flex; align-items: center; gap: 8px;
  padding: 7px 12px; border-bottom: 1px solid var(--border); font-size: 11px;
}}
.result-item:last-child {{ border-bottom: none; }}
.result-ip {{ color: var(--accent2); min-width: 110px; font-weight: 600; }}
.result-name {{ color: var(--text2); min-width: 160px; }}
.result-msg {{ color: var(--text3); font-size: 10px; flex: 1; }}
.result-ok   {{ color: var(--green); }}
.result-fail {{ color: var(--red); }}
</style>

<div class="upload-layout">

  <!-- ═══ SINISTRA: selezione router ═══ -->
  <div class="panel-left">
    <div style="font-size:13px;font-weight:700;color:var(--text);">{T("Seleziona Router")}</div>

    <input type="text" class="search-box" id="routerSearch"
           placeholder="{T('Cerca per IP o nome…')}" oninput="filterRouters()">

    <div style="display:flex;gap:6px;flex-wrap:wrap;" id="companyBtns">
      <button class="company-btn active" data-site="" onclick="filterBySite(this,'')">{T("Tutti")}</button>
    </div>

    <div style="display:flex;justify-content:space-between;align-items:center;">
      <label style="display:flex;gap:6px;align-items:center;font-size:11px;color:var(--text2);cursor:pointer;">
        <input type="checkbox" id="selectAll" onchange="toggleAll(this)"> {T("Seleziona tutti visibili")}
      </label>
      <span class="sel-count"><span id="selCount">0</span>{T(" selezionati")}</span>
    </div>

    <div class="router-list" id="routerList">
      <div style="padding:16px;color:var(--text3);font-size:11px;">{T("Caricamento router…")}</div>
    </div>
  </div>

  <!-- ═══ DESTRA: upload form + risultati ═══ -->
  <div class="panel-right">
    <div style="font-size:13px;font-weight:700;color:var(--text);">{T("Carica Script")}</div>

    <!-- Credential picker (same as backup manager) -->
    <div>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;">
        <label style="font-size:10px;font-weight:700;color:var(--text2);text-transform:uppercase;
                      letter-spacing:.7px;margin:0;">{T("Credenziali SSH")}</label>
        <a href="/credentials" style="margin-left:auto;font-size:10px;color:var(--accent);
                                       text-decoration:none;font-weight:600;white-space:nowrap;">
          Credential Manager →
        </a>
      </div>
      <select id="upCredPicker" style="width:100%;box-sizing:border-box;font-size:12px;margin-bottom:4px;">
        <option value="">— {T("Automatico: usa le credenziali del sito o del router")} —</option>
        {chr(10).join(f'        <option value="{c["id"]}">{c["name"]}</option>' for c in CRED_SETS)}
      </select>
      {"" if CRED_SETS else f'<div style="font-size:10px;color:var(--text3);font-style:italic;margin-bottom:4px;">{T("Nessun set credenziali configurato.")} <a href="/credentials" style="color:var(--accent);">{T("Creane uno nel Credential Manager")} →</a></div>'}
    </div>

    <div>
      <label style="font-size:11px;color:var(--text2);display:block;margin-bottom:4px;">{T("File script (.rsc)")}</label>
      <input type="file" id="upFile" accept=".rsc,.txt" style="width:100%;">
    </div>

    <div style="display:flex;flex-direction:column;gap:8px;">
      <label style="display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text2);cursor:pointer;user-select:none;">
        <input type="checkbox" id="upRunAfter" checked>
        {T("Esegui lo script subito dopo il caricamento")}
      </label>
      <div style="display:flex;gap:8px;align-items:center;">
        <button class="btn btn-primary" onclick="startUploadImport()"
                style="font-size:13px;padding:8px 20px;" id="upBtn">
          Upload
        </button>
        <span id="upStatus" style="font-size:11px;color:var(--text2);"></span>
      </div>
    </div>

    <div style="display:none;" id="upProgressWrap">
      <div style="background:var(--bg3);border-radius:6px;height:7px;overflow:hidden;margin-bottom:6px;">
        <div id="upBar" style="height:100%;width:0%;background:var(--accent);border-radius:6px;transition:width .3s;"></div>
      </div>
      <div id="upMsg" style="font-size:11px;color:var(--text2);"></div>
    </div>

    <div class="result-list" id="resultList"></div>
  </div>
</div>

<script>
const UPLOAD_SITES  = {sites_for_upload};
const COMPANIES     = {companies_js};
let allRouters   = [];
let activeSiteId = '';

// Load routers + build site buttons
fetch('/api/state').then(r => r.json()).then(data => {{
  allRouters = data.routers;
  renderSiteBtns();
  renderRouterList(allRouters);
}});

function renderSiteBtns() {{
  const wrap = document.getElementById('companyBtns');
  // First update "Tutti" count
  wrap.querySelector('[data-site=""]').textContent = 'Tutti (' + allRouters.length + ')';
  UPLOAD_SITES.forEach(function(s) {{
    const count = allRouters.filter(r => r.site_id === s.id).length;
    const btn = document.createElement('button');
    btn.className = 'company-btn';
    btn.dataset.site = s.id;
    btn.textContent = s.name + ' (' + count + ')';
    btn.onclick = function() {{ filterBySite(btn, s.id); }};
    wrap.appendChild(btn);
  }});
  // Fallback: also add groups from COMPANIES if no sites
  if(!UPLOAD_SITES.length) {{
    Object.entries(COMPANIES).forEach(([name, prefix]) => {{
      const count = allRouters.filter(r => r.ip.startsWith(prefix)).length;
      const btn = document.createElement('button');
      btn.className = 'company-btn';
      btn.dataset.site = 'prefix:' + prefix;
      btn.textContent = name + ' (' + count + ')';
      btn.onclick = function() {{ filterBySite(btn, 'prefix:' + prefix); }};
      wrap.appendChild(btn);
    }});
  }}
}}

function filterBySite(el, siteId) {{
  activeSiteId = siteId;
  document.querySelectorAll('.company-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  filterRouters();
}}

function filterRouters() {{
  const q = document.getElementById('routerSearch').value.toLowerCase();
  const filtered = allRouters.filter(r => {{
    if(activeSiteId.startsWith('prefix:')) {{
      const pf = activeSiteId.slice(7);
      if(!r.ip.startsWith(pf)) return false;
    }} else if(activeSiteId !== '') {{
      if(r.site_id !== activeSiteId) return false;
    }}
    return r.ip.includes(q) || (r.name || '').toLowerCase().includes(q);
  }});
  renderRouterList(filtered);
}}

function renderRouterList(routers) {{
  const list = document.getElementById('routerList');
  if (!routers.length) {{
    list.innerHTML = '<div style="padding:16px;color:var(--text3);font-size:11px;">Nessun router trovato.</div>';
    updateSelCount(); return;
  }}
  list.innerHTML = routers.map(r => {{
    const statusCls = r.status === 'ONLINE' ? 'pill pill-green' : 'pill pill-red';
    return '<div class="router-item" onclick="toggleRouter(this)" data-ip="' + r.ip + '">'
      + '<input type="checkbox" class="r-check" data-ip="' + r.ip + '" onclick="event.stopPropagation();this.closest(\\'.router-item\\').classList.toggle(\\'selected\\',this.checked);updateSelCount();">'
      + '<span class="router-ip">' + r.ip + '</span>'
      + '<span class="router-name">' + (r.name || '—') + '</span>'
      + '<span class="router-status"><span class="' + statusCls + '">' + (r.status || '—') + '</span></span>'
      + '</div>';
  }}).join('');
  updateSelCount();
}}

function toggleRouter(item) {{
  const cb = item.querySelector('.r-check');
  cb.checked = !cb.checked;
  item.classList.toggle('selected', cb.checked);
  updateSelCount();
}}

function toggleAll(master) {{
  document.querySelectorAll('.r-check').forEach(cb => {{
    cb.checked = master.checked;
    cb.closest('.router-item').classList.toggle('selected', master.checked);
  }});
  updateSelCount();
}}

function updateSelCount() {{
  const n    = document.querySelectorAll('.r-check:checked').length;
  const run  = document.getElementById('upRunAfter').checked;
  document.getElementById('selCount').textContent = n;
  document.getElementById('upBtn').textContent = (run ? 'Upload + Run' : 'Upload') + ' (' + n + ')';
}}
document.getElementById('upRunAfter').addEventListener('change', updateSelCount);

function getSelectedIPs() {{
  return Array.from(document.querySelectorAll('.r-check:checked')).map(cb => cb.dataset.ip);
}}

// ── Upload + Import ──────────────────────────────────────────────
let _pollTimer = null;

async function startUploadImport() {{
  const ips     = getSelectedIPs();
  const file    = document.getElementById('upFile').files[0];
  const runAfter= document.getElementById('upRunAfter').checked;
  const stat    = document.getElementById('upStatus');

  if (!ips.length) {{ stat.textContent = '! Seleziona almeno un router.'; return; }}
  if (!file) {{ stat.textContent = '! Seleziona un file .rsc.'; return; }}

  const btn  = document.getElementById('upBtn');
  const wrap = document.getElementById('upProgressWrap');
  const bar  = document.getElementById('upBar');
  const msg  = document.getElementById('upMsg');
  const rlist= document.getElementById('resultList');

  btn.disabled  = true;
  stat.textContent = '';
  wrap.style.display = 'block';
  bar.style.width = '0%';
  msg.textContent = 'Invio richiesta…';
  rlist.innerHTML = '';
  rlist.classList.add('visible');

  const fd = new FormData();
  fd.append('file', file);
  fd.append('ips',  ips.join(','));
  fd.append('run_after', runAfter ? '1' : '');
  fd.append('cred_id', document.getElementById('upCredPicker').value);

  try {{
    const res  = await fetch('/upload_import', {{ method: 'POST', body: fd }});
    const data = await res.json();
    if (!data.ok) {{
      msg.textContent = 'x ' + data.msg;
      btn.disabled = false; return;
    }}
    pollJob(data.job_id, data.total, bar, msg, btn, rlist);
  }} catch(e) {{
    msg.textContent = 'x Errore: ' + e;
    btn.disabled = false;
  }}
}}

function pollJob(job_id, total, bar, msg, btn, rlist) {{
  clearTimeout(_pollTimer);
  _pollTimer = setTimeout(async () => {{
    const j = await fetch('/api/job?id=' + job_id).then(r => r.json());
    const pct = total > 0 ? Math.round(j.done / total * 100) : 0;
    bar.style.width = pct + '%';
    const ok   = j.results.filter(r => r.ok).length;
    const fail = j.results.filter(r => !r.ok).length;
    msg.textContent = j.done + ' / ' + total + '  OK ' + ok + '  x ' + fail;

    // Render results
    rlist.innerHTML = j.results.map(r => {{
      const cls = r.ok ? 'result-ok' : 'result-fail';
      const ico = r.ok ? 'OK' : 'x';
      return '<div class="result-item">'
        + '<span class="' + cls + '">' + ico + '</span>'
        + '<span class="result-ip">' + r.ip + '</span>'
        + '<span class="result-name">' + (r.name || '—') + '</span>'
        + '<span class="result-msg">' + (r.msg || '') + '</span>'
        + '</div>';
    }}).join('');

    if (j.done < total) {{
      pollJob(job_id, total, bar, msg, btn, rlist);
    }} else {{
      btn.disabled = false;
      msg.style.color = fail === 0 ? 'var(--green)' : 'var(--red)';
      msg.textContent += '  — Completato';
    }}
  }}, 600);
}}
</script>
""", session=session, page_key="upload")

    def render_provision_page(self, session=None):
        """
        Pagina Provisioning — 3 tab:
          · Template   : elenco + editor RSC con variabili
          · Dispositivi: pre-registrazione MAC + factory password
          · Log        : storico apply
        """
        _s       = session or {}
        lang_en  = _s.get("lang", "") == "en"
        is_admin = _s.get("role", "viewer") in ("admin", "manager")
    
        # ── Dati serializzati per JS ───────────────────────────────────────────
        sites_js      = json.dumps({
            sid: s.get("name", sid)
            for sid, s in sorted(SITES.items(), key=lambda x: x[1].get("name", ""))
        })
        templates_js  = json.dumps(list(ZTP_TEMPLATES.values()))
        devices_js    = json.dumps([
            {
                "mac":           d["mac"],
                "hostname_hint": d.get("hostname_hint", ""),
                "site_id":       d.get("site_id", ""),
                "note":          d.get("note", ""),
                "registered_at": d.get("registered_at", ""),
                "applied":       d.get("applied", False),
                "applied_at":    d.get("applied_at", ""),
            }
            for d in ZTP_DEVICES.values()
        ])
        log_js = json.dumps(ZTP_LOG[:100])
    
        T = lambda it: it   # in integrazione: usa T() di dashboard.py
    
        content = f"""
    <style>
    /* ── Layout ── */
    .prov-layout {{
      display: flex; flex-direction: column; gap: 16px;
    }}
    /* ── Tab bar ── */
    .tab-bar {{
      display: flex; gap: 0; border-bottom: 2px solid var(--border);
    }}
    .tb-btn {{
      padding: 8px 18px; font-size: 12px; font-weight: 600;
      border: none; background: none; cursor: pointer;
      color: var(--text2); border-bottom: 2px solid transparent;
      margin-bottom: -2px; font-family: var(--mono);
      transition: color .15s, border-color .15s;
    }}
    .tb-btn.active {{
      color: var(--accent2); border-bottom-color: var(--accent2);
    }}
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}
    /* ── Due colonne template ── */
    .tpl-split {{
      display: grid; grid-template-columns: 260px 1fr; gap: 14px;
      height: calc(100vh - 170px);
    }}
    .tpl-list {{
      border: 1px solid var(--border); border-radius: var(--r2);
      background: var(--bg2); overflow-y: auto; display: flex; flex-direction: column;
    }}
    .tpl-item {{
      padding: 10px 12px; cursor: pointer;
      border-bottom: 1px solid var(--border);
      transition: background .1s;
    }}
    .tpl-item:last-child {{ border-bottom: none; }}
    .tpl-item:hover {{ background: var(--bg3); }}
    .tpl-item.sel {{ background: var(--accent3); border-left: 3px solid var(--accent2); }}
    .tpl-name {{ font-weight: 600; color: var(--text); font-size: 12px; }}
    .tpl-site {{ font-size: 10px; color: var(--text3); margin-top: 2px; }}
    .tpl-editor {{
      display: flex; flex-direction: column; gap: 10px;
      border: 1px solid var(--border); border-radius: var(--r2);
      background: var(--bg2); padding: 14px; overflow-y: auto;
    }}
    .field-row {{
      display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
    }}
    .field-label {{
      font-size: 10px; font-weight: 700; color: var(--text2);
      text-transform: uppercase; letter-spacing: .7px;
      min-width: 110px;
    }}
    .field-input {{
      flex: 1; padding: 6px 9px; font-size: 12px;
      border: 1px solid var(--border2); border-radius: var(--r);
      background: var(--bg3); color: var(--text); font-family: var(--mono);
      min-width: 0;
    }}
    .field-input:focus {{ outline: none; border-color: var(--accent2); }}
    textarea.field-input {{
      resize: vertical; min-height: 280px;
      font-size: 11px; line-height: 1.7; tab-size: 2;
    }}
    /* ── Variabili rilevate ── */
    .var-chips {{ display: flex; flex-wrap: wrap; gap: 6px; }}
    .var-chip {{
      display: inline-flex; align-items: center; gap: 4px;
      padding: 3px 8px; border-radius: 20px; font-size: 10px;
      font-weight: 700; font-family: var(--mono);
    }}
    .var-auto   {{ background: var(--accent3); color: var(--accent2); }}
    .var-custom {{ background: rgba(124,58,237,.1); color: #7c3aed; }}
    /* ── Device table ── */
    .dev-table {{
      width: 100%; border-collapse: collapse; font-size: 11px;
    }}
    .dev-table th {{
      padding: 7px 10px; text-align: left; font-size: 10px; font-weight: 700;
      text-transform: uppercase; letter-spacing: .7px; color: var(--text3);
      border-bottom: 2px solid var(--border);
    }}
    .dev-table td {{
      padding: 8px 10px; border-bottom: 1px solid var(--border); color: var(--text);
      vertical-align: middle;
    }}
    .dev-table tr:last-child td {{ border-bottom: none; }}
    .dev-table tr:hover td {{ background: var(--bg3); }}
    .pill {{
      display: inline-block; padding: 2px 7px; border-radius: 20px;
      font-size: 10px; font-weight: 700;
    }}
    .pill-green {{ background: rgba(22,163,74,.12); color: var(--green); }}
    .pill-gray  {{ background: var(--bg3); color: var(--text3); }}
    /* ── Log table ── */
    .log-table {{
      width: 100%; border-collapse: collapse; font-size: 11px;
    }}
    .log-table th {{
      padding: 7px 10px; text-align: left; font-size: 10px; font-weight: 700;
      text-transform: uppercase; letter-spacing: .7px; color: var(--text3);
      border-bottom: 2px solid var(--border);
    }}
    .log-table td {{
      padding: 7px 10px; border-bottom: 1px solid var(--border); color: var(--text);
      vertical-align: top; font-family: var(--mono);
    }}
    .log-table tr:last-child td {{ border-bottom: none; }}
    .ok-dot   {{ color: var(--green); font-weight: 700; }}
    .err-dot  {{ color: var(--red);   font-weight: 700; }}
    /* ── Reg form ── */
    .reg-form {{
      display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
      max-width: 680px; margin-bottom: 20px;
      padding: 14px; border: 1px solid var(--border);
      border-radius: var(--r2); background: var(--bg2);
    }}
    .reg-form .full {{ grid-column: 1 / -1; }}
    /* ── Extra vars table ── */
    .evars-wrap {{ margin-top: 4px; }}
    .evars-table {{
      width: 100%; border-collapse: collapse; font-size: 11px;
    }}
    .evars-table th {{
      text-align: left; padding: 4px 6px; font-size: 10px; color: var(--text3);
      font-weight: 700; text-transform: uppercase; border-bottom: 1px solid var(--border);
    }}
    .evars-table td {{
      padding: 4px 6px; border-bottom: 1px solid var(--border);
    }}
    .evars-table td:first-child {{
      font-family: var(--mono); color: var(--accent2); font-size: 11px;
    }}
    .section-head {{
      font-size: 10px; font-weight: 700; text-transform: uppercase;
      letter-spacing: .8px; color: var(--text3); margin: 0 0 6px;
    }}
    </style>
    
    <div class="prov-layout">
    
      <!-- ══ Subnav ══ -->
      <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
        <span style="font-size:14px;font-weight:700;color:var(--text);">{T("Provisioning")}</span>
        <span style="font-size:10px;color:var(--text3);">{T("Template RSC + pre-registrazione dispositivi")}</span>
      </div>
    
      <!-- ══ Tab bar ══ -->
      <div class="tab-bar">
        <button class="tb-btn active" onclick="switchTab('tpl')">{T("Template")}</button>
        <button class="tb-btn" onclick="switchTab('dev')">{T("Dispositivi")} <span id="devBadge" style="font-size:10px;color:var(--text3);"></span></button>
        <button class="tb-btn" onclick="switchTab('log')">{T("Log")}</button>
      </div>
    
      <!-- ══════════════════════ TAB: TEMPLATE ══════════════════════ -->
      <div id="tab-tpl" class="tab-panel active">
        <div class="tpl-split">
    
          <!-- Elenco template -->
          <div style="display:flex;flex-direction:column;gap:8px;">
            <button class="btn btn-primary" style="width:100%;" onclick="newTemplate()">{T("+ Nuovo template")}</button>
            <div class="tpl-list" id="tplList">
              <div style="padding:16px;color:var(--text3);font-size:11px;">{T("Nessun template. Crea il primo →")}</div>
            </div>
          </div>
    
          <!-- Editor -->
          <div class="tpl-editor" id="tplEditor">
            <div style="color:var(--text3);font-size:12px;padding:20px 0;text-align:center;">
              {T("Seleziona un template o creane uno nuovo.")}
            </div>
          </div>
    
        </div>
      </div>
    
      <!-- ══════════════════════ TAB: DISPOSITIVI ══════════════════════ -->
      <div id="tab-dev" class="tab-panel">
    
        <!-- Form registrazione -->
        <div class="reg-form" id="regForm">
          <div>
            <div class="section-head">{T("MAC Address")}</div>
            <input id="regMac" class="field-input" style="width:100%;"
                   placeholder="AA:BB:CC:DD:EE:FF"
                   oninput="regMacInput(this)">
            <div id="regMacNote" style="font-size:10px;color:var(--text3);margin-top:3px;"></div>
          </div>
          <div>
            <div class="section-head">{T("Factory Password")} <span style="color:var(--red);">*</span></div>
            <input id="regPass" class="field-input" style="width:100%;" type="password"
                   placeholder="{T('Password stampata sul router')}">
          </div>
          <div>
            <div class="section-head">{T("Hostname (suggerimento)")}</div>
            <input id="regHostname" class="field-input" style="width:100%;"
                   placeholder="{T('es. router-filiale-roma')}">
          </div>
          <div>
            <div class="section-head">{T("Sede")}</div>
            <select id="regSite" class="field-input" style="width:100%;">
              <option value="">{T("— Nessuna sede —")}</option>
            </select>
          </div>
          <div class="full">
            <div class="section-head">{T("Note")}</div>
            <input id="regNote" class="field-input" style="width:100%;"
                   placeholder="{T('es. Router consegnato a Milano il 10/06')}">
          </div>
          <div class="full" style="display:flex;gap:8px;">
            <button class="btn btn-primary" onclick="registerDevice()">{T("Registra dispositivo")}</button>
            <span id="regMsg" style="font-size:11px;color:var(--text3);align-self:center;"></span>
          </div>
        </div>
    
        <!-- Tabella dispositivi pre-registrati -->
        <div style="overflow-x:auto;">
          <table class="dev-table" id="devTable">
            <thead>
              <tr>
                <th>MAC</th>
                <th>{T("Hostname (hint)")}</th>
                <th>{T("Sede")}</th>
                <th>{T("Nota")}</th>
                <th>{T("Registrato")}</th>
                <th>{T("Applicato")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody id="devTbody">
              <tr><td colspan="7" style="color:var(--text3);padding:16px;">{T("Nessun dispositivo pre-registrato.")}</td></tr>
            </tbody>
          </table>
        </div>
    
      </div>
    
      <!-- ══════════════════════ TAB: LOG ══════════════════════ -->
      <div id="tab-log" class="tab-panel">
        <div style="overflow-x:auto;">
          <table class="log-table" id="logTable">
            <thead>
              <tr>
                <th>{T("Data/ora")}</th>
                <th>IP</th>
                <th>{T("Hostname")}</th>
                <th>{T("Template")}</th>
                <th>{T("Esito")}</th>
                <th>{T("Messaggio")}</th>
              </tr>
            </thead>
            <tbody id="logTbody">
              <tr><td colspan="6" style="color:var(--text3);padding:16px;">{T("Nessuna operazione registrata.")}</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    
    </div><!-- /prov-layout -->
    
    <!-- ══ Apply modal ══ -->
    <div id="applyModal" class="modal-overlay" style="display:none;"
         onclick="if(event.target===this)closeApplyModal()">
      <div class="modal" style="max-width:480px;width:95%;">
        <div style="font-size:13px;font-weight:700;margin-bottom:14px;">{T("Applica template")}</div>
        <div style="display:flex;flex-direction:column;gap:10px;">
          <div>
            <div class="section-head">IP router</div>
            <input id="aIp" class="field-input" style="width:100%;" placeholder="192.168.1.1">
          </div>
          <div>
            <div class="section-head">MAC (per auto-risoluzione factory password)</div>
            <input id="aMac" class="field-input" style="width:100%;"
                   placeholder="{T('Lascia vuoto se non pre-registrato')}" oninput="aLookupMac()">
            <div id="aMacNote" style="font-size:10px;color:var(--text3);margin-top:3px;"></div>
          </div>
          <div>
            <div class="section-head">{T("Hostname da impostare")}</div>
            <input id="aHostname" class="field-input" style="width:100%;" placeholder="router-sede-01">
          </div>
          <div>
            <div class="section-head">{T("Factory password (se non pre-registrata)")}</div>
            <input id="aFactoryPass" class="field-input" style="width:100%;" type="password"
                   placeholder="{T('Lascia vuoto se già registrata o non serve')}">
          </div>
          <div>
            <div class="section-head">{T("Template")}</div>
            <select id="aTplId" class="field-input" style="width:100%;"></select>
          </div>
          <div id="aExtraVarsWrap" style="display:none;">
            <div class="section-head">{T("Variabili extra")}</div>
            <div id="aExtraVars"></div>
          </div>
        </div>
        <div style="display:flex;gap:8px;margin-top:16px;">
          <button class="btn btn-primary" onclick="submitApply()">{T("Applica")}</button>
          <button class="btn" onclick="closeApplyModal()">{T("Annulla")}</button>
          <span id="aMsg" style="font-size:11px;color:var(--text3);align-self:center;margin-left:4px;"></span>
        </div>
        <div id="aProgress" style="margin-top:12px;display:none;">
          <div style="font-size:11px;color:var(--text3);">{T("Apply in corso…")}</div>
          <div id="aResults" style="margin-top:8px;font-size:11px;font-family:var(--mono);"></div>
        </div>
      </div>
    </div>
    
    <script>
    // ── Dati dal server ──────────────────────────────────────────────────────────
    const SITES_MAP  = {sites_js};
    const TPL_DATA   = {templates_js};
    const DEV_DATA   = {devices_js};
    const LOG_DATA   = {log_js};
    
    // ── State locale ─────────────────────────────────────────────────────────────
    let templates = {{}};   // id → template
    let selTplId  = null;   // template selezionato nell'editor
    
    // ── Tab switching ─────────────────────────────────────────────────────────────
    function switchTab(name) {{
      document.querySelectorAll('.tb-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      const idx = {{ tpl: 0, dev: 1, log: 2 }};
      document.querySelectorAll('.tb-btn')[idx[name]].classList.add('active');
      document.getElementById('tab-' + name).classList.add('active');
    }}
    
    // ── Populate siti nei select ─────────────────────────────────────────────────
    function populateSiteSelects() {{
      const opts = ['<option value="">— Nessuna sede —</option>'];
      Object.entries(SITES_MAP).forEach(([id, name]) => {{
        opts.push(`<option value="${{id}}">${{name}}</option>`);
      }});
      document.getElementById('regSite').innerHTML = opts.join('');
    }}
    
    // ══════════════════════════ TAB TEMPLATE ═════════════════════════════════════
    
    function renderTplList() {{
      const list = document.getElementById('tplList');
      const ids  = Object.keys(templates);
      if (!ids.length) {{
        list.innerHTML = '<div style="padding:16px;color:var(--text3);font-size:11px;">Nessun template.</div>';
        return;
      }}
      list.innerHTML = ids.map(id => {{
        const t    = templates[id];
        const site = t.site_id ? (SITES_MAP[t.site_id] || t.site_id) : 'Globale';
        const sel  = id === selTplId ? ' sel' : '';
        return `<div class="tpl-item${{sel}}" onclick="selectTemplate('${{id}}')" data-id="${{id}}">
          <div class="tpl-name">${{esc(t.name)}}</div>
          <div class="tpl-site">${{esc(site)}}</div>
        </div>`;
      }}).join('');
    }}
    
    function selectTemplate(id) {{
      selTplId = id;
      renderTplList();
      renderEditor(templates[id]);
    }}
    
    function newTemplate() {{
      selTplId = null;
      renderTplList();
      renderEditor(null);
    }}
    
    function renderEditor(tpl) {{
      const ed   = document.getElementById('tplEditor');
      const isNew = !tpl;
      const siteOpts = ['<option value="">— Globale —</option>'].concat(
        Object.entries(SITES_MAP).map(([id, n]) =>
          `<option value="${{id}}" ${{tpl && tpl.site_id===id ? 'selected' : ''}}>${{esc(n)}}</option>`)
      ).join('');
    
      const evars = tpl ? tpl.extra_vars || {{}} : {{}};
      const evarRows = Object.entries(evars).map(([k, v]) =>
        `<tr><td>${{esc(k)}}</td><td style="color:var(--text2);">${{esc(v)}}</td></tr>`
      ).join('');
    
      ed.innerHTML = `
        <div class="field-row">
          <span class="field-label">Nome</span>
          <input id="eName" class="field-input" value="${{esc(tpl ? tpl.name : '')}}"
                 placeholder="es. Config base sede">
        </div>
        <div class="field-row">
          <span class="field-label">Associa a sede</span>
          <select id="eSite" class="field-input">${{siteOpts}}</select>
        </div>
        <div>
          <div class="section-head" style="margin-bottom:6px;">Script RSC</div>
          <div style="font-size:10px;color:var(--text3);margin-bottom:6px;">
            Usa <code style="color:var(--accent2);">{{{{variabile}}}}</code> per i segnaposto.<br>
            Variabili auto: <code>ip</code> <code>mac</code> <code>hostname</code>
            <code>site_name</code> <code>site_id</code> <code>date</code><br>
            Variabili custom: dichiara <code># VAR:nome:default</code> in una riga di commento.
          </div>
          <textarea id="eScript" class="field-input"
                    style="min-height:300px;"
                    oninput="detectVars()"
                    placeholder="# VAR:ntp_server:pool.ntp.org&#10;/system identity set name={{{{hostname}}}}&#10;/system ntp client set enabled=yes servers={{{{ntp_server}}}}">${{esc(tpl ? tpl.script : '')}}</textarea>
        </div>
        <div>
          <div class="section-head">Variabili rilevate nello script</div>
          <div id="varChips" class="var-chips" style="margin-top:4px;"></div>
        </div>
        ${{evarRows ? `<div class="evars-wrap">
          <div class="section-head">Variabili extra dichiarate</div>
          <table class="evars-table" style="margin-top:4px;">
            <thead><tr><th>Nome</th><th>Default</th></tr></thead>
            <tbody>${{evarRows}}</tbody>
          </table>
        </div>` : ''}}
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button class="btn btn-primary" onclick="saveTemplate()">${{isNew ? 'Crea template' : 'Salva modifiche'}}</button>
          ${{!isNew ? `<button class="btn" style="color:var(--red);border-color:var(--red);" onclick="deleteTemplate('${{tpl.id}}')">Elimina</button>` : ''}}
          ${{!isNew ? `<button class="btn" onclick="openApplyModal('${{tpl.id}}')">▶ Applica ora…</button>` : ''}}
          <span id="edMsg" style="font-size:11px;color:var(--text3);align-self:center;"></span>
        </div>
      `;
      detectVars();
    }}
    
    const AUTO_VARS = ['ip','mac','hostname','site_name','site_id','date'];
    
    function detectVars() {{
      const script = document.getElementById('eScript')?.value || '';
      const found  = [...new Set([...script.matchAll(/\{{{{(\w+)\}}}}/g)].map(m => m[1]))];
      const chips  = document.getElementById('varChips');
      if (!chips) return;
      chips.innerHTML = found.map(v => {{
        const cls = AUTO_VARS.includes(v) ? 'var-auto' : 'var-custom';
        const lbl = AUTO_VARS.includes(v) ? 'auto' : 'custom';
        return `<span class="var-chip ${{cls}}">{{{{${{v}}}}}} <span style="opacity:.6;font-weight:400;">${{lbl}}</span></span>`;
      }}).join('') || '<span style="color:var(--text3);font-size:11px;">Nessuna variabile rilevata.</span>';
    }}
    
    async function saveTemplate() {{
      const name   = document.getElementById('eName')?.value.trim();
      const site   = document.getElementById('eSite')?.value;
      const script = document.getElementById('eScript')?.value;
      const msg    = document.getElementById('edMsg');
      if (!name)   {{ msg.textContent = 'Nome obbligatorio.'; return; }}
      if (!script) {{ msg.textContent = 'Script vuoto.'; return; }}
    
      // Estrai variabili custom (# VAR:nome:default)
      const extra_vars = {{}};
      for (const line of script.split('\\n')) {{
        const m = line.match(/^\\s*#\\s*VAR\\s*:\\s*(\\w+)\\s*:\\s*(.*)/);
        if (m && !AUTO_VARS.includes(m[1].trim())) {{
          extra_vars[m[1].trim()] = m[2].trim();
        }}
      }}
    
      msg.textContent = 'Salvataggio…';
      const fd = new FormData();
      fd.append('id',          selTplId || '');
      fd.append('name',        name);
      fd.append('site_id',     site);
      fd.append('script',      script);
      fd.append('extra_vars',  JSON.stringify(extra_vars));
    
      const r  = await fetch('/api/ztp/template/save', {{ method: 'POST', body: fd }});
      const j  = await r.json();
      if (j.ok) {{
        msg.style.color = 'var(--green)';
        msg.textContent = 'Salvato.';
        templates[j.id] = j.template;
        selTplId = j.id;
        renderTplList();
        setTimeout(() => {{ msg.textContent = ''; msg.style.color = 'var(--text3)'; }}, 2000);
      }} else {{
        msg.style.color = 'var(--red)'; msg.textContent = j.msg;
      }}
    }}
    
    async function deleteTemplate(id) {{
      if (!confirm('Eliminare questo template?')) return;
      const fd = new FormData(); fd.append('id', id);
      const r  = await fetch('/api/ztp/template/delete', {{ method: 'POST', body: fd }});
      const j  = await r.json();
      if (j.ok) {{
        delete templates[id];
        selTplId = null;
        renderTplList();
        document.getElementById('tplEditor').innerHTML =
          '<div style="color:var(--text3);font-size:12px;padding:20px;text-align:center;">Template eliminato.</div>';
      }}
    }}
    
    // ══════════════════════════ TAB DISPOSITIVI ════════════════════════════════
    
    let devices = [];  // array locale
    
    function renderDevTable() {{
      const tbody = document.getElementById('devTbody');
      const badge = document.getElementById('devBadge');
      badge.textContent = devices.length ? `(${{devices.length}})` : '';
      if (!devices.length) {{
        tbody.innerHTML = '<tr><td colspan="7" style="color:var(--text3);padding:16px;">Nessun dispositivo pre-registrato.</td></tr>';
        return;
      }}
      tbody.innerHTML = devices.map(d => {{
        const site    = d.site_id ? (SITES_MAP[d.site_id] || d.site_id) : '—';
        const applied = d.applied
          ? `<span class="pill pill-green">✓ ${{d.applied_at ? d.applied_at.slice(0,10) : 'sì'}}</span>`
          : `<span class="pill pill-gray">—</span>`;
        return `<tr>
          <td style="font-family:var(--mono);color:var(--accent2);">${{esc(d.mac)}}</td>
          <td>${{esc(d.hostname_hint || '—')}}</td>
          <td>${{esc(site)}}</td>
          <td style="color:var(--text3);">${{esc(d.note || '—')}}</td>
          <td style="color:var(--text3);">${{d.registered_at ? d.registered_at.slice(0,10) : '—'}}</td>
          <td>${{applied}}</td>
          <td>
            <button class="btn" style="padding:3px 8px;font-size:10px;color:var(--red);border-color:var(--red);"
                    onclick="removeDevice('${{esc(d.mac)}}')">Rimuovi</button>
          </td>
        </tr>`;
      }}).join('');
    }}
    
    function regMacInput(el) {{
      const mac_n = el.value.replace(/[^0-9a-fA-F]/g,'');
      const note  = document.getElementById('regMacNote');
      if (mac_n.length === 12) {{
        const fmt = mac_n.match(/.{{2}}/g).join(':').toUpperCase();
        const dup = devices.find(d => d.mac === fmt);
        note.style.color = dup ? 'var(--yellow)' : 'var(--green)';
        note.textContent = dup ? '⚠ Già registrato — salva per aggiornare.' : '✓ MAC valido';
      }} else {{
        note.textContent = '';
      }}
    }}
    
    async function registerDevice() {{
      const mac  = document.getElementById('regMac').value.trim();
      const pass = document.getElementById('regPass').value;
      const host = document.getElementById('regHostname').value.trim();
      const site = document.getElementById('regSite').value;
      const note = document.getElementById('regNote').value.trim();
      const msg  = document.getElementById('regMsg');
    
      if (!mac)  {{ msg.style.color='var(--red)'; msg.textContent='MAC obbligatorio.'; return; }}
      if (!pass) {{ msg.style.color='var(--red)'; msg.textContent='Factory password obbligatoria.'; return; }}
    
      msg.style.color='var(--text3)'; msg.textContent='Registrazione…';
      const fd = new FormData();
      fd.append('mac', mac); fd.append('factory_pass', pass);
      fd.append('hostname_hint', host); fd.append('site_id', site); fd.append('note', note);
    
      const r = await fetch('/api/ztp/device/register', {{ method: 'POST', body: fd }});
      const j = await r.json();
      if (j.ok) {{
        msg.style.color='var(--green)'; msg.textContent='✓ Registrato: ' + j.mac;
        // Aggiorna locale
        const existing = devices.findIndex(d => d.mac === j.mac);
        const entry = {{ mac: j.mac, hostname_hint: host, site_id: site, note, registered_at: new Date().toISOString().slice(0,10), applied: false, applied_at: '' }};
        if (existing >= 0) devices[existing] = entry; else devices.push(entry);
        renderDevTable();
        // Reset form
        ['regMac','regPass','regHostname','regNote'].forEach(id => document.getElementById(id).value = '');
        document.getElementById('regSite').value = '';
        document.getElementById('regMacNote').textContent = '';
      }} else {{
        msg.style.color='var(--red)'; msg.textContent=j.msg;
      }}
    }}
    
    async function removeDevice(mac) {{
      if (!confirm(`Rimuovere il dispositivo ${{mac}}?`)) return;
      const fd = new FormData(); fd.append('mac', mac);
      const r  = await fetch('/api/ztp/device/remove', {{ method: 'POST', body: fd }});
      const j  = await r.json();
      if (j.ok) {{
        devices = devices.filter(d => d.mac !== mac);
        renderDevTable();
      }}
    }}
    
    // ══════════════════════════ TAB LOG ═════════════════════════════════════════
    
    function renderLog() {{
      const tbody = document.getElementById('logTbody');
      if (!LOG_DATA.length) return;
      tbody.innerHTML = LOG_DATA.map(e => `
        <tr>
          <td style="color:var(--text3);white-space:nowrap;">${{esc(e.ts)}}</td>
          <td style="color:var(--accent2);">${{esc(e.ip)}}</td>
          <td>${{esc(e.hostname || '—')}}</td>
          <td style="color:var(--text2);">${{esc(e.template_name)}}</td>
          <td>${{e.ok ? '<span class="ok-dot">OK</span>' : '<span class="err-dot">ERR</span>'}}</td>
          <td style="color:var(--text3);max-width:280px;word-break:break-all;">${{esc(e.msg)}}</td>
        </tr>`).join('');
    }}
    
    // ══════════════════════════ APPLY MODAL ══════════════════════════════════════
    
    function openApplyModal(tplId) {{
      // Popola select template
      const sel = document.getElementById('aTplId');
      sel.innerHTML = Object.values(templates).map(t =>
        `<option value="${{t.id}}" ${{t.id===tplId?'selected':''}}>${{esc(t.name)}}</option>`
      ).join('');
      sel.onchange = () => updateExtraVarsForm();
      updateExtraVarsForm();
      document.getElementById('applyModal').style.display = 'flex';
      document.getElementById('aProgress').style.display = 'none';
      document.getElementById('aResults').innerHTML = '';
      document.getElementById('aMsg').textContent = '';
    }}
    
    function closeApplyModal() {{
      document.getElementById('applyModal').style.display = 'none';
    }}
    
    function aLookupMac() {{
      const mac   = document.getElementById('aMac').value.trim();
      const note  = document.getElementById('aMacNote');
      const digits = mac.replace(/[^0-9a-fA-F]/g,'');
      if (digits.length === 12) {{
        const fmt = digits.match(/.{{2}}/g).join(':').toUpperCase();
        const dev = devices.find(d => d.mac === fmt);
        if (dev) {{
          note.style.color = 'var(--green)';
          note.textContent = `✓ Pre-registrato — factory password disponibile${{dev.hostname_hint ? ' · hint: '+dev.hostname_hint : ''}}`;
          if (dev.hostname_hint && !document.getElementById('aHostname').value)
            document.getElementById('aHostname').value = dev.hostname_hint;
        }} else {{
          note.style.color = 'var(--yellow)';
          note.textContent = '⚠ Non pre-registrato — inserisci la factory password manualmente';
        }}
      }} else {{
        note.textContent = '';
      }}
    }}
    
    function updateExtraVarsForm() {{
      const tplId = document.getElementById('aTplId').value;
      const tpl   = templates[tplId];
      const wrap  = document.getElementById('aExtraVarsWrap');
      const cnt   = document.getElementById('aExtraVars');
      if (!tpl || !tpl.extra_vars || !Object.keys(tpl.extra_vars).length) {{
        wrap.style.display = 'none'; return;
      }}
      wrap.style.display = 'block';
      cnt.innerHTML = Object.entries(tpl.extra_vars).map(([k, dflt]) => `
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
          <span style="font-family:var(--mono);color:var(--accent2);font-size:11px;min-width:120px;">{{{{${{k}}}}}}</span>
          <input class="field-input" style="flex:1;" id="ev_${{k}}" value="${{esc(dflt)}}"
                 placeholder="${{dflt}}">
        </div>`).join('');
    }}
    
    async function submitApply() {{
      const ip      = document.getElementById('aIp').value.trim();
      const mac     = document.getElementById('aMac').value.trim();
      const host    = document.getElementById('aHostname').value.trim();
      const fpass   = document.getElementById('aFactoryPass').value;
      const tplId   = document.getElementById('aTplId').value;
      const msg     = document.getElementById('aMsg');
      const prog    = document.getElementById('aProgress');
      const res     = document.getElementById('aResults');
    
      if (!ip)    {{ msg.style.color='var(--red)'; msg.textContent='IP obbligatorio.'; return; }}
      if (!tplId) {{ msg.style.color='var(--red)'; msg.textContent='Seleziona un template.'; return; }}
    
      // Raccogli variabili extra
      const tpl   = templates[tplId];
      const evars = {{}};
      if (tpl && tpl.extra_vars) {{
        Object.keys(tpl.extra_vars).forEach(k => {{
          const el = document.getElementById('ev_' + k);
          if (el) evars[k] = el.value;
        }});
      }}
    
      msg.style.color='var(--text3)'; msg.textContent='Avvio apply…';
      const fd = new FormData();
      fd.append('ip',           ip);
      fd.append('mac',          mac);
      fd.append('hostname',     host);
      fd.append('template_id',  tplId);
      fd.append('factory_pass', fpass);
      fd.append('extra_vars',   JSON.stringify(evars));
    
      const r  = await fetch('/api/ztp/apply', {{ method: 'POST', body: fd }});
      const j  = await r.json();
      if (!j.ok) {{ msg.style.color='var(--red)'; msg.textContent=j.msg; return; }}
    
      msg.textContent = '';
      prog.style.display = 'block';
      res.innerHTML = '<span style="color:var(--text3);">In corso…</span>';
    
      // Poll job
      const jobId  = j.job_id;
      let   done   = false;
      while (!done) {{
        await new Promise(r => setTimeout(r, 800));
        const pr = await fetch('/api/job?id=' + jobId);
        const pj = await pr.json();
        if (pj.done >= pj.total) {{
          done = true;
          const row = pj.results[0] || {{}};
          const ok  = row.ok;
          res.innerHTML = `<span style="color:${{ok?'var(--green)':'var(--red)'}};">
            ${{ok ? '✓ OK' : '✗ Errore'}} — ${{esc(row.msg || '')}}
          </span>`;
          msg.style.color = ok ? 'var(--green)' : 'var(--red)';
          msg.textContent = ok ? 'Completato.' : 'Errore.';
        }}
      }}
    }}
    
    // ══════════════════════════ INIT ═════════════════════════════════════════════
    
    function esc(s) {{
      return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }}
    
    (function init() {{
      // Carica templates
      TPL_DATA.forEach(t => {{ templates[t.id] = t; }});
      renderTplList();
      // Carica devices
      devices = DEV_DATA;
      renderDevTable();
      populateSiteSelects();
      // Carica log
      renderLog();
    }})();
    </script>
    """
    
        # Nota: in integrazione usa self._page_shell(...)
        # return self._page_shell("Provisioning", content, session, page_key="provision")
        return self._page_shell("Provisioning", content, session=session, page_key="provision")

    def render_site_scan_page(self, session=None):
        """
        Pagina Site Auto-Scan — configura subnet e scansione automatica per sede.
        In integrazione: self._page_shell("Site Auto-Scan", content, session, page_key="topology")
        """
        sites_js = json.dumps({
            sid: {
                "id":               sid,
                "name":             s.get("name", sid),
                "city":             s.get("city", ""),
                "scan_subnet":      s.get("scan_subnet", ""),
                "scan_interval":    s.get("scan_interval", 0),
                "scan_auto_add":    s.get("scan_auto_add", False),
                "scan_status":      s.get("scan_status", "idle"),
                "scan_last_run":    s.get("scan_last_run", ""),
                "scan_next_run":    s.get("scan_next_run", ""),
                "scan_last_found":  s.get("scan_last_found", 0),
                "scan_last_added":  s.get("scan_last_added", 0),
                "scan_last_error":  s.get("scan_last_error", ""),
                "scan_job_id":      s.get("scan_job_id", ""),
            }
            for sid, s in sorted(SITES.items(), key=lambda x: x[1].get("name", ""))
        })
    
        content = f"""
    <style>
    .ss-header {{
      display:flex; align-items:center; justify-content:space-between;
      flex-wrap:wrap; gap:10px; margin-bottom:18px;
    }}
    .ss-title {{ font-size:14px; font-weight:700; color:var(--text); }}
    .ss-subtitle {{ font-size:11px; color:var(--text3); margin-top:2px; }}
    .ss-grid {{
      display:grid;
      grid-template-columns:repeat(auto-fill, minmax(340px, 1fr));
      gap:14px;
    }}
    .ss-card {{
      background:var(--bg2); border:1.5px solid var(--border);
      border-radius:var(--r3); padding:16px; display:flex; flex-direction:column; gap:12px;
      transition:box-shadow .15s;
    }}
    .ss-card:hover {{ box-shadow:var(--shadow); }}
    .ss-card-head {{
      display:flex; align-items:center; justify-content:space-between; gap:8px;
    }}
    .ss-site-name {{ font-weight:700; font-size:13px; color:var(--text); }}
    .ss-site-city {{ font-size:10px; color:var(--text3); margin-top:1px; }}
    .ss-status-pill {{
      display:inline-flex; align-items:center; gap:5px;
      padding:3px 9px; border-radius:20px; font-size:10px; font-weight:700;
    }}
    .st-idle    {{ background:var(--bg3); color:var(--text3); border:1px solid var(--border2); }}
    .st-running {{ background:rgba(217,119,6,.12); color:var(--yellow); border:1px solid rgba(217,119,6,.3); }}
    .st-done    {{ background:rgba(22,163,74,.10); color:var(--green); border:1px solid rgba(22,163,74,.25); }}
    .st-error   {{ background:rgba(220,38,38,.08); color:var(--red);   border:1px solid rgba(220,38,38,.22); }}
    .ss-row {{
      display:grid; grid-template-columns:1fr 1fr; gap:8px;
    }}
    .ss-field {{ display:flex; flex-direction:column; gap:4px; }}
    .ss-label {{
      font-size:10px; font-weight:700; color:var(--text3);
      text-transform:uppercase; letter-spacing:.7px;
    }}
    .ss-input {{
      padding:6px 9px; font-size:11px; width:100%;
      border:1px solid var(--border2); border-radius:var(--r);
      background:var(--bg3); color:var(--text); font-family:var(--mono);
      transition:border-color .15s;
    }}
    .ss-input:focus {{ outline:none; border-color:var(--accent2); }}
    .ss-toggle-row {{
      display:flex; align-items:center; gap:8px;
    }}
    .ss-toggle-label {{ font-size:11px; color:var(--text2); }}
    .ss-info-row {{
      display:flex; gap:14px; flex-wrap:wrap;
      font-size:10px; color:var(--text3); border-top:1px solid var(--border);
      padding-top:8px;
    }}
    .ss-info-item {{ display:flex; flex-direction:column; gap:2px; }}
    .ss-info-val {{ color:var(--text2); font-weight:600; }}
    .ss-actions {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
    .ss-msg {{ font-size:11px; color:var(--text3); }}
    .ss-results {{
      font-size:11px; font-family:var(--mono);
      background:var(--bg3); border-radius:var(--r); padding:8px 10px;
      color:var(--text2); border:1px solid var(--border);
      display:none;
    }}
    .ss-results.visible {{ display:block; }}
    .ss-empty {{
      text-align:center; padding:48px 24px; color:var(--text3);
      font-size:12px;
    }}
    /* spinner */
    @keyframes ss-spin {{ to {{ transform:rotate(360deg); }} }}
    .ss-spinner {{
      display:inline-block; width:10px; height:10px;
      border:2px solid rgba(217,119,6,.3); border-top-color:var(--yellow);
      border-radius:50%; animation:ss-spin .8s linear infinite;
    }}
    </style>
    
    <div class="ss-header">
      <div>
        <div class="ss-title">Site Auto-Scan</div>
        <div class="ss-subtitle">
          Assegna una subnet a ogni sede — ROSM la scansiona automaticamente e
          aggiunge i router MikroTik trovati.
          <a href="/provision" style="margin-left:12px;font-size:10px;">← ZTP Provisioning</a>
        </div>
      </div>
    </div>
    
    <div id="ssGrid" class="ss-grid">
      <div class="ss-empty" id="ssEmpty" style="display:none;">
        Nessuna sede configurata.<br>
        <span style="font-size:10px;">Crea le sedi nel Site Manager di ROSM prima di configurare la scansione.</span>
      </div>
    </div>
    
    <script>
    const SITES_DATA = {sites_js};
    let sitesMap = {{}};
    
    const INTERVALS = [
      [0,   "Disabilitata"],
      [5,   "ogni 5 minuti"],
      [15,  "ogni 15 minuti"],
      [30,  "ogni 30 minuti"],
      [60,  "ogni ora"],
      [120, "ogni 2 ore"],
      [360, "ogni 6 ore"],
      [720, "ogni 12 ore"],
      [1440,"ogni 24 ore"],
    ];
    
    function esc(s) {{
      return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }}
    
    function statusPill(st, err) {{
      const map = {{
        idle:    ['st-idle',    '○ Inattiva'],
        running: ['st-running', '<span class="ss-spinner"></span> In corso…'],
        done:    ['st-done',    '✓ Completata'],
        error:   ['st-error',   '✗ Errore'],
      }};
      const [cls, label] = map[st] || map.idle;
      const tip = (st === 'error' && err) ? ` title="${{esc(err)}}"` : '';
      return `<span class="ss-status-pill ${{cls}}"${{tip}}>${{label}}</span>`;
    }}
    
    function intervalOpts(current) {{
      return INTERVALS.map(([v, l]) =>
        `<option value="${{v}}" ${{v===current?'selected':''}}>${{l}}</option>`
      ).join('');
    }}
    
    function renderCard(s) {{
      const found   = s.scan_last_found  ?? 0;
      const added   = s.scan_last_added  ?? 0;
      const lastRun = s.scan_last_run  || '—';
      const nextRun = s.scan_next_run  || '—';
      const isRunning = s.scan_status === 'running';
    
      return `
      <div class="ss-card" id="card-${{s.id}}">
        <div class="ss-card-head">
          <div>
            <div class="ss-site-name">${{esc(s.name)}}</div>
            ${{s.city ? `<div class="ss-site-city">${{esc(s.city)}}</div>` : ''}}
          </div>
          ${{statusPill(s.scan_status, s.scan_last_error)}}
        </div>
    
        <div class="ss-row">
          <div class="ss-field">
            <span class="ss-label">Subnet CIDR</span>
            <input class="ss-input" id="subnet-${{s.id}}"
                   value="${{esc(s.scan_subnet)}}"
                   placeholder="es. 10.0.1.0/24">
          </div>
          <div class="ss-field">
            <span class="ss-label">Scansione automatica</span>
            <select class="ss-input" id="itvl-${{s.id}}">
              ${{intervalOpts(s.scan_interval)}}
            </select>
          </div>
        </div>
    
        <div class="ss-toggle-row">
          <input type="checkbox" id="autoadd-${{s.id}}" ${{s.scan_auto_add ? 'checked' : ''}}>
          <label class="ss-toggle-label" for="autoadd-${{s.id}}">
            Auto-aggiungi i router MikroTik trovati a questa sede
          </label>
        </div>
    
        <div class="ss-info-row">
          <div class="ss-info-item">
            <span>Ultima scansione</span>
            <span class="ss-info-val" id="lastrun-${{s.id}}">${{lastRun}}</span>
          </div>
          <div class="ss-info-item">
            <span>Prossima</span>
            <span class="ss-info-val" id="nextrun-${{s.id}}">${{nextRun}}</span>
          </div>
          <div class="ss-info-item">
            <span>MikroTik trovati</span>
            <span class="ss-info-val" id="found-${{s.id}}">${{found}}</span>
          </div>
          <div class="ss-info-item">
            <span>Auto-aggiunti</span>
            <span class="ss-info-val" id="added-${{s.id}}">${{added}}</span>
          </div>
        </div>
    
        <div class="ss-actions">
          <button class="btn btn-primary" onclick="saveConfig('${{s.id}}')">Salva</button>
          <button class="btn" id="scanbtn-${{s.id}}"
                  onclick="scanNow('${{s.id}}')"
                  ${{isRunning ? 'disabled' : ''}}>
            ${{isRunning ? '⏳ Scansione…' : '▶ Scan ora'}}
          </button>
          <span class="ss-msg" id="msg-${{s.id}}"></span>
        </div>
    
        <div class="ss-results" id="results-${{s.id}}"></div>
      </div>`;
    }}
    
    function renderAll() {{
      const grid    = document.getElementById('ssGrid');
      const empty   = document.getElementById('ssEmpty');
      const ids     = Object.keys(SITES_DATA);
      if (!ids.length) {{
        empty.style.display = 'block';
        return;
      }}
      ids.forEach(sid => {{
        sitesMap[sid] = SITES_DATA[sid];
        const div = document.createElement('div');
        div.innerHTML = renderCard(SITES_DATA[sid]);
        grid.appendChild(div.firstElementChild);
      }});
    }}
    
    async function saveConfig(sid) {{
      const subnet   = document.getElementById(`subnet-${{sid}}`).value.trim();
      const interval = parseInt(document.getElementById(`itvl-${{sid}}`).value);
      const autoAdd  = document.getElementById(`autoadd-${{sid}}`).checked;
      const msg      = document.getElementById(`msg-${{sid}}`);
      msg.style.color = 'var(--text3)';
      msg.textContent = 'Salvataggio…';
    
      const fd = new FormData();
      fd.append('sid',      sid);
      fd.append('subnet',   subnet);
      fd.append('interval', interval);
      fd.append('auto_add', autoAdd ? '1' : '0');
    
      const r = await fetch('/api/site_scan/config', {{ method:'POST', body:fd }});
      const j = await r.json();
      if (j.ok) {{
        msg.style.color = 'var(--green)';
        msg.textContent = '✓ Salvato';
        // Aggiorna next_run locale
        document.getElementById(`nextrun-${{sid}}`).textContent = j.next_run || '—';
        setTimeout(() => {{ msg.textContent = ''; }}, 2500);
      }} else {{
        msg.style.color = 'var(--red)';
        msg.textContent = j.msg;
      }}
    }}
    
    async function scanNow(sid) {{
      const msg = document.getElementById(`msg-${{sid}}`);
      const btn = document.getElementById(`scanbtn-${{sid}}`);
      msg.style.color = 'var(--text3)';
      msg.textContent = 'Avvio…';
      btn.disabled = true;
      btn.textContent = '⏳ Scansione…';
    
      const fd = new FormData();
      fd.append('sid', sid);
      const r = await fetch('/api/site_scan/now', {{ method:'POST', body:fd }});
      const j = await r.json();
    
      if (!j.ok) {{
        msg.style.color = 'var(--red)';
        msg.textContent = j.msg;
        btn.disabled = false;
        btn.textContent = '▶ Scan ora';
        return;
      }}
      msg.textContent = '';
      // Aggiorna status badge e inizia polling
      updateCardStatus(sid, 'running', '');
      if (j.job_id) pollScan(sid, j.job_id);
    }}
    
    function updateCardStatus(sid, status, err) {{
      const card = document.getElementById(`card-${{sid}}`);
      if (!card) return;
      const pill = card.querySelector('.ss-status-pill');
      const map = {{
        idle:    ['st-idle',    '○ Inattiva'],
        running: ['st-running', '<span class="ss-spinner"></span> In corso…'],
        done:    ['st-done',    '✓ Completata'],
        error:   ['st-error',   '✗ Errore'],
      }};
      const [cls, label] = map[status] || map.idle;
      pill.className = `ss-status-pill ${{cls}}`;
      pill.innerHTML = label;
      if (status === 'error' && err) pill.title = err;
      else pill.removeAttribute('title');
    }}
    
    async function pollScan(sid, jobId) {{
      const results = document.getElementById(`results-${{sid}}`);
      results.classList.add('visible');
      results.textContent = 'Scansione in corso…';
    
      for (let i = 0; i < 200; i++) {{
        await new Promise(r => setTimeout(r, 2000));
        // Leggi stato sito (non job, così abbiamo anche last_found ecc.)
        const r = await fetch(`/api/site_scan/status?sid=${{sid}}`);
        const j = await r.json();
        const s = j.site || {{}};
    
        if (s.scan_status === 'running') {{
          // Aggiorna progresso dal job
          if (jobId) {{
            const jr = await fetch(`/api/scan_job?id=${{jobId}}`);
            const jj = await jr.json();
            const done  = jj.done  ?? 0;
            const total = jj.total ?? 0;
            const pct   = total ? Math.round(done/total*100) : 0;
            results.textContent = `Scansione: ${{done}}/${{total}} IP (${{pct}}%)`;
          }}
          continue;
        }}
    
        // Scansione terminata
        updateCardStatus(sid, s.scan_status, s.scan_last_error);
        document.getElementById(`lastrun-${{sid}}`).textContent = s.scan_last_run || '—';
        document.getElementById(`nextrun-${{sid}}`).textContent = s.scan_next_run || '—';
        document.getElementById(`found-${{sid}}`).textContent   = s.scan_last_found ?? 0;
        document.getElementById(`added-${{sid}}`).textContent   = s.scan_last_added ?? 0;
    
        const btn = document.getElementById(`scanbtn-${{sid}}`);
        btn.disabled    = false;
        btn.textContent = '▶ Scan ora';
    
        if (s.scan_status === 'done') {{
          const f = s.scan_last_found ?? 0;
          const a = s.scan_last_added ?? 0;
          results.innerHTML = `<span style="color:var(--green);">✓ Scansione completata — `+
            `${{f}} MikroTik trovati` + (a ? `, ${{a}} aggiunti al sito` : '') + `.</span>`;
        }} else if (s.scan_status === 'error') {{
          results.innerHTML = `<span style="color:var(--red);">✗ ${{esc(s.scan_last_error)}}</span>`;
        }}
        break;
      }}
    }}
    
    renderAll();
    
    // Avvia polling automatico per siti già in running al caricamento pagina
    Object.values(SITES_DATA).forEach(s => {{
      if (s.scan_status === 'running' && s.scan_job_id) {{
        pollScan(s.id, s.scan_job_id);
      }}
    }});
    </script>
    """
        return self._page_shell("Site Auto-Scan", content, session=session, page_key="site-scan")

    def handle_site_scan_post(self, path: str, form):
        """
        Dispatcher POST per le API Site Auto-Scan.
        In integrazione:
            if post_path.startswith("/api/site_scan/"):
                return _ztp.handle_site_scan_post(self, post_path, form)
        """
        if path == "/api/site_scan/config":
            sid      = form.getvalue("sid", "").strip()
            subnet   = form.getvalue("subnet", "").strip()
            interval = form.getvalue("interval", "0")
            auto_add = form.getvalue("auto_add", "0") == "1"
            if not sid:
                return self._json({"ok": False, "msg": "sid mancante"})
            try:
                interval = int(interval)
            except ValueError:
                interval = 0
            ok, err = site_scan_configure(sid, subnet, interval, auto_add)
            if not ok:
                return self._json({"ok": False, "msg": err})
            next_run = SITES.get(sid, {}).get("scan_next_run", "")
            return self._json({"ok": True, "next_run": next_run})
    
        if path == "/api/site_scan/now":
            sid = form.getvalue("sid", "").strip()
            if not sid:
                return self._json({"ok": False, "msg": "sid mancante"})
            ok, result = _launch_site_scan(sid, manual=True)
            if not ok:
                return self._json({"ok": False, "msg": result})
            return self._json({"ok": True, "job_id": result})
    
        return self._json({"ok": False, "msg": "Path non riconosciuto"})

    def handle_site_scan_get(self, sid: str):
        """GET /api/site_scan/status?sid= — restituisce lo stato attuale del sito."""
        site = SITES.get(sid, {})
        return self._json({"ok": True, "site": {
            "scan_status":     site.get("scan_status", "idle"),
            "scan_last_run":   site.get("scan_last_run", ""),
            "scan_next_run":   site.get("scan_next_run", ""),
            "scan_last_found": site.get("scan_last_found", 0),
            "scan_last_added": site.get("scan_last_added", 0),
            "scan_last_error": site.get("scan_last_error", ""),
            "scan_job_id":     site.get("scan_job_id", ""),
        }})

    def handle_ztp_post(self, path: str, form):
        """
        Dispatcher per le API ZTP. In integrazione:
            if path.startswith("/api/ztp/"):
                return self.respond(handle_ztp_post(self, path, form))
        """
    
        # ── Salva / aggiorna template ─────────────────────────────────────────────
        if path == "/api/ztp/template/save":
            tid        = form.getvalue("id", "").strip()
            name       = form.getvalue("name", "").strip()
            site_id    = form.getvalue("site_id", "").strip()
            script     = form.getvalue("script", "").strip()
            extra_raw  = form.getvalue("extra_vars", "{}")
    
            if not name:
                return self._json({"ok": False, "msg": "Nome obbligatorio"})
            if not script:
                return self._json({"ok": False, "msg": "Script vuoto"})
    
            try:
                extra_vars = json.loads(extra_raw)
            except Exception:
                extra_vars = {}
    
            new_id = ztp_template_save(tid, name, site_id, script, extra_vars)
            return self._json({"ok": True, "id": new_id, "template": ZTP_TEMPLATES[new_id]})
    
        # ── Elimina template ──────────────────────────────────────────────────────
        if path == "/api/ztp/template/delete":
            tid = form.getvalue("id", "").strip()
            if not tid:
                return self._json({"ok": False, "msg": "ID mancante"})
            ok = ztp_template_delete(tid)
            return self._json({"ok": ok, "msg": "" if ok else "Template non trovato"})
    
        # ── Pre-registra dispositivo ──────────────────────────────────────────────
        if path == "/api/ztp/device/register":
            mac          = form.getvalue("mac", "").strip()
            factory_pass = form.getvalue("factory_pass", "")
            hostname     = form.getvalue("hostname_hint", "").strip()
            site_id      = form.getvalue("site_id", "").strip()
            cred_id      = form.getvalue("cred_id", "").strip()
            note         = form.getvalue("note", "").strip()
    
            ok, result = ztp_device_register(mac, hostname, factory_pass, site_id, cred_id, note)
            return self._json({"ok": ok, "mac": result if ok else "", "msg": "" if ok else result})
    
        # ── Rimuovi dispositivo pre-registrato ────────────────────────────────────
        if path == "/api/ztp/device/remove":
            mac = form.getvalue("mac", "").strip()
            ok  = ztp_device_remove(mac)
            return self._json({"ok": ok, "msg": "" if ok else "Dispositivo non trovato"})
    
        # ── Avvia apply ───────────────────────────────────────────────────────────
        if path == "/api/ztp/apply":
            ip           = form.getvalue("ip", "").strip()
            mac          = form.getvalue("mac", "").strip()
            hostname     = form.getvalue("hostname", "").strip()
            template_id  = form.getvalue("template_id", "").strip()
            factory_pass = form.getvalue("factory_pass", "")
            cred_id      = form.getvalue("cred_id", "").strip()
            extra_raw    = form.getvalue("extra_vars", "{}")
    
            if not ip:
                return self._json({"ok": False, "msg": "IP mancante"})
            if not template_id or template_id not in ZTP_TEMPLATES:
                return self._json({"ok": False, "msg": "Template non valido"})
    
            try:
                extra_overrides = json.loads(extra_raw)
            except Exception:
                extra_overrides = {}
    
            # Se il MAC è pre-registrato, usa la factory password archiviata
            if mac and not factory_pass:
                dev = _ztp_find_device_by_mac(mac)
                if dev:
                    factory_pass = _decrypt(dev.get("factory_pass_enc", ""))
                    if not cred_id:
                        cred_id = dev.get("cred_id", "")
    
            job_id = ztp_apply(ip, mac, hostname, template_id,
                               extra_overrides, factory_pass, cred_id)
            return self._json({"ok": True, "job_id": job_id})
    
        return self._json({"ok": False, "msg": "Path non riconosciuto"})

    def render_stats_page(self, session=None):
        """Server-side rendered stats — comprehensive, no async JS."""
        rs = ROUTERS
        import re as _re, math as _math
        from collections import Counter
        from datetime import datetime as _dt

        # ── Counters ─────────────────────────────────────────────────────────
        total        = len(rs)
        online       = sum(1 for r in rs if r.get("status") == "ONLINE")
        offline      = total - online
        online_pct   = round(online / total * 100, 1) if total else 0
        with_info    = sum(1 for r in rs if r.get("name"))
        n_sites      = len(SITES)
        n_creds      = len(CRED_SETS)
        bk_files     = backup_list_files()
        bk_idx       = backup_index_by_router()
        backed_up    = sum(1 for r in rs if router_has_backup(r, bk_idx))
        ts           = _dt.now().strftime("%H:%M:%S")
        last_bk      = BACKUP_CONFIG.get("last_run", "—")

        PALETTE = ["#4f8ef7","#2adf8a","#f7c44f","#f74f6a","#9b7ef7",
                   "#f78a4f","#4fd4f7","#df2a7e","#7ef7b8","#f7f74f"]

        # ── Helpers ───────────────────────────────────────────────────────────
        def kpi(val, label, sub="", col="var(--text)", icon=""):
            return (f'<div class="kpi">'
                    f'<div class="kpi-icon">{icon}</div>'
                    f'<div class="kpi-val" style="color:{col}">{val}</div>'
                    f'<div class="kpi-label">{label}</div>'
                    f'<div class="kpi-sub">{sub}</div></div>')

        def bar_chart(data, palette, label_width=120):
            if not data:
                return f'<div style="color:var(--text3);font-size:11px;padding:8px 0;">{T("Nessun dato disponibile.")}</div>'
            mx = max(v for _, v in data)
            rows = ""
            for i, (k, v) in enumerate(data):
                pct = round(v / mx * 100, 1) if mx else 0
                col = palette[i % len(palette)]
                rows += (f'<div class="bar-row">'
                         f'<span class="bar-label" style="min-width:{label_width}px" title="{k}">{k}</span>'
                         f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{col}"></div></div>'
                         f'<span class="bar-count">{v}</span></div>')
            return rows

        def donut(slices):
            total_v = sum(v for _, v, _ in slices)
            if not total_v:
                return f'<div style="color:var(--text3);font-size:11px;padding:8px 0;">{T("Nessun dato disponibile.")}</div>'
            cx = cy = 60; r = 50; cum = 0; paths = ""
            for _, v, col in slices:
                pct = v / total_v
                a0  = cum * 2 * _math.pi - _math.pi / 2
                a1  = (cum + pct) * 2 * _math.pi - _math.pi / 2
                cum += pct
                x0, y0 = cx + r * _math.cos(a0), cy + r * _math.sin(a0)
                x1, y1 = cx + r * _math.cos(a1), cy + r * _math.sin(a1)
                paths += (f'<path d="M {cx} {cy} L {x0:.1f} {y0:.1f} '
                          f'A {r} {r} 0 {1 if pct > .5 else 0} 1 {x1:.1f} {y1:.1f} Z" '
                          f'fill="{col}" opacity=".85"/>')
            legend = ""
            for label, v, col in slices:
                pct_s = f"{v / total_v * 100:.1f}"
                legend += (f'<div class="donut-leg-item"><div class="donut-dot" style="background:{col}"></div>'
                           f'<span>{label}: <strong style="color:var(--text)">{v}</strong>'
                           f' <span style="color:var(--text3)">({pct_s}%)</span></span></div>')
            svg = (f'<svg width="120" height="120" viewBox="0 0 120 120">'
                   f'<circle cx="60" cy="60" r="40" fill="var(--bg3)"/>{paths}'
                   f'<circle cx="60" cy="60" r="30" fill="var(--bg2)"/>'
                   f'<text x="60" y="56" text-anchor="middle" fill="var(--text)" font-size="16" '
                   f'font-weight="700" font-family="Syne,sans-serif">{total_v}</text>'
                   f'<text x="60" y="70" text-anchor="middle" fill="var(--text2)" font-size="9">{T("totale")}</text></svg>')
            return f'<div class="donut-wrap">{svg}<div class="donut-legend">{legend}</div></div>'

        def card(title, body, wide=False):
            cls = "stat-card" + (" stat-card-wide" if wide else "")
            return (f'<div class="{cls}"><div class="stat-card-title">{title}</div>{body}</div>')

        def progress_bar(pct, col="var(--accent)"):
            return (f'<div class="prog-track" style="margin-top:10px;">'
                    f'<div class="prog-fill" style="width:{pct}%;background:{col}"></div></div>'
                    f'<div style="font-size:10px;color:var(--text3);margin-top:4px;">{pct:.1f}%</div>')

        # ── KPI row ───────────────────────────────────────────────────────────
        kpi_html = (
            kpi(total,        T("Dispositivi"),       T("nel registro"),              "var(--text)",   "") +
            kpi(len(bk_files),T("Backup archiviati"), f"{'ultimo' if LANGUAGE=='it' else 'last'}: {last_bk[:10] if last_bk and last_bk!='—' else '—'}",
                               "var(--yellow)", "")
        )

        # ── Uptime buckets ────────────────────────────────────────────────────
        _k1 = T("< 1 giorno"); _k2 = T("1–7 giorni"); _k3 = T("1–4 settimane")
        _k4 = T("1–3 mesi");   _k5 = T("> 3 mesi");   _k6 = T("N/D")
        up_bkts = {_k1:0, _k2:0, _k3:0, _k4:0, _k5:0, _k6:0}
        for r in rs:
            m = _re.search(r'(?:(\d+)w)?(?:(\d+)d)?(?:(\d+):\d+:\d+)?', r.get("uptime",""))
            if not m or not r.get("uptime"):
                up_bkts[_k6] += 1; continue
            mins = ((int(m.group(1) or 0)*7 + int(m.group(2) or 0)) * 1440
                    + int(m.group(3) or 0) * 60)
            if   mins <   1440: up_bkts[_k1] += 1
            elif mins <  10080: up_bkts[_k2] += 1
            elif mins <  40320: up_bkts[_k3] += 1
            elif mins < 129600: up_bkts[_k4] += 1
            else:               up_bkts[_k5] += 1

        # ── Firmware version distribution (ROS version from packages field) ──
        fw_dist = Counter(r.get("packages","").strip() for r in rs
                          if r.get("packages","").strip()).most_common(12)

        # ── Sedi status table ─────────────────────────────────────────────────
        if SITES:
            site_rows = ""
            for sid, s in sorted(SITES.items(), key=lambda x: x[1].get("name","")):
                devs  = [r for r in rs if r.get("site_id") == sid]
                on    = sum(1 for r in devs if r.get("status") == "ONLINE")
                off   = len(devs) - on
                pct   = round(on / len(devs) * 100) if devs else 0
                bar_c = "var(--green)" if pct >= 80 else "var(--yellow)" if pct >= 40 else "var(--red)"
                cred  = next((c["name"] for c in CRED_SETS if c["id"] == s.get("credential_id","")), "—")
                site_rows += (
                    f'<tr>'
                    f'<td style="font-weight:600;color:var(--text);">{s.get("name","")}</td>'
                    f'<td style="color:var(--text3);font-size:10px;">{s.get("city","") or "—"}</td>'
                    f'<td style="text-align:center;">{len(devs)}</td>'
                    f'<td style="color:var(--green);text-align:center;">{on}</td>'
                    f'<td style="color:var(--red);text-align:center;">{off}</td>'
                    f'<td style="text-align:center;"><span style="color:{bar_c};font-weight:700">{pct}%</span></td>'
                    f'<td style="font-size:10px;color:var(--text3);">{cred}</td>'
                    f'</tr>'
                )
            sites_html = (
                '<table class="table-sm"><thead><tr>'
                f'<th>{T("Sede")}</th><th>{T("Città")}</th><th>{T("Tot")}</th>'
                f'<th style="color:var(--green)">On</th><th style="color:var(--red)">Off</th>'
                f'<th>%</th><th>{T("Credenziali")}</th>'
                '</tr></thead>'
                f'<tbody>{site_rows}</tbody></table>'
            )
        else:
            sites_html = f'<div style="color:var(--text3);font-size:11px;padding:8px 0;">{T("Nessuna sede configurata in Site Manager.")}</div>'

        # ── Backup coverage ───────────────────────────────────────────────────
        not_backed  = total - backed_up
        bk_pct      = round(backed_up / total * 100, 1) if total else 0

        # ── Online over time — Canvas chart ───────────────────────────────────
        ph      = list(PING_HISTORY)
        ph_json = json.dumps(ph)
        _lang   = LANGUAGE  # 'en' or 'it'

        # Controls HTML (language-aware)
        _rng_opts = [("1h","1h"),("6h","6h"),("24h","24h"),("7d","7d"),("0","All" if _lang=="en" else "Tutto")]
        _typ_opts = [("area","Area"),("line","Line"),("bar","Bars" if _lang=="en" else "Barre")]
        _col_opts = [("#16a34a","#16a34a"),("#2563eb","#2563eb"),("#7c3aed","#7c3aed"),
                     ("#d97706","#d97706"),("#dc2626","#dc2626")]
        rng_btns = "".join(f'<button class="cb" data-cr="{v}" onclick="_cSetRange(\'{v}\')">{lbl}</button>'
                           for v, lbl in _rng_opts)
        typ_btns = "".join(f'<button class="cb" data-ct="{v}" onclick="_cSetType(\'{v}\')">{lbl}</button>'
                           for v, lbl in _typ_opts)
        col_swatches = "".join(
            f'<div class="cc-swatch" data-cc="{c}" onclick="_cSetColor(\'{c}\')" style="background:{c};"></div>'
            for c, _ in _col_opts)

        controls_html = (
            f'<div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;'
            f'margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid var(--border);">'
            f'<span class="cg-lbl">{"Last" if _lang=="en" else "Ultime"}:</span>'
            f'{rng_btns}'
            f'<span class="cg-sep"></span>'
            f'<span class="cg-lbl">{"Type" if _lang=="en" else "Tipo"}:</span>'
            f'{typ_btns}'
            f'<span class="cg-sep"></span>'
            f'<label class="cg-chk"><input type="checkbox" id="chkSmooth" onchange="_cToggle(\'ch_smooth\',this)">'
            f' {"Smooth" if _lang=="en" else "Levigato"}</label>'
            f'<label class="cg-chk"><input type="checkbox" id="chkGrid" onchange="_cToggle(\'ch_grid\',this)">'
            f' Grid</label>'
            f'<label class="cg-chk"><input type="checkbox" id="chkDots" onchange="_cToggle(\'ch_dots\',this)">'
            f' {"Dots" if _lang=="en" else "Punti"}</label>'
            f'<span class="cg-sep"></span>'
            f'{col_swatches}'
            f'</div>'
        )

        # Raw JS template — use .replace() to inject data (avoids f-string brace issues)
        _chart_js = (r"""<script>
(function(){
try {
var PH=PH_JSON;
var LANG='PH_LANG';
var _r=sessionStorage.getItem('ch_range')||'24h';
if(['1h','6h','24h','7d','0'].indexOf(_r)===-1) _r='24h';
var _t=sessionStorage.getItem('ch_type')||'area';
var _sm=sessionStorage.getItem('ch_smooth')!=='false';
var _gr=sessionStorage.getItem('ch_grid')!=='false';
var _dt=sessionStorage.getItem('ch_dots')==='true';
var _c=sessionStorage.getItem('ch_color')||'#16a34a';
var _raf=null;

function _data(){
  if(!_r||_r==='0') return PH;
  var ms={'1h':3600000,'6h':21600000,'24h':86400000,'7d':604800000}[_r];
  if(!ms) return PH;
  var cutoff=Date.now()-ms;
  var res=PH.filter(function(h){try{return new Date((h.ts||'').replace(' ','T')).getTime()>=cutoff;}catch(e){return true;}});
  return res.length?res:PH;
}
function _sv(k,v){sessionStorage.setItem(k,String(v));}

window._cSetRange=function(n){_r=n;_sv('ch_range',n);_sync();_draw();};
window._cSetType=function(t){_t=t;_sv('ch_type',t);_sync();_draw();};
window._cSetColor=function(c){_c=c;_sv('ch_color',c);_sync();_draw();};
window._cToggle=function(k,el){
  var v=el.checked;_sv(k,v);
  if(k==='ch_smooth')_sm=v;else if(k==='ch_grid')_gr=v;else if(k==='ch_dots')_dt=v;
  _draw();
};

function _sync(){
  document.querySelectorAll('[data-cr]').forEach(function(b){b.classList.toggle('cb-act',b.dataset.cr===_r);});
  document.querySelectorAll('[data-ct]').forEach(function(b){b.classList.toggle('cb-act',b.dataset.ct===_t);});
  document.querySelectorAll('[data-cc]').forEach(function(b){b.classList.toggle('cb-act',b.dataset.cc===_c);});
  var cs=document.getElementById('chkSmooth'),cg=document.getElementById('chkGrid'),cd=document.getElementById('chkDots');
  if(cs)cs.checked=_sm;if(cg)cg.checked=_gr;if(cd)cd.checked=_dt;
}

function _buildPath(ctx,pts){
  ctx.beginPath(); ctx.moveTo(pts[0][0],pts[0][1]);
  if(_sm&&pts.length>2){
    for(var i=0;i<pts.length-1;i++){
      var p0=pts[Math.max(i-1,0)],p1=pts[i],p2=pts[i+1],p3=pts[Math.min(i+2,pts.length-1)];
      ctx.bezierCurveTo(p1[0]+(p2[0]-p0[0])/6,p1[1]+(p2[1]-p0[1])/6,
                        p2[0]-(p3[0]-p1[0])/6,p2[1]-(p3[1]-p1[1])/6,p2[0],p2[1]);
    }
  } else {pts.slice(1).forEach(function(p){ctx.lineTo(p[0],p[1]);});}
}

function _draw(){
  var cv=document.getElementById('pingChart');
  if(!cv)return;
  var rect=cv.getBoundingClientRect();
  if(!rect.width||!rect.height)return;          // guard: canvas not visible yet
  var dpr=Math.min(window.devicePixelRatio||1,2); // cap at 2x to avoid OOM
  cv.width=Math.round(rect.width*dpr);
  cv.height=Math.round(rect.height*dpr);
  var ctx=cv.getContext('2d');
  ctx.scale(dpr,dpr);
  var W=rect.width,H=rect.height;
  var PL=40,PR=38,PT=16,PB=30,CW=W-PL-PR,CH=H-PT-PB;
  if(CW<=0||CH<=0)return;
  var data=_data(),n=data.length;
  ctx.clearRect(0,0,W,H);

  if(n<1){
    ctx.fillStyle='#8896ab';ctx.font='12px system-ui,sans-serif';
    ctx.textAlign='center';ctx.fillText(LANG==='it'?'Nessun dato':'No data',W/2,H/2);
    return;
  }

  var cxf=function(i){return PL+(i/Math.max(n-1,1))*CW;};
  var cyf=function(v,t){return PT+(1-v/Math.max(t,1))*CH;};
  var pts=data.map(function(h,i){return[cxf(i),cyf(h.online,h.total)];});

  // Y-axis labels + optional grid lines
  var maxT2=Math.max.apply(null,data.map(function(h){return h.total||1;}));
  [0,25,50,75,100].forEach(function(pct){
    var gy=PT+(1-pct/100)*CH;
    if(_gr){
      ctx.strokeStyle='#e8edf4';ctx.lineWidth=1;
      ctx.setLineDash(pct===0||pct===100?[]:[5,5]);
      ctx.beginPath();ctx.moveTo(PL,gy);ctx.lineTo(W-PR,gy);ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.fillStyle='#8896ab';ctx.font='10px system-ui,sans-serif';
    ctx.textAlign='right';ctx.fillText(Math.round(maxT2*pct/100),PL-5,gy+3.5);
    ctx.textAlign='left';ctx.fillText(pct+'%',W-PR+5,gy+3.5);
  });

  // Chart
  if(_t==='bar'){
    var bw=Math.max(1,CW/n*0.7);
    data.forEach(function(h,i){
      var pct=h.total>0?h.online/h.total:0;
      var bh=Math.max(1,pct*CH),by=PT+CH-bh,bx=cxf(i)-bw/2;
      ctx.beginPath();                           // FIX: reset path per bar
      ctx.fillStyle=_c+(i===n-1?'ff':'aa');
      if(ctx.roundRect){ctx.roundRect(bx,by,bw,bh,Math.min(3,bw/2));ctx.fill();}
      else{ctx.fillRect(bx,by,bw,bh);}          // FIX: fillRect doesn't need ctx.fill()
    });
  } else {
    if(_t==='area'){
      _buildPath(ctx,pts);
      ctx.lineTo(pts[n-1][0],PT+CH);ctx.lineTo(pts[0][0],PT+CH);ctx.closePath();
      var g=ctx.createLinearGradient(0,PT,0,PT+CH);
      g.addColorStop(0,_c+'55');g.addColorStop(0.65,_c+'18');g.addColorStop(1,_c+'00');
      ctx.fillStyle=g;ctx.fill();
    }
    _buildPath(ctx,pts);
    ctx.strokeStyle=_c;ctx.lineWidth=2.5;ctx.lineJoin='round';ctx.lineCap='round';
    ctx.setLineDash([]);ctx.stroke();
  }

  // Dots (only when few points, to avoid performance issues)
  if(_dt&&n<=500){
    ctx.fillStyle=_c;
    pts.slice(0,-1).forEach(function(p){ctx.beginPath();ctx.arc(p[0],p[1],2,0,Math.PI*2);ctx.fill();});
  }

  // Last point highlight
  var lp=data[n-1],lx=pts[n-1][0],ly=pts[n-1][1];
  var lPct=Math.round(lp.online/Math.max(lp.total,1)*100);
  ctx.beginPath();ctx.arc(lx,ly,10,0,Math.PI*2);ctx.fillStyle=_c+'22';ctx.fill();
  ctx.beginPath();ctx.arc(lx,ly,4.5,0,Math.PI*2);ctx.fillStyle=_c;ctx.fill();

  // Value annotation
  var aR=lx>PL+CW*0.65,ax=lx+(aR?-13:13),al=aR?'right':'left';
  var ay=Math.max(PT+20,ly-14);
  ctx.textAlign=al;ctx.fillStyle=_c;
  ctx.font='bold 16px system-ui,sans-serif';ctx.fillText(lPct+'%',ax,ay);
  ctx.fillStyle='#8896ab';ctx.font='10px system-ui,sans-serif';
  ctx.fillText(lp.online+'/'+lp.total,ax,ay+15);

  // X labels
  var nL=Math.min(6,n);
  var sd=n>1&&data[0].ts.slice(0,10)===data[n-1].ts.slice(0,10);
  ctx.fillStyle='#8896ab';ctx.font='10px system-ui,sans-serif';
  for(var li=0;li<nL;li++){
    var idx2=Math.round(li*(n-1)/Math.max(nL-1,1));
    var ts2=data[idx2].ts||'';
    var lbl2=sd?ts2.slice(11,16):ts2.slice(5,16);
    ctx.textAlign=li===0?'left':(li===nL-1?'right':'center');
    ctx.fillText(lbl2,cxf(idx2),H-4);
  }
}

// Tooltip — throttled via rAF to avoid layout-thrashing on fast mouse moves
var _tip=null,_tipRaf=false,_tipE=null;
function _showTip(){
  _tipRaf=false;
  if(!_tipE)return;
  var e=_tipE,cv=document.getElementById('pingChart');
  if(!cv)return;
  var rect=cv.getBoundingClientRect();
  var mx=e.clientX-rect.left,data=_data(),n=data.length;
  if(!n||rect.width<=0)return;
  var PL=40,PR=38,CW=rect.width-PL-PR;
  if(CW<=0)return;
  var idx=Math.max(0,Math.min(n-1,Math.round((mx-PL)/CW*(n-1))));
  var h=data[idx];
  var pct=Math.round(h.online/Math.max(h.total,1)*100);
  if(!_tip){
    _tip=document.createElement('div');
    _tip.style.cssText='position:fixed;background:#1a2236;color:#fff;font-size:11px;padding:5px 9px;border-radius:6px;pointer-events:none;z-index:9999;white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,.3);';
    document.body.appendChild(_tip);
  }
  _tip.textContent=(h.ts||'').slice(0,16)+' — '+pct+'% ('+h.online+'/'+h.total+')';
  _tip.style.left=(e.clientX+14)+'px';_tip.style.top=(e.clientY-32)+'px';_tip.style.display='';
}
var cv0=document.getElementById('pingChart');
if(cv0){
  cv0.addEventListener('mousemove',function(e){_tipE=e;if(!_tipRaf){_tipRaf=true;requestAnimationFrame(_showTip);}});
  cv0.addEventListener('mouseleave',function(){_tipE=null;if(_tip)_tip.style.display='none';});
}

_sync();
window.addEventListener('resize',function(){if(_raf)cancelAnimationFrame(_raf);_raf=requestAnimationFrame(_draw);});
_draw();
} catch(e){ console.error('Chart error:',e); }
})();
</script>""").replace('PH_JSON', ph_json).replace('PH_LANG', _lang)

        if ph:
            _ts0 = ph[0]['ts'][:16]  if len(ph[0]['ts'])  >= 16 else ph[0]['ts']
            _ts1 = ph[-1]['ts'][:16] if len(ph[-1]['ts']) >= 16 else ph[-1]['ts']
            spark_footer = (
                f'<div style="display:flex;justify-content:space-between;margin-top:8px;'
                f'font-size:10px;color:#8896ab;">'
                f'<span>{_ts0} &nbsp;→&nbsp; {_ts1}</span>'
                f'<span>{len(ph)} {"entries" if _lang=="en" else "voci"}'
                f' · max {PING_HISTORY.maxlen}</span>'
                f'</div>'
            )
            spark_body = (
                controls_html +
                '<canvas id="pingChart" style="width:100%;height:240px;display:block;border-radius:6px;"></canvas>' +
                spark_footer +
                _chart_js
            )
        else:
            spark_body = f'<div style="color:var(--text3);font-size:11px;padding:20px 0;text-align:center;">{T("Avvia un ping dalla Dashboard per popolare il grafico.")}</div>'

        # ── Last ping result ──────────────────────────────────────────────────
        if ph:
            lp_e = ph[-1]
            lp_on  = lp_e.get("online", 0)
            lp_off = lp_e.get("total", lp_on) - lp_on
            last_ping_html = (
                donut([(T("Online"), lp_on, "var(--green)"),
                       (T("Offline"), lp_off, "var(--red)")]) +
                f'<div style="font-size:10px;color:var(--text3);margin-top:6px;">{lp_e["ts"]}</div>'
            )
        else:
            last_ping_html = f'<div style="color:var(--text3);font-size:11px;padding:8px 0;">{T("Avvia un ping dalla Dashboard per popolare il grafico.")}</div>'

        # ── Assemble cards ────────────────────────────────────────────────────
        cards_html = (
            # Row 1: last ping + online over time (wide)
            card(T("Risultati ultimo ping"), last_ping_html) +
            card(T("Online nel tempo"), spark_body, wide=True) +

            # Row 2: infrastructure
            card(T("Sedi — stato dispositivi"), sites_html, wide=True) +

            # Row 3: firmware + uptime
            card(T("Versione firmware RouterOS"),
                 bar_chart(fw_dist, [PALETTE[(i+2)%len(PALETTE)] for i in range(12)],
                           label_width=90)) +
            card(T("Distribuzione uptime"),
                 bar_chart(list(up_bkts.items()),
                           ["#4f8ef7","#22c55e","#f59e0b","#f78a4f","#ef4444","#3f4558"])) +

            # Row 4: SSH + backup
            card(T("Copertura info SSH"),
                 donut([(T("Info disponibili"), with_info, "var(--accent)"),
                        (T("Senza dati SSH"), total - with_info, "rgba(102,113,143,.15)")])) +
            card(T("Copertura backup"),
                 donut([(T("Con backup"), backed_up, "var(--yellow)"),
                        (T("Senza backup"), not_backed, "rgba(102,113,143,.15)")]))
        )

        return self._page_shell("Statistiche", f"""
<style>
.stats-grid {{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
  gap:16px;
}}
.stat-card {{
  background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:18px 20px;
}}
.stat-card-wide {{
  grid-column: 1 / -1;
}}
.stat-card-title {{
  font-size:10px;font-weight:700;color:var(--text2);text-transform:uppercase;
  letter-spacing:.8px;margin-bottom:14px;
}}
.kpi-grid {{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));
  gap:12px;margin-bottom:22px;
}}
.kpi {{
  background:var(--bg2);border:1px solid var(--border);border-radius:12px;
  padding:14px 16px;
}}
.kpi-icon {{ font-size:16px;margin-bottom:4px; }}
.kpi-val  {{ font-size:26px;font-weight:800;font-family:var(--sans);line-height:1; }}
.kpi-label {{ font-size:11px;color:var(--text2);margin-top:4px;font-weight:600; }}
.kpi-sub   {{ font-size:10px;color:var(--text3);margin-top:2px; }}
.bar-row  {{ display:flex;align-items:center;gap:8px;margin-bottom:7px;font-size:11px; }}
.bar-label {{ color:var(--text2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:right; }}
.bar-track {{ flex:1;background:var(--bg3);border-radius:4px;height:14px; }}
.bar-fill  {{ height:100%;border-radius:4px;transition:width .3s; }}
.bar-count {{ min-width:30px;text-align:right;color:var(--text);font-weight:600; }}
.donut-wrap  {{ display:flex;align-items:center;gap:20px; }}
.donut-legend {{ display:flex;flex-direction:column;gap:7px; }}
.donut-leg-item {{ display:flex;align-items:center;gap:7px;font-size:11px;color:var(--text2); }}
.donut-dot {{ width:10px;height:10px;border-radius:50%;flex-shrink:0; }}
.prog-track {{ background:var(--bg3);border-radius:4px;height:10px; }}
.prog-fill  {{ height:100%;border-radius:4px; }}
.table-sm {{ width:100%;border-collapse:collapse;font-size:11px; }}
.table-sm th {{ padding:6px 10px;color:var(--text3);font-weight:700;text-transform:uppercase;
  font-size:9px;letter-spacing:.5px;border-bottom:1px solid var(--border);text-align:left; }}
.table-sm td {{ padding:7px 10px;border-bottom:1px solid var(--border);color:var(--text2); }}
.table-sm tr:last-child td {{ border-bottom:none; }}
.table-sm tr:hover td {{ background:var(--bg3); }}
/* ── Chart controls ──────────────────────────── */
.cb{{display:inline-flex;align-items:center;justify-content:center;padding:3px 10px;border-radius:5px;border:1px solid var(--border2);background:var(--bg3);color:var(--text2);cursor:pointer;font-size:10px;font-weight:600;transition:all .12s;line-height:1;}}
.cb:hover{{border-color:var(--accent);color:var(--accent);background:var(--accent3);}}
.cb-act{{background:var(--accent)!important;border-color:var(--accent)!important;color:#fff!important;}}
.cg-lbl{{font-size:10px;color:var(--text2);font-weight:700;white-space:nowrap;}}
.cg-sep{{display:inline-block;width:1px;height:16px;background:var(--border);margin:0 2px;}}
.cg-chk{{display:flex;align-items:center;gap:4px;font-size:10px;color:var(--text2);cursor:pointer;user-select:none;}}
.cg-chk input{{accent-color:var(--accent);cursor:pointer;}}
.cc-swatch{{width:18px;height:18px;border-radius:50%;cursor:pointer;border:2px solid transparent;flex-shrink:0;transition:border-color .12s;}}
.cc-swatch.cb-act{{border-color:var(--text)!important;}}
</style>
<meta http-equiv="refresh" content="30">

<div class="kpi-grid">{kpi_html}</div>
<div class="stats-grid">{cards_html}</div>

<div style="font-size:10px;color:var(--text3);text-align:right;margin-top:12px;">
  {T("Aggiornato alle")} {ts} &nbsp;·&nbsp; {total} {T("dispositivi")} &nbsp;·&nbsp;
  {'refresh automatico ogni 30s' if LANGUAGE=='it' else 'auto-refresh every 30s'} &nbsp;·&nbsp;
  <a href="/stats" style="color:var(--accent);text-decoration:none;">{T("↺ Aggiorna ora")}</a>
</div>
""", session=session, page_key="stats")

    def render_report_page(self, session=None):
        """Unified activity log — all processes write to APP_LOG."""
        role       = (session or {}).get("role", "viewer")
        is_admin   = (role == "admin")
        can_write  = _can_do(session, "log_write")   # can clear the log

        # ── URL params (set by GET handler) ──────────────────────────
        cat_filter  = getattr(self, "_log_cat",      "all")
        date_filter = getattr(self, "_log_date",     "")
        tf_from     = getattr(self, "_log_tf",       "")
        tf_to       = getattr(self, "_log_tt",       "")
        per_page    = getattr(self, "_log_per_page", 50)
        page        = getattr(self, "_log_page",     1)

        CATEGORIES = [
            ("all",      T("Tutti"),      "#8896ab"),
            ("ping",     "Ping",          "#4f8ef7"),
            ("ssh",      "SSH",           "#9b7ef7"),
            ("backup",   "Backup",        "#f7c44f"),
            ("script",   "Script",        "#4fd4f7"),
            ("security", T("Sicurezza"),  "#f74f6a"),
            ("system",   T("Sistema"),    "#2adf8a"),
            ("error",    T("Errori"),     "#f78a4f"),   # filters by level=error
        ]
        LEVEL_COLORS = {"info": "var(--text2)", "warn": "#f7c44f", "error": "#f74f6a"}
        CAT_COLORS   = {k: c for k, _, c in CATEGORIES}

        # ── URL builder helper ────────────────────────────────────────
        def _url(**kw):
            p = {"cat": cat_filter, "date": date_filter,
                 "tf": tf_from, "tt": tf_to, "pp": str(per_page), "p": "1"}
            p.update({k: str(v) for k, v in kw.items()})
            qs = "&".join(f"{k}={urllib.parse.quote(v)}"
                          for k, v in p.items() if v and v != "1")
            return f"/log?{qs}" if qs else "/log"

        # ── 1. Full log reversed (newest first) ───────────────────────
        all_entries = list(reversed(list(APP_LOG)))

        # ── 2. Category / level filter ────────────────────────────────
        # FIX: "error" tab → filter by level, not by category key
        if cat_filter == "error":
            filtered = [e for e in all_entries if e.get("level") == "error"]
        elif cat_filter != "all":
            filtered = [e for e in all_entries if e.get("category") == cat_filter]
        else:
            filtered = all_entries

        # ── 3. Date filter ────────────────────────────────────────────
        if date_filter:
            filtered = [e for e in filtered if e.get("ts", "").startswith(date_filter)]

        # ── 4. Time filter ────────────────────────────────────────────
        if tf_from or tf_to:
            def _in_t(e):
                t = e.get("ts", "")[11:16]
                if tf_from and t < tf_from: return False
                if tf_to   and t > tf_to:   return False
                return True
            filtered = [e for e in filtered if _in_t(e)]

        # ── 5. Pagination ─────────────────────────────────────────────
        total_filtered = len(filtered)
        total_pages    = max(1, (total_filtered + per_page - 1) // per_page)
        page           = max(1, min(page, total_pages))
        start          = (page - 1) * per_page
        page_entries   = filtered[start:start + per_page]

        ts_now  = datetime.now().strftime("%H:%M:%S")
        log_max = _app_cfg.get("app_log_maxlen", 2000)

        # ── Category tab buttons ──────────────────────────────────────
        tabs_html = '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px;">'
        for key, label, col in CATEGORIES:
            if key == "error":
                cnt = sum(1 for e in all_entries if e.get("level") == "error")
            elif key == "all":
                cnt = len(all_entries)
            else:
                cnt = sum(1 for e in all_entries if e.get("category") == key)
            act = f' style="background:{col};border-color:{col};color:#fff;"' if key == cat_filter else ''
            tabs_html += (f'<a href="{_url(cat=key)}" class="lc"{act}>'
                          f'{label}'
                          f'<span style="margin-left:5px;opacity:.65;font-size:9px;">{cnt}</span></a>')
        tabs_html += '</div>'

        # ── Search bar ────────────────────────────────────────────────
        pp_opts = "".join(
            f'<option value="{v}" {"selected" if per_page==v else ""}>{v}</option>'
            for v in [25, 50, 100, 200, 500]
        )
        lbl_date   = "Date" if LANGUAGE != "it" else "Data"
        lbl_dalle  = T("Dalle")
        lbl_alle   = T("Alle")
        lbl_per_pg = T("Per pagina")
        lbl_search = T("Cerca")
        lbl_reset  = T("Azzera filtri")
        search_html = (
            f'<form method="GET" action="/log" style="display:flex;gap:8px;flex-wrap:wrap;'
            f'align-items:flex-end;margin-bottom:14px;padding:12px 14px;'
            f'background:var(--bg2);border:1px solid var(--border);border-radius:10px;">'
            f'<input type="hidden" name="cat" value="{cat_filter}">'
            f'<div style="display:flex;flex-direction:column;gap:3px;">'
            f'<label style="font-size:9px;font-weight:700;color:var(--text3);text-transform:uppercase;">{lbl_date}</label>'
            f'<input type="date" name="date" value="{date_filter}" '
            f'style="font-size:11px;padding:4px 8px;border-radius:6px;'
            f'border:1px solid var(--border2);background:var(--bg3);color:var(--text);">'
            f'</div>'
            f'<div style="display:flex;flex-direction:column;gap:3px;">'
            f'<label style="font-size:9px;font-weight:700;color:var(--text3);text-transform:uppercase;">{lbl_dalle}</label>'
            f'<input type="time" name="tf" value="{tf_from}" '
            f'style="font-size:11px;padding:4px 8px;border-radius:6px;'
            f'border:1px solid var(--border2);background:var(--bg3);color:var(--text);">'
            f'</div>'
            f'<div style="display:flex;flex-direction:column;gap:3px;">'
            f'<label style="font-size:9px;font-weight:700;color:var(--text3);text-transform:uppercase;">{lbl_alle}</label>'
            f'<input type="time" name="tt" value="{tf_to}" '
            f'style="font-size:11px;padding:4px 8px;border-radius:6px;'
            f'border:1px solid var(--border2);background:var(--bg3);color:var(--text);">'
            f'</div>'
            f'<div style="display:flex;flex-direction:column;gap:3px;">'
            f'<label style="font-size:9px;font-weight:700;color:var(--text3);text-transform:uppercase;">{lbl_per_pg}</label>'
            f'<select name="pp" style="font-size:11px;padding:4px 8px;border-radius:6px;'
            f'border:1px solid var(--border2);background:var(--bg3);color:var(--text);">{pp_opts}</select>'
            f'</div>'
            f'<button type="submit" class="btn btn-primary" style="font-size:11px;padding:5px 14px;">{lbl_search}</button>'
            f'<a href="/log?cat={cat_filter}" class="btn" style="font-size:11px;padding:5px 14px;">{lbl_reset}</a>'
            f'</form>'
        )

        # ── Log rows ──────────────────────────────────────────────────
        th_time = T("Orario"); th_cat = T("Categoria")
        th_lvl  = T("Livello"); th_msg = T("Messaggio")
        if page_entries:
            rows_html = ""
            for e in page_entries:
                cat  = e.get("category", "system")
                lvl  = e.get("level", "info")
                ip   = e.get("ip", "")
                name = e.get("name", "")
                msg  = e.get("msg", "")
                if LANGUAGE != "it":
                    for it_s, en_s in _T_EN.items():
                        if it_s != en_s and it_s in msg:
                            msg = msg.replace(it_s, en_s)
                ts_e = e.get("ts", "")[:16]
                ccol = CAT_COLORS.get(cat, "#8896ab")
                lcol = LEVEL_COLORS.get(lvl, "var(--text2)")
                bg   = "background:rgba(247,79,106,.04);" if lvl == "error" else (
                       "background:rgba(247,196,79,.04);" if lvl == "warn" else "")
                dev  = ""
                if ip:
                    dev = f'<span style="font-family:var(--mono);font-size:11px;">{ip}</span>'
                    if name:
                        dev += f' <span style="color:var(--text3);font-size:10px;">({name})</span>'
                rows_html += (
                    f'<tr style="{bg}">'
                    f'<td style="white-space:nowrap;color:var(--text3);font-size:10px;">{ts_e}</td>'
                    f'<td><span style="background:{ccol}22;color:{ccol};border:1px solid {ccol}44;'
                    f'padding:2px 6px;border-radius:4px;font-size:9px;font-weight:700;'
                    f'text-transform:uppercase;white-space:nowrap;">{cat}</span></td>'
                    f'<td><span style="color:{lcol};font-size:10px;font-weight:700;">{lvl.upper()}</span></td>'
                    f'<td style="font-size:11px;">{dev}</td>'
                    f'<td style="font-size:11px;color:var(--text);word-break:break-word;">{msg}</td>'
                    f'</tr>'
                )
            table_html = (
                f'<table class="table-sm rpt-table"><thead><tr>'
                f'<th>{th_time}</th><th>{th_cat}</th><th>{th_lvl}</th>'
                f'<th>Device</th><th>{th_msg}</th>'
                f'</tr></thead><tbody>{rows_html}</tbody></table>'
            )
        else:
            _empty_msg = T("Nessun evento trovato con i filtri selezionati.")
            table_html = (
                f'<div style="color:var(--text3);font-size:12px;padding:40px 0;text-align:center;">'
                f'{_empty_msg}</div>'
            )

        # ── Pagination bar ────────────────────────────────────────────
        if total_pages > 1:
            pag_items = []
            # Prev
            if page > 1:
                pag_items.append(f'<a href="{_url(p=str(page-1))}" class="pg-btn">‹</a>')
            else:
                pag_items.append('<span class="pg-btn pg-dis">‹</span>')
            # Page numbers (show at most 7 around current)
            lo = max(1, page - 3)
            hi = min(total_pages, page + 3)
            if lo > 1:
                pag_items.append(f'<a href="{_url(p="1")}" class="pg-btn">1</a>')
                if lo > 2: pag_items.append('<span class="pg-ell">…</span>')
            for pn in range(lo, hi + 1):
                cls = "pg-btn pg-act" if pn == page else "pg-btn"
                pag_items.append(f'<a href="{_url(p=str(pn))}" class="{cls}">{pn}</a>')
            if hi < total_pages:
                if hi < total_pages - 1: pag_items.append('<span class="pg-ell">…</span>')
                pag_items.append(f'<a href="{_url(p=str(total_pages))}" class="pg-btn">{total_pages}</a>')
            # Next
            if page < total_pages:
                pag_items.append(f'<a href="{_url(p=str(page+1))}" class="pg-btn">›</a>')
            else:
                pag_items.append('<span class="pg-btn pg-dis">›</span>')
            lbl_showing = T("Mostrati")
            lbl_of      = "of" if LANGUAGE != "it" else "di"
            end_idx     = min(start + per_page, total_filtered)
            pagination_html = (
                f'<div style="display:flex;align-items:center;justify-content:space-between;'
                f'padding:12px 14px;border-top:1px solid var(--border);flex-wrap:wrap;gap:8px;">'
                f'<span style="font-size:11px;color:var(--text3);">'
                f'{lbl_showing} {start+1}–{end_idx} {lbl_of} {total_filtered}</span>'
                f'<div style="display:flex;gap:4px;flex-wrap:wrap;">{"".join(pag_items)}</div>'
                f'</div>'
            )
        else:
            pagination_html = ""

        # ── Log controls bar ──────────────────────────────────────────
        admin_bar = ""
        if can_write:
            clear_conf = T("Svuotare il log degli eventi?")
            lbl_clear  = T("Svuota log")
            clear_form = (
                f'<form method="POST" action="/log/clear" style="margin-left:auto;">'
                f'<button class="btn" style="font-size:11px;color:var(--red);border-color:var(--red)44;"'
                f' onclick="return confirm(\'{clear_conf}\')">{lbl_clear}</button></form>'
            )
            if is_admin:
                ml_opts = "".join(
                    f'<option value="{v}" {"selected" if log_max==v else ""}>{v}</option>'
                    for v in [500, 1000, 2000, 5000, 10000]
                )
                lbl_maxarch = T("Max archiviati")
                lbl_save    = T("Salva")
                size_form = (
                    f'<form method="POST" action="/log/settings" style="display:flex;gap:8px;align-items:center;">'
                    f'<label style="color:var(--text2);font-weight:600;">{lbl_maxarch}:</label>'
                    f'<select name="log_maxlen" style="font-size:11px;padding:3px 8px;border-radius:5px;'
                    f'border:1px solid var(--border2);background:var(--bg3);color:var(--text);">{ml_opts}</select>'
                    f'<button type="submit" class="btn" style="font-size:11px;padding:4px 12px;">{lbl_save}</button>'
                    f'</form>'
                )
            else:
                size_form = ""
            admin_bar = (
                f'<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;'
                f'margin-top:14px;padding:10px 14px;background:var(--bg2);'
                f'border:1px solid var(--border);border-radius:8px;font-size:11px;">'
                + size_form + clear_form +
                f'</div>'
            )

        # ── Assemble page ─────────────────────────────────────────────
        pg_title   = T("Log attività")
        lbl_tot    = T("eventi in memoria")
        lbl_filt   = T("filtrati")
        lbl_of     = "of" if LANGUAGE != "it" else "di"
        lbl_upd    = T("aggiornato alle")
        lbl_now    = T("↺ Aggiorna ora")

        return self._page_shell("Log", f"""
<style>
.rpt-table {{ width:100%;border-collapse:collapse;font-size:11px; }}
.rpt-table th {{ padding:6px 10px;color:var(--text3);font-weight:700;text-transform:uppercase;
  font-size:9px;letter-spacing:.5px;border-bottom:1px solid var(--border);text-align:left; }}
.rpt-table td {{ padding:7px 10px;border-bottom:1px solid var(--border);vertical-align:top; }}
.rpt-table tr:last-child td {{ border-bottom:none; }}
.rpt-table tr:hover td {{ filter:brightness(1.04); }}
.lc {{ display:inline-flex;align-items:center;padding:4px 10px;border-radius:6px;
  border:1px solid var(--border2);background:var(--bg3);color:var(--text2);
  font-size:10px;font-weight:600;text-decoration:none;transition:all .12s;gap:0; }}
.lc:hover {{ border-color:var(--accent);color:var(--accent); }}
.pg-btn {{ display:inline-flex;align-items:center;justify-content:center;
  min-width:30px;height:28px;padding:0 6px;border-radius:5px;font-size:11px;font-weight:600;
  border:1px solid var(--border2);background:var(--bg3);color:var(--text2);
  text-decoration:none;transition:all .12s; }}
.pg-btn:hover {{ border-color:var(--accent);color:var(--accent); }}
.pg-act {{ background:var(--accent)!important;border-color:var(--accent)!important;color:#fff!important; }}
.pg-dis {{ opacity:.35;pointer-events:none; }}
.pg-ell {{ display:inline-flex;align-items:center;justify-content:center;
  min-width:22px;height:28px;font-size:11px;color:var(--text3); }}
</style>
<meta http-equiv="refresh" content="30">

<div style="display:flex;align-items:center;justify-content:space-between;
     margin-bottom:14px;flex-wrap:wrap;gap:8px;">
  <div>
    <div style="font-size:18px;font-weight:800;color:var(--text);">{pg_title}</div>
    <div style="font-size:11px;color:var(--text3);margin-top:2px;">
      {len(APP_LOG)} {lbl_tot}
      {f' &nbsp;·&nbsp; <strong style="color:var(--accent);">{total_filtered} {lbl_filt}</strong>' if total_filtered != len(APP_LOG) else ''}
      &nbsp;·&nbsp; {lbl_upd} {ts_now}
      &nbsp;·&nbsp; <a href="/log" style="color:var(--accent);text-decoration:none;">{lbl_now}</a>
    </div>
  </div>
</div>

{tabs_html}
{search_html}

<div style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;overflow:hidden;">
{table_html}
{pagination_html}
</div>

{admin_bar}
""", session=session, page_key="log")

    def render_upgrade_page(self, session=None):
        lang_en  = LANGUAGE == "en"
        sites_js = json.dumps([
            {"id": sid, "name": s.get("name", sid), "cred_id": s.get("credential_id", "")}
            for sid, s in sorted(SITES.items(), key=lambda x: x[1].get("name",""))
        ])
        return self._page_shell(T("Aggiornamento RouterOS"), f"""
<style>
.upg-layout{{display:flex;gap:16px;height:calc(100vh - 80px);}}
.upg-left{{width:340px;flex-shrink:0;display:flex;flex-direction:column;gap:8px;}}
.upg-right{{flex:1;display:flex;flex-direction:column;gap:14px;overflow-y:auto;}}
/* Router list */
.upg-list{{flex:1;overflow-y:auto;border:1px solid var(--border);border-radius:8px;
  background:var(--bg2);}}
.upg-ritem{{display:flex;align-items:center;gap:10px;padding:9px 12px;
  border-bottom:1px solid var(--border);cursor:pointer;transition:background .08s;user-select:none;}}
.upg-ritem:last-child{{border-bottom:none;}}
.upg-ritem:hover{{background:var(--bg3);}}
.upg-ritem.selected{{background:rgba(38,80,160,.08);}}
.upg-ritem input[type=checkbox]{{flex-shrink:0;}}
.upg-rinfo{{flex:1;min-width:0;}}
.upg-rip{{font-size:12px;font-weight:700;color:var(--accent2);font-family:var(--mono);}}
.upg-rname{{font-size:10px;color:var(--text3);margin-top:1px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}}
.upg-rmeta{{display:flex;flex-direction:column;align-items:flex-end;gap:3px;flex-shrink:0;}}
.upg-rdot{{width:7px;height:7px;border-radius:50%;background:var(--text3);}}
.upg-rdot.online{{background:var(--green);}}
.upg-rver{{font-size:9px;color:var(--text3);font-family:var(--mono);}}
/* Right panel */
.upg-card{{background:var(--bg2);border:1px solid var(--border);border-radius:8px;padding:14px 16px;}}
.upg-tabs{{display:flex;gap:0;border-bottom:2px solid var(--border);margin-bottom:14px;}}
.upg-tab{{padding:7px 16px;font-size:12px;font-weight:700;cursor:pointer;border:none;
  background:transparent;color:var(--text2);border-bottom:2px solid transparent;margin-bottom:-2px;
  transition:all .15s;}}
.upg-tab.active{{color:var(--accent);border-bottom-color:var(--accent);}}
.upg-panel{{display:none;flex-direction:column;gap:12px;}}
.upg-panel.active{{display:flex;}}
.upg-warn{{background:rgba(220,38,38,.07);border:1.5px solid rgba(220,38,38,.3);
  border-radius:6px;padding:9px 13px;font-size:11px;color:var(--red);line-height:1.55;}}
/* Site filter buttons */
.upg-site-bar{{display:flex;gap:5px;flex-wrap:wrap;}}
.upg-site-btn{{padding:4px 10px;border-radius:5px;font-size:11px;cursor:pointer;
  border:1px solid var(--border2);background:var(--bg3);color:var(--text2);
  font-family:var(--mono);transition:all .15s;white-space:nowrap;}}
.upg-site-btn:hover,.upg-site-btn.active{{
  border-color:var(--accent);color:var(--accent);background:rgba(38,80,160,.08);}}
/* Results table */
.upg-result-list{{border:1px solid var(--border);border-radius:6px;background:var(--bg2);overflow:hidden;}}
.upg-row{{display:flex;align-items:center;gap:8px;padding:7px 12px;
  border-bottom:1px solid var(--border);font-size:11px;}}
.upg-row:last-child{{border-bottom:none;}}
.upg-row-ip{{color:var(--accent2);font-weight:700;font-family:var(--mono);min-width:115px;}}
.upg-row-name{{color:var(--text2);min-width:100px;flex:1;}}
.upg-row-ver{{font-family:var(--mono);font-size:10px;margin-left:auto;}}
.upg-row-st{{font-size:10px;color:var(--text3);margin-left:8px;}}
.ok-ico{{color:var(--green);font-weight:800;}}
.fail-ico{{color:var(--red);font-weight:800;}}
/* Results list for check-for-updates */
.upg-res-row{{display:flex;align-items:center;gap:10px;padding:8px 14px;
  border-bottom:1px solid var(--border);font-size:11px;}}
.upg-res-row:last-child{{border-bottom:none;}}
.upg-res-dot{{width:8px;height:8px;border-radius:50%;background:var(--border2);flex-shrink:0;}}
.upg-res-dot.update{{background:var(--yellow);}}
.upg-res-ip{{color:var(--accent2);font-weight:700;font-family:var(--mono);min-width:115px;flex-shrink:0;}}
.upg-res-name{{color:var(--text2);min-width:110px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
.upg-res-ver{{font-family:var(--mono);font-size:11px;margin-left:auto;flex-shrink:0;}}
.upg-res-ver.ok{{color:var(--green);}}
.upg-res-ver.update{{color:var(--yellow);font-weight:700;}}
.upg-res-ver.fail{{color:var(--red);}}
.upg-chg-link{{color:var(--accent2);text-decoration:underline;cursor:pointer;}}
.upg-chg-link:hover{{color:var(--accent);}}
</style>

<div class="upg-layout">

  <!-- ── Left: router picker ───────────────────────── -->
  <div class="upg-left">
    <input type="text" class="search-box" id="upgSearch"
           placeholder="{T('Cerca per IP o nome…')}" oninput="upgFilter()">
    <div class="upg-site-bar" id="upgSiteBtns">
      <button class="upg-site-btn active" data-site="" onclick="upgFilterSite(this,'')">{T("Tutti")}</button>
    </div>
    <div style="display:flex;justify-content:space-between;align-items:center;">
      <label style="display:flex;gap:6px;align-items:center;font-size:11px;color:var(--text2);cursor:pointer;">
        <input type="checkbox" id="upgSelAll" onchange="upgToggleAll(this)">
        {T("Seleziona tutti")}
      </label>
      <span style="font-size:11px;color:var(--text2);">
        <span id="upgSelCount" style="color:var(--accent);font-weight:700;">0</span> sel.
      </span>
    </div>
    <div class="upg-list" id="upgRouterList">
      <div style="padding:16px;color:var(--text3);font-size:11px;">{T("Caricamento…")}</div>
    </div>
  </div>

  <!-- ── Right: tabs ── -->
  <div class="upg-right">

    <!-- Credential picker (same layout as backup manager) -->
    <div style="flex-shrink:0;">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;">
        <label style="font-size:10px;font-weight:700;color:var(--text2);text-transform:uppercase;
                      letter-spacing:.7px;margin:0;">
          {"SSH Credentials" if lang_en else "Credenziali SSH"}
        </label>
        <a href="/credentials" style="margin-left:auto;font-size:10px;color:var(--accent);
                                       text-decoration:none;font-weight:600;white-space:nowrap;">
          {"Credential Manager" if lang_en else "Credential Manager"} →
        </a>
      </div>
      <select id="upgCredPicker" style="width:100%;box-sizing:border-box;font-size:12px;margin-bottom:4px;">
        <option value="">— {"Automatic: device / site credentials" if lang_en else "Automatico: credenziali dispositivo / sito"} —</option>
        {chr(10).join(f'        <option value="{c["id"]}">{c["name"]}</option>' for c in CRED_SETS)}
      </select>
      {"" if CRED_SETS else f'<div style="font-size:10px;color:var(--text3);font-style:italic;margin-bottom:4px;">{"No credentials configured." if lang_en else "Nessuna credenziale configurata."} <a href="/credentials" style="color:var(--accent);">{"Create one" if lang_en else "Creane una"} →</a></div>'}
    </div>

    <!-- Tabs card -->
    <div class="upg-card" style="flex:1;">
      <div class="upg-tabs">
        <button class="upg-tab active" onclick="upgSwitchTab('online',this)">
          {"Online update" if lang_en else "Aggiornamento online"}
        </button>
        <button class="upg-tab" onclick="upgSwitchTab('npk',this)">
          {"Upload .npk" if lang_en else "Carica .npk"}
        </button>
      </div>

      <!-- Tab 1: Online update -->
      <div class="upg-panel active" id="upg-tab-online">
        <div style="font-size:11px;color:var(--text2);line-height:1.6;">
          {"Connects via SSH and runs" if lang_en else "Si connette via SSH ed esegue"}
          <code>/system package update check-for-updates</code>
          {"on each selected router." if lang_en else "su ciascun router selezionato."}
        </div>
        <div style="display:flex;gap:8px;align-items:center;margin-bottom:6px;">
          <label style="font-size:10px;font-weight:700;color:var(--text2);text-transform:uppercase;letter-spacing:.6px;white-space:nowrap;">
            {"Channel" if lang_en else "Canale"}
          </label>
          <select id="upgChannel" style="font-size:11px;padding:4px 8px;">
            <option value="">— {"Current channel" if lang_en else "Canale attuale"} —</option>
            <option value="stable">stable</option>
            <option value="long-term">long-term</option>
            <option value="testing">testing</option>
            <option value="development">development</option>
          </select>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
          <button class="btn btn-primary" id="upgCheckBtn" onclick="upgCheckOnline()">
            {"Check versions" if lang_en else "Controlla versioni"}
          </button>
          <button class="btn" id="upgDownloadBtn" onclick="upgDownloadOnly()" disabled
                  style="background:var(--accent2);color:#fff;border-color:var(--accent2);">
            {"Download only" if lang_en else "Solo download"}
          </button>
          <button class="btn" id="upgInstallBtn" onclick="upgInstallOnline()" disabled
                  style="background:var(--red);color:#fff;border-color:var(--red);">
            {"Download &amp; Install" if lang_en else "Scarica &amp; Installa"}
          </button>
        </div>
        <div class="upg-warn">
          {"<strong>Warning:</strong> Installing updates will reboot the router — connections will be interrupted."
           if lang_en else
           "<strong>Attenzione:</strong> L'installazione riavvierà il router — le connessioni saranno interrotte."}
        </div>
        <!-- Terminal monitor -->
        <div id="upgTermWrap">
          <div id="upgTerminal" style="
            background:#0d1117;border-radius:6px;
            font-family:var(--mono);font-size:11px;
            min-height:80px;max-height:200px;overflow-y:auto;
            padding:10px 14px;line-height:1.7;
          "></div>
        </div>
        <!-- Results list -->
        <div id="upgOnlineResults" style="display:none;
          border:1px solid var(--border);border-radius:8px;overflow:hidden;
          background:var(--bg2);max-height:260px;overflow-y:auto;"></div>
      </div>

      <!-- Tab 2: .npk upload -->
      <div class="upg-panel" id="upg-tab-npk">
        <div style="font-size:11px;color:var(--text2);line-height:1.6;">
          {"Upload a <code>.npk</code> package via SFTP — the router installs it on the next reboot."
           if lang_en else
           "Carica un pacchetto <code>.npk</code> via SFTP — il router lo installa al prossimo riavvio."}
        </div>
        <div>
          <label style="font-size:11px;color:var(--text2);display:block;margin-bottom:4px;">
            {"Package file (.npk)" if lang_en else "File pacchetto (.npk)"}
          </label>
          <input type="file" id="upgNpkFile" accept=".npk" style="width:100%;">
        </div>
        <label style="display:flex;align-items:center;gap:8px;font-size:12px;color:var(--text2);
                      cursor:pointer;user-select:none;">
          <input type="checkbox" id="upgReboot">
          {"Reboot immediately after upload" if lang_en else "Riavvia subito dopo il caricamento"}
        </label>
        <div class="upg-warn">
          {"<strong>Warning:</strong> Rebooting will interrupt all connections on that router."
           if lang_en else
           "<strong>Attenzione:</strong> Il riavvio interromperà tutte le connessioni su quel router."}
        </div>
        <div style="display:flex;gap:8px;align-items:center;">
          <button class="btn btn-primary" id="upgNpkBtn" onclick="upgUploadNpk()">
            {"Upload .npk" if lang_en else "Carica .npk"}
          </button>
          <span id="upgNpkStatus" style="font-size:11px;color:var(--text2);"></span>
        </div>
        <div id="upgNpkProgress" style="display:none;">
          <div style="background:var(--bg3);border-radius:6px;height:6px;overflow:hidden;margin-bottom:5px;">
            <div id="upgNpkBar" style="height:100%;width:0%;background:var(--accent);border-radius:6px;transition:width .3s;"></div>
          </div>
          <div id="upgNpkMsg" style="font-size:11px;color:var(--text2);"></div>
        </div>
        <div id="upgNpkResults" class="upg-result-list" style="display:none;"></div>
      </div>
    </div>

  </div>
</div>

<script>
const UPG_SITES    = {sites_js};
let upgRouters     = [];
let upgActiveSite  = '';

fetch('/api/state').then(r=>r.json()).then(d=>{{
  upgRouters = d.routers;
  var wrap = document.getElementById('upgSiteBtns');
  wrap.querySelector('[data-site=""]').textContent = '{T("Tutti")} (' + upgRouters.length + ')';
  UPG_SITES.forEach(function(s) {{
    var cnt = upgRouters.filter(r=>r.site_id===s.id).length;
    if(!cnt) return;
    var b = document.createElement('button');
    b.className='upg-site-btn'; b.dataset.site=s.id;
    b.textContent = s.name + ' (' + cnt + ')';
    b.onclick = function(){{ upgFilterSite(b, s.id); }};
    wrap.appendChild(b);
  }});
  upgRender(upgRouters);
}});

function upgFilterSite(el, sid) {{
  upgActiveSite = sid;
  document.querySelectorAll('#upgSiteBtns .upg-site-btn').forEach(b=>b.classList.remove('active'));
  el.classList.add('active');
  upgFilter();
}}
function upgFilter() {{
  var q=document.getElementById('upgSearch').value.toLowerCase();
  var f=upgRouters.filter(r=>{{
    if(upgActiveSite&&upgActiveSite!==''){{if(r.site_id!==upgActiveSite)return false;}}
    return r.ip.includes(q)||(r.name||'').toLowerCase().includes(q);
  }});
  upgRender(f);
}}
function upgRender(rs) {{
  var l=document.getElementById('upgRouterList');
  if(!rs.length){{
    l.innerHTML='<div style="padding:16px;color:var(--text3);font-size:11px;">{T("Nessun router trovato.")}</div>';
    upgCount(); return;
  }}
  l.innerHTML=rs.map(r=>{{
    var online=r.status==='ONLINE';
    var ver=r.packages||'';
    return '<div class="upg-ritem" onclick="upgToggle(this)" data-ip="'+r.ip+'">'
      +'<input type="checkbox" class="upg-check" data-ip="'+r.ip+'"'
      +' onclick="event.stopPropagation();this.closest(\\'.upg-ritem\\').classList.toggle(\\'selected\\',this.checked);upgCount();">'
      +'<div class="upg-rinfo">'
      +'<div class="upg-rip">'+r.ip+'</div>'
      +'<div class="upg-rname">'+(r.name||'—')+'</div>'
      +'</div>'
      +'<div class="upg-rmeta">'
      +'<span class="upg-rdot'+(online?' online':'')+'"></span>'
      +(ver?'<span class="upg-rver">'+ver+'</span>':'')
      +'</div>'
      +'</div>';
  }}).join('');
  upgCount();
}}
function upgToggle(item) {{
  var cb=item.querySelector('.upg-check');
  cb.checked=!cb.checked; item.classList.toggle('selected',cb.checked); upgCount();
}}
function upgToggleAll(m) {{
  document.querySelectorAll('.upg-check').forEach(cb=>{{
    cb.checked=m.checked;
    cb.closest('.upg-ritem').classList.toggle('selected',m.checked);
  }});
  upgCount();
}}
function upgCount() {{
  var n=document.querySelectorAll('.upg-check:checked').length;
  document.getElementById('upgSelCount').textContent=n;
}}
function upgGetIPs() {{
  return Array.from(document.querySelectorAll('.upg-check:checked')).map(cb=>cb.dataset.ip);
}}
function upgSwitchTab(name, btn) {{
  document.querySelectorAll('.upg-tab').forEach(b=>b.classList.remove('active'));
  document.querySelectorAll('.upg-panel').forEach(p=>p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('upg-tab-'+name).classList.add('active');
}}

// ── Tab 1: Online check — job-based with terminal monitor ────────
var _upgCheckPoll  = null;
var _upgCheckRes   = [];

function _upgTs() {{
  var n=new Date();
  return [n.getHours(),n.getMinutes(),n.getSeconds()].map(x=>String(x).padStart(2,'0')).join(':');
}}
function upgTermLine(text, color) {{
  var term=document.getElementById('upgTerminal');
  if(!term) return;
  var line=document.createElement('div');
  line.style.color=color||'#e6edf3';
  line.innerHTML='<span style="color:#484f58;">['+_upgTs()+']</span> '+text;
  term.appendChild(line);
  term.scrollTop=term.scrollHeight;
}}

function _upgGetCred()    {{ return document.getElementById('upgCredPicker').value; }}
function _upgGetChannel() {{ return document.getElementById('upgChannel').value; }}

async function upgCheckOnline() {{
  var ips=upgGetIPs();
  var checkBtn=document.getElementById('upgCheckBtn');
  if(!ips.length){{alert('{"Select at least one router." if lang_en else "Seleziona almeno un router."}');return;}}
  checkBtn.disabled=true;
  document.getElementById('upgInstallBtn').disabled=true;
  document.getElementById('upgDownloadBtn').disabled=true;
  var terminal=document.getElementById('upgTerminal');
  var rl=document.getElementById('upgOnlineResults');
  terminal.innerHTML='';
  rl.style.display='none'; rl.innerHTML='';
  _upgCheckRes=[];
  upgTermLine('{"Starting check for" if lang_en else "Avvio controllo per"} '+ips.length+' {"router(s)…" if lang_en else "router…"}','#79c0ff');
  var fd=new URLSearchParams();
  fd.append('ips',ips.join(','));
  fd.append('cred_id',_upgGetCred());
  fd.append('channel',_upgGetChannel());
  try {{
    var r=await fetch('/api/ros-check-start',{{method:'POST',body:fd}});
    var d=await r.json();
    if(!d.ok){{upgTermLine('x '+d.msg,'#f85149');checkBtn.disabled=false;return;}}
    upgTermLine('{"Checking in parallel…" if lang_en else "Controllo in parallelo…"}','#79c0ff');
    _upgPollCheckJob(d.job_id, d.total, 0, checkBtn);
  }} catch(e) {{
    upgTermLine('x '+e,'#f85149');
    checkBtn.disabled=false;
  }}
}}

function _upgPollCheckJob(job_id, total, seen, checkBtn) {{
  clearTimeout(_upgCheckPoll);
  _upgCheckPoll=setTimeout(async function(){{
    try {{
      var j=await fetch('/api/job?id='+job_id).then(r=>r.json());
      var newRows=j.results.slice(seen);
      newRows.forEach(function(row){{
        _upgCheckRes.push(row);
        if(!row.ok) {{
          upgTermLine('x '+row.ip+(row.name?' ('+row.name+')':'')+' — '+(row.msg||'error'),'#f85149');
        }} else {{
          var upd=row.latest!=='?'&&row.current!==row.latest;
          if(upd) {{
            upgTermLine('! '+row.ip+(row.name?' ('+row.name+')':'')+' — '+row.current+' -> '+row.latest,'#d29922');
          }} else {{
            upgTermLine('{"OK" if lang_en else "OK"} '+row.ip+(row.name?' ('+row.name+')':'')+' — '+row.current,'#3fb950');
          }}
        }}
      }});
      if(j.done < total) {{
        _upgPollCheckJob(job_id, total, j.results.length, checkBtn);
      }} else {{
        var ok=_upgCheckRes.filter(r=>r.ok).length;
        var fail=_upgCheckRes.filter(r=>!r.ok).length;
        var hasUpd=_upgCheckRes.filter(r=>r.ok&&r.latest!=='?'&&r.current!==r.latest).length;
        upgTermLine('─────────────────────────────────────────','#484f58');
        upgTermLine((hasUpd
          ?'{"Updates available:" if lang_en else "Aggiornamenti disponibili:"} '+hasUpd
          :'{"All up to date." if lang_en else "Tutti aggiornati."}')
          +'  OK '+ok+'  x '+fail, hasUpd?'#d29922':'#3fb950');
        checkBtn.disabled=false;
        document.getElementById('upgInstallBtn').disabled=(hasUpd===0);
        document.getElementById('upgDownloadBtn').disabled=(hasUpd===0);
        // Show results list
        var rl=document.getElementById('upgOnlineResults');
        rl.style.display='block';
        rl.innerHTML=_upgCheckRes.map(function(row){{
          if(!row.ok) return '<div class="upg-res-row">'
            +'<span class="upg-res-dot"></span>'
            +'<span class="upg-res-ip">'+row.ip+'</span>'
            +'<span class="upg-res-name">'+(row.name||'—')+'</span>'
            +'<span class="upg-res-ver fail">'+(row.msg||'error')+'</span>'
            +'</div>';
          var hasUpd2=row.latest!=='?'&&row.current!==row.latest;
          var verHtml=hasUpd2
            ?'<span class="upg-res-ver update">'+row.current
              +' &rarr; <a href="https://mikrotik.com/download/changelogs" target="_blank"'
              +' class="upg-chg-link" title="{"View changelog" if lang_en else "Vedi changelog"}">'+row.latest+'</a></span>'
            :'<span class="upg-res-ver ok">'+row.current+'</span>';
          return '<div class="upg-res-row">'
            +'<span class="upg-res-dot'+(hasUpd2?' update':'')+'"></span>'
            +'<span class="upg-res-ip">'+row.ip+'</span>'
            +'<span class="upg-res-name">'+(row.name||'—')+'</span>'
            +verHtml+'</div>';
        }}).join('');
      }}
    }} catch(e) {{
      upgTermLine('x Poll error: '+e,'#f85149');
      checkBtn.disabled=false;
    }}
  }},700);
}}

async function upgDownloadOnly() {{
  var ips=upgGetIPs();
  if(!ips.length){{alert('{"Select at least one router." if lang_en else "Seleziona almeno un router."}');return;}}
  if(!confirm('{"Download updates on selected routers (no reboot)?" if lang_en else "Scaricare gli aggiornamenti sui router selezionati (senza riavvio)?"}'))return;
  document.getElementById('upgDownloadBtn').disabled=true;
  document.getElementById('upgInstallBtn').disabled=true;
  document.getElementById('upgCheckBtn').disabled=true;
  document.getElementById('upgTerminal').innerHTML='';
  upgTermLine('{"Downloading updates (no install)…" if lang_en else "Download aggiornamenti (senza installazione)…"}','#79c0ff');
  var fd=new URLSearchParams();
  fd.append('ips',ips.join(','));
  fd.append('cred_id',_upgGetCred());
  fd.append('channel',_upgGetChannel());
  try {{
    var r=await fetch('/api/ros-download',{{method:'POST',body:fd}});
    var d=await r.json();
    document.getElementById('upgDownloadBtn').disabled=false;
    document.getElementById('upgCheckBtn').disabled=false;
    if(!d.ok){{upgTermLine('x '+d.msg,'#f85149');return;}}
    upgTermLine('{"Download complete. Ready to install." if lang_en else "Download completato. Pronto per installazione."}','#3fb950');
    var rl=document.getElementById('upgOnlineResults');
    rl.style.display='block';
    rl.innerHTML=d.results.map(function(row){{
      var cls=row.ok?'ok':'fail';
      return '<div class="upg-res-row">'
        +'<span class="upg-res-dot'+(row.ok?' update':'')+'"></span>'
        +'<span class="upg-res-ip">'+row.ip+'</span>'
        +'<span class="upg-res-name">'+(row.name||'—')+'</span>'
        +'<span class="upg-res-ver '+cls+'">'+(row.msg||'')+'</span></div>';
    }}).join('');
    document.getElementById('upgInstallBtn').disabled=false;
  }} catch(e) {{
    document.getElementById('upgDownloadBtn').disabled=false;
    document.getElementById('upgCheckBtn').disabled=false;
    upgTermLine('x '+e,'#f85149');
  }}
}}

async function upgInstallOnline() {{
  var ips=upgGetIPs();
  if(!ips.length){{alert('! {T("Seleziona almeno un router.")}');return;}}
  if(!confirm('{"Install updates and reboot the selected routers?" if lang_en else "Installare gli aggiornamenti e riavviare i router selezionati?"}'))return;
  document.getElementById('upgInstallBtn').disabled=true;
  document.getElementById('upgDownloadBtn').disabled=true;
  document.getElementById('upgCheckBtn').disabled=true;
  document.getElementById('upgTerminal').innerHTML='';
  upgTermLine('{"Downloading and installing…" if lang_en else "Download e installazione in corso…"}','#79c0ff');
  var fd=new URLSearchParams();
  fd.append('ips',ips.join(','));
  fd.append('cred_id',_upgGetCred());
  fd.append('channel',_upgGetChannel());
  try {{
    var r=await fetch('/api/ros-install',{{method:'POST',body:fd}});
    var d=await r.json();
    document.getElementById('upgInstallBtn').disabled=false;
    document.getElementById('upgDownloadBtn').disabled=false;
    document.getElementById('upgCheckBtn').disabled=false;
    if(!d.ok){{upgTermLine('x '+d.msg,'#f85149');return;}}
    upgTermLine('{"Install complete — routers rebooting." if lang_en else "Installazione avviata — i router si riavvieranno."}','#3fb950');
    var rl=document.getElementById('upgOnlineResults');
    rl.style.display='block';
    rl.innerHTML=d.results.map(function(row){{
      var cls=row.ok?'ok':'fail';
      return '<div class="upg-res-row">'
        +'<span class="upg-res-dot'+(row.ok?' update':'')+'"></span>'
        +'<span class="upg-res-ip">'+row.ip+'</span>'
        +'<span class="upg-res-name">'+(row.name||'—')+'</span>'
        +'<span class="upg-res-ver '+cls+'">'+(row.msg||'')+'</span></div>';
    }}).join('');
  }} catch(e) {{
    document.getElementById('upgInstallBtn').disabled=false;
    document.getElementById('upgDownloadBtn').disabled=false;
    document.getElementById('upgCheckBtn').disabled=false;
    upgTermLine('x '+e,'#f85149');
  }}
}}

// ── Tab 2: .npk upload ──────────────────────────────────────────
let _upgPollTimer=null;
async function upgUploadNpk() {{
  var ips=upgGetIPs();
  var file=document.getElementById('upgNpkFile').files[0];
  var reboot=document.getElementById('upgReboot').checked;
  var stat=document.getElementById('upgNpkStatus');
  if(!ips.length){{stat.textContent='! {T("Seleziona almeno un router.")}';return;}}
  if(!file){{stat.textContent='! {"Select a .npk file." if lang_en else "Seleziona un file .npk."}';return;}}
  var btn=document.getElementById('upgNpkBtn');
  var wrap=document.getElementById('upgNpkProgress');
  var bar=document.getElementById('upgNpkBar');
  var msg=document.getElementById('upgNpkMsg');
  btn.disabled=true; stat.textContent='';
  wrap.style.display='block'; bar.style.width='0%'; msg.textContent='{"Uploading…" if lang_en else "Caricamento…"}';
  var fd=new FormData();
  fd.append('file',file); fd.append('ips',ips.join(','));
  fd.append('reboot',reboot?'1':'');
  fd.append('cred_id',_upgGetCred());
  try {{
    var r=await fetch('/upload_npk',{{method:'POST',body:fd}});
    var d=await r.json();
    if(!d.ok){{msg.textContent='x '+d.msg;btn.disabled=false;return;}}
    upgPollNpk(d.job_id,d.total,bar,msg,btn);
  }} catch(e){{msg.textContent='x '+e;btn.disabled=false;}}
}}

function upgPollNpk(job_id,total,bar,msg,btn) {{
  clearTimeout(_upgPollTimer);
  _upgPollTimer=setTimeout(async function(){{
    var j=await fetch('/api/job?id='+job_id).then(r=>r.json());
    var pct=total>0?Math.round(j.done/total*100):0;
    bar.style.width=pct+'%';
    var ok=j.results.filter(r=>r.ok).length, fail=j.results.filter(r=>!r.ok).length;
    msg.textContent=j.done+' / '+total+'  OK '+ok+'  x '+fail;
    var rl=document.getElementById('upgNpkResults');
    rl.style.display='block';
    rl.innerHTML=j.results.map(function(row){{
      var ico=row.ok?'<span class="ok-ico">✓</span>':'<span class="fail-ico">x</span>';
      return '<div class="upg-row">'+ico+'<span class="upg-ip">'+row.ip+'</span><span class="upg-name">'+(row.name||'—')+'</span><span class="upg-status">'+(row.msg||'')+'</span></div>';
    }}).join('');
    if(j.done<total){{upgPollNpk(job_id,total,bar,msg,btn);}}
    else{{btn.disabled=false;msg.style.color=fail===0?'var(--green)':'var(--red)';}}
  }},600);
}}
</script>
""", session=session, page_key="upgrade")

    def render_uploads_page(self, session=None):
        if not UPLOADS_LOG:
            content = "<div class='card'><div class='card-body' style='color:var(--text2)'>No uploads recorded yet.</div></div>"
        else:
            content = ""
            for script in sorted(UPLOADS_LOG.keys()):
                entries = UPLOADS_LOG[script]
                rows_html = ""
                for e in reversed(entries[-500:]):
                    rows_html += f"""<tr>
                      <td style="color:var(--text2)">{e.get('when','')}</td>
                      <td style="color:var(--accent2)">{e.get('ip','')}</td>
                      <td style="color:var(--text);font-weight:600">{e.get('name','')}</td>
                    </tr>"""
                content += f"""
<div class="card">
  <div class="card-header">
    <span>{script}</span>
    <span style="color:var(--text3)">{len(entries)} entries</span>
  </div>
  <div class="table-wrap">
  <table>
    <thead><tr><th>When</th><th>IP</th><th>Name</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  </div>
</div>"""

        return self._page_shell("Uploads Log", content, session=session)

    def render_runs_page(self, session=None):
        if not RUNS_LOG:
            content = "<div class='card'><div class='card-body' style='color:var(--text2)'>No runs recorded yet.</div></div>"
        else:
            rows_html = ""
            for e in reversed(RUNS_LOG[-500:]):
                ok_html = '<span class="pill pill-green">OK</span>' if e.get("ok") else '<span class="pill pill-red">FAIL</span>'
                result_escaped = (e.get("result") or "").replace("<","&lt;").replace(">","&gt;")
                rows_html += f"""<tr>
                  <td style="color:var(--text2)">{e.get('when','')}</td>
                  <td style="color:var(--accent2)">{e.get('ip','')}</td>
                  <td style="color:var(--text);font-weight:600">{e.get('name','')}</td>
                  <td style="color:var(--yellow)">{e.get('script','')}</td>
                  <td>{ok_html}</td>
                  <td style="color:var(--text2);max-width:400px;overflow:hidden;text-overflow:ellipsis;" title="{result_escaped}">{result_escaped[:80]}</td>
                </tr>"""
            content = f"""
<div class="card">
  <div class="card-header">
    <span>Execution Log</span>
    <span style="color:var(--text3)">{len(RUNS_LOG)} total entries (showing last 500)</span>
  </div>
  <div class="table-wrap">
  <table>
    <thead><tr><th>When</th><th>IP</th><th>Name</th><th>Script</th><th>Result</th><th>Output</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  </div>
</div>"""

        return self._page_shell("Runs Log", content, session=session)

    def _shared_header_html(self, session, active_page="", extra_controls=""):
        """
        Two-row header:
          Row 1 (navy): brand + version + username + logout
          Row 2 (white sub-nav): page navigation links
        active_page: 'home','dashboard','topology','discovery','stats','upload','backup','users'
        extra_controls: optional HTML shown in the sub-nav row (right side)
        """
        username = (session or {}).get("username", "")
        role     = (session or {}).get("role", "viewer")
        is_admin = (role == "admin")

        is_elevated = role in ELEVATED_ROLES

        # Nav bar: operational items (admin_only=True → admin-only, elevated_only=True → elevated+)
        # (key, href, label, admin_only, elevated_only)
        NAV_ITEMS = [
            ("home",        "/home",        T("Home"),                False, False),
            ("dashboard",   "/",            T("Dashboard"),           False, False),
            ("topology",    "/topology",    T("Site Manager"),        False, False),
            ("backup",      "/backup",      "Backup",                 False, True),
            ("discovery",   "/discovery",   T("Network Discovery"),   False, False),
            ("upload",      "/upload",      "Script Upload",          True,  False),
        ]

        # MGMT dropdown — full list for admin, subset for manager/technician
        ALL_MGMT = [
            ("/stats",       T("Statistiche"),         "stats",       False),
            ("/users",       T("Utenti"),              "users",       False),  # filtered below
            ("/log",         T("Log"),                 "log",         False),
            ("/credentials", "Credentials",            "credentials", False),
            ("/settings",    T("Impostazioni"),        "settings",    False),
            ("/guide",       T("Guida"),               "guide",       False),
            ("/upgrade",     T("Upgrade RouterOS"),    "upgrade",     False),  # admin + manager only
        ]

        nav_items_html = ""
        for key, href, label, admin_only, elevated_only in NAV_ITEMS:
            if admin_only and not is_admin:
                continue
            if elevated_only and not is_elevated:
                continue
            if key == "backup" and not _can_do(session, "backup"):
                continue
            if key == active_page:
                nav_items_html += f'<span class="subnav-item subnav-active">{label}</span>'
            else:
                nav_items_html += f'<a class="subnav-item" href="{href}">{label}</a>'

        # MGMT dropdown (admin sees all; elevated sees non-admin items)
        if is_elevated:
            visible_mgmt = [
                (h, l, k) for h, l, k, ao in ALL_MGMT
                if (not ao or is_admin)
                and (k != "users"    or is_admin or _can_do(session, "users_write"))
                and (k != "credentials" or _can_do(session, "credentials"))
                and (k != "upgrade"  or _can_do(session, "upgrade"))
                and (k != "log"      or True)   # log readable by all elevated
            ]
            mgmt_links = "".join(
                f'<a href="{href}" class="mgmt-drop-item{" mgmt-drop-active" if active_page == key else ""}">'
                f'{label}</a>'
                for href, label, key in visible_mgmt
            )
            mgmt_html = f"""<div class="mgmt-wrap">
  <div class="mgmt-btn">MGMT</div>
  <div class="mgmt-drop"><div class="mgmt-drop-inner">{mgmt_links}</div></div>
</div>"""
        else:
            mgmt_html = ""

        # Page label: shown ONLY for MGMT pages (right side of subnav)
        _MGMT_LABEL_META = {
            "stats":       T("Statistiche"),
            "users":       T("Utenti"),
            "settings":    T("Impostazioni"),
            "log":         T("Log"),
            "credentials": "Credentials",
            "upgrade":     T("Upgrade RouterOS"),
        }
        if active_page in _MGMT_LABEL_META:
            _lbl = _MGMT_LABEL_META[active_page]
            page_label_html = (
                f'<span style="display:inline-flex;align-items:center;gap:4px;'
                f'font-size:11px;font-family:var(--sans);">'
                f'<span style="color:var(--text3);font-weight:500;letter-spacing:.3px;">MGMT</span>'
                f'<span style="color:var(--text3);">›</span>'
                f'<span style="color:var(--text2);font-weight:600;">{_lbl}</span>'
                f'</span>'
            )
        else:
            page_label_html = ""

        subnav_right = page_label_html
        if page_label_html and extra_controls:
            subnav_right += '<span style="width:1px;height:14px;background:var(--border2);flex-shrink:0;"></span>'
        subnav_right += extra_controls

        logout_label  = T("Logout")

        # Real-Time Monitoring banner (shown on ALL pages when active)
        _rtm_active = bool(_app_cfg.get("rtm_enabled"))
        _rtm_banner_html = (
            '<div id="rtm-banner" style="background:linear-gradient(90deg,#c0392b,#e74c3c);'
            'color:#fff;text-align:center;font-size:11.5px;font-weight:700;letter-spacing:.5px;'
            'padding:5px 16px;display:flex;align-items:center;justify-content:center;gap:8px;">'
            '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
            'background:#fff;animation:rtm-pulse .8s infinite ease-in-out;"></span>'
            'REAL TIME MONITORING ATTIVO'
            '<button onclick="toggleRTM()" style="background:rgba(255,255,255,.2);'
            'border:1px solid rgba(255,255,255,.4);color:#fff;border-radius:5px;'
            'padding:2px 10px;font-size:11px;cursor:pointer;font-weight:600;margin-left:6px;">'
            'Disattiva</button>'
            '</div>'
        ) if _rtm_active else ""

        return f"""
<div class="header-sticky-wrap">
<style>
@keyframes rtm-pulse{{0%,100%{{opacity:1;transform:scale(1);}}50%{{opacity:.35;transform:scale(1.5);}}}}
.mgmt-wrap{{position:relative;display:inline-flex;align-items:center;}}
.mgmt-btn{{
  padding:4px 10px;border-radius:6px;font-size:10px;font-weight:800;
  letter-spacing:.8px;cursor:pointer;user-select:none;
  background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.25);
  color:rgba(255,255,255,.9);transition:all .15s;
}}
.mgmt-wrap:hover .mgmt-btn{{background:var(--accent);border-color:var(--accent);color:#fff;}}
.mgmt-drop{{
  visibility:hidden;opacity:0;pointer-events:none;
  position:absolute;top:100%;right:0;
  padding-top:8px;
  min-width:190px;z-index:9999;
  transition:opacity .15s ease, visibility 0s linear .5s;
}}
.mgmt-drop-inner{{
  background:var(--bg2);border:1px solid var(--border2);border-radius:10px;
  box-shadow:0 8px 28px rgba(0,0,0,.18);padding:6px;
  display:flex;flex-direction:column;gap:2px;
}}
.mgmt-wrap:hover .mgmt-drop{{
  visibility:visible;opacity:1;pointer-events:all;
  transition:opacity .15s ease, visibility 0s linear 0s;
}}
.mgmt-drop-item{{
  padding:8px 12px;border-radius:7px;font-size:12px;font-weight:500;
  color:var(--text2);text-decoration:none;transition:all .12s;display:block;
}}
.mgmt-drop-item:hover{{background:var(--bg3);color:var(--text);}}
.mgmt-drop-active{{color:var(--accent)!important;font-weight:700;background:var(--accent3);}}
</style>
{_rtm_banner_html}<div class="topbar-accent"></div>
<div class="header-top-bar">
  <div class="header-brand">
    <span class="logo-rosm">ROSM</span>
    <span class="header-version" onclick="document.getElementById('changelogModal').classList.add('open')"
          title="v{APP_VERSION} {APP_STAGE}">v{APP_VERSION} {APP_STAGE}</span>
  </div>
  <div style="display:flex;align-items:center;gap:10px;">
    <span style="font-size:12px;color:rgba(255,255,255,.75);">{username}</span>
    {mgmt_html}
    <a class="btn header-logout-btn" href="/logout">{logout_label}</a>
  </div>
</div>
<div class="subnav-bar">
  <div class="subnav-links">
    {nav_items_html}
  </div>
  <div class="subnav-extra">{subnav_right}</div>
</div>
</div>
<script>
function toggleRTM(){{
  fetch('/api/rtm_toggle',{{method:'POST'}})
    .then(function(r){{return r.json();}})
    .then(function(){{location.reload();}});
}}
</script>"""

    def _changelog_modal_html(self):
        cl_html = ""
        for i, (ver, date, items) in enumerate(CHANGELOG):
            tag_cls = "cl-tag cl-tag-latest" if i == 0 else "cl-tag"
            lis = "".join(f"<li>{it}</li>" for it in items)
            cl_html += f'<div class="cl-version"><span class="{tag_cls}">v{ver}</span><span class="cl-date">{date}</span><ul class="cl-list">{lis}</ul></div>'
        close_btn = ('<button onclick="document.getElementById(\'changelogModal\').classList.remove(\'open\')"'
                     ' style="background:var(--accent);border:none;color:#fff;padding:7px 18px;'
                     'border-radius:var(--r);cursor:pointer;font-weight:600;font-size:12px;">Chiudi</button>')
        _cr_close_lbl = "Close" if LANGUAGE == "en" else "Chiudi"
        credits_close_btn = ('<button onclick="document.getElementById(\'creditsModal\').style.display=\'none\'"'
                             ' style="background:var(--accent);border:none;color:#fff;padding:7px 18px;'
                             f'border-radius:var(--r);cursor:pointer;font-weight:600;font-size:12px;">{_cr_close_lbl}</button>')
        return f"""<div id="changelogModal" onclick="if(event.target===this)this.classList.remove('open')">
  <div class="changelog-box">
    <h2>Changelog — ROSM</h2>
    {cl_html}
    <div style="margin-top:16px;text-align:right;">{close_btn}</div>
  </div>
</div>
<div id="creditsModal" onclick="if(event.target===this)this.style.display='none'"
     style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);
            z-index:9000;align-items:center;justify-content:center;">
  <div style="background:var(--bg2);border:1px solid var(--border2);border-radius:14px;
              box-shadow:0 20px 60px rgba(0,0,0,.22);max-width:500px;width:92%;
              max-height:86vh;overflow-y:auto;padding:40px;">

    <div style="text-align:center;margin-bottom:28px;">
      <div style="font-size:20px;font-weight:700;letter-spacing:-.3px;color:var(--text);
                  font-family:var(--sans);">ROSM</div>
      <div style="font-size:11px;color:var(--text3);margin-top:6px;font-family:var(--mono);">
        Router OS Manager &nbsp;·&nbsp; v{APP_VERSION}
      </div>
    </div>

    <p style="font-size:13px;color:var(--text2);line-height:1.85;
              font-family:var(--sans);margin-bottom:28px;">
      {"ROSM was born from the need to manage fleets of MikroTik routers without opening Winbox on every single device. Developed and maintained by <strong>Jacopo Cipriani</strong>, an Italian ICT consultant with a passion for network infrastructure — who spends his nights writing code that, he hopes, makes life a little easier for those who work in this sector." if LANGUAGE=="en" else "ROSM nasce dall'esigenza concreta di gestire flotte di router MikroTik senza aprire Winbox su ogni singola macchina. Sviluppato e mantenuto da <strong>Jacopo Cipriani</strong>, consulente ICT italiano con una passione per le infrastrutture di rete — che passa le notti a scrivere codice che, spera, renda la vita un po' piu semplice a chi lavora in questo settore."}
    </p>

    <div style="border-top:1px solid var(--border);margin-bottom:22px;"></div>

    <div style="font-size:10px;font-weight:700;color:var(--text3);text-transform:uppercase;
                letter-spacing:1.2px;font-family:var(--sans);margin-bottom:18px;">
      {"Acknowledgements" if LANGUAGE=="en" else "Ringraziamenti"}
    </div>

    <div style="display:flex;flex-direction:column;gap:14px;margin-bottom:18px;">

      <div>
        <div style="font-size:12px;font-weight:600;color:var(--text);font-family:var(--sans);margin-bottom:2px;">Enrico G.</div>
        <div style="font-size:12px;color:var(--text3);font-family:var(--sans);">{"For introducing me to the MikroTik world." if LANGUAGE=="en" else "Per avermi fatto scoprire il mondo MikroTik."}</div>
      </div>

      <div>
        <div style="font-size:12px;font-weight:600;color:var(--text);font-family:var(--sans);margin-bottom:2px;">Lorenzo B.</div>
        <div style="font-size:12px;color:var(--text3);font-family:var(--sans);">{"For teaching me the basics and sparking my passion for this sector." if LANGUAGE=="en" else "Per avermi insegnato le basi e appassionato a questo settore."}</div>
      </div>

      <div>
        <div style="font-size:12px;font-weight:600;color:var(--text);font-family:var(--sans);margin-bottom:2px;">Marco B.</div>
        <div style="font-size:12px;color:var(--text3);font-family:var(--sans);">{"Friend and reference point, always pushed me to take one more step forward." if LANGUAGE=="en" else "Amico e punto di riferimento, mi ha sempre spinto a fare un passo in piu."}</div>
      </div>

    </div>

    <div style="font-size:12px;color:var(--text3);font-style:italic;line-height:1.7;
                font-family:var(--sans);margin-bottom:4px;">
      <strong style="color:var(--text2);font-style:normal;">L.</strong> —
      {"for putting up with me when I spend sleepless nights writing lines and lines of code." if LANGUAGE=="en" else "per sopportarmi quando passo le notti insonni a scrivere righe e righe di codice."}
    </div>
    <div style="font-size:11px;color:var(--text3);font-style:italic;font-family:var(--sans);margin-bottom:26px;">
      {"Without even one of them, this tool would not exist today." if LANGUAGE=="en" else "Senza anche uno di loro, questo tool non sarebbe esistito."}
    </div>

    <div style="border-top:1px solid var(--border);margin-bottom:18px;"></div>

    <div style="font-size:12px;color:var(--text3);line-height:1.8;font-family:var(--sans);margin-bottom:22px;">
      {"ROSM is free and always will be — " if LANGUAGE=="en" else "ROSM e gratuito e lo sara per sempre — "}
      <a href="mailto:Rosman.mail@icloud.com" style="color:var(--accent);">Rosman.mail@icloud.com</a>
      <br><span style="font-size:11px;">
        {"UI and code built with the help of " if LANGUAGE=="en" else "UI e codice sviluppati con il supporto di "}
        <span style="display:inline-block;background:#c05621;color:#fff;font-size:8px;
                     padding:2px 5px;border-radius:3px;font-weight:700;letter-spacing:.3px;
                     vertical-align:middle;">Claude</span>
        {"(Anthropic AI)." if LANGUAGE=="en" else "(Anthropic AI)."}
      </span>
      <br>
      <a href="https://ko-fi.com/rosm" target="_blank" rel="noopener"
         style="display:inline-flex;align-items:center;gap:5px;margin-top:10px;
                color:var(--accent);font-size:11px;font-weight:600;text-decoration:none;">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M17 8h1a4 4 0 1 1 0 8h-1"></path>
          <path d="M3 8h14v9a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V8z"></path>
          <line x1="6" y1="2" x2="6" y2="4"></line>
          <line x1="10" y1="2" x2="10" y2="4"></line>
          <line x1="14" y1="2" x2="14" y2="4"></line>
        </svg>
        {"Buy me a beer on Ko-fi" if LANGUAGE=="en" else "Offrimi una birra su Ko-fi"}
      </a>
    </div>

    <div style="text-align:right;">{credits_close_btn}</div>
  </div>
</div>"""

    def _page_shell(self, title, content, session=None, page_key="",
                    extra_controls="", body_modals=""):
        header      = self._shared_header_html(session, page_key, extra_controls)
        dark_attr   = ' data-theme="dark"' if _user_dark_mode(session) else ''
        # Inject in-app tour overlay if ?tour=N is present in the URL
        _qs_tour = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _tour_block = _get_tour_js((_qs_tour.get("tour") or [""])[0])
        return f"""<!DOCTYPE html>
<html lang="en"{dark_attr}>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — ROSM</title>
{FAVICON_TAG}
<style>
{COMMON_CSS}
</style>
</head>
<body>

{header}

<div id="changeLogPanel"></div>

{body_modals}
{self._changelog_modal_html()}

<div class="container">
  {content}
</div>

<div class="version-footer">
  ROSM v{APP_VERSION} {APP_STAGE} &nbsp;·&nbsp;
  <a href="#" onclick="document.getElementById('changelogModal').classList.add('open');return false;">Changelog</a>
  &nbsp;·&nbsp;
  <a href="#" onclick="document.getElementById('creditsModal').style.display='flex';return false;">Credits</a>
</div>


<script>
(function(){{
  if(!sessionStorage.getItem('rosm_debug_mode'))return;
  var bar=document.createElement('div');
  bar.id='_dbg_active_bar';
  bar.style.cssText='position:fixed;top:0;left:0;right:0;z-index:99990;background:#d97706;'+
    'color:#fff;font-size:12px;font-weight:700;padding:7px 16px;display:flex;align-items:center;'+
    'gap:10px;font-family:var(--sans);box-shadow:0 2px 8px rgba(0,0,0,.25);letter-spacing:.03em;';
  bar.innerHTML='<span>Debug mode active</span>'+
    '<button onclick="window._rosmDbgDeactivate()" style="margin-left:auto;background:rgba(0,0,0,.25);'+
    'color:#fff;border:1px solid rgba(255,255,255,.5);border-radius:6px;padding:3px 12px;'+
    'font-size:11px;cursor:pointer;font-weight:700;font-family:inherit;">Disattiva e scarica</button>';
  document.body.insertBefore(bar,document.body.firstChild);
  document.body.style.paddingTop=(parseInt(document.body.style.paddingTop||0)+36)+'px';
}})();
window._rosmDbgDeactivate=async function(){{
  sessionStorage.removeItem('rosm_debug_mode');
  try{{
    var r=await fetch('/api/debug');
    var j=await r.json();
    var b=new Blob([JSON.stringify(j,null,2)],{{type:'application/json'}});
    var u=URL.createObjectURL(b);
    var a=document.createElement('a');
    a.href=u;a.download='rosm_debug_'+new Date().toISOString().replace(/[:.]/g,'-').substring(0,19)+'.json';
    document.body.appendChild(a);a.click();document.body.removeChild(a);
    URL.revokeObjectURL(u);
  }}catch(e){{alert('Debug download error: '+e);}}
  var bar=document.getElementById('_dbg_active_bar');
  if(bar)bar.remove();
}};
</script>

{_tour_block}
</body>
</html>
"""

    # ------------------------------------------------------------------
    def _build_state_payload(self):
        return {
            "ping_running":    PING_RUNNING,
            "ssh_active":      SSH_ACTIVE,
            "auto_enabled":    AUTO_ENABLED,
            "auto_interval":   AUTO_INTERVAL,
            "ssh_working_ips": [r["ip"] for r in ROUTERS if r["ssh_status"] == "WORKING"],
            "ssh_pending_ips": [r["ip"] for r in ROUTERS if r["ssh_status"] == "PENDING"],
            "run_active_ips":  [r["ip"] for r in ROUTERS if r["run_status"] == "RUNNING"],
            "ping_history":    list(PING_HISTORY),
            "change_log":      list(CHANGE_LOG),
            "custom_cols":     list(CUSTOM_COLS),
            "custom_col_data": dict(CUSTOM_COL_DATA),
            "sites":           dict(SITES),
            "routers": [
                {k: v for k, v in r.items() if k != "password"}
                for r in ROUTERS
            ],
        }

    def _handle_sse(self):
        """Server-Sent Events: push state only when it changes (max 1s latency)."""
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            last_hash = None
            while True:
                payload  = self._build_state_payload()
                cur_hash = hashlib.md5(
                    json.dumps(payload, sort_keys=True).encode()
                ).hexdigest()
                if cur_hash != last_hash:
                    msg = f"data: {json.dumps(payload)}\n\n"
                    self.wfile.write(msg.encode())
                    self.wfile.flush()
                    last_hash = cur_hash
                time.sleep(1)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    # ------------------------------------------------------------------
    @staticmethod
    def _apply_translations(html: str) -> str:
        """Replace Italian text with English in the rendered HTML.
        Sorted longest-first so 'Salva configurazione' is replaced before 'Salva'.
        Skips pairs where IT == EN (no-op). Only runs when LANGUAGE != 'it'."""
        pairs = sorted(
            [(k, v) for k, v in _T_EN.items() if k != v],
            key=lambda x: -len(x[0])
        )
        for it_str, en_str in pairs:
            html = html.replace(it_str, en_str)
        return html

    def respond(self, html: str) -> None:
        if LANGUAGE != "it":
            html = self._apply_translations(html)
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location="/"):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()


# ─────────────────────────────────────────────────────────────────
# § Startup
# ─────────────────────────────────────────────────────────────────
def _kill_existing_instance():
    import signal
    my_pid = str(os.getpid())
    killed = False

    # 1. Kill by process name (dashboard.py)
    try:
        pids = subprocess.check_output(["pgrep", "-f", "dashboard.py"], text=True).split()
        for p in pids:
            p = p.strip()
            if p != my_pid:
                try:
                    os.kill(int(p), signal.SIGTERM)
                    print(f"ROSM — istanza precedente terminata (PID {p}), riavvio...")
                    killed = True
                except ProcessLookupError:
                    pass
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # 2. Fallback: kill whatever is holding port 8080 (lsof)
    try:
        out = subprocess.check_output(
            ["lsof", "-ti", "tcp:8080"], text=True, stderr=subprocess.DEVNULL
        ).split()
        for p in out:
            p = p.strip()
            if p and p != my_pid:
                try:
                    os.kill(int(p), signal.SIGTERM)
                    print(f"ROSM — processo sulla porta 8080 terminato (PID {p})")
                    killed = True
                except ProcessLookupError:
                    pass
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    if killed:
        # Wait up to 3s for the port to be released; SIGKILL if still alive after 1.5s
        time.sleep(1.5)
        try:
            out = subprocess.check_output(
                ["lsof", "-ti", "tcp:8080"], text=True, stderr=subprocess.DEVNULL
            ).split()
            for p in out:
                p = p.strip()
                if p and p != my_pid:
                    try:
                        os.kill(int(p), signal.SIGKILL)
                        print(f"ROSM — SIGKILL inviato a PID {p} (porta ancora occupata)")
                    except ProcessLookupError:
                        pass
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        time.sleep(0.8)

_kill_existing_instance()

_restarted_by = next(
    (a[len("--restarted-by="):] for a in sys.argv[1:] if a.startswith("--restarted-by=")),
    None
)
if _restarted_by:
    app_log("system", "info",
            f"ROSM v{APP_VERSION} riavviato su porta 8080 (richiesto da: '{_restarted_by}')")
else:
    app_log("system", "info", f"ROSM v{APP_VERSION} avviato su porta 8080")
threading.Thread(target=monitor,            daemon=True).start()
threading.Thread(target=backup_monitor,     daemon=True).start()
_load_ztp()
threading.Thread(target=_site_scan_monitor, daemon=True, name="site-scan-monitor").start()
# Restore RTM if it was active before restart
if _app_cfg.get("rtm_enabled"):
    _start_rtm()
# Load OUI cache from disk, then refresh from IEEE in background
_load_oui_cache()
threading.Thread(target=_download_oui_db, daemon=True).start()
print(f"ROSM — Router OS Manager: http://localhost:8080")
ThreadingHTTPServer.allow_reuse_address = True   # must be set before socket creation
_bind_addrs = _get_bind_addresses(_app_cfg)
ALL_SERVERS = []
for _addr in _bind_addrs:
    try:
        ALL_SERVERS.append(ThreadingHTTPServer((_addr, 8080), Handler))
    except OSError as _bind_exc:
        app_log("system", "error", f"Bind su {_addr}:8080 fallito — {_bind_exc}")
if not ALL_SERVERS:
    ALL_SERVERS = [ThreadingHTTPServer(("0.0.0.0", 8080), Handler)]
server = ALL_SERVERS[0]
for _extra_srv in ALL_SERVERS[1:]:
    threading.Thread(target=_extra_srv.serve_forever, daemon=True).start()
server.serve_forever()