# Myro — command deck (front-end)

A local-first, dark, "command-deck" UI for Myro. Vite + React + TypeScript, plain
CSS with design tokens as CSS custom properties. Runs fully offline against mock
data; every screen and interaction is clickable with no backend.

**The one law:** color carries meaning — **teal = safe / automatic**, **amber =
asks-first**. It's applied everywhere: trace chips, confirm cards, tags, connector
write-actions, and the audit log.

## Run

The built deck ships **pre-built and committed** in `dist/`, so end users need
**no Node install** — `Myro.bat` / `myro.sh` launch the Python backend, which
serves `dist/` at `/`, and the new UI appears. Nothing else to do.

To develop or rebuild the deck:

```bash
npm install
npm run dev        # http://localhost:5173 (hot reload, mock data)
npm run build      # rebuild the committed dist/ — commit it to ship UI changes
```

> Because `dist/` is what actually ships, **rebuild and commit it** whenever you
> change the UI, or users will keep seeing the old build.

No third-party network calls, fonts, or trackers — JetBrains Mono is bundled
locally via `@fontsource`, so it loads and is fully interactive offline.

## Structure

```
src/
  styles/tokens.css     all design tokens (single-sourced CSS variables)
  styles/global.css     one stylesheet, organized by component/view
  lib/types.ts          the domain contract the whole UI reads
  lib/mock.ts           realistic sample state
  lib/api.ts            the ONE data seam — live backend with mock fallback
  lib/live.ts           fetch client to Myro's localhost /api (interfaces/api.py)
  lib/state.tsx         app context: view, scope, toasts, ⌘K, confirm gate
  components/           Shell, ConfirmCard, TraceChip, GraphView, Palette, primitives…
  views/                Chat · Voice · Memory · Routines · Connectors · Settings
  App.tsx               client-side view routing (no reloads)
```

## The real backend (already wired)

Everything reads through **`src/lib/api.ts`**, a *live-with-fallback* seam.
At boot `initApi()` probes the backend's `/api/status`; if it answers, each
method calls **`src/lib/live.ts`** (real `fetch` to the localhost `/api`) and
falls back to `mock.ts` on any error. So the deck shows **real data when the
backend serves it, and stays fully clickable offline**. Endpoints the backend
doesn't expose yet (graph, timeline, audit) stay on mock. The types in
`types.ts` are the contract — components never change.

Same-origin by default: the backend (`interfaces/api.py`) serves this `dist/`
at `/` and the API under `/api/*`, so there's no CORS. Point at a separate dev
origin with `VITE_API_BASE`.

## Views

- **Chat** — plain-language turns; read-only answers resolve on their own, while
  consequential actions raise a **ConfirmCard** that runs nothing without Confirm.
- **Memory** — Facts (scope + forgetting-curve meter + supersede + reinforce /
  forget + local-only lock), an interactive **knowledge Graph** (click a node →
  inspector), and a searchable **Timeline**; fused-search results show which
  retriever matched.
- **Routines** — saved/scheduled tasks that run unattended and **fail closed**;
  gated actions must be pre-authorized when saved.
- **Connectors** — read-only local sources; each write action is a gated `ASKS`.
- **Settings** — scope-aware model routing (sensitive → on-box), backups, phone
  notifications, interfaces + MCP bridge, and an audit log with rollback.
- **Voice** — on-device speech, "Hey Myro" wake word, push-to-talk.

`⌘K` / `Ctrl-K` opens the command palette anywhere.
