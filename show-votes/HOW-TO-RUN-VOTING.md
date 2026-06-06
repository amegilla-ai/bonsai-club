# Show voting - how to run it

A web page showing all submitted trees (photo + owner + size). Guests vote
**Definitely / Maybe / No**; totals update live for everyone. The host also
marks each tree **Include / Exclude**, sorts, filters, comments, and exports.

Works on phones - layout reflows to one column, buttons are big.

## Secrets - set them in `.env`

Secrets are NOT in the code. Copy `.env.example` to `.env` and set your own:

```bash
cd show-votes
cp .env.example .env
# edit .env:
#   BONSAI_PASSCODE=<shared passcode friends type once>
#   BONSAI_HOST_KEY=<long random string only you know>
```

`.env` is gitignored. The passcode gets everyone past the entry gate; the host
key (added as `?host=...`) unlocks Include/Exclude, host comment edits, and exports.

---

## 1. Run it

No dependencies beyond Python 3 and Pillow (for the PDF export):

```bash
cd show-votes
pip install pillow reportlab   # only needed for the Selected-trees PDF
python3 vote_app.py
```

- Guest view: http://localhost:8070/  (enter your passcode)
- Host view:  http://localhost:8070/?host=YOUR_HOST_KEY

If `channel.json` is absent it falls back to `sample/` so it runs out of the box.

### Optional: run as a background service (Linux/systemd)
Create `~/.config/systemd/user/show-votes.service` pointing `ExecStart` at
`vote_app.py`, then `systemctl --user enable --now show-votes`. Lets it survive
logout and auto-restart. See the sandboxing directives in the repo's example unit.

---

## 2. Make it public (optional, Tailscale Funnel)

If you use Tailscale, expose it over HTTPS without your friends needing Tailscale:

```bash
tailscale funnel --bg --https=8443 localhost:8070
```

Share your tailnet's funnel URL (`https://<your-machine>.ts.net:8443/`) plus the
passcode (sent separately). Turn it off when done:

```bash
tailscale funnel --https=8443 off
```

Closing the funnel only removes public access - the app keeps running locally and
the votes are untouched. **Reopen any time** with the same `funnel --bg` command;
the same URL and all data come back.

### Auto-close after a set time (optional)
A systemd timer can close the funnel for you so you don't forget. One-shot example
(`~/.config/systemd/user/funnel-off.{service,timer}`):

```ini
# funnel-off.service
[Service]
Type=oneshot
ExecStart=/usr/bin/tailscale funnel --https=8443 off
```
```ini
# funnel-off.timer
[Timer]
OnCalendar=2026-06-13 09:00:00
Persistent=true
[Install]
WantedBy=timers.target
```
```bash
systemctl --user daemon-reload
systemctl --user enable --now funnel-off.timer   # arm it
systemctl --user list-timers funnel-off.timer    # check when it fires
systemctl --user disable --now funnel-off.timer  # cancel it
```
`Persistent=true` runs the close on next boot if the machine was off at the set
time. It fires once - reopening the funnel later stays open until you close it again.

---

## During the call
- Everyone types their **name** once at the top.
- Tap **Definitely / Maybe / No**. Tapping your current choice again **removes** your vote. No double-counting.
- **Sort: by rating** orders trees by score (Definitely = 2 pts, Maybe = 1).
- **Owner** dropdown filters to one member's trees - handy for a max-per-person rule.
- Each tree has a **comment thread** - add, and edit/delete your own (host can edit/delete any).
- **Status badge** (Included / Not selected) shows to everyone; only the host can set it.
- Host filters: **Included / Not included / Undecided**. Tapping Include/Exclude again clears it.
- **Per-owner summary** at the bottom counts included trees and flags anyone over a threshold.

## Exports (host only, buttons at the bottom)
- **Export results CSV** - owner, tree, score, D/M/N counts, decision, and a column per voter. Opens in Excel/LibreOffice. Direct: `/export.csv?host=YOUR_HOST_KEY`
- **Selected trees PDF** - included trees grouped by owner, with photos, downscaled to attach easily. Direct: `/selected.pdf?host=YOUR_HOST_KEY`
- Live text summary: `/results`

## Reset for a fresh call
Wipes votes, decisions, and comments (keeps trees and photos):

```bash
cd show-votes
python3 -c "import sqlite3;c=sqlite3.connect('votes.db');[c.execute(f'DELETE FROM {t}') for t in ('votes','decisions','comments')];c.commit();c.close();print('reset')"
```

## Security notes
- **Passcode gate**: the URL alone is useless without the passcode.
- **Host actions enforced server-side**: a guest cannot include/exclude or export even if they guess the URLs - the server checks the host key (403 otherwise).
- **Rate limiting + request-size caps** in the app blunt floods.
- If exposing publicly, run sandboxed (systemd hardening directives) and turn the funnel off when the window closes.

## Data
- Votes/decisions/comments saved in `votes.db` (gitignored) - survive restarts.
- Entries load from `channel.json` (export from your Discord thread). The bundled `sample/` lets the app run without real data.

## Re-exporting from Discord
The Discord token is not stored on disk. Pass it as an env var for that one command,
and supply your own channel id:

```bash
export DISCORD_TOKEN='your-token-here'
docker run --rm -v "$PWD":/out tyrrrz/discordchatexporter:stable export \
  -t "$DISCORD_TOKEN" -c YOUR_CHANNEL_ID -f Json --media --reuse-media -o /out/channel.json
unset DISCORD_TOKEN
```

The vote app itself does NOT need the token - it only reads `channel.json`.
