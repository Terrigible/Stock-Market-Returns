from werkzeug.middleware.profiler import ProfilerMiddleware

from returns_dashboard import app

if __name__ == "__main__":
    app.server.wsgi_app = ProfilerMiddleware(
        app.server.wsgi_app, restrictions=[30], profile_dir="./profiles"
    )
    app.run()
