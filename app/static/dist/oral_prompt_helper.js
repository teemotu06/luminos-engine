(function (root, factory) {
if (typeof module === "object" && module.exports) {
module.exports = factory();
return;
}
root.OralPromptHelper = factory();
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
function normalizeQuestionPrompt(prompt) {
const text = String(prompt || "").trim();
if (!text) return "";
return text.replace(/\s+/g, " ");
}
function splitQuestionPrompt(prompt) {
const normalized = normalizeQuestionPrompt(prompt);
if (!normalized) {
return { primary: "", secondary: "" };
}
const sentences = normalized
.split(/(?<=[?.!])\s+/)
.map((part) => part.trim())
.filter(Boolean);
if (sentences.length <= 1) {
return { primary: normalized, secondary: "" };
}
return {
primary: sentences[0],
secondary: sentences.slice(1).join(" "),
};
}
function extractComprehensionSegments(prompt) {
const normalized = normalizeQuestionPrompt(prompt);
if (!normalized) return [];
return normalized
.split(/(?<=[?.!])\s+/)
.map((part) => part.trim())
.filter(Boolean);
}
function normalizeInstructionText(text) {
return String(text || "").replace(/\s+/g, " ").trim();
}
function buildGenericLuminosPrompt(context = {}) {
const customText = normalizeInstructionText(context.customText);
if (customText) return customText;
const promptText = normalizeInstructionText(context.promptText);
const teacherCue = normalizeInstructionText(context.teacherCue);
const viewType = normalizeInstructionText(context.viewType);
const title = normalizeInstructionText(context.title);
const frontText = normalizeInstructionText(context.frontText);
const targetWord = normalizeInstructionText(context.targetWord);
const targetSentence = normalizeInstructionText(context.targetSentence);
const dictatedText = normalizeInstructionText(context.dictatedText);
const quickCheckTitle = normalizeInstructionText(context.quickCheckTitle);
if (viewType === "audio_prompt") {
return promptText || teacherCue || "Listen carefully.";
}
if (viewType === "writing_encoding") {
return promptText || `Write ${dictatedText || "what you hear"}.`;
}
if (viewType === "drag_letter") {
return promptText || `Build ${targetWord || "the word"}.`;
}
if (viewType === "drag_word") {
return targetSentence ? `Build the sentence: ${targetSentence}` : "Build the sentence.";
}
if (viewType === "minimal_pair") {
return teacherCue || "Listen carefully and choose the correct sound.";
}
if (viewType === "quick_check") {
return quickCheckTitle || teacherCue || "Let's check the lesson.";
}
if (viewType === "flashcard") {
return teacherCue || (frontText ? `What sound is ${frontText}?` : title || "Say the sound.");
}
if (viewType === "read_respond") {
return promptText || teacherCue || title || "Read and respond.";
}
return promptText || teacherCue || title || "";
}
function buildGenericLuminosSupportLine(context = {}) {
const customSupportText = normalizeInstructionText(context.customSupportText);
if (customSupportText) return customSupportText;
const teacherCue = normalizeInstructionText(context.teacherCue);
const promptText = normalizeInstructionText(context.promptText);
if (teacherCue && teacherCue !== promptText) {
return teacherCue;
}
return "Follow the instruction, then move to the next task.";
}
function buildOralPromptLine({ name, promptContext, performanceType }) {
if (!name) return "";
const customText = promptContext?.customText;
if (customText) {
return customText.includes("{name}") ? customText.replaceAll("{name}", name) : `${name}, ${customText}`;
}
const questionPrompt = splitQuestionPrompt(promptContext?.comprehensionPrompt);
if (questionPrompt.primary && promptContext?.mode !== "read_story") {
if (performanceType === "correction_reread") {
return `${name}, try again. ${questionPrompt.primary}`;
}
return `${name}, ${questionPrompt.primary}`;
}
const promptLineMap = {
read_story: {
default: `${name}, please read the story.`,
reread_fluency: `${name}, please reread the story smoothly.`,
correction_reread: `${name}, please correct it and read again.`,
},
answer_question: {
default: `${name}, please answer the question.`,
reread_fluency: `${name}, please answer the question clearly.`,
correction_reread: `${name}, please think again and answer the question.`,
},
answer_with_story: {
default: `${name}, please answer using the story.`,
reread_fluency: `${name}, please answer using the story.`,
correction_reread: `${name}, please use the story and answer again.`,
},
retell: {
default: `${name}, please tell us what happened.`,
reread_fluency: `${name}, please tell us what happened clearly.`,
correction_reread: `${name}, please try again and tell us what happened.`,
},
show_and_explain: {
default: `${name}, please point and explain your answer.`,
reread_fluency: `${name}, please point and explain your answer.`,
correction_reread: `${name}, please try again and point to your answer.`,
},
};
const lineSet = promptLineMap[promptContext?.mode] || promptLineMap.read_story;
if (performanceType === "reread_fluency") {
return lineSet.reread_fluency || lineSet.default;
}
if (performanceType === "correction_reread") {
return lineSet.correction_reread || lineSet.default;
}
return lineSet.default;
}
function oralInstructionSupportLine(promptContext) {
if (promptContext.comprehensionPrompt && promptContext.mode !== "read_story") {
const questionPrompt = splitQuestionPrompt(promptContext.comprehensionPrompt);
if (questionPrompt.secondary) {
return questionPrompt.secondary;
}
const supportLineMap = {
answer_question: "Answer in a full sentence.",
answer_with_story: "Use the story in your answer.",
retell: "Tell what happened in order.",
show_and_explain: "Point first, then explain your answer.",
};
return supportLineMap[promptContext.mode] || "Answer clearly and use the story when needed.";
}
return "Listen, then mark the response below.";
}
return {
normalizeQuestionPrompt,
splitQuestionPrompt,
extractComprehensionSegments,
normalizeInstructionText,
buildGenericLuminosPrompt,
buildGenericLuminosSupportLine,
buildOralPromptLine,
oralInstructionSupportLine,
};
});
