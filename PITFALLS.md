# Luminos — Known Pitfalls

## 1. Never inline dynamic data inside HTML attributes (Alpine x-data)

**Symptom:** Alpine component silently fails to initialize. The error boundary stays
visible ("Starting… Reload to reconnect"). No error appears in the console or in
`window.addEventListener('error', ...)` because Alpine catches x-data parse errors
internally and discards them.

**Root cause:** HTML attribute parsing is not JavaScript-aware. If the attribute uses
single-quote delimiters and any injected value contains a literal apostrophe, the HTML
parser ends the attribute early. Alpine receives a broken expression and silently does
nothing.

```html
<!-- WRONG — one apostrophe in class_name breaks everything, silently -->
<div x-data='boardShell({ className: "{{ class_name }}" })'>

<!-- RIGHT — script tag has no quoting constraints -->
<script>
  window._BOARD_CONFIG = {
    className: {{ class_name | tojson }},
    ...
  };
</script>
<div x-data="boardShell(window._BOARD_CONFIG)">
```

**Rule:** Put all dynamic config in a `<script>` tag as a global, then reference it
from `x-data`. The `x-data` attribute itself should contain only a plain function call
with no interpolated values.

**Wasted:** ~1 week debugging this. The Map reactive-loop issue we also fixed during
that time was real but separate — and masked by this underlying bug.

---

## 2. Map objects inside Alpine reactive scope cause infinite loops

**Symptom:** Browser shows "Page Unresponsive" immediately on load. Alpine initializes
but the JS thread hangs.

**Root cause:** Alpine uses Vue 3's `reactive()` internally. Vue wraps `Map` objects
with a special Collection proxy that tracks `.size`, `.has()`, `.get()`, `.set()` etc.
as reactive dependencies. Certain access patterns (LRU-style delete+set) trigger a
reactive dependency cycle that spins the scheduler.

**Fix:** Use a plain object instead of `Map` for any cache stored in Alpine reactive
data.

```js
// WRONG
ttsAudioCache: new Map(),

// RIGHT
ttsAudioCache: Object.create(null),
// access with: key in cache, cache[key], cache[key] = val, delete cache[key]
```
