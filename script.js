(() => {
  'use strict';

  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];

  const T = {
    fr: {
      navHome:'Accueil', navEvolution:'Évolution', navAnalysis:'Analyse', navForecast:'Prévision', navData:'Données', navMethods:'Méthodes',
      guideButton:'Ouvrir le guide', guideReplay:'Rejouer le guide',
      heroKicker:'Taux de change', heroSubtitle:'Le taux. Son évolution. Une prévision.', heroCta:'Voir l’évolution', heroGuide:'Comment ça marche', heroSource:'Données publiées par la Banque Centrale du Congo',
      official:'Source BCC', perDollar:'Francs congolais pour 1 dollar', previousValue:'Dernière valeur', scrollHint:'Faites défiler', syncHistory:'Historique BCC synchronisé jusqu’au', syncDirect:'Dernière cotation lue directement sur la BCC', syncFallback:'Dernière cotation issue de l’historique synchronisé',
      evoKicker:'01 · Évolution', evoTitle:'Voir le taux dans le temps.', historical:'Historique USD/CDF', chartInstruction:'Survolez un point pour voir la date.', showTable:'Voir les valeurs', hideTable:'Masquer les valeurs', tableCaption:'Quelques observations', date:'Date',
      periodLabel:'Période', lastPoint:'Dernier point', recentTrend:'Variation récente', fromPrevious:'vs. précédent', nextAnalysis:'Continuer vers l’analyse',
      analysisKicker:'02 · Analyse', analysisTitle:'Quelques repères. Rien de plus.', analysisNote:'Calculés à partir des dernières observations', metricVariation:'Variation récente', metricAverage:'Moyenne récente', metricVolatility:'Volatilité récente', technicalKicker:'03 · Indicateurs', technicalTitle:'Ce que dit la série maintenant.', technicalNote:'Calculé directement sur les observations visibles', researchKicker:'04 · Comparaison', researchTitle:'Deux approches. Une même référence.', researchCopy:'Les modèles expérimentaux sont comparés à la prévision naïve sur un test final hors échantillon.', methodsKicker:'05 · Méthodes', methodsTitle:'Voir comment la prévision est évaluée.', methodsNote:'Documentation complète intégrée au projet', methodXgb:'Modèle direct par horizon, variables construites à partir du passé strict, walk-forward et test final.', methodStrategy:'La série est transformée en indicateurs techniques puis comparée à la référence naïve avec validation walk-forward.', methodArchivesTitle:'Audit', methodArchivesCopy:'Les scripts, modèles, rapports et graphiques expérimentaux restent inclus dans le ZIP pour reproduire ou auditer les résultats.', validationTableTitle:'Validation finale', validationTableNote:'Ratio MAE : 1,00 = naïve', signalBull:'Haussier', signalBear:'Baissier', signalNeutral:'Neutre', 
      forecastKicker:'03 · Prévision', forecastTitle:'Ce qui pourrait suivre.', forecastMethod:'Prévision mise à jour automatiquement', forecastSmall:'Une estimation des prochaines cotations. Les zones montrent l’incertitude.', confidenceLabel:'Incertitude', validationNote:'5 = les 5 prochaines cotations BCC. 10 et 20 fonctionnent de la même façon.', forecastValue:'Valeur estimée', forecastHistorical:'Historique', forecastCentral:'Prévision',
      dataKicker:'04 · Données', dataTitle:'Voir. Chercher. Exporter.', download:'Télécharger', searchLabel:'Rechercher une date', fullTableCaption:'Observations USD/CDF', variation:'Variation', status:'Source', sourceTitle:'Banque Centrale du Congo', sourceBrief:'Source institutionnelle de la série', openSource:'Ouvrir', footerNote:'Données BCC et prévision recalculée automatiquement.',
      guideSkip:'Passer', guideNext:'Suivant', guideEnd:'Terminer',
      guide1Title:'Aujourd’hui', guide1Copy:'Le dernier taux est ici. Un coup d’œil suffit.',
      guide2Title:'Évolution', guide2Copy:'Passez sur la courbe. Une date, une valeur.',
      guide3Title:'Prévision', guide3Copy:'Choisissez 5, 10 ou 20 prochaines cotations pour voir l’estimation.',
      rows:'lignes', obs:'observations'
    },
    en: {
      navHome:'Home', navEvolution:'Trend', navAnalysis:'Analysis', navForecast:'Forecast', navData:'Data', navMethods:'Methods',
      guideButton:'Open guide', guideReplay:'Replay guide',
      heroKicker:'Exchange rate', heroSubtitle:'The rate. The trend. A forecast.', heroCta:'See the trend', heroGuide:'How it works', heroSource:'Data published by the Central Bank of the Congo',
      official:'BCC source', perDollar:'Congolese francs for 1 dollar', previousValue:'Previous value', scrollHint:'Scroll', syncHistory:'BCC history synchronized through', syncDirect:'Latest quote read directly from the BCC', syncFallback:'Latest quote from the synchronized history',
      evoKicker:'01 · Trend', evoTitle:'See the rate over time.', historical:'USD/CDF history', chartInstruction:'Hover a point to see the date.', showTable:'See values', hideTable:'Hide values', tableCaption:'A few observations', date:'Date',
      periodLabel:'Period', lastPoint:'Last point', recentTrend:'Recent change', fromPrevious:'vs. previous', nextAnalysis:'Continue to analysis',
      analysisKicker:'02 · Analysis', analysisTitle:'A few useful signals.', analysisNote:'Calculated on the displayed series', metricVariation:'Recent change', metricAverage:'Recent average', metricVolatility:'Recent volatility', dependence:'Dependence', technicalKicker:'03 · Indicators', technicalTitle:'What the series says now.', technicalNote:'Calculated directly on the visible observations', researchKicker:'04 · Comparison', researchTitle:'Two approaches. One reference.', researchCopy:'Experimental models are compared with the naive forecast on a final out-of-sample test.', methodsKicker:'05 · Methods', methodsTitle:'See how the forecast is evaluated.', methodsNote:'Full documentation included in the project', methodXgb:'Direct model by horizon, strict past-only features, walk-forward and final test.', methodStrategy:'The series is transformed into technical indicators and compared with the naive reference using walk-forward validation.', methodArchivesTitle:'Audit', methodArchivesCopy:'Scripts, models, reports and charts remain included in the ZIP for reproducibility and audit.', validationTableTitle:'Final validation', validationTableNote:'MAE ratio: 1.00 = naive', signalBull:'Bullish', signalBear:'Bearish', signalNeutral:'Neutral',
      forecastKicker:'03 · Forecast', forecastTitle:'What could follow?', forecastMethod:'Forecast updated automatically', forecastSmall:'An estimate for the upcoming quotes. The bands show uncertainty.', confidenceLabel:'Uncertainty', validationNote:'5 means the next 5 BCC quotes. 10 and 20 work the same way.', forecastValue:'Estimated value', forecastHistorical:'History', forecastCentral:'Forecast',
      dataKicker:'04 · Data', dataTitle:'View. Search. Export.', download:'Download', searchLabel:'Search by date', fullTableCaption:'USD/CDF observations', variation:'Change', status:'Source', sourceTitle:'Central Bank of the Congo', sourceBrief:'Institutional source of the series', openSource:'Open', footerNote:'BCC data with an automatically recalculated forecast.',
      guideSkip:'Skip', guideNext:'Next', guideEnd:'Finish',
      guide1Title:'Today', guide1Copy:'The latest rate is here. One glance is enough.',
      guide2Title:'Trend', guide2Copy:'Move over the curve. One date, one value.',
      guide3Title:'Forecast', guide3Copy:'Choose 5, 10 or 20 upcoming quotes to see the estimate.',
      rows:'rows', obs:'observations'
    }
  };

  const state = {
    lang:'fr', data:[], range:'all', model:null, analyses:null, forecast:[], horizon:5, live:null
  };

  const fmt = (value) => new Intl.NumberFormat(state.lang === 'fr' ? 'fr-FR' : 'en-US', {minimumFractionDigits:2, maximumFractionDigits:2}).format(Number(value) || 0);
  const fmtPct = (value) => `${value < 0 ? '-' : ''}${Math.abs(value).toFixed(2).replace('.', state.lang === 'fr' ? ',' : '.') } %`;
  const shortDate = (date) => new Intl.DateTimeFormat(state.lang === 'fr' ? 'fr-FR' : 'en-US', {day:'2-digit', month:'short', year:'numeric'}).format(new Date(`${date}T00:00:00`));

  function setText() {
    document.documentElement.lang = state.lang;
    document.title = state.lang === 'fr' ? 'USD/CDF | Taux, évolution et prévision' : 'USD/CDF | Rate, trend and forecast';
    const seoDescription = document.querySelector('meta[name=description]');
    if (seoDescription) seoDescription.content = state.lang === 'fr' ? 'Consultez le taux USD/CDF, son évolution et une prévision à court terme à partir des données publiées par la Banque Centrale du Congo.' : 'View the USD/CDF rate, its trend and a short-term forecast based on data published by the Central Bank of the Congo.';
    const ogTitle = document.querySelector('meta[property=og\:title]');
    if (ogTitle) ogTitle.content = document.title;
    $$('[data-i18n]').forEach(el => {
      const key = el.dataset.i18n;
      if (T[state.lang][key]) el.textContent = T[state.lang][key];
    });
    $$('[data-i18n-aria]').forEach(el => {
      const key = el.dataset.i18nAria;
      if (T[state.lang][key]) el.setAttribute('aria-label', T[state.lang][key]);
    });
    $$('.lang').forEach(btn => {
      const active = btn.dataset.lang === state.lang;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-pressed', String(active));
    });
    if ($('#toggle-data-view')) $('#toggle-data-view span:first-child').textContent = $('#chart-data-table').hidden ? T[state.lang].showTable : T[state.lang].hideTable;
    if ($('#sync-status') && state.data.length) $('#sync-status').textContent = state.directLive ? `${T[state.lang].syncDirect} · ${shortDate(state.data.at(-1).date)}` : `${T[state.lang].syncFallback} · ${shortDate(state.data.at(-1).date)}`;
    $$('.horizon-switcher button').forEach(btn => { const n=btn.dataset.horizon; btn.setAttribute('aria-label', state.lang==='fr' ? `${n} prochaines cotations` : `${n} upcoming quotes`); });
  }

  async function loadData() {
    const [seriesResponse, modelResponse, analysesResponse, liveResponse] = await Promise.all([
      fetch('data/usd-cdf.json', {cache:'no-cache'}),
      fetch('data/model.json', {cache:'no-cache'}),
      fetch('data/analyses.json', {cache:'no-cache'}),
      fetch('api/bcc', {cache:'no-store'}).catch(() => null)
    ]);
    if (!seriesResponse.ok) throw new Error('series');
    const seriesObj = await seriesResponse.json();
    state.data = (seriesObj.series || []).filter(x => Number.isFinite(Number(x.value))).map(x => ({...x, value:Number(x.value)}));
    state.model = modelResponse.ok ? await modelResponse.json() : null;
    state.analyses = analysesResponse.ok ? await analysesResponse.json() : null;

    let direct = null;
    if (liveResponse?.ok) {
      try { direct = await liveResponse.json(); } catch (_) {}
    }
    if (direct && direct.date && Number.isFinite(Number(direct.value))) {
      const idx = state.data.findIndex(x => x.date === direct.date);
      if (idx >= 0) state.data[idx] = {...state.data[idx], value:Number(direct.value), live:true};
      else if (direct.date > state.data.at(-1)?.date) state.data.push({date:direct.date, value:Number(direct.value), live:true});
      state.directLive = direct;
    } else {
      state.directLive = null;
    }
    updateLive();
    renderAll();
  }

  function updateLive() {
    if (!state.data.length) return;
    const last = state.data.at(-1);
    const prev = state.data.at(-2) || last;
    const pct = prev.value ? ((last.value - prev.value) / prev.value) * 100 : 0;
    state.live = { ...last, previous:prev.value, changePct:pct };
    $('#live-date').textContent = shortDate(last.date);
    $('#live-rate').textContent = fmt(last.value);
    $('#live-previous').textContent = `${fmt(prev.value)} CDF`;
    $('#side-last').textContent = fmt(last.value);
    $('#side-change').textContent = fmtPct(pct);
    $('#metric-variation').textContent = fmtPct(pct);
    $('#side-change').classList.toggle('negative', pct < 0);
    $('#live-change').classList.toggle('negative', pct < 0);
    $('#live-change').innerHTML = `<b>${pct > 0 ? '↑' : pct < 0 ? '↓' : '•'}</b><span>${fmtPct(pct)}</span>`;
    const sync = $('#sync-status');
    if (sync) {
      if (state.directLive) sync.textContent = `${T[state.lang].syncDirect} · ${shortDate(last.date)}`;
      else sync.textContent = `${T[state.lang].syncFallback} · ${shortDate(last.date)}`;
    }
  }

  function getVisibleData() {
    if (!state.data.length || state.range === 'all') return state.data;
    const last = new Date(state.data.at(-1).date);
    const days = ({'1m':31,'6m':183,'1y':365,'5y':1825})[state.range] || 3650;
    const cutoff = new Date(last); cutoff.setDate(last.getDate() - days);
    return state.data.filter(d => new Date(d.date) >= cutoff);
  }

  function scalePoints(data, w, h, pad) {
    const values = data.map(d => d.value);
    const min = Math.min(...values), max = Math.max(...values), span = Math.max(1, max - min);
    return {min,max,pts:data.map((d,i) => ({x:pad.l + (i/(data.length-1 || 1))*(w-pad.l-pad.r), y:pad.t + (1-(d.value-min)/span)*(h-pad.t-pad.b), d}))};
  }
  function linePath(points) { return points.map((p,i)=>`${i?'L':'M'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' '); }
  function polyPath(points) { return points.map((p,i)=>`${i?'L':'M'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' '); }

  function drawMiniChart() {
    const data = state.data.slice(-28); if (data.length < 2) return;
    const W=420,H=74,pad={l:2,r:2,t:7,b:7},s=scalePoints(data,W,H,pad);
    const d = linePath(s.pts);
    const el = $('#mini-chart');
    el.innerHTML = `<path d="${d}" fill="none" stroke="#0d4638" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`;
  }

  function drawHistorical() {
    const svg=$('#historical-chart'), data=getVisibleData();
    if (!data.length) return;
    const W=1000,H=430,pad={l:58,r:18,t:24,b:42}, s=scalePoints(data,W,H,pad);
    const yTicks=5; let grid='';
    for(let i=0;i<=yTicks;i++){
      const y=pad.t+i*(H-pad.t-pad.b)/yTicks, v=s.max-(s.max-s.min)*i/yTicks;
      grid += `<line x1="${pad.l}" x2="${W-pad.r}" y1="${y}" y2="${y}" stroke="#edf0ed"/><text x="${pad.l-10}" y="${y+4}" text-anchor="end" font-size="11" fill="#7a8580">${fmt(v)}</text>`;
    }
    const idx=[0,Math.floor((data.length-1)*.25),Math.floor((data.length-1)*.5),Math.floor((data.length-1)*.75),data.length-1];
    idx.forEach((ix,j)=>{
      const p=s.pts[ix], label=shortDate(p.d.date).replace(/\s?\d{4}$/,'');
      grid += `<text x="${p.x}" y="${H-14}" text-anchor="${j===0?'start':j===idx.length-1?'end':'middle'}" font-size="11" fill="#7a8580">${label}</text>`;
    });
    const fill=`M ${pad.l} ${H-pad.b} ${s.pts.map(p=>`L ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')} L ${W-pad.r} ${H-pad.b} Z`;
    svg.innerHTML = `<title id="historical-chart-title">USD/CDF</title><desc id="historical-chart-desc">${T[state.lang].evoTitle}</desc>${grid}<path d="${fill}" fill="#0d4638" opacity=".05"/><path d="${linePath(s.pts)}" fill="none" stroke="#0d4638" stroke-width="2.7" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`;
    attachChartInteraction(data,s.pts,W,H,pad);
    renderChartTable(data);
    $('#range-summary').textContent = `${shortDate(data[0].date)} → ${shortDate(data.at(-1).date)}`;
  }

  function attachChartInteraction(data,pts,W,H,pad){
    const wrap=$('#historical-wrap'), tip=$('#chart-tooltip');
    const show = (ix) => {
      const i=Math.max(0,Math.min(data.length-1,ix)), d=data[i], p=pts[i];
      tip.hidden=false; tip.innerHTML=`<strong>${shortDate(d.date)}</strong><br>${fmt(d.value)} CDF`;
      tip.style.left=`${(p.x/W)*100}%`; tip.style.top=`${(p.y/H)*100}%`;
      wrap.dataset.cursor = String(i);
      $('#live-announcer').textContent = `${shortDate(d.date)} ${fmt(d.value)} CDF`;
    };
    wrap.onpointermove = e => {
      const r=wrap.getBoundingClientRect(); const px=(e.clientX-r.left)/r.width*W;
      show(Math.round((px-pad.l)/(W-pad.l-pad.r)*(data.length-1)));
    };
    wrap.onpointerleave = ()=>{tip.hidden=true};
    wrap.onkeydown = e => {
      if(e.key!=='ArrowLeft'&&e.key!=='ArrowRight') return;
      e.preventDefault(); show(Number(wrap.dataset.cursor||data.length-1)+(e.key==='ArrowRight'?1:-1));
    };
  }

  function renderChartTable(data){
    const picks=[0,Math.floor(data.length*.25),Math.floor(data.length*.5),Math.floor(data.length*.75),data.length-1].filter((v,i,a)=>v>=0 && a.indexOf(v)===i);
    $('#chart-table-body').innerHTML = picks.map(i=>`<tr><td>${shortDate(data[i].date)}</td><td>${fmt(data[i].value)}</td></tr>`).join('');
  }

  function dailyPct(data){return data.slice(1).map((d,i)=>data[i].value ? ((d.value-data[i].value)/data[i].value)*100 : 0)}
  function average(values){return values.length ? values.reduce((a,b)=>a+b,0)/values.length : 0}
  function std(values){if(values.length<2) return 0; const m=average(values); return Math.sqrt(values.reduce((s,v)=>s+(v-m)**2,0)/(values.length-1))}


  function renderAnalysis(){
    const data=state.data; if(data.length<22)return;
    const pct=dailyPct(data), last20=pct.slice(-20), avg20=average(data.slice(-20).map(d=>d.value)), vol=std(last20), last=pct.at(-1)||0;
    $('#metric-variation').textContent=fmtPct(last);
    $('#metric-average').textContent=fmt(avg20);
    $('#metric-volatility').textContent=`${vol.toFixed(2).replace('.',state.lang==='fr'?',':'.')} %`;
    const marker = Math.max(0,Math.min(100,((avg20-Math.min(...data.slice(-20).map(d=>d.value)))/(Math.max(...data.slice(-20).map(d=>d.value))-Math.min(...data.slice(-20).map(d=>d.value) || 1)))*100));
    $('#average-marker').style.left=`${marker}%`;
    const vdata=pct.slice(-24); const W=220,H=52,min=Math.min(...vdata),max=Math.max(...vdata),span=Math.max(.01,max-min);
    const pts=vdata.map((v,i)=>({x:i/(vdata.length-1)*(W-2)+1,y:7+(1-(v-min)/span)*(H-14)}));
    $('#variation-chart').innerHTML=`<path d="${linePath(pts)}" fill="none" stroke="#0d4638" stroke-width="2" stroke-linecap="round"/>`;
    const bars=$('#volatility-bars'); bars.innerHTML=''; last20.slice(-10).forEach(v=>{const h=Math.max(6,Math.min(100,Math.abs(v)/Math.max(vol,.01)*100)); const i=document.createElement('i'); i.style.height=`${h}%`; bars.appendChild(i)});
  }

  function renderTechnicalAnalysis(){
    const a = state.analyses?.technical_snapshot;
    if(!a) return;
    const pct = (v) => `${v >= 0 ? '+' : ''}${Number(v).toFixed(2).replace('.', state.lang==='fr'?',':'.')} %`;
    $('#tech-ema-gap').textContent = pct(a.ema_gap_20_50 * 100);
    $('#tech-ema-values').textContent = `EMA20 ${fmt(a.ema_20)} · EMA50 ${fmt(a.ema_50)}`;
    $('#tech-rsi').textContent = Number(a.rsi_14).toFixed(1).replace('.', state.lang==='fr'?',':'.');
    $('#tech-momentum').textContent = pct(a.momentum_10_pct);
    $('#tech-macd').textContent = Number(a.macd_hist).toFixed(2).replace('.', state.lang==='fr'?',':'.');
    const pill = $('#tech-signal');
    const label = a.ema_signal > 0 ? T[state.lang].signalBull : a.ema_signal < 0 ? T[state.lang].signalBear : T[state.lang].signalNeutral;
    pill.textContent = label;
    pill.className = `signal-pill ${a.ema_signal>0?'bull':a.ema_signal<0?'bear':'neutral'}`;
    const rsiNote = $('#tech-rsi-note');
    if(rsiNote) rsiNote.textContent = a.rsi_14 >= 70 ? 'Zone élevée' : a.rsi_14 <= 30 ? 'Zone basse' : 'Zone intermédiaire';
  }

  function renderResearchSummary(){
    const a = state.analyses; const root = $('#research-summary'); if(!root || !a) return;
    const mk = (title, rows, kind) => `<article class="research-mini ${kind}"><span>${title}</span>${rows.map(r=>`<div><b>${r.label}</b><strong>${r.value}</strong></div>`).join('')}</article>`;
    const strat = a.strategy.summary; const xgb = a.xgboost.metrics;
    root.innerHTML = [5,10,20].map(h=>{
      const k=`h${h}`, s=strat[k], x=xgb[k];
      return mk(`h = ${h}`, [
        {label:'EMA / stratégie · test',value:Number(s.test_ratio).toFixed(3)},
        {label:'XGBoost · test',value:Number(x.test_ratio).toFixed(3)},
        {label:'Décision',value:s.selected_model==='naive' && x.selected_model==='naive'?'Naïve':s.selected_model==='ma'?'EMA / MA':'Naïve'}
      ], h===10?'accent':'');
    }).join('');
    const body=$('#research-table-body'); if(body){
      body.innerHTML=[5,10,20].map(h=>{
        const k=`h${h}`, s=strat[k], x=xgb[k];
        const decision = s.selected_model !== 'naive' ? 'Stratégie' : x.selected_model !== 'naive' ? 'XGBoost' : 'Naïve';
        return `<tr><td>${h}</td><td>${Number(s.test_ratio).toFixed(3)}</td><td>${Number(x.test_ratio).toFixed(3)}</td><td><span class="decision-tag ${decision==='Stratégie'?'preferred':''}">${decision}</span></td></tr>`;
      }).join('');
    }
  }

  function buildForecast(){
    if(state.model?.forecast?.length){ state.forecast=state.model.forecast; return; }
    const y=state.data.map(d=>d.value); if(y.length<30){state.forecast=[];return;}
    const last=y.at(-1), diffs=y.slice(1).map((v,i)=>v-y[i]), drift=average(diffs.slice(-60));
    state.forecast=Array.from({length:30},(_,i)=>({horizon:i+1,value:last + (i+1)*drift,lower80:last + (i+1)*drift - 1.28*Math.sqrt((i+1))*12,upper80:last + (i+1)*drift + 1.28*Math.sqrt((i+1))*12,lower95:last + (i+1)*drift - 1.96*Math.sqrt((i+1))*12,upper95:last + (i+1)*drift + 1.96*Math.sqrt((i+1))*12}));
  }

  function drawForecast(){
    buildForecast(); if(!state.forecast.length || !state.data.length)return;
    const h=state.horizon, fc=state.forecast.slice(0,h), hist=state.data.slice(-70), svg=$('#forecast-chart');
    const W=760,H=330,pad={l:46,r:16,t:18,b:34};
    const vals=[...hist.map(d=>d.value),...fc.map(d=>d.value),...fc.map(d=>d.upper95),...fc.map(d=>d.lower95)];
    const min=Math.min(...vals),max=Math.max(...vals),span=Math.max(1,max-min), total=hist.length+fc.length-1;
    const x=i=>pad.l+i/total*(W-pad.l-pad.r), y=v=>pad.t+(1-(v-min)/span)*(H-pad.t-pad.b);
    const histPts=hist.map((d,i)=>({x:x(i),y:y(d.value)})), fcPts=fc.map((d,i)=>({x:x(hist.length-1+i),y:y(d.value)}));
    const b95u=fc.map((d,i)=>({x:x(hist.length-1+i),y:y(d.upper95)})); const b95l=[...fc].reverse().map((d,i)=>({x:x(hist.length-1+(fc.length-1-i)),y:y(d.lower95)}));
    const b80u=fc.map((d,i)=>({x:x(hist.length-1+i),y:y(d.upper80)})); const b80l=[...fc].reverse().map((d,i)=>({x:x(hist.length-1+(fc.length-1-i)),y:y(d.lower80)}));
    const split=x(hist.length-1);
    let grid='';
    for(let i=0;i<4;i++){const yy=pad.t+i*(H-pad.t-pad.b)/3,v=max-i*(max-min)/3;grid+=`<line x1="${pad.l}" x2="${W-pad.r}" y1="${yy}" y2="${yy}" stroke="#edf0ed"/><text x="${pad.l-9}" y="${yy+4}" text-anchor="end" font-size="10" fill="#7a8580">${fmt(v)}</text>`}
    const finalH=fc.at(-1); $('#forecast-end').textContent=fmt(finalH.value);
    const endLabel = state.lang==='fr' ? `après ${h} prochaines cotations` : `after ${h} upcoming quotes`;
    svg.setAttribute('aria-label', `${T[state.lang].forecastValue}: ${fmt(finalH.value)} CDF, ${endLabel}`);
    svg.innerHTML=`${grid}<polygon points="${[...b95u,...b95l].map(p=>`${p.x},${p.y}`).join(' ')}" fill="#ead7cd" opacity=".72"/><polygon points="${[...b80u,...b80l].map(p=>`${p.x},${p.y}`).join(' ')}" fill="#d7e2dd"/><path d="${linePath(histPts)}" fill="none" stroke="#8f9b96" stroke-width="2.2" stroke-linecap="round"/><line x1="${split}" x2="${split}" y1="${pad.t}" y2="${H-pad.b}" stroke="#b78265" stroke-dasharray="5 5"/><path d="${linePath(fcPts)}" fill="none" stroke="#1e6b55" stroke-width="2.8" stroke-linecap="round"/>`;
    $('#validation-note').style.opacity = '1';
  }

  function renderDataTable(){
    const q=$('#data-search').value.trim().toLowerCase(); const rows=state.data.slice().reverse().filter(d=>!q||d.date.includes(q)).slice(0,80);
    $('#full-data-body').innerHTML=rows.map((d,i)=>{const prev=state.data.find(x=>x.date===d.date); const idx=state.data.indexOf(prev); const before=idx>0?state.data[idx-1].value:d.value; const pct=before?((d.value-before)/before)*100:0; const cls=pct>0?'delta-up':pct<0?'delta-down':''; const arrow=pct>0?'↑':pct<0?'↓':'•'; return `<tr><td>${d.date}</td><td>${fmt(d.value)}</td><td class="${cls}">${arrow} ${fmtPct(pct)}</td><td><span class="status-tag">BCC</span></td></tr>`}).join('');
    $('#table-count').textContent=`${rows.length} ${T[state.lang].rows}`;
  }

  function renderAll(){drawMiniChart();drawHistorical();renderAnalysis();renderTechnicalAnalysis();renderResearchSummary();drawForecast();renderDataTable();setText();}

  function setupNavigation(){
    $$('.period-switcher button').forEach(b=>b.addEventListener('click',()=>{state.range=b.dataset.range; $$('.period-switcher button').forEach(x=>x.classList.remove('active'));b.classList.add('active');drawHistorical();}));
    $$('.horizon-switcher button').forEach(b=>b.addEventListener('click',()=>{state.horizon=Number(b.dataset.horizon); $$('.horizon-switcher button').forEach(x=>x.classList.remove('active'));b.classList.add('active');drawForecast();}));
    $('#data-search').addEventListener('input',renderDataTable);
    $('#toggle-data-view').addEventListener('click',()=>{const el=$('#chart-data-table'), hidden=el.hidden; el.hidden=!hidden; $('#toggle-data-view').setAttribute('aria-expanded',String(hidden)); setText();});
    $$('.lang').forEach(btn=>btn.addEventListener('click',()=>{state.lang=btn.dataset.lang;renderAll();}));
    $('#menu-button').addEventListener('click',()=>{const btn=$('#menu-button'),nav=$('#mobile-nav'),open=btn.getAttribute('aria-expanded')==='true';btn.setAttribute('aria-expanded',String(!open));nav.hidden=open;});
    $$('.mobile-nav a').forEach(a=>a.addEventListener('click',()=>{$('#mobile-nav').hidden=true;$('#menu-button').setAttribute('aria-expanded','false')}));
    $('#hero-guide').addEventListener('click',startGuide); $('#guide-trigger').addEventListener('click',startGuide); $('.mobile-guide').addEventListener('click',startGuide);
    $$('.main-nav a,.mobile-nav a').forEach(a=>a.addEventListener('click',()=>setTimeout(updateActiveNav,50)));
    const observed=['accueil','evolution','analyse','prevision','methodes','donnees'].map(id=>document.getElementById(id)).filter(Boolean);
    const navLinks=$$('.main-nav a,.mobile-nav a');
    const io=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting) navLinks.forEach(a=>a.classList.toggle('active',a.getAttribute('href')===`#${entry.target.id}`));}),{rootMargin:'-42% 0px -48% 0px',threshold:0}); observed.forEach(el=>io.observe(el));
  }
  function updateActiveNav(){const id=location.hash.replace('#','')||'accueil'; $$('.main-nav a,.mobile-nav a').forEach(a=>a.classList.toggle('active',a.getAttribute('href')===`#${id}`));}

  const guideSteps=[
    {target:'#rate-card',titleKey:'guide1Title',copyKey:'guide1Copy'},
    {target:'#evolution-card',titleKey:'guide2Title',copyKey:'guide2Copy'},
    {target:'#forecast-card',titleKey:'guide3Title',copyKey:'guide3Copy'}
  ];
  let guideIndex=0;
  function positionGuide(shouldScroll=false){
    if ($('#guide-layer').hidden) return;
    const target=document.querySelector(guideSteps[guideIndex].target), box=$('#guide-target'), card=$('#guide-card');
    if(!target) return;
    if(shouldScroll) target.scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'center'});
    requestAnimationFrame(()=>{
      const r=target.getBoundingClientRect();
      box.style.left=`${r.left-6}px`; box.style.top=`${r.top-6}px`; box.style.width=`${r.width+12}px`; box.style.height=`${r.height+12}px`;
      const cw=card.offsetWidth, ch=card.offsetHeight, gap=20;
      let left=Math.min(window.innerWidth-cw-16,Math.max(16,r.left));
      let top=r.bottom+gap;
      if(top+ch>window.innerHeight-16) top=r.top-ch-gap;
      if(top<16) top=16;
      card.style.left=`${left}px`; card.style.top=`${top}px`;
    });
  }
  function renderGuide(shouldScroll=true){
    const step=guideSteps[guideIndex];
    $('#guide-number').textContent=`0${guideIndex+1}`;
    $('#guide-title').textContent=T[state.lang][step.titleKey];
    $('#guide-copy').textContent=T[state.lang][step.copyKey];
    $('#guide-next').textContent=guideIndex===guideSteps.length-1?T[state.lang].guideEnd:T[state.lang].guideNext;
    $('#guide-progress').innerHTML=guideSteps.map((_,i)=>`<i class="${i<=guideIndex?'active':''}"></i>`).join('');
    positionGuide(shouldScroll);
  }
  function startGuide(){
    guideIndex=0;
    $('#guide-layer').hidden=false;
    renderGuide(true);
    setTimeout(()=>$('#guide-next').focus(),220);
  }
  function endGuide(){
    $('#guide-layer').hidden=true;
    $('#guide-trigger').focus();
  }
  $('#guide-next').addEventListener('click',()=>{
    if(guideIndex===guideSteps.length-1){endGuide();return;}
    guideIndex++; renderGuide(true);
  });
  $('#guide-skip').addEventListener('click',endGuide);
  window.addEventListener('resize',()=>positionGuide(false));
  window.addEventListener('scroll',()=>positionGuide(false),{passive:true});

  const observer=new IntersectionObserver(entries=>entries.forEach(e=>e.isIntersecting&&e.target.classList.add('in-view')),{threshold:.12});
  $$('.reveal').forEach(el=>observer.observe(el));

  setupNavigation();
  updateActiveNav();
  loadData().catch(err=>{
    console.error(err);
    document.body.insertAdjacentHTML('afterbegin','<div style="padding:11px 14px;background:#0d4638;color:#fff;text-align:center;font-size:11px">Impossible de charger les données.</div>');
  });
})();
