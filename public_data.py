"""Read ordinary public HTML. No account, cookies, private API, or login bypass."""
import datetime as dt
import html
import json
from pathlib import Path
import re
import threading
import time
from html.parser import HTMLParser
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
REGISTRY = json.loads((ROOT / 'public_sources.json').read_text())
LOCK = threading.Lock()
TTL = 900

class ImageParser(HTMLParser):
    def __init__(self): super().__init__(); self.avatar = None
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'img' and attrs.get('class') == 'avatar' and self.avatar is None:
            src = attrs.get('src', '')
            if re.match(r'^https://[a-zA-Z0-9.-]+\.sinaimg\.cn/', src): self.avatar = src

def parse_profile(text, entry, fetched_at):
    title = re.search(r'<title>([^<]+)的微博_新浪新闻</title>', text)
    if not title: raise ValueError('公开页面未返回艺人资料，可能暂时不可访问。')
    name = html.unescape(title.group(1)).strip()
    if name.casefold() not in [n.casefold() for n in entry['aliases']]:
        raise ValueError('页面姓名与目标艺人不符，未写入数据。')
    pairs = re.findall(r'<span class="num">([^<]+)</span>\s*<span class="label">([^<]+)</span>', text)
    fields = {'粉丝': ('followers','粉丝数'), '关注': ('following','关注数'), '微博': ('posts','微博数量')}
    metrics=[]
    for raw, label in pairs[:3]:
        raw, label = html.unescape(raw).strip(), html.unescape(label).strip()
        if label not in fields or not re.fullmatch(r'[\d,.]+[万亿]?', raw): continue
        exact = bool(re.fullmatch(r'[\d,]+', raw))
        metric, caption = fields[label]
        metrics.append({'metric':metric,'label':caption,'displayValue':raw,'exact':exact,
                        'value':int(raw.replace(',','')) if exact else None})
    if len(metrics) != 3 or {m['metric'] for m in metrics} != {'followers','following','posts'}:
        raise ValueError('公开页面结构变化，无法可靠提取指标。')
    image=ImageParser();image.feed(text)
    return {'artistId': entry['id'], 'name': name, 'uid': entry['uid'], 'photo':image.avatar,
            'sourceUrl': 'https://www.sina.cn/media/' + entry['uid'], 'platform':'微博',
            'sourceLabel':'新浪公开微博主页', 'fetchedAt':fetched_at, 'platformUpdatedAt':None,
            'metrics':metrics, 'note':'直接读取无需登录的新浪公开主页；平台未提供这些计数的更新时间，可能存在同步延迟。'}

def read_store():
    try:return json.loads((ROOT/'public-data.json').read_text())
    except (OSError,ValueError):return {'profiles':[]}

def write_store(store):
    path=ROOT/'public-data.json'; temporary=ROOT/'public-data.tmp'
    temporary.write_text(json.dumps(store,ensure_ascii=False,indent=2));temporary.replace(path)
    # Static opening and the original preview server can also display the last successful snapshot.
    (ROOT/'public-data.js').write_text('window.YINLANG_PUBLIC = '+json.dumps(store,ensure_ascii=False)+';\n')

def refresh(entry):
    with LOCK:
        store=read_store()
        cached=next((p for p in store['profiles'] if p['uid']==entry['uid']),None)
        if cached:
            stamp=dt.datetime.fromisoformat(cached['fetchedAt'])
            if time.time()-stamp.timestamp()<TTL: return {'profile':cached,'cached':True,'error':None}
        try:
            request=Request('https://www.sina.cn/media/'+entry['uid'],headers={'User-Agent':'YinlangPublicDashboard/1.0','Accept':'text/html'})
            with urlopen(request,timeout=15) as response:
                # A login redirect is not a valid profile and will fail the parser.
                text=response.read(3_000_000).decode('utf-8')
            profile=parse_profile(text,entry,dt.datetime.now(dt.timezone.utc).isoformat())
            history=store.setdefault('history',[])
            if cached and not any(p['uid']==cached['uid'] and p['fetchedAt']==cached['fetchedAt'] for p in history): history.append(cached)
            store['history']=history[-1000:]
            store['profiles']=[p for p in store['profiles'] if p['uid']!=entry['uid']]+[profile]
            write_store(store)
            return {'profile':profile,'cached':False,'error':None}
        except Exception as exc:
            message=str(exc) if isinstance(exc,ValueError) else '本次未能读取公开页面。保留上一次资料，不补写新数据。'
            return {'profile':cached,'cached':bool(cached),'error':message}
