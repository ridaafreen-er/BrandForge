"use client";
import { useEffect, useRef, useState } from "react";
import Image from "next/image";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const PLATS = ["instagram", "reels", "linkedin", "x", "blog", "audio"];
const LABEL: any = { instagram: "Instagram", reels: "Reels", linkedin: "LinkedIn", x: "X", blog: "Blog", audio: "Audio ad" };
const DEMO = { brand_name: "Brew & Bloom", product: "Cold brew coffee", audience: "College students", industry: "Cafe / Beverage", goal: "Launch our cold brew", campaign: "Cold Brew Launch",
  tone: "Playful, youthful, energetic", description: "A local cafe serving fresh, affordable coffee to busy students.", key_message: "Affordable cold brew for busy students.", avoid: "cheap", colors: "", website: "", platforms: PLATS };

async function api(path: string, method = "GET", body?: any) {
  const r = await fetch(API + path, { method, credentials: "include", headers: body ? { "Content-Type": "application/json" } : undefined, body: body ? JSON.stringify(body) : undefined });
  if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch {} throw new Error(m); }
  return r;
}
const J = async (p: string, m = "GET", b?: any) => (await api(p, m, b)).json();
const fileToData = (f: File) => new Promise<string>((res) => { const r = new FileReader(); r.onload = () => res(String(r.result)); r.readAsDataURL(f); });

function Score({ s }: { s: number }) {
  const c = s >= 8 ? "text-ok border-ok/40" : "text-bad border-bad/40";
  return <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${c}`}>{s >= 8 ? "✓ Brand fit" : "Needs improvement"} {s.toFixed(1)}</span>;
}

export default function App() {
  const [view, setView] = useState("landing");
  const [form, setForm] = useState<any>({ ...DEMO, brand_name: "", product: "", audience: "", industry: "", goal: "", campaign: "", tone: "", description: "", key_message: "", avoid: "", platforms: PLATS });
  const [brand, setBrand] = useState<any>(null);
  const [cam, setCam] = useState<any>(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const [sys, setSys] = useState<any>(null);
  const [edit, setEdit] = useState<any>(null);
  const [demo, setDemo] = useState(false);
  const [history, setHistory] = useState<any[]>([]);
  const [accounts, setAccounts] = useState<any[]>([]);
  const [user, setUser] = useState<any>(null);
  const [authReady, setAuthReady] = useState(false);
  const poll = useRef<any>(null);

  useEffect(() => { J("/api/status").then(setSys).catch(() => setErr(`Can't reach the API at ${API}. Start the backend (see README).`)); }, []);
  useEffect(() => { J("/api/auth/me").then(x=>setUser(x.user)).catch(()=>{}).finally(()=>setAuthReady(true)); }, []);
  useEffect(() => { if(user) J("/api/accounts").then((x) => setAccounts(x.accounts)).catch(() => {}); }, [user]);
  const run = async (label: string, fn: () => Promise<void>) => { setBusy(label); setErr(""); try { await fn(); } catch (e: any) { setErr(e.message || "Something went wrong"); } setBusy(""); };

  const analyze = (f = form) => run("Analyzing your brand…", async () => { setBrand(await J("/api/brand/analyze", "POST", f)); setView("kit"); });
  const startDemo = () => { setForm(DEMO); setDemo(true); setView("brief"); analyze(DEMO); };
  const approve = () => run("Planning campaign…", async () => { await J(`/api/brand/${brand.id}/approve`, "POST"); setCam(await J("/api/campaign/create", "POST", { brand_id: brand.id })); setView("plan"); });
  const generate = () => run("Starting agents…", async () => {
    await J("/api/campaign/generate", "POST", { brand_id: cam.id }); setView("gen");
    clearInterval(poll.current);
    poll.current = setInterval(async () => { try { const c = await J(`/api/campaign/${cam.id}`); setCam((p: any) => ({ ...p, ...c })); if (c.status === "ready") { clearInterval(poll.current); setTimeout(() => setView("board"), 900); } } catch {} }, 1000);
  });
  const refresh = async () => setCam(await J(`/api/campaign/${cam.id}`));
  const assets: any[] = (cam?.assets || []).slice().sort((a: any, b: any) => PLATS.indexOf(a.platform) - PLATS.indexOf(b.platform));
  const readyN = assets.filter((a) => a.status === "ready").length;

  const regen = (a: any) => run(`Regenerating ${LABEL[a.platform]}…`, async () => { const n = await J(`/api/assets/${a.id}/regenerate`, "POST", {}); await refresh(); if (edit?.id === a.id) setEdit(n); });
  const approveAsset = (a: any) => run("", async () => { await J(`/api/assets/${a.id}/approve`, "POST"); await refresh(); });
  const generateImages = (a: any) => run("Generating carousel images…", async () => {
    const result = await J(`/api/assets/${a.id}/images`, "POST");
    await refresh();
    if (result.errors?.length) setErr(`${result.generated} images generated. ${result.errors.join("; ")}`);
  });
  const report = () => assets.map((a) => `=== ${LABEL[a.platform]} (${a.critic?.overall}/10) ===\n${a.text}`).join("\n\n");
  const doExport = () => run("Building export…", async () => {
    const r = await api(`/api/export/${cam.id}`, "POST"); const u = URL.createObjectURL(await r.blob());
    const l = document.createElement("a"); l.href = u; l.download = `brandforge-${cam.id}.zip`; l.click(); URL.revokeObjectURL(u);
  });
  const openHistory = () => run("Loading history…", async () => { setHistory(await J("/api/publishing/history")); setView("history"); });
  const simulate = (a: any, platform: string) => run("Creating demo preview…", async () => { await J(`/api/publish/${a.id}`, "POST", { platform }); setHistory(await J("/api/publishing/history")); setView("history"); });
  const stages = [{id:"brief", label:"Brand Brief"},{id:"kit",label:"AI Brand Kit"},{id:"plan",label:"Campaign Strategy"},{id:"gen",label:"AI Content Generation"},{id:"board",label:"Content Review"},{id:"accounts",label:"Connect Accounts"},{id:"publish",label:"Publish"},{id:"history",label:"Publishing History"}];
  const canStage = (id: string) => id === "brief" || (id === "kit" && !!brand) || (id === "plan" && !!cam) || (["gen","board","publish","history"].includes(id) && !!cam) || id === "accounts";

  return (
    <main className="min-h-screen font-body">
      {!authReady ? <Section title="BrandForge" sub="Loading your account…" /> : !user ? <AuthPanel onSuccess={setUser} /> : <>
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-ink/90 px-6 py-3 backdrop-blur">
        <button onClick={() => setView("landing")} className="font-display text-xl font-bold tracking-tight">Brand<span className="text-ember">Forge</span></button>
        <div className="flex flex-wrap items-center gap-2 text-xs text-mute">
          {sys && <span>Backend {sys.version} · {sys.engine}</span>}
          <button className="btn-ghost" onClick={() => setView("accounts")}>Connected Accounts</button><button className="btn-ghost" onClick={openHistory}>Publishing History</button>
          <span>{user.email}</span><button className="btn-ghost" onClick={()=>run("Signing out…",async()=>{await J("/api/auth/logout","POST",{});setUser(null);setBrand(null);setCam(null);setView("landing")})}>Sign out</button>
          {view !== "landing" && <button className="btn-ghost" onClick={() => { setView("brief"); setBrand(null); setCam(null); }}>New campaign</button>}
        </div>
      </header>
      {view !== "landing" && <nav aria-label="Campaign workflow" className="mx-auto flex max-w-6xl flex-wrap gap-2 px-6 pt-5">{stages.map((s,i)=><button key={s.id} disabled={!canStage(s.id)} onClick={()=>{if(s.id==="brief"&&brand)setForm(brand.brief);setView(s.id)}} className={`rounded-full border px-3 py-1 text-xs ${view===s.id?"border-ember text-ember":"border-line text-mute"}`}>{i+1}. {s.label}</button>)}</nav>}
      {err && <div role="alert" className="mx-auto mt-4 max-w-4xl rounded-lg border border-bad/40 bg-bad/10 px-4 py-3 text-sm text-bad">{err}</div>}
      {busy && <div className="fixed bottom-5 right-5 z-40 rounded-lg border border-line bg-panel px-4 py-2 text-sm"><span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-ember" />{busy}</div>}

      {view === "landing" && <Landing onStart={() => setView("brief")} onDemo={startDemo} />}

      {view === "brief" && <Section title="Describe your brand once" sub="Required fields marked *. Everything else sharpens the result.">
        {brand && <button className="btn-ghost mb-4" onClick={()=>run("Saving brief…",async()=>{const b=await J(`/api/brand/${brand.id}`,"PUT",form);setBrand(b);setView("kit");})}>Save Changes</button>}
        <form className="grid gap-4 md:grid-cols-2" onSubmit={(e) => { e.preventDefault(); analyze(); }}>
          {([["brand_name", "Brand name *"], ["product", "Product / service *"], ["audience", "Target audience *"], ["industry", "Industry *"], ["goal", "Campaign goal *"], ["campaign", "Campaign name"], ["tone", "Brand tone *"], ["website", "Website URL"], ["key_message", "Key message"], ["avoid", "Things to avoid (comma separated)"], ["colors", "Preferred colors (hex, comma separated)"]] as any[]).map(([k, l]) => (
            <div key={k}><label className="lbl" htmlFor={k}>{l}</label><input id={k} className="inp" required={l.includes("*")} value={form[k] || ""} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></div>))}
          <div className="md:col-span-2"><label className="lbl" htmlFor="d">Short brand description *</label><textarea id="d" required rows={3} className="inp" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
          {["logo", "product_image"].map((k) => <div key={k}><label className="lbl">{k === "logo" ? "Logo" : "Product image"} (optional)</label><input type="file" accept="image/*" className="text-xs text-mute" onChange={async (e) => e.target.files?.[0] && setForm({ ...form, [k]: await fileToData(e.target.files[0]) })} /></div>)}
          <fieldset className="md:col-span-2"><legend className="lbl">Platforms</legend><div className="flex flex-wrap gap-2">{PLATS.map((p) => { const on = form.platforms.includes(p); return <button type="button" key={p} aria-pressed={on} onClick={() => setForm({ ...form, platforms: on ? form.platforms.filter((x: string) => x !== p) : [...form.platforms, p] })} className={`rounded-full border px-3 py-1 text-sm ${on ? "border-ember bg-ember/10 text-ember" : "border-line text-mute"}`}>{LABEL[p]}</button>; })}</div></fieldset>
          <div className="flex gap-3 md:col-span-2"><button className="btn-primary" disabled={!!busy || !form.platforms.length}>Generate brand kit</button><button type="button" className="btn-ghost" onClick={() => setForm(DEMO)}>Fill with demo brand</button></div>
        </form></Section>}

      {view === "kit" && brand && <Section title={`${brand.kit.brandName} brand kit`} sub="Review it. Nothing is generated until you approve.">
        {brand.engine === "demo" && <Note>Demo engine: this kit was assembled from your brief by templates, not by an AI provider.</Note>}
        <div className="grid gap-4 md:grid-cols-3">
          <Card t="Brand voice">{brand.kit.tone}</Card><Card t="Visual style">{brand.kit.visualStyle}</Card><Card t="Audience">{brand.kit.audience}</Card>
          <Card t="Personality">{brand.kit.personality.join(" · ")}</Card><Card t="Writing style">{brand.kit.writingStyle}</Card><Card t="Main CTA">{brand.kit.CTA}</Card>
          <Card t="Content pillars"><ol className="list-decimal pl-4">{brand.kit.contentPillars.map((p: string) => <li key={p}>{p}</li>)}</ol></Card>
          <Card t="Vocabulary / avoid"><p>Use: {brand.kit.vocabulary.join(", ")}</p><p className="mt-1 text-bad">Avoid: {brand.kit.forbiddenWords.join(", ")}</p></Card>
          <Card t="Palette"><div className="flex gap-2">{brand.kit.colors.map((c: string) => <div key={c} title={c} className="h-10 w-10 rounded-md border border-line" style={{ background: c }} />)}</div></Card>
          <div className="md:col-span-3"><Card t="Summary & positioning">{brand.kit.summary}<br /><span className="text-mute">{brand.kit.positioning}</span></Card></div>
        </div>
        <div className="mt-6 flex gap-2"><button className="btn-ghost" onClick={()=>{setForm(brand.brief);setView("brief")}}>Edit Brand Brief</button><button className="btn-primary" onClick={approve} disabled={!!busy}>Approve brand kit</button></div>
      </Section>}

      {view === "plan" && cam && <Section title={cam.plan.name} sub="Campaign plan. Review it, then generate.">
        <PlanEditor cam={cam} onSave={async(plan:any)=>run("Saving strategy…",async()=>{const c=await J(`/api/campaign/${cam.id}`,"PUT",plan);setCam({...c,assets:await J(`/api/campaign/${cam.id}/assets`)});})}/>
        <div className="grid gap-4 md:grid-cols-2">
          <Card t="Objective">{cam.plan.objective}</Card><Card t="Core idea">{cam.plan.idea}</Card><Card t="Hook">{cam.plan.hook}</Card><Card t="Key message / CTA">{cam.plan.keyMessage}<br /><b>{cam.plan.CTA}</b></Card>
          <Card t="Content strategy">{cam.plan.contentStrategy}</Card><Card t="Platform strategy">{cam.plan.platformStrategy}</Card>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">{cam.plan.platforms.map((p: any) => <div key={p.platform} className="rounded-xl border border-line bg-panel p-4"><div className="font-display text-lg">{LABEL[p.platform]}</div><div className="text-sm text-mute">{p.format} · {p.ratio}</div></div>)}</div>
        <button className="btn-primary mt-6" onClick={generate} disabled={!!busy}>Generate campaign</button>
      </Section>}

      {view === "gen" && <Section title="Forging your campaign" sub="Agents run in parallel. Status below is read from the server.">
        <button className="btn-ghost mb-3" onClick={()=>setView("plan")}>Previous: Campaign Strategy</button>
        <ul className="max-w-md space-y-2 text-sm">
          {[["Brand analysis", "done"], ["Campaign planning", "done"], ...assets.map((a) => [LABEL[a.platform], a.status === "ready" ? "done" : a.status === "error" ? "error" : "generating"])].map(([n, s]: any) => (
            <li key={n} className="flex justify-between rounded-lg border border-line bg-panel px-4 py-2"><span>{n}</span><span className={s === "done" ? "text-ok" : s === "error" ? "text-bad" : "text-ember"}>{s === "done" ? "✓" : s === "error" ? "Failed" : "Generating…"}</span></li>))}
        </ul>
        <p className="mt-3 text-xs text-mute">{readyN}/{assets.length} ready</p>
      </Section>}

      {view === "board" && cam && <Section title={`${cam.ctx.brandName} — ${cam.plan.name}`} sub={`${readyN}/${assets.length} READY`}>
        {cam.engine === "demo" && <Note>Demo engine: content below is template-generated, not from an external AI API. Add an API key to the backend for real generation.</Note>}
        {cam.review_reason && <Note>Needs Review: {cam.review_reason}. Review and approve the affected assets again.</Note>}
        <div className="mb-4 flex gap-2"><button className="btn-primary" onClick={doExport}>Export campaign</button><button className="btn-ghost" onClick={() => navigator.clipboard.writeText(report())}>Copy all</button><button className="btn-ghost" onClick={()=>setView("publish")}>Continue to Publish</button></div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{assets.map((a) => <AssetCard key={a.id} a={a} cam={cam} onEdit={() => setEdit(a)} onRegen={() => regen(a)} onApprove={() => approveAsset(a)} onGenerateImages={() => generateImages(a)} imageEnabled={Boolean(sys?.images)} />)}</div>
      </Section>}

      {view === "accounts" && <Section title="Connected Accounts" sub="No live accounts are connected. Credentials and connection states are never shown as connected unless confirmed by the provider."><Note>DEMO MODE — Authorization is disabled until BrandForge has user authentication and per-user account ownership. Provider credentials are checked server-side and never returned.</Note><div className="grid gap-4 md:grid-cols-3">{["instagram","linkedin","wordpress"].map(p=>{const a=accounts.find((x:any)=>x.platform===p);return <div key={p} className="rounded-xl border border-line bg-panel p-5"><div className="font-display text-xl">{LABEL[p] || "WordPress"}</div><p className="my-3 text-sm text-mute">Status: Not connected · Authorization: Not granted</p><p className="mb-3 text-xs text-mute">OAuth app: {a?.oauth_configured?"Credentials configured":"Credentials not configured"}</p><button className="btn-ghost" disabled={!a?.authorization_available}>Connect Account</button></div>})}</div></Section>}

      {view === "publish" && cam && <Section title="Publish" sub="Choose an approved asset and preview a clearly labeled demo result."><Note>DEMO MODE — This simulates workflow history only. It does not connect accounts, publish content, or create a live post URL.</Note><div className="grid gap-4 md:grid-cols-2">{assets.map(a=><div key={a.id} className="rounded-xl border border-line bg-panel p-4"><h2 className="font-display text-lg">{LABEL[a.platform]}</h2><p className="my-2 line-clamp-4 whitespace-pre-wrap text-sm">{a.text}</p><p className="mb-3 text-xs text-mute">{a.approved?"Approved":"Needs approval"}</p>{["instagram","linkedin","wordpress"].map(p=><button key={p} className="btn-ghost mr-2 mt-2" disabled={!a.approved} onClick={()=>simulate(a,p)}>Preview {p} · DEMO</button>)}</div>)}</div></Section>}

      {view === "history" && <Section title="Publishing History" sub="Demo previews are labeled and contain no fabricated live URLs."><div className="overflow-x-auto rounded-xl border border-line"><table className="w-full text-left text-sm"><thead className="bg-panel text-mute"><tr>{["Content","Platform","Account","Status","Date","Action"].map(x=><th key={x} className="p-3">{x}</th>)}</tr></thead><tbody>{history.map(h=><tr key={h.id} className="border-t border-line"><td className="p-3">{h.content?.slice(0,70)}</td><td className="p-3">{h.platform}</td><td className="p-3">{h.account}</td><td className="p-3">{h.status}</td><td className="p-3">{new Date(h.created+"Z").toLocaleString()}</td><td className="p-3">{h.url ? <a href={h.url}>View</a> : "Preview only"}</td></tr>)}{!history.length&&<tr><td className="p-4 text-mute" colSpan={6}>No publishing activity yet.</td></tr>}</tbody></table></div></Section>}

      {edit && <Editor a={assets.find((x) => x.id === edit.id) || edit} onClose={() => setEdit(null)} onChange={async () => { await refresh(); }} regen={regen} setBusy={setBusy} setErr={setErr} />}
      </>}
    </main>
  );
}

function AuthPanel({onSuccess}:any){const [mode,setMode]=useState("login");const [email,setEmail]=useState("");const [password,setPassword]=useState("");const [error,setError]=useState("");const [busy,setBusy]=useState(false);const submit=async(e:any)=>{e.preventDefault();setBusy(true);setError("");try{const r=await api(`/api/auth/${mode}`,"POST",{email,password});onSuccess((await r.json()).user)}catch(ex:any){setError(ex.message)}finally{setBusy(false)}};return <Section title={mode==="login"?"Welcome back":"Create your BrandForge account"} sub="Your campaigns and connected accounts are private to your account."><form onSubmit={submit} className="max-w-md space-y-4 rounded-xl border border-line bg-panel p-5"><label className="lbl block">Email<input required type="email" autoComplete="email" className="inp mt-1" value={email} onChange={e=>setEmail(e.target.value)}/></label><label className="lbl block">Password<input required type="password" minLength={mode==="register"?12:1} autoComplete={mode==="login"?"current-password":"new-password"} className="inp mt-1" value={password} onChange={e=>setPassword(e.target.value)}/>{mode==="register"&&<span className="mt-1 block text-xs text-mute">Use at least 12 characters.</span>}</label>{error&&<p role="alert" className="text-sm text-bad">{error}</p>}<button className="btn-primary" disabled={busy}>{busy?"Please wait…":mode==="login"?"Sign in":"Create account"}</button><p className="text-sm text-mute">{mode==="login"?"New to BrandForge?":"Already have an account?"} <button type="button" className="text-steel underline" onClick={()=>{setMode(mode==="login"?"register":"login");setError("")}}>{mode==="login"?"Register":"Sign in"}</button></p></form></Section>}

function Section({ title, sub, children }: any) { return <div className="mx-auto max-w-6xl px-6 py-10"><h1 className="font-display text-3xl font-bold">{title}</h1><p className="mb-6 mt-1 text-mute">{sub}</p>{children}</div>; }
function PlanEditor({cam,onSave}:any){const [editing,setEditing]=useState(false);const [draft,setDraft]=useState<any>(cam.plan);useEffect(()=>setDraft(cam.plan),[cam]);return <div className="mb-4 flex flex-wrap gap-2">{editing&&["name","objective","idea","keyMessage","CTA","contentStrategy"].map(k=><label key={k} className="min-w-[220px] flex-1 text-xs text-mute">{k}<input className="inp mt-1" value={draft[k]||""} onChange={e=>setDraft({...draft,[k]:e.target.value})}/></label>)}{editing?<><button className="btn-primary self-end" onClick={()=>{onSave(draft);setEditing(false)}}>Save Changes</button><button className="btn-ghost self-end" onClick={()=>{setDraft(cam.plan);setEditing(false)}}>Cancel</button></>:<button className="btn-ghost" onClick={()=>setEditing(true)}>Edit Strategy</button>}</div>}
function Card({ t, children }: any) { return <div className="rounded-xl border border-line bg-panel p-4"><div className="mb-1 text-xs text-mute">{t}</div><div className="text-sm leading-relaxed">{children}</div></div>; }
function Note({ children }: any) { return <div className="mb-4 rounded-lg border border-steel/30 bg-steel/10 px-4 py-2 text-xs text-steel">{children}</div>; }

function Landing({ onStart, onDemo }: any) {
  return <div className="mx-auto max-w-6xl px-6 pb-24 pt-20">
    <h1 className="font-display text-6xl font-bold leading-[1.02] tracking-tight md:text-8xl">One brand idea in.<br /><span className="text-ember">Publish-ready content</span> for every platform out.</h1>
    <p className="mt-6 max-w-xl text-lg text-mute">Describe your brand once. AI agents build the brand kit, plan the campaign, write for each platform, and score every asset against your voice.</p>
    <div className="mt-8 flex gap-3"><button className="btn-primary px-6 py-3" onClick={onStart}>Build your campaign</button><button className="btn-ghost px-6 py-3" onClick={onDemo}>Try live demo</button></div>
    <div className="mt-16 grid items-center gap-4 md:grid-cols-[1fr_auto_1fr_auto_1.4fr]" aria-label="Brief to campaign to six assets">
      <div className="rounded-xl border border-line bg-panel p-5"><div className="text-xs text-mute">Brand brief</div><div className="mt-2 font-display text-xl">Brew & Bloom</div><div className="text-sm text-mute">Cold brew · students · playful</div></div>
      <svg width="48" height="12" aria-hidden><line x1="0" y1="6" x2="48" y2="6" stroke="#FFB020" strokeWidth="2" strokeDasharray="6 6" className="animate-flow" /></svg>
      <div className="rounded-xl border border-ember/40 bg-ember/5 p-5"><div className="text-xs text-ember">AI campaign</div><div className="mt-2 text-sm">Brand kit → plan → agents → critic</div></div>
      <svg width="48" height="12" aria-hidden><line x1="0" y1="6" x2="48" y2="6" stroke="#7AA2F7" strokeWidth="2" strokeDasharray="6 6" className="animate-flow" /></svg>
      <div className="grid grid-cols-3 gap-2">{PLATS.map((p, i) => <div key={p} style={{ animationDelay: `${i * 0.35}s` }} className="animate-pour rounded-lg border border-line bg-panel px-2 py-3 text-center text-xs">{LABEL[p]}</div>)}</div>
    </div></div>;
}

function Visual({ a, cam }: any) {
  const [c1, c2] = [cam.ctx.colors[0], cam.ctx.colors[1]];
  const m = a.meta || {};
  const lines: string[] = a.platform === "instagram" ? (m.slides || []).map((s: any) => s.title) : a.platform === "reels" ? (m.scenes || []).map((s: any) => `${s.time} ${s.visual}`) : [];
  const slides: any[] = m.slides || [];
  if (slides.some((s) => s.image)) return <div className="mb-3 flex gap-2 overflow-x-auto rounded-lg">{slides.filter((s) => s.image).map((s, i) => <figure key={s.image} className="w-36 shrink-0"><Image src={`${API}${s.image}`} alt={s.title || `Carousel slide ${i + 1}`} width={464} height={576} unoptimized className="aspect-[4/5] w-full rounded-lg object-cover" /><figcaption className="mt-1 truncate text-xs text-mute">{s.title}</figcaption></figure>)}</div>;
  return <div className="mb-3 overflow-hidden rounded-lg" style={{ background: `linear-gradient(135deg, ${c1}, ${c2})` }}>
    <div className="flex h-28 items-end justify-between p-3 text-xs text-white/90"><span className="font-display text-base">{cam.ctx.brandName}</span><span>{a.ratio}</span></div>
    {lines.length > 0 && <div className="flex gap-1 overflow-x-auto bg-black/30 p-2 text-[10px] text-white/80">{lines.map((l, i) => <span key={i} className="shrink-0 rounded bg-white/10 px-2 py-1">{l}</span>)}</div>}
  </div>;
}

function AssetCard({ a, cam, onEdit, onRegen, onApprove, onGenerateImages, imageEnabled }: any) {
  const [open, setOpen] = useState(false);
  const sc = a.critic?.overall ?? 0;
  return <div className="flex flex-col rounded-xl border border-line bg-panel p-4">
    <div className="mb-2 flex items-start justify-between"><div><div className="font-display text-lg">{LABEL[a.platform]}</div><div className="text-xs text-mute">{a.ratio} · {a.format} · {a.summary}</div></div>{a.critic && <Score s={sc} />}</div>
    <Visual a={a} cam={cam} />
    {a.platform === "instagram" && <div className="mb-3"><button className="btn-ghost" onClick={onGenerateImages} disabled={!imageEnabled}>Generate carousel images</button>{!imageEnabled && <span className="ml-2 text-xs text-mute">Set GEMINI_API_KEY to enable</span>}</div>}
    <pre className={`whitespace-pre-wrap font-body text-sm text-[#C9D2DF] ${open ? "" : "line-clamp-6"}`}>{a.text}</pre>
    <button className="mt-1 self-start text-xs text-steel" onClick={() => setOpen(!open)}>{open ? "Collapse" : "View"}</button>
    {a.critic && <ul className="mt-3 space-y-1 text-xs text-mute">{a.critic.feedback.slice(0, 3).map((f: string, i: number) => <li key={i}>• {f}</li>)}</ul>}
    <div className="mt-auto flex flex-wrap items-center gap-2 pt-4"><button className="btn-ghost" onClick={onEdit}>Edit</button><button className={sc < 8 ? "btn-primary" : "btn-ghost"} onClick={onRegen}>Regenerate</button><button className="btn-ghost" onClick={onApprove} disabled={a.approved}>{a.approved ? "Approved ✓" : "Approve"}</button></div>
  </div>;
}

function Editor({ a, onClose, onChange, regen, setBusy, setErr }: any) {
  const [txt, setTxt] = useState(a.text);
  const [msg, setMsg] = useState("");
  useEffect(() => { setTxt(a.text); }, [a.text]);
  const call = async (label: string, fn: () => Promise<void>) => { setBusy(label); try { await fn(); } catch (e: any) { setErr(e.message); } setBusy(""); };
  const refine = (mode: string) => call("Rewriting…", async () => { const r = await J(`/api/assets/${a.id}/refine`, "POST", { mode }); setTxt(r.text); setMsg("Proposal loaded below. Save to keep it; your current version is untouched until then."); });
  const save = () => call("Saving…", async () => { await J(`/api/assets/${a.id}`, "PUT", { text: txt }); await onChange(); setMsg("Saved as a new version."); });
  const voice = () => call("Generating voiceover…", async () => { const r = await J(`/api/assets/${a.id}/voiceover`, "POST"); setMsg(r.message || "Voiceover generated. It will be included in the export."); });
  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" role="dialog" aria-modal="true">
    <div className="grid max-h-[90vh] w-full max-w-5xl gap-4 overflow-auto rounded-2xl border border-line bg-ink p-6 md:grid-cols-[1fr_260px]">
      <div>
        <div className="mb-3 flex items-center justify-between"><h2 className="font-display text-2xl">{LABEL[a.platform]}</h2>{a.critic && <Score s={a.critic.overall} />}</div>
        <div className="mb-3 flex flex-wrap gap-2">{[["shorter", "Make shorter"], ["engaging", "More engaging"], ["genz", "More Gen-Z"], ["professional", "More professional"], ["cta", "Stronger CTA"]].map(([m, l]) => <button key={m} className="btn-ghost" onClick={() => refine(m)}>{l}</button>)}</div>
        <textarea className="inp h-80 font-mono text-xs" value={txt} onChange={(e) => setTxt(e.target.value)} aria-label="Asset text" />
        {msg && <p className="mt-2 text-xs text-steel">{msg}</p>}
        {a.critic?.improve && <p className="mt-2 text-xs text-bad">Critic: {a.critic.improve}</p>}
        <div className="mt-4 flex flex-wrap gap-2"><button className="btn-primary" onClick={save} disabled={txt === a.text}>Save as new version</button><button className="btn-ghost" onClick={() => regen(a)}>Regenerate with critic feedback</button>{a.platform === "audio" && <button className="btn-ghost" onClick={voice}>Generate voiceover</button>}<button className="btn-ghost ml-auto" onClick={onClose}>Close</button></div>
      </div>
      <aside><div className="mb-2 text-xs text-mute">Version history</div><ul className="space-y-2">{[...a.versions].map((v: any, i: number) => ({ v, i })).reverse().map(({ v, i }: any) => <li key={i} className="rounded-lg border border-line bg-panel p-2 text-xs"><div>{v.label}</div><button className="mt-1 text-steel" onClick={() => call("Restoring…", async () => { await J(`/api/assets/${a.id}/restore/${i}`, "POST"); await onChange(); })}>Restore</button></li>)}</ul>
        {a.critic && <div className="mt-4 text-xs text-mute"><div className="mb-1">Scores</div>{Object.entries(a.critic.scores).map(([k, v]: any) => <div key={k} className="flex justify-between"><span>{k.replace(/([A-Z])/g, " $1").toLowerCase()}</span><span>{v}</span></div>)}</div>}</aside>
    </div></div>;
}
