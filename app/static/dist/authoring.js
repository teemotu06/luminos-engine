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
    return {
      slideType: config.slideType || "",
      requiredFields: Object.assign(
        {
          slide_title: "",
          teacher_cue: "",
          expected_response: "",
          correction_move: "",
        },
        config.requiredFields || {},
      ),
      formErrors: {},
      generalErrors: [],
      mediaTarget: "",
      mediaBrowserTarget: "",
      advancedOpen: false,
      markable: !!config.initialMarkable,
      setMediaTarget(field) {
        this.mediaTarget = field || "";
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
      toggleAdvanced() {
        this.advancedOpen = !this.advancedOpen;
      },
      validateBeforeSubmit(event) {
        this.formErrors = {};
        this.generalErrors = [];
        ["teacher_cue", "expected_response", "correction_move"].forEach((fieldName) => {
          const value = String(this.requiredFields[fieldName] || "").trim();
          if (!value) {
            this.formErrors[fieldName] = "This field is required.";
          }
        });
        const slideTitle = String(this.requiredFields.slide_title || "").trim();
        if (!slideTitle) {
          this.formErrors.slide_title = "This field is required.";
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
