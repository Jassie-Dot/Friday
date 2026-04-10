async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

function renderList(container, items, formatter) {
  if (!items.length) {
    container.innerHTML = '<div class="empty">Nothing yet.</div>';
    return;
  }
  container.innerHTML = items.map(formatter).join("");
}

async function refreshHealth() {
  const payload = await fetchJson("/api/health");
  const health = payload.data;
  document.getElementById("health-status").textContent = health.status.toUpperCase();
  document.getElementById("primary-model").textContent = health.models.primary;
  document.getElementById("fast-model").textContent = health.models.fast;
}

async function refreshTasks() {
  const payload = await fetchJson("/api/tasks");
  const tasks = payload.data.tasks || [];
  renderList(document.getElementById("task-list"), tasks.reverse(), (task) => `
    <article class="list-item">
      <div class="list-top">
        <strong>${task.status.toUpperCase()}</strong>
        <span>${task.id.slice(0, 8)}</span>
      </div>
      <p>${task.objective}</p>
      <small>${task.summary || "No summary yet."}</small>
    </article>
  `);
}

async function refreshEvents() {
  const payload = await fetchJson("/api/events");
  const events = payload.data.events || [];
  renderList(document.getElementById("event-list"), events.reverse(), (event) => `
    <article class="list-item">
      <div class="list-top">
        <strong>${event.source.toUpperCase()}</strong>
        <span>${event.message_type}</span>
      </div>
      <small>${JSON.stringify(event.payload)}</small>
    </article>
  `);
}

async function submitTask(event) {
  event.preventDefault();
  const objective = document.getElementById("objective").value.trim();
  if (!objective) {
    return;
  }

  const output = document.getElementById("task-output");
  output.textContent = "Running task...";

  try {
    const payload = await fetchJson("/api/tasks/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ objective, context: {}, max_steps: 8, auto_retry: true, store_memory: true }),
    });
    output.textContent = JSON.stringify(payload.data, null, 2);
    await refreshTasks();
    await refreshEvents();
  } catch (error) {
    output.textContent = `Task failed: ${error.message}`;
  }
}

document.getElementById("task-form").addEventListener("submit", submitTask);

async function tick() {
  try {
    await Promise.all([refreshHealth(), refreshTasks(), refreshEvents()]);
  } catch (error) {
    document.getElementById("health-status").textContent = "ERROR";
  }
}

tick();
setInterval(tick, 5000);
