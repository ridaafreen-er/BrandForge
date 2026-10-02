"""BrandForge agents. All share one BrandContext. Real LLM if a key is set, otherwise a labelled demo engine."""
import os, re, json, time, hashlib, base64, urllib.request, urllib.error, urllib.parse

PLATFORMS = ["instagram", "reels", "linkedin", "x", "blog", "audio"]
PLAN_FORMATS = {
    "instagram": ("Carousel + caption", "4:5", "5 slides + caption"),
    "reels": ("Short-form video + voiceover", "9:16", "4 scenes + captions"),
    "linkedin": ("Founder story post", "text", "Story post"),
    "x": ("Thread", "text", "6-post thread"),
    "blog": ("SEO article", "long-form", "Article + meta"),
    "audio": ("20-second ad", "audio", "Script + voice direction"),
}

# ---------------- LLM provider abstraction ----------------
def provider():
    if os.getenv("GROQ_API_KEY"): return "groq"
    if os.getenv("GEMINI_API_KEY"): return "gemini"
    if os.getenv("OPENROUTER_API_KEY"): return "openrouter"
    if os.getenv("OPENAI_API_KEY"): return "openai"
    return None

def _post(url, headers, body):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace").strip()
        raise RuntimeError(f"Provider HTTP {e.code}: {detail or e.reason}") from e

def llm_json(system, prompt):
    """Return parsed JSON dict from the configured provider, or None (caller falls back)."""
    p = provider()
    if not p: return None
    try:
        if p == "openai":
            d = _post("https://api.openai.com/v1/chat/completions",
                      {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]},
                      {"model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"), "response_format": {"type": "json_object"},
                       "messages": [{"role": "system", "content": system + " Reply with JSON only."}, {"role": "user", "content": prompt}]})
            txt = d["choices"][0]["message"]["content"]
        elif p == "openrouter":
            d = _post("https://openrouter.ai/api/v1/chat/completions",
                      {"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"]},
                      {"model": os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"), "response_format": {"type": "json_object"},
                       "messages": [{"role": "system", "content": system + " Reply with JSON only."}, {"role": "user", "content": prompt}]})
            txt = d["choices"][0]["message"]["content"]
            txt = d["choices"][0]["message"]["content"]
        elif p == "groq":
            d = _post("https://api.groq.com/openai/v1/chat/completions",
                      {"Authorization": "Bearer " + os.environ["GROQ_API_KEY"]},
                      {"model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), "response_format": {"type": "json_object"},
                       "messages": [{"role": "system", "content": system + " Reply with JSON only."}, {"role": "user", "content": prompt}]})
            txt = d["choices"][0]["message"]["content"]
        elif p == "gemini":
            d = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{os.getenv('GEMINI_MODEL', 'gemini-3.8-flash')}:generateContent",
                      {"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                      {"systemInstruction": {"parts": [{"text": system + " Reply with JSON only."}]},
                       "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                       "generationConfig": {"responseMimeType": "application/json"}})
            txt = d["candidates"][0]["content"]["parts"][0]["text"]
        txt = re.sub(r"^```(?:json)?|```$", "", txt.strip()).strip()
        return json.loads(txt)
    except Exception as e:
        print("LLM error, using demo engine:", e)
        return None

def engine_name(): return provider() or "demo"

# ---------------- helpers ----------------
def _seed(*a): return int(hashlib.md5("|".join(map(str, a)).encode()).hexdigest()[:6], 16)
def _words(s): return [w.strip() for w in re.split(r"[,/;]", s or "") if w.strip()]
PALETTES = {
    ("cafe", "coffee", "beverage", "food"): ["#3B2417", "#C8793A", "#F6E7D0", "#7FB069", "#FFB020"],
    ("tech", "software", "saas", "ai"): ["#0F172A", "#6366F1", "#22D3EE", "#F1F5F9", "#F59E0B"],
    ("fashion", "beauty", "lifestyle"): ["#1F1A24", "#E85D75", "#F7D6E0", "#F4F0EC", "#C9A227"],
    ("fitness", "health", "wellness"): ["#0B3D2E", "#2FBF71", "#E8F7EE", "#FF7A45", "#1D1D1D"],
}
def pick_palette(industry, preferred):
    hexes = re.findall(r"#[0-9a-fA-F]{6}", preferred or "")
    if len(hexes) >= 2: return hexes[:5]
    for keys, pal in PALETTES.items():
        if any(k in (industry or "").lower() for k in keys): return pal
    return ["#1E293B", "#3B82F6", "#F8FAFC", "#F97316", "#10B981"]

# ---------------- BrandAnalyzer ----------------
def brand_analyzer(b):
    tone = _words(b["tone"]) or ["friendly"]
    fb = {
        "brandName": b["brand_name"],
        "summary": f"{b['brand_name']} offers {b['product']} for {b['audience']}. {b['description']}",
        "audience": b["audience"],
        "personality": [t.capitalize() for t in tone[:3]] + ["Authentic"],
        "tone": ", ".join(tone),
        "writingStyle": "Short sentences, active voice, conversational. " + ("Emoji welcome in moderation." if re.search("play|fun|youth|gen|energ", b["tone"].lower()) else "Clear and confident."),
        "vocabulary": tone + [w for w in re.findall(r"[A-Za-z]{5,}", b.get("key_message", ""))[:4]],
        "forbiddenWords": _words(b.get("avoid", "")) or ["cheap", "synergy", "revolutionary"],
        "colors": pick_palette(b["industry"], b.get("colors")),
        "visualStyle": "Warm, modern, energetic" if "play" in b["tone"].lower() else "Clean, modern, confident",
        "contentPillars": ["Product", "Audience lifestyle", "Community", "Offers"],
        "CTA": b.get("cta") or f"Try {b['product']} today",
        "positioning": f"The go-to {b['industry'].lower()} brand for {b['audience'].lower()}.",
        "keyMessages": [b.get("key_message") or f"{b['product']} made for {b['audience']}."],
    }
    kit = llm_json("You are BrandAnalyzer. Produce a brand kit as JSON with exactly these keys: " + ", ".join(fb) +
                   ". personality, vocabulary, forbiddenWords, colors (5 hex strings), contentPillars, keyMessages are arrays of strings; others strings.",
                   "Brief:\n" + json.dumps(b))
    if isinstance(kit, dict) and all(k in kit for k in fb):
        kit["brandName"] = b["brand_name"]; kit["forbiddenWords"] = list(set(kit["forbiddenWords"]) | set(_words(b.get("avoid", ""))))
        return kit
    return fb

# ---------------- CampaignPlanner ----------------
def campaign_planner(kit, brief, platforms):
    name = brief.get("campaign") or brief.get("goal") or "Launch Campaign"
    fb = {
        "name": name, "objective": brief["goal"], "idea": f"{kit['brandName']}: {kit['keyMessages'][0]}",
        "hook": f"Meet {brief['product']} — made for {brief['audience'].lower()}.",
        "keyMessage": kit["keyMessages"][0], "CTA": kit["CTA"], "audience": kit["audience"],
        "contentStrategy": f"Lead with {kit['contentPillars'][0].lower()}, prove it with {kit['contentPillars'][1].lower()}, close with {kit['contentPillars'][3].lower()}.",
        "platformStrategy": "Each platform gets native formats, not copies of one text.",
    }
    plan = llm_json("You are CampaignPlanner. JSON with keys: " + ", ".join(fb) + ". All strings. Do not change the brand identity.",
                    f"Brand kit: {json.dumps(kit)}\nBrief: {json.dumps(brief)}")
    if not (isinstance(plan, dict) and all(k in plan for k in fb)): plan = fb
    plan["platforms"] = [{"platform": p, "format": PLAN_FORMATS[p][0], "ratio": PLAN_FORMATS[p][1], "summary": PLAN_FORMATS[p][2]} for p in platforms]
    return plan

def make_ctx(kit, plan):
    return {**{k: kit[k] for k in ("brandName", "audience", "tone", "personality", "visualStyle", "forbiddenWords", "writingStyle", "positioning")},
            "description": kit["summary"], "colors": kit["colors"], "keyMessages": [plan["keyMessage"]], "CTA": plan["CTA"],
            "campaign": plan["name"], "hook": plan["hook"], "idea": plan["idea"]}

# ---------------- Demo engine (templates fed by BrandContext, no hard-coded brand) ----------------
PLAYFUL = lambda c: bool(re.search("play|fun|youth|gen|energ|bold", c["tone"].lower()))
def _tags(c):
    a = re.sub(r"\W", "", c["brandName"]); b = re.sub(r"\W", "", c["campaign"])
    return "#" + a + " #" + b + " #NewDrop"

def _demo(platform, c, extra=""):
    n, km, cta, h, aud = c["brandName"], c["keyMessages"][0], c["CTA"], c["hook"], c["audience"].lower()
    pl = PLAYFUL(c); e = (lambda s: s) if pl else (lambda s: "")
    if platform == "instagram":
        slides = [("Hook", h + e(" ✨")), ("The problem", f"{aud.capitalize()} are busy. Good options shouldn't be hard to find."),
                  ("The answer", km), ("Why it works", f"Made around what {aud} actually care about."), ("Your move", cta + e(" 👉"))]
        text = "\n".join(f"SLIDE {i+1} — {t}: {b}" for i, (t, b) in enumerate(slides)) + f"\n\nCAPTION:\n{h} {km}{e(' 🙌')}\n{cta}.\n\n{_tags(c)}"
        meta = {"slides": [{"title": t, "body": b, "image_prompt": f"{t} slide, {c['visualStyle']} style, palette {', '.join(c['colors'][:3])}, for {aud}"} for t, b in slides]}
    elif platform == "reels":
        sc = [("0-3s", "Close-up hook shot", h), ("3-8s", "Product in action", f"{n} is here. {km}"), ("8-13s", f"{aud.capitalize()} in everyday life", "Fits right into your day."), ("13-18s", "Logo + offer end card", cta)]
        text = "HOOK: " + h + "\n\n" + "\n".join(f"[{t}] VISUAL: {v} | VO: {vo} | CAPTION: {vo[:40]}" for t, v, vo in sc) + f"\n\nCTA: {cta}\nFORMAT: 9:16, 18s"
        meta = {"scenes": [{"time": t, "visual": v, "voiceover": vo} for t, v, vo in sc], "metadata": {"ratio": "9:16", "duration": "18s", "title": f"{n} — {c['campaign']}"}}
    elif platform == "linkedin":
        text = (f"Why we started {n}.\n\n{c['description']}\n\nWe noticed {aud} were underserved, so we built around one idea: {km}\n\n"
                f"Three lessons so far:\n1. Know your audience before your product.\n2. Keep the promise simple.\n3. Make the first step easy.\n\n{cta}.\n\n{_tags(c)}")
        meta = {}
    elif platform == "x":
        tw = [f"{h} 🧵" if pl else h, f"The problem: {aud} are short on time and options.", f"Our answer: {km}", f"What makes {n} different? It's built for {aud}, not around them.",
              "The first 100 people to try it will tell us what to improve. We're listening.", f"{cta}. Reply with your take 👇" if pl else f"{cta}."]
        text = "\n\n".join(f"{i+1}/ {t}" for i, t in enumerate(tw)); meta = {"tweets": tw}
    elif platform == "blog":
        t = f"{c['campaign']}: {km}"
        text = (f"SEO TITLE: {t}\nMETA: {n} introduces {c['campaign']} — {km} Learn what's new and how to get started.\n\n# {t}\n\n## Why we built this\n{c['description']}\n\n"
                f"## Who it's for\nEveryone in the {aud} community who wants less friction and more value.\n\n## What makes it different\n{km} We focus on {', '.join(p.lower() for p in c['personality'][:3])} experiences.\n\n"
                f"## How to get started\nIt takes a minute. {cta}.\n\n## Final thoughts\nThis is only the beginning for {n}. Tell us what you want to see next.\n\n" + ("Our team believes in making things better every day. " * 8))
        meta = {}
    else:
        text = f"VOICE: upbeat, friendly, medium pace\n\n[0-5s] Hey {aud}! {h}\n[5-15s] {n}. {km}\n[15-20s] {cta}. {n}."
        meta = {"voice_direction": "Upbeat, friendly, medium pace", "duration": "20s"}
    return text, meta

def _formal_tamper(platform, text, c):  # demo engine: LinkedIn drafts come out stiff so the critic has something real to flag
    return re.sub(r"[!✨👉🙌👇🧵]", "", text) if platform in ("linkedin",) and PLAYFUL(c) else text

def improve(platform, text, c, fb):
    """Demo-engine regeneration: applies critic instructions against the shared BrandContext."""
    for w in c["forbiddenWords"]: text = re.sub(re.escape(w), "", text, flags=re.I)
    if c["CTA"].lower()[:10] not in text.lower(): text += f"\n\n{c['CTA']}."
    if not any(w in text.lower() for w in re.findall(r"\w{5,}", c["keyMessages"][0].lower())[:3]): text += f"\n{c['keyMessages'][0]}"
    if PLAYFUL(c) and text.count("!") + len(re.findall(r"[^\x00-\x7F]", text)) < 2: text = text.replace(f"{c['CTA']}.", f"{c['CTA']}! 🚀 ", 1)
    return text.strip()

# ---------------- Generators (Copy / Visual / Voice / Video + PlatformAdapter) ----------------
SPECS = {
    "instagram": "Visual-first carousel: 5 slides (title+body+image_prompt) and caption with hashtags and CTA.",
    "reels": "9:16 reel, <=20s: hook, 4 scenes (time, visual, voiceover), captions, CTA.",
    "linkedin": "Professional but on-brand founder story, 600-1500 chars, no hashtag spam.",
    "x": "Thread of 5-7 posts, each <=280 chars, strong hook, CTA last.",
    "blog": "SEO title, meta description, H2 headings, 600+ word article.",
    "audio": "20-second ad, ~50 words, voice direction, CTA.",
}
AGENT = {"instagram": "CopyGenerator+VisualGenerator", "reels": "VideoGenerator", "linkedin": "CopyGenerator", "x": "CopyGenerator", "blog": "CopyGenerator", "audio": "VoiceGenerator"}

def generate_asset(platform, c, plan, feedback=None, previous=None):
    """PlatformAdapter applies SPECS; every agent gets the same BrandContext c. Returns (text, meta, engine)."""
    prompt = (f"BrandContext: {json.dumps(c)}\nCampaign plan: {json.dumps({k: v for k, v in plan.items() if k != 'platforms'})}\n"
              f"Platform: {platform}. Requirements: {SPECS[platform]}\nDo not invent brand identity; obey forbiddenWords.\n"
              + (f"Previous draft:\n{previous}\nCritic feedback to fix: {feedback}\n" if feedback else "")
              + 'Return JSON: {"text": "full readable asset", "meta": {}}. For instagram meta.slides=[{title,body,image_prompt}]; reels meta.scenes=[{time,visual,voiceover}]; x meta.tweets=[...].')
    r = llm_json(f"You are the {AGENT[platform]} agent in BrandForge.", prompt)
    if isinstance(r, dict) and isinstance(r.get("text"), str): return r["text"], r.get("meta") or {}, provider()
    time.sleep(0.8 + (_seed(platform) % 20) / 10)  # simulated latency, demo engine only
    if previous is not None: return improve(platform, previous, c, feedback), {}, "demo"
    t, m = _demo(platform, c); return _formal_tamper(platform, t, c), m, "demo"

def rewrite(text, mode, c):
    instr = {"shorter": "Make it ~40% shorter.", "engaging": "Make it more engaging with a stronger hook.", "genz": "Rewrite in a Gen-Z voice.",
             "professional": "Make it more professional.", "cta": "Make the CTA stronger and clearer."}[mode]
    r = llm_json("You are an editor. Keep brand voice and facts.", f"BrandContext: {json.dumps(c)}\n{instr}\nText:\n{text}\nReturn JSON {{\"text\": \"...\"}}")
    if isinstance(r, dict) and r.get("text"): return r["text"], provider()
    if mode == "shorter":
        ps = text.split("\n\n"); return "\n\n".join(ps[: max(2, len(ps) * 3 // 5)] + ps[-1:]) if len(ps) > 3 else text[: int(len(text) * .7)].rsplit(" ", 1)[0] + "…", "demo"
    if mode == "engaging": return "Wait for it 👀\n\n" + text, "demo"
    if mode == "genz": return text.replace(".", " fr.").replace("Hey", "Yo") + " 🔥", "demo"
    if mode == "professional": return re.sub(r"[!✨👉🙌👇🧵🔥🚀]", ".", text), "demo"
    return text.rstrip() + f"\n\n👉 {c['CTA']} — start now!", "demo"

# ---------------- BrandCritic ----------------
DIMS = ["brandAlignment", "audienceRelevance", "messageConsistency", "toneConsistency", "platformFit", "ctaQuality"]
LIMITS = {"x": (200, 1800), "linkedin": (500, 2200), "blog": (1200, 20000), "audio": (80, 600), "instagram": (200, 3000), "reels": (150, 2000)}

def critic(platform, text, c):
    r = llm_json("You are BrandCritic. Score strictly 0-10.", f"BrandContext: {json.dumps(c)}\nPlatform: {platform} ({SPECS[platform]})\nAsset:\n{text}\n"
                 f'Return JSON {{"scores": {{{", ".join(chr(34)+d+chr(34)+": number" for d in DIMS)}}}, "feedback": ["..."], "improve": "instructions"}}')
    if isinstance(r, dict) and isinstance(r.get("scores"), dict) and all(d in r["scores"] for d in DIMS):
        s = {d: round(float(r["scores"][d]), 1) for d in DIMS}
        return {"scores": s, "overall": round(sum(s.values()) / 6, 1), "feedback": r.get("feedback", []), "improve": r.get("improve", ""), "engine": provider()}
    t = text.lower(); fb, pen = [], {d: 0.0 for d in DIMS}
    jit = lambda d: (_seed(platform, d, len(text)) % 7) / 10
    if any(w.lower() in t for w in c["forbiddenWords"] if w): pen["brandAlignment"] += 2.5; fb.append("Contains a word the brand asked to avoid.")
    cta_ok = c["CTA"].lower()[:10] in t
    if cta_ok: fb.append("CTA is strong and matches the approved brand CTA.")
    else: pen["ctaQuality"] += 2.5; fb.append("CTA is missing or doesn't match the approved CTA.")
    kw = re.findall(r"\w{5,}", c["keyMessages"][0].lower()); hit = sum(w in t for w in kw)
    if kw and hit < max(1, len(kw) // 2): pen["messageConsistency"] += 2.0; fb.append("Key message is not clearly stated.")
    energy = text.count("!") + len(re.findall(r"[^\x00-\x7F]", text))
    if PLAYFUL(c) and energy < 2 and platform not in ("blog",): pen["toneConsistency"] += 5.0; pen["audienceRelevance"] += 1.2; fb.append("Tone is more formal than the approved brand voice.")
    elif PLAYFUL(c): fb.append("Tone matches the approved playful voice.")
    lo, hi = LIMITS[platform]
    if not lo <= len(text) <= hi: pen["platformFit"] += 1.8; fb.append(f"Length is off for {platform} (target {lo}-{hi} chars).")
    else: fb.append("Format and length fit the platform.")
    s = {d: round(max(3, min(10, 9.4 - pen[d] - jit(d))), 1) for d in DIMS}
    ov = round(sum(s.values()) / 6, 1)
    imp = "" if ov >= 8 else " ".join(f for f in fb if "strong" not in f and "matches" not in f and "fit the" not in f) + f" Keep the approved voice ({c['tone']}) and CTA."
    return {"scores": s, "overall": ov, "feedback": fb, "improve": imp, "engine": "demo"}

# ---------------- Voice (optional real TTS) ----------------
def tts(text):
    key = os.getenv("GEMINI_API_KEY")
    if not key: return None
    d = _post("https://generativelanguage.googleapis.com/v1beta/interactions",
              {"x-goog-api-key": key},
              {"model": os.getenv("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts"),
               "input": [{"type": "user_input", "content": [{"type": "text", "text": text,
                          "annotations": [{"type": "speech_metadata", "style": "Warm, friendly voiceover."}]}]}],
               "response_format": {"type": "audio"},
               "generation_config": {"speech_config": [{"voice": os.getenv("GEMINI_TTS_VOICE", "Kore")}]},
               "store": False})
    audio = (d.get("output_audio") or {}).get("data")
    if not audio:
        for step in d.get("steps", []):
            for item in step.get("content", []):
                if item.get("type") == "audio" and item.get("data"):
                    audio = item["data"]
                    break
            if audio: break
    if not audio: raise ValueError("Gemini returned no audio data.")
    return base64.b64decode(audio)

def generate_image(prompt, aspect_ratio="4:5"):
    image_prompt = prompt
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            model = os.getenv("GEMINI_IMAGE_PROMPT_MODEL", "gemini-2.5-flash")
            d = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                      {"x-goog-api-key": gemini_key},
                      {"contents": [{"role": "user", "parts": [{"text":
                          "Rewrite this as one detailed, visually specific image-generation prompt. Preserve the brand and subject, "
                          "describe composition, lighting, materials, and palette, avoid requesting text in the image, and keep it under 120 words.\n\n"
                          + prompt}]}]})
            image_prompt = d["candidates"][0]["content"]["parts"][0]["text"].strip()[:1400] or prompt
        except Exception as e:
            print("Gemini image-prompt enhancement failed; using the original prompt:", e)

    dimensions = {"4:5": (1024, 1280), "9:16": (768, 1365), "1:1": (1024, 1024)}
    width, height = dimensions.get(aspect_ratio, (1024, 1024))
    params = urllib.parse.urlencode({
        "model": os.getenv("POLLINATIONS_IMAGE_MODEL", "black-forest-labs/flux.1-schnell"),
        "width": width,
        "height": height,
        "nologo": "true",
    })
    url = f"https://gen.pollinations.ai/image/{urllib.parse.quote(image_prompt, safe='')}?{params}"
    headers = {"Accept": "image/*", "User-Agent": "BrandForge/1.0"}
    pollinations_key = os.getenv("POLLINATIONS_API_KEY")
    if pollinations_key:
        headers["Authorization"] = "Bearer " + pollinations_key
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            content_type = response.headers.get_content_type().lower()
            image = response.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace").strip()
        raise RuntimeError(f"Pollinations HTTP {e.code}: {detail or e.reason}") from e
    extensions = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    extension = extensions.get(content_type)
    if not extension or not image:
        raise ValueError(f"Pollinations returned {content_type or 'no content type'}, not a supported image.")
    return image, extension
