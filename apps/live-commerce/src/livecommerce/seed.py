from __future__ import annotations

from .models import ProductCreate
from .store import Store


DEMO_PRODUCTS = [
    ProductCreate(
        sku="SKU-AURORA-LAMP",
        title="Aurora Desk Lamp",
        description="Adjustable desk lamp with three brightness modes.",
        price_minor=7900,
        currency="USD",
        inventory=40,
        image_url="/static/product-lamp.svg",
    ),
    ProductCreate(
        sku="SKU-CLOUD-MUG",
        title="Cloud Ceramic Mug",
        description="350 ml ceramic mug with a matte finish.",
        price_minor=2400,
        currency="USD",
        inventory=120,
        image_url="/static/product-mug.svg",
    ),
    ProductCreate(
        sku="SKU-TRAVEL-SPEAKER",
        title="Pocket Travel Speaker",
        description="Compact rechargeable speaker for indoor and outdoor use.",
        price_minor=5900,
        currency="USD",
        inventory=65,
        image_url="/static/product-speaker.svg",
    ),
]


def seed_products(store: Store) -> list[dict[str, object]]:
    return store.upsert_products(DEMO_PRODUCTS)
