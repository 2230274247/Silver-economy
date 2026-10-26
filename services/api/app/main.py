from fastapi import FastAPI

app = FastAPI(title="银发记忆 Demo", version="0.1.0-alpha")


@app.get("/")
def index() -> dict[str, str]:
    return {"service": "silver-memory-api", "stage": "scaffold", "provider": "not-configured"}
