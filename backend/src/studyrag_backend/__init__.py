__version__ = "0.2.0"


def main() -> None:
    """Run the API through the installed console script."""
    import uvicorn

    uvicorn.run(
        "studyrag_backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
