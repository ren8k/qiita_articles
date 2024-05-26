---
title: 世界最速！？Amazon Bedrock の Custom model import の機能検証
tags:
  - AWS
  - bedrock
  - 生成AI
  - LLM
  - Llama3
private: true
updated_at: '2024-05-26T18:38:41+09:00'
id: 97022fa42dde9c8e8fd8
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

株式会社 NTT データ デザイン＆テクノロジーコンサルティング事業本部の [@ren8k](https://qiita.com/ren8k) です。2024/04/23 に，Amazon Bedrock で [Custom model import](https://docs.aws.amazon.com/bedrock/latest/userguide/model-customization-import-model.html) の機能がリリースされました。しかし，本機能を利用するためには，Bedrock の Service Quotas にて複数項目の上限緩和申請が必要な上，通常の申請フローでは利用が困難のようです．（X を見ると，申請承認に時間がかかる or 用途によっては reject される模様です．）

そこで，AWS Partner Solutions Architect(PSA)の方と連携し，Service Quotas の上限緩和申請を優先的に承認していただくことで，本機能を利用することができました．

本記事では，Custom model import の利用手順および，機能検証した結果を共有いたします。

https://aws.amazon.com/jp/about-aws/whats-new/2024/04/custom-model-import-amazon-bedrock/

https://aws.amazon.com/jp/blogs/aws/import-custom-models-in-amazon-bedrock-preview/

:::note info
本機能を検証するにあたり，ご協力いただいた AWS Partner Solutions Architect の方，および，海外の Bedrock チームの方々には感謝申し上げます．
:::

:::note warn
本記事の内容は執筆時点（2024/05/25）の情報に基づいており，閲覧日時点での情報と異なる可能性があります．加えて，Custom model import は現在 Public Preview の機能であり，機能や仕様が変更される可能性もある点にご注意下さい．
:::

## Custom model import とは

Amazon SageMaker や他の機械学習プラットフォームで学習させたモデルを Amazon Bedrock に取り込み，Bedrock の API を通じてモデルを呼び出し推論することができる機能です．

現時点では，本機能は以下のモデルアーキテクチャーをサポートしています．

- Llama2 と Llama3
- Mistral
- FLAN-T5

インポート元として，Amazon SageMaker や Amazon S3 からモデルを選択することが可能です．S3 からモデルをインポートする場合，モデルファイルは Hugging Face の safetensors 形式で保存されている必要があります．

## 利用手順

現時点（2024/05/25）では，以下のフローで Custom model import を利用することができます．

- Service Quotas の上限緩和申請
- S3 へモデルをアップロード
- Model Import Job の実行

## Service Quotas の上限緩和申請

後続の Import job の実行のため，以下の 2 つの Service Quotas の上限緩和申請が必要です．

- `Concurrent model import jobs`
- `Imported models per account`

特に 2 つ目の上限緩和には，かなり時間がかかる可能性があります．具体的には，海外の Bedrock チームからユースケースの詳細を求められ，その後，Bedrock チームおよび，担当者によるユースケースのレビューを通過するまで待つ必要があります．私の場合，PSA の方にご協力いただけたので，1~2 週間程度で承認されました．

## S3 へモデルをアップロード

バージニア北部の任意の S3 バケットにモデルをアップロードします．本検証では，rinna 社が提供する Llama3 の日本語継続事前学習モデルである [Llama 3 Youko 8B](https://huggingface.co/rinna/llama-3-youko-8b) を利用しました．Llama 3 Youko 8B は，80 億パラメータの Llama 3 8B に対して，日本語と英語の学習データ 220 億トークンを用いて継続事前学習したモデルです．[[1]](https://rinna.co.jp/news/2024/05/20240507.html)

以下に実行したコマンドを示します．

- git lfs のインストール

```bash
sudo apt install git-lfs
```

- モデルのダウンロード

```bash
git clone https://huggingface.co/rinna/llama-3-youko-8b
```

- S3 へのアップロード（下記の`<your bucket>` は，任意のバケット名に置き換えてください．）

```bash
aws s3 cp llama-3-youko-8b/ s3://<your bucket>/llama-3-youko-8b --recursive
```

:::note warn
モデルファイルの総量は 約 30GB あるので，S3 への転送時間が少しかかります．また，Cloud9 などでアップロードする場合，ディスク容量にご注意下さい．
:::

## Model Import Job の実行

実際の操作画面を示しながら，手順を解説いたします．

- バージニア北部リージョンで，Amazon Bedrock コンソールから，ナビケーションペインの [基盤モデル] セクションから [Imported models] を選択します．

![000.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/f7752729-bec9-c34d-bf13-8c25580e9252.png)

- [Import model] を選択します．

![001.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/8bcfc966-bc03-db37-8477-287b82ea75d1.png)

- `Model Import Job` を実行するため，以下の情報を入力します．その他の項目は，デフォルト値のままで問題ございません．
  - `Model name`: 任意のモデル名
  - `S3の場所`: 先ほどアップロードしたモデルの S3 URI

<img width="500" src="https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/eedc2fdb-c10a-1b51-0a96-7223d8663153.png">

- `Model Import Job`が開始されます．Status が`Importing`から`Completed`に変わるまで待ちます．

![003.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/90e48e5c-a619-9f52-220d-d20ed91db5ff.png)

- `Model Import Job`が完了すると，Status が`Completed`に変わります．私の環境では約 10~15 分程度で完了しました．

![004.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/ed3ad2b4-1239-f1cc-ba24-09f29465536d.png)

- [Models] を選択し，モデル名を選択すると，モデルの S3 URI や，インポートしたモデルの Model ARN などの詳細情報を確認できます。また，右上の [Open in playground] を選択すると，プレイグラウンドでの検証が可能です．

★TODO: 追加（Model タブを選択した際の画面）
★TODO: 追加（モデルの詳細）

- 以下がプレイグラウンドでの検証画面です．画面の左上に表示されているモデル名が，自身で Import したモデル名になっていることを確認できます．

★TODO: 追加（プレイグラウンドでの未入力画面）

## 機能検証

今回は，プレイグラウンド（GUI）および，API（CUI）を利用して，実際にインポートしたモデルで推論することができるかを検証しました．

### 検証設定

利用するモデルとしては，前述の [Llama 3 Youko 8B](https://huggingface.co/rinna/llama-3-youko-8b) を利用します．評価用データとしては，[JCommonsenseQA](https://huggingface.co/datasets/leemeng/jcommonsenseqa-v1.1) の validation データを利用しました．

### プロンプトの設定

以下のような，1-shot のプロンプトを与えました．

```
### 例 ###
質問: 電子機器で使用される最も主要な電子回路基板の事をなんと言う？
choice0: 掲示板
choice1: パソコン
choice2: マザーボード
choice3: ハードディスク
choice4: まな板
回答: <answer>マザーボード</answer>

質問: 次のうち、金管楽器であるのはどれ？
choice0: トランペット
choice1: ガラス
choice2: メビウス
choice3: メタル
choice4: 設計
回答:
```

### プレイグラウンドでの検証

前述のプロンプトをプレイグラウンドに入力し，停止シーケンスに`</answer>`を設定後，`実行`ボタンを押下しました．

★TODO: 追加（API での検証結果）

![005.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/33c11cd1-3d98-777f-b9ef-043bd9d6f9a8.png)

実行結果は以下です．適切にプロンプト内の質問に回答することできております．しかし，停止シーケンスに`</answer>`を設定しているにも関わらず，指定したシーケンスを含めた回答が続いており，不具合の可能性があります．

★TODO: 追加（API での検証結果）

![006.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/2a709da9-fb30-4769-164e-4f8dea33d539.png)

### API での検証

プレイグラウンドの右上にある 3 つの小さな縦のドットを選択し，`View API request` を選択することで，API リクエストの構文を確認できます．今回の検証では，以下の shell を利用しました．

通常の Bedrock の [invoke-model API](https://docs.aws.amazon.com/ja_jp/bedrock/latest/userguide/inference-invoke.html)を利用しておりますが，モデル ID にはインポートされたモデルの ARN を指定している点が特徴です．

★TODO: 下記では，停止シーケンスの設定がなされていない

```bash
PROMPT=$(cat <<EOD
### 例 ###
質問: 電子機器で使用される最も主要な電子回路基板の事をなんと言う？
choice0: 掲示板
choice1: パソコン
choice2: マザーボード
choice3: ハードディスク
choice4: まな板
回答: <answer>マザーボード</answer>

質問: 次のうち、金管楽器であるのはどれ？
choice0: トランペット
choice1: ガラス
choice2: メビウス
choice3: メタル
choice4: 設計
回答:
EOD
)

aws bedrock-runtime invoke-model \
--model-id arn:aws:bedrock:us-east-1:<account-id>:imported-model/XXXXXXXXXXXX \
--body "{\"prompt\":\"$PROMPT\",\"max_tokens\":512,\"top_k\":50,\"top_p\":0.9,\"stop\":[],\"temperature\":0.5}" \
--cli-binary-format raw-in-base64-out \
--region us-east-1 \
invoke-model-output.txt
```

結果としては，プレイグラウンドでの検証と同様の結果が得られました．

```
★TODO: 追加（API での検証結果）
```

## 機能改善のためリクエストしたい点

実際に機能を利用し，個人的に感じた改善点を以下に示します．

- Hugging Face 上のモデルを import する際に，URL を指定するだけで直接 import できる機能
  - 開発・Fine-Tuning したモデルを Hugging Face 上で公開することはデファクトスタンダードになっているため，Hugging Face の URL からモデルを直接 import できる機能があると便利だと考えております．
- 対応モデルの拡充
  - 現状， Llama2/3，Mistral，FLAN-T5 ベースのモデルのみ対応しておりますが，他のモデルにも対応していただけると汎用性が高まると考えております．
- Service Quotas での承認に要する時間の短縮
  - 他の Bedrocker にも利用いただき，多様な観点でのフィードバックを得るためにも，承認時間の短縮は望ましいと考えております．

## 一部不具合の可能性のある点

以下については，まだ preview 段階であり致し方ないということを前提に，AWS 社にフィードバックを行っております．

- コンソール上で`Model Import Job`を実行する際，下記項目のデフォルト設定値の datetime の month の値が先月の値になっている．
  - `Import job name `
  - `Service role`
- 停止シーケンスが正常に機能していない可能性がある．
  - 同様のプロンプトおよび停止シーケンスの設定で，Claude3 sonnet で試した場合，正常に機能していることを確認しております．

## まとめ

本記事では，Amazon Bedrock の Custom model import の機能を利用するための手順および機能検証結果を共有いたしました．外部で公開されているモデルを import し，統一的な Bedrock の API でモデルを利用することができるため，非常に便利な機能だと感じました．また，Bedrock のモデル評価機能である [Model Evaluation](https://aws.amazon.com/jp/blogs/aws/amazon-bedrock-model-evaluation-is-now-generally-available/) を利用することで，Bedrock 標準モデルとの比較評価も容易に行うことができそうです．

なお，リクエストしたい機能や一部不具合の可能性のある点については，AWS 社 にフィードバックを行っている状況です．今後の機能改善が楽しみです．

## 参考文献

[1] [rinna、Llama 3 の日本語継続事前学習モデル「Llama 3 Youko 8B」を公開](https://rinna.co.jp/news/2024/05/20240507.html)

## 仲間募集

NTT データ デザイン＆テクノロジーコンサルティング事業本部 では、以下の職種を募集しています。

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
