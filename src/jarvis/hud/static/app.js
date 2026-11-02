/* JARVIS HUD client (Task 7.2). Event-driven: renders whatever the server's
   HUDStateMachine reports over the /events WebSocket. No polling.
   Served from /hud/ ; API lives at / (same origin). */
(function () {
  "use strict";

  var qs = new URLSearchParams(location.search);
  var token = qs.get("token") || "";
  // /hud/index.html -> apiBase ""; /hud -> apiBase "" (both fine)
  var apiBase = location.pathname.replace(/\/hud(\/.*)?$/, "");
  var reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var body = document.body;
  var connEl = document.getElementById("conn");
  var stateLabel = document.getElementById("state-label");
  var transcriptEl = document.getElementById("transcript");
  var timelineEl = document.getElementById("timeline");
  var confirmCard = document.getElementById("confirm-card");
  var confirmQ = document.getElementById("confirm-q");
  var errorBanner = document.getElementById("error-banner");
  var errorMsg = document.getElementById("error-msg");
  var canvas = document.getElementById("orb");
  var ctx = canvas.getContext("2d");

  var state = "idle";
  var audioLevel = 0;
  var liveLi = null;
  var startT = performance.now();

  function api(path) { return apiBase + path; }

  function setState(s) {
    state = s;
    body.dataset.state = s;
    stateLabel.textContent = s;
  }

  /* --- orb renderer (Canvas 2D; state-colored, audio-reactive) --- */
  function drawOrb() {
    var t = (performance.now() - startT) / 1000;
    var w = canvas.width, h = canvas.height, cx = w / 2, cy = h / 2;
    ctx.clearRect(0, 0, w, h);
    var color = getComputedStyle(body).getPropertyValue("--state-color").trim() || "#6ea8fe";

    var baseR = 70, amp = 0;
    if (state === "idle") amp = reducedMotion ? 0 : 4 * Math.sin(t * 1.2);
    else if (state === "listening") amp = audioLevel * 26 + 3 * Math.sin(t * 6);
    else if (state === "thinking") amp = 10 * Math.abs(Math.sin(t * 2.5));
    else if (state === "speaking") amp = audioLevel * 20 + 4 * Math.sin(t * 9);
    else if (state === "error") amp = (Math.sin(t * 30) > 0 ? 8 : -4);

    ctx.beginPath();
    var segs = 64, i, a, r, x, y;
    for (i = 0; i <= segs; i++) {
      a = (i / segs) * Math.PI * 2;
      r = baseR + amp * Math.sin(a * 3 + t * 2);
      x = cx + r * Math.cos(a); y = cy + r * Math.sin(a);
      if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.strokeStyle = color; ctx.lineWidth = 3; ctx.stroke();
    ctx.globalAlpha = 0.18; ctx.fillStyle = color; ctx.fill(); ctx.globalAlpha = 1;

    if (state === "thinking" && !reducedMotion) {
      ctx.save(); ctx.translate(cx, cy); ctx.rotate(t * 1.5);
      ctx.strokeStyle = color; ctx.lineWidth = 5;
      for (var k = 0; k < 3; k++) {
        ctx.beginPath(); ctx.arc(0, 0, baseR + 18, k * 2.1, k * 2.1 + 1.1); ctx.stroke();
      }
      ctx.restore();
    }
    if (!reducedMotion) requestAnimationFrame(drawOrb);
  }

  /* --- transcript / timeline --- */
  function addTranscript(who, text, live) {
    if (live) {
      if (!liveLi || liveLi.dataset.who !== who) {
        liveLi = document.createElement("li");
        liveLi.dataset.who = who;
        transcriptEl.appendChild(liveLi);
      }
      liveLi.className = who + " live";
      liveLi.textContent = text;
    } else {
      if (liveLi && liveLi.dataset.who === who) {
        liveLi.classList.remove("live");
        liveLi.textContent = text;
        liveLi = null;
      } else {
        var li = document.createElement("li");
        li.className = who;
        li.textContent = text;
        transcriptEl.appendChild(li);
      }
    }
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
  }

  function addTimeline(label, ok) {
    var li = document.createElement("li");
    li.textContent = label;
    if (ok === true) li.className = "ok-true";
    if (ok === false) li.className = "ok-false";
    timelineEl.appendChild(li);
    timelineEl.scrollTop = timelineEl.scrollHeight;
  }

  /* --- commands back to jarvisd --- */

  /* Task 7.9: offline queue. When the PWA loses connectivity, commands are
     stored in localStorage and flushed in order when 'online' fires. */
  var QUEUE_KEY = "jarvis-pending-commands";
  function loadQueue() {
    try { return JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]"); }
    catch (e) { return []; }
  }
  function saveQueue(q) {
    try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); }
    catch (e) { /* storage full/blocked: drop */ }
  }
  function postCommand(text) {
    return fetch(api("/command"), {
      method: "POST",
      headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token },
      body: JSON.stringify({ text: text })
    });
  }
  function flushQueue() {
    var q = loadQueue();
    if (!q.length || !navigator.onLine) return;
    var next = q.shift();
    saveQueue(q);
    postCommand(next).then(flushQueue).catch(function () {
      var r = loadQueue(); r.unshift(next); saveQueue(r);
    });
  }
  window.addEventListener("online", function () {
    connEl.textContent = "connected";
    flushQueue();
    connect();
  });
  window.addEventListener("offline", function () {
    connEl.textContent = "offline — commands will queue";
  });

  function sendCommand(text) {
    if (!navigator.onLine) {
      var q = loadQueue(); q.push(text); saveQueue(q);
      addTimeline("queued (offline): " + text, null);
      return;
    }
    postCommand(text).catch(function () {
      var q2 = loadQueue(); q2.push(text); saveQueue(q2);
    });
  }

  /* Task 7.9: PWA install prompt. */
  var deferredPrompt = null;
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferredPrompt = e;
    document.getElementById("btn-install").hidden = false;
  });
  document.getElementById("btn-install").addEventListener("click", function () {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(function () {
      deferredPrompt = null;
      document.getElementById("btn-install").hidden = true;
    });
  });

  /* Task 7.9: notifications for important events (opt-in, in-page).
     True Web Push (VAPID) is documented in docs/PWA_SETUP.md; this covers
     the HUD-open case with zero server crypto. */
  function notifyImportant(title, body) {
    if (!("Notification" in window)) return;
    if (Notification.permission === "granted") {
      try { new Notification(title, { body: body, tag: "jarvis" }); }
      catch (e) { /* ignore */ }
    } else if (Notification.permission === "default") {
      Notification.requestPermission();
    }
  }

  document.getElementById("btn-haan").addEventListener("click", function () {
    sendCommand("haan"); confirmCard.hidden = true;
  });
  document.getElementById("btn-nahi").addEventListener("click", function () {
    sendCommand("nahi"); confirmCard.hidden = true;
  });
  document.getElementById("btn-dismiss").addEventListener("click", function () {
    errorBanner.hidden = true; setState("idle");
  });
  document.getElementById("cmd-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var input = document.getElementById("cmd-input");
    if (input.value.trim()) { sendCommand(input.value.trim()); input.value = ""; }
  });
  document.querySelectorAll("#mode-toggle button").forEach(function (btn) {
    btn.addEventListener("click", function () {
      body.dataset.mode = btn.dataset.setmode;
      document.querySelectorAll("#mode-toggle button").forEach(function (b) {
        b.setAttribute("aria-selected", b === btn ? "true" : "false");
      });
    });
  });
  document.getElementById("btn-telemetry").addEventListener("click", function () {
    var t = document.getElementById("telemetry");
    t.hidden = !t.hidden;
    this.setAttribute("aria-pressed", String(!t.hidden));
  });
  document.getElementById("btn-contrast").addEventListener("click", function () {
    body.classList.toggle("hc");
    this.setAttribute("aria-pressed", String(body.classList.contains("hc")));
  });

  /* --- event handling (mirrors server event_to_dict) --- */
  function onEvent(ev) {
    var type = ev.type || "";
    if (type === "WakeDetected") setState("listening");
    else if (type === "UtterancePartial") addTranscript("user", ev.text || "", true);
    else if (type === "UtteranceFinal") { addTranscript("user", ev.text || "", false); setState("thinking"); }
    else if (type === "AgentThinking") setState("thinking");
    else if (type === "ToolRequested") addTimeline((ev.tool || "?") + "…", null);
    else if (type === "ToolFinished") addTimeline((ev.tool || "?"), ev.ok !== false);
    else if (type === "ConfirmationRequested") {
      setState("confirming");
      confirmQ.textContent = ev.question || ("Allow " + (ev.tool || "") + "?");
      confirmCard.hidden = false;
      notifyImportant("JARVIS confirmation", confirmQ.textContent);
    }
    else if (type === "ConfirmationAnswered") { confirmCard.hidden = true; setState("thinking"); }
    else if (type === "SpeechStarted") { setState("speaking"); addTranscript("jarvis", ev.text || "", false); }
    else if (type === "SpeechStopped") setState("idle");
    else if (type === "Interrupt") setState("idle");
    else if (type === "Error") {
      setState("error");
      errorMsg.textContent = (ev.where ? ev.where + ": " : "") + (ev.message || "error");
      errorBanner.hidden = false;
      notifyImportant("JARVIS error", errorMsg.textContent);
    }
    else if (type === "AudioLevel") { audioLevel = Math.max(0, Math.min(1, ev.level || 0)); }
  }

  /* --- websocket --- */
  function connect() {
    var proto = location.protocol === "https:" ? "wss:" : "ws:";
    var ws = new WebSocket(proto + "//" + location.host + api("/events") +
                           "?token=" + encodeURIComponent(token));
    ws.onopen = function () { connEl.textContent = "connected"; };
    ws.onclose = function () {
      connEl.textContent = "reconnecting…";
      setTimeout(connect, 2000);
    };
    ws.onmessage = function (m) {
      try {
        var ev = JSON.parse(m.data);
        if (ev.type && ev.type !== "hello") onEvent(ev);
      } catch (e) { /* ignore malformed */ }
    };
  }

  /* --- snapshot for clients that connect mid-session --- */
  fetch(api("/hud/snapshot?token=" + encodeURIComponent(token)))
    .then(function (r) { return r.json(); })
    .then(function (snap) {
      setState(snap.state || "idle");
      (snap.transcript || []).forEach(function (t) { addTranscript(t.who, t.text, t.live); });
      (snap.timeline || []).forEach(function (t) { addTimeline(t.label, t.ok); });
      if (snap.confirm_card && !snap.confirm_card.dismissed) {
        confirmQ.textContent = snap.confirm_card.question || "";
        confirmCard.hidden = false;
      }
    }).catch(function () {});

  connect();
  drawOrb();
})();
