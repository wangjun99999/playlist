# -*- coding: utf-8 -*-
# @Author  : Doubebly
# @Time    : 2025/5/19 21:19

import sys
import requests
import base64
import os
import time
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "BeeSport"

    def init(self, extend):
        self.ext_time = 120
        self.cache_path = '/storage/emulated/0/TV/cache_BeeSport'
        if not os.path.exists(self.cache_path):
            os.mkdir(self.cache_path, 0o755)
        pass

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass


    def liveContent(self, url):
    data_list = [{'tvg-id': '', 'tvg-name': '', 'tvg-logo': '...', 'pid': 'TNT_Sports_1', ...}, ...]
    tv_list = ['#EXTM3U']
    
    for i in data_list:
        pid = i['pid']
        # 直接调用fun_beesport获取真实直播流地址（跳过proxy）
        real_url = self.fun_beesport_direct(pid)  # 新增方法，直接返回真实地址
        # 拼接完整的M3U条目
        tv_list.append(f'#EXTINF:-1 tvg-id="{i["tvg-id"]}" tvg-logo="{i["tvg-logo"]}" group-title="BeeSport",{i["name"]}')
        tv_list.append(real_url)  # 直接使用真实地址
    
    return '\n'.join(tv_list)

# 新增：直接获取真实直播流地址的方法
def fun_beesport_direct(self, pid):
    cache_play_url = self.cache_get(pid)
    if cache_play_url != 'False':
        return cache_play_url
    
    # 原fun_beesport中的授权逻辑（复制过来，直接返回地址而非重定向）
    headers = {'User-Agent': '...', 'origin': 'https://beesport.net', ...}
    json_data = {'channel': f'https://live_tv.starcdnup.com/{pid}/index.m3u8'}
    try:
        response = requests.post('https://beesport.net/authorize-channel', headers=headers, json=json_data)
        real_url = response.json()['channels'][0]
        self.cache_set(pid, real_url)
        return real_url
    except:
        # 异常时返回默认测试地址
        return 'https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/xgplayer_doc_video/mp4/xgplayer-demo-720p.mp4'

    def homeContent(self, filter):
        return {}

    def homeVideoContent(self):
        return {}

    def categoryContent(self, cid, page, filter, ext):
        return {}

    def detailContent(self, did):
        return {}

    def searchContent(self, key, quick, page='1'):
        return {}

    def searchContentPage(self, keywords, quick, page):
        return {}

    def playerContent(self, flag, pid, vipFlags):
        return {}

    def localProxy(self, params):
        _fun = params.get('fun', None)
        _type = params.get('type', None)
        if _fun is not None:
            fun = getattr(self, f'fun_{_fun}')
            return fun(params)
        return [302, "text/plain", None, {'Location': 'https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/xgplayer_doc_video/mp4/xgplayer-demo-720p.mp4'}]


    def fun_beesport(self, params):
        pid = params['pid']
        cache_play_url = self.cache_get(pid)
        if cache_play_url != 'False':
            return [302, "text/plain", None, {'Location': cache_play_url}]
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Content-Type': 'application/json',
            'accept-language': 'zh-CN,zh;q=0.9',
            'cache-control': 'no-cache',
            'origin': 'https://beesport.net',
            'referer': 'https://beesport.net/live-tv',
        }

        json_data = {
            'channel': f'https://live_tv.starcdnup.com/{pid}/index.m3u8',
        }
        try:
            response = requests.post('https://beesport.net/authorize-channel', headers=headers, json=json_data)
            url = response.json()['channels'][0]
            self.cache_set(pid, url)
            return [302, "text/plain", None, {'Location': url}]
        except Exception as e:
            return [302, "text/plain", None, {'Location': 'https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/xgplayer_doc_video/mp4/xgplayer-demo-720p.mp4'}]

    def destroy(self):
        files_and_dirs = os.listdir(self.cache_path)
        if len(files_and_dirs) > 0:
            for file in files_and_dirs:
                os.remove(os.path.join(self.cache_path, file))
        return '正在Destroy'

    def b64encode(self, data):
        return base64.b64encode(data.encode('utf-8')).decode('utf-8')

    def b64decode(self, data):
        return base64.b64decode(data.encode('utf-8')).decode('utf-8')


    def cache_get(self, key):
        t = time.time()
        path = self.cache_getkey(key)
        if not os.path.exists(path):
            return 'False'
        if t - os.path.getmtime(path) > self.ext_time:
            return 'False'
        with open(path, 'r', encoding='utf-8') as f:
            data = f.read()
        return data

    def cache_set(self, key, data):
        path = self.cache_getkey(key)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(data)
        return True

    def cache_getkey(self, key):
        return self.cache_path + '/' + key + '.txt'

if __name__ == '__main__':
    spider = Spider()
    m3u_content = spider.liveContent("")
    with open('beesport.m3u', 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    print("M3U文件生成成功：beesport.m3u")
