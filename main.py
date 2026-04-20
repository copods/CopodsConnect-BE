from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from routes import items
from core.exceptions import (
    validation_exception_handler,
    generic_exception_handler
)

app = FastAPI()

# Register routes
app.include_router(items.router)

# Register exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)


@app.get("/")
def root():
    return {"status": "Connected"}