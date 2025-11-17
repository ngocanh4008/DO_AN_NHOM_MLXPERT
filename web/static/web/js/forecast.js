// =======================================================
// FORECAST DASHBOARD – DỰ BÁO NHU CẦU
// =======================================================

// Helper
const fmtInt = (n) => (n ?? 0).toLocaleString("vi-VN");
const $ = (s) => document.querySelector(s);

// Chart.js defaults
Chart.defaults.font.family = "Inter, system-ui, Arial, sans-serif";
Chart.defaults.plugins.legend.position = "top";
Chart.defaults.plugins.tooltip.mode = "index";
Chart.defaults.plugins.tooltip.intersect = false;

let chartForecast, chartRegion, chartTop;

// =======================================================
// INIT EVENTS
// =======================================================
document.addEventListener("DOMContentLoaded", () => {
  $("#btn-forecast")?.addEventListener("click", runForecast);
  $("#btn-train")?.addEventListener("click", trainModel);
  $("#btn-export")?.addEventListener("click", exportResult);

  runForecast();
});

// =======================================================
// FILTER GETTERS
// =======================================================
function getSelectedProductId() {
  const el = document.getElementById("f-product-id");
  if (!el) return "ALL";
  const v = (el.value || "").trim();
  return v === "" ? "ALL" : v;
}

function getRegion() {
  const el = document.getElementById("f-region");
  if (!el) return "ALL";
  const v = (el.value || "").trim();
  return v === "" ? "ALL" : v;
}

function getModel() {
  const el = document.getElementById("f-model");
  return el ? el.value : "lightgbm_v8_grid.pkl";
}

function getHorizon() {
  const el = document.getElementById("f-month-horizon");
  return el ? parseInt(el.value) || 3 : 3;
}

// =======================================================
// MAIN FORECAST
// =======================================================
async function runForecast() {
  const btn = $("#btn-forecast");

  const iconLoading = btn.dataset.iconLoading;
  const iconDefault = btn.dataset.iconDefault;

  try {
    const payload = {
      product_id: getSelectedProductId(),
      region: getRegion(),
      model: getModel(),
      horizon: getHorizon(),
    };

    btn.innerHTML = `<img src="${iconLoading}" class="btn-icon"> Đang dự báo...`;
    btn.disabled = true;

    const res = await fetch("/api/forecast/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "Lỗi không xác định");

    updateKPI(data);
    drawForecastMain(data);
    drawRegionChart(data.region_labels || [], data.region_data || []);
    drawTopChart(data.top_labels || [], data.top_changes || []);

    // ============================
    // TOP 10 — CHUẨN DỮ LIỆU
    // ============================
    const listData = (data.top_labels || []).map((label, idx) => ({
      product: label,
      value: (data.top_changes || [])[idx] ?? 0
    }));
    renderTop10List(listData);

    // UPDATE INSIGHT
    $("#insight").textContent = genInsight(data);

  } catch (e) {
    console.error("Forecast error:", e);
    alert("Lỗi khi chạy dự báo: " + e.message);

  } finally {
    btn.innerHTML = `<img src="${iconDefault}" class="btn-icon"> Dự báo mới`;
    btn.disabled = false;
  }
}

// =======================================================
// EXPORT FILE
// =======================================================
async function exportResult() {
  try {
    const payload = {
      product_id: getSelectedProductId(),
      region: getRegion(),
      model: getModel(),
      horizon: getHorizon(),
    };

    $("#btn-export").disabled = true;
    $("#btn-export").innerHTML = '<i class="ri-loader-4-line ri-spin"></i> Đang tạo file...';

    const res = await fetch("/api/forecast/export/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let errorMessage = `Lỗi từ máy chủ: ${res.status} ${res.statusText}`;
      try {
        const errorData = await res.json();
        if (errorData.error) errorMessage += " - Chi tiết: " + errorData.error;
      } catch {}
      throw new Error(errorMessage);
    }

    const blob = await res.blob();

    let filename = "forecast.csv";
    const contentDisposition = res.headers.get("Content-Disposition");
    if (contentDisposition) {
      const match = contentDisposition.match(/filename\*?=['"]?([^'"]+)/i);
      if (match && match[1]) {
        filename = decodeURIComponent(match[1].replace(/^UTF-8''/, ""));
      }
    }

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);

  } catch (e) {
    console.error("Export error:", e);
    alert("❌ Lỗi khi tải kết quả dự báo.");

  } finally {
    $("#btn-export").disabled = false;
    $("#btn-export").innerHTML = '<i class="ri-download-2-line"></i> Tải kết quả';
  }
}

// =======================================================
// KPI UPDATE
// =======================================================
function updateKPI(data) {
  const k = data.kpis || {};

  $("#kpi-revenue").textContent = k.sum_forecast != null ? fmtInt(Math.round(k.sum_forecast)) : "—";
  $("#kpi-qty").textContent = k.avg_forecast != null ? fmtInt(Math.round(k.avg_forecast)) : "—";
  $("#kpi-mape").textContent = k.mape_tail != null ? k.mape_tail + "%" : "—";

  $("#kpi-top").textContent = data.top_strongest || data.product_id || "—";

  const change = data.top_strongest_change ?? 0;
  const elTrend = $("#top-strongest-trend");
  const elIcon = $("#top-strongest-icon");

  const prefix = change > 0 ? "+" : "";
  elTrend.textContent = `${prefix}${change}% so với TB nhóm`;

  elIcon.className = change >= 0 ? "ri-arrow-up-s-line up" : "ri-arrow-down-s-line down";
}

// =======================================================
// MAIN CHART
// =======================================================
function drawForecastMain(data) {
  const labelsHist = (data.labels_hist || []).map(m => "Tháng " + m);
  const labelsFuture = (data.labels_future || []).map(m => "Tháng " + m);

  const actual = (data.actual || []).map(x => (isFinite(x) ? x : 0));
  const fitted = (data.fitted || []).map(x => (isFinite(x) ? x : null));
  const forecast = (data.forecast || []).map(x => (isFinite(x) ? x : null));

  const ctx = $("#chart-forecast")?.getContext("2d");
  if (!ctx) return;
  if (chartForecast) chartForecast.destroy();

  chartForecast = new Chart(ctx, {
    type: "line",
    data: {
      labels: [...labelsHist, ...labelsFuture],
      datasets: [
        {
          label: "Thực tế",
          data: [...actual, ...Array(labelsFuture.length).fill(null)],
          borderColor: "#2563eb",
          backgroundColor: "rgba(37,99,235,0.15)",
          borderWidth: 2.5,
        },
        {
          label: "Mô hình (Fitted)",
          data: [...fitted, ...Array(labelsFuture.length).fill(null)],
          borderColor: "#9ca3af",
          borderDash: [6, 4],
          borderWidth: 1.5,
        },
        {
          label: "Dự báo",
          data: [...Array(labelsHist.length).fill(null), ...forecast],
          borderColor: "#f97316",
          backgroundColor: "rgba(249,115,22,0.15)",
          borderWidth: 2.5,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
    },
  });
}

// =======================================================
// REGION CHART
// =======================================================
function drawRegionChart(labels, values) {
  const ctx = $("#chart-region")?.getContext("2d");
  if (!ctx) return;
  if (chartRegion) chartRegion.destroy();

  chartRegion = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: ["#3b82f6", "#f87171", "#fbbf24", "#34d399", "#a78bfa"],
      }],
    },
    options: {
      cutout: "55%",
      plugins: { legend: { position: "right" } },
    },
  });
}

// =======================================================
// TOP CHANGE BAR CHART
// =======================================================
function drawTopChart(labels, values) {
  const ctx = $("#chart-top")?.getContext("2d");
  if (!ctx) return;
  if (chartTop) chartTop.destroy();

  chartTop = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Mức thay đổi (%)",
        data: values,
        backgroundColor: "rgba(59,130,246,0.3)",
        borderColor: "#3b82f6",
        borderWidth: 1.5,
      }],
    },
    options: {
      indexAxis: "y",
      plugins: { legend: { position: "top" } }
    },
  });
}

// =======================================================
// RENDER TOP 10 LIST (CHUẨN % VÀ ICON)
// =======================================================
function renderTop10List(data) {
  const ol = $("#top10-ol");
  if (!ol) return;

  ol.innerHTML = "";

  data.forEach(item => {
    let pct = item.value;
    let prefix = pct > 0 ? "+" : "";
    let color = pct > 0 ? "#16a34a" : pct < 0 ? "#dc2626" : "#64748B";
    let arrow = pct > 0 ? "▲" : pct < 0 ? "▼" : "▬";

    const li = document.createElement("li");
    li.innerHTML = `
      <span style="color:${color}; font-weight:600;">
        ${arrow} ${prefix}${pct.toFixed(2)}%
      </span>
      — <strong>${item.product}</strong>
    `;
    ol.appendChild(li);
  });
}

// =======================================================
// INSIGHT GENERATOR
// =======================================================
function genInsight(data) {
  const k = data.kpis || {};
  const horizon = data.forecast?.length || 0;
  const total = fmtInt(Math.round(k.sum_forecast || 0));
  const mape = k.mape_tail;

  let txt = `Dự báo ${horizon} tháng tới với tổng sản lượng ~ ${total} đơn vị. `;

  if (mape != null) {
    if (mape <= 10) txt += `Độ khớp rất tốt (MAPE ${mape}%).`;
    else if (mape <= 20) txt += `Độ khớp chấp nhận được (MAPE ${mape}%).`;
    else txt += `Độ khớp thấp (MAPE ${mape}%), nên xem xét hiệu chỉnh mô hình.`;
  }

  return txt;
}
