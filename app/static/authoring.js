(() => {
  window.authoringEditorShell = function authoringEditorShell() {
    return {
      validationResult: null,
      openBlockId: "01",
    };
  };

  window.toggleAuthoringSlideEditor = function toggleAuthoringSlideEditor(button, lessonId, blockId, slideId) {
    const blockRoot = button.closest("[data-block-panel]");
    const target = document.getElementById(`slide-editor-${slideId}`);
    const row = button.closest("[data-slide-row]");
    if (!blockRoot || !target || !window.htmx) return;

    const currentlyOpen = blockRoot.getAttribute("data-open-slide-id") || "";
    if (currentlyOpen === slideId) {
      target.innerHTML = "";
      blockRoot.setAttribute("data-open-slide-id", "");
      if (row) row.setAttribute("data-open", "false");
      const currentLabel = button.getAttribute("data-edit-label") || "Edit";
      button.textContent = currentLabel;
      return;
    }

    if (currentlyOpen) {
      const previousTarget = document.getElementById(`slide-editor-${currentlyOpen}`);
      if (previousTarget) previousTarget.innerHTML = "";
      const previousRow = blockRoot.querySelector(`[data-slide-row][data-slide-id="${currentlyOpen}"]`);
      if (previousRow) previousRow.setAttribute("data-open", "false");
      const previousButton = blockRoot.querySelector(`[data-slide-edit-button="${currentlyOpen}"]`);
      if (previousButton) {
        previousButton.textContent = previousButton.getAttribute("data-edit-label") || "Edit";
      }
    }

    blockRoot.setAttribute("data-open-slide-id", slideId);
    if (row) row.setAttribute("data-open", "true");
    button.textContent = button.getAttribute("data-close-label") || "Close";
    window.htmx.ajax("GET", `/authoring/lessons/${lessonId}/blocks/${blockId}/slides/${slideId}`, {
      target: `#slide-editor-${slideId}`,
      swap: "innerHTML",
    });
  };

  function defaultValueForType(type) {
    if (type === "bool") return false;
    if (type === "list[str]") return [];
    return "";
  }

  window.authoringSlideForm = function authoringSlideForm(config = {}) {
    const normalizeInitialBuildUnitsInput = (initialUnitsInput, initialTargetWord) => {
      const unitsText = String(initialUnitsInput || "").trim();
      const wordText = String(initialTargetWord || "").trim();
      if (!unitsText) return wordText;
      if (!wordText) return unitsText;
      const normalizedUnits = unitsText
        .split(/[\n,|]+/)
        .map((item) => item.trim())
        .filter(Boolean)
        .join("")
        .toLowerCase();
      if (normalizedUnits && normalizedUnits !== wordText.toLowerCase()) {
        return wordText;
      }
      return unitsText;
    };

    return {
      slideType: config.slideType || "",
      requiredFields: Object.assign(
        {
          slide_title: "",
          teacher_cue: "",
        },
        config.requiredFields || {},
      ),
      formErrors: {},
      generalErrors: [],
      mediaTarget: "",
      mediaBrowserTarget: "",
      attachedSlideAudioUrl: config.initialSlideAudioUrl || "",
      slideAudioDuration: "",
      slideAudioUploading: false,
      slideAudioUploadError: "",
      slideAudioInputKey: 0,
      attachedAudioUrls: Object.assign({}, config.initialAudioFieldValues || {}),
      audioFieldDurations: {},
      audioUploadingField: "",
      audioUploadErrors: {},
      audioInputKeys: {},
      attachedImageUrls: Object.assign({}, config.initialImageFieldValues || {}),
      imageDurations: {},
      imageUploadingField: "",
      imageUploadErrors: {},
      imageInputKeys: {},
      advancedOpen: false,
      markable: !!config.initialMarkable,
      buildUnitsInput: normalizeInitialBuildUnitsInput(config.initialBuildUnitsInput, config.initialTargetWord),
      spellWordInput: String(config.initialSpellWord || "").trim(),
      spellLetterPoolInput: String(config.initialSpellLetterPoolInput || "").trim(),
      patternWordInputs: Array.isArray(config.initialPatternWordInputs) && config.initialPatternWordInputs.length
        ? [...config.initialPatternWordInputs]
        : ["s[at]", "[at]"],
      patternPrompt: String(config.initialPatternPrompt || "What do you notice? Which sound part do they share?").trim(),
      patternRevealMode: String(config.initialPatternRevealMode || "sequential").trim() || "sequential",
      filenameFromPath(path) {
        const value = String(path || "").trim();
        if (!value) return "";
        const clean = value.split("?")[0].split("#")[0];
        const parts = clean.split("/");
        return parts[parts.length - 1] || value;
      },
      formatAudioDuration(seconds) {
        if (!Number.isFinite(seconds) || seconds <= 0) return "";
        const total = Math.round(seconds);
        const mins = Math.floor(total / 60);
        const secs = total % 60;
        return mins > 0 ? `${mins}:${String(secs).padStart(2, "0")}` : `0:${String(secs).padStart(2, "0")}`;
      },
      updateSlideAudioDuration(event) {
        const seconds = Number(event?.target?.duration);
        this.slideAudioDuration = this.formatAudioDuration(seconds);
      },
      setMediaTarget(field) {
        this.mediaTarget = field || "";
      },
      openMediaBrowser(mediaType, targetSelector, options = {}) {
        if (!window.htmx) return;
        if (this.mediaBrowserTarget && this.mediaBrowserTarget !== targetSelector) {
          this.clearMediaBrowser();
        }
        this.mediaBrowserTarget = targetSelector || "";
        const query = new URLSearchParams();
        Object.entries(options || {}).forEach(([key, value]) => {
          if (value === undefined || value === null || value === "") return;
          query.set(key, String(value));
        });
        const url = "/authoring/media/browse/" + mediaType + (query.toString() ? "?" + query.toString() : "");
        window.htmx.ajax("GET", url, {
          target: targetSelector,
          swap: "innerHTML",
        });
      },
      clearMediaBrowser() {
        if (!this.mediaBrowserTarget) return;
        const container = document.querySelector(this.mediaBrowserTarget);
        if (container) {
          container.innerHTML = "";
        }
      },
      triggerSlideAudioUpload() {
        this.slideAudioUploadError = "";
        const input = this.$root.querySelector('[data-slide-audio-file-input]');
        if (!input) return;
        input.click();
      },
      async handleSlideAudioFileSelected(event) {
        const input = event?.target;
        const file = input?.files?.[0];
        if (!file) return;
        this.slideAudioUploadError = "";
        this.slideAudioUploading = true;
        try {
          const formData = new FormData();
          formData.append("file", file);
          formData.append("media_type", "audio");
          const response = await fetch("/authoring/media/upload", {
            method: "POST",
            body: formData,
            credentials: "same-origin",
            headers: { Accept: "application/json" },
          });
          let payload = {};
          try {
            payload = await response.json();
          } catch (_error) {
            payload = {};
          }
          if (!response.ok || !payload?.success || !payload?.path) {
            this.slideAudioUploadError = String(payload?.error || "Audio upload failed. Please try again.");
            return;
          }
          this.attachedSlideAudioUrl = payload.path;
          this.slideAudioDuration = "";
          const hiddenInput = this.$root.querySelector('[data-authoring-field="slide_audio_url"]');
          if (hiddenInput) {
            hiddenInput.value = payload.path;
            hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
            hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
          }
        } catch (_error) {
          this.slideAudioUploadError = "Audio upload failed. Please try again.";
        } finally {
          this.slideAudioUploading = false;
          this.slideAudioInputKey += 1;
          if (input) input.value = "";
        }
      },
      removeSlideAudio() {
        this.attachedSlideAudioUrl = "";
        this.slideAudioDuration = "";
        this.slideAudioUploadError = "";
        const input = this.$root.querySelector('[data-authoring-field="slide_audio_url"]');
        if (!input) return;
        input.value = "";
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
      },
      audioUrlFor(fieldName) {
        return String(this.attachedAudioUrls[fieldName] || "").trim();
      },
      updateFieldAudioDuration(event, fieldName) {
        const seconds = Number(event?.target?.duration);
        this.audioFieldDurations[fieldName] = this.formatAudioDuration(seconds);
      },
      triggerFieldAudioUpload(fieldName) {
        const input = this.$root.querySelector(`[data-audio-upload-input="${fieldName}"]`);
        if (!input) return;
        this.audioUploadErrors[fieldName] = "";
        input.click();
      },
      async handleFieldAudioSelected(event, fieldName) {
        const input = event?.target;
        const file = input?.files?.[0];
        if (!file) return;
        this.audioUploadErrors[fieldName] = "";
        this.audioUploadingField = fieldName;
        try {
          const formData = new FormData();
          formData.append("file", file);
          formData.append("media_type", "audio");
          const response = await fetch("/authoring/media/upload", {
            method: "POST",
            body: formData,
            credentials: "same-origin",
            headers: { Accept: "application/json" },
          });
          let payload = {};
          try {
            payload = await response.json();
          } catch (_error) {
            payload = {};
          }
          if (!response.ok || !payload?.success || !payload?.path) {
            this.audioUploadErrors[fieldName] = String(payload?.error || "Audio upload failed. Please try again.");
            return;
          }
          this.attachedAudioUrls[fieldName] = payload.path;
          this.audioFieldDurations[fieldName] = "";
          const hiddenInput = this.$root.querySelector(`[data-authoring-field="payload__${fieldName}"]`);
          if (hiddenInput) {
            hiddenInput.value = payload.path;
            hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
            hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
          }
        } catch (_error) {
          this.audioUploadErrors[fieldName] = "Audio upload failed. Please try again.";
        } finally {
          this.audioUploadingField = "";
          this.audioInputKeys[fieldName] = (this.audioInputKeys[fieldName] || 0) + 1;
          if (input) input.value = "";
        }
      },
      removeFieldAudio(fieldName) {
        this.attachedAudioUrls[fieldName] = "";
        this.audioFieldDurations[fieldName] = "";
        this.audioUploadErrors[fieldName] = "";
        const hiddenInput = this.$root.querySelector(`[data-authoring-field="payload__${fieldName}"]`);
        if (!hiddenInput) return;
        hiddenInput.value = "";
        hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
        hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
      },
      imageUrlFor(fieldName) {
        return String(this.attachedImageUrls[fieldName] || "").trim();
      },
      triggerImageUpload(fieldName) {
        const input = this.$root.querySelector(`[data-image-upload-input="${fieldName}"]`);
        if (!input) return;
        this.imageUploadErrors[fieldName] = "";
        input.click();
      },
      async handleImageFileSelected(event, fieldName) {
        const input = event?.target;
        const file = input?.files?.[0];
        if (!file) return;
        this.imageUploadErrors[fieldName] = "";
        this.imageUploadingField = fieldName;
        try {
          const formData = new FormData();
          formData.append("file", file);
          formData.append("media_type", "image");
          const response = await fetch("/authoring/media/upload", {
            method: "POST",
            body: formData,
            credentials: "same-origin",
            headers: { Accept: "application/json" },
          });
          let payload = {};
          try {
            payload = await response.json();
          } catch (_error) {
            payload = {};
          }
          if (!response.ok || !payload?.success || !payload?.path) {
            this.imageUploadErrors[fieldName] = String(payload?.error || "Image upload failed. Please try again.");
            return;
          }
          this.attachedImageUrls[fieldName] = payload.path;
          const hiddenInput = this.$root.querySelector(`[data-authoring-field="payload__${fieldName}"]`);
          if (hiddenInput) {
            hiddenInput.value = payload.path;
            hiddenInput.dispatchEvent(new Event("input", { bubbles: true }));
            hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));
          }
        } catch (_error) {
          this.imageUploadErrors[fieldName] = "Image upload failed. Please try again.";
        } finally {
          this.imageUploadingField = "";
          this.imageInputKeys[fieldName] = (this.imageInputKeys[fieldName] || 0) + 1;
          if (input) input.value = "";
        }
      },
      removeImageAttachment(fieldName) {
        this.attachedImageUrls[fieldName] = "";
        this.imageUploadErrors[fieldName] = "";
        const input = this.$root.querySelector(`[data-authoring-field="payload__${fieldName}"]`);
        if (!input) return;
        input.value = "";
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
      },
      closeSlideAudioPicker() {
        if (this.mediaBrowserTarget && this.mediaBrowserTarget.includes("slide-audio")) {
          const container = document.querySelector(this.mediaBrowserTarget);
          if (container) container.innerHTML = "";
          this.mediaBrowserTarget = "";
        }
      },
      toggleAdvanced() {
        this.advancedOpen = !this.advancedOpen;
      },
      autoSegmentBuildWord(rawWord) {
        const word = String(rawWord || "").trim();
        if (!word) return [];
        const graphemes = [
          "tch", "igh", "dge",
          "ck", "sh", "ch", "th", "wh", "ph", "ng", "nk", "qu",
          "ee", "oo", "ai", "ay", "oa", "ow", "oi", "oy", "ar", "or", "er", "ir", "ur", "ea", "ie",
        ];
        const units = [];
        let index = 0;
        const lower = word.toLowerCase();
        while (index < word.length) {
          const match = graphemes.find((item) => lower.startsWith(item, index));
          if (match) {
            units.push(word.slice(index, index + match.length));
            index += match.length;
          } else {
            units.push(word.slice(index, index + 1));
            index += 1;
          }
        }
        return units;
      },
      parseBuildUnitsInput(value) {
        const text = String(value || "").trim();
        if (!text) return [];
        if (/[\n,|]/.test(text)) {
          return text
            .split(/[\n,|]+/)
            .map((item) => item.trim())
            .filter(Boolean);
        }
        return this.autoSegmentBuildWord(text.replace(/\s+/g, ""));
      },
      parseSpellLetterPoolInput(value, fallbackWord = "") {
        const text = String(value || "").trim();
        if (text) {
          if (/[\n,|]/.test(text)) {
            return text
              .split(/[\n,|]+/)
              .map((item) => item.trim())
              .filter(Boolean);
          }
          return text.replace(/\s+/g, "").split("").filter(Boolean);
        }
        const fallback = String(fallbackWord || "").replace(/\s+/g, "");
        return fallback ? fallback.split("").filter(Boolean) : [];
      },
      parsePatternWordInput(value) {
        const text = String(value || "").trim();
        if (!text) return [];
        const segments = [];
        let plain = "";
        let highlighted = "";
        let inHighlight = false;
        for (const char of text) {
          if (char === "[" && !inHighlight) {
            if (plain) {
              segments.push({ text: plain, highlight: false });
              plain = "";
            }
            inHighlight = true;
            highlighted = "";
            continue;
          }
          if (char === "]" && inHighlight) {
            if (highlighted) {
              segments.push({ text: highlighted, highlight: true });
            }
            highlighted = "";
            inHighlight = false;
            continue;
          }
          if (inHighlight) highlighted += char;
          else plain += char;
        }
        if (highlighted) segments.push({ text: highlighted, highlight: true });
        if (plain) segments.push({ text: plain, highlight: false });
        return segments.filter((segment) => String(segment.text || "").trim());
      },
      addPatternWord() {
        if (this.patternWordInputs.length >= 4) return;
        this.patternWordInputs.push("");
      },
      removePatternWord(index) {
        if (this.patternWordInputs.length <= 2) return;
        this.patternWordInputs.splice(index, 1);
      },
      get parsedBuildUnits() {
        return this.parseBuildUnitsInput(this.buildUnitsInput);
      },
      get buildUnitsDelimited() {
        return this.parsedBuildUnits.join(", ");
      },
      get buildWordPreview() {
        return this.parsedBuildUnits.join("");
      },
      get parsedSpellLetterPool() {
        return this.parseSpellLetterPoolInput(this.spellLetterPoolInput, this.spellWordInput);
      },
      get spellLetterPoolDelimited() {
        return this.parsedSpellLetterPool.join(", ");
      },
      get spellWordPreview() {
        return String(this.spellWordInput || "").trim();
      },
      get parsedPatternWords() {
        return this.patternWordInputs
          .map((word) => this.parsePatternWordInput(word))
          .filter((segments) => segments.length);
      },
      get patternWordsJson() {
        return JSON.stringify(this.parsedPatternWords.map((segments) => ({ segments })));
      },
      get patternWordPreview() {
        return this.patternWordInputs.map((word) => String(word || "").trim()).filter(Boolean);
      },
      validateBeforeSubmit(event) {
        this.formErrors = {};
        this.generalErrors = [];
        ["teacher_cue"].forEach((fieldName) => {
          const value = String(this.requiredFields[fieldName] || "").trim();
          if (!value) {
            this.formErrors[fieldName] = "This field is required.";
          }
        });
        const slideTitle = String(this.requiredFields.slide_title || "").trim();
        if (!slideTitle) {
          this.formErrors.slide_title = "This field is required.";
        }
        if (this.slideType === "drag_letter" && this.parsedBuildUnits.length === 0) {
          this.formErrors.build_units = "Enter at least one build unit.";
        }
        if (this.slideType === "spell_word") {
          if (!this.spellWordPreview) {
            this.formErrors.spell_word = "Enter the correct word.";
          }
          if (this.parsedSpellLetterPool.length === 0) {
            this.formErrors.spell_letter_pool = "Enter at least one letter or unit.";
          }
        }
        if (this.slideType === "pattern_noticing") {
          if (this.parsedPatternWords.length < 2) {
            this.formErrors.pattern_words = "Enter at least two words.";
          }
          if (this.parsedPatternWords.length > 4) {
            this.formErrors.pattern_words = "Use no more than four words.";
          }
          if (!String(this.patternPrompt || "").trim()) {
            this.formErrors.pattern_prompt = "Enter the prompt.";
          }
        }
        if (Object.keys(this.formErrors).length || this.generalErrors.length) {
          event.preventDefault();
        }
      },
      handleHtmxError(event) {
        const xhr = event?.detail?.xhr;
        if (!xhr) return;
        this.generalErrors = [];
        try {
          const payload = JSON.parse(xhr.responseText || "{}");
          if (Array.isArray(payload.errors) && payload.errors.length) {
            this.generalErrors = payload.errors.map((item) => String(item || "").trim()).filter(Boolean);
          } else if (payload.detail) {
            this.generalErrors = [String(payload.detail)];
          } else {
            this.generalErrors = ["Save failed. Please review the form and try again."];
          }
        } catch (_error) {
          this.generalErrors = ["Save failed. Please review the form and try again."];
        }
        if (this.generalErrors.length) {
          this.$root.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      },
      applyMediaSelection(event) {
        if (!this.mediaTarget) return;
        const input = this.$root.querySelector('[data-authoring-field="' + this.mediaTarget + '"]');
        if (!input) return;
        input.value = event.detail.path || "";
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
        if (this.mediaTarget === "slide_audio_url") {
          this.attachedSlideAudioUrl = event.detail.path || "";
          this.slideAudioDuration = "";
        }
        this.clearMediaBrowser();
        this.mediaTarget = "";
      },
    };
  };

  window.itemListEditor = function itemListEditor(initialItems, subFields) {
    return {
      items: Array.isArray(initialItems) ? JSON.parse(JSON.stringify(initialItems)) : [],
      subFields: Array.isArray(subFields) ? subFields : [],
      pendingMediaTarget: null,
      mediaBrowserTarget: "",
      get serializedItems() {
        return JSON.stringify(this.items);
      },
      emptyItem() {
        const item = {};
        this.subFields.forEach((field) => {
          item[field.name] = defaultValueForType(field.type);
        });
        return item;
      },
      addItem() {
        this.items.push(this.emptyItem());
      },
      removeItem(index) {
        if (this.items.length > 1 && !window.confirm("Remove this item?")) return;
        this.items.splice(index, 1);
      },
      moveUp(index) {
        if (index <= 0) return;
        const item = this.items.splice(index, 1)[0];
        this.items.splice(index - 1, 0, item);
      },
      moveDown(index) {
        if (index >= this.items.length - 1) return;
        const item = this.items.splice(index, 1)[0];
        this.items.splice(index + 1, 0, item);
      },
      setPendingMediaTarget(rowIndex, fieldName) {
        this.pendingMediaTarget = { rowIndex, fieldName };
      },
      openMediaBrowser(mediaType, targetSelector) {
        if (!window.htmx) return;
        if (this.mediaBrowserTarget && this.mediaBrowserTarget !== targetSelector) {
          this.clearMediaBrowser();
        }
        this.mediaBrowserTarget = targetSelector || "";
        window.htmx.ajax("GET", "/authoring/media/browse/" + mediaType, {
          target: targetSelector,
          swap: "innerHTML",
        });
      },
      clearMediaBrowser() {
        if (!this.mediaBrowserTarget) return;
        const container = document.querySelector(this.mediaBrowserTarget);
        if (container) {
          container.innerHTML = "";
        }
      },
      applyMediaSelection(event) {
        if (!this.pendingMediaTarget) return;
        const { rowIndex, fieldName } = this.pendingMediaTarget;
        if (!this.items[rowIndex]) return;
        this.items[rowIndex][fieldName] = event.detail.path || "";
        this.clearMediaBrowser();
        this.pendingMediaTarget = null;
      },
    };
  };
})();
