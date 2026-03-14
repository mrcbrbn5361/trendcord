from fastapi import FastAPI

app = FastAPI()

@app.get("/products")
async def read_products():
    return []

@app.get("/users")
async def read_users():
    return []

@app.get("/price-tracking")
async def price_tracking():
    return []
