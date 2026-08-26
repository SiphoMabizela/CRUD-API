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


# Database setup is run whenever the application starts.
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

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "INSERT INTO tasks (title, done) VALUES (?, ?)",
        (task.title.strip(), False)
    )

    task_id = cursor.lastrowid

    connection.commit()

    cursor.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    )

    row = cursor.fetchone()

    connection.close()

    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"])
    }


@app.put(
    "/tasks/{task_id}",
    summary="Update a task",
    description="Updates the title and/or completion status of an existing task."
)
def update_task(task_id: int, task_update: TaskUpdate):
    connection = get_connection()
    cursor = connection.cursor()

    # Check whether the task exists.
    cursor.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    )

    row = cursor.fetchone()

    if row is None:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    # Validate the title if one was provided.
    if task_update.title is not None and not task_update.title.strip():
        connection.close()

        raise HTTPException(
            status_code=400,
            detail="Title cannot be empty"
        )

    # If a field was not supplied, keep its existing value.
    new_title = (
        task_update.title.strip()
        if task_update.title is not None
        else row["title"]
    )

    new_done = (
        task_update.done
        if task_update.done is not None
        else bool(row["done"])
    )

    # Update the task using parameterized SQL.
    cursor.execute(
        """
        UPDATE tasks
        SET title = ?, done = ?
        WHERE id = ?
        """,
        (new_title, new_done, task_id)
    )

    connection.commit()

    # Retrieve the updated task.
    cursor.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    )

    updated_row = cursor.fetchone()

    connection.close()

    return {
        "id": updated_row["id"],
        "title": updated_row["title"],
        "done": bool(updated_row["done"])
    }


@app.delete(
    "/tasks/{task_id}",
    status_code=204,
    summary="Delete a task",
    description="Deletes an existing task using its unique ID."
)
def delete_task(task_id: int):
    connection = get_connection()
    cursor = connection.cursor()

    # Check whether the task exists.
    cursor.execute(
        "SELECT * FROM tasks WHERE id = ?",
        (task_id,)
    )

    row = cursor.fetchone()

    if row is None:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    # the task will be deleted using a parameterized query.
    cursor.execute(
        "DELETE FROM tasks WHERE id = ?",
        (task_id,)
    )

    connection.commit()
    connection.close()

    # 204 responses must have an empty body.
    return None