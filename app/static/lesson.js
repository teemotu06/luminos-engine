(() => {
  const STATUS_PRIORITY = { secure: 0, shaky: 1, missed: 2, skipped: 3 };
  const OralPromptHelper = window.OralPromptHelper || {};

  window.lessonShell = (config = {}) => ({
    activeBlendIndex: -1,
    activeSlideIndex: Number(config.initialSlideIndex || 0),
    attemptId: config.attemptId || "",
    classLabel: config.className || "",
    audioPlayers: {},
    audioUnlocked: false,
    blendTimer: null,
    isSubmitting: false,
    lastMarkingResult: "",
    lastOralPromptAudioUrl: "",
    oralPromptRequestToken: 0,
    oralPromptSpeakTimeout: null,
    lastSpokenOralPromptKey: "",
    lessonId: config.lessonId || "",
    oralPromptPaused: false,
    quickCheckMarks: {},
    revealed: false,
    roster: config.roster || [],
    slideMarks: {},
    studentMarks: {},
    topDockOpen: false,
    topDockTimer: null,
    ttsAudioCache: {},
    comprehensionRound: {
      enabled: false,
      turns: [],
      activeTurnIndex: -1,
      completedCount: 0,
    },
    oralCheck: {
      enabled: false,
      initializedSlideId: "",
      sessionId: "",
      phase: "idle",
      phaseLabel: "",
      taskLabel: "",
      boardPromptTitle: "",
      boardPromptBody: "",
      teacherScript: "",
      progressLabel: "",
      auditSelectionStrategy: "roster_order",
      resolvedStudentCount: 0,
      requiredStudentCount: 0,
      activeAssignmentId: "",
      activeStudentName: "",
      activePerformanceType: "",
      unresolvedStudentCount: 0,
      sessionStatus: "idle",
      assignments: [],
    },

    get activeBlockId() {
      return this.currentSlideElement()?.dataset.blockId || null;
    },

    get activeBlockLabel() {
      return this.currentSlideElement()?.dataset.blockLabel || "";
    },

    get activeSlideTitle() {
      return this.currentSlideElement()?.dataset.slideTitle || "";
    },

    activeSlideId() {
      return this.currentSlideElement()?.dataset.slideId || "";
    },

    get progressPercent() {
      const frames = this.slideFrames();
      if (!frames.length) return 0;
      return ((this.activeSlideIndex + 1) / frames.length) * 100;
    },

    get revealHintLabel() {
      if (window.matchMedia?.("(pointer: coarse)").matches) {
        return "Tap to reveal";
      }
      return "Click to reveal";
    },

    clampSlideIndex(index) {
      const frames = this.slideFrames();
      if (!frames.length) return 0;
      return Math.max(0, Math.min(index, frames.length - 1));
    },

    oralCheckConfigForSlide(slideIndex) {
      const el = document.querySelector(`.lesson-slide-frame[data-slide-index="${slideIndex}"]`);
      if (!el || el.dataset.oralCheckEligible !== "true") return null;
      const configRaw = el.dataset.oralCheckConfig;
      if (!configRaw || configRaw === "null") {
        return {
          enabled: true,
          participation_mode: "full_roster",
          text_length_mode: "normal",
          rehearsal_seconds: 30,
          required_evidence_count: 1,
          audit_sample_size: 0,
          audit_selection_strategy: "roster_order",
        };
      }
      try {
        return JSON.parse(configRaw);
      } catch (_error) {
        return {
          enabled: true,
          participation_mode: "full_roster",
          text_length_mode: "normal",
          rehearsal_seconds: 30,
          required_evidence_count: 1,
          audit_sample_size: 0,
          audit_selection_strategy: "roster_order",
        };
      }
    },

    slideLuminosSaysConfigForSlide(slideIndex) {
      const el = document.querySelector(`.lesson-slide-frame[data-slide-index="${slideIndex}"]`);
      if (!el) return null;
      const configRaw = el.dataset.luminosSays;
      if (!configRaw || configRaw === "null") return null;
      try {
        return JSON.parse(configRaw);
      } catch (_error) {
        return null;
      }
    },

    activeSlidePromptContext() {
      const el = this.currentSlideElement();
      const config = this.oralCheckConfigForSlide(this.activeSlideIndex) || {};
      const luminosSays = this.slideLuminosSaysConfigForSlide(this.activeSlideIndex) || {};
      const title = (el?.dataset.slideTitle || "").toLowerCase();
      const displayMode = (el?.dataset.displayMode || "").toLowerCase();
      const viewType = (el?.dataset.viewType || "").toLowerCase();
      const teacherCue = (el?.dataset.teacherCue || "").trim();
      const slidePromptText = (el?.dataset.promptText || "").trim();
      const frontText = (el?.dataset.frontText || "").trim();
      const targetWord = (el?.dataset.targetWord || "").trim();
      const targetSentence = (el?.dataset.targetSentence || "").trim();
      const dictatedText = (el?.dataset.dictatedText || "").trim();
      const quickCheckTitle = (el?.dataset.quickCheckTitle || "").trim();
      const comprehensionPrompt = (el?.dataset.comprehensionPrompt || "").trim();
      let comprehensionQuestions = [];
      try {
        comprehensionQuestions = JSON.parse(el?.dataset.comprehensionQuestions || "[]");
      } catch (_error) {
        comprehensionQuestions = [];
      }

      let promptMode = config.prompt_mode || "";
      if (!promptMode) {
        if (title.includes("retell")) promptMode = "retell";
        else if (title.includes("comprehension")) promptMode = "answer_question";
        else if (comprehensionQuestions.length || comprehensionPrompt) {
          const normalizedPrompt = (comprehensionQuestions[0] || comprehensionPrompt).toLowerCase();
          if (normalizedPrompt.includes("using the story") || normalizedPrompt.includes("use the story")) {
            promptMode = "answer_with_story";
          } else if (normalizedPrompt.includes("point to") || normalizedPrompt.includes("show me")) {
            promptMode = "show_and_explain";
          } else {
            promptMode = "answer_question";
          }
        } else if (displayMode === "reader") {
          promptMode = "read_story";
        } else {
          promptMode = "read_story";
        }
      }

      return {
        mode: promptMode,
        customText: (config.prompt_text || "").trim(),
        genericCustomText: (luminosSays.prompt_text || "").trim(),
        genericSupportText: (luminosSays.support_text || "").trim(),
        autoSpeak: luminosSays.auto_speak !== false,
        teacherCue,
        slidePromptText,
        viewType,
        title: el?.dataset.slideTitle || "",
        frontText,
        targetWord,
        targetSentence,
        dictatedText,
        quickCheckTitle,
        comprehensionPrompt,
        comprehensionQuestions,
      };
    },

    activeComprehensionTurn() {
      if (!this.comprehensionRound.enabled) return null;
      return this.comprehensionRound.turns[this.comprehensionRound.activeTurnIndex] || null;
    },

    normalizedQuestionPrompt(prompt = "") {
      return (OralPromptHelper.normalizeQuestionPrompt || ((value) => String(value || "").trim()))(prompt);
    },

    splitQuestionPrompt(prompt = "") {
      if (OralPromptHelper.splitQuestionPrompt) {
        return OralPromptHelper.splitQuestionPrompt(prompt);
      }
      return { primary: this.normalizedQuestionPrompt(prompt), secondary: "" };
    },

    currentSlideElement() {
      return document.querySelector(
        `.lesson-slide-frame[data-slide-index="${this.activeSlideIndex}"]`
      );
    },

    ensureQuickCheckItem(slideIndex, itemIndex) {
      if (!this.quickCheckMarks[slideIndex]) {
        this.quickCheckMarks[slideIndex] = {};
      }

      if (!this.quickCheckMarks[slideIndex][itemIndex]) {
        this.quickCheckMarks[slideIndex][itemIndex] = {
          status: "",
          errorTags: [],
          koreanTransfer: false,
        };
      }

      return this.quickCheckMarks[slideIndex][itemIndex];
    },

    ensureSlideMark(slideIndex) {
      if (!this.slideMarks[slideIndex]) {
        this.slideMarks[slideIndex] = {
          status: "",
          errorTags: [],
          koreanTransfer: false,
          teacherNote: "",
        };
      }

      return this.slideMarks[slideIndex];
    },

    getAudioPlayer(src) {
      if (!src) return null;

      if (!this.audioPlayers[src]) {
        const isTtsPrompt = src.includes("/tts-cache/");
        this.audioPlayers[src] = new Howl({
          src: [src],
          html5: !isTtsPrompt,
          preload: true,
        });
      }

      return this.audioPlayers[src];
    },

    async unlockAudio() {
      if (this.audioUnlocked) return;
      try {
        if (typeof Howler !== "undefined" && Howler.ctx && Howler.ctx.state === "suspended") {
          await Howler.ctx.resume();
        }
        this.audioUnlocked = true;
      } catch (_error) {
        // Ignore unlock failures; direct play attempts may still succeed.
      }
    },

    pauseAudio(src) {
      const player = this.getAudioPlayer(src);
      if (player && player.playing()) {
        player.pause();
      }
    },

    async fetchTtsPromptAudioUrl(text) {
      const normalized = String(text || "").trim();
      if (!normalized) return "";
      if (this.ttsAudioCache[normalized]) return this.ttsAudioCache[normalized];

      const response = await fetch("/lesson/tts/prompt", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: normalized }),
      });

      if (!response.ok) {
        let detail = `Local TTS request failed (${response.status})`;
        try {
          const data = await response.json();
          if (data?.detail) detail = data.detail;
        } catch (_error) {
          // Ignore parse failure and keep the generic message.
        }
        throw new Error(detail);
      }

      const data = await response.json();
      this.ttsAudioCache[normalized] = data.audio_url || "";
      return this.ttsAudioCache[normalized];
    },

    async speakOralPromptIfNeeded(force = false) {
      const comprehensionTurn = this.activeComprehensionTurn();
      const hasReadingPrompt =
        this.oralCheck.enabled && this.oralCheck.activeAssignmentId && this.oralCheck.activeStudentName;
      const hasGenericPrompt = !!this.genericLuminosPromptLine();
      if (!hasReadingPrompt && !comprehensionTurn && !hasGenericPrompt) {
        return;
      }

      const text = this.oralNotificationLine();
      if (!text) return;

      const promptKey = comprehensionTurn
        ? `comprehension:${this.activeSlideId()}:${this.comprehensionRound.activeTurnIndex}:${text}`
        : hasReadingPrompt
          ? `${this.oralCheck.sessionId}:${this.oralCheck.activeAssignmentId}:${text}`
          : `slide:${this.activeSlideId()}:${text}`;
      if (!force && this.lastSpokenOralPromptKey === promptKey) {
        return;
      }

      const requestToken = ++this.oralPromptRequestToken;

      try {
        await this.unlockAudio();
        const audioUrl = await this.fetchTtsPromptAudioUrl(text);
        if (!audioUrl) return;
        if (requestToken !== this.oralPromptRequestToken) return;
        const currentComprehensionTurn = this.activeComprehensionTurn();
        const currentPromptKey = currentComprehensionTurn
          ? `comprehension:${this.activeSlideId()}:${this.comprehensionRound.activeTurnIndex}:${this.oralNotificationLine()}`
          : (this.oralCheck.enabled && this.oralCheck.activeAssignmentId && this.oralCheck.activeStudentName)
            ? `${this.oralCheck.sessionId}:${this.oralCheck.activeAssignmentId}:${this.oralNotificationLine()}`
            : `slide:${this.activeSlideId()}:${this.oralNotificationLine()}`;
        if (!this.oralNotificationLine() || currentPromptKey !== promptKey) {
          return;
        }

        this.stopCurrentOralPrompt();
        this.lastSpokenOralPromptKey = promptKey;
        this.lastOralPromptAudioUrl = audioUrl;
        this.oralPromptPaused = false;
        this.playAudio(audioUrl);
        void this.prefetchUpcomingOralPrompt();
      } catch (error) {
        if (requestToken !== this.oralPromptRequestToken) return;
        console.error("Local Kokoro TTS failed:", error);
        this.lastMarkingResult = error.message;
      }
    },

    async playCurrentOralPrompt() {
      if (!this.oralNotificationLine()) {
        return;
      }

      const requestToken = ++this.oralPromptRequestToken;
      await this.unlockAudio();
      let audioUrl = this.lastOralPromptAudioUrl;
      if (!audioUrl) {
        audioUrl = await this.fetchTtsPromptAudioUrl(this.oralNotificationLine());
        if (requestToken !== this.oralPromptRequestToken) return;
        this.lastOralPromptAudioUrl = audioUrl;
      }
      if (!audioUrl) return;

      this.oralPromptPaused = false;
      this.stopCurrentOralPrompt();
      this.playAudio(audioUrl);
    },

    async prefetchTtsPromptAudio(text) {
      const normalized = String(text || "").trim();
      if (!normalized) return;
      try {
        await this.fetchTtsPromptAudioUrl(normalized);
      } catch (_error) {
        // Silent prefetch failure is acceptable; explicit play path will surface errors.
      }
    },

    nextOralPromptText() {
      const comprehensionTurn = this.activeComprehensionTurn();
      if (comprehensionTurn) {
        const nextTurn = this.comprehensionRound.turns.find((item, index) => index > this.comprehensionRound.activeTurnIndex && item.status === "pending");
        return nextTurn ? `${nextTurn.studentName}, ${nextTurn.prompt}` : "";
      }

      if (!this.oralCheck.enabled) return "";
      const currentIndex = this.oralCheck.assignments.findIndex((item) => String(item.assignment_id) === String(this.oralCheck.activeAssignmentId));
      const nextAssignment = this.oralCheck.assignments.find((item, index) => index > currentIndex && item.status === "pending");
      if (!nextAssignment) return "";

      const promptContext = {
        ...this.activeSlidePromptContext(),
        mode: "read_story",
        comprehensionPrompt: "",
      };
      return this.buildOralPromptLine({
        name: nextAssignment.student_name,
        promptContext,
        performanceType: nextAssignment.performance_type,
      });
    },

    async prefetchUpcomingOralPrompt() {
      const nextText = this.nextOralPromptText();
      if (!nextText) return;
      await this.prefetchTtsPromptAudio(nextText);
    },

    pauseCurrentOralPrompt() {
      if (!this.lastOralPromptAudioUrl) return;
      this.pauseAudio(this.lastOralPromptAudioUrl);
      this.oralPromptPaused = true;
    },

    stopCurrentOralPrompt() {
      if (!this.lastOralPromptAudioUrl) return;
      const player = this.getAudioPlayer(this.lastOralPromptAudioUrl);
      if (player) {
        player.stop();
      }
      this.oralPromptPaused = false;
    },

    clearPendingOralPromptWork() {
      this.oralPromptRequestToken += 1;
      if (this.oralPromptSpeakTimeout) {
        window.clearTimeout(this.oralPromptSpeakTimeout);
        this.oralPromptSpeakTimeout = null;
      }
      this.stopCurrentOralPrompt();
      this.lastSpokenOralPromptKey = "";
      this.lastOralPromptAudioUrl = "";
      this.oralPromptPaused = false;
    },

    scheduleOralPromptSpeak(delay = 80, force = false) {
      if (this.oralPromptSpeakTimeout) {
        window.clearTimeout(this.oralPromptSpeakTimeout);
      }
      const scheduledSlideId = this.activeSlideId();
      this.oralPromptSpeakTimeout = window.setTimeout(() => {
        this.oralPromptSpeakTimeout = null;
        if (this.activeSlideId() !== scheduledSlideId) return;
        void this.unlockAudio().then(() => this.speakOralPromptIfNeeded(force));
      }, delay);
    },

    getQuickCheckItemKoreanTransfer(slideIndex, itemIndex) {
      return this.ensureQuickCheckItem(slideIndex, itemIndex).koreanTransfer;
    },

    getQuickCheckItemMark(slideIndex, itemIndex) {
      return this.ensureQuickCheckItem(slideIndex, itemIndex).status;
    },

    getResponsiveTextStyle(text = "", mode = "default", scale = 1) {
      const normalizedText = String(text || "").trim();
      const charCount = normalizedText.length;
      const wordCount = normalizedText ? normalizedText.split(/\s+/).length : 0;

      let fontSize = 56;

      switch (mode) {
        case "sentence":
          if (charCount <= 8) fontSize = 96;
          else if (charCount <= 16) fontSize = 84;
          else if (charCount <= 28) fontSize = 72;
          else fontSize = 60;
          break;
        case "word":
          if (charCount <= 2) fontSize = 112;
          else if (charCount <= 4) fontSize = 96;
          else if (charCount <= 8) fontSize = 80;
          else fontSize = 64;
          break;
        case "choice":
          if (charCount <= 3) fontSize = 80;
          else if (charCount <= 8) fontSize = 64;
          else fontSize = 52;
          break;
        case "letter-card":
          fontSize = 56;
          break;
        case "word-card":
          if (charCount <= 3) fontSize = 42;
          else if (charCount <= 6) fontSize = 34;
          else fontSize = 28;
          break;
        case "prompt":
          if (charCount <= 24) fontSize = 28;
          else if (charCount <= 60) fontSize = 24;
          else fontSize = 20;
          break;
        default:
          if (wordCount <= 2 && charCount <= 12) fontSize = 56;
          else if (charCount <= 32) fontSize = 42;
          else fontSize = 32;
      }

      return `font-size: ${Math.round(fontSize * scale)}px;`;
    },

    getSlideKoreanTransfer(slideIndex) {
      return this.ensureSlideMark(slideIndex).koreanTransfer;
    },

    getSlideMark(slideIndex) {
      return this.ensureSlideMark(slideIndex).status;
    },

    getSlideTeacherNote(slideIndex) {
      return this.ensureSlideMark(slideIndex).teacherNote;
    },

    isActiveOralCheck(slideIndex, slideId) {
      return (
        this.activeSlideIndex === slideIndex &&
        this.oralCheck.enabled &&
        this.oralCheck.initializedSlideId === slideId
      );
    },

    goToNextSlide() {
      if (!this.canAdvanceFromActiveSlide()) return;
      this.goToSlide(this.activeSlideIndex + 1);
    },

    goToPrevSlide() {
      this.goToSlide(this.activeSlideIndex - 1);
    },

    skipDynamicReview() {
      const frames = this.slideFrames();
      const first = frames.findIndex(f => !f.dataset.slideId?.startsWith("dyn-"));
      if (first !== -1) this.goToSlide(first);
    },

    getStudentMark(slideIndex, studentName) {
      return (this.studentMarks[slideIndex] || {})[studentName] || "";
    },

    goToSlide(index) {
      this.clearPendingOralPromptWork();
      this.activeSlideIndex = this.clampSlideIndex(index);
      this.revealed = false;
      this.activeBlendIndex = -1;
      this.ensureActiveSlideRuntime();
    },

    hasSlideErrorTag(slideIndex, errorTag) {
      return this.ensureSlideMark(slideIndex).errorTags.includes(errorTag);
    },

    init() {
      const blockProgress = document.querySelector(".block-progress");
      if (blockProgress) {
        let isDragging = false;
        let startX = 0;
        let scrollLeft = 0;
        let hasDragged = false;

        blockProgress.addEventListener("mousedown", (e) => {
          isDragging = true;
          hasDragged = false;
          startX = e.pageX - blockProgress.getBoundingClientRect().left;
          scrollLeft = blockProgress.scrollLeft;
          blockProgress.style.cursor = "grabbing";
          blockProgress.style.userSelect = "none";
        });

        blockProgress.addEventListener("mousemove", (e) => {
          if (!isDragging) return;
          const x = e.pageX - blockProgress.getBoundingClientRect().left;
          const walk = x - startX;
          if (Math.abs(walk) > 4) {
            hasDragged = true;
            blockProgress.scrollLeft = scrollLeft - walk;
          }
        });

        const stopDrag = () => {
          isDragging = false;
          blockProgress.style.cursor = "";
          blockProgress.style.userSelect = "";
        };

        blockProgress.addEventListener("mouseup", stopDrag);
        blockProgress.addEventListener("mouseleave", stopDrag);

        blockProgress.addEventListener("click", (e) => {
          if (hasDragged) {
            e.stopPropagation();
            e.preventDefault();
            hasDragged = false;
          }
        }, true);
      }

      Alpine.store("lessonRoster").shell = this;
      this.topDockOpen = false;
      this.ensureActiveSlideRuntime();

      window.addEventListener("keydown", (event) => {
        const active = document.activeElement;
        const tag = active?.tagName?.toLowerCase();
        const isTyping =
          tag === "input" || tag === "textarea" || active?.isContentEditable;

        if (isTyping) return;

        const key = event.key.toLowerCase();

        if (key === "r") {
          event.preventDefault();
          Alpine.store("lessonRoster").toggleRosterDetails();
          return;
        }

        if (event.code === "Space") {
          event.preventDefault();

          if (!this.revealed) {
            this.toggleReveal();
            return;
          }

          this.goToNextSlide();
          return;
        }

        if (event.key === "ArrowLeft") {
          event.preventDefault();
          this.goToPrevSlide();
          return;
        }

        if (event.key === "ArrowRight") {
          event.preventDefault();
          this.goToNextSlide();
        }
      });
    },

    async ensureActiveSlideRuntime() {
      const slideIndex = this.activeSlideIndex;
      const slideId = this.activeSlideId();
      const config = this.oralCheckConfigForSlide(slideIndex);

      if (!config || !this.roster.length) {
        this.clearPendingOralPromptWork();
        this.comprehensionRound = {
          enabled: false,
          turns: [],
          activeTurnIndex: -1,
          completedCount: 0,
        };
        this.oralCheck = {
          enabled: false,
          initializedSlideId: "",
          sessionId: "",
          phase: "idle",
          phaseLabel: "",
          taskLabel: "",
          boardPromptTitle: "",
          boardPromptBody: "",
          teacherScript: "",
          progressLabel: "",
          auditSelectionStrategy: "roster_order",
          resolvedStudentCount: 0,
          requiredStudentCount: 0,
          activeAssignmentId: "",
          activeStudentName: "",
          activePerformanceType: "",
          unresolvedStudentCount: 0,
          sessionStatus: "idle",
          assignments: [],
        };
        const promptContext = this.activeSlidePromptContext();
        if (promptContext.autoSpeak !== false) {
          this.scheduleOralPromptSpeak(80, false);
        }
        return;
      }

      if (this.oralCheck.initializedSlideId === slideId && this.oralCheck.sessionId) {
        return;
      }

      try {
        const response = await fetch(`/lesson/${this.lessonId}/oral-check/session/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            attempt_id: this.attemptId,
            lesson_id: this.lessonId,
            slide_id: slideId,
            block_id: this.activeBlockId,
            roster: this.roster,
            participation_mode: config.participation_mode || "full_roster",
            text_length_mode: config.text_length_mode || "normal",
            required_evidence_count: config.required_evidence_count || 1,
            rehearsal_seconds: config.rehearsal_seconds || 30,
            audit_sample_size: config.audit_sample_size || 0,
            audit_selection_strategy: config.audit_selection_strategy || "roster_order",
            force_restart: false,
          }),
        });
        if (!response.ok) {
          throw new Error(`Oral check start failed (${response.status})`);
        }
        const data = await response.json();
        this.hydrateOralCheck(data, slideId);
      } catch (error) {
        this.lastMarkingResult = error.message;
      }
    },

    hydrateOralCheck(data, slideId) {
      const previousAssignmentId = this.oralCheck.activeAssignmentId || "";
      const phaseLabelMap = {
        individual_check: "Individual check",
        reteach_queue: "Reteach queue",
        complete: "Complete",
      };
      const boardPromptMap = {
        read_accuracy: {
          title: "Read It Accurately",
          body: `${data.active_student_name || "This student"} reads once while everyone tracks the words.`,
          teacher: `Call ${data.active_student_name || "the student"} to read the sentence accurately. Mark the read immediately.`,
        },
        reread_fluency: {
          title: "Reread Smoothly",
          body: `${data.active_student_name || "This student"} reads again with smoother phrasing and stronger pacing.`,
          teacher: `Have ${data.active_student_name || "the student"} reread smoothly. Listen for phrasing, pace, and confidence.`,
        },
        correction_reread: {
          title: "Correct And Reread",
          body: `${data.active_student_name || "This student"} corrects the first read and then rereads the full line.`,
          teacher: `Give the correction fast, then have ${data.active_student_name || "the student"} reread immediately.`,
        },
      };
      const performanceLabelMap = {
        read_accuracy: "Read aloud once.",
        reread_fluency: "Reread smoothly.",
        correction_reread: "Correct and reread.",
      };
      const prompt = boardPromptMap[data.active_performance_type] || {
        title: "Oral Check",
        body: "Follow the current reading direction.",
        teacher: "Listen and mark the current read.",
      };
      this.oralCheck = {
        enabled: true,
        initializedSlideId: slideId,
        sessionId: data.session_id,
        phase: data.phase,
        phaseLabel: phaseLabelMap[data.phase] || "Oral check",
        taskLabel: performanceLabelMap[data.active_performance_type] || "Read aloud once.",
        boardPromptTitle: prompt.title,
        boardPromptBody: prompt.body,
        teacherScript: prompt.teacher,
        progressLabel: `${data.resolved_student_count}/${data.required_student_count} resolved${data.participation_mode === "audit_roster" ? " · audit sample" : ""}`,
        auditSelectionStrategy: data.audit_selection_strategy || "roster_order",
        resolvedStudentCount: data.resolved_student_count || 0,
        requiredStudentCount: data.required_student_count || 0,
        activeAssignmentId: data.active_assignment_id || "",
        activeStudentName: data.active_student_name || "",
        activePerformanceType: data.active_performance_type || "",
        unresolvedStudentCount: data.unresolved_student_count || 0,
        sessionStatus: data.session_status || "in_progress",
        assignments: data.assignments || [],
      };
      this.lastMarkingResult = "";

      if (!data.active_assignment_id) {
        this.clearPendingOralPromptWork();
      }

      if (data.active_assignment_id && data.active_assignment_id !== previousAssignmentId) {
        this.lastOralPromptAudioUrl = "";
        void this.speakOralPromptIfNeeded();
      }

      if (
        !data.active_assignment_id &&
        data.session_status === "complete" &&
        this.activeSlideId() === slideId
      ) {
        this.startComprehensionRoundForActiveSlide();
      }
    },

    isActiveReaderOralPrompt(slideId) {
      return this.oralCheck.enabled && this.oralCheck.initializedSlideId === slideId;
    },

    buildOralPromptLine({ name, promptContext, performanceType }) {
      if (OralPromptHelper.buildOralPromptLine) {
        return OralPromptHelper.buildOralPromptLine({ name, promptContext, performanceType });
      }
      return name ? `${name}, please read the story.` : "";
    },

    oralNotificationLine() {
      const comprehensionTurn = this.activeComprehensionTurn();
      if (comprehensionTurn) {
        return `${comprehensionTurn.studentName}, ${comprehensionTurn.prompt}`;
      }
      const genericPromptLine = this.genericLuminosPromptLine();
      if (genericPromptLine && (!this.oralCheck.activeAssignmentId || !this.oralCheck.activeStudentName)) {
        return genericPromptLine;
      }
      if (!this.oralCheck.activeAssignmentId || !this.oralCheck.activeStudentName) {
        return "";
      }
      const promptContext = {
        ...this.activeSlidePromptContext(),
        mode: "read_story",
        comprehensionPrompt: "",
      };
      return this.buildOralPromptLine({
        name: this.oralCheck.activeStudentName,
        promptContext,
        performanceType: this.oralCheck.activePerformanceType,
      });
    },

    oralInstructionSupportLine() {
      const comprehensionTurn = this.activeComprehensionTurn();
      if (comprehensionTurn) {
        return `Question ${this.comprehensionRound.activeTurnIndex + 1} of ${this.comprehensionRound.turns.length}. Listen, then mark the response below.`;
      }
      if (this.genericLuminosPromptLine() && (!this.oralCheck.activeAssignmentId || !this.oralCheck.activeStudentName)) {
        return this.genericLuminosSupportLine();
      }
      const promptContext = this.activeSlidePromptContext();
      if (OralPromptHelper.oralInstructionSupportLine) {
        return OralPromptHelper.oralInstructionSupportLine({
          ...promptContext,
          mode: "read_story",
          comprehensionPrompt: "",
        });
      }
      return "Listen, then mark the response below.";
    },

    genericLuminosPromptLine() {
      if (this.comprehensionRound.enabled) return "";
      if (this.oralCheck.enabled) {
        return "";
      }
      const promptContext = this.activeSlidePromptContext();
      if (OralPromptHelper.buildGenericLuminosPrompt) {
        return OralPromptHelper.buildGenericLuminosPrompt({
          customText: promptContext.genericCustomText,
          promptText: promptContext.slidePromptText,
          teacherCue: promptContext.teacherCue,
          viewType: promptContext.viewType,
          title: promptContext.title,
          frontText: promptContext.frontText,
          targetWord: promptContext.targetWord,
          targetSentence: promptContext.targetSentence,
          dictatedText: promptContext.dictatedText,
          quickCheckTitle: promptContext.quickCheckTitle,
        });
      }
      return promptContext.genericCustomText || promptContext.slidePromptText || promptContext.teacherCue || "";
    },

    genericLuminosSupportLine() {
      const promptContext = this.activeSlidePromptContext();
      if (OralPromptHelper.buildGenericLuminosSupportLine) {
        return OralPromptHelper.buildGenericLuminosSupportLine({
          customSupportText: promptContext.genericSupportText,
          teacherCue: promptContext.teacherCue,
          promptText: promptContext.slidePromptText,
        });
      }
      return promptContext.genericSupportText || promptContext.teacherCue || "";
    },

    extractComprehensionSegments(prompt = "") {
      if (OralPromptHelper.extractComprehensionSegments) {
        return OralPromptHelper.extractComprehensionSegments(prompt);
      }
      const normalized = this.normalizedQuestionPrompt(prompt);
      return normalized ? [normalized] : [];
    },

    startComprehensionRoundForActiveSlide() {
      if (this.comprehensionRound.enabled) return;
      const promptContext = this.activeSlidePromptContext();
      const configuredQuestions = (promptContext.comprehensionQuestions || []).filter((item) => String(item || "").trim());
      const segments = configuredQuestions.length
        ? configuredQuestions.map((item) => String(item).trim())
        : this.extractComprehensionSegments(promptContext.comprehensionPrompt);
      if (!segments.length || !this.roster.length) return;

      const turnCount = Math.max(this.roster.length, segments.length);
      const turns = Array.from({ length: turnCount }, (_, index) => ({
        prompt: segments[index % segments.length],
        studentName: this.roster[index % this.roster.length],
        status: "pending",
      }));

      this.comprehensionRound = {
        enabled: true,
        turns,
        activeTurnIndex: 0,
        completedCount: 0,
      };
      this.clearPendingOralPromptWork();
      this.scheduleOralPromptSpeak(80, true);
    },

    advanceComprehensionRound(status) {
      const turn = this.activeComprehensionTurn();
      if (!turn) return;

      turn.status = status;
      const nextIndex = this.comprehensionRound.turns.findIndex((item) => item.status === "pending");
      this.comprehensionRound.completedCount = this.comprehensionRound.turns.filter((item) => item.status !== "pending").length;

      if (nextIndex === -1) {
        this.comprehensionRound = {
          enabled: false,
          turns: [],
          activeTurnIndex: -1,
          completedCount: 0,
        };
        this.clearPendingOralPromptWork();
        this.lastMarkingResult = "Comprehension round complete";
        return;
      }

      this.comprehensionRound.activeTurnIndex = nextIndex;
      this.lastOralPromptAudioUrl = "";
      this.lastMarkingResult = `${turn.studentName} · ${status}`;
      void this.speakOralPromptIfNeeded(true);
    },

    getOralPendingStudents() {
      if (!this.oralCheck.enabled) return [];
      return this.oralCheck.assignments
        .filter((item) => item.status === "pending")
        .slice(0, 4)
        .map((item) => item.student_name);
    },

    getOralReteachStudents() {
      if (!this.oralCheck.enabled) return [];
      return this.oralCheck.assignments
        .filter((item) => item.performance_type === "correction_reread" && item.status !== "secure" && item.status !== "deferred" && item.status !== "absent")
        .map((item) => item.student_name);
    },

    canRestartAuditStrategy() {
      return (
        this.oralCheck.enabled &&
        this.oralCheck.sessionStatus !== "complete" &&
        this.oralCheck.resolvedStudentCount === 0 &&
        this.oralCheck.requiredStudentCount > 0
      );
    },

    async restartAuditSelectionStrategy(strategy) {
      const config = this.oralCheckConfigForSlide(this.activeSlideIndex);
      if (!config || !this.canRestartAuditStrategy()) return;
      try {
        const response = await fetch(`/lesson/${this.lessonId}/oral-check/session/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            attempt_id: this.attemptId,
            lesson_id: this.lessonId,
            slide_id: this.activeSlideId(),
            block_id: this.activeBlockId,
            roster: this.roster,
            participation_mode: config.participation_mode || "audit_roster",
            text_length_mode: config.text_length_mode || "normal",
            required_evidence_count: config.required_evidence_count || 1,
            rehearsal_seconds: config.rehearsal_seconds || 30,
            audit_sample_size: config.audit_sample_size || 0,
            audit_selection_strategy: strategy,
            force_restart: true,
          }),
        });
        if (!response.ok) {
          throw new Error(`Audit strategy restart failed (${response.status})`);
        }
        this.hydrateOralCheck(await response.json(), this.activeSlideId());
        this.lastMarkingResult = `Audit strategy · ${strategy.replaceAll("_", " ")}`;
      } catch (error) {
        this.lastMarkingResult = error.message;
      }
    },

    canAdvanceFromActiveSlide() {
      if (!this.oralCheck.enabled) return true;
      if (this.oralCheck.initializedSlideId !== this.activeSlideId()) return true;
      if (this.oralCheck.unresolvedStudentCount > 0) {
        this.lastMarkingResult = `Cannot advance: ${this.oralCheck.unresolvedStudentCount} students unresolved`;
        return false;
      }
      if (this.comprehensionRound.enabled) {
        this.lastMarkingResult = `Cannot advance: comprehension round still active`;
        return false;
      }
      return true;
    },

    playAudio(src) {
      const player = this.getAudioPlayer(src);
      if (player) {
        player.stop();
        player.play();
      }
    },

    quickCheckHasErrorTag(slideIndex, itemIndex, errorTag) {
      return this.ensureQuickCheckItem(slideIndex, itemIndex).errorTags.includes(errorTag);
    },

    runVocabBlend(units = [], wordAudioSrc) {
      if (this.blendTimer) {
        clearTimeout(this.blendTimer);
        this.blendTimer = null;
      }

      this.activeBlendIndex = -1;

      if (!units.length) {
        if (wordAudioSrc) this.playAudio(wordAudioSrc);
        return;
      }

      const stepDuration = 800;
      let currentIndex = 0;

      const runStep = () => {
        this.activeBlendIndex = currentIndex;
        const unit = units[currentIndex];
        if (unit.audio) this.playAudio(unit.audio);

        if (currentIndex < units.length - 1) {
          currentIndex += 1;
          this.blendTimer = window.setTimeout(runStep, stepDuration);
          return;
        }

        this.blendTimer = window.setTimeout(() => {
          this.activeBlendIndex = -1;
          if (wordAudioSrc) this.playAudio(wordAudioSrc);
          this.blendTimer = null;
        }, stepDuration);
      };

      runStep();
    },

    runBlendSequence(phonemeParts = [], blendAudioSrc, wordAudioSrc) {
      if (this.blendTimer) {
        clearTimeout(this.blendTimer);
        this.blendTimer = null;
      }

      this.activeBlendIndex = -1;

      if (!phonemeParts.length) {
        if (wordAudioSrc) this.playAudio(wordAudioSrc);
        return;
      }

      const stepDuration = 900;
      let currentIndex = 0;

      const runStep = () => {
        this.activeBlendIndex = currentIndex;

        if (currentIndex < phonemeParts.length - 1) {
          currentIndex += 1;
          this.blendTimer = window.setTimeout(runStep, stepDuration);
          return;
        }

        this.blendTimer = window.setTimeout(() => {
          this.activeBlendIndex = -1;
          if (wordAudioSrc) this.playAudio(wordAudioSrc);
          this.blendTimer = null;
        }, stepDuration);
      };

      if (blendAudioSrc) this.playAudio(blendAudioSrc);
      runStep();
    },

    setQuickCheckItemMark(slideIndex, itemIndex, status) {
      this.ensureQuickCheckItem(slideIndex, itemIndex).status = status;
    },

    setSlideMark(slideIndex, status) {
      this.ensureSlideMark(slideIndex).status = status;
    },

    setAndSubmitSlideMark(slideIndex, option, slideId, blockId) {
      this.setSlideMark(slideIndex, option);
      this.submitSlideMark({ slideIndex, slideId, blockId });
    },

    async finishLesson() {
      if (!this.canAdvanceFromActiveSlide()) return;
      try {
        await fetch(`/lesson/${this.lessonId}/complete`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ attempt_id: this.attemptId }),
        });
      } catch (e) {
        // navigate regardless
      }
      window.location.href = `/lesson/${this.lessonId}/review/${this.attemptId}`;
    },

    setSlideTeacherNote(slideIndex, value) {
      this.ensureSlideMark(slideIndex).teacherNote = value;
    },

    slideFrames() {
      return Array.from(document.querySelectorAll(".lesson-slide-frame"));
    },

    submitQuickCheck({ slideIndex, slideId, blockId, items = [], completed = false }) {
      const itemResults = items.map((item, itemIndex) => {
        const state = this.ensureQuickCheckItem(slideIndex, itemIndex);
        return {
          label: item.label,
          phoneme: item.phoneme || null,
          status: state.status || "skipped",
          error_tags: state.errorTags,
          korean_transfer: state.koreanTransfer,
        };
      });

      const status = itemResults.reduce((worst, current) => {
        if (STATUS_PRIORITY[current.status] > STATUS_PRIORITY[worst]) return current.status;
        return worst;
      }, "secure");

      const errorTags = [...new Set(itemResults.flatMap((item) => item.error_tags))];
      const koreanTransfer = itemResults.some((item) => item.korean_transfer);

      return this.postMark({
        attempt_id: this.attemptId,
        lesson_id: this.lessonId,
        slide_id: slideId,
        block_id: blockId,
        status,
        error_tags: errorTags,
        korean_transfer: koreanTransfer,
        teacher_note: this.getSlideTeacherNote(slideIndex),
        completed,
        item_results: itemResults,
      });
    },

    async submitSlideMark({ slideIndex, slideId, blockId, completed = false }) {
      const slideMark = this.ensureSlideMark(slideIndex);
      if (!slideMark.status) return;

      return this.postMark({
        attempt_id: this.attemptId,
        lesson_id: this.lessonId,
        slide_id: slideId,
        block_id: blockId,
        status: slideMark.status,
        error_tags: slideMark.errorTags,
        korean_transfer: slideMark.koreanTransfer,
        teacher_note: slideMark.teacherNote,
        completed,
      });
    },

    async postMark(payload) {
      this.isSubmitting = true;
      this.lastMarkingResult = "";

      try {
        const response = await fetch(`/lesson/${this.lessonId}/mark`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          throw new Error(`Marking request failed (${response.status})`);
        }

        const data = await response.json();
        this.lastMarkingResult = `${data.mastery_status} · ${data.next_recommendation}`;
        return data;
      } catch (error) {
        this.lastMarkingResult = error.message;
        return null;
      } finally {
        this.isSubmitting = false;
      }
    },

    showTopDock() {
      if (this.topDockTimer) {
        window.clearTimeout(this.topDockTimer);
        this.topDockTimer = null;
      }
      this.topDockOpen = true;
    },

    hideTopDock() {
      if (this.topDockTimer) {
        window.clearTimeout(this.topDockTimer);
      }
      this.topDockTimer = window.setTimeout(() => {
        this.topDockOpen = false;
        this.topDockTimer = null;
      }, 140);
    },

    handleRuntimePointerMove(event) {
      if (!event) return;
      if (event.clientY <= 84) {
        this.showTopDock();
      }
    },

    cycleStudentMark(studentName, slideId, blockId) {
      const CYCLE = ["secure", "shaky", "missed", "skipped"];
      const slideIndex = this.activeSlideIndex;
      if (!this.studentMarks[slideIndex]) this.studentMarks[slideIndex] = {};
      const current = this.studentMarks[slideIndex][studentName] || "";
      const currentIdx = CYCLE.indexOf(current);
      let next;
      if (currentIdx === -1) {
        next = CYCLE[0];
      } else if (currentIdx === CYCLE.length - 1) {
        next = "";
      } else {
        next = CYCLE[currentIdx + 1];
      }
      this.studentMarks[slideIndex][studentName] = next;
      if (next === "") {
        this.deleteStudentMark({
          attempt_id: this.attemptId,
          lesson_id: this.lessonId,
          slide_id: slideId,
          student_name: studentName,
        });
      } else {
        this.postStudentMark({
          attempt_id: this.attemptId,
          lesson_id: this.lessonId,
          slide_id: slideId,
          block_id: blockId,
          student_name: studentName,
          status: next,
        });
      }
    },

    async deleteStudentMark(payload) {
      try {
        await fetch(`/lesson/${this.lessonId}/student-mark`, {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } catch (error) {
        console.error("Student mark delete failed:", error);
      }
    },

    async postStudentMark(payload) {
      try {
        await fetch(`/lesson/${this.lessonId}/student-mark`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      } catch (error) {
        console.error("Student mark failed:", error);
      }
    },

    async markActiveOralAssignment(status) {
      await this.unlockAudio();
      if (this.comprehensionRound.enabled) {
        this.advanceComprehensionRound(status);
        return;
      }
      if (!this.oralCheck.enabled || !this.oralCheck.activeAssignmentId) return;
      try {
        const response = await fetch(`/lesson/${this.lessonId}/oral-check/assignment/mark`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_id: this.oralCheck.sessionId,
            assignment_id: this.oralCheck.activeAssignmentId,
            status,
          }),
        });
        if (!response.ok) {
          throw new Error(`Oral check mark failed (${response.status})`);
        }
        const data = await response.json();
        this.hydrateOralCheck(data.session, this.activeSlideId());
        this.studentMarks[this.activeSlideIndex] = this.studentMarks[this.activeSlideIndex] || {};
        this.studentMarks[this.activeSlideIndex][data.student_name] = data.status;
        this.lastMarkingResult = `${data.student_name} · ${data.status}`;

        if (data.session.unresolved_student_count === 0) {
          await fetch(`/lesson/${this.lessonId}/oral-check/session/complete`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: this.oralCheck.sessionId }),
          }).then(async (completeResponse) => {
            if (completeResponse.ok) {
              this.hydrateOralCheck(await completeResponse.json(), this.activeSlideId());
            }
          });
        }
      } catch (error) {
        this.lastMarkingResult = error.message;
      }
    },

    toggleQuickCheckErrorTag(slideIndex, itemIndex, errorTag) {
      const state = this.ensureQuickCheckItem(slideIndex, itemIndex);
      if (state.errorTags.includes(errorTag)) {
        state.errorTags = state.errorTags.filter((tag) => tag !== errorTag);
      } else {
        state.errorTags = [...state.errorTags, errorTag];
      }
    },

    toggleQuickCheckKoreanTransfer(slideIndex, itemIndex) {
      const state = this.ensureQuickCheckItem(slideIndex, itemIndex);
      state.koreanTransfer = !state.koreanTransfer;
    },

    toggleReveal() {
      this.revealed = !this.revealed;
    },

    toggleSlideErrorTag(slideIndex, errorTag) {
      const slideMark = this.ensureSlideMark(slideIndex);
      if (slideMark.errorTags.includes(errorTag)) {
        slideMark.errorTags = slideMark.errorTags.filter((tag) => tag !== errorTag);
      } else {
        slideMark.errorTags = [...slideMark.errorTags, errorTag];
      }
    },

    toggleSlideKoreanTransfer(slideIndex) {
      const slideMark = this.ensureSlideMark(slideIndex);
      slideMark.koreanTransfer = !slideMark.koreanTransfer;
    },
  });

  window.reviewShell = (config = {}) => ({
    attemptId: config.attemptId || "",
    lessonId: config.lessonId || "",
    marks: config.marks || {},
    editingKey: null,
    editStatus: "",
    editNote: "",
    isSaving: false,

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
      try {
        await fetch(`/lesson/${this.lessonId}/student-mark`, {
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
        const key = `${slideId}__${studentName}`;
        this.marks[key] = {
          ...(this.marks[key] || {}),
          status: this.editStatus,
          teacher_note: this.editNote,
        };
        this.closeEdit();
      } catch (err) {
        console.error("Review save failed:", err);
      } finally {
        this.isSaving = false;
      }
    },
  });

  document.addEventListener("alpine:init", () => {
    Alpine.store("lessonRoster", {
      shell: null,
      rosterDetailsOpen: false,
      panelCollapsed: false,
      get roster() { return this.shell ? this.shell.roster : []; },
      get classLabel() { return this.shell ? this.shell.classLabel : ""; },
      get hasRoster() { return !!this.roster.length; },
      get rosterMarkedCount() {
        if (!this.shell || !this.roster.length) return 0;
        const idx = this.shell.activeSlideIndex;
        return this.roster.filter((student) => !!((this.shell.studentMarks[idx] || {})[student])).length;
      },
      get rosterRemainingCount() {
        return Math.max(0, this.roster.length - this.rosterMarkedCount);
      },
      get hasActiveLuminosPrompt() {
        return !!(
          this.shell &&
          (
            (
              this.shell.oralCheck.enabled &&
              this.shell.oralCheck.initializedSlideId === this.shell.activeSlideId() &&
              this.shell.oralCheck.sessionStatus !== "complete" &&
              this.shell.oralCheck.activeAssignmentId &&
              this.shell.oralCheck.activeStudentName
            ) ||
            this.shell.comprehensionRound.enabled ||
            !!this.shell.genericLuminosPromptLine()
          )
        );
      },
      get hasActiveOralCheck() {
        return this.hasActiveLuminosPrompt;
      },
      get oralProgressLabel() {
        if (!this.shell) return "";
        if (this.shell.comprehensionRound.enabled) {
          return `${this.shell.comprehensionRound.completedCount}/${this.shell.comprehensionRound.turns.length} comprehension`;
        }
        if (this.shell.genericLuminosPromptLine()) {
          return this.shell.activeBlockLabel || this.shell.activeSlideTitle || "";
        }
        return this.shell.oralCheck.progressLabel || "";
      },
      get auditSelectionStrategy() {
        return this.shell ? this.shell.oralCheck.auditSelectionStrategy || "roster_order" : "roster_order";
      },
      get showAuditStrategyControls() {
        return !!(
          this.shell &&
          this.shell.oralCheck.progressLabel.includes("audit sample") &&
          this.shell.canRestartAuditStrategy()
        );
      },
      get pendingStudents() {
        return this.shell ? this.shell.getOralPendingStudents() : [];
      },
      get reteachStudents() {
        return this.shell ? this.shell.getOralReteachStudents() : [];
      },
      get lastMarkingResult() {
        return this.shell ? this.shell.lastMarkingResult : "";
      },
      get canPlayOralPrompt() {
        return !!(
          this.shell &&
          !!this.shell.oralNotificationLine() &&
          (
            (this.shell.oralCheck.enabled &&
            this.shell.oralCheck.activeAssignmentId &&
            this.shell.oralCheck.activeStudentName) ||
            this.shell.comprehensionRound.enabled ||
            this.shell.genericLuminosPromptLine()
          )
        );
      },
      get canPauseOralPrompt() {
        return !!(
          this.shell &&
          this.shell.lastOralPromptAudioUrl &&
          this.shell.getAudioPlayer(this.shell.lastOralPromptAudioUrl)?.playing()
        );
      },
      toggleRosterDetails() {
        if (!this.hasRoster) return;
        this.rosterDetailsOpen = !this.rosterDetailsOpen;
      },
      togglePanelCollapsed() {
        this.panelCollapsed = !this.panelCollapsed;
        if (this.panelCollapsed) {
          this.rosterDetailsOpen = false;
        }
      },
      oralNotificationLine() {
        return this.shell ? this.shell.oralNotificationLine() : "";
      },
      oralInstructionSupportLine() {
        return this.shell ? this.shell.oralInstructionSupportLine() : "";
      },
      playCurrentOralPrompt() {
        if (!this.shell) return;
        void this.shell.playCurrentOralPrompt();
      },
      pauseCurrentOralPrompt() {
        if (!this.shell) return;
        this.shell.pauseCurrentOralPrompt();
      },
      restartAuditSelectionStrategy(strategy) {
        if (!this.shell) return;
        this.shell.restartAuditSelectionStrategy(strategy);
      },
      markActiveOralAssignment(status) {
        if (!this.shell) return;
        this.shell.markActiveOralAssignment(status);
      },
      get showMarkingActions() {
        return !!(
          this.shell &&
          (
            (this.shell.oralCheck.enabled &&
              this.shell.oralCheck.activeAssignmentId &&
              this.shell.oralCheck.activeStudentName) ||
            this.shell.comprehensionRound.enabled
          )
        );
      },
      getStudentStatus(student) {
        if (!this.shell) return "";
        const idx = this.shell.activeSlideIndex;
        return (this.shell.studentMarks[idx] || {})[student] || "";
      },
      cycleStudent(student) {
        if (!this.shell) return;
        const idx = this.shell.activeSlideIndex;
        const el = document.querySelector(`.lesson-slide-frame[data-slide-index="${idx}"]`);
        const slideId = el ? el.dataset.slideId : "";
        const blockId = el ? el.dataset.blockId : "";
        this.shell.cycleStudentMark(student, slideId, blockId);
      },
    });

    Alpine.data("dragBuild", (expectedItems = []) => ({
      placedItems: [],
      revealed: false,
      checked: false,

      placeItem(item) {
        if (this.revealed) return;
        this.checked = false;
        if (this.placedItems.length >= expectedItems.length) return;
        this.placedItems.push(item);
      },

      removeItem(index) {
        if (this.revealed) return;
        this.checked = false;
        this.placedItems.splice(index, 1);
      },

      reset() {
        this.placedItems = [];
        this.revealed = false;
        this.checked = false;
      },

      reveal() {
        this.placedItems = [...expectedItems];
        this.revealed = true;
        this.checked = true;
      },

      check() {
        if (this.placedItems.length !== expectedItems.length) return;
        this.checked = true;
      },

      isCorrect() {
        if (this.placedItems.length !== expectedItems.length) return false;
        return expectedItems.every(
          (item, index) => this.placedItems[index] === item
        );
      },
    }));
  });
})();
