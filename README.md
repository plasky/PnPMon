# LIGO P&P Monitor

A macOS desktop app that watches specific pages on [pnp.ligo.org](https://pnp.ligo.org) and sends you a notification whenever something changes.

<img width="720" alt="LIGO P&P Monitor screenshot" src="https://github.com/user-attachments/assets/placeholder"/>

**Features:**
- Monitor any pnp.ligo.org subpage for changes
- Hourly background checks (configurable)
- macOS Notification Center alerts when a page changes
- Built-in browser to log in via your institution's LIGO SSO (SAML)
- Search the recent publications listing and add pages to your watchlist in one click
- Gravitational-wave waveform header graphic, because why not

---

## Requirements

- macOS (tested on macOS 14+)
- [Homebrew](https://brew.sh) with Python 3.13 installed:
  ```
  brew install python@3.13
  ```

That's it. Everything else is installed automatically.

---

## Setup

**1. Clone the repository**

```bash
git clone https://github.com/plasky/PnPMon.git
cd PnPMon
```

**2. Run the setup script** (one time only — installs Python packages and downloads Chromium)

```bash
./setup.sh
```

This takes a couple of minutes on first run while it downloads the Chromium browser used for SAML login.

---

## Running

```bash
python PnPMonitor.py
```

The app opens a window and also appears as an icon in the macOS menu bar. Closing the window hides it to the menu bar — the app keeps running in the background. Right-click the menu bar icon to access **Check Now** or **Quit**.

> **Note:** No need to activate a virtual environment manually. `PnPMonitor.py` handles that automatically.

---

## First-time use

### 1. Log in to LIGO SSO

Click **Login** in the toolbar. A Chromium browser window will open and navigate to `pnp.ligo.org`. Log in with your usual institutional credentials (the same ones you use for other LIGO services). Once you're logged in, the browser window closes automatically and your session is saved securely in the macOS Keychain.

You'll need to repeat this every few weeks when the session expires.

### 2. Add pages to monitor

Click **+ Add Page**, paste in a `pnp.ligo.org` URL, and give it a short label. The app will check it on the next hourly cycle, or immediately if you click **Check Now**.

Alternatively, click **🔍 Search Publications** to browse the 20 most recent publications and add any of them to your watchlist with a single click.

### 3. Receive notifications

When a monitored page changes, a macOS notification appears with the page name and a brief summary of what changed (e.g. "+1 new item"). Click the notification to be taken to the page.

On first notification, macOS will ask whether to allow notifications from the app — click **Allow**.

---

## Settings

Click **⚙ Settings** to change:

| Setting | Default | Description |
|---------|---------|-------------|
| Check interval | 60 minutes | How often pages are fetched |
| Notifications | On | Whether to show macOS alerts on change |

---

## Project layout

```
PnPMon/
├── PnPMonitor.py          # Entry point — run this
├── requirements.txt       # Python dependencies
├── setup.sh               # One-time setup script
└── pnpmonitor/
    ├── app.py             # App lifecycle and system tray
    ├── core/
    │   ├── storage.py     # SQLite database (~/.pnpmonitor/state.db)
    │   ├── auth.py        # Session cookie management (macOS Keychain)
    │   ├── monitor.py     # Page fetching and change detection
    │   ├── fetcher.py     # Publications listing fetcher
    │   ├── notifier.py    # macOS Notification Center integration
    │   └── scheduler.py   # Background hourly scheduler
    └── gui/
        ├── main_window.py     # Main dashboard
        ├── search_dialog.py   # Recent publications search
        ├── auth_dialog.py     # SSO login dialog
        ├── settings_dialog.py # Settings panel
        └── waveform_widget.py # GW chirp waveform graphic
```

---

## How change detection works

Each time a page is checked, the app:
1. Fetches the page HTML using your saved LIGO session
2. Strips dynamic content that changes on every load (JavaScript, CSRF tokens, hidden form fields)
3. Computes a SHA-256 hash of the stable text content
4. Compares it to the stored hash from the previous check

If the hash differs, a notification is sent with a summary of what changed (e.g. how many table rows or list items were added or removed).

Session cookies are stored in the macOS Keychain under the service name `PnPMonitor` and are never written to disk in plaintext.

---

## Troubleshooting

**"Session expired" in the log**
Click **Login** to re-authenticate. This happens every few weeks as LIGO's SSO session tokens expire.

**"No publications found" in the search dialog**
The publications page structure may have changed. Open an issue with the URL you see after clicking Login and navigating to the publications section.

**The app doesn't appear in the menu bar**
macOS sometimes delays tray icon registration. Try quitting and re-running.

**Notifications don't appear**
Go to System Settings → Notifications → scroll to find PnPMonitor → ensure notifications are allowed.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| [PyQt6](https://pypi.org/project/PyQt6/) | GUI framework |
| [Playwright](https://playwright.dev/python/) | SAML login via Chromium |
| [requests](https://docs.python-requests.org/) | Page fetching |
| [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) | HTML parsing |
| [keyring](https://pypi.org/project/keyring/) | macOS Keychain storage |
| [APScheduler](https://apscheduler.readthedocs.io/) | Background scheduling |
| [matplotlib](https://matplotlib.org/) + [NumPy](https://numpy.org/) | Waveform graphics |
