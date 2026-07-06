# Myro — command deck (front-end)

A local-first, dark, "command-deck" UI for Myro. Vite + React + TypeScript, plain
CSS with design tokens as CSS custom properties. Runs fully offline against mock
data; every screen and interaction is clickable with no backend.

**The one law:** color carries meaning — **teal = safe / automatic**, **amber =
asks-first**. It's applied everywhere: trace chips, confirm cards, tags, connector
write-actions, and the audit log.

## Run

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # static build in dist/ (servable from any local path)
```

No third-party network calls, fonts, or trackers — JetBrains Mono is bundled
locally via `@fontsource`, so it loads and is fully interactive offline.

## Structure

```
src/
  styles/tokens.css     all design tokens (single-sourced CSS variables)
  styles/global.css     one stylesheet, organized by component/view
  lib/types.ts          the domain contract the whole UI reads
  lib/mock.ts           realistic sample state
  lib/api.ts            the ONE data seam — typed stubs over mock.ts
  lib/state.tsx         app context: view, scope, toasts, ⌘K, confirm gate
  components/           Shell, ConfirmCard, TraceChip, GraphView, Palette, primitives…
  views/                Chat · Voice · Memory · Routines · Connectors · Settings
  App.tsx               client-side view routing (no reloads)
```

## Wiring the real backend

Everything reads through **`src/lib/api.ts`**. Each method today resolves from
`mock.ts`; to go live, replace each body with a `fetch` to the localhost API
(e.g. `http://127.0.0.1:8787`). The types in `types.ts` are the contract — keep
them and the components don't change.

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
