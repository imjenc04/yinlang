"""Music metrics from ordinary, credential-free platform pages."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, urlopen
import html, json, re, threading, time
ROOT=Path(__file__).resolve().parent
CHART_URL='https://m.kuwo.cn/newh5app/ranklist_detail/154'
SALES_URL='https://i2.y.qq.com/n3/m/digitalbum/pages/sale/index.html?mid=000S79v91L2U6W'
LOCK=threading.Lock()
TTL=900
checked=-TTL

def chart_metrics(raw, stamp):
    # Read visible ranking rows, not embedded executable scripts or hidden APIs.
    dates=re.findall(r'(\d{4}-\d{2}-\d{2})\s*更新',raw)
    if not dates: raise ValueError('榜单更新时间缺失')
    rows=re.findall(r'class="number(?:Top)?[^\"]*"[^>]*>(\d+)</div>\s*<div[^>]*>\s*<div class="wordBody_title[^\"]*"[^>]*>(.*?)</div>.*?<span class="small wordType"[^>]*>(.*?)</span>',raw,re.S)
    if len(rows)!=20: raise ValueError('榜单可见行结构变化')
    sources=[];metrics=[]
    for ident,name in [('leehom','王力宏'),('chace','Chace'),('ouyang','欧阳娜娜'),('shanyi','单依纯'),('jay','周杰伦'),('ding','丁世光')]:
        sid='kuwo-154-'+ident+'-'+re.sub(r'\D','',stamp)
        matching=[]
        for rank,title,credit in rows:
            credit=html.unescape(re.sub('<[^>]+>','',credit));performers=credit.split('-',1)[0].split('&')
            if name not in performers: continue
            title=html.unescape(re.sub('<[^>]+>','',title));number=int(rank)
            matching.append(dict(artistId=ident,platform='酷我音乐',metric='chart-154-'+title,label=title+' · 综艺榜',displayValue='#'+str(number),value=number,exact=True,sourceId=sid,chartDate=dates[0],direction='lower-is-better'))
        if matching:
            sources.append(dict(id=sid,artistId=ident,kind='web',platform='酷我音乐',label='酷我综艺榜',url=CHART_URL,fetchedAt=stamp,capturedAt=dates[0],note='榜单日期 '+dates[0]+'；仅核对页面可见前 20 名。榜位不是播放量；合唱作品不计作个人独唱。'))
            metrics.extend(matching)
    return sources,metrics

def sales_metrics(raw,stamp):
    text=re.sub('<script\\b[^>]*>.*?</script>','',raw,flags=re.S)
    text=html.unescape(re.sub('<[^>]+>',' ',text))
    if 'Come What May' not in text or '王力宏' not in text: raise ValueError('数字作品身份无法核对')
    found=re.search(r'数字专辑已售\s*([\d,]+)\s*张',text)
    if not found: raise ValueError('销量数值未提供')
    count=int(found[1].replace(',',''));sid='qq-sales-leehom-'+re.sub(r'\D','',stamp)
    return [dict(id=sid,artistId='leehom',kind='web',platform='QQ音乐',label='Come What May',url=SALES_URL,fetchedAt=stamp,capturedAt=stamp[:10],note='数字销量按张计数，不等于独立购买人数；页面计数可能存在同步延迟。')],[dict(artistId='leehom',platform='QQ音乐',metric='sales-come-what-may',label='Come What May · 数字销量',displayValue=f'{count:,} 张',value=count,exact=True,sourceId=sid)]

def read_cache():
    try: return json.loads((ROOT/'music-data.json').read_text())
    except (OSError,ValueError): return {'sources':[],'metrics':[]}

def write_cache(data):
    for name,content in [('music-data.json',json.dumps(data,ensure_ascii=False)),('music-data.js','window.YINLANG_MUSIC = '+json.dumps(data,ensure_ascii=False)+';')]:
        temp=ROOT/(name+'.tmp');temp.write_text(content);temp.replace(ROOT/name)

def refresh_music():
    global checked
    with LOCK:
        result=read_cache()
        if time.monotonic()-checked<TTL: return result
        errors=[];stamp=datetime.now(timezone.utc).isoformat()
        for url,parser in [(CHART_URL,chart_metrics),(SALES_URL,sales_metrics)]:
            try:
                request=Request(url,headers={'User-Agent':'YinlangMusicDashboard/1.0'})
                with urlopen(request,timeout=8) as response: raw=response.read(2000000).decode('utf-8')
                sources,metrics=parser(raw,stamp)
                # Keep historical snapshots; failed reads never erase successful records.
                result['sources'].extend(sources);result['metrics'].extend(metrics)
            except Exception: errors.append('酷我综艺榜' if url==CHART_URL else 'QQ音乐数字销量')
        result['sources']=result['sources'][-400:];ids={s['id'] for s in result['sources']}
        result['metrics']=[m for m in result['metrics'] if m['sourceId'] in ids]
        result['error']='、'.join(errors)+'暂未更新' if errors else ''
        checked=time.monotonic();write_cache(result);return result
