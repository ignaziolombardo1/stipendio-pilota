"""Sceglie quali mercati hanno fatto un movimento grande e vanno segnalati. Funzione pura, provata a parte."""
import datetime, json, os

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mercato.json")

def load(now_utc=None, max_age_min=130):
    try:
        d = json.load(open(PATH, encoding="utf-8"))
        upd = datetime.datetime.strptime(d["updated"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=datetime.timezone.utc)
        now_utc = now_utc or datetime.datetime.now(datetime.timezone.utc)
        if (now_utc - upd).total_seconds() > max_age_min * 60:
            return {}
        return {a["id"]: a for a in d["assets"]}
    except Exception:
        return {}

def fmt(v):
    return ("+" if v > 0 else "−") + ("%.1f" % abs(v)).replace(".", ",") + "%"

def hits(item, market, done):
    """item: {"mk": {"ids": [...], "th": 5}}. Ritorna ([(asset, chiave)], testo) per i mercati sopra soglia non ancora segnalati."""
    mk = item.get("mk") or {}
    try:
        th = max(1.0, min(30.0, float(mk.get("th", 5))))
    except (TypeError, ValueError):
        th = 5.0
    out = []
    for i in (mk.get("ids") or [])[:20]:
        a = market.get(i)
        if not a or a.get("d1") is None:
            continue
        t = th * (1.6 if a.get("group") == "Criptovalute" else 1)
        key = "mk-%s-%s" % (i, a.get("asof"))
        if abs(a["d1"]) >= t and key not in done:
            out.append((a, key))
    if not out:
        return [], ""
    out.sort(key=lambda x: -abs(x[0]["d1"]))
    parts = ["%s %s" % (a["name"], fmt(a["d1"])) for a, _ in out[:4]]
    text = "Oggi si muovono molto: " + ", ".join(parts) + ". Apri l'app per capire perché. Non è un consiglio."
    return out, text
