/*
 * МЕДЖЕК Сервис — frontend програм (нэг хуудастай вэб програм, SPA).
 *
 * Бүтэц:
 *   1. API клиент      — сервертэй JWT токеноор харилцах
 *   2. Төлөв (state)   — серверээс татсан өгөгдлийг санах ойд хадгалах
 *   3. Чиглүүлэгч      — URL-ийн # хэсгээр хуудас сонгох (#devices, #device/MJ-0001 …)
 *   4. Харагдац (view) — хуудас бүрийн HTML-ийг төлөвөөс үүсгэх
 *   5. Маягт (form)    — бүртгэх, засах цонхнууд
 *
 * Хэрэглэгчийн оруулсан бүх текстийг esc() функцээр дамжуулж HTML-д
 * оруулдаг тул XSS халдлагаас хамгаалагдсан.
 */
(function () {
  "use strict";

  /* ================================================================
   * 1. Туслах функцууд
   * ================================================================ */

  const $ = (s) => document.querySelector(s);
  const TOKEN_KEY = "medjack.token";
  const USER_KEY = "medjack.user";

  /** HTML-д аюултай тэмдэгтүүдийг орлуулж, текстийг аюулгүй болгоно. */
  const esc = (v) =>
    String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /** "2026-09-23" огноог "2026.09.23" хэлбэрээр харуулна. Хоосон бол зураас. */
  const fmt = (s) => (s ? String(s).slice(0, 10).replace(/-/g, ".") : "—");

  /** Өнөөдрийн огноог YYYY-MM-DD хэлбэрээр буцаана (цагийн бүсийг харгалзана). */
  function todayISO() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }

  /** Брэнд, загварыг нэгтгэж төхөөрөмжийн нэр болгоно (хоосон хэсгийг алгасна). */
  const devName = (d) => [d.brand, d.model].filter(Boolean).join(" ");

  /** Дэлгэцийн доод хэсэгт богино мэдэгдэл (toast) 2.2 секунд харуулна. */
  function toast(text) {
    const el = $("#toast");
    el.textContent = text;
    el.classList.add("on");
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => el.classList.remove("on"), 2200);
  }

  const STATUS_CLS = { "Ажиллаж байгаа": "p-ok", "Засварт": "p-warn", "Ашиглалтаас гарсан": "p-off" };
  const TSTATUS_CLS = { "Нээлттэй": "p-bad", "Хийгдэж байгаа": "p-warn", "Хаагдсан": "p-ok" };
  const WSTATE_CLS = { "Хүчинтэй": "p-ok", "30 хоногт дуусна": "p-warn", "7 хоногт дуусна": "p-bad", "Дууссан": "p-off", "Тодорхойгүй": "p-off" };
  const MONTHS = ["1-р сар", "2-р сар", "3-р сар", "4-р сар", "5-р сар", "6-р сар", "7-р сар", "8-р сар", "9-р сар", "10-р сар", "11-р сар", "12-р сар"];

  /* ================================================================
   * 2. API клиент
   * ================================================================ */

  /**
   * Сервер рүү хүсэлт илгээж, JSON хариуг буцаана.
   *
   * Хадгалсан JWT токеныг `Authorization` толгойд автоматаар нэмнэ.
   * 401 хариу ирвэл токены хугацаа дууссан гэж үзэж нэвтрэх дэлгэц рүү
   * буцаана. Бусад алдааны үед серверийн мессежийг ойлгомжтой болгож
   * Error объект болгон шиднэ.
   */
  async function api(path, { method = "GET", body, raw = false } = {}) {
    const headers = {};
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) headers.Authorization = `Bearer ${token}`;
    if (body !== undefined) headers["Content-Type"] = "application/json";

    let res;
    try {
      res = await fetch(path, { method, headers, body: body !== undefined ? JSON.stringify(body) : undefined });
    } catch (e) {
      throw new Error("Сервертэй холбогдож чадсангүй. Интернэт холболтоо шалгана уу.");
    }
    if (res.status === 401 && !path.endsWith("/login")) {
      logout("Нэвтрэлтийн хугацаа дууссан. Дахин нэвтэрнэ үү.");
      throw new Error("unauthorized");
    }
    if (!res.ok) throw new Error(await errorText(res));
    if (raw) return res;
    return res.status === 204 ? null : res.json();
  }

  /**
   * Серверийн алдааны хариуг хэрэглэгчид ойлгомжтой нэг мөр болгоно.
   *
   * FastAPI-ийн баталгаажуулалтын (422) алдаа нь жагсаалт хэлбэртэй ирдэг
   * тул эхний алдааны мессежийг авч, техникийн угтварыг арилгана.
   */
  async function errorText(res) {
    try {
      const data = await res.json();
      if (typeof data.detail === "string") return data.detail;
      if (Array.isArray(data.detail) && data.detail.length) {
        const first = data.detail[0];
        const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : "";
        const msg = VALIDATION_MN[first.type]
          ? VALIDATION_MN[first.type](first.ctx || {})
          : String(first.msg || "").replace(/^Value error,\s*/, "");
        return field && field !== "body" ? `${FIELD_NAMES[field] || field}: ${msg}` : msg;
      }
    } catch (e) { /* JSON биш хариу */ }
    return `Алдаа гарлаа (${res.status}).`;
  }

  /** Pydantic-ийн англи хэл дээрх түгээмэл алдааг монгол болгох толь. */
  const VALIDATION_MN = {
    missing: () => "заавал бөглөнө үү.",
    string_too_short: (c) => `дор хаяж ${c.min_length} тэмдэгт байх ёстой.`,
    string_too_long: (c) => `${c.max_length} тэмдэгтээс хэтрэхгүй байх ёстой.`,
    date_from_datetime_parsing: () => "огноог зөв оруулна уу.",
    date_parsing: () => "огноог зөв оруулна уу.",
    int_parsing: () => "сонголтоо хийнэ үү.",
    literal_error: () => "зөвшөөрөгдөөгүй утга байна.",
  };

  const FIELD_NAMES = {
    organization_name: "Байгууллагын нэр", serial_number: "Серийн дугаар", model: "Загвар",
    category: "Ангилал", install_date: "Суурилуулсан огноо", problem_description: "Гэмтлийн тайлбар",
    reported_date: "Дуудлага ирсэн огноо", manual_url: "Гарын авлагын холбоос",
  };

  /* ================================================================
   * 3. Төлөв ба өгөгдөл ачаалах
   * ================================================================ */

  const S = {
    user: null,
    config: {},
    dash: null,
    customers: [],
    devices: [],
    tickets: [],
    detail: {},      // паспортын дэлгэрэнгүй: { "MJ-0001": {...} }
    loaded: false,
  };
  const F = { q: "", w: "all", ts: "open" }; // жагсаалтын шүүлтүүд

  /**
   * Самбар, харилцагч, төхөөрөмж, дуудлагын өгөгдлийг зэрэг (параллель) татна.
   *
   * Бүртгэл өөрчлөгдөх бүрт дуудагддаг тул бүх дэлгэц үргэлж серверийн
   * хамгийн сүүлийн өгөгдлийг харуулна. Паспортын кэшийг цэвэрлэж,
   * дараа нь нээхэд дахин татагдах нөхцөлийг бүрдүүлнэ.
   */
  async function loadAll() {
    const [dash, customers, devices, tickets] = await Promise.all([
      api("/api/dashboard"),
      api("/api/customers"),
      api("/api/devices"),
      api("/api/tickets?status=all"),
    ]);
    Object.assign(S, { dash, customers, devices, tickets, detail: {}, loaded: true });
    render();
  }

  /** Паспортын дэлгэрэнгүйг (засварын түүхтэй) серверээс татаж кэшлэнэ. */
  async function loadDetail(code) {
    try {
      S.detail[code] = await api(`/api/devices/${encodeURIComponent(code)}`);
    } catch (e) {
      S.detail[code] = { error: e.message };
    }
    render();
  }

  const custById = (id) => S.customers.find((c) => c.customer_id === id);

  /* ================================================================
   * 4. Нэвтрэлт
   * ================================================================ */

  /**
   * Нэвтрэх маягтын утгыг сервер рүү илгээж, амжилттай бол токеныг
   * хадгалаад үндсэн програмыг нээнэ.
   */
  async function login() {
    const username = $("#lu").value.trim();
    const password = $("#lp").value;
    $("#lerr").textContent = "";
    if (!username || !password) { $("#lerr").textContent = "Нэр, нууц үгээ оруулна уу."; return; }
    $("#lbtn").disabled = true;
    try {
      const res = await api("/api/auth/login", { method: "POST", body: { username, password } });
      localStorage.setItem(TOKEN_KEY, res.access_token);
      localStorage.setItem(USER_KEY, JSON.stringify({ username: res.username, full_name: res.full_name, role: res.role }));
      $("#lp").value = "";
      await start();
    } catch (e) {
      $("#lerr").textContent = e.message;
    } finally {
      $("#lbtn").disabled = false;
    }
  }

  /** Токеныг устгаж нэвтрэх дэлгэц рүү буцна. Шалтгааныг сонголтоор харуулна. */
  function logout(reason) {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    S.loaded = false;
    $("#app").hidden = true;
    $("#login").hidden = false;
    $("#lerr").textContent = reason || "";
    $("#lu").focus();
  }

  /**
   * Програмыг эхлүүлнэ: токен байвал өгөгдөл татаж үндсэн дэлгэцийг,
   * байхгүй бол нэвтрэх дэлгэцийг харуулна.
   */
  async function start() {
    S.config = await fetch("/api/public/config").then((r) => r.json()).catch(() => ({}));
    if (!localStorage.getItem(TOKEN_KEY)) return logout();
    S.user = JSON.parse(localStorage.getItem(USER_KEY) || "{}");
    $("#login").hidden = true;
    $("#app").hidden = false;
    $("#who").textContent = `${S.user.full_name || S.user.username} · ${S.user.role === "admin" ? "Админ" : "Инженер"}`;
    render();
    try { await loadAll(); } catch (e) { if (e.message !== "unauthorized") toast(e.message); }
  }

  const isAdmin = () => S.user && S.user.role === "admin";

  /* ================================================================
   * 5. Чиглүүлэгч (router)
   * ================================================================ */

  /** URL-ийн # хэсгийг задлан аль хуудсыг харуулахыг тодорхойлно. */
  function route() {
    const h = decodeURIComponent(location.hash.replace(/^#/, ""));
    if (h.startsWith("device/")) return { name: "device", code: h.slice(7) };
    return { name: ["dash", "devices", "tickets", "customers", "labels"].includes(h) ? h : "dash" };
  }
  const go = (name) => { location.hash = name; };

  /* ================================================================
   * 6. Харагдац (view) — хуудас бүрийн HTML
   * ================================================================ */

  /** Хуудасны гарчиг, тайлбар, баруун талын товчнуудыг үүсгэнэ. */
  function header(title, sub, actions) {
    return `<div class="head"><div><h1>${title}</h1>${sub ? `<p>${sub}</p>` : ""}</div>${actions ? `<div class="actions">${actions}</div>` : ""}</div>`;
  }
  const tier = (n) => (n <= 7 ? "d-7" : n <= 14 ? "d-14" : "d-30");

  /**
   * Хяналтын самбар: үндсэн үзүүлэлт, сануулга, 6 сарын график,
   * нээлттэй дуудлагууд.
   */
  function vDash() {
    const d = S.dash;
    if (!d) return `<div class="empty">Ачаалж байна…</div>`;
    const max = Math.max(1, ...d.months.map((m) => m.installs + m.tickets));
    const open = S.tickets.filter((t) => t.status !== "Хаагдсан");
    return header("Хяналтын самбар",
      `Өнөөдөр ${fmt(d.today)}. Баталгаа болон төлөвлөгөөт үйлчилгээний сануулгыг 30, 14, 7 хоногийн өмнө автоматаар гаргана.`,
      `<button class="btn" data-act="newTicket">Засвар бүртгэх</button><button class="btn primary" data-act="newDevice">Төхөөрөмж нэмэх</button>`)
      + `<div class="stats">
        <div class="stat"><div class="n">${d.active_devices}</div><div class="l">Ашиглалтад байгаа төхөөрөмж</div></div>
        <div class="stat"><div class="n">${d.under_warranty}</div><div class="l">Баталгаат хугацаатай</div></div>
        <div class="stat ${d.reminders.length ? "warn" : ""}"><div class="n">${d.reminders.length}</div><div class="l">Идэвхтэй сануулга</div></div>
        <div class="stat ${d.stale_tickets ? "bad" : ""}"><div class="n">${d.open_tickets}</div><div class="l">Нээлттэй дуудлага${d.stale_tickets ? `, ${d.stale_tickets} нь 3+ хоног хүлээгдсэн` : ""}</div></div>
      </div>
      <div class="cols">
        <section><h2>Сануулга</h2><div class="panel">
          ${d.reminders.length ? d.reminders.map((r, i) => `<div class="rem">
            <div class="days ${tier(r.days_left)}">${Math.abs(r.days_left)}<small>${r.days_left < 0 ? "хоног хэтэрсэн" : "хоног"}</small></div>
            <div><div class="t">${esc(r.title)}</div><div class="s">${esc(r.device_model)} · <span class="mono">${esc(r.serial_number)}</span> · ${esc(r.customer_name)}</div></div>
            <button class="btn sm" data-act="notify" data-i="${i}">Мэдэгдэл</button></div>`).join("")
          : `<div class="empty">Ойрын 30 хоногт анхаарах зүйл алга.</div>`}
        </div></section>
        <section><h2>Сүүлийн 6 сар</h2><div class="panel">
          <div class="bars">${d.months.map((m) => `<div class="bar" title="Суурилуулалт ${m.installs}, засвар ${m.tickets}">
            <i class="b" style="height:${(m.tickets / max) * 100}%"></i><i class="a" style="height:${(m.installs / max) * 100}%"></i>
            <span>${MONTHS[Number(m.month.slice(5)) - 1]}</span></div>`).join("")}</div>
          <div class="legend"><span><i style="background:var(--teal)"></i>Суурилуулалт</span><span><i style="background:var(--signal)"></i>Засварын дуудлага</span></div>
          ${d.avg_close_days !== null ? `<p class="muted" style="margin:10px 0 0;font-size:13px">Дуудлагыг шийдвэрлэсэн дундаж хугацаа: ${d.avg_close_days} хоног</p>` : ""}
        </div>
        <h2 style="margin-top:22px">Нээлттэй дуудлага</h2>
        <div class="panel">${open.length ? open.slice(0, 5).map((t) => `<div class="rem" style="grid-template-columns:1fr auto">
          <div><div class="t">${esc(t.problem_description)}</div><div class="s">${esc(t.device_model)} · ${esc(t.customer_name)} · ${fmt(t.reported_date)}</div></div>
          <button class="btn sm" data-act="editTicket" data-id="${t.ticket_id}">Нээх</button></div>`).join("")
          : `<div class="empty">Нээлттэй дуудлага алга.</div>`}</div>
        </section>
      </div>`;
  }

  /**
   * Төхөөрөмжийн жагсаалт: код, серийн дугаар, загвар, харилцагчаар
   * шууд хайх ба баталгааны төлөвөөр шүүх.
   */
  function vDevices() {
    const q = F.q.toLowerCase();
    const list = S.devices.filter((d) => {
      const hay = [d.device_code, d.serial_number, d.brand, d.model, d.category, d.location, d.customer_name].join(" ").toLowerCase();
      if (q && !hay.includes(q)) return false;
      const w = d.warranty_days_left;
      if (F.w === "soon") return w !== null && w >= 0 && w <= 30;
      if (F.w === "valid") return w !== null && w >= 0;
      if (F.w === "expired") return w !== null && w < 0;
      return true;
    });
    return header("Төхөөрөмжийн паспорт", "Серийн дугаар, загвар, харилцагчаар хайна. Мөр дээр дарж паспорт, QR код, засварын түүхийг харна.",
      `<button class="btn" data-act="csv" data-kind="devices">CSV татах</button><button class="btn primary" data-act="newDevice">Төхөөрөмж нэмэх</button>`)
      + `<div class="toolbar"><input id="q" type="search" placeholder="Серийн дугаар, загвар, эмнэлэг…" value="${esc(F.q)}" aria-label="Хайх">
        <select id="wf" aria-label="Баталгаагаар шүүх"><option value="all">Бүх баталгаа</option><option value="valid">Хүчинтэй</option><option value="soon">30 хоногт дуусах</option><option value="expired">Дууссан</option></select></div>`
      + (list.length ? `<div class="tablewrap"><table><thead><tr><th>Код</th><th>Төхөөрөмж</th><th>Серийн дугаар</th><th>Харилцагч</th><th>Суурилуулсан</th><th>Баталгаа</th><th>Төлөв</th></tr></thead><tbody>
        ${list.map((d) => `<tr class="click" data-open="${esc(d.device_code)}" tabindex="0">
          <td class="mono">${esc(d.device_code)}</td>
          <td><b>${esc(devName(d))}</b><div class="muted" style="font-size:12.5px">${esc(d.category)}</div></td>
          <td class="mono">${esc(d.serial_number)}</td>
          <td>${esc(d.customer_name || "—")}</td>
          <td>${fmt(d.install_date)}</td>
          <td><span class="pill ${WSTATE_CLS[d.warranty_state] || "p-off"}">${esc(d.warranty_state)}</span><div class="muted" style="font-size:12.5px">${fmt(d.warranty_end_date)} хүртэл</div></td>
          <td><span class="pill ${STATUS_CLS[d.status] || "p-off"}">${esc(d.status)}</span></td></tr>`).join("")}
        </tbody></table></div>`
        : `<div class="tablewrap"><div class="empty">${S.devices.length ? "Хайлтад тохирох төхөөрөмж олдсонгүй." : "Төхөөрөмж бүртгэгдээгүй байна. «Төхөөрөмж нэмэх» товчоор эхлүүлнэ үү."}</div></div>`);
  }

  /**
   * Төхөөрөмжийн паспорт: QR код, үндсэн мэдээлэл, баталгааны хугацааны
   * шугам, засварын бүрэн түүх. Өгөгдлийг анх нээхэд серверээс татна.
   */
  function vDevice(code) {
    const d = S.detail[code];
    if (!d) { loadDetail(code); return `<div class="empty">Ачаалж байна…</div>`; }
    if (d.error) return header("Төхөөрөмж олдсонгүй", esc(d.error), `<button class="btn" data-go2="devices">Жагсаалт руу</button>`);
    const start = new Date(d.install_date), end = d.warranty_end_date ? new Date(d.warranty_end_date) : null;
    const pct = end && end > start ? Math.max(0, Math.min(100, ((Date.now() - start) / (end - start)) * 100)) : 0;
    const warn = d.warranty_days_left !== null && d.warranty_days_left >= 0 && d.warranty_days_left <= 30;
    return header(`<span class="muted" style="font-weight:500;font-size:15px"><a href="#devices">Төхөөрөмж</a> / ${esc(d.device_code)}</span>`, "",
      `<button class="btn" data-act="print">Хэвлэх</button><button class="btn" data-act="editDevice" data-code="${esc(d.device_code)}">Засах</button><button class="btn primary" data-act="newTicket" data-id="${d.device_id}">Засвар бүртгэх</button>`)
      + `<article class="tag">
        <div class="qr"><div class="qrbox"><img src="/api/public/qr/${encodeURIComponent(d.device_code)}.svg" width="168" height="168" alt="${esc(d.device_code)} QR код"></div><div class="code">${esc(d.device_code)}</div></div>
        <div class="body">
          <div class="cat">${esc(d.category)}</div>
          <h1>${esc(devName(d))}</h1>
          <div class="sn">SN ${esc(d.serial_number)}</div>
          <dl class="facts">
            <div><dt>Харилцагч</dt><dd>${esc(d.customer_name)}</dd></div>
            <div><dt>Байршил</dt><dd>${esc(d.location || "—")}</dd></div>
            <div><dt>Холбоо барих</dt><dd>${esc(d.customer_contact || "—")}${d.customer_phone ? ` · ${esc(d.customer_phone)}` : ""}</dd></div>
            <div><dt>Төлөв</dt><dd><span class="pill ${STATUS_CLS[d.status] || "p-off"}">${esc(d.status)}</span></dd></div>
            <div><dt>Дараагийн үйлчилгээ</dt><dd>${fmt(d.next_service_date)}</dd></div>
            <div><dt>Гарын авлага</dt><dd>${d.manual_url ? `<a href="${esc(d.manual_url)}" target="_blank" rel="noopener">PDF нээх</a>` : "—"}</dd></div>
          </dl>
          <div class="wbar"><div class="track"><div class="fill" style="width:${pct}%;${warn ? "background:var(--amber)" : ""}"></div></div>
            <div class="meta"><span>Суурилуулсан ${fmt(d.install_date)}</span><span>Баталгаа ${fmt(d.warranty_end_date)} · <span class="pill ${WSTATE_CLS[d.warranty_state] || "p-off"}">${esc(d.warranty_state)}</span></span></div></div>
        </div>
      </article>
      <section class="timeline"><h2>Засвар үйлчилгээний түүх (${d.tickets.length})</h2>
        ${d.tickets.length ? d.tickets.map((t) => `<div class="ev"><div class="when">${fmt(t.reported_date)}<br><span class="pill ${TSTATUS_CLS[t.status] || "p-off"}">${esc(t.status)}</span></div>
          <div><div class="what">${esc(t.problem_description)}</div>
          <dl>${t.diagnosis ? `<dt>Онош</dt><dd>${esc(t.diagnosis)}</dd>` : ""}${t.action_taken ? `<dt>Хийсэн ажил</dt><dd>${esc(t.action_taken)}</dd>` : ""}${t.parts_used ? `<dt>Сольсон сэлбэг</dt><dd>${esc(t.parts_used)}</dd>` : ""}<dt>Инженер</dt><dd>${esc(t.technician || "—")}</dd>${t.closed_date ? `<dt>Хаасан</dt><dd>${fmt(t.closed_date)}</dd>` : ""}</dl>
          <button class="btn sm noprint" style="margin-top:8px" data-act="editTicket" data-id="${t.ticket_id}">Засах</button></div></div>`).join("")
          : `<div class="empty" style="text-align:left;padding:14px 0">Энэ төхөөрөмж дээр засварын дуудлага бүртгэгдээгүй.</div>`}
      </section>`;
  }

  /** Засварын дуудлагын жагсаалт: нээлттэй, хаагдсан, бүгдээр шүүнэ. */
  function vTickets() {
    const list = S.tickets.filter((t) => (F.ts === "all" ? true : F.ts === "open" ? t.status !== "Хаагдсан" : t.status === "Хаагдсан"));
    return header("Засвар үйлчилгээ", "Дуудлага бүр төхөөрөмжийн паспорттой холбогдож, онош, хийсэн ажил, сольсон сэлбэг хадгалагдана.",
      `<button class="btn" data-act="csv" data-kind="tickets">CSV татах</button><button class="btn primary" data-act="newTicket">Засвар бүртгэх</button>`)
      + `<div class="toolbar"><select id="tsf" aria-label="Төлөвөөр шүүх"><option value="open">Нээлттэй</option><option value="closed">Хаагдсан</option><option value="all">Бүгд</option></select></div>`
      + (list.length ? `<div class="tablewrap"><table><thead><tr><th>№</th><th>Ирсэн</th><th>Төхөөрөмж</th><th>Гэмтэл</th><th>Инженер</th><th>Төлөв</th></tr></thead><tbody>
        ${list.map((t) => `<tr class="click" data-ticket="${t.ticket_id}" tabindex="0">
          <td class="mono">${t.ticket_id}</td><td>${fmt(t.reported_date)}</td>
          <td><b>${esc(t.device_model)}</b><div class="muted" style="font-size:12.5px">${esc(t.device_code)} · ${esc(t.customer_name)}</div></td>
          <td>${esc(t.problem_description)}</td><td>${esc(t.technician || "—")}</td>
          <td><span class="pill ${TSTATUS_CLS[t.status] || "p-off"}">${esc(t.status)}</span></td></tr>`).join("")}
        </tbody></table></div>`
        : `<div class="tablewrap"><div class="empty">Энэ төлөвтэй дуудлага алга.</div></div>`);
  }

  /** Харилцагч байгууллагын жагсаалт ба тус бүрийн төхөөрөмжийн тоо. */
  function vCustomers() {
    return header("Харилцагч байгууллага", "Эмнэлэг, лабораторийн мэдээлэл ба тэдэнд суурилуулсан төхөөрөмжийн тоо.",
      `<button class="btn" data-act="csv" data-kind="customers">CSV татах</button><button class="btn primary" data-act="newCustomer">Харилцагч нэмэх</button>`)
      + (S.customers.length ? `<div class="tablewrap"><table><thead><tr><th>№</th><th>Байгууллага</th><th>Хаяг</th><th>Холбоо барих</th><th>Утас</th><th>Төхөөрөмж</th></tr></thead><tbody>
        ${S.customers.map((c) => `<tr class="click" data-cust="${c.customer_id}" tabindex="0"><td class="mono">${c.customer_id}</td><td><b>${esc(c.organization_name)}</b></td><td>${esc(c.address || "—")}</td><td>${esc(c.contact_person || "—")}</td><td>${esc(c.phone || "—")}</td><td>${c.device_count}</td></tr>`).join("")}
        </tbody></table></div>`
        : `<div class="tablewrap"><div class="empty">Харилцагч бүртгэгдээгүй байна.</div></div>`);
  }

  /** Хэвлэх QR шошгоны хуудас: ашиглалтад байгаа төхөөрөмж бүрт нэг шошго. */
  function vLabels() {
    const list = S.devices.filter((d) => d.status !== "Ашиглалтаас гарсан");
    return header("QR шошго", "Шошгыг наалттай цаасан дээр хэвлэж төхөөрөмжид наана. Утсаар уншуулахад төхөөрөмжийн паспорт нээгдэнэ.",
      `<button class="btn primary" data-act="print">Хэвлэх</button>`)
      + (list.length ? `<div class="labels">${list.map((d) => `<div class="label">
          <div class="qrbox"><img src="/api/public/qr/${encodeURIComponent(d.device_code)}.svg" width="86" height="86" alt="QR"></div>
          <div><b>${esc(devName(d))}</b><span class="mono">${esc(d.device_code)} · SN ${esc(d.serial_number)}</span>
          <small>Баталгаа: ${fmt(d.warranty_end_date)} хүртэл<br>${esc(S.config.company_name || "")} сервис: ${esc(S.config.service_phone || "—")}</small></div></div>`).join("")}</div>`
        : `<div class="tablewrap"><div class="empty">Шошго хэвлэх төхөөрөмж алга.</div></div>`);
  }

  /**
   * Одоогийн URL-д тохирох хуудсыг зурж, цэсний идэвхтэй төлөв болон
   * сануулгын тоог шинэчилнэ. Хайлтын талбарт бичиж байх үед курсорын
   * байрлалыг хадгална.
   */
  function render() {
    if ($("#app").hidden) return;
    const r = route();
    const navName = r.name === "device" ? "devices" : r.name;
    document.querySelectorAll(".nav").forEach((b) => b.toggleAttribute("aria-current", b.dataset.go === navName));
    if (S.dash) {
      const rc = S.dash.reminders.length, oc = S.dash.open_tickets;
      $("#remCount").hidden = !rc; $("#remCount").textContent = rc;
      $("#openCount").hidden = !oc; $("#openCount").textContent = oc;
    }
    const focused = document.activeElement && document.activeElement.id === "q";
    const caret = focused ? document.activeElement.selectionStart : null;

    let html;
    if (!S.loaded) html = `<div class="empty">Өгөгдөл ачаалж байна…</div>`;
    else if (r.name === "device") html = vDevice(r.code);
    else html = { devices: vDevices, tickets: vTickets, customers: vCustomers, labels: vLabels, dash: vDash }[r.name]();
    $("#view").innerHTML = html;

    if ($("#wf")) $("#wf").value = F.w;
    if ($("#tsf")) $("#tsf").value = F.ts;
    if (focused && $("#q")) { $("#q").focus(); try { $("#q").setSelectionRange(caret, caret); } catch (e) { /* */ } }
  }

  /* ================================================================
   * 7. Маягтууд (dialog)
   * ================================================================ */

  const dlg = $("#dlg");

  /**
   * Бүртгэх, засах цонхыг нээнэ.
   *
   * `onSave` нь маягтын утгуудыг хүлээн авч Promise буцаана. Сервер алдаа
   * буцаавал цонх хаагдахгүй, алдааны мессеж маягтын доор харагдана.
   * `onDelete` өгөгдсөн ба хэрэглэгч админ бол «Устгах» товч нэмэгдэнэ.
   */
  function openDlg(title, fieldsHtml, onSave, onDelete) {
    $("#dlgBody").innerHTML = `<h2>${title}</h2><div class="grid2">${fieldsHtml}</div><div class="err" id="ferr" role="alert"></div>
      <div class="row">${onDelete && isAdmin() ? `<button class="btn danger" id="fdel" style="margin-right:auto">Устгах</button>` : ""}
      <button class="btn" id="fcancel">Болих</button><button class="btn primary" id="fsave">Хадгалах</button></div>`;
    dlg.showModal();
    $("#fcancel").onclick = () => dlg.close();
    $("#fsave").onclick = async () => {
      const values = {};
      $("#dlgBody").querySelectorAll("[name]").forEach((i) => { values[i.name] = i.value.trim(); });
      $("#fsave").disabled = true;
      try { await onSave(values); dlg.close(); await loadAll(); }
      catch (e) { if (e.message !== "unauthorized") $("#ferr").textContent = e.message; }
      finally { $("#fsave").disabled = false; }
    };
    if ($("#fdel")) $("#fdel").onclick = async () => {
      if (!confirm("Энэ бичлэгийг устгах уу? Энэ үйлдлийг буцаах боломжгүй.")) return;
      try { await onDelete(); dlg.close(); await loadAll(); }
      catch (e) { $("#ferr").textContent = e.message; }
    };
  }

  const inp = (name, label, val, type = "text", cls = "") =>
    `<label class="f ${cls}">${label}<input name="${name}" type="${type}" value="${esc(val ?? "")}"></label>`;
  const sel = (name, label, val, opts, cls = "") =>
    `<label class="f ${cls}">${label}<select name="${name}">${opts.map((o) => { const [v, l] = Array.isArray(o) ? o : [o, o]; return `<option value="${esc(v)}" ${String(v) === String(val) ? "selected" : ""}>${esc(l)}</option>`; }).join("")}</select></label>`;
  const area = (name, label, val) => `<label class="f full">${label}<textarea name="${name}">${esc(val ?? "")}</textarea></label>`;

  /** Харилцагч бүртгэх, засах маягт. */
  function customerForm(c) {
    const isNew = !c;
    c = c || {};
    openDlg(isNew ? "Шинэ харилцагч" : "Харилцагч засах",
      inp("organization_name", "Байгууллагын нэр", c.organization_name, "text", "full")
      + inp("address", "Хаяг", c.address, "text", "full")
      + inp("contact_person", "Холбоо барих хүн", c.contact_person)
      + inp("phone", "Утас", c.phone, "tel"),
      async (v) => {
        await api(isNew ? "/api/customers" : `/api/customers/${c.customer_id}`, { method: isNew ? "POST" : "PUT", body: v });
        toast("Харилцагч хадгалагдлаа");
      },
      isNew ? null : async () => { await api(`/api/customers/${c.customer_id}`, { method: "DELETE" }); toast("Устгагдлаа"); });
  }

  /**
   * Төхөөрөмж бүртгэх, засах маягт.
   * Шинэ төхөөрөмж хадгалагдмагц түүний паспорт руу шууд шилжинэ.
   */
  function deviceForm(d) {
    if (!S.customers.length) { toast("Эхлээд харилцагч бүртгэнэ үү"); go("customers"); return; }
    const isNew = !d;
    d = d || { install_date: todayISO(), status: "Ажиллаж байгаа" };
    const cats = ["ЭКГ аппарат", "Биохимийн анализатор", "Хяналтын монитор", "Инкубатор", "Биологийн аюулгүйн шүүгээ", "Автоклав", "Бусад"];
    openDlg(isNew ? "Шинэ төхөөрөмж" : `Төхөөрөмж засах · ${esc(d.device_code)}`,
      sel("customer_id", "Харилцагч", d.customer_id, S.customers.map((c) => [c.customer_id, c.organization_name]), "full")
      + sel("category", "Ангилал", d.category, cats)
      + inp("brand", "Брэнд", d.brand)
      + inp("model", "Загвар", d.model)
      + inp("serial_number", "Серийн дугаар", d.serial_number)
      + inp("install_date", "Суурилуулсан огноо", d.install_date, "date")
      + inp("warranty_end_date", "Баталгаа дуусах огноо", d.warranty_end_date, "date")
      + inp("next_service_date", "Дараагийн төлөвлөгөөт үйлчилгээ", d.next_service_date, "date")
      + sel("status", "Төлөв", d.status, ["Ажиллаж байгаа", "Засварт", "Ашиглалтаас гарсан"])
      + inp("location", "Байршил (тасаг, өрөө)", d.location, "text", "full")
      + inp("manual_url", "Гарын авлагын PDF холбоос", d.manual_url, "url", "full"),
      async (v) => {
        v.customer_id = Number(v.customer_id);
        const saved = await api(isNew ? "/api/devices" : `/api/devices/${encodeURIComponent(d.device_code)}`, { method: isNew ? "POST" : "PUT", body: v });
        toast("Төхөөрөмж хадгалагдлаа");
        if (isNew) go(`device/${saved.device_code}`);
      },
      isNew ? null : async () => {
        await api(`/api/devices/${encodeURIComponent(d.device_code)}`, { method: "DELETE" });
        toast("Устгагдлаа");
        go("devices");
      });
  }

  /**
   * Засварын дуудлага бүртгэх, шинэчлэх маягт.
   * `deviceId` өгөгдвөл паспортоос нээсэн гэж үзэж төхөөрөмжийг урьдчилан сонгоно.
   */
  function ticketForm(t, deviceId) {
    if (!S.devices.length) { toast("Эхлээд төхөөрөмж бүртгэнэ үү"); return; }
    const isNew = !t;
    t = t || { reported_date: todayISO(), status: "Нээлттэй", device_id: deviceId ? Number(deviceId) : "", technician: S.user.full_name || "" };
    const opts = S.devices.map((d) => [d.device_id, `${d.device_code} · ${devName(d)} · ${d.customer_name}`]);
    openDlg(isNew ? "Засварын дуудлага бүртгэх" : `Дуудлага №${t.ticket_id}`,
      sel("device_id", "Төхөөрөмж", t.device_id, opts, "full")
      + inp("reported_date", "Дуудлага ирсэн огноо", t.reported_date, "date")
      + sel("status", "Төлөв", t.status, ["Нээлттэй", "Хийгдэж байгаа", "Хаагдсан"])
      + area("problem_description", "Гэмтлийн тайлбар", t.problem_description)
      + area("diagnosis", "Онош", t.diagnosis)
      + area("action_taken", "Хийсэн ажил", t.action_taken)
      + inp("parts_used", "Сольсон сэлбэг", t.parts_used)
      + inp("technician", "Инженер", t.technician)
      + inp("closed_date", "Хаасан огноо", t.closed_date, "date"),
      async (v) => {
        v.device_id = Number(v.device_id);
        await api(isNew ? "/api/tickets" : `/api/tickets/${t.ticket_id}`, { method: isNew ? "POST" : "PUT", body: v });
        toast(isNew ? "Дуудлага бүртгэгдлээ" : "Дуудлага шинэчлэгдлээ");
      },
      isNew ? null : async () => { await api(`/api/tickets/${t.ticket_id}`, { method: "DELETE" }); toast("Устгагдлаа"); });
  }

  /**
   * Сануулгын мэдэгдлийн текстийг харуулж, санах ой руу хуулах боломж олгоно.
   * Текстийг сервер бэлтгэдэг тул бүх ажилтан ижил загвартай мессеж илгээнэ.
   */
  function notifyForm(r) {
    $("#dlgBody").innerHTML = `<h2>Харилцагчид илгээх мэдэгдэл</h2>
      <p class="muted" style="margin-top:0">Хүлээн авагч: ${esc(r.customer_name)}${r.customer_phone ? " · " + esc(r.customer_phone) : ""}. Текстийг хуулж SMS, WhatsApp, Facebook-ээр илгээнэ.</p>
      <div class="msgbox" id="msg">${esc(r.message)}</div>
      <div class="row"><button class="btn" id="fcancel">Хаах</button><button class="btn primary" id="fcopy">Текст хуулах</button></div>`;
    dlg.showModal();
    $("#fcancel").onclick = () => dlg.close();
    $("#fcopy").onclick = async () => {
      try { await navigator.clipboard.writeText(r.message); toast("Хуулагдлаа"); }
      catch (e) {
        const range = document.createRange(); range.selectNodeContents($("#msg"));
        const s = getSelection(); s.removeAllRanges(); s.addRange(range);
        toast("Текстийг сонголоо — Ctrl+C дарна уу");
      }
    };
  }

  /**
   * Сонгосон хүснэгтийг CSV файлаар татна.
   * Файлын хүсэлт ч гэсэн токентой явах ёстой тул fetch-ээр авч Blob болгон хадгална.
   */
  async function exportCSV(kind) {
    try {
      const res = await api(`/api/export/${kind}.csv`, { raw: true });
      const blob = await res.blob();
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `medjack_${kind}_${todayISO()}.csv`;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    } catch (e) { if (e.message !== "unauthorized") toast(e.message); }
  }

  /* ================================================================
   * 8. Үйл явдлын сонсогчид (event listeners)
   * ================================================================ */

  window.addEventListener("hashchange", () => { render(); $("#view").focus({ preventScroll: true }); window.scrollTo(0, 0); });
  document.querySelectorAll(".nav").forEach((b) => b.addEventListener("click", () => go(b.dataset.go)));
  $("#lbtn").addEventListener("click", login);
  $("#lp").addEventListener("keydown", (e) => { if (e.key === "Enter") login(); });
  $("#logoutBtn").addEventListener("click", () => logout());

  document.addEventListener("input", (e) => { if (e.target.id === "q") { F.q = e.target.value; render(); } });
  document.addEventListener("change", (e) => {
    if (e.target.id === "wf") { F.w = e.target.value; render(); }
    if (e.target.id === "tsf") { F.ts = e.target.value; render(); }
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.matches("tr.click")) e.target.click(); });

  /** Хуудсан дээрх бүх товч, мөрийн даралтыг нэг газраас зохицуулна (event delegation). */
  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-open],[data-ticket],[data-cust],[data-act],[data-go2]");
    if (!t || !$("#view").contains(t) && !$("#dlg").contains(t)) return;
    if (t.dataset.go2) return go(t.dataset.go2);
    if (t.dataset.open) return go(`device/${t.dataset.open}`);
    if (t.dataset.ticket) return ticketForm(S.tickets.find((x) => x.ticket_id === Number(t.dataset.ticket)));
    if (t.dataset.cust) return customerForm(custById(Number(t.dataset.cust)));
    switch (t.dataset.act) {
      case "newDevice": return deviceForm();
      case "editDevice": return deviceForm(S.detail[t.dataset.code] || S.devices.find((d) => d.device_code === t.dataset.code));
      case "newTicket": return ticketForm(null, t.dataset.id);
      case "editTicket": return ticketForm(S.tickets.find((x) => x.ticket_id === Number(t.dataset.id)));
      case "newCustomer": return customerForm();
      case "notify": return notifyForm(S.dash.reminders[Number(t.dataset.i)]);
      case "print": return window.print();
      case "csv": return exportCSV(t.dataset.kind);
    }
  });

  /** Цайвар, харанхуй горимыг солиод сонголтыг хадгална. */
  $("#themeBtn").addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    document.documentElement.dataset.theme = cur === "dark" ? "light" : "dark";
    localStorage.setItem("medjack.theme", document.documentElement.dataset.theme);
  });
  const savedTheme = localStorage.getItem("medjack.theme");
  if (savedTheme) document.documentElement.dataset.theme = savedTheme;

  start();
})();
