(() => {
const ACTION_BUTTONS = {
reveal: { label: "Reveal Answer", icon: "Show", className: "slide-action-btn--reveal" },
reveal_answer: { label: "Reveal Answer", icon: "Show", className: "slide-action-btn--reveal" },
reveal_letter: { label: "Letter Answer", icon: "Letter", className: "slide-action-btn--reveal" },
produce_phase: { label: "Produce", icon: "Produce", className: "slide-action-btn--reveal" },
play_model: { label: "Play Model", icon: "Model", className: "slide-action-btn--audio" },
play_sound: { label: "Play Sound", icon: "Audio", className: "slide-action-btn--audio" },
play_audio: { label: "Play Sound", icon: "Audio", className: "slide-action-btn--audio" },
read_sentence: { label: "Read Aloud", icon: "Read", className: "slide-action-btn--audio" },
mark_students: { label: "STUDENTS", icon: "MARK", className: "slide-action-btn--mark" },
};
const AUDIO_FIELD_PRIORITY = [
"audio_url",
"audio",
"audio_file",
"audio_prompt",
"audio_support",
"blend_audio",
"word_audio",
];
function stableShuffle(items, seedSource = "") {
const list = Array.isArray(items) ? [...items] : [];
if (list.length <= 1) return list;
let seed = 0;
const source = String(seedSource || "");
for (let i = 0; i < source.length; i += 1) {
seed = ((seed * 31) + source.charCodeAt(i)) >>> 0;
}
const next = () => {
seed = (seed * 1664525 + 1013904223) >>> 0;
return seed / 4294967296;
};
for (let i = list.length - 1; i > 0; i -= 1) {
const j = Math.floor(next() * (i + 1));
[list[i], list[j]] = [list[j], list[i]];
}
return list;
}
window.teacherShell = (config = {}) => ({
lessonId:       config.lessonId       || "",
attemptId:      config.attemptId      || "",
initialSlideId: config.initialSlideId || "",
classId:        config.classId        || "",
className:      config.className      || "",
initialState:   config.initialState   || null,
roster:         config.roster         || [],
slides:         config.slides         || [],
slideTitles:    config.slideTitles    || {},
blocks:         config.blocks         || [],
slideBlocks:    config.slideBlocks    || {},
blockLabels:    config.blockLabels    || {},
slideContents:  config.slideContents  || {},
slidePayloads: config.slidePayloads || {},
slideViewTypes: config.slideViewTypes || {},
slideTeacherCues: config.slideTeacherCues || {},
slideExpectedResponses: config.slideExpectedResponses || {},
slideCorrectionMoves: config.slideCorrectionMoves || {},
slideTeacherPrompts: config.slideTeacherPrompts || {},
slideAudioUrls: config.slideAudioUrls || {},
slideMarkable: config.slideMarkable || {},
slideMarkingOptions: config.slideMarkingOptions || {},
slideTypeLabels: config.slideTypeLabels || {},
slideTypeControlActions: config.slideTypeControlActions || {},
activeSlideId: config.initialSlideId || config.slides?.[0] || "",
manualMarkingOpen: false,
audioPlaying: false,
currentAudioKey: "",
activePromptIndex: null,
activePromptText: "",
isNavigating: false,
pendingSlideId: "",
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
pollBaseInterval: 500,
pollCurrentInterval: 500,
wsSocket: null,
wsPingTimer: null,
studentStatuses: {},
persistedMarks: {},
lastLoadedMarkSlideId: "",
uiPhase: "",
markingMode: "none",
studentOutcomes: {},
pendingCount: 0,
secureCount: 0,
mixedCount: 0,
revisitCount: 0,
dragLetterPlaced: [],
dragLetterAvailable: [],
dragLetterRevealCount: 0,
spellWordPlaced: [],
spellWordAvailable: [],
spellWordTileSeed: 0,
patternNoticingRevealCount: 0,
get activeSlideIndex() {
return this.resolveSlideIndex(this.activeSlideId);
},
get activeSlideTitle() {
return this.slideTitles[this.activeSlideId] || "";
},
get activeSlidePayload() {
return this.slidePayloads[this.activeSlideId] || {};
},
get activeBlockId() {
return this.slideBlocks[this.activeSlideId] || "";
},
get activeBlockLabel() {
return this.blockLabels[this.activeBlockId] || `Block ${this.activeBlockId || ""}`.trim();
},
get blockStatus() {
const activeIdx = this.slides.indexOf(this.activeSlideId);
return this.blocks.map((blockId) => {
const blockSlideIndices = this.slides
.map((sid, i) => (this.slideBlocks[sid] === blockId ? i : -1))
.filter((i) => i !== -1);
if (!blockSlideIndices.length) return { id: blockId, status: "upcoming" };
const first = Math.min(...blockSlideIndices);
const last  = Math.max(...blockSlideIndices);
if (last < activeIdx)   return { id: blockId, status: "done" };
if (first <= activeIdx) return { id: blockId, status: "current" };
return { id: blockId, status: "upcoming" };
});
},
get blockProgressLabel() {
const idx = this.blocks.indexOf(this.activeBlockId);
if (idx === -1 || !this.blocks.length) return "";
return `${idx + 1} / ${this.blocks.length}`;
},
get currentBlockSlides() {
return this.slides.filter((slideId) => this.slideBlocks[slideId] === this.activeBlockId);
},
get currentBlockSlideCount() {
return this.currentBlockSlides.length || 0;
},
get currentBlockSlidePosition() {
const slides = this.currentBlockSlides;
const idx = slides.indexOf(this.activeSlideId);
return idx === -1 ? 0 : idx + 1;
},
get hasPrevBlock() {
const idx = this.blocks.indexOf(this.activeBlockId);
return idx > 0;
},
get hasNextBlock() {
const idx = this.blocks.indexOf(this.activeBlockId);
return idx !== -1 && idx < this.blocks.length - 1;
},
get slideContent() {
return this.slideContents[this.activeSlideId] || "";
},
get activeViewTypeLabel() {
const vt = this.slideViewTypes[this.activeSlideId] || "";
return this.slideTypeLabels[vt] || (vt ? vt.replace(/_/g, " ") : "");
},
get isDragLetterSlide() {
return (this.slideViewTypes[this.activeSlideId] || "") === "drag_letter";
},
get isSpellWordSlide() {
return (this.slideViewTypes[this.activeSlideId] || "") === "spell_word";
},
get isListenSpellSlide() {
return (this.slideViewTypes[this.activeSlideId] || "") === "listen_spell";
},
get isPatternNoticingSlide() {
return (this.slideViewTypes[this.activeSlideId] || "") === "pattern_noticing";
},
get isSoundMatchSlide() {
return (this.slideViewTypes[this.activeSlideId] || "") === "sound_match";
},
get soundMatchPayload() {
return this.slidePayloads[this.activeSlideId] || {};
},
get soundMatchCorrectChoice() {
const choice = String(this.soundMatchPayload.correct_choice || "A").trim().toUpperCase();
return choice === "B" ? "B" : "A";
},
get soundMatchCorrectAudio() {
const payload = this.soundMatchPayload;
const field = this.soundMatchCorrectChoice === "B" ? "pair_b_audio" : "pair_a_audio";
return String(payload[field] || "").trim();
},
get soundMatchCorrectWord() {
const payload = this.soundMatchPayload;
const field = this.soundMatchCorrectChoice === "B" ? "pair_b_example_word" : "pair_a_example_word";
return String(payload[field] || "").trim();
},
get soundMatchProductionCue() {
return String(this.soundMatchPayload.production_cue || "").trim();
},
get soundMatchKoreanFlag() {
return String(this.soundMatchPayload.korean_flag || "").trim();
},
get listenSpellTargetWord() {
const payload = this.slidePayloads[this.activeSlideId] || {};
return String(payload.target_word || "").trim();
},
get listenSpellTargetPattern() {
const payload = this.slidePayloads[this.activeSlideId] || {};
return String(payload.target_pattern || "").trim();
},
get patternNoticingWords() {
const payload = this.slidePayloads[this.activeSlideId] || {};
return Array.isArray(payload.words) ? payload.words : [];
},
get patternNoticingRevealMode() {
const payload = this.slidePayloads[this.activeSlideId] || {};
return String(payload.reveal_mode || "sequential");
},
get patternNoticingPrompt() {
const payload = this.slidePayloads[this.activeSlideId] || {};
return String(payload.prompt || "").trim();
},
get patternNoticingMaxReveal() {
return this.patternNoticingWords.length || 0;
},
get patternNoticingProgressLabel() {
return `${Math.min(this.patternNoticingRevealCount, this.patternNoticingMaxReveal)} / ${this.patternNoticingMaxReveal}`;
},
get patternNoticingBracketWords() {
return this.patternNoticingWords.map((word) => {
const segments = Array.isArray(word?.segments) ? word.segments : [];
return segments
.map((segment) => {
const text = String(segment?.text || "").trim();
if (!text) return "";
return segment?.highlight ? `[${text}]` : text;
})
.join("");
}).filter(Boolean);
},
get dragLetterSlotCount() {
const p = this.slidePayloads[this.activeSlideId] || {};
const slots = Array.isArray(p.slots) && p.slots.length ? p.slots : (Array.isArray(p.target_letters) ? p.target_letters : []);
return slots.length;
},
get dragLetterIsComplete() {
return this.dragLetterPlaced.length > 0 && this.dragLetterPlaced.every((l) => l !== null);
},
get dragLetterSelectionLetters() {
return this.dragLetterPlaced.map((item) => (item == null ? "" : String(item))).filter(Boolean);
},
get dragLetterIsCorrect() {
if (!this.dragLetterIsComplete) return false;
const p = this.slidePayloads[this.activeSlideId] || {};
const target = Array.isArray(p.slots) && p.slots.length
? p.slots
: (Array.isArray(p.target_letters) ? p.target_letters : []);
return this.dragLetterSelectionLetters.join("").toLowerCase() === target.join("").toLowerCase();
},
initDragLetter() {
if (!this.isDragLetterSlide) {
this.dragLetterRevealCount = 0;
this.dragLetterPlaced = [];
this.dragLetterAvailable = [];
return;
}
this.applyDragLetterRevealState(this.dragLetterRevealCount);
},
applyDragLetterRevealState(revealCount = 0) {
if (!this.isDragLetterSlide) {
this.dragLetterPlaced = [];
this.dragLetterAvailable = [];
return;
}
const p = this.slidePayloads[this.activeSlideId] || {};
const slots = Array.isArray(p.slots) && p.slots.length
? [...p.slots]
: (Array.isArray(p.target_letters) ? [...p.target_letters] : []);
const tiles = stableShuffle(
Array.isArray(p.draggable_letters) ? [...p.draggable_letters] : [],
`${this.activeSlideId}:drag_letter_tiles`
);
const clampedReveal = Math.max(0, Math.min(Number(revealCount || 0), slots.length));
const placed = slots.map((letter, index) => (index < clampedReveal ? letter : null));
const available = [...tiles];
for (let index = 0; index < clampedReveal; index += 1) {
const matchedIndex = available.indexOf(slots[index]);
if (matchedIndex !== -1) {
available.splice(matchedIndex, 1);
}
}
this.dragLetterRevealCount = clampedReveal;
this.dragLetterPlaced = placed;
this.dragLetterAvailable = available;
},
applyDragLetterSelection(selection = []) {
if (!this.isDragLetterSlide) {
this.dragLetterPlaced = [];
this.dragLetterAvailable = [];
return;
}
const p = this.slidePayloads[this.activeSlideId] || {};
const tiles = stableShuffle(
Array.isArray(p.draggable_letters) ? [...p.draggable_letters] : [],
`${this.activeSlideId}:drag_letter_tiles`
);
const normalized = Array.isArray(selection)
? selection.map((item) => (item == null ? null : String(item).trim() || null))
: [];
const placed = Array.from({ length: this.dragLetterSlotCount }, (_, index) => normalized[index] ?? null);
const available = [...tiles];
placed.forEach((letter) => {
if (!letter) return;
const matchedIndex = available.indexOf(letter);
if (matchedIndex !== -1) {
available.splice(matchedIndex, 1);
}
});
this.dragLetterRevealCount = placed.filter(Boolean).length;
this.dragLetterPlaced = placed;
this.dragLetterAvailable = available;
},
async persistDragLetterSelection() {
if (!this.classId || !this.isDragLetterSlide) return;
try {
await fetch(`/classes/${this.classId}/control/drag-letter-selection`, {
method: "POST",
headers: { "Content-Type": "application/json" },
credentials: "same-origin",
body: JSON.stringify({ letters: this.dragLetterPlaced }),
});
} catch (_err) {
// non-fatal — board will retry on next interaction
}
},
dragLetterTileClick(index) {
const letter = this.dragLetterAvailable[index];
if (letter === undefined) return;
const emptySlot = this.dragLetterPlaced.indexOf(null);
if (emptySlot === -1) return;
const available = [...this.dragLetterAvailable];
available.splice(index, 1);
this.dragLetterAvailable = available;
const placed = [...this.dragLetterPlaced];
placed[emptySlot] = letter;
this.dragLetterPlaced = placed;
this.dragLetterRevealCount = this.dragLetterPlaced.filter(Boolean).length;
void this.persistDragLetterSelection();
},
dragLetterSlotClick(slotIndex) {
const letter = this.dragLetterPlaced[slotIndex];
if (letter === null || letter === undefined) return;
const placed = [...this.dragLetterPlaced];
placed[slotIndex] = null;
this.dragLetterPlaced = placed;
this.dragLetterAvailable = [...this.dragLetterAvailable, letter];
this.dragLetterRevealCount = this.dragLetterPlaced.filter(Boolean).length;
void this.persistDragLetterSelection();
},
async dragLetterReset() {
this.initDragLetter();
await this.persistDragLetterSelection();
await this.resetLetterReveal();
},
get dragLetterMaxReveal() {
return this.dragLetterSlotCount;
},
get spellWordTargetLetters() {
const payload = this.slidePayloads[this.activeSlideId] || {};
const word = String(payload.correct_word || "").replace(/\s+/g, "");
return word ? word.split("").filter(Boolean) : [];
},
get spellWordSlotCount() {
return this.spellWordTargetLetters.length;
},
get spellWordFilledLetters() {
return this.spellWordPlaced
.map((item, slotIndex) => (item ? { ...item, slotIndex } : null))
.filter(Boolean);
},
get spellWordSelectionLetters() {
return this.spellWordFilledLetters.map((item) => item.letter);
},
get spellWordIsComplete() {
return this.spellWordSelectionLetters.length === this.spellWordSlotCount && this.spellWordSlotCount > 0;
},
get spellWordIsCorrect() {
if (!this.spellWordIsComplete) return false;
return this.spellWordSelectionLetters.join("").toLowerCase() === this.spellWordTargetLetters.join("").toLowerCase();
},
initSpellWord() {
if (!this.isSpellWordSlide) {
this.spellWordPlaced = [];
this.spellWordAvailable = [];
return;
}
const payload = this.slidePayloads[this.activeSlideId] || {};
const available = stableShuffle(
(Array.isArray(payload.letter_pool) ? [...payload.letter_pool] : [])
.map((item) => String(item || "").trim())
.filter(Boolean),
`${this.activeSlideId}:spell_word_tiles`
).map((letter, index) => ({
id: `${this.activeSlideId}-spell-tile-${this.spellWordTileSeed + index}-${letter}`,
letter,
}));
this.spellWordTileSeed += available.length + 1;
this.spellWordPlaced = Array.from({ length: this.spellWordSlotCount }, () => null);
this.spellWordAvailable = available;
},
applySpellWordRevealState(revealed = false) {
if (!this.isSpellWordSlide) {
this.spellWordPlaced = [];
this.spellWordAvailable = [];
return;
}
if (!revealed) {
this.initSpellWord();
return;
}
const answer = this.spellWordTargetLetters;
this.spellWordPlaced = answer.map((letter, index) => ({
id: `${this.activeSlideId}-spell-answer-${index}-${letter}`,
letter,
}));
this.spellWordAvailable = [];
},
async persistSpellWordSelection() {
if (!this.classId || !this.isSpellWordSlide) return;
const letters = this.spellWordFilledLetters.map((item) => item.letter);
try {
await fetch(`/classes/${this.classId}/control/spell-word-selection`, {
method: "POST",
headers: { "Content-Type": "application/json" },
credentials: "same-origin",
body: JSON.stringify({ letters }),
});
} catch (_err) {
// non-fatal — board will retry on next interaction
}
},
spellWordTileClick(index) {
const tile = this.spellWordAvailable[index];
if (!tile) return;
const emptySlot = this.spellWordPlaced.indexOf(null);
if (emptySlot === -1) return;
const available = [...this.spellWordAvailable];
available.splice(index, 1);
this.spellWordAvailable = available;
const placed = [...this.spellWordPlaced];
placed[emptySlot] = tile;
this.spellWordPlaced = placed;
void this.persistSpellWordSelection();
},
spellWordSlotClick(slotIndex) {
const tile = this.spellWordPlaced[slotIndex];
if (!tile) return;
const placed = [...this.spellWordPlaced];
placed[slotIndex] = null;
this.spellWordPlaced = placed;
this.spellWordAvailable = [...this.spellWordAvailable, tile];
void this.persistSpellWordSelection();
},
async spellWordReset() {
this.initSpellWord();
await this.persistSpellWordSelection();
if (this.isAnswerRevealed) {
await this.handleControl("hide_answer");
}
},
async revealNextLetter() {
if (!this.classId) return;
const next = Math.min(this.dragLetterRevealCount + 1, this.dragLetterMaxReveal);
try {
const response = await fetch(`/classes/${this.classId}/control/letter-reveal`, {
method: "POST",
headers: { "Content-Type": "application/json" },
credentials: "same-origin",
body: JSON.stringify({ count: next }),
});
if (!response.ok) throw new Error(`Letter reveal failed (${response.status})`);
const data = await response.json();
this.applyDragLetterRevealState(Number(data.letter_reveal_count || 0));
await this.persistDragLetterSelection();
} catch (_err) {
// non-fatal — board will re-sync on next poll
}
},
async resetLetterReveal() {
if (!this.classId) return;
try {
const response = await fetch(`/classes/${this.classId}/control/letter-reveal`, {
method: "POST",
headers: { "Content-Type": "application/json" },
credentials: "same-origin",
body: JSON.stringify({ count: 0 }),
});
if (!response.ok) throw new Error(`Letter reveal reset failed (${response.status})`);
const data = await response.json();
this.applyDragLetterRevealState(Number(data.letter_reveal_count || 0));
await this.persistDragLetterSelection();
} catch (_err) {
// non-fatal
}
},
async syncLetterRevealCount() {
if (!this.classId || !this.isDragLetterSlide) {
this.dragLetterRevealCount = 0;
return;
}
try {
const response = await fetch(`/classes/${this.classId}/session-state`, {
cache: "no-store",
credentials: "same-origin",
});
if (!response.ok) return;
const data = await response.json();
if (data.slide_id !== this.activeSlideId) {
this.applyDragLetterRevealState(0);
} else if (Array.isArray(data.drag_letter_selection) && data.drag_letter_selection.length) {
this.applyDragLetterSelection(data.drag_letter_selection);
} else {
this.applyDragLetterRevealState(Number(data.letter_reveal_count || 0));
}
} catch (_err) {
// non-fatal
}
},
async syncPatternNoticingRevealCount() {
if (!this.classId || !this.isPatternNoticingSlide) {
this.patternNoticingRevealCount = 0;
return;
}
try {
const response = await fetch(`/classes/${this.classId}/session-state`, {
cache: "no-store",
credentials: "same-origin",
});
if (!response.ok) return;
const data = await response.json();
this.patternNoticingRevealCount =
data.slide_id === this.activeSlideId ? Number(data.pattern_noticing_reveal_count || 0) : 0;
} catch (_err) {
// non-fatal
}
},
async setPatternNoticingRevealCount(count) {
if (!this.classId || !this.isPatternNoticingSlide) return;
try {
const response = await fetch(`/classes/${this.classId}/control/pattern-noticing-reveal`, {
method: "POST",
headers: { "Content-Type": "application/json" },
credentials: "same-origin",
body: JSON.stringify({ count }),
});
if (!response.ok) throw new Error(`Pattern reveal failed (${response.status})`);
const data = await response.json();
this.patternNoticingRevealCount = Number(data.pattern_noticing_reveal_count || 0);
} catch (_err) {
// non-fatal
}
},
get activeTeacherCue() {
return this.slideTeacherCues[this.activeSlideId] || this.promptText || "";
},
get activeExpectedResponse() {
return this.slideExpectedResponses[this.activeSlideId] || "";
},
get activeCorrectionMove() {
return this.slideCorrectionMoves[this.activeSlideId] || "";
},
get activeSlideMetaLine() {
return `${this.activeViewTypeLabel} · ${this.activeSlideId || ""}`.trim();
},
get activeSlideSummary() {
if (this.activeSlideTitle) return `${this.activeViewTypeLabel}: ${this.activeSlideTitle}`;
return this.activeViewTypeLabel;
},
get currentSlideMarkable() {
return !!this.slideMarkable[this.activeSlideId];
},
get currentMarkingOptions() {
const options = this.slideMarkingOptions[this.activeSlideId] || [];
return options.length ? options : ["secure", "shaky", "missed"];
},
get currentSlideActions() {
const viewType = this.slideViewTypes[this.activeSlideId] || "";
const actions = Array.isArray(this.slideTypeControlActions[this.activeSlideId]) ? [...this.slideTypeControlActions[this.activeSlideId]] : [];
const normalized = actions
.map((action) => {
if (viewType === "drag_letter" && ["reveal", "reveal_answer"].includes(action)) {
return "reveal_letter";
}
return action;
})
.filter((action, index, array) => array.indexOf(action) === index);
if (this.isSoundMatchSlide) {
const phaseActions = {
listening: ["play_sound", "reveal_answer"],
revealed: ["produce_phase", "reveal_answer", "mark_students"],
produce: ["play_model", "reveal_answer"],
};
const allowed = phaseActions[this.currentState] || phaseActions.listening;
return normalized.filter((action) => {
if (!allowed.includes(action)) return false;
if (action === "mark_students") return this.currentSlideMarkable && this.roster.length > 0;
return true;
});
}
return normalized.filter((action) => {
if (action === "prompts") return false;
if (action === "mark_students") return this.currentSlideMarkable && this.roster.length > 0;
return true;
});
},
get isAnswerRevealed() {
if (this.isListenSpellSlide) {
return this.currentState === "revealed";
}
if (this.isSoundMatchSlide) {
return ["revealed", "produce"].includes(this.currentState);
}
return !["idle", "transition"].includes(this.currentState);
},
get hasPersistentMarkButton() {
return this.roster.length > 0;
},
get currentTeacherPrompts() {
return Array.isArray(this.slideTeacherPrompts[this.activeSlideId]) ? this.slideTeacherPrompts[this.activeSlideId] : [];
},
get hasPromptPanel() {
return this.currentTeacherPrompts.length > 0;
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
get teachingMode() {
if (this.currentState === "idle") return "ready";
return "teach";
},
get gridCompletionPercent() {
if (!this.roster.length) return 0;
return Math.round(((this.roster.length - this.pendingCount) / this.roster.length) * 100);
},
// Max 8 words shown in deliver mode — teacher glances, not reads
get deliverScript() {
const text = String(this.promptText || "").trim();
const words = text.split(/\s+/);
if (words.length <= 8) return text;
return words.slice(0, 8).join(" ") + "…";
},
get primaryAudioUrl() {
const explicit = this.slideAudioUrls[this.activeSlideId];
if (typeof explicit === "string" && explicit.trim()) return explicit.trim();
const payload = this.activeSlidePayload || {};
for (const field of AUDIO_FIELD_PRIORITY) {
const value = payload[field];
if (typeof value === "string" && value.trim()) return value.trim();
}
if (Array.isArray(payload.items)) {
const itemAudio = payload.items.find((item) => item && typeof item.audio_url === "string" && item.audio_url.trim());
if (itemAudio) return itemAudio.audio_url.trim();
}
return "";
},
get primaryMarkControls() {
const primary = ["mark_secure", "mark_shaky", "mark_missed"];
return primary.filter((c) => this.teacherControls.includes(c));
},
get overflowMarkControls() {
const overflow = ["mark_deferred", "mark_absent", "mark_class", "skip"];
return overflow.filter((c) => this.teacherControls.includes(c));
},
get deliverControls() {
const deliver = ["replay", "pause", "force_advance"];
return deliver.filter((c) => this.teacherControls.includes(c));
},
get roomTemperature() {
const statuses = Object.values(this.studentStatuses);
if (!statuses.length) return "neutral";
const secured = statuses.filter((s) => s === "secure").length;
const missed = statuses.filter((s) => s === "missed").length;
if (secured / statuses.length >= 0.65) return "warm";
if (missed / statuses.length >= 0.35) return "cold";
return "mixed";
},
get roomTempPercent() {
const total = Object.keys(this.studentStatuses).length;
if (!total || !this.roster.length) return 0;
const marked = Object.values(this.studentStatuses).filter(
(s) => s && s !== "absent"
).length;
return Math.round((marked / this.roster.length) * 100);
},
get timerIsUrgent() {
if (!this.stateTimeoutMs || !this.stateStartedAt) return false;
const startedAt = Date.parse(this.stateStartedAt);
if (!Number.isFinite(startedAt)) return false;
const remaining = Math.max(0, startedAt + this.stateTimeoutMs - Date.now());
return remaining < 5000 && remaining > 0;
},
markLabel(control) {
const labels = {
mark_secure: "Got it",
mark_shaky: "Mixed",
mark_missed: "Revisit",
mark_deferred: "Deferred",
mark_absent: "Absent",
mark_class: "Whole class",
skip: "Skip",
};
return labels[control] || control.replaceAll("_", " ");
},
markSubLabel(control) {
const sub = {
mark_secure: "understood well",
mark_shaky: "needs reinforcing",
mark_missed: "reteach needed",
};
return sub[control] || "";
},
chipClass(student) {
if (student === this.currentStudent) return "chip chip--active";
const outcome = this.studentOutcomes[student];
if (outcome === "secure")  return "chip chip--secure";
if (outcome === "mixed")   return "chip chip--mixed";
if (outcome === "revisit") return "chip chip--revisit";
return "chip chip--waiting";
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
triggerPrimaryAction() {
if (this.teachingMode === "complete") {
if (this.activeSlideIndex < this.slides.length - 1) void this.goNextSlide();
} else if (this.teachingMode === "mark_sequential") {
const primary = this.primaryMarkControls[0];
if (primary) void this.handleControl(primary);
} else if (this.teachingMode === "deliver" || this.teachingMode === "observe") {
const advance = this.teacherControls.includes("force_advance") ? "force_advance" : null;
if (advance) void this.handleControl(advance);
} else if (this.teachingMode === "ready") {
void this.handleControl("force_advance");
}
},
_onKeyDown(e) {
if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
if (e.code === "Space" || e.key === " ") {
e.preventDefault();
this.triggerPrimaryAction();
}
},
init() {
this.startTimerTicker();
this.activeSlideId = this.syncResolvedSlideId(this.initialSlideId || this.activeSlideId);
this.initDragLetter();
this.initSpellWord();
if (this.$refs.slideAudio) {
this.$refs.slideAudio.addEventListener("play", () => { this.audioPlaying = true; });
this.$refs.slideAudio.addEventListener("ended", () => {
this.audioPlaying = false;
this.currentAudioKey = "";
});
this.$refs.slideAudio.addEventListener("pause", () => {
this.audioPlaying = false;
if (!this.$refs.slideAudio.currentTime || this.$refs.slideAudio.ended) {
this.currentAudioKey = "";
}
});
}
if (this.initialState) {
this.applyState(this.initialState);
this.connectionStatus = "ok";
}
if (this.activeSlideId) {
void this.loadPersistedMarks(this.activeSlideId);
void this.syncLetterRevealCount();
void this.syncPatternNoticingRevealCount();
}
void this.poll().then(() => this.schedulePoll());
this.connectWebSocket();
this._boundKeyDown = this._onKeyDown.bind(this);
window.addEventListener("keydown", this._boundKeyDown);
},
connectWebSocket() {
if (!this.lessonId || !this.attemptId) return;
const proto = location.protocol === "https:" ? "wss:" : "ws:";
const url = `${proto}//${location.host}/lesson/${this.lessonId}/ws/${this.attemptId}`;
const ws = new WebSocket(url);
this.wsSocket = ws;
ws.onmessage = (event) => {
try {
const data = JSON.parse(event.data);
if (data && typeof data === "object") {
// Skip if teacher is mid-navigation (pending slide differs from incoming)
if (this.isNavigating && this.pendingSlideId && data.slide_id !== this.pendingSlideId) return;
this.applyState(data);
if (this.pendingSlideId && data.slide_id === this.pendingSlideId) {
this.pendingSlideId = "";
this.isNavigating = false;
}
if (this.consecutiveFailures > 0) {
this.pollCurrentInterval = this.pollBaseInterval;
this.consecutiveFailures = 0;
}
if (this.clientStatusTone === "error") this.clearClientStatus();
}
} catch (_) {}
};
ws.onopen = () => {
if (this.wsPingTimer) window.clearInterval(this.wsPingTimer);
this.wsPingTimer = window.setInterval(() => {
if (ws.readyState === WebSocket.OPEN) ws.send("ping");
}, 20000);
};
ws.onclose = () => {
if (this.wsPingTimer) { window.clearInterval(this.wsPingTimer); this.wsPingTimer = null; }
this.wsSocket = null;
window.setTimeout(() => this.connectWebSocket(), 3000);
};
ws.onerror = () => {};
},
schedulePoll() {
if (this.pollTimer) window.clearTimeout(this.pollTimer);
this.pollTimer = window.setTimeout(async () => {
this.pollTimer = null;
await this.poll();
this.schedulePoll();
}, this.pollCurrentInterval);
},
destroy() {
if (this.autoAdvanceTimer) {
window.clearTimeout(this.autoAdvanceTimer);
this.autoAdvanceTimer = null;
}
if (this.pollTimer) {
window.clearTimeout(this.pollTimer);
this.pollTimer = null;
}
if (this.wsPingTimer) {
window.clearInterval(this.wsPingTimer);
this.wsPingTimer = null;
}
if (this.wsSocket) {
this.wsSocket.onclose = null;
this.wsSocket.close();
this.wsSocket = null;
}
if (this._boundKeyDown) {
window.removeEventListener("keydown", this._boundKeyDown);
this._boundKeyDown = null;
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
const versionAtSchedule = this.stateVersion;
this.autoAdvanceTimer = window.setTimeout(() => {
this.autoAdvanceTimer = null;
if (this.stateVersion !== versionAtSchedule) return;
void this.handleControl("force_advance");
}, remaining);
},
async poll() {
if (!this.activeSlideId) return;
try {
const response = await fetch(`/lesson/${this.lessonId}/command-state/${this.attemptId}`);
if (!response.ok) {
throw new Error(`Command state request failed (${response.status})`);
}
const data = await response.json();
if (this.isNavigating && this.pendingSlideId && data.slide_id !== this.pendingSlideId) {
return;
}
this.applyState(data);
if (this.pendingSlideId && data.slide_id === this.pendingSlideId) {
this.pendingSlideId = "";
this.isNavigating = false;
}
this.connectionStatus = "ok";
if (this.consecutiveFailures > 0) {
this.pollCurrentInterval = this.pollBaseInterval;
this.consecutiveFailures = 0;
}
if (this.clientStatusTone === "error") {
this.clearClientStatus();
}
} catch (error) {
this.consecutiveFailures += 1;
this.connectionStatus = this.consecutiveFailures >= 3 ? "degraded" : "connecting";
this.pollCurrentInterval = Math.min(this.pollCurrentInterval * 2, 8000);
this.lastResult = error.message;
if (this.consecutiveFailures >= 5) {
if (this.pollTimer) {
window.clearTimeout(this.pollTimer);
this.pollTimer = null;
}
this.connectionStatus = "lost";
this.setRetryClientAction("Tap to reconnect", () => {
this.pollCurrentInterval = this.pollBaseInterval;
this.consecutiveFailures = 0;
void this.poll().then(() => this.schedulePoll());
});
this.setClientStatus("Connection lost — tap to reconnect", "error");
return;
}
this.setRetryClientAction("Retry connection", () => this.poll());
this.setClientStatus(error.message, "error");
}
},
resolveSlideIndex(slideId) {
if (!slideId) return -1;
return this.slides.indexOf(slideId);
},
syncResolvedSlideId(slideId) {
const nextIndex = this.resolveSlideIndex(slideId);
if (nextIndex !== -1) {
return this.slides[nextIndex];
}
return this.slides[0] || "";
},
applyState(data) {
const previousState = this.currentState;
const previousStartedAt = this.stateStartedAt;
const previousSlideId = this.activeSlideId;
const wasAnswerRevealed = this.isAnswerRevealed;
if (previousSlideId && data.slide_id && previousSlideId !== data.slide_id && this.$refs.slideAudio) {
this.$refs.slideAudio.pause();
this.$refs.slideAudio.currentTime = 0;
this.currentAudioKey = "";
this.audioPlaying = false;
}
if (data.slide_id) {
const nextIndex = this.resolveSlideIndex(data.slide_id);
if (nextIndex === -1) {
console.error("Teacher received unknown slide_id", data.slide_id, this.slides);
this.setClientStatus(`Slide sync error: unknown slide ${data.slide_id}`, "error");
return;
}
this.activeSlideId = this.slides[nextIndex];
}
this.activePromptIndex = null;
this.activePromptText = "";
if (previousSlideId !== this.activeSlideId) {
this.manualMarkingOpen = false;
this.persistedMarks = {};
this.initDragLetter();
this.initSpellWord();
void this.syncLetterRevealCount();
void this.syncPatternNoticingRevealCount();
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
this.uiPhase = data.ui_phase || "";
this.markingMode = data.marking_mode || "none";
this.studentOutcomes = data.student_outcomes || {};
this.pendingCount = data.pending_count ?? 0;
this.secureCount = data.secure_count ?? 0;
this.mixedCount = data.mixed_count ?? 0;
this.revisitCount = data.revisit_count ?? 0;
this.studentStatuses = {
...this.studentStatuses,
...(this.currentStudent && this.currentState === "complete" ? { [this.currentStudent]: "complete" } : {}),
};
this.refreshTimerLabel();
if (this.isSpellWordSlide) {
if (this.isAnswerRevealed) {
this.applySpellWordRevealState(true);
} else if (wasAnswerRevealed && !this.isAnswerRevealed) {
this.applySpellWordRevealState(false);
} else if (Array.isArray(data.spell_word_selection)) {
const selectedLetters = data.spell_word_selection.map((item) => String(item || "").trim()).filter(Boolean);
if (selectedLetters.length) {
const answerSlots = Array.from({ length: this.spellWordSlotCount }, () => null);
const available = [...this.spellWordAvailable];
selectedLetters.forEach((letter, idx) => {
const matchIndex = available.findIndex((tile) => tile && tile.letter === letter);
if (matchIndex !== -1 && idx < answerSlots.length) {
answerSlots[idx] = available.splice(matchIndex, 1)[0];
}
});
this.spellWordPlaced = answerSlots;
this.spellWordAvailable = available;
} else {
this.initSpellWord();
}
}
}
if (this.isDragLetterSlide) {
if (Array.isArray(data.drag_letter_selection) && data.drag_letter_selection.length) {
this.applyDragLetterSelection(data.drag_letter_selection);
} else if (typeof data.letter_reveal_count === "number") {
this.applyDragLetterRevealState(Number(data.letter_reveal_count || 0));
}
}
if (this.currentState !== previousState || this.stateStartedAt !== previousStartedAt || this.paused) {
this.scheduleTimedAdvance();
}
if (previousSlideId !== this.activeSlideId) {
void this.loadPersistedMarks(this.activeSlideId);
}
},
async syncActiveSlide(slideId) {
if (!slideId) return null;
const response = await fetch(`/lesson/${this.lessonId}/command-state/${this.attemptId}/active-slide`, {
method: "POST",
headers: { "Content-Type": "application/json" },
body: JSON.stringify({ slide_id: slideId }),
});
if (!response.ok) {
throw new Error(`Slide sync failed (${response.status})`);
}
return response.json();
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
force_advance: "Next step →",
};
return labels[control] || control.replaceAll("_", " ");
},
actionLabel(action) {
const config = ACTION_BUTTONS[action];
if (!config) return action.replaceAll("_", " ");
if (this.isPatternNoticingSlide && ["reveal", "reveal_answer"].includes(action)) {
if (this.patternNoticingRevealMode === "sequential") {
return this.patternNoticingRevealCount >= this.patternNoticingMaxReveal ? "Hide" : "Reveal Pattern";
}
return this.patternNoticingRevealCount >= this.patternNoticingMaxReveal ? "Hide" : "Reveal Pattern";
}
if (action === "reveal_letter") {
return this.dragLetterRevealCount >= this.dragLetterMaxReveal ? "Hide" : "Letter Answer";
}
if (this.isListenSpellSlide && ["reveal", "reveal_answer"].includes(action)) {
return this.isAnswerRevealed ? "Hide" : "Reveal";
}
if (this.isSoundMatchSlide) {
if (action === "reveal_answer") return "Reveal";
if (action === "produce_phase") return "Produce";
if (action === "play_model") return "Play Model";
}
if (["reveal", "reveal_answer"].includes(action)) {
return this.isAnswerRevealed ? "Hide" : "Answer";
}
return `${config.icon} ${config.label}`;
},
actionButtonClass(action) {
const config = ACTION_BUTTONS[action];
const classes = {};
if (config && config.className) classes[config.className] = true;
if (this.audioPlaying && ["play_sound", "play_audio", "read_sentence"].includes(action) && this.currentAudioKey === "slide") {
classes["slide-action-btn--active"] = true;
}
return classes;
},
actionDisabled(action) {
if (this.isPatternNoticingSlide && ["reveal", "reveal_answer"].includes(action)) {
return !this.classId || !this.patternNoticingMaxReveal;
}
if (this.isSoundMatchSlide) {
if (["play_sound", "play_model"].includes(action)) {
return !this.soundMatchCorrectAudio;
}
if (action === "mark_students") {
return this.currentState !== "revealed" || !this.currentSlideMarkable || !this.roster.length;
}
}
if (action === "reveal_letter") {
return !this.classId || !this.dragLetterMaxReveal;
}
if (["play_sound", "play_audio", "read_sentence"].includes(action)) {
return !this.primaryAudioUrl;
}
if (action === "mark_students") {
return !this.currentSlideMarkable || !this.roster.length;
}
return false;
},
actionTooltip(action) {
if (this.actionDisabled(action) && ["play_sound", "play_audio", "read_sentence"].includes(action)) {
return "No audio attached";
}
return "";
},
isSelectedMark(student, option) {
return (this.persistedMarks[student] || "") === String(option || "").trim().toLowerCase();
},
async loadPersistedMarks(slideId = this.activeSlideId) {
if (!slideId || !this.attemptId || !this.roster.length) {
this.persistedMarks = {};
this.lastLoadedMarkSlideId = "";
return;
}
if (slideId === this.lastLoadedMarkSlideId) {
return;
}
try {
this.lastLoadedMarkSlideId = slideId;
const response = await fetch(
`/lesson/${this.lessonId}/student-marks?attempt_id=${encodeURIComponent(this.attemptId)}&slide_id=${encodeURIComponent(slideId)}`
);
if (!response.ok) {
throw new Error(`Mark load failed (${response.status})`);
}
const rows = await response.json();
if (slideId !== this.activeSlideId) return;
this.persistedMarks = rows.reduce((acc, row) => {
acc[row.student_name] = row.status;
return acc;
}, {});
} catch (error) {
this.persistedMarks = {};
this.lastLoadedMarkSlideId = "";
this.setRetryClientAction("Retry marks", () => this.loadPersistedMarks(slideId));
this.setClientStatus(error.message, "error");
}
},
async handleStudentMark(student, option) {
const status = String(option || "").trim().toLowerCase();
const previous = this.persistedMarks[student] || "";
this.persistedMarks = { ...this.persistedMarks, [student]: status };
try {
const response = await fetch(`/lesson/${this.lessonId}/student-mark`, {
method: "POST",
headers: { "Content-Type": "application/json" },
body: JSON.stringify({
attempt_id: this.attemptId,
lesson_id: this.lessonId,
slide_id: this.activeSlideId,
block_id: this.activeBlockId,
student_name: student,
status,
error_tags: [],
support_level: null,
teacher_note: null,
}),
});
if (!response.ok) throw new Error(`Mark failed (${response.status})`);
this.clearClientStatus();
} catch (error) {
const rollback = { ...this.persistedMarks };
if (previous) rollback[student] = previous;
else delete rollback[student];
this.persistedMarks = rollback;
this.setRetryClientAction("Retry mark", () => this.handleStudentMark(student, option));
this.setClientStatus(error.message, "error");
}
},
async playAudio(url, key) {
if (!url || !this.$refs.slideAudio) return;
const player = this.$refs.slideAudio;
try {
if (this.currentAudioKey === key && !player.paused) {
player.pause();
player.currentTime = 0;
this.currentAudioKey = "";
this.audioPlaying = false;
return;
}
if (player.src !== url) {
player.src = url;
}
player.currentTime = 0;
this.currentAudioKey = key;
await player.play();
} catch (_) {
this.currentAudioKey = "";
this.audioPlaying = false;
}
},
async playCurrentAudio() {
if (!this.primaryAudioUrl) return;
this.activePromptIndex = null;
this.activePromptText = "";
await this.playAudio(this.primaryAudioUrl, "slide");
},
isPromptPlaying(index) {
return this.currentAudioKey === `prompt-${index}` || this.activePromptIndex === index;
},
promptButtonLabel(prompt, index) {
const text = String((prompt && prompt.text) || "").trim() || `Prompt ${index + 1}`;
const icon = prompt && prompt.audio_url ? (this.currentAudioKey === `prompt-${index}` ? "■" : "▶") : "📖";
return `${icon} ${text}`;
},
async handlePromptAction(index) {
const prompt = this.currentTeacherPrompts[index];
if (!prompt) return;
this.activePromptIndex = index;
this.activePromptText = prompt.text || "";
if (prompt.audio_url) {
await this.playAudio(prompt.audio_url, `prompt-${index}`);
}
},
async handleSlideAction(action) {
if (this.actionDisabled(action)) return;
if (action === "mark_students") {
this.manualMarkingOpen = !this.manualMarkingOpen;
return;
}
if (this.isPatternNoticingSlide && ["reveal", "reveal_answer"].includes(action)) {
if (this.patternNoticingRevealCount >= this.patternNoticingMaxReveal) {
await this.setPatternNoticingRevealCount(0);
} else if (this.patternNoticingRevealMode === "sequential") {
await this.setPatternNoticingRevealCount(this.patternNoticingRevealCount + 1);
} else {
await this.setPatternNoticingRevealCount(this.patternNoticingMaxReveal);
}
return;
}
if (this.isSoundMatchSlide) {
if (action === "play_sound" || action === "play_model") {
await this.playAudio(this.soundMatchCorrectAudio, "slide");
return;
}
if (action === "reveal_answer") {
await this.handleControl(this.isAnswerRevealed ? "hide_answer" : "force_advance");
return;
}
if (action === "produce_phase") {
await this.handleControl("force_advance");
return;
}
}
if (action === "reveal_letter") {
if (this.dragLetterRevealCount >= this.dragLetterMaxReveal) await this.resetLetterReveal();
else await this.revealNextLetter();
return;
}
if (["play_sound", "play_audio", "read_sentence"].includes(action)) {
await this.playCurrentAudio();
return;
}
if (["reveal", "reveal_answer"].includes(action)) {
await this.handleControl(this.isAnswerRevealed ? "hide_answer" : "force_advance");
}
},
async handleControl(control) {
let payload = { slide_id: this.activeSlideId, action: "force_advance" };
let prevStatus = null;
let optimisticStudent = null;
if (control.startsWith("mark_")) {
if (control === "mark_class") {
payload = { slide_id: this.activeSlideId, action: "mark_class", status: "secure" };
} else {
const status = control.replace("mark_", "");
payload = { slide_id: this.activeSlideId, action: "mark", student: this.currentStudent, status };
if (this.currentStudent) {
optimisticStudent = this.currentStudent;
prevStatus = this.studentStatuses[this.currentStudent] ?? null;
this.studentStatuses = { ...this.studentStatuses, [this.currentStudent]: status };
}
}
} else if (control === "skip") {
payload = { slide_id: this.activeSlideId, action: "skip", student: this.currentStudent };
if (this.currentStudent) {
optimisticStudent = this.currentStudent;
prevStatus = this.studentStatuses[this.currentStudent] ?? null;
this.studentStatuses = { ...this.studentStatuses, [this.currentStudent]: "deferred" };
}
} else if (control === "replay") {
payload = { slide_id: this.activeSlideId, action: "replay" };
} else if (control === "pause") {
payload = { slide_id: this.activeSlideId, action: this.paused ? "resume" : "pause" };
} else if (control === "force_advance") {
payload = { slide_id: this.activeSlideId, action: "force_advance" };
} else if (control === "hide_answer") {
payload = { slide_id: this.activeSlideId, action: "hide_answer" };
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
// Roll back optimistic student status update
if (optimisticStudent !== null) {
if (prevStatus === null) {
const { [optimisticStudent]: _removed, ...rest } = this.studentStatuses;
this.studentStatuses = rest;
} else {
this.studentStatuses = { ...this.studentStatuses, [optimisticStudent]: prevStatus };
}
}
this.lastResult = error.message;
this.setRetryClientAction("Retry action", () => this.handleControl(control));
this.setClientStatus(error.message, "error");
}
},
async handleGridMark(student) {
const prev = this.studentOutcomes[student] || "pending";
const cycle = ["pending", "secure", "mixed", "revisit"];
const next = cycle[(cycle.indexOf(prev) + 1) % cycle.length];
// Optimistic update
this.studentOutcomes = { ...this.studentOutcomes, [student]: next };
this._recomputeOutcomeCounts();
try {
const response = await fetch(`/lesson/${this.lessonId}/command-state/${this.attemptId}/advance`, {
method: "POST",
headers: { "Content-Type": "application/json" },
body: JSON.stringify({ slide_id: this.activeSlideId, action: "mark_grid", student, status: next }),
});
if (!response.ok) throw new Error(`Grid mark failed (${response.status})`);
this.applyState(await response.json());
this.clearClientStatus();
} catch (error) {
// Roll back optimistic update
this.studentOutcomes = { ...this.studentOutcomes, [student]: prev };
this._recomputeOutcomeCounts();
this.setRetryClientAction("Retry mark", () => this.handleGridMark(student));
this.setClientStatus(error.message, "error");
}
},
_recomputeOutcomeCounts() {
const vals = Object.values(this.studentOutcomes);
this.pendingCount = vals.filter((s) => s === "pending").length;
this.secureCount = vals.filter((s) => s === "secure").length;
this.mixedCount = vals.filter((s) => s === "mixed").length;
this.revisitCount = vals.filter((s) => s === "revisit").length;
},
async goPrevSlide() {
if (this.isNavigating) return;
const currentIndex = this.activeSlideIndex;
if (currentIndex <= 0) return;
const targetSlideId = this.slides[currentIndex - 1] || "";
if (!targetSlideId) return;
this.lastResult = "";
this.clearClientStatus();
try {
this.isNavigating = true;
this.pendingSlideId = targetSlideId;
const data = await this.syncActiveSlide(targetSlideId);
this.applyState(data);
this.pendingSlideId = "";
this.isNavigating = false;
} catch (error) {
this.pendingSlideId = "";
this.isNavigating = false;
this.lastResult = error.message;
this.setRetryClientAction("Retry slide sync", () => this.goPrevSlide());
this.setClientStatus(error.message, "error");
}
void this.poll();
},
async goNextSlide() {
if (this.isNavigating) return;
const currentIndex = this.activeSlideIndex;
if (currentIndex < 0 || currentIndex >= this.slides.length - 1) return;
const targetSlideId = this.slides[currentIndex + 1] || "";
if (!targetSlideId) return;
this.lastResult = "";
this.clearClientStatus();
try {
this.isNavigating = true;
this.pendingSlideId = targetSlideId;
const data = await this.syncActiveSlide(targetSlideId);
this.applyState(data);
this.pendingSlideId = "";
this.isNavigating = false;
} catch (error) {
this.pendingSlideId = "";
this.isNavigating = false;
this.lastResult = error.message;
this.setRetryClientAction("Retry slide sync", () => this.goNextSlide());
this.setClientStatus(error.message, "error");
}
void this.poll();
},
async goPrevBlock() {
if (!this.hasPrevBlock) return;
const idx = this.blocks.indexOf(this.activeBlockId);
const targetBlockId = this.blocks[idx - 1];
const targetSlideId = this.slides.find((slideId) => this.slideBlocks[slideId] === targetBlockId) || "";
if (!targetSlideId) return;
try {
this.isNavigating = true;
this.pendingSlideId = targetSlideId;
const data = await this.syncActiveSlide(targetSlideId);
this.applyState(data);
this.pendingSlideId = "";
this.isNavigating = false;
} catch (error) {
this.pendingSlideId = "";
this.isNavigating = false;
this.lastResult = error.message;
this.setRetryClientAction("Retry block sync", () => this.goPrevBlock());
this.setClientStatus(error.message, "error");
}
void this.poll();
},
async goNextBlock() {
if (!this.hasNextBlock) return;
const idx = this.blocks.indexOf(this.activeBlockId);
const targetBlockId = this.blocks[idx + 1];
const targetSlideId = this.slides.find((slideId) => this.slideBlocks[slideId] === targetBlockId) || "";
if (!targetSlideId) return;
try {
this.isNavigating = true;
this.pendingSlideId = targetSlideId;
const data = await this.syncActiveSlide(targetSlideId);
this.applyState(data);
this.pendingSlideId = "";
this.isNavigating = false;
} catch (error) {
this.pendingSlideId = "";
this.isNavigating = false;
this.lastResult = error.message;
this.setRetryClientAction("Retry block sync", () => this.goNextBlock());
this.setClientStatus(error.message, "error");
}
void this.poll();
},
});
})();
