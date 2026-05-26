(function () {

  const $ = (sel) => document.querySelector(sel);



  const APP_USER = window.APP_USER || { role: "user" };

  const isAdmin = APP_USER.role === "admin";



  let uploadedVideoPath = "";

  let sessionStart = Date.now();

  let runningSince = null;

  let lastFrameIdx = 0;

  let lastFrameTime = 0;

  let fpsSmooth = 0;



  const els = {

    statusPill: $("#statusPill"),

    statRunning: $("#statRunning"),

    statAlerts: $("#statAlerts"),

    statFrames: $("#statFrames"),

    statDetector: $("#statDetector"),

    statFps: $("#statFps"),

    sourceLabel: $("#sourceLabel"),

    lastMessage: $("#lastMessage"),

    fallOverlay: $("#fallOverlay"),

    videoWrap: $("#videoWrap"),

    videoIdle: $("#videoIdle"),

    scanLine: $("#scanLine"),

    btnStartCam: $("#btnStartCam"),

    btnStartImou: $("#btnStartImou"),

    btnTestRtsp: $("#btnTestRtsp"),

    btnStartVideo: $("#btnStartVideo"),

    btnStop: $("#btnStop"),

    btnTestEmail: $("#btnTestEmail"),

    btnTestIot: $("#btnTestIot"),

    btnRefreshFalls: $("#btnRefreshFalls"),

    btnLogout: $("#btnLogout"),

    btnTheme: $("#btnTheme"),

    btnFullscreen: $("#btnFullscreen"),

    fileInput: $("#fileInput"),

    uploadName: $("#uploadName"),

    configForm: $("#configForm"),

    emailStatus: $("#emailStatus"),

    fallsGallery: $("#fallsGallery"),

    toast: $("#toast"),

    toastMsg: $("#toastMsg"),

    toastIcon: $("#toastIcon"),

    toastClose: $("#toastClose"),

    liveClock: $("#liveClock"),

    sessionUptime: $("#sessionUptime"),

    lightbox: $("#lightbox"),

    lightboxImg: $("#lightboxImg"),

    lightboxCaption: $("#lightboxCaption"),

    lightboxClose: $("#lightboxClose"),

    imouIp: $("#imouIp"),

    imouUser: $("#imouUser"),

    imouPassword: $("#imouPassword"),

    imouSubtype: $("#imouSubtype"),

    imouRtspUrl: $("#imouRtspUrl"),

    imouPanel: $("#imouPanel"),

  };



  const TOAST_ICONS = {

    ok: '<svg viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2"><path d="M20 6 9 17l-5-5"/></svg>',

    err: '<svg viewBox="0 0 24 24" fill="none" stroke="#dc2626" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>',

    "": '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>',

  };



  function showToast(message, type) {

    if (els.toastMsg) els.toastMsg.textContent = message;

    else if (els.toast) els.toast.textContent = message;

    if (els.toastIcon) els.toastIcon.innerHTML = TOAST_ICONS[type || ""] || TOAST_ICONS[""];

    els.toast.className = "toast " + (type || "");

    clearTimeout(showToast._t);

    showToast._t = setTimeout(() => els.toast.classList.add("hidden"), 4500);

  }



  function initTheme() {

    const saved = localStorage.getItem("fallguard-theme");

    if (saved === "light") document.documentElement.setAttribute("data-theme", "light");

    if (els.btnTheme) {

      els.btnTheme.addEventListener("click", () => {

        const light = document.documentElement.getAttribute("data-theme") === "light";

        if (light) {

          document.documentElement.removeAttribute("data-theme");

          localStorage.setItem("fallguard-theme", "purple");

        } else {

          document.documentElement.setAttribute("data-theme", "light");

          localStorage.setItem("fallguard-theme", "light");

        }

      });

    }

  }



  function checkAccessDenied() {

    const params = new URLSearchParams(window.location.search);

    if (params.get("access") === "denied") {

      showToast("Bạn không có quyền truy cập trang đó.", "err");

      window.history.replaceState({}, "", window.location.pathname);

    }

  }



  function pad2(n) {

    return String(n).padStart(2, "0");

  }



  function updateClock() {

    const now = new Date();

    if (els.liveClock) {

      els.liveClock.textContent = `${pad2(now.getHours())}:${pad2(now.getMinutes())}:${pad2(now.getSeconds())}`;

    }

    if (els.sessionUptime) {

      const sec = Math.floor((Date.now() - sessionStart) / 1000);

      const m = Math.floor(sec / 60);

      const s = sec % 60;

      els.sessionUptime.textContent = `Phiên: ${pad2(m)}:${pad2(s)}`;

    }

  }



  function updateFps(frameIdx, running) {

    if (!els.statFps) return;

    if (!running) {

      els.statFps.innerHTML = '— <span class="stat-unit">fps</span>';

      lastFrameIdx = 0;

      lastFrameTime = 0;

      fpsSmooth = 0;

      return;

    }

    const now = performance.now();

    if (lastFrameTime && frameIdx > lastFrameIdx) {

      const delta = frameIdx - lastFrameIdx;

      const dt = (now - lastFrameTime) / 1000;

      if (dt > 0) {

        const instant = delta / dt;

        fpsSmooth = fpsSmooth ? fpsSmooth * 0.7 + instant * 0.3 : instant;

        els.statFps.innerHTML = `${fpsSmooth.toFixed(1)} <span class="stat-unit">fps</span>`;

      }

    }

    lastFrameIdx = frameIdx;

    lastFrameTime = now;

  }



  function openLightbox(src, caption) {

    if (!els.lightbox) return;

    els.lightboxImg.src = src;

    els.lightboxCaption.textContent = caption || "";

    els.lightbox.classList.remove("hidden");

    document.body.style.overflow = "hidden";

  }



  function closeLightbox() {

    if (!els.lightbox) return;

    els.lightbox.classList.add("hidden");

    els.lightboxImg.src = "";

    document.body.style.overflow = "";

  }



  async function api(url, options) {

    const res = await fetch(url, options);

    const data = await res.json().catch(() => ({}));

    if (res.status === 401) {

      window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname);

      throw new Error("Phiên đăng nhập hết hạn.");

    }

    if (!res.ok) {

      throw new Error(data.error || "Yêu cầu thất bại.");

    }

    return data;

  }



  function bindRangeOutputs() {

    if (!els.configForm) return;

    els.configForm.querySelectorAll('input[type="range"]').forEach((input) => {

      const out = els.configForm.querySelector(`output[data-for="${input.name}"]`);

      const sync = () => {

        if (out) out.textContent = input.value;

      };

      input.addEventListener("input", sync);

      sync();

    });

  }



  function readConfigPayload() {

    const fd = new FormData(els.configForm);

    return {

      fall_aspect_threshold: parseFloat(fd.get("fall_aspect_threshold")),

      fall_drop_threshold: parseFloat(fd.get("fall_drop_threshold")),

      pose_angle_threshold: parseFloat(fd.get("pose_angle_threshold")),

      horizontal_only_threshold: parseFloat(fd.get("horizontal_only_threshold")),

      hog_min_score: parseFloat(fd.get("hog_min_score")),

      cooldown_sec: parseFloat(fd.get("cooldown_sec")),

      no_email: fd.get("no_email") === "on",

      send_immediate_image: fd.get("send_immediate_image") === "on",

    };

  }



  function applyConfigToForm(cfg) {

    if (!cfg || !els.configForm) return;

    const map = [

      "fall_aspect_threshold",

      "fall_drop_threshold",

      "pose_angle_threshold",

      "horizontal_only_threshold",

      "hog_min_score",

      "cooldown_sec",

    ];

    map.forEach((key) => {

      const input = els.configForm.querySelector(`[name="${key}"]`);

      if (input && cfg[key] !== undefined) {

        input.value = cfg[key];

        const out = els.configForm.querySelector(`output[data-for="${key}"]`);

        if (out) out.textContent = cfg[key];

      }

    });

    const noEmail = els.configForm.querySelector('[name="no_email"]');

    const sendImg = els.configForm.querySelector('[name="send_immediate_image"]');

    if (noEmail) noEmail.checked = !!cfg.no_email;

    if (sendImg) sendImg.checked = cfg.send_immediate_image !== false;

    if (els.emailStatus) {

      if (cfg.smtp_configured) {

        els.emailStatus.textContent = "SMTP đã cấu hình — sẵn sàng gửi cảnh báo.";

      } else {

        els.emailStatus.textContent = "Chưa cấu hình SMTP trong .env.";

      }

    }

  }



  function updateUI(status) {

    const running = !!status.running;

    const warning = !!status.warning_active;



    if (running && !runningSince) runningSince = Date.now();

    if (!running) runningSince = null;



    if (els.statRunning) els.statRunning.textContent = running ? "Đang chạy" : "Dừng";

    if (els.statAlerts) els.statAlerts.textContent = String(status.alert_count || 0);

    if (els.statFrames) els.statFrames.textContent = String(status.frame_idx || 0);

    if (els.statDetector) els.statDetector.textContent = status.detector_mode || "—";

    els.sourceLabel.textContent = status.source_label || "Chưa chọn nguồn";

    els.lastMessage.textContent = status.last_message || "";



    updateFps(status.frame_idx || 0, running);



    els.btnStartCam.disabled = running;

    if (els.btnStartImou) els.btnStartImou.disabled = running;

    els.btnStartVideo.disabled = running || !uploadedVideoPath;

    els.btnStop.disabled = !running;



    if (els.videoWrap) {

      els.videoWrap.classList.toggle("is-running", running);

    }

    if (els.scanLine) {

      els.scanLine.classList.toggle("hidden", !running);

    }



    els.statusPill.className =

      "pill " + (warning ? "pill-fall" : running ? "pill-running" : "pill-idle");

    els.statusPill.innerHTML =

      '<span class="pill-dot"></span> ' +

      (warning ? "CẢNH BÁO TÉ NGÃ" : running ? "Đang giám sát" : "Chưa chạy");



    if (warning) {

      els.fallOverlay.classList.remove("hidden");

      els.videoWrap.classList.add("fall-active");

    } else {

      els.fallOverlay.classList.add("hidden");

      els.videoWrap.classList.remove("fall-active");

    }



    if (isAdmin && status.config) {

      applyConfigToForm(status.config);

    }

  }



  async function pollStatus() {

    try {

      const status = await api("/api/status");

      updateUI(status);

    } catch (_) {

      /* ignore */

    }

  }



  async function loadConfig() {

    if (!isAdmin) return;

    try {

      const cfg = await api("/api/config");

      applyConfigToForm(cfg);

    } catch (err) {

      showToast(err.message, "err");

    }

  }



  function showFallsSkeleton() {

    els.fallsGallery.innerHTML =

      '<div class="skeleton-gallery">' +

      Array(4)

        .fill('<div class="skeleton-card"></div>')

        .join("") +

      "</div>";

  }



  async function loadFalls() {

    showFallsSkeleton();

    try {

      const data = await api("/api/falls");

      const items = data.items || [];

      if (!items.length) {

        els.fallsGallery.innerHTML = '<p class="empty-state">Chưa có sự kiện nào được lưu.</p>';

        return;

      }

      els.fallsGallery.innerHTML = items

        .map(

          (it) => `

        <article class="fall-item" data-src="${it.image_url}" data-caption="${(it.time || it.id || "").replace(/"/g, "&quot;")}">

          <img src="${it.image_url}" alt="Sự kiện té ngã" loading="lazy" />

          <div class="fall-item-meta">

            <time>${it.time || it.id}</time>

            ${it.video_url ? `<a href="${it.video_url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">Xem clip</a>` : ""}

          </div>

        </article>`

        )

        .join("");



      els.fallsGallery.querySelectorAll(".fall-item").forEach((card) => {

        card.addEventListener("click", () => {

          openLightbox(card.dataset.src, card.dataset.caption);

        });

      });

    } catch (err) {

      els.fallsGallery.innerHTML = '<p class="empty-state">Không tải được lịch sử.</p>';

      showToast(err.message, "err");

    }

  }



  if (els.configForm && isAdmin) {

    els.configForm.addEventListener("submit", async (e) => {

      e.preventDefault();

      try {

        const data = await api("/api/config", {

          method: "POST",

          headers: { "Content-Type": "application/json" },

          body: JSON.stringify(readConfigPayload()),

        });

        applyConfigToForm(data.config);

        showToast("Đã lưu cấu hình.", "ok");

      } catch (err) {

        showToast(err.message, "err");

      }

    });

  }



  function readImouPayload() {
    return {
      mode: "imou",
      ip: (els.imouIp && els.imouIp.value.trim()) || "",
      username: (els.imouUser && els.imouUser.value.trim()) || "admin",
      password: (els.imouPassword && els.imouPassword.value) || "",
      subtype: parseInt((els.imouSubtype && els.imouSubtype.value) || "1", 10),
      rtsp_url: (els.imouRtspUrl && els.imouRtspUrl.value.trim()) || "",
    };
  }

  async function loadImouDefaults() {
    try {
      const d = await api("/api/camera/imou-defaults");
      if (els.imouIp && d.ip) els.imouIp.value = d.ip;
      if (els.imouUser && d.username) els.imouUser.value = d.username;
      if (els.imouSubtype) els.imouSubtype.value = String(d.subtype ?? 1);
      if (els.imouRtspUrl && d.rtsp_url) els.imouRtspUrl.value = d.rtsp_url;
      if (els.imouPanel && (d.ip || d.rtsp_url)) els.imouPanel.open = true;
    } catch (_) {
      /* optional */
    }
  }

  els.btnStartCam.addEventListener("click", async () => {

    try {

      await api("/api/start", {

        method: "POST",

        headers: { "Content-Type": "application/json" },

        body: JSON.stringify({ mode: "camera", camera: 0 }),

      });

      showToast("Đã bắt đầu giám sát webcam.", "ok");

      pollStatus();

    } catch (err) {

      showToast(err.message, "err");

    }

  });

  if (els.btnStartImou) {
    els.btnStartImou.addEventListener("click", async () => {
      const payload = readImouPayload();
      if (!payload.rtsp_url && !payload.ip) {
        showToast("Nhập IP camera Imou hoặc URL RTSP.", "err");
        return;
      }
      if (!payload.rtsp_url && !payload.password) {
        showToast("Nhập mật khẩu RTSP (mật khẩu thiết bị trong app Imou).", "err");
        return;
      }
      els.btnStartImou.disabled = true;
      try {
        await api("/api/start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        showToast("Đã kết nối camera Imou — đang giám sát.", "ok");
        pollStatus();
      } catch (err) {
        showToast(err.message, "err");
      } finally {
        els.btnStartImou.disabled = false;
        pollStatus();
      }
    });
  }

  if (els.btnTestRtsp) {
    els.btnTestRtsp.addEventListener("click", () => {
      const p = readImouPayload();
      let url = p.rtsp_url;
      if (!url && p.ip && p.password) {
        const user = encodeURIComponent(p.username || "admin");
        const pass = encodeURIComponent(p.password);
        url = `rtsp://${user}:${pass}@${p.ip}:554/cam/realmonitor?channel=1&subtype=${p.subtype}`;
      }
      if (!url) {
        showToast("Điền IP + mật khẩu hoặc URL RTSP để thử.", "err");
        return;
      }
      showToast("Mở VLC → Media → Open Network Stream → dán URL RTSP.", "ok");
      if (navigator.clipboard) {
        navigator.clipboard.writeText(url).catch(() => {});
      }
    });
  }

  els.btnStartVideo.addEventListener("click", async () => {

    if (!uploadedVideoPath) return;

    try {

      await api("/api/start", {

        method: "POST",

        headers: { "Content-Type": "application/json" },

        body: JSON.stringify({ mode: "video", video_path: uploadedVideoPath }),

      });

      showToast("Đang phân tích video…", "ok");

      pollStatus();

    } catch (err) {

      showToast(err.message, "err");

    }

  });



  els.btnStop.addEventListener("click", async () => {

    try {

      await api("/api/stop", { method: "POST" });

      showToast("Đã dừng — đang gửi cảnh báo nếu có sự kiện.", "ok");

      loadFalls();

      pollStatus();

    } catch (err) {

      showToast(err.message, "err");

    }

  });



  if (els.btnTestEmail) {

    els.btnTestEmail.addEventListener("click", async () => {

      els.btnTestEmail.disabled = true;

      try {

        const data = await api("/api/test-email", { method: "POST" });

        showToast(data.message || "Gửi email thành công.", "ok");

      } catch (err) {

        showToast(err.message, "err");

      } finally {

        els.btnTestEmail.disabled = false;

      }

    });

  }



  if (els.btnTestIot) {

    els.btnTestIot.addEventListener("click", async () => {

      els.btnTestIot.disabled = true;

      try {

        const data = await api("/api/test-iot", { method: "POST" });

        showToast(data.message || "ESP32 đã nhận tín hiệu.", "ok");

      } catch (err) {

        showToast(err.message, "err");

      } finally {

        els.btnTestIot.disabled = false;

      }

    });

  }



  els.btnLogout.addEventListener("click", async () => {

    try {

      await api("/api/logout", { method: "POST" });

    } catch (_) {

      /* ignore */

    }

    window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname);

  });



  els.btnRefreshFalls.addEventListener("click", loadFalls);



  if (els.btnFullscreen && els.videoWrap) {

    els.btnFullscreen.addEventListener("click", async () => {

      try {

        if (!document.fullscreenElement) {

          await els.videoWrap.requestFullscreen();

        } else {

          await document.exitFullscreen();

        }

      } catch (_) {

        showToast("Trình duyệt không hỗ trợ toàn màn hình.", "err");

      }

    });

  }



  if (els.toastClose) {

    els.toastClose.addEventListener("click", () => els.toast.classList.add("hidden"));

  }



  if (els.lightboxClose) {

    els.lightboxClose.addEventListener("click", closeLightbox);

  }

  if (els.lightbox) {

    els.lightbox.addEventListener("click", (e) => {

      if (e.target === els.lightbox) closeLightbox();

    });

  }

  document.addEventListener("keydown", (e) => {

    if (e.key === "Escape") closeLightbox();

  });



  els.fileInput.addEventListener("change", async () => {

    const file = els.fileInput.files[0];

    if (!file) return;

    const form = new FormData();

    form.append("video", file);

    els.uploadName.textContent = "Đang tải lên…";

    try {

      const res = await fetch("/api/upload", { method: "POST", body: form });

      const data = await res.json();

      if (res.status === 401) {

        window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname);

        return;

      }

      if (!res.ok) throw new Error(data.error || "Upload thất bại.");

      uploadedVideoPath = data.video_path;

      els.uploadName.textContent = "Đã tải: " + data.filename;

      els.btnStartVideo.disabled = false;

      showToast("Tải video thành công.", "ok");

    } catch (err) {

      els.uploadName.textContent = "";

      showToast(err.message, "err");

    }

    els.fileInput.value = "";

  });



  initTheme();

  checkAccessDenied();

  bindRangeOutputs();

  loadImouDefaults();

  if (isAdmin) loadConfig();

  loadFalls();

  pollStatus();

  setInterval(pollStatus, 800);

  setInterval(updateClock, 1000);

  updateClock();

})();


