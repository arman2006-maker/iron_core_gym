const state = {
  role: "admin",
  overview: null,
  selectedMemberId: 5,
  selectedTable: "member",
  presets: [],
  rbac: null,
};

function currentHeaders() {
  return {
    "Content-Type": "application/json",
    "X-Role": state.role,
  };
}

async function api(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: { ...currentHeaders(), ...(options.headers || {}) },
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

function showToast(msg, isError = false) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.toggle("error", isError);
  el.classList.remove("hidden");
  clearTimeout(window.__toastTimer);
  window.__toastTimer = setTimeout(() => el.classList.add("hidden"), 4200);
}

function fmtINR(n) {
  return "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
}

function escapeHtml(val) {
  return String(val ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderTable(containerId, columns, rows, actionRenderer = null) {
  const el = document.getElementById(containerId);
  if (!rows || rows.length === 0) {
    el.innerHTML = `<div style="padding:14px;color:var(--muted);font-size:0.84rem;">No rows returned.</div>`;
    return;
  }
  const cols = columns && columns.length ? columns : Object.keys(rows[0]);
  let html = "<table><thead><tr>";
  for (const c of cols) html += `<th>${escapeHtml(c)}</th>`;
  if (actionRenderer) html += "<th>Action</th>";
  html += "</tr></thead><tbody>";
  for (const r of rows) {
    html += "<tr>";
    for (const c of cols) html += `<td>${escapeHtml(r[c])}</td>`;
    if (actionRenderer) html += `<td>${actionRenderer(r)}</td>`;
    html += "</tr>";
  }
  html += "</tbody></table>";
  el.innerHTML = html;
}

// =========================================================
// TAB 1: OVERVIEW
// =========================================================
async function loadOverview() {
  const data = await api("/api/overview");
  state.overview = data;

  const k = data.kpis;
  document.getElementById("kpiGrid").innerHTML = `
    <div class="kpi-card">
      <div class="kpi-label">Schema Footprint</div>
      <div class="kpi-val">${data.total_tables} Tables</div>
      <div class="kpi-sub">${data.total_rows} live records in <code>gym.db</code></div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Active Memberships</div>
      <div class="kpi-val">${k.active_members} / ${k.total_members}</div>
      <div class="kpi-sub">Auto-checked against ${data.reference_date}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Cumulative Revenue</div>
      <div class="kpi-val">${fmtINR(k.total_revenue)}</div>
      <div class="kpi-sub">Pending dues: ${fmtINR(k.pending_dues)}</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Class Occupancy</div>
      <div class="kpi-val">${k.occupancy_pct}%</div>
      <div class="kpi-sub">${k.maintenance_equipment} equipment under maintenance</div>
    </div>
  `;

  document.getElementById("totalRowBadge").textContent = `${data.total_tables} Tables • ${data.total_rows} Rows`;
  renderRevenueChart(data.monthly_revenue);

  // Class Load list
  const loadEl = document.getElementById("classLoadList");
  loadEl.innerHTML = data.views.v_class_load
    .map(
      (c) => `
      <div class="load-row">
        <div class="load-top">
          <span><strong>#${c.session_id} ${escapeHtml(c.class_name)}</strong> &bull; ${escapeHtml(c.trainer_name)} (${escapeHtml(c.room)})</span>
          <span>${c.seats_booked}/${c.capacity} (${c.load_pct}%)</span>
        </div>
        <div class="progress-track">
          <div class="progress-fill" style="width:${Math.min(100, c.load_pct)}%"></div>
        </div>
      </div>`
    )
    .join("");

  renderTable(
    "duesPendingTable",
    ["sub_id", "name", "plan_name", "dues_left"],
    data.views.v_dues_pending.slice(0, 8)
  );
  renderTable(
    "auditLogTable",
    ["log_id", "table_name", "action", "details"],
    data.audit_log.slice(0, 8)
  );

  renderTableChips();
}

function renderRevenueChart(monthly) {
  const box = document.getElementById("revenueChart");
  if (!monthly || !monthly.length) {
    box.innerHTML = "No payment data.";
    return;
  }
  const latest = monthly[monthly.length - 1];
  document.getElementById("revTotalBadge").textContent = `Running Total: ${fmtINR(latest.run_total)}`;

  const maxRev = Math.max(...monthly.map((m) => m.rev), 1);
  const w = 540;
  const h = 210;
  const padL = 44;
  const padB = 28;
  const plotW = w - padL - 20;
  const plotH = h - padB - 20;
  const barW = Math.floor(plotW / monthly.length) - 10;

  let bars = "";
  let linePts = [];
  const maxRun = Math.max(...monthly.map((m) => m.run_total), 1);

  monthly.forEach((m, idx) => {
    const x = padL + idx * (plotW / monthly.length) + 6;
    const bh = Math.round((m.rev / maxRev) * (plotH - 12));
    const y = 16 + (plotH - bh);
    bars += `<rect x="${x}" y="${y}" width="${barW}" height="${bh}" rx="5" fill="#ff6b2b" opacity="0.88">
      <title>${m.ym}: Monthly ${fmtINR(m.rev)} | Running ${fmtINR(m.run_total)}</title>
    </rect>`;
    bars += `<text x="${x + barW / 2}" y="${h - 8}" text-anchor="middle" fill="#8c9ab0" font-size="10">${m.ym.slice(2)}</text>`;

    const ly = 16 + (plotH - Math.round((m.run_total / maxRun) * (plotH - 12)));
    linePts.push(`${x + barW / 2},${ly}`);
  });

  box.innerHTML = `
    <svg viewBox="0 0 ${w} ${h}" style="width:100%;height:auto;">
      <line x1="${padL}" y1="${16 + plotH}" x2="${w - 10}" y2="${16 + plotH}" stroke="#263042" />
      ${bars}
      <polyline fill="none" stroke="#22c55e" stroke-width="2.5" points="${linePts.join(" ")}" />
      ${linePts
        .map((p) => {
          const [cx, cy] = p.split(",");
          return `<circle cx="${cx}" cy="${cy}" r="3.5" fill="#22c55e" />`;
        })
        .join("")}
      <text x="${padL}" y="12" fill="#8c9ab0" font-size="10">Orange Bars: Monthly Revenue | Green Line: Cumulative Running Total</text>
    </svg>
  `;
}

// =========================================================
// TAB 2: MEMBER & OPS APP
// =========================================================
async function loadMemberPortal() {
  const data = await api(`/api/member-portal?member_id=${state.selectedMemberId}`);
  const sel = document.getElementById("memberSelect");
  const attSel = document.getElementById("attMemberSelect");
  const nosqlSel = document.getElementById("nosqlMemberSelect");

  const optsHtml = data.members_list
    .map((m) => `<option value="${m.member_id}">#${m.member_id} ${escapeHtml(m.name)}</option>`)
    .join("");
  if (!sel.innerHTML) {
    sel.innerHTML = optsHtml;
    attSel.innerHTML = optsHtml;
    nosqlSel.innerHTML = optsHtml;
  }
  sel.value = String(state.selectedMemberId);

  const sub = data.subscription;
  const statusBadge =
    sub && sub.status === "ACTIVE"
      ? `<span class="badge badge-green">ACTIVE (${sub.days_left} days left)</span>`
      : `<span class="badge badge-red">${sub ? sub.status : "NO PLAN"}</span>`;

  document.getElementById("memberBanner").innerHTML = `
    <div class="stat-pill"><strong>${escapeHtml(data.member.name)}</strong> &bull; ${escapeHtml(data.member.branch_name)}</div>
    <div class="stat-pill">Plan: <strong>${sub ? escapeHtml(sub.plan_name) : "None"}</strong> ${statusBadge}</div>
    <div class="stat-pill">Dues Left: <strong>${fmtINR(data.dues_left)}</strong></div>
  `;

  if (data.dues_left > 0) {
    document.getElementById("payAmountInput").value = data.dues_left;
  }

  renderTable(
    "bookableSessionsTable",
    ["session_id", "class_name", "trainer_name", "session_start", "free_seats"],
    data.free_classes,
    (row) => {
      const label = row.free_seats > 0 ? "Book Seat" : "Full (Block/Waitlist)";
      const cls = row.free_seats > 0 ? "btn-primary" : "btn-outline";
      return `<button class="btn btn-sm ${cls}" onclick="bookSession(${row.session_id})">${label}</button>`;
    }
  );

  renderTable(
    "memberBookingsTable",
    ["booking_id", "session_id", "class_name", "session_start", "room"],
    data.upcoming_bookings,
    (row) => `<button class="btn btn-sm btn-outline" onclick="cancelBooking(${row.booking_id})">Cancel</button>`
  );

  renderTable(
    "memberWaitlistTable",
    ["wait_id", "session_id", "class_name", "session_start"],
    data.waitlist
  );

  await loadEquipment();
}

async function loadEquipment() {
  const eq = await api("/api/tables/equipment");
  renderTable(
    "equipmentTable",
    ["equip_id", "equip_name", "category", "status", "issued_to_member_id"],
    eq.rows,
    (row) => {
      if (row.status === "ISSUED") {
        return `<button class="btn btn-sm btn-outline" onclick="returnEquip(${row.equip_id})">Return</button>`;
      }
      return `<button class="btn btn-sm btn-primary" onclick="issueEquip(${row.equip_id})">Issue to #${state.selectedMemberId}</button>`;
    }
  );
}

window.bookSession = async function (sessionId) {
  const joinWl = document.getElementById("waitlistFallbackChk").checked;
  try {
    const res = await api("/api/bookings", {
      method: "POST",
      body: JSON.stringify({
        member_id: state.selectedMemberId,
        session_id: sessionId,
        join_waitlist_if_full: joinWl,
      }),
    });
    showToast(res.message);
    await Promise.all([loadMemberPortal(), loadOverview()]);
  } catch (err) {
    showToast(err.message, true);
  }
};

window.cancelBooking = async function (bookingId) {
  try {
    const res = await api(`/api/bookings/${bookingId}`, { method: "DELETE" });
    showToast(res.promoted ? `Booking cancelled. ${res.promoted}!` : "Booking cancelled.");
    await Promise.all([loadMemberPortal(), loadOverview()]);
  } catch (err) {
    showToast(err.message, true);
  }
};

window.issueEquip = async function (equipId) {
  try {
    const res = await api("/api/equipment/issue", {
      method: "POST",
      body: JSON.stringify({ equip_id: equipId, member_id: state.selectedMemberId }),
    });
    showToast(res.message);
    await loadEquipment();
  } catch (err) {
    showToast(err.message, true);
  }
};

window.returnEquip = async function (equipId) {
  try {
    await api("/api/equipment/return", {
      method: "POST",
      body: JSON.stringify({ equip_id: equipId }),
    });
    showToast(`Equipment #${equipId} returned to AVAILABLE.`);
    await loadEquipment();
  } catch (err) {
    showToast(err.message, true);
  }
};

// =========================================================
// TAB 3: ER DIAGRAM & TABLE INSPECTOR
// =========================================================
function renderErDiagram() {
  const nodes = [
    { id: "branch", x: 185, y: 16, w: 125, h: 64, pk: "branch_id", cols: ["branch_name", "city"] },
    { id: "gym_class", x: 640, y: 16, w: 130, h: 64, pk: "class_id", cols: ["class_name", "category"] },
    { id: "trainer", x: 805, y: 16, w: 135, h: 64, pk: "trainer_id", cols: ["name", "speciality"] },
    { id: "audit_log", x: 965, y: 16, w: 135, h: 64, pk: "log_id", cols: ["table_name", "action"] },

    { id: "equipment", x: 40, y: 140, w: 145, h: 80, pk: "equip_id", cols: ["equip_name", "status", "branch_id (FK)"] },
    { id: "membership_plan", x: 205, y: 140, w: 160, h: 80, pk: "plan_id", cols: ["plan_name", "duration", "fee"] },
    { id: "member", x: 395, y: 140, w: 150, h: 80, pk: "member_id", cols: ["name", "phone", "branch_id (FK)"] },
    { id: "class_session", x: 630, y: 140, w: 170, h: 86, pk: "session_id", cols: ["class_id (FK)", "trainer_id (FK)", "capacity / booked"], hot: true },

    { id: "maintenance", x: 30, y: 292, w: 150, h: 80, pk: "maint_id", cols: ["equip_id (FK)", "issue", "cost"] },
    { id: "subscription", x: 205, y: 292, w: 155, h: 84, pk: "sub_id", cols: ["member_id (FK)", "plan_id (FK)", "end_date / status"], hot: true },
    { id: "attendance", x: 375, y: 292, w: 140, h: 80, pk: "att_id", cols: ["member_id (FK)", "check_in", "check_out"] },
    { id: "booking", x: 530, y: 292, w: 145, h: 80, pk: "booking_id", cols: ["member_id (FK)", "session_id (FK)", "status"], hot: true },
    { id: "waitlist", x: 690, y: 292, w: 140, h: 80, pk: "wait_id", cols: ["member_id (FK)", "session_id (FK)", "requested_at"] },
    { id: "workout_plan", x: 845, y: 292, w: 155, h: 80, pk: "wp_id", cols: ["member_id (FK)", "trainer_id (FK)", "goal"] },

    { id: "payment", x: 205, y: 425, w: 155, h: 80, pk: "payment_id", cols: ["sub_id (FK)", "amount", "mode"] },
  ];

  const edges = [
    ["branch", "equipment", "1:N"],
    ["branch", "member", "1:N"],
    ["equipment", "maintenance", "1:N"],
    ["membership_plan", "subscription", "1:N"],
    ["member", "subscription", "1:N"],
    ["subscription", "payment", "1:N"],
    ["member", "attendance", "1:N"],
    ["member", "booking", "1:N"],
    ["member", "waitlist", "1:N"],
    ["member", "workout_plan", "1:N"],
    ["gym_class", "class_session", "1:N"],
    ["trainer", "class_session", "1:N"],
    ["trainer", "workout_plan", "1:N"],
    ["class_session", "booking", "1:N"],
    ["class_session", "waitlist", "1:N"],
  ];

  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  let svg = `<svg viewBox="0 0 1120 515" style="width:100%;min-width:840px;height:auto;">`;

  for (const [a, b, card] of edges) {
    const n1 = byId[a];
    const n2 = byId[b];
    const x1 = n1.x + n1.w / 2;
    const y1 = n1.y + n1.h;
    const x2 = n2.x + n2.w / 2;
    const y2 = n2.y;
    const mx = (x1 + x2) / 2;
    const my = (y1 + y2) / 2;
    svg += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#475569" stroke-width="1.6" />`;
    svg += `<text x="${mx + 4}" y="${my}" fill="#ff6b2b" font-size="11" font-weight="700">${card}</text>`;
  }

  for (const n of nodes) {
    const headerFill = n.hot ? "#ff6b2b" : "#0f172a";
    const strokeCol = state.selectedTable === n.id ? "#22c55e" : n.hot ? "#ff6b2b" : "#334155";
    svg += `
      <g class="er-entity" onclick="inspectTable('${n.id}')">
        <rect x="${n.x}" y="${n.y}" width="${n.w}" height="${n.h}" rx="6" fill="#1e293b" stroke="${strokeCol}" stroke-width="2" />
        <rect x="${n.x}" y="${n.y}" width="${n.w}" height="21" rx="5" fill="${headerFill}" />
        <text x="${n.x + 8}" y="${n.y + 14}" fill="#ffffff" font-size="11" font-weight="700">${n.id.toUpperCase()}</text>
        <text x="${n.x + 8}" y="${n.y + 34}" fill="#f8fafc" font-size="10.5" font-weight="700">PK ${n.pk}</text>
        ${n.cols
          .map(
            (c, i) =>
              `<text x="${n.x + 8}" y="${n.y + 47 + i * 12}" fill="#94a3b8" font-size="9.8">${c}</text>`
          )
          .join("")}
      </g>
    `;
  }
  svg += "</svg>";
  document.getElementById("erDiagramWrap").innerHTML = svg;
}

function renderTableChips() {
  if (!state.overview) return;
  const wrap = document.getElementById("tableCountChips");
  wrap.innerHTML = state.overview.table_counts
    .map(
      (t) =>
        `<span class="chip ${state.selectedTable === t.table ? "active" : ""}" onclick="inspectTable('${t.table}')">${t.table} (${t.rows})</span>`
    )
    .join("");
}

window.inspectTable = async function (tbl) {
  state.selectedTable = tbl;
  renderErDiagram();
  renderTableChips();
  document.getElementById("selectedTableTitle").innerHTML = `Table Inspector: <code>${tbl}</code>`;
  try {
    const res = await api(`/api/tables/${tbl}`);
    document.getElementById("selectedTableMeta").textContent = `Showing ${res.rows.length} rows (${res.columns.length} columns)`;
    renderTable("tableBrowserWrap", res.columns, res.rows);
  } catch (err) {
    document.getElementById("selectedTableMeta").textContent = err.message;
    document.getElementById("tableBrowserWrap").innerHTML = `<div style="padding:14px;color:var(--red);font-family:var(--font-mono);font-size:0.84rem;">${escapeHtml(err.message)}</div>`;
  }
};

// =========================================================
// TAB 4: SQL QUERY LAB & EXPLAIN
// =========================================================
async function loadSqlPresets() {
  const res = await api("/api/queries/presets");
  state.presets = res.presets;
  const grid = document.getElementById("presetButtons");
  grid.innerHTML = state.presets
    .map(
      (p, i) => `
      <button class="preset-btn ${i === 0 ? "active" : ""}" onclick="selectPreset(${i})">
        <strong>${escapeHtml(p.title)}</strong>
        <small>${escapeHtml(p.technique)} &bull; ${p.rows.length} rows</small>
      </button>`
    )
    .join("");
  if (state.presets.length) selectPreset(0);
}

window.selectPreset = function (idx) {
  const p = state.presets[idx];
  document.querySelectorAll(".preset-btn").forEach((b, i) => b.classList.toggle("active", i === idx));
  document.getElementById("sqlEditor").value = p.sql;
  document.getElementById("sqlStatusText").textContent = `${p.rows.length} rows returned (${p.technique})`;
  renderTable("sqlResultTable", p.columns, p.rows);
};

async function runCustomSql() {
  const sql = document.getElementById("sqlEditor").value.trim();
  try {
    const res = await api("/api/queries/run", {
      method: "POST",
      body: JSON.stringify({ sql }),
    });
    document.getElementById("sqlStatusText").textContent = `${res.rows.length} rows returned`;
    renderTable("sqlResultTable", res.columns, res.rows);
  } catch (err) {
    document.getElementById("sqlStatusText").textContent = err.message;
    showToast(err.message, true);
  }
}

async function runExplainLab() {
  const res = await api("/api/explain-demo");
  const beforeTxt = JSON.stringify(res.before, null, 2);
  const afterTxt = JSON.stringify(res.after, null, 2);
  document.getElementById("explainComparison").innerHTML = `
    <div>
      <h4 class="subhead">Before Index (Full Table Scan)</h4>
      <div class="terminal-mini" style="color:#fca5a5;">EXPLAIN QUERY PLAN SELECT * FROM attendance WHERE check_in='2026-11-19 17:00:00';\n\n${escapeHtml(beforeTxt)}</div>
    </div>
    <div>
      <h4 class="subhead">After <code>CREATE INDEX idx_att_in ON attendance(check_in)</code></h4>
      <div class="terminal-mini">EXPLAIN QUERY PLAN SELECT * FROM attendance WHERE check_in='2026-11-19 17:00:00';\n\n${escapeHtml(afterTxt)}</div>
    </div>
  `;
}

// =========================================================
// TAB 5: CONCURRENCY, SAVEPOINT, RBAC & SQLI
// =========================================================
async function runConcurrency() {
  const out = document.getElementById("concurrencyOutput");
  out.textContent = "Running two concurrent SQLite transactions on Zumba #99...";
  const res = await api("/api/labs/concurrency", { method: "POST", body: "{}" });
  const lines = res.timeline.map(
    (t) => `[${t.time}] Session ${t.session}> ${t.sql}\n    => ${t.output}`
  );
  lines.push(`\nFINAL SESSION #99: ${res.session_99.seats_booked}/${res.session_99.capacity} (${res.session_99.load_pct}% load)`);
  lines.push(`WAITLIST FOR #99: ${res.waitlist.map((w) => `#${w.member_id} ${w.name}`).join(", ")}`);
  out.textContent = lines.join("\n");
  loadOverview();
}

async function runSavepoint() {
  const res = await api("/api/labs/savepoint", { method: "POST", body: "{}" });
  const lines = res.steps.map((s) => `mysql> ${s.step}\n[${s.status}] ${s.detail}`);
  lines.push("\nLatest payments for sub_id=25:");
  res.payments_for_sub_25.forEach((p) => {
    lines.push(`  payment_id=${p.payment_id} | amount=${p.amount} | mode=${p.mode} | paid_on=${p.paid_on}`);
  });
  document.getElementById("savepointOutput").textContent = lines.join("\n");
  loadOverview();
}

async function refreshRbacState() {
  const res = await api("/api/rbac/status");
  state.rbac = res.roles;
  const granted = state.rbac.front_desk.permissions.insert_payment;
  const btn = document.getElementById("toggleFrontDeskPayBtn");
  btn.textContent = granted ? "GRANTED (Click to REVOKE)" : "REVOKED (Click to GRANT)";
  btn.className = `btn btn-sm ${granted ? "btn-primary" : "btn-outline"}`;
}

async function toggleFrontDeskPayment() {
  const currently = state.rbac?.front_desk?.permissions?.insert_payment ?? true;
  await api("/api/rbac/toggle", {
    method: "POST",
    body: JSON.stringify({ role: "front_desk", permission: "insert_payment", grant: !currently }),
  });
  await refreshRbacState();
  showToast(!currently ? "GRANT INSERT ON gym.payment TO role_front_desk" : "REVOKE INSERT ON gym.payment FROM role_front_desk");
}

async function runRbacTest() {
  const role = document.getElementById("rbacTestRole").value;
  const action = document.getElementById("rbacTestAction").value;
  const res = await api("/api/rbac/test", {
    method: "POST",
    body: JSON.stringify({ role, action }),
  });
  const el = document.getElementById("rbacOutput");
  el.style.color = res.allowed ? "#86efac" : "#fca5a5";
  el.textContent = `${role}> ${res.sql}\n${res.output}`;
}

async function runSqli() {
  const inp = document.getElementById("sqliInput").value;
  const res = await api("/api/labs/sqli", {
    method: "POST",
    body: JSON.stringify({ input: inp }),
  });
  document.getElementById("sqliOutput").textContent = [
    `$ python3 sqli_demo.py`,
    `User types in login box: ${res.input}`,
    ``,
    `[UNSAFE] string concatenation:`,
    `  ${res.unsafe.query}`,
    `  -> rows leaked: ${res.unsafe.rows_leaked}`,
    ``,
    `[SAFE] parameterized query:`,
    `  ${res.safe.query}`,
    `  -> rows returned: ${res.safe.rows_returned} (input treated as data)`,
  ].join("\n");
}

// =========================================================
// TAB 6: ETL & NOSQL
// =========================================================
async function loadEtl() {
  try {
    const res = await api("/api/etl/run", { method: "POST", body: "{}" });
    document.getElementById("etlSummary").innerHTML = `
      <div class="etl-box"><strong>${res.loaded.dim_member}</strong><span>dim_member</span></div>
      <div class="etl-box"><strong>${res.loaded.dim_plan}</strong><span>dim_plan</span></div>
      <div class="etl-box"><strong>${res.loaded.dim_date}</strong><span>dim_date</span></div>
      <div class="etl-box"><strong>${res.loaded.fact_attendance}</strong><span>fact_attendance</span></div>
    `;
    renderTable("etlReportTable", ["plan", "visits", "avg_min"], res.report);
    renderTable("etlFactsTable", ["fact_id", "name", "plan_name", "date_key", "day_name", "duration_min"], res.sample_facts);
  } catch (err) {
    showToast(err.message, true);
  }
}

async function loadNosql() {
  const res = await api("/api/nosql/logs");
  renderTable("nosqlAggTable", ["workout_type", "logs", "total_calories", "avg_rpe"], res.aggregation);
  document.getElementById("nosqlDocsList").innerHTML = res.documents
    .map((d) => `<div class="doc-item">${escapeHtml(JSON.stringify(d, null, 2))}</div>`)
    .join("");
}

// =========================================================
// EVENT WIRING
// =========================================================
document.querySelectorAll(".nav-tab").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll(".nav-tab").forEach((b) => b.classList.toggle("active", b === btn));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === `tab-${tab}`));

    if (tab === "overview") await loadOverview();
    if (tab === "operations") await loadMemberPortal();
    if (tab === "schema") {
      renderErDiagram();
      await inspectTable(state.selectedTable);
    }
    if (tab === "sql") {
      if (!state.presets.length) await loadSqlPresets();
      await runExplainLab();
    }
    if (tab === "labs") await refreshRbacState();
    if (tab === "etl") await Promise.all([loadEtl(), loadNosql()]);
  });
});

document.getElementById("roleSelect").addEventListener("change", (e) => {
  state.role = e.target.value;
  showToast(`Switched active RBAC role to ${state.role}`);
});

document.getElementById("memberSelect").addEventListener("change", async (e) => {
  state.selectedMemberId = Number(e.target.value);
  await loadMemberPortal();
});

document.getElementById("paymentForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const amount = Number(document.getElementById("payAmountInput").value);
  const mode = document.getElementById("payModeSelect").value;
  try {
    const portal = await api(`/api/member-portal?member_id=${state.selectedMemberId}`);
    if (!portal.subscription) throw new Error("No subscription found for member.");
    const res = await api("/api/payments", {
      method: "POST",
      body: JSON.stringify({ sub_id: portal.subscription.sub_id, amount, mode }),
    });
    showToast(res.message);
    await Promise.all([loadMemberPortal(), loadOverview()]);
  } catch (err) {
    showToast(err.message, true);
  }
});

document.getElementById("checkInBtn").addEventListener("click", async () => {
  const memberId = Number(document.getElementById("attMemberSelect").value);
  try {
    const res = await api("/api/attendance", {
      method: "POST",
      body: JSON.stringify({ member_id: memberId }),
    });
    const box = document.getElementById("opsFeedbackTerminal");
    box.classList.remove("hidden");
    box.textContent = `CHECKED_IN member #${memberId} at ${res.check_in}`;
    showToast(`Recorded check-in for member #${memberId}`);
    await loadOverview();
  } catch (err) {
    showToast(err.message, true);
  }
});

document.getElementById("renewPlanBtn").addEventListener("click", async () => {
  const planId = Number(document.getElementById("renewPlanSelect").value);
  try {
    const res = await api("/api/subscriptions/renew", {
      method: "POST",
      body: JSON.stringify({ member_id: state.selectedMemberId, plan_id: planId }),
    });
    showToast(`Renewed member #${state.selectedMemberId} on ${res.plan}`);
    await Promise.all([loadMemberPortal(), loadOverview()]);
  } catch (err) {
    showToast(err.message, true);
  }
});

document.getElementById("testAutoExpireBtn").addEventListener("click", async () => {
  const res = await api("/api/subscriptions/expire-test", {
    method: "POST",
    body: JSON.stringify({ sub_id: 21 }),
  });
  const box = document.getElementById("expireResultBox");
  box.classList.remove("hidden");
  box.textContent =
    `MariaDB [gym]> UPDATE subscription SET end_date=CURDATE()-INTERVAL 1 DAY WHERE sub_id=21;\n` +
    `=> sub_id=${res.subscription.sub_id}, end_date=${res.subscription.end_date}, status=${res.subscription.status}`;
  showToast("Trigger trg_auto_expire_subscription fired!");
  await loadOverview();
});

document.getElementById("runSqlBtn").addEventListener("click", runCustomSql);
document.getElementById("runExplainBtn").addEventListener("click", runExplainLab);
document.getElementById("runConcurrencyBtn").addEventListener("click", runConcurrency);
document.getElementById("runSavepointBtn").addEventListener("click", runSavepoint);
document.getElementById("toggleFrontDeskPayBtn").addEventListener("click", toggleFrontDeskPayment);
document.getElementById("runRbacTestBtn").addEventListener("click", runRbacTest);
document.getElementById("runSqliBtn").addEventListener("click", runSqli);
document.getElementById("runEtlBtn").addEventListener("click", loadEtl);

document.getElementById("nosqlForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  await api("/api/nosql/logs", {
    method: "POST",
    body: JSON.stringify({
      member_id: Number(document.getElementById("nosqlMemberSelect").value),
      workout_type: document.getElementById("nosqlType").value,
      exercise: document.getElementById("nosqlExercise").value,
      calories_burned: Number(document.getElementById("nosqlCals").value),
      rpe: Number(document.getElementById("nosqlRpe").value),
      trainer_note: document.getElementById("nosqlNote").value,
    }),
  });
  showToast("Inserted MongoDB-style workout log document.");
  await loadNosql();
});

document.getElementById("resetDbBtn").addEventListener("click", async () => {
  await api("/api/reset", { method: "POST", body: "{}" });
  showToast("Database reset to initial 15 tables / 375 rows!");
  await loadOverview();
  await loadMemberPortal();
});

// Boot
(async function init() {
  await loadOverview();
  await loadMemberPortal();
  renderErDiagram();
})();
