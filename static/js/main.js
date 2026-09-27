/**
 * AI Meeting Action-Item Extractor
 * Dynamic Frontend Logic & Interactivity
 */

document.addEventListener("DOMContentLoaded", () => {
  initStudioTabs();
  initDropzone();
  initTextareaCounters();
  initDropdowns();
  initTableInteractions();
  initEditModal();
  initAnalyticsCharts();
});

/* ==========================================================================
   1. Studio Tabs (Upload vs Paste)
   ========================================================================== */
function initStudioTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  if (!tabBtns.length) return;

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.dataset.tab;
      
      tabBtns.forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(content => {
        content.classList.remove("active");
      });

      btn.classList.add("active");
      const activeContent = document.getElementById(targetId);
      if (activeContent) {
        activeContent.classList.add("active");
      }
    });
  });
}

/* ==========================================================================
   2. Dropzone & File Upload Preview
   ========================================================================== */
function initDropzone() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-upload-input");
  const previewCard = document.getElementById("file-preview");
  const fileNameDisplay = document.getElementById("file-preview-name");
  const fileSizeDisplay = document.getElementById("file-preview-size");
  const removeFileBtn = document.getElementById("file-remove-btn");
  const titleInput = document.getElementById("meeting-title-input");

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener("click", () => fileInput.click());

  ["dragenter", "dragover"].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", e => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      fileInput.files = files;
      handleFileSelected(files[0]);
    }
  });

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) {
      handleFileSelected(fileInput.files[0]);
    }
  });

  if (removeFileBtn) {
    removeFileBtn.addEventListener("click", e => {
      e.stopPropagation();
      fileInput.value = "";
      if (previewCard) previewCard.style.display = "none";
    });
  }

  function handleFileSelected(file) {
    const allowed = ["txt", "pdf", "docx"];
    const ext = file.name.split(".").pop().toLowerCase();

    if (!allowed.includes(ext)) {
      alert(`Invalid file format: .${ext}. Only .txt, .pdf, and .docx are supported.`);
      fileInput.value = "";
      return;
    }

    if (previewCard && fileNameDisplay) {
      fileNameDisplay.textContent = file.name;
      if (fileSizeDisplay) {
        fileSizeDisplay.textContent = formatBytes(file.size);
      }
      previewCard.style.display = "flex";
    }

    // Auto-fill title if empty
    if (titleInput && !titleInput.value.trim()) {
      const baseName = file.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " ");
      titleInput.value = capitalizeWords(baseName);
    }
  }
}

function formatBytes(bytes, decimals = 1) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
}

function capitalizeWords(str) {
  return str.replace(/\b\w/g, l => l.toUpperCase());
}

/* ==========================================================================
   3. Textarea Live Counters & Sample Inserter
   ========================================================================== */
function initTextareaCounters() {
  const textarea = document.getElementById("transcript-textarea");
  const charCounter = document.getElementById("char-count");
  const lineCounter = document.getElementById("line-count");
  const pasteSampleBtn = document.getElementById("paste-sample-btn");
  const titleInput = document.getElementById("meeting-title-input");

  if (!textarea) return;

  function updateCounts() {
    const text = textarea.value;
    if (charCounter) charCounter.textContent = `${text.length.toLocaleString()} characters`;
    if (lineCounter) {
      const lines = text ? text.split("\n").length : 0;
      lineCounter.textContent = `${lines} lines`;
    }
  }

  textarea.addEventListener("input", updateCounts);
  updateCounts();

  if (pasteSampleBtn) {
    pasteSampleBtn.addEventListener("click", async () => {
      const sampleText = `Sprint Planning & Delivery Sync - Q3
Date: October 14, 2024
Participants: Arun, Priya, John, Sarah, Vikram, David

David (Product Lead): Good morning everyone, thanks for joining today's sprint delivery sync. Today we need to lock down our deliverables.

Arun: From the backend side, the database migrations are complete. Arun will prepare the API documentation by Friday.

Priya: On the design and client side, Priya is responsible for the presentation. I'll make sure the slide deck matches the updated branding.

John: I have synced with the finance and compliance team. John needs to send the report by Monday.

Sarah (QA): The automated regression suite is mostly passing. Sarah: I'll complete the testing tomorrow.

David: Fantastic. We must finalize the client onboarding workflow by next Wednesday.

Vikram: I can take a look at the open backend PRs today. Vikram should review the pull requests before 5 PM tomorrow.

David: Also, the security audit checklist needs to be updated.

Arun: Just to confirm again, Arun will prepare the API documentation by Friday so the frontend team has everything they need.`;

      textarea.value = sampleText;
      updateCounts();
      if (titleInput && !titleInput.value) {
        titleInput.value = "Sprint Planning & Delivery Sync - Q3";
      }
      showToast("Sample transcript loaded into editor!");
    });
  }
}

/* ==========================================================================
   4. Dropdown Controls
   ========================================================================== */
function initDropdowns() {
  const dropdownToggles = document.querySelectorAll(".dropdown-toggle");

  dropdownToggles.forEach(toggle => {
    toggle.addEventListener("click", e => {
      e.stopPropagation();
      const parent = toggle.closest(".dropdown");
      document.querySelectorAll(".dropdown").forEach(d => {
        if (d !== parent) d.classList.remove("open");
      });
      if (parent) parent.classList.toggle("open");
    });
  });

  document.addEventListener("click", () => {
    document.querySelectorAll(".dropdown").forEach(d => d.classList.remove("open"));
  });
}

/* ==========================================================================
   5. Interactive Results Table: Status Toggle, Search, Filter
   ========================================================================== */
function initTableInteractions() {
  // Status toggle checkboxes
  document.querySelectorAll(".status-toggle-form").forEach(form => {
    const checkbox = form.querySelector(".status-toggle");
    if (!checkbox) return;

    checkbox.addEventListener("change", async () => {
      const url = form.action;
      const row = form.closest("tr");
      
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json"
          }
        });

        if (response.ok) {
          const data = await response.json();
          if (data.success) {
            updateRowStatusUI(row, data.status);
            refreshProgressMetrics();
            showToast(`Task marked as ${data.status}`);
          }
        } else {
          // Revert checkbox on error
          checkbox.checked = !checkbox.checked;
          showToast("Failed to update status", "error");
        }
      } catch (err) {
        checkbox.checked = !checkbox.checked;
        showToast("Network error updating status", "error");
      }
    });
  });

  // Table live search & filter
  const searchInput = document.getElementById("table-search-input");
  const statusFilter = document.getElementById("table-status-filter");
  const tableRows = document.querySelectorAll("#action-items-table tbody tr.item-row");

  function filterTable() {
    const query = (searchInput ? searchInput.value : "").toLowerCase().trim();
    const filterStatus = statusFilter ? statusFilter.value.toLowerCase() : "all";

    tableRows.forEach(row => {
      const text = row.textContent.toLowerCase();
      const rowStatus = (row.dataset.status || "").toLowerCase();

      const matchesQuery = !query || text.includes(query);
      const matchesStatus = filterStatus === "all" || rowStatus === filterStatus;

      row.style.display = matchesQuery && matchesStatus ? "" : "none";
    });
  }

  if (searchInput) searchInput.addEventListener("input", filterTable);
  if (statusFilter) statusFilter.addEventListener("change", filterTable);
}

function updateRowStatusUI(row, newStatus) {
  if (!row) return;

  row.dataset.status = newStatus.toLowerCase();
  const badge = row.querySelector(".status-badge-cell .badge");
  const taskText = row.querySelector(".task-text");

  if (newStatus === "Completed") {
    row.classList.add("item-completed");
    if (badge) {
      badge.className = "badge badge-completed";
      badge.textContent = "Completed";
    }
  } else if (newStatus === "Overdue") {
    row.classList.remove("item-completed");
    if (badge) {
      badge.className = "badge badge-overdue";
      badge.textContent = "Overdue";
    }
  } else {
    row.classList.remove("item-completed");
    if (badge) {
      badge.className = "badge badge-pending";
      badge.textContent = "Pending";
    }
  }
}

function refreshProgressMetrics() {
  const rows = document.querySelectorAll("#action-items-table tbody tr.item-row");
  if (!rows.length) return;

  let completed = 0;
  let overdue = 0;
  let pending = 0;

  rows.forEach(r => {
    const s = r.dataset.status;
    if (s === "completed") completed++;
    else if (s === "overdue") overdue++;
    else pending++;
  });

  const total = rows.length;
  const pct = Math.round((completed / total) * 100);

  const completedCountEl = document.getElementById("metric-completed-count");
  const pendingCountEl = document.getElementById("metric-pending-count");
  const progressBarEl = document.getElementById("meeting-progress-bar");
  const progressTextEl = document.getElementById("meeting-progress-percent");

  if (completedCountEl) completedCountEl.textContent = completed;
  if (pendingCountEl) pendingCountEl.textContent = pending;
  if (progressBarEl) progressBarEl.style.width = `${pct}%`;
  if (progressTextEl) progressTextEl.textContent = `${pct}%`;
}

/* ==========================================================================
   6. Edit Action Item Modal
   ========================================================================== */
function initEditModal() {
  const modalBackdrop = document.getElementById("edit-item-modal");
  const editForm = document.getElementById("edit-item-form");
  const closeBtns = document.querySelectorAll(".close-edit-modal");

  if (!modalBackdrop || !editForm) return;

  // Open modal button clicks
  document.querySelectorAll(".edit-item-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.id;
      const task = btn.dataset.task || "";
      const owner = btn.dataset.owner || "";
      const deadline = btn.dataset.deadline || "";
      const status = btn.dataset.status || "Pending";

      editForm.action = `/action-items/${id}/edit`;
      document.getElementById("edit-task-input").value = task;
      document.getElementById("edit-owner-input").value = owner;
      document.getElementById("edit-deadline-input").value = deadline;
      document.getElementById("edit-status-input").value = status;

      modalBackdrop.classList.add("open");
    });
  });

  closeBtns.forEach(btn => {
    btn.addEventListener("click", () => modalBackdrop.classList.remove("open"));
  });

  modalBackdrop.addEventListener("click", e => {
    if (e.target === modalBackdrop) {
      modalBackdrop.classList.remove("open");
    }
  });
}

/* ==========================================================================
   7. Chart.js Analytics Initializer
   ========================================================================== */
async function initAnalyticsCharts() {
  const statusCanvas = document.getElementById("statusChart");
  const ownerCanvas = document.getElementById("ownerChart");
  const confidenceCanvas = document.getElementById("confidenceChart");

  if (!statusCanvas && !ownerCanvas && !confidenceCanvas) return;

  try {
    const response = await fetch("/api/analytics");
    if (!response.ok) return;
    const data = await response.json();

    // 1. Status Distribution Donut Chart
    if (statusCanvas && typeof Chart !== "undefined") {
      new Chart(statusCanvas, {
        type: "doughnut",
        data: {
          labels: data.status_distribution.labels,
          datasets: [{
            data: data.status_distribution.data,
            backgroundColor: ["#10b981", "#f59e0b", "#f43f5e"],
            borderColor: "#1a2234",
            borderWidth: 3
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: "bottom",
              labels: { color: "#94a3b8", font: { family: "Inter", size: 12 } }
            }
          },
          cutout: "70%"
        }
      });
    }

    // 2. Owner Workload Bar Chart
    if (ownerCanvas && typeof Chart !== "undefined") {
      new Chart(ownerCanvas, {
        type: "bar",
        data: {
          labels: data.owner_workload.labels,
          datasets: [
            {
              label: "Completed",
              data: data.owner_workload.completed,
              backgroundColor: "#10b981",
              borderRadius: 4
            },
            {
              label: "Pending",
              data: data.owner_workload.pending,
              backgroundColor: "#f59e0b",
              borderRadius: 4
            },
            {
              label: "Overdue",
              data: data.owner_workload.overdue,
              backgroundColor: "#f43f5e",
              borderRadius: 4
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              stacked: true,
              ticks: { color: "#94a3b8" },
              grid: { display: false }
            },
            y: {
              stacked: true,
              ticks: { color: "#94a3b8", stepSize: 1 },
              grid: { color: "#2d3b55" }
            }
          },
          plugins: {
            legend: {
              position: "bottom",
              labels: { color: "#94a3b8", font: { family: "Inter" } }
            }
          }
        }
      });
    }

    // 3. Confidence Distribution Chart
    if (confidenceCanvas && typeof Chart !== "undefined") {
      new Chart(confidenceCanvas, {
        type: "bar",
        data: {
          labels: data.confidence_distribution.labels,
          datasets: [{
            label: "Action Items",
            data: data.confidence_distribution.data,
            backgroundColor: ["#10b981", "#3b82f6", "#f59e0b"],
            borderRadius: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: {
              ticks: { color: "#94a3b8" },
              grid: { display: false }
            },
            y: {
              ticks: { color: "#94a3b8", stepSize: 1 },
              grid: { color: "#2d3b55" }
            }
          },
          plugins: {
            legend: { display: false }
          }
        }
      });
    }

  } catch (err) {
    console.error("Error loading analytics charts:", err);
  }
}

/* ==========================================================================
   Helper Toast Message
   ========================================================================== */
function showToast(message, type = "success") {
  let toastContainer = document.getElementById("toast-container");
  if (!toastContainer) {
    toastContainer = document.createElement("div");
    toastContainer.id = "toast-container";
    toastContainer.style.position = "fixed";
    toastContainer.style.bottom = "24px";
    toastContainer.style.right = "24px";
    toastContainer.style.zIndex = "9999";
    toastContainer.style.display = "flex";
    toastContainer.style.flexDirection = "column";
    toastContainer.style.gap = "8px";
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement("div");
  toast.className = `alert alert-${type}`;
  toast.style.boxShadow = "0 8px 20px rgba(0,0,0,0.5)";
  toast.style.minWidth = "260px";
  toast.textContent = message;

  toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(8px)";
    toast.style.transition = "all 0.3s ease";
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}
