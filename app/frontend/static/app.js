const state = {
  vehicles: [],
  deviceTypes: [],
  devices: [],
  assignments: [],
  checks: [],
  repairs: [],
  alerts: [],
  upcoming: [],
};

const vehicleForm = document.getElementById("vehicle-form");
const vehicleTable = document.getElementById("vehicle-table");
const deviceTypeForm = document.getElementById("device-type-form");
const deviceTypeTable = document.getElementById("device-type-table");
const deviceForm = document.getElementById("device-form");
const deviceTypeSelect = document.getElementById("device-type-select");
const componentSerialsContainer = document.getElementById("component-serials");
const deviceTable = document.getElementById("device-table");
const assignmentForm = document.getElementById("assignment-form");
const assignmentDeviceSelect = document.getElementById("assignment-device");
const assignmentComponentSelect = document.getElementById("assignment-component");
const assignmentVehicleSelect = document.getElementById("assignment-vehicle");
const assignmentTable = document.getElementById("assignment-table");
const checkForm = document.getElementById("check-form");
const checkDeviceSelect = document.getElementById("check-device");
const checkComponentSelect = document.getElementById("check-component");
const checkTable = document.getElementById("check-table");
const repairForm = document.getElementById("repair-form");
const repairDeviceSelect = document.getElementById("repair-device");
const repairComponentSelect = document.getElementById("repair-component");
const repairTable = document.getElementById("repair-table");
const alertTable = document.getElementById("alert-table");
const upcomingTable = document.getElementById("upcoming-table");
const toast = document.getElementById("toast");
const refreshButton = document.getElementById("refresh-data");

const API_BASE = "";

function escapeHtml(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatDate(value) {
  if (!value) {
    return "—";
  }
  const [year, month, day] = value.split("T")[0].split("-");
  return `${day}.${month}.${year}`;
}

function formatDateTime(value) {
  if (!value) {
    return "—";
  }
  const [datePart, timePartRaw] = value.split("T");
  const [year, month, day] = datePart.split("-");
  let timePart = timePartRaw || "";
  timePart = timePart.replace(/Z$/, "").replace(/\+.*/, "");
  return `${day}.${month}.${year}${timePart ? " " + timePart.slice(0, 5) : ""}`;
}

function showToast(message, type = "info") {
  toast.textContent = message;
  toast.classList.remove("error", "info", "show");
  toast.classList.add(type, "show");
  window.setTimeout(() => {
    toast.classList.remove("show");
  }, 4000);
}

async function fetchJson(path, options = {}) {
  const config = { ...options };
  if (config.body && !(config.body instanceof FormData)) {
    config.headers = {
      "Content-Type": "application/json",
      ...(config.headers || {}),
    };
  }
  const response = await fetch(`${API_BASE}${path}`, config);
  const text = await response.text();
  if (!response.ok) {
    let detail = text;
    try {
      const payload = JSON.parse(text);
      detail = payload.detail || payload.message || text;
    } catch (err) {
      detail = text || response.statusText;
    }
    throw new Error(detail || "Unbekannter Fehler");
  }
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch (err) {
    return null;
  }
}

function getDeviceById(id) {
  return state.devices.find((device) => device.id === id);
}

function getVehicleById(id) {
  return state.vehicles.find((vehicle) => vehicle.id === id);
}

function getDeviceTypeById(id) {
  return state.deviceTypes.find((type) => type.id === id);
}

function findActiveAssignment(deviceId, componentId) {
  return state.assignments.find((assignment) => {
    if (assignment.device_id !== deviceId) {
      return false;
    }
    if (componentId) {
      return assignment.component_id === componentId;
    }
    return assignment.component_id === null;
  });
}

function populateDeviceTypeSelect() {
  deviceTypeSelect.innerHTML = '<option value="">Bitte wählen …</option>';
  state.deviceTypes
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .forEach((type) => {
      const option = document.createElement("option");
      option.value = String(type.id);
      option.textContent = type.name;
      deviceTypeSelect.appendChild(option);
    });
}

function populateDeviceSelect(selectElement, placeholder = "Bitte wählen …") {
  selectElement.innerHTML = "";
  const option = document.createElement("option");
  option.value = "";
  option.textContent = placeholder;
  selectElement.appendChild(option);

  state.devices
    .slice()
    .sort((a, b) => a.inventory_number.localeCompare(b.inventory_number))
    .forEach((device) => {
      const type = getDeviceTypeById(device.device_type_id);
      const optionDevice = document.createElement("option");
      optionDevice.value = String(device.id);
      optionDevice.textContent = `${device.inventory_number} (${type ? type.name : "Gerät"})`;
      selectElement.appendChild(optionDevice);
    });
}

function populateVehicleSelect(selectElement) {
  selectElement.innerHTML = "";
  const option = document.createElement("option");
  option.value = "";
  option.textContent = "Bitte wählen …";
  selectElement.appendChild(option);

  state.vehicles
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .forEach((vehicle) => {
      const optionVehicle = document.createElement("option");
      optionVehicle.value = String(vehicle.id);
      optionVehicle.textContent = `${vehicle.name} (${vehicle.radio_id})`;
      selectElement.appendChild(optionVehicle);
    });
}

function updateComponentSelect(selectElement, deviceId, label = "Gesamtes Gerät") {
  selectElement.innerHTML = "";
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = label;
  selectElement.appendChild(defaultOption);

  if (!deviceId) {
    selectElement.disabled = true;
    return;
  }

  selectElement.disabled = false;
  const device = getDeviceById(deviceId);
  if (!device || !device.components || device.components.length === 0) {
    return;
  }

  device.components.forEach((component) => {
    const option = document.createElement("option");
    option.value = String(component.id);
    option.textContent = component.component_type_name;
    selectElement.appendChild(option);
  });
}

function renderVehicles() {
  if (!state.vehicles.length) {
    vehicleTable.querySelector("tbody").innerHTML =
      '<tr><td colspan="5">Noch keine Fahrzeuge angelegt.</td></tr>';
    return;
  }
  const rows = state.vehicles
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((vehicle) => {
      return `<tr>
        <td>${escapeHtml(vehicle.name)}</td>
        <td>${escapeHtml(vehicle.radio_id)}</td>
        <td>${escapeHtml(vehicle.vehicle_type)}</td>
        <td>${vehicle.in_service_since ? escapeHtml(formatDate(vehicle.in_service_since)) : "—"}</td>
        <td>${vehicle.out_of_service ? escapeHtml(formatDate(vehicle.out_of_service)) : "—"}</td>
      </tr>`;
    })
    .join("");
  vehicleTable.querySelector("tbody").innerHTML = rows;
}

function renderDeviceTypes() {
  if (!state.deviceTypes.length) {
    deviceTypeTable.querySelector("tbody").innerHTML =
      '<tr><td colspan="5">Noch keine Gerätetypen angelegt.</td></tr>';
    return;
  }
  const rows = state.deviceTypes
    .slice()
    .sort((a, b) => a.name.localeCompare(b.name))
    .map((type) => {
      const components = type.components?.length
        ? type.components.map((c) => escapeHtml(c.name)).join(", ")
        : "—";
      const intervals = [type.default_mtk_interval_days, type.default_stk_interval_days]
        .map((value) => (value ? `${value} T` : "–"))
        .join(" / ");
      return `<tr>
        <td>${escapeHtml(type.name)}</td>
        <td>${type.manufacturer ? escapeHtml(type.manufacturer) : "—"}</td>
        <td>${type.model ? escapeHtml(type.model) : "—"}</td>
        <td>${components}</td>
        <td>${intervals}</td>
      </tr>`;
    })
    .join("");
  deviceTypeTable.querySelector("tbody").innerHTML = rows;
}

function renderDevices() {
  if (!state.devices.length) {
    deviceTable.querySelector("tbody").innerHTML =
      '<tr><td colspan="5">Noch keine Geräte angelegt.</td></tr>';
    return;
  }
  const rows = state.devices
    .slice()
    .sort((a, b) => a.inventory_number.localeCompare(b.inventory_number))
    .map((device) => {
      const type = getDeviceTypeById(device.device_type_id);
      const components = device.components?.length
        ? device.components
            .map((component) => `${escapeHtml(component.component_type_name)}: ${escapeHtml(component.serial_number || "–")}`)
            .join("<br>")
        : "—";
      return `<tr>
        <td>${escapeHtml(device.inventory_number)}</td>
        <td>${escapeHtml(type ? type.name : "-")}</td>
        <td>${escapeHtml(device.status)}</td>
        <td>${escapeHtml(device.serial_number || "–")}</td>
        <td>${components}</td>
      </tr>`;
    })
    .join("");
  deviceTable.querySelector("tbody").innerHTML = rows;
}

function renderAssignments() {
  if (!state.assignments.length) {
    assignmentTable.querySelector("tbody").innerHTML =
      '<tr><td colspan="5">Derzeit keine aktiven Zuordnungen.</td></tr>';
    return;
  }
  const rows = state.assignments
    .slice()
    .sort((a, b) => a.assigned_from.localeCompare(b.assigned_from))
    .map((assignment) => {
      const device = getDeviceById(assignment.device_id);
      const component = device?.components?.find((c) => c.id === assignment.component_id);
      const vehicle = getVehicleById(assignment.vehicle_id);
      return `<tr>
        <td>${escapeHtml(device ? device.inventory_number : "Gerät")}</td>
        <td>${component ? escapeHtml(component.component_type_name) : "Gesamt"}</td>
        <td>${escapeHtml(vehicle ? `${vehicle.name} (${vehicle.radio_id})` : "Fahrzeug")}</td>
        <td>${assignment.assigned_from ? escapeHtml(formatDateTime(assignment.assigned_from)) : "—"}</td>
        <td>${assignment.notes ? escapeHtml(assignment.notes) : "—"}</td>
      </tr>`;
    })
    .join("");
  assignmentTable.querySelector("tbody").innerHTML = rows;
}

function renderChecks() {
  if (!state.checks.length) {
    checkTable.querySelector("tbody").innerHTML =
      '<tr><td colspan="6">Noch keine Prüfungen dokumentiert.</td></tr>';
    return;
  }
  const rows = state.checks
    .slice()
    .sort((a, b) => b.performed_on.localeCompare(a.performed_on))
    .map((check) => {
      const device = getDeviceById(check.device_id);
      const component = device?.components?.find((c) => c.id === check.component_id);
      return `<tr>
        <td>${escapeHtml(device ? device.inventory_number : "Gerät")}</td>
        <td>${component ? escapeHtml(component.component_type_name) : "Gesamt"}</td>
        <td>${escapeHtml(check.check_type)}</td>
        <td>${escapeHtml(formatDate(check.performed_on))}</td>
        <td>${check.due_on ? escapeHtml(formatDate(check.due_on)) : "—"}</td>
        <td>${check.result ? escapeHtml(check.result) : "—"}</td>
      </tr>`;
    })
    .join("");
  checkTable.querySelector("tbody").innerHTML = rows;
}

function renderRepairs() {
  if (!state.repairs.length) {
    repairTable.querySelector("tbody").innerHTML =
      '<tr><td colspan="5">Noch keine Reparaturen erfasst.</td></tr>';
    return;
  }
  const rows = state.repairs
    .slice()
    .sort((a, b) => b.reported_on.localeCompare(a.reported_on))
    .map((repair) => {
      const device = getDeviceById(repair.device_id);
      const component = device?.components?.find((c) => c.id === repair.component_id);
      const statusBadge = repair.repaired_on
        ? '<span class="badge ok">abgeschlossen</span>'
        : '<span class="badge alert">offen</span>';
      return `<tr>
        <td>${escapeHtml(device ? device.inventory_number : "Gerät")}</td>
        <td>${component ? escapeHtml(component.component_type_name) : "Gesamt"}</td>
        <td>${escapeHtml(formatDate(repair.reported_on))}</td>
        <td>${repair.repaired_on ? escapeHtml(formatDate(repair.repaired_on)) : "—"}</td>
        <td>${statusBadge}</td>
      </tr>`;
    })
    .join("");
  repairTable.querySelector("tbody").innerHTML = rows;
}

function renderAlerts() {
  if (!state.alerts.length) {
    alertTable.querySelector("tbody").innerHTML =
      '<tr><td colspan="7">Keine offenen Warnungen.</td></tr>';
    return;
  }
  const rows = state.alerts
    .slice()
    .sort((a, b) => a.due_on.localeCompare(b.due_on))
    .map((alert) => {
      const device = getDeviceById(alert.device_id);
      const component = device?.components?.find((c) => c.id === alert.component_id);
      const assignment = findActiveAssignment(alert.device_id, alert.component_id);
      const vehicle = assignment ? getVehicleById(assignment.vehicle_id) : null;
      const acknowledged = Boolean(alert.acknowledged_at);
      const resolved = Boolean(alert.resolved_at);
      const actions = [];
      if (!acknowledged) {
        actions.push(`<button type="button" data-alert="${alert.id}" data-action="ack" class="secondary">Quittieren</button>`);
      }
      if (!resolved) {
        actions.push(`<button type="button" data-alert="${alert.id}" data-action="resolve">Erledigt</button>`);
      }
      if (!actions.length) {
        actions.push("—");
      }
      return `<tr>
        <td>${escapeHtml(device ? device.inventory_number : "Gerät")}${
        component ? `<br><small>${escapeHtml(component.component_type_name)}</small>` : ""
      }</td>
        <td>${vehicle ? escapeHtml(`${vehicle.name} (${vehicle.radio_id})`) : "—"}</td>
        <td>${escapeHtml(alert.check_type)}</td>
        <td>${escapeHtml(formatDate(alert.due_on))}</td>
        <td>${typeof alert.days_until_due === "number" ? alert.days_until_due : "—"}</td>
        <td>${alert.message ? escapeHtml(alert.message) : "—"}</td>
        <td class="action-row">${actions.join(" ")}</td>
      </tr>`;
    })
    .join("");
  alertTable.querySelector("tbody").innerHTML = rows;
}

function renderUpcoming() {
  if (!state.upcoming.length) {
    upcomingTable.querySelector("tbody").innerHTML =
      '<tr><td colspan="5">Keine anstehenden Prüfungen in der Auswahl.</td></tr>';
    return;
  }
  const rows = state.upcoming
    .slice()
    .sort((a, b) => a.due_on.localeCompare(b.due_on))
    .map((item) => {
      return `<tr>
        <td>${escapeHtml(item.device_inventory_number)}</td>
        <td>${item.component_name ? escapeHtml(item.component_name) : "Gesamt"}</td>
        <td>${escapeHtml(item.check_type)}</td>
        <td>${escapeHtml(formatDate(item.due_on))}</td>
        <td>${typeof item.days_until_due === "number" ? item.days_until_due : "—"}</td>
      </tr>`;
    })
    .join("");
  upcomingTable.querySelector("tbody").innerHTML = rows;
}

function refreshTables() {
  renderVehicles();
  renderDeviceTypes();
  renderDevices();
  renderAssignments();
  renderChecks();
  renderRepairs();
  renderAlerts();
  renderUpcoming();
}

async function refreshData(showNotification = false) {
  try {
    refreshButton.disabled = true;
    const [vehicles, deviceTypes, devices, assignments, checks, repairs, alerts, upcoming] =
      await Promise.all([
        fetchJson("/vehicles/"),
        fetchJson("/device-types/"),
        fetchJson("/devices/"),
        fetchJson("/assignments/active"),
        fetchJson("/checks/"),
        fetchJson("/repairs/"),
        fetchJson("/maintenance/alerts"),
        fetchJson("/maintenance/upcoming"),
      ]);
    state.vehicles = vehicles || [];
    state.deviceTypes = deviceTypes || [];
    state.devices = devices || [];
    state.assignments = assignments || [];
    state.checks = checks || [];
    state.repairs = repairs || [];
    state.alerts = alerts || [];
    state.upcoming = upcoming || [];
    populateDeviceTypeSelect();
    populateDeviceSelect(assignmentDeviceSelect);
    populateDeviceSelect(checkDeviceSelect);
    populateDeviceSelect(repairDeviceSelect);
    populateVehicleSelect(assignmentVehicleSelect);
    refreshTables();
    updateComponentSelect(assignmentComponentSelect, parseInt(assignmentDeviceSelect.value, 10) || null);
    updateComponentSelect(checkComponentSelect, parseInt(checkDeviceSelect.value, 10) || null, "Gesamtes Gerät");
    updateComponentSelect(repairComponentSelect, parseInt(repairDeviceSelect.value, 10) || null, "Gesamtes Gerät");
    updateComponentSerialInputs();
    if (showNotification) {
      showToast("Daten aktualisiert");
    }
  } catch (error) {
    console.error(error);
    showToast(error.message || "Fehler beim Laden der Daten", "error");
  } finally {
    refreshButton.disabled = false;
  }
}

function updateComponentSerialInputs() {
  const typeId = parseInt(deviceTypeSelect.value, 10);
  componentSerialsContainer.innerHTML = "";
  componentSerialsContainer.hidden = true;
  if (!typeId) {
    return;
  }
  const type = getDeviceTypeById(typeId);
  if (!type || !type.components || !type.components.length) {
    return;
  }
  componentSerialsContainer.hidden = false;
  const heading = document.createElement("h4");
  heading.textContent = "Komponenten-Seriennummern";
  componentSerialsContainer.appendChild(heading);
  type.components.forEach((component) => {
    const label = document.createElement("label");
    label.innerHTML = `${escapeHtml(component.name)}<input data-component="${component.id}" placeholder="Seriennummer" />`;
    componentSerialsContainer.appendChild(label);
  });
}

vehicleForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(vehicleForm);
  const payload = {
    radio_id: formData.get("radio_id").trim(),
    vehicle_type: formData.get("vehicle_type"),
    name: formData.get("name").trim(),
    in_service_since: formData.get("in_service_since") || null,
    out_of_service: formData.get("out_of_service") || null,
  };
  try {
    await fetchJson("/vehicles/", { method: "POST", body: JSON.stringify(payload) });
    vehicleForm.reset();
    showToast("Fahrzeug gespeichert");
    await refreshData();
  } catch (error) {
    showToast(error.message, "error");
  }
});

deviceTypeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(deviceTypeForm);
  const componentsRaw = formData.get("components");
  const components = componentsRaw
    ? componentsRaw
        .split(/\n+/)
        .map((name) => name.trim())
        .filter((name) => name.length > 0)
        .map((name) => ({ name }))
    : [];
  const payload = {
    name: formData.get("name").trim(),
    manufacturer: formData.get("manufacturer")?.trim() || null,
    model: formData.get("model")?.trim() || null,
    default_mtk_interval_days: formData.get("default_mtk_interval_days")
      ? Number(formData.get("default_mtk_interval_days"))
      : null,
    default_stk_interval_days: formData.get("default_stk_interval_days")
      ? Number(formData.get("default_stk_interval_days"))
      : null,
    is_composite: formData.get("is_composite") === "on",
    components,
  };
  try {
    await fetchJson("/device-types/", { method: "POST", body: JSON.stringify(payload) });
    deviceTypeForm.reset();
    showToast("Gerätetyp gespeichert");
    await refreshData();
  } catch (error) {
    showToast(error.message, "error");
  }
});

deviceTypeSelect.addEventListener("change", () => {
  updateComponentSerialInputs();
});

deviceForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(deviceForm);
  const typeId = Number(formData.get("device_type_id"));
  const componentSerials = {};
  componentSerialsContainer.querySelectorAll("input[data-component]").forEach((input) => {
    const value = input.value.trim();
    componentSerials[input.dataset.component] = value.length ? value : null;
  });
  const payload = {
    inventory_number: formData.get("inventory_number").trim(),
    device_type_id: typeId,
    serial_number: formData.get("serial_number")?.trim() || null,
    purchase_date: formData.get("purchase_date") || null,
    status: formData.get("status")?.trim() || "aktiv",
    notes: formData.get("notes")?.trim() || null,
    component_serials: componentSerials,
  };
  try {
    await fetchJson("/devices/", { method: "POST", body: JSON.stringify(payload) });
    deviceForm.reset();
    deviceTypeSelect.value = "";
    updateComponentSerialInputs();
    showToast("Gerät gespeichert");
    await refreshData();
  } catch (error) {
    showToast(error.message, "error");
  }
});

assignmentDeviceSelect.addEventListener("change", () => {
  const id = parseInt(assignmentDeviceSelect.value, 10) || null;
  updateComponentSelect(assignmentComponentSelect, id);
});

checkDeviceSelect.addEventListener("change", () => {
  const id = parseInt(checkDeviceSelect.value, 10) || null;
  updateComponentSelect(checkComponentSelect, id, "Gesamtes Gerät");
});

repairDeviceSelect.addEventListener("change", () => {
  const id = parseInt(repairDeviceSelect.value, 10) || null;
  updateComponentSelect(repairComponentSelect, id, "Gesamtes Gerät");
});

assignmentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(assignmentForm);
  const payload = {
    device_id: Number(formData.get("device_id")),
    vehicle_id: Number(formData.get("vehicle_id")),
    component_id: formData.get("component_id") ? Number(formData.get("component_id")) : null,
    assigned_from: formData.get("assigned_from") || null,
    assigned_by: formData.get("assigned_by")?.trim() || null,
    notes: formData.get("notes")?.trim() || null,
  };
  try {
    await fetchJson("/assignments/", { method: "POST", body: JSON.stringify(payload) });
    assignmentForm.reset();
    updateComponentSelect(assignmentComponentSelect, null);
    showToast("Zuordnung erstellt");
    await refreshData();
  } catch (error) {
    showToast(error.message, "error");
  }
});

checkForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(checkForm);
  const payload = {
    device_id: Number(formData.get("device_id")),
    component_id: formData.get("component_id") ? Number(formData.get("component_id")) : null,
    check_type: formData.get("check_type"),
    performed_on: formData.get("performed_on"),
    due_on: formData.get("due_on") || null,
    performed_by: formData.get("performed_by")?.trim() || null,
    result: formData.get("result")?.trim() || null,
    certificate_path: formData.get("certificate_path")?.trim() || null,
    notes: formData.get("notes")?.trim() || null,
    attachments: [],
  };
  try {
    await fetchJson("/checks/", { method: "POST", body: JSON.stringify(payload) });
    checkForm.reset();
    updateComponentSelect(checkComponentSelect, null, "Gesamtes Gerät");
    showToast("Prüfung erfasst");
    await refreshData();
  } catch (error) {
    showToast(error.message, "error");
  }
});

repairForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(repairForm);
  const payload = {
    device_id: Number(formData.get("device_id")),
    component_id: formData.get("component_id") ? Number(formData.get("component_id")) : null,
    reported_on: formData.get("reported_on"),
    repaired_on: formData.get("repaired_on") || null,
    reported_issue: formData.get("reported_issue")?.trim(),
    repair_action: formData.get("repair_action")?.trim() || null,
    repaired_by: formData.get("repaired_by")?.trim() || null,
    cost: formData.get("cost") ? Number(formData.get("cost")) : null,
    document_path: formData.get("document_path")?.trim() || null,
    notes: formData.get("notes")?.trim() || null,
    attachments: [],
  };
  try {
    await fetchJson("/repairs/", { method: "POST", body: JSON.stringify(payload) });
    repairForm.reset();
    updateComponentSelect(repairComponentSelect, null, "Gesamtes Gerät");
    showToast("Reparatur gespeichert");
    await refreshData();
  } catch (error) {
    showToast(error.message, "error");
  }
});

alertTable.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-alert]");
  if (!button) {
    return;
  }
  const alertId = button.dataset.alert;
  const action = button.dataset.action;
  const payload = action === "ack" ? { acknowledged: true } : { resolve: true };
  try {
    await fetchJson(`/maintenance/alerts/${alertId}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showToast("Warnung aktualisiert");
    await refreshData();
  } catch (error) {
    showToast(error.message, "error");
  }
});

refreshButton.addEventListener("click", () => refreshData(true));

document.addEventListener("DOMContentLoaded", () => {
  refreshData();
});
