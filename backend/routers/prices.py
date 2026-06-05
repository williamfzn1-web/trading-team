from fastapi import APIRouter
from services.price_feed import get_current_prices

router = APIRouter()


@router.get("/")
def get_prices():
    return get_current_prices()
