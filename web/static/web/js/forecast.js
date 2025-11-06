// =======================================================
// FORECAST DASHBOARD – DỰ BÁO NHU CẦU
// =======================================================

// Helper: định dạng số VN
const fmtInt = (n) => (n ?? 0).toLocaleString("vi-VN");
const $ = (s) => document.querySelector(s);

// Chart.js mặc định
Chart.defaults.font.family = "Inter, system-ui, Arial, sans-serif";
Chart.defaults.plugins.legend.position = "top";
Chart.defaults.plugins.tooltip.mode = "index";
Chart.defaults.plugins.tooltip.intersect = false;

let chartForecast, chartRegion, chartTop;

// =======================================================
// Sự kiện khởi tạo
// =======================================================
document.addEventListener("DOMContentLoaded", () => {
  $("#btn-forecast")?.addEventListener("click", runForecast);
  $("#btn-train")?.addEventListener("click", trainModel);
  $("#btn-export")?.addEventListener("click", exportResult);

  // Auto load dự báo ban đầu
  runForecast();

  // Reload khi thay đổi filter
  ["#f-product-id", "#f-region", "#f-model", "#f-month-horizon"].forEach((sel) => {
    const el = $(sel);
    if (el) el.addEventListener("change", () => runForecast());
  });
});

// =======================================================
// Lấy giá trị filter
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
  if (!el) return "xgb";
  return (el.value || "xgb").trim().toLowerCase();
}

function getHorizon() {
  const el = document.getElementById("f-month-horizon");
  if (!el) return 3;
  return parseInt(el.value) || 3;
}

// =======================================================
// Gọi API Dự báo
// =======================================================
async function runForecast() {
  try {
    const payload = {
      product_id: getSelectedProductId(),
      region: getRegion(),
      model: getModel(),
      horizon: getHorizon(),
    };

    $("#btn-forecast").textContent = "⏳ Đang dự báo...";
    $("#btn-forecast").disabled = true;

    const res = await fetch("/api/forecast/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "Lỗi không xác định");

    // Cập nhật KPI
    updateKPI(data);

    // Vẽ biểu đồ chính
    drawForecastMain(data);

    // Vẽ biểu đồ phụ (dữ liệu thật từ API)
    drawRegionChart(data.region_labels || [], data.region_data || []);
    drawTopChart(data.top_labels || [], data.top_changes || []);

    // Sinh insight
    $("#insight").textContent = genInsight(data);
  } catch (e) {
    console.error("Forecast error:", e);
    alert("Lỗi khi chạy dự báo: " + e.message);
  } finally {
    $("#btn-forecast").textContent = "Dự báo mới";
    $("#btn-forecast").disabled = false;
  }
}

// =======================================================
// Huấn luyện mô hình (demo)
// =======================================================
async function trainModel() {
  $("#btn-train").disabled = true;
  $("#btn-train").textContent = "⏳ Đang huấn luyện...";
  try {
    await new Promise((r) => setTimeout(r, 1000));
    alert("Huấn luyện mô hình thành công!");
  } catch (e) {
    console.error(e);
    alert("Lỗi huấn luyện mô hình");
  } finally {
    $("#btn-train").disabled = false;
    $("#btn-train").textContent = "Huấn luyện mô hình";
  }
}

// =======================================================
// Tải kết quả
// =======================================================
function exportResult() {
  alert("Giả lập: tải kết quả PDF/CSV");
}

// =======================================================
// Cập nhật KPI
// =======================================================
function updateKPI(data) {
  const k = data.kpis || {};
  $("#kpi-qty").textContent = fmtInt(Math.round(k.avg_forecast || 0));
  $("#kpi-revenue").textContent = fmtInt(Math.round(k.sum_forecast || 0));
  $("#kpi-mape").textContent = k.mape_tail != null ? k.mape_tail + "%" : "—";
  $("#kpi-top").textContent = data.product_id || "—";
}

// =======================================================
// Biểu đồ chính: Actual - Fitted - Forecast
// =======================================================
function drawForecastMain(data) {
  const labelsHist = (data.labels_hist || []).map((m) => "Tháng " + m);
  const labelsFuture = (data.labels_future || []).map((m) => "Tháng " + m);
  const actual = (data.actual || []).map(x => (x && isFinite(x) ? x : 0));
  const fitted = (data.fitted || []).map(x => (x && isFinite(x) ? x : null));
  const forecast = (data.forecast || []).map(x => (x && isFinite(x) ? x : null));

  const ctx = document.getElementById("chart-forecast")?.getContext("2d");
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
          tension: 0.35,
          spanGaps: true,
        },
        {
          label: "Mô hình (Fitted)",
          data: [...fitted, ...Array(labelsFuture.length).fill(null)],
          borderColor: "#9ca3af",
          borderDash: [6, 4],
          borderWidth: 1.5,
          tension: 0.3,
          spanGaps: true,
        },
        {
          label: "Dự báo",
          data: [...Array(labelsHist.length).fill(null), ...forecast],
          borderColor: "#f97316",
          backgroundColor: "rgba(249,115,22,0.15)",
          borderWidth: 2.8,
          tension: 0.35,
          spanGaps: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { display: false }, title: { display: true, text: "Tháng" } },
        y: {
          beginAtZero: true,
          grid: { color: "rgba(0,0,0,0.05)" },
          ticks: { callback: (v) => (v >= 1000 ? v.toLocaleString("vi-VN") : v) },
          title: { display: true, text: "Sản lượng bán (đơn vị)" },
        },
      },
      plugins: {
        legend: { position: "bottom" },
        tooltip: {
          callbacks: {
            label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y?.toLocaleString("vi-VN")}`,
          },
        },
      },
    },
  });
}

// =======================================================
// Biểu đồ phụ: Cơ cấu theo khu vực
// =======================================================
function drawRegionChart(labels, values) {
  const ctx = document.getElementById("chart-region")?.getContext("2d");
  if (!ctx) return;
  if (chartRegion) chartRegion.destroy();
  chartRegion = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: ["#3b82f6", "#f87171", "#fbbf24", "#34d399", "#a78bfa"],
      }],
    },
    options: {
      plugins: { legend: { position: "right" } },
      cutout: "55%",
    },
  });
}

// =======================================================
// Biểu đồ phụ: Top sản phẩm tăng/giảm
// =======================================================
function drawTopChart(labels, values) {
  const ctx = document.getElementById("chart-top")?.getContext("2d");
  if (!ctx) return;
  if (chartTop) chartTop.destroy();
  chartTop = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
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
      scales: {
        x: { grid: { color: "rgba(0,0,0,0.05)" } },
        y: { grid: { display: false } },
      },
      plugins: {
        legend: { position: "top" },
      },
    },
  });
}

// =======================================================
// Sinh nội dung phân tích
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
