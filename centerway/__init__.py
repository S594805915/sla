# coding: utf-8
from flask import Flask
from celery import Celery
from flask_sqlalchemy import SQLAlchemy
from centerway.config import config

db = SQLAlchemy()
celery = Celery()


# def create_app(config_name):
#     app = Flask(__name__)
#     app.config.from_object(config[config_name])
#     config[config_name].init_app(app)
#     db.init_app(app)
#     init_celery(app, celery)
#     return app


