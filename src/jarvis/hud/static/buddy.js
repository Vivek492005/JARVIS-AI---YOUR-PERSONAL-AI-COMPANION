/* JARVIS buddy controller: floating companion character + expandable chat card.
   chat.js (loaded first) drives the conversation and reports liveness through
   window.JarvisBuddy.setState(). This file owns: expand/collapse, drag,
   pop-out window, attention dot. No network of its own. */
(function () {
  "use strict";

  var buddy = document.getElementById("buddy");
  var card = document.getElementById("chat-card");
  var notif = buddy.querySelector(".buddy-notif");
  var POS_KEY = "jarvis-buddy-pos";
  var BUDDY_PX = 128;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* --- state bridge (called by chat.js onEvent) --- */
  function setState(s) {
    buddy.dataset.state = s;
    if (s === "attention") notif.hidden = false;
  }
  function clearAttention() { notif.hidden = true; }

  /* --- expand / collapse --- */
  function openChat() {
    if (!card.hidden) return;
    card.hidden = false;
    // Force reflow so the transition runs.
    void card.offsetWidth;
    card.classList.add("open");
    clearAttention();
    poke(); say("Hey! 🙏 Bolo, kya karun?");
    var input = document.getElementById("input");
    if (input) input.focus();
  }
  function closeChat() {
    if (card.hidden) return;
    card.classList.remove("open");
    say("Phir milenge! 👋");
    setTimeout(function () { card.hidden = true; }, 200);
  }
  function toggleChat() { card.hidden ? openChat() : closeChat(); }

  window.JarvisBuddy = {
    setState: setState,
    clearAttention: clearAttention,
    open: openChat,
    close: closeChat,
    toggle: toggleChat
  };

  document.getElementById("btn-close").addEventListener("click", closeChat);
  document.getElementById("btn-pop").addEventListener("click", function () {
    // Compact always-on-top-ish window. If the browser blocks the popup,
    // the user just keeps using this tab.
    window.open(location.href, "jarvis-buddy",
                "width=430,height=680,menubar=no,toolbar=no,location=no,status=no");
  });

  /* Click-outside collapses (the stage is a full-viewport overlay). */
  document.getElementById("stage").addEventListener("click", function (e) {
    if (!card.hidden && !card.contains(e.target) && !buddy.contains(e.target)) closeChat();
  });

  /* --- drag (pointer events; a tap without movement still toggles) --- */
  var drag = null;
  function loadPos() {
    try {
      var p = JSON.parse(localStorage.getItem(POS_KEY) || "null");
      if (p && typeof p.x === "number" && typeof p.y === "number") {
        buddy.style.right = "auto"; buddy.style.bottom = "auto";
        buddy.style.left = Math.max(0, Math.min(window.innerWidth - BUDDY_PX, p.x)) + "px";
        buddy.style.top = Math.max(0, Math.min(window.innerHeight - BUDDY_PX, p.y)) + "px";
      }
    } catch (e) { /* ignore */ }
  }
  function savePos() {
    try {
      localStorage.setItem(POS_KEY, JSON.stringify({
        x: buddy.offsetLeft, y: buddy.offsetTop
      }));
    } catch (e) { /* ignore */ }
  }
  buddy.addEventListener("pointerdown", function (e) {
    drag = { sx: e.clientX, sy: e.clientY,
             ox: buddy.offsetLeft, oy: buddy.offsetTop, moved: false };
    try { buddy.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
  });
  buddy.addEventListener("pointermove", function (e) {
    if (!drag) return;
    var dx = e.clientX - drag.sx, dy = e.clientY - drag.sy;
    if (Math.abs(dx) + Math.abs(dy) > 6) drag.moved = true;
    if (drag.moved) {
      buddy.style.right = "auto"; buddy.style.bottom = "auto";
      buddy.style.left = Math.max(0, Math.min(window.innerWidth - BUDDY_PX, drag.ox + dx)) + "px";
      buddy.style.top = Math.max(0, Math.min(window.innerHeight - BUDDY_PX, drag.oy + dy)) + "px";
    }
  });
  function endDrag(e) {
    if (!drag) return;
    var wasDrag = drag.moved;
    drag = null;
    if (wasDrag) { savePos(); doAction("act-squash"); poke(); e.preventDefault(); e.stopPropagation(); }
    else toggleChat();
  }
  buddy.addEventListener("pointerup", endDrag);
  buddy.addEventListener("pointercancel", function () { drag = null; });
  buddy.addEventListener("keydown", function (e) {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleChat(); }
    if (e.key === "Escape") closeChat();
  });

  /* --- liveliness engine: the buddy feels alive --- */
  var bodyEl = buddy.querySelector(".buddy-body");
  var sayEl = document.getElementById("buddy-say");
  var sayTimer = null, idleTimer = null, sleepTimer = null;
  var lastActive = Date.now();

  function poke() {
    lastActive = Date.now();
    buddy.classList.remove("sleeping");
    if (idleTimer) { clearTimeout(idleTimer); idleTimer = null; }
    scheduleIdle();
  }
  function say(text, ms) {
    if (reduceMotion) return;
    sayEl.textContent = text;
    sayEl.hidden = false;
    if (sayTimer) clearTimeout(sayTimer);
    sayTimer = setTimeout(function () { sayEl.hidden = true; }, ms || 2600);
  }
  function doAction(cls) {
    if (reduceMotion || buddy.dataset.state !== "idle") return;
    bodyEl.classList.remove("act-hop", "act-spin", "act-tilt", "act-squash");
    void bodyEl.offsetWidth; // restart animation
    bodyEl.classList.add(cls);
    setTimeout(function () { bodyEl.classList.remove(cls); }, 850);
  }
  var IDLE_ACTS = ["act-hop", "act-spin", "act-tilt", "act-squash"];
  var IDLE_QUIPS = [
    "Pssst… kuch chahiye? 👀",
    "Main yahin hoon! ✨",
    "Mic dabake bolke dekho 🎙️",
    "Aaj ka din kaisa ja raha hai? ☀️"
  ];
  function scheduleIdle() {
    if (reduceMotion) return;
    if (idleTimer) clearTimeout(idleTimer);
    idleTimer = setTimeout(function () {
      // Random cute action every 8–15s while idle.
      doAction(IDLE_ACTS[Math.floor(Math.random() * IDLE_ACTS.length)]);
      if (Math.random() < 0.35) say(IDLE_QUIPS[Math.floor(Math.random() * IDLE_QUIPS.length)]);
      scheduleIdle();
      // Fall asleep after ~90s of no interaction.
      if (sleepTimer) clearTimeout(sleepTimer);
      sleepTimer = setTimeout(function () {
        if (Date.now() - lastActive > 85000 && buddy.dataset.state === "idle") {
          buddy.classList.add("sleeping");
          say("Zzz… 😴");
        }
      }, 90000);
    }, 8000 + Math.random() * 7000);
  }

  /* Subtle tilt toward the cursor — the buddy "looks" at you.
     Applied to the avatar img so it composes with the body animations. */
  var tiltRaf = null;
  var avatarEl = buddy.querySelector(".buddy-avatar");
  document.getElementById("stage").addEventListener("pointermove", function (e) {
    if (reduceMotion || drag) return;
    if (tiltRaf) return;
    tiltRaf = requestAnimationFrame(function () {
      tiltRaf = null;
      var r = buddy.getBoundingClientRect();
      var cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      var dx = (e.clientX - cx) / window.innerWidth, dy = (e.clientY - cy) / window.innerHeight;
      var dist = Math.min(1, Math.hypot(dx, dy) * 3);
      avatarEl.style.transform = "rotate(" + (dx * 10 * dist).toFixed(1) + "deg) translate(" +
        (dx * 8 * dist).toFixed(1) + "px," + (dy * 8 * dist).toFixed(1) + "px)";
      clearTimeout(avatarEl._tiltT);
      avatarEl._tiltT = setTimeout(function () { avatarEl.style.transform = ""; }, 600);
    });
  });

  /* Rapid triple-click = excitement. */
  var clicks = [];
  buddy.addEventListener("click", function () {
    poke();
    var now = Date.now();
    clicks = clicks.filter(function (t) { return now - t < 900; });
    clicks.push(now);
    if (clicks.length >= 3) { clicks = []; doAction("act-spin"); say("Hehe! ✨ Mazaa aa gaya!"); }
  });

  /* Drop bounce after a drag (handled inside endDrag). */

  /* Wake on hover. */
  buddy.addEventListener("pointerenter", function () { poke(); });

  /* Right-click menu: hide for an hour, reset position. */
  var menu = null;
  buddy.addEventListener("contextmenu", function (e) {
    e.preventDefault(); poke();
    if (menu) menu.remove();
    menu = document.createElement("div");
    menu.className = "buddy-menu";
    menu.innerHTML = "<button data-a='chat'>💬 Chat kholo</button>" +
      "<button data-a='hide'>😴 1 ghante chhup jao</button>" +
      "<button data-a='reset'>📍 Wapas corner me</button>";
    buddy.appendChild(menu);
    menu.addEventListener("click", function (ev) {
      var a = ev.target.dataset && ev.target.dataset.a;
      menu.remove(); menu = null;
      if (a === "chat") openChat();
      else if (a === "hide") {
        buddy.style.display = "none";
        sayEl.hidden = true;
        setTimeout(function () {
          buddy.style.display = "";
          doAction("act-hop"); say("Main wapas aa gaya! 🎉");
        }, 3600000);
      } else if (a === "reset") {
        try { localStorage.removeItem(POS_KEY); } catch (err) {}
        buddy.style.left = ""; buddy.style.top = "";
        buddy.style.right = "22px"; buddy.style.bottom = "22px";
        doAction("act-hop");
      }
    });
    setTimeout(function () {
      document.addEventListener("click", function h(ev) {
        if (menu && !menu.contains(ev.target)) { menu.remove(); menu = null; }
        document.removeEventListener("click", h);
      });
    }, 0);
  });

  if (!reduceMotion) { bodyEl.classList.add("breathe"); scheduleIdle(); }

  loadPos();
})();
