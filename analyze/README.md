# Qiita 投稿記事の閲覧数・のいいね数の分析

会社の技術ブログ発信の手段として Qiita を利用していますが，技術ブログを成果として報告する際，期間毎の閲覧数を定量指標として示したいと考えました．また，いいね数や閲覧数などを定量的に分析することで，どのような記事が人気があるのかを把握したいと考えました．

上記の目的を達成するために，Qiita API を利用して，Qiita 投稿記事のいいね数・閲覧数などを取得し，集計する Python スクリプトを作成しました．集計コードは以下で公開しています．

https://github.com/ren8k/analyze_qiita

## 利用方法

- コードを clone し，`src` ディレクトリに移動

```bash
git clone https://github.com/ren8k/analyze_qiita.git
cd src
```

- Qiita のアクセストークンの発行

  - ログインした状態で https://qiita.com/settings/tokens/new へアクセス
  - スコープでは `read_qiita` を選択し，任意の名前を `アクセストークンの説明` に入力した後，`発行` を押下
  - 発行されたアクセストークンをコピー

- config.py の以下の変数を設定する．
  - `USER_ID`: Qiita のユーザ名
  - `API_TOKEN`: Qiita API のアクセストークン
  - `START_DATE`: 集計開始日時
  - `END_DATE`: 集計終了日時

```python:config.py
from datetime import datetime, timezone
from typing import Final

PER_PAGE: Final[int] = 100
USER_ID: Final[str] = "<user name>"
API_TOKEN: Final[str] = "<api token>"
START_DATE: Final[datetime] = datetime(2024, 4, 1, tzinfo=timezone.utc)
END_DATE: Final[datetime] = datetime(2025, 3, 31, tzinfo=timezone.utc)
```

- `main.py` を実行する．

```bash
python main.py
```

- 以下のような出力が得られる．

| 記事タイトル                                                                                 | いいね数 | ストック数 | View 数 | 作成日     | タグ                                                     |
| :------------------------------------------------------------------------------------------- | -------: | ---------: | ------: | :--------- | :------------------------------------------------------- |
| Amazon Titan Image Generator v2 の全機能を徹底検証：機能解説と実践ガイド                     |       14 |          8 |    3820 | 2024-09-26 | Python, AWS, bedrock, 画像生成, 生成 AI                  |
| Amazon Bedrock における Claude 3 Haiku の Fine-Tuning 検証レポート                           |       28 |         15 |   13230 | 2024-07-30 | Python, AWS, bedrock, 生成 AI, claude                    |
| Amazon Bedrock Converse API で Claude3 の JSON モードを利用する                              |       20 |         11 |    8314 | 2024-07-01 | Python, AWS, bedrock, 生成 AI, LLM                       |
| 「Amazon Bedrock」で始める生成 AI アプリ開発入門バイブルの登場！！                           |        7 |          7 |    5663 | 2024-06-22 | AWS, 技術書, bedrock, 生成 AI, LLM                       |
| Amazon Bedrock Converse API と Tool use を知識ゼロから学び，発展的なチャットアプリを実装する |       32 |         19 |   14341 | 2024-06-10 | Python, AWS, bedrock, 生成 AI, claude                    |
| Amazon Bedrock の Converse API と Streamlit で 10 分でチャットアプリを作成する               |       12 |          6 |    4348 | 2024-05-31 | Python, AWS, bedrock, Streamlit, 生成 AI                 |
| 世界最速！？Amazon Bedrock の Custom model import の機能検証                                 |       17 |          8 |    8498 | 2024-05-26 | AWS, bedrock, 生成 AI, LLM, Llama3                       |
| Amazon Bedrock で Advanced RAG を実装する上での Tips                                         |       27 |         22 |   19018 | 2024-05-18 | Python, AWS, rag, bedrock, KnowledgeBaseForAmazonBedrock |

============ Summary ============

- 期間: 2024-04-01 から 2025-03-31
- 対象記事数: 8
- View 総計: 77232
- 平均いいね数: 19.6
- 平均ストック数: 12.0
- 平均いいね率: 0.2%

\================================

私の記事の集計結果によると，全ての記事に AWS や Bedrock が関連していることがわかります．

## 簡易説明

`analyzer.py` で定義している関数 `get_article_stats` により，集計処理を行います．アルゴリズムとしては以下です．

- 統計情報 (views, likes, stocks) の初期化
- ページング処理により記事を取得し，集計の実施
  - 関数 `get_user_items`: 認証中のユーザーの記事の一覧を作成日時の降順で取得
  - 関数 `get_item_details`: 記事の詳細情報を取得
- 記事の以下の詳細情報を取得
  - タイトル
  - いいね数
  - ストック数
  - View 数
  - 作成日
  - タグ
- 統計情報を更新

```python: analyzer.py
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

        if len(items) < PER_PAGE:
            break  # 最後のページであればループを終了
        page += 1

    return articles, all_views, all_likes, all_stocks, items_count
```

上記の関数を改修することで，指定のタグが付与された記事のみを集計することも可能です．

## Reference

- https://qiita.com/api/v2/docs
