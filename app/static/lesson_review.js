(() => {
  window.reviewShell = (config = {}) => ({
    attemptId: config.attemptId || "",
    lessonId: config.lessonId || "",
    marks: config.marks || {},
    editingKey: null,
    editStatus: "",
    editNote: "",
    isSaving: false,
    clientStatusMessage: "",
    clientStatusTone: "neutral",
    retryClientLabel: "",
    retryClientAction: null,

    setClientStatus(message, tone = "neutral") {
      this.clientStatusMessage = message || "";
      this.clientStatusTone = tone;
    },

    clearClientStatus() {
      this.clientStatusMessage = "";
      this.clientStatusTone = "neutral";
      this.retryClientLabel = "";
      this.retryClientAction = null;
    },

    setRetryClientAction(label, action) {
      this.retryClientLabel = label || "Retry";
      this.retryClientAction = typeof action === "function" ? action : null;
    },

    async retryClientRequest() {
      if (!this.retryClientAction || this.isSaving) return;
      await this.retryClientAction();
    },

    getMarkStatus(slideId, studentName) {
      return (this.marks[`${slideId}__${studentName}`] || {}).status || "";
    },

    hasNote(slideId, studentName) {
      return !!(this.marks[`${slideId}__${studentName}`] || {}).teacher_note;
    },

    openEdit(slideId, studentName) {
      const key = `${slideId}__${studentName}`;
      const existing = this.marks[key] || {};
      this.editingKey = key;
      this.editStatus = existing.status || "";
      this.editNote = existing.teacher_note || "";
    },

    closeEdit() {
      this.editingKey = null;
    },

    async saveEdit(slideId, studentName, blockId) {
      if (!this.editStatus) return;
      this.isSaving = true;
      this.clearClientStatus();
      this.setClientStatus("Saving review update…", "pending");
      const retryArgs = [slideId, studentName, blockId];
      try {
        const response = await fetch(`/lesson/${this.lessonId}/student-mark`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            attempt_id: this.attemptId,
            lesson_id: this.lessonId,
            slide_id: slideId,
            block_id: blockId,
            student_name: studentName,
            status: this.editStatus,
            teacher_note: this.editNote,
          }),
        });
        if (!response.ok) {
          throw new Error(`Review save failed (${response.status})`);
        }
        const key = `${slideId}__${studentName}`;
        this.marks[key] = {
          ...(this.marks[key] || {}),
          status: this.editStatus,
          teacher_note: this.editNote,
        };
        this.setClientStatus(`${studentName} · saved`, "success");
        this.closeEdit();
      } catch (err) {
        console.error("Review save failed:", err);
        this.setRetryClientAction("Retry save", () => this.saveEdit(...retryArgs));
        this.setClientStatus(err.message || "Review save failed", "error");
      } finally {
        this.isSaving = false;
      }
    },
  });
})();
