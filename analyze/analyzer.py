import time
from datetime import datetime
from typing import Any, Dict, List, Tuple

from api import get_item_details, get_user_items
from config import END_DATE, PER_PAGE, START_DATE


def is_within_date_range(date: datetime) -> bool:
    return START_DATE <= date <= END_DATE


def get_article_stats() -> Tuple[List[Dict[str, Any]], int, int, int, int]:
    all_views: int = 0
    all_likes: int = 0
    all_stocks: int = 0
    articles: List[Dict[str, Any]] = []
    items_count: int = 0

    page: int = 1
    while True:
        items: List[Dict[str, Any]] = get_user_items(page)
        if not items:
            break

        for item in items:
            created_at: datetime = datetime.fromisoformat(
                item["created_at"].replace("Z", "+00:00")
            )
            if not is_within_date_range(created_at) or item["private"]:
                continue

            item_details: Dict[str, Any] = get_item_details(item["id"])
            page_views: int = item_details["page_views_count"]

            all_views += page_views
            all_likes += item["likes_count"]
            all_stocks += item["stocks_count"]
            tags: str = ", ".join([tag["name"] for tag in item["tags"]])
            items_count += 1

            articles.append(
                {
                    "title": item["title"],
                    "likes": item["likes_count"],
                    "stocks": item["stocks_count"],
                    "views": page_views,
                    "created_at": created_at.strftime("%Y-%m-%d"),
                    "tags": tags,
                }
            )
            time.sleep(1)

        if len(items) < PER_PAGE:
            break  # 最後のページであればループを終了
        page += 1

    return articles, all_views, all_likes, all_stocks, items_count


def calculate_averages(
    all_likes: int,
    all_stocks: int,
    all_views: int,
    items_count: int,
) -> Tuple[float, float, float]:
    ave_likes: float = round(all_likes / items_count, 1) if items_count > 0 else 0
    ave_stocks: float = round(all_stocks / items_count, 1) if items_count > 0 else 0
    engagement_rate: float = (
        round(all_likes / all_views * 100, 2) if all_views > 0 else 0
    )
    return ave_likes, ave_stocks, engagement_rate
