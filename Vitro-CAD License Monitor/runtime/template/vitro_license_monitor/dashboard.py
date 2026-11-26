from __future__ import annotations

import html
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Settings
from .storage import Storage


def _start(settings: Settings, name: str) -> datetime:
    try:
        zone = ZoneInfo(settings.timezone)
    except ZoneInfoNotFoundError:
        zone = datetime.now().astimezone().tzinfo or timezone.utc
    now = datetime.now(zone)
    if name == "day":
        value = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif name == "week":
        value = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    elif name == "month":
        value = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        raise ValueError(name)
    return value.astimezone(timezone.utc)


def build_model(settings: Settings, storage: Storage) -> dict[str, Any]:
    latest = storage.latest()
    histories = {name: storage.since(_start(settings, name)) for name in ("day", "week", "month")}
    return {
        "latest": latest,
        "histories": histories,
        "capacity": {"WEB": settings.web_capacity, "PRO": settings.pro_capacity},
        "warning": {
            "WEB": max(1, int(settings.web_capacity * settings.warning_ratio + 0.9999)),
            "PRO": max(1, int(settings.pro_capacity * settings.warning_ratio + 0.9999)),
        },
        "timezone": settings.timezone,
    }


def render(settings: Settings, model: dict[str, Any]) -> str:
    title = html.escape("Занятость лицензий Vitro-CAD")
    data = json.dumps(model, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>
:root{{--bg:#f3f6f9;--card:#fff;--ink:#17202a;--muted:#66727f;--line:#dce3ea;--web:#2f80ed;--pro:#7b61ff;--warn:#e39a00}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif}}
main{{max-width:1120px;margin:auto;padding:24px}}header{{display:flex;justify-content:space-between;gap:16px;align-items:flex-end}}h1{{margin:0}}button{{padding:8px 14px;border:1px solid var(--line);border-radius:8px;background:#fff;cursor:pointer}}button.active{{background:#17202a;color:#fff}}
.cards{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:18px 0}}.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}}.metric{{font-size:30px;font-weight:700}}.muted{{color:var(--muted)}}svg{{width:100%;height:280px;display:block}}.grid{{stroke:var(--line)}}.threshold{{stroke:var(--warn);stroke-dasharray:6 5}}.series{{fill:none;stroke-width:3}}@media(max-width:720px){{.cards{{grid-template-columns:1fr}}header{{align-items:flex-start;flex-direction:column}}}}
</style></head><body><main><header><div><h1>{title}</h1><div id="fresh" class="muted"></div></div><div><button data-range="day">День</button> <button data-range="week">Неделя</button> <button data-range="month">Месяц</button></div></header>
<section class="cards"><article class="card" id="card-WEB"></article><article class="card" id="card-PRO"></article></section>
<section class="card"><h2>WEB</h2><svg id="chart-WEB" viewBox="0 0 920 280"></svg></section><section class="card" style="margin-top:16px"><h2>PRO</h2><svg id="chart-PRO" viewBox="0 0 920 280"></svg></section></main>
<script>const data={data};let range='day';const color={{WEB:'#2f80ed',PRO:'#7b61ff'}};const key=t=>t==='WEB'?'web_active':'pro_active';
function card(t){{const x=data.latest?.[key(t)],cap=data.capacity[t],pct=x==null?null:Math.round(x/cap*100);document.getElementById('card-'+t).innerHTML=`<div class="muted">${{t}} активны</div><div class="metric">${{x??'—'}} / ${{cap}}</div><div class="muted">${{pct==null?'Нет данных':pct+' %'}} · порог ${{data.warning[t]}}</div>`}}
function chart(t){{const svg=document.getElementById('chart-'+t),pts=data.histories[range]||[],cap=data.capacity[t],max=Math.max(cap,...pts.map(p=>Number(p[key(t)]||0)),1),L=65,R=865,T=18,B=220;if(!pts.length){{svg.innerHTML='<text x="460" y="130" text-anchor="middle" fill="#66727f">История ещё не накоплена</text>';return}}const times=pts.map(p=>Date.parse(p.observed_at)),min=Math.min(...times),mx=Math.max(...times);const X=(i)=>mx>min?L+(R-L)*(times[i]-min)/(mx-min):(L+R)/2,Y=v=>B-(B-T)*v/max;let g='';for(let i=0;i<=4;i++){{const y=T+(B-T)*i/4;g+=`<line class="grid" x1="${{L}}" y1="${{y}}" x2="${{R}}" y2="${{y}}"/><text x="8" y="${{y+4}}" fill="#66727f">${{Math.round(max*(1-i/4))}}</text>`}}const points=pts.map((p,i)=>`${{X(i)}},${{Y(Number(p[key(t)]||0))}}`).join(' '),wy=Y(data.warning[t]);const labels=pts.map((p,i)=>{{if(i%(Math.ceil(pts.length/6)||1)!==0)return '';const d=new Date(p.observed_at),label=range==='day'?d.toLocaleString('ru-RU',{{hour:'2-digit',minute:'2-digit'}}):d.toLocaleDateString('ru-RU');return `<text x="${{X(i)}}" y="248" text-anchor="middle" fill="#66727f">${{label}}</text>`}}).join('');svg.innerHTML=g+`<line class="threshold" x1="${{L}}" y1="${{wy}}" x2="${{R}}" y2="${{wy}}"/><polyline class="series" stroke="${{color[t]}}" points="${{points}}"/>${{labels}}<text x="460" y="274" text-anchor="middle" fill="#66727f">Дата и время замера</text>`}}
function draw(){{['WEB','PRO'].forEach(t=>{{card(t);chart(t)}});document.getElementById('fresh').textContent=data.latest?'Последний замер: '+new Date(data.latest.observed_at).toLocaleString('ru-RU'):'Нет замеров';document.querySelectorAll('[data-range]').forEach(b=>b.classList.toggle('active',b.dataset.range===range))}}document.querySelectorAll('[data-range]').forEach(b=>b.onclick=()=>{{range=b.dataset.range;draw()}});draw();</script></body></html>"""
