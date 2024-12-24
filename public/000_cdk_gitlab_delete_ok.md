---
title: CodeCommit の代替として GitLab on ECS を CDK で一撃で構築する
tags:
  - AWS
  - GitLab
  - ECS
  - EFS
  - CDK
private: true
updated_at: "2024-12-25T07:05:12+09:00"
id: 3724c4dd8e519e8e3bf0
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

株式会社 NTT データ デジタルサクセスコンサルティング事業部の [@ren8k](https://qiita.com/ren8k) です．
新規の AWS アカウント上で MLOps を実現する必要があり，CodeCommit が利用できなかったので，AWS 上に GitLab のセルフホスト環境を構築しました．また，初めて CDK と TypeScript に挑戦し，IaC 化を行いました．本稿では，CDK の実装の工夫や，GitLab のセルフホスト環境構築の際に直面した課題とその解決策を，具体的なコードとともにご紹介します．特に ECS に EFS をマウントする際の実装や Tips は，同じような課題に直面している方の参考になるはずです．

CDK の実装は以下のリポジトリに公開しておりますので，ぜひご活用ください！

https://github.com/ren8k/aws-cdk-gitlab-on-ecs

## TL;DR

- [CodeCommit の代替として GitLab のセルフホスティングを実現](#ソリューション)
- [GitLab on ECS を一撃でデプロイするための CDK 実装の解説](#コード-各コンストラクト-の解説)
  - [ECS タスクに EFS をマウントする際の Tips や CDK 実装例を提示](#ecs-タスクに-efs-をマウントする際の-tips)
  - [ECS Exec の有効化の Tips](#ecs-exec-の有効化の-tips)
- [GitLab をコンテナホストする際の Tips を共有](#gitlab-セルフホスティングの-tips)
- [ローカル/CloudShell からの CDK のデプロイ方法の解説](#デプロイ手順)

## 背景

新規の AWS アカウント上で，[SageMaker AI Project Templates](https://docs.aws.amazon.com/sagemaker/latest/dg/sagemaker-projects-templates-sm.html) を利用する必要がありました．SageMaker AI Project Templates とは，SageMaker AI を利用した MLOps を迅速に実現するために，以下の AWS リソースを CloudFormation で一括構築することができるテンプレートです．

![mlops-architecture.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/c66a4c7e-c4f8-db14-996d-38e09ed36d5b.png)

> SageMaker AI Project Templates を利用することで，モデルの学習〜デプロイ〜モデル・データの品質モニタリングまでの一連のプロセスを自動化する MLOps アーキテクチャを構築することができます．なお，Training Pipeline は簡略的に図示しています．

SageMaker AI Project Templates では，MLOps の CI/CD パイプライン用のリポジトリとして CodeCommit または 3rd party 製の Git リポジトリサービスが利用可能です．しかし，2024/7/25 以降，新規 AWS アカウントにおいて，[CodeCommit は利用不可能](https://aws.amazon.com/jp/blogs/devops/how-to-migrate-your-aws-codecommit-repository-to-another-git-provider/)なため，3rd party 製の Git リポジトリサービスを利用する必要がありました．

そこで，CodeCommit の代替として GitLab をセルフホスティングすることを検討しました．本検討の理由は以下です．

- セキュリティ要件により、インターネット上の Git リポジトリサービスの利用には制限がある
  - 一定の承認プロセスを経れば利用可能だが、社内手続きが複雑でかなり時間がかかる
- GitLab は，Issue 管理，Wiki などの機能が豊富である

ただし，利用する AWS サービスの選定やアーキテクチャの検討，CDK での IaC 化を行う際に色々苦戦した部分が多かったので，本稿ではその解説や Tips の共有を行います．

:::note info
筆者は Data Scientist であり，CDK に関しては初学者でしたので，余計に苦戦しました．
:::

## ソリューション

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

## コード (各コンストラクト) の解説

利用する AWS サービス毎に，以下のコンストラクトやスタックを実装しました．

- [Network (VPC)](#network-vpc)
- [Storage (EFS)](#storage-efs)
- [Security (Secrets Manager)](#security-secrets-manager)
- [LoadBalancer (ALB, DNS)](#loadbalancer-alb-dns)
- [EFS Initialization (Lambda)](#efs-initialization-lambda)
- [Computing (ECS, Fargate)](#computing-ecs-fargate)
- [GitlabServerlessStack](#gitlabserverlessstack)

以降，各実装について解説します．

### Network (VPC)

Network コンストラクトは，VPC とその関連リソースの構成を担うコンポーネントです．既存の VPC を利用するか，新規に VPC を作成するかを選択でき，以下のパラメータを props として受け取ります．

- `vpcCidr`: VPC の CIDR ブロック（IP アドレス範囲）
- `useNatInstance`: NAT Instance を使用するかどうかのフラグ
- `vpcId`: 既存の VPC ID

VPC の構成は，`vpcId` の指定有無によって 2 つのパターンに分かれます．既存の VPC を使用する場合は `vpcId` を指定し，新規作成の場合は VPC CIDR とサブネット構成が自動的に設定されます．新規作成時は，可用性を考慮して 2 つのアベイラビリティーゾーンにまたがる形で、パブリックサブネットとプライベートサブネットが各 2 つずつ作成されます.また，VPC CIDR は`vpcCidr` で指定することができます．

プライベートサブネットからのアウトバウンド通信には，`useNatInstance` の設定に応じて NAT Gateway または NAT Instance が使用されます．NAT Instance を選択した場合は，コスト最適化のため `t4g.nano` インスタンスが使用されます．また，Secret Manager へのアクセスを可能にするため， VPC 内からの HTTPS インバウンドトラフィックのみを許可しています．

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

Storage コンストラクトでは EFS を定義しています．EFS は，GitLab のデータの永続化のために利用します．設定に必要な以下のパラメータを props として受け取ります．

- `vpc`: EFS を配置する VPC

指定した VPC のプライベートサブネット内に EFS が作成され，セキュアな環境を実現します．また，データの災害復旧のため，自動バックアップ機能を有効化するとともに，スタック削除時には EFS が自動的に削除されるよう設定しています．

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

### Security (Secrets Manager)

Security コンストラクトでは Secret Manager を定義しています．設定に必要な以下のパラメータを props として受け取ります．

- `gitlabRootEmail`: GitLab の root ユーザーのメールアドレス

GitLab のルートユーザーの認証情報を Secrets Manager で管理します．具体的には，指定されたメールアドレスとともに，Secrets Manager によって自動生成されたセキュアなパスワードが保存されます．

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

LoadBalancer コンストラクトは，Application Load Balancer (ALB) の設定を担うコンポーネントです．設定に必要な以下のパラメータを props として受け取ります．

- `vpc`: ALB を配置する VPC
- `allowedCidrs`: ALB へのアクセスを許可する CIDR リスト
- `domainName`: ドメイン名 (option)
- `subDomain`: サブドメイン (option)
- `hostedZoneId`: ホストゾーン ID (option)
- `useHttps`: HTTPS を使用するかどうかのフラグ

指定された VPC のパブリックサブネットに ALB を配置し，許可された CIDR からのアクセスのみを受け付けるよう制限します．`useHttps` が `true` に設定されている場合は，以下の HTTPS 関連の設定も自動的に行われます．

- ACM 証明書の作成
- Route53 での A レコード（サブドメインから ALB へのエイリアスレコード）の作成
- ALB のリスナーと証明書の関連付け

GitLab へのアクセスは，HTTPS 使用時は `https://<subDomain>.<domainName>`，HTTP 使用時は `http://<ALBのDNS名>` の URL を介して行われます。

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

EfsInitLambda コンストラクトでは，GitLab 用の EFS 初期化処理を実装しています．props にて，以下の引数を定義しています．

- `vpc`: Lambda 関数を配置する VPC
- `fileSystem`: 初期化対象の EFS

EFS 初期化処理は Lambda 関数とカスタムリソースを組み合わせて実現しています．Lambda 関数は VPC のプライベートサブネットに配置され，指定された EFS のルートディレクトリに GitLab の実行に必要な `data`，`logs`，`config` の各ディレクトリを作成します．また，カスタムリソースを利用しているため，CloudFormation のスタック作成時に自動的に初期化処理が実行されます．

:::note info

#### EFS アクセスポイントを利用していない理由

Lambda を利用せずとも，EFS アクセスポイントを利用すれば，EFS 側のファイルシステム上に直接ディレクトリを作成することは可能です．EFS アクセスポイントを利用していない理由は，GitLab コンテナの起動時やリポジトリの clone の際に，マウントディレクトリ内で複数の UID/GID での操作が必要になるためです．

詳細については，[後述の節](#efs-アクセスポイント利用時の-git-clone-権限エラーとその解決)で述べております．
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

Computing コンストラクトは，GitLab を実行するための ECS on Fargate 環境を構築するコンポーネントです．設定に必要な以下のパラメータを props として受け取ります．

- `vpc`: コンテナを配置する VPC
- `fileSystem`: GitLab データを保存する EFS
- `targetGroup`: コンテナを登録する ALB のターゲットグループ
- `gitlabSecret`: GitLab の認証情報を格納した Secrets Manager
- `gitlabImageTag`: 利用する GitLab イメージのタグ
- `externalUrl`: GitLab の外部アクセス URL
- `useHttps`: HTTPS を使用するかどうかのフラグ

Fargate のコンテナ環境は，VPC のプライベートサブネットに構築され，ALB を介して外部からのアクセスを許可します．

データの永続化については，EFS をコンテナにマウントすることで実現しています．GitLab のデータ（`/var/opt/gitlab`），ログ（`/var/log/gitlab`），設定（`/etc/gitlab`）は，それぞれ EFS 上の対応するディレクトリにマッピングされます．マウントポイントでの複数の UID/GID での操作が必要なため，EFS アクセスポイントは使用せず，直接マウントしています．

:::note info

#### ECS タスクに EFS をマウントする際の Tips

ECS タスクに EFS をマウントするためには，以下に示す ECS タスクロールの権限設定と EFS のセキュリティグループ (SG) の設定が必要です．

- (1) ECS タスクロールに EFS への read/write 権限の付与
- (2) EFS の SG で ECS からのインバウンドトラフィックの許可

**(1) ECS タスクロールに EFS への read/write 権限の付与**

ECS タスクロールに以下のポリシーを付与することで，ECS が EFS に対して読み込み・書き込みすることができるようになります．

- `elasticfilesystem:ClientMount`
- `elasticfilesystem:ClientWrite`

CDK の実装では，メソッド `grantReadWrite` を使用して，ECS タスクロールに EFS への read/write 権限を付与しています．

```typescript
// Allow ECS tasks to mount EFS
props.fileSystem.grantReadWrite(taskRole);
```

<!-- https://github.com/aws/aws-cdk/issues/13442#issuecomment-1321150902 -->

**(2) EFS の SG で ECS からのインバウンドトラフィックの許可**

EFS の SG で，NFS ポート (2049) での ECS サービスからのインバウンドを許可することで，ECS - EFS 間のトラフィックが可能になります．

CDK の実装では，メソッド `connections` を使用して ECS サービスからのインバウンドを許可しています．

```typescript
// Allow inbound NFS traffic from ECS
props.fileSystem.connections.allowDefaultPortFrom(
  service,
  "Allow inbound NFS traffic from ECS"
);
```

**参考**

- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/efs-best-practices.html
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/tutorial-efs-volumes.html#efs-security-group

:::

<details open><summary>実装</summary>

```typescript
import * as cdk from "aws-cdk-lib";
import * as ecs from "aws-cdk-lib/aws-ecs";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as iam from "aws-cdk-lib/aws-iam";
import * as elbv2 from "aws-cdk-lib/aws-elasticloadbalancingv2";
import * as secretsmanager from "aws-cdk-lib/aws-secretsmanager";
import * as efs from "aws-cdk-lib/aws-efs";
import { Construct } from "constructs";

export interface ComputingProps {
  readonly vpc: ec2.IVpc;
  readonly fileSystem: efs.IFileSystem;
  readonly targetGroup: elbv2.IApplicationTargetGroup;
  readonly gitlabSecret: secretsmanager.ISecret;
  readonly gitlabImageTag: string;
  readonly externalUrl: string;
  readonly useHttps: boolean;
}

export class Computing extends Construct {
  private readonly gitlabDir = {
    container: {
      data: "/var/opt/gitlab",
      logs: "/var/log/gitlab",
      config: "/etc/gitlab",
    },
    efs: {
      data: "/srv/gitlab/data",
      logs: "/srv/gitlab/logs",
      config: "/srv/gitlab/config",
    },
  } as const;

  constructor(scope: Construct, id: string, props: ComputingProps) {
    super(scope, id);

    const cluster = new ecs.Cluster(this, "GitlabCluster", {
      vpc: props.vpc,
      containerInsights: true,
    });

    const taskRole = new iam.Role(this, "EcsTaskRole", {
      assumedBy: new iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
    });
    // Allow ECS tasks to mount EFS
    props.fileSystem.grantReadWrite(taskRole);

    const taskDefinition = new ecs.FargateTaskDefinition(
      this,
      "GitlabTaskDefinition",
      {
        cpu: 2048,
        memoryLimitMiB: 6144, // require more than 6GB in my experience
        taskRole: taskRole,
        runtimePlatform: { cpuArchitecture: ecs.CpuArchitecture.X86_64 },
      }
    );

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
          ? // If HTTPS is enabled, set the external URL to use the domain name with HTTPS.
            // Also, configure NGINX to listen on port 80 and disable HTTPS inside the GitLab container,
            // as SSL termination is handled by the ALB (reverse proxy).
            // https://stackoverflow.com/questions/51487180/gitlab-set-external-url-to-https-without-certificate
            `external_url '${props.externalUrl}'; nginx['listen_port'] = 80; nginx['listen_https'] = false;`
          : // If HTTPS is not enabled, use the ALB's DNS name and set the external URL.
            `external_url '${props.externalUrl}'`,
      },
      logging: ecs.LogDrivers.awsLogs({ streamPrefix: "gitlab" }),
    });

    container.addMountPoints(
      {
        sourceVolume: "data",
        containerPath: this.gitlabDir.container.data,
        readOnly: false,
      },
      {
        sourceVolume: "logs",
        containerPath: this.gitlabDir.container.logs,
        readOnly: false,
      },
      {
        sourceVolume: "config",
        containerPath: this.gitlabDir.container.config,
        readOnly: false,
      }
    );

    // Mount EFS directories
    // Not using EFS access points because multiple UID/GID operations are required for file operations at mount points
    const addEfsVolume = (
      taskDefinition: ecs.FargateTaskDefinition,
      name: string,
      fileSystemId: string,
      rootDirectory: string
    ) => {
      taskDefinition.addVolume({
        name: name,
        efsVolumeConfiguration: {
          fileSystemId: fileSystemId,
          transitEncryption: "ENABLED",
          authorizationConfig: {
            iam: "ENABLED",
          },
          rootDirectory: rootDirectory,
        },
      });
    };

    addEfsVolume(
      taskDefinition,
      "data",
      props.fileSystem.fileSystemId,
      this.gitlabDir.efs.data
    );
    addEfsVolume(
      taskDefinition,
      "logs",
      props.fileSystem.fileSystemId,
      this.gitlabDir.efs.logs
    );
    addEfsVolume(
      taskDefinition,
      "config",
      props.fileSystem.fileSystemId,
      this.gitlabDir.efs.config
    );

    const service = new ecs.FargateService(this, "GitlabService", {
      cluster,
      taskDefinition,
      desiredCount: 1,
      assignPublicIp: false,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS },
      healthCheckGracePeriod: cdk.Duration.seconds(540), // gitlab requires a long grace period for health checks
      enableExecuteCommand: true,
    });

    service.attachToApplicationTargetGroup(props.targetGroup);

    // Allow inbound NFS traffic from ECS
    props.fileSystem.connections.allowDefaultPortFrom(
      service,
      "Allow inbound NFS traffic from ECS"
    );
  }
}
```

</details>

:::note info

#### ECS Exec の有効化の Tips

GitLab のコンテナの状況確認やデバッグのため，ECS Exec を有効化しております．ECS Exec とは，SSM Session Manager を使用して ECS タスクにログインするための機能です．

ECS タスクロールに以下のポリシーを付与することで，ECS Exec を有効化することが可能になります．

- `ssmmessages:CreateControlChannel`
- `ssmmessages:CreateDataChannel`
- `ssmmessages:OpenControlChannel`
- `ssmmessages:OpenDataChannel`

これにより，以下のようなコマンドで ECS Fargate のコンテナにログインすることができます．（開発段階において，コンテナにログインして状況確認する際に重宝しました．）なお，ログイン端末上で [`session-manager-plugin`](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html) をインストールする必要があります．

```sh
#/bin/bash
CLUSTER_NAME=XXXXXXXXXXXXXXXXXXX
TASK_ID=arn:aws:ecs:ap-northeast-1:123456789123:task/YYYYYYYYYYYYY
CONTAINER_NAME=ZZZZZZZZZZZZZZZZ

aws ecs execute-command \
    --cluster $CLUSTER_NAME \
    --task  $TASK_ID\
    --container $CONTAINER_NAME \
    --interactive \
    --command "/bin/bash"
```

CDK の実装では，FargateService の定義時に `enableExecuteCommand: true` を指定することで，ECS Exec を有効化することができます．なお，**この 1 行の設定追記だけで，上述のポリシーが ECS タスクロールに自動で付与されます．**

**参考**

- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html#ecs-exec-required-iam-permissions

<!-- https://dev.classmethod.jp/articles/tsnote-ecs-update-service-fails-with-invalidparameterexception-in-ecs-exec/ -->

:::

### GitlabServerlessStack

GitlabServerlessStack は，GitLab をサーバーレスで実行するための AWS リソースを統合的に管理するメインスタックです．前述のコンストラクトを順次作成し，GitLab の実行環境を構築します．

なお，リソースの依存関係を適切に制御するため，以下の順序制約を設定しています．これは，CDK スタックの削除時，リソースの削除順序を制御するためです．

- VPC -> Lambda: ネットワーク構成完了後に Lambda を実行
- Lambda -> ECS: EFS 初期化完了後にコンテナを起動

最後に，構築された GitLab の URL を CloudFormation の出力値として設定し，デプロイ完了後にアクセス URL を確認できるようにしています．

<details open><summary>実装</summary>

```typescript
import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import { Network } from "./constructs/network";
import { Storage } from "./constructs/storage";
import { LoadBalancer } from "./constructs/loadbalancer";
import { Security } from "./constructs/security";
import { Computing } from "./constructs/computing";
import { EfsInitLambda } from "./constructs/efs-init-lambda";

export interface GitlabServerlessStackProps extends cdk.StackProps {
  /**
   * The IP address ranges in CIDR notation that have access to GitLab.
   * You can restrict access to specific IP ranges for security.
   * @example ["1.1.1.1/32", "2.2.2.2/24"]
   */
  readonly allowedCidrs: string[];

  /**
   * The CIDR block for the VPC where GitLab will be deployed.
   * Ignored when you import an existing VPC.
   * @example "10.0.0.0/16"
   */
  readonly vpcCidr?: string;

  /**
   * Use t4g.nano NAT instances instead of NAT Gateway.
   * Set to true to minimize AWS costs.
   * Ignored when you import an existing VPC.
   * @default false
   */
  readonly useNatInstance?: boolean;

  /**
   * If set, it imports the existing VPC instead of creating a new one.
   * The VPC must have public and private subnets.
   * @default create a new VPC
   */
  readonly vpcId?: string;

  /**
   * The domain name for GitLab's service URL.
   * You must own a Route53 public hosted zone for the domain in your account.
   * @default undefined - No custom domain is used
   */
  readonly domainName?: string;

  /**
   * The subdomain to use for GitLab.
   * This will be combined with the domain name to form the complete URL.
   * @example "gitlab" will result in "gitlab.yourdomain.com"
   * @default undefined
   */
  readonly subDomain?: string;

  /**
   * The ID of Route53 hosted zone for the domain.
   * Required if domainName is specified.
   * @default undefined
   */
  readonly hostedZoneId?: string;

  /**
   * The email address for the GitLab root user.
   * This will be used to create the initial admin account.
   * @default "admin@example.com"
   */
  readonly gitlabRootEmail?: string;

  /**
   * The version tag of the GitLab container image to deploy.
   * The image will be pulled from [here](https://hub.docker.com/r/gitlab/gitlab-ce)
   * @example "17.5.0-ce.0"
   * @default "latest"
   */
  readonly gitlabImageTag?: string;
}

export class GitlabServerlessStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: GitlabServerlessStackProps) {
    super(scope, id, props);

    const {
      gitlabRootEmail: rootEmail = "admin@example.com",
      gitlabImageTag: imageTag = "latest",
    } = props;

    if (
      (props.hostedZoneId != null) !== (props.domainName != null) ||
      (props.hostedZoneId != null) !== (props.subDomain != null)
    ) {
      throw new Error(
        `You have to set hostedZoneId, domainName, and subDomain together! Or leave them all blank.`
      );
    }

    const useHttps = Boolean(
      props.domainName && props.subDomain && props.hostedZoneId
    );

    // Network (VPC)
    const network = new Network(this, "Network", {
      useNatInstance: props.useNatInstance,
      vpcId: props.vpcId,
    });

    // Storage (EFS)
    const storage = new Storage(this, "Storage", {
      vpc: network.vpc,
    });

    // Security (Secrets Manager)
    const security = new Security(this, "Security", {
      gitlabRootEmail: rootEmail,
    });

    // LoadBalancer (ALB, DNS)
    const loadBalancer = new LoadBalancer(this, "LoadBalancer", {
      vpc: network.vpc,
      allowedCidrs: props.allowedCidrs,
      domainName: props.domainName,
      subDomain: props.subDomain,
      hostedZoneId: props.hostedZoneId,
      useHttps,
    });

    // EFS Initialization (Lambda)
    const efsInitializer = new EfsInitLambda(this, "EfsInitLambda", {
      vpc: network.vpc,
      fileSystem: storage.fileSystem,
    });

    // Computing (ECS, Fargate)
    const computing = new Computing(this, "Computing", {
      vpc: network.vpc,
      fileSystem: storage.fileSystem,
      targetGroup: loadBalancer.targetGroup,
      gitlabSecret: security.gitlabSecret,
      gitlabImageTag: imageTag,
      externalUrl: loadBalancer.url,
      useHttps,
    });

    // Dependencies (VPC -> Lambda -> ECS)
    efsInitializer.initFunction.node.addDependency(network.vpc);
    computing.node.addDependency(efsInitializer.initFunction);

    new cdk.CfnOutput(this, "GitlabUrl", {
      value: loadBalancer.url,
    });
  }
}
```

</details>

## GitLab セルフホスティングの Tips

本節では，[Docker コンテナ上で GitLab をセルフホスト](https://docs.gitlab.com/ee/install/docker/installation.html)する際に詰まった点や，ポイントについて共有します．

### GitLab の外部 URL (https) の設定

GitLab コンテナを ALB (リバースプロキシ) の背後に配置する場合，GitLab 内部の Nginx に対し，以下のように HTTPS を利用しないように設定する必要があります．以下の設定は，docker run 実行時の環境変数 `GITLAB_OMNIBUS_CONFIG` にて指定することができます．(CDK コードにおける該当箇所は下部に記載しています．)

- `nginx['listen_port'] = 80`
- `nginx['listen_https'] = false;`

これは，GitLab の `external_url` に `https://` を指定すると，GitLab の Listen Port が 443 となり，内部の Nginx が HTTPS 通信を行うようになるためです． 本ソリューションの構成では， ALB とクライアントが SSL 通信を行うため，GitLab 側は SSL (HTTPS) 通信を行わず，HTTP を利用して ALB と通信する必要があります．そのため，外部 URL に `https://` を指定する場合は，内部の Nginx の Listen port の設定を明示的に 80 に設定する必要があります．

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

### EFS アクセスポイント利用時の git clone 権限エラーとその解決

GitLab コンテナは，起動時に `/var/opt/gitlab`, `/var/log/gitlab`, `/etc/gitlab` ディレクトリを作成します．これらのディレクトリは，GitLab のアプリケーションデータ，ログ，設定ファイルを保存するためのディレクトリです．これらのディレクトリをローカルボリュームにマウントすることで，GitLab のデータを永続化することができます．

| ローカルパス          | コンテナパス      | 用途                         |
| --------------------- | ----------------- | ---------------------------- |
| `$GITLAB_HOME/data`   | `/var/opt/gitlab` | アプリケーションデータを保存 |
| `$GITLAB_HOME/logs`   | `/var/log/gitlab` | ログを保存                   |
| `$GITLAB_HOME/config` | `/etc/gitlab`     | GitLab の設定ファイルを保存  |

> [公式ドキュメント](https://docs.gitlab.com/ee/install/docker/installation.html#create-a-directory-for-the-volumes)では，`$GITLAB_HOME=/srv/gitlab` としています．

ソリューション開発当初，GitLab のデータ永続化のためのボリュームマウント先として，EFS アクセスポイントを利用することを検討しました．ここで，アクセスポイントとは，EFS 上の指定したディレクトリに対し，指定した POSIX ユーザー ID (UID) とグループ ID (GID) でマウントすることができる機能です．また，指定したディレクトリが存在しない場合，自動でディレクトリを作成することができます．

ECS と EFS アクセスポイントを組み合わせることで，指定したディレクトリを EFS 上に自動作成し， ECS タスクに EFS 上のディレクトリをマウントすることができます．当初は，POSIX UID と GID を 0:0 に設定し，root ユーザーとして EFS 上のディレクトリをマウントしていました．この理由は，GitLab コンテナは，初回起動時に root ユーザーで必要なファイルやディレクトリを作成する必要があるためです．

GitLab コンテナが正常に起動し，動作確認のためリポジトリを作成して `git clone` を実行すると，以下のエラーが発生しました．この原因は，`git clone` の実行には `/var/opt/gitlab/git-data/repositories` 内の一部のファイルの所有者が git ユーザー (UID: 998) である必要があるためです．(本エラーに関する情報が少なく，原因究明に時間を要しました．)

```
fatal: unable to access 'https://gitlab.example.com/root/test-pj.git/':
Error while processing content unencoding: invalid stored block lengths
```

つまり，GitLab コンテナの起動には EFS アクセスポイントの POSIX UID と GID を 0:0 にする必要があり，その結果，マウント先のディレクトリ内の全てのファイルの所有者が root となっていたため，本事象が発生していました．

そこで，本ソリューションでは，EFS アクセスポイントを利用せず，Lambda から直接 EFS にマウントしてディレクトリを作成後，ECS タスクに EFS 上のディレクトリをマウントするようにしています．CDK の実装では，CustomResource を利用して Lambda の操作を行っております．

参考: https://gitlab.com/gitlab-org/charts/gitlab/-/issues/5546#note_2017038672

### ヘルスチェックパスについて

ALB のターゲットグループのヘルスチェックのために，[公式ドキュメント](https://docs.gitlab.com/ee/administration/monitoring/health_check.html)に記載されている GitLab のヘルスチェックのエンドポイント `/-/health` を利用すると，期待するレスポンスを得ることができませんでした．こちらの原因は不明ですが，暫定対処として，`/-/users/sign_in` に対してヘルスチェックを行うことで，サーバーの稼働状況を確認しています．

### GitLab の初回の起動時間について

GitLab コンテナは，初回起動時に利用できるまでに約 5~6 分程度要します．そのため，ECS のヘルスチェックの猶予期間を長めに見積もり 9 分 (540 秒) に設定しています．ヘルスチェックの猶予期間が短い場合，GitLab コンテナの起動中に行われたヘルスチェック結果により，コンテナが正常でないと判断される結果，コンテナの再生成が繰り返されてしまいます．

## デプロイ手順

ローカル，CloudShell での，[本リポジトリ](https://github.com/ren8k/aws-cdk-gitlab-on-ecs)を利用したデプロイ手順を解説します．

### 前提条件

本アプリをデプロイするには，以下の依存関係がインストールされている必要があります．

- [Node.js](https://nodejs.org/en/download/package-manager) (v22 以降)
- [AWS CDK](https://docs.aws.amazon.com/cdk/v2/guide/work-with-cdk-typescript.html) (v2 以降)
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) と `Administrator` 相当のポリシーを持つ IAM プロファイル

### ローカルの場合

[`bin/aws-cdk-gitlab-on-ecs.ts`](https://github.com/ren8k/aws-cdk-gitlab-on-ecs/blob/main/bin/aws-cdk-gitlab-on-ecs.ts) を編集することで，AWS リージョンなどの設定パラメータを調整できます．利用可能なすべてのパラメータについては [`GitlabServerlessStackProps`](./lib/aws-cdk-gitlab-on-ecs-stack.ts) インターフェースも確認してください．

その後，以下のコマンドを実行してスタック全体をデプロイできます．なお，コマンドはリポジトリのルートで実行してください．

```sh
# install npm dependencies
npm ci
# bootstrap the AWS account (required only once per account and region)
npx cdk bootstrap
# deploy the CDK stack
npx cdk deploy
```

初回のデプロイには通常約 20 分かかります．デプロイが成功すると，アプリケーションの URL が表示されます．

```
 ✅  GitlabServerlessStack

✨  Deployment time: 1003.7s

Outputs:
GitlabServerlessStack.GitlabUrl = https://gitlab.example.com
Stack ARN:
arn:aws:cloudformation:ap-northeast-1:XXXXXXXXXXXX:stack/GitlabServerlessStack/5901fab0-a4e6-11ef-9796-0e94afb0bd61

✨  Total time: 1006.43s
```

### AWS CloudShell の場合

CloudShell には AWS CLI や AWS CDK がプリインストールされているため，CDK アプリケーションを容易にデプロイを行うことができます．クイックにデプロイしたい場合にご利用下さい．

まず，[CloudShell](https://console.aws.amazon.com/cloudshell/home) を起動します．その後，以下のコマンドを実行することで，deploy.sh をダウンロードし，実行権限を付与します．

```sh
wget https://raw.githubusercontent.com/ren8k/aws-cdk-gitlab-on-ecs/refs/heads/main/deploy.sh -O deploy.sh
chmod +x deploy.sh
```

次に，以下のコマンドを実行し，CDK アプリケーションをデプロイします．なお，デプロイ時の IP アドレス制限や VPC の CIDR 等の設定を行いたい場合，以下のコマンドを実行せず，本リポジトリを clone 後，[`bin/aws-cdk-gitlab-on-ecs.ts`](https://github.com/ren8k/aws-cdk-gitlab-on-ecs/blob/main/bin/aws-cdk-gitlab-on-ecs.ts) を編集して下さい．

```sh
export UV_USE_IO_URING=0
./deploy.sh
```

<details open><summary>deploy.shの内容</summary>

```bash:deploy.sh
#!/bin/bash
cd /tmp || exit
git clone https://github.com/ren8k/aws-cdk-gitlab-on-ecs.git
cd aws-cdk-gitlab-on-ecs || exit
npm ci
npx cdk bootstrap
npx cdk deploy
```

</details>

:::note warn
執筆時点（2024/12/21）では，東京リージョンの CloudShell 環境において，`npm ci` の実行が終了しない事象が発生しています．この原因は，以下の Issue で報告されている通り，東京リージョンの CloudShell 環境で利用されている Amazon Linux 2023 のカーネルバージョン `6.1.115-126.197.amzn2023` に起因するバグのためです．(コマンド `cat /proc/version` より確認することができます．) 具体的には，npm cli 実行時，`io_uring` サプシステムがオーバーフローしてしまう結果，プロセスがハング（応答停止）してしまうためです．

このため，現時点では以下の Issue の記載の通り，`./deploy.sh` 実行前にコマンド `export UV_USE_IO_URING=0` を実行することで，本バグを回避することが可能です．その他，東京リージョン以外のリージョン（例えば大阪リージョン，バージニア北部リージョン）の CloudShell 環境で利用されている Linux カーネルバージョンは `6.1.112-124.190.amzn2023.x86_64` なので，こちらを利用することで，本バグを回避することも可能です．

なお，上記事象は AWS サポートに報告しており，現在修正対応中とのことです．

https://github.com/amazonlinux/amazon-linux-2023/issues/840#issuecomment-2485782075
:::

## GitLab へのサインイン方法

デフォルトの管理者ユーザー名は`root`です．パスワードは Secrets Manager に保存されており，デプロイ時に生成されたランダムな文字列です．

![gitlab_signin.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/a960c7ed-c682-e29c-fea4-2287b2051081.png)

## リソースの削除方法

以下のコマンドを実行します．EFS（GitLab のリポジトリ用のストレージ）を含む全てのリソースが削除される点にご注意下さい．

```sh
npx cdk destroy --force
```

## まとめ

本記事では，AWS CDK を用いたサーバーレス構成での GitLab セルフホスティングのためのソリューションを提案しました．具体的には，ECS Fargate や EFS などを組み合わせたアーキテクチャを設計し，[CDK による IaC 化](https://github.com/ren8k/aws-cdk-gitlab-on-ecs)を行いました．本ソリューションにより，CodeCommit が利用できない新規の AWS アカウント内でも MLOps，DevOps を完結することが可能になります．

本記事が，AWS CDK によるサーバーレス構成での実装や GitLab のセルフホスティングを検討されている方の参考になれば幸いです．

## 謝辞

本 CDK の実装を行うにあたり，以下のリポジトリや資料を参考にさせていただきました．CDK 初学者の私にとって，非常に学びの多い素晴らしい資料でした．末尾ではございますが，感謝申し上げます．

- [aws-samples/dify-self-hosted-on-aws](https://github.com/aws-samples/dify-self-hosted-on-aws)
- [aws-samples/generative-ai-use-cases-jp](https://github.com/aws-samples/generative-ai-use-cases-jp)
- [初心者がおさえておきたい AWS CDK のベストプラクティス 2024](https://speakerdeck.com/konokenj/cdk-best-practice-2024)
- [AWS CDK における「再利用性」を考える](https://speakerdeck.com/gotok365/aws-cdk-reusability)
- [AWS CDK のあるあるお悩みに答えたい](https://speakerdeck.com/tmokmss/answering-cdk-faqs)
- [AWS CDK における単体テストの使い所を学ぶ](https://aws.amazon.com/jp/builders-flash/202411/learn-cdk-unit-test/)
- [AWS CDK でクラウドアプリケーションを開発するためのベストプラクティス](https://aws.amazon.com/jp/blogs/news/best-practices-for-developing-cloud-applications-with-aws-cdk/)

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
