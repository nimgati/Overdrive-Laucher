import socket


class Client:
    def __init__(self, host='192.168.1.15', port=6390):
        self.host = host
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect((self.host, self.port))
            print(f"[INFO] Connected to server {self.host}:{self.port}")
        except Exception as e:
            print(f"[ERROR] Failed to connect: {e}")
            self.socket = None

    def send_request(self, request):
        if not self.socket:
            print("[ERROR] No connection to server.")
            return None
        try:
            self.socket.sendall(request.encode())
            response = self.socket.recv(4096).decode()
            return response.strip()
        except Exception as e:
            print(f"[ERROR] Failed to send request: {e}")
            return None

    def get_user_list(self, username, password):
        request = f"{username} {password} GET user_list"
        return self.send_request(request)

    def get_user_points(self, username, password, target_user):
        request = f"{username} {password} GET user_point {target_user}"
        return self.send_request(request)

    def add_user_points(self, username, password, target_user, points):
        request = f"{username} {password} POST-ADD user_point {target_user} {points}"
        return self.send_request(request)

    def change_user_name(self, username, password, old_user_name, new_user_name):
        requests = f"{username} {password} POST-ADD change_name {old_user_name}, {new_user_name}"

    def close(self):
        if self.socket:
            self.socket.close()
            print("[INFO] Connection closed.")


if __name__ == "__main__":
    client = Client()
    username = "test1"
    password = "14555"

    print(client.get_user_list(username, password))
    print(client.get_user_points(username, password, "nytrox"))
    print(client.add_user_points(username, password, "test1", 100))

    client.close()