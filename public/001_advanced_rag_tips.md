---
title: Amazon Bedrock で Advanced RAG を実装する上での Tips
tags:
  - "AWS Bedrock"
  - "Bedrock"
  - "生成AI"
  - "RAG"
  - "Advanced RAG"
private: true
updated_at: ""
id: null
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

株式会社 NTT データ デザイン＆テクノロジーコンサルティング事業本部の@ren8k です。
2024/05/01 に，AWS から「[Amazon Kendra と Amazon Bedrock で構成した RAG システムに対する Advanced RAG 手法の精度寄与検証](https://aws.amazon.com/jp/blogs/news/verifying-the-accuracy-contribution-of-advanced-rag-methods-on-rag-systems-built-with-amazon-kendra-and-amazon-bedrock/)」という先進的なブログが公開されました．

https://aws.amazon.com/jp/blogs/news/verifying-the-accuracy-contribution-of-advanced-rag-methods-on-rag-systems-built-with-amazon-kendra-and-amazon-bedrock/

上記ブログの内容に感化され，AWS SDK for Python (Boto3)を利用して，ブログで紹介されている Advanced RAG の再現実装を私の方で行いました．その際に，Advanced RAG を実現する上での実装方法や Claude3 を利用する際のプロンプトエンジニアリングで学べた点が多かったので，本ブログにまとめようと思います．なお，Advanced RAG の再現実装（Python）は[本リポジトリ](https://github.com/ren8k/aws-bedrock-advanced-rag-baseline)に公開していますので，興味のある方はご参照ください．

https://github.com/ren8k/aws-bedrock-advanced-rag-baseline

## TL;DR

以下の Tips について重点的に解説しております．

- XML タグ，Chain Of Thought（CoT）を利用したプロンプトエンジニアリングが有効
- Python の非同期による並列実行が有効

## 目次

- Advanced RAG について
  - アルゴリズム：
  - pre-retrieve, retrieve, post-retrieve の各ステップにおける工夫
- 構築したアーキテクチャ
- 実施手順
  - 前提条件
  - Knowledge Base の作成（任意）
  - Advanced RAG の実行
- 実装の工夫・Tips
  - Pre-Retrieve での工夫
    - プロンプトエンジニアリング(JSON 形式での回答取得)
    - 複数回の実行
  - Retrieve での工夫
    - 並列実行
  - Post-Retrieve
    - プロンプトエンジニアリング(CoT，XML タグの利用)
    - 並列実行

## 構築したアーキテクチャ

## 実施手順

---

## 実装の工夫・Tips

### Pre-Retrieve: Claude3 を利用したクエリ拡張

クエリ拡張は，単一のクエリから多様な観点で複数のクエリを作成し，それらに対して検索を実行して検索結果をマージする手法です．これにより，クエリとソースドキュメントの表記・表現が異なる場合でも適切な回答を得ることを目的としています．特に，[RAG-Fusion](https://towardsdatascience.com/forget-rag-the-future-is-rag-fusion-1147298d8ad1)という手法では，LLM を利用してクエリ拡張を行うことが提案されています．

本実装では，Claude3 Haiku に対して 拡張したクエリを **JSON 形式**で出力させるため，以下の工夫を行っています．

1. Claude3 特有のプロンプトエンジニアリング
2. システムプロンプトおよび Claude3 の応答の事前入力の工夫
3. JSON 形式で取得できなかった場合は再度 Claude3 Haiku にリクエストを送信（リトライ）

以降，各工夫について詳細に解説します．

#### 1. Claude3 特有のプロンプトエンジニアリング

プロンプト中では以下の Tips を取り入れております．なお，プロンプトは[公式ブログ](https://aws.amazon.com/jp/blogs/news/verifying-the-accuracy-contribution-of-advanced-rag-methods-on-rag-systems-built-with-amazon-kendra-and-amazon-bedrock/)のものを流用させていただいております．

- 具体例を記載する(Few-shot Prompting)
- XML タグを利用した詳細な指示

以下にプロンプトを示します．なお，簡単のために，実際に利用されているプロンプトテンプレート中の変数を展開した状態で記載しています．プロンプトでは，`<example>`タグ内に具体例を，`<format>`タグ内に出力フォーマットを記載しております．Claude3 では，指示とコンテンツ・例をタグを利用し分離して提示することで，より精度の高い回答を得ることができます．詳細は，Anthropic の公式ドキュメントの「[Use XML tags](https://docs.anthropic.com/en/docs/use-xml-tags)」および「[Use examples](https://docs.anthropic.com/en/docs/use-examples)」を参照下さい．

```yaml:claude-3_query_expansion.yaml
検索エンジンに入力するクエリを最適化し、様々な角度から検索を行うことで、より適切で幅広い検索結果が得られるようにします。
具体的には、類義語や日本語と英語の表記揺れを考慮し、多角的な視点からクエリを生成します。

以下の<question>タグ内にはユーザーの入力した質問文が入ります。
この質問文に基づいて、3個の検索用クエリを生成してください。
各クエリは30トークン以内とし、日本語と英語を適切に混ぜて使用することで、広範囲の文書が取得できるようにしてください。

生成されたクエリは、<format>タグ内のフォーマットに従って出力してください。

<example>
question: Knowledge Bases for Amazon Bedrock ではどのベクトルデータベースを使えますか？
query_1: Knowledge Bases for Amazon Bedrock vector databases engine DB
query_2: Amazon Bedrock ナレッジベース ベクトルエンジン vector databases DB
query_3: Amazon Bedrock RAG 検索拡張生成 埋め込みベクトル データベース エンジン
</example>

<format>
JSON形式で、各キーには単一のクエリを格納する。
</format>

<question>
{question}
</question>
```

#### 2. システムプロンプトおよび Claude3 の応答の事前入力の工夫

- システムプロンプトでも有効な JSON 形式での出力を指定
- Claude3 の引数 messages では，prefill の Assistant フィールドに`{`を指定[^2-2]
  https://docs.anthropic.com/ja/docs/control-output-format

```yaml
anthropic_version: bedrock-2023-05-31
max_tokens: 1000
temperature: 0
system: Respond valid json format.
# https://docs.anthropic.com/claude/docs/control-output-format#prefilling-claudes-response
messages:
  [
    { "role": "user", "content": [{ "type": "text", "text": "{prompt}" }] },
    { "role": "assistant", "content": [{ "type": "text", "text": "{" }] },
  ]
stop_sequences: ["</output>"]
```

実際にクエリ拡張際に得られるクエリ(例)を以下に示す．

```json
{
  "query_1": "Amazon generative AI models language GPT-3 Alexa",
  "query_2": "Amazon generative AI 生成モデル 自然言語処理 AI",
  "query_3": "Amazon generative AI 言語生成 人工知能 AI技術"
}
```

### Retrieve での工夫

### Post-Retrieve での工夫

## まとめ

## 仲間募集

NTT データ テクノロジーコンサルティング事業本部 では、以下の職種を募集しています。

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

～データ活用基盤の段階的な拡張支援（Quick Start) と保守運用のマネジメント（Analytics Managed）をご提供することでお客様の DX を成功に導く、データ活用プラットフォームサービス～
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
