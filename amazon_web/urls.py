from django.conf.urls import patterns, include, url
from django.contrib import admin
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'amazon_web.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^admin/', include(admin.site.urls)),
    url(r'^item/',include('oneItem.urls')),
)

urlpatterns += static(r'/static/', document_root = settings.STATIC_ROOT)
urlpatterns += static(r'/media/', document_root = settings.MEDIA_ROOT)
