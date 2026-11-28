/**
 * Student Dashboard controller for static/student_dashboard.html.
 */

import { api } from "./api.js";
import { escapeHtml, renderEmptyState, showToast } from "./ui.js";
import { SmartClassSocket } from "./ws.js";

const OFFLINE_QUEUE_KEY = "smartclass_offline_queue";

const currentUser = JSON.parse(localStorage.getItem("smartclass_user") || "null");
if (!currentUser || currentUser.role !== "student") {
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.replace(`/?redirect=${next}`);
}

const state = {
  student: currentUser,
  token: null,
  checkinToken: null,
  sessionId: null,
  quizTimer: null,
  ws: new SmartClassSocket("global"),
};

function getTokenFromPath() {
  const match = window.location.pathname.match(/\/s\/([^/]+)/);
  if (match) return decodeURIComponent(match[1]);
  const params = new URLSearchParams(window.location.search);
  return params.get("token");
}

function getCheckInTokenFromPath() {
  const match = window.location.pathname.match(/\/checkin\/([^/]+)/);
  if (match) return decodeURIComponent(match[1]);
  const params = new URLSearchParams(window.location.search);
  return params.get("checkin");
}

function initStudentIdentity() {
  if (!state.student) return;
  const studentId = state.student.id_number || state.student.user_id;
  document.getElementById("student-header-name").textContent = state.student.full_name || "Student Dashboard";
  document.getElementById("student-id-display").textContent = studentId;

  document.getElementById("student-signout-btn").addEventListener("click", () => {
    localStorage.removeItem("smartclass_user");
    localStorage.removeItem("smartclass_student");
    window.location.href = "/";
  });
}

async function initCheckInCard() {
  state.checkinToken = getCheckInTokenFromPath();
  if (!state.checkinToken) return;

  const card = document.getElementById("checkin-card");
  try {
    const info = await api.getCheckInDetails(state.checkinToken);
    state.sessionId = info.session_id;
    card.classList.remove("hidden");
    document.getElementById("checkin-course-title").textContent = info.course_name;
    const mins = Math.floor((info.seconds_remaining || 0) / 60);
    const secs = String((info.seconds_remaining || 0) % 60).padStart(2, "0");
    document.getElementById("checkin-timer-text").textContent = `${mins}:${secs} remaining`;

    document.getElementById("checkin-submit-btn").addEventListener("click", async () => {
      try {
        const res = await api.submitAttendanceCheckIn({
          token: state.checkinToken,
          student_id: state.student.id_number || state.student.user_id,
          full_name: state.student.full_name || "Student",
        });
        document.getElementById("checkin-submit-btn").classList.add("hidden");
        const done = document.getElementById("checkin-done-banner");
        done.textContent = `Checked in at ${new Date(res.checked_in_at).toLocaleTimeString()}`;
        done.classList.remove("hidden");
        showToast("Attendance marked!", "success");
      } catch (err) {
        showToast(err.friendlyMessage || "Check-in failed or expired", "error");
      }
    });
  } catch (err) {
    card.classList.remove("hidden");
    document.getElementById("checkin-submit-btn").classList.add("hidden");
    const done = document.getElementById("checkin-done-banner");
    done.textContent = err.friendlyMessage || "This attendance check-in QR has expired.";
    done.classList.remove("hidden");
  }
}

function renderCourses(courses) {
  const container = document.getElementById("available-courses-list");
  if (!courses.length) {
    container.innerHTML = renderEmptyState({
      title: "No courses found",
      subtitle: "Your lecturer has not published any courses yet. Check back soon.",
    });
    return;
  }

  container.innerHTML = courses
    .map((course) => {
      let actionHtml = "";
      if (course.enrollment_status === "approved") {
        actionHtml = `<span class="px-3 py-1.5 rounded-full text-xs font-semibold bg-[#c08552]/20 text-[#4b2e2b] shrink-0">Enrolled</span>`;
      } else if (course.enrollment_status === "pending") {
        actionHtml = `<span class="px-3 py-1.5 rounded-full text-xs font-semibold bg-[#fff8f0] border border-[#8c5a3c]/30 text-[#8c5a3c] shrink-0">Pending Approval</span>`;
      } else {
        actionHtml = `<button data-cid="${escapeHtml(course.id)}" class="join-course-btn bg-[#c08552] hover:bg-[#8c5a3c] text-white text-xs font-semibold px-4 py-2 rounded-xl transition shadow-sm shrink-0">Request to Join</button>`;
      }

      return `
        <div class="flex items-center justify-between gap-3 rounded-2xl border border-[#8c5a3c]/15 bg-[#fff8f0]/50 px-4 py-3.5">
          <div>
            <p class="text-sm font-bold text-[#4b2e2b]">${escapeHtml(course.name)}</p>
            <p class="text-xs text-[#8c5a3c] mt-0.5">${escapeHtml(course.lecturer_name || "Course Instructor")}</p>
          </div>
          ${actionHtml}
        </div>`;
    })
    .join("");

  container.querySelectorAll(".join-course-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const studentId = state.student.id_number || state.student.user_id;
      try {
        await api.requestEnrollment(studentId, btn.dataset.cid);
        showToast("Enrollment request sent to lecturer!", "success");
        await refreshAvailableCourses();
      } catch (err) {
        showToast(err.friendlyMessage || "Could not request enrollment", "error");
      }
    });
  });
}

async function refreshAvailableCourses() {
  if (!state.student) return;
  const studentId = state.student.id_number || state.student.user_id;
  try {
    const courses = await api.listCourses(studentId);
    renderCourses(courses);
  } catch (err) {
    showToast(err.friendlyMessage || "Failed to load courses", "error");
  }
}

function showQuizBanner(message, tone = "success") {
  const banner = document.getElementById("quiz-result-banner");
  const card = document.getElementById("quiz-card");
  card.classList.add("hidden");
  banner.classList.remove("hidden");

  if (tone === "success") {
    banner.className = "rounded-2xl border border-[#c08552]/40 bg-white text-[#4b2e2b] p-6 text-center space-y-2 shadow-lg shadow-[#8c5a3c]/10";
    banner.innerHTML = `<div class="text-lg font-bold text-[#c08552]">Response Recorded</div><p class="text-sm text-[#4b2e2b]">${escapeHtml(message)}</p>`;
  } else {
    banner.className = "rounded-2xl border border-rose-300 bg-rose-50 text-[#4b2e2b] p-6 text-center space-y-2 shadow-lg shadow-[#8c5a3c]/10";
    banner.innerHTML = `<div class="text-lg font-bold text-rose-800">Submission Window Closed</div><p class="text-sm text-rose-900">${escapeHtml(message)}</p>`;
  }
}

function startStudentTimer(secondsLeft) {
  if (state.quizTimer) clearInterval(state.quizTimer);
  let remaining = secondsLeft;
  const el = document.getElementById("student-quiz-timer");
  const tick = () => {
    const m = String(Math.floor(Math.max(0, remaining) / 60)).padStart(2, "0");
    const s = String(Math.max(0, remaining) % 60).padStart(2, "0");
    el.textContent = `${m}:${s}`;
    if (remaining <= 0) {
      clearInterval(state.quizTimer);
      showQuizBanner("The 5-minute submission window has closed.", "error");
    }
    remaining -= 1;
  };
  tick();
  state.quizTimer = setInterval(tick, 1000);
}

async function initQuizCard() {
  state.token = getTokenFromPath();
  if (!state.token) return;

  try {
    const q = await api.getTokenQuestion(state.token);
    state.sessionId = q.session_id;
    document.getElementById("quiz-card").classList.remove("hidden");
    document.getElementById("student-question-text").textContent = q.question_text;

    const optionsWrap = document.getElementById("quiz-options-container");
    optionsWrap.innerHTML = Object.entries(q.options)
      .map(
        ([key, label]) => `
      <label class="flex items-center gap-3 min-h-[54px] rounded-2xl border border-[#8c5a3c]/20 bg-[#fff8f0]/40 px-4 py-3 cursor-pointer hover:border-[#c08552] has-[:checked]:border-[#c08552] has-[:checked]:bg-[#c08552]/10 transition">
        <input type="radio" name="quiz_option" value="${escapeHtml(key)}" required class="w-4 h-4 accent-[#c08552]" />
        <span class="font-mono text-xs font-bold text-[#c08552]">${escapeHtml(key)}</span>
        <span class="text-sm font-medium text-[#4b2e2b]">${escapeHtml(label)}</span>
      </label>`
      )
      .join("");

    startStudentTimer(q.seconds_remaining || 300);
  } catch (err) {
    showQuizBanner(err.friendlyMessage || "The 5-minute submission window has closed.", "error");
  }
}

function renderActivePoll(poll) {
  const container = document.getElementById("student-poll-container");
  if (!poll) {
    container.innerHTML = renderEmptyState({
      title: "No active poll right now",
      subtitle: "When your lecturer launches an instant check-in, you can vote here with one tap.",
    });
    return;
  }

  const isClosed = poll.is_open === false;
  const options = poll.options || Object.keys(poll.results || {});
  container.innerHTML = `
    <div class="flex items-center justify-between gap-2 mb-3">
      <p class="font-semibold text-[#4b2e2b]">${escapeHtml(poll.prompt)}</p>
      ${isClosed ? `<span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#4b2e2b] text-[#fff8f0] shrink-0">Poll Closed</span>` : ""}
    </div>
    <div class="space-y-2.5">
      ${options
        .map(
          (opt) => `
        <button data-opt="${escapeHtml(opt)}" ${isClosed ? "disabled" : ""} class="poll-vote-btn w-full min-h-[48px] flex items-center justify-between rounded-2xl border border-[#8c5a3c]/20 bg-[#fff8f0]/40 ${
            isClosed ? "opacity-60 cursor-not-allowed" : "hover:border-[#c08552] hover:bg-[#c08552]/15"
          } px-4 py-2.5 text-sm font-medium text-[#4b2e2b] transition">
          <span>${escapeHtml(opt)}</span>
          <span class="font-mono text-xs font-semibold text-[#8c5a3c]">${poll.results?.[opt] ?? 0}</span>
        </button>`
        )
        .join("")}
    </div>
  `;

  if (!isClosed) {
    container.querySelectorAll(".poll-vote-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const studentId = state.student?.id_number || state.student?.user_id || null;
        try {
          const updated = await api.votePoll({
            poll_id: poll.poll_id,
            selected_option: btn.dataset.opt,
            student_id: studentId,
          });
          renderActivePoll(updated);
          showToast("Your poll vote has been recorded!", "success");
        } catch (err) {
          showToast(err.friendlyMessage || "Unable to submit vote", "error");
        }
      });
    });
  }
}

async function refreshPolls() {
  if (!state.sessionId) {
    try {
      const sessions = await api.listSessions();
      if (sessions.length) state.sessionId = sessions[0].id;
    } catch {
      return;
    }
  }
  if (!state.sessionId) {
    renderActivePoll(null);
    return;
  }
  try {
    const polls = await api.listSessionPolls(state.sessionId);
    renderActivePoll(polls[0] || null);
  } catch (err) {
    console.error(err);
  }
}

async function refreshStudentHomeworkReviews() {
  const studentId = state.student?.id_number || state.student?.user_id;
  const container = document.getElementById("student-hw-reviews");
  if (!studentId || !container) return;
  try {
    const reviews = await api.listHomeworkReviews(studentId);
    if (!reviews.length) {
      container.innerHTML = "";
      return;
    }
    container.innerHTML = reviews
      .slice(0, 3)
      .map(
        (r) => `
      <div class="rounded-2xl border border-[#8c5a3c]/15 bg-[#fff8f0]/60 p-3.5 space-y-1.5 text-xs">
        <div class="flex items-center justify-between">
          <span class="font-bold text-[#4b2e2b]">${escapeHtml(r.submission_label)}</span>
          <span class="px-2.5 py-0.5 rounded-full font-bold bg-[#c08552]/20 text-[#4b2e2b]">${r.score}/100</span>
        </div>
        <p class="text-[#4b2e2b]/90">${escapeHtml(r.ood_feedback)}</p>
        <p class="text-[#8c5a3c]">${escapeHtml(r.comparative_notes || "")}</p>
      </div>`
      )
      .join("");
  } catch (err) {
    console.error(err);
  }
}

function getOfflineQueue() {
  try {
    return JSON.parse(localStorage.getItem(OFFLINE_QUEUE_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveOfflineQueue(items) {
  try {
    localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(items));
  } catch {
    // ignore storage quota failures
  }
}

async function flushOfflinePrivateMessages() {
  const queue = getOfflineQueue();
  const mine = queue.filter((item) => item.kind === "private_message");
  if (!mine.length || !navigator.onLine) return;

  const remaining = [];
  for (const item of queue) {
    if (item.kind !== "private_message") {
      remaining.push(item);
      continue;
    }
    try {
      await api.createForumPost(item.payload);
    } catch {
      remaining.push(item);
    }
  }
  saveOfflineQueue(remaining);
  const badge = document.getElementById("student-offline-badge");
  if (badge) badge.classList.toggle("hidden", !remaining.some((i) => i.kind === "private_message"));
}

document.addEventListener("DOMContentLoaded", async () => {
  initStudentIdentity();
  await initCheckInCard();
  await refreshAvailableCourses();
  await initQuizCard();
  await refreshPolls();
  await refreshStudentHomeworkReviews();
  await flushOfflinePrivateMessages();

  document.getElementById("refresh-courses-btn").addEventListener("click", refreshAvailableCourses);
  document.getElementById("refresh-poll-btn").addEventListener("click", refreshPolls);
  window.addEventListener("online", flushOfflinePrivateMessages);

  const statusEl = document.getElementById("student-ws-status");
  state.ws.onStatusChange = (s) => {
    statusEl.textContent = s === "connected" ? "Connected live" : "Reconnecting...";
    if (s === "connected") flushOfflinePrivateMessages();
  };
  state.ws.on("POLL_UPDATE", (data) => {
    renderActivePoll({
      poll_id: data.poll_id,
      prompt: data.prompt || "Live Poll",
      results: data.results,
      is_open: data.is_open !== false,
    });
  });
  state.ws.connect(state.sessionId || "global");

  document.getElementById("quiz-submit-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!state.student) return;
    const selected = document.querySelector("input[name='quiz_option']:checked")?.value;
    if (!selected) {
      showToast("Please select an answer option first.", "warning");
      return;
    }

    try {
      const res = await api.submitQuizAnswer({
        token: state.token,
        student_id: state.student.id_number || state.student.user_id,
        full_name: state.student.full_name,
        selected_option: selected,
      });
      showQuizBanner(
        res.is_correct
          ? "Your answer was recorded and verified as correct!"
          : "Your answer has been recorded.",
        "success"
      );
      showToast("Quiz response submitted!", "success");
    } catch (err) {
      showQuizBanner(err.friendlyMessage || "The 5-minute submission window has closed.", "error");
      showToast(err.friendlyMessage || "Submission window closed", "error");
    }
  });

  document.getElementById("student-hw-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const url = document.getElementById("student-hw-url").value.trim();
    if (!url) return showToast("Enter a GitHub repository URL.", "warning");
    try {
      await api.reviewHomework([url], state.sessionId, state.student.id_number || state.student.user_id);
      document.getElementById("student-hw-url").value = "";
      showToast("Homework review ready!", "success");
      await refreshStudentHomeworkReviews();
    } catch (err) {
      showToast(err.friendlyMessage || "Homework review failed", "error");
    }
  });

  document.getElementById("private-msg-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const content = document.getElementById("private-msg-text").value.trim();
    if (!content) {
      showToast("Please write a message before sending.", "warning");
      return;
    }
    const payload = {
      session_id: state.sessionId,
      author_id: state.student?.id_number || state.student?.user_id || null,
      author_name: state.student?.full_name || "Student",
      author_role: "student",
      post_type: "private_message",
      content,
    };
    try {
      if (!navigator.onLine) throw new Error("offline");
      await api.createForumPost(payload);
      document.getElementById("private-msg-text").value = "";
      document.getElementById("private-msg-status").classList.remove("hidden");
      showToast("Private message sent to lecturer!", "success");
    } catch (err) {
      if (!navigator.onLine || !err.response) {
        const q = getOfflineQueue();
        q.push({ kind: "private_message", payload });
        saveOfflineQueue(q);
        document.getElementById("private-msg-text").value = "";
        document.getElementById("student-offline-badge")?.classList.remove("hidden");
        showToast("Offline — message queued and will send on reconnect.", "warning");
      } else {
        showToast(err.friendlyMessage || "Failed to send message", "error");
      }
    }
  });
});
