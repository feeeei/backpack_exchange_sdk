import json
import threading
import time
from typing import Callable, Dict, List, Optional
import websocket

class WebSocketClient:
    """
    WebSocket client for Backpack Exchange.
    Handles real-time data streams including market data, account updates, and trading information.
    """
    def __init__(self, api_key: str = None, secret_key: str = None):
        """
        Initialize WebSocket client.
        
        Args:
            api_key (str, optional): API key for authenticated streams
            secret_key (str, optional): Secret key for authenticated streams
        """
        self.ws = None
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = "wss://ws.backpack.exchange"
        self.callbacks: Dict[str, List[Callable]] = {}
        self._connect()

    def _connect(self):
        """
        Establish WebSocket connection and set up event handlers.
        Includes automatic reconnection on connection loss.
        """
        def on_message(ws, message):
            """Handle incoming WebSocket messages"""
            try:
                data = json.loads(message)
                stream = data.get("stream")
                if stream and stream in self.callbacks:
                    for callback in self.callbacks[stream]:
                        callback(data["data"])
            except Exception as e:
                print(f"Error processing message: {e}")

        def on_error(ws, error):
            """Handle WebSocket errors"""
            print(f"WebSocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            """Handle WebSocket connection closure and implement reconnection"""
            print("WebSocket connection closed")
            time.sleep(5)  # Wait before reconnecting
            self._connect()

        def on_open(ws):
            """Handle WebSocket connection establishment"""
            print("WebSocket connection established")
            
        def on_ping(ws, message):
            """Respond to ping messages to maintain connection"""
            ws.send_pong(message)

        # Initialize WebSocket connection with handlers
        self.ws = websocket.WebSocketApp(
            self.base_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open,
            on_ping=on_ping
        )

        # Start WebSocket connection in a separate thread
        wst = threading.Thread(target=self.ws.run_forever)
        wst.daemon = True
        wst.start()

    def _generate_signature(self, streams: List[str], timestamp: int, window: int = 5000) -> Dict[str, str]:
        """
        Generate authentication signature for private streams.
        
        Args:
            streams (List[str]): List of stream names to subscribe to
            timestamp (int): Current timestamp in milliseconds
            window (int): Signature validity window in milliseconds
            
        Returns:
            Dict[str, str]: Authentication headers
        """
        if not self.api_key or not self.secret_key:
            return {}
            
        sign_str = f"instruction=subscribe&timestamp={timestamp}&window={window}"
        signature = self._sign_message(sign_str)
        
        return {
            "api-key": self.api_key,
            "signature": signature,
            "timestamp": str(timestamp),
            "window": str(window)
        }

    def subscribe(self, streams: List[str], callback: Callable, is_private: bool = False):
        """
        Subscribe to one or more data streams.
        
        Args:
            streams (List[str]): List of stream names to subscribe to
            callback (Callable): Function to handle incoming messages
            is_private (bool): Whether these are private authenticated streams
        """
        # Register callbacks for each stream
        for stream in streams:
            if stream not in self.callbacks:
                self.callbacks[stream] = []
            self.callbacks[stream].append(callback)

        # Prepare subscription message
        subscribe_data = {
            "method": "SUBSCRIBE",
            "params": streams
        }

        # Add authentication for private streams
        if is_private:
            timestamp = int(time.time() * 1000)
            auth_data = self._generate_signature(streams, timestamp)
            subscribe_data["signature"] = [
                auth_data["api-key"],
                auth_data["signature"],
                auth_data["timestamp"],
                auth_data["window"]
            ]

        # Send subscription request
        self.ws.send(json.dumps(subscribe_data))

    def unsubscribe(self, streams: List[str]):
        """
        Unsubscribe from one or more data streams.
        
        Args:
            streams (List[str]): List of stream names to unsubscribe from
        """
        unsubscribe_data = {
            "method": "UNSUBSCRIBE",
            "params": streams
        }
        self.ws.send(json.dumps(unsubscribe_data))
        
        # Remove callbacks for unsubscribed streams
        for stream in streams:
            if stream in self.callbacks:
                del self.callbacks[stream]

    def close(self):
        """Close the WebSocket connection"""
        if self.ws:
            self.ws.close() 