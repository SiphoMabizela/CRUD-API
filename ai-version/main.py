from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import sqlite3


app = FastAPI()

DATABASE = "tasks.db"


# -------------------------
# Database setup
# -------------------------

def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def initialise_database():
    conn = get_connection()

    try:
        # Create the tasks table if it does not already exist
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        # Only insert seed data when the table is completely empty
        cursor = conn.execute("SELECT COUNT(*) FROM tasks")
        task_count = cursor.fetchone()[0]

        if task_count == 0:
            seed_tasks = [
                ("Learn FastAPI", 0),
                ("Learn SQLite", 0),
                ("Build a CRUD API", 0),
            ]

            conn.executemany(
                "INSERT INTO tasks (title, done) VALUES (?, ?)",
                seed_tasks
            )

        conn.commit()

    finally:
        conn.close()


# Create the database and table when the application starts
initialise_database()


# -------------------------
# Request models
# -------------------------

class TaskCreate(BaseModel):
    title: str


class TaskUpdate(BaseModel):
    title: str
    done: bool


# -------------------------
# Helper functions
# -------------------------

def row_to_task(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"]),
    }


# -------------------------
# GET /tasks
# -------------------------

@app.get("/tasks")
def get_tasks():
    conn = get_connection()

    try:
        cursor = conn.execute(
            "SELECT id, title, done FROM tasks ORDER BY id"
        )

        rows = cursor.fetchall()

        return [row_to_task(row) for row in rows]

    finally:
        conn.close()


# -------------------------
# GET /tasks/{task_id}
# -------------------------

@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    conn = get_connection()

    try:
        cursor = conn.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?",
            (task_id,)
        )

        row = cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

        return row_to_task(row)

    finally:
        conn.close()


# -------------------------
# POST /tasks
# -------------------------

@app.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate):
    # Validate title
    if not task.title or not task.title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Title cannot be empty"
        )

    title = task.title.strip()

    conn = get_connection()

    try:
        cursor = conn.execute(
            "INSERT INTO tasks (title, done) VALUES (?, ?)",
            (title, 0)
        )

        conn.commit()

        task_id = cursor.lastrowid

        cursor = conn.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?",
            (task_id,)
        )

        row = cursor.fetchone()

        return row_to_task(row)

    finally:
        conn.close()


# -------------------------
# PUT /tasks/{task_id}
# -------------------------

@app.put("/tasks/{task_id}")
def update_task(task_id: int, task: TaskUpdate):
    # Validate title
    if not task.title or not task.title.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Title cannot be empty"
        )

    title = task.title.strip()

    conn = get_connection()

    try:
        # Check whether the task exists
        cursor = conn.execute(
            "SELECT id FROM tasks WHERE id = ?",
            (task_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

        # Update the task
        conn.execute(
            """
            UPDATE tasks
            SET title = ?, done = ?
            WHERE id = ?
            """,
            (title, int(task.done), task_id)
        )

        conn.commit()

        # Return the updated task
        cursor = conn.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?",
            (task_id,)
        )

        row = cursor.fetchone()

        return row_to_task(row)

    finally:
        conn.close()


# -------------------------
# DELETE /tasks/{task_id}
# -------------------------

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):
    conn = get_connection()

    try:
        # Check whether the task exists
        cursor = conn.execute(
            "SELECT id FROM tasks WHERE id = ?",
            (task_id,)
        )

        if cursor.fetchone() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )

        conn.execute(
            "DELETE FROM tasks WHERE id = ?",
            (task_id,)
        )

        conn.commit()

        # A 204 response must not contain a response body
        return None

    finally:
        conn.close()