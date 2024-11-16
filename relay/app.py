import asyncio
import websockets
import json
from websockets.exceptions import ConnectionClosed


JETSTREAM_URL = "wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post"
connected_clients = set()

async def forward_messages():
    """Connects to Bluesky Jetstream and forwards messages to all connected clients."""
    while True:
        try:
            async with websockets.connect(JETSTREAM_URL) as jetstream:
           
                while True:
                    try:
                        message = await jetstream.recv()
                        # Forward the message to all connected clients
                        if connected_clients:
                            await asyncio.gather(
                                *[client.send(message) for client in connected_clients],
                                return_exceptions=True
                            )
                    except ConnectionClosed:
                         break
                    except Exception as e:
                        continue
                        
        except Exception as e:
            await asyncio.sleep(5)  # Wait before reconnecting

async def handle_client(websocket, path):
    """Handles individual WebSocket client connections."""
    try:
        connected_clients.add(websocket)
        
        try:
            # Keep the connection alive until the client disconnects
            await websocket.wait_closed()
        finally:
            connected_clients.remove(websocket)
            
    except Exception as e:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

async def main():
    """Main function to start the WebSocket server."""
    # Start the Jetstream connection in the background
    asyncio.create_task(forward_messages())
    
    # Start the WebSocket server
    async with websockets.serve(handle_client, "0.0.0.0", 8765):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server shutdown requested")
    except Exception as e:
        print("err")