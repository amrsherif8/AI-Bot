from workers import asgi
from main import app

# Cloudflare Workers ASGI entry point
Default = asgi.entrypoint(app)
