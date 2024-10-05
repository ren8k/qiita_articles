from typing import Any, Dict, List

import pandas as pd
from analyzer import calculate_averages, get_article_stats
from config import END_DATE, START_DATE


def print_article_table(articles: List[Dict[str, Any]]) -> None:
    df = pd.DataFrame(articles)
    # df = df[['title', 'likes', 'stocks', 'views', 'created_at', 'tags']]
    df.columns = ["記事タイトル", "いいね数", "ストック数", "View数", "作成日", "タグ"]
    markdown_table = df.to_markdown(index=False)
    print(markdown_table)


def print_summary(
    all_views: int,
    ave_likes: float,
    ave_stocks: float,
    engagement_rate: float,
    items_count: int,
) -> None:
    print("\n============ Summary ============")
    print(f"- 期間: {START_DATE.date()} から {END_DATE.date()}")
    print(f"- 対象記事数: {items_count}")
    print(f"- View総計: {all_views}")
    print(f"- 平均いいね数: {ave_likes}")
    print(f"- 平均ストック数: {ave_stocks}")
    print(f"- 平均いいね率: {engagement_rate}%")
    print("================================")


def main() -> None:
    articles, all_views, all_likes, all_stocks, items_count = get_article_stats()
    ave_likes, ave_stocks, engagement_rate = calculate_averages(
        all_likes, all_stocks, all_views, items_count
    )

    print_article_table(articles)
    print_summary(all_views, ave_likes, ave_stocks, engagement_rate, items_count)


if __name__ == "__main__":
    main()
