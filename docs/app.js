const PESO_REL = { alta: 0, media: 1, baixa: 2 };
const DIA = 86400000;
const estado = { cat: "", editais: [] };

const $ = (id) => document.getElementById(id);

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function hoje() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

function diasAte(prazo) {
  if (!prazo) return null;
  const [a, m, d] = prazo.split("-").map(Number);
  if (!a || !m || !d) return null;
  return Math.round((new Date(a, m - 1, d) - hoje()) / DIA);
}

function dataBR(iso) {
  if (!iso) return "";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${a}`;
}

function encerrado(e) {
  const dias = diasAte(e.prazo);
  return e.aberto === false || (dias !== null && dias < 0);
}

function linkSeguro(url) {
  return /^https?:\/\//i.test(url || "") ? url : null;
}

function cartao(e) {
  const dias = diasAte(e.prazo);
  const fechado = encerrado(e);
  const novo = e.primeiro_visto && (Date.now() - new Date(e.primeiro_visto)) < 7 * DIA;
  const link = linkSeguro(e.link);

  let prazo = "Prazo não informado";
  if (e.prazo) {
    prazo = `Prazo ${dataBR(e.prazo)}`;
    if (fechado) prazo += " · encerrado";
    else if (dias === 0) prazo += ' <span class="tag urgente">fecha hoje</span>';
    else if (dias <= 15) prazo += ` <span class="tag urgente">fecha em ${dias} dia${dias > 1 ? "s" : ""}</span>`;
    else prazo += ` · ${dias} dias`;
  }

  const rel = e.relevancia === "alta" ? '<span class="tag alta">relevância alta</span>'
    : e.relevancia === "media" ? '<span class="tag media">relevância média</span>' : "";

  return `
    <article class="edital rel-${esc(e.relevancia)}${fechado ? " encerrado" : ""}">
      <h2>${link ? `<a href="${esc(link)}" target="_blank" rel="noopener">${esc(e.titulo)}</a>` : esc(e.titulo)}</h2>
      <div class="meta">
        <span class="tag fonte">${esc(e.fonte_nome)}</span>
        ${novo ? '<span class="tag novo">novo</span>' : ""}
        ${rel}
        <span>${prazo}</span>
        ${e.valor ? `<span>${esc(e.valor)}</span>` : ""}
      </div>
      <p>${esc(e.resumo)}</p>
      ${e.motivo ? `<p class="motivo">${esc(e.motivo)}</p>` : ""}
    </article>`;
}

function render() {
  const termo = $("busca").value.trim().toLowerCase();
  const relMin = $("relevancia").value;
  const ordem = $("ordem").value;
  const verEncerrados = $("encerrados").checked;

  let lista = estado.editais.filter((e) => {
    if (estado.cat && e.categoria !== estado.cat) return false;
    if (!verEncerrados && encerrado(e)) return false;
    if (relMin && PESO_REL[e.relevancia] > PESO_REL[relMin]) return false;
    if (termo) {
      const alvo = `${e.titulo} ${e.resumo} ${e.fonte_nome} ${e.motivo}`.toLowerCase();
      if (!alvo.includes(termo)) return false;
    }
    return true;
  });

  const porPrazo = (a, b) => (a.prazo || "9999").localeCompare(b.prazo || "9999");
  if (ordem === "prazo") lista.sort(porPrazo);
  if (ordem === "relevancia") lista.sort((a, b) => (PESO_REL[a.relevancia] - PESO_REL[b.relevancia]) || porPrazo(a, b));
  if (ordem === "novos") lista.sort((a, b) => (b.primeiro_visto || "").localeCompare(a.primeiro_visto || ""));

  $("contagem").textContent = `${lista.length} de ${estado.editais.length} editais`;
  $("lista").innerHTML = lista.length
    ? lista.map(cartao).join("")
    : '<p class="vazio">Nenhum edital com esses filtros.</p>';
}

function renderFontes(status) {
  const fontes = status.fontes || [];
  const comErro = fontes.filter((f) => !f.ok).length;
  $("fontes").querySelector("summary").textContent =
    `Status das fontes (${fontes.length - comErro} ok${comErro ? `, ${comErro} com erro` : ""})`;
  $("tabela-fontes").innerHTML = fontes.map((f) => `
    <tr>
      <td><a href="${esc(linkSeguro(f.url) || "#")}" target="_blank" rel="noopener">${esc(f.nome)}</a></td>
      <td class="${f.ok ? "ok" : "erro"}">${f.ok ? "ok" : `erro<small>${esc(f.erro)}</small>`}</td>
      <td>${f.n_editais ?? 0}</td>
      <td>${dataBR(f.extraido_em) || "—"}</td>
    </tr>`).join("");
}

async function carregar(nome) {
  const resp = await fetch(`data/${nome}.json?v=${Date.now()}`);
  if (!resp.ok) throw new Error(`${nome}.json: HTTP ${resp.status}`);
  return resp.json();
}

async function iniciar() {
  try {
    const [dados, status] = await Promise.all([carregar("editais"), carregar("status")]);
    estado.editais = dados.editais || [];
    const abertos = estado.editais.filter((e) => !encerrado(e)).length;
    $("resumo").textContent = dados.atualizado_em
      ? `${abertos} editais abertos · atualizado em ${dataBR(dados.atualizado_em)} às ${dados.atualizado_em.slice(11, 16)}`
      : "Ainda sem dados: a primeira coleta não rodou.";
    renderFontes(status);
    render();
  } catch (err) {
    $("resumo").textContent = `Erro ao carregar os dados (${err.message}).`;
  }
}

$("busca").addEventListener("input", render);
["relevancia", "ordem", "encerrados"].forEach((id) => $(id).addEventListener("change", render));
$("categorias").addEventListener("click", (ev) => {
  const btn = ev.target.closest("button");
  if (!btn) return;
  estado.cat = btn.dataset.cat;
  $("categorias").querySelectorAll("button").forEach((b) => b.classList.toggle("ativo", b === btn));
  render();
});

iniciar();
