(() => {
window.boardShell = (config = {}) => ({
lessonId: config.lessonId || "",
attemptId: config.attemptId || "",
initialSlideId: config.initialSlideId || "",
classId: config.classId || "",
className: config.className || "",
initialState: config.initialState || null,
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
revealed: false,
audioUrl: "",
audioUnlocked: false,
needsAudioGesture: false,
queuePosition: 0,
queueTotal: 0,
paused: false,
stateTimeoutMs: null,
stateStartedAt: "",
timerLabel: "",
pollTimer: null,
commandEmphasized: false,
commandSettleTimer: null,
connectionStatus: "connecting",
consecutiveFailures: 0,
boardAudioElement: null,
boardAudioGestureHandler: null,
currentBoardAudioUrl: "",
lastHandledAudioEventId: -1,
lastAudioError: "",
clientStatusMessage: "",
clientStatusTone: "neutral",
retryClientLabel: "",
retryClientAction: null,
ttsAudioCache: {},
get activeSlideId() {
return this.slides[this.activeSlideIndex] || "";
},
get activeSlideTitle() {
return this.slideTitles[this.activeSlideId] || "";
},
get currentStateLabel() {
return this.currentState.replaceAll("_", " ");
},
get queueSummary() {
if (!this.queueTotal) return "";
return `${Math.min(this.queuePosition, this.queueTotal)} / ${this.queueTotal}`;
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
window.setInterval(() => {
this.refreshTimerLabel();
}, 250);
this.needsAudioGesture = true;
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
this.attachBoardAudioGestureHandlers();
void this.poll().then(() => {
void this.primeBoardPromptAudio();
});
this.pollTimer = window.setInterval(() => {
void this.poll();
}, 250);
},
destroy() {
if (this.pollTimer) {
window.clearInterval(this.pollTimer);
this.pollTimer = null;
}
if (this.commandSettleTimer) {
window.clearTimeout(this.commandSettleTimer);
this.commandSettleTimer = null;
}
this.detachBoardAudioGestureHandlers();
this.stopBoardAudio();
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
attachBoardAudioGestureHandlers() {
if (this.boardAudioGestureHandler) return;
this.boardAudioGestureHandler = () => {
this.audioUnlocked = true;
if (this.needsAudioGesture || this.promptText) {
void this.armBoardAudio();
}
};
window.addEventListener("pointerdown", this.boardAudioGestureHandler, { passive: true });
window.addEventListener("keydown", this.boardAudioGestureHandler);
},
detachBoardAudioGestureHandlers() {
if (!this.boardAudioGestureHandler) return;
window.removeEventListener("pointerdown", this.boardAudioGestureHandler);
window.removeEventListener("keydown", this.boardAudioGestureHandler);
this.boardAudioGestureHandler = null;
},
getBoardAudioElement() {
if (this.boardAudioElement) return this.boardAudioElement;
const audio = new Audio();
audio.preload = "auto";
audio.playsInline = true;
this.boardAudioElement = audio;
return this.boardAudioElement;
},
async fetchTtsPromptAudioUrl(text) {
const normalized = String(text || "").trim();
if (!normalized) return "";
if (this.ttsAudioCache[normalized]) return this.ttsAudioCache[normalized];
const response = await fetch("/lesson/tts/prompt", {
method: "POST",
headers: { "Content-Type": "application/json" },
signal: AbortSignal.timeout(8000),
body: JSON.stringify({ text: normalized }),
});
if (!response.ok) {
throw new Error(`Board TTS request failed (${response.status})`);
}
const data = await response.json();
this.ttsAudioCache[normalized] = data.audio_url || "";
return this.ttsAudioCache[normalized];
},
async primeBoardPromptAudio() {
if (!this.promptText || this.audioUrl) return;
const promptSnapshot = this.promptText;
const eventSnapshot = this.audioEventId;
try {
const audioUrl = await this.fetchTtsPromptAudioUrl(this.promptText);
if (audioUrl && this.promptText === promptSnapshot) {
this.audioUrl = audioUrl;
this.clearClientStatus();
if (!this.paused && eventSnapshot > this.lastHandledAudioEventId) {
void this.playBoardPrompt().then((played) => {
if (played) {
this.lastHandledAudioEventId = eventSnapshot;
}
});
}
}
} catch (_error) {
// Silent prefetch failure is acceptable; explicit replay/play can retry.
}
},
stopBoardAudio() {
const audio = this.getBoardAudioElement();
audio.pause();
try {
audio.currentTime = 0;
} catch (_error) {
// Ignore if the current source does not support seeking yet.
}
},
async unlockAudio() {
this.audioUnlocked = true;
this.needsAudioGesture = false;
},
async armBoardAudio() {
await this.unlockAudio();
if (!this.audioUnlocked) {
this.needsAudioGesture = true;
return;
}
return this.playBoardPrompt();
},
async playBoardPrompt() {
let playbackUrl = this.audioUrl;
if (!playbackUrl && this.promptText) {
try {
playbackUrl = await this.fetchTtsPromptAudioUrl(this.promptText);
} catch (_error) {
this.lastAudioError = "TTS request failed";
this.setRetryClientAction("Retry audio", () => this.playBoardPrompt());
this.setClientStatus("Board TTS request failed", "error");
playbackUrl = "";
}
}
if (!playbackUrl) return false;
this.audioUrl = playbackUrl;
await this.unlockAudio();
this.lastAudioError = "";
const audio = this.getBoardAudioElement();
audio.pause();
if (audio.src !== playbackUrl) {
audio.src = playbackUrl;
}
try {
audio.currentTime = 0;
} catch (_error) {
// Ignore if the media is not seekable yet.
}
this.currentBoardAudioUrl = playbackUrl;
try {
await audio.play();
this.audioUnlocked = true;
this.needsAudioGesture = false;
this.clearClientStatus();
return true;
} catch (error) {
this.lastAudioError = error?.message || "Playback blocked";
this.needsAudioGesture = true;
this.setRetryClientAction("Retry audio", () => this.playBoardPrompt());
this.setClientStatus(this.lastAudioError, "warning");
return false;
}
},
scheduleCommandSettle() {
if (this.commandSettleTimer) {
window.clearTimeout(this.commandSettleTimer);
}
this.commandSettleTimer = window.setTimeout(() => {
this.commandEmphasized = false;
this.commandSettleTimer = null;
}, 2600);
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
applyState(data) {
const previousPrompt = this.promptText;
const previousUiEventId = this.uiEventId;
const previousPaused = this.paused;
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
this.promptText = data.prompt_text || "";
this.boardPromptText = data.prompt_text || "";
this.teacherPromptText = data.teacher_prompt_text || data.prompt_text || "";
this.audioUrl = data.audio_url || "";
this.queuePosition = data.queue_position || 0;
this.queueTotal = data.queue_total || 0;
this.paused = !!data.paused;
this.stateTimeoutMs = data.state_timeout_ms || null;
this.stateStartedAt = data.state_started_at || "";
if (!this.promptText) {
this.stopBoardAudio();
this.currentBoardAudioUrl = "";
this.commandEmphasized = false;
this.revealed = false;
if (this.commandSettleTimer) {
window.clearTimeout(this.commandSettleTimer);
this.commandSettleTimer = null;
}
return;
}
if (this.paused && !previousPaused) {
this.stopBoardAudio();
}
if (this.promptText !== previousPrompt || this.uiEventId !== previousUiEventId) {
this.commandEmphasized = true;
this.revealed = false;
this.scheduleCommandSettle();
void this.primeBoardPromptAudio();
}
if (!this.paused && this.audioUrl && this.audioEventId > this.lastHandledAudioEventId) {
const eventId = this.audioEventId;
void this.playBoardPrompt().then((played) => {
if (played) {
this.lastHandledAudioEventId = eventId;
}
});
}
this.refreshTimerLabel();
},
async poll() {
try {
const response = await fetch(`/lesson/${this.lessonId}/command-state/${this.attemptId}`);
if (!response.ok) {
throw new Error(`Board state request failed (${response.status})`);
}
const data = await response.json();
this.applyState(data);
this.connectionStatus = "ok";
this.consecutiveFailures = 0;
if (this.clientStatusTone === "error" && !this.lastAudioError) {
this.clearClientStatus();
}
} catch (error) {
this.consecutiveFailures += 1;
this.connectionStatus = this.consecutiveFailures >= 3 ? "degraded" : "connecting";
this.setRetryClientAction("Retry connection", () => this.poll());
this.setClientStatus(error.message, "error");
}
},
});
})();
