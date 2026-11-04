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
    var input = document.getElementById("input");
    if (input) input.focus();
  }
  function closeChat() {
    if (card.hidden) return;
    card.classList.remove("open");
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
        buddy.style.left = Math.max(0, Math.min(window.innerWidth - 76, p.x)) + "px";
        buddy.style.top = Math.max(0, Math.min(window.innerHeight - 76, p.y)) + "px";
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
      buddy.style.left = Math.max(0, Math.min(window.innerWidth - 76, drag.ox + dx)) + "px";
      buddy.style.top = Math.max(0, Math.min(window.innerHeight - 76, drag.oy + dy)) + "px";
    }
  });
  function endDrag(e) {
    if (!drag) return;
    var wasDrag = drag.moved;
    drag = null;
    if (wasDrag) { savePos(); e.preventDefault(); e.stopPropagation(); }
    else toggleChat();
  }
  buddy.addEventListener("pointerup", endDrag);
  buddy.addEventListener("pointercancel", function () { drag = null; });
  buddy.addEventListener("keydown", function (e) {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggleChat(); }
    if (e.key === "Escape") closeChat();
  });

  loadPos();
})();
