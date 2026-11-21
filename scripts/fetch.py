#!/usr/bin/env python3
"""抓取 Caliper Bench 当前快照到 archive/<generated>.html。

页面会把数据内嵌在 HTML 里，所以整页保存即可，约 3.4 MB/期。
"""
import os
import re
import ssl
import urllib.request

URL = 'https://caliperbench.com/'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fetch(url):
    try:
        with urllib.request.urlopen(url, timeout=120,
                                    context=ssl.create_default_context()) as r:
            return r.read()
    except ssl.SSLError:
        # 某些容器缺少中间证书链，退回不校验（只读取公开数据）
        with urllib.request.urlopen(url, timeout=120,
                                    context=ssl._create_unverified_context()) as r:
            return r.read()


def main():
    html = fetch(URL)
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
