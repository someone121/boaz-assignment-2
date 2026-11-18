/**
 * Student Dashboard controller for static/student_dashboard.html.
 */

import { api } from "./api.js";
import { escapeHtml, renderEmptyState, showToast } from "./ui.js";
import { SmartClassSocket } from "./ws.js";

const currentUser = JSON.parse(localStorage.getItem("smartclass_user") || "null");
if (!currentUser || currentUser.role !== "student") {
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.replace(`/?redirect=${next}`);
}

const state = {
  student: currentUser,
  token: null,
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

  const options = poll.options || Object.keys(poll.results || {});
  container.innerHTML = `
    <p class="font-semibold text-[#4b2e2b] mb-3">${escapeHtml(poll.prompt)}</p>
    <div class="space-y-2.5">
      ${options
        .map(
          (opt) => `
        <button data-opt="${escapeHtml(opt)}" class="poll-vote-btn w-full min-h-[48px] flex items-center justify-between rounded-2xl border border-[#8c5a3c]/20 bg-[#fff8f0]/40 hover:border-[#c08552] hover:bg-[#c08552]/15 px-4 py-2.5 text-sm font-medium text-[#4b2e2b] transition">
          <span>${escapeHtml(opt)}</span>
          <span class="font-mono text-xs font-semibold text-[#8c5a3c]">${poll.results?.[opt] ?? 0}</span>
        </button>`
        )
        .join("")}
    </div>
  `;

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

document.addEventListener("DOMContentLoaded", async () => {
  initStudentIdentity();
  await refreshAvailableCourses();
  await initQuizCard();
  await refreshPolls();

  document.getElementById("refresh-courses-btn").addEventListener("click", refreshAvailableCourses);
  document.getElementById("refresh-poll-btn").addEventListener("click", refreshPolls);

  const statusEl = document.getElementById("student-ws-status");
  state.ws.onStatusChange = (s) => {
    statusEl.textContent = s === "connected" ? "Connected live" : "Reconnecting...";
  };
  state.ws.on("POLL_UPDATE", (data) => {
    renderActivePoll({
      poll_id: data.poll_id,
      prompt: data.prompt || "Live Poll",
      results: data.results,
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

  document.getElementById("private-msg-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const content = document.getElementById("private-msg-text").value.trim();
    if (!content) {
      showToast("Please write a message before sending.", "warning");
      return;
    }
    try {
      await api.createForumPost({
        session_id: state.sessionId,
        author_id: state.student?.id_number || state.student?.user_id || null,
        author_name: state.student?.full_name || "Student",
        author_role: "student",
        post_type: "private_message",
        content,
      });
      document.getElementById("private-msg-text").value = "";
      document.getElementById("private-msg-status").classList.remove("hidden");
      showToast("Private message sent to lecturer!", "success");
    } catch (err) {
      showToast(err.friendlyMessage || "Failed to send message", "error");
    }
  });
});
