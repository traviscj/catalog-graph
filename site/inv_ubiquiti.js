// ---------- UniFi inventory plugin: ledger (ports / PoE / console apps) over units placed under a path → planner over switch multisets ----------
const POE = {poe:1,'poe+':2,'poe++':3,poe_bt:4,poe_bt_90w:4}, POEN = ['','af','at (PoE+)','PoE++','bt 90W'], NOM = [0,13,25.5,51,71];
const UPLINKS = ['100MbE','1GbE','2.5GbE','10GbE','10G SFP+','WiFi','none'];
const PWRS = ['ac','dc','usb_c','poe','poe+','poe++','poe_bt','battery'];
let invFull = false;

const speedG = u => { if(!u) return 0; const s=String(u); if(/^(wifi|lte|superlink|rs-|none|usb)/i.test(s)) return 0; if(/^GbE/i.test(s)) return 1;
  const m=s.match(/^(\d+(?:\.\d+)?)\s*(G|M)/i); return m ? +m[1]*(m[2].toUpperCase()==='M'?.001:1) : 0; };
const tierOf = g => g<=1 ? 0 : g<=2.5 ? 1 : 2;
const portsT = o => { o=o||{}; return [(o.rj45_1g||0)+(o.sfp_1g||0), o.rj45_2_5g||0, (o.rj45_10g||0)+(o.sfp_plus_10g||0)+(o.sfp28_25g||0)+(o.qsfp28_100g||0)]; };

// per-unit resource vector
function unitRes(p, it){
  const f=p.f||{}, g=p.generic, pj=primary(p);
  const role = g?.f.upstream ? 'upstream' : (g?.f.root || pj.some(j=>j.startsWith('gateway'))) ? 'root' : 'node';
  const sp = speedG(f.uplink), tier = tierOf(sp);
  const isNet = g ? /^(router|sw_)/.test(g.id) : pj.some(j=>/^(switch|gateway)/.test(j));
  const sup = isNet ? portsT(f.ports) : [0,0,0];
  let own = null;
  if(isNet && sup.some(x=>x)){ own = Math.min(tier, 2); while(own>0 && !sup[own]) own--; }
  const pw = it?.pwr || (f.power_in||[])[0];
  const pd = POE[pw]||0;
  const ps = POE[f.poe_class] || Math.max(0, ...(f.poe_out_types||[]).map(t=>POE[t]||0));
  const psn = ps ? (+f.poe_out_ports||0) : 0;
  return {role, tier, sp, wired: sp>0 && !f.inline && role!=='upstream', sup, own,
    pd, pdw: pd ? (+f.power_draw_w || NOM[pd]) : 0, ps, psn, psw: psn ? (f.poe_budget_w ?? psn*NOM[ps]) : 0,
    app: f.requires_console && INVCFG.apps.includes(f.managed_by) ? f.managed_by : null,
    hosts: f.hosts_apps||[], maxdev: (f.hosts_apps||[]).length ? (+f.max_devices||0) : 0};
}
function L0(){ return {S:[0,0,0],D:[0,0,0],PS:[0,0,0,0,0],PD:[0,0,0,0,0],W:0,WD:0,need:{},host:{},maxdev:0,managed:0,n:0}; }
function acc(L, r, n){
  L.n+=n; if(r.role==='upstream') return L;
  for(let t=0;t<3;t++) L.S[t]+=r.sup[t]*n;
  if(r.own!=null) L.D[r.own]+=n;                    // a switch/gateway spends one of its own ports on uplink/WAN
  if(r.wired && r.role!=='root') L.D[r.tier]+=n;    // …and every non-root wired thing takes a port on its parent
  if(r.pd){ L.PD[r.pd]+=n; L.WD+=r.pdw*n; }
  if(r.ps){ L.PS[r.ps]+=r.psn*n; L.W+=r.psw*n; }
  if(r.app){ L.need[r.app]=(L.need[r.app]||0)+n; L.managed+=n; }
  r.hosts.forEach(a=>L.host[a]=(L.host[a]||0)+n);
  L.maxdev+=r.maxdev*n;
  return L;
}
const Lclone = L => ({...L, S:[...L.S], D:[...L.D], PS:[...L.PS], PD:[...L.PD], need:{...L.need}, host:{...L.host}});
const cum = (a,i) => a.slice(i).reduce((x,y)=>x+y,0);
// nested shortfalls: a tier-t device can use any port ≥ t at full speed; a class-k PoE device needs a port ≥ k
function shorts(L){
  let speed=0, poe=0;
  for(let t=2;t>=1;t--) speed=Math.max(speed, cum(L.D,t)-cum(L.S,t));
  for(let k=4;k>=1;k--) poe=Math.max(poe, cum(L.PD,k)-cum(L.PS,k));
  return {ports: cum(L.D,0)-cum(L.S,0), speed, poe, w: L.WD-L.W,
    apps: Object.keys(L.need).filter(a=>!L.host[a]), cap: L.maxdev && L.managed>L.maxdev ? L.managed-L.maxdev : 0};
}
const withR = us => us.map(u=>({...u, r:unitRes(u.p,u.it)}));
const ledgerOf = us => us.reduce((L,u)=>acc(L,u.r,u.n), L0());

// planner: cheapest switch multisets (optionally replacing one existing switch) that clear port/PoE/budget shortfalls
let CANDS = null;
function cands(){
  if(CANDS) return CANDS;
  const all = ids.filter(id=>{const p=P[id];return p.price && !p.legacy && p.in_store!==false && primary(p).some(j=>j.startsWith('switch_')) && !primary(p).includes('switch_industrial')})
    .map(id=>{const r=unitRes(P[id]); const L=acc(L0(),r,1);
      const v=[...[2,1,0].map(t=>cum(L.S,t)-cum(L.D,t)), ...[4,3,2,1].map(k=>cum(L.PS,k)-cum(L.PD,k)), L.W-L.WD];
      return {id, price:P[id].price, r, v}});
  // drop anything another switch beats on every axis for no more money (feasibility is monotone in v, so this is lossless)
  CANDS = all.filter(a=>!all.some(b=>b!==a && b.price<=a.price && b.v.every((x,i)=>x>=a.v[i]) &&
    (b.price<a.price || b.v.some((x,i)=>x>a.v[i]) || b.id<a.id)));
  return CANDS;
}
function plan(units, Lt){
  const C=cands(), out=[], ok=s=>s.ports<=0&&s.poe<=0&&s.w<=0&&(!invFull||s.speed<=0);
  const tryCombo=(Lb, combo, removed)=>{
    const L=Lclone(Lb); combo.forEach(c=>acc(L,c.r,1)); const s=shorts(L); if(!ok(s)) return;
    out.push({combo, removed, price: combo.reduce((a,c)=>a+c.price,0), s, L});
  };
  const combos=(k)=>{const r=[];const rec=(st,cur)=>{if(cur.length) r.push(cur);if(cur.length===k)return;for(let i=st;i<C.length;i++)rec(i,[...cur,C[i]])};rec(0,[]);return r;};
  const c3=combos(C.length>45?2:3), c2=c3.filter(c=>c.length<=2);
  c3.forEach(c=>tryCombo(Lt,c,null));
  const mine=units.filter(u=>u.r.sup.some(x=>x) && u.r.role==='node');
  const seen=new Set();
  mine.forEach(u=>{const key=u.p.id; if(seen.has(key))return; seen.add(key);
    const Lb=acc(Lclone(Lt),u.r,-1); c2.forEach(c=>tryCombo(Lb,c,u.p));});
  out.sort((a,b)=>a.price-b.price || a.combo.length-b.combo.length);
  // keep only minimal options: drop any whose purchase contains a cheaper feasible purchase, and any "retire X" whose
  // purchase already works without retiring anything (retiring then buys nothing but fewer boxes)
  const key=c=>c.map(x=>x.id).sort().join('+'), addOnly=new Set(out.filter(o=>!o.removed).map(o=>key(o.combo)));
  const sub=(a,b)=>{const m={};b.forEach(x=>m[x.id]=(m[x.id]||0)+1);return a.every(x=>m[x.id]-->0);};
  const keep=[], sig=new Set();
  for(const o of out){const k=key(o.combo)+'|'+(o.removed?.id||'');
    if(sig.has(k) || (o.removed&&addOnly.has(key(o.combo))) || keep.some(q=>q.removed===o.removed&&q.combo.length<o.combo.length&&sub(q.combo,o.combo))) continue;
    sig.add(k);keep.push(o);if(keep.length>=12)break;}
  // pareto on (price, devices added): nothing else is both cheaper-or-equal and fewer-or-equal boxes
  keep.forEach(o=>o.pareto=!keep.some(q=>q!==o&&q.price<=o.price&&(q.combo.length-(q.removed?1:0))<=(o.combo.length-(o.removed?1:0))&&(q.price<o.price||q.combo.length<o.combo.length)));
  return keep;
}

function ledgerRows(Ln, Lt){
  const nf=(v,hard)=>hard==='app'?'':v<0?`<span class="${hard?'bad':'warn'}">${v}</span>`:`<span class="dim">${v}</span>`;
  const row=(label,sN,dN,sT,dT,hard)=>`<tr><td>${label}</td><td class="n">${sN}</td><td class="n">${dN}</td><td class="n">${nf(sN-dN,hard)}</td><td class="n">${sT}</td><td class="n">${dT}</td><td class="n">${nf(sT-dT,hard)}</td></tr>`;
  const r=[];
  r.push(row('switch ports (all)',cum(Ln.S,0),cum(Ln.D,0),cum(Lt.S,0),cum(Lt.D,0),true));
  r.push(row('  ≥2.5G full-speed',cum(Ln.S,1),cum(Ln.D,1),cum(Lt.S,1),cum(Lt.D,1),false));
  r.push(row('  ≥10G full-speed',Ln.S[2],Ln.D[2],Lt.S[2],Lt.D[2],false));
  for(let k=1;k<=4;k++) if(cum(Ln.PS,k)+cum(Ln.PD,k)+cum(Lt.PS,k)+cum(Lt.PD,k)) r.push(row(`PoE ports ≥${POEN[k]}`,cum(Ln.PS,k),cum(Ln.PD,k),cum(Lt.PS,k),cum(Lt.PD,k),true));
  r.push(row('PoE budget W (aggregate)',Math.round(Ln.W),Math.round(Ln.WD),Math.round(Lt.W),Math.round(Lt.WD),true));
  const apps=[...new Set([...Object.keys(Ln.need),...Object.keys(Lt.need)])];
  apps.forEach(a=>r.push(row(`console: ${a} (hosts / devices)`,Ln.host[a]||0,Ln.need[a]||0,Lt.host[a]||0,Lt.need[a]||0,'app')));
  if(Ln.maxdev||Lt.maxdev) r.push(row('console device cap',Ln.maxdev,Ln.managed,Lt.maxdev,Lt.managed,true));
  return r.join('');
}

function specEditorU(sid, it, p){
  const t=p.generic, f=p.f, a=`data-site="${sid}" data-k="${it.k}"`;
  const num=(field,v,w=3)=>`<input type="number" min="0" ${a} data-spec="${field}" value="${v??''}" style="width:${w+2}ch">`;
  const sel=(field,opts,v)=>`<select ${a} data-spec="${field}">${opts.map(x=>`<option ${x===v?'selected':''}>${x}</option>`).join('')}</select>`;
  const parts=[`name <input ${a} data-field="name" value="${esc(it.name||'')}" size="22">`, `$ <input type="number" ${a} data-field="price" value="${it.price??''}" style="width:7ch">`];
  if(t.edit.includes('ports')) parts.push('ports '+['rj45_1g','rj45_2_5g','rj45_10g','sfp_1g','sfp_plus_10g'].map(k=>`${CFG.portAbbr[k]} ${num('ports.'+k,f.ports[k])}`).join(' '));
  if(t.edit.includes('uplink')) parts.push('uplink '+sel('uplink',UPLINKS,f.uplink||'none'));
  if(t.edit.includes('power_in')) parts.push('power '+sel('power_in',PWRS,(f.power_in||[])[0]));
  if(t.edit.includes('power_draw_w')) parts.push('draw W '+num('power_draw_w',f.power_draw_w,4));
  if(t.edit.includes('poe_out_ports')) parts.push('PoE ports '+num('poe_out_ports',f.poe_out_ports));
  if(t.edit.includes('poe_class')) parts.push('class '+sel('poe_class',['poe','poe+','poe++','poe_bt'],f.poe_class||(f.poe_out_types||[]).slice(-1)[0]));
  if(t.edit.includes('poe_budget_w')) parts.push('budget W '+num('poe_budget_w',f.poe_budget_w,4));
  return `<tr class="spec"><td></td><td colspan="${8+INVDOM.itemCols.length}" class="small">${parts.join(' · ')}</td></tr>`;
}

function optTable(opts){
  if(!opts.length) return '<p class="dim small">no combination of ≤3 current switches (or 1 replacement + ≤2) clears it — split the target or check PoE class</p>';
  return `<div class="wrap"><table class="small"><thead><tr><th></th><th>buy</th><th>retire</th><th class="n">$</th><th class="n">Δboxes</th><th class="n">free all/≥2.5/≥10</th><th class="n">free PoE</th><th class="n">PoE W left</th><th class="n">slow links</th><th class="n">max draw W</th></tr></thead><tbody>${
    opts.map(o=>{const cnt={};o.combo.forEach(c=>cnt[c.id]=(cnt[c.id]||0)+1);const L=o.L,fr=[0,1,2].map(t=>cum(L.S,t)-cum(L.D,t));
      const draw=o.combo.reduce((a,c)=>a+(+P[c.id].f.power_draw_w||0),0);
      return `<tr><td>${o.pareto?'<b class="up">★</b>':''}</td><td>${Object.entries(cnt).map(([id,n])=>`${n>1?n+'× ':''}${plink(id)}`).join(' + ')}</td><td>${o.removed?`<span class="down">${esc(o.removed.name)}</span>`:''}</td>
      <td class="n">${m0(o.price)}</td><td class="n">${o.combo.length-(o.removed?1:0)}</td><td class="n">${fr.join('/')}</td><td class="n">${cum(L.PS,0)-cum(L.PD,0)}</td><td class="n">${Math.round(L.W-L.WD)}</td><td class="n">${o.s.speed>0?`<span class="warn">${o.s.speed}</span>`:'<span class="dim">0</span>'}</td><td class="n dim">${draw||''}</td></tr>`}).join('')}</tbody></table></div>`;
}

const WIFI = {'WiFi 5':5,'WiFi 6':6,'WiFi 6E':6.5,'WiFi 7':7};
const INVDOM = {
  ledgerNote: '(units placed under this path; red = short)',
  itemCols: [
    {h:'power', td:(it,p,sid,a)=>{const pw=p.f.power_in||[];return !p.generic&&pw.length>1?`<select ${a} data-field="pwr">${pw.map(x=>`<option ${x===(it.pwr||pw[0])?'selected':''}>${x}</option>`).join('')}</select>`:esc(pw[0]||'')}},
    {h:'uplink', td:(it,p,sid,a)=>{const f=p.f;return speedG(f.uplink)||it.f?.uplink?`<select ${a} data-spec="uplink" title="actual link speed">${[...new Set([f.uplink,...UPLINKS])].map(x=>`<option ${x===f.uplink?'selected':''}>${esc(x)}</option>`).join('')}</select>`:esc(f.uplink||'')}},
    {h:'ports', td:(it,p)=>{const r=unitRes(p,it);return RENDER.ports(r.sup.some(x=>x)?p.f.ports:null)}},
    {h:'PoE out', n:1, td:(it,p)=>{const r=unitRes(p,it);return r.psn?`${r.psn}×${POEN[r.ps].split(' ')[0]} ${Math.round(r.psw)}W`:''}},
    {h:'PoE in', n:1, td:(it,p)=>{const r=unitRes(p,it);return r.pd?`${POEN[r.pd].split(' ')[0]} ${r.pdw}W`:''}},
  ],
  siteHeads: ['ports used/have','PoE used/have','PoE W','apps w/o host','legacy','issues'],
  siteCells(ctx){
    const un=withR(ctx.placedNow), Lt=ledgerOf(withR(ctx.placedTgt)), st=shorts(Lt);
    const leg=un.filter(u=>u.p.legacy).length, nIss=(st.ports>0)+(st.poe>0)+(st.w>0)+st.apps.length+(st.cap>0);
    return [`${cum(Lt.D,0)}/${cum(Lt.S,0)}`, `${cum(Lt.PD,0)}/${cum(Lt.PS,0)}`, `${Math.round(Lt.WD)}/${Math.round(Lt.W)}`,
      st.apps.map(a=>`<span class="bad">${a}</span>`).join(' '), leg?`<span class="warn">${leg}</span>`:'', nIss?`<span class="bad">${nIss}</span>`:'<span class="up">ok</span>'];
  },
  locHeads: ['ports','PoE W','gear'],
  locCells(av, x){
    const pl=withR(av.filter(u=>within(u.place,x))), L=ledgerOf(pl), st=shorts(L);
    return [cum(L.S,0)?`<span class="${st.ports>0?'bad':''}">${cum(L.D,0)}/${cum(L.S,0)}</span>`:'', L.W||L.WD?`<span class="${st.w>0?'bad':''}">${Math.round(L.WD)}/${Math.round(L.W)}</span>`:'',
      `<span class="dim">${[...new Set(av.filter(u=>!u.p.generic||u.p.generic.job!=='need').map(u=>primary(u.p)[0]))].filter(Boolean).slice(0,5).join(' ')}</span>`];
  },
  ledger(ctx){
    const Ln=ledgerOf(withR(ctx.placedNow)), Lt=ledgerOf(withR(ctx.placedTgt));
    return `<div class="wrap"><table class="small"><thead><tr><th>resource</th><th class="n">now have</th><th class="n">need</th><th class="n">free</th><th class="n">target have</th><th class="n">need</th><th class="n">free</th></tr></thead><tbody>${ledgerRows(Ln,Lt)}</tbody></table></div>
    <p class="dim small">Tree model over items placed under this path: each switch/gateway spends 1 own port on uplink/WAN; every non-root wired device takes 1 parent port. PoE checked by class and as one pooled budget. SFP vs RJ45 media ignored.</p>`;
  },
  issues(ctx){
    const unT=withR(ctx.placedTgt), Lt=ledgerOf(unT), st=shorts(Lt), iss=[];
    if(st.ports>0||st.poe>0||st.w>0||(invFull&&st.speed>0)){
      const what=[st.ports>0&&`${st.ports} ports`, st.poe>0&&`${st.poe} PoE ports (class-matched)`, st.w>0&&`${Math.round(st.w)} W PoE budget`, invFull&&st.speed>0&&`${st.speed} multi-gig ports`].filter(Boolean).join(' · ');
      iss.push(`<h2 class="bad">short: ${what}</h2><p class="small dim">options = cheapest ≤3 in-store switches, or retire one of yours + ≤2 new; ★ = Pareto on ($, boxes). Each new switch costs a port upstream plus its own uplink. <label><input type="checkbox" data-act="full" ${invFull?'checked':''}> require full-speed multi-gig</label></p>${optTable(plan(unT,Lt))}`);
    } else if(st.speed>0) iss.push(`<p class="warn small">${st.speed} device(s) faster than the ports left for them (they'll link at lower speed). <label><input type="checkbox" data-act="full"> plan for full speed</label></p>`);
    st.apps.forEach(app=>{const c=ids.filter(id=>!P[id].legacy&&P[id].price&&(P[id].f.hosts_apps||[]).includes(app)).sort((x,y)=>P[x].price-P[y].price).slice(0,6);
      iss.push(`<h2 class="bad">no console hosts ${esc(app)} (${Lt.need[app]} device${Lt.need[app]>1?'s':''} need it)</h2><ul class="t">${c.map(id=>`<li>${plink(id)} <span class="dim">${money(P[id].price)} · hosts ${esc((P[id].f.hosts_apps||[]).join(' '))}${P[id].f.max_devices?` · ≤${P[id].f.max_devices} devices`:''}</span></li>`).join('')}${app==='network'?'<li>self-hosted Network (OS Server / VM) <span class="dim">$0 · add generic "Self-hosted UniFi Network"</span></li>':''}</ul>`);});
    if(st.cap>0) iss.push(`<h2 class="bad">console device cap exceeded by ${st.cap}</h2>`);
    // required partners (from the pairs pass) that nothing usable here fills; console + PoE reqs are covered by the ledger
    const have=new Set(ctx.availTgt.flatMap(u=>[u.p.id,...primary(u.p)]));
    const rq={};unT.forEach(u=>(PAIRS[u.p.id]||[]).filter(x=>x.req&&P[x.id]).forEach(x=>{const mj=primary(P[x.id])[0];
      if(!mj||/^(console_host|nvr_recording|switch_|gateway_)/.test(mj)||have.has(x.id)||have.has(mj))return;(rq[mj]=rq[mj]||{mj,who:new Set(),x}).who.add(u.p.name);}));
    Object.values(rq).forEach(r=>{const alt=ids.filter(id=>!P[id].legacy&&P[id].price&&primary(P[id]).includes(r.mj)).sort((x,y)=>P[x].price-P[y].price).slice(0,5);
      iss.push(`<h2 class="warn">${esc([...r.who].join(', '))} need${r.who.size>1?'':'s'} a ${esc(r.mj)}</h2><div class="small dim">${esc(r.x.why)}</div><ul class="t small">${alt.map(id=>`<li>${plink(id)} <span class="dim">${money(P[id].price)}</span></li>`).join('')}</ul>`)});
    return iss;
  },
  // capability atoms for "what would it add": jobs it does, apps it hosts, radio/port/PoE tiers it brings
  caps(p){
    const f=p.f||{}, out=[], push=(a,l,g,w)=>out.push({a,l,g,w});
    if(p.generic?.job==='need') return out;
    primary(p).filter(j=>!['accessory','client','upstream'].includes(j)).forEach(j=>push('job:'+j,j,'job',2));
    (f.hosts_apps||[]).forEach(a=>push('host:'+a,'hosts '+a,'console',2));
    const w=WIFI[f.wifi_std]; if(w) [5,6,6.5,7].filter(x=>x<=w).forEach(x=>push('wifi:'+x,'WiFi '+(x===6.5?'6E':x),'wifi',.7));
    if((f.bands||[]).includes('6')) push('band:6','6 GHz','wifi',.7);
    if(f.outdoor_rated) push('outdoor','outdoor','env',.5);
    const t=portsT(f.ports); if(t[1]) push('port:2.5','2.5G ports','ports',.7); if(t[2]) push('port:10','10G ports','ports',1);
    const ps=Math.max(0,...(f.poe_out_types||[]).map(x=>POE[x]||0)); for(let k=1;k<=ps;k++) push('poe:'+k,'PoE out '+POEN[k].split(' ')[0],'poe',.5);
    (f.redundancy||[]).forEach(r=>push('red:'+r,String(r),'resilience',.5));
    return out;
  },
  addBase(X, U){ const L=ledgerOf(withR(X==='*'?U:U.filter(u=>within(u.place,X)))); return {L, s:shorts(L)}; },
  addHeads: ['Δ free ports','Δ PoE W','fixes'],
  addCells(p, U, X, base){
    const r=unitRes(p), L=acc(Lclone(base.L),r,1), s=shorts(L), b=base.s;
    const dp=(cum(L.S,0)-cum(L.D,0))-(cum(base.L.S,0)-cum(base.L.D,0)), dw=Math.round((L.W-L.WD)-(base.L.W-base.L.WD));
    const fx=[b.ports>0&&s.ports<b.ports&&'ports', b.poe>0&&s.poe<b.poe&&'PoE', b.w>0&&s.w<b.w&&'PoE W', b.apps.filter(a=>!s.apps.includes(a)).join(' ')].filter(Boolean);
    return [dp?{h:`<span class="${dp>0?'up':'down'}">${dp>0?'+':''}${dp}</span>`}:'', dw?{h:`<span class="${dw>0?'up':'down'}">${dw>0?'+':''}${dw}</span>`}:'', fx.length?{h:`<b class="up">${fx.join(' ')}</b>`,live:true}:''];
  },
  specEditor: specEditorU,
  specSet(it, sp, e){
    if(sp==='power_in'){ it.f.power_in=[e.value]; return true; }
    if(sp==='poe_class'){ it.f.poe_class=e.value; it.f.poe_out_types=[e.value]; return true; }
    return false;
  },
  click(ev, b){ if(b.dataset.act==='full'){ invFull=b.checked; route(); return true; } return false; },
};
