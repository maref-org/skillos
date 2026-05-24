# Verified Dashboard Design Patterns

## Architecture Patterns

### Single-File SPA (Proven)
Self-contained HTML with embedded `<style>` and `<script>`. Zero build step, zero config, instant deployment via `python3 -m http.server`.
**When:** Internal tools, prototypes, agent consoles under 1000 lines.
**Trade-off:** No TypeScript, no module system. Acceptable for dashboards that change infrequently.

### IIFE Scope Isolation
```javascript
(function(){
  const API='http://localhost:8123';
  // all code here
})();
```
**Why:** Prevents global namespace pollution. Use `window.fn = ...` for functions that need HTML attribute access (onclick/onchange).

### CSS Variable Theming
```css
:root{ --accent:#0071e3; --bg:#f5f5f7; }
[data-mode="dark"]{ --accent:#0a84ff; --bg:#1d1d1f; }
```
**Why:** Single attribute toggle (`<html data-mode="dark">`) switches ALL colors. No class juggling.

### File-Backed Persistence
```python
data = _read_json(path, default)
# ... mutations ...
_write_json(path, data)
```
**Why:** JSON files simpler than SQL for internal tools. Atomic write, no migration needed. Works across server restarts without external DB.

### LLM Context Injection
```python
system_context = f"系统当前状态:\n- 总任务: {total}\n- 已完成: {done}\n..."
reply = llm_generate(f"你是 Athena，请基于以下真实数据回复。\n{system_context}\n\n{content}")
```
**Why:** Prevents LLM hallucinations by injecting real-time system data into every prompt.

---

## CSS Patterns

### Three-Column Layout
```css
#sidebar-left{width:240px;min-width:200px;max-width:360px}
#center-col{flex:1;display:flex;flex-direction:column;min-width:300px}
#sidebar-right{width:300px;min-width:240px;max-width:400px}
#sidebar-left.collapsed{width:0!important;min-width:0!important}
```
**Pattern:** flex:1 center + fixed-width collapsible sidebars.

### View Switching
```css
.v{display:none;flex-direction:column;flex:1;min-height:0}
.v.active{display:flex}
```
```javascript
document.querySelectorAll('.v').forEach(x=>x.classList.remove('active'));
document.getElementById('v-'+viewName).classList.add('active');
```

### Scroll Per View
Each view gets its own `overflow-y:auto` container. Parent `.v` has `overflow:hidden` removed.
```css
.chat-scroll,.dash-scroll,.st-scroll{flex:1;overflow-y:auto}
```
**Anti-pattern fixed:** Parent `.v` set to `overflow:hidden` prevented child scroll containers from working.

### Zoom Resilience
```css
.st-row{display:flex;flex-wrap:wrap;align-items:center;gap:8px}
input{flex:1;min-width:50px}
```
Tested at 150% zoom — content wraps instead of overflowing.

### Loading Animation
```css
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
```
Used for thinking indicators, error dots, status indicators.

### Status Colors (Three-Tier)
- **Green** (>40% good metrics, ≤40% bad): `var(--good)`
- **Yellow** (40-70%): `var(--warn)`
- **Red** (>70%): `var(--danger)`
Applied to activity, pressure, error rate, and progress bars.

---

## JavaScript Patterns

### Event Delegation (Proven)
```javascript
document.addEventListener('click',function(e){
  var row=e.target.closest('[data-st-toggle]');
  if(!row)return;
  var key=row.getAttribute('data-st-toggle');
  // handle toggle
});
```
**Why:** Works with dynamically generated content. No need to re-bind after innerHTML updates.

### Parallel XHR Data Loading
```javascript
function loadDashboard(){
  _tasks=null;
  var x=new XMLHttpRequest(); x.open('GET',API+'/api/v1/tasks'); x.send();
  var s=new XMLHttpRequest(); s.open('GET',API+'/api/v1/tasks/stats'); s.send();
  var y=new XMLHttpRequest(); y.open('GET',API+'/api/v1/metrics'); y.send();
}
```
**Why:** Three parallel fetches. Each callback populates its own section independently.

### Time-Based Data Filtering
```javascript
var now3d=Date.now()-86400000*3;
var active=_tasks.filter(function(t){
  return t.status!=='done' && (t.status==='running' || t.createdAt>now3d);
});
```
**Why:** Hides stale/zombie data without removing it from source. Running tasks always shown regardless of age.

### Direct DOM onclick (Most Reliable)
```html
<div onclick="(function(){var b=document.getElementById('tog-theme');var n=b.classList.contains('on');b.className='tog '+(n?'off':'on')})()">
```
**Why:** After extensive testing with IIFE-scoped functions, addEventListener, and event delegation, **inline IIFE onclick** was the only pattern that worked across all environments without scope chain issues.

### XHR with Error Handling
```javascript
var x=new XMLHttpRequest();
x.open('POST',API+'/api/v1/tasks/'+encodeURIComponent(tid)+'/retry');
x.onload=function(){
  if(x.status===200){btn.textContent='✓';btn.style.background='var(--good)'}
  else{btn.textContent='失败';btn.style.background='var(--danger)'}
};
x.onerror=function(){btn.textContent='网络错';btn.style.background='var(--danger)'};
x.send();
```

### Data Refresh Intervals
```javascript
setInterval(loadDashboard,15000);
setInterval(loadConversations,30000);
setInterval(loadAgents,20000);
setInterval(loadSkills,60000);
setInterval(loadMonitoring,10000);
```
**Why:** Each section has its own refresh rate based on data change frequency.
