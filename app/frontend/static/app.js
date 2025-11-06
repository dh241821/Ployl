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
  const vehicleIdInput = vehicleForm?.querySelector('input[name="vehicle_id"]');
  const vehicleCancel = document.getElementById("vehicle-cancel");
  const vehicleSubmit = vehicleForm?.querySelector('button[type="submit"]');

  let assignments = (data.assignments || []).map((assignment) => ({
    ...assignment,
    vehicle_id: Number(assignment.vehicle_id),
    device_id: Number(assignment.device_id),
  }));
  const deviceMap = new Map((data.devices || []).map((device) => [device.id, device]));
  data.vehicles = (data.vehicles || []).map((vehicle) => ({
    ...vehicle,
    id: Number(vehicle.id),
  }));

  function mapVehicle(item) {
    return {
      id: Number(item.id),
      radio_id: item.radio_id,
      vehicle_type: item.vehicle_type,
      in_service_since: item.in_service_since || null,
      out_of_service: item.out_of_service || null,
    };
  }

  function resetVehicleForm() {
    if (!vehicleForm) return;
    vehicleForm.reset();
    if (vehicleIdInput) vehicleIdInput.value = "";
    if (vehicleSubmit) vehicleSubmit.textContent = "Standort speichern";
    vehicleCancel?.setAttribute("hidden", "hidden");
  }

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
          <td>
            <div class="table-actions">
              <button type="button" class="secondary small" data-action="edit" data-id="${vehicle.id}">Bearbeiten</button>
              <button type="button" class="danger small" data-action="delete" data-id="${vehicle.id}">Löschen</button>
            </div>
          </td>`;
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
          <td>
            <div class="table-actions">
              <a class="button-link" href="/ui/devices/${device.id}">Öffnen</a>
            </div>
          </td>`;
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
      select.value = String(selectedId);
      renderAssignments(Number(selectedId));
    }
  }

  async function reloadVehicles(selectedId) {
    const refreshed = await apiFetch("/vehicles/");
    data.vehicles = (refreshed || []).map(mapVehicle);
    renderVehicleTable();
    renderLocationSelect(selectedId);
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

    const editingId = vehicleIdInput?.value ? Number(vehicleIdInput.value) : null;

    try {
      if (editingId) {
        await apiFetch(`/vehicles/${editingId}`, {
          method: "PATCH",
          body: payload,
        });
        await reloadVehicles(editingId);
        showToast("Standort aktualisiert.", "info");
      } else {
        const vehicle = await apiFetch("/vehicles/", {
          method: "POST",
          body: payload,
        });
        await reloadVehicles(Number(vehicle.id));
        showToast("Standort gespeichert.", "info");
      }
      resetVehicleForm();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  vehicleTable?.addEventListener("click", async (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("button[data-action]") : null;
    if (!button) return;
    const id = Number(button.dataset.id);
    if (!id) return;
    const vehicle = data.vehicles.find((item) => item.id === id);
    if (!vehicle && button.dataset.action === "edit") {
      showToast("Standort nicht gefunden.", "error");
      return;
    }
    if (button.dataset.action === "edit") {
      if (!vehicleForm || !vehicle) return;
      if (vehicleIdInput) vehicleIdInput.value = String(vehicle.id);
      const radioInput = vehicleForm.querySelector('input[name="radio_id"]');
      const typeInput = vehicleForm.querySelector('input[name="vehicle_type"]');
      const inServiceInput = vehicleForm.querySelector('input[name="in_service_since"]');
      const outServiceInput = vehicleForm.querySelector('input[name="out_of_service"]');
      if (radioInput) radioInput.value = vehicle.radio_id;
      if (typeInput) typeInput.value = vehicle.vehicle_type;
      if (inServiceInput) inServiceInput.value = vehicle.in_service_since ? vehicle.in_service_since : "";
      if (outServiceInput) outServiceInput.value = vehicle.out_of_service ? vehicle.out_of_service : "";
      if (vehicleSubmit) vehicleSubmit.textContent = "Standort aktualisieren";
      vehicleCancel?.removeAttribute("hidden");
      radioInput?.focus();
    } else if (button.dataset.action === "delete") {
      if (!confirm("Standort wirklich löschen? Zugeordnete Geräte werden nicht entfernt.")) return;
      try {
        await apiFetch(`/vehicles/${id}`, { method: "DELETE" });
        data.vehicles = data.vehicles.filter((item) => item.id !== id);
        assignments = assignments.filter((assignment) => assignment.vehicle_id !== id);
        renderVehicleTable();
        const currentSelection = select ? Number(select.value) : null;
        const nextSelection = currentSelection === id ? null : currentSelection;
        renderLocationSelect(nextSelection || undefined);
        if (currentSelection === id && tbody) {
          tbody.innerHTML = "";
        }
        resetVehicleForm();
        showToast("Standort entfernt.", "info");
      } catch (err) {
        showToast(err.message, "error");
      }
    }
  });

  vehicleCancel?.addEventListener("click", () => {
    resetVehicleForm();
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
  if (select?.value) {
    renderLocationSelect(Number(select.value));
  } else {
    renderLocationSelect();
  }
}

function initDevices() {
  const data =
    readJsonScript("devices-data") || {
      categories: [],
      device_types: [],
      devices: [],
      locations: [],
    };

  const categoryForm = document.getElementById("category-form");
  const categoryTable = document.querySelector("#category-table tbody");
  const categorySelects = [
    document.getElementById("product-category-select"),
    document.getElementById("device-filter-category"),
  ];
  const categoryIdInput = categoryForm?.querySelector('input[name="category_id"]');
  const categoryCancel = document.getElementById("category-cancel");
  const categorySubmit = categoryForm?.querySelector('button[type="submit"]');

  const deviceTypeForm = document.getElementById("device-type-form");
  const deviceTypeTable = document.querySelector("#device-type-table tbody");
  const deviceTypeSelect = document.getElementById("device-type-select");
  const deviceTypeFilterSelect = document.getElementById("device-filter-type");
  const deviceTypeSelects = [deviceTypeSelect, deviceTypeFilterSelect];
  const deviceTypeIdInput = deviceTypeForm?.querySelector('input[name="device_type_id"]');
  const deviceTypeCancel = document.getElementById("device-type-cancel");
  const deviceTypeSubmit = deviceTypeForm?.querySelector('button[type="submit"]');

  const filterForm = document.getElementById("device-filter-form");
  const filterReset = document.getElementById("device-filter-reset");
  const exportButton = document.getElementById("device-export");
  const locationFilterSelect = document.getElementById("device-filter-location");
  const assignedFilterSelect = document.getElementById("device-filter-assigned");
  const statusFilterInput = document.getElementById("device-filter-status");
  const searchFilterInput = document.getElementById("device-filter-search");

  const componentSerials = document.getElementById("component-serials");

  const deviceForm = document.getElementById("device-form");
  const deviceTable = document.querySelector("#device-table tbody");
  const deviceIdInput = deviceForm?.querySelector('input[name="device_id"]');
  const deviceCancel = document.getElementById("device-cancel");
  const deviceSubmit = deviceForm?.querySelector('button[type="submit"]');
  const inventoryInput = deviceForm?.querySelector('input[name="inventory_number"]');
  const serialInput = deviceForm?.querySelector('input[name="serial_number"]');
  const purchaseInput = deviceForm?.querySelector('input[name="purchase_date"]');
  const statusInput = deviceForm?.querySelector('input[name="status"]');
  const notesInput = deviceForm?.querySelector('textarea[name="notes"]');

  let currentFilters = {};

  function mapCategory(item) {
    return { id: Number(item.id), name: item.name };
  }

  function mapDeviceType(item) {
    const categoryId = item.category_id ?? item.category?.id ?? null;
    const components = Array.isArray(item.components)
      ? item.components.map((component) =>
          typeof component === "string"
            ? { id: undefined, name: component }
            : { id: component.id, name: component.name }
        )
      : [];
    return {
      id: Number(item.id),
      name: item.name,
      manufacturer: item.manufacturer,
      model: item.model,
      category_id: categoryId,
      is_composite: Boolean(item.is_composite),
      default_mtk_interval_days: item.default_mtk_interval_days || null,
      default_stk_interval_days: item.default_stk_interval_days || null,
      components,
    };
  }

  function mapLocation(item) {
    const id = Number(item.id);
    const radioId = item.radio_id;
    const vehicleType = item.vehicle_type || "";
    const label = vehicleType ? `${radioId} (${vehicleType})` : radioId;
    return { id, radio_id: radioId, vehicle_type: vehicleType, label };
  }

  function mapDevice(item) {
    const deviceType = item.device_type || {};
    const category = deviceType.category || {};
    const assignment = item.active_assignment || item.current_assignment || null;
    const vehicle = assignment?.vehicle || null;
    const locationId = vehicle?.id ?? assignment?.vehicle_id ?? null;
    const fallbackLabel = vehicle
      ? `${vehicle.radio_id}${vehicle.vehicle_type ? ` (${vehicle.vehicle_type})` : ""}`
      : null;
    return {
      id: Number(item.id),
      inventory_number: item.inventory_number,
      serial_number: item.serial_number || null,
      status: item.status || "",
      purchase_date: item.purchase_date || null,
      notes: item.notes || null,
      device_type_id: deviceType.id || item.device_type_id || null,
      device_type_name: deviceType.name || item.device_type_name || deviceType?.name || "—",
      category_id: category.id ?? item.category_id ?? deviceType?.category?.id ?? null,
      location_id: locationId ? Number(locationId) : null,
      location_label: fallbackLabel,
      assigned: Boolean(locationId),
    };
  }

  data.categories = (data.categories || []).map(mapCategory);
  data.device_types = (data.device_types || []).map(mapDeviceType);
  data.locations = (data.locations || []).map(mapLocation);
  data.devices = (data.devices || []).map(mapDevice);

  function updateCategorySelects() {
    const options = data.categories
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((category) => `<option value="${category.id}">${category.name}</option>`)
      .join("");
    categorySelects.forEach((select) => {
      if (!select) return;
      const current = select.value;
      const placeholder = select.dataset.placeholder || "";
      const fallback = placeholder || (select.required ? "Bitte wählen …" : "Keine");
      select.innerHTML = `<option value="">${fallback}</option>${options}`;
      if (current) {
        select.value = current;
      }
    });
  }

  function renderCategories() {
    if (!categoryTable) return;
    categoryTable.innerHTML = data.categories
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .map(
        (category) => `
          <tr data-category-id="${category.id}">
            <td>${category.name}</td>
            <td>
              <div class="table-actions">
                <button type="button" class="secondary small" data-action="edit" data-id="${category.id}">Bearbeiten</button>
                <button type="button" class="danger small" data-action="delete" data-id="${category.id}">Löschen</button>
              </div>
            </td>
          </tr>`
      )
      .join("");
  }

  function renderDeviceTypes() {
    if (!deviceTypeTable) return;
    deviceTypeTable.innerHTML = data.device_types
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((product) => {
        const components = product.components.length
          ? `<ul>${product.components.map((component) => `<li>${component.name}</li>`).join("")}</ul>`
          : "—";
        const categoryName = data.categories.find((cat) => cat.id === product.category_id)?.name || "—";
        return `
          <tr data-device-type-id="${product.id}">
            <td>${product.name}</td>
            <td>${categoryName}</td>
            <td>${product.manufacturer || "—"}</td>
            <td>${product.model || "—"}</td>
            <td>${components}</td>
            <td>
              <div class="table-actions">
                <button type="button" class="secondary small" data-action="edit" data-id="${product.id}">Bearbeiten</button>
                <button type="button" class="secondary small" data-action="add-component" data-id="${product.id}">Komponente</button>
                <button type="button" class="danger small" data-action="delete" data-id="${product.id}">Löschen</button>
              </div>
            </td>
          </tr>`;
      })
      .join("");
  }

  function renderDeviceTypeSelects() {
    deviceTypeSelects.forEach((select) => {
      if (!select) return;
      const current = select.value;
      const placeholder = select.dataset.placeholder || "";
      const fallback = placeholder || (select.required ? "Bitte wählen …" : "Alle");
      select.innerHTML = `<option value="">${fallback}</option>`;
      data.device_types
        .slice()
        .sort((a, b) => a.name.localeCompare(b.name))
        .forEach((product) => {
          const option = document.createElement("option");
          option.value = product.id;
          option.textContent = product.name;
          select.appendChild(option);
        });
      if (current) {
        select.value = current;
      }
    });
  }

  function renderLocationFilter() {
    if (!locationFilterSelect) return;
    const placeholder = locationFilterSelect.dataset.placeholder || "Alle";
    const current = currentFilters.location_id ? String(currentFilters.location_id) : locationFilterSelect.value;
    locationFilterSelect.innerHTML = `<option value="">${placeholder}</option>`;
    data.locations
      .slice()
      .sort((a, b) => a.radio_id.localeCompare(b.radio_id))
      .forEach((location) => {
        const option = document.createElement("option");
        option.value = location.id;
        option.textContent = location.label;
        locationFilterSelect.appendChild(option);
      });
    if (current) {
      locationFilterSelect.value = current;
    }
  }

  function getLocationLabel(device) {
    if (device.location_id) {
      const match = data.locations.find((location) => location.id === device.location_id);
      if (match) return match.label;
    }
    return device.location_label || "—";
  }

  function renderDevices() {
    if (!deviceTable) return;
    deviceTable.innerHTML = "";
    data.devices
      .slice()
      .sort((a, b) => a.inventory_number.localeCompare(b.inventory_number))
      .forEach((device) => {
        const product = data.device_types.find((item) => item.id === device.device_type_id);
        const productName = product ? product.name : device.device_type_name || "—";
        const categoryName = product
          ? data.categories.find((cat) => cat.id === product.category_id)?.name || "—"
          : data.categories.find((cat) => cat.id === device.category_id)?.name || "—";
        const locationLabel = getLocationLabel(device);
        const row = document.createElement("tr");
        row.dataset.deviceId = device.id;
        row.innerHTML = `
          <td>${device.inventory_number}</td>
          <td>${productName}</td>
          <td>${categoryName}</td>
          <td>${device.serial_number || "—"}</td>
          <td>${locationLabel || "—"}</td>
          <td>${device.status || "—"}</td>
          <td>
            <div class="table-actions">
              <button type="button" class="secondary small" data-action="edit" data-id="${device.id}">Bearbeiten</button>
              <button type="button" class="danger small" data-action="delete" data-id="${device.id}">Löschen</button>
              <a class="button-link" href="/ui/devices/${device.id}">Öffnen</a>
            </div>
          </td>`;
        deviceTable.appendChild(row);
      });
  }

  function resetCategoryForm() {
    categoryForm?.reset();
    if (categoryIdInput) categoryIdInput.value = "";
    if (categorySubmit) categorySubmit.textContent = "Kategorie speichern";
    categoryCancel?.setAttribute("hidden", "hidden");
  }

  function resetDeviceTypeForm() {
    deviceTypeForm?.reset();
    if (deviceTypeIdInput) deviceTypeIdInput.value = "";
    if (deviceTypeSubmit) deviceTypeSubmit.textContent = "Produkt speichern";
    deviceTypeCancel?.setAttribute("hidden", "hidden");
  }

  function resetDeviceForm() {
    deviceForm?.reset();
    if (deviceIdInput) deviceIdInput.value = "";
    inventoryInput?.removeAttribute("disabled");
    deviceTypeSelect?.removeAttribute("disabled");
    if (deviceSubmit) deviceSubmit.textContent = "Gerät speichern";
    deviceCancel?.setAttribute("hidden", "hidden");
    if (componentSerials) {
      componentSerials.innerHTML = "";
      componentSerials.hidden = true;
    }
  }

  function syncFilterForm() {
    if (categorySelects[1]) {
      categorySelects[1].value = currentFilters.category_id ? String(currentFilters.category_id) : "";
    }
    if (deviceTypeFilterSelect) {
      deviceTypeFilterSelect.value = currentFilters.device_type_id ? String(currentFilters.device_type_id) : "";
    }
    if (locationFilterSelect) {
      locationFilterSelect.value = currentFilters.location_id ? String(currentFilters.location_id) : "";
    }
    if (assignedFilterSelect) {
      assignedFilterSelect.value = currentFilters.assigned || "";
    }
    if (statusFilterInput) {
      statusFilterInput.value = currentFilters.status || "";
    }
    if (searchFilterInput) {
      searchFilterInput.value = currentFilters.search || "";
    }
  }

  async function refreshCategories() {
    const refreshed = await apiFetch("/categories/");
    data.categories = (refreshed || []).map(mapCategory);
    renderCategories();
    updateCategorySelects();
    renderDeviceTypes();
    renderDeviceTypeSelects();
    renderDevices();
    syncFilterForm();
  }

  async function loadDeviceTypes() {
    const refreshed = await apiFetch("/device-types/");
    data.device_types = (refreshed || []).map(mapDeviceType);
    renderDeviceTypes();
    renderDeviceTypeSelects();
    syncFilterForm();
    deviceTypeSelect?.dispatchEvent(new Event("change"));
    renderDevices();
  }

  function buildFilterParams(filters) {
    const params = new URLSearchParams();
    if (filters.category_id) params.set("category_id", String(filters.category_id));
    if (filters.device_type_id) params.set("device_type_id", String(filters.device_type_id));
    if (filters.location_id) params.set("location_id", String(filters.location_id));
    if (filters.status) params.set("status", filters.status);
    if (filters.search) params.set("search", filters.search);
    if (filters.assigned === "assigned") params.set("assigned", "true");
    if (filters.assigned === "unassigned") params.set("assigned", "false");
    return params;
  }

  async function loadDevices(filters = currentFilters) {
    currentFilters = {
      category_id: filters.category_id || null,
      device_type_id: filters.device_type_id || null,
      location_id: filters.location_id || null,
      assigned: filters.assigned || "",
      status: filters.status || "",
      search: filters.search || "",
    };
    const params = buildFilterParams(currentFilters);
    const query = params.toString();
    const refreshed = await apiFetch(query ? `/devices/?${query}` : "/devices/");
    data.devices = (refreshed || []).map(mapDevice);
    renderDevices();
    syncFilterForm();
  }

  async function loadLocations() {
    const refreshed = await apiFetch("/vehicles/");
    if (!Array.isArray(refreshed)) return;
    data.locations = refreshed.map(mapLocation);
    renderLocationFilter();
    renderDevices();
    syncFilterForm();
  }

  categoryForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(categoryForm);
    const name = (formData.get("name") || "").toString().trim();
    if (!name) return;
    const editingId = categoryIdInput?.value ? Number(categoryIdInput.value) : null;
    try {
      if (editingId) {
        await apiFetch(`/categories/${editingId}`, {
          method: "PATCH",
          body: { name },
        });
        showToast("Kategorie aktualisiert.", "info");
      } else {
        await apiFetch("/categories/", {
          method: "POST",
          body: { name },
        });
        showToast("Kategorie gespeichert.", "info");
      }
      await refreshCategories();
      resetCategoryForm();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  categoryTable?.addEventListener("click", async (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("button[data-action]") : null;
    if (!button) return;
    const id = Number(button.dataset.id);
    if (!id) return;
    const category = data.categories.find((item) => item.id === id);
    if (button.dataset.action === "edit") {
      if (!categoryForm || !category) return;
      if (categoryIdInput) categoryIdInput.value = String(category.id);
      const nameInput = categoryForm.querySelector('input[name="name"]');
      if (nameInput) nameInput.value = category.name;
      if (categorySubmit) categorySubmit.textContent = "Kategorie aktualisieren";
      categoryCancel?.removeAttribute("hidden");
      nameInput?.focus();
    } else if (button.dataset.action === "delete") {
      if (!confirm("Kategorie wirklich löschen? Zugeordnete Produkte verlieren ihre Kategorie.")) return;
      try {
        await apiFetch(`/categories/${id}`, { method: "DELETE" });
        await refreshCategories();
        resetCategoryForm();
        showToast("Kategorie entfernt.", "info");
      } catch (err) {
        showToast(err.message, "error");
      }
    }
  });

  categoryCancel?.addEventListener("click", () => {
    resetCategoryForm();
  });

  deviceTypeForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(deviceTypeForm);
    const editingId = deviceTypeIdInput?.value ? Number(deviceTypeIdInput.value) : null;
    const basePayload = {
      name: (formData.get("name") || "").toString().trim(),
      manufacturer: (formData.get("manufacturer") || "").toString().trim() || null,
      model: (formData.get("model") || "").toString().trim() || null,
      category_id: formData.get("category_id") ? Number(formData.get("category_id")) : null,
      default_mtk_interval_days: formData.get("default_mtk_interval_days")
        ? Number(formData.get("default_mtk_interval_days"))
        : null,
      default_stk_interval_days: formData.get("default_stk_interval_days")
        ? Number(formData.get("default_stk_interval_days"))
        : null,
      is_composite: formData.get("is_composite") === "on",
    };
    if (!basePayload.name) {
      showToast("Bitte einen Produktnamen angeben.", "error");
      return;
    }
    const componentLines = (formData.get("components") || "")
      .toString()
      .split(/?
/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((name) => ({ name }));

    try {
      if (editingId) {
        await apiFetch(`/device-types/${editingId}`, {
          method: "PATCH",
          body: basePayload,
        });
        if (componentLines.length) {
          await apiFetch(`/device-types/${editingId}/components`, {
            method: "POST",
            body: componentLines,
          });
        }
        showToast("Produkt aktualisiert.", "info");
      } else {
        await apiFetch("/device-types/", {
          method: "POST",
          body: { ...basePayload, components: componentLines },
        });
        showToast("Produkt gespeichert.", "info");
      }
      await loadDeviceTypes();
      await loadDevices();
      resetDeviceTypeForm();
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  deviceTypeTable?.addEventListener("click", async (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("button[data-action]") : null;
    if (!button) return;
    const id = Number(button.dataset.id);
    if (!id) return;
    const product = data.device_types.find((item) => item.id === id);
    if (button.dataset.action === "edit") {
      if (!deviceTypeForm || !product) return;
      if (deviceTypeIdInput) deviceTypeIdInput.value = String(product.id);
      const nameInput = deviceTypeForm.querySelector('input[name="name"]');
      const manufacturerInput = deviceTypeForm.querySelector('input[name="manufacturer"]');
      const modelInput = deviceTypeForm.querySelector('input[name="model"]');
      const categorySelect = deviceTypeForm.querySelector('select[name="category_id"]');
      const mtkInput = deviceTypeForm.querySelector('input[name="default_mtk_interval_days"]');
      const stkInput = deviceTypeForm.querySelector('input[name="default_stk_interval_days"]');
      const compositeInput = deviceTypeForm.querySelector('input[name="is_composite"]');
      if (nameInput) nameInput.value = product.name;
      if (manufacturerInput) manufacturerInput.value = product.manufacturer || "";
      if (modelInput) modelInput.value = product.model || "";
      if (categorySelect) categorySelect.value = product.category_id ? String(product.category_id) : "";
      if (mtkInput) mtkInput.value = product.default_mtk_interval_days || "";
      if (stkInput) stkInput.value = product.default_stk_interval_days || "";
      if (compositeInput) compositeInput.checked = Boolean(product.is_composite);
      const componentTextarea = deviceTypeForm.querySelector('textarea[name="components"]');
      if (componentTextarea) componentTextarea.value = "";
      if (deviceTypeSubmit) deviceTypeSubmit.textContent = "Produkt aktualisieren";
      deviceTypeCancel?.removeAttribute("hidden");
      nameInput?.focus();
    } else if (button.dataset.action === "add-component") {
      const input = prompt("Neue Komponente hinzufügen (mehrere Einträge mit Zeilenumbruch)");
      if (!input) return;
      const components = input
        .split(/?
/)
        .map((line) => line.trim())
        .filter(Boolean)
        .map((name) => ({ name }));
      if (!components.length) return;
      try {
        await apiFetch(`/device-types/${id}/components`, {
          method: "POST",
          body: components,
        });
        await loadDeviceTypes();
        showToast("Komponenten ergänzt.", "info");
      } catch (err) {
        showToast(err.message, "error");
      }
    } else if (button.dataset.action === "delete") {
      if (!confirm("Produkt wirklich löschen? Zugeordnete Geräte verhindern das Löschen.")) return;
      try {
        await apiFetch(`/device-types/${id}`, { method: "DELETE" });
        await loadDeviceTypes();
        await loadDevices();
        showToast("Produkt entfernt.", "info");
      } catch (err) {
        showToast(err.message, "error");
      }
    }
  });

  deviceTypeCancel?.addEventListener("click", () => {
    resetDeviceTypeForm();
  });

  deviceTypeSelect?.addEventListener("change", (event) => {
    const value = Number(event.target.value);
    const product = data.device_types.find((item) => item.id === value);
    if (!componentSerials) return;
    componentSerials.innerHTML = "";
    if (!product || product.components.length === 0) {
      componentSerials.hidden = true;
      return;
    }
    componentSerials.hidden = false;
    const heading = document.createElement("h4");
    heading.textContent = "Komponenten-Seriennummern";
    componentSerials.appendChild(heading);
    product.components.forEach((component) => {
      if (!component.id) return;
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
    if (!deviceForm) return;
    const formData = new FormData(deviceForm);
    const editingId = deviceIdInput?.value ? Number(deviceIdInput.value) : null;
    if (editingId) {
      const payload = {
        serial_number: (formData.get("serial_number") || "").toString().trim() || null,
        purchase_date: formData.get("purchase_date") || null,
        status: (formData.get("status") || "").toString().trim() || null,
        notes: (formData.get("notes") || "").toString().trim() || null,
      };
      try {
        await apiFetch(`/devices/${editingId}`, {
          method: "PATCH",
          body: payload,
        });
        await loadDevices();
        resetDeviceForm();
        showToast("Gerät aktualisiert.", "info");
      } catch (err) {
        showToast(err.message, "error");
      }
      return;
    }

    const payload = {
      inventory_number: formData.get("inventory_number"),
      device_type_id: Number(formData.get("device_type_id")),
      serial_number: formData.get("serial_number") || null,
      purchase_date: formData.get("purchase_date") || null,
      status: (formData.get("status") || "aktiv").toString().trim() || "aktiv",
      notes: formData.get("notes") || null,
      component_serials: {},
    };

    if (!payload.inventory_number || !payload.device_type_id) {
      showToast("Bitte Inventarnummer und Produkt auswählen.", "error");
      return;
    }

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
      await apiFetch("/devices/", {
        method: "POST",
        body: payload,
      });
      await loadDevices();
      resetDeviceForm();
      showToast("Gerät gespeichert.", "info");
    } catch (err) {
      showToast(err.message, "error");
    }
  });

  deviceTable?.addEventListener("click", async (event) => {
    const button = event.target instanceof HTMLElement ? event.target.closest("button[data-action]") : null;
    if (!button) return;
    const id = Number(button.dataset.id);
    if (!id) return;
    const device = data.devices.find((item) => item.id === id);
    if (button.dataset.action === "edit") {
      if (!deviceForm || !device) return;
      if (deviceIdInput) deviceIdInput.value = String(device.id);
      if (inventoryInput) {
        inventoryInput.value = device.inventory_number;
        inventoryInput.setAttribute("disabled", "disabled");
      }
      if (deviceTypeSelect) {
        deviceTypeSelect.value = device.device_type_id ? String(device.device_type_id) : "";
        deviceTypeSelect.setAttribute("disabled", "disabled");
      }
      if (serialInput) serialInput.value = device.serial_number || "";
      if (purchaseInput) purchaseInput.value = device.purchase_date || "";
      if (statusInput) statusInput.value = device.status || "aktiv";
      if (notesInput) notesInput.value = device.notes || "";
      if (componentSerials) {
        componentSerials.innerHTML = "";
        componentSerials.hidden = true;
      }
      if (deviceSubmit) deviceSubmit.textContent = "Gerät aktualisieren";
      deviceCancel?.removeAttribute("hidden");
      serialInput?.focus();
    } else if (button.dataset.action === "delete") {
      if (!confirm("Gerät wirklich löschen? Alle zugehörigen Einträge werden entfernt.")) return;
      try {
        await apiFetch(`/devices/${id}`, { method: "DELETE" });
        await loadDevices();
        resetDeviceForm();
        showToast("Gerät entfernt.", "info");
      } catch (err) {
        showToast(err.message, "error");
      }
    }
  });

  deviceCancel?.addEventListener("click", () => {
    resetDeviceForm();
  });

  filterForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(filterForm);
    const filters = {
      category_id: formData.get("category_id") ? Number(formData.get("category_id")) : null,
      device_type_id: formData.get("device_type_id") ? Number(formData.get("device_type_id")) : null,
      location_id: formData.get("location_id") ? Number(formData.get("location_id")) : null,
      assigned: (formData.get("assigned") || "").toString(),
      status: (formData.get("status") || "").toString().trim(),
      search: (formData.get("search") || "").toString().trim(),
    };
    if (filters.assigned !== "assigned" && filters.assigned !== "unassigned") {
      filters.assigned = "";
    }
    await loadDevices(filters);
  });

  filterReset?.addEventListener("click", async () => {
    filterForm?.reset();
    await loadDevices({});
  });

  exportButton?.addEventListener("click", () => {
    const params = buildFilterParams(currentFilters);
    const query = params.toString();
    const url = query ? `/devices/export?${query}` : "/devices/export";
    window.open(url, "_blank");
  });

  updateCategorySelects();
  renderCategories();
  renderDeviceTypes();
  renderDeviceTypeSelects();
  renderLocationFilter();
  renderDevices();
  syncFilterForm();
  loadLocations();
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
