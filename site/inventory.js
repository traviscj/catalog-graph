// ---------- inventory core: sites → items (placement path + usage scope) → domain ledger + "what would X add" ----------
// Included by build_site.py only when the domain declares SITE.inventory; the domain plugin (site/inv_<domain>.js) is
// appended after this file and defines INVDOM. Depends on globals from the main script.
//
// Locations are paths: an item sits at `<site>/<loc>` (loc may nest: "basement/rack"). Its usage scope defaults to that
// placement but can be widened or moved ("house" for a modem in the office that serves the house, "*" for a handheld
// you carry everywhere). A query at path X sees every item whose scope contains X (inherited) or lies under X (aggregate).
const INVCFG = CFG.inventory;
const TPL = Object.fromEntries(INVCFG.templates.map(t=>[t.id,t]));
const STATUSES = ['active','planned','goal','remove','spare','retired'];
// now = active + remove (still installed); target = active + planned + goal (remove dropped). spare/retired never count.
const IN_NOW = new Set(['active','remove']), IN_TGT = new Set(['active','planned','goal']);
let INV = {}, invMode = 'local', invErr = '', invCol = null;
let addNow = false, addLeg = false, addAll = false;
const specOpen = new Set();

const isObj = v => v && typeof v==='object' && !Array.isArray(v);
const deepMerge = (a,b) => { if(!b) return a; const o={...a}; for(const [k,v] of Object.entries(b)) o[k] = isObj(v)&&isObj(a?.[k]) ? deepMerge(a[k],v) : v; return o; };
function itemP(it){
  if(it.ref.startsWith('g:')){
    const t=TPL[it.ref.slice(2)]; if(!t) return null;
    return {id:it.ref, name:it.name||t.name, price:it.price??null, f:deepMerge(t.f,it.f), jobs:[{job:t.job,role:'primary'}], generic:t};
  }
  const p=P[it.ref]; if(!p) return null;
  return it.f ? {...p, f:deepMerge(p.f,it.f)} : p;
}

// ---------- paths ----------
const normPath = s => String(s||'').split('/').map(x=>x.trim()).filter(Boolean).join('/');
const placeOf = (sid,it) => normPath(sid+'/'+(it.loc||''));
// scope: "*" = everywhere; first segment naming a site = absolute; otherwise relative to the item's own site
function scopeOf(sid,it){
  const s=String(it.scope||'').trim(); if(!s) return placeOf(sid,it); if(s==='*') return '*';
  const n=normPath(s); return INV[n.split('/')[0]] ? n : normPath(sid+'/'+n);
}
const within = (x,s) => s==='*' || x===s || x.startsWith(s+'/');
function allUnits(set){
  const out=[];
  Object.entries(INV).forEach(([sid,s])=>(s.items||[]).forEach(it=>{ if(!set.has(it.status||'active')) return; const p=itemP(it); if(!p) return;
    out.push({sid, it, p, n:+it.qty||1, place:placeOf(sid,it), scope:scopeOf(sid,it)}); }));
  return out;
}
const availAt = (X,set) => { const U=allUnits(set); return X==='*' ? U : U.filter(u=>within(X,u.scope)||within(u.scope,X)); };
const placedIn = (X,set) => allUnits(set).filter(u=>X==='*'||within(u.place,X));
function sitePaths(sid){
  const ps=new Set([sid]);
  allUnits(new Set(STATUSES)).forEach(u=>[u.place,u.scope].forEach(x=>{ if(x==='*'||x.split('/')[0]!==sid) return;
    const seg=x.split('/'); for(let i=1;i<=seg.length;i++) ps.add(seg.slice(0,i).join('/')); }));
  return [...ps].sort();
}
const allPaths = () => ['*',...Object.keys(INV).sort().flatMap(sitePaths)];
const pathLink = x => x==='*' ? '<a href="#add.*">*</a>' : x.split('/').map((seg,i,a)=>`<a href="#s.${esc(a.slice(0,i+1).join('/'))}">${esc(seg)}</a>`).join('<span class="dim">/</span>');
const ctxAt = X => ({X, sid:X==='*'?null:X.split('/')[0], placedNow:placedIn(X,IN_NOW), placedTgt:placedIn(X,IN_TGT), availNow:availAt(X,IN_NOW), availTgt:availAt(X,IN_TGT)});

// ---------- capabilities: union over what's available at a path; marginal = product caps − that union ----------
function capsOf(units){
  const m=new Map();
  units.forEach(u=>INVDOM.caps(u.p,u.it).forEach(c=>{ if(!m.has(c.a)) m.set(c.a,{...c,by:[]}); m.get(c.a).by.push(u); }));
  return m;
}
function marginal(p, have){
  const cs=INVDOM.caps(p), nw=cs.filter(c=>!have.has(c.a));
  return {cs, nw, pts:nw.reduce((a,c)=>a+(c.w??1),0)};
}
const capChips = cs => cs.map(c=>`<span class="tag cap-${esc(c.g)}" title="${esc(c.g)}">${esc(c.l)}</span>`).join(' ');

// ---------- persistence: db (per-viewer private subtree) with localStorage fallback ----------
const dirty=new Set(), saveChain={}; let saveT=null;
function invTouch(sid){ dirty.add(sid); clearTimeout(saveT); saveT=setTimeout(invFlush,400); route(); }
function invFlush(){
  if(invMode==='db'){
    for(const sid of dirty){ const doc=INV[sid]?JSON.parse(JSON.stringify(INV[sid])):null, ref=invCol.doc(sid);
      saveChain[sid]=(saveChain[sid]||Promise.resolve()).then(()=>doc?ref.set(doc):ref.delete()).catch(e=>{invErr=e.code||String(e);route();}); }
  } else { try{ localStorage.setItem('inv',JSON.stringify(INV)); }catch(e){} }
  dirty.clear();
}
function invRerender(){
  const h=location.hash.slice(1)||'all'; const a=document.activeElement;
  if(a && a.closest && a.closest('#app') && /INPUT|SELECT/.test(a.tagName)) return;
  if(/^(inv|add|s\.|p\.|all)/.test(h)) route();
}
async function invInit(){
  try{ const s=localStorage.getItem('inv'); if(s) INV=JSON.parse(s); }catch(e){}
  const cl=window.claude; if(!cl?.use) return;
  try{
    const [db,user]=await Promise.all([cl.use('db'),cl.use('user')]);
    const uid=user && await user.id();
    if(!db||!uid){ invMode='local'; invRerender(); return; }
    invCol=db.collection(`data/users/${uid}/inv/sites`); invMode='db'; INV={};
    invCol.onSnapshot(snap=>{
      snap.docChanges().forEach(ch=>{ if(ch.doc.metadata.hasPendingWrites) return;
        if(ch.type==='removed') delete INV[ch.doc.id]; else INV[ch.doc.id]=JSON.parse(JSON.stringify(ch.doc.data())); });
      invRerender();
    }, e=>{ invMode='local'; invErr=e.code; invRerender(); });
  }catch(e){ invMode='local'; invErr=e.code||String(e); }
}

// ---------- shared view bits ----------
const owned = id => { const r=[]; Object.entries(INV).forEach(([sid,s])=>(s.items||[]).forEach(it=>{if(it.ref===id)r.push({sid,s,it})})); return r; };
const ownCount = id => owned(id).filter(o=>IN_NOW.has(o.it.status||'active')).reduce((a,o)=>a+(+o.it.qty||1),0);
const stCls = s => ({active:'',planned:'side',goal:'up',remove:'bad',spare:'dim',retired:'dim'})[s||'active'];
const m0 = v => money(v).replace('.00','');
const storeBanner = () => invMode==='db' ? `<span class="dim small">synced · private to you</span>` :
  `<span class="warn small">browser-only storage${invErr?` (${esc(invErr)})`:''} — open on claude.ai signed in to sync</span>`;
function ownLine(id){
  const o=owned(id), U=allUnits(IN_TGT);
  const m=U.length&&INVDOM.caps(P[id]).length ? marginal(P[id], capsOf(U)) : null;
  return (o.length ? `<div class="small">owned: ${o.map(x=>`${pathLink(placeOf(x.sid,x.it))} ×${x.it.qty||1} <span class="${stCls(x.it.status)}">${x.it.status||'active'}</span>`).join(' · ')}</div>` : '')+
    (m ? `<div class="small">adds to your inventory: ${m.nw.length?capChips(m.nw):'<span class="dim">nothing new</span>'} <a class="dim" href="#add.*">by location →</a></div>` : '');
}
// legacy units → their current-gen replacement edge
function legacyIssue(units){
  const leg=units.filter(u=>u.p.legacy&&P[u.p.id]); if(!leg.length) return null;
  return `<h2 class="warn">legacy here</h2><ul class="t small">${leg.map(u=>{const e=E.filter(e=>e.src===u.p.id&&e.deltas.some(d=>d.k==='legacy'&&d.d>0));
    return `<li>${plink(u.p.id)} ×${u.n} → ${e.map(e=>`${plink(e.dst)} <span class="dim">${money(P[e.dst].price)}</span>`).join(' · ')||'<span class="dim">no mapped replacement</span>'}</li>`}).join('')}</ul>`;
}

function viewInv(){
  const sites=Object.entries(INV).sort((a,b)=>(a[1].name||a[0]).localeCompare(b[1].name||b[0]));
  const rows=sites.map(([sid,s])=>{const ctx=ctxAt(sid), un=ctx.placedNow;
    const val=un.reduce((a,u)=>a+(u.p.price||0)*u.n,0), goal=(s.items||[]).filter(i=>['planned','goal'].includes(i.status)).reduce((a,i)=>{const p=itemP(i);return a+((p&&p.price)||0)*(+i.qty||1)},0);
    return `<tr><td><a href="#s.${sid}">${esc(s.name||sid)}</a></td><td class="dim">${esc(s.desc||'')}</td><td class="n">${sitePaths(sid).length-1}</td><td class="n">${(s.items||[]).length}</td><td class="n">${un.reduce((a,u)=>a+u.n,0)}</td>
      <td class="n">${m0(val)}</td><td class="n side">${goal?'+'+m0(goal):''}</td>${INVDOM.siteCells(ctx).map(c=>`<td class="n">${c}</td>`).join('')}<td><a class="dim" href="#add.${sid}">adds →</a></td></tr>`}).join('');
  // ownership matrix: what lives where
  const refs={}; sites.forEach(([sid,s])=>(s.items||[]).forEach(it=>{const p=itemP(it);if(!p)return;const k=it.ref.startsWith('g:')?it.ref+'|'+(it.name||''):it.ref;
    (refs[k]=refs[k]||{p,it,by:{}}).by[sid]=(refs[k].by[sid]||[]).concat(it)}));
  const mat=Object.values(refs).sort((a,b)=>(primary(a.p)[0]||'').localeCompare(primary(b.p)[0]||'')||a.p.name.localeCompare(b.p.name));
  const nh=7+INVDOM.siteHeads.length+1;
  return `<h1>Inventory <span class="dim small">${sites.length} sites</span> ${storeBanner()}</h1>
  <div class="wrap"><table><thead><tr><th>site</th><th>desc</th><th class="n">locs</th><th class="n">items</th><th class="n">units</th><th class="n">value $</th><th class="n">planned $</th>${INVDOM.siteHeads.map(h=>`<th class="n">${h}</th>`).join('')}<th></th></tr></thead><tbody>${rows||`<tr><td colspan="${nh}" class="dim">no sites yet</td></tr>`}</tbody></table></div>
  <p><input id="newsite" placeholder="new site name (e.g. office)" size="28"> <button data-act="addsite">add site</button> <span class="dim small">ledger columns are target state (active + planned + goal − remove) · <a href="#add.*">what would each product add? →</a></span></p>
  ${mat.length?`<h2>what lives where</h2><div class="wrap"><table><thead><tr><th>product</th><th>job</th><th class="n">$ ea</th>${sites.map(([sid,s])=>`<th class="n">${esc(s.name||sid)}</th>`).join('')}</tr></thead><tbody>${
    mat.map(m=>`<tr><td>${m.p.generic?`<span class="dim">≈</span> ${esc(m.p.name)}`:plink(m.p.id)}${m.p.legacy?' <span class="bad small">legacy</span>':''}</td><td class="dim">${primary(m.p)[0]||''}</td><td class="n dim">${m0(m.p.price)}</td>${
      sites.map(([sid])=>`<td class="n">${(m.by[sid]||[]).map(it=>`<span class="${stCls(it.status)}" title="${esc(it.status||'active')} ${esc(it.loc||'')}">${it.qty||1}</span>`).join('+')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`:''}`;
}

// generic spec editor driven by template descriptors {k, t:num|bool|sel|set|text, opts?, l?}; domains may override
function specEditorGeneric(sid, it, p){
  const t=p.generic, a=`data-site="${sid}" data-k="${it.k}"`;
  const parts=[`name <input ${a} data-field="name" value="${esc(it.name||'')}" size="22">`, `$ <input type="number" ${a} data-field="price" value="${it.price??''}" style="width:7ch">`];
  (t.edit||[]).forEach(d=>{const v=get(p,'f.'+d.k), l=d.l||d.k.split('.').pop().replace(/_/g,' ');
    if(d.t==='num') parts.push(`${esc(l)} <input type="number" min="0" ${a} data-spec="${d.k}" value="${v??''}" style="width:${(d.w||4)+2}ch">`);
    else if(d.t==='text') parts.push(`${esc(l)} <input ${a} data-spec="${d.k}" value="${esc(v??'')}" size="${d.w||14}">`);
    else if(d.t==='bool') parts.push(`<label><input type="checkbox" ${a} data-spec="${d.k}" ${v?'checked':''}> ${esc(l)}</label>`);
    else if(d.t==='sel') parts.push(`${esc(l)} <select ${a} data-spec="${d.k}">${d.opts.map(x=>`<option ${x===v?'selected':''}>${esc(x)}</option>`).join('')}</select>`);
    else if(d.t==='set') parts.push(`${esc(l)} ${d.opts.map(x=>`<label class="nowrap"><input type="checkbox" ${a} data-arr="${d.k}" data-val="${esc(x)}" ${(v||[]).includes(x)?'checked':''}>${esc(x)}</label>`).join(' ')}`);
  });
  return `<tr class="spec"><td></td><td colspan="${8+INVDOM.itemCols.length}" class="small">${parts.join(' · ')}</td></tr>`;
}

function locTree(sid, X){
  const paths=sitePaths(sid), heads=INVDOM.locHeads||[];
  return `<div class="wrap"><table class="small"><thead><tr><th>location</th><th class="n">here</th><th class="n">under</th><th class="n">serving</th>${heads.map(h=>`<th>${h}</th>`).join('')}</tr></thead><tbody>${
    paths.map(x=>{const d=x.split('/').length-1, pl=placedIn(x,IN_TGT), av=availAt(x,IN_TGT);
      const here=pl.filter(u=>u.place===x).reduce((a,u)=>a+u.n,0), under=pl.reduce((a,u)=>a+u.n,0), from=av.filter(u=>!within(u.place,x)).reduce((a,u)=>a+u.n,0);
      return `<tr class="${x===X?'sel':''}"><td>${'&nbsp;&nbsp;'.repeat(d)}<a href="#s.${esc(x)}">${esc(x.split('/').pop())}</a></td><td class="n">${here||''}</td><td class="n dim">${under||''}</td><td class="n ${from?'side':''}">${from||''}</td>${
        (INVDOM.locCells?INVDOM.locCells(av,x):[]).map(c=>`<td>${c}</td>`).join('')}</tr>`}).join('')}</tbody></table></div>
  <p class="dim small">here = placed at exactly this path · under = placed anywhere below · serving = placed elsewhere but scoped to cover this path (e.g. a modem in the office serving the whole house, an HT scoped *). Columns right of that are what's usable at the path (inherited + below).</p>`;
}

function viewSite(path){
  const X=normPath(path), sid=X.split('/')[0], s=INV[sid];
  if(!s) return `<p>unknown site ${esc(sid)} · <a href="#inv">inventory</a></p>`;
  const ctx=ctxAt(X), a=it=>`data-site="${sid}" data-k="${it.k}"`;
  const items=(s.items||[]).filter(it=>within(placeOf(sid,it),X)).map(it=>({it,p:itemP(it)}));
  const order=p=>p?(primary(p)[0]||'zz'):'zz';
  items.sort((x,y)=>(x.it.loc||'').localeCompare(y.it.loc||'')||order(x.p).localeCompare(order(y.p))||(x.p?.name||'').localeCompare(y.p?.name||''));
  const nc=8+INVDOM.itemCols.length;
  const rows=items.map(({it,p})=>{
    if(!p) return `<tr><td colspan="${nc}" class="bad">unknown ref ${esc(it.ref)} <button ${a(it)} data-act="del">×</button></td></tr>`;
    const n=+it.qty||1, sc=scopeOf(sid,it), pl=placeOf(sid,it);
    return `<tr class="${['spare','retired'].includes(it.status)?'dim':''}"><td><select ${a(it)} data-field="status" class="${stCls(it.status)}">${STATUSES.map(x=>`<option ${x===(it.status||'active')?'selected':''}>${x}</option>`).join('')}</select></td>
      <td>${p.generic?`<span class="dim">≈</span> ${esc(p.name)} <a href="#" class="dim small" data-act="spec" ${a(it)}>spec</a>`:plink(p.id)}${p.legacy?' <span class="bad small">legacy</span>':''}</td>
      <td class="dim">${primary(p)[0]||''}</td>
      <td><input type="number" min="1" ${a(it)} data-field="qty" value="${n}" style="width:5ch"></td>
      <td><input ${a(it)} data-field="loc" value="${esc(it.loc||'')}" size="14" placeholder="(site root)" list="locs-${sid}"></td>
      <td><input ${a(it)} data-field="scope" value="${esc(it.scope||'')}" size="10" placeholder="= placement" list="scopes" title="usage scope: where this is usable. blank = where it sits; a site or site/path; * = everywhere"${sc!==pl?' class="side"':''}></td>
      <td class="n dim">${m0(p.price)}</td>
      ${INVDOM.itemCols.map(c=>`<td class="${c.n?'n':''}">${c.td(it,p,sid,a(it))}</td>`).join('')}
      <td><input ${a(it)} data-field="note" value="${esc(it.note||'')}" size="22" placeholder="note"> <button ${a(it)} data-act="del" title="delete">×</button></td></tr>`+
      (p.generic&&specOpen.has(it.k)?(INVDOM.specEditor||specEditorGeneric)(sid,it,p):'');
  }).join('');
  const from=ctx.availTgt.filter(u=>!within(u.place,X));
  const iss=[...INVDOM.issues(ctx), legacyIssue(ctx.availNow.filter(u=>within(u.place,X)))].filter(Boolean);
  const crumbs=X.split('/').map((seg,i,arr)=>i===arr.length-1?`<b>${esc(i?seg:(s.name||sid))}</b>`:`<a href="#s.${esc(arr.slice(0,i+1).join('/'))}">${esc(i?seg:(s.name||sid))}</a>`).join(' / ');
  const locOpts=sitePaths(sid).map(x=>x.split('/').slice(1).join('/')).filter(Boolean);
  return refsDatalist()+`<datalist id="locs-${sid}">${locOpts.map(x=>`<option value="${esc(x)}">`).join('')}</datalist><datalist id="scopes">${allPaths().map(x=>`<option value="${esc(x)}">`).join('')}</datalist>
  <h1>${crumbs} <span class="dim small">${esc(s.desc||'')}</span> ${storeBanner()}</h1>
  <div class="small"><a href="#inv">← all sites</a> · <a href="#add.${esc(X)}">what would each product add here? →</a> · desc <input data-site="${sid}" data-sitefield="desc" value="${esc(s.desc||'')}" size="30"> · <button data-act="delsite" data-site="${sid}">${pendingDel===sid?'click again to delete site':'delete site'}</button></div>
  <div class="cols"><div><h2>locations</h2>${locTree(sid,X)}</div>
  <div><h2>ledger @ ${esc(X)} ${INVDOM.ledgerNote?`<span class="dim">${INVDOM.ledgerNote}</span>`:''}</h2>${INVDOM.ledger(ctx)}</div></div>
  <h2>items placed ${X===sid?'at this site':'under '+esc(X)} <span class="dim">· now = active+remove · target = active+planned+goal · loc nests with "/" · serves: blank = where it sits</span></h2>
  <div class="wrap"><table><thead><tr><th>status</th><th>product</th><th>job</th><th>qty</th><th>location</th><th>serves</th><th class="n">$ ea</th>${INVDOM.itemCols.map(c=>`<th class="${c.n?'n':''}">${c.h}</th>`).join('')}<th>note</th></tr></thead><tbody>${rows||`<tr><td colspan="${nc}" class="dim">nothing placed here</td></tr>`}</tbody></table></div>
  <p class="small"><input id="additem" list="refs" placeholder="add: product name or ≈ generic…" size="40"> qty <input id="addqty" type="number" min="1" value="1" style="width:5ch"> <select id="addst">${STATUSES.map(x=>`<option>${x}</option>`).join('')}</select> <button data-act="additem" data-site="${sid}" data-loc="${esc(X.split('/').slice(1).join('/'))}">add${X!==sid?' at '+esc(X.split('/').slice(1).join('/')):''}</button></p>
  ${from.length?`<h2 class="side">serving ${esc(X)} from elsewhere</h2><ul class="t small">${from.map(u=>`<li>${u.p.generic?esc(u.p.name):plink(u.p.id)} ×${u.n} <span class="dim">placed</span> ${pathLink(u.place)} <span class="dim">serves</span> ${u.scope==='*'?'*':pathLink(u.scope)}</li>`).join('')}</ul>`:''}
  <h2>${iss.length?'what to do':'<span class="up">no shortfalls in target</span>'}</h2>${iss.join('')}`;
}

// what would each catalog product add at path X: capability atoms not already available there, plus domain columns
let addSort='pts';
function viewAdd(path){
  const X=path==='*'||!path?'*':normPath(path), set=addNow?IN_NOW:IN_TGT;
  const U=availAt(X,set), have=capsOf(U), q=$('#q').value.trim();
  const base=INVDOM.addBase?INVDOM.addBase(X,U):null;
  const list=ids.filter(id=>(typeof inKind!=='function'||inKind(id))&&(addLeg||!P[id].legacy)&&matches(P[id],q)&&(!jobFilter||allJobs(P[id]).includes(jobFilter))).map(id=>{
    const p=P[id], m=marginal(p,have), cs=new Set(m.cs.map(c=>c.a));
    // owned units this would make redundant: everything they offer, it offers too
    const sup=U.filter(u=>u.p.id!==id&&INVDOM.caps(u.p,u.it).length&&INVDOM.caps(u.p,u.it).every(c=>cs.has(c.a)));
    return {id,p,...m,sup,x:INVDOM.addCells?INVDOM.addCells(p,U,X,base):[]};
  }).filter(r=>addAll||r.pts>0||r.x.some(c=>c&&c.live));
  const key={pts:r=>-r.pts, price:r=>r.p.price||1e9, ppp:r=>r.pts?(r.p.price||1e9)/r.pts:1e12};
  list.sort((a,b)=>key[addSort](a)-key[addSort](b)||(a.p.price||0)-(b.p.price||0));
  const groups={}; [...have.values()].forEach(c=>(groups[c.g]=groups[c.g]||[]).push(c));
  const xh=INVDOM.addHeads||[];
  return `<h1>What would it add @ <select id="addscope">${allPaths().map(x=>`<option ${x===X?'selected':''}>${esc(x)}</option>`).join('')}</select> <span class="dim small">${U.length} units usable here</span></h1>
  <div class="small">vs <label><input type="radio" name="an" data-act="addnow" value="0" ${addNow?'':'checked'}>target (active+planned+goal)</label> <label><input type="radio" name="an" data-act="addnow" value="1" ${addNow?'checked':''}>now</label>
   · <label><input type="checkbox" data-act="addleg" ${addLeg?'checked':''}> include legacy</label> · <label><input type="checkbox" data-act="addall" ${addAll?'checked':''}> show products that add nothing</label>
   · sort <a href="#" data-act="addsort" data-k="pts">${addSort==='pts'?'<b>gain</b>':'gain'}</a> <a href="#" data-act="addsort" data-k="ppp">${addSort==='ppp'?'<b>$/pt</b>':'$/pt'}</a> <a href="#" data-act="addsort" data-k="price">${addSort==='price'?'<b>$</b>':'$'}</a>
   · ${X==='*'?'':pathLink(X)+' · '}filter box + job chips apply</div>
  ${typeof kindTabs==='function'?kindTabs():''}<div class="chips">${jobCounts().map(([j,n])=>`<span class="chip ${jobFilter===j?'on':''}" data-job="${j}">${j} <i>${n}</i></span>`).join('')}</div>
  <h2>already usable @ ${esc(X)}</h2><div class="small">${Object.entries(groups).map(([g,cs])=>`<span class="dim">${esc(g)}:</span> ${cs.map(c=>`<span title="${esc(c.by.map(u=>u.p.name).join(', '))}">${esc(c.l)}<sup class="dim">${c.by.length>1?c.by.length:''}</sup></span>`).join(' ')}`).join(' &nbsp;│&nbsp; ')||'<span class="dim">nothing yet</span>'}</div>
  ${base&&INVDOM.addBaseHtml?INVDOM.addBaseHtml(base):''}
  <h2>candidates <span class="dim">(${list.length}) · gain = Σ weights of new capabilities · supersedes = owned gear whose every capability this also has</span></h2>
  <div class="wrap"><table><thead><tr><th>product</th><th class="n">$</th><th>job</th><th class="n">gain</th><th class="n">$/pt</th>${xh.map(h=>`<th>${h}</th>`).join('')}<th>new here</th><th>supersedes</th></tr></thead><tbody>${
    list.slice(0,300).map(r=>`<tr><td>${plink(r.id)}${r.p.legacy?' <span class="bad small">legacy</span>':''}${ownCount(r.id)?` <b class="up small">own ${ownCount(r.id)}</b>`:''}</td><td class="n">${m0(r.p.price)}</td><td class="dim">${primary(r.p)[0]||''}</td>
      <td class="n">${r.pts?`<b>${r.pts.toFixed(1)}</b>`:'<span class="dim">0</span>'}</td><td class="n dim">${r.pts&&r.p.price?'$'+Math.round(r.p.price/r.pts):''}</td>${r.x.map(c=>`<td class="small">${c?c.h??c:''}</td>`).join('')}
      <td class="small need">${capChips(r.nw)}</td><td class="small">${r.sup.map(u=>`<span class="down">${esc(u.p.name)}</span>`).join(' ')}</td></tr>`).join('')}</tbody></table></div>`;
}

let pendingDel=null;
const refIndex = () => { const m={}; ids.forEach(id=>m[`${P[id].name} (${money(P[id].price)||'n/a'})`]=id); INVCFG.templates.forEach(t=>m[`≈ ${t.name}`]='g:'+t.id); return m; };
let REFS=null;
function refsDatalist(){ REFS=REFS||refIndex(); return `<datalist id="refs">${Object.keys(REFS).map(k=>`<option value="${esc(k)}">`).join('')}</datalist>`; }
const newK = () => Math.random().toString(36).slice(2,9);
const slug = s => s.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,40) || 'site';
function setPath(o, path, v){ const ks=path.split('.'); let x=o; ks.slice(0,-1).forEach(k=>x=x[k]=x[k]||{}); x[ks.at(-1)]=v; }

function invClick(ev){
  const b=ev.target.closest('[data-act]'); if(!b) return false;
  const act=b.dataset.act, sid=b.dataset.site, k=b.dataset.k;
  if(INVDOM.click && INVDOM.click(ev,b)) return true;
  if(act==='spec'){ ev.preventDefault(); specOpen.has(k)?specOpen.delete(k):specOpen.add(k); route(); return true; }
  if(act==='addnow'){ addNow=b.value==='1'; route(); return true; }
  if(act==='addleg'){ addLeg=b.checked; route(); return true; }
  if(act==='addall'){ addAll=b.checked; route(); return true; }
  if(act==='addsort'){ ev.preventDefault(); addSort=b.dataset.k; route(); return true; }
  if(act==='addsite'){ const n=$('#newsite').value.trim(); if(!n) return true; let id=slug(n); while(INV[id]) id+='-2'; INV[id]={name:n,desc:'',items:[]}; invTouch(id); location.hash='s.'+id; return true; }
  if(act==='delsite'){ if(pendingDel!==sid){ pendingDel=sid; route(); return true; } pendingDel=null; delete INV[sid]; invTouch(sid); location.hash='inv'; return true; }
  if(act==='del'){ INV[sid].items=INV[sid].items.filter(i=>i.k!==k); invTouch(sid); return true; }
  if(act==='additem'){ REFS=REFS||refIndex(); const v=$('#additem').value.trim(); const ref=REFS[v] || ids.find(id=>P[id].name.toLowerCase()===v.toLowerCase()||id===v.toLowerCase());
    if(!ref){ $('#additem').style.borderColor='var(--bad)'; return true; }
    const it={k:newK(), ref, qty:+$('#addqty').value||1, status:$('#addst').value}; if(b.dataset.loc) it.loc=b.dataset.loc;
    INV[sid].items.push(it); invTouch(sid); return true; }
  return false;
}
function invChange(ev){
  const e=ev.target;
  if(e.id==='addscope'){ location.hash='add.'+e.value; return true; }
  const sid=e.dataset.site; if(!sid||!INV[sid]) return false;
  if(e.dataset.sitefield){ INV[sid][e.dataset.sitefield]=e.value; invTouch(sid); return true; }
  const it=(INV[sid].items||[]).find(i=>i.k===e.dataset.k); if(!it) return false;
  const numv = e.type==='number' ? (e.value===''?null:+e.value) : e.type==='checkbox' ? e.checked : e.value;
  if(e.dataset.field){ const v=e.dataset.field==='loc'?normPath(numv):numv; if(v===null||v==='') delete it[e.dataset.field]; else it[e.dataset.field]=v; }
  else if(e.dataset.arr){ const cur=get(itemP(it),'f.'+e.dataset.arr)||[], v=e.dataset.val; it.f=it.f||{};
    const ord=(TPL[it.ref.slice(2)]?.edit||[]).find(d=>d.k===e.dataset.arr)?.opts||[];
    setPath(it.f, e.dataset.arr, (e.checked?[...new Set([...cur,v])]:cur.filter(x=>x!==v)).sort((x,y)=>ord.indexOf(x)-ord.indexOf(y))); }
  else if(e.dataset.spec){ it.f=it.f||{}; if(!(INVDOM.specSet && INVDOM.specSet(it,e.dataset.spec,e,numv))) setPath(it.f, e.dataset.spec, numv); }
  invTouch(sid); return true;
}
