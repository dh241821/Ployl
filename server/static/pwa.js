if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/static/service-worker.js').catch(console.error);
}

const loginForm = document.getElementById('login-form');
const dashboard = document.getElementById('dashboard');
const scannerSection = document.getElementById('scanner');
const notificationsSection = document.getElementById('notifications');
const loginSection = document.getElementById('login-section');
const notificationOutput = document.getElementById('notification-output');
let accessToken = null;
let statusChart;
let repairChart;

async function api(path, options = {}) {
  const headers = options.headers || {};
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}

loginForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new URLSearchParams();
  formData.append('username', document.getElementById('username').value);
  formData.append('password', document.getElementById('password').value);
  formData.append('grant_type', 'password');
  const result = await fetch('/api/auth/token', {
    method: 'POST',
    body: formData
  });
  if (!result.ok) {
    alert('Login fehlgeschlagen');
    return;
  }
  const data = await result.json();
  accessToken = data.access_token;
  loginSection.hidden = true;
  dashboard.hidden = false;
  scannerSection.hidden = false;
  notificationsSection.hidden = false;
  loadDashboard();
  initScanner();
});

async function loadDashboard() {
  try {
    const data = await api('/api/dashboard');
    document.getElementById('kpi-due').innerText = data.kpis.due_products;
    document.getElementById('kpi-repair').innerText = data.kpis.in_repair;
    document.getElementById('kpi-expired').innerText = data.kpis.expired_materials;
    document.getElementById('kpi-low-stock').innerText = data.kpis.low_stock_materials;
    document.getElementById('kpi-maintenance').innerText = data.kpis.maintenance_due_within_30_days;
    renderCharts(data);
  } catch (error) {
    console.error(error);
  }
}

function renderCharts(data) {
  const statusCtx = document.getElementById('status-chart').getContext('2d');
  const repairCtx = document.getElementById('repair-chart').getContext('2d');
  if (statusChart) statusChart.destroy();
  if (repairChart) repairChart.destroy();
  statusChart = new Chart(statusCtx, {
    type: 'doughnut',
    data: {
      labels: data.product_status_chart.labels,
      datasets: [{
        data: data.product_status_chart.values,
        backgroundColor: ['#16a34a', '#f97316', '#ef4444']
      }]
    }
  });
  repairChart = new Chart(repairCtx, {
    type: 'line',
    data: {
      labels: data.repair_frequency_chart.labels,
      datasets: [{
        label: 'Reparaturkosten',
        data: data.repair_frequency_chart.values,
        borderColor: '#2563eb',
        tension: 0.3,
        fill: false
      }]
    }
  });
}

function initScanner() {
  const html5QrCode = new Html5Qrcode('qr-reader');
  html5QrCode.start({ facingMode: 'environment' }, { fps: 10, qrbox: 250 }, async (decodedText) => {
    html5QrCode.pause();
    try {
      const result = await api(`/api/scanner/lookup?payload=${encodeURIComponent(decodedText)}`);
      if (result.produkt) {
        document.getElementById('scan-result').innerText = `${result.produkt.name} (${result.produkt.seriennummer})`;
      } else if (result.material_bestand !== null) {
        document.getElementById('scan-result').innerText = `Materialbestand: ${result.material_bestand}`;
      }
    } catch (error) {
      document.getElementById('scan-result').innerText = 'Scan unbekannt';
    } finally {
      setTimeout(() => html5QrCode.resume(), 1500);
    }
  });
}

document.getElementById('dispatch-btn')?.addEventListener('click', async () => {
  try {
    const result = await api('/api/notifications/dispatch', { method: 'POST' });
    notificationOutput.textContent = JSON.stringify(result, null, 2);
  } catch (error) {
    notificationOutput.textContent = error.message;
  }
});

setInterval(() => {
  if (accessToken) {
    loadDashboard();
  }
}, 60000);
