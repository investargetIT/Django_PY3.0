#coding=utf-8
import os

import datetime
import traceback

import xlrd
from PIL import Image, ImageDraw, ImageFont
import random

from aip import AipOcr
from elasticsearch import Elasticsearch
from reportlab.lib.pagesizes import A1
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from invest.settings import APILOG_PATH, HAYSTACK_CONNECTIONS
from reportlab.pdfbase.ttfonts import TTFont
from pdfrw import PdfReader, PdfWriter, PageMerge
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.layout import LAParams
from pdfminer.converter import PDFPageAggregator
from PyPDF2 import PdfFileWriter, PdfFileReader
# 随机颜色1:
from third.thirdconfig import baiduaip_appid, baiduaip_appkey, baiduaip_secretkey
from utils.customClass import InvestError


def rndColor():
    return (random.randint(64, 255), random.randint(64, 255), random.randint(64, 255))

# 随机颜色2:
def rndColor2():
    return (random.randint(32, 127), random.randint(32, 127), random.randint(32, 127))


def rndColor3():
    colorset = [(247, 58, 97), (87, 96, 105), (173, 195, 192), (185, 227, 217)]
    return colorset[random.randint(0,3)]

def get_file_content(filePath):
    with open(filePath, 'rb') as fp:
        return fp.read()

#默认头像生成kk
def makeAvatar(name):
    width = 100
    height = 100
    font = ImageFont.truetype(APILOG_PATH['fontPath'], size=50)
    backcolor = rndColor3()
    image = Image.new('RGB', (width, height), backcolor)
    (letterWidth, letterHeight) = font.getsize(name)
    textY0 = (width - letterHeight - 14) / 2
    textY0 = int(textY0)
    textX0 = int((height - letterWidth) / 2)
    # 创建Draw对象:
    draw = ImageDraw.Draw(image)
    draw.text((textX0, textY0), name, font=font, fill=(255,255,255))
    from third.views.qiniufile import qiniuuploadfile
    image.save(APILOG_PATH['userAvatarPath'], 'jpeg')
    success, url, key = qiniuuploadfile(APILOG_PATH['userAvatarPath'], 'image')
    if success:
        return key
    else:
        return None

#水印增加（单文件）
def addWaterMark(pdfpath, watermarkcontent=None):
    try:
        now = datetime.datetime.now()

        watermarkpath = pdfpath.split('.')[0] + '-water' + '.pdf'
        out_path = pdfpath.split('.')[0] + '-out' + '.pdf'
        watermark = create_watermark(watermarkpath, watermarkcontent)

        # Get our files ready
        input_file = PdfReader(pdfpath)
        for page in input_file.pages:
            PageMerge(page).add(watermark, prepend=False).render()
        PdfWriter(out_path, trailer=input_file).write()
        os.remove(pdfpath)
        os.rename(out_path, pdfpath)
        os.remove(watermarkpath)
        print('覆盖水印pdf--%s--源文件%s' % (now, out_path))
    except Exception:
        print('覆盖水印pdf出错--%s--源文件%s' % (now, out_path))
        filepath = APILOG_PATH['excptionlogpath'] + '/' + now.strftime('%Y-%m-%d')
        f = open(filepath, 'a')
        f.writelines(now.strftime('%H:%M:%S') + '\n' + traceback.format_exc() + '\n\n')
        f.close()
    return pdfpath


def create_watermark(waterpath, watermarkcontent):
    """创建PDF水印模板
    """
    # 使用reportlab来创建一个PDF文件来作为一个水印文件
    pdfmetrics.registerFont(TTFont('song', APILOG_PATH['pdfwaterfontPath']))
    if not isinstance(watermarkcontent, list):
        watermarkcontent = []
    while len(watermarkcontent) < 3:
        watermarkcontent.append(u'多维海拓')
    c = canvas.Canvas(waterpath, A1)
    c.rotate(45)
    fontsize = 20     # 水印字体大小
    fontAlpha = 0.05  # 水印字体透明度
    space = 80        # 水印间距
    c.setFont("song", fontsize)
    c.translate(0, -A1[1] * 0.5)
    width0 = c.stringWidth(text=watermarkcontent[0], fontName='song', fontSize=fontsize)
    width1 = c.stringWidth(text=watermarkcontent[1], fontName='song', fontSize=fontsize)
    width2 = c.stringWidth(text=watermarkcontent[2].replace('@', '[at]'), fontName='song', fontSize=fontsize)
    y = 0
    while y < A1[1]:
        x = 100
        while x < A1[0]:
            c.setFillAlpha(fontAlpha)
            c.drawString(x, y, watermarkcontent[0])
            x = x + width0 + space
            c.drawString(x, y, watermarkcontent[1])
            x = x + width1 + space
            c.drawString(x, y, watermarkcontent[2].replace('@', '[at]'))
            x = x + width2 + space
        y += 60
    c.save()
    pdf_watermark = PageMerge().add(PdfReader(waterpath).pages[0])[0]
    return pdf_watermark


#水印增加（多文件）
def addWaterMarkToPdfFiles(pdfpaths, watermarkcontent=None):
    try:
        if len(pdfpaths) == 0:
            return
        watermarkpath = pdfpaths[0].split('.')[0] + '-water' + '.pdf'
        watermark = create_watermark(watermarkpath, watermarkcontent)
    except Exception:
        now = datetime.datetime.now()
        print('制作水印pdf--%s'%now)
        filepath = APILOG_PATH['excptionlogpath'] + '/' + now.strftime('%Y-%m-%d')
        f = open(filepath, 'a')
        f.writelines(now.strftime('%H:%M:%S') + '\n' + traceback.format_exc() + '\n\n')
        f.close()
        return
    # Get our files ready
    for path in pdfpaths:
        now = datetime.datetime.now()
        try:
            print('覆盖水印pdf--%s--源文件%s' % (now, path))
            out_path = path.split('.')[0] + '-out' + '.pdf'
            input_file = PdfReader(path)
            for page in input_file.pages:
                PageMerge(page).add(watermark, prepend=False).render()
            PdfWriter(out_path, trailer=input_file).write()
            os.remove(path)
            os.rename(out_path, path)
        except Exception as err:
            print('覆盖水印pdf失败--%s--源文件%s' % (now, path))
            filepath = APILOG_PATH['excptionlogpath'] + '/' + now.strftime('%Y-%m-%d')
            f = open(filepath, 'a')
            f.writelines(now.strftime('%H:%M:%S') + '\n' + traceback.format_exc() + '\n\n')
            f.close()
    if os.path.exists(watermarkpath):
        os.remove(watermarkpath)
    return

'''
pypdf2加密
'''

def encryptPdfFilesWithPassword(filepaths, password):
    try:
        if password and len(filepaths) > 0:
            for input_filepath in filepaths:
                now = datetime.datetime.now()
                print('加密pdf--%s--源文件%s' % (now, input_filepath))
                (filepath, tempfilename) = os.path.split(input_filepath)
                (filename, filetype) = os.path.splitext(tempfilename)
                out_path = os.path.join(filepath, filename + '-encryout.pdf')
                try:
                    pdf_reader = PdfFileReader(input_filepath)
                    pdf_writer = PdfFileWriter()
                    for page in range(pdf_reader.getNumPages()):
                        pdf_writer.addPage(pdf_reader.getPage(page))
                    pdf_writer.encrypt(user_pwd="", owner_pwd=str(password))  # 设置pdf密码
                    with open(out_path, 'wb') as out:
                        pdf_writer.write(out)
                    os.remove(input_filepath)
                    os.rename(out_path, input_filepath)
                except Exception as err:
                    if os.path.exists(out_path) and os.path.exists(input_filepath):
                        os.remove(out_path)
                    print('加密pdf--%s--源文件%s' % (now, input_filepath))
                    filepath = APILOG_PATH['excptionlogpath'] + '/' + now.strftime('%Y-%m-%d')
                    f = open(filepath, 'a')
                    f.writelines(now.strftime('%H:%M:%S')+ '加密pdf失败（文件路径%s）'% input_filepath  + '\n' + traceback.format_exc() + '\n\n')
                    f.close()
    except Exception as err:
        print('加密pdf失败')
        now = datetime.datetime.now()
        filepath = APILOG_PATH['excptionlogpath'] + '/' + now.strftime('%Y-%m-%d')
        f = open(filepath, 'a')
        f.writelines(now.strftime('%H:%M:%S') + '\n' + traceback.format_exc() + '\n\n')
        f.close()


def getPdfWordContent(pdfPath):
    try:
        wordlist = []
        fp = open(pdfPath, "rb")
        parser = PDFParser(fp)
        doc = PDFDocument(parser)
        parser.set_document(doc)
        #创建PDF资源管理器
        resource = PDFResourceManager()
        #参数分析器
        laparam = LAParams()
        #创建一个聚合器
        device = PDFPageAggregator(resource, laparams=laparam)
        #创建PDF页面解释器
        interpreter = PDFPageInterpreter(resource, device)
        #使用文档对象得到页面集合
        for page in PDFPage.create_pages(doc):
            #使用页面解释器来读取
            interpreter.process_page(page)
            #使用聚合器来获取内容
            layout=device.get_result()
            for out in layout:
                if hasattr(out, "get_text"):
                    wordlist.append(out.get_text())
        return ''.join(wordlist)
    except Exception:
        print('抽取pdf文本失败')
        now = datetime.datetime.now()
        filepath = APILOG_PATH['excptionlogpath'] + '/' + now.strftime('%Y-%m-%d')
        f = open(filepath, 'a')
        f.writelines(now.strftime('%H:%M:%S') + '\n' + traceback.format_exc() + '\n\n')
        f.close()


def BaiDuAipGetImageWord(image_path):
    try:
        client = AipOcr(baiduaip_appid, baiduaip_appkey, baiduaip_secretkey)
        image = get_file_content(image_path)
        imageRes = client.basicGeneral(image)
        words_result = imageRes.get('words_result', [])
        error_msg = imageRes.get('error_msg')
        if error_msg:
            return '图片内容识别失败--' + str(error_msg)
        words = ''
        for wordsDic in words_result:
            words = words + wordsDic.get('words')
        return words
    except Exception:
        now = datetime.datetime.now()
        filepath = APILOG_PATH['excptionlogpath'] + '/' + now.strftime('%Y-%m-%d')
        f = open(filepath, 'a')
        f.writelines(now.strftime('%H:%M:%S') + '\n' + traceback.format_exc() + '\n\n')
        f.close()

def getEsScrollResult(body):
    es = Elasticsearch({HAYSTACK_CONNECTIONS['default']['URL']})
    query = es.search(index=HAYSTACK_CONNECTIONS['default']['INDEX_NAME'], body=body, scroll='5m', size=1000)
    results = query['hits']['hits']  # es查询出的结果第一页
    total = query['hits']['total']  # es查询出的结果总量
    scroll_id = query['_scroll_id']  # 游标用于输出es查询出的所有结果

    for i in range(0, int(total / 1000) + 1):
        scroll_body = {
            "scroll": "5m",
            "scroll_id": scroll_id
        }
        scroll_query = es.scroll(body=scroll_body)
        scroll_id = scroll_query['_scroll_id']
        scroll_result = scroll_query['hits']['hits']
        results += scroll_result
    return results


#文件分片
def file_iterator(fn, chunk_size=512):
    while True:
        c = fn.read(chunk_size)
        if c:
            yield c
        else:
            break


def open_excel(filename=None, file_contents=None):
    try:
        data = xlrd.open_workbook(filename=filename, file_contents=file_contents)
        return data
    except Exception as e:
        raise InvestError(20071, msg='读取文件失败', detail=str(e))

#根据索引获取Excel表格中的数据   参数:file：Excel文件路径     colnameindex：表头列名所在行的索引  ，by_index：表的索引
def excel_table_byindex(filename=None, file_contents=None, colnameindex=0, by_index=0):
    data = open_excel(filename, file_contents)
    table = data.sheets()[by_index]
    nrows = table.nrows #行数
    colnames =  table.row_values(colnameindex) #某一行数据
    res_list =[]
    for rownum in range(colnameindex + 1, nrows):
         row = table.row_values(rownum)
         if row:
             app = {}
             for i in range(len(colnames)):
                app[colnames[i]] = row[i]
             res_list.append(app)
    return res_list