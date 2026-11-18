/**
 * Unified Student & Lecturer login controller for static/login.html.
 */

import { api } from "./api.js";
import { showToast } from "./ui.js";

const state = {
  role: "student",
};

function dashboardPathForRole(role) {
  const params = new URLSearchParams(window.location.search);
  const redirect = params.get("redirect");
  if (redirect && role === "student" && redirect.startsWith("/")) {
    return redirect;
  }
  return role === "lecturer" ? "/lecturer_dashboard" : "/student_dashboard";
}

function setRole(role) {
  state.role = role;
  const studentBtn = document.getElementById("role-student-btn");
  const lecturerBtn = document.getElementById("role-lecturer-btn");
  const passwordWrap = document.getElementById("password-field-wrap");
  const passwordInput = document.getElementById("password-input");
  const submitBtn = document.getElementById("login-submit-btn");

  const activeCls = "role-btn py-2.5 rounded-xl text-sm font-semibold bg-[#c08552] text-white shadow-sm transition";
  const idleCls = "role-btn py-2.5 rounded-xl text-sm font-medium text-[#8c5a3c] hover:text-[#4b2e2b] transition";

  if (role === "lecturer") {
    lecturerBtn.className = activeCls;
    studentBtn.className = idleCls;
    passwordWrap.classList.remove("hidden");
    passwordInput.required = true;
    submitBtn.textContent = "Sign In as Lecturer";
  } else {
    studentBtn.className = activeCls;
    lecturerBtn.className = idleCls;
    passwordWrap.classList.add("hidden");
    passwordInput.required = false;
    passwordInput.value = "";
    submitBtn.textContent = "Sign In as Student";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const existing = JSON.parse(localStorage.getItem("smartclass_user") || "null");
  if (existing && existing.id_number && existing.role) {
    document.getElementById("already-signed-in").classList.remove("hidden");
    document.getElementById("current-user-label").textContent =
      `${existing.full_name || existing.id_number} (${existing.role})`;

    document.getElementById("continue-session-btn").addEventListener("click", () => {
      window.location.href = dashboardPathForRole(existing.role);
    });
    document.getElementById("switch-account-btn").addEventListener("click", () => {
      localStorage.removeItem("smartclass_user");
      localStorage.removeItem("smartclass_student");
      localStorage.removeItem("smartclass_lecturer");
      document.getElementById("already-signed-in").classList.add("hidden");
      showToast("Signed out cleanly.", "info");
    });
  }

  document.getElementById("role-student-btn").addEventListener("click", () => setRole("student"));
  document.getElementById("role-lecturer-btn").addEventListener("click", () => setRole("lecturer"));

  document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errorBox = document.getElementById("login-error");
    errorBox.classList.add("hidden");

    const idNumber = document.getElementById("id-number-input").value.trim();
    const fullName = document.getElementById("full-name-input").value.trim() || null;
    const password = document.getElementById("password-input").value || null;

    if (idNumber.length < 2) {
      showToast("Please enter a valid ID number.", "warning");
      return;
    }
    if (state.role === "lecturer" && !password) {
      showToast("Lecturer password is required.", "warning");
      return;
    }

    try {
      const user = await api.login({
        id_number: idNumber,
        full_name: fullName,
        role: state.role,
        password: state.role === "lecturer" ? password : null,
      });

      const sessionData = {
        id_number: user.id_number || user.user_id,
        user_id: user.user_id || user.id_number,
        full_name: user.full_name,
        role: user.role,
      };
      localStorage.setItem("smartclass_user", JSON.stringify(sessionData));
      if (user.role === "lecturer") {
        localStorage.setItem("smartclass_lecturer", JSON.stringify(sessionData));
      } else {
        localStorage.setItem("smartclass_student", JSON.stringify(sessionData));
      }

      window.location.href = dashboardPathForRole(user.role);
    } catch (err) {
      const msg = err.friendlyMessage || "Unable to sign in.";
      errorBox.textContent = msg;
      errorBox.classList.remove("hidden");
      showToast(msg, "error");
    }
  });
});
