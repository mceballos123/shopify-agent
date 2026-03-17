RECEIPT_LOOKUP_QUERY = """
query shopPayPaymentRequestReceipts($sourceIdentifier: String!) {
  shopPayPaymentRequestReceipts(sourceIdentifier: $sourceIdentifier) {
    token
    processingStatusType
    paymentRequest {
      total { amount currencyCode }
      subtotal { amount currencyCode }
    }
  }
}
"""
