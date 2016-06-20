#coding:utf-8
from django.shortcuts import render,render_to_response
from django.http import HttpResponse
from django.http import JsonResponse
from django.template import Context,Template,RequestContext
from django.template import loader
from oneItem.models import *
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from datetime import *
import xlrd
from django.core.files.base import ContentFile

from amazonproduct import API
from oneItem.tasks import *
from celery.result import AsyncResult


import sys,os


api = API(locale='us')
def call(fp):
    return api._parse(fp)
#default_encoding = 'utf-8'
#if sys.getdefaultencoding() != default_encoding:
#    reload(sys)
#    sys.setdefaultencoding(default_encoding)

# Create your views here.
def index(request):
    image_url_list = ['/media/' + str(x.image_file.name) for x in ImageInfo.objects.all()]
    
    return render_to_response('index.html',{'image_list':image_url_list},content_type = "text/html")

def detail(request,asin):
    xml_file = settings.ITEM_XML_DIR + asin + '.xml'
    fp = open(xml_file,'r')
    #try:
    result = call(fp)
    #result = api.item_lookup(asin,ResponseGroup='Images,ItemAttributes,OfferFull,Variations')
    xml_to_dic = result.Items.Item[0].__dict__
    item_attribute = result.Items.Item[0].ItemAttributes.__dict__
    #variation = result.Items.Item[0].VariationSummary.__dict__
    item_param = {}
    total_feature = []
    if 'Feature' in item_attribute.keys():
        for feature in item_attribute['Feature']:
            total_feature.append(str(feature))
    item_param['page_url'] = str(result.Items.Item[0].DetailPageURL)
    item_param['total_feature'] = total_feature
    #item_param['brand'] = item_attribute['Brand']
    item_param['title'] = item_attribute['Title']
    if 'VariationSummary' in xml_to_dic.keys():
        variation = result.Items.Item[0].VariationSummary.__dict__
        item_param['price_low'] = variation['LowestPrice'].FormattedPrice
        item_param['price_high'] = variation['HighestPrice'].FormattedPrice
    elif 'OfferSummary' in xml_to_dic.keys():
        offersum = result.Items.Item[0].OfferSummary.__dict__
        item_param['price_low'] = offersum['LowestNewPrice'].FormattedPrice
        item_param['price_high'] = ''
        
    if 'LargeImage' in xml_to_dic.keys():
        item_param['image_url'] = result.Items.Item[0].LargeImage.URL
        item_param['h'] = result.Items.Item[0].LargeImage.Height
        item_param['w'] = result.Items.Item[0].LargeImage.Width
    else:
        item_param['image_url'] = result.Items.Item[0].Variations.Item[0].LargeImage.URL
        item_param['h'] = result.Items.Item[0].Variations.Item[0].LargeImage.Height
        item_param['w'] = result.Items.Item[0].Variations.Item[0].LargeImage.Width
    fp.close()
    print item_param
    return render_to_response('detail.html',{'item':item_param,'asin':asin},content_type = "text/html")

def xml(request,asin):
    xml_file = settings.ITEM_XML_DIR + asin + '.xml'
    fp = open(xml_file,'r')    
    content = fp.read()
    fp.close()
    return HttpResponse(content,content_type='text/xml')

def showrelog(request,job_id):
    job_obj = JobInfo.objects.get(job_id=job_id)
    fp = open(job_obj.report_file.path,'r')    
    content = fp.read()
    fp.close()    
    return HttpResponse(content,content_type='text/plain')

def job(request):
    return render_to_response('job.html',{},content_type = "text/html")

def uploadxls(request):
    file_obj = ''
    file_content = ''
    try:
        file_obj = request.FILES.values()[0]
        file_content = file_obj.read()
    except Exception,e:
        return ({'status':'Fail','reason':'No xls file uploaded'})

    job_id = datetime.now().strftime('%Y%m%d%H%M%S')
    (status,asin_total,asin_list) = validate_xls(file_content,job_id)
    if not status:
        return JsonResponse({'status':'Fail','reason':'Invalid Format'})

    mail = ''
    try:
        mail = request.POST['mail']
    except Exception,e:
        mail = ''
   
    exist_asin_list = [x.asin for x in ItemInfo.objects.all()]
    exist_total = 0
    for asin in asin_list:
        if asin in exist_asin_list: 
            exist_total += 1

    list_file_validation = 'Total: %d\nNew: %d\nExisting: %d'%(asin_total,asin_total-exist_total,exist_total)

    

    upfilename = file_obj.name
    
    jobinfo = JobInfo(job_id = job_id, 
                      user_file_name = upfilename, 
                      mail_box = mail,
                      list_file_validation = list_file_validation)
    jobinfo.save() 

    jobinfo.new_item_list_file.save(job_id + '_up.xls',ContentFile(file_content),save=False)
    jobinfo.save()

            
    return JsonResponse({'status':'success','reason':'Job %s Inserted'%job_id})

def showjoblist(request):
    job_list = JobInfo.objects.order_by('job_id').reverse()
    job_list_detail = []
    for job in job_list:
        result = {}
        result['job_id'] = job.job_id
        result['mail'] = job.mail_box
        result['upfilename'] = job.user_file_name
        result['upfilepath'] = job.new_item_list_file.name
        result['upfilebrief'] = job.list_file_validation
        result['rebrief'] = job.result_brief
        result['relog'] = job.report_file
        result['refile'] = job.item_info_xls
        result['status'] = 'NONE'
        if job.celery_task_id:
            a = AsyncResult(id = job.celery_task_id)
            result['status'] = a.status
        job_list_detail.append(result)
    t = loader.get_template('job_table.html')  
    c = Context({'r_list': job_list_detail})
    return JsonResponse({'status':'success','reason':t.render(c)})

def validate_xls(xls_content,job_id):
    status = True
    asin_total = 0
    asin_list = []

    tmp_file_name = settings.MEDIA_ROOT  + job_id+'_tmp.xls'
    print tmp_file_name
    tmp_file = open(tmp_file_name,'w')
    tmp_file.write(xls_content)
    tmp_file.close()
    #os.system('rm -rf ' + tmp_file_name )
    try:
    	tmp_xls = xlrd.open_workbook(tmp_file_name)
    	table = tmp_xls.sheets()[0]
    	nrows = table.nrows
    	asin_total = 0
        for row in range(1,nrows):
            asin = str(table.cell(row,0).value).encode("UTF-8")
            if asin not in asin_list:
                asin_list.append(asin)
                asin_total += 1

    except Exception,e:
        status = False
      
    os.system('rm -rf ' + tmp_file_name ) 
    return status,asin_total,asin_list

def startjob(request):
    job_id = ''
    try:
        job_id = request.GET['job_id']
    except:
        return JsonResponse({'status':'fail','reason':'Invalid Job ID'})
    
    job_detail = ''
    try:
        job_detail = JobInfo.objects.get(job_id = job_id)
    except:
        return JsonResponse({'status':'fail','reason':'No this Job ID'})
        
    celery_task_id = startNewItemJob.delay(job_id)
    job_detail.celery_task_id = celery_task_id
    job_detail.save()

    return  JsonResponse({'status':'success','reason':'Job started'})

