from django.db import models


# Create your models here.

class AsinRelation(models.Model):
    asin = models.CharField(max_length=15)
    parent = models.CharField(max_length=15)

class Asin(models.Model):
    asin = models.CharField(max_length=15)
    #job_id = models.CharField(max_length=15,default='')
    status = models.IntegerField(default=0)
    failtimes = models.IntegerField(default=0)

class ItemInfo(models.Model):
    asin = models.CharField(max_length=15)
    title = models.TextField()
    en_title = models.TextField(default='')
    upc = models.CharField(max_length=15,blank=True, null=True)
    itemdetailurl = models.TextField(blank=True, null=True)
    package_height = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    package_length = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    package_width = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    package_weight = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True)
    package_height_unit = models.CharField(max_length=5,blank=True, null=True)
    package_length_unit = models.CharField(max_length=5,blank=True, null=True)
    package_width_unit = models.CharField(max_length=5,blank=True, null=True)
    package_weight_unit = models.CharField(max_length=5,blank=True, null=True)    
    package_quantity = models.IntegerField(default = 0,blank=True, null=True)
    listprice = models.IntegerField(blank=True, null=True)
    lowprice = models.IntegerField(blank=True, null=True)
    features = models.TextField(blank=True)
    brand = models.TextField(blank=True)
    color = models.TextField(blank=True)
    binding = models.TextField(blank=True)
    item_height = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True) 
    item_length = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True) 
    item_width = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True) 
    item_weight = models.DecimalField(max_digits=5, decimal_places=1, blank=True, null=True) 
    item_height_unit = models.CharField(max_length=5,blank=True, null=True)
    item_length_unit = models.CharField(max_length=5,blank=True, null=True)
    item_width_unit = models.CharField(max_length=5,blank=True, null=True)
    item_weight_unit = models.CharField(max_length=5,blank=True, null=True)
    imageurl = models.TextField(default='')
    lable = models.TextField(blank=True)
    model = models.TextField(blank=True)
    #image_file = models.FileField(upload_to='itemImage')

class ImageInfo(models.Model):
    asin = models.CharField(max_length=15)
    image_file = models.FileField(upload_to='itemImage')
    image_type = models.CharField(max_length=15, default='')

class JobInfo(models.Model):
    job_id = models.CharField(max_length=15)
    user_file_name = models.TextField(default='')
    new_item_list_file = models.FileField(upload_to='newItemList')
    item_info_xls = models.FileField(upload_to='itemInfo')
    report_file = models.FileField(upload_to='reportFiles')
    list_file_validation = models.TextField()
    result_brief = models.TextField()
    mail_box = models.TextField()
    celery_task_id = models.TextField(default='')
    
    
    
