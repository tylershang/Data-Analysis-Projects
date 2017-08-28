from lxml import html
from bs4 import BeautifulSoup
import re
import urllib, urllib2, cookielib
import zlib
import time
from datetime import datetime as DT
from Queue import Queue
from threading import Thread

FAKE_HEADERS = [('Host', 'www.google.com'),
                ('Connection', 'keep-alive'),
                ('Cache-Control', 'max-age=0'),
                ('Cookie', 'csm-hit=s-A6S3DNYPX262YVEAB4Y9|1503639555648; x-wl-uid=1eowKmZ/Q/taPRzB1Zzz3IRrOG95Gkx1d0coMX4J4MWIeYTrtf11WJG0DE2cDeBC6EbGnzyY7YUQ=; session-token=6vtaHQYIgc4wUiAQTeDcQGEzWX7obdu10rBy8FvTZcL2CrImToCmjPsw6wWRpn0Ip4HZx9FO2IoZNibALmLWSPrkSJlWYtsDypBU5WOnbTAxIEXqcMuRuY8HUGlcX1FJcyqfxT1nUajpKFBOlROLhHWl6xO4X9UYnEM1GvTUz7wQSq+a2HuWVowy4W+CHmNHwWxKa0LMPDEh9fN/D4tZUQCDzSoMkdlbTJQaYtoKYmP4aoLJHDdmaiTJWtqy9wB3; ubid-main=135-5664481-3259942; session-id-time=2082787201l; session-id=141-9519987-8554269'),
                ('Accept','text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'),
                ('Upgrade-Insecure-Requests', '1'),
                ('User-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36'),
                ('Referer', 'https://www.bilibili.com/'),
                ('Accept-Encoding','gzip, deflate, sdch'),
                ('Accept-Language','en-US,en;q=0.8')]

TIME_OUT = 10

def _tstamp():
    """
    formatted time stamp
    """
    ts = time.time()
    return '[{:s}]'.format(DT.fromtimestamp(ts).strftime('%m-%d %H:%M:%S'))

class ProxyList(object):
    def __init__(self,fproxy):
        self._list = []
        with open(fproxy) as fp:
            for line in fp:
                proxy = line.strip()
                if len(proxy) == 0:
                    break
                self._list.append(proxy)
        self._pt = 0
        self._len = len(self._list)

    def get_proxy(self):
        proxy = self._list[self._pt]
        self._pt = (self._pt+1)%self._len
        return proxy

    def get_proxy_at(self, pt):
        self._pt = (pt+1)%self._len
        return self._list[pt%self._len]

    def reset_pt(self):
        self._pt = 0

class Scraper(object):
    def __init__(self, keywords, proxy_list, debug=False, max_thread=8, max_items=0):
        self.keywords = keywords
        self.proxy_list = proxy_list
        self.debug = debug
        self.queue = Queue(maxsize=max_items)
        self.product_list = []
        self.max_thread = max_thread

    def get_page_url(self, key_words, page_num):
        search_key_words = 'https://www.amazon.com/s?url=search-alias%3Daps&field-keywords='
        return search_key_words + key_words + '&page=' + str(page_num)


    def product_parser(self, url, proxy_str):
        # read a url page
        #page = requests.get(url)
        #tree = html.fromstring(page.content)
        cookie_file = cookielib.MozillaCookieJar('cookies/'+'cookie')
        cookie = urllib2.HTTPCookieProcessor(cookie_file)
        proxy = urllib2.ProxyHandler({'http': proxy_str})
        opener = urllib2.build_opener(proxy,cookie)
        #opener = urllib2.build_opener(proxy)
        opener.addheaders = FAKE_HEADERS
        try:
            response = opener.open(url, timeout=TIME_OUT)
            cookie_file.save(ignore_discard=True, ignore_expires=True)
        except urllib2.HTTPError, e:
            print('[HTTPError]'+url+' '+proxy_str)
            print('[HTTPError]'+str(e.code)+' '+str(e.reason))
            return -1
        data=zlib.decompress(response.read(), 16+zlib.MAX_WBITS)
        tree = html.fromstring(data)

        name = tree.xpath('//h1[@id="title"]//text()')
        sale_price = tree.xpath('//span[contains(@id,"ourprice") or contains(@id,"saleprice")]/text()')
        original_price = tree.xpath('//td[contains(text(),"List Price") or contains(text(),"M.R.P") or contains(text(),"Price")]/following-sibling::td/text()')
        category = tree.xpath('//a[@class="a-link-normal a-color-tertiary"]//text()')
        availability = tree.xpath('//div[@id="availability"]//text()')

        name = ' '.join(''.join(name).split()) if name else None
        sale_price = float(''.join(sale_price).split()[0][1:]) if sale_price else None
        category = ' > '.join([i.strip() for i in category]) if category else None
        # original_price = float(''.join(sale_price).split()[0][1:]) if original_price else None
        availability = ''.join(availability).strip().split('\n')[0] if availability else None

        if not original_price:
            original_price = sale_price

        info = {
            'Name':name,
            'Sale price':sale_price,
            'Category':category,
            # 'Original price':original_price,
            'Availability':availability,
            #'URL':url,
        }
        return info

    def get_product_asin(self, page_url, proxy_str):
        asin = []
        #soup = BeautifulSoup(requests.get(page_url).content,"lxml")
        cookie_file = cookielib.MozillaCookieJar('cookies/'+'cookie')
        cookie = urllib2.HTTPCookieProcessor(cookie_file)
        proxy = urllib2.ProxyHandler({'http': proxy_str})
        opener = urllib2.build_opener(proxy,cookie)
        #opener = urllib2.build_opener(proxy)
        opener.addheaders = FAKE_HEADERS
        try:
            response = opener.open(page_url, timeout=TIME_OUT)
            cookie_file.save(ignore_discard=True, ignore_expires=True)
        except urllib2.HTTPError, e:
            print('[HTTPError]'+url+' '+proxy_str)
            print('[HTTPError]'+str(e.code)+' '+str(e.reason))
            return -1
        data=zlib.decompress(response.read(), 16+zlib.MAX_WBITS)
        soup = BeautifulSoup(data,"lxml")
        for p in soup.findAll('li',{'data-asin': re.compile('.{8}') }):
            asin.append(p['data-asin'])

        return asin

    def page_parser(self, page_url):
        proxy = self.proxy_list.get_proxy()
        asin = self.get_product_asin(page_url,proxy)
        if self.debug:
            print(asin)
        if len(asin) == 0:
            return False
        for i in asin:
            try:
                self.queue.put(i,block=False)
            except:
                return False
        time.sleep(2)
        return True

    def product_parser_worker(self, q, name):
        while not q.empty():
            try:
                asin = q.get(block=False)
                product_link = 'https://www.amazon.com/dp/' + asin
                proxy = self.proxy_list.get_proxy()
                if self.debug:
                    print(product_link+' '+proxy+' begins...')
                product_info = self.product_parser(product_link, proxy)
                if product_info != -1:
                    self.product_list.append(product_info)
            except:
                continue
            q.task_done()
            time.sleep(2)

    def run(self):
        num_threads = self.max_thread
        page_num = 1

        while True:
            if self.debug:
                print('Search page: '+str(page_num))
            if not self.page_parser(self.get_page_url('apple',page_num)):
                break
            page_num += 1

        print(_tstamp()+'Products\' asin count: '+str(self.queue.qsize()))
        threads = [Thread(target=self.product_parser_worker,args=(self.queue,str(i))) for i in range(num_threads)]
        for thread in threads:
            thread.setDaemon(True)
            thread.start()
        for  thread in threads:
            thread.join()
        print(_tstamp()+'Products\' info get: '+str(len(self.product_list)))


if __name__ == "__main__":
    plist = ProxyList('proxylist-2017-08-24-15-35-59.txt')
    plist.get_proxy_at(400)
    scraper = Scraper('jacket+coat', plist, debug=True, max_thread=16)
    scraper.run()
    print(scraper.product_list)

# Test Case
# page_parser('https://www.amazon.com/s?url=search-alias%3Daps&field-keywords=coat+jacket&page=1')
