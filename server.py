import socketio
from aiohttp import web
import os
from dotenv import load_dotenv
import asyncio
import sys
import requests
import asyncio
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi import Header, HTTPException
import uvicorn
from starlette.middleware.cors import CORSMiddleware
from socket_server import sio
from agent_graph import model_streamer
from fastapi.staticfiles import StaticFiles
from tools_graph import create_on_start
import hashlib
import time
import logging
from global_store import global_store
from fastapi import Form

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


OPEN_API_KEY = os.getenv('OPEN_API_KEY')

## ---- WEBSOCKET SETUP ----- ##

# Create a Socket.IO server
app = FastAPI()
# Set up CORS middleware for FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173",
                   "http://34.44.107.80:5173",
                   "http://localhost:3001",
                   "http://localhost:3000",
                   "https://client-next-supabase.vercel.app",
                   "https://buildsync-playground.app"],  # List of allowed origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)
app.mount("/public", StaticFiles(directory="public"), name="public")
# Create a Socket.IO server allowing CORS for specific origins
combined_asgi_app = socketio.ASGIApp(sio, app)


@ sio.event
async def DOMContentLoaded(sid):
    try:
        await create_on_start()
        print("Created session start load with sid", sid)
    except Exception as e:
        logger.exception(f"Error in DOMContentLoaded: {str(e)}")
        await sio.emit('error', {'message': 'Error initializing session'}, room=sid)


@app.post("/upload")
async def upload_file(file: UploadFile = File(...), sid: str = Form(None)):
    print('Upload file received')
    try:
        if not sid:
            raise HTTPException(status_code=400, detail="SID is required")
        # Save the uploaded file
        directory = f"public/{sid}"
        if not os.path.exists(directory):
            os.makedirs(directory)
        file_location = f"{directory}/{file.filename}"
        logger.info(f"Saving file to: {file_location}")
        with open(file_location, "wb") as f:
            content = await file.read()
            f.write(content)
        logger.info("File saved successfully")

        logger.info(f"Emitting backgroundModelChange event. SID: {sid}")
        if sid:
            print('sid found')
            await sio.emit('backgroundModelChange', {'userId': sid, 'file_name': file_location}, skip_sid=sid)
        else:
            await sio.emit('backgroundModelChange', {'file_name': file_location})
        logger.info("Event emitted successfully")

        return JSONResponse(status_code=200, content={"message": "File uploaded successfully"})
    except Exception as e:
        logger.exception(
            f"An error occurred while uploading the file: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"File upload failed: {str(e)}")


@ sio.event
async def userAction(sid, data):
    try:
        print('User Action recieved')
        await sio.emit('userAction', data, room=sid)
        user_command = data['message']
        curHighlightedObjects = None
        viewer_message = data.get('highlightedFragments', None)
        if viewer_message:
            curHighlightedObjects = global_store.sid_to_highlighted_objects.get(sid, None)
            print('[userAction] sid -> highlightedObjects', global_store.sid_to_highlighted_objects)
            print('[userAction] curHighlightedObjects', curHighlightedObjects)
            global_store.sid_to_highlighted_objects.pop(sid, None)
        if True:  # user_command.startswith('/')
            unique_string = f"{user_command}-{time.time()}"
            unique_hash = "ai-" + \
                hashlib.sha256(unique_string.encode()).hexdigest()
            print(f"Generated unique hash: {unique_hash}")

            await sio.emit('aiActionStart', {'hash':  unique_hash}, room=sid)
            await model_streamer(sid, data, unique_hash, curHighlightedObjects)
            await sio.emit('aiActionEnd', {'hash': unique_hash}, room=sid)
    except Exception as e:
        logger.exception(f"Error in userAction: {str(e)}")
        await sio.emit('error', {'message': 'Error processing user action'}, room=sid)


@ sio.event
async def highlightedFragments(sid, data):
    try:
        print(f'highlightedFragments recieved {data}')
        curHighlightedObjects = data.get('highlightedFragments', None)
        global_store.sid_to_highlighted_objects[sid] = curHighlightedObjects
        print('[highlightedFragments] curHighlightedObjects added to sid ', sid)
    except Exception as e:
        logger.exception(f"Error in highlightedFragments: {str(e)}")
        await sio.emit('error', {'message': 'Error processing highlighted fragments'}, room=sid)

@ sio.event
async def fileChange(sid, data):
    try:
        print('File change received:', data)
        file_name = data['file_name']
        print(f"Emitting fileChange event. SID: {sid}, File Name: {file_name}")
        await sio.emit('fileChange', {'userId': sid, 'file_name': file_name}, room=sid)
    except Exception as e:
        logger.exception(f"Error in fileChange: {str(e)}")
        await sio.emit('error', {'message': 'Error processing file change'}, room=sid)


@ app.get("/")
async def health_check():
    print('Server is running')
    return {"message": "Server is running"}


async def send_agent_response(message, sid):
    try:
        await sio.emit('agentResponse', {'message': message}, room=sid)
    except Exception as e:
        logger.exception(f"Error in send_agent_response: {str(e)}")
        await sio.emit('error', {'message': 'Error sending agent response'}, room=sid)


def perform_action():
    # url = 'http://127.0.0.1:8080/chat'
    # data = {'text': 'value'}
    # response = requests.post(url, json=data)
    # print(response.json())
    print('Perform action has been disabled')


def check_status():
    # url = 'http://127.0.0.1:8080/health'
    # response = requests.get(url)
    # print(response.json())
    print('Health check has been disabled')


if __name__ == '__main__':
    check_status()
    perform_action()
    # streaming_answer = agent_executor.invoke({"input": "Create a square 20x20 feet structure on level 1. Show your thinking step by step but be concise."})
    # asyncio.run(start())
    uvicorn.run("server:combined_asgi_app", host="localhost", port=8000, reload=True)
