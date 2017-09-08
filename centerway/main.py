# coding: utf-8
import os
import time
import requests
from datetime import datetime
from flask import Flask, request, current_app, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
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
    calls = db.Column(db.INTEGER, nullable=True)
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
        calls = centerway.calls + 1
        centerway.end_time = time
        centerway.calls = calls
    else:
        db.session.add(Centerway(app_name=appname,
                                 error_message='no live upstreams', start_time=time, end_time=time, calls=1))
    db.session.commit()

    return ''


@app.route('/stats', methods=['POST'])
def stats():
    data = request.get_json()
    appname = data["app_name"]
    start = datetime.strptime(data["start_time"], '%Y/%m/%d %H:%M:%S')
    end = datetime.strptime(data["end_time"], '%Y/%m/%d %H:%M:%S')
    if appname:
        centerway = Centerway.query.filter_by(app_name=appname).\
            filter(Centerway.start_time >= start, Centerway.end_time <= end).all()
    else:
        centerway = Centerway.query.with_entities(Centerway.app_name,
                                                  func.sum(Centerway.sustain_time).label('sustain_time')).\
            filter(Centerway.start_time >= start, Centerway.end_time <= end).group_by(Centerway.app_name).all()
    count = len(centerway)
    return jsonify(centerway)


@celery.task(name="check_recovery")
def update():
    rs = Centerway.query.filter_by(is_recovery_notice=False).all()
    for r in rs:
        sustain_time = int((r.end_time - r.start_time).total_seconds() / 60)
        r.sustain_time = sustain_time
        if (datetime.now() - r.end_time).total_seconds() >= 240:
            r.is_recovery_notice = True
            msg = r.app_name + "于" + datetime.strftime(r.end_time, '%Y%m%d %H:%M:%S') + \
                  "恢复, 持续时间:" + str(sustain_time) + "分钟."
            send_msg(msg, current_app.config.get("RECEIVERS"))

        if sustain_time and sustain_time % 5 == 0:
            msg = r.app_name + "已经故障了" + str(sustain_time) + "分钟."
            send_msg(msg, current_app.config.get("RECEIVERS"))
        db.session.commit()


@celery.task(name="check_problem")
def alert_active():
    rs = Centerway.query.filter_by(is_problem_notice=False)
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
