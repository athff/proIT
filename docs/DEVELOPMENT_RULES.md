# Development Rules

## Coding Standards

### Python

- Follow [PEP 8](https://pep.org/pep-0008/) style guide
- Maximum line length: 88 characters (black default) or 79 for legacy compatibility
- Type hints used where beneficial; `from __future__ import annotations` enabled
- Docstrings follow [Google Style](https://sphinxcontrib-napoleon.readthedocs.io/en/latest/) or [NumPy Style]
- `isort` for import ordering; `black` for formatting; `flake8` for linting

### Django

- Function-based views for simple cases; class-based views (`ViewSet`, `ListCreateAPIView`, etc.) for API endpoints
- Models with `__str__` method and `get_absolute_url` where applicable
- Managers and querysets used for common filter patterns
- Migrations generated and applied incrementally; never edit migration files manually after generation

### File Organization

- One logical grouping per Django app: `models.py`, `views.py`, `serializers.py`, `urls.py`, `admin.py`, `tests/`, `management/`
- Project-level `settings.py`, `urls.py`, `wsgi.py`, `asgi.py`
- Shared utilities and constants in project-level or app-specific `utils.py`

## Testing Requirements

### Test Framework

- [pytest](https://pytest.org/) as the test runner
- [django-test-plus](https://github.com/coderholic/django-test-plus) for enhanced test utilities
- [factory-boy](https://factoryboy.readthedocs.io/) for test data generation

### Test Coverage

- Minimum 80% test coverage for all new code
- All models have tests covering creation, relationships, and `__str__`
- All viewsets have tests for create, retrieve, update, partial_update, destroy (CRUD)
- Authentication and permission classes tested for success and failure cases
- Integration tests for API workflows (checkout, check-in, license assignment)

### Test Execution

- `pytest` command from project root
- `--tb=short` for tracebacks
- `-x` to stop on first failure in CI
- Coverage reported via `coverage` tool

### Example Test Structure

```python
# tests/assets_test.py
from django.test import TestCase
from rest_framework.test import APIClient
from .models import Asset

class AssetModelTest(TestCase):
    def test_asset_creation(self):
        asset = Asset.objects.create(
            asset_tag="TEST-001",
            asset_type=AssetType.LAPTOP,
            status=AssetStatus.ACTIVE,
        )
        self.assertEqual(str(asset), "TEST-001")
        self.assertEqual(asset.status, AssetStatus.ACTIVE)

class AssetApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_list_assets(self):
        response = self.client.get("/api/assets/")
        self.assertEqual(response.status_code, 200)