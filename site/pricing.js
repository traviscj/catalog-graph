// ---------- price model: hedonic regression of price on functionality (CFG.pricing), fit in-page per scope ----------
// price_i ≈ a + Σ_j β_j x_ij, weighted ridge with box constraints, solved by coordinate descent on standardized columns.
//   model 'rel' : additive $, weights 1/price² (minimizes relative error, so $10k radios don't dominate $150 HTs)
//   model 'abs' : additive $, unweighted
//   model 'log' : log price, β = % premium (shown as $ at the scope's median price)
// λ is picked by leave-one-out CV; per-radio "fair price" is the LOO prediction (fit without that radio).
// Brand columns: per-brand refit shrunk toward the market β (ridge centred on market), brand premium = mean actual/market-LOO.
const PCFG = CFG.pricing;
PCFG.kinds_all = CFG.kinds ? Object.keys(CFG.kinds) : ['radio'];
const PF = PCFG.features;
// default model per kind (picked by CV R²): radios fit additive-$ best, antennas (HT duck … 10 kW beam) need log price
const PDEFAULT = {radio:'rel', antenna:'log'};
let pModel='rel', pModelUser=null, pIcpt=true, pLeg=false, pOB=false, pWant={}, pSort='dpct';
const P_CACHE = {};

function pfeat(p, d){
  const v=d.path?get(p,d.path):null;
  switch(d.t){
    case 'bool': return d.neg ? (v===false?1:0) : (v===true?1:0);
    case 'lin': return +v>0 ? +v : 0;
    case 'truthy': return (v && !(Array.isArray(v)&&!v.length) && v!=='none') ? 1 : 0;
    case 'in': return (v||[]).includes(d.v)?1:0;
    case 'not': return v===true?0:1;
    case 're': return v!=null && new RegExp(d.v).test(String(v)) ? 1 : 0;
    case 'log2': return +v>0 ? Math.max(0, Math.log2(+v/d.v)) : 0;
    case 'and': return d.all.every(x=>pfeat(p,x)) ? 1 : 0;
    case 'job': return primary(p).includes(d.v) ? 1 : 0;
    // owner rating, deviation from d.v shrunk toward 0 by review count (n/(n+5)); unrated = 0
    case 'rating': return p.rating ? (p.rating.avg-d.v)*p.rating.n/(p.rating.n+5) : 0;
  }
  return 0;
}
// scope = facet filter "kind:radio;form:base;brand:Yaesu;brand:Icom" — OR within a facet, AND across; exactly one kind
// (each kind has its own features). The filter box text and the $ range also narrow it unless `bare` (product-page line).
let pMin=null, pMax=null;
function parseScope(s){
  const o={}; String(s||'').split(';').filter(Boolean).forEach(kv=>{const [k,v]=kv.split(/:(.*)/s); if(k&&v!=null)(o[k]=o[k]||new Set()).add(v);});
  if(!o.kind) o.kind=new Set(['radio']); if(o.kind.size>1) o.kind=new Set([[...o.kind][0]]);
  return o;
}
const fmtScope = o => Object.entries(o).flatMap(([k,vs])=>[...vs].map(v=>`${k}:${v}`)).join(';');
const scopeKind = scope => [...parseScope(scope==='all'?'':scope).kind][0];
const scopeLabel = s => fmtScope(parseScope(s)).replace(/;/g,' · ').replace(/:/g,'=');
const facetVal = (p,sc) => sc.job ? primary(p) : [String(get(p,sc.path)??sc.default??'')];
function scopeIds(scope, bare){
  const o=parseScope(scope==='all'?'':scope), q=bare?'':$('#q').value.trim();
  return ids.filter(id=>{const p=P[id];
    if(!(p.price>0) || (!pLeg&&p.legacy) || (!pOB&&/-ob$/.test(id)) || primary(p).includes('accessory')) return false;
    if(!bare && ((pMin!=null&&p.price<pMin) || (pMax!=null&&p.price>pMax))) return false;
    if(q && !matches(p,q)) return false;
    return Object.entries(o).every(([k,vs])=>{const sc=PCFG.scopes.find(x=>x.k===k); return !sc || facetVal(p,sc).some(v=>vs.has(v));});
  });
}
// chips per facet, counts = what you'd get toggling that value on, given every other active facet
function facetChips(scope){
  const o=parseScope(scope);
  return PCFG.scopes.map(sc=>{
    const others={...o}; delete others[sc.k]; if(sc.k!=='kind') others.kind=o.kind;
    // kind row counts every kind (switching kind resets the other facets)
    const base=sc.k==='kind' ? PCFG.kinds_all.flatMap(k=>scopeIds('kind:'+k)) : scopeIds(fmtScope(others)); const c={};
    base.forEach(id=>facetVal(P[id],sc).forEach(v=>{ if(v) c[v]=(c[v]||0)+1; }));
    const vals=Object.entries(c).filter(([v,n])=>n>=1&&!(sc.job&&v==='accessory')).sort((a,b)=>sc.k==='brand'||sc.job?b[1]-a[1]:a[0].localeCompare(b[0]));
    if(vals.length<2 && !o[sc.k]) return '';
    const on=o[sc.k]||new Set();
    return `<div class="chips"><span class="dim small" style="width:42px">${esc(sc.k)}</span>${vals.slice(0,sc.k==='brand'||sc.job?30:99).map(([v,n])=>`<span class="chip ${on.has(v)?'on':''}" data-act="pfacet" data-k="${esc(sc.k)}" data-v="${esc(v)}">${esc(v)} <i>${n}</i></span>`).join('')}${on.size&&sc.k!=='kind'?`<span class="chip" data-act="pfacet" data-k="${esc(sc.k)}" data-v="">× clear</span>`:''}</div>`;
  }).join('');
}

// weighted ridge, coordinate descent. X: rows of k features, y, w (Σw = n), lam, center c (per-coef, raw units), lo (per-coef raw lower bound)
function cdFit(X, y, w, lam, c, lo, warm, icpt=pIcpt||pModel==='log'){
  const n=X.length, k=X[0]?.length||0, sw=w.reduce((a,b)=>a+b,0);
  const m=new Array(k).fill(0), s=new Array(k).fill(1);
  for(let j=0;j<k;j++){ let a=0; if(icpt){ for(let i=0;i<n;i++) a+=w[i]*X[i][j]; m[j]=a/sw; }
    let v=0; for(let i=0;i<n;i++) v+=w[i]*(X[i][j]-m[j])**2; s[j]=Math.sqrt(v/sw)||0; }
  const Z=X.map(r=>r.map((x,j)=>s[j]?(x-m[j])/s[j]:0));
  const a0=icpt?y.reduce((a,yi,i)=>a+w[i]*yi,0)/sw:0;
  const g=new Array(k).fill(0); if(warm) for(let j=0;j<k;j++) g[j]=s[j]?warm[j]*s[j]:0;
  const r=y.map((yi,i)=>yi-a0-Z[i].reduce((a,z,j)=>a+z*g[j],0));
  const zz=new Array(k).fill(0); for(let j=0;j<k;j++) for(let i=0;i<n;i++) zz[j]+=w[i]*Z[i][j]**2;
  for(let it=0; it<400; it++){
    let dmax=0;
    for(let j=0;j<k;j++){ if(!s[j]) continue;
      let num=lam*sw/n*s[j]*c[j]; for(let i=0;i<n;i++) num+=w[i]*Z[i][j]*(r[i]+g[j]*Z[i][j]);
      let nv=num/(zz[j]+lam*sw/n); const lb=lo[j]*s[j]; if(nv<lb) nv=lb;
      const d=nv-g[j]; if(d){ for(let i=0;i<n;i++) r[i]-=d*Z[i][j]; g[j]=nv; dmax=Math.max(dmax,Math.abs(d)); } }
    if(dmax<1e-7*(Math.abs(a0)+1)) break;
  }
  const beta=g.map((x,j)=>s[j]?x/s[j]:0), a=a0-beta.reduce((acc,b,j)=>acc+b*m[j],0);
  return {a, beta, live:s.map(x=>x>0)};
}
const LAMS=[0.001,0.003,0.01,0.03,0.1,0.3,1,3,10,30,100];

function priceFit(scope, bare){
  const L=scopeIds(scope, bare), n=L.length;
  pModel=pModelUser||PDEFAULT[scopeKind(scope)]||'rel';
  const key=[fmtScope(parseScope(scope)),pModel,pIcpt,pLeg,pOB,bare?'':$('#q').value.trim(),bare?'':pMin,bare?'':pMax].join('|'); if(P_CACHE[key]) return P_CACHE[key];
  if(n<5) return P_CACHE[key]={L, n, tooFew:true};
  const kd=scopeKind(scope);
  const Xall=L.map(id=>PF.map(d=>(d.kind||'radio')===kd?pfeat(P[id],d):0));
  // drop columns with no variation in this scope; free-sign features get lo=-∞
  const cols=PF.map((d,j)=>j).filter(j=>new Set(Xall.map(r=>r[j])).size>1);
  const F=cols.map(j=>PF[j]), X=Xall.map(r=>cols.map(j=>r[j]));
  const price=L.map(id=>P[id].price), y=pModel==='log'?price.map(Math.log):price;
  const w0=pModel==='rel'?price.map(p=>1/p**2):price.map(()=>1), ws=w0.reduce((a,b)=>a+b,0), w=w0.map(x=>x*n/ws);
  const lo=F.map(d=>d.sign==='±'?-Infinity:0), c0=F.map(()=>0);
  const pred=(fit,row)=>fit.a+row.reduce((a,x,j)=>a+x*fit.beta[j],0);
  const toP=v=>pModel==='log'?Math.exp(v):v;
  const err=(yh,i)=>pModel==='log'?(yh-y[i])**2:((toP(yh)-price[i])/price[i])**2;
  // cross-validated λ: leave-one-out for small scopes, 10-fold (deterministic folds) above 120 items; warm-started from the full fit
  const K=n<=120?n:10, fold=L.map((_,i)=>K===n?i:(i*7919)%K);
  let best=null;
  for(const lam of LAMS){
    const full=cdFit(X,y,w,lam,c0,lo);
    let e=0; const loo=new Array(n);
    for(let k=0;k<K;k++){ const tr=L.map((_,q)=>q).filter(q=>fold[q]!==k), te=L.map((_,q)=>q).filter(q=>fold[q]===k); if(!te.length) continue;
      const ww=tr.map(q=>w0[q]), s=ww.reduce((a,b)=>a+b,0);
      const f=cdFit(tr.map(q=>X[q]), tr.map(q=>y[q]), ww.map(x=>x*tr.length/s), lam, c0, lo, full.beta);
      te.forEach(i=>{const yh=pred(f,X[i]); loo[i]=toP(yh); e+=err(yh,i);}); }
    if(!best||e<best.e) best={lam, e, full, loo};
  }
  const {lam, full, loo}=best;
  // bootstrap β spread (deterministic LCG so the page is stable across renders)
  let seed=12345; const rnd=()=>(seed=(seed*1103515245+12345)%2147483648)/2147483648;
  const boots=[];
  for(let b=0;b<(n>200?40:120);b++){ const idx=L.map(()=>Math.floor(rnd()*n)); const ww=idx.map(q=>w0[q]),s=ww.reduce((a,c)=>a+c,0);
    boots.push(cdFit(idx.map(q=>X[q]), idx.map(q=>y[q]), ww.map(x=>x*n/s), lam, c0, lo, full.beta).beta); }
  const q=(arr,p)=>{const a=[...arr].sort((x,y)=>x-y);return a[Math.min(a.length-1,Math.max(0,Math.round(p*(a.length-1))))];};
  const med=q(price,.5);
  // $ value of a coefficient: additive → β; log → (e^β−1)·median price (per unit of x)
  const usd=(b)=>pModel==='log'?(Math.exp(b)-1)*med:b;
  const coef=F.map((d,j)=>({d, j, n:X.filter(r=>r[j]>0).length, b:full.beta[j], usd:usd(full.beta[j]), pct:pModel==='log'?Math.exp(full.beta[j])-1:null,
    lo:usd(q(boots.map(x=>x[j]),.1)), hi:usd(q(boots.map(x=>x[j]),.9))}));
  const rows=L.map((id,i)=>({id, price:price[i], fair:loo[i], fit:toP(pred(full,X[i])), x:X[i], d:loo[i]-price[i], dpct:(loo[i]-price[i])/loo[i]}));
  const r2=(()=>{const ly=price.map(Math.log), mu=ly.reduce((a,b)=>a+b,0)/n; const ss=ly.reduce((a,v)=>a+(v-mu)**2,0), se=rows.reduce((a,r)=>a+(Math.log(r.price)-Math.log(Math.max(1,r.fair)))**2,0); return 1-se/ss;})();
  const mape=rows.reduce((a,r)=>a+Math.abs(r.price-r.fair)/r.price,0)/n;
  // brands: refit on each brand's radios with ridge centred on the market β; premium = geometric-mean actual / market LOO
  // brand columns: the 12 brands with most items in scope (≥2 each); the rest still count toward the market fit
  const bc={}; L.forEach(id=>bc[P[id].brand]=(bc[P[id].brand]||0)+1);
  const brands=Object.keys(bc).filter(b=>bc[b]>=2).sort((a,b)=>bc[b]-bc[a]).slice(0,12).sort();
  const B={};
  brands.forEach(br=>{const idx=L.map((id,i)=>i).filter(i=>P[L[i]].brand===br); const nb=idx.length;
    const prem=Math.exp(idx.reduce((a,i)=>a+Math.log(price[i]/Math.max(1,loo[i])),0)/nb)-1;
    let fit=null; if(nb>=3){ const ww=idx.map(i=>w0[i]),s=ww.reduce((a,c)=>a+c,0);
      fit=cdFit(idx.map(i=>X[i]), idx.map(i=>y[i]), ww.map(x=>x*nb/s), Math.max(lam,0.3)*3, full.beta, lo, full.beta); }
    B[br]={n:nb, prem, fit, has:F.map((_,j)=>idx.filter(i=>X[i][j]>0).length)};});
  return P_CACHE[key]={L, n, F, X, rows, coef, lam, med, r2, mape, brands, B, usd, full};
}
const fmtUsd = v => v==null||!isFinite(v) ? '' : (v<0?'−':'')+'$'+Math.abs(Math.round(v)).toLocaleString();
const dealCls = p => p>.15?'up':p>.05?'up dim':p<-.15?'bad':p<-.05?'warn':'dim';
const dealTxt = p => `<span class="${dealCls(p)}">${p>0?'+':''}${Math.round(p*100)}%</span>`;

// product-page one-liner against the whole catalog
function priceLine(id){
  if(!PCFG||!P[id]?.price) return '';
  const m=priceFit('kind:'+(P[id].kind||'radio'), true); if(m.tooFew) return '';
  const r=m.rows.find(r=>r.id===id); if(!r) return '';
  const top=m.coef.map(c=>({c,v:c.usd*r.x[c.j]})).filter(o=>Math.abs(o.v)>=1).sort((a,b)=>Math.abs(b.v)-Math.abs(a.v)).slice(0,5);
  return `<div class="small">price model (all ${P[id].kind||'radio'}s): fair ≈ <b>${fmtUsd(r.fair)}</b> vs ${fmtUsd(r.price)} → ${dealTxt(r.dpct)} ${r.dpct>0?'under':'over'} · ${top.map(o=>`${esc(o.c.d.l)} ${fmtUsd(o.v)}`).join(' · ')} <a href="#price.kind:${P[id].kind||'radio'}" class="dim">model →</a></div>`;
}

function viewPrice(scope){
  scope=fmtScope(parseScope(!scope||scope==='all'?'':scope));
  const m=priceFit(scope);
  const head=`<h1>Price model <span class="dim small">${esc(scopeLabel(scope))}${$('#q').value.trim()?` · text “${esc($('#q').value.trim())}”`:''} · ${m.n} items</span></h1>
  ${facetChips(scope)}<div class="small">$ <input id="pmin" type="number" min="0" placeholder="min" value="${pMin??''}" style="width:8ch"> – <input id="pmax" type="number" min="0" placeholder="max" value="${pMax??''}" style="width:8ch"> · the filter box at top also narrows the scope · <a href="#price.${esc(scope)}" class="dim">link to this scope</a></div>
  <div class="small">model <select id="pmodel">${[['rel','additive $, relative error'],['abs','additive $, absolute error'],['log','multiplicative (log price)']].map(([k,l])=>`<option value="${k}" ${k===pModel?'selected':''}>${l}</option>`).join('')}</select>
   · <label title="off: every dollar is attributed to some function (2m/70cm, HF… carry the base price); on: a fitted baseline absorbs what all radios share"><input type="checkbox" data-act="picpt" ${pIcpt||pModel==='log'?'checked':''} ${pModel==='log'?'disabled':''}> baseline price</label>
   · <label><input type="checkbox" data-act="pleg" ${pLeg?'checked':''}> include legacy</label> · <label><input type="checkbox" data-act="pob" ${pOB?'checked':''}> include open-box</label>
   ${m.tooFew?'':`· n=${m.n} · ${m.F.length} features vary · λ=${m.lam} (${m.n>120?'10-fold':'LOO'} CV) · CV mean |error| ${Math.round(m.mape*100)}% · CV R²(log) ${m.r2.toFixed(2)}`}</div>`;
  if(m.tooFew) return head+`<p class="warn">fewer than 5 priced items in this scope — loosen a filter</p>`;
  const coefs=[...m.coef].sort((a,b)=>b.usd-a.usd), mx=Math.max(...coefs.map(c=>Math.abs(c.usd)),1);
  const bar=v=>`<span style="display:inline-block;height:8px;width:${Math.round(Math.abs(v)/mx*90)}px;background:var(--${v>=0?'acc':'down'});opacity:.7"></span>`;
  // requirement tool
  const want=Object.fromEntries(Object.entries(pWant).filter(([k])=>m.F.some(d=>d.k===k)));
  const req=Object.keys(want).filter(k=>want[k]==='req'), nice=Object.keys(want).filter(k=>want[k]==='nice');
  const ji=k=>m.F.findIndex(d=>d.k===k);
  const meets=(r,ks)=>ks.every(k=>r.x[ji(k)]>0);
  const pick=m.rows.map(r=>{const unwanted=m.coef.filter(c=>c.d.sign!=='±'&&r.x[c.j]>0&&!want[c.d.k]).reduce((a,c)=>a+c.usd*r.x[c.j],0);
    const niceHave=nice.filter(k=>r.x[ji(k)]>0);
    return {...r, ok:meets(r,req), unwanted, niceHave, eff:r.price-unwanted};});
  const okRows=pick.filter(r=>r.ok).sort((a,b)=>a.price-b.price);
  const cheapest=ks=>Math.min(...m.rows.filter(r=>meets(r,ks)).map(r=>r.price));
  const giveUp=req.map(k=>{const c0=cheapest(req), c1=cheapest(req.filter(x=>x!==k)), co=m.coef.find(c=>c.d.k===k);
    const who=m.rows.filter(r=>meets(r,req.filter(x=>x!==k))).sort((a,b)=>a.price-b.price)[0];
    return {k, l:co.d.l, save:c0-c1, model:co.usd, who};}).sort((a,b)=>(b.save||0)-(a.save||0));
  const sortKey={dpct:r=>-r.dpct, price:r=>r.price, d:r=>-r.d, fair:r=>-r.fair};
  const rows=[...m.rows].sort((a,b)=>sortKey[pSort](a)-sortKey[pSort](b));
  const contrib=r=>m.coef.map(c=>({c,v:c.usd*r.x[c.j]})).filter(o=>Math.abs(o.v)>=1).sort((a,b)=>Math.abs(b.v)-Math.abs(a.v)).slice(0,4).map(o=>`${esc(o.c.d.k)} ${fmtUsd(o.v)}`).join(' ');
  // brand × feature
  const bcell=(br,c)=>{const b=m.B[br]; if(!b.has[c.j]) return '<td class="n dim">·</td>'; if(!b.fit) return `<td class="n dim" title="too few radios to refit">${fmtUsd(c.usd)}</td>`;
    const v=m.usd(b.fit.beta[c.j]), d=v-c.usd, rel=Math.abs(c.usd)>20?d/Math.abs(c.usd):0;
    return `<td class="n ${rel>.25?'bad':rel<-.25?'up':''}" title="${b.has[c.j]} radio(s) have it">${fmtUsd(v)}</td>`;};
  return head+`
  <div class="cols">
  <div><h2>what each function costs <span class="dim">(market, this scope; p10–p90 bootstrap)</span></h2><div class="wrap"><table class="small"><thead><tr><th>function</th><th class="n">#have</th><th class="n">$ each</th>${pModel==='log'?'<th class="n">%</th>':''}<th class="n">p10</th><th class="n">p90</th><th></th><th>want</th></tr></thead><tbody>${
    coefs.map(c=>`<tr><td>${esc(c.d.l)}${c.d.sign==='±'?' <span class="dim">±</span>':''}</td><td class="n dim">${c.n}</td><td class="n"><b>${fmtUsd(c.usd)}</b></td>${pModel==='log'?`<td class="n">${Math.round(c.pct*100)}%</td>`:''}<td class="n dim">${fmtUsd(c.lo)}</td><td class="n dim">${fmtUsd(c.hi)}</td><td>${bar(c.usd)}</td>
      <td>${c.d.sign==='±'?'':`<a href="#" data-act="pwant" data-k="${c.d.k}" class="${want[c.d.k]==='req'?'bad':want[c.d.k]==='nice'?'up':'dim'}">${want[c.d.k]||'—'}</a>`}</td></tr>`).join('')}</tbody></table></div>
    <p class="dim small">${pIcpt||pModel==='log'?`Baseline (intercept) ${pModel==='log'?fmtUsd(Math.exp(m.full.a)):fmtUsd(m.full.a)}.`:'No baseline: band functions carry the base price of a radio.'} Wide p10–p90 = the catalog can't separate that function from the ones it travels with (e.g. 6m almost always comes with HF). Power is priced per doubling. ± rows (form, legacy, open-box) are free-signed adjustments, not functions. Click "want" to cycle — / nice / req.</p></div>
  <div><h2>brand vs market <span class="dim">($ per function, refit per brand shrunk toward market · green = cheaper than market, red = pricier)</span></h2><div class="wrap"><table class="small"><thead><tr><th>function</th>${m.brands.map(b=>`<th class="n">${esc(b)}</th>`).join('')}<th class="n">market</th></tr></thead><tbody>
    <tr><td><b>brand premium</b> <span class="dim">vs fair</span></td>${m.brands.map(b=>{const v=m.B[b].prem;return `<td class="n ${dealCls(-v)}"><b>${v>0?'+':''}${Math.round(v*100)}%</b></td>`}).join('')}<td class="n dim">0%</td></tr>
    <tr><td class="dim">radios</td>${m.brands.map(b=>`<td class="n dim">${m.B[b].n}</td>`).join('')}<td class="n dim">${m.n}</td></tr>
    ${coefs.filter(c=>c.d.sign!=='±').map(c=>`<tr><td>${esc(c.d.l)}</td>${m.brands.map(b=>bcell(b,c)).join('')}<td class="n"><b>${fmtUsd(c.usd)}</b></td></tr>`).join('')}</tbody></table></div>
    <p class="dim small">Premium = geometric mean of actual ÷ market-fair (LOO) over the brand's radios: +20% means you pay 20% more than the market rate for the same functions. Per-brand $ need ≥3 radios; "·" = brand has no radio with it here.</p></div>
  </div>
  ${req.length||nice.length?`<h2>your spec: <span class="bad">req ${req.map(k=>esc(m.F[ji(k)].l)).join(', ')||'—'}</span> · <span class="up">nice ${nice.map(k=>esc(m.F[ji(k)].l)).join(', ')||'—'}</span> <a href="#" data-act="pclear" class="dim">clear</a></h2>
  <div class="cols"><div><div class="wrap"><table class="small"><thead><tr><th>radio</th><th class="n">$</th><th class="n">fair</th><th class="n">deal</th><th class="n">paying for unwanted</th><th class="n">$ − unwanted</th><th>nice-to-haves</th></tr></thead><tbody>${
    okRows.map(r=>`<tr><td>${plink(r.id)}</td><td class="n">${m0(r.price)}</td><td class="n dim">${fmtUsd(r.fair)}</td><td class="n">${dealTxt(r.dpct)}</td><td class="n ${r.unwanted>r.price*.3?'warn':'dim'}">${fmtUsd(r.unwanted)}</td><td class="n"><b>${fmtUsd(r.eff)}</b></td><td>${r.niceHave.map(k=>esc(m.F[ji(k)].l)).join(', ')}${nice.length?` <span class="dim">${r.niceHave.length}/${nice.length}</span>`:''}</td></tr>`).join('')||'<tr><td colspan="7" class="bad">nothing in this scope meets every requirement</td></tr>'}</tbody></table></div></div>
  <div><h3 class="small">what to give up <span class="dim">(cheapest radio meeting all reqs vs all-but-one)</span></h3><div class="wrap"><table class="small"><thead><tr><th>drop</th><th class="n">market saves</th><th class="n">model $</th><th>cheapest then</th></tr></thead><tbody>${
    giveUp.map(g=>`<tr><td>${esc(g.l)}</td><td class="n">${isFinite(g.save)?`<b class="${g.save>0?'up':'dim'}">${fmtUsd(g.save)}</b>`:'<span class="dim">n/a</span>'}</td><td class="n dim">${fmtUsd(g.model)}</td><td>${g.who?plink(g.who.id)+' <span class="dim">'+m0(g.who.price)+'</span>':''}</td></tr>`).join('')||'<tr><td colspan="4" class="dim">mark some functions req</td></tr>'}</tbody></table></div></div></div>`:''}
  <h2>radios: actual vs fair <span class="dim">(fair = predicted ${m.n>120?'out-of-fold (10-fold CV)':'from every other item in scope'} · deal = (fair − actual)/fair)</span> · sort <a href="#" data-act="psort" data-k="dpct">deal</a> <a href="#" data-act="psort" data-k="d">Δ$</a> <a href="#" data-act="psort" data-k="price">$</a></h2>
  <div class="wrap"><table class="small"><thead><tr><th>radio</th><th>brand</th><th>form</th><th class="n">$</th><th class="n">fair</th><th class="n">Δ$</th><th class="n">deal</th><th>biggest priced functions</th></tr></thead><tbody>${
    rows.map(r=>`<tr><td>${plink(r.id)}${P[r.id].legacy?' <span class="bad small">legacy</span>':''}</td><td class="dim">${esc(P[r.id].brand)}</td><td class="dim">${esc(P[r.id].f.form_factor||'')}</td><td class="n">${m0(r.price)}</td><td class="n">${fmtUsd(r.fair)}</td><td class="n ${r.d>0?'up':'down'}">${r.d>0?'+':''}${fmtUsd(r.d)}</td><td class="n">${dealTxt(r.dpct)}</td><td class="dim">${contrib(r)}</td></tr>`).join('')}</tbody></table></div>`;
}

function priceClick(ev,b){
  const a=b.dataset.act;
  if(a==='pwant'){ ev.preventDefault(); const k=b.dataset.k, cur=pWant[k]; pWant[k]=cur==null?'nice':cur==='nice'?'req':undefined; if(!pWant[k]) delete pWant[k]; route(); return true; }
  if(a==='pfacet'){ const cur=(location.hash.match(/^#price\.(.*)$/)||[])[1]||''; const o=parseScope(decodeURIComponent(cur)), k=b.dataset.k, v=b.dataset.v;
    if(k==='kind'){ location.hash='price.kind:'+v; return true; }
    if(!v) delete o[k]; else { o[k]=o[k]||new Set(); o[k].has(v)?o[k].delete(v):o[k].add(v); if(!o[k].size) delete o[k]; }
    location.hash='price.'+fmtScope(o); return true; }
  if(a==='pclear'){ ev.preventDefault(); pWant={}; route(); return true; }
  if(a==='psort'){ ev.preventDefault(); pSort=b.dataset.k; route(); return true; }
  if(a==='pleg'){ pLeg=b.checked; route(); return true; }
  if(a==='picpt'){ pIcpt=b.checked; route(); return true; }
  if(a==='pob'){ pOB=b.checked; route(); return true; }
  return false;
}
function priceChange(ev){
  const e=ev.target;
  if(e.id==='pmin'||e.id==='pmax'){ const v=e.value===''?null:+e.value; if(e.id==='pmin') pMin=v; else pMax=v; route(); return true; }
  if(e.id==='pmodel'){ pModelUser=e.value; route(); return true; }
  return false;
}
