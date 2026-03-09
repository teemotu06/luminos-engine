document.addEventListener("alpine:init", () => {
  Alpine.data("lessonShell", () => ({
    presentationMode: false,
    audioPlayers: {},

    togglePresentationMode() {
      this.presentationMode = !this.presentationMode;
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

    init() {
      window.addEventListener("keydown", (event) => {
        const key = event.key.toLowerCase();

        if (key === "p") {
          this.togglePresentationMode();
          return;
        }

        if (event.key === "ArrowLeft") {
          this.goToPrevSlide();
          return;
        }

        if (event.key === "ArrowRight") {
          this.goToNextSlide();
        }
      });
    },
  }));

  Alpine.data("dragBuild", (expectedItems = []) => ({
    placedItems: [],
    revealed: false,
    checked: false,

    placeItem(item) {
      if (this.revealed) return;
      if (this.placedItems.length >= expectedItems.length) return;
      if (this.placedItems.includes(item)) return;
      this.placedItems.push(item);
    },

    removeItem(index) {
      if (this.revealed) return;
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
      this.checked = false;
    },

    check() {
      this.checked = true;
    },

    isCorrect() {
      if (this.placedItems.length !== expectedItems.length) {
        return false;
      }

      return expectedItems.every((item, index) => this.placedItems[index] === item);
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