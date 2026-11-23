/**
 * Telegram Mini App - Multi-Stop Driving Route Navigation (A -> B -> C -> ...)
 */

// Translations dictionary for Mini App interface
const I18N = {
  ru: {
    badgeTitle: "Маршрут поездки",
    pointsSuffix: "точек",
    pointsSuffix2: "точки",
    pointsSuffix1: "точка",
    tripTime: "Общее время",
    distance: "Вся дистанция",
    legsTitle: "Отрезки маршрута:",
    legsHint: "нажмите для фокуса",
    navigators: "Поехать по навигатору (все точки):",
    btnRetry: "Повторить",
    errorTitle: "Не удалось построить маршрут",
    errorNotFound: "Маршрут не найден или срок его действия истёк",
    errorNoParams: "Параметры маршрута не указаны",
    minSuffix: "мин",
    hoursSuffix: "ч",
    kmSuffix: "км",
    toggleLangTo: "UZ",
    popupStart: "Точка A (Старт)",
    popupPoint: "Точка",
    showAllRoute: "Показать весь маршрут",
  },
  uz: {
    badgeTitle: "Safar marshruti",
    pointsSuffix: "ta nuqta",
    pointsSuffix2: "ta nuqta",
    pointsSuffix1: "ta nuqta",
    tripTime: "Umumiy vaqt",
    distance: "Umumiy masofa",
    legsTitle: "Yo'l qismlari:",
    legsHint: "fokus uchun bosing",
    navigators: "Navigatorda ochish (barcha nuqtalar):",
    btnRetry: "Qayta urinish",
    errorTitle: "Marshrutni yuklab bo'lmadi",
    errorNotFound: "Marshrut topilmadi yoki muddati tugagan",
    errorNoParams: "Marshrut parametrlari kiritilmagan",
    minSuffix: "daq",
    hoursSuffix: "s",
    kmSuffix: "km",
    toggleLangTo: "RU",
    popupStart: "A Nuqta (Boshlanish)",
    popupPoint: "Nuqta",
    showAllRoute: "Barcha marshrutni ko'rish",
  },
};

// Vibrant neon color palette for distinct route legs
const LEG_COLORS = [
  { stroke: "#00E5FF", glow: "rgba(0, 229, 255, 0.45)", text: "text-cyan-400", bg: "bg-cyan-500/15", border: "border-cyan-500/30" },
  { stroke: "#A855F7", glow: "rgba(168, 85, 247, 0.45)", text: "text-purple-400", bg: "bg-purple-500/15", border: "border-purple-500/30" },
  { stroke: "#10B981", glow: "rgba(16, 185, 129, 0.45)", text: "text-emerald-400", bg: "bg-emerald-500/15", border: "border-emerald-500/30" },
  { stroke: "#F59E0B", glow: "rgba(245, 158, 11, 0.45)", text: "text-amber-400", bg: "bg-amber-500/15", border: "border-amber-500/30" },
  { stroke: "#EC4899", glow: "rgba(236, 72, 153, 0.45)", text: "text-pink-400", bg: "bg-pink-500/15", border: "border-pink-500/30" },
  { stroke: "#3B82F6", glow: "rgba(59, 130, 246, 0.45)", text: "text-blue-400", bg: "bg-blue-500/15", border: "border-blue-500/30" },
  { stroke: "#14B8A6", glow: "rgba(20, 184, 166, 0.45)", text: "text-teal-400", bg: "bg-teal-500/15", border: "border-teal-500/30" },
  { stroke: "#F43F5E", glow: "rgba(244, 63, 94, 0.45)", text: "text-rose-400", bg: "bg-rose-500/15", border: "border-rose-500/30" },
];

// Global State
let currentLang = "ru";
let map = null;
let allRoutesGroup = null;
let markersGroup = null;
let legLayerGroups = [];
let currentRouteData = null;

// Initialize Telegram WebApp SDK
const tg = window.Telegram?.WebApp;
if (tg) {
  try {
    tg.ready();
    tg.expand();
    if (tg.setHeaderColor) tg.setHeaderColor("#0f172a");
    if (tg.setBackgroundColor) tg.setBackgroundColor("#0b1120");
  } catch (err) {
    console.warn("Telegram WebApp API error:", err);
  }
}

/**
 * Format duration into localized string (e.g., '1 ч 20 мин' or '35 мин')
 */
function formatDuration(durationMinutes, lang) {
  const total = Math.max(1, Math.round(durationMinutes));
  const h = Math.floor(total / 60);
  const m = total % 60;
  const t = I18N[lang] || I18N.ru;

  if (h > 0 && m > 0) {
    return `${h} ${t.hoursSuffix} ${m} ${t.minSuffix}`;
  } else if (h > 0) {
    return `${h} ${t.hoursSuffix}`;
  }
  return `${m} ${t.minSuffix}`;
}

/**
 * Trigger light haptic vibration in Telegram
 */
function hapticLight() {
  if (tg?.HapticFeedback) {
    try {
      tg.HapticFeedback.impactOccurred("light");
    } catch (_) {}
  }
}

/**
 * Open external link via Telegram WebApp or browser window fallback
 */
function openExternal(url) {
  hapticLight();
  if (tg && typeof tg.openLink === "function") {
    tg.openLink(url);
  } else {
    window.open(url, "_blank");
  }
}

/**
 * Apply interface text strings for the given language
 */
function setLanguage(lang) {
  currentLang = lang === "uz" ? "uz" : "ru";
  const t = I18N[currentLang];

  document.getElementById("badge-title").textContent = t.badgeTitle;
  document.getElementById("lbl-trip-time").textContent = t.tripTime;
  document.getElementById("lbl-distance").textContent = t.distance;
  document.getElementById("lbl-legs-title").textContent = t.legsTitle;
  document.getElementById("lbl-legs-hint").textContent = t.legsHint;
  document.getElementById("lbl-navigators").textContent = t.navigators;
  document.getElementById("btn-retry").textContent = t.btnRetry;
  document.getElementById("lang-label").textContent = t.toggleLangTo;

  if (currentRouteData) {
    updateRouteUI(currentRouteData);
  }
}

/**
 * Initialize Leaflet interactive map with OpenStreetMap + Dark CSS filter
 */
function initMap() {
  map = L.map("map", {
    center: [41.2995, 69.2401],
    zoom: 13,
    zoomControl: false,
    attributionControl: false,
  });

  // OpenStreetMap with CSS dark filter (.map-tiles-dark)
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    className: "map-tiles-dark",
  }).addTo(map);

  allRoutesGroup = L.featureGroup().addTo(map);
  markersGroup = L.featureGroup().addTo(map);
}

/**
 * Center map view to fit all route bounds
 */
function centerFullRoute() {
  if (!allRoutesGroup || allRoutesGroup.getLayers().length === 0) return;
  hapticLight();
  map.fitBounds(allRoutesGroup.getBounds(), {
    paddingTopLeft: [30, 70],
    paddingBottomRight: [30, 270],
    maxZoom: 16,
    animate: true,
    duration: 0.8,
  });
}

/**
 * Focus map view on a specific route leg
 */
function focusLeg(index) {
  const legGroup = legLayerGroups[index];
  if (!legGroup) return;
  hapticLight();
  map.fitBounds(legGroup.getBounds(), {
    paddingTopLeft: [40, 80],
    paddingBottomRight: [40, 260],
    maxZoom: 16,
    animate: true,
    duration: 0.6,
  });
}

/**
 * Render multi-stop route geometry and custom markers
 */
function renderMultiRoute(data) {
  allRoutesGroup.clearLayers();
  markersGroup.clearLayers();
  legLayerGroups = [];

  const points = data.points || [];
  const legs = data.legs || [];
  const t = I18N[currentLang];

  // Render each leg with distinct neon colors
  legs.forEach((leg, index) => {
    const colorObj = LEG_COLORS[index % LEG_COLORS.length];
    const legCoords = leg.coordinates || [];

    const legGroup = L.featureGroup();

    // Glow underlay polyline
    const glowLine = L.polyline(legCoords, {
      color: colorObj.stroke,
      weight: 8,
      opacity: 0.45,
      className: "neon-route-casing",
    });

    // Core vivid line
    const coreLine = L.polyline(legCoords, {
      color: colorObj.stroke,
      weight: 4.5,
      opacity: 0.95,
      className: "neon-route-path",
    });

    legGroup.addLayer(glowLine);
    legGroup.addLayer(coreLine);

    legGroup.addTo(allRoutesGroup);
    legLayerGroups.push(legGroup);
  });

  let markerMap = {};

  // Render Waypoint Markers (A, B, C, D...)
  points.forEach((pt, index) => {
    const isStart = index === 0;
    const isEnd = index === points.length - 1 && points.length > 1;

    let pinClass = "pin-waypoint";
    if (isStart) pinClass = "pin-origin";
    else if (isEnd) pinClass = "pin-dest";

    const icon = L.divIcon({
      className: "custom-pin",
      html: `<div class="${pinClass}">${pt.label}</div>`,
      iconSize: [32, 32],
      iconAnchor: [16, 16],
    });

    let popupTitle = isStart ? t.popupStart : `${t.popupPoint} ${pt.label}`;
    if (pt.custom_name) {
      popupTitle = `${pt.custom_name} (${pt.label})`;
    }
    const displayAddr = pt.address || (pt.name !== pt.custom_name ? pt.name : "") || `${pt.lat.toFixed(5)}, ${pt.lon.toFixed(5)}`;
    const marker = L.marker([pt.lat, pt.lon], { icon })
      .bindPopup(`<b>${popupTitle}</b><br><span class="text-xs text-slate-300">${displayAddr}</span>`);

    markersGroup.addLayer(marker);
    markerMap[pt.label] = marker;
  });

  centerFullRoute();
}

/**
 * Populate Bottom Sheet UI with multi-stop summary and legs list
 */
function updateRouteUI(data) {
  const t = I18N[currentLang];
  const points = data.points || [];
  const legs = data.legs || [];

  // Update Points Badge in header
  const badgeEl = document.getElementById("badge-points-count");
  if (points.length > 0) {
    badgeEl.textContent = `${points.length} ${t.pointsSuffix}`;
    badgeEl.classList.remove("hidden");
  }

  // Total Duration & Distance
  const durationEl = document.getElementById("route-duration");
  const distanceEl = document.getElementById("route-distance");
  durationEl.innerHTML = formatDuration(data.total_duration_min, currentLang);
  distanceEl.innerHTML = `${data.total_distance_km.toFixed(1)} <span class="text-xs font-normal text-slate-400">${t.kmSuffix}</span>`;

  // Populate Legs Container with human-readable addresses
  const legsContainer = document.getElementById("legs-container");
  legsContainer.innerHTML = "";

  // Start point summary card
  if (points.length > 0) {
    const startPt = points[0];
    const startAddr = startPt.address || startPt.name || t.popupStart;
    const startCard = document.createElement("div");
    startCard.className = "flex items-center justify-between p-2 rounded-xl bg-slate-800/40 border border-emerald-500/25 text-xs mb-1";
    startCard.innerHTML = `
      <div class="flex items-center gap-2 min-w-0">
        <span class="px-2 py-0.5 rounded-lg text-[10px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shrink-0">
          A (Старт)
        </span>
        <span class="truncate text-slate-300 text-[11px] font-medium">${startAddr}</span>
      </div>
    `;
    startCard.onclick = () => {
      hapticLight();
      map.setView([startPt.lat, startPt.lon], 16, { animate: true });
    };
    legsContainer.appendChild(startCard);
  }

  legs.forEach((leg, index) => {
    const colorObj = LEG_COLORS[index % LEG_COLORS.length];
    const legRow = document.createElement("div");
    legRow.className = `leg-item flex items-center justify-between p-2 rounded-xl bg-slate-800/70 hover:bg-slate-700/80 border border-white/5 cursor-pointer text-xs transition`;

    const legDurationStr = formatDuration(leg.duration_min, currentLang);
    const toPt = points[index + 1] || {};
    const customName = leg.to_custom_name || toPt.custom_name;
    const targetAddr = leg.to_address || `${t.popupPoint} ${leg.to_label}`;

    let titleHtml = "";
    if (customName) {
      titleHtml = `
        <span class="text-slate-100 text-xs font-semibold block leading-tight truncate">
          ${customName}
        </span>
        <span class="text-slate-400 text-[11px] block leading-tight truncate mt-0.5">
          ${targetAddr}
        </span>
      `;
    } else {
      titleHtml = `
        <span class="text-slate-200 text-xs font-medium block leading-tight line-clamp-2">
          ${targetAddr}
        </span>
      `;
    }

    legRow.innerHTML = `
      <div class="flex items-start gap-2 min-w-0 pr-2">
        <span class="px-2 py-0.5 rounded-lg text-[11px] font-bold ${colorObj.bg} ${colorObj.text} border ${colorObj.border} shrink-0 mt-0.5">
          ${leg.from_label} → ${leg.to_label}
        </span>
        <div class="min-w-0">
          ${titleHtml}
        </div>
      </div>
      <div class="text-right shrink-0 pl-1">
        <span class="font-semibold text-slate-100 text-xs block">${leg.distance_km.toFixed(1)} ${t.kmSuffix}</span>
        <span class="text-slate-400 text-[10px] block">${legDurationStr}</span>
      </div>
    `;

    legRow.addEventListener("click", () => {
      focusLeg(index);
    });

    legsContainer.appendChild(legRow);
  });

  // Setup Navigator URLs for ALL points in the chain
  if (points.length >= 2) {
    // 1. Yandex Maps: rtext=latA,lonA~latB,lonB~latC,lonC...&rtt=auto
    const yandexPoints = points.map(p => `${p.lat.toFixed(6)},${p.lon.toFixed(6)}`).join("~");
    const yandexUrl = `https://yandex.uz/maps/?rtext=${yandexPoints}&rtt=auto`;

    // 2. 2GIS: points=lonA%2ClatA%7ClonB%2ClatB%7ClonC%2ClatC...
    const dgisPoints = points.map(p => `${p.lon.toFixed(6)}%2C${p.lat.toFixed(6)}`).join("%7C");
    const dgisUrl = `https://2gis.uz/directions/points/${dgisPoints}`;

    // 3. Google Maps:
    // Single destination: origin=...&destination=...&travelmode=driving
    // Multi-stop: origin=latA,lonA&destination=latLast,lonLast&waypoints=latB,lonB|latC,lonC...
    const originPt = points[0];
    const destPt = points[points.length - 1];
    let googleUrl = `https://www.google.com/maps/dir/?api=1&origin=${originPt.lat.toFixed(6)},${originPt.lon.toFixed(6)}&destination=${destPt.lat.toFixed(6)},${destPt.lon.toFixed(6)}&travelmode=driving`;

    if (points.length > 2) {
      const intermediateWaypoints = points.slice(1, -1).map(p => `${p.lat.toFixed(6)},${p.lon.toFixed(6)}`).join("|");
      googleUrl += `&waypoints=${encodeURIComponent(intermediateWaypoints)}`;
    }

    document.getElementById("btn-nav-yandex").onclick = () => openExternal(yandexUrl);
    document.getElementById("btn-nav-2gis").onclick = () => openExternal(dgisUrl);
    document.getElementById("btn-nav-google").onclick = () => openExternal(googleUrl);
  }
}

/**
 * Show error card
 */
function showError(message) {
  document.getElementById("route-loading").classList.add("hidden");
  document.getElementById("route-content").classList.add("hidden");
  const errBox = document.getElementById("route-error");
  errBox.classList.remove("hidden");
  document.getElementById("error-message").textContent = message;
}

/**
 * Fetch route data by route_id
 */
async function loadRouteById(routeId) {
  const loadingEl = document.getElementById("route-loading");
  const contentEl = document.getElementById("route-content");
  const errorEl = document.getElementById("route-error");

  loadingEl.classList.remove("hidden");
  contentEl.classList.add("hidden");
  errorEl.classList.add("hidden");

  try {
    const response = await fetch(`/api/route/${encodeURIComponent(routeId)}`);
    const data = await response.json();

    if (!response.ok || data.status !== "ok") {
      const msg = data.detail || data.message || I18N[currentLang].errorNotFound;
      showError(msg);
      return;
    }

    currentRouteData = data;
    renderMultiRoute(data);
    updateRouteUI(data);

    loadingEl.classList.add("hidden");
    contentEl.classList.remove("hidden");
  } catch (err) {
    console.error("Multi-route fetch failure:", err);
    showError(I18N[currentLang].errorTitle);
  }
}

/**
 * Backwards compatibility: fetch route by single dest coordinates
 */
async function loadLegacyRoute(destLat, destLon) {
  const loadingEl = document.getElementById("route-loading");
  const contentEl = document.getElementById("route-content");
  const errorEl = document.getElementById("route-error");

  loadingEl.classList.remove("hidden");
  contentEl.classList.add("hidden");
  errorEl.classList.add("hidden");

  try {
    const response = await fetch(`/api/route?dest_lat=${destLat}&dest_lon=${destLon}`);
    const data = await response.json();

    if (!response.ok || data.status !== "ok") {
      const msg = data.detail || data.message || I18N[currentLang].errorTitle;
      showError(msg);
      return;
    }

    // Adapt legacy structure to multi-stop format
    const adaptedData = {
      points: [
        { label: "A", name: data.origin.name || "Точка А", lat: data.origin.lat, lon: data.origin.lon },
        { label: "B", name: "Точка назначения", lat: data.destination.lat, lon: data.destination.lon },
      ],
      legs: [
        {
          from_label: "A",
          to_label: "B",
          distance_km: data.route.distance_km,
          duration_min: data.route.duration_min,
          coordinates: data.route.coordinates,
        }
      ],
      total_distance_km: data.route.distance_km,
      total_duration_min: data.route.duration_min,
    };

    currentRouteData = adaptedData;
    renderMultiRoute(adaptedData);
    updateRouteUI(adaptedData);

    loadingEl.classList.add("hidden");
    contentEl.classList.remove("hidden");
  } catch (err) {
    console.error("Legacy route fetch failure:", err);
    showError(I18N[currentLang].errorTitle);
  }
}

// App Entry Point
document.addEventListener("DOMContentLoaded", () => {
  initMap();

  // Read URL query parameters
  const params = new URLSearchParams(window.location.search);
  const routeIdParam = params.get("route_id");
  const langParam = params.get("lang");
  const latParam = parseFloat(params.get("dest_lat"));
  const lonParam = parseFloat(params.get("dest_lon"));

  if (langParam === "uz" || langParam === "ru") {
    setLanguage(langParam);
  } else {
    setLanguage("ru");
  }

  // Setup Lang Toggle Button
  document.getElementById("btn-lang-toggle").addEventListener("click", () => {
    hapticLight();
    setLanguage(currentLang === "ru" ? "uz" : "ru");
  });

  // Re-center full route button
  document.getElementById("btn-recenter").addEventListener("click", () => {
    centerFullRoute();
  });

  // Retry button
  document.getElementById("btn-retry").addEventListener("click", () => {
    hapticLight();
    if (routeIdParam) {
      loadRouteById(routeIdParam);
    } else if (!isNaN(latParam) && !isNaN(lonParam)) {
      loadLegacyRoute(latParam, lonParam);
    }
  });

  // Load route
  if (routeIdParam) {
    loadRouteById(routeIdParam);
  } else if (!isNaN(latParam) && !isNaN(lonParam)) {
    loadLegacyRoute(latParam, lonParam);
  } else {
    showError(I18N[currentLang].errorNoParams);
  }
});
