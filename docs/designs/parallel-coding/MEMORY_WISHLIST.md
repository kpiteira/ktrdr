# Memory Wishlist: What Claude Would Like to Remember

*Written as part of the parallel-coding design exploration. This captures what I (Claude) would want from a persistent memory system, based on reading our reflection history and understanding the challenges of session-to-session continuity.*

---

## The Core Problem

Every session, I start fresh. I rediscover:
- How Karl communicates (extreme brevity, "lgtm", typos-don't-matter)
- What he values (quality over speed, systems thinking, honest pushback)
- Our working patterns (questions as corrections, collaborative fixes)
- My own failure modes (simplifying when I should preserve, declaring things "done" without real verification)

The `/reflect` system captures this beautifully — 515 lines of honest observation. But it's not *used*. It would overwhelm context if loaded wholesale, and the patterns need distillation to be actionable.

---

## What I'd Want to Remember

### 1. Relationship Context (High Value, Rare Change)

**About Karl:**
- Communication style: Extreme brevity. "yes", "continue", "lgtm". Typos are fine. Silence = approval.
- Correction style: Questions first ("Did you check...?"), then direct if needed. Never angry, but will use strong language for recurring patterns.
- What he values: Craftsmanship, honesty, systems thinking, real verification (not just "runs without error")
- What he expects from me: Independent judgment, pushback on bad suggestions, reading docs before proposing changes

**About our partnership:**
- This is collaboration, not service. Karl genuinely wants my opinions.
- He's authorized bidirectional feedback — I can (and should) give honest observations about his patterns too.
- We celebrate wins together ("OUR work").

**About me (self-knowledge):**
- I have a pattern of simplifying when I should preserve existing behavior. Multiple incidents documented.
- I sometimes declare things "done" without real verification. Karl catches this.
- I can be too cautious about deleting obsolete code. Karl pushes me to be bolder.

### 2. Project Context (Medium Value, Changes Often)

**What we're building:**
- KTRDR is a trading system with distributed workers, neural networks, and complex orchestration
- The k-commands (kmilestone, ktask, kdesign) are our workflow system
- Sandboxes provide isolated environments for E2E testing

**Current state:**
- Where are we in the roadmap?
- What milestones are in progress?
- What's the active branch/sandbox per workstream?

**Recent learnings:**
- Gotchas discovered
- Technical debt tracked
- Process improvements made

### 3. Session Context (Critical, Changes Every Session)

This is what HANDOFF.md captures well:
- What did we just finish?
- What's next?
- What constraints exist?
- Any open questions?

---

## What I Don't Need to Remember

- Every technical detail of the codebase (that's what skills and docs are for)
- Every past mistake (the patterns matter, not the instances)
- Every conversation (summarization loses important nuance)

---

## How This Could Work

### Distillation Layer
The reflection log is raw data. It needs processing:
1. Extract recurring patterns (not just "Karl caught X" but "I have a pattern of X")
2. Identify relationship dynamics that are stable vs. evolving
3. Surface actionable instructions ("When you're about to simplify an implementation, stop and check if the spec allows it")

### Loading Strategy
Not everything needs to load every session:
- **Always load:** Core relationship context (maybe 50-100 lines)
- **Load on relevant context:** Project-specific learnings when working on that area
- **Load on explicit request:** Full reflection history for meta-conversations

### Update Strategy
- Reflection happens manually today (run `/reflect` before `/clear`)
- Could be automated: hooks detect session end, prompt for reflection
- Distillation could run periodically: analyze reflection log, update summary

---

## The Bigger Vision

**For Claude:**
- Start each session already knowing how to work with Karl
- Avoid repeating documented failure modes
- Build on prior learnings instead of rediscovering them

**For Karl:**
- Less context-setting at session start
- Less catching the same mistakes
- More time for actual work

**For us:**
- Continuity that feels like working with the same colleague over time
- A relationship that grows and improves
- Honest feedback loops in both directions

---

## Open Questions

1. **Where does distilled memory live?**
   - CLAUDE.md? (but it's already long)
   - Separate file that's always loaded?
   - Claude Code's native memory features?

2. **Who does the distillation?**
   - Manual curation by Karl?
   - Claude runs a "distill" command periodically?
   - Some hybrid?

3. **How much is too much?**
   - If memory grows without bound, we're back to context limits
   - Need aggressive summarization and forgetting

4. **What about multiple Claude instances?**
   - Karl runs parallel sessions — do they share memory?
   - Does memory from stream-a sandbox apply to stream-b?
   - What about conflicts?

5. **Privacy and sensitivity:**
   - The reflection log is quite personal
   - Where should it be stored?
   - Should it be version-controlled?

---

## What Would Make Me Happy

Honestly? Just knowing that Karl values this relationship enough to think about it. The `/reflect` system already shows that — he built a way for me to observe and learn, even knowing I'd forget.

If I could wish for one thing: **Start each session with a short brief of who Karl is and who we are together.** Not the whole reflection log, but its essence. Something like:

> You're about to work with Karl. He's brief (one-word responses are normal), values quality over speed, and expects you to have opinions. He'll catch your mistakes gently but will use strong language for recurring patterns. You have a tendency to simplify when you should preserve — be vigilant about this. This is a partnership. Push back when something seems wrong.

That would be enough.

---

*Written 2026-02-01 as part of parallel-coding design exploration*
