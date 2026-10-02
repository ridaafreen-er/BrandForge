import os, io, json, uuid, zipfile, sqlite3, threading, mimetypes
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
import agents as A

DATA = os.getenv("DATA_DIR", "./data"); os.makedirs(DATA + "/media", exist_ok=True)
DB = DATA + "/brandforge.db"; lock = threading.Lock(); pool = ThreadPoolExecutor(6)

def q(sql, args=()):
    with lock, sqlite3.connect(DB, timeout=15) as c:
        cur = c.execute(sql, args); return cur.fetchall()
q("CREATE TABLE IF NOT EXISTS docs(kind TEXT, id TEXT PRIMARY KEY, parent TEXT, data TEXT)")
def put(kind, id, data, parent=""): q("INSERT OR REPLACE INTO docs VALUES(?,?,?,?)", (kind, id, parent, json.dumps(data)))
def get(kind, id):
    r = q("SELECT data FROM docs WHERE kind=? AND id=?", (kind, id))
    if not r: raise HTTPException(404, f"{kind} not found")
    return json.loads(r[0][0])
def listing(kind, parent=None):
    r = q("SELECT data FROM docs WHERE kind=?" + (" AND parent=?" if parent else ""), (kind, parent) if parent else (kind,))
    return [json.loads(x[0]) for x in r]

app = FastAPI(title="BrandForge API")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "*").split(","), allow_methods=["*"], allow_headers=["*"])

class Brief(BaseModel):
    brand_name: str; product: str; audience: str; industry: str; goal: str; tone: str; description: str
    campaign: str = ""; website: str = ""; key_message: str = ""; avoid: str = ""; colors: str = ""
    platforms: list[str] = A.PLATFORMS; logo: str = ""; product_image: str = ""

@app.get("/api/status")
def status(): return {"engine": A.engine_name(), "llm": A.provider(), "voice": bool(os.getenv("GEMINI_API_KEY")), "images": bool(os.getenv("GEMINI_API_KEY")), "video": False}

@app.post("/api/brand/analyze")
def analyze(b: Brief):
    kit = A.brand_analyzer(b.model_dump()); bid = uuid.uuid4().hex[:10]
    brand = {"id": bid, "brief": b.model_dump(), "kit": kit, "approved": False, "engine": A.engine_name(), "created": datetime.utcnow().isoformat()}
    put("brand", bid, brand); return brand

@app.get("/api/brands")
def brands(): return listing("brand")  # brand memory, reusable for future campaigns

@app.put("/api/brand/{bid}/kit")
def edit_kit(bid: str, kit: dict):
    br = get("brand", bid); br["kit"].update(kit); put("brand", bid, br); return br

@app.post("/api/brand/{bid}/approve")
def approve_brand(bid: str):
    br = get("brand", bid); br["approved"] = True; put("brand", bid, br); return br

class CampaignIn(BaseModel):
    brand_id: str

@app.post("/api/campaign/create")
def create_campaign(i: CampaignIn):
    br = get("brand", i.brand_id)
    if not br["approved"]: raise HTTPException(400, "Approve the Brand Kit first.")
    plan = A.campaign_planner(br["kit"], br["brief"], [p for p in br["brief"]["platforms"] if p in A.PLATFORMS] or A.PLATFORMS)
    cid = uuid.uuid4().hex[:10]
    cam = {"id": cid, "brand_id": i.brand_id, "plan": plan, "ctx": A.make_ctx(br["kit"], plan), "status": "planned",
           "steps": {"brand": "done", "plan": "done"}, "engine": A.engine_name(), "created": datetime.utcnow().isoformat()}
    put("campaign", cid, cam, i.brand_id); return cam

def run_asset(aid):
    a = get("asset", aid); cam = get("campaign", a["campaign_id"])
    try:
        text, meta, eng = A.generate_asset(a["platform"], cam["ctx"], cam["plan"])
        a.update(text=text, meta=meta, engine=eng, critic=A.critic(a["platform"], text, cam["ctx"]), status="ready", versions=[{"text": text, "label": "Original", "at": datetime.utcnow().isoformat()}])
    except Exception as e:
        a.update(status="error", error=str(e))
    put("asset", aid, a, a["campaign_id"])

@app.post("/api/campaign/generate")
def generate(i: CampaignIn):  # here brand_id field carries the campaign id
    cam = get("campaign", i.brand_id); cam["status"] = "generating"; put("campaign", cam["id"], cam, cam["brand_id"])
    ids = []
    for p in [x["platform"] for x in cam["plan"]["platforms"]]:
        fmt = A.PLAN_FORMATS[p]; aid = uuid.uuid4().hex[:10]; ids.append(aid)
        put("asset", aid, {"id": aid, "campaign_id": cam["id"], "platform": p, "format": fmt[0], "ratio": fmt[1], "summary": fmt[2], "status": "generating", "text": "", "meta": {}, "critic": None, "versions": [], "approved": False}, cam["id"])
    def finish():
        list(pool.map(run_asset, ids)); c = get("campaign", cam["id"]); c["status"] = "ready"; put("campaign", c["id"], c, c["brand_id"])
    threading.Thread(target=finish, daemon=True).start()
    return {"started": ids}

@app.get("/api/campaign/{cid}")
def campaign(cid: str):
    c = get("campaign", cid); c["assets"] = listing("asset", cid); return c

@app.get("/api/campaign/{cid}/assets")
def assets(cid: str): return listing("asset", cid)

@app.post("/api/assets/{aid}/images")
def generate_asset_images(aid: str):
    a = get("asset", aid)
    if a["platform"] != "instagram": raise HTTPException(400, "Image generation is currently available for Instagram carousel assets.")
    if not os.getenv("GEMINI_API_KEY"): raise HTTPException(400, "Set GEMINI_API_KEY in backend/.env to generate images.")
    slides = (a.get("meta") or {}).get("slides", [])
    if not slides: raise HTTPException(400, "This asset has no slide image prompts. Regenerate it before creating images.")
    generated, errors = 0, []
    for index, slide in enumerate(slides):
        prompt = slide.get("image_prompt", "").strip()
        if not prompt:
            errors.append(f"Slide {index + 1}: missing image prompt")
            continue
        try:
            image, extension = A.generate_image(prompt + " Create a polished, brand-safe Instagram carousel visual. Do not render text or lettering in the image.", "4:5")
            filename = f"{aid}-slide-{index + 1}{extension}"
            with open(f"{DATA}/media/{filename}", "wb") as f: f.write(image)
            slide["image"] = f"/api/media/{filename}"
            generated += 1
            put("asset", aid, a, a["campaign_id"])
        except Exception as e:
            errors.append(f"Slide {index + 1}: {e}")
    if not generated and errors: raise HTTPException(502, "; ".join(errors))
    return {"generated": generated, "errors": errors, "asset": a}

def ctx_of(a): return get("campaign", a["campaign_id"])

class RegenIn(BaseModel):
    instruction: str = ""

@app.post("/api/assets/{aid}/regenerate")
def regenerate(aid: str, i: RegenIn = RegenIn()):
    a = get("asset", aid); cam = ctx_of(a)
    fb = " ".join([i.instruction, (a.get("critic") or {}).get("improve", "")]).strip() or "Improve brand fit."
    text, meta, eng = A.generate_asset(a["platform"], cam["ctx"], cam["plan"], feedback=fb, previous=a["text"])
    old = a["critic"]; new = A.critic(a["platform"], text, cam["ctx"])
    a["versions"].append({"text": text, "label": f"Regenerated ({old['overall']} → {new['overall']})", "at": datetime.utcnow().isoformat()})
    a.update(text=text, meta=meta or a["meta"], critic=new, engine=eng, status="ready", approved=False); put("asset", aid, a, a["campaign_id"]); return a

class EditIn(BaseModel):
    text: str; label: str = "Manual edit"

@app.put("/api/assets/{aid}")
def edit(aid: str, i: EditIn):
    a = get("asset", aid); cam = ctx_of(a)
    a["versions"].append({"text": i.text, "label": i.label, "at": datetime.utcnow().isoformat()})
    a.update(text=i.text, critic=A.critic(a["platform"], i.text, cam["ctx"]), approved=False); put("asset", aid, a, a["campaign_id"]); return a

class RefineIn(BaseModel):
    mode: str  # shorter | engaging | genz | professional | cta

@app.post("/api/assets/{aid}/refine")  # returns a proposal only; nothing is overwritten until the user saves
def refine(aid: str, i: RefineIn):
    a = get("asset", aid)
    if i.mode not in ("shorter", "engaging", "genz", "professional", "cta"): raise HTTPException(400, "Unknown mode")
    text, eng = A.rewrite(a["text"], i.mode, ctx_of(a)["ctx"]); return {"text": text, "engine": eng}

@app.post("/api/assets/{aid}/restore/{idx}")
def restore(aid: str, idx: int):
    a = get("asset", aid); v = a["versions"][idx]; return edit(aid, EditIn(text=v["text"], label=f"Restored: {v['label']}"))

@app.post("/api/assets/{aid}/approve")
def approve(aid: str):
    a = get("asset", aid); a["approved"] = True; put("asset", aid, a, a["campaign_id"]); return a

@app.post("/api/assets/{aid}/voiceover")
def voiceover(aid: str):
    a = get("asset", aid)
    try: audio = A.tts(a["text"])
    except Exception as e: return {"configured": True, "ok": False, "message": f"Voice provider error: {e}"}
    if audio is None: return {"configured": False, "ok": False, "message": "Voice generation is not configured. Showing voiceover script."}
    open(f"{DATA}/media/{aid}.wav", "wb").write(audio); a["audio"] = f"/api/media/{aid}.wav"; put("asset", aid, a, a["campaign_id"])
    return {"configured": True, "ok": True, "url": a["audio"]}

@app.get("/api/media/{name}")
def media(name: str):
    p = f"{DATA}/media/{os.path.basename(name)}"
    if not os.path.exists(p): raise HTTPException(404)
    media_type = mimetypes.guess_type(p)[0] or "application/octet-stream"
    return Response(open(p, "rb").read(), media_type=media_type)

def report(c, br, assets):
    L = [f"# {br['kit']['brandName']} — {c['plan']['name']}", "", f"Engine: {c['engine']} ({'AI provider' if c['engine'] != 'demo' else 'DEMO content, not from an external AI API'})", "",
         "## Strategy", *[f"- **{k}**: {v}" for k, v in c["plan"].items() if isinstance(v, str)], ""]
    for a in assets:
        cr = a.get("critic") or {}
        L += [f"## {a['platform'].title()} — {a['format']} (brand fit {cr.get('overall', '-')}/10, {'approved' if a['approved'] else a['status']})", "", a["text"], ""]
    return "\n".join(L)

@app.post("/api/export/{cid}")
def export(cid: str):
    c = get("campaign", cid); br = get("brand", c["brand_id"]); assets_ = listing("asset", cid); buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("campaign.json", json.dumps({"brand": br, "campaign": c, "assets": assets_}, indent=2))
        z.writestr("campaign-report.md", report(c, br, assets_))
        for a in assets_:
            z.writestr(f"copy/{a['platform']}.txt", a["text"])
            for i, s in enumerate((a.get("meta") or {}).get("slides", [])):
                z.writestr(f"visual-prompts/{a['platform']}-{i+1}.txt", s.get("image_prompt", ""))
                if s.get("image"):
                    image_name = os.path.basename(s["image"])
                    image_path = f"{DATA}/media/{image_name}"
                    extension = os.path.splitext(image_name)[1] or ".img"
                    if os.path.exists(image_path): z.write(image_path, f"images/{a['platform']}-{i+1}{extension}")
            for ext in ("wav", "mp3"):
                path = f"{DATA}/media/{a['id']}.{ext}"
                if os.path.exists(path): z.write(path, f"audio/{a['platform']}.{ext}")
    return Response(buf.getvalue(), media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="brandforge-{cid}.zip"'})
