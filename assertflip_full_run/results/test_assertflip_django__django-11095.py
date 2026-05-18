from django.test import SimpleTestCase
from unittest.mock import Mock

class InlineModelAdmin:
    def __init__(self, model, admin_site):
        self.model = model
        self.admin_site = admin_site
        self.inlines = [Mock(), Mock()]  # Simulating two inline classes

    def get_inline_instances(self, request, obj=None):
        inline_instances = []
        for inline_class in self.inlines:
            inline = inline_class(self.model, self.admin_site)
            if request.user.has_perm('view'):
                inline_instances.append(inline)
            if not request.user.has_perm('add'):
                inline.max_num = 0  # Simulating that no new instances can be added
        return inline_instances

class TestModelAdmin(SimpleTestCase):
    def setUp(self):
        self.model = Mock()
        self.admin_site = Mock()
        self.model_admin = InlineModelAdmin(self.model, self.admin_site)

    def test_get_inlines_with_view_permission_only(self):
        request = Mock()
        request.user.has_perm = Mock(side_effect=lambda perm: perm == 'view')
        inlines = self.model_admin.get_inline_instances(request)
        
        # Expecting no inlines to be returned because the user does not have 'add' permission
        self.assertEqual(len(inlines), 0)  # This should fail if the bug is present

    def test_get_inlines_with_view_and_add_permissions(self):
        request = Mock()
        request.user.has_perm = Mock(side_effect=lambda perm: perm in ['view', 'add'])
        inlines = self.model_admin.get_inline_instances(request)
        
        # Expecting both inlines to be returned
        self.assertEqual(len(inlines), 2)  # Both inlines should be returned

    def test_get_inlines_with_no_permissions(self):
        request = Mock()
        request.user.has_perm = Mock(return_value=False)
        inlines = self.model_admin.get_inline_instances(request)
        
        # Expecting no inlines to be returned
        self.assertEqual(len(inlines), 0)  # No inlines should be returned

    def test_get_inlines_with_mixed_permissions(self):
        request = Mock()
        request.user.has_perm = Mock(side_effect=lambda perm: perm in ['view', 'delete'])  # Only view and delete permissions
        inlines = self.model_admin.get_inline_instances(request)
        
        # Expecting no inlines to be returned because the user does not have 'add' permission
        self.assertEqual(len(inlines), 0)  # This should fail if the bug is present
