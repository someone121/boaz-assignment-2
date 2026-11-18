/**
 * Lecturer Control Center controller for static/lecturer_dashboard.html.
 */

import { api } from "./api.js";
import {
  escapeHtml,
  renderEmptyState,
  renderSafeMarkdown,
  showToast,
  validateUploadFile,
} from "./ui.js";
import { SmartClassSocket } from "./ws.js";

const currentUser = JSON.parse(localStorage.getItem("smartclass_user") || "null");
if (!currentUser || currentUser.role !== "lecturer") {
  window.location.replace("/");
}

const state = {
  sessionId: null,
  lecturer: currentUser,
  countdownTimer: null,
  webcamStream: null,
  webcamInterval: null,
  quizChart: null,
  pollChart: null,
  ws: new SmartClassSocket("global"),
};

function initCharts() {
  const quizCtx = document.getElementById("quiz-chart").getContext("2d");
  state.quizChart = new Chart(quizCtx, {
    type: "bar",
    data: {
      labels: ["A", "B", "C", "D"],
      datasets: [
        {
          label: "Responses",
          data: [0, 0, 0, 0],
          backgroundColor: ["#c08552", "#8c5a3c", "#4b2e2b", "#d4a373"],
          borderRadius: 10,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });

  const pollCtx = document.getElementById("poll-chart").getContext("2d");
  state.pollChart = new Chart(pollCtx, {
    type: "bar",
    data: {
      labels: ["Option 1", "Option 2"],
      datasets: [
        {
          label: "Votes",
          data: [0, 0],
          backgroundColor: ["#c08552", "#8c5a3c", "#4b2e2b", "#d4a373"],
          borderRadius: 10,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });
}

function updateQuizChart(optionCounts, totalResponses) {
  if (!state.quizChart) return;
  state.quizChart.data.datasets[0].data = [
    optionCounts.A || 0,
    optionCounts.B || 0,
    optionCounts.C || 0,
    optionCounts.D || 0,
  ];
  state.quizChart.update();
  document.getElementById("quiz-chart-total").textContent = `${totalResponses} total`;
  document.getElementById("quiz-response-counter").textContent = `${totalResponses} Responses`;
}

function updatePollChart(results, prompt = null) {
  if (!state.pollChart) return;
  const labels = Object.keys(results || {});
  const values = Object.values(results || {});
  const total = values.reduce((acc, v) => acc + v, 0);
  state.pollChart.data.labels = labels.length ? labels : ["Option 1", "Option 2"];
  state.pollChart.data.datasets[0].data = values.length ? values : [0, 0];
  state.pollChart.update();
  if (prompt) {
    document.getElementById("poll-chart-title").textContent = prompt;
  }
  document.getElementById("poll-chart-total").textContent = `${total} votes`;
}

function setupTabs() {
  const buttons = document.querySelectorAll(".tab-btn");
  const panels = document.querySelectorAll(".tab-panel");
  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.tab;
      buttons.forEach((b) => {
        b.classList.remove("border-[#c08552]", "text-[#c08552]", "font-semibold");
        b.classList.add("border-transparent", "text-[#8c5a3c]", "font-medium");
      });
      btn.classList.add("border-[#c08552]", "text-[#c08552]", "font-semibold");
      btn.classList.remove("border-transparent", "text-[#8c5a3c]", "font-medium");
      panels.forEach((p) => p.classList.toggle("hidden", p.id !== `tab-${target}`));
    });
  });
}

function setupAuth() {
  const badge = document.getElementById("lecturer-name-badge");
  const signOutBtn = document.getElementById("lecturer-signout-btn");

  if (badge && state.lecturer) {
    badge.textContent = `${state.lecturer.full_name} (${state.lecturer.id_number || state.lecturer.user_id})`;
  }

  signOutBtn?.addEventListener("click", () => {
    localStorage.removeItem("smartclass_user");
    localStorage.removeItem("smartclass_lecturer");
    window.location.href = "/";
  });
}

function setupWebSocket() {
  const badge = document.getElementById("ws-badge");
  state.ws.onStatusChange = (status) => {
    if (status === "connected") {
      badge.className =
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#c08552]/20 text-[#4b2e2b]";
      badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-[#c08552]"></span>Live`;
    } else {
      badge.className =
        "inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-white border border-[#8c5a3c]/20 text-[#8c5a3c]";
      badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-[#8c5a3c] animate-pulse"></span>Reconnecting`;
    }
  };

  state.ws.on("QUIZ_UPDATE", (data) => {
    updateQuizChart(data.option_counts || {}, data.total_responses || 0);
  });

  state.ws.on("POLL_UPDATE", (data) => {
    updatePollChart(data.results || {}, data.prompt);
  });

  state.ws.on("SUMMARY_READY", (data) => {
    document.getElementById("summary-spinner").classList.add("hidden");
    document.getElementById("summary-output").innerHTML = renderSafeMarkdown(data.markdown_summary || "");
    showToast("AI Lecture Summary published to Class Forum!", "success", "/forum", "View Forum");
  });

  state.ws.on("ATTENDANCE_DONE", (data) => {
    showToast(
      `Session complete: ${data.total_present} student(s) present.`,
      "success",
      data.download_url,
      "Download CSV"
    );
  });
}

async function loadSessions() {
  const select = document.getElementById("session-select");
  try {
    let sessions = await api.listSessions();
    if (!sessions.length) {
      const created = await api.startSession({
        course_name: "Intro to Software Engineering",
        lecturer_id: state.lecturer?.id_number || state.lecturer?.user_id || null,
      });
      sessions = [created];
    }
    select.innerHTML = sessions
      .map(
        (s) =>
          `<option value="${escapeHtml(s.id)}">${escapeHtml(s.course_name)} (${escapeHtml(
            s.id.slice(0, 6)
          )})</option>`
      )
      .join("");
    state.sessionId = sessions[0].id;
    select.value = state.sessionId;
    state.ws.connect(state.sessionId);
    renderSessionReportsList(sessions);
    refreshAttendanceTable();
    refreshLatestPoll();
  } catch (err) {
    showToast(err.friendlyMessage || "Unable to load sessions", "error");
  }

  select.addEventListener("change", () => {
    state.sessionId = select.value;
    state.ws.connect(state.sessionId);
    refreshAttendanceTable();
    refreshLatestPoll();
  });

  document.getElementById("start-session-btn").addEventListener("click", async () => {
    const input = document.getElementById("new-course-input");
    const courseName = input.value.trim() || `Lecture ${new Date().toLocaleTimeString()}`;
    try {
      const session = await api.startSession({
        course_name: courseName,
        lecturer_id: state.lecturer?.id_number || state.lecturer?.user_id || null,
      });
      input.value = "";
      await loadSessions();
      state.sessionId = session.id;
      select.value = session.id;
      state.ws.connect(session.id);
      showToast(`Started session: ${session.course_name}`, "success");
    } catch (err) {
      showToast(err.friendlyMessage || "Could not start session", "error");
    }
  });
}

async function refreshQuestions() {
  try {
    const data = await api.listQuestions();
    document.getElementById("question-count-badge").textContent = `${data.remaining}/${data.total} Ready`;
    document
      .getElementById("questions-exhausted-alert")
      .classList.toggle("hidden", !data.questions_exhausted);

    const list = document.getElementById("question-list");
    if (!data.questions.length) {
      list.innerHTML = renderEmptyState({
        title: "No questions loaded yet",
        subtitle: "Select an .xlsx file above and click Upload Question Bank.",
      });
      return;
    }

    list.innerHTML = data.questions
      .map(
        (q) => `
      <div class="flex items-center justify-between gap-2 rounded-xl border border-[#8c5a3c]/15 bg-[#fff8f0]/50 px-3.5 py-2.5 text-xs">
        <span class="font-medium text-[#4b2e2b] truncate">${escapeHtml(q.question_text)}</span>
        <div class="flex items-center gap-2 shrink-0">
          <span class="px-2.5 py-0.5 rounded-full font-semibold ${
            q.is_used ? "bg-[#8c5a3c]/15 text-[#8c5a3c]" : "bg-[#c08552]/20 text-[#4b2e2b]"
          }">${q.is_used ? "Used" : "Ready"}</span>
          <button data-qid="${q.id}" class="launch-specific-btn text-[#c08552] hover:text-[#8c5a3c] font-bold">Launch</button>
        </div>
      </div>`
      )
      .join("");

    list.querySelectorAll(".launch-specific-btn").forEach((btn) => {
      btn.addEventListener("click", () => launchQuestion(Number(btn.dataset.qid)));
    });
  } catch (err) {
    console.error(err);
  }
}

function startCountdown(ttlSeconds) {
  if (state.countdownTimer) clearInterval(state.countdownTimer);
  let remaining = ttlSeconds;
  const el = document.getElementById("quiz-countdown");

  const render = () => {
    const mins = String(Math.floor(remaining / 60)).padStart(2, "0");
    const secs = String(remaining % 60).padStart(2, "0");
    el.textContent = `${mins}:${secs}`;
    if (remaining <= 0) {
      clearInterval(state.countdownTimer);
      el.textContent = "EXPIRED";
    }
    remaining -= 1;
  };
  render();
  state.countdownTimer = setInterval(render, 1000);
}

async function launchQuestion(questionId = null) {
  if (!state.sessionId) return showToast("Start or select a session first.", "warning");
  try {
    const res = await api.triggerQuestion(
      state.sessionId,
      questionId,
      state.lecturer?.id_number || state.lecturer?.user_id || null
    );
    document.getElementById("empty-qr-state").classList.add("hidden");
    document.getElementById("active-qr-panel").classList.remove("hidden");
    document.getElementById("active-question-prompt").textContent = res.question_text;

    const fullUrl = `${window.location.origin}${res.qr_path}`;
    const linkEl = document.getElementById("qr-direct-link");
    linkEl.href = fullUrl;
    linkEl.textContent = fullUrl;

    const qrWrap = document.getElementById("qr-canvas");
    qrWrap.innerHTML = "";
    new QRCode(qrWrap, { text: fullUrl, width: 164, height: 164 });

    updateQuizChart({ A: 0, B: 0, C: 0, D: 0 }, 0);
    startCountdown(res.ttl_seconds || 300);
    await refreshQuestions();
    if (res.questions_exhausted) {
      showToast("Heads up: That was the last question in your Excel bank.", "warning");
    } else {
      showToast("5-minute QR question launched!", "success");
    }
  } catch (err) {
    showToast(err.friendlyMessage || "Unable to trigger question", "error");
  }
}

function setupQuizAndPolls() {
  document.getElementById("empty-qr-state").innerHTML = renderEmptyState({
    title: "No active QR challenge",
    subtitle: "Click Launch Next Question to project a 5-minute dynamic QR code.",
  });

  const excelInput = document.getElementById("excel-upload-input");
  const excelLabel = document.getElementById("excel-file-label");
  excelInput.addEventListener("change", () => {
    const file = excelInput.files[0];
    excelLabel.textContent = file
      ? `Selected: ${file.name} (${Math.max(1, Math.round(file.size / 1024))} KB)`
      : "Columns: Question, Option A, Option B, Option C, Option D, Correct";
  });

  document.getElementById("excel-upload-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const file = excelInput.files[0];
    if (!validateUploadFile(file, [".xlsx"], "Excel question bank")) return;
    try {
      const res = await api.uploadQuizExcel(file, state.sessionId);
      showToast(`Loaded ${res.loaded_count} question(s) from Excel.`, "success");
      excelInput.value = "";
      excelLabel.textContent = "Columns: Question, Option A, Option B, Option C, Option D, Correct";
      await refreshQuestions();
    } catch (err) {
      showToast(err.friendlyMessage || "Failed to parse Excel workbook", "error");
    }
  });

  document
    .getElementById("launch-next-question-btn")
    .addEventListener("click", () => launchQuestion(null));

  document.getElementById("preset-yesno-btn").addEventListener("click", () => {
    document.getElementById("poll-prompt").value = "Do you understand the current concept?";
    document.getElementById("poll-opt-1").value = "Yes";
    document.getElementById("poll-opt-2").value = "No";
    document.getElementById("poll-opt-3").value = "";
    document.getElementById("poll-opt-4").value = "";
  });

  document.getElementById("poll-create-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!state.sessionId) return showToast("Start or select a session first.", "warning");
    const prompt = document.getElementById("poll-prompt").value.trim();
    const opt1 = document.getElementById("poll-opt-1").value.trim();
    const opt2 = document.getElementById("poll-opt-2").value.trim();
    if (!prompt || !opt1 || !opt2) {
      showToast("Please enter a poll question and at least two options.", "warning");
      return;
    }
    try {
      const payload = {
        session_id: state.sessionId,
        prompt,
        option_1: opt1,
        option_2: opt2,
        option_3: document.getElementById("poll-opt-3").value.trim() || null,
        option_4: document.getElementById("poll-opt-4").value.trim() || null,
      };
      const poll = await api.createPoll(payload);
      updatePollChart(poll.results, poll.prompt);
      showToast("Live poll broadcasted!", "success");
    } catch (err) {
      showToast(err.friendlyMessage || "Could not create poll", "error");
    }
  });
}

async function refreshLatestPoll() {
  if (!state.sessionId) return;
  try {
    const polls = await api.listSessionPolls(state.sessionId);
    if (polls.length) {
      updatePollChart(polls[0].results, polls[0].prompt);
    }
  } catch (err) {
    console.error(err);
  }
}

function setupAIStudio() {
  document.getElementById("summary-output").innerHTML = renderEmptyState({
    title: "No lecture summary generated yet",
    subtitle: "Choose a recording or transcript above to generate key takeaways and publish to the Class Forum.",
  });
  document.getElementById("hw-review-results").innerHTML = renderEmptyState({
    title: "No homework evaluations yet",
    subtitle: "Paste one or more repository URLs above to generate a comparative OOD/SOLID rubric.",
  });

  const lectureInput = document.getElementById("lecture-upload-input");
  const lectureLabel = document.getElementById("lecture-file-label");
  lectureInput.addEventListener("change", () => {
    const file = lectureInput.files[0];
    lectureLabel.textContent = file
      ? `Selected: ${file.name} (${Math.max(1, Math.round(file.size / 1024))} KB)`
      : "Supports .mp4, .m4a, .mp3, .wav, .txt, .md";
  });

  document.getElementById("lecture-upload-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const file = lectureInput.files[0];
    if (!validateUploadFile(file, [".mp4", ".m4a", ".mp3", ".wav", ".txt", ".md"], "lecture recording")) {
      return;
    }

    const progressWrap = document.getElementById("upload-progress-wrap");
    const progressBar = document.getElementById("upload-progress-bar");
    const percentLabel = document.getElementById("upload-percent");
    const spinner = document.getElementById("summary-spinner");

    progressWrap.classList.remove("hidden");
    spinner.classList.remove("hidden");
    try {
      const courseName =
        document.getElementById("session-select").selectedOptions[0]?.textContent || "Course Forum";
      const res = await api.summarizeLecture(file, state.sessionId, courseName, (evt) => {
        if (evt.total) {
          const pct = Math.round((evt.loaded / evt.total) * 100);
          progressBar.style.width = `${pct}%`;
          percentLabel.textContent = `${pct}%`;
        }
      });
      spinner.classList.add("hidden");
      document.getElementById("summary-output").innerHTML = renderSafeMarkdown(res.markdown_summary);
      lectureInput.value = "";
      lectureLabel.textContent = "Supports .mp4, .m4a, .mp3, .wav, .txt, .md";
      showToast("Lecture summarized & posted to Class Forum!", "success", "/forum", "View Forum");
    } catch (err) {
      spinner.classList.add("hidden");
      showToast(err.friendlyMessage || "Summary failed", "error");
    }
  });

  document.getElementById("hw-review-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const raw = document.getElementById("hw-repo-urls").value;
    const urls = raw
      .split(/[\n,]+/)
      .map((u) => u.trim())
      .filter(Boolean);
    if (!urls.length) {
      showToast("Please paste at least one repository URL before submitting.", "warning");
      return;
    }
    try {
      const res = await api.reviewHomework(urls, state.sessionId);
      const callout = document.getElementById("hw-comparative-callout");
      const firstComparative = res.reviews[0]?.comparative_notes;
      if (firstComparative) {
        callout.textContent = firstComparative;
        callout.classList.remove("hidden");
      }

      const container = document.getElementById("hw-review-results");
      container.innerHTML = `
        <table class="w-full text-left text-xs">
          <thead class="bg-[#fff8f0] border-b border-[#8c5a3c]/20 text-[#8c5a3c] uppercase">
            <tr>
              <th class="py-3 px-3.5">Submission</th>
              <th class="py-3 px-3.5">Score</th>
              <th class="py-3 px-3.5">OOD / SOLID Rubric Feedback</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[#8c5a3c]/10">
            ${res.reviews
              .map(
                (r) => `
              <tr class="hover:bg-[#fff8f0]/60">
                <td class="py-3 px-3.5 align-top">
                  <div class="font-bold text-[#4b2e2b]">${escapeHtml(r.submission_label)}</div>
                  <div class="font-mono text-[11px] text-[#8c5a3c] truncate max-w-[140px]">${escapeHtml(r.repo_url)}</div>
                </td>
                <td class="py-3 px-3.5 align-top">
                  <span class="px-2.5 py-0.5 rounded-full font-bold bg-[#c08552]/20 text-[#4b2e2b]">${r.score}/100</span>
                </td>
                <td class="py-3 px-3.5 text-[#4b2e2b]/90 leading-relaxed">${escapeHtml(r.ood_feedback)}</td>
              </tr>`
              )
              .join("")}
          </tbody>
        </table>`;
      showToast(`Evaluated ${res.count} submission(s).`, "success");
    } catch (err) {
      showToast(err.friendlyMessage || "Homework review failed", "error");
    }
  });
}

async function refreshAttendanceTable() {
  if (!state.sessionId) return;
  try {
    const data = await api.getAttendanceStatus(state.sessionId);
    const wrap = document.getElementById("attendance-roster-wrap");
    document.getElementById("attendance-detected-badge").textContent = `${data.total_tracked} tracked`;
    if (!data.records.length) {
      wrap.innerHTML = renderEmptyState({
        title: "No attendance records yet",
        subtitle: "Start your webcam stream or process a classroom image/video to log dwell times.",
      });
      return;
    }
    wrap.innerHTML = `
      <table class="w-full text-left text-sm">
        <thead>
          <tr class="border-b border-[#8c5a3c]/20 text-xs uppercase text-[#8c5a3c]">
            <th class="py-2.5 pr-3">Track</th>
            <th class="py-2.5 pr-3">Student ID</th>
            <th class="py-2.5 pr-3">Name</th>
            <th class="py-2.5 pr-3">Observed</th>
            <th class="py-2.5">Status</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[#8c5a3c]/10">
          ${data.records
            .map(
              (rec) => `
            <tr>
              <td class="py-2.5 pr-3 font-mono text-xs text-[#8c5a3c]">#${rec.track_id}</td>
              <td class="py-2.5 pr-3 font-mono text-xs text-[#4b2e2b]">${escapeHtml(rec.student_id)}</td>
              <td class="py-2.5 pr-3 font-medium text-[#4b2e2b]">${escapeHtml(rec.full_name)}</td>
              <td class="py-2.5 pr-3 font-mono text-xs text-[#8c5a3c]">${rec.total_minutes_observed} min</td>
              <td class="py-2.5">
                <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                  rec.presence_status === "Present"
                    ? "bg-[#c08552]/20 text-[#4b2e2b]"
                    : "bg-rose-100 text-rose-800"
                }">${escapeHtml(rec.presence_status)}</span>
              </td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>`;
  } catch (err) {
    console.error(err);
  }
}

function setupAttendance() {
  const video = document.getElementById("webcam-video");
  const canvas = document.getElementById("webcam-canvas");
  const placeholder = document.getElementById("webcam-placeholder");
  const toggleBtn = document.getElementById("toggle-webcam-btn");
  const sendNowBtn = document.getElementById("capture-single-frame-btn");

  const captureAndSend = () => {
    if (!state.sessionId || !video.videoWidth) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob(async (blob) => {
      if (!blob) return;
      try {
        await api.uploadAttendanceFrame(state.sessionId, blob, "webcam.jpg", 5);
        await refreshAttendanceTable();
      } catch (err) {
        console.error(err);
      }
    }, "image/jpeg");
  };

  toggleBtn.addEventListener("click", async () => {
    if (state.webcamStream) {
      state.webcamStream.getTracks().forEach((t) => t.stop());
      state.webcamStream = null;
      clearInterval(state.webcamInterval);
      video.classList.add("hidden");
      placeholder.classList.remove("hidden");
      sendNowBtn.classList.add("hidden");
      toggleBtn.textContent = "Start Webcam Stream";
      return;
    }
    try {
      state.webcamStream = await navigator.mediaDevices.getUserMedia({ video: true });
      video.srcObject = state.webcamStream;
      video.classList.remove("hidden");
      placeholder.classList.add("hidden");
      sendNowBtn.classList.remove("hidden");
      toggleBtn.textContent = "Stop Webcam";
      state.webcamInterval = setInterval(captureAndSend, 5000);
    } catch {
      showToast("Webcam unavailable — choose a frame or video file instead.", "warning");
    }
  });

  sendNowBtn.addEventListener("click", captureAndSend);

  const attInput = document.getElementById("attendance-file-input");
  const attLabel = document.getElementById("attendance-file-label");
  attInput.addEventListener("change", () => {
    const file = attInput.files[0];
    attLabel.textContent = file ? file.name : "Choose Frame / Video";
  });

  document.getElementById("attendance-file-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const file = attInput.files[0];
    if (!state.sessionId) {
      showToast("Start or select a session first.", "warning");
      return;
    }
    if (
      !validateUploadFile(
        file,
        [".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".avi"],
        "classroom frame or video"
      )
    ) {
      return;
    }
    try {
      const res = await api.uploadAttendanceFrame(state.sessionId, file, file.name, 5);
      showToast(`Processed ${file.name}: ${res.detected_count} person(s) detected.`, "success");
      attInput.value = "";
      attLabel.textContent = "Choose Frame / Video";
      await refreshAttendanceTable();
    } catch (err) {
      showToast(err.friendlyMessage || "Frame processing failed", "error");
    }
  });

  document.getElementById("refresh-attendance-btn").addEventListener("click", refreshAttendanceTable);

  document.getElementById("stop-export-btn").addEventListener("click", async () => {
    if (!state.sessionId) return;
    try {
      await api.stopAttendance(state.sessionId);
      await api.downloadAttendanceCsv(state.sessionId);
      await refreshAttendanceTable();
      const sessions = await api.listSessions();
      renderSessionReportsList(sessions);
      await openSessionReportModal(state.sessionId);
    } catch (err) {
      showToast(err.friendlyMessage || "Export failed", "error");
    }
  });

  document.getElementById("refresh-sessions-report-btn").addEventListener("click", async () => {
    try {
      const sessions = await api.listSessions();
      renderSessionReportsList(sessions);
    } catch (err) {
      showToast(err.friendlyMessage || "Unable to refresh sessions", "error");
    }
  });

  document.getElementById("header-view-report-btn").addEventListener("click", () => {
    if (!state.sessionId) {
      showToast("Please start or select a session first.", "warning");
      return;
    }
    openSessionReportModal(state.sessionId);
  });
}

function renderSessionReportsList(sessions) {
  const container = document.getElementById("session-reports-list");
  if (!container) return;
  if (!sessions.length) {
    container.innerHTML = renderEmptyState({
      title: "No recorded sessions yet",
      subtitle: "Start a session above to track classroom attendance and generate reports.",
    });
    return;
  }

  container.innerHTML = sessions
    .map(
      (s) => `
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-2xl border border-[#8c5a3c]/15 bg-[#fff8f0]/60 px-4 py-3.5">
      <div>
        <div class="flex items-center gap-2">
          <span class="text-sm font-bold text-[#4b2e2b]">${escapeHtml(s.course_name)}</span>
          <span class="px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${
            s.is_active ? "bg-[#c08552]/20 text-[#4b2e2b]" : "bg-[#4b2e2b] text-[#fff8f0]"
          }">${s.is_active ? "Active" : "Completed"}</span>
        </div>
        <p class="text-xs text-[#8c5a3c] mt-0.5">
          Started: ${new Date(s.start_time).toLocaleString()} &middot; ID: <span class="font-mono">${escapeHtml(s.id.slice(0, 8))}</span>
        </p>
      </div>
      <button data-sid="${escapeHtml(s.id)}" class="view-session-report-btn bg-[#c08552] hover:bg-[#8c5a3c] text-white text-xs font-semibold px-4 py-2 rounded-xl transition shadow-sm shrink-0">
        View Report (צפה בדוח)
      </button>
    </div>`
    )
    .join("");

  container.querySelectorAll(".view-session-report-btn").forEach((btn) => {
    btn.addEventListener("click", () => openSessionReportModal(btn.dataset.sid));
  });
}

let activeReportSessionId = null;

async function openSessionReportModal(sessionId) {
  const modal = document.getElementById("session-report-modal");
  try {
    const report = await api.getSessionReport(sessionId);
    activeReportSessionId = report.session_id;

    document.getElementById("report-course-title").textContent = report.course_name;
    document.getElementById("report-status-pill").textContent = report.is_active
      ? "Live Session Report"
      : "Completed Session Report";
    document.getElementById("report-subtitle").textContent = report.is_mock_data
      ? "Preview statistics (no CV frames uploaded yet for this session)"
      : `Session ID: ${report.session_id.slice(0, 8)}`;

    document.getElementById("report-total-detected").textContent = String(report.total_detected);
    document.getElementById("report-left-early").textContent = String(report.students_left_early);
    document.getElementById("report-present-count").textContent = String(report.total_present);
    document.getElementById("report-rate-percent").textContent = `${report.attendance_rate_percent}%`;
    document.getElementById("report-duration-min").textContent = `${report.total_duration_minutes}m`;

    modal.classList.remove("hidden");
  } catch (err) {
    showToast(err.friendlyMessage || "Unable to load session report", "error");
  }
}

function setupReportModal() {
  const modal = document.getElementById("session-report-modal");
  const close = () => modal.classList.add("hidden");

  document.getElementById("close-report-modal-btn").addEventListener("click", close);
  document.getElementById("report-modal-done-btn").addEventListener("click", close);
  modal.addEventListener("click", (e) => {
    if (e.target === modal) close();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.classList.contains("hidden")) close();
  });

  document.getElementById("report-download-csv-btn").addEventListener("click", async () => {
    if (!activeReportSessionId) return;
    try {
      await api.downloadAttendanceCsv(activeReportSessionId);
      showToast("Attendance CSV downloaded!", "success");
    } catch (err) {
      showToast(err.friendlyMessage || "CSV download failed", "error");
    }
  });
}

async function refreshPendingEnrollments() {
  try {
    const pending = await api.listPendingEnrollments();
    document.getElementById("pending-enroll-count-badge").textContent = String(pending.length);
    const list = document.getElementById("pending-enrollments-list");
    if (!pending.length) {
      list.innerHTML = renderEmptyState({
        title: "No pending enrollments",
        subtitle: "All student course requests have been reviewed.",
      });
      return;
    }

    list.innerHTML = pending
      .map(
        (enr) => `
      <div class="flex items-center justify-between gap-3 rounded-2xl border border-[#8c5a3c]/15 bg-[#fff8f0]/60 px-4 py-3.5">
        <div>
          <p class="text-sm font-bold text-[#4b2e2b]">${escapeHtml(enr.student_name)}</p>
          <p class="text-xs text-[#8c5a3c] mt-0.5">
            ID: <span class="font-mono">${escapeHtml(enr.student_id)}</span> &middot; Course: <strong>${escapeHtml(enr.course_name)}</strong>
          </p>
        </div>
        <button data-eid="${enr.id}" class="approve-enroll-btn bg-[#c08552] hover:bg-[#8c5a3c] text-white text-xs font-semibold px-4 py-2 rounded-xl transition shadow-sm shrink-0">
          Approve
        </button>
      </div>`
      )
      .join("");

    list.querySelectorAll(".approve-enroll-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        try {
          await api.approveEnrollment(Number(btn.dataset.eid));
          showToast("Student enrollment approved!", "success");
          await refreshPendingEnrollments();
        } catch (err) {
          showToast(err.friendlyMessage || "Failed to approve enrollment", "error");
        }
      });
    });
  } catch (err) {
    console.error(err);
  }
}

async function refreshLecturerCourses() {
  try {
    const courses = await api.listCourses();
    const container = document.getElementById("lecturer-courses-list");
    if (!courses.length) {
      container.innerHTML = renderEmptyState({
        title: "No courses found",
        subtitle: "Use the input above to create your first course.",
      });
      return;
    }
    container.innerHTML = courses
      .map(
        (c) => `
      <div class="flex items-center justify-between rounded-xl border border-[#8c5a3c]/15 bg-[#fff8f0]/60 px-4 py-3 text-xs">
        <span class="font-semibold text-[#4b2e2b]">${escapeHtml(c.name)}</span>
        <span class="text-[#8c5a3c]">${escapeHtml(c.lecturer_name || "Instructor")}</span>
      </div>`
      )
      .join("");
  } catch (err) {
    console.error(err);
  }
}

function setupEnrollments() {
  document.getElementById("refresh-enrollments-btn").addEventListener("click", refreshPendingEnrollments);

  document.getElementById("create-course-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("course-name-input");
    const name = input.value.trim();
    if (!name) {
      showToast("Please enter a course name before creating.", "warning");
      return;
    }
    try {
      await api.createCourse({
        name,
        lecturer_id: state.lecturer?.id_number || state.lecturer?.user_id || null,
      });
      input.value = "";
      showToast(`Course "${name}" created!`, "success");
      await refreshLecturerCourses();
    } catch (err) {
      showToast(err.friendlyMessage || "Could not create course", "error");
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  initCharts();
  setupTabs();
  setupAuth();
  setupWebSocket();
  setupQuizAndPolls();
  setupAIStudio();
  setupAttendance();
  setupEnrollments();
  setupReportModal();
  await loadSessions();
  await refreshQuestions();
  await refreshPendingEnrollments();
  await refreshLecturerCourses();
});
