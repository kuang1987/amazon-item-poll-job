#!/usr/bin/env python
# -*- coding:utf-8 -*- 

import smtplib  
from email.mime.multipart import MIMEMultipart  
from email.mime.text import MIMEText  
from email.mime.image import MIMEImage 
from ntlm.ntlm import *
import os,sys
import django
import base64

mypath =  os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print mypath
sys.path.append(mypath)
os.environ['DJANGO_SETTINGS_MODULE'] = 'amazon_web.settings'
from django.conf import settings
django.setup() 

mail_server = settings.MAIL_SERVER
mail_server_port = settings.MAIL_SERVER_PORT
username = settings.USERNAME
password = settings.PASSWORD 

sender = username + '@kjt.com'


def send_mail(to_list,cc_list,subject,report=None,xls_file=None,log_file=None):
    #try:
    if True:
        msg = MIMEMultipart('related')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = (';').join(to_list)
        msg['Cc'] = (';').join(cc_list)
        receiver = (';').join(to_list+cc_list)
        if xls_file: 
            att = MIMEText(open(xls_file, 'rb').read(), 'base64', 'utf-8')  
            att["Content-Type"] = 'application/octet-stream'  
            att["Content-Disposition"] = 'attachment; filename="%s"'%(os.path.basename(xls_file))  
            msg.attach(att)  
        if log_file:
            att = MIMEText(open(log_file, 'rb').read(), 'base64', 'utf-8')  
            att["Content-Type"] = 'application/octet-stream'  
            att["Content-Disposition"] = 'attachment; filename="%s"'%(os.path.basename(log_file))  
            msg.attach(att)
        if report:
            msgText =  MIMEText(report,'plain','utf-8')
            msg.attach(msgText)
              
        smtp = smtplib.SMTP(mail_server,mail_server_port)
        smtp.starttls()
        smtp.login(username, password)  
        smtp.sendmail(sender, receiver, msg.as_string())  
        smtp.quit()
        return True
    #except:
    #    return False


if __name__ == '__main__':
    to_list = []
    cc_list = []
    to_list.append('kong.xiangxiang@kjt.com')
    cc_list.append('li.ming@kjt.com')
    subject = 'python test mail'
    #content = 'test'
    report = 'test'
    print send_mail(to_list,cc_list,subject,report)

