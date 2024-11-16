import asyncio
import websockets
import json
from websockets.exceptions import ConnectionClosed
from datetime import datetime
from aiohttp import web
import logging

JETSTREAM_URL = "wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post"
connected_clients = set()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Track server status
server_status = {
    "start_time": None,
    "last_jetstream_message": None,
    "connected_clients": 0,
    "is_jetstream_connected": False
}

async def forward_messages():
    """Connects to Bluesky Jetstream and forwards messages to all connected clients."""
    while True:
        try:
            async with websockets.connect(JETSTREAM_URL) as jetstream:
                server_status["is_jetstream_connected"] = True
                logger.info("Connected to Jetstream")
                
                while True:
                    try:
                        message = await jetstream.recv()
                        server_status["last_jetstream_message"] = datetime.utcnow().isoformat()
                        
                        # Forward the message to all connected clients
                        if connected_clients:
                            await asyncio.gather(
                                *[client.send(message) for client in connected_clients],
                                return_exceptions=True
                            )
                    except ConnectionClosed:
                        server_status["is_jetstream_connected"] = False
                        logger.warning("Jetstream connection closed")
                        break
                    except Exception as e:
                        logger.error(f"Error in forward_messages: {str(e)}")
                        continue
                        
        except Exception as e:
            server_status["is_jetstream_connected"] = False
            logger.error(f"Error connecting to Jetstream: {str(e)}")
            await asyncio.sleep(5)  # Wait before reconnecting

async def handle_client(websocket, path):
    """Handles individual WebSocket client connections."""
    try:
        connected_clients.add(websocket)
        server_status["connected_clients"] = len(connected_clients)
        logger.info(f"New client connected. Total clients: {len(connected_clients)}")
        
        try:
            # Keep the connection alive until the client disconnects
            await websocket.wait_closed()
        finally:
            connected_clients.remove(websocket)
            server_status["connected_clients"] = len(connected_clients)
            logger.info(f"Client disconnected. Total clients: {len(connected_clients)}")
            
    except Exception as e:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
            server_status["connected_clients"] = len(connected_clients)
        logger.error(f"Error in handle_client: {str(e)}")

async def health_check(request):
    """HTTP endpoint for Kubernetes health checks."""
    # For liveness probe, we just check if the server is running
    return web.Response(status=200, text="OK")

async def readiness_check(request):
    """HTTP endpoint for Kubernetes readiness checks."""
    # For readiness probe, we check if we're connected to Jetstream
    if server_status["is_jetstream_connected"]:
        # Check if we've received a message in the last minute
        if server_status["last_jetstream_message"]:
            last_message_time = datetime.fromisoformat(server_status["last_jetstream_message"])
            if (datetime.utcnow() - last_message_time).total_seconds() > 60:
                return web.Response(status=503, text="No recent messages from Jetstream")
        return web.Response(status=200, text="OK")
    return web.Response(status=503, text="Not connected to Jetstream")

async def startup_handler(app):
    """Handles startup tasks."""
    server_status["start_time"] = datetime.utcnow()
    app['forward_task'] = asyncio.create_task(forward_messages())

async def cleanup_handler(app):
    """Handles cleanup tasks."""
    app['forward_task'].cancel()
    try:
        await app['forward_task']
    except asyncio.CancelledError:
        pass

async def main():
    """Main function to start both the WebSocket and HTTP servers."""
    # Create the aiohttp app
    app = web.Application()
    app.router.add_get('/healthz', health_check)  # Kubernetes liveness probe
    app.router.add_get('/readyz', readiness_check)  # Kubernetes readiness probe
    app.on_startup.append(startup_handler)
    app.on_cleanup.append(cleanup_handler)
    
    # Start the WebSocket server
    websocket_server = await websockets.serve(handle_client, "0.0.0.0", 8765)
    
    # Start the HTTP server
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8090)
    await site.start()
    
    logger.info("Servers started. HTTP on port 8080, WebSocket on port 8765")
    
    try:
        await asyncio.Future()  # run forever
    finally:
        websocket_server.close()
        await websocket_server.wait_closed()
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")