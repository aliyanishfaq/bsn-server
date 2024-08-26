import asyncio
import socketio


# Create a Socket.IO server allowing CORS for specific origins
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins=[
                           "http://localhost:5173", "http://34.44.107.80:5173", "http://localhost:3001", "http://localhost:3000"])


@sio.event
async def connection(sid):
    print("AI Connected to server")


@sio.event
async def disconnect(sid):
    print("User Disconnected from server")


@sio.event
async def modelLoaded(sid):
    print("Model loaded")


@sio.event
async def userPosition(sid, data):
    # print('User position updated: ', data)

    # Broadcast updated positions to all users except the sender
    await sio.emit('userPosition', data, skip_sid=sid)


async def start():
    # await sio.connect('http://127.0.0.1:8080')
    # await sio.wait()
    print('Server connection has been disabled')
