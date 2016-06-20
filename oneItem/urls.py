from django.conf.urls import patterns, url

from oneItem import views

urlpatterns = patterns('',
	url(r'^index',views.index,name='index'),
        #url('detail/(?P<asin>.+)$',views.detail,name='detail'),
        #url('xml/(?P<asin>.+)$',views.xml,name='xml'),
	url(r'^job',views.job,name='job'),
        url('uploadxls',views.uploadxls,name='uploadxls'),
        url(r'^showjoblist',views.showjoblist,name='showjoblist'),
        url(r'^startjob',views.startjob,name='startjob'),
        url(r'^showrelog/(?P<job_id>.+)$',views.showrelog,name='showrelog'),
)
