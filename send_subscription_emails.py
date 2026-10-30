#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import logging
import os
import sys

from app import (
    DBHelper,
    USER_DB,
    load_cached_data,
    load_from_database,
    retrieve_research_candidates,
    serialize_recommendation,
)
from get_data.email_service import (
    build_recommendation_email,
    send_email,
    smtp_is_configured,
)


logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description='发送 DataPaper 个性化论文订阅邮件')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='只显示待发送用户和邮件标题，不连接 SMTP'
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if not USER_DB:
        logger.error('数据库工具不可用')
        return 1

    if not args.dry_run and not smtp_is_configured():
        logger.error('SMTP 配置不完整，请检查环境变量')
        return 1

    if not USER_DB.initialize_tables():
        return 1
    if not (load_from_database() or load_cached_data()):
        logger.error('没有可用于推荐的论文数据')
        return 1

    base_url = os.environ.get('APP_BASE_URL', 'http://127.0.0.1:5000')
    subscribers = USER_DB.get_due_email_subscribers()
    sent_count = 0
    skipped_count = 0
    failed_count = 0

    for user in subscribers:
        candidates = retrieve_research_candidates(user['research_field'], limit=5)
        recommendations = [serialize_recommendation(item) for item in candidates]
        if not recommendations:
            skipped_count += 1
            logger.info('跳过 %s：没有匹配论文', user['email'])
            continue

        message = build_recommendation_email(user, recommendations, base_url)
        if args.dry_run:
            sent_count += 1
            logger.info('[DRY RUN] %s -> %s', user['email'], message['Subject'])
            continue

        try:
            send_email(message)
            USER_DB.mark_subscription_email_sent(user['id'])
            sent_count += 1
            logger.info('已发送订阅邮件：%s', user['email'])
        except Exception as exception:
            failed_count += 1
            logger.error('发送给 %s 失败：%s', user['email'], exception)

    logger.info(
        '订阅邮件任务完成：待处理 %s，发送 %s，跳过 %s，失败 %s',
        len(subscribers),
        sent_count,
        skipped_count,
        failed_count,
    )
    return 1 if failed_count else 0


if __name__ == '__main__':
    sys.exit(main())
