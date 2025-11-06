const API_BASE = "";

function showToast(message, type = "info") {
  const toast = document.getElementById("toast");
  if (!toast) return;
  toast.textContent = message;
  toast.className = `toast ${type} show`;
  setTimeout(() => {
    toast.classList.remove("show");
  }, 4000);
}

async function apiFetch(path, options = {}) {
  const config = { ...options };
  if (config.body && !(config.body instanceof FormData)) {
    config.headers = {
      "Content-Type": "application/json",
      ...(config.headers || {}),
    };
    config.body = typeof config.body === "string" ? config.body : JSON.stringify(config.body);
  }
  const response = await fetch(`${API_BASE}${path}`, config);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const data = await response.json();
      detail = data.detail || data.message || detail;
    } catch (err) {
      // ignore
    }
    throw new Error(detail || `Fehler (${response.status})`);
  }
  if (response.status === 204) {
    return null;
  }
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch (err) {
    return text;
  }
}

function readJsonScript(id) {
  const element = document.getElementById(id);
  if (!element) return null;
  try {
    return JSON.parse(element.textContent);
  } catch (err) {
    console.error("JSON parse error", err);
    return null;
  }
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("de-AT", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

async function refreshHistory(deviceId, state) {
  const history = await apiFetch(`/devices/${deviceId}/history`);
  state.assignments = history.assignments || [];
  state.checks = history.safety_checks || [];
  state.repairs = history.repairs || [];
}

function initOverview() {
  const data = readJsonScript("overview-data") || { vehicles: [], assignments: [], devices: [] };
  const select = document.getElementById("location-select");
  const tbody = document.querySelector("#location-device-table tbody");
  const vehicleForm = document.getElementById("vehicle-form");
  const vehicleTable = document.querySelector("#vehicle-table tbody");
  const assignments = (data.assignments || []).map((assignment) => ({
    ...assignment,
    vehicle_id: Number(assignment.vehicle_id),
    device_id: Number(assignment.device_id),
  }));
  const deviceMap = new Map((data.devices || []).map((device) => [device.id, device]));
  data.vehicles = (data.vehicles || []).map((vehicle) => ({
    ...vehicle,
    id: Number(vehicle.id),
  }));

  function renderVehicleTable() {
    if (!vehicleTable) return;
    vehicleTable.innerHTML = "";
    data.vehicles
      .slice()
      .sort((a, b) => a.radio_id.localeCompare(b.radio_id))
      .forEach((vehicle) => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td>${vehicle.radio_id}</td>
          <td>${vehicle.vehicle_type}</td>
          <td>${formatDate(vehicle.in_service_since)}</td>
          <td>${formatDate(vehicle.out_of_service)}</td>
        `;
        vehicleTable.appendChild(row);
      });
  }

  function renderAssignments(vehicleId) {
    if (!tbody) return;
    tbody.innerHTML = "";
    const filtered = assignments.filter((assignment) => assignment.vehicle_id === vehicleId);
    if (filtered.length === 0) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 7;
      cell.textContent = "Keine Geräte zugeordnet.";
      row.appendChild(cell);
      tbody.appendChild(row);
      return;
    }
    filtered
      .slice()
      .sort((a, b) => (a.assigned_from || "").localeCompare(b.assigned_from || ""))
      .forEach((assignment) => {
        const device = deviceMap.get(assignment.device_id);
        if (!device) return;
        const row = document.createElement("tr");
        row.innerHTML = `
          <td>${device.inventory_number}</td>
          <td>${device.device_type?.name || "—"}</td>
          <td>${device.device_type?.category || "—"}</td>
          <td>${device.serial_number || "—"}</td>
          <td>${device.status || "—"}</td>
          <td>${formatDate(assignment.assigned_from)}</td>
          <td><a class="button-link" href="/ui/devices/${device.id}">Öffnen</a></td>
        `;
        tbody.appendChild(row);
      });
  }

  function renderLocationSelect(selectedId) {
    if (!select) return;
    const placeholderOption = select.querySelector("option[value=\""]");
    const placeholderText = placeholderOption ? placeholderOption.textContent : "Bitte wählen …";
    select.innerHTML = `<option value="">${placeholderText}</option>`;
    data.vehicles
      .slice()
      .sort((a, b) => a.radio_id.localeCompare(b.radio_id))
      .forEach((vehicle) => {
        const option = document.createElement("option");
        option.value = vehicle.id;
        option.textContent = `${vehicle.radio_id} – ${vehicle.vehicle_type}`;
        select.appendChild(option);
      });
    if (selectedId) {
      select.value = selectedId;
      renderAssignments(Number(selectedId));
    }
  }

  vehicleForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(vehicleForm);
    const payload = {
      radio_id: (formData.get("radio_id") || "").toString().trim(),
      vehicle_type: (formData.get("vehicle_type") || "").toString().trim(),
      in_service_since: formData.get("in_service_since") || null,
      out_of_service: formData.get("out_of_service") || null,
    };
    if (!payload.radio_id || !payload.vehicle_type) {
      showToast("Bitte Funkkennung und Typ angeben.", "error");
      return;
    }
    try {
      const vehicle = await apiFetch("/vehicles/", {
        method: "POST",
        body: payload,
      });
      const stored = {
        id: Number(vehicle.id),
        radio_id: vehicle.radio_id,
        vehicle_type: vehicle.vehicle_type,
        in_service_since: vehicle.in_service_since || null,
        out_of_service: vehicle.out_of_service || null,
      };
      data.vehicles.push(stored);
      renderVehicleTable();
      renderLocationSelect(String(stored.id));
      vehicleForm.reset();
      showToast("Standort gespeichert.", "info");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  select?.addEventListener("change", (event) => {
    const value = Number(event.target.value);
    if (!value) {
      if (tbody) tbody.innerHTML = "";
      return;
    }
    renderAssignments(value);
  });

  renderVehicleTable();
  renderLocationSelect(select?.value);
}

function initDevices() {
  const data = readJsonScript("devices-data") || { categories: [], device_types: [] };
  const categoryForm = document.getElementById("category-form");
  const categoryTable = document.querySelector("#category-table tbody");
  const categorySelects = [document.getElementById("product-category-select")];
  const deviceTypeForm = document.getElementById("device-type-form");
  const deviceTypeTable = document.querySelector("#device-type-table tbody");
  const deviceTypeSelect = document.getElementById("device-type-select");
  const componentSerials = document.getElementById("component-serials");
  const deviceForm = document.getElementById("device-form");
  const deviceTable = document.querySelector("#device-table tbody");
  data.devices = data.devices || [];

  function updateCategorySelects() {
    const options = data.categories
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((category) => `<option value="${category.id}">${category.name}</option>`)
      .join("");
    categorySelects.forEach((select) => {
      if (!select) return;
      const placeholder = select.querySelector("option[value=\""]");
      select.innerHTML = `<option value="">${placeholder ? placeholder.textContent : "Keine"}</option>${options}`;
    });
  }

  function renderCategories() {
    if (!categoryTable) return;
    categoryTable.innerHTML = data.categories
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((category) => `<tr><td>${category.name}</td></tr>`)
      .join("");
  }

  function renderDeviceTypes() {
    if (!deviceTypeTable) return;
    deviceTypeTable.innerHTML = data.device_types
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((product) => {
        const components = product.components?.length
          ? `<ul>${product.components.map((comp) => `<li>${comp}</li>`).join("")}</ul>`
          : "—";
        const categoryName = data.categories.find((cat) => cat.id === product.category_id)?.name || "—";
        return `
          <tr>
            <td>${product.name}</td>
            <td>${categoryName}</td>
            <td>${product.manufacturer || "—"}</td>
            <td>${product.model || "—"}</td>
            <td>${components}</td>
          </tr>`;
      })
      .join("");
  }

  function renderDeviceSelect() {
    if (!deviceTypeSelect) return;
    deviceTypeSelect.innerHTML = '<option value="">Bitte wählen …</option>';
    data.device_types
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .forEach((product) => {
        const option = document.createElement("option");
        option.value = product.id;
        option.textContent = product.name;
        deviceTypeSelect.appendChild(option);
      });
  }

  function renderDeviceTable(device, append = true) {
    if (!deviceTable) return;
    if (!append) {
      deviceTable.innerHTML = "";
      data.devices
        .slice()
        .sort((a, b) => a.inventory_number.localeCompare(b.inventory_number))
        .forEach((item) => renderDeviceTable(item));
      return;
    }
    const categoryName = data.categories.find((cat) => cat.id === device.device_type?.category_id)?.name || "—";
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${device.inventory_number}</td>
      <td>${device.device_type?.name || "—"}</td>
      <td>${categoryName}</td>
      <td>${device.serial_number || "—"}</td>
      <td>${device.status || "—"}</td>
      <td><a class="button-link" href="/ui/devices/${device.id}">Öffnen</a></td>`;
    deviceTable.appendChild(row);
  }

  categoryForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(categoryForm);
    const name = (formData.get("name") || "").toString().trim();
    if (!name) return;
    try {
      const category = await apiFetch("/categories/", {
        method: "POST",
        body: { name },
      });
      data.categories.push(category);
      renderCategories();
      updateCategorySelects();
      categoryForm.reset();
      showToast("Kategorie gespeichert.", "info");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  deviceTypeForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(deviceTypeForm);
    const payload = {
      name: formData.get("name"),
      manufacturer: formData.get("manufacturer") || null,
      model: formData.get("model") || null,
      category_id: formData.get("category_id") ? Number(formData.get("category_id")) : null,
      default_mtk_interval_days: formData.get("default_mtk_interval_days")
        ? Number(formData.get("default_mtk_interval_days"))
        : null,
      default_stk_interval_days: formData.get("default_stk_interval_days")
        ? Number(formData.get("default_stk_interval_days"))
        : null,
      is_composite: formData.get("is_composite") === "on",
      components: [],
    };
    const componentLines = (formData.get("components") || "")
      .toString()
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    payload.components = componentLines.map((name) => ({ name }));
    try {
      const product = await apiFetch("/device-types/", {
        method: "POST",
        body: payload,
      });
      const stored = {
        id: product.id,
        name: product.name,
        manufacturer: product.manufacturer,
        model: product.model,
        category_id: product.category?.id || payload.category_id,
        is_composite: product.is_composite,
        components: product.components?.map((comp) => ({ id: comp.id, name: comp.name })) || [],
      };
      data.device_types.push(stored);
      renderDeviceTypes();
      renderDeviceSelect();
      deviceTypeForm.reset();
      showToast("Produkt gespeichert.", "info");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  deviceTypeSelect?.addEventListener("change", (event) => {
    const value = Number(event.target.value);
    const product = data.device_types.find((item) => item.id === value);
    if (!componentSerials) return;
    componentSerials.innerHTML = "";
    if (!product || !product.components || product.components.length === 0) {
      componentSerials.hidden = true;
      return;
    }
    componentSerials.hidden = false;
    const heading = document.createElement("h4");
    heading.textContent = "Komponenten-Seriennummern";
    componentSerials.appendChild(heading);
    product.components.forEach((component) => {
      const wrapper = document.createElement("label");
      wrapper.textContent = component.name;
      const input = document.createElement("input");
      input.name = `component_${component.id}`;
      input.dataset.componentId = component.id;
      input.placeholder = `Seriennummer ${component.name}`;
      wrapper.appendChild(input);
      componentSerials.appendChild(wrapper);
    });
  });

  deviceForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(deviceForm);
    const payload = {
      inventory_number: formData.get("inventory_number"),
      device_type_id: Number(formData.get("device_type_id")),
      serial_number: formData.get("serial_number") || null,
      purchase_date: formData.get("purchase_date") || null,
      status: formData.get("status") || "aktiv",
      notes: formData.get("notes") || null,
      component_serials: {},
    };
    const product = data.device_types.find((item) => item.id === payload.device_type_id);
    if (product && componentSerials && !componentSerials.hidden) {
      const inputs = componentSerials.querySelectorAll("input[data-component-id]");
      inputs.forEach((input) => {
        const value = input.value.trim();
        const componentTypeId = Number(input.dataset.componentId);
        if (componentTypeId && value) {
          payload.component_serials[componentTypeId] = value;
        }
      });
    }
    try {
      const device = await apiFetch("/devices/", {
        method: "POST",
        body: payload,
      });
      const stored = {
        id: device.id,
        inventory_number: device.inventory_number,
        serial_number: device.serial_number,
        status: device.status,
        device_type: {
          name: device.device_type?.name,
          category_id: device.device_type?.category?.id || null,
        },
      };
      data.devices = data.devices || [];
      data.devices.push(stored);
      renderDeviceTable(stored);
      deviceForm.reset();
      componentSerials && (componentSerials.hidden = true);
      showToast("Gerät gespeichert.", "info");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  data.devices = data.devices || [];
  updateCategorySelects();
  renderCategories();
  renderDeviceTypes();
  renderDeviceSelect();
}

function initDeviceDetail() {
  const data = readJsonScript("device-detail-data");
  if (!data) return;
  const state = {
    device: data.device,
    assignments: data.assignments || [],
    checks: data.checks || [],
    repairs: data.repairs || [],
    vehicles: data.vehicles || [],
  };
  const deviceId = state.device.id;
  const assignmentTable = document.querySelector("#assignment-table tbody");
  const checkTable = document.querySelector("#check-table tbody");
  const repairTable = document.querySelector("#repair-table tbody");
  const statusElement = document.getElementById("device-status");

  function renderAssignments() {
    if (!assignmentTable) return;
    assignmentTable.innerHTML = "";
    state.assignments.forEach((assignment) => {
      const vehicle = state.vehicles.find((item) => item.id === assignment.vehicle_id);
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${vehicle ? `${vehicle.radio_id} – ${vehicle.vehicle_type}` : "—"}</td>
        <td>${formatDate(assignment.assigned_from)}</td>
        <td>${assignment.assigned_to ? formatDate(assignment.assigned_to) : "aktiv"}</td>`;
      assignmentTable.appendChild(row);
    });
  }

  function renderChecks() {
    if (!checkTable) return;
    checkTable.innerHTML = "";
    state.checks.forEach((check) => {
      const attachments = check.attachments?.length
        ? `<ul>${check.attachments
            .map((attachment) => `<li><a href="/uploads/${attachment.file_path}" target="_blank">${attachment.description || attachment.file_path}</a></li>`)
            .join("")}</ul>`
        : "—";
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${check.check_type}</td>
        <td>${formatDate(check.performed_on)}</td>
        <td>${formatDate(check.due_on)}</td>
        <td>${check.result || "—"}</td>
        <td>${attachments}</td>
        <td>
          <form class="upload-form" data-check-id="${check.id}">
            <input type="file" name="file" accept="application/pdf" required />
            <input type="text" name="description" placeholder="Beschreibung" />
            <button type="submit">Upload</button>
          </form>
        </td>`;
      checkTable.appendChild(row);
    });
  }

  function renderRepairs() {
    if (!repairTable) return;
    repairTable.innerHTML = "";
    state.repairs.forEach((repair) => {
      const attachments = repair.attachments?.length
        ? `<ul>${repair.attachments
            .map((attachment) => `<li><a href="/uploads/${attachment.file_path}" target="_blank">${attachment.description || attachment.file_path}</a></li>`)
            .join("")}</ul>`
        : "—";
      const row = document.createElement("tr");
      row.dataset.repairId = repair.id;
      row.innerHTML = `
        <td>${formatDate(repair.reported_on)}</td>
        <td>${formatDate(repair.repaired_on)}</td>
        <td>${repair.reported_issue}</td>
        <td>${repair.repair_action || "—"}</td>
        <td>${attachments}</td>
        <td>
          <form class="upload-form" data-repair-id="${repair.id}">
            <input type="file" name="file" accept="application/pdf" required />
            <input type="text" name="description" placeholder="Beschreibung" />
            <button type="submit">Upload</button>
          </form>
        </td>`;
      repairTable.appendChild(row);
    });
  }

  async function refreshDevice() {
    try {
      const device = await apiFetch(`/devices/${deviceId}`);
      state.device = device;
      if (statusElement) {
        statusElement.textContent = device.status;
      }
    } catch (err) {
      console.warn("Gerät konnte nicht aktualisiert werden", err);
    }
  }

  document.getElementById("assignment-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.target);
    const payload = {
      device_id: deviceId,
      vehicle_id: Number(formData.get("vehicle_id")),
      assigned_by: formData.get("assigned_by") || null,
      notes: formData.get("notes") || null,
      assigned_from: new Date().toISOString(),
    };
    try {
      await apiFetch("/assignments/", { method: "POST", body: payload });
      await refreshHistory(deviceId, state);
      renderAssignments();
      showToast("Zuordnung gespeichert.", "info");
      event.target.reset();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  document.getElementById("check-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.target);
    const payload = {
      device_id: deviceId,
      check_type: formData.get("check_type"),
      performed_on: formData.get("performed_on"),
      due_on: formData.get("due_on") || null,
      performed_by: formData.get("performed_by") || null,
      result: formData.get("result") || null,
      notes: formData.get("notes") || null,
    };
    try {
      await apiFetch("/checks/", { method: "POST", body: payload });
      await refreshHistory(deviceId, state);
      renderChecks();
      showToast("Prüfung erfasst.", "info");
      event.target.reset();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  document.getElementById("repair-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(event.target);
    const payload = {
      device_id: deviceId,
      reported_on: formData.get("reported_on"),
      repaired_on: formData.get("repaired_on") || null,
      reported_issue: formData.get("reported_issue"),
      repair_action: formData.get("repair_action") || null,
      repaired_by: formData.get("repaired_by") || null,
      cost: formData.get("cost") ? Number(formData.get("cost")) : null,
      notes: formData.get("notes") || null,
    };
    try {
      await apiFetch("/repairs/", { method: "POST", body: payload });
      await refreshHistory(deviceId, state);
      await refreshDevice();
      renderRepairs();
      showToast("Reparatur erfasst.", "info");
      event.target.reset();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (!form.classList.contains("upload-form")) return;
    event.preventDefault();
    const formData = new FormData(form);
    try {
      if (form.dataset.checkId) {
        const attachment = await apiFetch(`/checks/${form.dataset.checkId}/attachments`, {
          method: "POST",
          body: formData,
        });
        const check = state.checks.find((item) => String(item.id) === form.dataset.checkId);
        if (check) {
          check.attachments = check.attachments || [];
          check.attachments.push(attachment);
        }
        renderChecks();
        showToast("Dokument hochgeladen.", "info");
      } else if (form.dataset.repairId) {
        const attachment = await apiFetch(`/repairs/${form.dataset.repairId}/attachments`, {
          method: "POST",
          body: formData,
        });
        const repair = state.repairs.find((item) => String(item.id) === form.dataset.repairId);
        if (repair) {
          repair.attachments = repair.attachments || [];
          repair.attachments.push(attachment);
        }
        renderRepairs();
        showToast("Dokument hochgeladen.", "info");
      }
      form.reset();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  renderAssignments();
  renderChecks();
  renderRepairs();
}

function initRepairFilter() {
  const data = readJsonScript("repair-filter-data") || { devices: [] };
  const form = document.getElementById("repair-filter");
  const categorySelect = document.getElementById("filter-category");
  const serialSelect = document.getElementById("filter-serial");
  const tableBody = document.querySelector("#repair-filter-table tbody");

  function updateSerialOptions() {
    if (!serialSelect) return;
    const categoryId = Number(categorySelect.value);
    const devices = data.devices
      .filter((device) => !categoryId || device.device_type?.category_id === categoryId)
      .filter((device) => device.serial_number)
      .sort((a, b) => a.serial_number.localeCompare(b.serial_number));
    serialSelect.innerHTML = '<option value="">Alle</option>';
    devices.forEach((device) => {
      const option = document.createElement("option");
      option.value = device.serial_number;
      option.textContent = `${device.serial_number} – ${device.device_type?.name || "Gerät"}`;
      serialSelect.appendChild(option);
    });
  }

  categorySelect?.addEventListener("change", updateSerialOptions);

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const params = new URLSearchParams();
    if (categorySelect?.value) params.set("category_id", categorySelect.value);
    if (serialSelect?.value) params.set("serial_number", serialSelect.value);
    try {
      const repairs = await apiFetch(`/repairs/?${params.toString()}`);
      tableBody.innerHTML = "";
      if (!repairs || repairs.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");
        cell.colSpan = 7;
        cell.textContent = "Keine Reparaturen gefunden.";
        row.appendChild(cell);
        tableBody.appendChild(row);
        return;
      }
      repairs.forEach((repair) => {
        const device = data.devices.find((item) => item.id === repair.device_id);
        const categoryName = device?.device_type?.category || "—";
        const row = document.createElement("tr");
        row.innerHTML = `
          <td><a href="/ui/devices/${repair.device_id}">${device?.inventory_number || repair.device_id}</a></td>
          <td>${device?.serial_number || "—"}</td>
          <td>${categoryName}</td>
          <td>${formatDate(repair.reported_on)}</td>
          <td>${formatDate(repair.repaired_on)}</td>
          <td>${repair.reported_issue}</td>
          <td>${repair.repair_action || "—"}</td>`;
        tableBody.appendChild(row);
      });
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  updateSerialOptions();
}

document.addEventListener("DOMContentLoaded", () => {
  const page = document.body.dataset.page;
  if (page === "overview") {
    initOverview();
  } else if (page === "devices") {
    initDevices();
  } else if (page === "device-detail") {
    initDeviceDetail();
  } else if (page === "repairs") {
    initRepairFilter();
  }
});
