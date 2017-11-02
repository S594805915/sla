# coding: utf-8
from datetime import timedelta
from celery.schedules import crontab


class Config:
    EMAIL_FROM = "xiaoerzuche@sentry.xiaoerzuche.com.cn"
    EMAIL_PASS = "@Q123456@q"
    EMAIL_SERVER = "smtp.mailgun.org"
    EMAIL_SERVER_PORT = 25
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CELERYBEAT_SCHEDULE = {
        'update': {
            'task': 'check_recovery',
            'schedule': timedelta(seconds=30)
        },
        'health_report': {
            'task': 'health_report',
            'schedule': crontab(hour=0, minute=40)
        }
    }


class DevelopmentConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://centerway:centerway@10.8.10.183:3306/centerway'
    CELERY_BROKER_URL = 'redis://10.8.10.183:6379',
    CELERY_RESULT_BACKEND = 'redis://10.8.10.183:6379'
    RECEIVERS = ["18066804126"]
    DEBUG = True
    USER_EMAILS = ["dingl.li@hnair.com"]


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://centerway:centerway@mysql:3306/centerway'
    CELERY_BROKER_URL = 'redis://redis:6379',
    CELERY_RESULT_BACKEND = 'redis://redis:6379'
    RECEIVERS = ["18066804126", "15991686139", "13016252272", "18502977176"]
    USER_EMAILS = ["dingl.li@hnair.com", "xgang.jia@hnair.com", "chen-chen11@hnair.com", "x.chu@hnair.com"]
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
