/* Dessin filaire SVG du portique — mis à jour en temps réel */

/* Caractéristiques des profilés IPE (h, tf, Iy) — chargées depuis business/IPE.csv
   via /api/ipe-sections (seule source de vérité, cf. lecture_ipe_csv.py) */
let IPE_SECTIONS = {};
let IPE_TF_RANGE = { min: Infinity, max: -Infinity };

async function loadIPESections() {
  try {
    const r = await fetch('/api/ipe-sections');
    IPE_SECTIONS = await r.json();
    IPE_TF_RANGE = Object.values(IPE_SECTIONS).reduce((r, d) => ({
      min: Math.min(r.min, d.tf), max: Math.max(r.max, d.tf),
    }), { min: Infinity, max: -Infinity });
  } catch (e) {
    IPE_SECTIONS = {};
  }
  refreshPortique();
}

function parseIPE(label) {
  if (!label) return null;
  const trimmed = label.trim();
  if (IPE_SECTIONS[trimmed]) return IPE_SECTIONS[trimmed];
  const m = trimmed.match(/(\d+)/);
  return m ? (IPE_SECTIONS['IPE ' + m[1]] || null) : null;
}

/* Épaisseur de trait (px) de la semelle, proportionnelle à tf (épaisseur d'aile réelle) */
function flangeStrokeWidth(dim) {
  if (!dim) return 1.4;
  const { min, max } = IPE_TF_RANGE;
  if (!(max > min)) return 1.4;
  const t = (dim.tf - min) / (max - min);
  return 1.2 + 2.8 * Math.max(0, Math.min(1, t));
}

/* Lignes d'aile haute/basse + âme d'un rampant, offset perpendiculaire à a→b.
   "upper"/"lower" sont toujours orientées haut/bas visuellement (y croissant vers le bas),
   quel que soit le sens de parcours a→b (rampant gauche ou droit). */
function railLines(a, b, thick) {
  const dx = b[0]-a[0], dy = b[1]-a[1];
  const L  = Math.sqrt(dx*dx + dy*dy);
  let nx = -dy/L * thick/2, ny = dx/L * thick/2;
  if (ny < 0) { nx = -nx; ny = -ny; }  // "lower" toujours vers le bas
  return {
    lower:  [[a[0]+nx, a[1]+ny], [b[0]+nx, b[1]+ny]],
    upper:  [[a[0]-nx, a[1]-ny], [b[0]-nx, b[1]-ny]],
    center: [a, b],
  };
}

/* Repousse le point a le long de a→b jusqu'à ce que x atteigne faceX */
function clipToFaceX(a, b, faceX, side) {
  const beyond = side === 'min' ? a[0] < faceX : a[0] > faceX;
  if (!beyond || b[0] === a[0]) return a;
  const t = (faceX - a[0]) / (b[0] - a[0]);
  return [faceX, a[1] + (b[1]-a[1]) * t];
}

/* Ordonnée d'une droite (p0,p1) à l'abscisse x (extrapolation incluse) */
function lineYAtX(p0, p1, x) {
  if (p1[0] === p0[0]) return p0[1];
  const t = (x - p0[0]) / (p1[0] - p0[0]);
  return p0[1] + (p1[1]-p0[1]) * t;
}

/* Jarret d'about : triangle raidisseur sous l'aile inférieure du rampant, au nœud avec le
   poteau. under→tip est la zone de contact avec le rampant (reste à l'épaisseur de trait
   normale) ; below→tip est la face inférieure du jarret, retournée séparément pour être
   tracée un peu plus épaisse (à l'épaisseur du rampant). "below" descend à la verticale
   depuis "under" (et non perpendiculairement au rampant) pour rester au contact du
   parement du poteau même avec des pentes fortes. La normale est toujours orientée vers
   le bas, quel que soit le sens de parcours a→b. */
function jarretGeom(a, b, thick, faceX, side) {
  const dx = b[0]-a[0], dy = b[1]-a[1];
  const L  = Math.sqrt(dx*dx + dy*dy);
  const ux = dx/L, uy = dy/L;
  let nx = -dy/L * thick/2, ny = dx/L * thick/2;
  if (ny < 0) { nx = -nx; ny = -ny; }  // toujours vers le bas, indépendamment du sens a→b
  const under = clipToFaceX([a[0]+nx, a[1]+ny], [b[0]+nx, b[1]+ny], faceX, side);
  const below = [under[0], under[1] + thick*1.5];        // descend à la verticale, reste au poteau
  const tipDist = 0.22 * L;
  const tip = [under[0] + ux*tipDist, under[1] + uy*tipDist]; // 22% depuis la base dessinée
  return { under, below, tip };
}

/* ── SVG ── */
function drawPortique(opts) {
  const svg = document.getElementById('portique-svg');
  if (!svg) return;

  const W = 560, H = 250;
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);

  const ML = 104, MR = 108, MT = 32, MB = 44;
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
  const scale  = Math.min(scaleX, scaleY) * 0.94;

  const bot = H - MB;

  /* Points du portique avant */
  const bl  = [ML,                    bot];
  const br  = [ML + portee * scale,   bot];
  const tl  = [ML,                    bot - hpot   * scale];
  const tr  = [ML + portee * scale,   bot - hpot   * scale];
  const ri  = [ML + portee/2 * scale, bot - h_faite * scale];

  function ln(a, b, cls, extra='') {
    return `<line x1="${a[0].toFixed(1)}" y1="${a[1].toFixed(1)}" x2="${b[0].toFixed(1)}" y2="${b[1].toFixed(1)}" class="${cls}" ${extra}/>`;
  }
  function fmtM(v) {
    return v.toFixed(2).replace('.', ',') + ' m';
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
  /* Cote parallèle à un segment (p0,p1), décalée horizontalement de offsetX : les ticks
     restent ainsi alignés sur la hauteur des points d'origine (axes horizontaux des pieds
     de portique), tout en gardant la ligne de cote parallèle au segment d'origine. */
  function dimPar(p0, p1, offsetX, label) {
    const ddx = p1[0]-p0[0], ddy = p1[1]-p0[1];
    const o0 = [p0[0]+offsetX, p0[1]];
    const o1 = [p1[0]+offsetX, p1[1]];
    const tick = 4;
    const mx = (o0[0]+o1[0])/2, my = (o0[1]+o1[1])/2;
    const ang = Math.atan2(ddy, ddx) * 180 / Math.PI;
    return `
      <line x1="${o0[0].toFixed(1)}" y1="${o0[1].toFixed(1)}" x2="${o1[0].toFixed(1)}" y2="${o1[1].toFixed(1)}" class="dim-line"/>
      <line x1="${(o0[0]-tick).toFixed(1)}" y1="${o0[1].toFixed(1)}" x2="${(o0[0]+tick).toFixed(1)}" y2="${o0[1].toFixed(1)}" class="dim-tick"/>
      <line x1="${(o1[0]-tick).toFixed(1)}" y1="${o1[1].toFixed(1)}" x2="${(o1[0]+tick).toFixed(1)}" y2="${o1[1].toFixed(1)}" class="dim-tick"/>
      <text x="${mx.toFixed(1)}" y="${(my-4).toFixed(1)}" class="dim-text"
            transform="rotate(${ang.toFixed(1)},${mx.toFixed(1)},${my.toFixed(1)})">${label}</text>`;
  }

  /* Sections IPE : poteau/traverse post-calcul, acrotère fixé en IPE 100 */
  const dim_p = parseIPE(opts.poteau);
  const dim_t = parseIPE(opts.traverse);
  const dim_a = IPE_SECTIONS['IPE 100'] || null;
  const sw_p  = dim_p ? dim_p.h * scale / 1000 : 0;  // épaisseur poteau en px
  const sw_t  = dim_t ? dim_t.h * scale / 1000 : 0;  // épaisseur traverse en px
  const sw_a  = dim_a ? dim_a.h * scale / 1000 : 0;  // épaisseur acrotère en px
  const stroke_p = flangeStrokeWidth(dim_p);  // épaisseur de trait ~ tf du poteau
  const stroke_t = flangeStrokeWidth(dim_t);  // épaisseur de trait ~ tf de la traverse
  const stroke_a = flangeStrokeWidth(dim_a);  // épaisseur de trait ~ tf de l'acrotère
  const faceL = bl[0] - sw_p/2, faceR = br[0] + sw_p/2;          // parements extérieurs des poteaux
  const faceLi = bl[0] + sw_p/2, faceRi = br[0] - sw_p/2;        // parements intérieurs des poteaux
  const showDetailP = sw_p > 0;
  const showDetailT = sw_t > 0;
  const showKnee = showDetailP && showDetailT;   // jonction poteau/rampant détaillée
  /* Acrotères alignés sur le parement extérieur du poteau (pas sur son axe) */
  const acroCxL = faceL + sw_a/2, acroCxR = faceR - sw_a/2;

  /* Jonction poteau/rampant : les semelles du poteau montent jusqu'à la projection de la
     semelle supérieure du rampant (qui n'est pas coupée par le poteau) ; la semelle
     inférieure du rampant et le jarret s'arrêtent sur le parement intérieur du poteau. */
  let railL = null, railR = null;
  let topExtL = null, topIntL = null, topCL = null;
  let topExtR = null, topIntR = null, topCR = null;
  if (showKnee) {
    railL = railLines(tl, ri, sw_t);
    railR = railLines(tr, ri, sw_t);
    topExtL = lineYAtX(railL.upper[0], railL.upper[1], faceL);
    topIntL = lineYAtX(railL.upper[0], railL.upper[1], faceLi);
    topCL   = lineYAtX(railL.upper[0], railL.upper[1], bl[0]);
    topExtR = lineYAtX(railR.upper[0], railR.upper[1], faceR);
    topIntR = lineYAtX(railR.upper[0], railR.upper[1], faceRi);
    topCR   = lineYAtX(railR.upper[0], railR.upper[1], br[0]);
  }
  const showDetailA = h_acro > 0 && showKnee && sw_a > 0;
  /* Base de l'acrotère : posée sur la toiture (parement extérieur), sinon niveau du nœud */
  const acroBaseYL = showKnee ? topExtL : tl[1];
  const acroBaseYR = showKnee ? topExtR : tr[1];
  const tla = [tl[0], acroBaseYL - h_acro * scale];  // sommet acrotère gauche
  const tra = [tr[0], acroBaseYR - h_acro * scale];  // sommet acrotère droit

  /* Portique arrière (perspective) */
  function bk(p) { return [p[0]+dx, p[1]+dy]; }
  const bbl = bk(bl), bbr = bk(br), btl = bk(tl), btr = bk(tr),
        bri = bk(ri), btla = bk(tla), btra = bk(tra);

  /* ── Construction SVG ── */
  let h = `<defs>
    <style>
      .ff  { stroke:#1a5fa8; stroke-width:2.5; fill:none; stroke-linejoin:round }
      .fb  { stroke:#9ab4cc; stroke-width:1.5; fill:none; stroke-dasharray:6,4; stroke-linejoin:round }
      .fp  { stroke:#aaa;    stroke-width:1;   stroke-dasharray:4,4; fill:none }
      .fg  { stroke:#bbb;    stroke-width:1;   stroke-dasharray:8,4; fill:none }
      .axis { stroke:#888;   stroke-width:0.75; stroke-dasharray:10,3,2,3; fill:none }
      .sf  { fill:rgba(26,95,168,0.10); stroke:none }
      .sflange { stroke:#1a5fa8; stroke-linecap:round; fill:none }
      .sweb    { stroke:#1a5fa8; stroke-width:0.8; stroke-opacity:0.4; fill:none }
      .jarret  { fill:rgba(26,95,168,0.30); stroke:#1a5fa8; stroke-width:1 }
      .dim-line { stroke:#888; stroke-width:1 }
      .dim-tick { stroke:#888; stroke-width:1 }
      .dim-text { font-size:13px; fill:#555; text-anchor:middle; font-family:sans-serif }
      .slabel   { font-size:13px; fill:#c0392b; font-weight:bold; font-family:sans-serif }
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

  /* 3 — Axes de structure (traits mixtes fins), un par poteau */
  const axisTop = Math.min(tla[1], tl[1]) - 14;
  h += ln([bl[0], bot + 10], [bl[0], axisTop], 'axis');
  h += ln([br[0], bot + 10], [br[0], axisTop], 'axis');

  /* 4 — Remplissages + schéma aile/âme des sections (dessinés AVANT les traits de structure) */
  if (showKnee) {
    /* Poteaux : semelles remontant jusqu'à la semelle supérieure du rampant */
    h += `<polygon points="${[[faceL,bl[1]],[faceL,topExtL],[faceLi,topIntL],[faceLi,bl[1]]]
                .map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')}" class="sf"/>`;
    h += `<polygon points="${[[faceR,br[1]],[faceR,topExtR],[faceRi,topIntR],[faceRi,br[1]]]
                .map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')}" class="sf"/>`;
    h += ln([faceL, bl[1]], [faceL, topExtL], 'sflange', `stroke-width="${stroke_p.toFixed(2)}"`);
    h += ln([faceLi, bl[1]], [faceLi, topIntL], 'sflange', `stroke-width="${stroke_p.toFixed(2)}"`);
    h += ln([bl[0], bl[1]], [bl[0], topCL], 'sweb');
    h += ln([faceR, br[1]], [faceR, topExtR], 'sflange', `stroke-width="${stroke_p.toFixed(2)}"`);
    h += ln([faceRi, br[1]], [faceRi, topIntR], 'sflange', `stroke-width="${stroke_p.toFixed(2)}"`);
    h += ln([br[0], br[1]], [br[0], topCR], 'sweb');

    /* Rampants : semelle supérieure non coupée (jusqu'au parement extérieur), semelle
       inférieure + âme coupées au parement intérieur du poteau */
    const upperStartL = [faceL, topExtL], upperStartR = [faceR, topExtR];
    const lowerL  = clipToFaceX(railL.lower[0],  railL.lower[1],  faceLi, 'min');
    const centerL = clipToFaceX(railL.center[0], railL.center[1], faceLi, 'min');
    const lowerR  = clipToFaceX(railR.lower[0],  railR.lower[1],  faceRi, 'max');
    const centerR = clipToFaceX(railR.center[0], railR.center[1], faceRi, 'max');

    h += `<polygon points="${[upperStartL, railL.upper[1], railL.lower[1], lowerL]
                .map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')}" class="sf"/>`;
    h += `<polygon points="${[upperStartR, railR.upper[1], railR.lower[1], lowerR]
                .map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')}" class="sf"/>`;
    h += ln(upperStartL, railL.upper[1], 'sflange', `stroke-width="${stroke_t.toFixed(2)}"`);
    h += ln(lowerL, railL.lower[1], 'sflange', `stroke-width="${stroke_t.toFixed(2)}"`);
    h += ln(centerL, railL.center[1], 'sweb');
    h += ln(upperStartR, railR.upper[1], 'sflange', `stroke-width="${stroke_t.toFixed(2)}"`);
    h += ln(lowerR, railR.lower[1], 'sflange', `stroke-width="${stroke_t.toFixed(2)}"`);
    h += ln(centerR, railR.center[1], 'sweb');

    /* Jarret d'about aux nœuds rampant/poteau, arrêté au parement intérieur du poteau ;
       la semelle (under→tip) est tracée à l'épaisseur de trait du rampant */
    const jarretL = jarretGeom(tl, ri, sw_t, faceLi, 'min');
    const jarretR = jarretGeom(tr, ri, sw_t, faceRi, 'max');
    h += `<polygon points="${[jarretL.under, jarretL.below, jarretL.tip]
                .map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')}" class="jarret"/>`;
    h += `<polygon points="${[jarretR.under, jarretR.below, jarretR.tip]
                .map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')}" class="jarret"/>`;
    h += ln(jarretL.below, jarretL.tip, 'sflange', `stroke-width="${stroke_t.toFixed(2)}"`);
    h += ln(jarretR.below, jarretR.tip, 'sflange', `stroke-width="${stroke_t.toFixed(2)}"`);
  }
  if (showDetailA) {
    h += ln([acroCxL-sw_a/2, acroBaseYL], [acroCxL-sw_a/2, tla[1]], 'sflange', `stroke-width="${stroke_a.toFixed(2)}"`);
    h += ln([acroCxL+sw_a/2, acroBaseYL], [acroCxL+sw_a/2, tla[1]], 'sflange', `stroke-width="${stroke_a.toFixed(2)}"`);
    h += ln([acroCxL, acroBaseYL], [acroCxL, tla[1]], 'sweb');
    h += ln([acroCxR-sw_a/2, acroBaseYR], [acroCxR-sw_a/2, tra[1]], 'sflange', `stroke-width="${stroke_a.toFixed(2)}"`);
    h += ln([acroCxR+sw_a/2, acroBaseYR], [acroCxR+sw_a/2, tra[1]], 'sflange', `stroke-width="${stroke_a.toFixed(2)}"`);
    h += ln([acroCxR, acroBaseYR], [acroCxR, tra[1]], 'sweb');
  }

  /* 5 — Sol avant — tirets gris (non structurel) */
  h += ln(bl, br, 'fg');

  /* 6 — Structure (traits pleins bleus) : seulement pour les éléments dont la section
     détaillée n'est pas encore affichée (évite de superposer filaire + schéma aile/âme) */
  if (!showDetailP) {
    h += ln(bl, tl, 'ff');
    h += ln(br, tr, 'ff');
  }
  if (!showDetailT) {
    h += ln(tl, ri, 'ff');
    h += ln(tr, ri, 'ff');
  }
  if (h_acro > 0 && !showDetailA) {
    h += ln(tl, tla, 'ff');
    h += ln(tr, tra, 'ff');
  }

  /* 7 — Cotes */
  /* cote de portée */
  h += dimH(bl[0], br[0], bot+28, fmtM(portee));
  /* cote de hauteur poteau + acrotère */
  const dimX = faceL - 32;
  h += dimV(dimX, tl[1], bl[1], fmtM(hpot));
  if (h_acro > 0.01) {
    h += dimV(dimX, tla[1], tl[1], fmtM(h_acro));
  }
  /* cote d'entraxe — à droite, parallèle à la ligne de fuite 3D */
  h += dimPar(br, bbr, 40, fmtM(entraxe));

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

  /* 8 — Labels de sections (post-calcul) */
  if (opts.poteau) {
    /* Poteau gauche : à l'intérieur du portique */
    const lx = faceLi + 18;
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

let lastExtra = null;
function refreshPortique(extra) {
  if (extra) lastExtra = extra;
  drawPortique(getGeomValues(extra || lastExtra));
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

/* ── Messages de validation HTML5 en français ──
   Par défaut, le navigateur affiche ses propres messages ("Please fill out this
   field", etc.) dans la langue de son interface, indépendamment de la langue de la
   page. On les remplace ici par des messages français, adaptés au type d'erreur. */
function frenchValidationMessage(el) {
  const v = el.validity;
  /* badInput (texte non numérique) doit être testé avant valueMissing : un champ
     number avec un texte illisible ("1e", "-", …) a un .value vide, donc
     valueMissing est aussi vrai — mais le diagnostic le plus juste est badInput. */
  if (v.badInput) return 'Veuillez entrer un nombre.';
  if (v.typeMismatch) return 'Veuillez entrer une valeur valide.';
  if (v.valueMissing)   return el.tagName === 'SELECT' ? 'Veuillez sélectionner une option dans la liste.' : 'Veuillez remplir ce champ.';
  if (v.rangeUnderflow) return `La valeur doit être supérieure ou égale à ${el.min}.`;
  if (v.rangeOverflow)  return `La valeur doit être inférieure ou égale à ${el.max}.`;
  if (v.stepMismatch)   return `La valeur doit être un multiple de ${el.step}.`;
  return 'Valeur invalide.';
}

function updateFrenchValidity(el) {
  /* on réévalue à partir de zéro : un customValidity déjà posé fausserait
     validity.valid (il la force à false), il faut donc l'effacer d'abord */
  el.setCustomValidity('');
  if (!el.validity.valid) el.setCustomValidity(frenchValidationMessage(el));
}

function frenchifyFormValidation(form) {
  form.querySelectorAll('input, select, textarea').forEach((el) => {
    /* "invalid" seul ne suffit pas : le message natif d'un nombre mal formé
       ("Please enter a number") s'affiche en direct pendant la saisie, avant
       tout appel à reportValidity() — il faut donc aussi réagir à "input". */
    el.addEventListener('input', () => updateFrenchValidity(el));
    el.addEventListener('change', () => updateFrenchValidity(el));
    el.addEventListener('invalid', () => updateFrenchValidity(el));
  });
}

document.addEventListener('DOMContentLoaded', () => {
  ['hpot','portee','pente_pct','entraxe','h_acro'].forEach(id => {
    document.getElementById(id)?.addEventListener('input', () => refreshPortique());
  });
  refreshPortique();
  loadIPESections();

  const mainForm = document.querySelector('form[hx-post]');
  if (mainForm) frenchifyFormValidation(mainForm);

  document.body.addEventListener('htmx:before-request', (e) => {
    if (e.detail.elt === document.querySelector('form[hx-post]')) validateGeo(e);
  });
});

/* Appelé depuis result_partial après le calcul */
function updatePortiqueAfterCalc(poteau, traverse) {
  refreshPortique({ poteau, traverse });
}
