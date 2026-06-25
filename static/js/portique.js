/* Dessin filaire SVG du portique — mis à jour en temps réel */

const IPE_DIM = {
  80:  {h:80,  b:46},  100: {h:100, b:55},  120: {h:120, b:64},
  140: {h:140, b:73},  160: {h:160, b:82},  180: {h:180, b:91},
  200: {h:200, b:100}, 220: {h:220, b:110}, 240: {h:240, b:120},
  270: {h:270, b:135}, 300: {h:300, b:150}, 330: {h:330, b:160},
  360: {h:360, b:170}, 400: {h:400, b:180}, 450: {h:450, b:190},
  500: {h:500, b:200}, 550: {h:550, b:210}, 600: {h:600, b:220},
};

function parseIPE(label) {
  if (!label) return null;
  const m = label.match(/(\d+)/);
  return m ? (IPE_DIM[parseInt(m[1])] || null) : null;
}

/* Retourne le polygone SVG d'un élément en remplissage à l'épaisseur thick (px) */
function rafterPoly(a, b, thick) {
  const dx = b[0]-a[0], dy = b[1]-a[1];
  const L  = Math.sqrt(dx*dx + dy*dy);
  /* Normale interne : perpendiculaire +90° du vecteur a→b
     Pour l'arbalétrier gauche (tl→ri), ça pointe vers l'intérieur du portique */
  const nx = -dy/L * thick/2, ny = dx/L * thick/2;
  return [
    [a[0]+nx, a[1]+ny],
    [b[0]+nx, b[1]+ny],
    [b[0]-nx, b[1]-ny],
    [a[0]-nx, a[1]-ny],
  ].map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
}

/* ── SVG ── */
function drawPortique(opts) {
  const svg = document.getElementById('portique-svg');
  if (!svg) return;

  const W = 560, H = 340;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);

  const ML = 76, MR = 52, MT = 44, MB = 50;
  const drawW = W - ML - MR;
  const drawH = H - MT - MB;

  const hpot    = parseFloat(opts.hpot)    || 3.5;
  const portee  = parseFloat(opts.portee)  || 12;
  const pente   = parseFloat(opts.pente)   || 10;
  const entraxe = parseFloat(opts.entraxe) || 5;
  const h_acro  = parseFloat(opts.h_acro)  || 0;

  const h_faite = hpot + (portee / 2) * (pente / 100);
  /* hauteur de référence pour l'échelle : max(faîtage, poteau + acrotère) */
  const h_ref = Math.max(h_faite, hpot + h_acro);

  /* perspective axonométrique */
  const PERSP = 0.38;
  const e_draw = Math.min(entraxe, portee * 0.5);
  const dx = e_draw * PERSP * 0.7 * (drawW / (portee + e_draw * PERSP));
  const dy = -e_draw * PERSP * 0.4 * (drawH / h_ref);

  const scaleX = (drawW - dx)         / portee;
  const scaleY = (drawH - Math.abs(dy)) / h_ref;
  const scale  = Math.min(scaleX, scaleY) * 0.90;

  const bot = H - MB;

  /* Points du portique avant */
  const bl  = [ML,                    bot];
  const br  = [ML + portee * scale,   bot];
  const tl  = [ML,                    bot - hpot   * scale];
  const tr  = [ML + portee * scale,   bot - hpot   * scale];
  const ri  = [ML + portee/2 * scale, bot - h_faite * scale];
  const tla = [tl[0], tl[1] - h_acro * scale];  // sommet acrotère gauche
  const tra = [tr[0], tr[1] - h_acro * scale];  // sommet acrotère droit

  /* Portique arrière (perspective) */
  function bk(p) { return [p[0]+dx, p[1]+dy]; }
  const bbl = bk(bl), bbr = bk(br), btl = bk(tl), btr = bk(tr),
        bri = bk(ri), btla = bk(tla), btra = bk(tra);

  function ln(a, b, cls, extra='') {
    return `<line x1="${a[0].toFixed(1)}" y1="${a[1].toFixed(1)}" x2="${b[0].toFixed(1)}" y2="${b[1].toFixed(1)}" class="${cls}" ${extra}/>`;
  }
  function dimH(x1, x2, y, label) {
    const mx = (x1+x2)/2;
    return `<line x1="${x1}" y1="${y}" x2="${x2}" y2="${y}" class="dim-line"/>
            <line x1="${x1}" y1="${y-4}" x2="${x1}" y2="${y+4}" class="dim-tick"/>
            <line x1="${x2}" y1="${y-4}" x2="${x2}" y2="${y+4}" class="dim-tick"/>
            <text x="${mx}" y="${y+13}" class="dim-text">${label}</text>`;
  }
  function dimV(x, y1, y2, label) {
    const my = (y1+y2)/2;
    return `<line x1="${x}" y1="${y1}" x2="${x}" y2="${y2}" class="dim-line"/>
            <line x1="${x-4}" y1="${y1}" x2="${x+4}" y2="${y1}" class="dim-tick"/>
            <line x1="${x-4}" y1="${y2}" x2="${x+4}" y2="${y2}" class="dim-tick"/>
            <text x="${x-8}" y="${my+4}" class="dim-text" text-anchor="end">${label}</text>`;
  }

  /* Sections IPE (post-calcul) */
  const dim_p = parseIPE(opts.poteau);
  const dim_t = parseIPE(opts.traverse);
  const sw_p  = dim_p ? dim_p.h * scale / 1000 : 0;  // épaisseur poteau en px
  const sw_t  = dim_t ? dim_t.h * scale / 1000 : 0;  // épaisseur traverse en px

  /* ── Construction SVG ── */
  let h = `<defs>
    <style>
      .ff  { stroke:#1a5fa8; stroke-width:2.5; fill:none; stroke-linejoin:round }
      .fb  { stroke:#9ab4cc; stroke-width:1.5; fill:none; stroke-dasharray:6,4; stroke-linejoin:round }
      .fp  { stroke:#aaa;    stroke-width:1;   stroke-dasharray:4,4; fill:none }
      .fg  { stroke:#bbb;    stroke-width:1;   stroke-dasharray:8,4; fill:none }
      .sf  { fill:rgba(26,95,168,0.14); stroke:#1a5fa8; stroke-width:0.8 }
      .dim-line { stroke:#888; stroke-width:1 }
      .dim-tick { stroke:#888; stroke-width:1 }
      .dim-text { font-size:11px; fill:#555; text-anchor:middle; font-family:sans-serif }
      .slabel   { font-size:11px; fill:#c0392b; font-weight:bold; font-family:sans-serif }
    </style>
    <marker id="arr" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
      <polygon points="0,0 7,3.5 0,7" fill="#888"/>
    </marker>
  </defs>`;

  /* 1 — Portique arrière (tiretés) */
  h += ln(bbl, bbr, 'fg');               // sol arrière — tirets gris
  h += ln(bbl, btl, 'fb');
  h += ln(bbr, btr, 'fb');
  h += ln(btl, bri, 'fb');
  h += ln(btr, bri, 'fb');
  if (h_acro > 0) {
    h += ln(btl, btla, 'fb');
    h += ln(btr, btra, 'fb');
  }

  /* 2 — Connecteurs de perspective */
  [[bl,bbl],[br,bbr],[tl,btl],[tr,btr],[ri,bri]].forEach(([f,b]) => h += ln(f,b,'fp'));
  if (h_acro > 0) {
    h += ln(tla, btla, 'fp');
    h += ln(tra, btra, 'fp');
  }

  /* 3 — Remplissages des sections (dessinés AVANT les traits de structure) */
  if (sw_p > 0) {
    h += `<rect x="${(bl[0]-sw_p/2).toFixed(1)}" y="${tl[1].toFixed(1)}"
               width="${sw_p.toFixed(1)}" height="${(bl[1]-tl[1]).toFixed(1)}" class="sf"/>`;
    h += `<rect x="${(br[0]-sw_p/2).toFixed(1)}" y="${tr[1].toFixed(1)}"
               width="${sw_p.toFixed(1)}" height="${(br[1]-tr[1]).toFixed(1)}" class="sf"/>`;
  }
  if (sw_t > 0) {
    h += `<polygon points="${rafterPoly(tl, ri, sw_t)}" class="sf"/>`;
    h += `<polygon points="${rafterPoly(tr, ri, sw_t)}" class="sf"/>`;
  }

  /* 4 — Sol avant — tirets gris (non structurel) */
  h += ln(bl, br, 'fg');

  /* 5 — Structure avant (traits pleins bleus) */
  h += ln(bl, tl, 'ff');
  h += ln(br, tr, 'ff');
  h += ln(tl, ri, 'ff');
  h += ln(tr, ri, 'ff');
  if (h_acro > 0) {
    h += ln(tl, tla, 'ff');
    h += ln(tr, tra, 'ff');
  }

  /* 6 — Cotes */
  /* cote de portée */
  h += dimH(bl[0], br[0], bot+28, `${portee.toFixed(2)} m`);
  /* cote de hauteur poteau */
  h += dimV(ML-32, tl[1], bl[1], `${hpot.toFixed(2)} m`);
  /* cote acrotère (si présent) */
  if (h_acro > 0.01) {
    h += dimV(ML-32, tla[1], tl[1], `${h_acro.toFixed(2)} m`);
  }

  /* entraxe label */
  {
    const ex  = (bl[0]+bbl[0])/2 + 4;
    const ey  = (bl[1]+bbl[1])/2 - 9;
    const ang = Math.atan2(bbl[1]-bl[1], bbl[0]-bl[0]) * 180 / Math.PI;
    h += `<text x="${ex.toFixed(1)}" y="${ey.toFixed(1)}" class="dim-text" text-anchor="start"
          transform="rotate(${ang.toFixed(1)},${ex.toFixed(1)},${ey.toFixed(1)})">${entraxe.toFixed(2)} m</text>`;
  }

  /* flèche de pente — au-dessus de l'arbalétrier gauche */
  {
    const ang_up = Math.atan2(ri[1]-tl[1], ri[0]-tl[0]);  // direction montante
    const ang_dn = ang_up + Math.PI;                        // direction descendante
    /* normale extérieure au rampant (au-dessus de la toiture) */
    const nx = Math.cos(ang_up - Math.PI/2);
    const ny = Math.sin(ang_up - Math.PI/2);
    /* décalage : section traverse + marge */
    const ofs = sw_t / 2 + 16;
    const t   = 0.45;
    const px  = tl[0] + (ri[0]-tl[0]) * t;
    const py  = tl[1] + (ri[1]-tl[1]) * t;
    const ax  = px + nx * ofs;
    const ay  = py + ny * ofs;
    const alen = 26;
    const asx = ax - Math.cos(ang_dn) * alen/2, asy = ay - Math.sin(ang_dn) * alen/2;
    const aex = ax + Math.cos(ang_dn) * alen/2, aey = ay + Math.sin(ang_dn) * alen/2;
    h += `<line x1="${asx.toFixed(1)}" y1="${asy.toFixed(1)}"
               x2="${aex.toFixed(1)}" y2="${aey.toFixed(1)}"
               stroke="#888" stroke-width="1.2" marker-end="url(#arr)"/>`;
    const ang_deg = ang_up * 180 / Math.PI;
    const lx = ax + nx * 11, ly = ay + ny * 11;
    h += `<text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" class="dim-text"
               transform="rotate(${ang_deg.toFixed(1)},${lx.toFixed(1)},${ly.toFixed(1)})">${pente.toFixed(0)} %</text>`;
  }

  /* 7 — Labels de sections (post-calcul) — DANS le portique, loin des cotes */
  if (opts.poteau) {
    /* Poteau gauche : à droite de l'axe, dans le portique */
    const lx = bl[0] + sw_p/2 + 18;
    const ly = (tl[1] + bl[1]) / 2;
    h += `<text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" class="slabel" text-anchor="middle"
              transform="rotate(-90,${lx.toFixed(1)},${ly.toFixed(1)})">${opts.poteau}</text>`;
  }
  if (opts.traverse) {
    /* Arbalétrier gauche : décalé vers l'intérieur du portique (sous le rampant) */
    const dx_r = ri[0]-tl[0], dy_r = ri[1]-tl[1];
    const Lr   = Math.sqrt(dx_r*dx_r + dy_r*dy_r);
    /* normale interne (vers l'intérieur = +90° de tl→ri) */
    const nx_in = -dy_r/Lr, ny_in = dx_r/Lr;
    const t_mid = 0.42;
    const mx = tl[0] + dx_r * t_mid;
    const my = tl[1] + dy_r * t_mid;
    const inner_ofs = sw_t/2 + 14;
    const lx = mx + nx_in * inner_ofs;
    const ly = my + ny_in * inner_ofs;
    const ta = Math.atan2(dy_r, dx_r) * 180 / Math.PI;
    h += `<text x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" class="slabel" text-anchor="middle"
              transform="rotate(${ta.toFixed(1)},${lx.toFixed(1)},${ly.toFixed(1)})">${opts.traverse}</text>`;
  }

  svg.innerHTML = h;
}

/* ── Accesseurs formulaire ── */
function getGeomValues(extra) {
  return Object.assign({
    hpot:    document.getElementById('hpot')?.value,
    portee:  document.getElementById('portee')?.value,
    pente:   document.getElementById('pente_pct')?.value,
    entraxe: document.getElementById('entraxe')?.value,
    h_acro:  document.getElementById('h_acro')?.value,
  }, extra || {});
}

function refreshPortique(extra) {
  drawPortique(getGeomValues(extra));
}

/* ── Géocodage ── */
function selectCommune(li) {
  const lat   = li.dataset.lat;
  const lon   = li.dataset.lon;
  const city  = li.dataset.city;
  const ctx   = li.dataset.context;
  const label = li.dataset.label;

  document.getElementById('adresse-search').value = label;
  document.getElementById('geo-suggestions')?.remove();

  const card = document.getElementById('localisation-card');
  card.innerHTML = '<div class="text-muted small"><span class="spinner-border spinner-border-sm me-1"></span>Récupération de l\'altitude…</div>';

  htmx.ajax('GET',
    `/htmx/geocode-fill?lat=${lat}&lon=${lon}&city=${encodeURIComponent(city)}&context=${encodeURIComponent(ctx)}`,
    { target: '#localisation-card', swap: 'innerHTML' }
  );
}

function resetGeoSearch() {
  const card = document.getElementById('localisation-card');
  card.innerHTML = `
    <input type="hidden" name="departement"     value="">
    <input type="hidden" name="nom_commune"     value="">
    <input type="hidden" name="ancien_nom_comm" value="">
    <input type="hidden" name="altitude"        value="0">
    <div class="text-muted small fst-italic">Aucune commune sélectionnée</div>`;
  document.getElementById('adresse-search').value = '';
  document.getElementById('adresse-search').focus();
}

/* ── Validation submit ── */
function validateGeo(e) {
  const dept = document.querySelector('#localisation-card input[name="departement"]');
  if (!dept || !dept.value.trim()) {
    e.preventDefault();
    const card = document.getElementById('localisation-card');
    if (!card.querySelector('.geo-error')) {
      const err = document.createElement('div');
      err.className = 'geo-error text-danger small mt-1';
      err.textContent = 'Veuillez sélectionner une commune dans la liste.';
      card.appendChild(err);
    }
    document.getElementById('adresse-search').focus();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  ['hpot','portee','pente_pct','entraxe','h_acro'].forEach(id => {
    document.getElementById(id)?.addEventListener('input', () => refreshPortique());
  });
  refreshPortique();

  document.body.addEventListener('htmx:before-request', (e) => {
    if (e.detail.elt === document.querySelector('form[hx-post]')) validateGeo(e);
  });
});

/* Appelé depuis result_partial après le calcul */
function updatePortiqueAfterCalc(poteau, traverse) {
  refreshPortique({ poteau, traverse });
}
