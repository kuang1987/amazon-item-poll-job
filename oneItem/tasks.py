#!/usr/bin/env python

from celery.decorators import task
import time
import os,sys
import django
import logging
import logging.handlers
import xlrd
from amazonproduct import API
import urllib2
import requests
import Image
import re
from xlutils.copy import copy
import socket

mypath =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(mypath)
os.environ['DJANGO_SETTINGS_MODULE'] = 'amazon_web.settings'
from oneItem.models import *
from django.conf import settings
from django.core.files.base import ContentFile
from oneItem.utils import send_mail
from oneItem.amazon_util import AmazonUtil
django.setup()


unit_conv = {
    'hundredths-inches':[100,2.54,'cm'],
    'hundredths-pounds':[100,0.454,'kg'],
    'pounds':[1,0.454,'kg'],
    'ounces':[1,0.0283,'kg'],
    'grams':[1,0.001,'kg'],
    'inches':[1,2.54,'cm']
}



@task
def startNewItemJob(job_id):
    file_asin_list = []
    new_asin_list = []
    insert_ok_list = []
    insert_fail_list = []
    expect_pull_list = []
    pull_ok_list = []
    pull_fail_list = []
    expect_image_list = []
    image_ok_list = []
    image_fail_list = []
    expect_gen_file_list = []
    gen_file_ok_list = []
    gen_file_fail_list = []
    no_amazon_offer_list = []

    #if True:
    try:
        init_job_db(job_id)
        set_logger(job_id)
        logger = logging.getLogger(job_id)
        logger.info('job_id: %s -- start'%job_id)
        logger.info('job_id: %s -- start get asin list'%job_id)
        (file_asin_list,new_asin_list,insert_ok_list,insert_fail_list) = get_and_insert_asin_list(job_id)
        logger.info('job_id: %s -- end get asin list'%job_id)
        logger.info('job_id: %s -- start pull info'%job_id)
        (expect_pull_list,pull_ok_list,pull_fail_list,no_amazon_offer_list) = pullItemInfoFromAmazon(new_asin_list,insert_fail_list,job_id)
        logger.info('job_id: %s -- end pull info'%job_id)
        logger.info('job_id: %s -- start process image'%job_id)
        (expect_image_list,image_ok_list,image_fail_list) = process_image(expect_pull_list,pull_fail_list,job_id)
        logger.info('job_id: %s -- end process image'%job_id)
        logger.info('job_id: %s -- start clean fail item'%job_id)
        total_fail_list = clean_fail_item(insert_fail_list,pull_fail_list,image_fail_list,job_id)
        logger.info('job_id: %s -- end clean fail item'%job_id)        
        (expect_gen_file_list,gen_file_ok_list,gen_file_fail_list) = gen_result_file(job_id,file_asin_list,total_fail_list)
        logger.info('job_id: %s -- start generate report'%job_id)
        total_fail_list = total_fail_list + gen_file_fail_list
        generate_report(job_id,file_asin_list,total_fail_list,gen_file_ok_list,no_amazon_offer_list)
        logger.info('job_id: %s -- end generate report'%job_id)
        logger.info('job_id: %s -- start send report'%job_id)
        send_report(job_id)
        logger.info('job_id: %s -- end send report'%job_id)
    except Exception,e:
        raise Exception('job_id: %s -- reason -- %s'%(job_id,str(e)))   #tell celery task failed        
    

def init_job_db(job_id):
    job_detail = ''
    try:
        job_detail = JobInfo.objects.get(job_id = job_id)
    except:
        raise Exception('Invalid Job ID')

    if job_detail.report_file:
        os.system('rm -rf ' + job_detail.report_file.path)
        job_detail.report_file.delete()

    logfile_name = job_id + '_log.txt'
    try:
        job_detail.report_file.save(logfile_name,ContentFile(''),save=False)
        job_detail.save()
    except:
        raise Exception('Log File Init Fail')
    
def set_logger(job_id):
    try:
        job_detail = JobInfo.objects.get(job_id = job_id)
        handler = logging.FileHandler(job_detail.report_file.path) 
        fmt = '%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s'  
        formatter = logging.Formatter(fmt)   
        handler.setFormatter(formatter)       
        logger = logging.getLogger(job_id)      
        logger.addHandler(handler)            
        logger.setLevel(settings.LOG_LEVEL)
    except:
        raise Exception('set job logger failed -- job_id: %s'%job_id)

def get_and_insert_asin_list(job_id):
    logger = logging.getLogger(job_id)
    file_asin_list = []
    new_asin_list = []
    insert_ok_list = []
    insert_fail_list = []
    asin_total = 0
    try:
        job_detail = JobInfo.objects.get(job_id = job_id)
        tmp_xls = xlrd.open_workbook(job_detail.new_item_list_file.path)
    	table = tmp_xls.sheets()[0]
    	nrows = table.nrows
        for row in range(1,nrows):
            asin = str(table.cell(row,0).value).encode("UTF-8").strip()
            if asin not in file_asin_list:
                file_asin_list.append(asin)
    except:
        logger.error('get asin list from xls failed')
        raise Exception('open xls failed in get_asin_list')

    exist_asin_list = [x.asin for x in ItemInfo.objects.all()]
    for asin in file_asin_list:
        if asin not in exist_asin_list:
            new_asin_list.append(asin)
            new_asin_obj = Asin(asin = asin,
                                status = 0,
                                failtimes = 0)
            new_item_info = ItemInfo(asin=asin)
            try:
                new_item_info.save()
                new_asin_obj.save()
                insert_ok_list.append(asin)
                asin_total += 1
            except:
                insert_fail_list.append(asin)
                logger.error('Insert %s into Database Failed'%asin)
                continue 

    logger.info('%d success, %d fail'%(len(insert_ok_list),len(insert_fail_list))) 
    return file_asin_list,new_asin_list,insert_ok_list,insert_fail_list   

def pullItemInfoFromAmazon(new_asin_list,insert_fail_list,job_id):
    logger = logging.getLogger(job_id)
    expect_pull_list = []
    pull_ok_list = []
    pull_fail_list = []
    no_amazon_offer_list = []
    cn_succ_us_fail_list = []

    for asin in new_asin_list:
        if asin not in insert_fail_list:
            expect_pull_list.append(asin)

    if len(expect_pull_list) == 0:
        return expect_pull_list,pull_ok_list,pull_fail_list,no_amazon_offer_list

    for asin in expect_pull_list:
        amz_util = AmazonUtil()
        result_cn = ''
        status = -1
        (status_cn,result_cn) = amz_util.item_lookup(asin,'cn')  
        if status_cn != 0:
            if status_cn == 2: 
                logger.info('ASIN: %s not in Amazon CN'%asin)
                no_amazon_offer_list.append(asin)
            else:
                logger.info('ASIN: %s fail in Amazon CN'%asin)
            pull_fail_list.append(asin)
            continue
        result_us = ''
        status_us = -1
        (status_us,result_us) = amz_util.item_lookup(asin,'us')
        if status_us !=0 :
            logger.info('ASIN: %s fail in Amazon US'%asin)
            pull_fail_list.append(asin)
            continue
             
        (update_status,amazon_flag) = update_item_info(result_cn,result_us,asin,job_id)
        if update_status:
            logger.info('Update item info for %s success'%asin)
            pull_ok_list.append(asin)
        else:
            #if not amazon_flag:
            #    no_amazon_offer_list.append(asin)
            logger.error('Update item info for %s fail'%asin)
            pull_fail_list.append(asin)
            continue
    return expect_pull_list,pull_ok_list,pull_fail_list,no_amazon_offer_list

def update_item_info(xml_handler,xml_handler_us,asin,job_id):
    amazon_flag = True
    logger = logging.getLogger(job_id)
    item_info_obj = ''
    try:
        item_info_obj = ItemInfo.objects.get(asin=asin)
    except:
        logger.error('ASIN: %s -- fetch item info obj fail'%asin)
        return False

    try:
    #if True:
        for item in xml_handler.Items.Item:
            #total_offer = int(item.Offers.TotalOffers)
            #if total_offer == 0:
            #    amazon_flag = False
            #    logger.info('ASIN %s -- No amazon offer'%asin)
            #    return False,amazon_flag

            keys = item.ItemAttributes.__dict__.keys()
            if 'Binding' in keys:
                item_info_obj.binding = process_string(unicode(item.ItemAttributes.Binding).strip())
            if 'UPC' in keys:
                upc = upc_conv(unicode(item.ItemAttributes.UPC)).strip()
                item_info_obj.upc = upc
            if 'PackageDimensions' in keys:
                pd_keys = item.ItemAttributes.PackageDimensions.__dict__.keys()
                if 'Height' in pd_keys:
                    (num,unit) = number_conv(item.ItemAttributes.PackageDimensions.Height)
                    item_info_obj.package_height = num
                    item_info_obj.package_height_unit = unit
                if 'Length' in pd_keys:
                    (num,unit) = number_conv(item.ItemAttributes.PackageDimensions.Length)
                    item_info_obj.package_length = num
                    item_info_obj.package_length_unit = unit
                if 'Weight' in pd_keys:
                    (num,unit) = number_conv(item.ItemAttributes.PackageDimensions.Weight)
                    item_info_obj.package_weight = num
                    item_info_obj.package_weight_unit = unit
                if 'Width' in pd_keys:
                    (num,unit) = number_conv(item.ItemAttributes.PackageDimensions.Width)
                    item_info_obj.package_width = num
                    item_info_obj.package_width_unit = unit
            if 'ItemDimensions' in keys:
                id_keys = item.ItemAttributes.ItemDimensions.__dict__.keys()
                if 'Height' in id_keys:
                    (num,unit) = number_conv(item.ItemAttributes.ItemDimensions.Height)
                    item_info_obj.item_height = num
                    item_info_obj.item_height_unit = unit
                if 'Length' in id_keys:
                    (num,unit) = number_conv(item.ItemAttributes.ItemDimensions.Length)
                    item_info_obj.item_length = num
                    item_info_obj.item_length_unit = unit
                if 'Weight' in id_keys:
                    (num,unit) = number_conv(item.ItemAttributes.ItemDimensions.Weight)
                    item_info_obj.item_weight = num
                    item_info_obj.item_weight_unit = unit
                if 'Width' in id_keys:
                    (num,unit) = number_conv(item.ItemAttributes.ItemDimensions.Width)
                    item_info_obj.item_width = num
                    item_info_obj.item_width_unit = unit
                
            if 'Title' in keys:
                item_info_obj.title = process_string(unicode(item.ItemAttributes.Title).strip())
            if 'Brand' in keys:
                item_info_obj.brand = process_string(unicode(item.ItemAttributes.Brand).strip())
            if 'Color' in keys:
                item_info_obj.color = process_string(unicode(item.ItemAttributes.Color).strip())
            if 'Label' in keys:
                item_info_obj.lable = process_string(unicode(item.ItemAttributes.Label).strip())
            if 'Model' in keys:
                item_info_obj.model = process_string(unicode(item.ItemAttributes.Model).strip())
            #if 'ListPrice' in keys:
            #    item_info_obj.listprice = price_conv(str(item.ItemAttributes.ListPrice.FormattedPrice))
            if 'Feature' in keys:
                feature_list = []
                for feature in item.ItemAttributes.Feature:
                    feature_list.append(process_string(unicode(feature).strip()))
                item_info_obj.features = ('    ').join(feature_list)
    
            #imageurl = []
            #if 'ImageSets' in item.__dict__:
            #    for image in item.ImageSets.ImageSet:
            #        imageurl.append(unicode(image.LargeImage.URL))
            #else:
            #    imageurl.append(item.LargeImage.URL)

            #item_info_obj.imageurl = (';').join(imageurl)

            item_info_obj.lowprice = price_conv_cn(unicode(item.Offers.Offer.OfferListing.Price.FormattedPrice))


###from cn amazon
        for item in xml_handler_us.Items.Item:
            keys = item.ItemAttributes.__dict__.keys()
            item_info_obj.itemdetailurl = unicode(item.DetailPageURL)
            if 'ListPrice' in keys:
                item_info_obj.listprice = price_conv_us(unicode(item.ItemAttributes.ListPrice.FormattedPrice))
            else:
                item_info_obj.listprice = item_info_obj.lowprice

            if 'Title' in keys:
                item_info_obj.en_title = process_string(unicode(item.ItemAttributes.Title).strip())

            imageurl = []
            if 'ImageSets' in item.__dict__:
                for image in item.ImageSets.ImageSet:
                    imageurl.append(unicode(image.LargeImage.URL))
            else:
                imageurl.append(item.LargeImage.URL)

            item_info_obj.imageurl = (';').join(imageurl)
        
        item_info_obj.save()
        return True,amazon_flag
    except:
    #else:
        return False,amazon_flag

    return False,amazon_flag

def process_image(expect_pull_list,pull_fail_list,job_id):
    expect_image_list = []
    image_ok_list = []
    image_fail_list = []
    logger = logging.getLogger(job_id)

    for asin in expect_pull_list:
        if asin not in pull_fail_list:
            expect_image_list.append(asin)

    if len(expect_image_list) == 0:
        return expect_image_list,image_ok_list,image_fail_list

    for asin in expect_image_list:
        asin_image_file_list = ImageInfo.objects.filter(asin=asin)
        for asin_image_file in asin_image_file_list:
            os.system('rm -rf ' + asin_image_file.image_file.path)
            asin_image_file.delete()
        if download_and_change_image(asin,job_id):
            image_ok_list.append(asin)
            logger.info('ASIN: %s -- download image success'%asin)
        else:
            image_fail_list.append(asin)
            logger.info('ASIN: %s -- download image fail'%asin)
            continue
    return expect_image_list,image_ok_list,image_fail_list
        
def download_and_change_image(asin,job_id):
    status = False
    logger = logging.getLogger(job_id)
    try:
        asin_obj = ItemInfo.objects.get(asin=asin)
    except:
        logger.error('ASIN: %s -- fetch item info obj fail'%asin)
        return False        
    origin_image_list = asin_obj.imageurl.split(';')
    if len(origin_image_list) == 0:
        logger.error('ASIN: %s -- no origin image url'%asin)
        return False
    index = 0
    for url in origin_image_list:
        index += 1
        if item_image(url,asin,index,job_id):
            status = True
        else:
            continue

    return status

image_format = {
    'image/jpeg':'jpg',
    'image/tiff':'tif',
    'image/png' :'png'
}        

def item_image(url,asin,index,job_id):
    logger = logging.getLogger(job_id)
    r = ''
    for i in range(0,2):
        try:
            r = requests.get(url,timeout=10)
            logger.info('ASIN %s -- download image success'%(asin))
            break
        except:
            i += 1
            continue
    if r == '':
        logger.info('ASIN %s -- download image fail -- %s'%(asin,url))
        return False

    imageinfo = ImageInfo(asin=asin)
    imageinfo.image_type = str(r.headers['CONTENT-TYPE'])
    file_name = asin + '_' + str(index) + '.' + str(image_format[imageinfo.image_type])
    imageinfo.image_file.save(file_name,ContentFile(r.content),save=False)
    try:
        imageinfo.save()
        im = Image.open(imageinfo.image_file.path)
        (w,h) = im.size
        offset_w = (800 - w)/2
        offset_h = (800 - h)/2
        new_im = Image.new('RGBA',(800,800),(255,255,255,0))
        new_im.paste(im,(offset_w,offset_h))
        new_im.save(imageinfo.image_file.path)
        return True
    except:
        return False

def clean_fail_item(insert_fail_list,pull_fail_list,image_fail_list,job_id):
    logger = logging.getLogger(job_id)
    total_fail_list = insert_fail_list + pull_fail_list + image_fail_list
    for asin in total_fail_list:
        try:
            item_detail_obj = ItemInfo.objects.get(asin=asin)
            item_detail_obj.delete()
            logger.info('ASIN: %d -- clean item info'%asin)
        except:
            continue

    return total_fail_list


def gen_result_file(job_id,file_asin_list,total_fail_list):
    logger = logging.getLogger(job_id)
    expect_gen_file_list = []
    gen_file_ok_list = []
    gen_file_fail_list = []


    for asin in file_asin_list:
        if asin not in total_fail_list:
            expect_gen_file_list.append(asin)

    
    job_detail = JobInfo.objects.get(job_id = job_id)
    if job_detail.item_info_xls.name:
        try:
            os.system('rm -rf ' + job_detail.item_info_xls.path)
            job_detail.item_info_xls.delete()
            job_detail.save()
        except:
            raise Exception('delete old result xls fail -- job_id: %s'%job_id)

    try:
        f = open(settings.AMAZON_TEMPLATE_PATH,'r')
        content = f.read()
        job_detail.item_info_xls.save(job_id + '_result.xls', ContentFile(content),save= True)
        job_detail.save()
        f.close()
    except:
        raise Exception('save template xls fail -- job_id: %s'%job_id)

    data = None
    table = None
    try:
        data = xlrd.open_workbook(job_detail.item_info_xls.path,formatting_info=True)
        table = data.sheets()[0]
    except:
        raise Exception('open item info xls fail -- job_id: %s'%job_id)

    index = 2
    trade_type = table.cell(index,9).value
    cn = table.cell(index,31).value
    ba_status = table.cell(index,54).value
    item_type = table.cell(index,55).value
    on_status = table.cell(index,56).value
    tax_unit = table.cell(index,37).value
    #index = 4        
    for asin in expect_gen_file_list:
        try:
        #if True:
            item_data = get_item_data(asin)
            table.put_cell(index, 0, 1, item_data['binding'], 0)
            table.put_cell(index, 1, 1, item_data['brand'], 0)
            table.put_cell(index, 2, 1, item_data['name'], 0)
            table.put_cell(index, 3, 1, item_data['id'], 0)
            table.put_cell(index, 6, 1, item_data['keyword'], 0)
            table.put_cell(index, 7, 1, item_data['binding'], 0)
            table.put_cell(index, 8, 1, item_data['weight'], 0)
            table.put_cell(index, 9, 1, trade_type, 0)
            table.put_cell(index, 10, 1, item_data['upc'], 0)
            table.put_cell(index, 11, 1, item_data['image_url'], 0)
            table.put_cell(index, 12, 1, item_data['simple_desc'], 0)
            table.put_cell(index, 13, 1, item_data['full_desc'], 0)
            table.put_cell(index, 17, 1, item_data['list_price'], 0)
            table.put_cell(index, 18, 1, item_data['real_price'], 0)
            table.put_cell(index, 28, 1, item_data['en_name'], 0)
            table.put_cell(index, 29, 1, item_data['model'], 0)
            table.put_cell(index, 30, 1, item_data['package_quantity'], 0)
            table.put_cell(index, 31, 1, cn, 0)
            table.put_cell(index, 32, 1, item_data['binding'], 0)
            table.put_cell(index, 33, 1, item_data['binding'], 0)
            table.put_cell(index, 37, 1, tax_unit, 0)
            table.put_cell(index, 38, 1, item_data['package_quantity'], 0)
            table.put_cell(index, 39, 1, item_data['list_price'], 0)
            table.put_cell(index, 54, 1, ba_status, 0)
            table.put_cell(index, 55, 1, item_type, 0)
            table.put_cell(index, 56, 1, on_status, 0)
            table.put_cell(index, 57, 1, item_data['detail_url'], 0)
            #table.put_cell(index, , 1, item_data[''], 0)
            index += 1
            gen_file_ok_list.append(asin)
            logger.info('ASIN %s -- prepare item info success'%asin)
        except:
            gen_file_fail_list.append(asin)
            logger.error('ASIN %s -- prepare item info fail'%asin)
            continue


    try:
    #if True:
        wb = copy(data)
        wb.save(job_detail.item_info_xls.path)
    except:
        logger.error('write item info into xls fail -- job_id: %s'%job_id)
        gen_file_ok_list = []
        gen_file_fail_list = expect_gen_file_list
    

    return expect_gen_file_list,gen_file_ok_list,gen_file_fail_list

def get_item_data(asin):
    item_data = {}
    item_object = ''
    try:
        item_object = ItemInfo.objects.get(asin=asin)
    except:
        return item_data

    item_data['binding'] = item_object.binding#.decode('utf-8')
    item_data['brand'] = item_object.brand#.decode('utf-8')
    item_data['name'] = item_object.title#.decode('utf-8')
    item_data['en_name'] = item_object.en_title
    item_data['id'] = item_object.asin#.decode('utf-8')
    if item_object.lable:
        item_data['keyword'] = item_object.lable#.decode('utf-8')
    else:
        item_data['keyword'] = item_object.brand#.decode('utf-8')
 
    item_data['weight'] = ''#.decode('utf-8')
 
    if item_object.item_weight:
        item_data['weight'] = str(item_object.item_weight*1000)#.decode('utf-8')
    elif item_object.package_weight:
        item_data['weight'] = str(item_object.package_weight*1000)#.decode('utf-8')
    
    item_data['upc'] = item_object.upc#.decode('utf-8')
    image_list = ImageInfo.objects.filter(asin=asin)
    local_image_url_list = [settings.IMAGE_URL_PREFIX + x.image_file.name for x in image_list]
    ng_image_url_list = [settings.NG_IMAGE_URL_PREFIX + x.image_file.name for x in image_list]
    item_data['image_url'] = (';').join(local_image_url_list)#.decode('utf-8')
    item_data['simple_desc'] = get_simple_desc(item_object)
    item_data['full_desc'] = get_full_desc(item_object.features,ng_image_url_list)
    #list_price = unicode(item_object.listprice) + u'(\u7ea6\u5408)'
    list_price = unicode(item_object.listprice)
    item_data['list_price'] = list_price#.decode('utf-8')
    lowprice = unicode(item_object.lowprice)
    item_data['real_price'] = lowprice#.decode('utf-8')
    item_data['detail_url'] = item_object.itemdetailurl#.decode('utf-8')
    item_data['model'] = unicode(item_object.model)#.decode('utf-8')
    item_data['package_quantity'] = unicode(item_object.package_quantity)#.decode('utf-8')

    return item_data


def get_simple_desc(item_obj):
    content = ''
 
    #content += 'Name: %s\n'%item_obj.title
    content += u'\u5546\u54c1\u540d\u79f0: %s\n'%item_obj.title
    #content += 'Brand: %s\n'%item_obj.brand
    content += u'\u5546\u54c1\u54c1\u724c: %s\n'%item_obj.brand
    
    if item_obj.model:
        #content += 'Item Model: %s\n'%item_obj.model
        content += u'\u5546\u54c1\u578b\u53f7: %s\n'%item_obj.model
    if item_obj.color:
        #content += 'Item Color: %s\n'%item_obj.color
        content += u'\u5546\u54c1\u989c\u8272: %s\n'%item_obj.color

    #package_dim = 'Package Dimensions: '
    package_dim = u'\u5305\u88c5\u5c3a\u5bf8: '
    if item_obj.package_height and item_obj.package_length and item_obj.package_width:
        package_dim += str(item_obj.package_length) + str(item_obj.package_length_unit) + 'x' + str(item_obj.package_width) + str(item_obj.package_width_unit) + 'x' + str(item_obj.package_height) + str(item_obj.package_height_unit) + ';'
    if item_obj.package_weight:
        package_dim += str(item_obj.package_weight) + str(item_obj.package_weight_unit)

    content += package_dim + '\n'

    #item_dim = 'Item Dimensions: '
    item_dim = u'\u5546\u54c1\u5c3a\u5bf8: '
    if item_obj.item_height and item_obj.item_length and item_obj.item_width:
        item_dim += str(item_obj.item_length) + str(item_obj.item_length_unit) + 'x' + str(item_obj.item_width) + str(item_obj.item_width_unit) + 'x' + str(item_obj.item_height) + str(item_obj.item_height_unit) + ';'
    if item_obj.item_weight:
        item_dim += str(item_obj.item_weight) + str(item_obj.item_weight_unit)

    content += item_dim + '\n'
    
    return content#.decode('utf-8')
    
def get_full_desc(features, image_url_list):
    content = u''
    if features:
        feature_content = u'<p>\u5546\u54c1\u7b80\u4ecb: </p><br><ul>'
        feature_list = features.split('    ')
        for feature in feature_list:
            feature_content += u'<li>'+feature+'</li>'

        content += feature_content + u'</ul>'

    image_content = ''
    for image_url in image_url_list:
        image_content += u'<img src=\"' + image_url + '\">'

    content += image_content

    return content#.decode('utf-8')
               
   

def generate_report(job_id,file_asin_list,total_fail_list,gen_file_ok_list,no_amazon_offer_list):
    job_detail = JobInfo.objects.get(job_id = job_id)
    fail_list = []
    for asin in total_fail_list:
        if asin not in no_amazon_offer_list:
            fail_list.append(asin)
    report = """


----------------------------------
Total ASIN number in xls file: %d
Success: %d
No CN Amazon Offer: %d
Fail: %d
----------------------------------
No CN Amazon Offer:
%s


Fail ASIN: 
%s
"""%(len(file_asin_list),len(gen_file_ok_list),len(no_amazon_offer_list),len(fail_list),('\n').join(no_amazon_offer_list),('\n').join(fail_list))
    f = open(job_detail.report_file.path,'a')
    f.write(report)
    f.close()

    job_detail.result_brief = 'Total: %d\nSuccess: %d\nNo Amazon Offer: %d\nFail: %d'%(len(file_asin_list),len(gen_file_ok_list),len(no_amazon_offer_list),len(fail_list))
    job_detail.save()

def send_report(job_id):
    logger = logging.getLogger(job_id)
    xls_file = None
    log_file = None
    report = None
    subject = ''
    to_list = []
    cc_list = []
    try:
        job_detail = JobInfo.objects.get(job_id = job_id)
        report = job_detail.result_brief
        xls_file = job_detail.item_info_xls.path
        log_file = job_detail.report_file.path
        subject = 'Job %s Done'%(job_id)
        xls_url = settings.XLS_URL_PREFIX + job_detail.item_info_xls.name
        content = 'Item info:\n    %s\n\n'%xls_url
        to_list.append(job_detail.mail_box)
        cc_list.append('kong.xiangxiang@kjt.com')
    except:
        raise Exception('prepare sending mail fail -- job_id: %s'%job_id)

    send_flag = False
    if len(cc_list) > 0 and len(to_list) > 0 and report and subject :
        if send_mail(cc_list,to_list,subject,content,report):
            send_flag = True
            logger.info('job_id: %s -- sending report successfully'%job_id)

    if not send_flag:
        raise Exception('job_id: %s -- sending report failed'%job_id)
            

########Utils##############
def number_conv(obj):
    unit = obj.get('Units')
    number = float(obj)/unit_conv[unit][0]
    number = number*unit_conv[unit][1]
    new_unit = unit_conv[unit][2]
    return number,new_unit

def price_conv_us(price):
    price = re.sub('\$','',price)
    price = re.sub(',','',price)
    price = float(price)
    price = price*6.2
    return int(price)
    
def price_conv_cn(price):
    #price = repr(price)
    #price = price.encode('utf8')
    price = re.sub(u'\uffe5 ','',price,re.U)
    price = float(price)
    return int(price)   

def upc_conv(upc):
    l = len(upc)
    delta = 12 - l
    prefix = ''
    for i in range(0,delta):
        prefix += '0'
    return prefix + upc

def process_string(text):
    text = text.encode('utf-8')
    text = re.sub('^\'','',text)
    text = re.sub('\'$','',text)
    return text   

if __name__ == '__main__':
    #print startNewItemJob('20150115205049')
    job_id = '20150205194008'
    set_logger(job_id)
    #file_asin_list = ['B00MUK6M82']
    #total_fail_list = []
    #print gen_result_file('20150115205049',file_asin_list,total_fail_list

    #send_report('20150119120201')

    
    asin = 'B00EPDJY78'
    #item_detail = ItemInfo.objects.filter(asin=asin)
    #if len(item_detail) > 0:
    #    item_detail[0].delete()
    #new_item_info = ItemInfo(asin=asin)
    #new_item_info.save()
    #new_asin_list = [asin]
    #insert_fail_list = []
    
    #print pullItemInfoFromAmazon(new_asin_list,insert_fail_list,job_id)
    file_asin_list = [asin]
    total_fail_list = []
    print gen_result_file(job_id,file_asin_list,total_fail_list)
    

    #item_obj = ItemInfo.objects.get(asin = 'B00EPDJY78')
    #print get_simple_desc(item_obj)
    #print get_full_desc(item_obj.features,[])
