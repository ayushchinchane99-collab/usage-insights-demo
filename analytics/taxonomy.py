"""Semantic action taxonomy for the sample checkout application.

Every user action is described by a business-readable name, a plain-language
description, the product feature it belongs to, and (for the main task) its
position in the expected "happy path". Raw clicks are never analysed directly;
they are always mapped to one of these semantic actions first.
"""

TASK = "checkout"

# Ordered happy path of the main task: from browsing to a confirmed order.
HAPPY_PATH = [
    "view_product_list",
    "view_product",
    "add_to_cart",
    "view_cart",
    "start_checkout",
    "enter_shipping",
    "enter_payment",
    "submit_order",
]

# Detours that are not errors, but that deviate from the happy path.
DETOUR_ACTIONS = ["remove_from_cart", "back_to_cart"]

ACTIONS = {
    "view_product_list": {
        "description": "User opened the product catalogue",
        "feature": "catalogue",
    },
    "search_products": {
        "description": "User searched the catalogue with a text query",
        "feature": "search",
    },
    "apply_filter": {
        "description": "User filtered the catalogue by category or price",
        "feature": "filter",
    },
    "view_product": {
        "description": "User opened a product detail page",
        "feature": "catalogue",
    },
    "add_to_wishlist": {
        "description": "User saved a product to the wishlist",
        "feature": "wishlist",
    },
    "add_to_cart": {
        "description": "User added a product to the shopping cart",
        "feature": "cart",
    },
    "view_cart": {
        "description": "User opened the shopping cart",
        "feature": "cart",
    },
    "remove_from_cart": {
        "description": "User removed a product from the shopping cart",
        "feature": "cart",
    },
    "apply_promo_code": {
        "description": "User entered a promotion code in the cart",
        "feature": "promo_code",
    },
    "start_checkout": {
        "description": "User started the checkout process",
        "feature": "checkout",
    },
    "enter_shipping": {
        "description": "User completed the shipping address form",
        "feature": "checkout",
    },
    "back_to_cart": {
        "description": "User went back from checkout to the cart",
        "feature": "cart",
    },
    "enter_payment": {
        "description": "User completed the payment details form",
        "feature": "checkout",
    },
    "submit_order": {
        "description": "User submitted the order; the task is completed",
        "feature": "checkout",
    },
}

# Actions that exist in the application but that the instrumentation does NOT
# cover (a deliberate gap used to demonstrate gap analysis).
UNINSTRUMENTED = {"apply_promo_code"}

FEATURES = sorted({a["feature"] for a in ACTIONS.values()})


def describe(action: str) -> str:
    return ACTIONS[action]["description"]


def feature_of(action: str) -> str:
    return ACTIONS[action]["feature"]
