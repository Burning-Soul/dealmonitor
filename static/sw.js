
// Service Worker for 618 Deal Monitor PWA
// Acts as HTTP proxy to bypass CORS, scrapes manmanbuy.com
const CACHE_NAME = 'dealmonitor-v2';
const DATA_DB = 'dealmonitor-db';
const DB_VERSION = 1;

// ============ SCRAPER ============
function decodeGBK(buffer) {
  try { return new TextDecoder('gbk').decode(buffer); }
  catch { return new TextDecoder('utf-8').decode(buffer); }
}

function parseCount(text) {
  text = text.trim();
  if (text.includes('万')) {
    try { return Math.round(parseFloat(text.replace('万','').replace('+','')) * 10000); }
    catch { return 0; }
  }
  try { return parseInt(text.replace('+','').replace(',','')); }
  catch { return 0; }
}

async function fetchWithRetry(url, cookieStr, isGbk) {
  let resp = await fetch(url, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      'Accept': 'text/html,application/xhtml+xml,*/*',
      'Accept-Language': 'zh-CN,zh;q=0.9',
      'Cookie': cookieStr || ''
    }
  });
  let buf = await resp.arrayBuffer();
  return isGbk ? decodeGBK(buf) : new TextDecoder('utf-8').decode(buf);
}

async function scrapeHomepage(cookieStr) {
  let html = await fetchWithRetry('http://www.manmanbuy.com/', cookieStr, true);
  let re = /href="(https?:\/\/cu\.manmanbuy\.com\/discuxiao_(\d+)\.aspx)"[^>]*?title="([^"]+)"/g;
  let deals = [], seen = new Set();
  let m;
  while ((m = re.exec(html)) !== null) {
    if (!seen.has(m[2])) {
      seen.add(m[2]);
      deals.push({ id: m[2], url: m[1], title: m[3].trim().substring(0, 100) });
    }
  }
  return deals;
}

async function scrapeDealDetail(url, cookieStr) {
  let html = await fetchWithRetry(url, cookieStr, true);
  let result = { deal_url: url };

  // Price extraction
  let price = null;
  // Orange font
  let om = html.match(/color\s*:\s*#[fF]{2}[4-9a-fA-F]\w{3}[^>]*>\s*(\d+\.?\d+)\s*元?\s*</i);
  if (om) price = parseFloat(om[1]);

  // Meta description
  if (!price) {
    let mm = html.match(/<meta\s+name="description"[^>]*?content="[^"]*?(\d+\.?\d+)\s*元/i);
    if (mm) price = parseFloat(mm[1]);
  }

  // 当前价格
  if (!price) {
    let cm = html.match(/当前价格\s*(\d+\.?\d+)\s*元/);
    if (cm) price = parseFloat(cm[1]);
  }

  // Product URL (HistoryLowest)
  let productUrl = null;
  let hlm = html.match(/HistoryLowest\.aspx\?[^"']*?url=([^"'&\s]+)/i);
  if (hlm) productUrl = decodeURIComponent(hlm[1]);

  // Rating from tags
  let rating = '普通';
  let tagMatch = html.match(/标签[：:].*?<\/span>(.*?)(?:<\/div>|$)/i);
  if (tagMatch) {
    let tags = tagMatch[1].replace(/<[^>]+>/g, ' ').split(/\s+/).filter(t => t.length > 1);
    for (let tag of tags) {
      if (tag.includes('历史新低')) { rating = 'SSS'; break; }
      else if (tag.includes('天新低')) {
        let d = parseInt(tag) || 0;
        if (d >= 300) { rating = 'SS'; break; }
        else if (d >= 100) { rating = 'S'; break; }
      }
      else if (tag.includes('天次低')) {
        let d = parseInt(tag) || 0;
        if (d >= 300) { rating = 'S'; break; }
      }
      else if (tag.includes('历史最低')) { rating = 'SS'; break; }
    }
  }

  // Title
  let tm = html.match(/<title>\s*(.*?)\s*[_-].*?<\/title>/i);
  let product = tm ? tm[1].trim() : '?';

  // Comments
  let cmm = html.match(/评论\s*(\d+)\s*次/);
  let comments = cmm ? parseInt(cmm[1]) : 0;

  // Store
  let sm = html.match(/商城[：:][^<]*?<a[^>]*>(.*?)<\/a>/i);
  let store = sm ? sm[1] : '?';

  // Views
  let vm = html.match(/浏览\s*(\d[\d,]*)\s*次/);
  let views = vm ? parseInt(vm[1].replace(/,/g,'')) : 0;

  return { ...result, product, price, rating, comments, store, views, product_url: productUrl, tags: [] };
}

async function runFullScan() {
  let cookieStr = "60014_vid=52B86EE84E42B46529E303FBA1568CC2A1DA0110A49344278FF62812E153574E5AB67A503DB4966DD0E85BB2BF9A856F; uid_hot=cp12954912_364416763_2026/6/13; 60014_mmmuser=BghUBgAGAAg5CwUFWQAGUAQDBwkADwVWAAkFCgdSVwUFVFJVBwtQA1Q%3d; mmbuser_ext=CJSWXDP287";
  
  // Step 1: Homepage
  let deals = await scrapeHomepage(cookieStr);
  
  // Step 2: Detail pages (limit to avoid rate limiting)
  let scanned = [];
  for (let i = 0; i < Math.min(deals.length, 60); i++) {
    try {
      let detail = await scrapeDealDetail(deals[i].url, cookieStr);
      detail.id = deals[i].id;
      scanned.push(detail);
      // Small delay
      await new Promise(r => setTimeout(r, 300));
    } catch(e) {
      console.log('Detail fail:', deals[i].id, e.message);
    }
  }
  
  // Step 3: Compute rankings
  let sDeals = scanned.filter(d => ['SSS','SS','S','A'].includes(d.rating))
    .sort((a,b) => {
      let ra = {SSS:0,SS:1,S:2,A:3}[a.rating]||9;
      let rb = {SSS:0,SS:1,S:2,A:3}[b.rating]||9;
      return ra - rb || (b.views||0) - (a.views||0);
    });
  
  let viewDeals = [...scanned].sort((a,b) => (b.views||0) - (a.views||0));
  
  let mixedDeals = [...scanned].sort((a,b) => {
    let sa = ({SSS:60,SS:42,S:24,A:12}[a.rating]||0) + Math.min((a.views||0)/125, 40);
    let sb = ({SSS:60,SS:42,S:24,A:12}[b.rating]||0) + Math.min((b.views||0)/125, 40);
    return sb - sa;
  });
  
  return {
    scan_time: new Date().toISOString(),
    total: scanned.length,
    s_level: sDeals.slice(0, 8),
    views: viewDeals.slice(0, 8),
    mixed: mixedDeals.slice(0, 10)
  };
}

// ============ CACHE & MESSAGING ============
self.addEventListener('install', e => {
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(self.clients.claim());
});

self.addEventListener('message', async e => {
  if (e.data === 'scan') {
    let client = e.source;
    try {
      client.postMessage({ type: 'scan_start' });
      let result = await runFullScan();
      client.postMessage({ type: 'scan_complete', data: result });
    } catch(err) {
      client.postMessage({ type: 'scan_error', error: err.message });
    }
  }
});

// Cache static assets
self.addEventListener('fetch', e => {
  if (e.request.url.includes('/dealmonitor/') && !e.request.url.includes('manmanbuy')) {
    e.respondWith(
      caches.match(e.request).then(r => r || fetch(e.request).then(resp => {
        if (resp.ok) {
          let clone = resp.clone();
          caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
        }
        return resp;
      }))
    );
  }
});
