/* ============================================================
   Enterprise AI Automation Assistant — Frontend Script
   ============================================================ */

const loadingStepsText = [
  "Connecting to Gemini AI...",
  "Analyzing workflow request...",
  "Generating AI workflow summary...",
  "Extracting recommended tasks...",
  "Drafting communication...",
  "Triggering automation pipeline...",
  "Saving to database...",
];

let loadingInterval = null;
let stepIndex = 0;

function showLoading() {
  const overlay = document.getElementById("loadingOverlay");
  const stepsEl = document.getElementById("loadingSteps");
  if (!overlay) return;
  stepIndex = 0;
  if (stepsEl) stepsEl.textContent = loadingStepsText[0];
  overlay.classList.add("active");
  loadingInterval = setInterval(() => {
    stepIndex = (stepIndex + 1) % loadingStepsText.length;
    if (stepsEl) stepsEl.textContent = loadingStepsText[stepIndex];
  }, 1800);
}

function hideLoading() {
  const overlay = document.getElementById("loadingOverlay");
  if (overlay) overlay.classList.remove("active");
  if (loadingInterval) { clearInterval(loadingInterval); loadingInterval = null; }
}

function showToast(message, type = "success") {
  const toast = document.getElementById("toastSuccess");
  if (!toast) return;
  toast.querySelector(".toast-msg").textContent = message;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3800);
}

function addUserMessage(text) {
  const messages = document.getElementById("chatMessages");
  if (!messages) return;
  const div = document.createElement("div");
  div.className = "message user";
  div.innerHTML = `
    <div class="message-avatar"><i class="bi bi-person-fill"></i></div>
    <div class="message-bubble">${escapeHtml(text)}</div>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

function addAiMessage(text) {
  const messages = document.getElementById("chatMessages");
  if (!messages) return;
  const div = document.createElement("div");
  div.className = "message ai";
  div.innerHTML = `
    <div class="message-avatar"><i class="bi bi-cpu-fill"></i></div>
    <div class="message-bubble">${escapeHtml(text)}</div>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// Department colour mapping
const deptColors = {
  Engineering: { bg: "rgba(79,70,229,0.15)", color: "#a5b4fc", border: "rgba(79,70,229,0.3)" },
  Operations:  { bg: "rgba(6,182,212,0.15)",  color: "#67e8f9",  border: "rgba(6,182,212,0.3)" },
  Management:  { bg: "rgba(245,158,11,0.15)", color: "#fcd34d",  border: "rgba(245,158,11,0.3)" },
  Marketing:   { bg: "rgba(236,72,153,0.15)", color: "#f9a8d4",  border: "rgba(236,72,153,0.3)" },
  Finance:     { bg: "rgba(16,185,129,0.15)", color: "#6ee7b7",  border: "rgba(16,185,129,0.3)" },
};

function renderTasks(tasks) {
  const container = document.getElementById("tasksContainer");
  if (!container) return;
  container.innerHTML = "";
  tasks.forEach((task, i) => {
    const priority = task.priority || "Medium";
    const dept = task.department || "Operations";
    const status = task.status || "Pending";
    const dc = deptColors[dept] || deptColors["Operations"];
    container.innerHTML += `
      <div class="task-card mb-3">
        <div class="d-flex justify-content-between align-items-start mb-2 flex-wrap gap-2">
          <div class="fw-bold" style="font-size:14px;color:var(--text-light);flex:1">${escapeHtml(task.title)}</div>
          <div class="d-flex gap-2 align-items-center flex-shrink-0">
            <span class="priority-badge ${priority}">${escapeHtml(priority)}</span>
            <span style="font-size:10px;padding:3px 8px;border-radius:20px;background:rgba(255,255,255,0.06);color:var(--text-muted);border:1px solid var(--border);font-weight:600">
              <i class="bi bi-hourglass me-1"></i>${escapeHtml(status)}
            </span>
          </div>
        </div>
        <div style="font-size:13px;color:var(--text-muted);margin-bottom:10px">${escapeHtml(task.description)}</div>
        <div class="d-flex align-items-center gap-3">
          <span style="font-size:11px;padding:3px 9px;border-radius:20px;background:${dc.bg};color:${dc.color};border:1px solid ${dc.border};font-weight:600">
            <i class="bi bi-building me-1"></i>${escapeHtml(dept)}
          </span>
          <span style="font-size:11px;color:rgba(148,163,184,0.5)">
            <i class="bi bi-cpu me-1"></i>Task ${i + 1} · AI Recommended
          </span>
        </div>
      </div>`;
  });
}

// Stored workflow_id for email send
let lastWorkflowId = null;

async function processWorkflow() {
  const textarea = document.getElementById("workflowInput");
  const sendBtn = document.getElementById("sendBtn");
  if (!textarea) return;

  const input = textarea.value.trim();
  if (!input) { textarea.focus(); return; }

  textarea.disabled = true;
  sendBtn.disabled = true;
  addUserMessage(input);
  textarea.value = "";
  showLoading();

  try {
    const response = await fetch("/process", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input }),
    });
    const data = await response.json();
    hideLoading();

    if (!response.ok || data.error) {
      addAiMessage("Error: " + (data.error || "Something went wrong. Please try again."));
      return;
    }

    lastWorkflowId = data.workflow_id;

    addAiMessage(
      "Automation pipeline complete! Generated a workflow summary, " +
      data.tasks.length + " recommended tasks, and a communication draft — all saved to the database."
    );

    // Show summary
    const summaryContent = document.getElementById("summaryContent");
    const summarySection = document.getElementById("summarySection");
    if (summaryContent) summaryContent.textContent = data.summary;
    if (summarySection) summarySection.classList.add("visible");

    // Show tasks
    renderTasks(data.tasks);
    const tasksSection = document.getElementById("tasksSection");
    if (tasksSection) tasksSection.classList.add("visible");

    // Show email
    const emailContent = document.getElementById("emailContent");
    const emailSection = document.getElementById("emailSection");
    if (emailContent) emailContent.textContent = data.email;
    if (emailSection) emailSection.classList.add("visible");

    // Show email automation section
    const emailAutoSection = document.getElementById("emailAutoSection");
    if (emailAutoSection) emailAutoSection.classList.add("visible");

    if (summarySection) summarySection.scrollIntoView({ behavior: "smooth", block: "start" });
    showToast("Automation workflow saved to database!");

  } catch (err) {
    hideLoading();
    addAiMessage("Network error. Please check your connection and try again.");
  } finally {
    textarea.disabled = false;
    sendBtn.disabled = false;
    textarea.focus();
  }
}

async function sendEmailAutomation() {
  const recipientEl = document.getElementById("recipientEmail");
  const subjectEl   = document.getElementById("emailSubject");
  const emailContent = document.getElementById("emailContent");
  const sendEmailBtn = document.getElementById("sendEmailBtn");
  const emailAlert   = document.getElementById("emailAlert");

  const recipient = recipientEl?.value.trim();
  const subject   = subjectEl?.value.trim();
  const body      = emailContent?.textContent?.trim();

  if (!recipient || !subject) {
    showAlert(emailAlert, "danger", "Please enter a recipient email address and subject.");
    return;
  }
  if (!body) {
    showAlert(emailAlert, "danger", "No communication draft to send. Run a workflow first.");
    return;
  }

  // Basic email validation
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(recipient)) {
    showAlert(emailAlert, "danger", "Please enter a valid email address.");
    return;
  }

  sendEmailBtn.disabled = true;
  sendEmailBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Triggering Automation...';

  try {
    const response = await fetch("/send-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recipient_email: recipient,
        subject: subject,
        email_body: body,
        workflow_id: lastWorkflowId,
      }),
    });
    const data = await response.json();

    if (!response.ok || data.error) {
      showAlert(emailAlert, "danger", "Automation trigger failed: " + (data.error || "Unknown error"));
    } else {
      showAlert(emailAlert, "success",
        `Email automation triggered! Payload sent to n8n pipeline for ${recipient}.`);
      showToast("Email automation triggered successfully!");
    }
  } catch (err) {
    showAlert(emailAlert, "danger", "Network error while triggering automation.");
  } finally {
    sendEmailBtn.disabled = false;
    sendEmailBtn.innerHTML = '<i class="bi bi-send-fill me-2"></i>Trigger Email Automation';
  }
}

function showAlert(el, type, message) {
  if (!el) return;
  el.className = `alert alert-${type} d-flex align-items-center gap-2`;
  el.innerHTML = `<i class="bi bi-${type === 'success' ? 'check-circle-fill' : 'exclamation-triangle-fill'}"></i>${escapeHtml(message)}`;
  el.style.display = "flex";
  setTimeout(() => { el.style.display = "none"; }, 6000);
}

function copyEmail() {
  const emailContent = document.getElementById("emailContent");
  if (emailContent) {
    navigator.clipboard.writeText(emailContent.textContent).then(() => {
      showToast("Communication draft copied to clipboard!");
    });
  }
}

function autoResizeTextarea(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 140) + "px";
}

document.addEventListener("DOMContentLoaded", () => {
  const textarea = document.getElementById("workflowInput");
  const sendBtn  = document.getElementById("sendBtn");
  const sendEmailBtn = document.getElementById("sendEmailBtn");

  if (textarea) {
    textarea.addEventListener("input", () => autoResizeTextarea(textarea));
    textarea.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        processWorkflow();
      }
    });
  }
  if (sendBtn) sendBtn.addEventListener("click", processWorkflow);
  if (sendEmailBtn) sendEmailBtn.addEventListener("click", sendEmailAutomation);

  document.querySelectorAll(".sample-prompt").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (textarea) {
        textarea.value = btn.dataset.prompt;
        autoResizeTextarea(textarea);
        textarea.focus();
      }
    });
  });
});
