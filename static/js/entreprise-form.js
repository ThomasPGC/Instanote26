/* Aide à la saisie de l'identité professionnelle — partagé par le formulaire
   d'inscription (/auth/register) et la page profil (/compte).

   Attendus dans le DOM (tous facultatifs, le script est défensif) :
     #siret               input SIRET            -> vérif live au blur
     #siret-feedback      zone de message sous le champ SIRET
     #entreprise          input raison sociale   (pré-rempli depuis le SIRET si vide)
     #numero #rue #complement #code_postal #ville  champs adresse
     #rue-suggestions     conteneur des suggestions de voie (API BAN)
     #commune-select      <select> des communes du code postal
     #commune-help        message sous le code postal
     #citycode            input hidden : code INSEE, sert à scoper l'autocomplétion de voie
     #adresse-note        message "adresse pré-remplie depuis Sirene"

   Endpoints : /htmx/siret-info, /htmx/communes, /htmx/rue-search
   (app/routers/entreprise.py). La vérification qui fait foi est refaite côté
   serveur au submit. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);

  function debounce(fn, ms) {
    let t;
    return function () { clearTimeout(t); t = setTimeout(fn, ms); };
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }
  function feedback(el, cls, html) {
    if (!el) return;
    el.className = "form-text " + cls;
    el.innerHTML = html;
  }
  function digits(s) { return (s || "").replace(/\D/g, ""); }
  function setCitycode(v) { const el = $("citycode"); if (el) el.value = v || ""; }

  /* ---- SIRET ---------------------------------------------------------- */
  async function checkSiret() {
    const input = $("siret");
    const fb = $("siret-feedback");
    if (!input) return;
    const raw = digits(input.value);
    input.classList.remove("is-invalid", "is-valid");
    if (raw.length === 0) { feedback(fb, "text-muted", ""); return; }
    if (raw.length !== 14) {
      input.classList.add("is-invalid");
      feedback(fb, "text-danger", "Le SIRET doit comporter 14 chiffres.");
      return;
    }
    feedback(fb, "text-muted",
      '<span class="spinner-border spinner-border-sm me-1"></span>Vérification…');
    let data;
    try {
      const r = await fetch("/htmx/siret-info?siret=" + raw);
      data = await r.json();
    } catch (e) {
      feedback(fb, "text-warning",
        "Vérification indisponible pour le moment (l'inscription reste possible).");
      return;
    }
    if (data.status === "ok") {
      input.classList.add("is-valid");
      feedback(fb, "text-success",
        "✓ " + (data.raison_sociale ? esc(data.raison_sociale) : "Établissement en activité"));
      const ent = $("entreprise");
      if (ent && !ent.value && data.raison_sociale) ent.value = data.raison_sociale;
      if (data.adresse) fillAddress(data.adresse);
    } else if (data.status === "closed") {
      input.classList.add("is-invalid");
      feedback(fb, "text-danger",
        "✗ Établissement fermé ou entreprise radiée : utilisez un établissement en activité.");
    } else if (data.status === "not_found") {
      input.classList.add("is-invalid");
      feedback(fb, "text-danger", "✗ SIRET introuvable dans la base Sirene.");
    } else {
      feedback(fb, "text-warning",
        "Vérification indisponible pour le moment (l'inscription reste possible).");
    }
  }

  function fillAddress(a) {
    const set = (id, v) => { const el = $(id); if (el && v) el.value = v; };
    set("numero", a.numero);
    set("rue", a.rue);
    set("complement", a.complement);
    set("code_postal", a.code_postal);
    set("ville", a.ville);
    const note = $("adresse-note");
    if (note) {
      note.textContent = "Adresse pré-remplie depuis la base Sirene — ajustez si besoin.";
      note.hidden = false;
    }
    if (a.code_postal) lookupCommunes();
  }

  /* ---- Code postal -> communes -------------------------------------- */
  async function lookupCommunes() {
    const cpEl = $("code_postal");
    const sel = $("commune-select");
    const help = $("commune-help");
    const villeEl = $("ville");
    if (!cpEl) return;
    const cp = digits(cpEl.value);
    if (cp.length !== 5) {
      if (sel) sel.hidden = true;
      setCitycode("");
      return;
    }
    let list = [];
    try {
      const r = await fetch("/htmx/communes?code_postal=" + cp);
      list = await r.json();
    } catch (e) { list = []; }

    if (!list.length) {
      if (sel) sel.hidden = true;
      setCitycode("");
      if (help) {
        help.textContent = "Aucune commune trouvée pour ce code postal — saisissez la ville manuellement.";
        help.hidden = false;
      }
      return;
    }
    if (help) help.hidden = true;
    if (sel) {
      sel.innerHTML = '<option value="">— choisir la commune —</option>' +
        list.map((c) => '<option value="' + esc(c.code) + '" data-nom="' + esc(c.nom) + '">' +
          esc(c.nom) + "</option>").join("");
      sel.hidden = false;
    }
    if (list.length === 1) {
      if (sel) sel.value = list[0].code;
      if (villeEl && !villeEl.value) villeEl.value = list[0].nom;
      setCitycode(list[0].code);
    } else if (villeEl && villeEl.value) {
      const m = list.find((c) => c.nom.toLowerCase() === villeEl.value.trim().toLowerCase());
      if (m) { if (sel) sel.value = m.code; setCitycode(m.code); }
    }
  }

  function onCommuneSelect() {
    const sel = $("commune-select");
    const villeEl = $("ville");
    const opt = sel && sel.selectedOptions[0];
    if (opt && opt.value) {
      if (villeEl) villeEl.value = opt.dataset.nom || opt.textContent;
      setCitycode(opt.value);
    }
  }

  /* ---- Rue : autocomplétion BAN ------------------------------------- */
  const searchRue = debounce(async function () {
    const rueEl = $("rue");
    const box = $("rue-suggestions");
    if (!rueEl || !box) return;
    const q = rueEl.value.trim();
    if (q.length < 3) { box.innerHTML = ""; return; }
    const cc = ($("citycode") || {}).value || "";
    let list = [];
    try {
      const r = await fetch("/htmx/rue-search?q=" + encodeURIComponent(q) +
        "&citycode=" + encodeURIComponent(cc));
      list = await r.json();
    } catch (e) { list = []; }
    if (!list.length) { box.innerHTML = ""; return; }
    box.innerHTML = list.map((x) =>
      '<button type="button" class="list-group-item list-group-item-action py-1 px-2 small">' +
      esc(x.name) + (x.city ? ' <span class="text-muted">— ' + esc(x.city) + "</span>" : "") +
      "</button>").join("");
    box.querySelectorAll("button").forEach((b, i) => b.addEventListener("click", () => {
      $("rue").value = list[i].name;
      box.innerHTML = "";
    }));
  }, 300);

  /* ---- Init (idempotent, rejoué après les swaps HTMX de /compte) ---- */
  function init() {
    const siret = $("siret");
    if (!siret || siret.dataset.efInit) return;
    siret.dataset.efInit = "1";

    siret.addEventListener("blur", checkSiret);
    siret.addEventListener("input", debounce(() => {
      if (digits(siret.value).length === 14) checkSiret();
    }, 400));

    const cp = $("code_postal");
    if (cp) {
      cp.addEventListener("blur", lookupCommunes);
      cp.addEventListener("input", debounce(lookupCommunes, 500));
    }
    const sel = $("commune-select");
    if (sel) sel.addEventListener("change", onCommuneSelect);

    const rue = $("rue");
    if (rue) rue.addEventListener("input", searchRue);
    document.addEventListener("click", (e) => {
      const box = $("rue-suggestions");
      if (box && !box.contains(e.target) && e.target !== $("rue")) box.innerHTML = "";
    });

    // /compte : un SIRET / CP déjà enregistré -> initialiser citycode + communes
    if (cp && cp.value) lookupCommunes();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
  document.body.addEventListener("htmx:afterSwap", init);
})();
