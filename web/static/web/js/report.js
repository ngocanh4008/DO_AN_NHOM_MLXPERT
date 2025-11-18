
// REPORT MANAGEMENT DASHBOARD SCRIPT


// Utility function
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// Utility function to get CSRF token from cookie
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Global state
let filterState = {
    page: 1,
    pageSize: 5,
    search: '',
    time: 'all',
    type: 'all',
    creator: '',
};

// Dropdown options
const TIME_OPTIONS = [
    { value: "all",     label: "Tất cả thời gian" },
    { value: "today",   label: "Hôm nay" },
    { value: "7_days",  label: "7 ngày qua" },
    { value: "30_days", label: "30 ngày qua" }
];

const TYPE_OPTIONS = [
    { value: "all", label: "Tất cả" },
    { value: "Tổng quan vận hành", label: "Tổng quan vận hành" },
    { value: "Mô phỏng giá và khuyến mãi", label: "Mô phỏng giá và khuyến mãi" },
    { value: "Dự báo nhu cầu", label: "Dự báo nhu cầu" }
];


document.addEventListener("DOMContentLoaded", () => {
    setupDropdowns();
    attachFilterEvents();
    fetchReports();

    // Search live
    const searchInput = $("#search_input");
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            filterState.search = e.target.value.trim();
            filterState.page = 1;
            fetchReports();
        });
    }

    // Pagination click
    const paginationContainer = $("#pagination_container");
    if (paginationContainer) {
        paginationContainer.addEventListener('click', (e) => {
            const target = e.target.closest('.page-btn');
            if (target) handlePaginationClick(target);
        });
    }
});



// Setup dropdown filters

function setupDropdowns() {
    const timeFilter = document.querySelector("#filter-time");
    const typeFilter = document.querySelector("#filter-type");
    const creatorFilter = document.querySelector("#filter-creator");

    // Clear trước
    timeFilter.innerHTML = "";
    typeFilter.innerHTML = "";

    // Time options
    TIME_OPTIONS.forEach(opt => {
        const o = document.createElement("option");
        o.value = opt.value;
        o.textContent = opt.label;
        timeFilter.appendChild(o);
    });

    // Type options
    TYPE_OPTIONS.forEach(opt => {
        const o = document.createElement("option");
        o.value = opt.value;
        o.textContent = opt.label;
        typeFilter.appendChild(o);
    });
}

function attachFilterEvents() {
    const timeFilter = document.querySelector("#filter-time");
    const typeFilter = document.querySelector("#filter-type");
    const creatorFilter = document.querySelector("#filter-creator");

    if (timeFilter) {
        timeFilter.addEventListener("change", () => {
            filterState.time = timeFilter.value;
            filterState.page = 1;
            fetchReports();
        });
    }

    if (typeFilter) {
        typeFilter.addEventListener("change", () => {
            filterState.type = typeFilter.value;
            filterState.page = 1;
            fetchReports();
        });
    }

    if (creatorFilter) {
        creatorFilter.addEventListener("input", () => {
            filterState.creator = creatorFilter.value.trim();
            filterState.page = 1;
            fetchReports();
        });
    }
}



// Fetch reports from backend

async function fetchReports() {
    const tableBody = $("#report_table_body");
    const paginationContainer = $("#pagination_container");
    tableBody.innerHTML = `<tr><td colspan="7" class="text-center py-4">Đang tải dữ liệu...</td></tr>`;
    paginationContainer.innerHTML = '';

    try {
        const response = await fetch(`/api/reports?search=${filterState.search}&type=${filterState.type}&creator=${filterState.creator}&time=${filterState.time}&page=${filterState.page}&pageSize=${filterState.pageSize}`);
        if (!response.ok) throw new Error('Không lấy được dữ liệu từ server');
        const data = await response.json();

        renderTable(data.reports, data.currentPage);
        renderPagination(data.totalPages, data.currentPage);
    } catch (error) {
        console.error(error);
        tableBody.innerHTML = `<tr><td colspan="7" class="text-center text-red-600 py-4">🚫 Lỗi tải dữ liệu</td></tr>`;
    }
}


// Render table

function renderTable(reports, currentPage) {
    const tableBody = $("#report_table_body");
    const downloadIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>`;
    const trashIcon = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>`;

    tableBody.innerHTML = '';
    if (!reports.length) {
        tableBody.innerHTML = '<tr><td colspan="7" class="text-center py-4">Không tìm thấy báo cáo nào.</td></tr>';
        return;
    }

    reports.forEach((report, index) => {
        const stt = (currentPage - 1) * filterState.pageSize + index + 1;
        const row = document.createElement('tr');
        row.innerHTML = `
            <td data-label="STT">${stt}</td>
            <td data-label="Tên báo cáo"><a href="#" class="report-link">${report.name}</a></td> 
            <td data-label="Loại báo cáo">${report.type}</td>
            <td data-label="Người tạo">${report.creator}</td>
            <td data-label="Ngày tạo">${report.date}</td>
            <td data-label="Kích thước tệp">${report.size}</td>
            <td data-label="Hành động">
                <button class="download" onclick="redownloadReport('${report.id}', '${report.name}')">${downloadIcon}</button>
                <button class="delete" onclick="deleteReport('${report.id}', '${report.name}')">${trashIcon}</button>
            </td>
        `;
        tableBody.appendChild(row);
    });
}


// Pagination

function handlePaginationClick(target) {
    const page = target.getAttribute('data-page');
    const totalPages = parseInt($("#pagination_container").getAttribute('data-total-pages') || 1);

    if (page === 'prev') filterState.page = Math.max(1, filterState.page - 1);
    else if (page === 'next') filterState.page = Math.min(totalPages, filterState.page + 1);
    else filterState.page = parseInt(page);

    fetchReports();
}

function renderPagination(totalPages, currentPage) {
    const container = $("#pagination_container");
    container.setAttribute('data-total-pages', totalPages);
    container.innerHTML = '';

    const prevBtn = createPageButton("«", 'prev', currentPage > 1);
    container.appendChild(prevBtn);

    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, currentPage + 2);
    if (currentPage <= 3) endPage = Math.min(totalPages, 5);
    else if (currentPage > totalPages - 2) startPage = Math.max(1, totalPages - 4);

    for (let i = startPage; i <= endPage; i++) {
        container.appendChild(createPageButton(i, i, true, i === currentPage));
    }

    const nextBtn = createPageButton("»", 'next', currentPage < totalPages);
    container.appendChild(nextBtn);
}

function createPageButton(text, pageValue, isEnabled, isActive = false) {
    const btn = document.createElement('button');
    btn.textContent = text;
    btn.className = 'page-btn';
    btn.setAttribute('data-page', pageValue);
    if (!isEnabled) btn.disabled = true;
    if (isActive) btn.classList.add('active');
    return btn;
}

function redownloadReport(id, filename) {
    // Chuyển hướng trình duyệt đến URL API GET mới
    // Trình duyệt sẽ tự động tải file từ response của backend
    window.location.href = `/reports/redownload/${id}`;
}

function deleteReport(id, name) {
    if (!confirm(`Xóa lịch sử báo cáo "${name}" khỏi database?`)) return;

    //LẤY VÀ THÊM CSRF TOKEN VÀO HEADER
    const csrfToken = getCookie('csrftoken');

    fetch(`/api/reports/${id}`, {
        method: 'DELETE',
        headers: {
            'X-CSRFToken': csrfToken //
        }
    })
        .then(response => {
            if (response.ok) {
                alert(`Báo cáo "${name}" đã được xóa`);
                fetchReports();
            } else {
                response.json()
                    .then(data => {
                        const errorMessage = data.error || `Lỗi không xác định (Mã: ${response.status})`;
                        alert(`Xóa báo cáo thất bại: ${errorMessage}`);
                    })
                    .catch(() => {
                        alert(`Xóa báo cáo thất bại: Lỗi server (Mã ${response.status})`);
                    });
            }
        })
        .catch(err => {
            console.error(err);
            alert('Lỗi kết nối mạng khi xóa báo cáo');
        });
}
