[English](README.md) | [Italiano](README_IT.md)

# ROSM — Router OS Manager

![License](https://img.shields.io/github/license/CiprianiJacopo/ROS-Manager)
![Release](https://img.shields.io/github/v/release/CiprianiJacopo/ROS-Manager)

A single-file Python server for centrally managing fleets of MikroTik routers — without opening Winbox on every single device.

## What it does

- **Dashboard** — see every router's status, model, uptime, and open ports at a glance
- **Network Discovery** — scan a subnet and import routers automatically, with or without SSH credentials
- **Backups** — scheduled, automatic `.rsc` backups for every router
- **Monitoring** — real-time ping, port scanning, and online/offline history
- **RouterOS updates** — check and push RouterOS updates to your routers over SSH
- **Multi-user** — admin/viewer roles, optional 2FA (TOTP)
- **Encrypted storage** — credentials and backups encrypted at rest
- **Self-updating** — checks GitHub for new releases and updates itself with one click

## Install

Download the latest installer from [Releases](https://github.com/CiprianiJacopo/ROS-Manager/releases):
- **macOS** — `ROSM-X.Y.Z.pkg`
- **Windows** — `ROSM-X.Y.Z-Setup.exe`

Run it, follow the setup wizard, and ROSM opens in your browser at `http://localhost:8080`.

## Channels

This repository has two branches:
- `main` — **stable**, what this README describes.
- `Beta` — testing channel, ahead of stable, may contain bugs. See its own README on that branch.

You can switch channel from ROSM's Settings page at any time.

## Documentation

For architecture, code layout, and the reasoning behind non-obvious design decisions, see [CODE_OVERVIEW_EN.md](CODE_OVERVIEW_EN.md) (or [CODE_OVERVIEW_IT.md](CODE_OVERVIEW_IT.md) in Italian).

## License

GPLv3 — see [LICENSE](LICENSE).

## Support

If ROSM is useful to you, you can [buy the author a beer on Ko-fi](https://ko-fi.com/rosm).

Questions or feedback: Rosman.mail@icloud.com
