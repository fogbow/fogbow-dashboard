from django.conf.urls.defaults import patterns  # noqa
from django.conf.urls.defaults import url  # noqa

from openstack_dashboard.dashboards.fogbow.instance import views

urlpatterns = patterns('',
    url(r'^$', views.IndexView.as_view(), name='index'),
#     url(r'^(?P<instance_id>[^/]+)/detail/$',
#     views.DetailView.as_view(), name='detail')
)