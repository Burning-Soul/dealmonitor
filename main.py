# -*- coding: utf-8 -*-
"""618 Deal Monitor - Kivy + Flask Hybrid APK"""
import json, re, ssl, time, os, threading, shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from urllib import request, parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
import webbrowser

from kivy.app import App
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.floatlayout import FloatLayout
from kivy.clock import Clock
from kivy.utils import platform
from kivy.graphics import Color, Rectangle

Window.size = (420, 800)

# ===== FONT =====
if platform == 'android':
    for fp in ['/system/fonts/NotoSansCJK-Regular.ttc','/system/fonts/DroidSansFallback.ttf','/system/fonts/MiSans-Regular.ttf']:
        if os.path.exists(fp):
            try: LabelBase.register(name='CF', fn_regular=fp); break
            except: continue
    else: LabelBase.register(name='CF', fn_regular='DroidSans.ttf')
else:
    for fp in [r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf']:
        if os.path.exists(fp): LabelBase.register(name='CF', fn_regular=fp); break
    else: LabelBase.register(name='CF', fn_regular=r'C:\Windows\Fonts\msyh.ttc')
FONT = 'CF'

# ===== CONFIG =====
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = BASE_DIR / 'data'
STATIC_DIR = BASE_DIR / 'static'
DATA_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)
SEEN_FILE = DATA_DIR / 'seen_deals.json'
CACHE_FILE = DATA_DIR / 'deal_cache.json'
PORT = 8765

COOKIES = {
    '60014_vid': '52B86EE84E42B46529E303FBA1568CC2A1DA0110A49344278FF62812E153574E5AB67A503DB4966DD0E85BB2BF9A856F',
    'uid_hot': 'cp12954912_364416763_2026/6/13',
    '60014_mmmuser': 'BghUBgAGAAg5CwUFWQAGUAQDBwkADwVWAAkFCgdSVwUFVFJVBwtQA1Q%3d',
    'mmbuser_ext': 'CJSWXDP287',
}
COOKIE_STR = '; '.join(f'{k}={v}' for k,v in COOKIES.items())
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# ===== SCRAPER (same logic as before) =====
def fetch(url, cookie=True, timeout=15, decode_as='gb2312'):
    h = {'User-Agent': 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36',
         'Accept': 'text/html,application/xhtml+xml,*/*',
         'Accept-Language': 'zh-CN,zh;q=0.9'}
    if cookie: h['Cookie'] = COOKIE_STR
    req = request.Request(url, headers=h)
    with request.urlopen(req, timeout=timeout, context=ctx) as resp:
        raw = resp.read()
        try: return raw.decode(decode_as, errors='replace')
        except: return raw.decode('utf-8', errors='replace')

def scrape_homepage():
    html = fetch('http://www.manmanbuy.com/', decode_as='gbk')
    links = re.findall(r'href="(https?://cu\\.manmanbuy\\.com/discuxiao_(\\d+)\\.aspx)"[^>]*?title="([^"]+)"', html)
    seen_ids, deals = set(), []
    for url, did, title in links:
        if did not in seen_ids:
            seen_ids.add(did)
            deals.append({'id': did, 'url': url, 'title': title.strip()[:80]})
    return deals

def get_deal_detail(url):
    html = fetch(url, cookie=True, decode_as='gb2312')
    result = {}
    price = None
    om = re.findall(r'color\s*:\s*#[fF]{2}[4-9a-fA-F]\w{3}[^>]*>\s*(\d+\\.?\d*)\s*元?\s*<', html, re.I)
    if om:
        for p in om:
            pv = float(p)
            if 5 < pv < 50000: price = pv; break
    if price is None:
        m = re.search(r'<meta\s+name="description"[^>]*?content="[^"]*?(\d+\\.?\d*)\s*元', html, re.I)
        if m: price = float(m.group(1))
    if price is None:
        m = re.search(r'当前价格\s*(\d+\\.?\d*)\s*元', html)
        if m: price = float(m.group(1))
    if price is None:
        prices = re.findall(r'(\d+\\.?\d*)\s*元', html[:10000])
        valid = [float(p) for p in prices if 50 < float(p) < 50000]
        if valid: price = valid[0]
    result['price'] = price
    hl = re.search(r"HistoryLowest\.aspx\?[^\"\x27]*?url=([^\"\x27&\s]+)", html, re.I)
    if hl: result['product_url'] = unquote(hl.group(1))
    tag_section = re.search(r'标签[：:].*?</span>(.*?)(?:</div>|$)', html, re.DOTALL)
    rating = '普通'
    if tag_section:
        tags_raw = re.sub(r'<[^>]+>', ' ', tag_section.group(1))
        for tag in tags_raw.split():
            if '历史新低' in tag: rating = 'SSS'; break
            elif '天新低' in tag:
                try: d = int(tag.replace('天新低',''))
                except: d = 0
                if d >= 300: rating = 'SS'; break
                elif d >= 100: rating = 'S'; break
            elif '天次低' in tag:
                try: d = int(tag.replace('天次低',''))
                except: d = 0
                if d >= 300: rating = 'S'; break
            elif '历史最低' in tag: rating = 'SS'; break
    result['rating'] = rating
    tm = re.search(r'<title>\s*(.*?)\s*[_-].*?</title>', html, re.I|re.DOTALL)
    result['product'] = tm.group(1).strip() if tm else '?'
    cm = re.search(r'评论\s*(\d+)\s*次', html)
    result['comments'] = int(cm.group(1)) if cm else 0
    sm = re.search(r'商城[：:][^<]*?<a[^>]*>(.*?)</a>', html, re.I)
    result['store'] = sm.group(1) if sm else '?'
    vm = re.search(r'浏览\s*(\d[\d,]*)\s*次', html)
    result['views'] = int(vm.group(1).replace(',','')) if vm else 0
    return result

def load_json(path):
    if path.exists():
        try:
            with open(path, 'r', encoding='utf-8') as f: return json.load(f)
        except:
            backup = Path(str(path).replace('.json','_backup.json'))
            if backup.exists():
                try:
                    with open(backup, 'r', encoding='utf-8') as f: return json.load(f)
                except: pass
    return {}

def save_json(path, data):
    backup = Path(str(path).replace('.json','_backup.json'))
    if path.exists():
        try: shutil.copy2(path, backup)
        except: pass
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def compute_rankings(deals):
    rating_map = {'SSS':60,'SS':42,'S':24,'A':12}
    for d in deals:
        rating_pts = rating_map.get(d.get('rating',''),0)
        views_pts = min(d.get('views',0)/125, 40)
        d['score'] = int(rating_pts + views_pts)
    s_list = sorted([d for d in deals if d['rating'] in ('SSS','SS','S','A')],
                     key=lambda x:({'SSS':0,'SS':1,'S':2,'A':3}[x['rating']], -x.get('views',0)))
    v_list = sorted(deals, key=lambda x: -x.get('views',0))[:30]
    m_list = sorted(deals, key=lambda x: -x.get('score',0))[:30]
    return s_list, v_list, m_list

# ===== HTTP API HANDLER =====
class APIHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)
    
    def do_GET(self):
        if self.path == '/api/deals':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            cache = load_json(CACHE_FILE)
            if isinstance(cache, dict):
                deals = list(cache.values())
                s, v, m = compute_rankings(deals)
            else:
                s, v, m = [], [], []
            result = {'s_level': s, 'views': v, 'mixed': m, 'total': len(cache) if isinstance(cache, dict) else 0}
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8'))
        elif self.path == '/api/scan':
            deals_data = scan_thread_func()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(deals_data, ensure_ascii=False).encode('utf-8'))
        elif self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            cache = load_json(CACHE_FILE)
            total = len(cache) if isinstance(cache, dict) else 0
            self.wfile.write(json.dumps({'status': 'ok', 'total_deals': total}).encode('utf-8'))
        else:
            super().do_GET()
    
    def log_message(self, format, *args):
        pass  # Suppress log output

def scan_thread_func():
    seen = load_json(SEEN_FILE)
    if isinstance(seen, list): seen_ids = {d.get('id','') for d in seen}
    else: seen_ids = set(); seen = []
    cache = load_json(CACHE_FILE)
    if not isinstance(cache, dict): cache = {}
    current = scrape_homepage()
    if current:
        new_deals = [d for d in current if d['id'] not in seen_ids]
        cache_empty = len(cache) == 0
        to_scrape = current if cache_empty else new_deals
        for deal in to_scrape:
            try:
                detail = get_deal_detail(deal['url'])
                detail['deal_url'] = deal['url']
                detail['id'] = deal['id']
                detail['title'] = deal.get('title','')
                cache[deal['id']] = detail
                time.sleep(0.3)
            except: pass
        for d in current:
            if d['id'] not in seen_ids:
                seen.append({'id':d['id'],'first_seen':datetime.now().isoformat()})
        save_json(SEEN_FILE, seen)
        save_json(CACHE_FILE, cache)
    all_deals = list(cache.values())
    s, v, m = compute_rankings(all_deals)
    return {'s_level': s, 'views': v, 'mixed': m, 'total': len(all_deals)}

def start_server():
    server = HTTPServer(('0.0.0.0', PORT), APIHandler)
    server.serve_forever()

# ===== KIVY APP =====
class DealMonitorApp(App):
    def build(self):
        # Start HTTP server in background
        threading.Thread(target=start_server, daemon=True).start()
        
        root = FloatLayout()
        
        # Background
        with root.canvas.before:
            Color(0.08, 0.08, 0.12, 1)
            self.bg_rect = Rectangle(pos=root.pos, size=root.size)
        root.bind(pos=self._update_bg, size=self._update_bg)
        
        # Top bar
        top = BoxLayout(orientation='horizontal', size_hint=(1, None), height=56, pos_hint={'top': 1.0})
        with top.canvas.before:
            Color(0.91, 0.27, 0.38, 1)
            self.top_rect = Rectangle(pos=top.pos, size=top.size)
        top.bind(pos=self._update_top_bg, size=self._update_top_bg)
        top.add_widget(Label(text='618 比价监测', font_name=FONT, font_size=20, color=(1,1,1,1)))
        root.add_widget(top)
        
        # Status label
        self.status = Label(
            text='正在加载...', font_name=FONT, font_size=12,
            color=(0.6,0.6,0.6,1), size_hint=(1, None), height=28,
            pos_hint={'top': 0.93}
        )
        root.add_widget(self.status)
        
        # Tab buttons row
        self.tab_btns = {}
        tab_row = BoxLayout(orientation='horizontal', spacing=0, size_hint=(1, None),
                           height=40, pos_hint={'top': 0.89})
        for name, key in [('综合', 'mixed'), ('S级', 's_level'), ('热门', 'views')]:
            btn = Button(text=name, font_name=FONT, font_size=13,
                        background_color=(0.15,0.15,0.2,1), color=(0.6,0.6,0.6,1))
            btn.bind(on_release=lambda x, k=key: self.switch_tab(k))
            self.tab_btns[key] = btn
            tab_row.add_widget(btn)
        root.add_widget(tab_row)
        
        # Content area
        self.content = BoxLayout(orientation='vertical', spacing=8, padding=[12,8],
                                size_hint=(1, 0.76), pos_hint={'top': 0.83})
        root.add_widget(self.content)
        
        self.current_tab = 'mixed'
        self.s_data = []
        self.v_data = []
        self.m_data = []
        
        # Button row
        btn_row = BoxLayout(orientation='horizontal', spacing=8, size_hint=(1, None),
                           height=48, pos_hint={'bottom': 0.06}, padding=[12,0])
        
        scan_btn = Button(text='开始扫描', font_name=FONT, font_size=14,
                         background_color=(0.91,0.27,0.38,1), color=(1,1,1,1))
        scan_btn.bind(on_release=self.do_scan)
        btn_row.add_widget(scan_btn)
        
        web_btn = Button(text='打开网页版', font_name=FONT, font_size=14,
                        background_color=(0.2,0.5,0.8,1), color=(1,1,1,1))
        web_btn.bind(on_release=self.open_web)
        btn_row.add_widget(web_btn)
        
        root.add_widget(btn_row)
        
        # Load cached data
        Clock.schedule_once(lambda dt: self._init_tabs(), 1.0)
        
        return root
    
    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size
    
    def _update_top_bg(self, instance, value):
        self.top_rect.pos = instance.pos
        self.top_rect.size = instance.size
    
    def _init_tabs(self):
        self.refresh_display()
        # Highlight first tab
        if 'mixed' in self.tab_btns:
            self.tab_btns['mixed'].background_color = (0.91, 0.27, 0.38, 1)
            self.tab_btns['mixed'].color = (1, 1, 1, 1)
    
    def refresh_display(self):
        cache = load_json(CACHE_FILE)
        if isinstance(cache, dict) and cache:
            deals = list(cache.values())
            s, v, m = compute_rankings(deals)
            self.s_data = s
            self.v_data = v
            self.m_data = m
            self.status.text = f'已加载 {len(deals)} 条爆料 | SSS:{sum(1 for d in s if d.get("rating")=="SSS")} SS:{sum(1 for d in s if d.get("rating")=="SS")} S:{sum(1 for d in s if d.get("rating")=="S")}'
            self.render_tab(self.current_tab)
        else:
            self.status.text = '暂无数据 | 点击扫描获取爆料'
            self.content.clear_widgets()
            self.content.add_widget(Label(text='暂无数据\n点击下方按钮开始扫描', font_name=FONT,
                                         font_size=16, color=(0.5,0.5,0.5,1)))
    
    def switch_tab(self, key):
        self.current_tab = key
        for k, btn in self.tab_btns.items():
            if k == key:
                btn.background_color = (0.91, 0.27, 0.38, 1)
                btn.color = (1, 1, 1, 1)
            else:
                btn.background_color = (0.15, 0.15, 0.2, 1)
                btn.color = (0.6, 0.6, 0.6, 1)
        self.render_tab(key)
    
    def render_tab(self, key):
        self.content.clear_widgets()
        data = {'mixed': self.m_data, 's_level': self.s_data, 'views': self.v_data}.get(key, [])
        titles = {'mixed': '综合排行 (评级60%+热度40%)', 's_level': 'S级排行 (SSS/SS/S/A)', 'views': '热门排行 (按浏览量)'}
        
        if not data:
            self.content.add_widget(Label(text='暂无数据', font_name=FONT, font_size=16, color=(0.5,0.5,0.5,1)))
            return
        
        scroll = ScrollView(size_hint=(1, 1))
        items = BoxLayout(orientation='vertical', spacing=4, size_hint_y=None)
        items.bind(minimum_height=items.setter('height'))
        
        for i, d in enumerate(data[:30]):
            card = BoxLayout(orientation='horizontal', size_hint_y=None, height=70,
                           padding=[8,6], spacing=6)
            with card.canvas.before:
                Color(0.13, 0.13, 0.18, 1)
                card_rect = Rectangle(pos=card.pos, size=card.size)
            card.bind(pos=lambda w,v,r=card_rect: setattr(r, 'pos', w.pos),
                     size=lambda w,v,r=card_rect: setattr(r, 'size', w.size))
            
            rating = d.get('rating','?')
            title = d.get('product', d.get('title','?'))[:30]
            price = d.get('price')
            store = d.get('store','?')
            views = d.get('views',0)
            score = d.get('score', 0)
            
            rcolors = {'SSS':(1,0.2,0.2,1),'SS':(1,0.5,0.1,1),'S':(1,0.7,0.1,1),'A':(0.2,0.7,0.3,1)}
            rc = rcolors.get(rating, (0.5,0.5,0.5,1))
            badge = Label(text=rating, font_name=FONT, font_size=11, color=rc,
                        size_hint_x=None, width=36, halign='center')
            card.add_widget(badge)
            
            info = BoxLayout(orientation='vertical')
            info.add_widget(Label(text=title, font_name=FONT, font_size=13, halign='left',
                                 color=(0.9,0.9,0.9,1), shorten=True))
            sub = f'{store} | {views}浏览'
            if score > 0:
                sub += f' | {score}分'
            info.add_widget(Label(text=sub, font_name=FONT, font_size=10, color=(0.5,0.5,0.5,1)))
            card.add_widget(info)
            
            if price is not None:
                price_text = f'{price:.0f}' if price >= 1 else f'{price:.2f}'
                card.add_widget(Label(text=price_text, font_name=FONT, font_size=16,
                                     color=(1,0.3,0.25,1), size_hint_x=None, width=70))
            
            items.add_widget(card)
        
        if len(data) > 30:
            items.add_widget(Label(text=f'... 还有 {len(data)-30} 条', font_name=FONT,
                                  font_size=11, color=(0.4,0.4,0.4,1),
                                  size_hint_y=None, height=24))
        
        scroll.add_widget(items)
        self.content.add_widget(scroll)
    
    def do_scan(self, instance):
        self.status.text = '正在扫描慢慢买...'
        instance.disabled = True
        
        def scan_and_refresh():
            scan_thread_func()
            Clock.schedule_once(lambda dt: self._scan_done(instance))
        
        threading.Thread(target=scan_and_refresh, daemon=True).start()
    
    def _scan_done(self, btn):
        btn.disabled = False
        cache = load_json(CACHE_FILE)
        total = len(cache) if isinstance(cache, dict) else 0
        self.status.text = f'扫描完成! 共 {total} 条爆料'
        self.refresh_display()
    
    def open_web(self, instance):
        webbrowser.open(f'http://localhost:{PORT}/index.html')

if __name__ == '__main__':
    DealMonitorApp().run()
