"""Publica/agenda os vídeos do penumbra067 no Zernio a partir de posts.json.
Só usa contas com "penumbra" no nome (nunca outras marcas da mesma chave).
Uso: ZERNIO_API_KEY=... python publicar.py [--dry-run] [--so ID]"""
import json, os, sys, uuid, urllib.request
from datetime import datetime, timezone, timedelta

API = "https://zernio.com/api/v1"
RAW = "https://raw.githubusercontent.com/TonyWatanabe-dev/penumbra-midia/main/"
KEY = os.environ["ZERNIO_API_KEY"]
DRY = "--dry-run" in sys.argv or os.environ.get("TESTE") == "true"
SO = sys.argv[sys.argv.index("--so") + 1] if "--so" in sys.argv else os.environ.get("SO", "")
BRT = timezone(timedelta(hours=-3))

def call(method, path, body=None, headers=None):
    req = urllib.request.Request(API + path, method=method,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req) as r: return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e: return e.code, e.read().decode()[:800]

def posts(status):
    st, d = call("GET", f"/posts?status={status}&limit=100")
    return d.get("posts", []) if isinstance(d, dict) else []

st, data = call("GET", "/accounts")
accounts = data.get("accounts", []) if isinstance(data, dict) else []
print("Contas encontradas:", [(a.get("platform"), a.get("username") or a.get("displayName")) for a in accounts])
alvo = {}
for a in accounts:
    nome = f'{a.get("username","")} {a.get("displayName","")}'.lower()
    if "penumbra" in nome and a.get("platform") in ("youtube", "tiktok", "instagram"):
        alvo[a["platform"]] = a.get("_id") or a.get("id")
if not alvo: sys.exit("Nenhuma conta penumbra067 encontrada nesta chave do Zernio.")
print("Publicando em:", sorted(alvo))

agendados = posts("scheduled")
ja_foi = " ".join(m.get("url", "") for s in ("published", "publishing", "partial")
                  for p in posts(s) for m in p.get("mediaItems", []))
for p in json.load(open("posts.json", encoding="utf-8")):
    if SO and p["id"] != SO: continue
    if RAW + p["video"] in ja_foi:
        print(p["id"], "já publicado, pulando"); continue
    plats = []
    for plat, acc in alvo.items():
        e = {"platform": plat, "accountId": acc}
        if plat == "youtube": e["platformSpecificData"] = {"title": p["titulo_youtube"], "visibility": "public"}
        if plat == "instagram": e["platformSpecificData"] = {"firstComment": p["comentario_fixado"]}
        plats.append(e)
    item = {"type": "video", "url": RAW + p["video"]}
    if p.get("capa"): item["thumbnail"] = RAW + p["capa"]
    body = {"content": p["legenda"], "mediaItems": [item], "platforms": plats}
    if "tiktok" in alvo:
        body["tiktokSettings"] = {"privacy_level": "PUBLIC_TO_EVERYONE", "allow_comment": True, "allow_duet": True,
                                  "allow_stitch": True, "content_preview_confirmed": True, "express_consent_given": True}
        if p.get("capa"): body["tiktokSettings"]["video_cover_image_url"] = RAW + p["capa"]
    quando = p["quando"]
    # horário que já passou (ex.: rodou 12h05 para um post das 12h) -> publica na hora
    if quando != "agora" and datetime.fromisoformat(quando).replace(tzinfo=BRT) <= datetime.now(BRT) + timedelta(minutes=2):
        print(f'  {quando} já passou, publicando agora'); quando = "agora"
    if quando == "agora": body["publishNow"] = True
    else: body["scheduledFor"], body["timezone"] = quando, "America/Sao_Paulo"
    if DRY:
        print(f'[teste] {p["id"]} -> {quando} em {sorted(alvo)}'); continue
    for old in agendados:
        if RAW + p["video"] in " ".join(m.get("url", "") for m in old.get("mediaItems", [])):
            print("  removendo agendamento antigo", old["_id"], call("DELETE", f'/posts/{old["_id"]}')[0])
    chave = str(uuid.uuid5(uuid.NAMESPACE_URL, RAW + p["video"] + "|" + p.get("capa", "") + "|" + p["quando"]))
    st, r = call("POST", "/posts", body, {"Idempotency-Key": chave})
    print(p["id"], st, (r.get("post", {}).get("status") if isinstance(r, dict) else r))
    if st >= 300: falhas = globals().setdefault("falhas", []); falhas.append(p["id"])
if globals().get("falhas"): sys.exit(f"Falhou: {falhas}")
