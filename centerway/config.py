# coding: utf-8
from datetime import timedelta
from celery.schedules import crontab


class Config:
    EMAIL_FROM = "xiaoerzuche@sentry.com.cn"
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
    USER_EMAILS = ["dingl.li@aaa.com"]


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://centerway:centerway@mysql:3306/centerway'
    CELERY_BROKER_URL = 'redis://redis:6379',
    CELERY_RESULT_BACKEND = 'redis://redis:6379'
    RECEIVERS = ["180668041", "159916861", "130162522", "185029771"]
    USER_EMAILS = ["dingl.li@.com", "xgang.jia@.com", "chen-chen11@.com", "x.chu@.com"]
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
