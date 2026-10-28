// ---------- ham inventory plugin: per-location band ledger (radio ↔ antenna ↔ tuner), 13.8 V supply, digital path; capability atoms ----------
const HFB = ['160m','80m','60m','40m','30m','20m','17m','15m','12m','10m'], ALLB = [...HFB,'6m','4m','2m','1.25m','70cm','23cm'];
const BW = {'160m':1,'80m':1,'60m':.5,'40m':1,'30m':.7,'20m':1,'17m':.7,'15m':.8,'12m':.6,'10m':.8,'6m':2,'4m':.5,'2m':2,'1.25m':1,'70cm':2,'23cm':1.5};
const bandsOf = p => (p.f.bands_tx||[]).filter(b=>ALLB.includes(b));
const isRadio = p => bandsOf(p).length>0;
const pw = (p,k) => +((p.f.power_w||{})[k])||0;
const hfW = p => pw(p,'hf'), vuW = p => Math.max(pw(p,'2m'),pw(p,'70cm'));
const bandW = (p,b) => HFB.includes(b) ? hfW(p) : b==='6m' ? (pw(p,'6m')||hfW(p)) : b==='2m'||b==='1.25m'||b==='4m' ? (pw(p,'2m')||vuW(p)) : b==='70cm' ? (pw(p,'70cm')||vuW(p)) : pw(p,b);
const needs138 = p => isRadio(p) && p.f.form_factor!=='handheld' && /13\.8|external/i.test(p.f.power_source||'') && !/internal AC/i.test(p.f.power_source||'');
const txA = p => +p.f.tx_current_a || Math.round(Math.max(hfW(p),vuW(p))*.21+1);
const selfAnt = p => p.f.form_factor==='handheld';   // HTs carry their own antenna
const DV = x => String(x).toUpperCase().replace('SYSTEM FUSION','C4FM');
const bandStr = bs => RENDER.bands(ALLB.filter(b=>bs.has?bs.has(b):bs.includes(b)));

function capsHam(p){
  const f=p.f||{}, out=[], push=(a,l,g,w)=>out.push({a,l,g,w});
  if(isRadio(p)){
    const bs=bandsOf(p), hf=bs.some(b=>HFB.includes(b)), vu=bs.some(b=>['2m','70cm','1.25m'].includes(b));
    bs.forEach(b=>push('tx:'+b,b,'band',BW[b]));
    const ms=new Set((f.modes||[]).map(m=>/^(SSB|USB|LSB)/.test(m)?'SSB':/^CW/.test(m)?'CW':/^FM/.test(m)?'FM':/^AM$/.test(m)?'AM':/RTTY|PSK|DATA|FT8/.test(m)?'data':null).filter(Boolean));
    ms.forEach(m=>push('mode:'+m,m,'mode',.4));
    // weak-signal VHF/UHF (SSB/CW above 50 MHz) is its own capability: an HF rig with 6m SSB doesn't give 2m SSB
    if(vu && ms.has('SSB') && f.vhf_uhf!==false) push('vu:ssb','2m/70 SSB/CW','mode',1.2);
    (f.digital_voice||[]).forEach(d=>push('dv:'+DV(d),DV(d),'dv',2));
    [10,50,100,200,500].filter(x=>hfW(p)>=x).forEach(x=>push('hfw:'+x,`HF ≥${x}W`,'power',x>=200?1:.6));
    [5,25,50].filter(x=>vuW(p)>=x).forEach(x=>push('vuw:'+x,`V/U ≥${x}W`,'power',.4));
    if(f.band_scope) push('scope','scope','feature',1);
    if(f.dual_receive) push('2rx','2 RX','feature',1.5);
    if(f.atu) push('match:int','int. ATU','feature',.8);
    if(f.usb_single_cable) push('digi','USB digi','feature',1);
    if(f.lan_remote) push('lan','LAN remote','feature',1);
    if(f.gps) push('gps','GPS','feature',.5);
    if(f.aprs) push('aprs','APRS','feature',1);
    if(f.full_duplex_sat) push('sat','sat duplex','feature',1.5);
    if(f.crossband_repeat) push('xband','xband rpt','feature',.5);
    if(f.detachable_head) push('head','sep. head','feature',.5);
    if(f.rx_antenna_in) push('rxant','RX ant in','feature',.5);
    if(/[78]$/.test(String(f.ip_rating||''))) push('wx','waterproof','feature',.7);
    const ff=f.form_factor; if(ff){ push('form:'+ff,ff,'form',1); if(hf) push(`form:${ff}:hf`,`${ff} HF`,'form',1); if(vu) push(`form:${ff}:vu`,`${ff} V/U`,'form',.6); }
    if(f.battery && ff==='portable') push('battery','int. battery','feature',.7);
  }
  // HT antennas only serve handhelds (which carry their own), so they don't count as station band coverage
  if(f.mount==='handheld') (f.ant_bands||[]).forEach(b=>push('htant:'+b,b+' HT ant','antenna',.1));
  else (f.ant_bands||[]).forEach(b=>push('ant:'+b,b+' ant','antenna',.6));
  if(f.tuner) push('match:ext','ext. tuner','feature',.8);
  if(f.psu_a) [10,20,30,40].filter(x=>f.psu_a>=x).forEach(x=>push('psu:'+x,`PSU ≥${x}A`,'power',.3));
  if(f.digi_iface) push('digi','digi iface','feature',1);
  if(f.rx_only) { push('rx:sdr','SDR RX','feature',.5); if(f.hf_rx) push('rx:hf','HF SDR RX','feature',.5); }
  return out;
}

// band ledger over what's usable at a path
function hamL(U){
  const radios=U.filter(u=>isRadio(u.p)), ants=U.filter(u=>(u.p.f.ant_bands||[]).length&&u.p.f.mount!=='handheld'&&!u.p.f.rx_only), tuners=U.filter(u=>u.p.f.tuner);
  const psu=Math.max(0,...U.map(u=>+u.p.f.psu_a||0)), digi=U.filter(u=>u.p.f.digi_iface||u.p.f.usb_single_cable);
  const bands=ALLB.filter(b=>radios.some(u=>bandsOf(u.p).includes(b))||ants.some(u=>u.p.f.ant_bands.includes(b))).map(b=>{
    const rs=radios.filter(u=>bandsOf(u.p).includes(b)), as=ants.filter(u=>u.p.f.ant_bands.includes(b)), fixed=rs.filter(u=>!selfAnt(u.p));
    const maxW=Math.max(0,...fixed.map(u=>bandW(u.p,b))), antW=Math.max(0,...as.map(u=>+u.p.f.max_w||0));
    const resonant=as.some(u=>u.p.f.resonant), tuned=tuners.some(u=>(u.p.f.tuner_bands||HFB).includes(b)), intAtu=fixed.some(u=>u.p.f.atu);
    const st = !rs.length ? ['dim','idle antenna'] : fixed.length && !as.length ? ['bad','no antenna'] : as.length && !resonant && !tuned && !intAtu && fixed.length ? ['warn','needs tuner']
      : as.length && antW && maxW>antW ? ['warn',`ant ≤${antW}W < ${maxW}W`] : ['up', fixed.length?'ok':'HT only'];
    return {b, rs, as, maxW, antW, resonant, tuned, intAtu, st};
  });
  const hv=radios.filter(u=>needs138(u.p)), maxA=Math.max(0,...hv.map(u=>txA(u.p))), sumA=hv.reduce((a,u)=>a+txA(u.p)*u.n,0);
  return {radios, ants, tuners, psu, digi, bands, hv, maxA, sumA, hasHF:radios.some(u=>bandsOf(u.p).some(b=>HFB.includes(b)))};
}
const shortName = u => esc((u.p.name||'').replace(/^(Yaesu|Icom|Kenwood|FlexRadio)\s+/,'').slice(0,18));

const INVDOM = {
  ledgerNote: '(everything usable here: placed below or scoped to cover it)',
  itemCols: [
    {h:'TX', td:(it,p)=>isRadio(p)?bandStr(bandsOf(p)):(p.f.ant_bands||[]).length?`<span class="dim">ant</span> ${bandStr(p.f.ant_bands)}`:''},
    {h:'W', n:1, td:(it,p)=>isRadio(p)?[hfW(p),vuW(p)].filter(Boolean).join('/'):p.f.max_w?`<span class="dim">≤${p.f.max_w}</span>`:p.f.psu_a?`<span class="dim">${p.f.psu_a}A</span>`:''},
    {h:'DV', td:(it,p)=>esc((p.f.digital_voice||[]).map(DV).join(' '))},
    {h:'feat', td:(it,p)=>capsHam(p).filter(c=>c.g==='feature').map(c=>c.l).join(' ')},
  ],
  siteHeads: ['radios','bands (TX w/ antenna)','no antenna','PSU A need/have','issues'],
  siteCells(ctx){
    const L=hamL(ctx.availTgt), ok=L.bands.filter(x=>x.st[0]==='up').map(x=>x.b), noant=L.bands.filter(x=>x.st[1]==='no antenna').map(x=>x.b);
    const n=INVDOM.issues(ctx).length;
    return [L.radios.reduce((a,u)=>a+u.n,0), bandStr(ok), noant.length?`<span class="bad">${bandStr(noant)}</span>`:'',
      L.hv.length?`<span class="${L.maxA>L.psu?'bad':''}">${L.maxA}/${L.psu}</span>`:'', n?`<span class="bad">${n}</span>`:'<span class="up">ok</span>'];
  },
  locHeads: ['TX bands','DV','HF W','ant'],
  locCells(av){
    const L=hamL(av), rb=new Set(L.radios.flatMap(u=>bandsOf(u.p))), ab=new Set(L.ants.flatMap(u=>u.p.f.ant_bands));
    return [bandStr(rb), esc([...new Set(L.radios.flatMap(u=>(u.p.f.digital_voice||[]).map(DV)))].join(' ')), Math.max(0,...L.radios.map(u=>hfW(u.p)))||'', `<span class="dim">${bandStr(ab)}</span>`];
  },
  ledger(ctx){
    const L=hamL(ctx.availTgt), Ln=hamL(ctx.availNow);
    const nowSt=b=>(Ln.bands.find(x=>x.b===b)||{st:['dim','—']}).st;
    return `<div class="wrap"><table class="small"><thead><tr><th>band</th><th>radios (TX)</th><th class="n">max W</th><th>antennas</th><th>match</th><th>target</th><th>now</th></tr></thead><tbody>${
      L.bands.map(x=>{const ns=nowSt(x.b);return `<tr><td>${x.b}</td><td>${x.rs.map(shortName).join(' ')||'<span class="dim">—</span>'}</td><td class="n">${x.maxW||''}</td>
        <td>${x.as.map(u=>`${shortName(u)}${u.p.f.max_w?`<span class="dim">≤${u.p.f.max_w}</span>`:''}`).join(' ')||'<span class="dim">—</span>'}</td>
        <td class="dim">${x.as.length?(x.resonant?'resonant':[x.intAtu&&'int ATU',x.tuned&&'ext tuner'].filter(Boolean).join('+')||'—'):''}</td>
        <td class="${x.st[0]}">${x.st[1]}</td><td class="${ns[0]}">${ns[1]===x.st[1]?'=':ns[1]}</td></tr>`}).join('')||'<tr><td colspan="7" class="dim">no radios or antennas usable here</td></tr>'}
      <tr><td>13.8 V</td><td colspan="2">${L.hv.length?`max TX ${L.maxA} A · all keyed ${L.sumA} A`:'<span class="dim">no supply-fed radios</span>'}</td><td colspan="2">${L.psu?`supply ${L.psu} A`:'<span class="dim">no supply</span>'}</td>
        <td class="${!L.hv.length?'dim':L.maxA>L.psu?'bad':'up'}">${!L.hv.length?'':L.maxA>L.psu?`short ${L.maxA-L.psu} A`:'ok'}</td><td></td></tr>
      <tr><td>digital</td><td colspan="4">${L.digi.map(shortName).join(' ')||'<span class="dim">no USB-codec radio or interface</span>'}</td><td class="${L.digi.length?'up':L.hasHF?'warn':'dim'}">${L.digi.length?'FT8-ready':L.hasHF?'needs interface':''}</td><td></td></tr>
    </tbody></table></div>
    <p class="dim small">A band is usable when a radio transmits on it and an antenna usable here covers it (HTs carry their own). Non-resonant antennas need an internal ATU or external tuner; antenna power rating is checked against the strongest radio. Supply: largest 13.8 V supply vs the hungriest radio (one keyed at a time); TX amps estimated from W when unknown.</p>`;
  },
  issues(ctx){
    const L=hamL(ctx.availTgt), iss=[];
    const noant=L.bands.filter(x=>x.st[1]==='no antenna').map(x=>x.b), tune=L.bands.filter(x=>x.st[1]==='needs tuner').map(x=>x.b);
    const weak=L.bands.filter(x=>/^ant ≤/.test(x.st[1])), idle=L.bands.filter(x=>x.st[1]==='idle antenna').map(x=>x.b);
    if(noant.length) iss.push(`<h2 class="bad">no antenna for ${bandStr(noant)}</h2><div class="small dim">${L.radios.filter(u=>!selfAnt(u.p)&&bandsOf(u.p).some(b=>noant.includes(b))).map(u=>u.p.name).join(', ')} can't radiate there from ${esc(ctx.X)} — add an ≈ Antenna (or widen an existing antenna's scope)</div>`);
    if(tune.length) iss.push(`<h2 class="warn">${bandStr(tune)}: only non-resonant antennas and no tuner</h2><div class="small dim">add an ≈ External antenna tuner, or a radio with an internal ATU</div>`);
    weak.forEach(x=>iss.push(`<h2 class="warn">${x.b}: antenna rated ${x.antW} W, radio does ${x.maxW} W</h2><div class="small dim">turn power down or use ${esc(x.as.filter(u=>!(+u.p.f.max_w)||u.p.f.max_w>=x.maxW).map(u=>u.p.name).join(', ')||'a higher-rated antenna')}</div>`));
    if(L.hv.length && L.maxA>L.psu) iss.push(`<h2 class="bad">13.8 V supply short: need ≥${L.maxA} A, have ${L.psu||'none'}</h2><div class="small dim">${L.hv.map(u=>`${esc(u.p.name)} ${txA(u.p)} A`).join(' · ')} — add an ≈ 13.8 V power supply (or set the vehicle's 12 V as one)</div>`);
    if(L.hasHF && !L.digi.length) iss.push(`<h2 class="warn">no digital-mode path (FT8/WSPR)</h2><div class="small dim">add an ≈ Digital-mode interface, or a USB-codec radio</div>`);
    if(idle.length){
      const have=capsOf(ctx.availTgt), c=ids.filter(id=>!P[id].legacy&&P[id].price&&bandsOf(P[id]).some(b=>idle.includes(b))).map(id=>({id,k:bandsOf(P[id]).filter(b=>idle.includes(b)),m:marginal(P[id],have)}))
        .sort((a,b)=>b.k.length-a.k.length||P[a.id].price-P[b.id].price).slice(0,6);
      iss.push(`<h2 class="side">antennas with no radio: ${bandStr(idle)}</h2><ul class="t small">${c.map(r=>`<li>${plink(r.id)} <span class="dim">${money(P[r.id].price)} · uses ${bandStr(r.k)}</span></li>`).join('')}</ul>`);
    }
    return iss;
  },
  caps: capsHam,
  addBase(X,U){ return hamL(U); },
  addHeads: ['also needs here','uses idle ant / fixes'],
  addCells(p, U, X, L){
    if((p.f.ant_bands||[]).length && !isRadio(p) && p.f.mount!=='handheld' && !p.f.rx_only){
      // antenna: which radio bands here it would light up, and what it still needs (tuner, power headroom)
      const fix=L.bands.filter(x=>x.st[1]==='no antenna'&&p.f.ant_bands.includes(x.b)).map(x=>x.b);
      const maxW=Math.max(0,...L.bands.filter(x=>p.f.ant_bands.includes(x.b)).map(x=>x.maxW));
      const need=[p.f.resonant===false&&!L.tuners.length&&!L.radios.some(u=>u.p.f.atu)&&'tuner', p.f.max_w&&maxW>p.f.max_w&&`rated ${p.f.max_w}W < ${maxW}W`,
        p.f.radials&&'radials', p.f.directional&&'rotator'].filter(Boolean);
      return [need.length?{h:`<span class="warn">${esc(need.join(' · '))}</span>`}:'', fix.length?{h:`<b class="up">fixes ${bandStr(fix)}</b>`,live:true}:''];
    }
    if(!isRadio(p)) return ['',''];
    const ab=new Set(L.ants.flatMap(u=>u.p.f.ant_bands)), bs=bandsOf(p);
    const miss=selfAnt(p)?[]:bs.filter(b=>!ab.has(b)), idle=bs.filter(b=>L.bands.some(x=>x.b===b&&x.st[1]==='idle antenna'));
    const need=[miss.length&&`ant ${bandStr(miss)}`, needs138(p)&&txA(p)>L.psu&&`PSU ${txA(p)}A`, p.f.form_factor!=='handheld'&&(p.f.requires||[]).filter(r=>!/power supply|13\.8/i.test(r)).slice(0,1).join('')].filter(Boolean);
    return [need.length?{h:`<span class="warn">${esc(need.join(' · '))}</span>`}:'', idle.length?{h:`<b class="up">${bandStr(idle)}</b>`,live:true}:''];
  },
};
