import requests
import json
import enum

ntfy_url = "https://ntfy.sh/"
ntfy_route = "<NTFY_ROUTE>"

class PRIORITY(enum.Enum):
    """
    Enum representing the available priorities for notifications
    """
    urgent = 5
    high = 4
    default = 3
    low = 2
    min = 1


priorities = {"urgent": 5, "high": 4, "default": 3, "low": 2, "min": 1}

def notify(source, message, priority=PRIORITY.default):
    #  https://docs.ntfy.sh/publish/#__tabbed_1_7
    if not isinstance(priority, PRIORITY):
        raise TypeError("priority must be a PRIORITIES enum")

    requests.post(ntfy_url, 
                  data=json.dumps({
                      "topic": ntfy_route,
                      "message": message,
                      "title": f"Alert from {source}",
                      "priority": priority.value,
                      })
                      )