import asyncio
import socketio
from global_store import global_store
import os
import shutil


# Create a Socket.IO server allowing CORS for specific origins
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins=[
                           "http://localhost:5173", "http://34.44.107.80:5173", "http://localhost:3001", "http://localhost:3000", "https://client-next-supabase.vercel.app", "https://buildsync-playground.app"])


@sio.event
async def connection(sid):
    print("Client connected to server")


@sio.event
async def disconnect(sid):
    print("User Disconnected from server")
    global_store.sid_to_ifc_model.pop(sid, None)

    directory_path = os.path.join('public', sid)
    if os.path.exists(directory_path) and os.path.isdir(directory_path):
        shutil.rmtree(directory_path)
        print(f"Deleted directory: {directory_path}")
    else:
        print(f"Directory not found: {directory_path}")


@sio.event
async def modelLoaded(sid):
    print("Model loaded")


# receives data on the user position and shares that information with other users
@sio.event
async def userPosition(sid, data):
    # print("position: ", data)
    pass
    # print('User position updated: ', data)

    # Broadcast updated positions to all users except the sender
    # disabled for now
    # await sio.emit('userPosition', data, skip_sid=sid)


async def start():
    # await sio.connect('http://127.0.0.1:8080')
    # await sio.wait()
    print('Server connection has been disabled')
