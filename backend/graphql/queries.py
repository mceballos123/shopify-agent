from .mutations import CART_FRAGMENT

CART_QUERY = (
    CART_FRAGMENT
    + """
query getCart($id: ID!) {
  cart(id: $id) {
    ...CartFields
  }
}
"""
)
