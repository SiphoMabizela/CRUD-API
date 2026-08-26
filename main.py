import sqlite3

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


app = FastAPI(
    title="Task API",
    description="CRUD API for managing a to-do list.",
    version="1.0"
)

DATABASE_NAME = "tasks.db"


class TaskCreate(BaseModel):
    title: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    done: bool | None = None


def get_connection():
    """Create and return a connection to the SQLite database."""
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    """Create the tasks table and seed example tasks only when empty."""
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            done BOOLEAN NOT NULL DEFAULT 0
        )
        """
    )

    cursor.execute("SELECT COUNT(*) AS count FROM tasks")
    task_count = cursor.fetchone()["count"]

    if task_count == 0:
        example_tasks = [
            ("Do the laundry.", False),
            ("Write my CCNA exam.", False),
            ("Enroll to FlyRank internship.", True),
        ]

        cursor.executemany(
            "INSERT INTO tasks (title, done) VALUES (?, ?)",
            example_tasks
        )

    connection.commit()
    connection.close()


# database setup is ran whenever the application starts.
initialize_database()


@app.get(
    "/",
    summary="Get API information",
    description="Returns the name, version, and available task endpoint."
)
def read_root():
    return {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"]
    }


@app.get(
    "/health",
    summary="Check API health",
    description="Returns the current health status of the API."
)
def health_check():
    return {"status": "ok"}


@app.get(
    "/tasks",
    summary="Get all tasks",
    description="Returns all tasks stored in the SQLite database."
)
def get_tasks():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM tasks")
    rows = cursor.fetchall()

    connection.close()

    return [
        {
            "id": row["id"],
            "title": row["title"],
            "done": bool(row["done"])
        }
        for row in rows
    ]


@app.get(
    "/tasks/{task_id}",
    summary="Get a single task",
    description="Returns a task using its unique ID."
)
def get_task(task_id: int):
    connection = get_connection()
    cursor = connection.cursor()

    # Parameterized query prevents user input from being inserted
    # directly into the SQL statement.
    cursor.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    )

    row = cursor.fetchone()
    connection.close()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"])
    }


@app.post(
    "/tasks",
    status_code=201,
    summary="Create a new task",
    description="Creates a new task with a title and sets done to false."
)
def create_task(task: TaskCreate):
    if not task.title or not task.title.strip():
        raise HTTPException(
            status_code=400,
            detail="Title is required and cannot be empty"
        )
    return {}


@app.put(
    "/tasks/{task_id}",
    summary="Update a task",
    description="Updates the title and/or completion status of an existing task."
)
def update_task(task_id: int, task_update: TaskUpdate):
    raise HTTPException(
        status_code=404,
        detail="Task not found"
    )


@app.delete(
    "/tasks/{task_id}",
    status_code=204,
    summary="Delete a task",
    description="Deletes an existing task using its unique ID."
)
def delete_task(task_id: int):
    raise HTTPException(
        status_code=404,
        detail="Task not found"
    )