import hashlib
import logging
import requests
import horizon
import models as fogbow_models

from django.conf import settings
from django.contrib.auth import models
from django.utils.translation import ugettext_lazy as _
from keystoneclient import exceptions as keystone_exceptions
from openstack_auth import utils
from horizon import messages

LOG = logging.getLogger(__name__)

class FogbowConstants():
    COMPUTE_TERM = '/compute/'
    REQUEST_TERM_WITH_VERBOSE = '/fogbow_models?verbose=true'
    REQUEST_TERM = '/fogbow_models/'
    MEMBER_TERM = '/members'
    RESOURCE_TERM = '/-/'
        
    STATE_TERM = 'occi.compute.state'
    SHH_PUBLIC_KEY_TERM = 'org.fogbowcloud.request.ssh-public-address'
    CONSOLE_VNC_TERM = 'org.openstack.compute.console.vnc'
    MEMORY_TERM = 'occi.compute.memory'
    CORES_TERM = 'occi.compute.cores'
    IMAGE_SCHEME = 'http://schemas.ogf.org/occi/infrastructure#os_tpl'      
    
    FOGBOW_STATE_TERM = 'org.fogbowcloud.request.state'
    FOGBOW_TYPE_TERM = 'org.fogbowcloud.request.type'
    FOGBOW_INSTANCE_ID_TERM = 'org.fogbowcloud.request.instance-id' 

class IdentityPluginConstants():
    AUTH_KEYSTONE = 'Keystone'
    AUTH_TOKEN = 'Fogbow Raw Token'
    AUTH_OPENSTACK = 'Keystone'
    AUTH_OPENNEBULA = 'OpenNebula'
    AUTH_VOMS = 'Voms'

class Token():
    def __init__(self, id=None):
        self.id = id

class User(models.AnonymousUser):
    errors = False
    type = 'fogbow_user'
    authorized_tenants = {}
    
    def __init__(self, id=None, token=None, username=None, roles=None):
        self.id = id
        self.token = token
        self.username = username
        self.roles = roles

    def __unicode__(self):
        return self.username

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.username)

    @property
    def is_active(self):
        return True

    @property
    def is_superuser(self):
        return False

    def is_authenticated(self, request=None, margin=None):
        return self.token is not None
    
    def save(*args, **kwargs):
        pass
    
    def has_perms(self, perm_list, obj=None):
        return True
    
def checkUserAuthenticated(token):
    print 'PUts'
    headers = {'content-type': 'text/occi', 'X-Auth-Token' : token.id }
    response = requests.get('%s%s' % (settings.MY_ENDPOINT, FogbowConstants.RESOURCE_TERM) ,
                                   headers=headers)
    
    responseStr = response.text

    if 'Unauthorized' in responseStr or 'Bad Request' in responseStr or 'Authentication required.' in responseStr:
        return False    
    return True

def doRequest(method, endpoint, additionalHeaders, request):
    token = request.session.get('token','').id
    
    headers = {'content-type': 'text/occi', 'X-Auth-Token' : token}
    if additionalHeaders is not None:
        headers.update(additionalHeaders)    
        
    responseStr, response = '', None
    try:
        if method == 'get':
            response = requests.get(settings.MY_ENDPOINT + endpoint, headers=headers)
        elif method == 'delete':
            response = requests.delete(settings.MY_ENDPOINT + endpoint, headers=headers)
        elif method == 'post':   
            response = requests.post(settings.MY_ENDPOINT + endpoint, headers=headers)
        responseStr = response.text     
    except Exception:
        messages.error(self.request, _('Problem communicating with the Manager.'))
    
    if 'Unauthorized' in responseStr or 'Authentication required.' in responseStr:
        messages.error(request, _('Token Unauthorized.'))
    elif 'Bad Request' in responseStr:
        messages.error(request, _('Bad Request.'))
    return response

def isResponseOk(responseStr):
    if 'Unauthorized' not in responseStr and 'Bad Request' not in responseStr and 'Authentication required.' not in responseStr:
        return True
    return False    

def calculatePercent(value, valueTotal):
    defaultValue = 0
    try:
        return (value * 100) / valueTotal
    except Exception:
        return defaultValue

#
# OpenStack_auth / Fogbow
#

def set_session_from_user(request, user):
    request.session['token'] = user.token
    request.session['user_id'] = user.id
    request.session['region_endpoint'] = user.endpoint
    request.session['services_region'] = user.services_region
    request._cached_user = user
    request.user = user


def create_user_from_token(request, token, endpoint, services_region=None):
    return User(id=token.user['id'],
                token=token,
                user=token.user['name'],
                user_domain_id=token.user_domain_id,
                # We need to consider already logged-in users with an old
                # version of Token without user_domain_name.
                user_domain_name=getattr(token, 'user_domain_name', None),
                project_id=token.project['id'],
                project_name=token.project['name'],
                domain_id=token.domain['id'],
                domain_name=token.domain['name'],
                enabled=True,
                service_catalog=token.serviceCatalog,
                roles=token.roles,
                endpoint=endpoint,
                services_region=services_region)


class TokenOriginal(object):
    def __init__(self, auth_ref):
        user = {}
        user['id'] = auth_ref.user_id
        user['name'] = auth_ref.username
        self.user = user
        self.user_domain_id = auth_ref.user_domain_id
        self.user_domain_name = auth_ref.user_domain_name

        self.id = auth_ref.auth_token
        if len(self.id) > 64:
            algorithm = getattr(settings, 'OPENSTACK_TOKEN_HASH_ALGORITHM',
                                'md5')
            hasher = hashlib.new(algorithm)
            hasher.update(self.id)
            self.id = hasher.hexdigest()
        self.expires = auth_ref.expires

        # Project-related attributes
        project = {}
        project['id'] = auth_ref.project_id
        project['name'] = auth_ref.project_name
        self.project = project
        self.tenant = self.project

        # Domain-related attributes
        domain = {}
        domain['id'] = auth_ref.domain_id
        domain['name'] = auth_ref.domain_name
        self.domain = domain

        if auth_ref.version == 'v2.0':
            self.roles = auth_ref['user'].get('roles', [])
        else:
            self.roles = auth_ref.get('roles', [])

        if utils.get_keystone_version() < 3:
            self.serviceCatalog = auth_ref.get('serviceCatalog', [])
        else:
            self.serviceCatalog = auth_ref.get('catalog', [])


class UserOriginal(models.AnonymousUser):
    
    def __init__(self, id=None, token=None, user=None, tenant_id=None,
                 service_catalog=None, tenant_name=None, roles=None,
                 authorized_tenants=None, endpoint=None, enabled=False,
                 services_region=None, user_domain_id=None,
                 user_domain_name=None, domain_id=None, domain_name=None,
                 project_id=None, project_name=None):
        self.id = id
        self.pk = id
        self.token = token
        self.username = user
        self.user_domain_id = user_domain_id
        self.user_domain_name = user_domain_name
        self.domain_id = domain_id
        self.domain_name = domain_name
        self.project_id = project_id or tenant_id
        self.project_name = project_name or tenant_name
        self.service_catalog = service_catalog
        self._services_region = (services_region or
                                 self.default_services_region())
        self.roles = roles or []
        self.endpoint = endpoint
        self.enabled = enabled
        self._authorized_tenants = authorized_tenants

        # List of variables to be deprecated.
        self.tenant_id = self.project_id
        self.tenant_name = self.project_name

    def __unicode__(self):
        return self.username

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.username)

    def is_token_expired(self, margin=None):
        if self.token is None:
            return None
        return not utils.is_token_valid(self.token, margin)

    def is_authenticated(self, margin=None):
        return (self.token is not None and
                utils.is_token_valid(self.token, margin) and 
                checkUserAuthenticated(self.token))

    def is_anonymous(self, margin=None):
        return not self.is_authenticated(margin)

    @property
    def is_active(self):
        return self.enabled

    @property
    def is_superuser(self):
        return 'admin' in [role['name'].lower() for role in self.roles]

    @property
    def authorized_tenants(self):
        insecure = getattr(settings, 'OPENSTACK_SSL_NO_VERIFY', False)
        ca_cert = getattr(settings, "OPENSTACK_SSL_CACERT", None)

        if self.is_authenticated() and self._authorized_tenants is None:
            endpoint = self.endpoint
            token = self.token
            try:
                self._authorized_tenants = utils.get_project_list(
                    user_id=self.id,
                    auth_url=endpoint,
                    token=token.id,
                    insecure=insecure,
                    cacert=ca_cert,
                    debug=settings.DEBUG)
            except (keystone_exceptions.ClientException,
                    keystone_exceptions.AuthorizationFailure):
                LOG.exception('Unable to retrieve project list.')
        return self._authorized_tenants or []

    @authorized_tenants.setter
    def authorized_tenants(self, tenant_list):
        self._authorized_tenants = tenant_list

    def default_services_region(self):
        if self.service_catalog:
            for service in self.service_catalog:
                if service['type'] == 'identity':
                    continue
                for endpoint in service['endpoints']:
                    return endpoint['region']
        return None

    @property
    def services_region(self):
        return self._services_region

    @services_region.setter
    def services_region(self, region):
        self._services_region = region

    @property
    def available_services_regions(self):
        regions = []
        if self.service_catalog:
            for service in self.service_catalog:
                if service['type'] == 'identity':
                    continue
                for endpoint in service['endpoints']:
                    if endpoint['region'] not in regions:
                        regions.append(endpoint['region'])
        return regions

    def save(*args, **kwargs):
        pass

    def delete(*args, **kwargs):
        pass

    def has_a_matching_perm(self, perm_list, obj=None):
        if not perm_list:
            return True
        for perm in perm_list:
            if self.has_perm(perm, obj):
                return True
        return False

    def has_perms(self, perm_list, obj=None):
        if not perm_list:
            return True
        for perm in perm_list:
            if isinstance(perm, basestring):
                if not self.has_perm(perm, obj):
                    return False
            else:
                if not self.has_a_matching_perm(perm, obj):
                    return False
        return True
