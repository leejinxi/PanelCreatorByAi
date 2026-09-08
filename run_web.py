import uvicorn


def main() -> None:
    """在本机启动浏览器演示服务。"""

    uvicorn.run(
        "webapp.app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
