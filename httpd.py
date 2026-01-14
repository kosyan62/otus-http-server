import argparse
from server.config import Config
from server.server import ThreadedHTTPServer as Server

def main():
    parser = argparse.ArgumentParser(description="A simple http server")
    parser.add_argument("--host", "-H", type=str, default="0.0.0.0", help="host to listen on")
    parser.add_argument("--port", "-p", type=int, default=8080, help="port to listen on")
    parser.add_argument("--root", "-r", type=str, default=".", help="directory to serve")
    parser.add_argument("--workers", "-w", type=int, default=4, help="number of worker processes")
    # parser.add_argument("--daemon", "-d", action="store_true", help="run in daemon mode")
    parser.add_argument("--debug", "-D", action="store_true", help="enable debug mode")

    args = parser.parse_args()
    config = Config(host=args.host, port=args.port, root=args.root, workers=args.workers, debug=args.debug)
    if config.debug:
        print(f"Starting server on port {args.port}, serving directory '{args.root}' with {args.workers} workers.")
    server = Server(config)
    server.run()

if __name__ == "__main__":
    main()