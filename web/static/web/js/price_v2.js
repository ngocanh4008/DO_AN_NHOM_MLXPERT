// =======================================================
// PRICE SIMULATION DASHBOARD – FINAL FIXED
// =======================================================

const $ = (sel) => document.querySelector(sel);

document.addEventListener("DOMContentLoaded", () => {
  const slider = $("#discount_rate");
  const promoLabel = $("#promo_label");
  slider.addEventListener("input", () => (promoLabel.textContent = slider.value + "%"));

  $("#run_btn").addEventListener("click", async () => {
    await runPredict();
    await drawDiscountChart();  // stacked area
    await drawRegionChart();    // region chart
    await drawPriceChart();     // price chart
  });
});

// =======================================================
// 1️⃣ PREDICT
// =======================================================
async function runPredict() {
  const payload = {
    product_group_enc: parseInt($("#product_group").value),
    brand_name_enc: parseInt($("#brand_name").value),
    region_enc: parseInt($("#region_name").value),
    net_price: parseFloat($("#net_price").value),
    discount_rate: parseFloat($("#discount_rate").value),
    promo_on: $("#promo_on").checked,
  };

  const res = await fetch("/api/predict/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();

  if (!data.ok) {
    $("#ai_text").textContent = "⚠️ " + data.error;
    return;
  }

  $("#kq_sold").textContent = data.predicted_sales.toLocaleString("vi-VN");
  $("#kq_rev").textContent = data.predicted_revenue.toLocaleString("vi-VN");
  $("#kq_profit").textContent = data.predicted_profit.toLocaleString("vi-VN");

  $("#ai_text").textContent = genAIText(data, payload);
}

// =======================================================
// 2️⃣ AI INSIGHT TEXT
// =======================================================
async function runPredict() {
  const payload = {
    product_group_enc: parseInt($("#product_group").value),
    brand_name_enc: parseInt($("#brand_name").value),
    region_enc: parseInt($("#region_name").value),
    net_price: parseFloat($("#net_price").value),
    discount_rate: parseFloat($("#discount_rate").value),
    promo_on: $("#promo_on").checked,
  };

  // ===== Gọi /predict chính =====
  const res = await fetch("/api/predict/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!data.ok) {
    $("#ai_text").textContent = "⚠️ " + data.error;
    return;
  }

  $("#kq_sold").textContent = data.predicted_sales.toLocaleString("vi-VN");
  $("#kq_rev").textContent = data.predicted_revenue.toLocaleString("vi-VN");
  $("#kq_profit").textContent = data.predicted_profit.toLocaleString("vi-VN");

  // ✅ Gợi ý thông minh sau khi có kết quả cơ bản
  const smartSuggestion = await getSmartSuggestion(payload);
  $("#ai_text").innerHTML = smartSuggestion;
}
async function getSmartSuggestion(payload) {
  try {
    // ---- A. Quét theo giá ----
    const resPrice = await fetch("/api/simulate_series/", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, mode: "price" }),
    });
    const priceData = await resPrice.json();
    const bestPrice = priceData.series.reduce((a, b) => (a.profit > b.profit ? a : b));

    // ---- B. Quét theo khuyến mãi ----
    const resDisc = await fetch("/api/simulate_series/", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, mode: "discount" }),
    });
    const discData = await resDisc.json();
    const bestDisc = discData.series.reduce((a, b) => (a.profit > b.profit ? a : b));

    // ---- C. Quét theo vùng ----
    const resRegion = await fetch("/api/simulate_series/", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...payload, mode: "region" }),
    });
    const regionData = await resRegion.json();
    const bestRegion = regionData.series.reduce((a, b) => (a.profit > b.profit ? a : b));

    const regionLabels = ["KVCA","KVMB","KVMT","KVMTR","KVTN","KVMN","Khác"];

    // ---- Tổng hợp đề xuất thông minh ----
    return `
    💡 <b>Đề xuất thông minh:</b><br>
    • <b>Giá tối ưu:</b> ${bestPrice.x.toLocaleString("vi-VN")}đ<br>
    • <b>Khuyến mãi tối ưu:</b> ${bestDisc.x}%<br>
    • <b>Vùng lợi nhuận cao nhất:</b> ${regionLabels[bestRegion.x] || "Không xác định"}<br>
    <hr>
    📈 <b>Dự kiến đạt lợi nhuận:</b> ${Math.round(bestDisc.profit).toLocaleString("vi-VN")}đ/tuần<br>
    🧩 <i>AI đề xuất kết hợp giá ${bestPrice.x.toLocaleString("vi-VN")}đ và khuyến mãi ${bestDisc.x}% tại ${regionLabels[bestRegion.x]}</i>.
    `;
  } catch (err) {
    return "⚠️ Không thể phân tích đề xuất thông minh.";
  }
}

// =======================================================
// 3️⃣ BIỂU ĐỒ KHUYẾN MÃI – STACKED AREA CHART
// =======================================================
async function drawDiscountChart() {
  const payload = {
    product_group_enc: parseInt($("#product_group").value),
    brand_name_enc: parseInt($("#brand_name").value),
    region_enc: parseInt($("#region_name").value),
    net_price: parseFloat($("#net_price").value),
    discount_rate: parseFloat($("#discount_rate").value),
    promo_on: $("#promo_on").checked,
  };

  const res = await fetch("/api/simulate_series/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!data.ok) return;

  const x = data.series.map((d) => d.x);
  const ySold = data.series.map((d) => d.sold);
  const yRevenue = data.series.map((d) => d.revenue);
  const yProfit = data.series.map((d) => d.profit);

  // Tìm điểm lợi nhuận tối ưu
  const maxProfit = Math.max(...yProfit);
  const idx = yProfit.indexOf(maxProfit);

  const traces = [
    {
      x, y: ySold, name: "Sản lượng", mode: "lines", stackgroup: "one",
      line: { color: "steelblue" }, fillcolor: "rgba(70,130,180,0.5)"
    },
    {
      x, y: yRevenue, name: "Doanh thu", mode: "lines", stackgroup: "one",
      line: { color: "orange" }, fillcolor: "rgba(255,165,0,0.4)"
    },
    {
      x, y: yProfit, name: "Lợi nhuận", mode: "lines", stackgroup: "one",
      line: { color: "crimson" }, fillcolor: "rgba(220,20,60,0.4)"
    },
    {
      x: [x[idx]], y: [maxProfit],
      mode: "markers+text", name: "Điểm tối ưu",
      text: [`⭐ ${x[idx]}%`], textposition: "top center",
      marker: { color: "red", size: 12, symbol: "star" },
    }
  ];

  Plotly.newPlot("price-chart", traces, {
    title: "Tác động khuyến mãi lên các chỉ tiêu kinh doanh",
    xaxis: { title: "Tỷ lệ giảm giá (%)" },
    yaxis: { title: "Giá trị dự đoán (chuẩn hóa)" },
    legend: { orientation: "h", y: -0.3 },
  });
}

// =======================================================
// 4️⃣ BIỂU ĐỒ VÙNG MIỀN – BAR (region)
// =======================================================
async function drawRegionChart() {
  const payload = {
    product_group_enc: parseInt($("#product_group").value),
    brand_name_enc: parseInt($("#brand_name").value),
    region_enc: parseInt($("#region_name").value),
    net_price: parseFloat($("#net_price").value),
    discount_rate: parseFloat($("#discount_rate").value),
    promo_on: $("#promo_on").checked,
    mode: "region"
  };

  const res = await fetch("/api/simulate_series/", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!data.ok) return;

  const regionLabels = ["KVCA","KVMB","KVMT","KVMTR","KVTN","KVMN","Khác"];
  const x = data.series.map(d => regionLabels[d.x] || d.x);
  const y = data.series.map(d => d.sold);

  Plotly.newPlot("chart_top_regions", [{
    x, y, type: "bar", marker: { color: "teal" }
  }], {
    title: "Phản ứng vùng miền với khuyến mãi",
    xaxis: { title: "Vùng" },
    yaxis: { title: "Sản lượng dự đoán" }
  });
}

// =======================================================
// 5️⃣ BIỂU ĐỒ BIẾN ĐỘNG GIÁ – LINE (price)
// =======================================================
async function drawPriceChart() {
  const payload = {
    product_group_enc: parseInt($("#product_group").value),
    brand_name_enc: parseInt($("#brand_name").value),
    region_enc: parseInt($("#region_name").value),
    net_price: parseFloat($("#net_price").value),
    discount_rate: parseFloat($("#discount_rate").value),
    promo_on: $("#promo_on").checked,
    mode: "price"
  };

  const res = await fetch("/api/simulate_series/", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if (!data.ok) return;

  const x = data.series.map(d => d.x);
  const y1 = data.series.map(d => d.revenue);
  const y2 = data.series.map(d => d.sold);
  const y3 = data.series.map(d => d.profit);

  // ✅ tìm điểm có lợi nhuận cao nhất
  const maxProfit = Math.max(...y3);
  const idx = y3.indexOf(maxProfit);
  const bestX = x[idx];

  const fig = [
    { x, y: y1, type: "scatter", name: "Doanh thu", line: { color: "blue" }, visible: "legendonly" },
    { x, y: y2, type: "scatter", name: "Sản lượng", line: { color: "green" },visible: "legendonly"},
    { x, y: y3, type: "scatter", name: "Lợi nhuận", line: { color: "orange" },  },

    // ⭐ thêm trace đánh dấu điểm tối ưu
    {
      x: [bestX],
      y: [maxProfit],
      mode: "markers+text",
      name: "Điểm tối ưu",
      text: [`⭐ ${bestX.toLocaleString()}đ`],
      textposition: "top center",
      marker: { color: "red", size: 14, symbol: "star" },
      hoverinfo: "text"
    }
  ];

  Plotly.newPlot("chart_main", fig, {
    title: "Biến động theo Giá bán",
    xaxis: { title: "Giá bán (đ)" },
    yaxis: { title: "Giá trị" },
    legend: { orientation: "h", y: -0.3 },
  });
}
document.addEventListener("DOMContentLoaded", () => {
  const slider = $("#discount_rate");
  const promoLabel = $("#promo_label");
  slider.addEventListener("input", () => (promoLabel.textContent = slider.value + "%"));

  $("#run_btn").addEventListener("click", async () => {
    await runPredict();
    await drawDiscountChart();
    await drawRegionChart();
    await drawPriceChart();
  });

  // 🆕 Sự kiện tải xuống
  $("#btn_download").addEventListener("click", downloadReport);
});
// =======================================================
//  📥 DOWNLOAD REPORT
// =======================================================
async function downloadReport() {
  const payload = {
    product_group_enc: parseInt($("#product_group").value),
    brand_name_enc: parseInt($("#brand_name").value),
    region_enc: parseInt($("#region_name").value),
    net_price: parseFloat($("#net_price").value),
    discount_rate: parseFloat($("#discount_rate").value),
    promo_on: $("#promo_on").checked,
  };

  const res = await fetch("/api/download_report/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    alert("Lỗi khi tạo báo cáo");
    return;
  }

  // Nhận blob (file Excel)
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "BaoCaoGiaKhuyenMai.xlsx";
  a.click();
  window.URL.revokeObjectURL(url);
}
