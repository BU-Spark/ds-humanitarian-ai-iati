# UI guardrails for the Atlas page

AI coding agents (and people) read the DOM, not the screen, so they place things that look fine in code and collide on a real display. These rules exist to catch that before a deploy.

## Rules

1. **No hard-coded positions for anything that can collide.** Positions come from measured boxes (`getBoundingClientRect`), solved at runtime and on resize, font load, and content change. The globe solver in `globe/atlas-globe.js` is the reference: it takes the element it must avoid and returns a centre and radius that keep a fixed gap.
2. **Text always wins.** Decorative layers (globe, arcs' discs, glows) yield space to text: they move, shrink, or bleed off the edge, never the other way round. Minimum clearance between the globe disc and any text block is 16 px; the solver targets 32 px.
3. **Check the viewport matrix, not one screen.** Every visual change is checked at 390, 768, 1024, 1210, 1280, 1366, 1440, 1512, 1728, 1920 and 2560 px widths. 1210 x 756 is a 13 to 14 inch MacBook at default scaling.
4. **No sideways scroll** at any width; side gutters stay at least 16 px.
5. **Animated states count.** Check the resting state of every animated step (hero, each hotspot card), not just the first frame.
6. **Evidence before delivery.** A UI change is not done until `npm run check:layout` passes and a screenshot of the user's screen size has been looked at.

## How to run the check

```
cd fa26/web/globe
npm install && npx playwright install chromium     # once
python ../server.py &                               # or any server for fa26/web/static
npm run check:layout -- http://127.0.0.1:8080
```

It prints one row per viewport (layout mode, globe radius, smallest gap, worst element) and exits with code 1 on any violation, saving screenshots of failures to `ui-check-out/`.

## What it does not cover

Arcs that leave the globe disc (thin, decorative) are not counted as collisions. Colour contrast and motion are reviewed by eye.
