import mimetypes
from pathlib import Path
import socket
import logging

from datetime import datetime
from urllib.parse import urlparse, unquote_plus
from http.server import HTTPServer, BaseHTTPRequestHandler
from multiprocessing import Process
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from utilities.constants import Constants

URI_DB = "mongodb://mongodb:27017"
BASE_DIR = Path(__file__).parent / "front-part"
CHUNK_SIZE = 1024
HTTP_PORT = 3000
SOCKET_PORT = 5000
HTTP_HOST = "0.0.0.0"
SOCKET_HOST = "127.0.0.1"


class HttpGetHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        router = urlparse(self.path).path
        match router:
            case "/":
                self.send_html("front-part/index.html")
            case "/message.html":
                self.send_html("front-part/message.html")
            case _:
                file = BASE_DIR.joinpath(router[1:])
                if file.exists():
                    self.send_static(file)
                else:
                    self.send_html("front-part/error.html", 404)

    def do_POST(self):
        data = self.rfile.read(int(self.headers[Constants.content_length]))
        try:
            socket_client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            socket_client.sendto(data, (SOCKET_HOST, SOCKET_PORT))
            socket_client.close()
        except socket.error:
            logging.error(Constants.failed_to_send_data)

        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()

    def send_html(self, filename, status=200):
        self.send_response(status)
        self.send_header(Constants.content_type, Constants.html_content_type)
        self.end_headers()
        with open(filename, "rb") as f:
            self.wfile.write(f.read())

    def send_static(self, filename, status=200):
        self.send_response(status)
        mt = mimetypes.guess_type(filename)[0] or Constants.plain_content_type
        self.send_header(Constants.content_type, mt)
        self.end_headers()
        with open(filename, "rb") as file:
            self.wfile.write(file.read())


def run_http_server(port):
    httpd = HTTPServer((HTTP_HOST, HTTP_PORT), HttpGetHandler)
    try:
        httpd = HTTPServer((HTTP_HOST, port), HttpGetHandler)
        logging.info(Constants.server_started.format(HTTP_HOST, HTTP_PORT))
        httpd.serve_forever()
    except KeyboardInterrupt:
        logging.info(Constants.server_stopped_error)
    except Exception as e:
        logging.error(e)
    finally:
        logging.info(Constants.server_stopped)
        httpd.server_close()


def run_socket_server(port):
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((SOCKET_HOST, port))
    logging.info(Constants.socket_server_started.format(SOCKET_HOST, SOCKET_PORT))
    try:
        while True:
            data, addr = server.recvfrom(CHUNK_SIZE)
            logging.info(Constants.received_data.format(addr, data.decode()))
            save_to_db(data.decode())
    except KeyboardInterrupt:
        logging.info(Constants.socket_server_stopped_error)
    except Exception as e:
        logging.error(e)
    finally:
        logging.info(Constants.socket_server_stopped)
        server.close()


def save_to_db(data):
    client = MongoClient(URI_DB, server_api=ServerApi("1"))
    db = client.homework
    try:
        data_parse = unquote_plus(data)
        data_dict = {
            key: value for key, value in [el.split("=") for el in data_parse.split("&")]
        }
        document = {"date": datetime.now().strftime(Constants.datetime_format)}
        document.update(data_dict)
        db.messages.insert_one(document)

    except Exception as e:
        logging.error(e)
    finally:
        client.close()


def task_handler():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(process)s - %(message)s"
    )

    http_server = Process(
        target=run_http_server, args=(HTTP_PORT,), name=Constants.http_server
    )
    socket_server = Process(
        target=run_socket_server, args=(SOCKET_PORT,), name=Constants.socket_server
    )

    http_server.start()
    socket_server.start()

    try:
        http_server.join()
        socket_server.join()
    except KeyboardInterrupt:
        logging.info(Constants.server_stopped_error)
    finally:
        http_server.terminate()
        socket_server.terminate()
        http_server.join()
        socket_server.join()
        logging.info(Constants.server_stopped)
