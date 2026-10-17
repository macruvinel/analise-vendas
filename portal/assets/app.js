const $ = (selector) => document.querySelector(selector);
const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const integer = new Intl.NumberFormat('pt-BR');
const views = ['dashboard', 'compras', 'clientes', 'produtos', 'admin'];

let purchases = [];
let customers = [];
let products = [];
let adminTables = [];
let activeAdminTable = '';
let selectedDates = { start: '', end: '' };

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!response.ok) {
    let message = `Falha na API (${response.status}).`;
    try {
      const detail = await response.json();
      message = detail.detail || message;
    } catch {}
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function formatDate(date) {
  if (!date) return '—';
  const [year, month, day] = date.split('-');
  return `${day}/${month}/${year}`;
}

function purchaseRows(rows) {
  if (!rows.length) return '<tr><td colspan="5" class="empty-cell">Nenhuma compra encontrada.</td></tr>';
  return rows.map((item) => `
    <tr>
      <td class="cell-primary">#${escapeHtml(item.id)}</td>
      <td class="cell-primary">${escapeHtml(item.nome_cliente)}<span class="cell-secondary">Cliente #${escapeHtml(item.id_cliente)}</span></td>
      <td>${formatDate(item.dt_compra)}</td>
      <td class="align-right cell-primary">${currency.format(item.valor_total)}</td>
      <td><span class="status-pill">Concluída</span></td>
    </tr>`).join('');
}

function renderPurchases() {
  $('#recent-purchases').innerHTML = purchaseRows(purchases.slice(0, 6));
  const query = $('#purchase-search').value.trim().toLocaleLowerCase('pt-BR');
  const filtered = purchases.filter((item) =>
    String(item.id).includes(query) || item.nome_cliente.toLocaleLowerCase('pt-BR').includes(query));
  $('#purchases-table').innerHTML = purchaseRows(filtered);
  $('#purchase-count').textContent = `${filtered.length} registro${filtered.length === 1 ? '' : 's'}`;
}

function renderCustomers() {
  const query = $('#customer-search').value.trim().toLocaleLowerCase('pt-BR');
  const filtered = customers.filter((client) =>
    `${client.nome} ${client.email} ${client.cidade} ${client.bairro}`.toLocaleLowerCase('pt-BR').includes(query));
  $('#customers-table').innerHTML = filtered.length ? filtered.map((client) => `
    <tr>
      <td class="cell-primary">${escapeHtml(client.nome)}<span class="cell-secondary">${escapeHtml(client.email)}</span></td>
      <td>${escapeHtml(client.cidade)}<span class="cell-secondary">${escapeHtml(client.bairro)}</span></td>
      <td>${integer.format(client.quantidade_compras)}</td>
      <td class="align-right cell-primary">${currency.format(client.valor_total_compras)}</td>
      <td class="align-right">${currency.format(client.ticket_medio)}</td>
    </tr>`).join('') : '<tr><td colspan="5" class="empty-cell">Nenhum cliente encontrado.</td></tr>';
  $('#customer-count').textContent = `${filtered.length} de ${customers.length} clientes`;
}

function renderProducts() {
  const query = $('#product-search').value.trim().toLocaleLowerCase('pt-BR');
  const filtered = products.filter((product) =>
    `${product.nome} ${product.categoria}`.toLocaleLowerCase('pt-BR').includes(query));
  $('#products-table').innerHTML = filtered.length ? filtered.map((product) => `
    <tr>
      <td class="cell-primary">${escapeHtml(product.nome)}<span class="cell-secondary">Produto #${escapeHtml(product.id)}</span></td>
      <td>${escapeHtml(product.categoria)}</td>
      <td class="align-right">${currency.format(product.preco)}</td>
      <td>${integer.format(product.unidades_vendidas)}</td>
      <td class="align-right cell-primary">${currency.format(product.faturamento_total)}</td>
    </tr>`).join('') : '<tr><td colspan="5" class="empty-cell">Nenhum produto encontrado.</td></tr>';
  $('#product-count').textContent = `${filtered.length} de ${products.length} produtos`;
}

function renderRanking(highlights) {
  $('#top-products').innerHTML = highlights.length ? highlights.slice(0, 4).map((product, index) => `
    <div class="ranking-row">
      <span class="rank-number">${String(index + 1).padStart(2, '0')}</span>
      <span class="rank-name">${escapeHtml(product.nome)}<span class="rank-category">${escapeHtml(product.categoria)} · ${integer.format(product.unidades_vendidas)} un.</span></span>
      <span class="rank-value">${currency.format(product.faturamento_total)}</span>
    </div>`).join('') : '<p class="empty-cell">Sem dados de produtos.</p>';
}

function renderProductSummary(highlights) {
  const best = highlights.maior_potencial[0];
  const low = highlights.menor_potencial[0];
  $('#product-summary').innerHTML = `
    <div class="product-summary-card"><span>Maior faturamento acumulado</span><strong>${best ? escapeHtml(best.nome) : '—'}${best ? ` · ${currency.format(best.faturamento_total)}` : ''}</strong><small>Classificação pelo faturamento, com unidades vendidas como desempate.</small></div>
    <div class="product-summary-card"><span>Menor faturamento acumulado</span><strong>${low ? escapeHtml(low.nome) : '—'}${low ? ` · ${currency.format(low.faturamento_total)}` : ''}</strong><small>Os produtos sem vendas também aparecem nesta análise.</small></div>`;
}

function drawSalesChart(rows) {
  const canvas = $('#sales-chart');
  const empty = $('#chart-empty');
  const byMonth = new Map();
  rows.forEach((purchase) => {
    const month = purchase.dt_compra.slice(0, 7);
    byMonth.set(month, (byMonth.get(month) || 0) + purchase.valor_total);
  });
  const data = [...byMonth.entries()].sort(([a], [b]) => a.localeCompare(b));
  empty.hidden = data.length > 0;
  if (!data.length) return;
  const bounds = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, bounds.width * ratio);
  canvas.height = Math.max(1, bounds.height * ratio);
  const context = canvas.getContext('2d');
  context.scale(ratio, ratio);
  const width = bounds.width;
  const height = bounds.height;
  const pad = { top: 12, right: 13, bottom: 27, left: 48 };
  const chartWidth = width - pad.left - pad.right;
  const chartHeight = height - pad.top - pad.bottom;
  const maxValue = Math.max(...data.map(([, amount]) => amount), 1);
  const ticks = 4;
  context.font = '9px "DM Sans", sans-serif';
  context.textBaseline = 'middle';
  for (let tick = 0; tick <= ticks; tick += 1) {
    const y = pad.top + chartHeight * tick / ticks;
    const amount = maxValue * (ticks - tick) / ticks;
    context.strokeStyle = '#eef0f5';
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(pad.left, y);
    context.lineTo(width - pad.right, y);
    context.stroke();
    context.fillStyle = '#a3acb8';
    context.textAlign = 'right';
    context.fillText(amount >= 1000 ? `R$${(amount / 1000).toFixed(0)}k` : `R$${amount.toFixed(0)}`, pad.left - 8, y);
  }
  const step = chartWidth / Math.max(data.length - 1, 1);
  const points = data.map(([, amount], index) => ({
    x: pad.left + step * index,
    y: pad.top + chartHeight * (1 - amount / maxValue),
  }));
  const gradient = context.createLinearGradient(0, pad.top, 0, height - pad.bottom);
  gradient.addColorStop(0, 'rgba(103, 88, 216, .19)');
  gradient.addColorStop(1, 'rgba(103, 88, 216, 0)');
  context.beginPath();
  context.moveTo(points[0].x, height - pad.bottom);
  points.forEach((point) => context.lineTo(point.x, point.y));
  context.lineTo(points[points.length - 1].x, height - pad.bottom);
  context.closePath();
  context.fillStyle = gradient;
  context.fill();
  context.beginPath();
  points.forEach((point, index) => {
    if (index === 0) context.moveTo(point.x, point.y);
    else context.lineTo(point.x, point.y);
  });
  context.strokeStyle = '#6758d8';
  context.lineWidth = 2;
  context.lineJoin = 'round';
  context.stroke();
  data.forEach(([month], index) => {
    const point = points[index];
    context.beginPath();
    context.arc(point.x, point.y, 3, 0, Math.PI * 2);
    context.fillStyle = '#fff';
    context.fill();
    context.strokeStyle = '#6758d8';
    context.lineWidth = 2;
    context.stroke();
    context.fillStyle = '#929caa';
    context.textAlign = 'center';
    const [year, monthNumber] = month.split('-');
    context.fillText(new Date(Number(year), Number(monthNumber) - 1, 1).toLocaleDateString('pt-BR', { month: 'short' }).replace('.', ''), point.x, height - 10);
  });
}

function showView(name) {
  views.forEach((view) => {
    $(`#view-${view}`).classList.toggle('active', view === name);
    $(`[data-view="${view}"]`).classList.toggle('active', view === name);
  });
  const labels = { dashboard: 'Visão geral', compras: 'Compras', clientes: 'Clientes', produtos: 'Produtos', admin: 'Administração' };
  $('#breadcrumb').textContent = labels[name];
  if (name === 'admin') checkAdminSession();
}

function queryPeriod() {
  const params = new URLSearchParams();
  if (selectedDates.start) params.set('data_inicio', selectedDates.start);
  if (selectedDates.end) params.set('data_fim', selectedDates.end);
  return params.toString();
}

async function loadDashboard() {
  const errorBox = $('#load-error');
  errorBox.hidden = true;
  try {
    const period = queryPeriod();
    const [summary, sales, customerData, productData] = await Promise.all([
      api(`/analise-compras${period ? `?${period}` : ''}`),
      api(`/resumo-vendas${period ? `?${period}` : ''}`),
      api('/analise-clientes?limite=500'),
      api('/analise-produtos?limite=500'),
    ]);
    $('#kpi-revenue').textContent = currency.format(summary.valor_total);
    $('#kpi-orders').textContent = integer.format(summary.quantidade_compras);
    $('#kpi-customers').textContent = integer.format(summary.quantidade_clientes);
    $('#kpi-ticket').textContent = currency.format(summary.ticket_medio);
    purchases = sales.compras;
    customers = customerData.clientes;
    products = productData.maior_potencial;
    renderPurchases();
    renderCustomers();
    renderProducts();
    renderRanking(productData.maior_potencial);
    renderProductSummary(productData);
    drawSalesChart(sales.compras);
  } catch (error) {
    errorBox.textContent = `Não foi possível carregar os dados do portal: ${error.message}`;
    errorBox.hidden = false;
  }
}

function renderAdminTable(name) {
  const table = adminTables.find((item) => item.nome === name);
  if (!table) return;
  activeAdminTable = name;
  $('#admin-tabs').innerHTML = adminTables.map((item) => `
    <button class="admin-tab ${item.nome === name ? 'active' : ''}" role="tab" aria-selected="${item.nome === name}" data-table="${escapeHtml(item.nome)}">${escapeHtml(item.nome)}</button>`).join('');
  $('#admin-head').innerHTML = `<tr>${table.colunas.map((column) => `<th>${escapeHtml(column)}</th>`).join('')}</tr>`;
  $('#admin-body').innerHTML = table.linhas.length ? table.linhas.map((row) =>
    `<tr>${table.colunas.map((column) => `<td>${row[column] === null ? '<span class="cell-secondary">—</span>' : escapeHtml(row[column])}</td>`).join('')}</tr>`).join('') :
    `<tr><td colspan="${table.colunas.length}" class="empty-cell">Esta tabela não possui registros.</td></tr>`;
  $('#admin-table-count').textContent = `${integer.format(table.linhas.length)} registro${table.linhas.length === 1 ? '' : 's'} em ${table.nome}`;
}

async function checkAdminSession() {
  try {
    const result = await api('/admin/tabelas');
    adminTables = result.tabelas;
    $('#admin-login').hidden = true;
    $('#admin-data').hidden = false;
    if (!adminTables.some((table) => table.nome === activeAdminTable)) {
      activeAdminTable = adminTables[0]?.nome || '';
    }
    if (activeAdminTable) renderAdminTable(activeAdminTable);
  } catch (error) {
    if (error.status !== 401) $('#login-error').textContent = error.message;
    $('#admin-login').hidden = false;
    $('#admin-data').hidden = true;
  }
}

document.querySelectorAll('[data-view]').forEach((button) =>
  button.addEventListener('click', () => showView(button.dataset.view)));
document.querySelectorAll('[data-go]').forEach((button) =>
  button.addEventListener('click', () => showView(button.dataset.go)));
$('#apply-filter').addEventListener('click', () => {
  selectedDates = { start: $('#date-start').value, end: $('#date-end').value };
  if (selectedDates.start && selectedDates.end && selectedDates.start > selectedDates.end) {
    $('#load-error').textContent = 'A data inicial não pode ser posterior à data final.';
    $('#load-error').hidden = false;
    return;
  }
  loadDashboard();
});
$('#purchase-search').addEventListener('input', renderPurchases);
$('#customer-search').addEventListener('input', renderCustomers);
$('#product-search').addEventListener('input', renderProducts);
$('#admin-login').addEventListener('submit', async (event) => {
  event.preventDefault();
  const error = $('#login-error');
  error.hidden = true;
  try {
    await api('/admin/login', {
      method: 'POST',
      body: JSON.stringify({
        usuario: $('#admin-user').value,
        senha: $('#admin-password').value,
      }),
    });
    $('#admin-password').value = '';
    await checkAdminSession();
  } catch (loginError) {
    error.textContent = loginError.message;
    error.hidden = false;
  }
});
$('#admin-logout').addEventListener('click', async () => {
  try {
    await api('/admin/logout', { method: 'POST' });
    adminTables = [];
    activeAdminTable = '';
    $('#admin-login').reset();
    $('#login-error').hidden = true;
    $('#admin-login').hidden = false;
    $('#admin-data').hidden = true;
  } catch (error) {
    $('#login-error').textContent = `Não foi possível encerrar a sessão: ${error.message}`;
    $('#login-error').hidden = false;
  }
});
$('#admin-tabs').addEventListener('click', (event) => {
  const tab = event.target.closest('[data-table]');
  if (tab) renderAdminTable(tab.dataset.table);
});
window.addEventListener('resize', () => {
  if ($('#view-dashboard').classList.contains('active')) drawSalesChart(purchases);
});
$('#today-label').textContent = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium' }).format(new Date());
loadDashboard();
