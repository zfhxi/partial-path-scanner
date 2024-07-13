import requests
from requests import RequestException

from termcolor import colored


def scan(config, path, server_type):
    print(colored(f"Scan request from {server_type} for {path}.", "green"))
    try:
        data = {"Updates": [{"Path": f"{path}", "UpdateType": "Created"}]}
        headers = {"accept": "application/json", "Content-Type": "application/json"}
        host = config[server_type]["host"]
        try:
            command = requests.post(
                host + f'/Library/Media/Updated?api_key={config[server_type]["api_key"]}',
                headers=headers,
                json=data,
            )
            if command.status_code == 204:
                print(f"Successfully sent scan request to {server_type}.")
        except RequestException as e:
            print(colored(f"Error occurred when trying to send scan request to {server_type}. {e}", "red"))
    except KeyError:
        pass
