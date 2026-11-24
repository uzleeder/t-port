"""Vercel ASGI entrypoint. Database setup runs as an explicit release step, never on cold starts."""

from app.core.config import Settings
from app.main import create_app

# Preview deployments also have real accounts and HTTPS: never enable development cookies
# or test providers merely because an environment variable was omitted.
app = create_app(Settings(environment="production"), seed=False)
