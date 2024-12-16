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

- CodeCommit の代替として Gitlab のセルフホスティングを検討
- AWS CDK を利用した GitLab on ECS を一撃でデプロイする実装の解説
  - ECS に EFS をマウントする際の Tips や CDK 実装例を提示
- Gitlab をコンテナホストする際の Tips を共有

## 背景

新規 AWS アカウント上で，[SageMaker AI Project Templates](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-projects-templates-sm.html) を利用する必要がありました．SageMaker AI Project Templates とは，SageMaker AI を利用した MLOps を迅速に実現するために，以下の AWS リソースを CloudFormation で一括構築することができるテンプレートです．

![mlops-architecture.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/c66a4c7e-c4f8-db14-996d-38e09ed36d5b.png)

> SageMaker AI Project Templates を利用することで，モデルの学習〜デプロイ〜モデル・データの品質モニタリングまでの一連のプロセスを自動化する MLOps アーキテクチャを構築することができます．なお，Training Pipeline 部は一部省略しています．

SageMaker AI Project Templates では，MLOps の CI/CD パイプライン用のリポジトリとして CodeCommit または 3rd party 製の Git リポジトリサービスが利用可能です．しかし，2024/7/25 以降，新規 AWS アカウントにおいて，[CodeCommit は利用不可能](https://aws.amazon.com/jp/blogs/devops/how-to-migrate-your-aws-codecommit-repository-to-another-git-provider/)なため，3rd party 製の Git リポジトリサービスを利用する必要がありました．

そこで，CodeCommit の代替として GitLab をセルフホスティングすることを検討しました．本検討の理由は以下です．

- セキュリティ要件により、インターネット上の Git リポジトリサービスの利用には制限がある
  - 一定の承認プロセスを経れば利用可能だが、社内手続きが複雑でかなり時間がかかる
- GitLab は，Issue 管理，Wiki などの機能が豊富である

ただし，利用する AWS サービスの選定や，アーキテクチャの検討，CDK での IaC 化を行う際に色々苦戦した部分が多かったので，本稿ではその解説や Tips の共有を行います．

:::note info
筆者は Data Scientist であり，CDK に関しては初学者でしたので，余計に苦戦しました．
:::

## ソリューション（アーキテクチャ）

GitLab の運用に必要なインフラストラクチャの管理工数を最小限に抑えるため，ECS on Fargate + EFS の構成を採用しました．

![gitlab_architecture.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/166eb897-c701-6690-1e21-4321679840a1.png)

本ソリューションの特徴は以下です．

- **メンテナンスの労力が少ないフルマネージドサービスを採用**
  - ECS Fargate, EFS を使用
    - ECS，EFS は共に Private Subnet に配置し，Public Subnet に配置した ALB を経由して外部からのアクセスを許可
    - GitLab リポジトリのデータ永続化のために EFS を利用
    - GitLab の root ユーザーのパスワードは AWS Secrets Manager に保存
- **コスト効率の良いアーキテクチャ設計**
  - NAT Gateway の代わりに NAT インスタンスを使用可能
- **既存の AWS リソースとの連携**
  - 既存の VPC 内で GitLab をホスト可能
  - 既存のドメインの使用が可能

:::note warn
X でご教示いただいたのですが，GitLab では，EFS やその他の [Cloud File System の利用を推奨していません](https://docs.gitlab.com/ee/administration/nfs.html#avoid-using-cloud-based-file-systems)．I/O レイテンシによるパフォーマンスの低下のためです．具体的には，Git による多数の小規模ファイルの逐次書き込みの処理特性が，クラウドベースのファイルシステムと相性が悪いためです．

本番運用の場合や，大規模な利用を想定する場合には，ECS on EC2 (+EBS) の利用や，EC2 への GitLab のインストールを検討した方が良いと考えられます．一方で，個人用途や少人数での検証用途などであれば，本構成でも問題無いとも考えております．（実際 3~4 名で 1~2 ヶ月利用していますが，今の所問題は生じておりません．）
:::

## コード (各コンストラクタ) の解説

利用する AWS サービス毎に，以下のコンストラクタを用意しました．

- Network (VPC)
- Storage (EFS)
- Security (Secrets Manager)
- LoadBalancer (ALB, DNS)
- EFS Initialization (Lambda)
- Computing (ECS, Fargate)

以降，各コンストラクタの実装について解説します．

:::note info
ECS に EFS をマウントする際，以下の設定が必要です．

- grantReadWrite で ECS タスクに対して EFS への読み書き権限を付与
  - マウントに必要なポリシーについて: https://docs.aws.amazon.com/ja_jp/AmazonECS/latest/developerguide/tutorial-efs-volumes.html
  - "elasticfilesystem:ClientMount"
  - "elasticfilesystem:ClientRootAccess"
  - "elasticfilesystem:ClientWrite"
- EFS からのインバウンドを許可

:::

### Network (VPC)

Network コンストラクタでは VPC を定義しています．props にて，以下の引数を定義しています．

- `vpcCidr`: VPC の CIDR ブロック（IP アドレス範囲）
- `useNatInstance`: NAT Instance を使用するかどうかのフラグ
- `vpcId`: 既存の VPC ID

Network クラスでは，`vpcId` が指定された場合は既存の VPC を参照し，指定が無い場合は新規 VPC を作成します．なお，パブリックサブネット，プライベートサブネット共に 2 つずつ作成します．

`useNatInstance` が指定された場合は NAT Instance を作成し，指定が無い場合は NAT Gateway を作成します．

<details open><summary>実装</summary>

```typescript
import * as ec2 from "aws-cdk-lib/aws-ec2";
import { Construct } from "constructs";

export interface NetworkProps {
  readonly vpcCidr?: string;
  readonly useNatInstance?: boolean;
  readonly vpcId?: string;
}

export class Network extends Construct {
  public readonly vpc: ec2.IVpc;

  constructor(scope: Construct, id: string, props: NetworkProps) {
    super(scope, id);

    if (props.vpcId) {
      this.vpc = ec2.Vpc.fromLookup(this, "Default", {
        vpcId: props.vpcId,
      });
    } else {
      const natInstance = props.useNatInstance
        ? ec2.NatProvider.instanceV2({
            instanceType: ec2.InstanceType.of(
              ec2.InstanceClass.T4G,
              ec2.InstanceSize.NANO
            ),
            defaultAllowedTraffic: ec2.NatTrafficDirection.OUTBOUND_ONLY,
          })
        : undefined;

      this.vpc = new ec2.Vpc(this, "Default", {
        natGatewayProvider: natInstance ? natInstance : undefined,
        natGateways: 1,
        ipAddresses: props.vpcCidr
          ? ec2.IpAddresses.cidr(props.vpcCidr)
          : undefined,
        maxAzs: 2,
        subnetConfiguration: [
          {
            name: "Public",
            subnetType: ec2.SubnetType.PUBLIC,
          },
          {
            name: "Private",
            subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          },
        ],
      });

      if (natInstance) {
        natInstance.connections.allowFrom(
          ec2.Peer.ipv4(this.vpc.vpcCidrBlock),
          ec2.Port.tcp(443),
          "Allow HTTPS from VPC"
        ); // for SecretManager
      }
    }
  }
}
```

</details>

### Storage (EFS)

Storage コンストラクタでは EFS を定義しています．props にて，以下の引数を定義しています．

- `vpc`: EFS を配置する VPC

Storage クラスでは，指定された VPC のプライベートサブネット内に EFS を作成します．また，自動バックアップを有効化し，スタック削除時に EFS を削除するように設定しています．

<details open><summary>実装</summary>

```typescript
import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as efs from "aws-cdk-lib/aws-efs";
import { Construct } from "constructs";

export interface StorageProps {
  readonly vpc: ec2.IVpc;
}

export class Storage extends Construct {
  public readonly fileSystem: efs.FileSystem;

  constructor(scope: Construct, id: string, props: StorageProps) {
    super(scope, id);

    this.fileSystem = new efs.FileSystem(this, "Default", {
      vpc: props.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      enableAutomaticBackups: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
  }
}
```

</details>

### Security (Secrets Manager, IAM Role)

Security コンストラクタでは Secret Manager を定義しています．props にて，以下の引数を定義しています．

- `gitlabRootEmail`: GitLab の root ユーザーのメールアドレス

Security クラスでは，GitLab のルートユーザーのメールアドレスとパスワードを保存するための Secrets Manager を作成しています．なお，パスワードは Secret Manager で自動生成させています．

<details open><summary>実装</summary>

```typescript
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import { Construct } from "constructs";

export interface SecurityProps {
  readonly gitlabRootEmail: string;
}

export class Security extends Construct {
  public readonly gitlabSecret: secretsmanager.ISecret;

  constructor(scope: Construct, id: string, props: SecurityProps) {
    super(scope, id);

    this.gitlabSecret = new secretsmanager.Secret(this, "Default", {
      description: "Gitlab root credentials",
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ email: props.gitlabRootEmail }),
        generateStringKey: "password",
      },
    });
  }
}
```

</details>

### LoadBalancer (ALB, DNS)

LoadBalancer コンストラクタでは ALB を定義しています．props にて，以下の引数を定義しています．

- `vpc`: ALB を配置する VPC
- `allowedCidrs`: ALB へのアクセスを許可する CIDR リスト
- `domainName`: ドメイン名 (option)
- `subDomain`: サブドメイン (option)
- `hostedZoneId`: ホストゾーン ID (option)
- `useHttps`: HTTPS を使用するかどうかのフラグ

LoadBalancer クラスでは，ALB を作成し，指定された VPC のパブリックサブネットに配置します．`useHttps` が `true` の場合，以下の処理を行い，HTTPS を使用するように設定します．

- ACM 証明書を作成
- Route53 に A レコード（サブドメインから ALB へのエイリアスレコード）を作成
- ALB のリスナーと証明書の関連付けを行います．

また，ALB へのアクセスは，指定された CIDR からのアクセスに制限しています．最終的な GitLab の URL は，`https://<subDomain>.<domainName>` または `http://<ALBのDNS名>` となります．

<details open><summary>実装</summary>

```typescript
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as acm from "aws-cdk-lib/aws-certificatemanager";
import * as route53 from "aws-cdk-lib/aws-route53";
import * as route53targets from "aws-cdk-lib/aws-route53-targets";
import { Construct } from "constructs";

export interface LoadBalancerProps {
  readonly vpc: ec2.IVpc;
  readonly allowedCidrs: string[];
  readonly domainName?: string;
  readonly subDomain?: string;
  readonly hostedZoneId?: string;
  readonly useHttps: boolean;
}

export class LoadBalancer extends Construct {
  public readonly alb: elbv2.IApplicationLoadBalancer;
  public readonly targetGroup: elbv2.IApplicationTargetGroup;
  public readonly url: string;

  constructor(scope: Construct, id: string, props: LoadBalancerProps) {
    super(scope, id);

    this.alb = new elbv2.ApplicationLoadBalancer(this, "Default", {
      vpc: props.vpc,
      internetFacing: true,
      vpcSubnets: props.vpc.selectSubnets({ subnets: props.vpc.publicSubnets }),
    });

    this.targetGroup = new elbv2.ApplicationTargetGroup(
      this,
      "GitlabTargetGroup",
      {
        vpc: props.vpc,
        port: 80,
        protocol: elbv2.ApplicationProtocol.HTTP,
        targetType: elbv2.TargetType.IP,
        healthCheck: {
          path: "/users/sign_in",
          port: "80",
        },
      }
    );

    let certificate: acm.ICertificate | undefined;
    if (props.useHttps) {
      const hostedZone = route53.PublicHostedZone.fromHostedZoneAttributes(
        this,
        "HostedZone",
        {
          zoneName: props.domainName!,
          hostedZoneId: props.hostedZoneId!,
        }
      );

      certificate = new acm.Certificate(this, "GitlabCertificate", {
        domainName: `${props.subDomain}.${props.domainName}`,
        validation: acm.CertificateValidation.fromDns(hostedZone),
      });

      new route53.ARecord(this, "GitlabDnsRecord", {
        zone: hostedZone,
        recordName: props.subDomain,
        target: route53.RecordTarget.fromAlias(
          new route53targets.LoadBalancerTarget(this.alb)
        ),
      });
    }

    const listener = this.alb.addListener("GitlabListener", {
      protocol: props.useHttps
        ? elbv2.ApplicationProtocol.HTTPS
        : elbv2.ApplicationProtocol.HTTP,
      open: false,
      certificates: props.useHttps ? [certificate!] : undefined,
      defaultTargetGroups: [this.targetGroup],
    });

    props.allowedCidrs.forEach((cidr) =>
      listener.connections.allowDefaultPortFrom(ec2.Peer.ipv4(cidr))
    );

    this.url = props.useHttps
      ? `https://${props.subDomain}.${props.domainName}`
      : `http://${this.alb.loadBalancerDnsName}`;
  }
}
```

</details>

### EFS Initialization (Lambda)

EfsInitLambda コンストラクタでは EFS の初期化を行う Lambda 関数を定義しています．props にて，以下の引数を定義しています．

- `vpc`: Lambda 関数を配置する VPC
- `fileSystem`: 初期化対象の EFS

EfsInitLambda クラスでは，Lambda 関数を作成し，指定された EFS のルートディレクトリに `data`, `logs`, `config` のディレクトリを作成します．また，EFS のマウントポイントを `/mnt/efs` に設定し，Lambda 関数の環境変数として EFS の FileSystem ID を渡しています．

:::note info

#### アクセスポイントを利用していない理由

[後述の節](./###EFS-アクセスポイントでの-git-clone-権限エラーとその解決) で詳細に述べておりますが，
:::

<details open><summary>実装</summary>

```typescript
import * as cdk from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as efs from "aws-cdk-lib/aws-efs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as cr from "aws-cdk-lib/custom-resources";
import * as logs from "aws-cdk-lib/aws-logs";
import { Construct } from "constructs";

export interface EfsInitLambdaProps {
  readonly vpc: ec2.IVpc;
  readonly fileSystem: efs.FileSystem;
}

export class EfsInitLambda extends Construct {
  public readonly initFunction: lambda.IFunction;

  // Define Lambda function to initialize EFS.
  // This function makes 3 directories in EFS root: data, logs, config.
  constructor(scope: Construct, id: string, props: EfsInitLambdaProps) {
    super(scope, id);

    this.initFunction = new lambda.Function(this, "Default", {
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: "index.handler",
      code: lambda.Code.fromAsset("lambda"),
      vpc: props.vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      timeout: cdk.Duration.minutes(1),
      allowAllOutbound: false,
      filesystem: lambda.FileSystem.fromEfsAccessPoint(
        props.fileSystem.addAccessPoint("LambdaAccessPoint", {
          createAcl: {
            ownerGid: "0",
            ownerUid: "0",
            permissions: "755",
          },
          posixUser: {
            uid: "0",
            gid: "0",
          },
          path: "/",
        }),
        "/mnt/efs"
      ),
      environment: {
        EFS_ID: props.fileSystem.fileSystemId,
      },
    });

    const efsInitProvider = new cr.Provider(this, "EfsInitProvider", {
      onEventHandler: this.initFunction,
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    new cdk.CustomResource(this, "EfsInitializer", {
      serviceToken: efsInitProvider.serviceToken,
    });
  }
}
```

```python:lambda/index.py
import logging
import os
from typing import Any, Dict

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MOUNT_POINT = "/mnt/efs"

GITLAB_DIRS = [
    "/srv/gitlab/data",
    "/srv/gitlab/logs",
    "/srv/gitlab/config",
]


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    try:
        # check if the EFS mount point exists
        if not os.path.exists(MOUNT_POINT):
            logger.error(f"EFS mount point {MOUNT_POINT} does not exist")
            raise FileNotFoundError(f"EFS mount point {MOUNT_POINT} does not exist")

        # make 3 directories
        for dir_path in GITLAB_DIRS:
            full_path = os.path.join(MOUNT_POINT, dir_path.lstrip("/"))
            os.makedirs(full_path, exist_ok=True)
            logger.info(f"Successfully created directory: {full_path}")

        return {
            "StatusCode": 200,
            "Message": "Successfully initialized EFS directories",
        }

    except Exception as e:
        logger.error(f"Error during EFS initialization: {str(e)}")
        raise e
```

</details>

### Computing (ECS, Fargate)

<details open><summary>実装</summary>

```typescript

```

</details>

- FileSystem.connections を使用して ECS サービスからのインバウンドを許可するようにしましょう。

  - https://zenn.dev/geniee/articles/0ea34c630e1f24#%E6%9C%80%E5%BE%8C%E3%81%AB

- ECS EXEC もできるようにしております

- ECS へのログイン
  - Session Manager プラグインのインストール
    - https://qiita.com/kooohei/items/190802d07655809bd1bd
    - https://dev.classmethod.jp/articles/202310-ecs-efs-01/
  - ECS Exec の有効化
    - https://dev.classmethod.jp/articles/tsnote-ecs-update-service-fails-with-invalidparameterexception-in-ecs-exec/
  - 以下を実行

```bash
CLUSTER_NAME=XXX
TASK_ID=arn:XXX
CONTAINER_NAME=XXX

aws ecs execute-command \
    --cluster $CLUSTER_NAME \
    --task  $TASK_ID\
    --container $CONTAINER_NAME \
    --interactive \
    --command "/bin/bash"
```

:::note info

#### 補足

ECS タスクロールを定義し，以下の権限を付与しています．

- (1) EFS への read/write 権限
- (2) ECS Exec を有効化するための権限

**(1) EFS への read/write 権限**

ECS タスクロールに以下のポリシーを付与することで，ECS に EFS をマウントすることが可能になります．

- `elasticfilesystem:ClientMount`
- `elasticfilesystem:ClientWrite`

CDK の実装では，メソッド `grantReadWrite` を使用して，ECS タスクロールに EFS への read/write 権限を付与しています．

https://docs.aws.amazon.com/AmazonECS/latest/developerguide/efs-best-practices.html

<!-- https://github.com/aws/aws-cdk/issues/13442#issuecomment-1321150902 -->

**※どうやら，EXEC の有効化を ECS 側で明示すると，以下の権限付与は自動でやってくれるらしい．．（便利すぎんか）**

`enableExecuteCommand: true` を明示することで，上記できた．

**(2) ECS Exec を有効化するための権限**

ECS タスクロールに以下のポリシーを付与することで，ECS Exec を有効化することが可能になります．ECS Exec とは，SSM Session Manager を使用して ECS タスクにログインするための機能です．

- `ssmmessages:CreateControlChannel`
- `ssmmessages:CreateDataChannel`
- `ssmmessages:OpenControlChannel`
- `ssmmessages:OpenDataChannel`

https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html#ecs-exec-required-iam-permissions

これにより，以下のようなコマンドで ECS Fargate のコンテナにログインすることができます．（開発段階において，コンテナにログインして状況確認する際に重宝しました．）なお，ログイン端末上で `session-manager-plugin` をインストールする必要があります．

```sh
#/bin/bash
CLUSTER_NAME=XXXXXXXXXXXXXXXXXXX
TASK_ID=arn:aws:ecs:ap-northeast-1:123456789123:task/XXXXXXXXXXXXXXXXXXXXXXXXXX
CONTAINER_NAME=GitlabContainer

aws ecs execute-command \
    --cluster $CLUSTER_NAME \
    --task  $TASK_ID\
    --container $CONTAINER_NAME \
    --interactive \
    --command "/bin/bash"
```

<!-- https://dev.classmethod.jp/articles/tsnote-ecs-update-service-fails-with-invalidparameterexception-in-ecs-exec/ -->

:::

### (その他)Stack

dependencies を明示しなければ，スタック削除時にエラーが発生

Lambda と VPC の削除順序を制御できていない．
Lambda と VPC の削除が同時に行われているように見える．

## GitLab セルフホスティングの Tips

本節では，[Docker コンテナ上で GitLab をセルフホスト](https://docs.gitlab.com/ee/install/docker/installation.html)する際に詰まった点や，ポイントについて共有します．

### Gitlab の外部 URL (https) の設定

GitLab コンテナを ALB (リバースプロキシ) の背後に配置する場合，GitLab 内部の Nginx に対し，以下のように HTTPS を利用しないように設定する必要があります．以下の設定は，docker run 実行時の環境変数 `GITLAB_OMNIBUS_CONFIG` にて指定することができます．(CDK コードにおける該当箇所は下部に記載しています．)

- `nginx['listen_port'] = 80`
- `nginx['listen_https'] = false;`

これは，GitLab の `external_url` に `https://` を指定すると，GitLab の Listen Port が 443 となり，内部の Nginx が HTTPS 通信を行うようになるためです． 本ソリューションの構成では， ALB が SSL 通信を行うため，GitLab 側は SSL (HTTPS) 通信を行わず，HTTP を利用して ALB と通信する必要があります．そのため，外部 URL に `https://` を指定する場合は，内部の Nginx の Listen port の設定を明示的に 80 に設定する必要があります．

参考: https://stackoverflow.com/questions/51487180/

<details open><summary>CDK コードの該当箇所</summary>

```typescript
const container = taskDefinition.addContainer("GitlabContainer", {
  image: ecs.ContainerImage.fromRegistry(
    `gitlab/gitlab-ce:${props.gitlabImageTag}`
  ),
  portMappings: [{ containerPort: 80 }],
  secrets: {
    GITLAB_ROOT_PASSWORD: ecs.Secret.fromSecretsManager(
      props.gitlabSecret,
      "password"
    ),
    GITLAB_ROOT_EMAIL: ecs.Secret.fromSecretsManager(
      props.gitlabSecret,
      "email"
    ),
  },
  environment: {
    GITLAB_OMNIBUS_CONFIG: props.useHttps
      ? `external_url '${props.externalUrl}'; nginx['listen_port'] = 80; nginx['listen_https'] = false;`
      : `external_url '${props.externalUrl}'`,
  },
  logging: ecs.LogDrivers.awsLogs({ streamPrefix: "gitlab" }),
});
```

</details>

### EFS アクセスポイントでの git clone 権限エラーとその解決

GitLab コンテナは，起動時にコンテナ内に `/var/opt/gitlab`, `/var/log/gitlab`, `/etc/gitlab` ディレクトリを作成します．これらのディレクトリは，GitLab のアプリケーションデータ，ログ，設定ファイルを保存するためのディレクトリです．これらのディレクトリをローカルボリュームにマウントすることで，GitLab のデータを永続化することができます．

| ローカルパス          | コンテナパス      | 用途                         |
| --------------------- | ----------------- | ---------------------------- |
| `$GITLAB_HOME/data`   | `/var/opt/gitlab` | アプリケーションデータを保存 |
| `$GITLAB_HOME/logs`   | `/var/log/gitlab` | ログを保存                   |
| `$GITLAB_HOME/config` | `/etc/gitlab`     | GitLab の設定ファイルを保存  |

> [公式ドキュメント](https://docs.gitlab.com/ee/install/docker/installation.html#create-a-directory-for-the-volumes)では，`$GITLAB_HOME=/srv/gitlab` としています．

ソリューション開発当初，GitLab のデータ永続化のためのボリュームマウント先として，EFS アクセスポイントを利用することを検討しました．ここで，アクセスポイントとは，EFS 上の指定したディレクトリに対し，指定した POSIX ユーザー ID (UID) とグループ ID (GID) でマウントすることができる機能です．また，指定したディレクトリが存在しない場合，自動でディレクトリを作成することができます．

ECS と EFS アクセスポイントを組み合わせることで，指定したディレクトリを EFS 上に自動作成し， ECS タスクに EFS 上のディレクトリをマウントすることができます．当初は，POSIX UID と GID を 0:0 に設定し，root ユーザーとして EFS 上のディレクトリをマウントしていました．この理由は，GitLab コンテナは，初回起動時に root ユーザーで必要なファイルやディレクトリを作成する必要があるためです．

GitLab コンテナが正常に起動し，動作確認のためリポジトリを作成して `git clone` を実行すると，以下のエラーが発生しました．この原因は，`/var/opt/gitlab/git-data/repositories` 内の一部のファイルの所有者が git ユーザー (UID: 998) である必要があるためです．(本エラーに関する情報が少なく，原因究明に時間を要しました．)

```
fatal: unable to access 'https://gitlab.example.com/root/test-pj.git/':
Error while processing content unencoding: invalid stored block lengths
```

つまり，GitLab コンテナの起動には EFS アクセスポイントの POSIX UID と GID を 0:0 にする必要があり，その結果，マウント先のディレクトリ内の全てのファイルの所有者が root となっていたため，本事象が発生していました．

そこで，本ソリューションでは，EFS アクセスポイントを利用せず，Lambda から直接 EFS にマウントしてディレクトリを作成後，ECS タスクに EFS 上のディレクトリをマウントするようにしています．CDK の実装では，CustomResource を利用して，Lambda の操作を行っております．

参考: https://gitlab.com/gitlab-org/charts/gitlab/-/issues/5546#note_2017038672

### ヘルスチェックパスについて

ALB のターゲットグループのヘルスチェックのために，[公式ドキュメント](https://docs.gitlab.com/ee/administration/monitoring/health_check.html)に記載されている GitLab のヘルスチェックのエンドポイント `/-/health` を利用すると，期待するレスポンスを得ることができませんでした．こちらの原因は不明ですが，暫定対処として，現在は，`/-/users/sign_in` に対してヘルスチェックを行うことで，サーバーの稼働状況を確認しています．

### Gitlab の初回の起動時間について

GitLab コンテナは，初回起動時に利用できるまでに約 5~6 分程度要します．そのため，ECS のヘルスチェックの猶予期間を長めに見積もり 9 分 (540 秒) に設定しています．ヘルスチェックの猶予期間が短い場合，GitLab コンテナの起動中に行われたヘルスチェック結果により，コンテナが正常でないと判断される結果，コンテナの再生成が繰り返されてしまいます．

## 利用手順

### AWS CDK コマンドの場合

### AWS CloudShell の場合

## GitLab の初回サインイン方法

![gitlab_signin.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/a960c7ed-c682-e29c-fea4-2287b2051081.png)

https://qiita.com/takoikakani/items/936faf23ee6bc286a270

https://zenn.dev/tech4anyone/articles/62f360ccea30ca

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
