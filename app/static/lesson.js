(() => {
  window.lessonShell = () => ({
    activeBlendIndex: -1,
    blendTimer: null,
    presentationMode: false,
    revealed: false,
    audioPlayers: {},

    togglePresentationMode() {
      this.presentationMode = !this.presentationMode;
    },

    toggleReveal() {
      this.revealed = !this.revealed;
    },

    goToPrevSlide() {
      const prevLink = document.getElementById("lesson-prev-link");
      if (prevLink) {
        window.location.href = prevLink.href;
      }
    },

    goToNextSlide() {
      const nextLink = document.getElementById("lesson-next-link");
      if (nextLink) {
        window.location.href = nextLink.href;
      }
    },

    getAudioPlayer(src) {
      if (!src) {
        return null;
      }

      if (!this.audioPlayers[src]) {
        this.audioPlayers[src] = new Howl({
          src: [src],
          html5: true,
          preload: true,
        });
      }

      return this.audioPlayers[src];
    },

    playAudio(src) {
      const player = this.getAudioPlayer(src);
      if (player) {
        player.stop();
        player.play();
      }
    },

    runBlendSequence(phonemeParts = [], blendAudioSrc, wordAudioSrc) {
      if (this.blendTimer) {
        clearTimeout(this.blendTimer);
        this.blendTimer = null;
      }

      this.activeBlendIndex = -1;

      if (!phonemeParts.length) {
        if (wordAudioSrc) {
          this.playAudio(wordAudioSrc);
        }
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

          if (wordAudioSrc) {
            this.playAudio(wordAudioSrc);
          }

          this.blendTimer = null;
        }, stepDuration);
      };

      if (blendAudioSrc) {
        this.playAudio(blendAudioSrc);
      }

      runStep();
    },

    getPresentationFlow() {
      return (
        document.querySelector("[data-presentation-flow]")?.dataset
          .presentationFlow || null
      );
    },

    init() {
      window.addEventListener("keydown", (event) => {
        const active = document.activeElement;
        const tag = active?.tagName?.toLowerCase();
        const isTyping =
          tag === "input" ||
          tag === "textarea" ||
          active?.isContentEditable;

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
            const phonemeParts = JSON.parse(
              document.querySelector("[data-phoneme-parts]")?.dataset
                .phonemeParts || "[]"
            );
            const blendAudioSrc =
              document.querySelector("[data-blend-audio]")?.dataset.blendAudio ||
              null;
            const wordAudioSrc =
              document.querySelector("[data-word-audio]")?.dataset.wordAudio ||
              null;

            if (this.activeBlendIndex === -1 && !this.revealed) {
              this.runBlendSequence(phonemeParts, blendAudioSrc, wordAudioSrc);
              return;
            }

            if (!this.revealed) {
              this.toggleReveal();
              return;
            }

            this.goToNextSlide();
            return;
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
        if (this.placedItems.length !== expectedItems.length) {
          return;
        }

        this.checked = true;
      },

      isCorrect() {
        if (this.placedItems.length !== expectedItems.length) {
          return false;
        }

        return expectedItems.every(
          (item, index) => this.placedItems[index] === item
        );
      },
    }));

    Alpine.data("quickCheckItem", () => ({
      selectedMark: "",
      selectedErrorTag: "",
      koreanTransfer: false,

      chooseMark(mark) {
        this.selectedMark = mark;
      },

      chooseErrorTag(tag) {
        this.selectedErrorTag = tag;
      },

      toggleKoreanTransfer() {
        this.koreanTransfer = !this.koreanTransfer;
      },

      hasSelection() {
        return this.selectedMark !== "";
      },

      confirmMarking() {
        return this.hasSelection();
      },
    }));
  });
})();
