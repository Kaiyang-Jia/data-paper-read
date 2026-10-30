#!/usr/bin/env python
# -*- coding: utf-8 -*-

import html
import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import quote


def smtp_is_configured():
    return all([
        os.environ.get('SMTP_HOST'),
        os.environ.get('SMTP_USERNAME'),
        os.environ.get('SMTP_PASSWORD'),
        os.environ.get('SMTP_FROM_EMAIL'),
    ])


def build_recommendation_email(user, recommendations, base_url):
    frequency_label = '每日' if user.get('email_frequency') == 'daily' else '每周'
    subject = f"DataPaper {frequency_label}论文推荐：{user.get('research_field', '')[:30]}"
    unsubscribe_url = (
        f"{base_url.rstrip('/')}/unsubscribe/"
        f"{quote(str(user.get('unsubscribe_token', '')), safe='')}"
    )

    paper_text_parts = []
    paper_html_parts = []
    for paper in recommendations:
        title = paper.get('titleCn') or paper.get('title') or '未命名论文'
        paper_url = paper.get('url') or (
            f"https://doi.org/{paper.get('doi')}" if paper.get('doi') else base_url
        )
        reason = paper.get('reason') or '与你的研究领域相关。'
        metadata = ' · '.join(filter(None, [
            paper.get('journal'),
            paper.get('publishDate'),
            paper.get('Subject'),
        ]))
        paper_text_parts.append(
            f"- {title}\n  {metadata}\n  {reason}\n  {paper_url}"
        )
        paper_html_parts.append(f"""
            <article style="margin:0 0 18px;padding:18px;border:1px solid #e4e6ef;border-radius:12px;">
                <div style="color:#8c90a3;font-size:12px;">{html.escape(metadata)}</div>
                <h2 style="margin:8px 0;font-size:18px;line-height:1.5;">
                    {html.escape(title)}
                </h2>
                <p style="margin:0 0 12px;color:#5f6378;">{html.escape(reason)}</p>
                <a href="{html.escape(paper_url, quote=True)}"
                   style="color:#5b5ce2;font-weight:600;text-decoration:none;">查看论文</a>
            </article>
        """)

    text_body = (
        f"{user.get('display_name', '研究者')}，你好：\n\n"
        f"以下是根据你的研究领域“{user.get('research_field', '')}”匹配的论文：\n\n"
        f"{chr(10).join(paper_text_parts)}\n\n"
        f"管理或取消订阅：{unsubscribe_url}\n"
    )
    html_body = f"""
        <!doctype html>
        <html lang="zh-CN">
        <body style="margin:0;background:#f7f8fc;color:#17182b;font-family:Arial,'Microsoft YaHei',sans-serif;">
            <div style="max-width:680px;margin:0 auto;padding:30px 18px;">
                <div style="margin-bottom:20px;font-size:20px;font-weight:700;color:#5b5ce2;">DataPaper</div>
                <div style="padding:26px;background:#fff;border-radius:16px;">
                    <h1 style="margin:0 0 10px;font-size:24px;">你的{frequency_label}论文推荐</h1>
                    <p style="margin:0 0 24px;color:#5f6378;">
                        根据研究领域“{html.escape(user.get('research_field', ''))}”为你匹配。
                    </p>
                    {''.join(paper_html_parts)}
                </div>
                <p style="margin:18px 0;text-align:center;color:#8c90a3;font-size:12px;">
                    不想继续收到邮件？<a href="{html.escape(unsubscribe_url, quote=True)}"
                    style="color:#5b5ce2;">管理或取消订阅</a>
                </p>
            </div>
        </body>
        </html>
    """

    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = os.environ.get('SMTP_FROM_NAME', 'DataPaper') + (
        f" <{os.environ.get('SMTP_FROM_EMAIL')}>" if os.environ.get('SMTP_FROM_EMAIL') else ''
    )
    message['To'] = user['email']
    message.set_content(text_body)
    message.add_alternative(html_body, subtype='html')
    return message


def send_email(message):
    host = os.environ.get('SMTP_HOST')
    port = int(os.environ.get('SMTP_PORT', '465'))
    username = os.environ.get('SMTP_USERNAME')
    password = os.environ.get('SMTP_PASSWORD')
    use_ssl = os.environ.get('SMTP_USE_SSL', 'true').lower() == 'true'

    if not smtp_is_configured():
        raise RuntimeError('SMTP 配置不完整')

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context()) as server:
            server.login(username, password)
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(username, password)
            server.send_message(message)
