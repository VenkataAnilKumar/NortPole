from celery import Celery

import nortpole.background.celery.apps.app_base as app_base

celery_app = Celery(__name__)
celery_app.config_from_object("nortpole.background.celery.configs.client")
celery_app.Task = app_base.TenantAwareTask  # ty: ignore[invalid-assignment]
