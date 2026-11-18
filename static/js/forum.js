/**
 * Class Q&A / Blog Feed controller for static/forum.html.
 */

import { api } from "./api.js";
import { escapeHtml, renderEmptyState, renderSafeMarkdown, showToast } from "./ui.js";
import { SmartClassSocket } from "./ws.js";

const state = {
  filter: "all",
  posts: [],
  ws: new SmartClassSocket("global"),
};

function badgeForType(postType) {
  switch (postType) {
    case "ai_summary":
      return `<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#c08552]/20 text-[#4b2e2b]">AI Summary</span>`;
    case "note":
      return `<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#fff8f0] border border-[#8c5a3c]/30 text-[#8c5a3c]">Note</span>`;
    default:
      return `<span class="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[#4b2e2b] text-[#fff8f0]">Question</span>`;
  }
}

function renderFeed() {
  const feed = document.getElementById("forum-feed");
  const visible = state.posts.filter(
    (p) => p.post_type !== "private_message" && (state.filter === "all" || p.post_type === state.filter)
  );

  if (!visible.length) {
    feed.innerHTML = renderEmptyState({
      title: "No posts found",
      subtitle: "Ask a question, share a lecture note, or upload a recording to publish an AI summary.",
    });
    return;
  }

  feed.innerHTML = visible
    .map(
      (post) => `
    <article class="bg-white rounded-2xl border border-[#8c5a3c]/15 shadow-lg shadow-[#8c5a3c]/10 p-6 space-y-3">
      <div class="flex items-center justify-between gap-2 flex-wrap">
        <div class="flex items-center gap-2.5">
          <span class="font-bold text-sm text-[#4b2e2b]">${escapeHtml(post.author_name || post.author)}</span>
          <span class="text-xs text-[#8c5a3c] capitalize">${escapeHtml(post.author_role || "student")}</span>
          ${badgeForType(post.post_type)}
        </div>
        <span class="text-xs text-[#8c5a3c]">${new Date(post.created_at || post.timestamp).toLocaleString()}</span>
      </div>
      <div class="text-sm text-[#4b2e2b]/90 leading-relaxed space-y-1">
        ${post.post_type === "ai_summary" ? renderSafeMarkdown(post.content) : `<div class="whitespace-pre-wrap">${escapeHtml(post.content)}</div>`}
      </div>
    </article>`
    )
    .join("");
}

async function loadPosts() {
  try {
    state.posts = await api.listForumPosts();
    renderFeed();
  } catch (err) {
    showToast(err.friendlyMessage || "Unable to load forum posts", "error");
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  const currentUser = JSON.parse(localStorage.getItem("smartclass_user") || "null");
  const backLink = document.getElementById("forum-back-dashboard-link");
  if (backLink && currentUser) {
    backLink.href = currentUser.role === "lecturer" ? "/lecturer_dashboard" : "/student_dashboard";
  }

  if (currentUser) {
    document.getElementById("forum-author-name").value = currentUser.full_name || "";
    document.getElementById("forum-author-role").value = currentUser.role === "lecturer" ? "lecturer" : "student";
  }

  await loadPosts();

  const statusEl = document.getElementById("forum-ws-status");
  state.ws.onStatusChange = (s) => {
    statusEl.textContent = s === "connected" ? "Live updates active" : "Reconnecting...";
  };
  state.ws.on("NEW_FORUM_POST", (post) => {
    const normalized = {
      id: post.id,
      author_name: post.author,
      author_role: post.author_role || "student",
      post_type: post.post_type || "question",
      content: post.content,
      created_at: post.timestamp,
    };
    state.posts.unshift(normalized);
    renderFeed();
  });
  state.ws.connect("global");

  document.querySelectorAll(".forum-filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.filter = btn.dataset.filter;
      document.querySelectorAll(".forum-filter-btn").forEach((b) => {
        b.className =
          "forum-filter-btn px-4 py-2 rounded-full text-xs font-semibold bg-white border border-[#8c5a3c]/20 text-[#8c5a3c] hover:text-[#4b2e2b] transition";
      });
      btn.className =
        "forum-filter-btn px-4 py-2 rounded-full text-xs font-semibold bg-[#4b2e2b] text-[#fff8f0] transition shadow-sm";
      renderFeed();
    });
  });

  document.getElementById("forum-post-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const authorName = document.getElementById("forum-author-name").value.trim();
    const content = document.getElementById("forum-content").value.trim();
    if (!authorName || !content) {
      showToast("Please enter your name and post content.", "warning");
      return;
    }
    try {
      const created = await api.createForumPost({
        author_name: authorName,
        author_role: document.getElementById("forum-author-role").value,
        post_type: document.getElementById("forum-post-type").value,
        content,
      });
      document.getElementById("forum-content").value = "";
      if (!state.posts.some((p) => p.id === created.id)) {
        state.posts.unshift(created);
        renderFeed();
      }
      showToast("Posted to class feed!", "success");
    } catch (err) {
      showToast(err.friendlyMessage || "Unable to submit post", "error");
    }
  });
});
