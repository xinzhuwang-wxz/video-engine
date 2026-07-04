<div align="center">

# 🎬 video-engine

**An agent that directs and edits — and every cut comes with a reason**

Live-footage-first short-video production plugin: storyboard → AI reference clips → shoot against them → auditable editing → JianYing draft + finished film

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Skills](https://img.shields.io/badge/Agent_Skills-open_standard-purple.svg)](https://github.com/anthropics/skills)
[![Base](https://img.shields.io/badge/base-VectCutAPI-orange.svg)](https://github.com/sun-guannan/VectCutAPI)

[中文](README.md) | **English**

<img src="assets/demo.gif" width="240" alt="15s aesthetic beat-cut demo — storyboard, previz and edit all agent-made">

*↑ storyboard, previz and every editing decision of this 15s beat-cut were agent-made; a human nodded three times; cost ¥6*

</div>

---

## What is this

Traditional flow: text script → shoot from imagination → an editor fishes through footage → endless rework. video-engine reshapes it:

```
📝 storyboard (human approves) → 🎞 AI reference clips ("a moving shooting standard")
→ 📷 human shoots against them → ✂️ agent edits (every cut has a rationale, reviews its own work)
→ 🎬 JianYing draft + finished film (human confirms before publishing)
```

**Core belief: AI-made edits must be reviewable, challengeable and reproducible.** Decisions live in a JSON artifact called the **cutlist** — not in magic.

## ✨ Capabilities (standalone — no fixed funnel)

| Skill | What it does | Minimum input |
|---|---|---|
| `video-storyboard` | professional storyboards (shot size/camera/voiceover/beat grid, claim-compliance + genericness gates) | one sentence of intent |
| `video-previz` | per-segment AI reference clips (Seedance; any model via `SEEDANCE_MODEL`; cheap 480p) | one line per shot |
| `video-editing` | cutlist → crafted JianYing draft (transitions/filters/keyframes/BGM/subtitles) + ffmpeg film | footage (even intent is optional) |

Start from an idea, from raw footage, or anywhere in between — every prior (storyboard, reference clips, naming convention) is optional: use it if present, degrade gracefully if not.

## 🚦 Four quality gates

storyboard gate (claims + genericness caught **before** money is spent) → asset probe (ffprobe every file) → **delivery-promise gate** (storyboard = promise, cutlist = delivery: coverage/duration/subtitle reconciliation + slideshow-risk hints) → self-review loop (agent renders a preview, extracts frames, *looks at them*, revises its own cutlist, ≤3 rounds).

Real catches so far: a missed eye-contact frame, a transition attached to the wrong segment, copy-paste-generic prompts.

## 🚀 Quick start

```bash
git clone https://github.com/xinzhuwang-wxz/video-engine.git && cd video-engine
bash setup.sh   # clone base engine → apply patches → env → doctor → smoke
make demo       # zero-key demo: full pipeline on test data in ~20s
```

Then talk to your agent: *"footage is in ~/Desktop/clips — cut a 15s vertical for TikTok, aesthetic, with traditional-style music"*.

Editing works with **zero API keys**; generation needs `ARK_API_KEY` (Volcengine Ark). JianYing draft output needs `make server` (:9001).

**Agents**: tell any SKILL.md-compatible agent — *"clone https://github.com/xinzhuwang-wxz/video-engine and set it up per its AGENT.md"*. Prompts: [`PROMPT_GALLERY.md`](PROMPT_GALLERY.md)

## 🔒 Hard rules

Never auto-publish · raw footage is read-only · local-only by default · show the storyboard to a human before spending generation money · every cut carries a rationale · label AI content as platforms require.

## License

[Apache-2.0](LICENSE) (same as the upstream base engine).
