#!/usr/bin/env python

from amazonproduct import API
from amazonproduct.errors import InvalidParameterValue,TooManyRequests
import socket
import os,sys
import time
import urllib2

mypath =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(mypath)
os.environ['DJANGO_SETTINGS_MODULE'] = 'amazon_web.settings'

from django.conf import settings


class AmazonUtil:
    def __init__(self):
        #self.associate_tag = settings.ASSOCIATE_TAG
        #self.access_key_id = settings.ACCESS_KEY_ID
        #self.secret_access_key = settings.SECRET_ACCESS_KEY
        self.api = None

    def item_lookup(self,asin,locale,retry=3,time_interval=10,ResponseGroup='Images,ItemAttributes,Offers,BrowseNodes',MerchantId=None,Condition=None):
        self.api = API(access_key_id = settings.ACCESS_KEY_ID, secret_access_key = settings.SECRET_ACCESS_KEY, associate_tag = settings.ASSOCIATE_TAG, locale=locale)
        result = ''

        #status
        #0 -- Success
        #1 -- Socket Timeout
        #2 -- Invalid ASIN
        #-1 -- Fail
        status = -1   
        for i in range(0,retry):
            try:
                #result = self.api.item_lookup(asin,ResponseGroup=ResponseGroup,MerchantId = MerchantId,Condition=Condition)
                result = self.api.item_lookup(asin,ResponseGroup=ResponseGroup)
                status = 0
                break
            except urllib2.URLError,e:
                status = 1
                continue
            except socket.timeout,e:
                status = 1
                continue
            except InvalidParameterValue,e:
                status = 2
                break
            except TooManyRequests,e:
                status = -1
                time.sleep(time_interval)
                continue
        return status,result


if __name__ == '__main__':
    amazon_util = AmazonUtil()
    status,result = amazon_util.item_lookup('B000JIJPZY','cn')

    price = repr(result.Items.Item.Offers.Offer.OfferListing.Price.FormattedPrice)
    import re
    print price
    price = re.sub('\\\uffe5 ','',price,re.U)
    print price
