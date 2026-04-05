"""HUD and visualization rendering helpers."""
from __future__ import annotations

import math

import streamlit as st


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def render_hr_live_monitor(
    *,
    points_24h: int,
    points_7d: int,
    rolloffs_due_7d: int,
    perfect_due_7d: int,
    label: str = "At a glance",
    pto_utilization_pct: float | None = None,
):
    """
    Data-driven 'live monitor' animation bar.

    Normal mode (pto_utilization_pct is None):
      - Speed driven by recent points activity
      - Glow driven by upcoming rolloff/perfect-attendance deadlines
      - Color always cyan

    PTO mode (pto_utilization_pct provided):
      - Cyan  : utilization <= 50 %
      - Amber : 51–80 %
      - Red   : 81 %+  (pulsing)
    """
    # ── PTO color override ────────────────────────────────────────────────────
    safe_label = _html_inline(label)

    if pto_utilization_pct is not None:
        p = pto_utilization_pct
        if p <= 50.0:
            r, g, b = 0, 200, 240          # cyan
            pulse = False
            status = f"PTO Utilization {p:.0f}% — Normal"
        elif p <= 80.0:
            r, g, b = 240, 168, 0          # amber
            pulse = False
            status = f"PTO Utilization {p:.0f}% — Elevated"
        else:
            r, g, b = 255, 48, 80          # red
            pulse = True
            status = f"PTO Utilization {p:.0f}% — High"

        sweep_s   = 1.4
        glow      = 0.72
        baseline  = 0.35
        pulse_css = """
  animation: hr_pulse 0.9s ease-in-out infinite;
}
@keyframes hr_pulse {
  0%,100% { opacity: 0.65; }
  50%      { opacity: 1.0;  }
""" if pulse else ""
        safe_status = _html_inline(status)

        st.markdown(
            f"""<style>
.hr-monitor-wrap {{ margin: 6px 0 10px 0; }}
.hr-monitor-top  {{ display:flex; justify-content:space-between; align-items:baseline; gap:10px; margin-bottom:6px; }}
.hr-monitor-label  {{ font-size:0.92rem; opacity:0.92; }}
.hr-monitor-status {{ font-size:0.86rem; opacity:0.75; white-space:nowrap; color:rgb({r},{g},{b}); font-weight:600; }}
.hr-live-monitor {{
  position:relative; width:100%; height:14px; border-radius:999px;
  background:rgba(255,255,255,0.10); overflow:hidden;
  box-shadow:inset 0 0 0 1px rgba(255,255,255,0.12);
  {pulse_css}
}}
.hr-live-monitor::before {{
  content:""; position:absolute; left:0; top:50%; transform:translateY(-50%);
  width:100%; height:2px; background:rgba({r},{g},{b},{baseline});
}}
.hr-live-monitor::after {{
  content:""; position:absolute; top:0; left:-30%; width:30%; height:100%;
  background:linear-gradient(90deg,
    rgba(0,0,0,0),
    rgba({r},{g},{b},{glow}),
    rgba({r},{g},{b},{min(glow+0.12,0.90):.2f}),
    rgba({r},{g},{b},{glow}),
    rgba(0,0,0,0)
  );
  animation:hr_sweep {sweep_s:.2f}s linear infinite;
}}
@keyframes hr_sweep {{ 0% {{ left:-30%; }} 100% {{ left:100%; }} }}
</style>
<div class="hr-monitor-wrap">
  <div class="hr-monitor-top">
    <div class="hr-monitor-label">{safe_label}</div>
    <div class="hr-monitor-status">{safe_status}</div>
  </div>
  <div class="hr-live-monitor"></div>
</div>""",
            unsafe_allow_html=True,
        )
        return

    # ── Standard attendance mode ───────────────────────────────────────────────
    # Weighted: last 24h matters most, then 7d.
    activity_raw = (points_24h * 2.5) + (points_7d * 0.6)
    # Log scale so it doesn't go ridiculous on big weeks:
    activity_norm = 1.0 - math.exp(-activity_raw / 12.0)  # ~0..1
    activity_norm = _clamp(activity_norm, 0.0, 1.0)

    # --- Urgency score (0..1): deadlines coming due ---
    urgency_raw = (rolloffs_due_7d * 1.2) + (perfect_due_7d * 1.4)
    urgency_norm = 1.0 - math.exp(-urgency_raw / 10.0)
    urgency_norm = _clamp(urgency_norm, 0.0, 1.0)

    # --- Map scores -> animation + glow ---
    # Sweep duration: 2.6s (calm) down to 0.9s (hot)
    sweep_s = 2.6 - (1.7 * activity_norm)
    sweep_s = _clamp(sweep_s, 0.9, 2.6)

    # Glow opacity: subtle -> bright
    glow = 0.18 + (0.55 * urgency_norm)  # 0.18..0.73
    glow = _clamp(glow, 0.18, 0.75)

    # Base line opacity: slightly responds to activity
    baseline = 0.20 + (0.25 * activity_norm)  # 0.20..0.45
    baseline = _clamp(baseline, 0.18, 0.50)

    # Status text
    if activity_norm < 0.18 and urgency_norm < 0.18:
        status = "Calm"
    elif activity_norm < 0.45 and urgency_norm < 0.35:
        status = "Active"
    elif activity_norm < 0.75 or urgency_norm < 0.65:
        status = "Busy"
    else:
        status = "Hot"
    safe_status = _html_inline(status)

    # Render
    st.markdown(
        f"""
<style>
.hr-monitor-wrap {{
  margin: 6px 0 10px 0;
}}

.hr-monitor-top {{
  display:flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 6px;
}}

.hr-monitor-label {{
  font-size: 0.92rem;
  opacity: 0.92;
}}

.hr-monitor-status {{
  font-size: 0.86rem;
  opacity: 0.75;
  white-space: nowrap;
}}

.hr-live-monitor {{
  position: relative;
  width: 100%;
  height: 14px;
  border-radius: 999px;
  background: rgba(255,255,255,0.10);
  overflow: hidden;
  box-shadow: inset 0 0 0 1px rgba(255,255,255,0.12);
}}

.hr-live-monitor::before {{
  content:"";
  position:absolute;
  left:0; top:50%;
  transform: translateY(-50%);
  width:100%;
  height:2px;
  background: rgba(120,200,255,{baseline});
}}

.hr-live-monitor::after {{
  content:"";
  position:absolute;
  top:0; left:-30%;
  width:30%;
  height:100%;
  background: linear-gradient(90deg,
    rgba(0,0,0,0),
    rgba(120,200,255,{glow}),
    rgba(120,200,255,{_clamp(glow+0.12, 0.20, 0.90)}),
    rgba(120,200,255,{glow}),
    rgba(0,0,0,0)
  );
  animation: hr_sweep {sweep_s:.2f}s linear infinite;
}}

@keyframes hr_sweep {{
  0%   {{ left: -30%; }}
  100% {{ left: 100%; }}
}}
</style>

<div class="hr-monitor-wrap">
  <div class="hr-monitor-top">
    <div class="hr-monitor-label">{safe_label}</div>
    <div class="hr-monitor-status">{safe_status} &middot; 24h:{points_24h} &middot; 7d:{points_7d} &middot; due7d:{rolloffs_due_7d + perfect_due_7d}</div>
  </div>
  <div class="hr-live-monitor"></div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_tech_hud(
    building: str,
    *,
    at_risk_5plus: int = 0,
    total_employees: int = 1,
) -> None:
    """Live HUD status bar with reactive colors based on employees at 5+ points.

    ACTIVITY label + bar/border color:
      Cyan  (< 10 % at 5+ pts)  — Normal
      Amber (10–24 %)            — Elevated
      Red   (25 %+)              — Critical
    """
    pct = (at_risk_5plus / max(total_employees, 1)) * 100.0

    if pct < 10.0:
        act_label   = "NORMAL"
        act_rgb     = "0,200,240"      # cyan
        bar_speed   = "1.4s"
        border_rgba = "rgba(0,120,255,.22)"
        sweep_rgba  = "rgba(0,200,240,.04)"
        top_rgba    = "rgba(0,200,240,.30)"
    elif pct < 25.0:
        act_label   = "ELEVATED"
        act_rgb     = "240,168,0"      # amber
        bar_speed   = "0.9s"
        border_rgba = "rgba(240,168,0,.45)"
        sweep_rgba  = "rgba(240,168,0,.06)"
        top_rgba    = "rgba(240,168,0,.50)"
    else:
        act_label   = "CRITICAL"
        act_rgb     = "255,48,80"      # red
        bar_speed   = "0.55s"
        border_rgba = "rgba(255,48,80,.55)"
        sweep_rgba  = "rgba(255,48,80,.07)"
        top_rgba    = "rgba(255,48,80,.60)"

    components.html(
        f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{
  background: transparent;
  font-family: 'Space Mono','SF Mono','Fira Code',ui-monospace,'Cascadia Code','Courier New',monospace;
  overflow: hidden;
}}
#hud {{
  display: flex; justify-content: space-between; align-items: center;
  padding: 7px 14px;
  background: rgba(2,8,22,0.94);
  border: 1px solid {border_rgba};
  border-radius: 10px;
  font-size: 10.5px; letter-spacing: .08em; color: #2d4860;
  box-shadow: 0 0 0 1px rgba(0,200,240,.04), 0 4px 24px rgba(0,0,0,.60),
              inset 0 1px 0 rgba(255,255,255,.025);
  position: relative; overflow: hidden;
}}
#hud::after {{
  content: '';
  position: absolute; top: 0; left: -80%; width: 40%; height: 100%;
  background: linear-gradient(90deg, transparent, {sweep_rgba}, transparent);
  animation: hud-sweep 7s linear infinite;
  pointer-events: none;
}}
@keyframes hud-sweep {{ 0% {{ left:-80%; }} 100% {{ left:160%; }} }}
#hud::before {{
  content: '';
  position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent 5%, {top_rgba} 50%, transparent 95%);
  animation: hud-top 5s ease-in-out infinite;
}}
@keyframes hud-top {{ 0%,100% {{ opacity:.40; }} 50% {{ opacity:.90; }} }}
.hud-left  {{ display:flex; align-items:center; gap:0; flex-wrap:nowrap; }}
.hud-right {{ display:flex; align-items:center; gap:0; flex-wrap:nowrap; }}
.seg {{ white-space:nowrap; }}
.dot {{
  display:inline-block; width:6px; height:6px; border-radius:50%;
  background:#00e896; margin-right:6px; vertical-align:middle;
  box-shadow:0 0 6px rgba(0,232,150,.70);
  animation:dot-blink 1.8s ease-in-out infinite;
}}
@keyframes dot-blink {{
  0%,100% {{ opacity:1;   box-shadow:0 0 4px  rgba(0,232,150,.65); }}
  50%      {{ opacity:.45; box-shadow:0 0 12px rgba(0,232,150,.95); }}
}}
.bars {{ display:inline-flex; align-items:flex-end; gap:2px; height:12px; margin:0 4px; vertical-align:middle; }}
.bar  {{ width:3px; border-radius:1px; }}
.bar:nth-child(1) {{ animation:bar-bounce {bar_speed} ease-in-out infinite 0.00s; }}
.bar:nth-child(2) {{ animation:bar-bounce {bar_speed} ease-in-out infinite 0.15s; }}
.bar:nth-child(3) {{ animation:bar-bounce {bar_speed} ease-in-out infinite 0.30s; }}
@keyframes bar-bounce {{
  0%,100% {{ height:3px;  background:rgba({act_rgb},.30); }}
  50%      {{ height:11px; background:rgba({act_rgb},.90); box-shadow:0 0 6px rgba({act_rgb},.50); }}
}}
.act-val {{ color:rgba({act_rgb},1); font-weight:700; }}
.signal {{ display:inline-flex; align-items:center; gap:3px; margin:0 4px; vertical-align:middle; }}
.sig-dot {{ width:4px; height:4px; border-radius:50%; }}
.sig-dot:nth-child(1) {{ background:rgba({act_rgb},.90); box-shadow:0 0 4px rgba({act_rgb},.50); animation:sig-pulse 2.4s ease-in-out infinite 0.0s; }}
.sig-dot:nth-child(2) {{ background:rgba({act_rgb},.65); animation:sig-pulse 2.4s ease-in-out infinite 0.6s; }}
.sig-dot:nth-child(3) {{ background:rgba({act_rgb},.35); animation:sig-pulse 2.4s ease-in-out infinite 1.2s; }}
@keyframes sig-pulse {{ 0%,100%{{opacity:.50;}} 50%{{opacity:1;}} }}
.val  {{ color:#4a88c0; }}
.hi   {{ color:#00c8f0; font-weight:700; }}
.green{{ color:#00e896; font-weight:700; }}
.sep  {{ color:rgba(0,120,255,.22); padding:0 10px; }}
#hud-time {{ color:#00c8f0; font-weight:700; letter-spacing:.14em; min-width:72px; text-align:right; }}
#hud-date {{ color:#2d4860; }}
</style></head><body>
<div id="hud">
  <div class="hud-left">
    <span class="seg"><span class="dot"></span>SYS&nbsp;<span class="green">ONLINE</span></span>
    <span class="sep">|</span>
    <span class="seg">
      <span class="bars"><span class="bar"></span><span class="bar"></span><span class="bar"></span></span>
      ACTIVITY&nbsp;<span class="act-val">{act_label}</span>
    </span>
    <span class="sep">|</span>
    <span class="seg">BUILDING&nbsp;<span class="val">{building.upper()}</span></span>
    <span class="sep">|</span>
    <span class="seg">SESSION&nbsp;<span class="hi" id="uptime">00:00:00</span></span>
    <span class="sep">|</span>
    <span class="seg">SIGNAL: Strong <span class="signal"><span class="sig-dot"></span><span class="sig-dot"></span><span class="sig-dot"></span></span></span>
  </div>
  <div class="hud-right">
    <span class="seg" id="hud-date"></span>
    <span class="sep">|</span>
    <span id="hud-time">--:--:--</span>
  </div>
</div>
<script>
(function(){{
  var s=Date.now();
  var D=['SUN','MON','TUE','WED','THU','FRI','SAT'];
  var M=['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
  function p(n){{return n<10?'0'+n:''+n;}}
  function tick(){{
    var d=new Date(),ht=document.getElementById('hud-time'),
        hd=document.getElementById('hud-date'),up=document.getElementById('uptime');
    if(!ht)return;
    ht.textContent=p(d.getHours())+':'+p(d.getMinutes())+':'+p(d.getSeconds());
    hd.textContent=D[d.getDay()]+' '+p(d.getDate())+' '+M[d.getMonth()]+' '+d.getFullYear();
    var e=Math.floor((Date.now()-s)/1000);
    up.textContent=p(Math.floor(e/3600))+':'+p(Math.floor(e%3600/60))+':'+p(e%60);
  }}
  tick();setInterval(tick,1000);
}})();
</script>
</body></html>""",
        height=46,
        scrolling=False,
    )
