import base64
import sys
import time
import json
import requests
import re
from datetime import datetime
from urllib.parse import urlparse
from requests.exceptions import RequestException, Timeout

# 添加项目根目录到系统路径
sys.path.append('..')
from base.spider import Spider
from bs4 import BeautifulSoup

# 配置常量
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36'
TARGET_URL = 'http://www.yoozb.live/'
TIMEOUT = 10  # 请求超时时间（秒）
CACHE_EXPIRE = 300  # 缓存过期时间（秒）
OUTPUT_FILE = 'yoozb.m3u'  # 输出文件名


class LitvSpider(Spider):
    """Litv直播爬虫，用于获取直播信息并生成M3U播放列表"""
    
    def __init__(self):
        super().__init__()
        self.extend = None
        self.extendDict = {}
        self.is_proxy = False
        self.proxy = None
        self.cache = {}  # 用于缓存数据
        self.cache_time = {}  # 缓存时间
    
    def getName(self):
        return "Litv"

    def init(self, extend):
        """初始化爬虫配置"""
        self.extend = extend
        try:
            self.extendDict = json.loads(extend) if extend else {}
        except json.JSONDecodeError as e:
            self.extendDict = {}
            print(f"解析配置出错: {str(e)}")

        # 处理代理配置
        self.proxy = self.extendDict.get('proxy', None)
        self.is_proxy = self.proxy is not None
        
        # 转换为requests所需的代理格式
        if self.is_proxy and not isinstance(self.proxy, dict):
            self.proxy = {
                'http': self.proxy,
                'https': self.proxy
            }

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        """检查URL是否为视频格式"""
        video_extensions = ['.m3u8', '.mp4', '.ts', '.flv', '.avi', '.mov']
        parsed_url = urlparse(url)
        return any(parsed_url.path.endswith(ext) for ext in video_extensions)

    def manualVideoCheck(self):
        """手动视频检查（预留实现）"""
        return True

    def _get_cached_data(self, key):
        """获取缓存数据"""
        if key in self.cache and (time.time() - self.cache_time.get(key, 0) < CACHE_EXPIRE):
            return self.cache[key]
        return None

    def _set_cached_data(self, key, data):
        """设置缓存数据"""
        self.cache[key] = data
        self.cache_time[key] = time.time()

    def _fetch_html_content(self, url):
        """获取网页内容，带缓存和异常处理"""
        # 尝试从缓存获取
        cached = self._get_cached_data(url)
        if cached:
            return cached
            
        # 准备请求头
        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh,zh-CN;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': USER_AGENT,
        }
        
        try:
            # 发送请求
            response = requests.get(
                url, 
                headers=headers, 
                verify=False,
                timeout=TIMEOUT,
                proxies=self.proxy if self.is_proxy else None
            )
            response.raise_for_status()  # 检查HTTP错误状态码
            
            # 尝试不同编码解码
            encodings = ['utf-8-sig', 'gbk', 'utf-8', 'iso-8859-1']
            html_content = None
            
            for encoding in encodings:
                try:
                    html_content = response.content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
                    
            if not html_content:
                html_content = response.text  # 最后尝试默认解码
                
            # 缓存结果
            self._set_cached_data(url, html_content)
            return html_content
            
        except (RequestException, Timeout) as e:
            print(f"获取网页内容失败: {str(e)}")
            return None

    def liveContent(self, url=None):
        """获取直播内容并生成M3U播放列表（无分组）"""
        m3u_header = ['#EXTM3U', '#EXT-X-VERSION:3']
        url = url or TARGET_URL
        
        # 获取网页内容
        html_content = self._fetch_html_content(url)
        if not html_content:
            return '\n'.join(m3u_header)

        # 解析网页
        soup = BeautifulSoup(html_content, 'html.parser')
        data_div = soup.find('div', class_='data')
        
        if not data_div:
            print("未找到数据容器")
            return '\n'.join(m3u_header)
            
        rows = data_div.find_all('tr')
        if not rows:
            print("未找到数据行")
            return '\n'.join(m3u_header)

        # 初始化变量
        current_date = ""
        all_matches = []  # 不分组，所有比赛放在一个列表中

        for row in rows:
            # 处理日期行
            if 'class' in row.attrs and 'date' in row['class']:
                date_text = row.td.get_text(strip=True).split('&nbsp')[0]
                try:
                    dt = datetime.strptime(date_text, "%Y年%m月%d日")
                    current_date = dt.strftime("%m-%d")  # 格式化为 月-日
                except ValueError:
                    current_date = ""
                continue
            
            # 跳过表头
            if 'class' in row.attrs and 'head' in row['class']:
                continue
            
            # 处理比赛行
            if row.find('td', class_='matcha'):
                try:
                    tds = row.find_all('td')
                    if len(tds) < 8:  # 确保有足够的列
                        continue
                    
                    # 提取基础信息
                    category = tds[1].get_text(strip=True)
                    time_str = tds[2].get_text(strip=True)
                    full_time = f"{current_date} {time_str}" if current_date and time_str else time_str
                    status = tds[3].get_text(strip=True) or "预告"
                    home_team = tds[4].get_text(strip=True)
                    away_team = tds[6].get_text(strip=True)
                    
                    # 提取直播链接
                    live_links = []
                    for a in tds[7].find_all('a'):
                        if a.has_attr('href'):
                            link = a['href'].strip().replace("\n", "").replace(" ", "")
                            if link:
                                live_links.append(link)
                    
                    # 状态标准化
                    if "直播" in status:
                        status_key = "直播"
                    elif "结束" in status:
                        status_key = "结束"
                    else:
                        status_key = "预告"
                    
                    # 添加到总列表（不分组）
                    all_matches.append({
                        "时间": full_time,
                        "分类": category,
                        "主队": home_team,
                        "客队": away_team,
                        "直播链接": live_links,
                        "状态": status_key
                    })
                except (IndexError, AttributeError) as e:
                    print(f"解析比赛信息出错: {str(e)}")
                    continue

        # 生成M3U内容（无分组）
        m3u_content = m3u_header.copy()
        
        for i, match in enumerate(all_matches, 1):
            ch_name = f"[{match['时间']}] {match['分类']}-{match['主队']}vs{match['客队']}"
            
            # 处理直播和已结束的比赛
            if match['状态'] in ["直播", "结束"]:
                links = match['直播链接'][:3]  # 最多取3个链接
                for k, link in enumerate(links, 1):
                    if self.isVideoFormat(link):
                        ch_url = link
                    else:
                        ch_url = f"video://{link}"
                        
                    # 移除group-title属性，取消分组
                    extinf = f'#EXTINF:-1 tvg-name="{ch_name}{k}",{ch_name}{k}'
                    m3u_content.extend([extinf, ch_url])
            
            # 处理预告的比赛
            elif match['状态'] == "预告":
                ch_url = "https://gh-proxy.com/raw.githubusercontent.com/cqshushu/tvjk/master/yootv.mp4"
                # 移除group-title属性，取消分组
                extinf = f'#EXTINF:-1 tvg-name="{ch_name}",{ch_name}'
                m3u_content.extend([extinf, ch_url])

        return '\n'.join(m3u_content)

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
        """本地代理处理"""
        if params['type'] == "m3u8":
            return self.proxyM3u8(params)
        if params['type'] == "ts":
            return self.get_ts(params)
        
        # 默认返回一个示例视频
        return [
            302, 
            "text/plain", 
            None, 
            {'Location': 'https://sf1-cdn-tos.huoshanstatic.com/obj/media-fe/xgplayer_doc_video/mp4/xgplayer-demo-720p.mp4'}
        ]

    def proxyM3u8(self, params):
        """处理M3U8代理"""
        try:
            pid = params['pid']
            info = pid.split(',')
            if len(info) < 3:
                raise ValueError("无效的PID格式")
                
            a, b, c = info[0], info[1], info[2]
            timestamp = int(time.time() / 4 - 355017625)
            t = timestamp * 4
            
            m3u8_text = [
                '#EXTM3U',
                '#EXT-X-VERSION:3',
                '#EXT-X-TARGETDURATION:4',
                f'#EXT-X-MEDIA-SEQUENCE:{timestamp}'
            ]
            
            for i in range(10):
                url = f'https://ntd-tgc.cdn.hinet.net/live/pool/{a}/litv-pc/{a}-avc1_6000000={b}-mp4a_134000_zho={c}-begin={t}0000000-dur=40000000-seq={timestamp}.ts'
                
                if self.is_proxy:
                    url = f'http://127.0.0.1:9978/proxy?do=py&type=ts&url={self.b64encode(url)}'

                m3u8_text.append(f'#EXTINF:4,')
                m3u8_text.append(url)
                timestamp += 1
                t += 4
                
            return [200, "application/vnd.apple.mpegurl", '\n'.join(m3u8_text)]
            
        except Exception as e:
            print(f"M3U8代理处理出错: {str(e)}")
            return [500, "text/plain", f"处理出错: {str(e)}"]

    def get_ts(self, params):
        """获取TS文件"""
        try:
            url = self.b64decode(params['url'])
            headers = {'User-Agent': USER_AGENT}
            
            response = requests.get(
                url, 
                headers=headers, 
                stream=True, 
                timeout=TIMEOUT,
                proxies=self.proxy if self.is_proxy else None
            )
            response.raise_for_status()
            
            return [206, "application/octet-stream", response.content]
            
        except Exception as e:
            print(f"获取TS文件出错: {str(e)}")
            return [500, "text/plain", f"获取TS文件出错: {str(e)}"]

    def destroy(self):
        return '爬虫已销毁'

    def b64encode(self, data):
        """Base64编码"""
        return base64.b64encode(data.encode('utf-8')).decode('utf-8')

    def b64decode(self, data):
        """Base64解码"""
        try:
            return base64.b64decode(data.encode('utf-8')).decode('utf-8')
        except Exception as e:
            print(f"Base64解码出错: {str(e)}")
            return ""


if __name__ == '__main__':
    # 测试代码
    spider = LitvSpider()
    spider.init('{"proxy": null}')
    
    # 生成M3U文件
    m3u_content = spider.liveContent()
    
    # 保存到文件（使用指定的文件名）
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
        
    print(f"M3U文件已生成: {OUTPUT_FILE}")
