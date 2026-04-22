from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from routes import items
from utils.exceptions import (
    CustomException,
    validation_exception_handler,
    generic_exception_handler,
    custom_exception_handler
)

app = FastAPI()


app.include_router(items.router)


app.add_exception_handler(CustomException, custom_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)


@app.get("/")
def root():
    return {"status": "Connected"}