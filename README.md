# LIGO P&P Monitor

A macOS desktop app that watches specific pages on [pnp.ligo.org](https://pnp.ligo.org) and sends a notification whenever something changes.

**Features:**
- Monitor any pnp.ligo.org subpage for changes
- Hourly background checks (configurable — changes take effect immediately)
- macOS Notification Center alerts when a page changes
- Menu bar icon shows a red badge with the count of unread changes
- Log in via your institution's LIGO SSO (SAML) using your existing Chrome browser
- Search the recent publications listing and add pages to your watchlist in one click
- Mark changed pages as read directly from the table
- Gravitational-wave waveform header graphic

---

## Requirements

- macOS 14 or later
- [Homebrew](https://brew.sh) with Python 3.13:
  ```
  brew install python@3.13
  ```
- Google Chrome (recommended for SSO login — see [First-time use](#first-time-use))

That's it. Everything else is installed automatically by the setup script.

---

## Setup

**1. Clone the repository**

```bash
git clone https://github.com/plasky/PnPMon.git
cd PnPMon
```

**2. Run the setup script** (one time only)

```bash
./setup.sh
```

This installs all Python packages and downloads a fallback Chromium browser. Takes a couple of minutes on first run.

---

## Running

```bash
python PnPMonitor.py
```

The app opens a window and adds an icon to the macOS menu bar. Closing the window hides it to the tray — the app keeps running in the background and checking for changes hourly. Right-click the menu bar icon for **Check Now** or **Quit**.

> No need to activate a virtual environment manually — `PnPMonitor.py` handles that automatically.

---

## First-time use

### 1. Log in to LIGO SSO

Click **Login** in the toolbar. Your Chrome browser will open and navigate to `pnp.ligo.org`. Log in with your usual institutional credentials. Once you're logged in, Chrome closes automatically and your session is saved securely in the macOS Keychain.

> **No Chrome?** The app falls back to a standalone Chromium window. Safari cannot be used because Apple does not allow automated cookie extraction from it.

You will need to log in again every few weeks when the LIGO SSO session expires.

### 2. Add pages to monitor

Click **+ Add Page**, paste a `pnp.ligo.org` URL, and give it a short label. The app checks it on the next hourly cycle, or immediately if you click **Check Now**.

Alternatively, click **🔍 Search Publications** to browse the 20 most recent publications and add any of them to your watchlist with one click. Click **Get More** to load the next batch.

### 3. Receive notifications

When a monitored page changes, a macOS notification appears with the page name and a brief summary (e.g. "+1 new item"). The menu bar icon also shows a red badge with the total number of unread changes.

On first notification, macOS will ask whether to allow notifications — click **Allow**.

### 4. Mark changes as read

When a page shows **CHANGED** in the table, a green **✓ Mark as Read** button appears in that row. Clicking it reverts the status to **OK** and clears the badge count.

---

## Settings

Click **⚙ Settings** to change:

| Setting | Default | Description |
|---------|---------|-------------|
| Check interval | 60 minutes | How often pages are fetched (applied immediately) |
| Notifications | On | Whether to show macOS alerts on change |

---

## Project layout

```
PnPMon/
├── PnPMonitor.py          # Entry point — run this
├── requirements.txt       # Python dependencies
├── setup.sh               # One-time setup script
└── pnpmonitor/
    ├── app.py             # App lifecycle, system tray, badge
    ├── core/
    │   ├── storage.py     # SQLite database (~/.pnpmonitor/state.db)
    │   ├── auth.py        # Session cookie management (macOS Keychain)
    │   ├── monitor.py     # Page fetching and change detection
    │   ├── fetcher.py     # Publications listing fetcher
    │   ├── notifier.py    # macOS Notification Center integration
    │   └── scheduler.py   # Background scheduler
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
1. Fetches the page HTML using your saved LIGO session cookies
2. Strips dynamic content (JavaScript, CSRF tokens, hidden form fields) that changes on every load
3. Computes a SHA-256 hash of the stable text content
4. Compares it to the stored hash from the previous check

If the hash differs, a notification is sent with a human-readable summary (e.g. how many table rows or list items were added or removed).

Session cookies are stored in the macOS Keychain under the service name `PnPMonitor` and are never written to disk in plaintext.

---

## Troubleshooting

**"Session expired" in the log**
Click **Login** to re-authenticate. This happens every few weeks as LIGO SSO tokens expire.

**"No publications found" in the search dialog**
The publications page structure may have changed. Open an issue and include the URL you land on after logging in.

**The app doesn't appear in the menu bar**
macOS sometimes delays tray icon registration. Quit and re-run.

**Notifications don't appear**
Go to System Settings → Notifications, find PnPMonitor, and ensure alerts are enabled.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| [PyQt6](https://pypi.org/project/PyQt6/) | GUI framework and system tray |
| [Playwright](https://playwright.dev/python/) | SAML login browser automation |
| [requests](https://docs.python-requests.org/) | Page fetching |
| [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) | HTML parsing |
| [keyring](https://pypi.org/project/keyring/) | macOS Keychain storage |
| [APScheduler](https://apscheduler.readthedocs.io/) | Background scheduling |
| [matplotlib](https://matplotlib.org/) + [NumPy](https://numpy.org/) | Waveform graphics |
