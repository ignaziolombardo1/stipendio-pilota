#!/usr/bin/env python3
"""Crea mercato.json: prezzi giornalieri dell'ultimo anno, rischio e scenari per indici, ETF, azioni, cripto, materie prime.
Solo libreria standard. Se una fonte non risponde, tiene i dati precedenti. Non contiene previsioni: descrive cosa è successo e cosa potrebbe muovere i prezzi."""
import json, math, sys, os, datetime, urllib.request, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (compatible; StipendioPilota/1.0)"}
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mercato.json")

A = [
  ("sp500", "S&P 500 (USA)", "Indici e ETF", ["^GSPC"], "le 500 maggiori aziende americane", "i tassi della Fed, i profitti delle grandi aziende, l'inflazione americana"),
  ("nasdaq", "Nasdaq 100 (tecnologia USA)", "Indici e ETF", ["^NDX"], "le grandi aziende tecnologiche americane", "i profitti delle aziende tecnologiche, l'intelligenza artificiale, i tassi di interesse"),
  ("world", "Mondo (VWCE)", "Indici e ETF", ["VWCE.DE", "VWCE.MI"], "l'ETF sul mercato azionario mondiale", "l'economia globale, il cambio euro dollaro, i profitti delle aziende nel mondo"),
  ("stoxx", "Europa (Euro Stoxx 50)", "Indici e ETF", ["^STOXX50E"], "le 50 maggiori aziende dell'area euro", "i tassi della BCE, l'economia europea, i prezzi dell'energia"),
  ("ftsemib", "FTSE MIB (Italia)", "Indici e ETF", ["FTSEMIB.MI"], "le 40 maggiori aziende di Borsa Italiana", "le banche, l'energia, lo spread e le decisioni della BCE"),
  ("aapl", "Apple", "Azioni famose", ["AAPL"], "il produttore di iPhone e servizi", "le vendite di iPhone, i servizi digitali, le regole sulle grandi aziende tecnologiche"),
  ("msft", "Microsoft", "Azioni famose", ["MSFT"], "software e servizi cloud", "il cloud, l'intelligenza artificiale, i conti trimestrali"),
  ("nvda", "Nvidia", "Azioni famose", ["NVDA"], "i chip per l'intelligenza artificiale", "la domanda di chip per l'intelligenza artificiale, i conti trimestrali, la concorrenza"),
  ("tsla", "Tesla", "Azioni famose", ["TSLA"], "auto elettriche ed energia", "le consegne di auto, la concorrenza, le dichiarazioni del suo capo"),
  ("race", "Ferrari", "Azioni famose", ["RACE.MI", "RACE"], "le auto di lusso", "le consegne, i listini, la domanda di lusso nel mondo"),
  ("enel", "Enel", "Azioni famose", ["ENEL.MI"], "energia elettrica", "i prezzi dell'energia, i tassi, le regole sull'energia"),
  ("isp", "Intesa Sanpaolo", "Azioni famose", ["ISP.MI"], "la maggiore banca italiana", "i tassi della BCE, i conti trimestrali, lo spread"),
  ("btc", "Bitcoin", "Criptovalute", ["BTC-USD"], "la criptovaluta più diffusa", "la domanda degli investitori, le regole sulle criptovalute, la liquidità nei mercati"),
  ("eth", "Ethereum", "Criptovalute", ["ETH-USD"], "la seconda criptovaluta per valore", "l'uso della sua rete, le regole, l'andamento di Bitcoin"),
  ("gold", "Oro", "Materie prime e cambio", ["GC=F"], "il bene rifugio per eccellenza", "i tassi reali, le tensioni nel mondo, il dollaro"),
  ("oil", "Petrolio (WTI)", "Materie prime e cambio", ["CL=F"], "il petrolio americano", "le decisioni dei paesi produttori, l'economia mondiale, le tensioni politiche"),
  ("eurusd", "Euro / Dollaro", "Materie prime e cambio", ["EURUSD=X"], "quanti dollari vale un euro", "i tassi di BCE e Fed, la crescita di Europa e USA"),
]

def get(url, timeout=25):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()

def yahoo(sym):
    d = json.loads(get("https://query1.finance.yahoo.com/v8/finance/chart/%s?range=1y&interval=1d" % urllib.parse.quote(sym)))["chart"]["result"][0]
    ts, q = d["timestamp"], d["indicators"]["quote"][0]["close"]
    out = [(t, float(c)) for t, c in zip(ts, q) if c]
    return out, d["meta"].get("currency", "")

def pct(a, b): return (a / b - 1) * 100 if b else 0.0

def mean(x): return sum(x) / len(x)

def analyse(series, cur):
    c = [v for _, v in series]
    n = len(c)
    if n < 60: return None
    last = c[-1]
    ret = [math.log(c[i] / c[i - 1]) for i in range(max(1, n - 60), n) if c[i - 1] > 0]
    sd = math.sqrt(sum((r - mean(ret)) ** 2 for r in ret) / max(1, len(ret) - 1))
    vol = sd * math.sqrt(252) * 100
    hi = max(c); dd = pct(last, hi)
    peak, mdd = c[0], 0.0
    for v in c:
        peak = max(peak, v); mdd = min(mdd, pct(v, peak))
    s50 = mean(c[-50:]); s200 = mean(c[-200:]) if n >= 200 else mean(c)
    trend = "up" if last > s50 > s200 else "down" if last < s50 < s200 else "mix"
    score = round(min(100, vol / 60 * 100) * 0.65 + min(100, abs(dd) / 35 * 100) * 0.35)
    rl = "basso" if score < 35 else "medio" if score < 60 else "alto"
    at = lambda k: round(pct(last, c[-1 - k]), 2) if n > k else None
    step = max(1, (len(c[-90:])) // 45)
    spark = [round(v, 4) for v in c[-90:][::step]][-45:]
    return {"last": round(last, 4), "cur": cur, "d1": at(1), "w1": at(5), "m1": at(21), "m3": at(63), "y1": round(pct(last, c[0]), 2), "vol": round(vol, 1), "dd": round(dd, 1), "mdd": round(mdd, 1), "trend": trend, "risk": score, "rl": rl, "spark": spark, "asof": datetime.datetime.utcfromtimestamp(series[-1][0]).strftime("%Y-%m-%d")}

def scenari(name, a, why):
    t, mdd = a["trend"], abs(a["mdd"])
    if t == "up":
        s1 = "Il prezzo resta sopra le sue medie e continua a salire a piccoli passi. Chi ha già investito vede il valore crescere, chi entra ora compra a prezzi più alti."
        s2 = "Una brutta notizia o conti peggiori del previsto possono far scendere i prezzi in poche settimane: nell'ultimo anno ha è arrivato a perdere il %d%% rispetto al suo massimo." % round(mdd)
    elif t == "down":
        s1 = "Il calo continua e i prezzi scendono ancora. Per chi ha già investito significa vedere il valore ridursi, almeno nel breve."
        s2 = "Una buona notizia o un calo dei tassi possono far rimbalzare i prezzi, ma i rimbalzi durante un calo spesso non durano: nell'ultimo anno è arrivato a perdere il %d%% rispetto al suo massimo." % round(mdd)
    else:
        s1 = "Il prezzo resta in un intervallo, senza una direzione chiara: sale e scende restando vicino alle sue medie."
        s2 = "Una notizia forte, in positivo o in negativo, può far uscire il prezzo dall'intervallo: nell'ultimo anno è arrivato a perdere il %d%% rispetto al suo massimo." % round(mdd)
    return [["Se il trend continua", s1], ["Se cambia direzione", s2], ["Cosa lo muove", "Contano soprattutto " + why + "."]]

def main():
    old = {}
    try: old = {x["id"]: x for x in json.load(open(OUT, encoding="utf-8")).get("assets", [])}
    except Exception: pass
    res = []
    for aid, name, grp, syms, what, why in A:
        got = None
        for s in syms:
            try:
                ser, cur = yahoo(s); got = analyse(ser, cur)
                if got: got["sym"] = s; break
            except Exception as e: print("errore", s, e, file=sys.stderr)
        if got:
            got.update({"id": aid, "name": name, "group": grp, "what": what, "scen": scenari(name, got, why)}); res.append(got)
        elif aid in old: res.append(old[aid])
    if not res: print("nessun dato", file=sys.stderr); sys.exit(0)
    json.dump({"updated": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ"), "assets": res}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("ok", len(res))

if __name__ == "__main__": main()
