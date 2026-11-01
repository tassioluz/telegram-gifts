(function(){
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
const root=document.body.dataset.root||"";
const norm=s=>(s||"").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g,"");
const pct=r=>{r=+r;let s=r>=0.1||r===0?r.toFixed(1):r.toFixed(2);s=s.replace(/\.?0+$/,"");return s.replace(".",",")+"%"};

(function(){const g=$("#goto");if(!g)return;
  const m=location.pathname.match(/\/c\/([^\/]+?)(?:\.html)?$/);if(m&&[...g.options].some(o=>o.value===m[1]))g.value=m[1];
  g.addEventListener("change",()=>{if(g.value)location.href=root+"c/"+g.value+".html"})})();

if(window.PAGE==="index"){
  const cards=$$("#grid .card"),grid=$("#grid");let data=null;
  const byslug={};
  fetch(root+"data.json").then(r=>r.json()).then(d=>{data=d;d.collections.forEach(c=>byslug[c.slug]=c);
    const dl=$("#modelList"),seen=new Set();d.collections.forEach(c=>c.models.forEach(m=>{if(!seen.has(m.n)){seen.add(m.n);const o=document.createElement("option");o.value=m.n;dl.appendChild(o)}}));
    restore();apply()});
  const ids=["q","fBackdrop","fSymbol","fModel","fRarity","sort"];
  function restore(){const p=new URLSearchParams(location.hash.slice(1));ids.forEach(i=>{if(p.has(i))$("#"+i).value=p.get(i)})}
  function save(){const p=new URLSearchParams();ids.forEach(i=>{const v=$("#"+i).value;if(v)p.set(i,v)});history.replaceState(null,"",p.toString()?"#"+p:location.pathname)}
  function apply(){
    if(!data)return;save();
    const q=norm($("#q").value.trim()),fb=$("#fBackdrop").value,fs=$("#fSymbol").value,fm=norm($("#fModel").value.trim()),fr=parseFloat($("#fRarity").value)||null,so=$("#sort").value;
    let shown=0;const list=[];
    cards.forEach(el=>{const c=byslug[el.dataset.slug];if(!c){return}
      let ok=true,hits=[];
      if(q){const nm=norm(c.name).includes(q);const mm=c.models.filter(m=>norm(m.n).includes(q));if(!nm&&!mm.length)ok=false;else if(!nm)hits.push("Modelo: "+mm.slice(0,3).map(m=>m.n+" "+pct(m.r)).join(", ")+(mm.length>3?"…":""))}
      const attr=(arr,cond,label)=>{const f=arr.filter(cond);const g=fr?f.filter(x=>x.r<=fr):f;if(!g.length){ok=false}else hits.push(label+": "+g.slice(0,2).map(x=>x.n+" "+pct(x.r)).join(", ")+(g.length>2?"…":""))};
      if(ok&&fb)attr(c.backdrops,x=>x.n===fb,"Fundo");
      if(ok&&fs)attr(c.symbols,x=>x.n===fs,"Símbolo");
      if(ok&&fm)attr(c.models,x=>norm(x.n).includes(fm),"Modelo");
      if(ok&&fr&&!fb&&!fs&&!fm){const g=c.models.filter(x=>x.r<=fr);if(!g.length)ok=false;else hits.push(g.length+" modelo(s) ≤ "+pct(fr))}
      el.hidden=!ok;el.querySelector(".hit").textContent=ok?hits.join(" · "):"";if(ok){shown++;list.push([el,c])}});
    const key={name:(a,b)=>a.name.localeCompare(b.name),"floor-desc":(a,b)=>(b.floor??-1)-(a.floor??-1),"floor-asc":(a,b)=>(a.floor??1e12)-(b.floor??1e12),"supply-asc":(a,b)=>(a.supply??1e12)-(b.supply??1e12),"supply-desc":(a,b)=>(b.supply??-1)-(a.supply??-1),new:(a,b)=>(b.released||0)-(a.released||0),old:(a,b)=>(a.released||0)-(b.released||0)}[so];
    list.sort((x,y)=>key(x[1],y[1])).forEach(([el])=>grid.appendChild(el));
    $("#count").textContent=shown+" de "+cards.length+" coleções";$("#empty").hidden=shown>0}
  ids.forEach(i=>$("#"+i).addEventListener("input",apply));
}

function itemFilter(){
  const panes=$$("[data-pane]");if(!panes.length)return;
  const run=()=>{const q=norm(($("#iq")||{}).value||""),fr=parseFloat(($("#ir")||{}).value)||null,so=($("#is")||{}).value;
    let n=0,tot=0;panes.forEach(p=>{if(p.hidden)return;const its=[...p.children];tot+=its.length;
      its.forEach(el=>{const ok=(!q||norm(el.dataset.n).includes(q))&&(!fr||+el.dataset.r<=fr);el.hidden=!ok;if(ok)n++});
      if(so){its.sort((a,b)=>so==="az"?a.dataset.n.localeCompare(b.dataset.n):so==="com"?(b.dataset.r-a.dataset.r)||a.dataset.n.localeCompare(b.dataset.n):(a.dataset.r-b.dataset.r)||a.dataset.n.localeCompare(b.dataset.n)).forEach(e=>p.appendChild(e))}});
    if($("#icount"))$("#icount").textContent=n+" de "+tot};
  ["iq","ir","is"].forEach(i=>{const e=$("#"+i);if(e)e.addEventListener("input",run)});
  $$(".tabs button").forEach(b=>b.addEventListener("click",()=>{$$(".tabs button").forEach(x=>x.classList.toggle("on",x===b));panes.forEach(p=>p.hidden=p.dataset.pane!==b.dataset.tab);run()}));
  run();
}
itemFilter();

if(window.PAGE==="collection"){
  const G=window.GIFT,dlg=$("#dlg");let anim=null;
  const enc=x=>encodeURIComponent(x.replace(/\u2019/g,"'").replace(/\//g,"\\"));
  function play(url,el){if(!window.lottie){return false}
    fetch(url).then(r=>r.json()).then(j=>{if(anim)anim.destroy();el.innerHTML="";anim=lottie.loadAnimation({container:el,renderer:"svg",loop:true,autoplay:true,animationData:j})}).catch(()=>{});return true}
  $$(".item.model").forEach(b=>b.addEventListener("click",()=>{
    $("#dlgTitle").textContent=b.dataset.n;$("#dlgSub").textContent="Raridade: "+pct(b.dataset.r);
    const a=$("#anim");a.innerHTML='<img src="'+b.querySelector("img").src+'" style="width:100%">';dlg.showModal();play(b.dataset.lottie,a);
    const s=$("#bModel");if(s){s.value=b.dataset.n;build()}}));
  $("#dlgClose").addEventListener("click",()=>dlg.close());dlg.addEventListener("close",()=>{if(anim){anim.destroy();anim=null}});
  dlg.addEventListener("click",e=>{if(e.target===dlg)dlg.close()});
  const cov=$("#coverAnim");let covPlayed=false;
  cov.addEventListener("click",()=>{if(covPlayed||!cov.dataset.lottie||!window.lottie)return;covPlayed=true;
    fetch(cov.dataset.lottie).then(r=>r.json()).then(j=>{cov.innerHTML="";lottie.loadAnimation({container:cov,renderer:"svg",loop:true,autoplay:true,animationData:j})}).catch(()=>{})});
  // builder
  const bm=$("#bModel"),bb=$("#bBackdrop"),bs=$("#bSymbol");
  const bdMap={};$$(".item.bd").forEach(e=>bdMap[e.dataset.n]=e.dataset);
  const rOf=sel=>{const el=$$("[data-pane] .item").find(e=>e.dataset.n===sel.value&&e.parentElement.dataset.pane===sel.dataset.p);return el?+el.dataset.r:null};
  bm.dataset.p="models";bb.dataset.p="backdrops";bs.dataset.p="symbols";
  const spots=[[50,9],[22,16],[78,16],[9,40],[91,40],[9,66],[91,66],[22,88],[78,88],[50,93],[33,30],[67,30],[30,76],[70,76]];
  function build(){
    const mi=$$('[data-pane="models"] .item').find(e=>e.dataset.n===bm.value);
    $("#pModel").src=mi?mi.querySelector("img").src:"";
    const b=bdMap[bb.value];const pv=$("#preview");
    if(b)pv.style.background="radial-gradient(circle at 50% 45%,"+b.c+" 0%,"+b.e+" 100%)";
    const url=G.cdn+"/patterns/"+enc(G.name)+"/png/"+enc(bs.value)+".png";
    $("#pat").innerHTML=spots.map(([x,y],i)=>'<span style="left:calc('+x+'% - 13px);top:calc('+y+'% - 13px);background:'+(b?b.p:"#000")+';-webkit-mask-image:url(\''+url+'\');mask-image:url(\''+url+'\');opacity:.85;transform:scale('+(i>9?.8:1)+')"></span>').join("");
    const rm=rOf(bm),rb=rOf(bb),rs=rOf(bs);
    if(rm!=null&&rb!=null&&rs!=null){const p=rm/100*rb/100*rs/100;const one=Math.round(1/p);
      $("#bOdds").innerHTML="Modelo "+pct(rm)+" × Fundo "+pct(rb)+" × Símbolo "+pct(rs)+"<br>Chance desta combinação: <b>1 em "+one.toLocaleString("pt-BR")+"</b>"}}
  [bm,bb,bs].forEach(s=>s.addEventListener("input",build));
  function pick(sel){const opts=[...sel.options];const w=opts.map(o=>{const r=$$("[data-pane='"+sel.dataset.p+"'] .item").find(e=>e.dataset.n===o.value);return r?+r.dataset.r:1});
    let t=w.reduce((a,b)=>a+b,0)*Math.random();for(let i=0;i<w.length;i++){t-=w[i];if(t<=0){sel.selectedIndex=i;return}}}
  $("#bRandom").addEventListener("click",()=>{pick(bm);pick(bb);pick(bs);build()});
  pick(bm);pick(bb);pick(bs);build();
}
})();
