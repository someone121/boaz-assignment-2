/**
 * Course Forum controller for static/forum.html.
 *
 * Plain REST (Axios) — no WebSockets. The user picks one of their courses,
 * sees that course's threads with nested replies, and can post threads or
 * replies. New items are inserted into the DOM immediately from the API
 * response (no full re-render, so half-typed replies elsewhere survive).
 */

import { api } from "./api.js";
import { escapeHtml, renderEmptyState, showToast } from "./ui.js";

const LAST_COURSE_KEY = "smartclass_forum_course";

const state = {
  user: JSON.parse(localStorage.getItem("smartclass_user") || "null"),
  courses: [],
  courseId: null,
  posts: [],
  loadToken: 0, // guards against stale responses when switching courses quickly
};

const userId = () => state.user?.user_id || state.user?.id_number || null;
const currentCourse = () => state.courses.find((c) => c.id === state.courseId) || null;

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

/** Server stores naive UTC timestamps; mark them as UTC before parsing. */
function formatDate(iso) {
  if (!iso) return "";
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso);
  return new Date(hasZone ? iso : `${iso}Z`).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function roleBadge(role) {
  if (role === "lecturer") {
    return `<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-[#4b2e2b] text-[#fff8f0]">Lecturer</span>`;
  }
  return `<span class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-[#fff8f0] border border-[#8c5a3c]/30 text-[#8c5a3c]">Student</span>`;
}

function initials(name) {
  return (name || "?")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("");
}

function replyCountLabel(n) {
  return n === 1 ? "1 reply" : `${n} replies`;
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function renderComment(comment) {
  return `
    <li class="flex gap-3">
      <div class="w-8 h-8 rounded-xl bg-[#c08552]/15 text-[#8c5a3c] flex items-center justify-center text-[11px] font-bold shrink-0">
        ${escapeHtml(initials(comment.author_name))}
      </div>
      <div class="flex-1 min-w-0 rounded-2xl bg-[#fff8f0] border border-[#8c5a3c]/10 px-4 py-2.5">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="text-xs font-bold text-[#4b2e2b]">${escapeHtml(comment.author_name)}</span>
          ${roleBadge(comment.author_role)}
          <span class="text-[11px] text-[#8c5a3c] ml-auto">${escapeHtml(formatDate(comment.created_at))}</span>
        </div>
        <p class="text-sm text-[#4b2e2b]/90 mt-1 whitespace-pre-wrap break-words">${escapeHtml(comment.content)}</p>
      </div>
    </li>`;
}

function renderPost(post) {
  const comments = post.comments || [];
  return `
    <article data-post-id="${post.id}" class="bg-white rounded-2xl border border-[#8c5a3c]/15 shadow-lg shadow-[#8c5a3c]/10 p-6 space-y-4">
      <header class="flex items-start gap-3">
        <div class="w-10 h-10 rounded-2xl bg-gradient-to-br from-[#c08552] to-[#8c5a3c] text-[#fff8f0] flex items-center justify-center text-xs font-bold shrink-0">
          ${escapeHtml(initials(post.author_name))}
        </div>
        <div class="flex-1 min-w-0">
          <h3 class="text-base font-bold text-[#4b2e2b] break-words">${escapeHtml(post.title)}</h3>
          <div class="flex items-center gap-2 flex-wrap mt-0.5">
            <span class="text-xs font-semibold text-[#4b2e2b]">${escapeHtml(post.author_name)}</span>
            ${roleBadge(post.author_role)}
            <span class="text-xs text-[#8c5a3c]">· ${escapeHtml(formatDate(post.created_at))}</span>
          </div>
        </div>
      </header>

      <p class="text-sm text-[#4b2e2b]/90 leading-relaxed whitespace-pre-wrap break-words">${escapeHtml(post.content)}</p>

      <div class="border-t border-[#8c5a3c]/10 pt-4 space-y-3">
        <p class="text-xs font-semibold text-[#8c5a3c]" data-role="reply-count">${replyCountLabel(comments.length)}</p>
        <ul class="space-y-2.5" data-role="comment-list">
          ${comments.map(renderComment).join("")}
        </ul>
        <form data-role="reply-form" data-post-id="${post.id}" class="flex gap-2">
          <input name="content" type="text" maxlength="5000" autocomplete="off" placeholder="Add a reply..." aria-label="Add a reply"
            class="flex-1 min-w-0 rounded-2xl border border-[#8c5a3c]/25 bg-[#fff8f0]/40 px-4 py-2 text-sm text-[#4b2e2b] placeholder:text-[#8c5a3c]/50 focus:bg-white focus:ring-2 focus:ring-[#c08552] outline-none transition" />
          <button type="submit" class="bg-[#c08552] hover:bg-[#8c5a3c] disabled:opacity-60 disabled:cursor-not-allowed text-white text-xs font-semibold px-4 py-2 rounded-2xl transition shadow-sm shrink-0">
            Reply
          </button>
        </form>
      </div>
    </article>`;
}

function renderPostsEmptyState() {
  return renderEmptyState({
    title: "No discussions in this course yet.",
    subtitle: "Start the conversation! Ask a question or share something helpful with your classmates.",
    iconSvg: `
      <svg class="w-6 h-6 text-[#8c5a3c]" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.86 9.86 0 01-4-.8L3 20l1.3-3.9A7.6 7.6 0 013 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>`,
  });
}

function renderFeed() {
  const feed = document.getElementById("forum-feed");
  feed.innerHTML = state.posts.length ? state.posts.map(renderPost).join("") : renderPostsEmptyState();
}

function renderFeedLoading() {
  document.getElementById("forum-feed").innerHTML = `
    <div class="bg-white rounded-2xl border border-[#8c5a3c]/15 shadow-lg shadow-[#8c5a3c]/10 p-6 animate-pulse space-y-3">
      <div class="h-4 w-1/3 rounded-full bg-[#fff8f0]"></div>
      <div class="h-3 w-2/3 rounded-full bg-[#fff8f0]"></div>
      <div class="h-3 w-1/2 rounded-full bg-[#fff8f0]"></div>
    </div>`;
}

function renderCourseTabs() {
  const tabs = document.getElementById("forum-course-tabs");
  const countEl = document.getElementById("forum-course-count");

  if (!state.courses.length) {
    countEl.textContent = "";
    const isLecturer = state.user?.role === "lecturer";
    tabs.innerHTML = `<div class="w-full">${renderEmptyState({
      title: "No courses available yet",
      subtitle: isLecturer
        ? "Create a course from your dashboard to open its forum."
        : "Once a lecturer approves your enrollment, the course forum will appear here.",
    })}</div>`;
    return;
  }

  countEl.textContent = `${state.courses.length} course${state.courses.length === 1 ? "" : "s"}`;
  tabs.innerHTML = state.courses
    .map((course) => {
      const active = course.id === state.courseId;
      const cls = active
        ? "bg-[#4b2e2b] text-[#fff8f0] shadow-sm"
        : "bg-white border border-[#8c5a3c]/20 text-[#8c5a3c] hover:border-[#8c5a3c] hover:text-[#4b2e2b]";
      return `<button type="button" role="tab" aria-selected="${active}" data-course-id="${escapeHtml(course.id)}"
        class="forum-course-tab px-4 py-2 rounded-full text-xs font-semibold transition ${cls}">${escapeHtml(course.name)}</button>`;
    })
    .join("");
}

function renderSignedOut() {
  document.getElementById("forum-course-tabs").innerHTML = `
    <div class="w-full">${renderEmptyState({
      title: "Please log in to view your course forums",
      subtitle: "Forums are private to each course's lecturer and approved students.",
    })}
      <div class="flex justify-center mt-4">
        <a href="/login" class="bg-[#c08552] hover:bg-[#8c5a3c] text-white text-sm font-semibold px-6 py-2.5 rounded-2xl transition shadow-md shadow-[#c08552]/20">Go to Login</a>
      </div>
    </div>`;
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

async function loadCourses() {
  const uid = userId();
  if (state.user?.role === "lecturer") {
    const all = await api.listCourses();
    return all.filter((c) => c.lecturer_id === uid);
  }
  const all = await api.listCourses(uid);
  return all.filter((c) => c.enrollment_status === "approved");
}

async function selectCourse(courseId) {
  state.courseId = courseId;
  localStorage.setItem(LAST_COURSE_KEY, courseId);
  renderCourseTabs();

  const course = currentCourse();
  document.getElementById("forum-composer").classList.remove("hidden");
  document.getElementById("forum-composer-course").textContent = course?.name || "";

  const token = ++state.loadToken;
  renderFeedLoading();
  try {
    const posts = await api.listCoursePosts(courseId, userId());
    if (token !== state.loadToken) return; // user switched course meanwhile
    state.posts = posts;
    renderFeed();
  } catch (err) {
    if (token !== state.loadToken) return;
    state.posts = [];
    document.getElementById("forum-feed").innerHTML = renderEmptyState({
      title: "Couldn't load this course's discussions",
      subtitle: err.friendlyMessage || "Please try again in a moment.",
    });
    showToast(err.friendlyMessage || "Unable to load course posts", "error");
  }
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

async function handleNewPost(e) {
  e.preventDefault();
  if (!state.courseId) {
    showToast("Please select a course first.", "warning");
    return;
  }
  const titleEl = document.getElementById("forum-post-title");
  const contentEl = document.getElementById("forum-post-content");
  const submitBtn = document.getElementById("forum-post-submit");
  const title = titleEl.value.trim();
  const content = contentEl.value.trim();
  if (!title || !content) {
    showToast("Please add both a title and a message.", "warning");
    return;
  }

  const courseIdAtSubmit = state.courseId;
  submitBtn.disabled = true;
  try {
    const created = await api.createCoursePost(courseIdAtSubmit, {
      author_id: userId(),
      title,
      content,
    });
    titleEl.value = "";
    contentEl.value = "";

    if (state.courseId === courseIdAtSubmit) {
      const feed = document.getElementById("forum-feed");
      if (!state.posts.length) feed.innerHTML = ""; // clear empty state
      state.posts.unshift(created);
      feed.insertAdjacentHTML("afterbegin", renderPost(created));
    }
    showToast("Discussion posted!", "success");
  } catch (err) {
    showToast(err.friendlyMessage || "Unable to create post", "error");
  } finally {
    submitBtn.disabled = false;
  }
}

async function handleReply(form) {
  const postId = Number(form.dataset.postId);
  const input = form.elements.content;
  const button = form.querySelector("button[type=submit]");
  const content = input.value.trim();
  if (!content) {
    showToast("Please write a reply before sending.", "warning");
    return;
  }

  button.disabled = true;
  try {
    const comment = await api.createPostComment(postId, { author_id: userId(), content });
    input.value = "";

    const post = state.posts.find((p) => p.id === postId);
    if (post) {
      post.comments = post.comments || [];
      post.comments.push(comment);
    }
    const article = form.closest("article");
    article.querySelector('[data-role="comment-list"]').insertAdjacentHTML("beforeend", renderComment(comment));
    article.querySelector('[data-role="reply-count"]').textContent = replyCountLabel(post ? post.comments.length : 1);
    showToast("Reply added!", "success");
  } catch (err) {
    showToast(err.friendlyMessage || "Unable to add reply", "error");
  } finally {
    button.disabled = false;
  }
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", async () => {
  const backLink = document.getElementById("forum-back-dashboard-link");
  if (!state.user || !userId()) {
    renderSignedOut();
    return;
  }

  backLink.href = state.user.role === "lecturer" ? "/lecturer_dashboard" : "/student_dashboard";
  document.getElementById("forum-user-label").textContent =
    `Signed in as ${state.user.full_name || userId()} · ${state.user.role === "lecturer" ? "Lecturer" : "Student"}`;

  document.getElementById("forum-course-tabs").addEventListener("click", (e) => {
    const tab = e.target.closest(".forum-course-tab");
    if (tab && tab.dataset.courseId !== state.courseId) selectCourse(tab.dataset.courseId);
  });
  document.getElementById("forum-post-form").addEventListener("submit", handleNewPost);
  document.getElementById("forum-feed").addEventListener("submit", (e) => {
    const form = e.target.closest('form[data-role="reply-form"]');
    if (!form) return;
    e.preventDefault();
    handleReply(form);
  });

  try {
    state.courses = await loadCourses();
  } catch (err) {
    state.courses = [];
    showToast(err.friendlyMessage || "Unable to load your courses", "error");
  }
  renderCourseTabs();

  if (!state.courses.length) {
    document.getElementById("forum-feed").innerHTML = "";
    return;
  }
  const remembered = localStorage.getItem(LAST_COURSE_KEY);
  const initial = state.courses.some((c) => c.id === remembered) ? remembered : state.courses[0].id;
  await selectCourse(initial);
});
