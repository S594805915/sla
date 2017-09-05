from datetime import timedelta
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://centerway:centerway@10.8.10.183:3306/centerway'
CELERY_BROKER_URL = 'redis://10.8.10.183:6379',
CELERY_RESULT_BACKEND = 'redis://10.8.10.183:6379'
SQLALCHEMY_TRACK_MODIFICATIONS = False
RECEIVERS = ["18066804126", "15991686139"]
CELERYBEAT_SCHEDULE = {
    'update': {
        'task': 'check_recovery',
        'schedule': timedelta(seconds=5)
    },
    'send_msg': {
        'task': 'check_problem',
        'schedule': timedelta(seconds=5)
    }
}

