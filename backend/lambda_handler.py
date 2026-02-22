"""AWS Lambda handler for the FastAPI API (via Mangum)."""

from mangum import Mangum
from app.main import app

handler = Mangum(app, lifespan="off")
