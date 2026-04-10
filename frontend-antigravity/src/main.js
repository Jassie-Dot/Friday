import "./style.css";

const RAW_API_URL = import.meta.env.VITE_FRIDAY_API_URL || "http://127.0.0.1:8000";
const API_URL = RAW_API_URL.trim().replace(/\/+$/, "");
const WS_URL = API_URL.replace(/^http/, "ws") + "/ws/presence";

const app = document.querySelector("#app");
app.innerHTML = `
  <main class="shell">
    <section class="hero">
      <article class="card hero-copy">
        <p class="eyebrow">ALTERNATE SURFACE</p>
        <h1>FRIDAY Antigravity</h1>
        <p>This optional interface exposes the same local AI core through a command-first control surface. It is intended for workflow-driven use when you want more textual steering without leaving the realtime runtime.</p>
        <div class="mode-badge" id="mode-badge">Mode · antigravity</div>
      </article>
      <aside class="card status" id="status-card">
        <div class="status-row"><span>Presence</span><strong id="presence-mode">idle</strong></div>
        <div class="status-row"><span>Headline</span><strong id="presence-headline">FRIDAY online</strong></div>
        <div class="status-row"><span>Objective</span><strong id="presence-objective">None</strong></div>
        <div class="status-row"><span>Active agents</span><strong id="presence-agents">None</strong></div>
      </aside>
    </section>
    <section class="grid">
      <article class="card composer">
        <h2>Command Surface</h2>
        <p>Submit high-level objectives into the local multi-agent runtime.</p>
        <form id="objective-form">
          <textarea id="objective-input" placeholder="Example: Search for local OCR libraries, compare them, then generate a summary and save findings to a file."></textarea>
          <button type="submit">Dispatch objective</button>
        </form>
        <pre id="output"></pre>
      </article>
      <article class="card feed">
        <h2>Live Activity</h2>
        <div class="feed-list" id="feed-list"></div>
      </article>
    </section>
  </main>
`;

const presenceMode = document.getElementById("presence-mode");
const presenceHeadline = document.getElementById("presence-headline");
const presenceObjective = document.getElementById("presence-objective");
const presenceAgents = document.getElementById("presence-agents");
const feedList = document.getElementById("feed-list");
const form = document.getElementById("objective-form");
const input = document.getElementById("objective-input");
const output = document.getElementById("output");

function pushEvent(title, body) {
  const node = document.createElement("article");
  node.className = "event";
  node.innerHTML = `<strong>${title}</strong><small>${body}</small>`;
  feedList.prepend(node);
  while (feedList.children.length > 24) {
    feedList.removeChild(feedList.lastChild);
  }
}

function applyPresence(presence) {
  presenceMode.textContent = presence.mode;
  presenceHeadline.textContent = presence.headline;
  presenceObjective.textContent = presence.current_objective || "None";
  presenceAgents.textContent = presence.active_agents?.join(", ") || "None";
}

async function submitObjective(event) {
  event.preventDefault();
  const objective = input.value.trim();
  if (!objective) {
    return;
  }
  output.textContent = "Dispatching objective...";
  try {
    const response = await fetch(`${API_URL}/api/objectives/submit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        objective,
        context: { source: "frontend-antigravity" },
        max_steps: 8,
        auto_retry: true,
        store_memory: true
      })
    });
    const payload = await response.json();
    output.textContent = JSON.stringify(payload.data, null, 2);
    input.value = "";
    pushEvent("Objective queued", objective);
  } catch (error) {
    output.textContent = error.message;
    pushEvent("Dispatch failed", error.message);
  }
}

form.addEventListener("submit", submitObjective);

function connect() {
  const socket = new WebSocket(WS_URL);
  socket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "bootstrap") {
      applyPresence(payload.presence);
      payload.events?.slice(-8).forEach((item) => pushEvent(`${item.source} · ${item.message_type}`, JSON.stringify(item.payload)));
      return;
    }
    if (payload.type === "presence") {
      applyPresence(payload.data);
      return;
    }
    if (payload.type === "event") {
      pushEvent(`${payload.data.source} · ${payload.data.message_type}`, JSON.stringify(payload.data.payload));
    }
  });
  socket.addEventListener("close", () => {
    pushEvent("Realtime link", "Connection lost. Retrying...");
    setTimeout(connect, 1200);
  });
}

connect();
