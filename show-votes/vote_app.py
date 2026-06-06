#!/usr/bin/env python3
"""Live show-selection voting for the Twickenham bonsai club.

Parses the DiscordChatExporter channel.json in this folder, shows every
submitted tree (photo + owner + description). Two roles:

  Guests  - vote Definitely / Maybe / No. Live totals visible to all.
  Host    - open with ?host=KEY to also mark each tree In / Out for the
            show, sort by rating, and filter In / Out / undecided.

No dependencies - uses Python's built-in http.server. Run:
    python3 vote_app.py
Share the plain Tailscale Funnel URL with guests; keep the ?host=KEY URL
for yourself. The host key is printed on startup.
"""
import csv
import io
import json
import re
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

import os

HERE = Path(__file__).resolve().parent


def load_env():
    """Load KEY=VALUE lines from a local .env (gitignored). No dependency."""
    f = HERE / ".env"
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()

# Use the real club export if present, else the bundled sample (fresh clones).
if (HERE / "channel.json").exists():
    CHANNEL = HERE / "channel.json"
    MEDIA = HERE / "channel.json_Files"
else:
    CHANNEL = HERE / "sample" / "channel.json"
    MEDIA = HERE / "sample" / "channel.json_Files"
DB = HERE / "votes.db"
PORT = int(os.environ.get("BONSAI_PORT", "8070"))
# Secrets come from .env / environment so they never live in the public repo.
# Set BONSAI_HOST_KEY and BONSAI_PASSCODE (see README / .env.example).
HOST_KEY = os.environ.get("BONSAI_HOST_KEY", "changeme-host")
PASSCODE = os.environ.get("BONSAI_PASSCODE", "changeme-pass")
COOKIE = "bcpass"

IMG_RE = re.compile(r"\.(jpg|jpeg|png|webp|gif)$", re.I)
_lock = threading.Lock()

MAX_BODY = 64 * 1024  # reject POST bodies bigger than 64 KB
RATE_MAX = 200        # max requests per IP per window (one page load = ~30 image GETs)
RATE_WINDOW = 10      # seconds
_hits = {}            # ip -> [timestamps]
_rate_lock = threading.Lock()


def rate_ok(ip, now):
    with _rate_lock:
        q = [t for t in _hits.get(ip, []) if now - t < RATE_WINDOW]
        if len(q) >= RATE_MAX:
            _hits[ip] = q
            return False
        q.append(now)
        _hits[ip] = q
        return True


def db():
    con = sqlite3.connect(DB)
    con.execute(
        "CREATE TABLE IF NOT EXISTS votes("
        " voter TEXT, entry_id TEXT, choice TEXT,"
        " PRIMARY KEY(voter,entry_id))"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS decisions("
        " entry_id TEXT PRIMARY KEY, decision TEXT)"
    )
    con.execute(
        "CREATE TABLE IF NOT EXISTS comments("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " entry_id TEXT, author TEXT, body TEXT, ts INTEGER)"
    )
    con.commit()
    return con


def load_entries():
    data = json.loads(CHANNEL.read_text())
    out = []
    for m in data["messages"]:
        atts = list(m.get("attachments") or [])
        fwd = m.get("forwardedMessage") or {}
        atts += list(fwd.get("attachments") or [])
        photos = [
            Path(a["url"]).name
            for a in atts
            if IMG_RE.search(a.get("fileName", "") or a.get("url", ""))
        ]
        if not photos:
            continue
        a = m.get("author", {})
        out.append(
            {
                "id": m["id"],
                "owner": a.get("nickname") or a.get("name") or "Unknown",
                "text": (m.get("content") or fwd.get("content") or "").strip(),
                "photos": photos,
            }
        )
    return out


ENTRIES = load_entries()


def tallies():
    con = db()
    rows = con.execute(
        "SELECT entry_id,choice,COUNT(*) FROM votes GROUP BY entry_id,choice"
    ).fetchall()
    decs = dict(con.execute("SELECT entry_id,decision FROM decisions").fetchall())
    crows = con.execute(
        "SELECT id,entry_id,author,body,ts FROM comments ORDER BY ts ASC,id ASC"
    ).fetchall()
    con.close()
    t = {}
    for eid, choice, n in rows:
        t.setdefault(eid, {"Definitely": 0, "Maybe": 0, "No": 0})[choice] = n
    comments = {}
    for cid, eid, author, body, ts in crows:
        comments.setdefault(eid, []).append(
            {"id": cid, "author": author, "body": body, "ts": ts}
        )
    return {"tallies": t, "decisions": decs, "comments": comments}


PAGE = r"""<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Shohin/Mame Show - Voting</title>
<style>
 body{font-family:system-ui,Arial,sans-serif;margin:0;background:#f4f4f2;color:#222}
 header{background:#2c5f2d;color:#fff;padding:12px 16px;position:sticky;top:0;z-index:9}
 header h1{margin:0;font-size:17px}
 .bar{padding:8px 16px;background:#fff;border-bottom:1px solid #ddd;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
 .bar input{font-size:16px;padding:7px;width:min(240px,55vw)}
 .bar button{padding:7px 11px;font-size:14px;border:1px solid #bbb;border-radius:6px;background:#fafafa;cursor:pointer}
 .bar button.on{background:#2c5f2d;color:#fff;border-color:#2c5f2d}
 .ownerrow select{font-size:16px;padding:6px}
 @media(max-width:600px){.ownerrow{flex-basis:100%}.ownerrow select{width:100%}}
 .comments{border-top:1px solid #eee;padding:8px 10px;margin-top:auto}
 .cmt{font-size:13px;padding:3px 0;border-bottom:1px solid #f3f3f3;word-break:break-word}
 .cmtauthor{font-weight:600;color:#2c5f2d}
 .cmtbtn{font-size:11px;margin-left:6px;padding:2px 6px;border:1px solid #ccc;border-radius:4px;background:#fafafa;cursor:pointer}
 .cmtadd{display:flex;gap:6px;margin-top:6px}
 .cmtinput{flex:1;font-size:14px;padding:6px;border:1px solid #ccc;border-radius:5px}
 #summary{padding:14px 16px;background:#fff;border-top:2px solid #2c5f2d;margin-top:10px}
 #summary h2{font-size:16px;margin:0 0 8px}
 #summary table{border-collapse:collapse;width:min(420px,100%)}
 #summary td{padding:4px 10px;border-bottom:1px solid #eee;font-size:14px}
 #summary td.n{text-align:right;font-weight:600}
 #summary tr.over td{color:#b02a37}
 .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;padding:14px}
 .card{background:#fff;border:1px solid #ddd;border-radius:8px;overflow:hidden;display:flex;flex-direction:column}
 .card.in{border:2px solid #2c5f2d}
 .card.out{opacity:.5}
 .status{text-align:center;font-size:13px;font-weight:600;padding:4px}
 .status.in{color:#2c5f2d}
 .status.out{color:#b02a37}
 .card img{width:100%;height:230px;object-fit:cover;background:#eee;cursor:pointer}
 .meta{padding:8px 10px}
 .owner{font-weight:600}
 .desc{font-size:13px;color:#555;margin-top:2px;height:3.2em;overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;line-height:1.6em;cursor:pointer}
 .desc.full{height:auto;-webkit-line-clamp:unset;overflow:visible}
 .score{font-size:12px;color:#2c5f2d;font-weight:600;margin-top:3px}
 .btns{display:flex;gap:6px;padding:0 10px 8px}
 .btns button{flex:1;padding:9px 4px;font-size:14px;border:1px solid #bbb;border-radius:6px;background:#fafafa;cursor:pointer}
 .btns button.sel[data-c=Definitely]{background:#2c5f2d;color:#fff;border-color:#2c5f2d}
 .btns button.sel[data-c=Maybe]{background:#e0a800;color:#fff;border-color:#e0a800}
 .btns button.sel[data-c=No]{background:#b02a37;color:#fff;border-color:#b02a37}
 .tally{display:flex;gap:8px;padding:0 10px 6px;font-size:13px;color:#444}
 .tally span{flex:1;text-align:center}
 .dec{display:flex;gap:6px;padding:0 10px 10px}
 .dec button{flex:1;padding:8px 4px;font-size:13px;border:1px dashed #999;border-radius:6px;background:#fff;cursor:pointer}
 .dec button.in{background:#2c5f2d;color:#fff;border-style:solid}
 .dec button.out{background:#b02a37;color:#fff;border-style:solid}
 #lb{display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:99;align-items:center;justify-content:center}
 #lb img{max-width:95vw;max-height:95vh}
</style></head><body>
<header><h1>Shohin/Mame Club Show - Selection Voting</h1></header>
<div class=bar>
 Name: <input id=voter placeholder="type your name" autocomplete=off>
 <span class=ownerrow>Owner: <select id=ownerSel onchange="setOwner(this.value)"><option value="">All owners</option></select></span>
 <button id=sortBtn onclick="toggleSort()">Sort: by rating</button>
 <span id=hostfilters style="display:none">
  Show:
  <button class=fil data-f=all onclick="setF('all')">All</button>
  <button class=fil data-f=in onclick="setF('in')">Included</button>
  <button class=fil data-f=out onclick="setF('out')">Not included</button>
  <button class=fil data-f=undecided onclick="setF('undecided')">Undecided</button>
 </span>
</div>
<div class=grid id=grid></div>
<div id=summary></div>
<div id=exportrow style="display:none;padding:18px 16px 40px;text-align:center">
 <button onclick="location.href='/export.csv?host=__HOSTKEY__'" style="padding:12px 22px;font-size:16px;border:1px solid #2c5f2d;border-radius:6px;background:#2c5f2d;color:#fff;cursor:pointer">Export results CSV</button>
 <button onclick="location.href='/selected.pdf?host=__HOSTKEY__'" style="padding:12px 22px;font-size:16px;border:1px solid #2c5f2d;border-radius:6px;background:#fff;color:#2c5f2d;cursor:pointer;margin-left:10px">Selected trees PDF</button>
</div>
<div id=lb onclick="this.style.display='none'"><img id=lbimg></div>
<script>
const entries = __ENTRIES__;
const HOST = new URLSearchParams(location.search).get('host') === '__HOSTKEY__';
let voter = localStorage.getItem('voter')||'';
let sortByRating = true, filter='all', owner='', state={tallies:{},decisions:{}};
const vin=document.getElementById('voter'); vin.value=voter;
vin.oninput=e=>{voter=e.target.value.trim();localStorage.setItem('voter',voter);};
if(HOST){document.getElementById('hostfilters').style.display='';document.getElementById('exportrow').style.display='block';}
const osel=document.getElementById('ownerSel');
[...new Set(entries.map(e=>e.owner))].sort().forEach(o=>{const op=document.createElement('option');op.value=o;op.textContent=o;osel.appendChild(op);});
function setOwner(o){owner=o;render();}
const mine=JSON.parse(localStorage.getItem('myvotes')||'{}');
function img(p){return '/media/'+encodeURIComponent(p);}
function show(p){document.getElementById('lbimg').src=img(p);document.getElementById('lb').style.display='flex';}
function score(t){return (t.Definitely||0)*2+(t.Maybe||0);}
function toggleSort(){sortByRating=!sortByRating;document.getElementById('sortBtn').textContent='Sort: '+(sortByRating?'by rating':'original');render();}
function setF(f){filter=f;document.querySelectorAll('.fil').forEach(b=>b.classList.toggle('on',b.dataset.f===f));render();}
function render(){
 let list=entries.map(e=>({e,t:state.tallies[e.id]||{Definitely:0,Maybe:0,No:0},d:state.decisions[e.id]||''}));
 if(owner) list=list.filter(x=>x.e.owner===owner);
 if(HOST&&filter!=='all') list=list.filter(x=>filter==='undecided'?!x.d:x.d===filter);
 if(sortByRating) list.sort((a,b)=>score(b.t)-score(a.t));
 const g=document.getElementById('grid'); g.innerHTML='';
 list.forEach(({e,t,d})=>{
  const sel=mine[e.id];
  const card=document.createElement('div'); card.className='card'+(d?' '+d:'');
  let h='<img src="'+img(e.photos[0])+'" onclick="show(\''+e.photos[0]+'\')">'+
   '<div class=meta><div class=owner>'+e.owner+'</div><div class=desc onclick="this.classList.toggle(\'full\')" title="tap to expand">'+(e.text||'')+'</div>'+
   '<div class=score>score '+score(t)+'</div></div>'+
   '<div class=btns>'+['Definitely','Maybe','No'].map(c=>
     '<button data-c="'+c+'" class="'+(sel===c?'sel':'')+'" onclick="vote(\''+e.id+'\',\''+c+'\')">'+c+'</button>').join('')+'</div>'+
   '<div class=tally><span>D '+t.Definitely+'</span><span>M '+t.Maybe+'</span><span>N '+t.No+'</span></div>'+
   (d?'<div class="status '+d+'">'+(d==='in'?'✓ Included in show':'Not selected')+'</div>':'');
  if(HOST) h+='<div class=dec>'+
     '<button class="'+(d==='in'?'in':'')+'" onclick="decide(\''+e.id+'\',\'in\',\''+d+'\')">Include</button>'+
     '<button class="'+(d==='out'?'out':'')+'" onclick="decide(\''+e.id+'\',\'out\',\''+d+'\')">Exclude</button></div>';
  card.innerHTML=h;
  card.appendChild(comments(e.id));
  g.appendChild(card);
 });
 renderSummary();
}
function renderSummary(){
 const cnt={};
 entries.forEach(e=>{cnt[e.owner]=cnt[e.owner]||{in:0,total:0};cnt[e.owner].total++;if((state.decisions[e.id]||'')==='in')cnt[e.owner].in++;});
 const owners=Object.keys(cnt).sort((a,b)=>cnt[b].in-cnt[a].in||a.localeCompare(b));
 const totalIn=owners.reduce((s,o)=>s+cnt[o].in,0);
 let rows=owners.map(o=>{
  const over=cnt[o].in>3?' class=over':'';
  return '<tr'+over+'><td>'+o+'</td><td class=n>'+cnt[o].in+'</td><td>of '+cnt[o].total+' submitted'+(cnt[o].in>3?' (over 3)':'')+'</td></tr>';
 }).join('');
 document.getElementById('summary').innerHTML=
  '<h2>Included per owner - '+totalIn+' tree'+(totalIn===1?'':'s')+' selected</h2>'+
  '<table>'+rows+'</table>';
}
function el(tag,props,kids){const n=document.createElement(tag);Object.assign(n,props||{});(kids||[]).forEach(k=>n.appendChild(typeof k==='string'?document.createTextNode(k):k));return n;}
function comments(eid){
 const wrap=el('div',{className:'comments'});
 (state.comments&&state.comments[eid]||[]).forEach(c=>{
  const canEdit = HOST || (voter && c.author===voter);
  const line=el('div',{className:'cmt'});
  line.appendChild(el('span',{className:'cmtauthor'},[c.author+': ']));
  line.appendChild(el('span',{},[c.body]));
  if(canEdit){
   line.appendChild(el('button',{className:'cmtbtn',onclick:()=>editComment(c)},['edit']));
   line.appendChild(el('button',{className:'cmtbtn',onclick:()=>delComment(c.id)},['x']));
  }
  wrap.appendChild(line);
 });
 const inp=el('input',{className:'cmtinput',placeholder:'add a comment...'});
 inp.addEventListener('keydown',ev=>{if(ev.key==='Enter')addComment(eid,inp);});
 const row=el('div',{className:'cmtadd'},[inp,el('button',{className:'cmtbtn',onclick:()=>addComment(eid,inp)},['post'])]);
 wrap.appendChild(row);
 return wrap;
}
async function addComment(eid,inp){
 if(!voter){alert('Enter your name first');vin.focus();return;}
 const text=inp.value.trim(); if(!text)return;
 inp.value='';
 await fetch('/comment',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({author:voter,entry_id:eid,body:text})});
 refresh(true);
}
const HQ = HOST ? '?host='+encodeURIComponent(new URLSearchParams(location.search).get('host')) : '';
async function editComment(c){
 const t=prompt('Edit comment:',c.body); if(t===null)return;
 const text=t.trim(); if(!text)return;
 await fetch('/comment/edit'+HQ,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:c.id,author:voter,body:text})});
 refresh(true);
}
async function delComment(id){
 if(!confirm('Delete this comment?'))return;
 await fetch('/comment/delete'+HQ,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,author:voter})});
 refresh(true);
}
async function vote(id,choice){
 if(!voter){alert('Enter your name first');vin.focus();return;}
 const toggle = mine[id]===choice;
 if(toggle) delete mine[id]; else mine[id]=choice;
 localStorage.setItem('myvotes',JSON.stringify(mine));
 await fetch('/vote',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({voter,entry_id:id,choice:toggle?'none':choice})});
 refresh(true);
}
async function decide(id,decision,current){
 const send = (current===decision) ? 'none' : decision;
 await fetch('/decide?host='+encodeURIComponent('__HOSTKEY__'),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({entry_id:id,decision:send})});
 refresh(true);
}
function typing(){const a=document.activeElement;return a&&(a.tagName==='INPUT'||a.tagName==='TEXTAREA')&&a.id!=='voter';}
async function refresh(force){
 state=await (await fetch('/state')).json();
 if(force||!typing()) render();
}
refresh(true); setInterval(refresh,3000);
</script></body></html>"""


GATE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Bonsai Show - Enter Passcode</title>
<style>
 body{font-family:system-ui,Arial,sans-serif;background:#2c5f2d;color:#fff;display:flex;
  min-height:100vh;margin:0;align-items:center;justify-content:center}
 .box{background:#fff;color:#222;padding:28px;border-radius:10px;width:min(340px,86vw);text-align:center}
 h1{font-size:18px;margin:0 0 14px}
 input{font-size:18px;padding:10px;width:100%;box-sizing:border-box;border:1px solid #bbb;border-radius:6px}
 button{margin-top:12px;font-size:16px;padding:10px 18px;border:0;border-radius:6px;background:#2c5f2d;color:#fff;cursor:pointer;width:100%}
 .err{color:#b02a37;font-size:14px;margin-top:8px;min-height:18px}
</style></head><body>
<div class=box>
 <h1>Twickenham Bonsai Club<br>Show Voting</h1>
 <input id=pc type=password placeholder="passcode" autofocus>
 <button onclick="go()">Enter</button>
 <div class=err id=err></div>
</div>
<script>
const hq=location.search;
async function go(){
 const r=await fetch('/unlock'+hq,{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({passcode:document.getElementById('pc').value})});
 if(r.ok) location.href='/'+hq; else document.getElementById('err').textContent='Wrong passcode';
}
document.getElementById('pc').addEventListener('keydown',e=>{if(e.key==='Enter')go();});
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json", cookie=None):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def unlocked(self):
        raw = self.headers.get("Cookie", "")
        for part in raw.split(";"):
            if part.strip() == f"{COOKIE}={PASSCODE}":
                return True
        return False

    def log_message(self, *a):
        pass

    def do_GET(self):
        u = urlparse(self.path)
        if not rate_ok(self.client_address[0], time.time()):
            return self._send(429, "rate limited", "text/plain")
        if not self.unlocked():
            return self._send(200, GATE, "text/html; charset=utf-8")
        if u.path == "/":
            page = (
                PAGE.replace("__ENTRIES__", json.dumps(ENTRIES))
                .replace("__HOSTKEY__", HOST_KEY)
            )
            return self._send(200, page, "text/html; charset=utf-8")
        if u.path == "/state":
            return self._send(200, json.dumps(tallies()))
        if u.path == "/results":
            return self._send(200, results_text(), "text/plain; charset=utf-8")
        if u.path == "/export.csv":
            if parse_qs(u.query).get("host", [""])[0] != HOST_KEY:
                return self._send(403, "forbidden", "text/plain")
            body = export_csv().encode("utf-8-sig")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header(
                "Content-Disposition",
                'attachment; filename="bonsai-show-votes.csv"',
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if u.path == "/selected.pdf":
            if parse_qs(u.query).get("host", [""])[0] != HOST_KEY:
                return self._send(403, "forbidden", "text/plain")
            body = selected_pdf()
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header(
                "Content-Disposition",
                'attachment; filename="bonsai-show-selected.pdf"',
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if u.path.startswith("/media/"):
            fn = unquote(u.path[len("/media/"):])
            f = (MEDIA / fn).resolve()
            if MEDIA.resolve() in f.parents and f.is_file():
                data = f.read_bytes()
                ct = "image/jpeg" if f.suffix.lower() in (".jpg", ".jpeg") else "image/png"
                return self._send(200, data, ct)
            return self._send(404, "not found", "text/plain")
        self._send(404, "{}")

    def do_POST(self):
        u = urlparse(self.path)
        now = time.time()
        ip = self.client_address[0]
        if not rate_ok(ip, now):
            return self._send(429, '{"error":"rate limited"}')
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return self._send(400, '{"ok":false}')
        if n > MAX_BODY:
            return self._send(413, '{"error":"too large"}')
        try:
            body = json.loads(self.rfile.read(n) or "{}")
            if not isinstance(body, dict):
                raise ValueError
        except (ValueError, json.JSONDecodeError):
            return self._send(400, '{"ok":false}')
        if u.path == "/unlock":
            if (body.get("passcode") or "") == PASSCODE:
                ck = f"{COOKIE}={PASSCODE}; Path=/; Max-Age=604800; SameSite=Lax"
                return self._send(200, '{"ok":true}', cookie=ck)
            return self._send(403, '{"ok":false}')
        if not self.unlocked():
            return self._send(403, '{"ok":false}')
        if u.path == "/vote":
            voter = (body.get("voter") or "").strip()[:40]
            eid = str(body.get("entry_id"))
            choice = body.get("choice")
            if not voter or choice not in ("Definitely", "Maybe", "No", "none"):
                return self._send(400, '{"ok":false}')
            with _lock:
                con = db()
                if choice == "none":
                    con.execute(
                        "DELETE FROM votes WHERE voter=? AND entry_id=?",
                        (voter, eid),
                    )
                else:
                    con.execute(
                        "INSERT INTO votes(voter,entry_id,choice) VALUES(?,?,?) "
                        "ON CONFLICT(voter,entry_id) DO UPDATE SET choice=excluded.choice",
                        (voter, eid, choice),
                    )
                con.commit()
                con.close()
            return self._send(200, '{"ok":true}')
        if u.path == "/decide":
            if parse_qs(u.query).get("host", [""])[0] != HOST_KEY:
                return self._send(403, '{"ok":false}')
            eid = str(body.get("entry_id"))
            dec = body.get("decision")
            if dec not in ("in", "out", "none"):
                return self._send(400, '{"ok":false}')
            with _lock:
                con = db()
                if dec == "none":
                    con.execute("DELETE FROM decisions WHERE entry_id=?", (eid,))
                else:
                    con.execute(
                        "INSERT INTO decisions(entry_id,decision) VALUES(?,?) "
                        "ON CONFLICT(entry_id) DO UPDATE SET decision=excluded.decision",
                        (eid, dec),
                    )
                con.commit()
                con.close()
            return self._send(200, '{"ok":true}')
        if u.path == "/comment":
            author = (body.get("author") or "").strip()[:40]
            eid = str(body.get("entry_id"))
            text = (body.get("body") or "").strip()[:1000]
            if not author or not text:
                return self._send(400, '{"ok":false}')
            with _lock:
                con = db()
                con.execute(
                    "INSERT INTO comments(entry_id,author,body,ts) VALUES(?,?,?,?)",
                    (eid, author, text, int(time.time())),
                )
                con.commit()
                con.close()
            return self._send(200, '{"ok":true}')
        if u.path == "/comment/edit":
            host = parse_qs(u.query).get("host", [""])[0] == HOST_KEY
            cid = body.get("id")
            who = (body.get("author") or "").strip()[:40]
            text = (body.get("body") or "").strip()[:1000]
            if not isinstance(cid, int) or not text:
                return self._send(400, '{"ok":false}')
            with _lock:
                con = db()
                row = con.execute(
                    "SELECT author FROM comments WHERE id=?", (cid,)
                ).fetchone()
                if not row:
                    con.close()
                    return self._send(404, '{"ok":false}')
                if not host and row[0] != who:
                    con.close()
                    return self._send(403, '{"ok":false}')
                con.execute("UPDATE comments SET body=? WHERE id=?", (text, cid))
                con.commit()
                con.close()
            return self._send(200, '{"ok":true}')
        if u.path == "/comment/delete":
            host = parse_qs(u.query).get("host", [""])[0] == HOST_KEY
            cid = body.get("id")
            who = (body.get("author") or "").strip()[:40]
            if not isinstance(cid, int):
                return self._send(400, '{"ok":false}')
            with _lock:
                con = db()
                row = con.execute(
                    "SELECT author FROM comments WHERE id=?", (cid,)
                ).fetchone()
                if not row:
                    con.close()
                    return self._send(404, '{"ok":false}')
                if not host and row[0] != who:
                    con.close()
                    return self._send(403, '{"ok":false}')
                con.execute("DELETE FROM comments WHERE id=?", (cid,))
                con.commit()
                con.close()
            return self._send(200, '{"ok":true}')
        self._send(404, "{}")


def results_text():
    st = tallies()
    t, d = st["tallies"], st["decisions"]
    rows = []
    for e in ENTRIES:
        tt = t.get(e["id"], {"Definitely": 0, "Maybe": 0, "No": 0})
        sc = tt["Definitely"] * 2 + tt["Maybe"]
        rows.append((sc, d.get(e["id"], ""), e["owner"], e["text"][:48], tt))
    rows.sort(key=lambda r: -r[0])
    out = ["score in/out | owner - tree            (D/M/N)"]
    for sc, dec, owner, text, tt in rows:
        out.append(
            f"{sc:<5} {dec or '-':<6} | {owner} - {text}  "
            f"({tt['Definitely']}/{tt['Maybe']}/{tt['No']})"
        )
    return "\n".join(out)


def export_csv():
    st = tallies()
    t, d = st["tallies"], st["decisions"]
    con = db()
    voters = sorted(r[0] for r in con.execute("SELECT DISTINCT voter FROM votes"))
    per = {
        (eid, voter): choice
        for voter, eid, choice in con.execute(
            "SELECT voter,entry_id,choice FROM votes"
        )
    }
    con.close()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(
        ["owner", "tree", "score", "definitely", "maybe", "no", "decision"]
        + voters
    )
    rows = []
    for e in ENTRIES:
        tt = t.get(e["id"], {"Definitely": 0, "Maybe": 0, "No": 0})
        sc = tt["Definitely"] * 2 + tt["Maybe"]
        rows.append((sc, e, tt))
    rows.sort(key=lambda r: -r[0])
    for sc, e, tt in rows:
        w.writerow(
            [
                e["owner"],
                e["text"],
                sc,
                tt["Definitely"],
                tt["Maybe"],
                tt["No"],
                d.get(e["id"], ""),
            ]
            + [per.get((e["id"], v), "") for v in voters]
        )
    return buf.getvalue()


def selected_pdf():
    """PDF of Included trees only, grouped by owner, with description + photo."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    from PIL import Image

    decs = tallies()["decisions"]
    included = [e for e in ENTRIES if decs.get(e["id"]) == "in"]
    by_owner = {}
    for e in included:
        by_owner.setdefault(e["owner"], []).append(e)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    margin = 18 * mm
    y = H - margin

    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y, "Shohin/Mame Show - Selected Trees")
    y -= 8 * mm
    c.setFont("Helvetica", 11)
    c.drawString(margin, y, f"{len(included)} trees selected, {len(by_owner)} members")
    y -= 10 * mm

    def new_page():
        nonlocal y
        c.showPage()
        y = H - margin

    for owner in sorted(by_owner):
        if y < 60 * mm:
            new_page()
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, y, owner)
        y -= 7 * mm
        for e in by_owner[owner]:
            img_h = 55 * mm
            if y - img_h - 12 * mm < margin:
                new_page()
            # photo
            try:
                p = (MEDIA / e["photos"][0]).resolve()
                im = Image.open(p).convert("RGB")
                im.thumbnail((900, 900))
                iw, ih = im.size
                draw_w = 70 * mm
                draw_h = draw_w * ih / iw
                if draw_h > img_h:
                    draw_h = img_h
                    draw_w = draw_h * iw / ih
                ibuf = io.BytesIO()
                im.save(ibuf, format="JPEG", quality=70)
                ibuf.seek(0)
                c.drawImage(
                    ImageReader(ibuf), margin, y - draw_h,
                    width=draw_w, height=draw_h, preserveAspectRatio=True,
                )
                text_x = margin + draw_w + 6 * mm
            except Exception:
                draw_h = 0
                text_x = margin

            # description wrapped beside photo
            c.setFont("Helvetica", 11)
            desc = e["text"] or "(no description)"
            words = desc.split()
            line = ""
            ty = y - 4 * mm
            max_w = W - text_x - margin
            for w in words:
                test = (line + " " + w).strip()
                if c.stringWidth(test, "Helvetica", 11) > max_w:
                    c.drawString(text_x, ty, line)
                    ty -= 5 * mm
                    line = w
                else:
                    line = test
            if line:
                c.drawString(text_x, ty, line)
            y -= max(draw_h, 18 * mm) + 8 * mm
        y -= 4 * mm

    c.showPage()
    c.save()
    return buf.getvalue()


if __name__ == "__main__":
    db().close()
    print(f"Loaded {len(ENTRIES)} entries")
    print(f"Guest URL:  http://<your-funnel-host>/")
    print(f"Host URL:   http://<your-funnel-host>/?host={HOST_KEY}")
    print(f"Live text results: /results")
    print(f"Serving on 0.0.0.0:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
