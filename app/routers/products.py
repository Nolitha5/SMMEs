"""Products endpoints."""
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/", summary="List all active products")
def list_products(request: Request):
    monitor = request.app.state.monitor
    return {"products": monitor.get_all_products()}


@router.get("/categories", summary="List distinct product categories")
def list_categories(request: Request):
    monitor = request.app.state.monitor
    products = monitor.get_all_products()
    categories = sorted({p["category"] for p in products})
    return {"categories": categories}


@router.get("/{product_id}", summary="Get a single product by ID")
def get_product(product_id: str, request: Request):
    monitor = request.app.state.monitor
    product = monitor.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found")
    return product


@router.get("/category/{category}", summary="Products in a category")
def products_by_category(category: str, request: Request):
    monitor = request.app.state.monitor
    products = monitor.get_products_by_category(category)
    return {"category": category, "count": len(products), "products": products}
