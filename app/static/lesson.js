(() => {
  const PRESENTATION_MODE_STORAGE_KEY = "luminos.presentationMode";
  const STATUS_PRIORITY = { secure: 0, shaky: 1, missed: 2, skipped: 3 };

  window.lessonShell = (config = {}) => ({
    activeBlendIndex: -1,
    activeSlideIndex: Number(config.initialSlideIndex || 0),
    attemptId: config.attemptId || "",
    audioPlayers: {},
    blendTimer: null,
    isSubmitting: false,
    lastMarkingResult: "",
    lessonId: config.lessonId || "",
    presentationMode: false,
    quickCheckMarks: {},
    revealed: false,
    slideMarks: {},

    get activeBlockId() {
      return this.currentSlideElement()?.dataset.blockId || null;
    },

    clampSlideIndex(index) {
      const frames = this.slideFrames();
      if (!frames.length) return 0;
      return Math.max(0, Math.min(index, frames.length - 1));
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
        this.audioPlayers[src] = new Howl({
          src: [src],
          html5: true,
          preload: true,
        });
      }

      return this.audioPlayers[src];
    },

    getPresentationFlow() {
      return (
        this.currentSlideElement()?.querySelector("[data-presentation-flow]")?.dataset
          .presentationFlow || null
      );
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

    goToNextSlide() {
      this.goToSlide(this.activeSlideIndex + 1);
    },

    goToPrevSlide() {
      this.goToSlide(this.activeSlideIndex - 1);
    },

    goToSlide(index) {
      this.activeSlideIndex = this.clampSlideIndex(index);
      this.revealed = false;
      this.activeBlendIndex = -1;
    },

    hasSlideErrorTag(slideIndex, errorTag) {
      return this.ensureSlideMark(slideIndex).errorTags.includes(errorTag);
    },

    init() {
      this.presentationMode =
        window.sessionStorage.getItem(PRESENTATION_MODE_STORAGE_KEY) === "true";

      window.addEventListener("keydown", (event) => {
        const active = document.activeElement;
        const tag = active?.tagName?.toLowerCase();
        const isTyping =
          tag === "input" || tag === "textarea" || active?.isContentEditable;

        if (isTyping) return;

        const key = event.key.toLowerCase();

        if (key === "p") {
          event.preventDefault();
          this.togglePresentationMode();
          return;
        }

        if (key === "r") {
          event.preventDefault();
          this.toggleReveal();
          return;
        }

        if (event.code === "Space") {
          event.preventDefault();

          const presentationFlow = this.getPresentationFlow();

          if (presentationFlow === "blend-reveal-next") {
            const activeStage = this.currentSlideElement();
            const phonemeParts = JSON.parse(
              activeStage?.querySelector("[data-phoneme-parts]")?.dataset
                .phonemeParts || "[]"
            );
            const blendAudioSrc =
              activeStage?.querySelector("[data-blend-audio]")?.dataset.blendAudio ||
              null;
            const wordAudioSrc =
              activeStage?.querySelector("[data-word-audio]")?.dataset.wordAudio ||
              null;

            if (this.activeBlendIndex === -1 && !this.revealed) {
              this.runBlendSequence(phonemeParts, blendAudioSrc, wordAudioSrc);
              return;
            }

            if (!this.revealed) {
              this.toggleReveal();
              return;
            }
          }

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

    savePresentationMode() {
      window.sessionStorage.setItem(
        PRESENTATION_MODE_STORAGE_KEY,
        this.presentationMode ? "true" : "false"
      );
    },

    setQuickCheckItemMark(slideIndex, itemIndex, status) {
      this.ensureQuickCheckItem(slideIndex, itemIndex).status = status;
    },

    setSlideMark(slideIndex, status) {
      this.ensureSlideMark(slideIndex).status = status;
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

    togglePresentationMode() {
      this.presentationMode = !this.presentationMode;
      this.savePresentationMode();
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

  document.addEventListener("alpine:init", () => {
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
