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
for r in rows:
    try:
        now = datetime.datetime.now(ZoneInfo(r.get("tz") or "Europe/Rome"))
    except Exception:
        now = datetime.datetime.now(ZoneInfo("Europe/Rome"))
    day = min(int(r["payday"]), calendar.monthrange(now.year, now.month)[1])
    today = now.date().isoformat()
    if now.day != day or now.hour < int(r["hour"]) or r.get("last_sent") == today:
        continue
    payload = json.dumps({"title": "Stipendio Pilota", "body": "Oggi è il giorno della paga. Quanto hai preso questo mese? Aprila e scrivilo: ti preparo il nuovo mese.", "url": "./#home"})
    try:
        webpush(subscription_info=r["sub"], data=payload, vapid_private_key=VAPID, vapid_claims={"sub": "https://stipendio-pilota.vercel.app"})
        rpc("sp_push_mark", {"p_token": TOKEN, "p_user": r["user_id"], "p_day": today, "p_drop": False})
        sent += 1
    except WebPushException as e:
        code = getattr(e.response, "status_code", 0) if getattr(e, "response", None) is not None else 0
        print("errore invio:", code, file=sys.stderr)
        if code in (404, 410):
            rpc("sp_push_mark", {"p_token": TOKEN, "p_user": r["user_id"], "p_day": today, "p_drop": True})
print("sottoscrizioni:", len(rows), "inviate:", sent)
