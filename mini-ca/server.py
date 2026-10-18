
import http.server
import ssl

HOST = "127.0.0.1"
PORT = 8443

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"mTLS OK: client certificate verified!\n")

    def log_message(self, format, *args):
        print(f"[HTTPS] {self.client_address[0]} - {format % args}")

server = http.server.HTTPServer((HOST, PORT), Handler)

context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
context.load_cert_chain(
    certfile="certs/server-chain.pem",
    keyfile="private/server.key.pem"
)

# Trust the Root CA; clients can present the intermediate certificate too.
context.load_verify_locations(cafile="certs/ca.cert.pem")
context.verify_mode = ssl.CERT_REQUIRED

server.socket = context.wrap_socket(server.socket, server_side=True)

print(f"mTLS server listening on https://{HOST}:{PORT}")
server.serve_forever()
