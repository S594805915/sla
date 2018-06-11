# coding: utf-8
import os
import requests
import datetime as dt
import calendar
from datetime import datetime
from flask import Flask, request, current_app, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from celery.utils.log import get_task_logger
from celery_init import make_celery
from config import config
import xlsxwriter
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from raven.contrib.flask import Sentry
logger = get_task_logger(__name__)

app = Flask(__name__)
app.config.from_object(config[os.getenv('FLASK_CONFIG') or 'default'])
celery = make_celery(app)
db = SQLAlchemy(app)
sentry = Sentry(app, dsn='https://60e2471c95df406a969e51560520b7c6:261e38a54e6d496faf82621fe6437dd7@sentry.95071222.net/18')


class Centerway(db.Model):
    __tablename__ = 'centerway'
    id = db.Column(db.INTEGER, nullable=False, primary_key=True, autoincrement=True)
    app_name = db.Column(db.String(128), nullable=False)
    error_message = db.Column(db.Text, nullable=False)
    start_time = db.Column(db.DATETIME, nullable=False)
    end_time = db.Column(db.DATETIME, nullable=True, default=None)
    sustain_time = db.Column(db.INTEGER, nullable=True, default=None)
    calls = db.Column(db.INTEGER, nullable=True)
    is_sustain_notice = db.Column(db.BOOLEAN, nullable=True, default=False)
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
        centerway.is_sustain_notice = False
    else:
        db.session.add(Centerway(app_name=appname,
                                 error_message='no live upstreams', start_time=time, end_time=time, calls=1))
    db.session.commit()

    return ''


# @app.route('/stats', methods=['POST'])
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


def sustime_format(seconds):
    if not seconds:
        seconds = 0
    minite = int(seconds / 60)
    second = seconds % 60
    return str(minite) + "分钟" + str(second) + "秒."


@celery.task(name="check_recovery")
def update():
    rs = Centerway.query.filter_by(is_recovery_notice=False).all()
    for r in rs:
        sustain_time = int((r.end_time - r.start_time).total_seconds())

        if (datetime.now() - r.end_time).total_seconds() > 300:
            msg = r.app_name + "于" + datetime.strftime(r.end_time, '%Y%m%d %H:%M:%S') + \
                  "恢复, 故障持续时间:" + sustime_format(sustain_time)
            send_msg(msg, current_app.config.get("RECEIVERS"))
            r.is_recovery_notice = True
            r.sustain_time = sustain_time
            db.session.commit()
            continue
            
        if not r.is_problem_notice:
            msg = r.app_name + "在" + datetime.strftime(r.start_time, '%Y%m%d %H:%M:%S') + "发生故障!"
            send_msg(msg, current_app.config.get("RECEIVERS"))
            r.is_problem_notice = True
            r.sustain_time = sustain_time
            db.session.commit()
            continue

        if int(sustain_time / 60 ) % 5 == 0 and int(sustain_time / 60 ) != int(r.sustain_time / 60 ) \
               and not r.is_sustain_notice and r.is_problem_notice:
            msg = r.app_name + "已经故障了" + sustime_format(sustain_time)
            send_msg(msg, current_app.config.get("RECEIVERS"))
            r.sustain_time = sustain_time
            r.is_sustain_notice = True
            db.session.commit()


@celery.task(name="health_report")
def health_report():
    yesterday = datetime.today() - dt.timedelta(1)
    suffix = "_sla.xlsx"

    _, last_day_num = calendar.monthrange(yesterday.year, yesterday.month)
    last_day_of_month = dt.date(yesterday.year, yesterday.month, last_day_num)
    first_day_of_month = dt.date(yesterday.year, yesterday.month, 1)

    file_name = yesterday.strftime('%Y%m%d')
    generate_report(filename=file_name, start_time=yesterday, end_time=yesterday, suffix=suffix)

    if yesterday.weekday() == 6:
        last_sunday = yesterday - dt.timedelta(6)
        file_name = last_sunday.strftime('%Y%m%d') + "-" + yesterday.strftime('%Y%m%d')
        generate_report(filename=file_name, start_time=last_sunday, end_time=yesterday, suffix=suffix)
    if last_day_of_month == yesterday.date():
        file_name = yesterday.strftime('%Y%m')
        generate_report(filename=file_name, start_time=first_day_of_month, end_time=last_day_of_month, suffix=suffix)


def generate_report(filename, start_time, end_time, suffix):
    centerway = Centerway.query.with_entities(Centerway.app_name,
                                              func.sum(Centerway.calls).label('failed_calls'),
                                              func.sum(Centerway.sustain_time).label('sustain_time')).\
        filter(Centerway.start_time >= start_time.strftime('%Y-%m-%d 00:00:00'),
               Centerway.start_time <= end_time.strftime('%Y-%m-%d 23:59:59')
               ).group_by(Centerway.app_name)\
        .all()

    write_excel(filename, centerway, suffix)
    send_doc_by_email(filename, suffix)


def write_excel(filename, rs, suffix):
    workbook = xlsxwriter.Workbook(filename + suffix)
    worksheet = workbook.add_worksheet(filename)
    worksheet.set_column(0, 0, 20)
    worksheet.set_column(1, 3, 12)
    worksheet.set_column(6, 10, 20)
    # 每列的title
    cols_title = ("应用名称", "请求失败数(个)", "不可用时长")
    row, col = 0, 0
    for title in cols_title:
        worksheet.write(row, col, title)
        col += 1

    row, col = 1, 0
    for r in rs:
        worksheet.write(row, col, r[0])
        worksheet.write(row, col + 1, r[1])
        worksheet.write(row, col + 2, sustime_format(r[2]))
        row += 1
        col = 0
    workbook.close()


def send_doc_by_email(filename, suffix):
    msg = MIMEMultipart()  # 创建一个可带附件的实例
    attachment = open(filename + suffix, "rb")
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(attachment.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', "attachment; filename = % s" % filename + suffix)

    msg['Subject'] = filename + "SLA报告"
    # msg.attach(MIMEText("附件是最新里程为0公里的订单信息", 'plain'))
    msg.attach(part)
    text = msg.as_string()

    server = smtplib.SMTP(current_app.config.get("EMAIL_SERVER"), current_app.config.get("EMAIL_SERVER_PORT"))
    server.login(current_app.config.get("EMAIL_FROM"), current_app.config.get("EMAIL_PASS"))
    server.sendmail(current_app.config.get("EMAIL_FROM"), current_app.config.get("USER_EMAILS"), text)


def send_msg(msg, receivers):
    for receiver in receivers:
        requests.post('http://www.xiaoerzuche.com/web/smsMsg/sendMsg.ihtml',
                      data={"msgPhone": receiver, "msgContent": msg})

if __name__ == '__main__':
    db.create_all()
    health_report()
    app.run('0.0.0.0', 50001, 'DEBUG')
