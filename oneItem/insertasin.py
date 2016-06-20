#!/usr/bin/env python

import os,sys

sys.path.append('/home/xiakong/amazon_web')
os.environ['DJANGO_SETTINGS_MODULE'] = 'amazon_web.settings'
from oneItem.models import Asin


fp = open('/home/xiakong/amazon/parent_ASIN.txt','r')
content = fp.readlines()
fp.close()

for line in content:
    asin = Asin(asin=line.strip())
    asin.save()
