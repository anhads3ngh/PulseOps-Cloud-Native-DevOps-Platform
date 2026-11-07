"""Run FastAPI behind API Gateway HTTP API, payload format 2.0."""
from mangum import Mangum

from pulseops.api import app

handler = Mangum(app, lifespan="off")
