---
name: browser-tdd
description: Execute a DOM-based Test-Driven Generation loop. Automatically generates web code, tests it in the browser up to 3 times, and fixes bugs autonomously.
tags: [tdd, dom, browser, automation, harness, qa]
---

# Browser-TDD (DOM-based Test-Driven Generation)

**Description:**
This skill enables the Antigravity-K agent to autonomously create a web program, open it in a headless browser, interact with the DOM elements, verify functionality, and iteratively fix the code up to 3 times until the program works perfectly.

**When to use:**
- When the user asks to "build and test a web UI" or "use DOM to test the program".
- When you are tasked with creating a robust, bug-free HTML/JS interactive component.
- Mentioned by: `/browser-tdd`, `browser tdd`, or "test 3 times using dom".

## Workflow

When this skill is invoked, follow these exact steps sequentially:

### 1. Code Generation
- Create the initial version of the requested HTML/CSS/JS file.
- Ensure elements have clear IDs or Classes to make them easily targetable by the browser DOM tools.

### 2. Autonomous Testing Loop (Max 3 Iterations)
You must perform an iterative Test-Fix loop. Do NOT stop after the first try unless 100% of tests pass.

#### Iteration 1
1. **Test**: Call `browser_subagent` (or `browse` / `self_test_tool`) and provide a highly detailed task to open the file and interact with the elements (e.g., click buttons, type inputs, verify text changes or class toggles).
2. **Evaluate**: Analyze the subagent's report.
3. **Fix**: If the report indicates any bugs (e.g., element not found, state not updated), use `multi_replace_file_content` to fix the source code.

#### Iteration 2
1. **Test**: Run the `browser_subagent` again to verify the fixes and test any additional edge cases (like clearing inputs or Enter key support).
2. **Evaluate**: Analyze the report.
3. **Fix**: Apply further fixes to the code if needed.

#### Iteration 3
1. **Final Validation**: Run the `browser_subagent` one last time for a final pass.
2. **Conclude**: If it passes, the loop is complete. If it still fails, stop the loop and report the remaining issues to the user.

### 3. Reporting
- Show the final results to the user.
- Emphasize the bugs that were caught and autonomously fixed during the testing loop.

## Core Rules
- **No manual intervention**: The agent MUST write the test instructions for the subagent, wait for the result, and apply the fixes by itself.
- **Clear Inputs**: When testing input fields, always ensure the subagent's instructions check whether the input field is properly cleared or reset after submission.
- **Use Subagent properly**: Make sure the subagent's `Task` prompt includes clear success/failure conditions so its final report is actionable.
