from django.utils.translation import ugettext_lazy as _

from django.core.urlresolvers import reverse_lazy  # noqa
from django.core.urlresolvers import reverse  # noqa

from django.conf import settings
import requests
from horizon import tables
from horizon import messages

import openstack_dashboard.models as fogbow_models

STORAGE_TERM = fogbow_models.FogbowConstants.STORAGE_TERM
LINK_TERM = fogbow_models.FogbowConstants.LINK_TERM

class TerminateAttachment(tables.BatchAction):
    name = "terminate"
    action_present = _("Terminate")
    action_past = _("Terminated")
    data_type_singular = _("attachment")
    data_type_plural = _("attachments")
    classes = ('btn-danger', 'btn-terminate')
    success_url = reverse_lazy("horizon:fogbow:attachment:index")

    def allowed(self, request, instance=None):
        return True

    def action(self, request, obj_id):
        self.current_past_action = 0
        response = fogbow_models.doRequest('delete', STORAGE_TERM + LINK_TERM + obj_id, None, request)
        if response == None or fogbow_models.isResponseOk(response.text) == False:
            messages.error(request, _('Is was not possible to delete : %s') % obj_id)          

def get_attachment_id(request):
    if 'null' not in request.attachmentId:
        return request.attachmentId 
    else:
        return '-'

class CreateAttachment(tables.LinkAction):
    name = 'create'
    verbose_name = _('Create attachment')
    url = 'horizon:fogbow:attachment:create'
    classes = ('ajax-modal', 'btn-create')

class AttachmentFilterAction(tables.FilterAction):

    def filter(self, table, attachments, filter_string):
        q = filter_string.lower()
        return [attachment for attachment in attachments
                if q in attachment.name.lower()]

class InstancesTable(tables.DataTable):
    attachmentId = tables.Column(get_attachment_id, link=("horizon:fogbow:attachment:detail"), verbose_name=_("Attachment id"))
    target = tables.Column('target', verbose_name=_('Volume'))
    source = tables.Column('source', verbose_name=_('Instance'))

    class Meta:
        name = "attachment"
        verbose_name = _("Attachments")        
        table_actions = (CreateAttachment, TerminateAttachment, AttachmentFilterAction)
        row_actions = (TerminateAttachment, )
        