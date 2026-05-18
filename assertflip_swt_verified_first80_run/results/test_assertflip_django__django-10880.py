from django.db import models
from django.test import TestCase

# Define a simple model for testing
class TestModel(models.Model):
    value = models.IntegerField()

    class Meta:
        app_label = 'test_app'  # Explicitly set the app label

class CountDistinctCaseBugTest(TestCase):
    def test_count_distinct_case(self):
        from django.db.models import Count, Case, When

        # Construct the query
        query = TestModel.objects.annotate(
            count_case=Count(
                Case(
                    When(value__gt=0, then=1),
                    When(value__lt=0, then=0),
                    default=0,
                ),
                distinct=True
            )
        )

        # Execute the query and capture the SQL
        sql, params = query.query.get_compiler('default').as_sql()

        # Check for the absence of the bug in the generated SQL
        self.assertNotIn("DISTINCTCASE", sql)  # Test will fail if the bug is present
