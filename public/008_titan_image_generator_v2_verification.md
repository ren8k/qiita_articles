---
title: Amazon Titan Image Generator v2の Deep Dive
tags:
  - AWS
  - bedrock
  - Python
  -
  - 生成AI
private: true
updated_at: ""
id: null
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

株式会社 NTT データ デジタルサクセスコンサルティング事業部の [@ren8k](https://qiita.com/ren8k) です．

v2 が使えるようになった．

https://aws.amazon.com/jp/about-aws/whats-new/2024/08/titan-image-generator-v2-amazon-bedrock/

機能が沢山増えた．改めて何ができるのかを確認する．

https://aws.amazon.com/jp/blogs/news/amazon-titan-image-generator-v2-is-now-available-in-amazon-bedrock/

## 目次

- はじめに
- Amazon Titan Image Generator v2 とは
- Amazon Titan Image Generator v2 の機能
- 各機能の紹介
- プロンプトエンジニアリングについて
- まとめ

## Amazon Titan Image Generator v2 とは

- Amazon 謹製の画像生成 AI
- 多機能
- 生成したという印もついてる
- データセットも安全なものを利用している
- その他あれば

入力の言語は英語のみ対応しており，最大 512 文字まで入力が可能です．その他詳細な仕様については，公式ドキュメントの[本ページ](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-image-models.html)に記載があります．

## Amazon Titan Image Generator v2 の機能一覧

| タスクタイプ | 機能                               | 説明                                           |
| ------------ | ---------------------------------- | ---------------------------------------------- |
| TEXT_IMAGE   | 画像生成                           | テキストプロンプトを使用して画像を生成します。 |
| TEXT_IMAGE   | 画像コンディショニング(Canny Edge) | Canny Edge 画像を生成します。                  |

---

| タスクタイプ              | 機能                               | 説明                                                                                                   |
| ------------------------- | ---------------------------------- | ------------------------------------------------------------------------------------------------------ |
| `TEXT_IMAGE`              | 画像生成                           | テキストプロンプトを使用して画像を生成。                                                               |
| `TEXT_IMAGE`              | 画像コンディショニング(Canny Edge) | 入力条件画像のレイアウトと構図に従う画像も生成可能。                                                   |
| `INPAINTING`              | 画像修正                           | マスクの内側を周囲の背景に合わせて変更し、画像を修正。                                                 |
| `OUTPAINTING`             | 画像拡張                           | マスクで定義された領域をシームレスに拡張し、画像を修正。                                               |
| `IMAGE_VARIATION`         | バリエーション生成                 | 元の画像のバリエーションを生成して画像を修正。                                                         |
| `COLOR_GUIDED_GENERATION` | 色指定画像生成                     | テキストプロンプトと Hex カラーコードのリストを使用し、指定カラーパレットに従う画像を生成（V2 のみ）。 |
| `BACKGROUND_REMOVAL`      | 背景除去                           | 複数のオブジェクトを識別し背景を削除、透明な背景の画像を出力（V2 のみ）。                              |

## 機能紹介

また，推論パラメーターについては，以下のパラメーターがあります．その他詳細な情報は公式ドキュメントの[本ページ](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-titan-image.html)に記載があります．

"numberOfImages": num_image, # Range: 1 to 5
"quality": "premium", # Options: standard/premium
"height": 1024, # Supported height list in the docs
"width": 1024, # Supported width list in the docs
"cfgScale": cfg_scale, # Range: 1.0 (exclusive) to 10.0
"seed": seed, # Range: 0 to 214783647

```python
def titan_image(
    payload: dict,
    num_image: int = 2,
    cfg: float = 10.0,
    seed: int = 42,
    modelId: str = "amazon.titan-image-generator-v2",
) -> list:
    #   ImageGenerationConfig Options:
    #   - numberOfImages: Number of images to be generated
    #   - quality: Quality of generated images, can be standard or premium
    #   - height: Height of output image(s)
    #   - width: Width of output image(s)
    #   - cfgScale: Scale for classifier-free guidance
    #   - seed: The seed to use for reproducibility
    body = json.dumps(
        {
            **payload,
            "imageGenerationConfig": {
                "numberOfImages": num_image,  # Range: 1 to 5
                "quality": "premium",  # Options: standard/premium
                "height": 1024,  # Supported height list above
                "width": 1024,  # Supported width list above
                "cfgScale": cfg,  # Range: 1.0 (exclusive) to 10.0
                "seed": seed,  # Range: 0 to 214783647
            },
        }
    )

    response = bedrock_runtime_client.invoke_model(
        body=body,
        modelId=modelId,
        accept="application/json",
        contentType="application/json",
    )

    response_body = json.loads(response.get("body").read())
    images = [
        Image.open(io.BytesIO(base64.b64decode(base64_image)))
        for base64_image in response_body.get("images")
    ]
    return images
```

### 画像生成

### 画像コンディショニング(Canny Edge)

違い: https://chatgpt.com/c/66e7db36-bc2c-800a-a4f0-5da080dcb115

Canny Edge を実際に試してみる

### 画像コンディショニング(Segmentation)

### インペインティング(Default)

### インペインティング(Removal)

小さいオブジェクトだとうまくいくかも

猫と犬が走ってる画像（画像中で中くらいにうつってる）を生成する

#### コラム

SAM とかでもマスクを取得可能であるというのをさらっと書く．

### アウトペインティング(Default)

### アウトペインティング(Precise)

マスク外部の情報も与えると良いらしい．

### イメージバリエーション

### カラーパレットによる画像ガイダンス

### 背景の削除

### サブジェクトの一貫性

fine-tuning のことでは？

fine-tuning 用のデータセットの準備が難しかったため，今回は検証を行っておりません．データセットの構造とかは以下の公式ドキュメントや公式ブログが参考になりそうです．

https://docs.aws.amazon.com/bedrock/latest/userguide/titan-image-models.html#titanimage-finetuning

https://aws.amazon.com/jp/blogs/news/fine-tune-your-amazon-titan-image-generator-g1-model-using-amazon-bedrock-model-customization/

---

ここでマスク画像は，黒塗り部分が inpaint 対象である点に注意（[DALL-E-3](https://platform.openai.com/docs/api-reference/images/createEdit#images-createedit-mask) や [Stable Diffusion 2 Inpainting](https://huggingface.co/stabilityai/stable-diffusion-2-inpainting) 系のモデルでは，白塗り部分が inpaint 対象である．）

SDXL の方が新しいかも？

https://huggingface.co/diffusers/stable-diffusion-xl-1.0-inpainting-0.1

https://qiita.com/nabata/items/86cb2ac5b3e345ea86a7#create-image-edit

## プロンプトエンジニアリングについて

Amazon Titan Image Generator v2 を利用する際，一般的な LLM と同様，プロンプトエンジニアリングが重要です．プロンプトエンジニアリングには以下の推奨事項があります．詳細は，[公式ドキュメント](https://docs.aws.amazon.com/bedrock/latest/userguide/titan-image-models.html#titanimage-prompt)や[プロンプトエンジニアリングガイドブック](https://d2eo22ngex1n9g.cloudfront.net/Documentation/User+Guides/Titan/Amazon+Titan+Image+Generator+Prompt+Engineering+Guidelines.pdf)を参照下さい．

- 画像生成の際，プロンプトを主題から始める．
  - 例: An image of a ...
- 可能な限り，詳細情報をプロンプトに含める．
  - 例: 表現方法（油彩/水彩画など），色，照明，備考，形容詞，品質，およびスタイル（印象派，写実的など）
- テキストを囲む場合，ダブルクオーテーション ("") を使用する．
  - 例: An image of a boy holding a sign that says "success"
- プロンプトの要素を論理的に順序付け，句読点を使用して関係性を示す．
  - 例: An image of a cup of coffee from the side, steam rising, on a wooden table,...
- プロンプトでは具体的な単語を使用し，必要に応じてネガティブプロンプトを使用する．
- インペインティング・アウトペインティングの場合，マスク領域内部だけでなく，マスク領域外部（背景）との関連性を記述する．

また，モデルの推論パラメーター (`cfgScale` や `numberOfImages`など) を調整することも重要です．

## まとめ

summary

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

</div></details>
