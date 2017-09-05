# coding: utf-8
import os
import requests
from datetime import datetime
from flask import Flask, request, current_app
from flask_sqlalchemy import SQLAlchemy
from celery.utils.log import get_task_logger
from centerway.celery_init import make_celery
from centerway.config import config
logger = get_task_logger(__name__)

app = Flask(__name__)
app.config.from_object(config[os.getenv('FLASK_CONFIG') or 'default'])
celery = make_celery(app)
db = SQLAlchemy(app)


class Centerway(db.Model):
    __tablename__ = 'centerway'
    id = db.Column(db.INTEGER, nullable=False, primary_key=True, autoincrement=True)
    app_name = db.Column(db.String(128), nullable=False)
    error_message = db.Column(db.Text, nullable=False)
    start_time = db.Column(db.DATETIME, nullable=False)
    end_time = db.Column(db.DATETIME, nullable=True, default=None)
    sustain_time = db.Column(db.INTEGER, nullable=True, default=None)
    is_problem_notice = db.Column(db.BOOLEAN, nullable=True, default=False)
    is_recovery_notice = db.Column(db.BOOLEAN, nullable=True, default=False)


@app.route('/gate', methods=['POST'])
def do():
    body = request.form
    msg = body["msgContent"]
    msg_list = msg.split(' ')
    is_no_live_upstreams = 'no live upstreams' in msg
    time = datetime.strptime(' '.join(msg_list[0:2]), '%Y/%m/%d %H:%M:%S')
    if is_no_live_upstreams:
        appname = msg_list[-3].split('/')[2]

    centerway = Centerway.query.filter_by(app_name=appname, is_recovery_notice=False).first()
    if centerway:
        centerway.end_time = time
    else:
        db.session.add(Centerway(app_name=appname, error_message='no live upstreams', start_time=time, end_time=time))
    db.session.commit()

    return ''


@celery.task(name="check_recovery")
def update():
    rs = Centerway.query.filter_by(is_recovery_notice=False).all()
    for r in rs:
        if (datetime.now() - r.end_time).total_seconds() >= 300:
            sustain_time = (r.end_time - r.start_time).total_seconds() / 60
            r.is_recovery_notice = True
            msg = r.app_name + "于" + datetime.strftime(r.end_time, '%Y%m%d %H:%M:%S') + \
                  "恢复, 持续时间:" + str(sustain_time) + "分钟."
            send_msg(msg, current_app.config.get("RECEIVERS"))
            db.session.commit()


@celery.task(name="check_problem")
def alert_active():
    rs = Centerway.query.filter_by(is_problem_notice=False).all()
    for r in rs:
        msg = r.app_name + "在" + datetime.strftime(r.start_time, '%Y%m%d %H:%M:%S') + "发生故障!"
        send_msg(msg, current_app.config.get("RECEIVERS"))
        r.is_problem_notice = True
        db.session.commit()


def send_msg(msg, receivers):
    for receiver in receivers:
        requests.post('http://www.xiaoerzuche.com/web/smsMsg/sendMsg.ihtml',
                      data={"msgPhone": receiver, "msgContent": msg})

if __name__ == '__main__':
    db.create_all()
    app.run('0.0.0.0', 5555, True)
