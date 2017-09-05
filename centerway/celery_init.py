# coding: utf-8
def init_celery(application, celery):
    celery.conf.update(application.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with application.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
