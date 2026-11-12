#!/usr/bin/env python3
"""Aggiorna data.json: prezzi settimanali dei due fondi e titoli di notizie.
Usa solo la libreria standard. Se una fonte non risponde, tiene i dati precedenti."""
import json, re, sys, html, datetime, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

UA = {"User-Agent": "Mozilla/5.0 (compatible; StipendioPilota/1.0)"}
FUNDS = [
    {"id": "eq", "name": "Vanguard FTSE All-World (VWCE)", "isin": "IE00BK5BQT80", "symbols": ["VWCE.DE", "VWCE.MI", "VWCE.AS"]},
    {"id": "bond", "name": "iShares Core Global Aggregate Bond EUR Hedged", "isin": "IE00BDBRDM35", "symbols": ["AGGH.DE", "AGGH.MI", "AGGH.AS", "EUNA.DE"]},
]
FEEDS = [
    ("ANSA Economia", "https://www.ansa.it/sito/notizie/economia/economia_rss.xml"),
    ("Repubblica Economia", "https://www.repubblica.it/rss/economia/rss2.0.xml"),
    ("Il Sole 24 Ore", "https://www.ilsole24ore.com/rss/finanza-e-mercati.xml"),
    ("Il Sole 24 Ore", "https://www.ilsole24ore.com/rss/italia--economia.xml"),
    ("Corriere Economia", "https://xml2.corriereobjects.it/rss/economia.xml"),
    ("Corriere Economia", "https://www.corriere.it/rss/economia.xml"),
    ("Adnkronos Economia", "https://www.adnkronos.com/RSS_Economia.xml"),
    ("Sky TG24 Economia", "https://tg24.sky.it/rss/economia.xml"),
    ("Sky TG24 Economia", "https://tg24.sky.it/economia.rss"),
    ("Il Post Economia", "https://www.ilpost.it/economia/feed/"),
    ("La Stampa Economia", "https://www.lastampa.it/rss/economia.xml"),
    ("Il Fatto Quotidiano", "https://www.ilfattoquotidiano.it/economia-e-lobby/feed/"),
]

def get(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def yahoo(symbol):
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%s?range=5y&interval=1wk" % urllib.parse.quote(symbol)
    d = json.loads(get(url))["chart"]["result"][0]
    ts = d["timestamp"]; q = d["indicators"]["quote"][0]["close"]
    cur = d["meta"].get("currency", "")
    out = []
    for t, c in zip(ts, q):
        if c: out.append([datetime.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"), round(float(c), 4)])
    return out, cur

def yahoo_by_isin(isin):
    url = "https://query2.finance.yahoo.com/v1/finance/search?q=%s&quotesCount=8" % isin
    for q in json.loads(get(url)).get("quotes", []):
        if q.get("symbol"):
            try:
                s, cur = yahoo(q["symbol"])
                if len(s) > 20 and cur == "EUR": return s, cur, q["symbol"]
            except Exception: pass
    return None

def stooq(symbol):
    rows = get("https://stooq.com/q/d/l/?s=%s&i=w" % symbol.lower()).decode().strip().splitlines()[1:]
    out = []
    for r in rows:
        p = r.split(",")
        if len(p) >= 5:
            try: out.append([p[0], round(float(p[4]), 4)])
            except ValueError: pass
    return out[-270:]

def fetch_fund(f):
    for sym in f["symbols"]:
        try:
            s, cur = yahoo(sym)
            if len(s) > 20 and cur == "EUR": return s, sym
        except Exception as e: print("yahoo", sym, e, file=sys.stderr)
    try:
        r = yahoo_by_isin(f["isin"])
        if r: return r[0], r[2]
    except Exception as e: print("isin", f["isin"], e, file=sys.stderr)
    for sym in f["symbols"]:
        try:
            s = stooq(sym)
            if len(s) > 20: return s, sym
        except Exception as e: print("stooq", sym, e, file=sys.stderr)
    return None, None

def clean(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", t or ""))).strip()

def feed(name, url):
    root = ET.fromstring(get(url))
    out = []
    for it in root.iter("item"):
        title, link = clean(it.findtext("title")), (it.findtext("link") or "").strip()
        if not title or not link.startswith("http"): continue
        try: d = parsedate_to_datetime(it.findtext("pubDate")).strftime("%Y-%m-%dT%H:%M")
        except Exception: d = ""
        out.append({"t": title[:180], "u": link, "s": name, "d": d})
        if len(out) >= 8: break
    return out

def main(path="data.json"):
    try: old = json.load(open(path, encoding="utf-8"))
    except Exception: old = {}
    data = {"updated": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"), "funds": [], "news": []}
    oldf = {f["id"]: f for f in old.get("funds", [])}
    for f in FUNDS:
        s, sym = fetch_fund(f)
        prev = oldf.get(f["id"], {})
        if s: data["funds"].append({"id": f["id"], "name": f["name"], "isin": f["isin"], "symbol": sym, "series": s})
        else: data["funds"].append({"id": f["id"], "name": f["name"], "isin": f["isin"], "symbol": prev.get("symbol", ""), "series": prev.get("series", [])})
    seen, news, ok = set(), [], []
    done = set()
    for name, url in FEEDS:
        if name in done: continue
        try:
            items = feed(name, url)
            if items: done.add(name); ok.append(name)
            for n in items:
                k = re.sub(r"\W+", "", n["t"].lower())[:60]
                if k not in seen: seen.add(k); news.append(n)
        except Exception as e: print("feed", name, e, file=sys.stderr)
    news.sort(key=lambda n: n["d"], reverse=True)
    data["news"] = news[:30] if news else old.get("news", [])
    data["sources"] = ok
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("fondi", [(f["id"], len(f["series"])) for f in data["funds"]], "notizie", len(data["news"]), "fonti", ok)

if __name__ == "__main__":
    main(*sys.argv[1:])
