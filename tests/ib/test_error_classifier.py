"""
Unit tests for IB Error Classifier

Tests the accurate classification of IB error codes based on official documentation.
"""

import unittest
from ktrdr.ib.error_classifier import IbErrorClassifier, IbErrorType


class TestIbErrorClassifier(unittest.TestCase):
    """Test IB error classification functionality."""
    
    def test_pacing_violation_errors(self):
        """Test pacing violation error classification."""
        # Error 100: Max rate exceeded
        error_type, wait_time = IbErrorClassifier.classify(100, "Max rate of messages per second has been exceeded")
        self.assertEqual(error_type, IbErrorType.PACING_VIOLATION)
        self.assertEqual(wait_time, 60.0)
        
        # Error 420: Invalid real-time query (pacing)
        error_type, wait_time = IbErrorClassifier.classify(420, "Invalid real-time query (pacing violation)")
        self.assertEqual(error_type, IbErrorType.PACING_VIOLATION)
        self.assertEqual(wait_time, 60.0)
    
    def test_connection_errors(self):
        """Test connection error classification."""
        # Error 326: Client ID conflict
        error_type, wait_time = IbErrorClassifier.classify(326, "Client id is already in use")
        self.assertEqual(error_type, IbErrorType.CONNECTION_ERROR)
        self.assertEqual(wait_time, 2.0)
        
        # Error 502: Couldn't connect to TWS
        error_type, wait_time = IbErrorClassifier.classify(502, "Couldn't connect to TWS")
        self.assertEqual(error_type, IbErrorType.CONNECTION_ERROR)
        self.assertEqual(wait_time, 5.0)
        
        # Error 504: Not connected
        error_type, wait_time = IbErrorClassifier.classify(504, "Not connected")
        self.assertEqual(error_type, IbErrorType.CONNECTION_ERROR)
        self.assertEqual(wait_time, 2.0)
    
    def test_permission_errors(self):
        """Test permission error classification."""
        # Error 354: Market data not subscribed
        error_type, wait_time = IbErrorClassifier.classify(354, "Requested market data is not subscribed")
        self.assertEqual(error_type, IbErrorType.PERMISSION_ERROR)
        self.assertEqual(wait_time, 0.0)
        
        # Error 10197: No market data permissions
        error_type, wait_time = IbErrorClassifier.classify(10197, "No market data permissions")
        self.assertEqual(error_type, IbErrorType.PERMISSION_ERROR)
        self.assertEqual(wait_time, 0.0)
    
    def test_historical_data_errors(self):
        """Test historical data error classification (corrected from assumptions)."""
        # Error 162: Historical data service error
        error_type, wait_time = IbErrorClassifier.classify(162, "Historical Market Data Service error message")
        self.assertEqual(error_type, IbErrorType.DATA_UNAVAILABLE)
        self.assertEqual(wait_time, 0.0)
        
        # Error 165: Historical data service query
        error_type, wait_time = IbErrorClassifier.classify(165, "Historical Market Data Service query message")
        self.assertEqual(error_type, IbErrorType.DATA_UNAVAILABLE)
        self.assertEqual(wait_time, 0.0)
    
    def test_fatal_errors(self):
        """Test fatal error classification."""
        # Error 200: No security definition
        error_type, wait_time = IbErrorClassifier.classify(200, "No security definition has been found for the request")
        self.assertEqual(error_type, IbErrorType.FATAL)
        self.assertEqual(wait_time, 0.0)
    
    def test_transport_error_detection(self):
        """Test transport error detection from message content."""
        # Handler is closed
        error_type, wait_time = IbErrorClassifier.classify(999, "handler is closed")
        self.assertEqual(error_type, IbErrorType.CONNECTION_ERROR)
        self.assertEqual(wait_time, 2.0)
        
        # Transport closed
        error_type, wait_time = IbErrorClassifier.classify(888, "transport closed")
        self.assertEqual(error_type, IbErrorType.CONNECTION_ERROR)
        self.assertEqual(wait_time, 2.0)
        
        # Connection closed
        error_type, wait_time = IbErrorClassifier.classify(777, "connection closed")
        self.assertEqual(error_type, IbErrorType.CONNECTION_ERROR)
        self.assertEqual(wait_time, 2.0)
    
    def test_permission_keyword_detection(self):
        """Test permission error detection from message keywords."""
        error_type, wait_time = IbErrorClassifier.classify(999, "market data not subscribed")
        self.assertEqual(error_type, IbErrorType.PERMISSION_ERROR)
        self.assertEqual(wait_time, 0.0)
        
        error_type, wait_time = IbErrorClassifier.classify(888, "subscription required")
        self.assertEqual(error_type, IbErrorType.PERMISSION_ERROR)
        self.assertEqual(wait_time, 0.0)
    
    def test_historical_pacing_vs_unavailable(self):
        """Test distinction between historical pacing and data unavailable."""
        # Historical pacing violation
        error_type, wait_time = IbErrorClassifier.classify(999, "historical data pacing violation")
        self.assertEqual(error_type, IbErrorType.PACING_VIOLATION)
        self.assertEqual(wait_time, 60.0)
        
        # Historical data unavailable (not pacing)
        error_type, wait_time = IbErrorClassifier.classify(888, "historical data not available")
        self.assertEqual(error_type, IbErrorType.DATA_UNAVAILABLE)
        self.assertEqual(wait_time, 0.0)
    
    def test_unknown_error_default(self):
        """Test default classification for unknown errors."""
        error_type, wait_time = IbErrorClassifier.classify(9999, "Unknown error message")
        self.assertEqual(error_type, IbErrorType.RETRYABLE)
        self.assertEqual(wait_time, 5.0)
    
    def test_client_id_conflict_detection(self):
        """Test client ID conflict detection."""
        # Direct error code
        self.assertTrue(IbErrorClassifier.is_client_id_conflict("Error 326: Client ID already in use"))
        
        # Message content
        self.assertTrue(IbErrorClassifier.is_client_id_conflict("already in use"))
        
        # Not a conflict
        self.assertFalse(IbErrorClassifier.is_client_id_conflict("Connection failed"))
    
    def test_should_retry_logic(self):
        """Test retry decision logic."""
        # Should retry
        self.assertTrue(IbErrorClassifier.should_retry(IbErrorType.RETRYABLE))
        self.assertTrue(IbErrorClassifier.should_retry(IbErrorType.PACING_VIOLATION))
        self.assertTrue(IbErrorClassifier.should_retry(IbErrorType.CONNECTION_ERROR))
        
        # Should not retry
        self.assertFalse(IbErrorClassifier.should_retry(IbErrorType.FATAL))
        self.assertFalse(IbErrorClassifier.should_retry(IbErrorType.PERMISSION_ERROR))
    
    def test_is_fatal_logic(self):
        """Test fatal error detection."""
        # Fatal errors
        self.assertTrue(IbErrorClassifier.is_fatal(IbErrorType.FATAL))
        self.assertTrue(IbErrorClassifier.is_fatal(IbErrorType.PERMISSION_ERROR))
        
        # Non-fatal errors
        self.assertFalse(IbErrorClassifier.is_fatal(IbErrorType.RETRYABLE))
        self.assertFalse(IbErrorClassifier.is_fatal(IbErrorType.CONNECTION_ERROR))
        self.assertFalse(IbErrorClassifier.is_fatal(IbErrorType.PACING_VIOLATION))
        self.assertFalse(IbErrorClassifier.is_fatal(IbErrorType.DATA_UNAVAILABLE))
    
    def test_retry_delay_calculation(self):
        """Test retry delay calculation with exponential backoff."""
        # Fatal errors - no retry
        self.assertEqual(IbErrorClassifier.get_retry_delay(IbErrorType.FATAL), 0.0)
        self.assertEqual(IbErrorClassifier.get_retry_delay(IbErrorType.PERMISSION_ERROR), 0.0)
        
        # Pacing violations - fixed delay (no exponential backoff)
        self.assertEqual(IbErrorClassifier.get_retry_delay(IbErrorType.PACING_VIOLATION, 1), 60.0)
        self.assertEqual(IbErrorClassifier.get_retry_delay(IbErrorType.PACING_VIOLATION, 3), 60.0)
        
        # Connection errors - exponential backoff with cap
        self.assertEqual(IbErrorClassifier.get_retry_delay(IbErrorType.CONNECTION_ERROR, 1), 2.0)
        self.assertEqual(IbErrorClassifier.get_retry_delay(IbErrorType.CONNECTION_ERROR, 2), 4.0)
        self.assertEqual(IbErrorClassifier.get_retry_delay(IbErrorType.CONNECTION_ERROR, 3), 8.0)
        # Should cap at 60 seconds
        self.assertEqual(IbErrorClassifier.get_retry_delay(IbErrorType.CONNECTION_ERROR, 10), 60.0)
        
        # Data unavailable - no delay
        self.assertEqual(IbErrorClassifier.get_retry_delay(IbErrorType.DATA_UNAVAILABLE, 1), 0.0)
    
    def test_format_error_info(self):
        """Test error information formatting."""
        info = IbErrorClassifier.format_error_info(326, "Client id is already in use")
        
        expected_keys = {
            "error_code", "error_message", "error_type", "is_retryable", 
            "is_fatal", "suggested_wait_seconds", "classification_source"
        }
        self.assertEqual(set(info.keys()), expected_keys)
        
        self.assertEqual(info["error_code"], 326)
        self.assertEqual(info["error_message"], "Client id is already in use")
        self.assertEqual(info["error_type"], "connection")
        self.assertTrue(info["is_retryable"])
        self.assertFalse(info["is_fatal"])
        self.assertEqual(info["suggested_wait_seconds"], 2.0)
        self.assertEqual(info["classification_source"], "official_ib_documentation")


if __name__ == "__main__":
    unittest.main()