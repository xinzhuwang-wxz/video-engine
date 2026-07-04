# video-engine · Agent-driven short-video production plugin

**[中文](README.md)** | English

<p align="center"><img src="assets/demo.gif" width="240" alt="15s aesthetic beat-cut demo — storyboard, previz and edit all agent-made"></p>

> One idea (or a folder of raw footage) in → a fully-crafted JianYing/CapCut draft + rendered film out.
> Humans only do three things: approve the storyboard, shoot, and confirm before publishing.

## Architecture: mature base + a decision layer on top

| Layer | What | Where it comes from |
|---|---|---|
| Decision | 3 **standalone capabilities** (storyboard / previz / editing — no fixed funnel: start from an idea, from raw footage, or anywhere in between; every prior is optional) + **cutlist contract** — every cut carries a written rationale | this repo |
| Execution | [VectCutAPI](https://github.com/sun-guannan/VectCutAPI) (2k★): 362 transitions / 468 filters / keyframes / audio tracks, HTTP :9001 | cloned by `setup.sh` + `patches/` |
| Generation | Seedance via Volcengine Ark (any model — swap with `SEEDANCE_MODEL`) | `scripts/seedance_gen.py` |
| Front-end | JianYing (local, human review/export) or VectCut cloud preview (opt-in, your own OSS) | base engine |

Key pieces the base doesn't have, which this repo adds:

- **Cutlist contract** (`cutlist.schema.json`) — the editing decision language: per-segment source/in/out/transition/rationale, plus global grade & BGM. Engine-agnostic.
- **Self-review loop** — the agent renders a low-res preview, extracts frames, *looks at them* (multimodal), and revises its own cutlist (≤3 rounds).
- **Beat alignment** — detects real energy onsets in the BGM and snaps cut points to them (theoretical BPM grids lie).
- **Style whitelist** — machine-dumped enum list (`style-presets/enums.json`) so agents can never hallucinate a filter name, plus judgment rules (not hardcoded answers).
- **Workspace discipline** — `assets/{SKU}/01-raw|02-AI|03-final|04-workbench/{NOTE}/` with an append-only manifest; presence *is* state, no timestamps needed.

## Install (any SKILL.md-compatible agent)

```bash
git clone https://github.com/xinzhuwang-wxz/video-engine.git && cd video-engine && bash setup.sh
```

- **Claude Code**: `ln -s $PWD/skills/* ~/.claude/skills/` (or just open the repo)
- **Codex**: works in-repo via `AGENT.md`, or drop skills into `~/.codex/skills`
- **Hermes / OpenClaw / others**: symlink `skills/` into their skill directory

Config: put `ARK_API_KEY` in `.env` (only needed for generation; editing works without it).
Start the engine: `cd vendor/CapCutAPI && .venv/bin/python capcut_server.py` (:9001).

## Hard rules

Never auto-publish · raw footage is read-only · local-only by default (cloud preview is explicit opt-in) ·
show the storyboard to a human before spending generation money · every editing decision carries a rationale ·
label AI-generated content as required by the target platform.

## License

Apache-2.0 (same as the upstream base engine).
