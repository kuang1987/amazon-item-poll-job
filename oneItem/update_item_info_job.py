#!/usr/bin/env python

import requests
import os,sys
import django
import json
import re
import copy

mypath =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(mypath)
os.environ['DJANGO_SETTINGS_MODULE'] = 'amazon_web.settings'
django.setup()
from amazon_web import settings
from oneItem.amazon_util import AmazonUtil

amz_util = AmazonUtil()

def Retry(f,times=3):
    i = 0
    def wrapper(*args):
        for i in range(0,times):
            try:
                return f(*args)
            except:
                continue
        return None
    return wrapper


#@Retry
def new_egg_service(params):
    full_url = params['url'] + params['interface']
    r = requests.request(params['method'],full_url,params=params['params'],data=params['payload'])
    print r.content
    if r.status_code != 200:
        r.raise_for_status()
    return r.content


def get_item_info_from_newegg():
    item_info = []
    params = {}
    params['url'] = settings.NEW_EGG_SERVICE_URL
    params['interface'] = 'getproductlist'
    params['method'] = 'get'
    params['params'] = {'merchantSysNo':86}
    params['payload'] = None
    response = new_egg_service(params)
    print response
    if response:
        item_info = json.loads(response)
    return item_info

def get_item_info_from_amazon(item):
    asin = item['ProductID']
    result = ''
    status,result = amz_util.item_lookup(asin,'cn')
    if status != 0 or result == '':
        return item

    total_offer = int(result.Items.Item.Offers.TotalOffers)
    if total_offer == 0:
        item['Status'] = 'D'
    else:
        try:
        #if True:
            item['UnitPrice'] = price_conv_cn(unicode(result.Items.Item.Offers.Offer.OfferListing.Price.FormattedPrice))
            item['Status'] = 'A'
        except:
            item['Status'] = 'D'
    return item

def price_conv_cn(price):
    price = re.sub(u'\uffe5 ','',price,re.U)
    price = float(price)
    return int(price)

def select_updated_items(mock_list = []):
    updated_items = []
    item_info_list = get_item_info_from_newegg()
    #item_info_list = mock_list
    if len(item_info_list) == 0:
        return updated_items
        
    for item in item_info_list:
        origin_item = copy.deepcopy(item)
        item = get_item_info_from_amazon(item)
        if item != origin_item:
            updated_items.append(item)

    return updated_items


def do_update(mock_list = []):
    #update_items = select_update_items()
    update_items = mock_list
    if len(update_items) == 0:
        return

    payload = {}
    payload['Version'] = 'v0.1'
    payload['MerchantSysNo'] = 86
    payload['MerchantCode'] = 'Amazon'
    payload['Products'] = update_items

    params = {}
    params['url'] = settings.NEW_EGG_SERVICE_URL
    params['interface'] = 'productsync'
    params['method'] = 'post'
    params['params'] = None
    params['payload'] = json.dumps(payload)

    print params['payload']

    r = new_egg_service(params)

    if r == 'True':
        print 'Success'
    else:
        print 'Fail'

    return

if __name__ == '__main__':
    #mock_list = [{"ProductID":"B006VB29D8","Status":"D","UnitPrice":1369.000000},{"ProductID":"B00BNEBL6E","Status":"D","UnitPrice":2494.000000},{"ProductID":"B00EU5AHXG","Status":"D","UnitPrice":2057.000000}]
    #print select_updated_items(mock_list)

    mock_list = [{'Status': 'A', 'UnitPrice': 63, 'ProductID': 'B006VB29D8'}, {'Status': 'A', 'UnitPrice': 111, 'ProductID': 'B00BNEBL6E'}, {'Status': 'A', 'UnitPrice': 111, 'ProductID': 'B00EU5AHXG'}]
    do_update(mock_list)
