from .mutations import CART_FRAGMENT

SHOP_QUERY = """
query getShop {
  shop {
    name
    description
  }
}
"""

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

PRODUCTS_QUERY = """
query getProducts($first: Int!, $after: String) {
  products(first: $first, after: $after) {
    edges {
      cursor
      node {
        id
        title
        description
        handle
        featuredImage {
          url(transform: { maxWidth: 400, maxHeight: 400 })
          altText
          width
          height
        }
        images(first: 5) {
          edges {
            node {
              url(transform: { maxWidth: 400, maxHeight: 400 })
              altText
              width
              height
            }
          }
        }
        priceRange {
          minVariantPrice {
            amount
            currencyCode
          }
          maxVariantPrice {
            amount
            currencyCode
          }
        }
        variants(first: 10) {
          edges {
            node {
              id
              title
              price {
                amount
                currencyCode
              }
              availableForSale
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""
