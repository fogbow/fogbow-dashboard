from horizon import views
from django.utils.translation import ugettext_lazy as _  # noqa
from horizon import tables
from horizon import tabs

from openstack_dashboard.dashboards.fogbow.instance \
    import tabs as project_tabs
from openstack_dashboard.dashboards.fogbow.instance \
    import tables as project_tables
from openstack_dashboard.dashboards.fogbow.instance \
    import models as project_models    
import openstack_dashboard.models as fogbow_request

# LOG = logging.getLogger(__name__)

THERE_ARE_NOT_INSTANCE = 'There are not instances'
X_OCCI_LOCATION = 'X-OCCI-Location: '
COMPUTE_TERM = fogbow_request.FogbowConstants.COMPUTE_TERM

class IndexView(tables.DataTableView):
    table_class = project_tables.InstancesTable
    template_name = 'fogbow/instance/index.html'

    def has_more_data(self, table):
        return self._more

    def get_data(self):
        responseStr = fogbow_request.doRequest('get', COMPUTE_TERM, None, self.request).text        
        
        instances = self.getInstances(responseStr)
        
        self._more = False
        
        return instances
    
    def normalizeAttribute(self, propertie):
        return propertie.replace(X_OCCI_LOCATION, '')

    def getInstances(self, responseStr):
        instances = []
        try:            
            if fogbow_request.isResponseOk(responseStr):                         
                properties =  memberProperties = responseStr.split('\n')
                for propertie in properties:
                    idInstance = self.normalizeAttribute(propertie)
                    instance = {'id': idInstance, 'instanceId': idInstance}
                    if areThereInstance(responseStr):
                        instances.append(project_models.Instance(instance))                                
        except Exception:
            instances = []
            
        return instances
        
def areThereInstance(responseStr):
    if THERE_ARE_NOT_INSTANCE in responseStr:
        return False
    return True 

class DetailViewInstance(tabs.TabView):
    tab_group_class = project_tabs.InstanceDetailTabGroupInstancePanel
    template_name = 'fogbow/instance/detail.html'     
        