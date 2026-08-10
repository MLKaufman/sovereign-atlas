const columns = [
  ["gene_symbol", "Gene"], ["cell_type", "Cell type"], ["species_common_name", "Species"],
  ["tissue", "Tissue"], ["marker_direction", "Direction"], ["confidence", "Confidence"],
  ["human_verified", "Verified"], ["source_titles", "Sources"], ["assay", "Assay"]
];
let allRows = [], visibleRows = [], sortKey = "gene_symbol", sortDirection = 1;
const $ = (id) => document.getElementById(id);
const text = (value) => value == null ? "" : String(value);
const escapeHtml = (value) => text(value).replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));

function setOptions(id, key) {
  const select = $(id), first = select.options[0];
  select.replaceChildren(first, ...[...new Set(allRows.map(r => text(r[key])).filter(Boolean))].sort().map(v => new Option(v, v)));
}

function renderHead() {
  $("tableHead").innerHTML = columns.map(([key, label]) =>
    `<th><button type="button" data-sort="${key}" aria-label="Sort by ${label}">${label}${sortKey === key ? (sortDirection > 0 ? " ↑" : " ↓") : ""}</button></th>`
  ).join("");
}

function renderCell(key, value) {
  if (key === "gene_symbol") return `<span class="gene">${escapeHtml(value)}</span>`;
  if (key === "marker_direction") return `<span class="pill ${value === "negative" ? "negative" : ""}">${escapeHtml(value)}</span>`;
  if (key === "human_verified") return value ? '<span class="yes" aria-label="Yes">✓</span>' : "—";
  if (key === "source_titles") return `<span class="sources">${escapeHtml(value || "No source linked")}</span>`;
  return escapeHtml(value || "—");
}

function applyFilters() {
  const query = $("search").value.trim().toLowerCase();
  const filters = { species_common_name: $("speciesFilter").value, cell_type: $("cellFilter").value, tissue: $("tissueFilter").value, marker_direction: $("directionFilter").value };
  visibleRows = allRows.filter(row => {
    if (query && !Object.values(row).some(v => text(v).toLowerCase().includes(query))) return false;
    if ($("verifiedFilter").checked && !row.human_verified) return false;
    return Object.entries(filters).every(([key, value]) => !value || text(row[key]) === value);
  }).sort((a, b) => text(a[sortKey]).localeCompare(text(b[sortKey]), undefined, {numeric: true}) * sortDirection);
  renderHead();
  $("tableBody").innerHTML = visibleRows.map(row => `<tr>${columns.map(([key]) => `<td>${renderCell(key, row[key])}</td>`).join("")}</tr>`).join("");
  $("visibleCount").textContent = visibleRows.length.toLocaleString();
  $("empty").hidden = visibleRows.length > 0;
  $("tableBody").parentElement.hidden = visibleRows.length === 0;
}

async function copyGenes(format) {
  const genes = [...new Set(visibleRows.map(r => r.gene_symbol))];
  const quoted = genes.map(g => `"${String(g).replaceAll('"', '\\"')}"`);
  const output = format === "r" ? `c(${quoted.join(", ")})` : format === "python" ? `[${quoted.join(", ")}]` : genes.join("\n");
  await navigator.clipboard.writeText(output);
  $("copyStatus").textContent = `Copied ${genes.length} gene${genes.length === 1 ? "" : "s"}`;
  setTimeout(() => $("copyStatus").textContent = "", 2500);
}

document.addEventListener("click", event => {
  const sort = event.target.closest("[data-sort]");
  if (sort) { const key = sort.dataset.sort; sortDirection = sortKey === key ? -sortDirection : 1; sortKey = key; applyFilters(); }
  const copy = event.target.closest("[data-copy]");
  if (copy) copyGenes(copy.dataset.copy).catch(() => $("copyStatus").textContent = "Clipboard access was blocked");
});
["search", "speciesFilter", "cellFilter", "tissueFilter", "directionFilter", "verifiedFilter"].forEach(id => $(id).addEventListener("input", applyFilters));
$("clearFilters").addEventListener("click", () => { $("search").value = ""; ["speciesFilter", "cellFilter", "tissueFilter", "directionFilter"].forEach(id => $(id).value = ""); $("verifiedFilter").checked = false; applyFilters(); });

fetch("markers.json").then(response => { if (!response.ok) throw new Error("Could not load markers"); return response.json(); }).then(rows => {
  allRows = rows; setOptions("speciesFilter", "species_common_name"); setOptions("cellFilter", "cell_type"); setOptions("tissueFilter", "tissue"); applyFilters();
}).catch(error => { $("tableBody").innerHTML = `<tr><td class="loading">${escapeHtml(error.message)}. Serve this directory with a local web server.</td></tr>`; });

