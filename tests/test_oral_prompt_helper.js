const assert = require("node:assert/strict");
const helper = require("../app/static/oral_prompt_helper.js");

assert.equal(
  helper.normalizeQuestionPrompt("  What is in the pan?   What did Pat do?  "),
  "What is in the pan? What did Pat do?"
);

assert.deepEqual(
  helper.splitQuestionPrompt("What is in the pan? What did Pat do? Find the word tin."),
  {
    primary: "What is in the pan?",
    secondary: "What did Pat do? Find the word tin.",
  }
);

assert.equal(
  helper.buildOralPromptLine({
    name: "Hyun",
    promptContext: {
      mode: "answer_question",
      customText: "",
      comprehensionPrompt: "What is in the pan? What did Pat do? Find the word tin.",
    },
    performanceType: "read_accuracy",
  }),
  "Hyun, What is in the pan?"
);

assert.equal(
  helper.oralInstructionSupportLine({
    mode: "answer_question",
    comprehensionPrompt: "What is in the pan? What did Pat do? Find the word tin.",
  }),
  "What did Pat do? Find the word tin."
);

assert.equal(
  helper.buildOralPromptLine({
    name: "James",
    promptContext: {
      mode: "read_story",
      customText: "",
      comprehensionPrompt: "",
    },
    performanceType: "correction_reread",
  }),
  "James, please correct it and read again."
);

assert.equal(
  helper.buildGenericLuminosPrompt({
    viewType: "writing_encoding",
    dictatedText: "sat",
  }),
  "Write sat."
);

assert.equal(
  helper.buildGenericLuminosPrompt({
    viewType: "flashcard",
    teacherCue: "What sound?",
    frontText: "s",
  }),
  "What sound?"
);

assert.equal(
  helper.buildGenericLuminosSupportLine({
    promptText: "Write sat.",
    teacherCue: "Play sat once. Replay only if needed before checking.",
  }),
  "Play sat once. Replay only if needed before checking."
);

console.log("oral_prompt_helper tests passed");
