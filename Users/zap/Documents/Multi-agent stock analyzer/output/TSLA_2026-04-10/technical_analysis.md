Error executing tool: Tool 'Technical data lookup (US market)' arguments validation failed: 1 validation error for USStockInput
ticker
  Input should be a valid string [type=string_type, input_value={'description': 'U.S. sto...tring', 'value': 'TSLA'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.11/v/string_type
Expected arguments: {"ticker": {"description": "U.S. stock ticker symbol (e.g. AAPL).", "title": "Ticker", "type": "string"}}
Required: ["ticker"]