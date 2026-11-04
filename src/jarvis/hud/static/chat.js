/* JARVIS Chat client. ChatGPT-style conversation UI over the jarvisd API:
   - POST /command to send, POST /interrupt to stop, WS /events for live updates.
   - Assistant replies arrive whole (SpeechStarted carries the full text —
     the provider layer has no token streaming); chat.js renders them with a
     cancelable typewriter so the UI feels live. onToken() is the hook a
     future server-side streaming endpoint can call instead.
   - Conversations persist in localStorage only; the server keeps no chat
     history beyond the HUD snapshot (fetched once to seed an empty chat).
   - Model output NEVER hits innerHTML raw: everything goes through
     renderMarkdown(), which escapes HTML first.
   Served from /hud/chat.html ; API lives at / (same origin). */
(function () {
  "use strict";

  var qs = new URLSearchParams(location.search);
  var token = qs.get("token") || "";
  var apiBase = location.pathname.replace(/\/hud(\/.*)?$/, "");
  var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function api(path) { return apiBase + path; }
  function authHeaders() {
    return { "Content-Type": "application/json", "Authorization": "Bearer " + token };
  }

  /* ---------- safe markdown (escape first, then limited markup) ---------- */
  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;")
            .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function renderMarkdown(src) {
    var codeBlocks = [];
    // 1. Pull out fenced code blocks before escaping.
    var text = src.replace(/```(\w*)\n?([\s\S]*?)(?:```|$)/g, function (m, lang, code) {
      codeBlocks.push('<pre><code>' + escapeHtml(code.replace(/\n$/, "")) + '</code></pre>');
      return "\u0000" + (codeBlocks.length - 1) + "\u0000";
    });
    text = escapeHtml(text);
    // 2. Inline code (safe: content already escaped).
    text = text.replace(/`([^`\n]+)`/g, "<code>$1</code>");
    // 3. Bold / italic.
    text = text.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    text = text.replace(/(^|[\s(])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    // 4. Links — only http(s), nothing else.
    text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    // 5. Lists + paragraphs, line by line.
    var lines = text.split("\n"), html = "", inList = null, para = [];
    function flushPara() {
      if (para.length) { html += "<p>" + para.join("<br>") + "</p>"; para = []; }
    }
    function closeList() {
      if (inList) { html += inList === "ul" ? "</ul>" : "</ol>"; inList = null; }
    }
    lines.forEach(function (ln) {
      var um = ln.match(/^\s*[-*]\s+(.*)$/);
      var om = ln.match(/^\s*\d+\.\s+(.*)$/);
      if (um || om) {
        flushPara();
        var kind = um ? "ul" : "ol", item = (um ? um[1] : om[1]);
        if (inList !== kind) { closeList(); html += kind === "ul" ? "<ul>" : "<ol>"; inList = kind; }
        html += "<li>" + item + "</li>";
      } else if (/^\s*$/.test(ln)) {
        flushPara(); closeList();
      } else {
        closeList(); para.push(ln);
      }
    });
    flushPara(); closeList();
    // 6. Restore code blocks.
    html = html.replace(/\u0000(\d+)\u0000/g, function (m, i) { return codeBlocks[+i]; });
    return html || "<p></p>";
  }

  /* ---------- conversations (localStorage) ---------- */
  var LS_CHATS = "jarvis-chats-v1", LS_ACTIVE = "jarvis-chat-active";
  function loadChats() {
    try { return JSON.parse(localStorage.getItem(LS_CHATS) || "[]"); }
    catch (e) { return []; }
  }
  function saveChats() {
    try { localStorage.setItem(LS_CHATS, JSON.stringify(chats)); }
    catch (e) { /* storage blocked: session-only */ }
  }
  var chats = loadChats();
  var activeId = null;
  try { activeId = localStorage.getItem(LS_ACTIVE); } catch (e) {}
  function activeChat() {
    var c = null;
    for (var i = 0; i < chats.length; i++) if (chats[i].id === activeId) c = chats[i];
    if (!c) {
      c = newChat(false);
      chats.unshift(c);
    }
    return c;
  }
  function newChat(select) {
    var c = { id: "c" + Date.now().toString(36) + Math.floor(Math.random() * 1e4),
              title: "New chat", created: Date.now(), messages: [] };
    if (select !== false) { chats.unshift(c); setActive(c.id); }
    return c;
  }
  function setActive(id) {
    activeId = id;
    try { localStorage.setItem(LS_ACTIVE, id); } catch (e) {}
    renderSidebar(); renderThread();
  }
  function touchChat(c, title) {
    if (title && (c.title === "New chat")) {
      c.title = title.length > 42 ? title.slice(0, 42) + "…" : title;
    }
    saveChats(); renderSidebar();
  }

  /* ---------- DOM ---------- */
  var threadEl = document.getElementById("thread");
  var convListEl = document.getElementById("conv-list");
  var inputEl = document.getElementById("input");
  var sendBtn = document.getElementById("btn-send");
  var stopBtn = document.getElementById("btn-stop");
  var micBtn = document.getElementById("btn-mic");
  var connEl = document.getElementById("side-conn");
  var workingEl = document.getElementById("working");
  var workingLabel = document.getElementById("working-label");
  var workingTools = document.getElementById("working-tools");
  var speakOpt = document.getElementById("opt-speak");

  try { if (speakOpt) speakOpt.checked = localStorage.getItem("jarvis-speak") === "1"; } catch (e) {}
  if (speakOpt) speakOpt.addEventListener("change", function () {
    try { localStorage.setItem("jarvis-speak", speakOpt.checked ? "1" : "0"); } catch (e) {}
    if (!speakOpt.checked && "speechSynthesis" in window) window.speechSynthesis.cancel();
  });
  var contrastOpt = document.getElementById("opt-contrast");
  if (contrastOpt) contrastOpt.addEventListener("change", function () {
    document.body.classList.toggle("hc", this.checked);
  });
  var sideBtn = document.getElementById("btn-side");
  if (sideBtn) sideBtn.addEventListener("click", function () {
    document.getElementById("sidebar").classList.toggle("closed");
  });
  var sidebarEl = document.getElementById("sidebar");
  if (sidebarEl && window.innerWidth <= 760) sidebarEl.classList.add("closed");

  function setConn(t) { if (connEl) connEl.textContent = t; }
  function scrollBottom() { threadEl.scrollTop = threadEl.scrollHeight; }
  function fmtTime(ts) {
    var d = new Date(ts);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  /* ---------- message rendering ---------- */
  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    return e;
  }
  function addMsg(role, text, opts) {
    opts = opts || {};
    var c = activeChat();
    var m = { role: role, text: text, ts: Date.now(), tools: opts.tools || [] };
    if (!opts.ephemeral) { c.messages.push(m); touchChat(c, role === "user" ? text : undefined); }

    var wrap = el("div", "msg " + role);
    var bubble = el("div", "bubble");
    bubble.innerHTML = role === "error" ? escapeHtml(text) : renderMarkdown(text);
    wrap.appendChild(bubble);
    var meta = el("div", "meta");
    meta.appendChild(el("span", null, escapeHtml(fmtTime(m.ts))));
    var acts = el("span", "acts");
    function actBtn(label, title, fn) {
      var b = el("button", null, escapeHtml(label));
      b.title = title; b.setAttribute("aria-label", title);
      b.addEventListener("click", fn); acts.appendChild(b);
    }
    actBtn("⧉", "Copy", function () { copyText(text); });
    if (role === "user") actBtn("↻", "Retry", function () { postCommand(text); });
    if (role === "jarvis") actBtn("🔊", "Speak", function () { speakText(text); });
    meta.appendChild(acts);
    wrap.appendChild(meta);
    if (opts.tools && opts.tools.length) wrap.appendChild(toolsDetails(opts.tools));
    threadElInner().appendChild(wrap);
    scrollBottom();
    return { wrap: wrap, bubble: bubble, record: m };
  }
  function toolsDetails(tools) {
    var d = el("details", "tools");
    d.appendChild(el("summary", null, "Tools used (" + tools.length + ")"));
    var ol = el("ol");
    tools.forEach(function (t) {
      var li = el("li", t.ok === false ? "bad" : "ok", escapeHtml(t.tool || "?"));
      ol.appendChild(li);
    });
    d.appendChild(ol);
    return d;
  }
  function threadElInner() {
    var inner = document.getElementById("thread-inner");
    if (!inner) { inner = el("div"); inner.id = "thread-inner"; threadEl.appendChild(inner); }
    return inner;
  }
  function renderThread() {
    threadEl.innerHTML = "";
    var c = activeChat();
    if (!c.messages.length) {
      var e = el("div", "empty");
      e.innerHTML = '<div class="big">◉</div><h1>What can I do for you?</h1>' +
        "<p>Ask anything — I can run tools, and I'll always ask before anything risky.</p>";
      threadEl.appendChild(e);
      return;
    }
    c.messages.forEach(function (m) { addMsg(m.role, m.text, { ephemeral: true, tools: m.tools }); });
    scrollBottom();
  }

  /* ---------- sidebar ---------- */
  function renderSidebar() {
    var cardTitle = document.getElementById("card-title");
    var ac = null;
    for (var i0 = 0; i0 < chats.length; i0++) if (chats[i0].id === activeId) ac = chats[i0];
    if (cardTitle) cardTitle.textContent = ac ? ac.title : "New chat";
    if (!convListEl) return;
    chats.forEach(function (c) {
      var li = el("li", c.id === activeId ? "active" : null);
      var t = el("span", "t", escapeHtml(c.title));
      t.title = "Rename (double-click)";
      t.addEventListener("click", function () { setActive(c.id); });
      t.addEventListener("dblclick", function (ev) {
        ev.stopPropagation();
        var name = prompt("Rename chat:", c.title);
        if (name && name.trim()) { c.title = name.trim().slice(0, 60); saveChats(); renderSidebar(); }
      });
      var x = el("button", "x", "×");
      x.title = "Delete chat"; x.setAttribute("aria-label", "Delete chat");
      x.addEventListener("click", function (ev) {
        ev.stopPropagation();
        if (!confirm("Delete this chat?")) return;
        chats = chats.filter(function (o) { return o.id !== c.id; });
        saveChats();
        if (c.id === activeId) { activeId = null; }
        setActive(activeChat().id);
      });
      li.appendChild(t); li.appendChild(x);
      convListEl.appendChild(li);
    });
  }
  var btnNew = document.getElementById("btn-new");
  if (btnNew) btnNew.addEventListener("click", function () {
    newChat(true); saveChats();
  });

  /* ---------- typewriter streaming ---------- */
  var typerTimer = null, typerTarget = null;
  function stopTypewriter() {
    if (typerTimer) { clearTimeout(typerTimer); typerTimer = null; }
    if (typerTarget) {
      typerTarget.bubble.innerHTML = renderMarkdown(typerTarget.full);
      typerTarget.bubble.classList.remove("cursor");
      scrollBottom();
      typerTarget = null;
    }
    updateStopBtn();
  }
  // Hook for a future server-side token stream: onToken(token) appends.
  function onToken(tok) {
    if (!typerTarget) return;
    typerTarget.full += tok;
  }
  function streamAssistant(fullText, tools, done) {
    var node = addMsg("jarvis", "", { ephemeral: true });
    var record = { role: "jarvis", text: fullText, ts: Date.now(), tools: tools || [] };
    // Persist the full text immediately; rendering catches up.
    var c = activeChat(); c.messages.push(record); saveChats();
    node.bubble.classList.add("cursor");
    if (reducedMotion || fullText.length < 4) {
      node.bubble.innerHTML = renderMarkdown(fullText);
      node.bubble.classList.remove("cursor");
      if (record.tools.length) node.wrap.appendChild(toolsDetails(record.tools));
      scrollBottom(); updateStopBtn();
      if (speakOpt.checked) speakText(fullText);
      done && done();
      return;
    }
    typerTarget = { bubble: node.bubble, full: fullText, node: node, record: record };
    var i = 0, step = Math.max(6, Math.floor(fullText.length / 120));
    updateStopBtn();
    (function tick() {
      if (!typerTarget) return;
      i = Math.min(fullText.length, i + step);
      typerTarget.bubble.innerHTML = renderMarkdown(fullText.slice(0, i)) ;
      typerTarget.bubble.classList.add("cursor");
      scrollBottom();
      if (i < fullText.length) { typerTimer = setTimeout(tick, 14); }
      else {
        var rec = typerTarget.record, nd = typerTarget.node;
        typerTarget = null; typerTimer = null;
        nd.bubble.classList.remove("cursor");
        if (rec.tools.length) nd.wrap.appendChild(toolsDetails(rec.tools));
        scrollBottom(); updateStopBtn();
        if (speakOpt.checked) speakText(fullText);
        done && done();
      }
    })();
  }

  /* ---------- working indicator + tools ---------- */
  var pendingTools = [];
  function currentTools() { return pendingTools.slice(); }
  function showWorking(label) {
    workingLabel.textContent = label || "Working…";
    workingEl.hidden = false;
    updateStopBtn();
  }
  function hideWorking() {
    workingEl.hidden = true; pendingTools = [];
    workingTools.innerHTML = ""; workingTools.hidden = true;
    document.getElementById("working-toggle").setAttribute("aria-expanded", "false");
    updateStopBtn();
  }
  document.getElementById("working-toggle").addEventListener("click", function () {
    var open = workingTools.hidden;
    workingTools.hidden = !open;
    this.setAttribute("aria-expanded", String(open));
  });
  function toolStarted(tool) {
    pendingTools.push({ tool: tool, ok: null });
    var li = el("li", null, escapeHtml(tool));
    li.dataset.tool = tool;
    workingTools.appendChild(li);
    if (workingEl.hidden) showWorking("Working…");
  }
  function toolFinished(tool, ok) {
    for (var i = pendingTools.length - 1; i >= 0; i--) {
      if (pendingTools[i].tool === tool && pendingTools[i].ok === null) {
        pendingTools[i].ok = ok !== false; break;
      }
    }
    var lis = workingTools.querySelectorAll("li");
    for (var j = lis.length - 1; j >= 0; j--) {
      if (lis[j].dataset.tool === tool && !lis[j].className) {
        lis[j].className = ok !== false ? "ok" : "bad"; break;
      }
    }
  }

  /* ---------- inline confirm cards ---------- */
  function addConfirmCard(question) {
    var card = el("div", "confirm");
    card.innerHTML = "<h4>Confirmation needed</h4>";
    var p = el("p", null, escapeHtml(question));
    card.appendChild(p);
    var row = el("div", "row");
    var haan = el("button", "haan", "Haan");
    var nahi = el("button", "nahi", "Nahi");
    function answer(v) {
      card.classList.add("answered");
      postCommand(v);
    }
    haan.addEventListener("click", function () { answer("haan"); });
    nahi.addEventListener("click", function () { answer("nahi"); });
    row.appendChild(haan); row.appendChild(nahi);
    card.appendChild(row);
    threadElInner().appendChild(card);
    scrollBottom();
    card._setAnswered = function () { card.classList.add("answered"); };
    return card;
  }
  var openConfirm = null;

  /* ---------- commands ---------- */
  var QUEUE_KEY = "jarvis-pending-commands";
  function loadQueue() {
    try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]"); }
    catch (e) { return []; }
  }
  function saveQueue(q) {
    try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); } catch (e) {}
  }
  function postRaw(path, body) {
    return fetch(api(path), {
      method: "POST", headers: authHeaders(), body: JSON.stringify(body || {})
    });
  }
  function postCommand(text) {
    if (!navigator.onLine) {
      var q = loadQueue(); q.push(text); saveQueue(q);
      addMsg("error", "Offline — message queued, will send on reconnect.", { ephemeral: true });
      return;
    }
    postRaw("/command", { text: text }).catch(function () {
      var q2 = loadQueue(); q2.push(text); saveQueue(q2);
    });
  }
  function flushQueue() {
    var q = loadQueue();
    if (!q.length || !navigator.onLine) return;
    var next = q.shift(); saveQueue(q);
    postRaw("/command", { text: next }).then(flushQueue).catch(function () {
      var r = loadQueue(); r.unshift(next); saveQueue(r);
    });
  }
  function interrupt() {
    stopTypewriter();
    postRaw("/interrupt", {}).catch(function () {});
    hideWorking();
  }

  /* ---------- composer ---------- */
  function autogrow() {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(160, inputEl.scrollHeight) + "px";
  }
  inputEl.addEventListener("input", autogrow);
  function updateStopBtn() {
    var busy = !!typerTarget || !workingEl.hidden;
    stopBtn.hidden = !busy;
    sendBtn.disabled = busy;
  }
  function sendInput() {
    var text = inputEl.value.trim();
    if (!text) return;
    stopTypewriter();
    addMsg("user", text);
    inputEl.value = ""; autogrow();
    showWorking("Thinking…");
    postCommand(text);
  }
  sendBtn.addEventListener("click", sendInput);
  stopBtn.addEventListener("click", interrupt);
  inputEl.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendInput(); }
  });

  /* ---------- mic (Web Speech API; no server STT endpoint exists) ---------- */
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  var recog = null;
  if (!SR) {
    micBtn.disabled = true;
    micBtn.title = "Voice input isn't supported in this browser — type instead.";
  } else {
    micBtn.addEventListener("click", function () {
      if (recog) { recog.stop(); return; }
      recog = new SR();
      recog.lang = "en-IN"; recog.interimResults = true; recog.maxAlternatives = 1;
      var finalText = "";
      recog.onresult = function (ev) {
        var interim = "";
        for (var i = ev.resultIndex; i < ev.results.length; i++) {
          var t = ev.results[i][0].transcript;
          if (ev.results[i].isFinal) finalText += t; else interim += t;
        }
        inputEl.value = (finalText + interim).trim(); autogrow();
      };
      recog.onend = function () { recog = null; micBtn.classList.remove("rec"); };
      recog.onerror = function () { recog = null; micBtn.classList.remove("rec"); };
      try { recog.start(); micBtn.classList.add("rec"); }
      catch (e) { recog = null; micBtn.classList.remove("rec"); }
    });
  }

  /* ---------- speech + clipboard ---------- */
  function speakText(text) {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(text.slice(0, 500));
    u.lang = "en-IN";
    window.speechSynthesis.speak(u);
  }
  function copyText(text) {
    function done(btn) {
      var old = btn.textContent; btn.textContent = "✓";
      setTimeout(function () { btn.textContent = old; }, 1200);
    }
    var btn = document.activeElement;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { done(btn); }, function () {});
    } else {
      var ta = document.createElement("textarea");
      ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); done(btn); } catch (e) {}
      document.body.removeChild(ta);
    }
  }

  /* ---------- events from jarvisd ---------- */
  function onEvent(ev) {
    var type = ev.type || "";
    if (type === "UtterancePartial") {
      // Live user dictation shown inside the composer, not the thread.
      inputEl.value = ev.text || ""; autogrow();
    }
    else if (type === "UtteranceFinal") {
      addMsg("user", ev.text || "");
      showWorking("Thinking…");
    }
    else if (type === "AgentThinking") { showWorking("Thinking…"); }
    else if (type === "ToolRequested") { toolStarted(ev.tool || "?"); }
    else if (type === "ToolFinished") { toolFinished(ev.tool || "?", ev.ok); }
    else if (type === "ConfirmationRequested") {
      if (openConfirm) openConfirm._setAnswered();
      openConfirm = addConfirmCard(ev.question || ("Allow " + (ev.tool || "") + "?"));
    }
    else if (type === "ConfirmationAnswered") {
      if (openConfirm) { openConfirm._setAnswered(); openConfirm = null; }
      showWorking("Thinking…");
    }
    else if (type === "SpeechStarted") {
      var doneTools = currentTools(); // capture before hideWorking() clears
      hideWorking();
      streamAssistant(ev.text || "", doneTools);
    }
    else if (type === "SpeechStopped") { stopTypewriter(); hideWorking(); }
    else if (type === "Interrupt") { stopTypewriter(); hideWorking(); }
    else if (type === "Error") {
      stopTypewriter(); hideWorking();
      addMsg("error", (ev.where ? ev.where + ": " : "") + (ev.message || "error"));
    }
    // Bridge to the floating buddy (buddy.html): reflect liveness in the
    // character. No-op on the full-page chat (window.JarvisBuddy undefined).
    if (window.JarvisBuddy && window.JarvisBuddy.setState) {
      var bs = null;
      if (type === "WakeDetected" || type === "UtterancePartial" || type === "UtteranceFinal") bs = "listening";
      else if (type === "AgentThinking" || type === "ToolRequested" || type === "ToolFinished") bs = "thinking";
      else if (type === "ConfirmationRequested") bs = "attention";
      else if (type === "ConfirmationAnswered") bs = "thinking";
      else if (type === "SpeechStarted") bs = "speaking";
      else if (type === "SpeechStopped" || type === "Interrupt" || type === "Error") bs = "idle";
      if (bs) window.JarvisBuddy.setState(bs);
    }
  }

  /* ---------- websocket ---------- */
  function connect() {
    var proto = location.protocol === "https:" ? "wss:" : "ws:";
    var ws = new WebSocket(proto + "//" + location.host + api("/events") +
                           "?token=" + encodeURIComponent(token));
    ws.onopen = function () { setConn("connected"); };
    ws.onclose = function () {
      setConn("reconnecting…");
      setTimeout(connect, 2000);
    };
    ws.onmessage = function (m) {
      try {
        var ev = JSON.parse(m.data);
        if (ev.type && ev.type !== "hello") onEvent(ev);
      } catch (e) { /* ignore malformed */ }
    };
  }
  window.addEventListener("online", function () { flushQueue(); connect(); });
  window.addEventListener("offline", function () { setConn("offline — messages will queue"); });

  /* ---------- boot ---------- */
  // Keep the ?token= on the HUD link (full-page chat only).
  var hudLink = document.getElementById("link-hud");
  if (hudLink) hudLink.href = "index.html?token=" + encodeURIComponent(token);
  renderSidebar();
  renderThread();
  // Seed an empty chat from the server snapshot (mid-session connect).
  fetch(api("/hud/snapshot?token=" + encodeURIComponent(token)))
    .then(function (r) { return r.json(); })
    .then(function (snap) {
      var c = activeChat();
      if (c.messages.length) return;
      (snap.transcript || []).forEach(function (t) {
        if (t.who === "user" || t.who === "jarvis")
          c.messages.push({ role: t.who, text: t.text || "", ts: Date.now(), tools: [] });
      });
      if (c.messages.length) { touchChat(c); renderThread(); }
    }).catch(function () {});
  updateStopBtn();
  connect();
})();
