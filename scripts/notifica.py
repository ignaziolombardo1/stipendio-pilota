"""Invia la notifica "oggi è il giorno della paga" a chi l'ha attivata.
Gira ogni ora su GitHub Actions. Legge e aggiorna le sottoscrizioni solo
attraverso due funzioni Supabase protette da un token (nessuna chiave admin)."""
import json, os, sys, urllib.request, datetime, calendar
from zoneinfo import ZoneInfo
from pywebpush import webpush, WebPushException
from py_vapid import Vapid

URL = os.environ["SUPABASE_URL"].rstrip("/")
KEY = os.environ["SUPABASE_KEY"]
TOKEN = os.environ["PUSH_TOKEN"]
VAPID = Vapid.from_pem(os.environ["VAPID_PRIVATE_KEY"].encode())

def rpc(name, body):
    req = urllib.request.Request(URL + "/rest/v1/rpc/" + name, data=json.dumps(body).encode(), method="POST",
                                 headers={"apikey": KEY, "Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        t = r.read().decode()
        return json.loads(t) if t else None

rows = rpc("sp_push_due", {"p_token": TOKEN}) or []
sent = 0

def send(r, title, body):
    payload = json.dumps({"title": title, "body": body, "url": "./#home"})
    try:
        webpush(subscription_info=r["sub"], data=payload, vapid_private_key=VAPID, vapid_claims={"sub": "https://stipendio-pilota.vercel.app"})
        return True
    except WebPushException as e:
        code = getattr(e.response, "status_code", 0) if getattr(e, "response", None) is not None else 0
        print("errore invio:", code, file=sys.stderr)
        if code in (404, 410):
            rpc("sp_push_mark", {"p_token": TOKEN, "p_user": r["user_id"], "p_day": datetime.date.today().isoformat(), "p_drop": True})
        return False

for r in rows:
    try:
        now = datetime.datetime.now(ZoneInfo(r.get("tz") or "Europe/Rome"))
    except Exception:
        now = datetime.datetime.now(ZoneInfo("Europe/Rome"))
    today = now.date().isoformat()
    if now.hour < int(r["hour"]):
        continue
    day = min(int(r["payday"]), calendar.monthrange(now.year, now.month)[1])
    if now.day == day and r.get("last_sent") != today:
        if send(r, "Stipendio Pilota", "Oggi è il giorno della paga. Quanto hai preso questo mese? Aprila e scrivilo: ti preparo il nuovo mese."):
            rpc("sp_push_mark", {"p_token": TOKEN, "p_user": r["user_id"], "p_day": today, "p_drop": False})
            sent += 1
    done = set(r.get("sent") or [])
    for it in (r.get("rem") or []):
        k, d = it.get("k"), it.get("date")
        if not k or not d or k in done or today < d:
            continue
        if (datetime.date.fromisoformat(today) - datetime.date.fromisoformat(d)).days > 14:
            continue
        if send(r, "Stipendio Pilota", it.get("text") or "Ricordati di mettere da parte i soldi del mese."):
            try:
                rpc("sp_push_sent", {"p_token": TOKEN, "p_user": r["user_id"], "p_key": k})
            except Exception as e:
                print("segno-inviato non riuscito:", e, file=sys.stderr)
            sent += 1
print("sottoscrizioni:", len(rows), "inviate:", sent)
