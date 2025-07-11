---
title: Amazon Nova Canvas の Virtual try-on の機能検証
tags:
  - Python
  - AWS
  - bedrock
  - 画像生成
  - 生成AI
private: false
updated_at: '2025-07-11T12:09:14+09:00'
id: af7b127cdffd859856f2
organization_url_name: null
slide: false
ignorePublish: false
---

## はじめに

株式会社 NTT データ デジタルサクセスソリューション事業部の [@ren8k](https://qiita.com/ren8k) です．

2025/07/02 に，Amazon Nova Canvas の新機能である，[Virtual try-on と Style options for image generation がリリースされました](https://aws.amazon.com/jp/about-aws/whats-new/2025/07/amazon-nova-canvas-virtual-try-on-style-options-image-generation/)．

https://aws.amazon.com/jp/blogs/news/amazon-nova-canvas-update-virtual-try-on-and-style-options-now-available/

[公式ドキュメント](https://docs.aws.amazon.com/nova/latest/userguide/image-gen-vto.html)や [API のリクエストの形式](https://docs.aws.amazon.com/nova/latest/userguide/image-gen-req-resp-structure.html)を見ると，想像以上に Virtual try-on の機能が複雑かつ豊富だったので，Dive Deep して機能検証してみました．

※ GitHub に，検証時に利用した Jupyter Notebook を公開しています．

https://github.com/ren8k/aws-bedrock-titan-image-generator-app/blob/main/notebook/verify_virtual_try-on_and_style_option.ipynb

## Virtual try-on とは

Virtual try-on は，衣服の画像を，人物が写っている画像に重ね合わせ，試着をシミュレーションする機能です．具体的には，(1) ソース画像，(2) 参照画像，(3) マスク画像 の 3 つの画像を入力とし，マスク画像に示した編集領域に合うように，参照画像をソース画像に合成する Inpaint 機能です．

本機能の特徴として，既存の画像生成タスクのように，テキストプロンプトやネガティブプロンプトを利用しない点が挙げられます．また，推論パラメータを指定することで，マスク画像をモデルに自動生成させることが可能であり，この場合はマスク画像の入力は不要です．

| (1) ソース画像                                                                                                             | (2) 参照画像                                                                                                                            | (3) マスク画像                                                                                                                           | (4) 試着画像                                                                                                                        |
| -------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| ![human.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/9745df07-7280-46ec-ba57-d5b13d471afd.png) | ![swag_top_engineer.jpg](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/8b1b105a-2357-451e-b4fb-a1498742b815.jpeg) | ![exp1-1_mask_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/a91f9558-f278-4f03-a6c8-f5fe76294b18.png) | ![exp1-1_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/2653ea81-ca97-4194-ac40-66261afa02f3.png) |

:::note warn
本記事におけるソース画像・生成画像は，Amazon Nova Canvas で生成した画像であり，実在の人物ではありません．参照画像で利用している衣服は，AWS のイベントでいただいたものを使用しています．
:::

## 検証用 Python 関数

本節以降，AWS SDK for Python (boto3) を使用し，Virtual try-on の機能を検証します．説明のため，Amazon Nova Canvas によりマスク画像，試着画像を生成して表示するヘルパー関数 `generate_image` を定義します．

```python
def generate_image(
    payload: dict,
    num_image: int = 1,
    cfg_scale: float = 6.5,
    seed: int = 42,
    model_id: str = "amazon.nova-canvas-v1:0",
) -> None:
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    body = json.dumps(
        {
            **payload,
            "imageGenerationConfig": {
                "numberOfImages": num_image,  # Range: 1 to 5
                "quality": "premium",  # Options: standard/premium
                "height": 1024,  # Supported height list above
                "width": 1024,  # Supported width list above
                "cfgScale": cfg_scale,  # Range: 1.0 (exclusive) to 10.0
                "seed": seed,  # Range: 0 to 214783647
            },
        }
    )

    response = client.invoke_model(
        body=body,
        modelId=model_id,
        accept="application/json",
        contentType="application/json",
    )

    response_body = json.loads(response.get("body").read())
    base64_image = response_body.get("images")[0]
    base64_bytes = base64_image.encode("ascii")
    image_bytes = base64.b64decode(base64_bytes)

    image = Image.open(io.BytesIO(image_bytes))
    image.show()

    if "returnMask" in payload.get("virtualTryOnParams", {}):
        mask_base64 = response_body.get("maskImage")
        mask_bytes = base64.b64decode(mask_base64.encode("ascii"))
        mask_image = Image.open(io.BytesIO(mask_bytes))
        mask_image.show()
```

ヘルパー関数の引数 `payload` に Virtual try-on のパラメータを指定します．本パラメータの説明については後述します．

また，入力画像を Base64 エンコードするためのヘルパー関数 `load_image_as_base64` と，画像をリサイズするためのヘルパー関数 `resize_image` を定義します．Amazon Nova Canvas に入力可能な画像のサイズは [4,194,304pixel 未満](https://docs.aws.amazon.com/ja_jp/nova/latest/userguide/image-gen-access.html#image-gen-resolutions)であるため，`resize_image` では 2048x2048 のサイズにリサイズしております．

```python
def load_image_as_base64(image_path) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def resize_image(reference_img_path, resized_reference_img_path) -> None:
    img = Image.open(reference_img_path)
    img = img.resize((2048, 2048), Image.LANCZOS)
    img.save(resized_reference_img_path)
```

## 検証 1: T シャツの試着

本検証では，基本的な機能を確認することを目的とし，男性が写ったソース画像に対し，T シャツ (2025 Japan AWS Top Engineer の Swag) の参照画像を合成 (試着) することが可能かを確認します．

| ソース画像                                                                                                                 | 参照画像                                                                                                                                |
| -------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| ![human.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/9745df07-7280-46ec-ba57-d5b13d471afd.png) | ![swag_top_engineer.jpg](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/8b1b105a-2357-451e-b4fb-a1498742b815.jpeg) |

以下のパラメータをヘルパー関数 `generate_image` に指定することで， Virtual try-on による試着を実現できます．

```python
generate_image(
    {
        "taskType": "VIRTUAL_TRY_ON",
        "virtualTryOnParams": {
            "sourceImage": load_image_as_base64(source_img_path),
            "referenceImage": load_image_as_base64(resized_reference_img_path),
            "maskType": "GARMENT", # マスク画像 (衣服) を自動生成
            "garmentBasedMask": {
                "garmentClass": "UPPER_BODY",
            },
            "returnMask": True,  # マスクを返す
        },
    },
)
```

`taskType` には `VIRTUAL_TRY_ON` を指定し，`virtualTryOnParams` に，ソース画像，参照画像，マスク画像に関するパラメータを指定します．以下に，各パラメータの説明を示します．

- `sourceImage`: ソース画像．`source_img_path` にはソース画像のパスを指定しています．
- `referenceImage`: 参照画像．`reference_img_path` には参照画像のパスを指定しています．
- `maskType`: マスク画像の設定．`GARMENT` を指定することで，衣服に特化したマスクを自動生成しています．
- `garmentBasedMask`: 置換対象の衣服の設定．本設定に基づき，マスク画像を生成します．
- `garmentClass`: 事前定義された衣服のクラスであり，ソース画像内で置換したい対象領域 (衣服) を指す．`UPPER_BODY` を指定することで，図中の上半身のマスクを自動生成します．
- `returnMask`: マスク画像を返すかどうか．`True` を指定することで，マスク画像を返します．

参考に，`garmentClass` の[一覧](https://docs.aws.amazon.com/nova/latest/userguide/image-gen-req-resp-structure.html)を以下に示します．

<details><summary>garmentClass 一覧 (折りたたんでます)</summary>

- `UPPER_BODY` - 上半身
- `LOWER_BODY` - 下半身
- `FULL_BODY` - 全身
- `FOOTWEAR` - 履物
- `LONG_SLEEVE_SHIRT` - 長袖シャツ
- `SHORT_SLEEVE_SHIRT` - 半袖シャツ
- `NO_SLEEVE_SHIRT` - ノースリーブシャツ（袖なしシャツ）
- `OTHER_UPPER_BODY` - その他の上半身衣服
- `LONG_PANTS` - 長ズボン
- `SHORT_PANTS` - 短パン（ショートパンツ）
- `OTHER_LOWER_BODY` - その他の下半身衣服
- `LONG_DRESS` - ロングドレス
- `SHORT_DRESS` - ショートドレス
- `FULL_BODY_OUTFIT` - 全身衣装
- `OTHER_FULL_BODY` - その他の全身衣服
- `SHOES` - 靴
- `BOOTS` - ブーツ
- `OTHER_FOOTWEAR` - その他の履物

</details>

以下に，自動生成されたマスク画像と，試着画像を示します．

| マスク画像                                                                                                                               | 試着画像                                                                                                                            |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| ![exp1-1_mask_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/a91f9558-f278-4f03-a6c8-f5fe76294b18.png) | ![exp1-1_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/2653ea81-ca97-4194-ac40-66261afa02f3.png) |

`maskType` に `GARMENT` を指定し，`garmentBasedMask` の `garmentClass` に `UPPER_BODY` を指定しているので，画像中の男性の上半身の領域を黒で示したマスク画像が自動生成されいることが確認できます．また，マスク画像の黒色の領域で，参照画像 (T シャツ) が自然に合成されていることも確認できます．

:::note info
`garmentClass` について
今回の例では，`garmentClass` に `LONG_SLEEVE_SHIRT` (長袖シャツ) を指定しても，同様の結果が得られます．ただし，`garmentClass` に ソース画像内の衣服と異なるクラス，例えば `SHORT_SLEEVE_SHIRT` (半袖シャツ) を指定した場合，マスク画像が適切に生成されず，試着結果が不自然になることがあります．(以下に実行結果を示します．)

そのため，`garmentClass` には，ソース画像内の衣服と同じクラスを指定するか，ソース画像内の衣服に依らず汎用的なクラスである `UPPER_BODY` を指定すると良いでしょう．

<details><summary>SHORT_SLEEVE_SHIRT を指定した結果 (折りたたんでます)</summary>

以下の結果では，マスク画像の生成自体はソース画像の長袖を認識していますが，試着画像では，ソース画像の長袖の袖部分が置換されておらず，ソース画像における半袖部分のみが置換される結果，不自然な画像が生成されています．

| マスク画像                                                                                                                               | 試着画像                                                                                                                            |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| ![exp1-3_mask_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/52137b91-62d9-45de-87a3-9a872be6a220.png) | ![exp1-3_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/6901a545-1477-4a7a-9c4a-34b57b23b790.png) |

<details>
:::

## 検証 2: 上着の試着

### 検証 2-1

本検証では，上着の試着が可能かを確認することを目的とし，検証 1 と同様のソース画像に対し，パーカー (生成 AI 実用化推進 PG の Swag) の参照画像を合成 (試着) することが可能かを確認します．

| ソース画像                                                                                                                 | 参照画像                                                                                                                              |
| -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| ![human.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/9745df07-7280-46ec-ba57-d5b13d471afd.png) | ![swag_aws_hoodie.jpg](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/d3e2088b-618e-484d-8f79-6adcfa3b83c3.jpeg) |

まず，検証 1 と同一のパラメータを指定し，ヘルパー関数 `generate_image` を実行してみます．

```python
generate_image(
    {
        "taskType": "VIRTUAL_TRY_ON",
        "virtualTryOnParams": {
            "sourceImage": load_image_as_base64(source_img_path),
            "referenceImage": load_image_as_base64(resized_reference_img_path),
            "maskType": "GARMENT",
            "garmentBasedMask": {
                "garmentClass": "UPPER_BODY",
            },
            "returnMask": True,
        },
    },
)
```

以下に，自動生成されたマスク画像と，試着画像を示します．

| マスク画像                                                                                                                               | 試着画像                                                                                                                            |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| ![exp2-1_mask_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/1d0a0081-9aba-4ba0-8ce9-9ef7d1e25b3e.png) | ![exp2-1_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/f228f302-e641-495e-ba0f-f0c1f65b2073.png) |

結果としては，前開きの状態でパーカーをソース画像に合成 (試着) させることができました．しかし，以下の点において，課題があると考えられます．

- (1) パーカー特有のフードや全体の膨らみを表現できておらず，不自然
- (2) ソース画像のインナーが変わってしまっている
- (3) 試着画像内のマスク領域の境界部分 (合成されたパーカーの周り) に不自然な継ぎ目が見える (これは検証 1 でも同様)

以降，推論パラメータの調整により，これらの課題を解決できるかを確認します．

### 検証 2-2

本検証では，検証 2-1 の「パーカー特有のフードや全体の膨らみを表現できておらず，不自然な課題」を解決できるかを確認します．この課題の原因は，合成 (試着) 結果はマスク画像におけるマスクの領域 (ソース画像の衣服の形状) に依存するためです．具体的には，ソース画像から生成されたマスク画像の領域 (白シャツの領域) が，パーカーのフードや全体の膨らみを表現できない程度に狭いことにあると考えられます． (マスク画像の精度が高い故の課題です．)

そこで，マスク画像のマスクの形状を Bounding Box に変更し，マスク (編集可能な領域) を広くすることで，パーカーのフードや全体の膨らみを表現できるかを確認します．マスクの形状は，`garmentBasedMask` の設定内で `maskShape: "BOUNDING_BOX"` を指定することで変更できます．

```python
generate_image(
    {
        "taskType": "VIRTUAL_TRY_ON",
        "virtualTryOnParams": {
            "sourceImage": load_image_as_base64(source_img_path),
            "referenceImage": load_image_as_base64(resized_reference_img_path),
            "maskType": "GARMENT",
            "garmentBasedMask": {
                "garmentClass": "UPPER_BODY",
                "maskShape": "BOUNDING_BOX",
            },
            "returnMask": True,
        },
    },
)
```

以下に，自動生成されたマスク画像と，試着画像を示します．

| マスク画像                                                                                                                               | 試着画像                                                                                                                            |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| ![exp2-2_mask_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/027efc89-16cc-4804-b216-a48b8754e4b6.png) | ![exp2-2_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/426cd5b5-6306-4abd-b123-09643249cbd9.png) |

結果として，マスク画像の形状が Bounding Box (四角形)となっており，マスク領域 (黒色の領域)が広くなっていることが確認できます．これにより，試着画像では，パーカーのフードや全体の膨らみが表現されており，より自然な合成 (試着) が実現できています．

しかし，マスクの形状を Bounding Box に変更したことで，検証 2-1 の課題である「試着画像内のマスク領域の境界部分に不自然な継ぎ目が見える課題」がより強調される結果となっています．

### 検証 2-3

本検証では，検証 2-1 の「ソース画像のインナーが変わってしまっている課題」を解決できるかを確認します．[公式ドキュメント](https://docs.aws.amazon.com/nova/latest/userguide/image-gen-vto.html#image-gen-vto-styling)を深く確認すると，Virtual try-on のパラメータには上着を重ね着する際の設定パラメータ `garmentStyling` が用意されており，`garmentStyling` の設定内で `"outerLayerStyle": "OPEN"` を指定することで，ソース画像の衣服を保持しつつ，上着を試着することが可能です．

```python
generate_image(
    {
        "taskType": "VIRTUAL_TRY_ON",
        "virtualTryOnParams": {
            "sourceImage": load_image_as_base64(source_img_path),
            "referenceImage": load_image_as_base64(resized_reference_img_path),
            "maskType": "GARMENT",
            "garmentBasedMask": {
                "garmentClass": "UPPER_BODY",
                "maskShape": "BOUNDING_BOX",
                "garmentStyling": {
                    "outerLayerStyle": "OPEN",
                },
            },
            "returnMask": True,
        },
    },
    seed=1,
)
```

以下に，自動生成されたマスク画像と，試着画像を示します．

| マスク画像                                                                                                                                | 試着画像                                                                                                                             |
| ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| ![exp4-2-2_mask_seed=1.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/5db6ef46-df4a-4941-8438-8a60c7f9d6b9.png) | ![exp4-2-2_seed=1.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/6e810275-d19e-4f18-9858-a100940cab8f.png) |

結果として，ソース画像の衣服が編集されないように，マスク画像内の中央部（ソース画像の白シャツ部）に白い縦長の領域が追加されております．これにより，ソース画像の白シャツが保持され，パーカーを重ね着したような自然な合成 (試着) が実現できています．なお，本検証では複数の seed 値を試しており，`seed=1` の結果が最も自然だったので，その結果を示しています．

### 検証 2-4

本検証では，検証 2-1 の「試着画像内のマスク領域の境界部分に不自然な継ぎ目が見える課題」を解決できるかを確認します．こちらも，[公式ドキュメント](https://docs.aws.amazon.com/nova/latest/userguide/image-gen-vto.html#image-gen-vto-stitching)を深く確認すると，Virtual try-on のパラメータには合成 (試着) のスタイルを指定する `mergeStyle` が用意されており，`mergeStyle` の設定内で `"SEAMLESS"` を指定することで，マスク画像とソース画像の境界線が目立たないように合成 (試着) することが可能です．

```python
generate_image(
    {
        "taskType": "VIRTUAL_TRY_ON",
        "virtualTryOnParams": {
            "sourceImage": load_image_as_base64(source_img_path),
            "referenceImage": load_image_as_base64(resized_reference_img_path),
            "maskType": "GARMENT",
            "garmentBasedMask": {
                "garmentClass": "UPPER_BODY",
                "maskShape": "BOUNDING_BOX",
                "garmentStyling": {
                    "outerLayerStyle": "OPEN",
                },
            },
            "mergeStyle": "SEAMLESS",
            "returnMask": True,
        },
    },
    seed=1,
)
```

以下に，自動生成されたマスク画像と，試着画像を示します．

| マスク画像                                                                                                                                | 試着画像                                                                                                                             |
| ----------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| ![exp3-2-1_mask_seed=1.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/19c79452-487c-4357-aee5-1d54b8a021fa.png) | ![exp3-2-1_seed=1.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/929dd3e5-150a-4297-a7b1-2e419d672495.png) |

結果として，マスク画像の Bounding Box の形状が，試着画像に継ぎ目として浮き出てくる事象を解消することができました．この点は，検証 2-3 の結果を拡大して比較すると，より明確に確認できます．

## まとめ

本稿では，Virtual try-on の様々な機能について，一つずつ検証しました．検証の結果，ソース画像と試着対象の参照画像を用意し，適切にパラメータを設定することで，かなり自然な試着画像を生成できることを確認しました．

本記事では取り上げておりませんが，ソース画像内の人物のポーズを保持・変更する機能や，衣服以外 (室内の家具等) の配置にも対応しており，Virtual try-on の機能は奥が深いです．

是非，本記事や公式ドキュメントを参考に，Virtual try-on の機能を試してみて下さい！

## おまけ

AWS Community Builders の Swag (帽子) を試着させようとすると，面白い結果が得られました．帽子などのアクセサリーにはまだ対応していないようです．(靴やズボンなどは対応しております．)

生成 AI の想像力 (創造力) はすごいですね笑

| ソース画像                                                                                                                 | 参照画像                                                                                                                              |
| -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| ![human.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/9745df07-7280-46ec-ba57-d5b13d471afd.png) | ![swag_aws_cb_cap.jpg](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/e76a5418-48c9-4bae-b5c2-56706b8913dd.jpeg) |

| マスク画像                                                                                                                               | 試着画像                                                                                                                            |
| ---------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| ![expXXX_mask_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/daed17ab-030f-4135-8d86-81c00d13dfaf.png) | ![expXXX_seed=42.png](https://qiita-image-store.s3.ap-northeast-1.amazonaws.com/0/3792375/a68ac509-127b-4ace-9e25-80c5480bf8a6.png) |

<details><summary>実行コード</summary>

`garmentClass` に `OTHER_UPPER_BODY` (その他の上半身衣服) を指定することで，帽子のマスク画像を生成しようと試みましたが，帽子のマスク画像は生成されず，ソース画像の上半身のマスク画像が生成されてしまいました．

```python
generate_image(
    {
        "taskType": "VIRTUAL_TRY_ON",
        "virtualTryOnParams": {
            "sourceImage": load_image_as_base64(source_img_path),
            "referenceImage": load_image_as_base64(resized_reference_img_path),
            "maskType": "GARMENT",
            "garmentBasedMask": {
                "garmentClass": "OTHER_UPPER_BODY",
            },
            "returnMask": True,
        },
    },
)
```

</details>
