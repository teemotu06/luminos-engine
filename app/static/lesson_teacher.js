(() => {
  window.teacherShell = (config = {}) => ({
    lessonId: config.lessonId || "",
    attemptId: config.attemptId || "",
    initialSlideId: config.initialSlideId || "",
    classId: config.classId || "",
    className: config.className || "",
    initialState: config.initialState || null,
    roster: config.roster || [],
    slides: config.slides || [],
    slideTitles: config.slideTitles || {},
    activeSlideIndex: 0,
    stateVersion: 0,
    audioEventId: 0,
    uiEventId: 0,
    currentState: "idle",
    currentStudent: "",
    promptText: "",
    boardPromptText: "",
    teacherPromptText: "",
    queuePosition: 0,
    queueTotal: 0,
    markRequired: false,
    advanceBlocked: false,
    reteachQueue: [],
    nextStudents: [],
    teacherControls: [],
    paused: false,
    stateTimeoutMs: null,
    stateStartedAt: "",
    timerLabel: "",
    autoAdvanceTimer: null,
    lastResult: "",
    clientStatusMessage: "",
    clientStatusTone: "neutral",
    retryClientLabel: "",
    retryClientAction: null,
    connectionStatus: "connecting",
    consecutiveFailures: 0,
    pollTimer: null,
    studentStatuses: {},
    get activeSlideId() {
      return this.slides[this.activeSlideIndex] || "";
    },

    get activeSlideTitle() {
      return this.slideTitles[this.activeSlideId] || "";
    },

    get queueSummary() {
      if (!this.queueTotal) return "0 / 0";
      return `${Math.min(this.queuePosition, this.queueTotal)} / ${this.queueTotal}`;
    },

    get currentStateLabel() {
      return this.currentState.replaceAll("_", " ");
    },

    get connectionLabel() {
      if (this.connectionStatus === "ok") return "Connected";
      if (this.connectionStatus === "degraded") return "Reconnecting";
      return "Connecting";
    },

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
      if (!this.retryClientAction) return;
      await this.retryClientAction();
    },

    init() {
      this.startTimerTicker();
      if (this.initialSlideId) {
        const initialIndex = this.slides.indexOf(this.initialSlideId);
        if (initialIndex !== -1) {
          this.activeSlideIndex = initialIndex;
        }
      }
      if (this.initialState) {
        this.applyState(this.initialState);
        this.connectionStatus = "ok";
      }
      void this.poll();
      this.pollTimer = window.setInterval(() => {
        void this.poll();
      }, 500);
    },

    destroy() {
      if (this.autoAdvanceTimer) {
        window.clearTimeout(this.autoAdvanceTimer);
        this.autoAdvanceTimer = null;
      }
      if (this.pollTimer) {
        window.clearInterval(this.pollTimer);
        this.pollTimer = null;
      }
    },

    startTimerTicker() {
      window.setInterval(() => {
        this.refreshTimerLabel();
      }, 250);
    },

    refreshTimerLabel() {
      if (!this.stateTimeoutMs || !this.stateStartedAt || this.paused) {
        this.timerLabel = "";
        return;
      }
      const startedAt = Date.parse(this.stateStartedAt);
      if (!Number.isFinite(startedAt)) {
        this.timerLabel = "";
        return;
      }
      const remaining = Math.max(0, startedAt + this.stateTimeoutMs - Date.now());
      this.timerLabel = `${(remaining / 1000).toFixed(1)}s`;
    },

    scheduleTimedAdvance() {
      if (this.autoAdvanceTimer) {
        window.clearTimeout(this.autoAdvanceTimer);
        this.autoAdvanceTimer = null;
      }
      if (!this.stateTimeoutMs || this.paused || this.markRequired) {
        return;
      }
      const startedAt = Date.parse(this.stateStartedAt || "");
      if (!Number.isFinite(startedAt)) return;
      const remaining = Math.max(0, startedAt + this.stateTimeoutMs - Date.now());
      this.autoAdvanceTimer = window.setTimeout(() => {
        this.autoAdvanceTimer = null;
        void this.handleControl("force_advance");
      }, remaining);
    },

    async poll() {
      if (!this.activeSlideId) return;
      try {
        const response = await fetch(
          `/lesson/${this.lessonId}/command-state/${this.attemptId}?slide_id=${encodeURIComponent(this.activeSlideId)}`
        );
        if (!response.ok) {
          throw new Error(`Command state request failed (${response.status})`);
        }
        const data = await response.json();
        this.applyState(data);
        this.connectionStatus = "ok";
        this.consecutiveFailures = 0;
        if (this.clientStatusTone === "error") {
          this.clearClientStatus();
        }
      } catch (error) {
        this.consecutiveFailures += 1;
        this.connectionStatus = this.consecutiveFailures >= 3 ? "degraded" : "connecting";
        this.lastResult = error.message;
        this.setRetryClientAction("Retry connection", () => this.poll());
        this.setClientStatus(error.message, "error");
      }
    },

    applyState(data) {
      const previousState = this.currentState;
      const previousStartedAt = this.stateStartedAt;
      if (data.slide_id) {
        const nextIndex = this.slides.indexOf(data.slide_id);
        if (nextIndex !== -1) {
          this.activeSlideIndex = nextIndex;
        }
      }
      this.stateVersion = data.state_version || 0;
      this.audioEventId = data.audio_event_id || 0;
      this.uiEventId = data.ui_event_id || 0;
      this.currentState = data.current_state || "idle";
      this.currentStudent = data.current_student || "";
      this.promptText = data.teacher_prompt_text || data.prompt_text || "";
      this.boardPromptText = data.prompt_text || "";
      this.queuePosition = data.queue_position || 0;
      this.queueTotal = data.queue_total || 0;
      this.markRequired = !!data.mark_required;
      this.advanceBlocked = !!data.advance_blocked;
      this.reteachQueue = data.reteach_queue || [];
      this.nextStudents = data.next_students || [];
      this.teacherControls = data.teacher_controls || [];
      this.paused = !!data.paused;
      this.stateTimeoutMs = data.state_timeout_ms || null;
      this.stateStartedAt = data.state_started_at || "";
      this.studentStatuses = {
        ...this.studentStatuses,
        ...(this.currentStudent && this.currentState === "complete" ? { [this.currentStudent]: "complete" } : {}),
      };
      this.refreshTimerLabel();
      if (this.currentState !== previousState || this.stateStartedAt !== previousStartedAt || this.paused) {
        this.scheduleTimedAdvance();
      }
    },

    async syncActiveSlide() {
      if (!this.activeSlideId) return;
      const response = await fetch(`/lesson/${this.lessonId}/command-state/${this.attemptId}/active-slide`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ slide_id: this.activeSlideId }),
      });
      if (!response.ok) {
        throw new Error(`Slide sync failed (${response.status})`);
      }
    },

    controlLabel(control) {
      const labels = {
        mark_secure: "Secure",
        mark_shaky: "Shaky",
        mark_missed: "Missed",
        mark_deferred: "Deferred",
        mark_absent: "Absent",
        mark_class: "Class mark",
        skip: "Skip",
        replay: "Replay",
        pause: this.paused ? "Resume" : "Pause",
        force_advance: "Advance",
      };
      return labels[control] || control.replaceAll("_", " ");
    },

    async handleControl(control) {
      let payload = { slide_id: this.activeSlideId, action: "force_advance" };
      if (control.startsWith("mark_")) {
        if (control === "mark_class") {
          payload = { slide_id: this.activeSlideId, action: "mark_class", status: "secure" };
        } else {
          const status = control.replace("mark_", "");
          payload = { slide_id: this.activeSlideId, action: "mark", student: this.currentStudent, status };
          if (this.currentStudent) {
            this.studentStatuses = { ...this.studentStatuses, [this.currentStudent]: status };
          }
        }
      } else if (control === "skip") {
        payload = { slide_id: this.activeSlideId, action: "skip", student: this.currentStudent };
        if (this.currentStudent) {
          this.studentStatuses = { ...this.studentStatuses, [this.currentStudent]: "deferred" };
        }
      } else if (control === "replay") {
        payload = { slide_id: this.activeSlideId, action: "replay" };
      } else if (control === "pause") {
        payload = { slide_id: this.activeSlideId, action: this.paused ? "resume" : "pause" };
      } else if (control === "force_advance") {
        payload = { slide_id: this.activeSlideId, action: "force_advance" };
      }

      try {
        const response = await fetch(`/lesson/${this.lessonId}/command-state/${this.attemptId}/advance`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!response.ok) {
          throw new Error(`Teacher action failed (${response.status})`);
        }
        this.applyState(await response.json());
        this.lastResult = this.controlLabel(control);
        this.clearClientStatus();
      } catch (error) {
        this.lastResult = error.message;
        this.setRetryClientAction("Retry action", () => this.handleControl(control));
        this.setClientStatus(error.message, "error");
      }
    },

    async goPrevSlide() {
      if (this.activeSlideIndex <= 0) return;
      this.activeSlideIndex -= 1;
      this.lastResult = "";
      this.clearClientStatus();
      try {
        await this.syncActiveSlide();
      } catch (error) {
        this.lastResult = error.message;
        this.setRetryClientAction("Retry slide sync", () => this.syncActiveSlide());
        this.setClientStatus(error.message, "error");
      }
      void this.poll();
    },

    async goNextSlide() {
      if (this.activeSlideIndex >= this.slides.length - 1) return;
      this.activeSlideIndex += 1;
      this.lastResult = "";
      this.clearClientStatus();
      try {
        await this.syncActiveSlide();
      } catch (error) {
        this.lastResult = error.message;
        this.setRetryClientAction("Retry slide sync", () => this.syncActiveSlide());
        this.setClientStatus(error.message, "error");
      }
      void this.poll();
    },
  });
})();
