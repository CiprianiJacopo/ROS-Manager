# ROSM — Code Overview (Beta)

A single-file Python server (`dashboard.py`) for centrally managing fleets of MikroTik routers: web dashboard, backups, monitoring, provisioning, RouterOS updates pushed to routers. Distributed as an installer package for macOS (`.pkg`) and Windows (`.exe`).

The Italian version (`CODE_OVERVIEW_IT.md`) is the reference copy — this English version is a translation of it.

## License

GPLv3 — see `LICENSE`. Forks and distributed modified versions must also stay open source under the GPL. Third-party dependencies (paramiko, cryptography, pyotp, segno, bcrypt, pynacl, psutil — see `requirements.txt`) carry their own licenses (MIT/BSD/Apache/LGPL); keep their copyright notices when distributing the package.

## Repository layout

- **`dashboard.py`** — the entire application: server, API, HTML/CSS/JS frontend, business logic. Single file, no framework.
- **`menubar.py`** / **`tray_win.py`** — the macOS menu bar / Windows system tray icon helper, launched alongside `dashboard.py`.
- **`requirements.txt`** — Python dependencies.
- **`build_mac_pkg.sh`** / **`build_win_pkg.sh`** / **`build_all.sh`** — build the installer packages. `VERSION=` near the top of the first two; `build_all.sh` runs both in sequence and also auto-generates `version.json` at the end.
- **`version.json`** — `{"version": ..., "date": ..., "changelog": [...]}`, read by the in-app update checker.
- **`ztp.py`** — sandbox file for prototyping new features before they're merged into `dashboard.py`. Not wired into the running app — don't delete it even if it looks unused.
- **`LICENSE`** — GPLv3 text.

This branch also contains features prototyped but not yet exposed in the main UI: **ZTP Provisioning** (route `/provision`, functional but hidden from nav/home) and **Site Auto-Scan** (a third tab inside Site Manager `/topology` — `/site-scan` now just redirects to `/topology`).

## Architecture

Everything runs through Python's stdlib `http.server` (`ThreadingHTTPServer`) — no web framework, no build step, no bundler. The file you read is the file that runs.

## Code layout

Search `dashboard.py` for `§ NAME` to jump to a section (there's an index comment block at the very top of the file). Roughly, top to bottom: version/changelog constants → i18n → encryption helpers → device/site/user data stores → network discovery & fingerprinting → auth/sessions → SSH helpers → backup manager → CSS → frontend JS template → HTTP request handler (most routes and page renderers) → server startup.

## Data never lives in the source

All real data (routers, users, sites, credentials, settings, encryption key, recovery code) is stored in separate JSON files created at first run, in the same directory as `dashboard.py` (`devices.json`, `users.json`, `config.json`, `.rosm_key`, etc.) — never inside the source file itself. A fresh clone or a fresh install never contains anyone's data.

## Working on the code

- Always edit `dashboard.py` (or the build scripts) directly — never the live installed copy (typically `/usr/local/rosm/dashboard.py` on macOS). Reinstall after editing to test.
- No emoji, in code, comments, or commit messages.

## Versioning

`APP_VERSION` in `dashboard.py`, `VERSION=` in `build_mac_pkg.sh`/`build_win_pkg.sh`, and the `"version"` field in `version.json` must always match — the auto-update mechanism (`/api/check-update`) compares `APP_VERSION` against the `version.json` published on this repository. Bump all three together.

## A few notable design decisions

Explanations of the "why" behind non-obvious choices that you can't get just from reading the code — useful so they don't get undone by accident.

### No `subprocess` for ping/reachability — macOS crash

`dashboard.py` is multi-threaded (HTTP server + monitoring threads). On macOS, when a multi-threaded process calls `fork()` (including via `subprocess.run`/`Popen`/`check_output`), Apple's Network.framework atfork handlers can SIGSEGV in the child process (crash report featuring `nw_settings_child_has_forked()` / `_os_log_preferences_refresh`). Practical effect observed: pinging with `subprocess.run(["ping", ...])` made ONLINE routers appear OFFLINE (the child process crashed before it could respond) and showed macOS's crash reporter to the user.

Because of this:
- `_tcp_reachable()` (a TCP connect on common ports: 22, 8291, 8728, 80, 443, 23) replaced `subprocess.run(ping)` for the reachability check in `fingerprint_host()` and `_ping_one()`. No fork, no crash.
- `_get_mac_from_arp()` entirely skips the `subprocess.check_output(["arp", ...])` call on macOS (`sys.platform == "darwin"`) — same crash (the MAC via ARP is purely cosmetic, for OUI vendor lookup). It stays active only on Windows, where `subprocess` doesn't `fork()` so there's no problem there. On RouterOS routers with SSH credentials configured, the MAC still arrives via SSH (`_ssh_connect_creds`), a different and safe code path.
- The 3 spots that restart the process (`/settings/access-restart`, `/api/restart`, `/api/do-update`) set `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` in the environment passed to `subprocess.Popen(...)`, because there the fork is unavoidable (a new Python process genuinely needs to be launched). **Note:** this variable acts on the CHILD process's environment after exec — it's not certain it prevents the crash, which happens inside `fork()` itself, before exec. It was kept as a precautionary mitigation at those 3 spots (where the fork is mandatory and can't be eliminated), but it should not be considered a proven fix: the tested pattern remains "eliminate the fork" (see `_tcp_reachable`/`_get_mac_from_arp`), not "suppress the crash with an env var".
- If another `subprocess.*` call reached at runtime (not at cold start, when the process is still single-threaded) is needed in the future, evaluate a no-fork alternative first — don't trust `OBJC_DISABLE_INITIALIZE_FORK_SAFETY` as a fix.

### i18n: two different mechanisms for Python and JavaScript

- Strings in Python f-strings: use `T("Italian text")` — it looks up the translation in `_T_EN` (a dict near `LANGUAGE`) if `LANGUAGE == "en"`, otherwise returns the Italian text as-is. If the entry is missing from `_T_EN`, the English UI still shows the Italian text (this has happened repeatedly with tooltip `title=` attributes — always check the string is in the dict).
- Strings inside `MAIN_JS_TEMPLATE` (the JS block, a raw string with no f-string): `T()` can't be called there, since the JS runs in the browser. Pattern used: pre-translated JS variables injected at render time via the `{js_i18n}` placeholder (substituted where `main_js` is built), named `_TJSx` (e.g. `_TJSC` = "Chiudi"/"Close"). To add one: add the entry to the `_js_i18n` string where it's built, then use `'+_TJSx+'` at the right spot in the template.

### Multi-interface binding (Frontend Access — wizard and Settings)

You can choose which network interfaces to publish ROSM on, even more than one at once (not just "localhost only" / "entire network").
- Config: `bind_addresses` (a list, e.g. `["127.0.0.1", "192.168.1.8"]`) replaced `bind_address` (a single string). `_get_bind_addresses()` reads the new list with a fallback to the legacy string, for compatibility with existing installations that update in place.
- `_list_network_interfaces()` uses `psutil` (an optional dependency, soft-imported like `MFA_AVAILABLE` — if not installed, the UI degrades to just the original 2 options with no crash). Needed because there's no reliable, stdlib-only, cross-platform (macOS+Windows) way to enumerate the IPs of all active interfaces.
- The checkboxes for specific interfaces only show up in the UI if there are **2 or more** active non-loopback interfaces — otherwise there'd be no point showing them.
- "All interfaces" (`0.0.0.0`) takes precedence over any other selection (`_normalize_bind_addresses()`), since it already includes them.
- On startup, a `ThreadingHTTPServer` is created for each selected address — a single socket can't bind to several specific addresses at once — all collected in `ALL_SERVERS`. This is why the 3 restart spots close ALL sockets in `ALL_SERVERS`, not just `self.server.socket` (which is only the one that handled the current restart request): otherwise the new process can't bind on the other addresses (port still held by the old process).
- If binding on a saved address fails at startup (e.g. a disconnected interface), it's logged and skipped; if ALL binds fail, it automatically falls back to `0.0.0.0` — you're never left unreachable.

### Network Discovery — SSH credentials are optional

`fingerprint_host()` works even without `ssh_user`/`ssh_pass`: it still detects IP, open ports, device type (via SSH/HTTP banner, MAC OUI). Credentials are only needed for the next step (reading RouterOS identity/model via SSH) — neither the backend (`/api/scan`) nor the frontend require credentials to start a scan anymore.

### Duplicate app bundles in /Applications — "ROSM.localized" folders

If a Mac has installed ROSM in the past with a `CFBundleIdentifier` different from the current one (a leftover from an older naming scheme — it's now `com.rosm.launcher`), the macOS Installer doesn't overwrite the existing bundle at the same path: it redirects it into a shadow folder `AppName.localized/AppName.app`. Finder hides the `.localized` suffix (just like it does with `.app`), so it shows up as a generic-looking folder with the same name as the app — the visible symptom: duplicate "ROSM" and "ROSM Uninstaller" entries alongside the real apps.

Fix: `build_mac_pkg.sh` also generates a **preinstall** script (in addition to the postinstall) that always removes, before installing, any pre-existing `/Applications/ROSM.app`, `/Applications/ROSM Uninstaller.app` and related `.localized` folders — every installation starts clean, regardless of the previous bundle identifier. `pkgbuild` picks it up automatically because it's in the same `$SCRIPTS_DIR` already passed via `--scripts`.

This never affects user data: these bundles are just launchers (a script + Info.plist + icon), regenerated identically on every install. Real data (`/usr/local/rosm/*.json`, the encryption key, etc.) is never part of the package payload and the postinstall script never touches it.

macOS only: Windows has no equivalent bundle-identity mechanism — `.lnk` shortcuts simply overwrite the same path.

## Index — where to find things in `dashboard.py`

- **Version and changelog**: `APP_VERSION`, `APP_STAGE` (set to `"Beta"` here), `CHANGELOG` — near the start of the file (around lines 60-115).
- **Update mechanism — constants**: `UPDATE_REPO`, `_UPDATE_BRANCHES` (channel→branch mapping, `Beta` with a capital B), `_update_branch()` — right after `APP_VERSION`.
- **Update endpoints**: `/api/check-update` (GET, reads `version.json`), `/api/do-update` (POST, downloads and installs `dashboard.py`), `/settings/update_channel` (POST, only saves the channel preference, doesn't install), `/settings/update_enabled` (POST, enable/disable toggle), `/settings/update_token` (POST, escape hatch to manually set a GitHub token, e.g. to point at your own private fork).
- **Update settings UI**: comment `# Update section (admin only)` — IT/EN labels, status toggle, channel selector, "Check for updates" area with JS (`updCheck`, `updSkip`, `updInstall`, `_buildCL` for rendering the changelog).
- **Network/reachability**: `_get_local_ip()`, `_list_network_interfaces()`, `_get_bind_addresses()`, `_normalize_bind_addresses()` (around lines 130-200), `_tcp_reachable()` (around line 1200, near `fingerprint_host()`). `ALL_SERVERS` — the list of active `ThreadingHTTPServer` instances, created at the bottom of the file when the process starts.
- **i18n**: `_T_EN` (IT→EN dict, around line 200) and `T()` (around line 760) near `LANGUAGE`. For strings inside `MAIN_JS_TEMPLATE` see the `_TJSx`/`{js_i18n}` pattern above, in "Notable design decisions".
