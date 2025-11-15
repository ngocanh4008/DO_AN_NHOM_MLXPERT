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
  $("#btn-export")?.addEventListener("click", exportResult); // Đã kết nối hàm tải file thật

  // Auto load dự báo ban đầu
  runForecast();

  // Reload khi thay đổi filter
  ["#f-product-id", "#f-region", "#f-model", "#f-month-horizon"].forEach((sel) => {
    const el = $(sel);
    //if (el) el.addEventListener("change", () => runForecast());
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

// static/web/js/forecast.js (tìm và thay thế hàm này)

function getModel() {
  const el = document.getElementById("f-model");
  // Trả về tên file chính xác (ví dụ: 'ligth_gbm_v8_grid.pkl')
  if (!el) return "lightgbm_v8_grid.pkl";
  return el.value || "lightgbm_v8_grid.pkl";
}

function getHorizon() {
  const el = document.getElementById("f-month-horizon");
  if (!el) return 3;
  return parseInt(el.value) || 3;
}

// =======================================================
// Gọi API Dự báo (Không đổi)
// =======================================================
async function runForecast() {
  const btn = $("#btn-forecast");

  // Lấy đường dẫn icon từ HTML (CHUẨN)
  const iconLoading = btn.dataset.iconLoading;
  const iconDefault = btn.dataset.iconDefault;

  try {
    const payload = {
      product_id: getSelectedProductId(),
      region: getRegion(),
      model: getModel(),
      horizon: getHorizon(),
    };

    // ==========================
    // HIỂN THỊ ICON LOADING PNG
    // ==========================
    btn.innerHTML = `
      <img src="${iconLoading}" class="btn-icon">
      Đang dự báo...
    `;
    btn.disabled = true;

    const res = await fetch("/api/forecast/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "Lỗi không xác định");

    // Update UI
    updateKPI(data);
    drawForecastMain(data);
    drawRegionChart(data.region_labels || [], data.region_data || []);
    drawTopChart(data.top_labels || [], data.top_changes || []);
    $("#insight").textContent = genInsight(data);

  } catch (e) {
    console.error("Forecast error:", e);
    alert("Lỗi khi chạy dự báo: " + e.message);

  } finally {
    // ==========================
    // TRẢ NÚT VỀ ICON MẶC ĐỊNH PNG
    // ==========================
    btn.innerHTML = `
      <img src="${iconDefault}" class="btn-icon">
      Dự báo mới
    `;
    btn.disabled = false;
  }
}
// =======================================================
// Tải kết quả (HÀM TẢI FILE THẬT)
// =======================================================
async function exportResult() {
  try {
    const payload = {
      product_id: getSelectedProductId(),
      region: getRegion(),
      model: getModel(),
      horizon: getHorizon(),
    };

    // BƯỚC 1: Hiển thị trạng thái tải
    $("#btn-export").disabled = true;
    $("#btn-export").innerHTML = '<i class="ri-loader-4-line ri-spin"></i> Đang tạo file...';

    // BƯỚC 2: Gọi API để tạo và tải file
    const res = await fetch("/api/forecast/export/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
        // Xử lý lỗi từ server
        let errorMessage = `Lỗi từ máy chủ: ${res.status} ${res.statusText}`;
        try {
            const errorData = await res.json();
            if (errorData.error) {
                errorMessage += ` - Chi tiết: ${errorData.error}`;
            }
        } catch (e) {
            // Không phải JSON, dùng lỗi mặc định
        }
        throw new Error(errorMessage);
    }

    // BƯỚC 3: Xử lý phản hồi dạng Blob (file)
    const blob = await res.blob();

    // Đọc tên file từ header (Content-Disposition)
    const contentDisposition = res.headers.get('Content-Disposition');
    let filename = `du_bao_nhu_cau_${new Date().toISOString().slice(0, 10)}.csv`;

    if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename\*?=['"]?([^'"]+)/i);
        if (filenameMatch && filenameMatch[1]) {
            // Xử lý trường hợp có mã hóa (ví dụ: UTF-8'')
            filename = decodeURIComponent(filenameMatch[1].replace(/^UTF-8''/i, ''));
        }
    }

    // BƯỚC 4: Tạo link ảo và kích hoạt tải file
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename; // Tên file
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    a.remove();

    console.log(`Tải file ${filename} thành công!`);

  } catch (e) {
    console.error("Lỗi khi tải file:", e);
    alert("❌ Lỗi khi tải kết quả dự báo. Vui lòng kiểm tra console hoặc liên hệ IT.");
  } finally {
    // BƯỚC 5: Đảm bảo nút trở lại trạng thái ban đầu
    $("#btn-export").innerHTML = '<i class="ri-download-2-line"></i> Tải kết quả';
    $("#btn-export").disabled = false;
  }
}

// =======================================================
// Cập nhật KPI (Không đổi)
// =======================================================
function updateKPI(data) {
  const k = data.kpis || {};

  const elRev = document.querySelector("#kpi-revenue");
  const elQty = document.querySelector("#kpi-qty");
  const elMape = document.querySelector("#kpi-mape");
  const elTop = document.querySelector("#kpi-top");

  // Nếu phần tử chưa tồn tại → không làm gì cả
  if (!elRev || !elQty || !elMape || !elTop) {
    console.warn("⚠️ Không tìm thấy phần tử KPI trong DOM");
    return;
  }

  elRev.textContent = k.sum_forecast != null ? fmtInt(Math.round(k.sum_forecast)) : "—";
  elQty.textContent = k.avg_forecast != null ? fmtInt(Math.round(k.avg_forecast)) : "—";
  elMape.textContent = k.mape_tail != null ? k.mape_tail + "%" : "—";
  elTop.textContent = data.top_strongest || data.product_id || "—";
}


// =======================================================
// Biểu đồ chính: Actual - Fitted - Forecast (Không đổi)
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
// Biểu đồ phụ: Cơ cấu theo khu vực (Không đổi)
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
// Biểu đồ phụ: Top sản phẩm tăng/giảm (Không đổi)
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
// Sinh nội dung phân tích (Không đổi)
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