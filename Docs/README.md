# FHire Frontend

**We don't rank resumes. We rank hiring decisions.**

Next.js 14 dashboard for AI Engineer candidate ranking — built with mock data, ready to swap to a FastAPI backend with a one-file change.

## Quick start

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

> **Note:** If your project folder contains `&` (e.g. `Frontend&ui`), npm scripts use `node ./node_modules/next/dist/bin/next` directly to avoid Windows path issues.

## Pages

| Route | Description |
|-------|-------------|
| `/` | Landing — hero, 4 dimension cards, CTA |
| `/rankings` | Filterable table, compare flow, CSV export |
| `/candidate/[id]` | Full detail — scores, timeline, reasoning, counterfactuals |
| `/compare?a=&b=` | Side-by-side dimension comparison + verdict |
| `/analytics` | Charts — score DNA, location, notice period, disqualifiers |
| `/demo` | Simulated ranking run → redirects to rankings |
| `/intake` | JD synthesis + dimension weight configurator |

## Mock data → Real API

All data fetching lives in **`src/lib/api.ts`**. Currently returns mock data with simulated delays.

When Member 2's FastAPI backend is ready:

1. Set `NEXT_PUBLIC_API_URL=https://your-api.vercel.app` (or local URL)
2. Set `NEXT_PUBLIC_USE_MOCK=false`
3. Replace mock branches in `getRankings()`, `getCandidate()`, `compareCandidates()`, `getStats()` with `axios.get(...)` calls

Components never import mock data directly — only `lib/api.ts`.

## CSV export

- **In-app:** Rankings page → "Export CSV" button
- **Static file:** `public/talentgraph-rankings.csv` (regenerate with `npm run generate-csv`)

## Deploy to Vercel

```bash
git push
# Import repo in Vercel — zero config needed
```

Environment variables (optional until backend exists):

```
NEXT_PUBLIC_API_URL=https://your-backend.example.com
NEXT_PUBLIC_USE_MOCK=true
```

## Tech stack

- Next.js 14 App Router, TypeScript
- Tailwind CSS + approved FHire design tokens
- shadcn/ui-style components (Radix primitives)
- Recharts
- Axios (adapter layer only)

## Project structure

```
src/
  app/           # Pages (App Router)
  components/    # UI + SignalField shader
  data/          # raw-candidates.json (50 profiles)
  lib/
    api.ts       # ← swap point for real API
    mock-data.ts
    candidate-scorer.ts
    types.ts
public/
  talentgraph-rankings.csv
```
