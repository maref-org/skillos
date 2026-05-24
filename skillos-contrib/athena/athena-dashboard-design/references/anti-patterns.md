# Dashboard Anti-Patterns & Root Causes

> Catalogued from 15+ bug fixes during Athena UI v1.1 development.

## 1. Inline onclick + IIFE Scope Isolation

**Symptom:** Settings toggles appear but clicking produces no response. No console errors.
**Root cause:** Functions defined inside IIFE `(function(){ window.toggleSetting=function(){...} })()` are NOT accessible as bare identifiers from HTML `onclick="toggleSetting()"`. The `window.X = ...` assignment makes the function globally accessible, but `onclick` handlers resolve through scope chain which may not find window properties.
**Fix:** Use inline IIFE in the onclick attribute itself:
```html
<!-- ❌ Broken -->
<button onclick="toggleSetting('theme')">

<!-- ✅ Reliable -->
<button onclick="(function(){var b=document.getElementById('tog-theme');var n=b.classList.contains('on');b.className='tog '+(n?'off':'on')})()">
```

## 2. Duplicate Event Handlers

**Symptom:** Toggle appears to "not work" — visually unchanged after clicking.
**Root cause:** Both `addEventListener('click', ...)` on document AND `onclick` attribute on the same element fire. First handler toggles, second handler toggles it back. Net effect: no change.
**Fix:** Use exactly ONE binding method per element. Remove all event delegation when using inline onclick.

## 3. ISO Date String Not Parsed as Timestamp

**Symptom:** Time-based filter (`now3d`) shows ALL old tasks instead of filtering them.
**Root cause:** `created_at` in `tasks.json` is ISO format string (`"2026-04-19T10:28:26+08:00"`). API code checked `isinstance(v, (int, float))` which failed for strings, falling back to `int(time.time()*1000)` — giving every task the current timestamp.
**Fix:** Add a date string parser:
```python
def _parse_ts(v: Any) -> int:
    if isinstance(v, str):
        return int(datetime.fromisoformat(v).timestamp() * 1000)
    return int(v) if isinstance(v, (int,float)) else int(time.time()*1000)
```

## 4. Missing Dark Mode CSS

**Symptom:** Settings toggle changes `data-mode` attribute but page doesn't change color.
**Root cause:** `document.documentElement.setAttribute('data-mode','dark')` works correctly, but NO CSS rules respond to `[data-mode="dark"]`. The attribute was set but no visual rules defined.
**Fix:** Define full dark mode variable overrides:
```css
[data-mode="dark"]{
  --accent:#0a84ff;--ink:#f0f0f2;--bg:#1d1d1f;
  --surface:#2c2c2e;--border-soft:#48484a;
}
[data-mode="dark"] .sidebar-nav a{color:#ffffff}
[data-mode="dark"] .topbar{background:rgba(44,44,46,0.92)}
/* ... 29 rules total for full coverage */
```

## 5. Fake Random GPU Data

**Symptom:** User reports "82°C GPU temperature feels wrong — I don't feel the machine heating up."
**Root cause:** Backend used `random.uniform(30, 90)` for GPU and `random.uniform(45, 85)` for GPU temperature as fallback values, producing fake metrics.
**Fix:** Return `None` for unavailable metrics. Show "N/A" in UI. Use psutil for real CPU/memory/disk data only.

## 6. Subprocess Relative Import Crash

**Symptom:** Runner daemon starts but worker subprocesses fail with `ImportError: attempted relative import with no known parent package`.
**Root cause:** `spawn_build_worker()` built command `python3 executor.py run-item ...` running `executor.py` directly. `executor.py` uses `from .config import ...` relative imports that need package context (`-m runner.executor`).
**Fix:** Point subprocess to the runner script which has a proper CLI entry point:
```python
# ❌ wrong target
str(Path(__file__).resolve())  # executor.py — no main, relative imports fail

# ✅ correct target
runner_script = Path(__file__).resolve().parent / "athena_ai_plan_runner.py"
```

## 7. Parent `overflow:hidden` Blocks Child Scroll

**Symptom:** Settings page content overflows but cannot scroll. User can't see "保存" button at 150% zoom.
**Root cause:** `.v` view container has `overflow:hidden`. Child `.st-scroll` has `overflow-y:auto`, but parent overflow:hidden clips the child's scroll container.
**Fix:** Remove `overflow:hidden` from `.v`. Each view's own scroll container handles overflow.

## 8. Missing `callback` When Data is Served Stale

**Symptom:** User deletes plan queue files but dashboard still shows old task data.
**Root cause:** Data comes from multiple sources: `tasks.json` (execution records — still has data) vs `plan_queue/` files (to-do list — deleted). UI showed tasks.json data which user perceived as "old data still showing."
**Fix:** Add a "清理过时" (cleanup) button that marks old pending/failed tasks as completed. Time-filter pipeline to show only recent tasks.

## 9. Scope: `var` in Callback ≠ Accessible Elsewhere

**Symptom:** Sidebar queue list shows "加载中…" forever.
**Root cause:** 
```javascript
x.onload=function(){
  try{var tasks=JSON.parse(x.responseText); /* tasks is LOCAL to this callback */}
  catch(e){}
};
// Later, in a DIFFERENT callback:
if(typeof tasks!='undefined'&&tasks.length) // tasks is undefined here
```
**Fix:** Declare shared variable at parent function level: `var _tasks=null;` at the start of `loadDashboard()`.

## 10. Duplicate XMLHttpRequest.send()

**Symptom:** Intermittent data loading failures, console errors about "invalid state."
**Root cause:** Two `x.send()` calls for the same XHR object (one in the callback block, one at the parent level).
**Fix:** Remove the duplicate. Each XHR object receives exactly one `.send()`.

## 11. `conversations.json` Creates 0-Byte File on Crash

**Symptom:** Server fails to start with `NameError: name 'OC' is not defined`.
**Root cause:** `CONVERSATIONS_PATH = OC / "conversations.json"` defined before `OC = REPO / ".openclaw"`. Also: `_load_conversations()` called before `_read_json()` defined.
**Fix:** Order definitions: paths → helpers (_ts, _read_json, _write_json) → conversation store → _load_conversations() call.

## 12. Status Mapping Missing `running`

**Symptom:** Running tasks displayed as "排队中" (pending) instead of "运行中" (running).
**Root cause:** Status mapping dict: `{"completed":"done","failed":"fail","processing":"running","pending":"pending"}` — missing `"running":"running"` entry.
**Fix:** Add `"running":"running"` and `"manual_hold":"pending"` to the mapping.
