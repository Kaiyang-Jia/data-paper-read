"""Local API entrypoint; authentic snapshot fallback, never fabricated papers."""
import os
os.environ.setdefault('USE_LOCAL_USER_DB', 'true')
import app as app_module

if __name__ == '__main__':
    if app_module.USER_DB:
        app_module.USER_DB.initialize_tables()
    if not app_module.load_from_database():
        app_module.load_cached_data()
    app_module.app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)
