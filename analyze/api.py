from typing import Any, Dict, Final, List

import requests
from config import API_TOKEN

BASE_URL: Final[str] = "https://qiita.com/api/v2"


def get_headers() -> Dict[str, str]:
    return {
        "content-type": "application/json",
        "Authorization": f"Bearer {API_TOKEN}",
    }


# https://qiita.com/api/v2/docs#get-apiv2authenticated_useritems
def get_user_items(page: int) -> List[Dict[str, Any]]:
    url: str = f"{BASE_URL}/authenticated_user/items?page={page}"
    response: requests.Response = requests.get(url, headers=get_headers())
    return response.json()


# https://qiita.com/api/v2/docs#get-apiv2itemsitem_id
def get_item_details(item_id: str) -> Dict[str, Any]:
    url: str = f"{BASE_URL}/items/{item_id}"
    response: requests.Response = requests.get(url, headers=get_headers())
    return response.json()
