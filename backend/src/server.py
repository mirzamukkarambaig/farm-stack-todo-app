from contextlib import asynccontextmanager
from datetime import datetime
import os
import sys

from bson import ObjectId
from fastapi import FastAPI, status
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
import uvicorn

from dal import ToDoDAL, ListSummary, ToDoList

# Constants
COLLECTION_NAME = "todo_lists"
MONGODB_URI = os.getenv("MONGODB_URI")
DEBUG = os.getenv("DEBUG", "").strip().lower() in {"1", "true", "on", "yes"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    client = AsyncIOMotorClient(MONGODB_URI)
    database = client.get_default_database()

    # Ensure the database is available
    pong = await database.command("ping")
    if int(pong["ok"]) != 1:
        raise Exception("Cluster connection is not okay!")
    
    todo_lists = database.get_collection(COLLECTION_NAME)
    app.todo_dal = ToDoDAL(todo_lists)

    # Yield control back to FastAPI
    yield

    # Shutdown
    client.close()


# FastAPI Application
app = FastAPI(lifespan=lifespan, debug=DEBUG)


# Request/Response Models
class NewList(BaseModel):
    name: str


class NewListResponse(BaseModel):
    id: str
    name: str


class NewItem(BaseModel):
    label: str


class ToDoItemUpdate(BaseModel):
    item_id: str
    checked_state: bool


class DummyResponse(BaseModel):
    id: str
    when: datetime


# Routes
@app.get("/api/lists", response_model=list[ListSummary])
async def get_all_lists() -> list[ListSummary]:
    return [i async for i in app.todo_dal.list_todo_lists()]


@app.post("/api/lists", status_code=status.HTTP_201_CREATED, response_model=NewListResponse)
async def create_todo_list(new_list: NewList) -> NewListResponse:
    list_id = await app.todo_dal.create_todo_list(new_list.name)
    return NewListResponse(id=list_id, name=new_list.name)


@app.get("/api/lists/{list_id}", response_model=ToDoList)
async def get_list(list_id: str) -> ToDoList:
    return await app.todo_dal.get_todo_list(list_id)


@app.delete("/api/lists/{list_id}", response_model=bool)
async def delete_list(list_id: str) -> bool:
    return await app.todo_dal.delete_todo_list(list_id)


@app.post(
    "/api/lists/{list_id}/items", 
    status_code=status.HTTP_201_CREATED, 
    response_model=ToDoList
)
async def create_item(list_id: str, new_item: NewItem) -> ToDoList:
    return await app.todo_dal.create_item(list_id, new_item.label)


@app.patch("/api/lists/{list_id}/checked_state", response_model=ToDoList)
async def set_checked_state(list_id: str, update: ToDoItemUpdate) -> ToDoList:
    return await app.todo_dal.set_checked_state(list_id, update.item_id, update.checked_state)


@app.get("/api/dummy", response_model=DummyResponse)
async def get_dummy() -> DummyResponse:
    return DummyResponse(id=str(ObjectId()), when=datetime.now())


# Entry Point
def main(argv=sys.argv[1:]):
    try:
        uvicorn.run("server:app", host="0.0.0.0", port=3001, reload=DEBUG)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
