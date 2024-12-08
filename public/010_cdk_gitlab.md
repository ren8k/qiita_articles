---
title: CodeCommit の代替として Gitlab on ECS を CDK で一撃で構築する
tags:
  - AWS
  - GitLab
  - CDK
  - ECS
  - EFS
private: true
updated_at: ""
id: null
organization_url_name: null
slide: false
ignorePublish: true
---

## はじめに

株式会社 NTT データ デジタルサクセスコンサルティング事業部の [@ren8k](https://qiita.com/ren8k) です．

初めて CDK を使ってみた．加えて，TypeScript での開発も初めて．入門記事です．

苦戦した部分も沢山あるので，備忘録として記事に残します．

ECS で EFS をマウントするケースで CDK 化する際の参考となれば幸いです！

なお，CDK の実装は以下のリポジトリに公開しております．

https://github.com/ren8k/aws-cdk-gitlab-on-ecs

## TL;DR

- CodeCommit の代替として，Gitlab のセルフホスティングを検討
- AWS CDK を利用した GitLab on ECS を一撃でデプロイする実装の解説
  - ECS から EFS へマウントする際の Tip
- Gitlab をコンテナホストする際の Tips を共有

## 背景

新規 AWS アカウント上で，[SageMaker AI Project Templates](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-projects-templates-sm.html) を利用する必要がありました．SageMaker AI Project Templates とは，SageMaker AI を利用した MLOps を実現するために，以下の AWS リソースを CloudFormation で一括構築することができるテンプレートです．

![mlops-architecture.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/c66a4c7e-c4f8-db14-996d-38e09ed36d5b.png)

> SageMaker AI Project Templates を利用することで，モデルの学習〜デプロイ〜モデル・データの品質モニタリングまでの一連のプロセスを自動化する MLOps アーキテクチャを構築することができます．なお，Training Pipeline 部は一部省略しています．

SageMaker AI Project Templates では，MLOps の CI/CD パイプライン用のリポジトリとして，CodeCommit または 3rd party 製の Git リポジトリサービスが利用可能です．しかし，2024/7/25 以降，新規 AWS アカウントにおいて，[CodeCommit は利用不可能](https://aws.amazon.com/jp/blogs/devops/how-to-migrate-your-aws-codecommit-repository-to-another-git-provider/)なため，3rd party 製の Git リポジトリサービスを利用する必要がありました．

そこで，CodeCommit の代替として GitLab をセルフホスティングすることを検討しました．本検討の理由は以下です．

- セキュリティ要件により、インターネット上の Git リポジトリサービスの利用には制限がある
  - 一定の承認プロセスを経れば利用可能だが、社内手続きが複雑でかなり時間がかかる
- GitLab は，Issue 管理，Wiki などの機能が豊富である

ただし，利用する AWS サービスの選定や，アーキテクチャの検討，CDK での IaC 化を行う際に，色々苦戦した部分が多かったので，本稿ではその解説や Tips の共有を行います．

:::note
筆者は Data Scientist であり，CDK は初学者でしたので，余計に苦戦しました．
:::

## ソリューション（アーキテクチャ）

GitLab リポジトリのインフラストラクチャ部分は可能な限り管理しなくて済むように検討した結果，ECS on Fargate + EFS の構成を採用しました．

![gitlab_architecture.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/166eb897-c701-6690-1e21-4321679840a1.png)

本ソリューションの特徴は以下です．

- **メンテナンスの労力が少ないフルマネージドサービスを採用**
  - ECS Fargate, EFS を使用
    - ECS，EFS は共に Private Subnet に配置し，Public Subnet に配置した ALB を経由して外部からのアクセスを許可
    - GitLab リポジトリのデータ永続化のために EFS を利用
- **コスト効率の良いアーキテクチャ設計**
  - NAT Gateway の代わりに NAT インスタンスを使用可能
- **既存の AWS リソースとの連携**
  - 既存の VPC 内で GitLab をホスト可能
  - 既存のドメインの使用が可能

https://zenn.dev/tech4anyone/articles/62f360ccea30ca

:::note warn
Twitter でご教示いただいたのですが，EFS (やその他の Cloud File System) は、GitLab が「使わないことを強く推奨」のようです．
本番環境の際には，EFS ではなく，DB などの永続化ストレージを使うことをお勧めします．

一方，個人用途や少人数での検証用途などであれば，本構成でも問題無いかと思います．（検証にて，3~4 名で 1~2 ヶ月利用していますが，今の所問題は生じておりません．）

https://chatgpt.com/c/67472a07-5da0-800a-b9ab-88d4df6eb2ad
:::
https://docs.gitlab.com/ee/administration/nfs.html#avoid-using-cloud-based-file-systems

## コード (各コンストラクタ) の解説

利用する AWS サービス毎に，以下のコンストラクタを用意しました．

- Network (VPC)
- Storage (EFS)
- Security (Secrets Manager, IAM Role)
- LoadBalancer (ALB, DNS)
- EFS Initialization (Lambda)
- Computing (ECS, Fargate)

以降，各コンストラクタの実装について解説します．

### Network (VPC)

### Storage (EFS)

### Security (Secrets Manager, IAM Role)

あと，ECS から EFS へのマウントに必要なポリシーもなかなか記載が見つからないので有益だと思われる

https://aws.amazon.com/jp/blogs/news/developers-guide-to-using-amazon-efs-with-amazon-ecs-and-aws-fargate-part-2/

https://github.com/aws/aws-cdk/issues/13442

うーん，やっぱ read write のポリシーを明示する必要があるっぽい

```
ResourceInitializationError: failed to invoke EFS utils commands to set up EFS volumes: stderr: b'mount.nfs4: access denied by server while mounting 127.0.0.1:/srv/gitlab/data' Traceback (most recent call last): File "/usr/sbin/supervisor_mount_efs", line 52, in <module> return_code = subprocess.check_call(["mount", "-t", "efs", "-o", opts, args.fs_id_with_path, args.dir_in_container], shell=False) File "/usr/lib64/python3.9/subprocess.py", line 373, in check_call raise CalledProcessError(retcode, cmd) subprocess.CalledProcessError: Command '['mount', '-t', 'efs', '-o', 'noresvport,tls,iam,awscredsuri=/v2/credentials/3f626a1f-4f38-4a0c-8a8a-d12e68b2995d', 'fs-0486fc40aef1fa1a5:/srv/gitlab/data', '/efs-vols/data']' returned non-zero exit status 32. During handling of the above exception, another exception occurred: Traceback (most recent call last): File "/usr/sbin/supervisor_mount_efs", line 56, in <module> "message": err.message, AttributeError: 'CalledProcessError' object has n: unsuccessful EFS utils comma
```

あと，ECS にログインするためのポリシーも付与している．
ECS へのログインはこのシェルでできますよ．

### LoadBalancer (ALB, DNS)

### EFS Initialization (Lambda)

### Computing (ECS, Fargate)

- FileSystem.connections を使用して ECS サービスからのインバウンドを許可するようにしましょう。

### (その他)Stack

dependencies を明示しなければ，スタック削除時にエラーが発生

Lambda と VPC の削除順序を制御できていない．
Lambda と VPC の削除が同時に行われているように見える．

## Gitlab セルフホスティングの Tips

本節では，実際に Gitlab セルフホスティングを構築する際に詰まった点や，ポイントについて共有します．

### Gitlab の外部 URL (https) の設定

https 化する場合，コンテナの設定が必要

- https://stackoverflow.com/questions/51487180/gitlab-set-external-url-to-https-without-certificate
  - gitlab は、external url に https を含む url を仕込むと、内部で 443 ポートを自動で利用してしまう可能性あり
  - https://chatgpt.com/c/67106314-1cf0-800a-a96b-4d84568918f7
  - https://chatgpt.com/c/671079f4-22e0-800a-8d14-4a42a117f032

```
 リバースプロキシ（nginxなど）でSSL通信を終端させ、GitLabコンテナとの通信はHTTP（ポート80）で行います。クライアントからのリクエストはHTTPS（ポート443）で受け取り、GitLabにはHTTPでリクエストを転送する形です。
```

### アクセスポイントを利用する場合，git clone できない問題

- パーミッションのせい

### ヘルスチェックパスについて

以下記載のエンドポイントでは，期待するレスポンスが返ってこない

https://docs.gitlab.com/ee/administration/monitoring/health_check.html

現在は，/-users/sign_in に対してヘルスチェックを行っている

### コンテナ起動後の Gitlab の起動に時間がかかり、ヘルスチェックを開始するタイミングをずらす必要がある

Gitlab のヘルスチェックパスが誤っており、ALB 側のヘルスチェックにも失敗してしまっていたため

## 利用手順

### AWS CDK コマンドの場合

### AWS CloudShell の場合

## Gitlab の初回サインイン方法

![gitlab_signin.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/a960c7ed-c682-e29c-fea4-2287b2051081.png)

https://qiita.com/takoikakani/items/936faf23ee6bc286a270

## まとめ

summary

## 謝辞

<!-- ## 仲間募集

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
https://www.nttdata.com/jp/ja/lineup/tdf/
最新のクラウド技術を採用して弊社が独自に設計したリファレンスアーキテクチャ（Datalake+DWH+AI/BI）を顧客要件に合わせてカスタマイズして提供します。
可視化、機械学習、DeepLearning などデータ資産を分析活用するための環境がオールインワンで用意されており、これまでとは別次元の量と質のデータを用いてアジリティ高く DX 推進を実現できます。

</div></details>

<details><summary> TDFⓇ-AM（Trusted Data Foundation - Analytics Managed Service）について</summary><div>

～データ活用基盤の段階的な拡張支援 (Quick Start) と保守運用のマネジメント（Analytics Managed）をご提供することでお客様の DX を成功に導く、データ活用プラットフォームサービス～
https://www.nttdata.com/jp/ja/lineup/tdf_am/
TDFⓇ-AM は、データ活用を Quick に始めることができ、データ活用の成熟度に応じて段階的に環境を拡張します。プラットフォームの保守運用は NTT データが一括で実施し、お客様は成果創出に専念することが可能です。また、日々最新のテクノロジーをキャッチアップし、常に活用しやすい環境を提供します。なお、ご要望に応じて上流のコンサルティングフェーズから AI/BI などのデータ活用支援に至るまで、End to End で課題解決に向けて伴走することも可能です。

</div></details>

<details><summary> NTTデータとDatabricksについて </summary>
NTTデータは、お客様企業のデジタル変革・DXの成功に向けて、「databricks」のソリューションの提供に加え、情報活用戦略の立案から、AI技術の活用も含めたアナリティクス、分析基盤構築・運用、分析業務のアウトソースまで、ワンストップの支援を提供いたします。

https://www.nttdata.com/jp/ja/lineup/databricks/

</details>

<details><summary>NTTデータとTableauについて </summary><div>

ビジュアル分析プラットフォームの Tableau と 2014 年にパートナー契約を締結し、自社の経営ダッシュボード基盤への採用や独自のコンピテンシーセンターの設置などの取り組みを進めてきました。さらに 2019 年度には Salesforce とワンストップでのサービスを提供開始するなど、積極的にビジネスを展開しています。

これまで Partner of the Year, Japan を 4 年連続で受賞しており、2021 年にはアジア太平洋地域で最もビジネスに貢献したパートナーとして表彰されました。
また、2020 年度からは、Tableau を活用したデータ活用促進のコンサルティングや導入サービスの他、AI 活用やデータマネジメント整備など、お客さまの企業全体のデータ活用民主化を成功させるためのノウハウ・方法論を体系化した「デジタルサクセス」プログラムを提供開始しています。

https://www.nttdata.com/jp/ja/lineup/tableau/

</div></details>

<details><summary>NTTデータとAlteryxについて </summary><div>
Alteryxは、業務ユーザーからIT部門まで誰でも使えるセルフサービス分析プラットフォームです。

Alteryx 導入の豊富な実績を持つ NTT データは、最高位にあたる Alteryx Premium パートナーとしてお客さまをご支援します。

導入時のプロフェッショナル支援など独自メニューを整備し、特定の業種によらない多くのお客さまに、Alteryx を活用したサービスの強化・拡充を提供します。

https://www.nttdata.com/jp/ja/lineup/alteryx/

</div></details>

<details><summary>NTTデータとDataRobotについて </summary><div>
DataRobotは、包括的なAIライフサイクルプラットフォームです。

NTT データは DataRobot 社と戦略的資本業務提携を行い、経験豊富なデータサイエンティストが AI・データ活用を起点にお客様のビジネスにおける価値創出をご支援します。

https://www.nttdata.com/jp/ja/lineup/datarobot/

</div></details>

<details><summary> NTTデータとInformaticaについて</summary><div>

データ連携や処理方式を専門領域として 10 年以上取り組んできたプロ集団である NTT データは、データマネジメント領域でグローバルでの高い評価を得ている Informatica 社とパートナーシップを結び、サービス強化を推進しています。

https://www.nttdata.com/jp/ja/lineup/informatica/

</div></details>

<details><summary>NTTデータとSnowflakeについて </summary><div>
NTTデータでは、Snowflake Inc.とソリューションパートナー契約を締結し、クラウド・データプラットフォーム「Snowflake」の導入・構築、および活用支援を開始しています。

NTT データではこれまでも、独自ノウハウに基づき、ビッグデータ・AI など領域に係る市場競争力のあるさまざまなソリューションパートナーとともにエコシステムを形成し、お客さまのビジネス変革を導いてきました。
Snowflake は、これら先端テクノロジーとのエコシステムの形成に強みがあり、NTT データはこれらを組み合わせることでお客さまに最適なインテグレーションをご提供いたします。

https://www.nttdata.com/jp/ja/lineup/snowflake/

</div></details> -->
