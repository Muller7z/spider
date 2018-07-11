
"""
网站：http://www.mmjpg.com/
反爬措施，检测header中的referer字段是否是本站地址，否则会返回防盗链的图片
作者：Muller
"""

from lxml import html
import requests
import os
from multiprocessing import Pool
from queue import Queue

# 使用requests库中的Session方法，保持会话
s = requests.Session()
# 全局headers
headers = {
    'Connection': 'keep-alive',
    'Cache-Control': 'max-age=0',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
    'Referer': 'http://www.mmjpg.com/',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}
"""图片网站的通用型爬虫
step0：创建一个目录mmjpg然后切换到此目录，所有文件都会保存至此目录
step1：访问一个主页面，找到这个主页下有多少分页
step2：访问每一个分页，找到分页下各有多少个图集，这里是1~6*3=18个图集
step3：将图集的url添加到一个队列，然后创建5个进程来handle每一个url
    every_process：1.进入图集，找到每个图集的图片数量和一个标题，然后构建一个文件目录
                   2.切换到这个目录，根据图片的数量，构建一个url列表
                   3.访问每一个url，找到图片的下载地址和标题，标题用来构建文件名
                   4.访问下载地址得到图片，保存图片
                   5.切换回上一级目录
step4：切换回上一级目录
"""


def get_subpage(main_url):
    """
    找到主页面下各分页的地址
    :param main_url:
    :return: list,sub_page_url
    """
    response = s.get(main_url, headers=headers)
    # 使用lxml库中的html模块处理html数据
    elm = html.fromstring(response.content)
    # 用xpath定位到想要的数据，注意返回的是一个列表
    sub_page_href = elm.xpath('//div[@class="pic"]//li/a/@href')
    return sub_page_href


def get_img_number(page_url):
    """
    找到此分页下共有多少图片
    :param page_url:
    :return: tuple,pic_number&title
    """
    r = s.get(page_url,headers=headers)
    elm = html.fromstring(r.content)
    pic_number = elm.xpath('//div[@class="page"]/a[7]/text()')[0]
    # title 用来建立一个目录，存放这一套图片
    title = elm.xpath('//div[@class="content"]//img/@alt')[0]
    return int(pic_number),title


def get_page_number(main_page_url):
    """
    找到此目录下有多少页
    :param main_page_url:
    :return: list:all_page_url
    """
    r = s.get(main_page_url,headers=headers)
    elm = html.fromstring(r.content)
    last_page_url =elm.xpath('//a[@class="last"]/@href')[0][-3:]
    i = last_page_url.index("/")
    number = int(last_page_url[i + 1:])
    # print(number)
    return [main_page_url+"/%s"%(str(i+1)) for i in range(number)]


def get_img_src(page_url):
    """
    找到图片的地址和图片标题
    :param page_url:
    :return: tuple,img_src&img_title
    """
    r = s.get(page_url,headers=headers)
    elm = html.fromstring(r.content)
    img_src = elm.xpath('//div[@class="content"]//img/@src')[0]
    # 这个title用来构建图片文件名
    title = elm.xpath('//div[@class="content"]//img/@alt')[0]
    return img_src,title


def img_downloader(url,filename):
    """
    图片下载器
    :param url:img_src
    :param filename: img_filename
    """
    img = s.get(url,headers=headers).content
    print("--------------------------------------------")
    print("正在下载图片：%s"%filename)

    with open(filename,"wb")as f:
        f.write(img)


def handle_sub_page(sub_page_url):
    """
    处理分页
    :param sub_page_url:
    """
    re = get_img_number(sub_page_url)
    page_number = re[0]
    title = re[1]
    try:
        os.mkdir(title)
        os.chdir("./%s" % title)
    except OSError as e:
        os.chdir("./%s" % title)

    for i in range(page_number):
        page_url = sub_page_url + "/" + str(i + 1)
        print(page_url)

        r = get_img_src(page_url)
        img_src = r[0]
        filename = r[1] + ".jpg"
        img_downloader(img_src, filename)

    os.chdir("..")


def multiprocess_handle(urllist):
    """
    处理多进程，维护一个队列
    :param urllist:
    """
    # 创建一个queue对象
    q = Queue()
    # 将url添加到队列
    [q.put(each) for each in urllist]

    print("主进程开始执行>>> pid={}".format(os.getpid()))
    # 创建5个进程,太高的并发会给对方造成较大压力，容易被ban
    ps = Pool(5)
    for i in range(len(urllist)):
        # 判断队列是否为空
        if not q.empty():
            ps.apply_async(handle_sub_page, args=(q.get(),))  # 异步执行

    # 关闭进程池，停止接受其它进程
    ps.close()
    # 阻塞进程，这将会等待每一个分页下的图集都下载完毕才会进入下一个分页
    ps.join()
    print("主进程终止")


if __name__ == '__main__':

    try:
        os.mkdir("mmpic")
        os.chdir("./mmpic")
    except OSError as e:
        os.chdir("./mmpic")

    main_page = "http://www.mmjpg.com/tag/myg"
    all_page_url = get_page_number(main_page)

    for page in all_page_url:
        sub_page_list = get_subpage(page)
        multiprocess_handle(sub_page_list)

    os.chdir("..")
