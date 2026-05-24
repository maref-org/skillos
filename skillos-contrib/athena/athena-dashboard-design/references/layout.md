# Three-Column Dashboard Layout

## HTML Skeleton

```html
<div id="app">
  <!-- Left Sidebar: 240px, collapsible -->
  <aside id="sidebar-left">
    <div class="sidebar-inner">
      <div class="sidebar-brand">
        <div class="logo">A</div>
        <div>App Name<div>v1.0.0</div></div>
      </div>
      <nav class="sidebar-nav">
        <div class="group">核心</div>
        <a href="#" class="active" data-view="dash">📊 仪表板</a>
        <a href="#" data-view="agents">🐝 蜂群<span class="badge" id="agent-badge">0</span></a>
        <div class="group">系统</div>
        <a href="#" data-view="settings">⚙️ 设置</a>
      </nav>
      <div class="sidebar-footer">
        <span class="dot"></span><span>集群</span>
        <button class="fold-btn">◀</button>
      </div>
    </div>
  </aside>
  <!-- Collapse button on edge -->
  <button class="collapse-btn left-btn" id="collapse-left">«</button>

  <!-- Center Column: flex:1 -->
  <div id="center-col">
    <header class="topbar">
      <button class="btn-icon" id="toggle-left">☰</button>
      <span id="view-title">标题</span>
      <button class="btn-icon" id="toggle-right">☰</button>
    </header>

    <!-- View containers: ONE per page -->
    <div class="v active" id="v-dash">
      <div class="dash-scroll">...</div>
    </div>
    <div class="v" id="v-agents">
      <div class="ag-scroll">...</div>
    </div>
    <div class="v" id="v-settings">
      <div class="st-scroll">...</div>
    </div>
  </div>

  <!-- Right Sidebar: 300px, collapsible -->
  <button class="collapse-btn right-btn" id="collapse-right">»</button>
  <aside id="sidebar-right">
    <div id="right-content">...</div>
  </aside>
</div>
```

## CSS Structure

```css
:root{--accent:#0071e3;--bg:#f5f5f7;--surface:#fff;--ink:#1d1d1f;--muted:#6e6e73;--border-soft:#d2d2d7;top-h:48px}
[data-mode="dark"]{--accent:#0a84ff;--bg:#1d1d1f;--surface:#2c2c2e;--ink:#f0f0f2;--muted:#a8a8ad;--border-soft:#48484a}
*{box-sizing:border-box;margin:0;padding:0}
body{font:14px/1.5 -apple-system,Inter,sans-serif;background:var(--bg);color:var(--ink);height:100vh;overflow:hidden}
#app{display:flex;width:100%;height:100%}

/* ── Left Sidebar ── */
#sidebar-left{width:240px;min-width:200px;max-width:360px;background:var(--surface);border-right:1px solid var(--border-soft);display:flex;flex-direction:column;padding:14px 10px;height:100vh;overflow:hidden;transition:width 0.25s,min-width 0.25s,padding 0.25s,opacity 0.2s}
#sidebar-left.collapsed{width:0!important;min-width:0!important;padding:0;border-right:none;opacity:0}
.sidebar-nav a{display:flex;align-items:center;gap:9px;padding:7px 10px;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;text-decoration:none;color:var(--ink)}
.sidebar-nav a:hover{background:var(--bg)}
.sidebar-nav a.active{background:var(--accent);color:white}

/* ── Center Column ── */
#center-col{flex:1;display:flex;flex-direction:column;min-width:300px;overflow:hidden}
.topbar{display:flex;align-items:center;justify-content:space-between;padding:0 20px;height:var(--top-h);background:rgba(255,255,255,0.85);-webkit-backdrop-filter:blur(12px);border-bottom:1px solid var(--border-soft)}
.v{display:none;flex-direction:column;flex:1;min-height:0}
.v.active{display:flex}

/* ── Right Sidebar ── */
#sidebar-right{width:300px;min-width:240px;max-width:400px;background:var(--surface);border-left:1px solid var(--border-soft);padding:16px 14px;display:flex;flex-direction:column;gap:16px;height:100vh;overflow:hidden;transition:width 0.25s,min-width 0.25s,padding 0.25s,opacity 0.2s}
#sidebar-right.collapsed{width:0!important;min-width:0!important;padding:0;border-left:none;opacity:0}

/* ── Collapse Buttons ── */
.collapse-btn{position:absolute;top:50%;transform:translateY(-50%);z-index:20;width:18px;height:48px;border-radius:0 6px 6px 0;cursor:pointer;color:var(--muted)}
.collapse-btn.left-btn{right:-18px}
.collapse-btn.right-btn{left:-18px;border-radius:6px 0 0 6px}

/* ── Scroll per view ── */
.dash-scroll,.ag-scroll,.st-scroll{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:16px}
```

## View Switching JavaScript

```javascript
const views={dash:'仪表板',agents:'Agent 蜂群',settings:'系统设置'};
document.querySelectorAll('.sidebar-nav a').forEach(a=>{
  a.addEventListener('click',function(e){
    e.preventDefault();
    document.querySelectorAll('.sidebar-nav a').forEach(x=>x.classList.remove('active'));
    this.classList.add('active');
    document.querySelectorAll('.v').forEach(x=>x.classList.remove('active'));
    document.getElementById('v-'+this.dataset.view).classList.add('active');
    document.getElementById('view-title').textContent=views[this.dataset.view];
  });
});

// Sidebar collapse
function toggleLeft(){document.getElementById('sidebar-left').classList.toggle('collapsed')}
function toggleRight(){document.getElementById('sidebar-right').classList.toggle('collapsed')}
document.getElementById('collapse-left').addEventListener('click',toggleLeft);
document.getElementById('collapse-right').addEventListener('click',toggleRight);
```

## Responsive Rules

```css
.st-row{display:flex;align-items:center;justify-content:space-between;padding:10px 16px;border-bottom:1px solid var(--border-soft);cursor:pointer}
.st-row:last-child{border-bottom:none}
@media (max-width:900px){#sidebar-right{display:none}}
```
