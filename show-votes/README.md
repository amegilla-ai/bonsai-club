# show-votes

Live show-selection voting for a bonsai club show. Built for picking which trees
go in a club exhibition, but works for any "vote on a set of photo entries" task.

Submissions come from a Discord thread (exported to `channel.json` + photos).
A small web app shows every tree and lets callers vote Definitely / Maybe / No,
with live totals. The host marks trees Include / Exclude, filters, and exports.

## Quick start

```bash
cd show-votes
cp .env.example .env          # set BONSAI_PASSCODE and BONSAI_HOST_KEY
pip install pillow reportlab  # only needed for the PDF export
python3 vote_app.py
```

- Guest view: http://localhost:8070/  (enter the passcode)
- Host view:  http://localhost:8070/?host=YOUR_HOST_KEY

With no `channel.json` present, it runs on the bundled `sample/` data.

Full operating notes: [HOW-TO-RUN-VOTING.md](HOW-TO-RUN-VOTING.md).

## Features
- Definitely / Maybe / No voting; tap your choice again to remove it
- Live totals for everyone; score = Definitely x2 + Maybe
- Per-tree comment threads (edit/delete your own; host any)
- Host-only Include / Exclude (visible to all), filter Included / Not / Undecided
- Owner dropdown filter (e.g. enforce a max-per-member rule)
- Sort by rating; per-owner included summary with over-threshold flag
- CSV export (per-voter breakdown) and selected-trees PDF with photos
- Passcode gate, host key, rate limiting; designed to run sandboxed

## How it's built
- Single file `vote_app.py`, Python standard library only (Pillow + reportlab
  optional, just for the PDF). No web framework.
- SQLite (`votes.db`) for votes, decisions, comments.
- Secrets via `.env` / environment - never hardcoded.

## Files
| File | What |
|------|------|
| `vote_app.py` | The app |
| `.env.example` | Copy to `.env`, set passcode + host key |
| `sample/` | Tiny sample channel + images so it runs without real data |
| `channel.json`, `channel.json_Files/` | Your real export (gitignored) |
| `votes.db` | SQLite store (gitignored) |

## Sharing publicly
If exposing over the internet (e.g. Tailscale Funnel), keep the passcode gate on,
run the app sandboxed, and turn the public link off when the voting window closes.
