"""Bound paid model concurrency; always release slots even on provider failure."""
from functools import wraps
from threading import BoundedSemaphore
from flask import jsonify

_slots = BoundedSemaphore(2)


def bounded_research(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not _slots.acquire(blocking=False):
            response = jsonify({'status': 'error', 'message': '当前研究请求较多，请稍后重试。'})
            response.headers['Retry-After'] = '15'
            return response, 429
        try:
            return view(*args, **kwargs)
        finally:
            _slots.release()
    return wrapped
