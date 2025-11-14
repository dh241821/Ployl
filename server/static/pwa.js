if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/static/service-worker.js').catch(console.error);
}

const loginForm = document.getElementById('login-form');
const dashboard = document.getElementById('dashboard');
const scannerSection = document.getElementById('scanner');
const notificationsSection = document.getElementById('notifications');
const loginSection = document.getElementById('login-section');
const notificationOutput = document.getElementById('notification-output');
const aiSection = document.getElementById('ai-assistant');
const aiForm = document.getElementById('ai-form');
const aiResponse = document.getElementById('ai-response');
const iotSection = document.getElementById('iot-section');
const iotStatus = document.getElementById('iot-status');
const iotList = document.getElementById('iot-list');
const arSection = document.getElementById('ar-section');
const arSteps = document.getElementById('ar-steps');
const offlineIndicator = document.getElementById('offline-indicator');
const themeToggle = document.getElementById('theme-toggle');
const installBtn = document.getElementById('install-btn');
let deferredPrompt = null;
let accessToken = null;
let statusChart;
let repairChart;
let offlineQueue = [];

try {
  offlineQueue = JSON.parse(localStorage.getItem('offlineQueue') || '[]');
} catch (error) {
  offlineQueue = [];
}

function persistOfflineQueue() {
  localStorage.setItem('offlineQueue', JSON.stringify(offlineQueue));
  updateOfflineIndicator();
}

function updateOfflineIndicator() {
  if (!offlineIndicator) return;
  const status = navigator.onLine ? 'Online' : 'Offline';
  const queued = offlineQueue.length;
  offlineIndicator.textContent = queued ? `${status} · ${queued} Offline-Aktionen` : status;
}

async function sha256(value) {
  const encoder = new TextEncoder();
  const data = encoder.encode(typeof value === 'string' ? value : JSON.stringify(value));
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hashBuffer))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
}

async function queueOfflineChange(entityType, payload) {
  const checksum = await sha256(payload);
  offlineQueue.push({ entityType, payload, checksum });
  persistOfflineQueue();
}

async function syncOfflineQueue() {
  if (!navigator.onLine || !accessToken || offlineQueue.length === 0) {
    updateOfflineIndicator();
    return;
  }
  const pending = [...offlineQueue];
  offlineQueue = [];
  persistOfflineQueue();
  for (const entry of pending) {
    try {
      await api('/api/offline/queue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entity_type: entry.entityType,
          payload: entry.payload,
          checksum: entry.checksum,
        })
      });
    } catch (error) {
      offlineQueue.push(entry);
    }
  }
  persistOfflineQueue();
}

window.addEventListener('online', () => {
  updateOfflineIndicator();
  syncOfflineQueue();
});
window.addEventListener('offline', updateOfflineIndicator);
updateOfflineIndicator();

themeToggle?.addEventListener('click', () => {
  const isDark = document.body.dataset.theme === 'dark';
  document.body.dataset.theme = isDark ? 'light' : 'dark';
  themeToggle.setAttribute('aria-pressed', String(!isDark));
  localStorage.setItem('theme', document.body.dataset.theme);
});

const storedTheme = localStorage.getItem('theme');
if (storedTheme) {
  document.body.dataset.theme = storedTheme;
  themeToggle?.setAttribute('aria-pressed', String(storedTheme === 'dark'));
}

window.addEventListener('beforeinstallprompt', (event) => {
  event.preventDefault();
  deferredPrompt = event;
  installBtn.hidden = false;
});

installBtn?.addEventListener('click', async () => {
  if (!deferredPrompt) return;
  deferredPrompt.prompt();
  await deferredPrompt.userChoice;
  deferredPrompt = null;
  installBtn.hidden = true;
});

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
  if (aiSection) aiSection.hidden = false;
  if (iotSection) iotSection.hidden = false;
  if (arSection) arSection.hidden = false;
  await Promise.all([loadDashboard(), loadIoTDevices(), loadArInstruction(), refreshInventoryForecasts()]);
  initScanner();
  syncOfflineQueue();
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

async function loadIoTDevices() {
  if (!iotSection) return;
  try {
    const devices = await api('/api/iot/devices');
    if (!devices.length) {
      iotStatus.textContent = 'Keine Sensoren registriert.';
      iotList.innerHTML = '';
      return;
    }
    iotStatus.textContent = `${devices.length} Sensoren aktiv.`;
    iotList.innerHTML = devices
      .map((device) => `<li><strong>${device.name}</strong> – ${device.sensor_type}${device.location ? ' @ ' + device.location : ''}</li>`)
      .join('');
  } catch (error) {
    iotStatus.textContent = 'Sensoren derzeit nicht erreichbar.';
  }
}

async function loadArInstruction() {
  if (!arSection) return;
  try {
    const instruction = await api('/api/ar/instructions/0');
    arSteps.innerHTML = instruction.steps.map((step) => `<li>${step}</li>`).join('');
  } catch (error) {
    arSteps.innerHTML = '<li>Keine Anleitung verfügbar.</li>';
  }
}

async function refreshInventoryForecasts() {
  try {
    await api('/api/predictions/inventory', { method: 'POST' });
  } catch (error) {
    console.warn('Forecast update failed', error);
  }
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

aiForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  const prompt = document.getElementById('ai-prompt').value.trim();
  if (!prompt) return;
  if (!navigator.onLine) {
    await queueOfflineChange('ai.chat', { prompt });
    aiResponse.textContent = 'Offline gespeichert – wird bei nächster Verbindung beantwortet.';
    return;
  }
  try {
    const result = await api('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt })
    });
    aiResponse.textContent = result.response;
  } catch (error) {
    aiResponse.textContent = 'Assistent derzeit nicht erreichbar.';
  }
});

setInterval(() => {
  if (accessToken) {
    loadDashboard();
    loadIoTDevices();
  }
}, 60000);
