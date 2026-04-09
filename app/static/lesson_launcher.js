(() => {
  window.launcherShell = () => ({
    selectedClassId: "",
    attemptIds: {},
    lessonProgress: {},
    masteryGates: {},
    classReviewMap: {},
    libraryError: "",

    init() {
      const mapNode = document.getElementById("class-review-map");
      if (mapNode && mapNode.textContent) {
        try {
          this.classReviewMap = JSON.parse(mapNode.textContent);
        } catch (_error) {
          this.classReviewMap = {};
        }
      }
      this.$watch("selectedClassId", (val) => {
        void this.fetchProgress(val);
        void this.fetchMasteryGates(val);
      });
    },

    async fetchProgress(classId) {
      if (!classId) { this.lessonProgress = {}; return; }
      try {
        const response = await fetch("/lesson/progress?class_id=" + encodeURIComponent(classId));
        if (!response.ok) throw new Error("Failed to load lesson progress");
        this.lessonProgress = await response.json();
      } catch (_error) {
        this.lessonProgress = {};
        this.libraryError = "Lesson progress is temporarily unavailable.";
      }
    },

    async fetchMasteryGates(classId) {
      if (!classId) { this.masteryGates = {}; return; }
      try {
        const response = await fetch("/lesson/mastery-gates?class_id=" + encodeURIComponent(classId));
        if (!response.ok) throw new Error("Failed to load mastery gates");
        this.masteryGates = await response.json();
      } catch (_error) {
        this.masteryGates = {};
        this.libraryError = "Mastery gate data is temporarily unavailable.";
      }
    },

    reviewFor(lessonId) {
      if (!this.selectedClassId) return null;
      return (this.classReviewMap[this.selectedClassId] || {})[lessonId] || null;
    },

    gateFor(lessonId) {
      if (!this.selectedClassId) return null;
      return this.masteryGates[lessonId] || null;
    },

    gateChipLabel(lessonId) {
      const gate = this.gateFor(lessonId);
      if (!gate) return "";
      const labels = {
        proceed: "Proceed",
        caution: "Caution",
        reteach: "Re-teach",
        repeat: "Repeat",
        no_data: "No data",
      };
      return labels[gate.gate_level] || gate.gate_label || "";
    },

    lessonUrl(lessonId, mode) {
      return this.lessonUrlForAttempt(lessonId, mode, "");
    },

    lessonUrlForAttempt(lessonId, mode, attemptId) {
      const m = mode || "lesson";
      const params = new URLSearchParams();
      if (this.selectedClassId) params.set("class_id", this.selectedClassId);
      if (attemptId) params.set("attempt_id", attemptId);
      const query = params.toString() ? "?" + params.toString() : "";
      if (m === "teacher") {
        if (!this.selectedClassId) return "";
        return "/classes/" + encodeURIComponent(this.selectedClassId) + "/control?lesson_id=" + encodeURIComponent(lessonId);
      }
      if (m === "board") {
        if (!this.selectedClassId) return "";
        return "/classes/" + encodeURIComponent(this.selectedClassId) + "/board";
      }
      return "/lesson/" + lessonId + (this.selectedClassId ? "?class_id=" + encodeURIComponent(this.selectedClassId) : "");
    },

    attemptCacheKey(lessonId) {
      return lessonId + "::" + (this.selectedClassId || "");
    },

    async ensureAttemptId(lessonId) {
      const cacheKey = this.attemptCacheKey(lessonId);
      if (this.attemptIds[cacheKey]) return this.attemptIds[cacheKey];
      const suffix = this.selectedClassId
        ? "?class_id=" + encodeURIComponent(this.selectedClassId)
        : "";
      const response = await fetch("/lesson/" + lessonId + "/attempt" + suffix, {
        method: "POST",
      });
      if (!response.ok) throw new Error("Failed to create lesson attempt");
      const data = await response.json();
      this.attemptIds[cacheKey] = data.attempt_id || "";
      return this.attemptIds[cacheKey];
    },

    async openLesson(lessonId, mode) {
      const m = mode || "lesson";
      if (m === "lesson") {
        window.location.assign(this.lessonUrl(lessonId, m));
        return;
      }

      if (!this.selectedClassId) {
        this.libraryError = "Select a class to open Teacher or Board.";
        return;
      }

      if (m === "teacher" || m === "board") {
        const targetUrl = this.lessonUrlForAttempt(lessonId, m, "");
        if (targetUrl) window.open(targetUrl, "_blank");
        return;
      }

      try {
        const attemptId = await this.ensureAttemptId(lessonId);
        window.open(this.lessonUrlForAttempt(lessonId, m, attemptId), "_blank");
      } catch (_error) {
        this.libraryError = "Lesson launch is temporarily unavailable.";
      }
    },
  });
})();
