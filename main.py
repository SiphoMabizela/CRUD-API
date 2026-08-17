from fastapi import FastAPI, HTTPException

app = FastAPI()


# in-memory task list
tasks = [
    {
        "id": 1,
        "title": "Do the laundry.",
        "done": False
    },
    {
        "id": 2,
        "title": "Write my CCNA exam.",
        "done": False
    },
    {
        "id": 3,
        "title": "Enroll to FlyRank internship.",
        "done": True
    }
]


@app.get("/")
def read_root():
    return {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"]
    }


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/tasks")
def get_tasks():
    return tasks


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    for task in tasks:
        if task["id"] == task_id:
            return task

    raise HTTPException(
    status_code=404,
    detail=f"Task {task_id} not found"
)