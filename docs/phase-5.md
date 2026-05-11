# Phase 5 — Screen intelligence + context awareness

## 1. Screen intelligence architecture

- **Capture**: `mss` grabs the primary monitor; frames are downscaled (`JARVIS_SCREEN_MAX_CAPTURE_WIDTH`) before OCR to limit CPU and memory.
- **Foreground context**: macOS `osascript` (System Events) reads front app + window title (no screen pixels).
- **OCR**: OpenCV preprocess (grayscale, upscale, Otsu) + **Tesseract** via `pytesseract` (requires [Tesseract](https://tesseract-ocr.github.io/) installed on the Mac, e.g. `brew install tesseract`).
- **Tagging**: Heuristic `infer_context_tags()` maps app/title/OCR text to modes (Slack, IDE, browser, Jira, meetings, etc.).
- **Crew**: **Context Analyst** then **Productivity Copilot** (`app/services/screen_crew_runner.py`) consume a single evidence block; **`JARVIS_LLM_STUB`** returns deterministic placeholders without Ollama.
- **History**: `context_history.sqlite3` under `JARVIS_DATA_DIR` stores snapshots (Fernet-encrypted by default, or plain JSON when encryption is off).
- **API**: `routes_phase5.py` — `/screen/*`, `/copilot/*`, `/focus/*`.
- **Desktop**: `/copilot` — pause, private mode, exclusions, capture, suggestions, focus timer.

## 2. OCR engine

- Implemented in `app/services/ocr_service.py`.
- Failure modes surface as `ocr_error` strings (`tesseract_not_installed`, `opencv_not_installed`, etc.) without crashing the API.

## 3. Context Agent

- Role strings in `app/agents/context_agent.py`; executed by `screen_crew_runner` as the first CrewAI task.

## 4. Productivity Copilot agent

- `app/agents/productivity_copilot_agent.py`; second task, context-linked to the analyst output.

## 5. Dashboard upgrades

- **Copilot** nav entry → live context, OCR excerpt, assist modes, exclusions editor, productivity heuristic, suggestion queue, focus timer.

## 6. Privacy model

- **Pause monitoring**: skips capture; `/screen/capture` returns `reason: monitoring_paused`.
- **Private mode**: stub 1×1 image path — no real pixels processed.
- **App exclusions**: substring match on front app name (default-sensitive apps included).
- **No image in API responses by default** (`include_image: false`); optional `true` for local debugging only.
- **No cloud upload** in this path; all processing is local.

## 7. Performance optimization

- Downscale before OCR; single-monitor primary capture; passive polling is **client-driven** (interval hint in `/copilot/status`); server runs work only on explicit capture/refresh/suggestions.

## 8. Testing plan

- `tests/test_phase5.py` — `/copilot/status`, `/screen/context`, `/focus/*`, paused capture behavior.
- Manual: grant **Screen Recording** for the terminal/Python host running uvicorn; verify OCR text appears.

## 9. Risk mitigation

- **Permissions**: macOS will block capture until Screen Recording is granted — surface errors in API JSON and UI.
- **Sensitive UIs**: exclusions + private mode + pause; operator defaults exclude password managers.
- **Hallucination**: crew prompts require evidence-only reasoning; stub mode for CI.

## 10. Definition of done

- [x] `/screen/capture`, `/screen/context`, `/screen/ocr`
- [x] `/copilot/status`, `/copilot/config`, `/copilot/suggestions`
- [x] `/focus/state`, `/focus/control`
- [x] Context + copilot agents, crew runner, encrypted context history
- [x] Electron Copilot deck + API client
- [x] `apps/api/.env.example` Phase 5 keys
- [ ] Native Apple Vision pipeline (optional future optimization)
