# Speaker Notes: Trusting AI-Generated Code

## 1. Quick Context (5 min)

### Opening

Welcome. The purpose of this presentation is to share the set up of a personal project I've been working on for a while as a support to learn about agents and agentic coding. That setup uses Claude Code because back when I started I used GitHub Copilot, Cline with Gemini and Claude Code. At the time, Copilot would loose itself very quickly with no way for me to understand when it would start spiraling down and I was not making any progress - it allowed no option to manage the context. Cline was better with its orchestrator agent allowing finer management of context, but Claude Code - even when it released, was a much simpler and allowed much better context management. I was making progress faster plus they kept releasing innovations (custom slash commands, sub-agents, skills, hooks, ...) so I just stuck with it. But today GitHub Copilot has mostly caught up and would absolutely be a viable option for everything I am showing (I mostly miss the context %!).

### The Project

**[Show architecture doc]**

### The topic for today

I wanted to share how I built the conditions in my project so that I can trust **enough** code I didn't write.

**Transition:** "Let me show you what I mean by actually doing some work..."

---

## 2. Let's Get to Work (3 min)

### Setup

> "So during this presentation, I'll alternate from giving work to the agent and talking through the system:"

**[Point to Zellij panes]**

> "This one is working on a CLI restructure - real feature work, multiple milestones. This one will work on a smaller infrastructure feature - adding a shell command to our sandbox system."
> "I'm going to kick off both tasks right now, and let them work while I present."

**[Run ktask on stream-a, then stream-b]**

**With Copilot:** You'd set up the same thing - kick off agent mode, let it work, potentially in the background. The mechanisms I'm showing work with any agentic tool.

**Transition:** "So what makes this possible? Let's start with the foundation..."

---

## 3. Foundations: How We Work Together (5 min)

### The Collaboration Contract

> "Most people think about giving AI instructions on *what* to build. Fewer think about *how* to collaborate. This is establishing the fundamental element of trust, and the psychological safety"

**[Open CLAUDE.md in VS Code]**

> "This is CLAUDE.md - it's like a collaboration contract. Not just 'here's my codebase' but 'here's how we work together.'"

### Key Sections to Highlight

**Working Agreement:**
> "Look at this: 'On uncertainty - say I'm not sure rather than fabricating confidence.' 'On disagreement - push back if something feels wrong.'"

> "I'm explicitly telling the AI: I want you to disagree with me. I want you to say when you don't know. That's not default behavior - you have to ask for it."

**Anti-patterns:**
> "This section is about what NOT to do. The 'quick fix' trap. Recognizing 'bad loops' - when you're patching symptoms instead of fixing root causes."

> "After 2-3 incremental fixes that don't work, stop. Ask if we should step back. That's in the instructions."

**Shared Values:**
> "'Craftsmanship over completion.' 'Technical debt is real debt.'"

> "This isn't just nice words - it shapes every interaction. The AI will push back if I try to rush something."

### Why This Matters

> "This is the first layer of trust: the AI knows how I want to work. It's not just generating code - it's generating code *the way I would want to*. after adopting this model which was inspired from Jenny's work, I saw a massive increase in honesty, much less 'it's production ready' when it's not, and the agent highlights what it's struggling with."

**With Copilot:** This is `copilot-instructions.md` - same concept, same file location. You can define how you want the AI to work with you.

**Transition:** "But good collaboration isn't enough. You also need clarity about what you're building..."

---

## 4. Specification: Clarity Before Code (8 min)

### The Problem with "Just Build It"

> "If I said 'add a training command to the CLI' - what would you build? What flags? What output format? What error handling?"

> "Ambiguity is where AI hallucinates. The less clear you are, the more it fills in gaps with assumptions. Properly specifying and spending time in a conversational format allows me to clarify my own thinking and making sure that the key scenarios and decisions are covered. This allows me to have more trust in what will be built."

### The Spec Structure

**Show the spec-work pane with the ongoing spec on the Orchestrator / autonomous coding agent**

> "This is our spec structure. Feature design, then architecture, then milestones, then tasks."

**Walk through each file briefly:**

- **DESIGN.md:** "The what and why. What problem are we solving? What's in scope, what's out?"
- **ARCHITECTURE.md:** "Technical decisions. What patterns? What tradeoffs?"
- **OVERVIEW.md:** "Milestones - how we break this into shippable chunks."
- **M*.md:** "Individual tasks with acceptance criteria."

### Why Structure Matters

> "Each level adds context. By the time we get to implementation, the AI knows: the goal, the constraints, the patterns to follow, and exactly what 'done' looks like."

> "Specs aren't documentation for humans - they're context for the AI. Specs are critical to clarify the intent, properly manage contexct and prevent hallucination."

**With Copilot:** Same approach, use SpecKit - structured specs work with any agent. The files become context for the AI regardless of which tool you use.

### Check-in

**[Glance at the running tasks]**

> "Let's see how our tasks are doing... [comment on progress]"

**Transition:** "So we have collaboration norms and clear specs. But how do you run multiple things at once without chaos?"

---

## 5. Execution: Parallel Streams (8 min)

### The Setup

**[Show Zellij with multiple panes]**

> "This is Zellij - like tmux but friendlier. I have multiple tabs: Coding, Autonomous Agent, Spec Work."

> "Each pane is a separate Claude instance with its own context."

### How Isolation Works

> "Each stream has its own sandbox - its own Docker environment, its own database, its own everything."

**[Maybe show ktrdr sandbox status briefly]**

> "This one is on port 8001, this one on 8002. They can't interfere with each other."

> "Different branches too. Stream-a is on the CLI restructure branch. Stream-b is on sandbox-shell. They merge separately."

### Interactive vs Autonomous

> "I use interactive mode when I'm actively working - I see what it's doing, I can course-correct."

> "Autonomous mode is fire-and-forget. Give it a task, let it run, check results later."

### What They've Been Doing

**[Switch between panes, show progress]**

> "Let's see what happened while we were talking... [narrate what you see]"

**With Copilot:** Copilot agent mode supports this too - multiple workspaces, different contexts. The isolation pattern is tool-agnostic.

**Transition:** "Speaking of verification - that's the next layer..."

---

## 6. Verification: Trust But Verify (10 min)

### The Sandbox Environment

> "Remember how I said each stream has its own environment? Let me show you what that means."

**[Show ktrdr sandbox status or the architecture diagram]**

> "Each sandbox is a complete copy: backend, database, observability, workers - all on different ports."

> "Why? So the AI can run destructive tests. It can break things, corrupt data, whatever - in *its* sandbox. My main environment is untouched."

### Automatic Quality Gates

> "Every piece of code goes through gates."

**[Maybe run make quality or show output]**

- "Linting - catches style issues"
- "Type checking - catches type errors"
- "Unit tests - catches logic errors"
- "Pre-commit hooks - catches issues before they're committed"

> "The AI doesn't get to skip these. If tests fail, it has to fix them before moving on."

### Skills and Prompts

**[Open .claude/commands/ktask.md or similar]**

> "These are 'skills' - structured prompts for specific tasks."

> "This one is ktask - it enforces TDD. Write tests first, then implementation, then verify."

> "I'm not hoping the AI writes tests. I'm telling it: you don't get to skip this step."

### Defense in Depth

> "Each layer catches different things:"

- "Collaboration contract catches approach problems"
- "Specs catch requirement problems"
- "Quality gates catch implementation problems"
- "E2E tests catch integration problems"

> "No single layer is enough. It's the combination that builds trust."

**With Copilot:** Same gates apply. `make quality`, pre-commit hooks - these work regardless of which AI wrote the code.

**Transition:** "But what happens when you come back tomorrow? How do you not lose context?"

---

## 7. Continuity: Handoffs & Learning (5 min)

### The Session Problem

> "AI doesn't remember. Every new session starts fresh."

> "If I worked on something yesterday, how does today's session know what happened?"

### Handoff Documents

**[Open a HANDOFF doc]**

> "At the end of each milestone, we create a handoff doc."

> "What was done. What decisions were made. What problems we hit. What's next."

> "This becomes context for the next session. The AI reads this and knows: 'ah, we tried X and it didn't work because Y.'"

### Example of Caught Failure

**[If you have a good example, show it]**

> "Here's a real example: [describe a specific case where tests caught something, or where handoff prevented repeating a mistake]"

> "Without this system, we would have [shipped the bug / repeated the mistake / wasted time rediscovering the same issue]."

### The Compound Effect

> "Each layer adds a little confidence. Together they compound."

> "I'm not saying this is bulletproof. But it's enough that I can let AI work unsupervised during a presentation."

**Transition:** "Speaking of which - let's see how we did..."

---

## 8. Wrap-up (4 min)

### Final Check-in

**[Switch to the task panes, review progress]**

> "Let's see what happened... [comment on what was accomplished]"

> "[If tasks completed] Look at this - tests passing, code committed, ready for review."
> "[If tasks are still running] Still in progress - but look how far it got."
> "[If something failed] Actually, this is interesting - let's see what happened and how the system handled it."

### The Layers Recap

> "So what did we cover? Five layers of trust:"

1. **Collaboration contract** - CLAUDE.md shapes *how* we work
2. **Structured specs** - clarity prevents hallucination
3. **Parallel isolation** - sandboxes prevent chaos
4. **Quality gates** - automated verification
5. **Handoffs** - learning persists across sessions

### Closing

> "Questions?"
