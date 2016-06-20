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

mypath =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print mypath
sys.path.append(mypath)
os.environ['DJANGO_SETTINGS_MODULE'] = 'amazon_web.settings'
from oneItem.models import *
from django.core.files.base import ContentFile
django.setup()

unit_conv = {
    'hundredths-inches':[100,2.54,'cm'],
    'hundredths-pounds':[100,0.454,'kg']
}

ASSOCIATE_TAG = 'kjtcom-20'
ACCESS_KEY_ID = 'AKIAJHHYAWCZG4VIZIWA'
SECRET_ACCESS_KEY = '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'

#api = API(locale='us')

global_logger = ''


@task
def startNewItemJob(job_id):
    job_detail = ''
    try:
        job_detail = JobInfo.objects.get(job_id = job_id)
    except Exception,e:
        return 'Invalid Job Id'
    if job_detail.report_file:
        os.system('rm -rf ' + job_detail.report_file.path)
        job_detail.report_file.delete()

    logfile_name = job_id + '_log.txt'
    job_detail.report_file.save(logfile_name,ContentFile(''),save=False)
    job_detail.save()

    handler = logging.FileHandler(job_detail.report_file.path) 
    fmt = '%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s'  
  
    formatter = logging.Formatter(fmt)   
    handler.setFormatter(formatter)       
  
    logger = logging.getLogger('tst')      
    logger.addHandler(handler)            
    logger.setLevel(logging.INFO)  
    #logging.basicConfig(level=logging.INFO,
    #            format='%(asctime)s %(filename)s[line:%(lineno)d] %(levelname)s %(message)s',
    #            datefmt='%a, %d %b %Y %H:%M:%S',
    #            filename= job_detail.report_file.path,
    #            filemode='w')

    logger.info('Job %s Start'%job_id)

    if not insertAsin(job_detail.new_item_list_file.path,job_id):
        logger.error('Insert ASIN into Database failed')
        return ''

    pullItemInfoFromAmazon(job_id)

def insertAsin(filename,job_id):
    logger = logging.getLogger('tst')
    asin_list = []
    asin_total = 0
    new_asin_list = []
    try:
    	tmp_xls = xlrd.open_workbook(filename)
    	table = tmp_xls.sheets()[0]
    	nrows = table.nrows
        for row in range(1,nrows):
            asin_list.append(str(table.cell(row,0).value).encode("UTF-8"))
        
    except Exception,e:
        print str(e)
        return False

    exist_asin_list = [x.asin for x in Asin.objects.all()]
    for asin in asin_list:
        if asin not in exist_asin_list:
            new_asin_obj = Asin(asin = asin,
                                job_id = job_id,
                                status = 0,
                                failtimes = 0)
            try:
                new_asin_obj.save()
                new_asin_list.append(asin)
                asin_total += 1
            except:
                logger.error('Insert %s into Database Failed'%asin)
                continue 

    logger.info('%d ASIN(s) inserted'%asin_total)
    return True

def pullItemInfoFromAmazon(job_id):
    logger = logging.getLogger('tst')
    asin_obj_list = Asin.objects.filter(job_id = job_id)
    asin_list = [x.asin for x in asin_obj_list]
    pull_fail_list = []
    insert_fail_list = []
    image_fail_list = []
    api = API(access_key_id = ACCESS_KEY_ID, secret_access_key = SECRET_ACCESS_KEY, associate_tag = ASSOCIATE_TAG, locale='us')
    for asin in asin_list[:10]:
        asin = asin.strip()
        result = ''
        for i in range(0,2):
            try:
                result = api.item_lookup(asin,ResponseGroup='Images,ItemAttributes,Offers,BrowseNodes',MerchantId = 'Amazon',Condition='New')
                logger.info('ASIN: %s  -- %d time  --  Success'%(asin,i+1))
                break
            except Exception,e:
                logger.info('ASIN: %s  -- %d time  --  Fail'%(asin,i+1))
                continue
        if result == '':
            logger.info('ASIN: %s Fail after 3 times'%asin)
            pull_fail_list.append(asin)
            continue
        
        if not insert_item_info(result,asin):
            logger.error('Insert item info for %s fail'%asin)
            insert_fail_list.append(asin)
            continue

        if not process_image(asin):
            logger.error('Processing Image for %s fail'%asin)
            image_fail_list.append(asin)
            continue

def number_conv(obj):
    unit = obj.get('Units')
    number = float(obj)/unit_conv[unit][0]
    number = number*unit_conv[unit][1]
    new_unit = unit_conv[unit][2]
    return number,new_unit

def price_conv(price):
    price = re.sub('\$','',price)
    price = float(price)
    price = price*6.2
    return int(price)   

def upc_conv(upc):
    l = len(upc)
    delta = 12 - l
    prefix = ''
    for i in range(0,delta):
        prefix += '0'
    return prefix + upc 
        
def insert_item_info(xml_handler,asin):
    try:
        item_info_obj = ItemInfo.objects.filter(asin=asin)
        for item in item_info_obj:
            item_info_obj.delete()
    except:
        pass 
    item_info_obj = ItemInfo(asin=asin)   
    for item in xml_handler.Items.Item:
        keys = item.ItemAttributes.__dict__.keys()
        if 'Binding' in keys:
            item_info_obj.binding = str(item.ItemAttributes.Binding)
        if 'UPC' in keys:
            upc = upc_conv(str(item.ItemAttributes.UPC))
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
            item_info_obj.title = str(item.ItemAttributes.Title)
        if 'Brand' in keys:
            item_info_obj.brand = str(item.ItemAttributes.Brand)
        if 'Color' in keys:
            item_info_obj.color = str(item.ItemAttributes.Color)
        if 'Label' in keys:
            item_info_obj.lable = str(item.ItemAttributes.Label)
        if 'Model' in keys:
            item_info_obj.model = str(item.ItemAttributes.Model)
        if 'ListPrice' in keys:
            item_info_obj.listprice = price_conv(str(item.ItemAttributes.ListPrice.FormattedPrice))
        if 'Feature' in keys:
            feature_list = []
            print item.ItemAttributes.Feature
            for feature in item.ItemAttributes.Feature:
                feature_list.append(str(feature))
            item_info_obj.feature = (',').join(feature_list)

        total_offer = int(item.Offers.TotalOffers)
        if total_offer != 1:
            return False

        item_info_obj.lowprice = price_conv(str(item.Offers.Offer.OfferListing.Price.FormattedPrice))

        #item_info_obj.imageurl = str(item.LargeImage.URL)
        imageurl = []
        if 'ImageSets' in item.__dict__:
            for image in item.ImageSets.ImageSet:
                imageurl.append(str(image.LargeImage.URL))
        else:
            imageurl.append(item.LargeImage.URL)
        item_info_obj.imageurl = (';').join(imageurl)
        item_info_obj.itemdetailurl = str(item.DetailPageURL)
        try:
            item_info_obj.save()
            return True
        except:
            return False

    return False

def process_image(asin):
    status = False
    asin_image_file_list = ImageInfo.objects.filter(asin=asin)
    for asin_image_file in asin_image_file_list:
        os.system('rm -rf ' + asin_image_file.image_file.path)
        asin_image_file.delete()

    asin_obj = ItemInfo.objects.get(asin=asin)
    origin_image_list = asin_obj.imageurl.split(';')
    index = 0
    for url in origin_image_list:
        index += 1
        if download_change_image(url,asin,index):
            status = True
        else:
            continue

    return status


image_format = {
    'image/jpeg':'jpg',
    'image/tiff':'tif',
    'image/png' :'png'
}        
    
def download_change_image(url,asin,index):
    r = ''
    for i in range(0,2):
        try:
            r = requests.get(url,timeout=5)
        except:
            i += 1
            continue
    if r == '':
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
    
        

if __name__ == '__main__':
    #print startNewItemJob('20150114205955') 
    asin = 'B00001P4ZH'
    api = API(access_key_id = ACCESS_KEY_ID, secret_access_key = SECRET_ACCESS_KEY, associate_tag = ASSOCIATE_TAG, locale='us')
    result = api.item_lookup(asin,ResponseGroup='Images,ItemAttributes,Offers,BrowseNodes',MerchantId = 'Amazon',Condition='New')
    #print insert_item_info(result,asin)
    #print result.Items.Item.Offers.TotalOffers

    #for offer in result.Items.Item.Offers:
        #print offer.Offer.__dict__
        #print offer.Merchant.Name
    #    print offer.Offer.OfferListing.Price.FormattedPrice
    print insert_item_info(result,asin)
    #print price_conv('$34.90')
     
    #print upc_conv('2129914776') 
