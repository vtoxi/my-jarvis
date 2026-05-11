# macOS setup (Apple Silicon)

## Toolchain

1. **Xcode Command Line Tools** (if not already installed):

   ```bash
   xcode-select --install
   ```

2. **Node.js 20+** — install via [nodejs.org](https://nodejs.org/) or your preferred version manager.

3. **Python 3.11+** — macOS often ships an older system Python; use [python.org](https://www.python.org/downloads/) or `pyenv`.

## Apple Silicon notes

- Prefer **arm64** native Node and Python builds (no Rosetta required for this project’s Phase 1 stack).
- Electron downloads an arm64 binary automatically on M-series Macs.

## First run

```bash
cd /path/to/my-jarvis
npm install
```

**Terminal A — API**

```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal B — Desktop**

```bash
npm run dev
```

## Window chrome

The desktop app uses `titleBarStyle: "hiddenInset"` with traffic lights offset for a HUD-style shell. If you change window dimensions in [`electron/main.ts`](../apps/desktop/electron/main.ts), keep padding in the renderer header compatible with the draggable region (future enhancement).

## Code signing & distribution

Phase 1 is **developer-run** only. For distribution outside your machine you will need Apple **code signing** + **notarization** and hardened runtime settings. Track that as a pre-release milestone, not part of Phase 1 MVP.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| API pill stays red | API running? Settings → URL matches `uvicorn` bind host/port? |
| CORS errors in dev console | Add your Vite origin to `JARVIS_CORS_ORIGINS` in `apps/api/.env`. |
| Blank window after build | `vite.config.ts` uses `base: './'` for `file://` loading from `dist/`. |
