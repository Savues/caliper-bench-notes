#!/usr/bin/env python3
"""抓取 Caliper Bench 当前快照到 archive/<generated>.html。

页面会把数据内嵌在 HTML 里，所以整页保存即可，约 3.4 MB/期。

两个实测坑：
  - 站点会拒绝 urllib 默认的 `Python-urllib` UA（403），必须伪装浏览器
  - 分块传输到 3.3 MB 附近可能抛 IncompleteRead，需要保留已读部分并重试
"""
import http.client
import os
import re
import ssl
import time
import urllib.request

URL = 'https://caliperbench.com/'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/131.0 Safari/537.36'),
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.9',
}
RETRIES = 4


def _once(url, insecure=False):
    req = urllib.request.Request(url, headers=HEADERS)
    ctx = ssl._create_unverified_context() if insecure else ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=180, context=ctx) as r:
        try:
            return r.read()
        except http.client.IncompleteRead as e:
            # 已读到的部分仍然可用，交给上层校验
            return e.partial


def fetch(url=URL, retries=RETRIES):
    """返回完整 HTML。校验必须包含 `const DATA = `，否则重试。"""
    insecure = False
    last = b''
    for attempt in range(retries):
        try:
            body = _once(url, insecure)
        except ssl.SSLError:
            insecure = True
            continue
        except Exception as exc:  # 网络抖动
            print(f'  第 {attempt + 1} 次失败：{exc}')
            time.sleep(3 * (attempt + 1))
            continue
        last = body
        if b'const DATA = ' in body:
            return body
        print(f'  第 {attempt + 1} 次取到不完整页面（{len(body) / 1e6:.1f} MB），重试')
        time.sleep(3 * (attempt + 1))
    if last:
        print(f'  警告：返回最后一次不完整结果（{len(last) / 1e6:.1f} MB）')
    return last


def main():
    html = fetch()
    if b'const DATA = ' not in html:
        raise SystemExit('抓取失败：页面不完整，未写入')
    text = html.decode('utf-8', 'ignore')
    m = re.search(r'generated (\d{4}-\d\d-\d\d \d\d:\d\d) UTC', text)
    stamp = (m.group(1) if m else 'unknown').replace(' ', '_').replace(':', '')
    d = os.path.join(ROOT, 'archive')
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, stamp + '.html')
    if os.path.exists(path) and open(path, 'rb').read() == html:
        print('未变化：' + path)
        return
    with open(path, 'wb') as f:
        f.write(html)
    print(f'已保存 {path}  ({len(html) / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
