"""
Example requests for the indicators API.

This module provides examples for using the indicators API endpoints.
"""
import json

# Example 1: List all available indicators
LIST_INDICATORS_EXAMPLE = {
    "url": "/api/v1/indicators",
    "method": "GET",
    "description": "List all available indicators with their metadata",
    "response_example": {
        "success": True,
        "data": [
            {
                "id": "RSIIndicator",
                "name": "RSI",
                "description": "Relative Strength Index measures the speed and change of price movements.",
                "type": "momentum",
                "parameters": [
                    {
                        "name": "period",
                        "type": "int",
                        "description": "The period over which to calculate RSI",
                        "default": 14,
                        "min_value": 2,
                        "max_value": 100,
                        "options": None
                    },
                    {
                        "name": "source",
                        "type": "str",
                        "description": "The price data to use for calculation",
                        "default": "close",
                        "min_value": None,
                        "max_value": None,
                        "options": ["close", "open", "high", "low"]
                    }
                ],
                "resources": None
            },
            {
                "id": "SMA",
                "name": "Simple Moving Average",
                "description": "Simple Moving Average calculates the average of a selected range of prices.",
                "type": "trend",
                "parameters": [
                    {
                        "name": "period",
                        "type": "int",
                        "description": "The period over which to calculate the average",
                        "default": 20,
                        "min_value": 1,
                        "max_value": 500,
                        "options": None
                    },
                    {
                        "name": "source",
                        "type": "str",
                        "description": "The price data to use for calculation",
                        "default": "close",
                        "min_value": None,
                        "max_value": None,
                        "options": ["close", "open", "high", "low"]
                    }
                ],
                "resources": None
            }
        ]
    }
}

# Example 2: Calculate a single indicator
CALCULATE_SINGLE_INDICATOR_EXAMPLE = {
    "url": "/api/v1/indicators/calculate",
    "method": "POST",
    "description": "Calculate RSI indicator for AAPL on 1-day timeframe",
    "request_example": {
        "symbol": "AAPL",
        "timeframe": "1d",
        "indicators": [
            {
                "id": "RSIIndicator",
                "parameters": {
                    "period": 14,
                    "source": "close"
                }
            }
        ],
        "start_date": "2023-01-01",
        "end_date": "2023-01-31"
    },
    "response_example": {
        "success": True,
        "dates": [
            "2023-01-01 00:00:00",
            "2023-01-02 00:00:00",
            "2023-01-03 00:00:00",
            # ... more dates
        ],
        "indicators": {
            "RSI_14": [
                45.23,
                52.87,
                48.12,
                # ... more values
            ]
        },
        "metadata": {
            "symbol": "AAPL",
            "timeframe": "1d",
            "start_date": "2023-01-01 00:00:00",
            "end_date": "2023-01-31 00:00:00",
            "points": 21,
            "total_items": 21,
            "total_pages": 1,
            "current_page": 1,
            "page_size": 1000,
            "has_next": False,
            "has_prev": False
        }
    }
}

# Example 3: Calculate multiple indicators with pagination
CALCULATE_MULTIPLE_INDICATORS_EXAMPLE = {
    "url": "/api/v1/indicators/calculate?page=1&page_size=100",
    "method": "POST",
    "description": "Calculate multiple indicators (RSI and SMA) with pagination",
    "request_example": {
        "symbol": "AAPL",
        "timeframe": "1d",
        "indicators": [
            {
                "id": "RSIIndicator",
                "parameters": {
                    "period": 14,
                    "source": "close"
                },
                "output_name": "RSI"
            },
            {
                "id": "SMA",
                "parameters": {
                    "period": 20,
                    "source": "close"
                },
                "output_name": "SMA20"
            },
            {
                "id": "SMA",
                "parameters": {
                    "period": 50,
                    "source": "close"
                },
                "output_name": "SMA50"
            }
        ],
        "start_date": "2023-01-01",
        "end_date": "2023-03-31"
    },
    "response_example": {
        "success": True,
        "dates": [
            "2023-01-01 00:00:00",
            "2023-01-02 00:00:00",
            # ... more dates (up to page_size)
        ],
        "indicators": {
            "RSI": [
                45.23,
                52.87,
                # ... more values
            ],
            "SMA20": [
                142.56,
                143.12,
                # ... more values
            ],
            "SMA50": [
                138.92,
                139.45,
                # ... more values
            ]
        },
        "metadata": {
            "symbol": "AAPL",
            "timeframe": "1d",
            "start_date": "2023-01-01 00:00:00",
            "end_date": "2023-03-31 00:00:00",
            "points": 64,
            "total_items": 64,
            "total_pages": 1,
            "current_page": 1,
            "page_size": 100,
            "has_next": False,
            "has_prev": False
        }
    }
}

# Example 4: Handle error cases
ERROR_EXAMPLES = [
    {
        "description": "Invalid timeframe error",
        "request_example": {
            "symbol": "AAPL",
            "timeframe": "invalid",  # Invalid timeframe
            "indicators": [
                {
                    "id": "RSIIndicator",
                    "parameters": {
                        "period": 14
                    }
                }
            ]
        },
        "response_example": {
            "detail": {
                "loc": ["body", "timeframe"],
                "msg": "Timeframe must be one of ['1m', '5m', '15m', '30m', '1h', '2h', '4h', '1d', '1w', '1M']",
                "type": "value_error"
            }
        },
        "status_code": 422
    },
    {
        "description": "Unknown indicator error",
        "request_example": {
            "symbol": "AAPL",
            "timeframe": "1d",
            "indicators": [
                {
                    "id": "UnknownIndicator",  # Unknown indicator
                    "parameters": {}
                }
            ]
        },
        "response_example": {
            "success": False,
            "error": {
                "code": "CONFIG-UnknownIndicator",
                "message": "Unknown indicator: UnknownIndicator",
                "details": {
                    "indicator_id": "UnknownIndicator"
                }
            }
        },
        "status_code": 400
    },
    {
        "description": "No data available error",
        "request_example": {
            "symbol": "NONEXISTENT",  # Symbol doesn't exist
            "timeframe": "1d",
            "indicators": [
                {
                    "id": "RSIIndicator",
                    "parameters": {
                        "period": 14
                    }
                }
            ]
        },
        "response_example": {
            "success": False,
            "error": {
                "code": "DATA-NoData",
                "message": "No data available for NONEXISTENT (1d)",
                "details": {
                    "symbol": "NONEXISTENT",
                    "timeframe": "1d"
                }
            }
        },
        "status_code": 404
    }
]

# Print formatted examples for documentation
if __name__ == "__main__":
    print("# Indicator API Examples\n")
    
    # List indicators example
    print("## List Available Indicators\n")
    print(f"**URL:** `{LIST_INDICATORS_EXAMPLE['url']}`")
    print(f"**Method:** `{LIST_INDICATORS_EXAMPLE['method']}`")
    print(f"**Description:** {LIST_INDICATORS_EXAMPLE['description']}\n")
    print("**Response:**")
    print("```json")
    print(json.dumps(LIST_INDICATORS_EXAMPLE['response_example'], indent=2))
    print("```\n")
    
    # Calculate single indicator example
    print("## Calculate Single Indicator\n")
    print(f"**URL:** `{CALCULATE_SINGLE_INDICATOR_EXAMPLE['url']}`")
    print(f"**Method:** `{CALCULATE_SINGLE_INDICATOR_EXAMPLE['method']}`")
    print(f"**Description:** {CALCULATE_SINGLE_INDICATOR_EXAMPLE['description']}\n")
    print("**Request:**")
    print("```json")
    print(json.dumps(CALCULATE_SINGLE_INDICATOR_EXAMPLE['request_example'], indent=2))
    print("```\n")
    print("**Response:**")
    print("```json")
    print(json.dumps(CALCULATE_SINGLE_INDICATOR_EXAMPLE['response_example'], indent=2))
    print("```\n")
    
    # Calculate multiple indicators example
    print("## Calculate Multiple Indicators with Pagination\n")
    print(f"**URL:** `{CALCULATE_MULTIPLE_INDICATORS_EXAMPLE['url']}`")
    print(f"**Method:** `{CALCULATE_MULTIPLE_INDICATORS_EXAMPLE['method']}`")
    print(f"**Description:** {CALCULATE_MULTIPLE_INDICATORS_EXAMPLE['description']}\n")
    print("**Request:**")
    print("```json")
    print(json.dumps(CALCULATE_MULTIPLE_INDICATORS_EXAMPLE['request_example'], indent=2))
    print("```\n")
    print("**Response:**")
    print("```json")
    print(json.dumps(CALCULATE_MULTIPLE_INDICATORS_EXAMPLE['response_example'], indent=2))
    print("```\n")
    
    # Error examples
    print("## Error Examples\n")
    for i, error in enumerate(ERROR_EXAMPLES, 1):
        print(f"### Error Example {i}: {error['description']}\n")
        print("**Request:**")
        print("```json")
        print(json.dumps(error['request_example'], indent=2))
        print("```\n")
        print(f"**Status Code:** {error['status_code']}")
        print("**Response:**")
        print("```json")
        print(json.dumps(error['response_example'], indent=2))
        print("```\n")