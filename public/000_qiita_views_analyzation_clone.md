---
title: Qiita投稿記事の閲覧数・いいね数の分析
tags:
  - Qiita
  - Python
  - API
private: true
updated_at: '2024-10-08T07:31:13+09:00'
id: bb3f6548cf151f52a2d8
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

<!--
株式会社 NTT データ デジタルサクセスコンサルティング事業部の [@ren8k](https://qiita.com/ren8k) です． -->

会社の技術ブログ発信の手段として Qiita を利用している場合，技術ブログを成果として報告する際に，期間毎の閲覧数を定量指標として示すことが有効です．また，いいね数や閲覧数などを定量的に分析することで，どのような記事が人気であるかを把握することができます．

上記の目的を達成するために，[Qiita API](https://qiita.com/api/v2/docs) を利用して，指定の期間内の Qiita 投稿記事のいいね数・閲覧数などを取得し，集計する Python スクリプトを作成しました．集計コードは以下のリンクで公開しています．

https://github.com/ren8k/analyze_qiita

## 利用方法

- コードを clone し，`src` ディレクトリに移動します．

```bash
git clone https://github.com/ren8k/analyze_qiita.git
cd src
```

- Qiita のアクセストークンを発行します．

  - ログインした状態で https://qiita.com/settings/tokens/new へアクセス
  - スコープでは `read_qiita` を選択し，任意の名前を `アクセストークンの説明` に入力した後，`発行` を押下
  - 発行されたアクセストークンをコピー
    <br>

- `config.py` の以下の変数を設定します．

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

- `main.py` を実行します．

```bash
python main.py
```

- `config.py`で指定した期間の各記事の閲覧数やいいね数を含む，以下のような出力が得られます．

```
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

================================

```

- markdown プレビューすると，以下のように表示されます．

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

上記の私の記事の集計結果によると，全ての記事に AWS や Bedrock が関連していることがわかります．また，記事毎の閲覧数にばらつきがありますが，いいね数と閲覧数には相関がありそうです．

## コード

<details><summary>config.py</summary>

```python:config.py
from datetime import datetime, timezone
from typing import Final

PER_PAGE: Final[int] = 100
USER_ID: Final[str] = "<user name>"
API_TOKEN: Final[str] = "<api token>"
START_DATE: Final[datetime] = datetime(2024, 4, 1, tzinfo=timezone.utc)
END_DATE: Final[datetime] = datetime(2025, 3, 31, tzinfo=timezone.utc)
```

</details>

<details><summary>api.py</summary>

```python:api.py
import requests
from typing import Any, Dict, Final, List
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

```

</details>

<details><summary>analyzer.py</summary>

```python:analyzer.py
import time
from datetime import datetime
from typing import Any, Dict, List, Tuple

from api import get_user_items
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

            all_views += item["page_views_count"]
            all_likes += item["likes_count"]
            all_stocks += item["stocks_count"]
            items_count += 1

            articles.append(
                {
                    "title": item["title"],
                    "likes": item["likes_count"],
                    "stocks": item["stocks_count"],
                    "views": item["page_views_count"],
                    "created_at": created_at.strftime("%Y-%m-%d"),
                    "tags": ", ".join([tag["name"] for tag in item["tags"]]),
                }
            )

        if len(items) < PER_PAGE:
            break  # 最後のページであればループを終了
        page += 1
        time.sleep(1)

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
```

</details>

<details><summary>main.py</summary>

```python:main.py
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
```

</details>

## 利用している API について

[`GET /api/v2/authenticated_user/items`](https://qiita.com/api/v2/docs#get-apiv2authenticated_useritems) により，認証中のユーザーの記事の一覧を作成日時の降順で取得できます．レスポンスには，各記事の以下の情報を含まれます． (以下の情報以外のメタデータも含んでおります．詳細は [API リファレンス](https://qiita.com/api/v2/docs#get-apiv2authenticated_useritems)を参照下さい．)

- id: 記事の ID
- title: 記事のタイトル
- created_at: 作成日時
- updated_at: 更新日時
- likes_count: いいね数
- stocks_count: ストック数
- comments_count: コメント数
- page_views_count: 閲覧数

:::note warn
[`GET /api/v2/authenticated_user/items`](https://qiita.com/api/v2/docs#get-apiv2authenticated_useritems) で記事の ID を取得し，それを基に [`GET /api/v2/items/:item_id`](https://qiita.com/api/v2/docs#get-apiv2itemsitem_id) で閲覧数を取得している他の記事もありましたが，前者の API のみで得られる情報は包含されています．
:::

## コードの簡易説明

本実装では，`analyzer.py` で定義している関数 `get_article_stats` にて，Qiita API を利用した集計処理を行っています．アルゴリズムとしては以下です．

- ページング処理により記事を取得し，集計を実施
  - 指定した期間内の記事，または，限定共有記事でないものを対象とする
  - 関数 `get_user_items` で，認証中のユーザーの記事の一覧を作成日時の降順で取得
- 記事の以下の詳細情報を抽出
  - タイトル
  - いいね数
  - ストック数
  - View 数
  - 作成日
  - タグ

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

            all_views += item["page_views_count"]
            all_likes += item["likes_count"]
            all_stocks += item["stocks_count"]
            items_count += 1

            articles.append(
                {
                    "title": item["title"],
                    "likes": item["likes_count"],
                    "stocks": item["stocks_count"],
                    "views": item["page_views_count"],
                    "created_at": created_at.strftime("%Y-%m-%d"),
                    "tags": ", ".join([tag["name"] for tag in item["tags"]]),
                }
            )

        if len(items) < PER_PAGE:
            break  # 最後のページであればループを終了
        page += 1
        time.sleep(1)

    return articles, all_views, all_likes, all_stocks, items_count
```

上記の関数を改修することで，例えば指定のタグが付与された記事のみを集計することも可能です．

## まとめ

Qiita API を利用して，指定の期間に投稿した記事の閲覧数・いいね数を取得し，集計する Python スクリプトを作成しました．本稿が，Qiita API を利用した集計を行う際の参考になりましたら幸いです．是非本実装をカスタマイズしてお使い下さい！

<!--
## 仲間募集

NTT データ デジタルサクセスコンサルティング事業部 では、以下の職種を募集しています。

<details><summary>1. クラウド技術を活用したデータ分析プラットフォームの開発・構築(ITアーキテクト/クラウドエンジニア)</summary>

クラウド／プラットフォーム技術の知見に基づき、DWH、BI、ETL 領域におけるソリューション開発を推進します。
https://enterprise-aiiot.nttdata.com/recruitment/career_sp/cloud_engineer

</details>

<details><summary>2. データサイエンス領域（データサイエンティスト／データアナリスト）</summary>

データ活用／情報処理／AI／BI／統計学などの情報科学を活用し、よりデータサイエンスの観点から、データ分析プロジェクトのリーダーとしてお客様の DX／デジタルサクセスを推進します。
https://enterprise-aiiot.nttdata.com/recruitment/career_sp/datascientist

</details>

<details><summary>3.お客様のAI活用の成功を推進するAIサクセスマネージャー</summary>

DataRobot をはじめとした AI ソリューションやサービスを使って、
お客様の AI プロジェクトを成功させ、ビジネス価値を創出するための活動を実施し、
お客様内での AI 活用を拡大、NTT データが提供する AI ソリューションの利用継続を推進していただく人材を募集しています。
https://nttdata.jposting.net/u/job.phtml?job_code=804

</details>

<details><summary>4.DX／デジタルサクセスを推進するデータサイエンティスト《管理職/管理職候補》</summary>
データ分析プロジェクトのリーダとして、正確な課題の把握、適切な評価指標の設定、分析計画策定や適切な分析手法や技術の評価・選定といったデータ活用の具現化、高度化を行い分析結果の見える化・お客様の納得感醸成を行うことで、ビジネス成果・価値を出すアクションへとつなげることができるデータサイエンティスト人材を募集しています。

https://nttdata.jposting.net/u/job.phtml?job_code=898

</details>

## ソリューション紹介

<details><summary> Trusted Data Foundationについて</summary><div>

～データ資産を分析活用するための環境をオールインワンで提供するソリューション～
https://enterprise-aiiot.nttdata.com/tdf/
最新のクラウド技術を採用して弊社が独自に設計したリファレンスアーキテクチャ（Datalake+DWH+AI/BI）を顧客要件に合わせてカスタマイズして提供します。
可視化、機械学習、DeepLearning などデータ資産を分析活用するための環境がオールインワンで用意されており、これまでとは別次元の量と質のデータを用いてアジリティ高く DX 推進を実現できます。

</div></details>

<details><summary> TDF-AM（Trusted Data FoundationⓇ - Analytics Managed Service）について</summary><div>

～データ活用基盤の段階的な拡張支援 (Quick Start) と保守運用のマネジメント（Analytics Managed）をご提供することでお客様の DX を成功に導く、データ活用プラットフォームサービス～
https://enterprise-aiiot.nttdata.com/service/tdf/tdf_am
TDFⓇ-AM は、データ活用を Quick に始めることができ、データ活用の成熟度に応じて段階的に環境を拡張します。プラットフォームの保守運用は NTT データが一括で実施し、お客様は成果創出に専念することが可能です。また、日々最新のテクノロジーをキャッチアップし、常に活用しやすい環境を提供します。なお、ご要望に応じて上流のコンサルティングフェーズから AI/BI などのデータ活用支援に至るまで、End to End で課題解決に向けて伴走することも可能です。

</div></details>

<details><summary>NTTデータとTableauについて </summary><div>

ビジュアル分析プラットフォームの Tableau と 2014 年にパートナー契約を締結し、自社の経営ダッシュボード基盤への採用や独自のコンピテンシーセンターの設置などの取り組みを進めてきました。さらに 2019 年度には Salesforce とワンストップでのサービスを提供開始するなど、積極的にビジネスを展開しています。

これまで Partner of the Year, Japan を 4 年連続で受賞しており、2021 年にはアジア太平洋地域で最もビジネスに貢献したパートナーとして表彰されました。
また、2020 年度からは、Tableau を活用したデータ活用促進のコンサルティングや導入サービスの他、AI 活用やデータマネジメント整備など、お客さまの企業全体のデータ活用民主化を成功させるためのノウハウ・方法論を体系化した「デジタルサクセス」プログラムを提供開始しています。
https://enterprise-aiiot.nttdata.com/service/tableau

</div></details>

<details><summary>NTTデータとAlteryxについて </summary><div>
Alteryxは、業務ユーザーからIT部門まで誰でも使えるセルフサービス分析プラットフォームです。

Alteryx 導入の豊富な実績を持つ NTT データは、最高位にあたる Alteryx Premium パートナーとしてお客さまをご支援します。

導入時のプロフェッショナル支援など独自メニューを整備し、特定の業種によらない多くのお客さまに、Alteryx を活用したサービスの強化・拡充を提供します。

https://enterprise-aiiot.nttdata.com/service/alteryx

</div></details>

<details><summary>NTTデータとDataRobotについて </summary><div>
DataRobotは、包括的なAIライフサイクルプラットフォームです。

NTT データは DataRobot 社と戦略的資本業務提携を行い、経験豊富なデータサイエンティストが AI・データ活用を起点にお客様のビジネスにおける価値創出をご支援します。

https://enterprise-aiiot.nttdata.com/service/datarobot

</div></details>

<details><summary> NTTデータとInformaticaについて</summary><div>

データ連携や処理方式を専門領域として 10 年以上取り組んできたプロ集団である NTT データは、データマネジメント領域でグローバルでの高い評価を得ている Informatica 社とパートナーシップを結び、サービス強化を推進しています。
https://enterprise-aiiot.nttdata.com/service/informatica

</div></details>

<details><summary>NTTデータとSnowflakeについて </summary><div>
NTTデータでは、Snowflake Inc.とソリューションパートナー契約を締結し、クラウド・データプラットフォーム「Snowflake」の導入・構築、および活用支援を開始しています。

NTT データではこれまでも、独自ノウハウに基づき、ビッグデータ・AI など領域に係る市場競争力のあるさまざまなソリューションパートナーとともにエコシステムを形成し、お客さまのビジネス変革を導いてきました。
Snowflake は、これら先端テクノロジーとのエコシステムの形成に強みがあり、NTT データはこれらを組み合わせることでお客さまに最適なインテグレーションをご提供いたします。

https://enterprise-aiiot.nttdata.com/service/snowflake

</div></details> -->
