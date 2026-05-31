# 🤖 QRZenBot

A Telegram bot that **scans** QR codes from photos and **generates** QR codes for URLs, text, WiFi, contacts, and payments — with inline menus, history, and usage analytics.

## ✨ Features
- 📷 **Scan** — send any photo, get the decoded contents
- ⚡ **Generate** — URL · Text · WiFi · Contact (vCard) · Payment (UPI/PayPal/BTC/ETH)
- 🎨 **Custom** color-styled QR codes
- 📚 **History** & 📊 **Analytics** — stored per user in SQLite

## 🚀 Run locally
1. Get a token from [@BotFather](https://t.me/BotFather) → `/newbot`.
2. Install the zbar system lib (needed by `pyzbar`):
   - macOS: `brew install zbar`
   - Debian/Ubuntu: `sudo apt-get install libzbar0`
   - Windows: ships inside the pyzbar wheel — no extra step
3. Install + run:
   ```bash
   pip install -r requirements.txt
   export BOT_TOKEN=<your token>
   python bot.py
   ```
Open Telegram, find your bot, send `/start`. 🎉

## ☁️ Deploy (Railway / Render)
1. Push this repo to GitHub.
2. New project from the repo → add env var `BOT_TOKEN`.
3. The **Dockerfile** auto-installs `libzbar0` and runs `python bot.py`.

Docker anywhere:
```bash
docker build -t qrzenbot .
docker run -e BOT_TOKEN=<your token> qrzenbot
```

## 🔧 Commands
| Command | Action |
|---|---|
| `/start` | Main menu |
| `/help` | Feature list |
| `/cancel` | Abort a generate flow |
| _(send a photo)_ | Scan a QR code |

## License
MIT
