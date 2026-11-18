/**
 * Axios API wrapper and interceptors for SmartClass AI.
 */

const apiClient = axios.create({
  baseURL: "",
  timeout: 60000,
});

// Normalize expired-token errors (403 / 410) for consistent UI messaging.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const detail = error?.response?.data?.detail || error.message || "Request failed";
    if (status === 403 || status === 410) {
      error.isWindowExpired = true;
      error.friendlyMessage = detail || "The 5-minute submission window has closed.";
    } else {
      error.friendlyMessage = detail;
    }
    return Promise.reject(error);
  }
);

export const api = {
  // Auth & Sessions
  login(payload) {
    return apiClient.post("/api/auth/login", payload).then((r) => r.data);
  },
  startSession(payload) {
    return apiClient.post("/api/session/start", payload).then((r) => r.data);
  },
  listSessions() {
    return apiClient.get("/api/sessions").then((r) => r.data);
  },
  getSessionReport(sessionId) {
    return apiClient.get(`/api/sessions/${encodeURIComponent(sessionId)}/report`).then((r) => r.data);
  },

  // Courses & Enrollments
  listCourses(studentId = null) {
    const params = studentId ? { student_id: studentId } : {};
    return apiClient.get("/api/courses", { params }).then((r) => r.data);
  },
  createCourse(payload) {
    return apiClient.post("/api/courses", payload).then((r) => r.data);
  },
  requestEnrollment(studentId, courseId) {
    return apiClient
      .post("/api/enroll", { student_id: studentId, course_id: courseId })
      .then((r) => r.data);
  },
  listPendingEnrollments() {
    return apiClient.get("/api/enroll/pending").then((r) => r.data);
  },
  approveEnrollment(enrollmentId) {
    return apiClient
      .post("/api/enroll/approve", { enrollment_id: enrollmentId })
      .then((r) => r.data);
  },

  // Attendance
  uploadAttendanceFrame(sessionId, fileBlob, filename = "frame.jpg", intervalSeconds = 5) {
    const formData = new FormData();
    formData.append("session_id", sessionId);
    formData.append("interval_seconds", String(intervalSeconds));
    formData.append("file", fileBlob, filename);
    return apiClient.post("/api/attendance/frame", formData).then((r) => r.data);
  },
  getAttendanceStatus(sessionId) {
    return apiClient.get(`/api/attendance/status/${encodeURIComponent(sessionId)}`).then((r) => r.data);
  },
  stopAttendance(sessionId) {
    return apiClient
      .post(`/api/attendance/stop`, null, { params: { session_id: sessionId } })
      .then((r) => r.data);
  },
  async downloadAttendanceCsv(sessionId) {
    const response = await apiClient.get("/api/attendance/export", {
      params: { session_id: sessionId },
      responseType: "blob",
    });
    const url = window.URL.createObjectURL(new Blob([response.data], { type: "text/csv" }));
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `attendance_${sessionId}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },

  // Quiz
  uploadQuizExcel(file, sessionId = null) {
    const formData = new FormData();
    formData.append("file", file);
    if (sessionId) formData.append("session_id", sessionId);
    return apiClient.post("/api/quiz/upload-excel", formData).then((r) => r.data);
  },
  listQuestions() {
    return apiClient.get("/api/quiz/questions").then((r) => r.data);
  },
  triggerQuestion(sessionId, questionId = null, lecturerId = null) {
    return apiClient
      .post("/api/quiz/trigger", {
        session_id: sessionId,
        question_id: questionId,
        lecturer_id: lecturerId,
      })
      .then((r) => r.data);
  },
  getTokenQuestion(token) {
    return apiClient.get(`/api/quiz/token/${encodeURIComponent(token)}`).then((r) => r.data);
  },
  submitQuizAnswer(payload) {
    return apiClient.post("/api/quiz/submit", payload).then((r) => r.data);
  },

  // Polls
  createPoll(payload) {
    return apiClient.post("/api/poll/create", payload).then((r) => r.data);
  },
  listSessionPolls(sessionId) {
    return apiClient.get(`/api/poll/${encodeURIComponent(sessionId)}`).then((r) => r.data);
  },
  votePoll(payload) {
    return apiClient.post("/api/poll/vote", payload).then((r) => r.data);
  },

  // Forum
  listForumPosts(params = {}) {
    return apiClient.get("/api/forum/posts", { params }).then((r) => r.data);
  },
  createForumPost(payload) {
    return apiClient.post("/api/forum/posts", payload).then((r) => r.data);
  },

  // AI Workflows
  summarizeLecture(file, sessionId, courseName, onUploadProgress) {
    const formData = new FormData();
    formData.append("file", file);
    if (sessionId) formData.append("session_id", sessionId);
    if (courseName) formData.append("course_name", courseName);
    return apiClient
      .post("/api/ai/summarize-lecture", formData, { onUploadProgress })
      .then((r) => r.data);
  },
  listSummaries() {
    return apiClient.get("/api/ai/summaries").then((r) => r.data);
  },
  reviewHomework(repoUrls, sessionId = null) {
    return apiClient
      .post("/api/ai/review-homework", { session_id: sessionId, repo_urls: repoUrls })
      .then((r) => r.data);
  },
  listHomeworkReviews() {
    return apiClient.get("/api/ai/reviews").then((r) => r.data);
  },
};
